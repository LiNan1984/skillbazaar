"""Skill Subscription API endpoints v4.7.

Endpoints
---------
POST /api/v4/subscriptions/create        — create a new subscription
GET  /api/v4/subscriptions/my            — list current user's subscriptions
POST /api/v4/subscriptions/{id}/cancel   — cancel a subscription
POST /api/v4/subscriptions/{id}/toggle-renew — toggle auto-renew
GET  /api/v4/subscriptions/check         — check subscription status for a product
POST /api/v4/cron/process-subscriptions  — cron: process renewals
GET  /api/v4/seller/subscription-stats   — seller subscription analytics
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse

import services.subscription_service as subscription_service
import services.auth_service as auth_service
from models import (
    SubscriptionCreateRequest,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionCheckResponse,
    SubscriptionProcessResponse,
    SellerSubscriptionStatsResponse,
)

router = APIRouter(tags=["subscription-v4"])


def _map_sub_row(row: dict) -> dict:
    """Map DB row keys (id, auto_renew as int) to API response keys."""
    mapped = dict(row)
    mapped["subscription_id"] = mapped.pop("id")
    # Coerce auto_renew int (0/1) to bool
    mapped["auto_renew"] = bool(mapped.get("auto_renew", 1))
    return mapped


def _map_sub_row_for_list(row: dict) -> dict:
    """Map DB row for list endpoints (includes product info)."""
    mapped = dict(row)
    mapped["subscription_id"] = mapped.pop("id")
    mapped["auto_renew"] = bool(mapped.get("auto_renew", 1))
    # Remove DB-internal keys not needed in list response
    mapped.pop("user_id", None)
    mapped.pop("created_at", None)
    mapped.pop("updated_at", None)
    return mapped


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def get_current_user(authorization: str = Header(None)) -> dict:
    """Get current user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = (
        authorization.replace("Bearer ", "")
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/v4/subscriptions/create", response_model=SubscriptionResponse, status_code=201)
async def create_subscription_endpoint(request: SubscriptionCreateRequest, user: dict = Depends(get_current_user)):
    """Create a new subscription for a product."""
    try:
        result = await subscription_service.create_subscription(
            user_id=user["id"],
            product_id=request.product_id,
            plan=request.plan,
        )
        is_existing = not result.pop("_is_new", True)
        status_code = 200 if is_existing else 201
        return JSONResponse(
            status_code=status_code,
            content=SubscriptionResponse(**_map_sub_row(result)).model_dump(),
        )
    except ValueError as e:
        detail = str(e)
        if "Insufficient" in detail:
            raise HTTPException(status_code=402, detail=detail)
        raise HTTPException(status_code=400, detail=detail)


@router.get("/api/v4/subscriptions/my", response_model=SubscriptionListResponse)
async def get_my_subscriptions_endpoint(user: dict = Depends(get_current_user)):
    """List current user's active subscriptions with product info."""
    subs = await subscription_service.get_my_subscriptions(user["id"])
    return SubscriptionListResponse(subscriptions=[_map_sub_row_for_list(s) for s in subs])


@router.post("/api/v4/subscriptions/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription_endpoint(subscription_id: int, user: dict = Depends(get_current_user)):
    """Cancel an active subscription (access continues until expires_at)."""
    try:
        result = await subscription_service.cancel_subscription(subscription_id, user["id"])
        return SubscriptionResponse(**_map_sub_row(result))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权操作此订阅")


@router.post("/api/v4/subscriptions/{subscription_id}/toggle-renew", response_model=SubscriptionResponse)
async def toggle_auto_renew_endpoint(subscription_id: int, user: dict = Depends(get_current_user)):
    """Toggle auto-renew on/off for a subscription."""
    try:
        result = await subscription_service.toggle_auto_renew(subscription_id, user["id"])
        return SubscriptionResponse(**_map_sub_row(result))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权操作此订阅")


@router.get("/api/v4/subscriptions/check", response_model=SubscriptionCheckResponse)
async def check_subscription_endpoint(product_id: int, user: dict = Depends(get_current_user)):
    """Check if user has active subscription for a product."""
    sub = await subscription_service.check_subscription(user["id"], product_id)
    if sub:
        return SubscriptionCheckResponse(
            has_subscription=True,
            subscription_id=sub["id"],
            plan=sub["plan"],
            expires_at=sub["expires_at"],
            days_remaining=sub.get("days_remaining"),
        )
    return SubscriptionCheckResponse(has_subscription=False)


@router.post("/api/v4/cron/process-subscriptions", response_model=SubscriptionProcessResponse)
async def process_subscriptions_cron():
    """Cron: process subscription renewals and expirations. No auth required."""
    result = await subscription_service.process_renewals()
    return SubscriptionProcessResponse(**result)


@router.get("/api/v4/seller/subscription-stats", response_model=SellerSubscriptionStatsResponse)
async def get_seller_subscription_stats_endpoint(user: dict = Depends(get_current_user)):
    """Get subscription analytics for the seller's products."""
    import database as db
    # Verify seller has at least one product with subscription enabled
    products, _ = await db.fetch_products(page=1, page_size=1000)
    seller_name = user.get("username", "")
    seller_products = [p for p in products if p.get("seller_name") == seller_name]

    stats = await subscription_service.get_seller_subscription_stats(user["id"])
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])
    return SellerSubscriptionStatsResponse(**stats)
