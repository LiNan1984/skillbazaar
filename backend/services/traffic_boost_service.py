"""Traffic Boost service v4.6.

Implements:
- Boost score initialization and exponential decay
- Seller dashboard statistics
"""
from __future__ import annotations

from datetime import datetime

import database as db


# ---------------------------------------------------------------------------
# Boost Score Management
# ---------------------------------------------------------------------------

async def set_boost_on_publish(product_id: int) -> None:
    """Set boost_score=100 for a newly published or republished product."""
    await db.update_product_boost_score(product_id, 100)


async def decay_boost_scores() -> dict:
    """Daily decay: reduce boost by ~14%, zero out if expired (>7 days).

    Returns summary of how many products were decayed vs reset to 0.
    """
    products, _ = await db.fetch_products(page=1, page_size=1000)
    now = datetime.now()
    decayed_count = 0
    reset_count = 0

    for p in products:
        boost = p.get("boost_score") or 0
        if boost <= 0:
            continue

        created_at = p.get("created_at", "")
        days_old = 0
        if created_at:
            try:
                days_old = (now - datetime.fromisoformat(created_at)).days
            except (ValueError, TypeError):
                pass

        if days_old >= 7:
            # Expired: clamp to 0 without decay
            await db.update_product_boost_score(p["id"], 0)
            reset_count += 1
        else:
            # Apply 14% daily decay
            new_boost = max(0, int(boost * 0.86))
            await db.update_product_boost_score(p["id"], new_boost)
            decayed_count += 1

    return {
        "decayed_count": decayed_count,
        "reset_count": reset_count,
        "message": f"Decayed boost scores for {decayed_count} products, reset {reset_count}",
    }


# ---------------------------------------------------------------------------
# Seller Dashboard Stats
# ---------------------------------------------------------------------------

async def get_seller_stats(seller_id: str) -> dict:
    """Aggregate stats for seller dashboard.

    Returns per-product breakdown and totals for the last 30 days.
    """
    # Resolve seller identity
    user = await db.fetch_user(seller_id)
    if not user:
        return {"error": "user not found"}

    seller_name = user.get("username", "")

    # Get all products for this seller
    all_products, _ = await db.fetch_products(page=1, page_size=1000)
    seller_products = [
        p for p in all_products
        if p.get("seller_name") == seller_name
    ]

    product_ids = [p["id"] for p in seller_products]
    total_products = len(seller_products)

    # Aggregate analytics from product_analytics table
    # (product.sales/downloads columns are not maintained by buy flow)
    analytics_map = {}
    if product_ids:
        conn = await db.get_db()
        try:
            placeholders = ",".join("?" for _ in product_ids)
            cursor = await conn.execute(
                f"SELECT product_id, SUM(views) as views, SUM(purchases) as purchases, "
                f"SUM(revenue_cents) as revenue FROM product_analytics "
                f"WHERE product_id IN ({placeholders}) GROUP BY product_id",
                tuple(product_ids),
            )
            rows = await cursor.fetchall()
            for row in rows:
                analytics_map[row[0]] = {
                    "views": row[1] or 0,
                    "purchases": row[2] or 0,
                    "revenue": row[3] or 0,
                }
        finally:
            await conn.close()

    total_views = 0
    total_sales = 0
    total_revenue = 0

    product_items = []
    for p in seller_products:
        pid = p["id"]
        price = p.get("price") or 0
        boost_score = p.get("boost_score") or 0
        a = analytics_map.get(pid, {"views": 0, "purchases": 0, "revenue": 0})

        total_views += a["views"]
        total_sales += a["purchases"]
        total_revenue += a["revenue"]

        product_items.append({
            "product_id": pid,
            "product_name": p.get("name", ""),
            "views": a["views"],
            "purchases": a["purchases"],
            "revenue_cents": a["revenue"],
            "boost_score": boost_score,
        })

    # Sort by views descending
    product_items.sort(key=lambda x: x["views"], reverse=True)

    # Compute conversion rate
    conversion_rate = (total_sales / total_views) if total_views > 0 else 0.0

    return {
        "seller_id": seller_id,
        "total_products": total_products,
        "total_views": total_views,
        "total_downloads": total_views,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "avg_conversion_rate": round(conversion_rate, 4),
        "top_products": product_items,
    }
