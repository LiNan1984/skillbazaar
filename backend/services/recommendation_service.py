"""Recommendation service v4.3."""
from __future__ import annotations

from typing import Optional

import database as db


async def get_similar_products(product_id: int, limit: int = 5) -> list[dict]:
    """Get similar products by category."""
    return await db.get_similar_products(product_id, limit)


async def get_frequently_bought_together(product_id: int, limit: int = 5) -> list[dict]:
    """Get products frequently bought together with the given product."""
    return await db.get_frequently_bought_together(product_id, limit)
