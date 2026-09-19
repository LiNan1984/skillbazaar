"""Payment service for payment integration."""
from __future__ import annotations

import database as db
from models import (
    PaymentOrderResponse,
    WithdrawalResponse,
    PaymentHistoryResponse,
    EarningsSummaryResponse,
    PaymentMethodResponse,
)


async def create_payment_order(user_id: str, product_id: int, channel: str, amount_cents: int) -> PaymentOrderResponse:
    """Create a payment order."""
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")

    order = await db.create_payment_order(user_id, product_id, channel, amount_cents)
    return PaymentOrderResponse(**order)


async def get_payment_status(payment_id: int) -> PaymentOrderResponse | None:
    """Query payment order status."""
    order = await db.get_payment_order(payment_id)
    if order:
        return PaymentOrderResponse(**order)
    return None


async def handle_payment_callback(channel: str, payload: dict) -> PaymentOrderResponse:
    """Handle payment gateway callback."""
    payment_id = payload.get("payment_id")
    status = payload.get("status")
    external_txn_id = payload.get("external_txn_id")

    order = await db.get_payment_order(payment_id)
    if not order:
        raise ValueError("Payment order not found")

    new_status = "completed" if status == "success" else "failed"
    updated = await db.update_payment_status(
        payment_id,
        new_status,
        external_txn_id=external_txn_id,
        gateway_response=payload,
    )

    if not updated:
        raise ValueError("Failed to update payment status")

    return PaymentOrderResponse(**updated)


async def request_withdrawal(user_id: str, amount_coins: int, channel: str, account_info: dict) -> WithdrawalResponse:
    """Request a withdrawal."""
    # Convert coins to cents (1 coin = 1 cent for simplicity)
    amount_cents = amount_coins

    # Check user balance
    user = await db.fetch_user(user_id)
    if not user:
        raise ValueError("User not found")

    if user.get("coins", 0) < amount_coins:
        raise ValueError("Insufficient balance")

    # Deduct coins
    await db.update_user_coins(user_id, user["coins"] - amount_coins)

    # Create withdrawal record
    withdrawal = await db.create_withdrawal(user_id, amount_cents, amount_coins, channel, account_info)
    return WithdrawalResponse(**withdrawal)


async def get_payment_history(user_id: str, page: int = 1, page_size: int = 20) -> PaymentHistoryResponse:
    """Get user's payment history."""
    items, total = await db.get_payment_history(user_id, page, page_size)
    return PaymentHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_earnings_summary(user_id: str) -> EarningsSummaryResponse:
    """Get earnings summary for a seller."""
    summary = await db.get_earnings_summary(user_id)
    return EarningsSummaryResponse(**summary)


async def create_payment_method(user_id: str, channel: str, account_ref: str, account_name: str = "") -> PaymentMethodResponse:
    """Add a payment method."""
    method = await db.create_payment_method(user_id, channel, account_ref, account_name)
    return PaymentMethodResponse(**method)


async def list_payment_methods(user_id: str) -> list[PaymentMethodResponse]:
    """List user's payment methods."""
    methods = await db.get_payment_methods(user_id)
    return [PaymentMethodResponse(**m) for m in methods]


async def delete_payment_method(method_id: int, user_id: str) -> bool:
    """Delete a payment method."""
    return await db.delete_payment_method(method_id, user_id)
