"""Analytics service for Seller Dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import database as db
from models import (
    SellerDashboardResponse,
    TopProduct,
    ProductAnalyticsResponse,
    DailyAnalytics,
    TrafficSource,
)


def _parse_period(period: str = "30d") -> tuple[str, str]:
    """Parse period string to start and end dates."""
    days = int(period.replace("d", ""))
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


async def record_view(product_id: int, user_id: str | None, source: str, session_id: str | None) -> None:
    """Record a product view for analytics."""
    await db.record_product_view(product_id, user_id, source, session_id)


async def get_seller_dashboard(user_id: str, username: str, period: str = "30d", metric: str = "revenue", limit: int = 10) -> SellerDashboardResponse:
    """Get aggregated analytics dashboard for all seller's products."""
    start_date, end_date = _parse_period(period)

    # Get all seller's products
    products = await db.get_seller_products(username)

    # Aggregate metrics
    total_views = 0
    total_purchases = 0
    total_revenue_cents = 0

    for product in products:
        analytics = await db.get_product_analytics_by_date(product["id"], start_date, end_date)
        for day in analytics:
            total_views += day["views"]
            total_purchases += day["purchases"]
            total_revenue_cents += day["revenue_cents"]

    # Calculate conversion rate
    avg_conversion_rate = (total_purchases / total_views * 100) if total_views > 0 else 0.0

    # Get top products
    top_products_data = await db.get_top_products_for_seller(username, metric, limit)
    top_products = [
        TopProduct(
            product_id=p["id"],
            product_name=p["name"],
            views=p["views"],
            purchases=p["purchases"],
            revenue_cents=p["revenue_cents"],
        )
        for p in top_products_data
    ]

    return SellerDashboardResponse(
        total_views=total_views,
        total_purchases=total_purchases,
        total_revenue_cents=total_revenue_cents,
        avg_conversion_rate=round(avg_conversion_rate, 2),
        top_products=top_products,
    )


async def get_product_analytics(product_id: int, seller_name: str, period: str = "30d") -> ProductAnalyticsResponse:
    """Get analytics for a single product."""
    # Verify ownership
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")
    if product["seller_name"] != seller_name:
        raise PermissionError("Not authorized to view this product's analytics")

    start_date, end_date = _parse_period(period)
    analytics_data = await db.get_product_analytics_by_date(product_id, start_date, end_date)

    analytics = [
        DailyAnalytics(
            date=day["date"],
            views=day["views"],
            unique_visitors=day["unique_visitors"],
            cart_adds=day["cart_adds"],
            purchases=day["purchases"],
            revenue_cents=day["revenue_cents"],
            conversion_rate=round((day["purchases"] / day["views"] * 100) if day["views"] > 0 else 0.0, 2),
        )
        for day in analytics_data
    ]

    return ProductAnalyticsResponse(
        product_id=product_id,
        product_name=product["name"],
        analytics=analytics,
    )


async def get_top_products(user_id: str, username: str, metric: str = "revenue", limit: int = 10) -> list[dict]:
    """Get top performing products for a seller."""
    return await db.get_top_products_for_seller(username, metric, limit)
