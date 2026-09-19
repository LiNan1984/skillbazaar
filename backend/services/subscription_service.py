"""Subscription service v4.7.

Implements:
- Subscription creation with coin deduction
- Subscription lifecycle (cancel, toggle auto-renew)
- Subscription querying (user's subs, access check)
- Cron renewal/expiry processing
- Seller subscription analytics
"""
from __future__ import annotations

from datetime import datetime, timedelta
import database as db


PLAN_DURATIONS = {
    "weekly": 7,
    "monthly": 30,
    "yearly": 365,
}


async def create_subscription(user_id: str, product_id: int, plan: str) -> dict:
    """Create a new subscription or return existing active one.

    Raises ValueError on validation errors.
    Returns dict with subscription data.
    """
    plan = plan.lower()
    if plan not in PLAN_DURATIONS:
        raise ValueError(f"Invalid plan: {plan}. Must be one of {list(PLAN_DURATIONS.keys())}")

    # Verify product exists and allows subscriptions
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")
    if product.get("status") != "active":
        raise ValueError("Product is not available")

    is_sub = product.get("is_subscription", 0)
    if not is_sub:
        raise ValueError("This product does not support subscriptions")

    # Validate plan against product's configured plans
    plans = await db.get_product_subscription_plans(product_id)
    plan_prices = {p["plan"]: p["price"] for p in plans}
    if plan not in plan_prices:
        raise ValueError(f"Plan '{plan}' not available for this product")

    price = plan_prices[plan]

    # Check for existing active subscription
    existing = await db.fetch_active_subscription(user_id, product_id)
    if existing:
        existing["_is_new"] = False
        return existing

    # Check user balance
    user_data = await _fetch_user(user_id)
    if not user_data:
        raise ValueError("User not found")
    coins = user_data.get("coins", 0)
    if coins < price:
        raise ValueError(f"Insufficient coins: have {coins}, need {price}")

    # Deduct coins
    new_coins = coins - price
    await db.update_user_coins(user_id, new_coins)

    # Create subscription
    now = datetime.utcnow()
    starts_at = now.isoformat()
    expires_at = (now + timedelta(days=PLAN_DURATIONS[plan])).isoformat()

    subscription = await db.create_subscription_db(
        user_id, product_id, plan, price, starts_at, expires_at
    )
    if not subscription:
        raise ValueError("Failed to create subscription")

    # Record event
    await db.insert_subscription_event(subscription["id"], "created", price)

    subscription["_is_new"] = True
    return subscription


async def _fetch_user(user_id: str) -> dict | None:
    """Fetch user data by ID."""
    db_conn = await db.get_db()
    try:
        cursor = await db_conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db_conn.close()


async def cancel_subscription(subscription_id: int, user_id: str) -> dict:
    """Cancel a subscription (access continues until expires_at).

    Raises ValueError if not found or not owned by user.
    """
    sub = await db.fetch_subscription_by_id(subscription_id)
    if not sub:
        raise ValueError("Subscription not found")
    if sub.get("user_id") != user_id:
        raise PermissionError("Not authorized")
    if sub.get("status") != "active":
        raise ValueError(f"Cannot cancel subscription with status: {sub.get('status')}")

    await db.update_subscription_status(subscription_id, "cancelled")
    await db.insert_subscription_event(subscription_id, "cancelled")

    updated = await db.fetch_subscription_by_id(subscription_id)
    if not updated:
        raise ValueError("Failed to cancel subscription")
    return updated


async def toggle_auto_renew(subscription_id: int, user_id: str) -> dict:
    """Toggle auto-renew flag on a subscription.

    Raises ValueError if not found or not owned by user.
    """
    sub = await db.fetch_subscription_by_id(subscription_id)
    if not sub:
        raise ValueError("Subscription not found")
    if sub.get("user_id") != user_id:
        raise PermissionError("Not authorized")

    updated = await db.toggle_subscription_auto_renew_db(subscription_id)
    if not updated:
        raise ValueError("Failed to toggle auto-renew")

    await db.insert_subscription_event(subscription_id, "toggled_auto_renew")
    return updated


async def get_my_subscriptions(user_id: str) -> list[dict]:
    """Get all active subscriptions for a user with product info."""
    return await db.fetch_user_subscriptions(user_id)


async def check_subscription(user_id: str, product_id: int) -> dict | None:
    """Check if user has an active subscription for a product.

    Returns the subscription dict if active or cancelled-but-not-expired, None otherwise.
    """
    # Try active subscription first
    sub = await db.fetch_active_subscription(user_id, product_id)
    if not sub:
        # Fallback: cancelled subscriptions still grant access until expires_at
        sub = await db.fetch_cancelled_subscription(user_id, product_id)
    if not sub:
        return None

    # Double-check expiry
    expires_at = sub.get("expires_at", "")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            if exp_dt < datetime.utcnow():
                return None
        except (ValueError, TypeError):
            pass

    # Compute days remaining
    days_remaining = None
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            days_remaining = max(0, (exp_dt - datetime.utcnow()).days)
        except (ValueError, TypeError):
            pass

    result = dict(sub)
    result["days_remaining"] = days_remaining
    return result


async def process_renewals() -> dict:
    """Cron: process subscription renewals and expirations.

    Returns summary dict with counts.
    """
    expired_subs = await db.find_expired_subscriptions()
    renewed_count = 0
    expired_count = 0
    payment_failed_count = 0

    for sub in expired_subs:
        sub_id = sub["id"]
        user_id = sub["user_id"]
        product_id = sub["product_id"]
        plan = sub["plan"]
        auto_renew = sub.get("auto_renew", 0)

        if auto_renew:
            # Attempt renewal
            product = await db.fetch_product_by_id(product_id)
            if not product:
                # Product gone, expire the subscription
                await db.update_subscription_status(sub_id, "expired")
                await db.insert_subscription_event(sub_id, "expired")
                expired_count += 1
                continue

            plans = await db.get_product_subscription_plans(product_id)
            plan_prices = {p["plan"]: p["price"] for p in plans}
            price = plan_prices.get(plan, sub["price"])

            user_data = await _fetch_user(user_id)
            if not user_data:
                await db.update_subscription_status(sub_id, "payment_failed")
                await db.insert_subscription_event(sub_id, "payment_failed")
                payment_failed_count += 1
                continue

            coins = user_data.get("coins", 0)
            if coins >= price:
                # Renew: deduct coins, extend expiry
                new_coins = coins - price
                await db.update_user_coins(user_id, new_coins)

                now = datetime.utcnow()
                new_expires = (now + timedelta(days=PLAN_DURATIONS.get(plan, 30))).isoformat()
                await db.update_subscription_expiry(sub_id, new_expires)
                await db.insert_subscription_event(sub_id, "renewed", price)
                renewed_count += 1
            else:
                # Insufficient funds
                await db.update_subscription_status(sub_id, "payment_failed")
                await db.insert_subscription_event(sub_id, "payment_failed")
                payment_failed_count += 1
        else:
            # Manual (non-auto-renew): expire
            await db.update_subscription_status(sub_id, "expired")
            await db.insert_subscription_event(sub_id, "expired")
            expired_count += 1

    message = f"Processed {renewed_count + expired_count + payment_failed_count} subscriptions"
    return {
        "renewed_count": renewed_count,
        "expired_count": expired_count,
        "payment_failed_count": payment_failed_count,
        "message": message,
    }


async def get_seller_subscription_stats(seller_id: str) -> dict:
    """Get subscription analytics for a seller's products."""
    return await db.get_seller_subscription_stats_db(seller_id)
