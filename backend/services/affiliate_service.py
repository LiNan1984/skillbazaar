"""Affiliate program service v4.4."""
from __future__ import annotations

from typing import Optional

import database as db


async def generate_affiliate_link(seller_id: str, product_id: int, commission_rate: float = 10.0) -> dict:
    """Generate an affiliate link for a product."""
    return await db.create_affiliate_link(seller_id, product_id, commission_rate)


async def get_affiliate_link(product_id: int, seller_id: str) -> dict | None:
    """Get affiliate link for a product."""
    return await db.get_affiliate_link_for_product(product_id, seller_id)


async def track_click(link_id: int, ip_address: str = None, user_agent: str = None):
    """Track an affiliate link click."""
    await db.track_affiliate_click(link_id, ip_address, user_agent)


async def track_conversion(link_id: int, buyer_id: str, transaction_id: int, product_price: int, commission_rate: float) -> dict:
    """Track an affiliate conversion (purchase)."""
    return await db.track_affiliate_conversion(link_id, buyer_id, transaction_id, product_price, commission_rate)


async def get_affiliate_statistics(product_id: int, seller_id: str) -> dict:
    """Get affiliate statistics for a product."""
    return await db.get_affiliate_stats(product_id, seller_id)
