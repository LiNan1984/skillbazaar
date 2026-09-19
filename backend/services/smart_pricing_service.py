"""Smart Pricing Suggestions service v4.5.1.

Implements market-based price suggestions and price trend analysis.
Uses simple statistical computations — no external ML library required.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import database as db


# ---------------------------------------------------------------------------
# Price Suggestion
# ---------------------------------------------------------------------------

async def get_price_suggestion(product_id: int | None = None, category: str | None = None) -> dict:
    """Return a data-informed price suggestion based on competitor analysis.

    One of *product_id* or *category* must be provided.
    """
    if product_id is not None and category is not None:
        raise ValueError("请仅提供 product_id 或 category，不要同时提供")
    if product_id is None and not category:
        raise ValueError("请提供 product_id 或 category")

    if product_id is not None:
        product = await db.fetch_product_by_id(product_id)
        if not product:
            raise ValueError("商品不存在")
        category = product.get("category", "")
        if not category:
            raise ValueError("该商品分类为空，无法提供定价建议")

    products, _ = await db.fetch_products(page=1, page_size=10000)
    competitors = []
    for p in products:
        if p.get("category") != category:
            continue
        if p.get("status") != "active":
            continue
        if product_id is not None and p.get("id") == product_id:
            continue
        competitors.append(p)

    competitors_count = len(competitors)
    if competitors_count == 0:
        raise ValueError("该分类暂无商品数据")

    prices = sorted([c["price"] for c in competitors])
    market_avg = _median(prices)
    competitor_min = prices[0]
    competitor_max = prices[-1]

    price_min = max(1, math.floor(market_avg * 0.80))
    price_max = math.ceil(market_avg * 1.20)

    confidence = None
    if product_id is not None:
        product = await db.fetch_product_by_id(product_id)
        rating = product.get("rating", 4.0)
        downloads = product.get("downloads", 0)
        rating_factor = _rating_factor(rating)
        downloads_factor = _downloads_factor(downloads)
        combined = max(0.80, min(1.20, rating_factor * downloads_factor))
        suggested_price = max(1, round(market_avg * combined))
        price_min = max(1, round(market_avg * 0.80 * combined))
        price_max = round(market_avg * 1.20 * combined)

    if competitors_count < 3:
        confidence = "low"
        price_min = max(1, math.floor(market_avg * 0.60))
        price_max = math.ceil(market_avg * 1.40)

    # Ensure the price range always encompasses all competitor prices
    price_min = min(price_min, competitor_min)
    price_max = max(price_max, competitor_max)

    if product_id is not None:
        pass  # suggested_price already set above
    else:
        suggested_price = max(1, round(market_avg))

    if confidence == "low":
        reason = f"同类商品样本较少（{competitors_count}个），建议范围较宽，仅供参考"
    elif product_id is not None:
        pct_change = _pct_change(market_avg, suggested_price)
        direction = "上浮" if pct_change > 0 else "下调"
        pct_str = f"{abs(pct_change):.0f}%"
        reason = f"同类商品中位价为 ¥{market_avg:.0f}，共 {competitors_count} 个竞品，建议价格{direction} {pct_str}"
    else:
        reason = f"同类商品中位价为 ¥{market_avg:.0f}，共 {competitors_count} 个竞品，建议定价 ¥{suggested_price}"

    result = {
        "suggested_price": suggested_price,
        "price_range": {"min": price_min, "max": price_max},
        "reason": reason,
        "market_avg": round(market_avg, 2),
        "competitors_count": competitors_count,
    }
    if confidence:
        result["confidence"] = confidence
    return result


# ---------------------------------------------------------------------------
# Price Trends
# ---------------------------------------------------------------------------

async def get_category_trends(category: str, days: int = 30) -> dict:
    """Return price statistics and trend direction for a category."""
    if days < 1 or days > 365:
        raise ValueError("days 参数必须在 1-365 之间")

    products, _ = await db.fetch_products(page=1, page_size=10000)
    category_products = [
        p for p in products
        if p.get("category") == category and p.get("status") == "active"
    ]

    if not category_products:
        raise ValueError("该分类暂无商品数据")

    prices = [p["price"] for p in category_products]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    price_trend = "stable"
    if days >= 14:
        cutoff = datetime.utcnow() - timedelta(days=days / 2)
        first_half = []
        second_half = []
        for p in category_products:
            created = p.get("created_at")
            if not created:
                continue
            try:
                pdt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if pdt < cutoff:
                first_half.append(p["price"])
            else:
                second_half.append(p["price"])

        if first_half and second_half:
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            if avg_first > 0:
                if avg_second > avg_first * 1.05:
                    price_trend = "up"
                elif avg_second < avg_first * 0.95:
                    price_trend = "down"

    return {
        "category": category,
        "avg_price": round(avg_price, 2),
        "min_price": min_price,
        "max_price": max_price,
        "price_trend": price_trend,
        "sample_count": len(category_products),
        "period_days": days,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _median(sorted_values: list[float]) -> float:
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return float(sorted_values[n // 2])
    return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2.0


def _rating_factor(rating: float) -> float:
    if rating >= 4.8:
        return 1.10
    if rating >= 4.5:
        return 1.05
    if rating >= 4.0:
        return 1.00
    return 0.90


def _downloads_factor(downloads: int) -> float:
    if downloads >= 10000:
        return 1.05
    if downloads >= 1000:
        return 1.03
    if downloads >= 100:
        return 1.00
    return 0.97


def _pct_change(baseline: float, new_value: float) -> float:
    if baseline == 0:
        return 0.0
    return ((new_value - baseline) / baseline) * 100
