"""New Product Traffic Boost endpoints v4.6.

Endpoints
---------
POST /api/v4/publish/boost-reset  — reset boost score for a product
GET  /api/v4/seller/stats         — seller dashboard stats
POST /api/v4/cron/decay-boost     — daily boost decay (cron)
POST /api/v4/products/{product_id}/republish — republish product, reset boost
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Depends

import services.traffic_boost_service as traffic_boost_service
import services.auth_service as auth_service
from models import (
    SellerStatsResponse,
    BoostDecayResponse,
    BoostResetResponse,
)

router = APIRouter(tags=["traffic-boost-v4"])


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

@router.post("/api/v4/publish/boost-reset", response_model=BoostResetResponse)
async def reset_boost(product_id: int, user: dict = Depends(get_current_user)):
    """Reset boost score for a published product (seller only)."""
    import database as db
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # Verify ownership: seller_name must match current user's username
    seller_name = product.get("seller_name", "")
    if seller_name != user.get("username", ""):
        raise HTTPException(status_code=403, detail="无权操作此商品")

    await traffic_boost_service.set_boost_on_publish(product_id)
    return BoostResetResponse(product_id=product_id, boost_score=100)


@router.get("/api/v4/seller/stats", response_model=SellerStatsResponse)
async def get_seller_stats(user: dict = Depends(get_current_user)):
    """Return dashboard stats for the current seller."""
    stats = await traffic_boost_service.get_seller_stats(user["id"])
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])
    return SellerStatsResponse(**stats)


@router.post("/api/v4/cron/decay-boost", response_model=BoostDecayResponse)
async def decay_boost():
    """Cron endpoint: decay all boost scores (reduce by ~14%, expire after 7 days)."""
    result = await traffic_boost_service.decay_boost_scores()
    return BoostDecayResponse(**result)


@router.post("/api/v4/products/{product_id}/republish")
async def republish_product(product_id: int, user: dict = Depends(get_current_user)):
    """Republish a product and reset its boost score to 100."""
    import database as db
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # Verify ownership
    seller_name = product.get("seller_name", "")
    if seller_name != user.get("username", ""):
        raise HTTPException(status_code=403, detail="无权操作此商品")

    await traffic_boost_service.set_boost_on_publish(product_id)
    return {"ok": True, "product_id": product_id, "boost_score": 100}
