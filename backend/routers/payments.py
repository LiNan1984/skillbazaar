"""Payment Integration router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from routers.user_v2 import get_current_user

import services.payment_service as payment_service
from models import (
    PaymentOrderCreate,
    PaymentCallbackRequest,
    WithdrawalRequest,
)


router = APIRouter(prefix="/api/payments", tags=["payments"])


# ---- Payment Orders ----

@router.post("/orders")
async def create_payment_order(
    body: PaymentOrderCreate,
    user: dict = Depends(get_current_user),
):
    """Create a payment order."""
    try:
        # Get product price
        product = await __import__("database", fromlist=["fetch_product_by_id"]).fetch_product_by_id(body.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        order = await payment_service.create_payment_order(
            user_id=user["id"],
            product_id=body.product_id,
            channel=body.channel,
            amount_cents=product["price"] * 100,
        )
        return order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{payment_id}")
async def get_payment_order(
    payment_id: int,
    user: dict = Depends(get_current_user),
):
    """Query payment order status."""
    order = await payment_service.get_payment_status(payment_id)
    if not order:
        raise HTTPException(status_code=404, detail="Payment order not found")
    return order


@router.post("/callback/{channel}")
async def payment_callback(
    channel: str,
    payload: PaymentCallbackRequest,
):
    """Handle payment gateway callback (webhook)."""
    try:
        order = await payment_service.handle_payment_callback(channel, payload.model_dump())
        return order
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Withdrawals ----

@router.post("/withdraw")
async def request_withdrawal(
    body: WithdrawalRequest,
    user: dict = Depends(get_current_user),
):
    """Request a withdrawal."""
    try:
        withdrawal = await payment_service.request_withdrawal(
            user_id=user["id"],
            amount_coins=body.amount_coins,
            channel=body.channel,
            account_info=body.account_info,
        )
        return withdrawal
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Payment History ----

@router.get("/history")
async def get_payment_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get user's payment history."""
    try:
        history = await payment_service.get_payment_history(user["id"], page, page_size)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/earnings")
async def get_earnings_summary(
    user: dict = Depends(get_current_user),
):
    """Get earnings summary for seller."""
    try:
        summary = await payment_service.get_earnings_summary(user["id"])
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Payment Methods ----

@router.post("/methods")
async def add_payment_method(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Add a payment method."""
    try:
        method = await payment_service.create_payment_method(
            user_id=user["id"],
            channel=body.get("channel", ""),
            account_ref=body.get("account_ref", ""),
            account_name=body.get("account_name", ""),
        )
        return method
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/methods")
async def list_payment_methods(
    user: dict = Depends(get_current_user),
):
    """List user's payment methods."""
    try:
        methods = await payment_service.list_payment_methods(user["id"])
        return [m.model_dump() for m in methods]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/methods/{method_id}")
async def delete_payment_method(
    method_id: int,
    user: dict = Depends(get_current_user),
):
    """Delete a payment method."""
    try:
        success = await payment_service.delete_payment_method(method_id, user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Payment method not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
