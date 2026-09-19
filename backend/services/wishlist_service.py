"""Wishlist service v4.3."""
from __future__ import annotations

from typing import Optional

import database as db


async def add_to_wishlist(user_id: str, product_id: int) -> dict:
    """Add a product to user's wishlist."""
    # Verify product exists
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")

    item = await db.add_to_wishlist(user_id, product_id)
    if not item:
        raise ValueError("Already in wishlist")
    return item


async def remove_from_wishlist(user_id: str, product_id: int) -> bool:
    """Remove a product from user's wishlist."""
    return await db.remove_from_wishlist(user_id, product_id)


async def get_user_wishlist(user_id: str) -> list[dict]:
    """Get all items in user's wishlist."""
    return await db.get_user_wishlist(user_id)


async def is_in_wishlist(user_id: str, product_id: int) -> bool:
    """Check if a product is in user's wishlist."""
    return await db.is_in_wishlist(user_id, product_id)
