"""Seller Dashboard service — v4.14.

Business logic for seller dashboard: overview stats, product metrics, and trends.
"""
from __future__ import annotations

import database as db


async def get_dashboard(seller_name: str) -> dict:
    """Get aggregated dashboard stats for a seller."""
    stats = await db.get_seller_total_stats(seller_name)

    # Get top 5 products by revenue
    products, _ = await db.get_seller_product_stats(seller_name, page=1, limit=5, sort="revenue")
    top_products = [
        {"id": p["id"], "name": p["name"], "revenue": p["revenue"], "purchases": p["purchases"]}
        for p in products
    ]

    # Get recent activity (last 7 days of transactions)
    trends = await db.get_seller_trend_data(seller_name, period="7d")
    recent_activity = trends["data"]

    return {
        **stats,
        "top_products": top_products,
        "recent_activity": recent_activity,
    }


async def get_products(seller_name: str, page: int = 1, limit: int = 20, sort: str = "revenue") -> dict:
    """Get seller's products with performance metrics."""
    products, total = await db.get_seller_product_stats(seller_name, page=page, limit=limit, sort=sort)
    return {
        "products": products,
        "total": total,
        "page": page,
        "limit": limit,
    }


async def get_trends(seller_name: str, period: str = "30d") -> dict:
    """Get time-series data for seller's products."""
    return await db.get_seller_trend_data(seller_name, period=period)
