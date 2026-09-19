"""Analytics Dashboard v4 service."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import database as db
from models import (
    ProductAnalyticsDashboard,
    CategoryAnalyticsItem,
    CategoryAnalyticsResponse,
    PlatformOverviewResponse,
)


def _parse_period(period: str = "30d") -> tuple[str, str]:
    """Parse period string to start and end dates."""
    days = int(period.replace("d", ""))
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


async def get_product_analytics_dashboard(product_id: int, user_id: str) -> ProductAnalyticsDashboard:
    """Get aggregated analytics for a single product.

    Only the seller of the product can view its analytics.
    Returns total views, purchases, conversion rate, and revenue.
    """
    # Fetch product to verify ownership
    product = await db.fetch_product_by_id(product_id)
    if product is None:
        raise ValueError("Product not found")

    # Verify ownership: the requesting user must be the seller
    if product.get("seller_name") != user_id:
        raise PermissionError("Not authorized to view this product's analytics")

    # Aggregate analytics across all dates
    analytics_data = await db.get_product_analytics_by_date(product_id, "2000-01-01", "2099-12-31")

    total_views = 0
    total_purchases = 0
    total_revenue_cents = 0

    for day in analytics_data:
        total_views += day.get("views", 0)
        total_purchases += day.get("purchases", 0)
        total_revenue_cents += day.get("revenue_cents", 0)

    # Calculate conversion rate
    conversion_rate = (total_purchases / total_views * 100) if total_views > 0 else 0.0

    # Convert cents to coins
    revenue = total_revenue_cents // 100

    return ProductAnalyticsDashboard(
        views=total_views,
        purchases=total_purchases,
        conversion_rate=round(conversion_rate, 2),
        revenue=revenue,
    )


async def get_category_analytics(user_id: str) -> CategoryAnalyticsResponse:
    """Get analytics grouped by product category.

    Returns product count and revenue for each category for the current seller's products.
    """
    # Get products for this seller only
    products = await db.get_seller_products(user_id)

    # Get all product analytics to calculate revenue per product
    category_stats: dict[str, dict] = {}

    for product in products:
        category = product.get("category", "Other")
        if category not in category_stats:
            category_stats[category] = {"product_count": 0, "revenue_cents": 0}
        category_stats[category]["product_count"] += 1

        # Get revenue for this product
        analytics_data = await db.get_product_analytics_by_date(
            product["id"], "2000-01-01", "2099-12-31"
        )
        for day in analytics_data:
            category_stats[category]["revenue_cents"] += day.get("revenue_cents", 0)

    # Convert to response items
    items = []
    for category, stats in category_stats.items():
        revenue = stats["revenue_cents"] // 100
        items.append(CategoryAnalyticsItem(
            category=category,
            product_count=stats["product_count"],
            revenue=revenue,
        ))

    # Sort by product count descending
    items.sort(key=lambda x: x.product_count, reverse=True)

    return CategoryAnalyticsResponse(categories=items)


async def get_platform_overview() -> PlatformOverviewResponse:
    """Get platform-wide overview metrics.

    Returns total products, users, revenue, and top categories.
    """
    # Get total products
    all_products, total_products = await db.fetch_products(category=None, page=1, page_size=1)

    # Get total users
    conn = await db.get_db()
    try:
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM users")
        row = await cursor.fetchone()
        total_users = row["cnt"] if row else 0
    finally:
        await conn.close()

    # Get total revenue from all completed buy transactions
    conn = await db.get_db()
    try:
        cursor = await conn.execute(
            """SELECT COALESCE(SUM(amount), 0) as total
               FROM transactions
               WHERE type = 'buy' AND status = 'completed'"""
        )
        row = await cursor.fetchone()
        total_revenue_cents = row["total"] if row else 0
    finally:
        await conn.close()

    # Convert cents to coins
    total_revenue = total_revenue_cents // 100

    # Get top categories by product count
    category_stats: dict[str, dict] = {}
    for product in all_products:
        category = product.get("category", "Other")
        if category not in category_stats:
            category_stats[category] = {"product_count": 0, "revenue_cents": 0}
        category_stats[category]["product_count"] += 1

    # If we didn't get all products due to pagination, query directly
    if total_products > len(all_products):
        conn = await db.get_db()
        try:
            cursor = await conn.execute(
                "SELECT category, COUNT(*) as cnt FROM products GROUP BY category"
            )
            rows = await cursor.fetchall()
            category_stats = {}
            for row in rows:
                category_stats[row["category"]] = {"product_count": row["cnt"], "revenue_cents": 0}
        finally:
            await conn.close()

    # Get revenue per category
    for category in category_stats:
        conn = await db.get_db()
        try:
            cursor = await conn.execute(
                """SELECT COALESCE(SUM(t.amount), 0) as total
                   FROM transactions t
                   JOIN products p ON t.product_id = p.id
                   WHERE p.category = ? AND t.type = 'buy' AND t.status = 'completed'""",
                (category,),
            )
            row = await cursor.fetchone()
            category_stats[category]["revenue_cents"] = row["total"] if row else 0
        finally:
            await conn.close()

    top_categories = []
    for category, stats in category_stats.items():
        revenue = stats["revenue_cents"] // 100
        top_categories.append(CategoryAnalyticsItem(
            category=category,
            product_count=stats["product_count"],
            revenue=revenue,
        ).model_dump())

    # Sort by product count descending
    top_categories.sort(key=lambda x: x["product_count"], reverse=True)

    return PlatformOverviewResponse(
        total_products=total_products,
        total_users=total_users,
        total_revenue=total_revenue,
        top_categories=top_categories,
    )
