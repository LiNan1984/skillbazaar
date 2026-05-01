from __future__ import annotations

import math
from datetime import datetime

import database as db


async def calculate_dynamic_price(product: dict) -> dict:
    """Calculate dynamic price based on demand, quality, and time factors."""
    base_price = product.get("base_price") or product.get("price") or 100
    pricing_model = product.get("pricing_model", "fixed")
    current_price = product.get("price", base_price)

    if pricing_model == "fixed":
        return {
            "current_price": product["price"],
            "base_price": base_price,
            "pricing_model": "fixed",
            "demand_score": 0,
            "price_trend": "stable",
        }

    downloads = product.get("downloads", 0)
    sales = product.get("sales", 0)
    rating = product.get("rating", 4.0)

    # Demand factor: log-scale based on downloads + sales
    demand_raw = math.log10(max(downloads, 1)) * 0.3 + math.log10(max(sales, 1)) * 0.7
    demand_factor = min(max(demand_raw / 3.0, 0.5), 3.0)  # Clamp between 0.5x - 3.0x

    # Quality factor: rating-based
    quality_factor = max(0.8, min(rating / 4.0, 1.5))  # 0.8x - 1.5x

    # Time decay: older products get slight discount (unless high demand)
    created_at = product.get("created_at", "")
    time_factor = 1.0
    if created_at:
        try:
            days_old = (datetime.now() - datetime.fromisoformat(created_at)).days
            if days_old > 90 and demand_raw < 2:
                time_factor = max(0.7, 1.0 - (days_old - 90) * 0.002)
        except (ValueError, TypeError):
            pass

    dynamic_price = int(base_price * demand_factor * quality_factor * time_factor)
    dynamic_price = max(1, dynamic_price)

    demand_score = round(demand_raw, 2)

    old_price = product["price"]
    if dynamic_price != old_price:
        trend = "up" if dynamic_price > old_price else "down"
        await db.update_product_price(product["id"], dynamic_price, demand_score)
        await db.insert_price_history({
            "product_id": product["id"],
            "old_price": old_price,
            "new_price": dynamic_price,
            "pricing_model": pricing_model,
            "demand_score": demand_score,
            "reason": f"demand={demand_factor:.2f} quality={quality_factor:.2f} time={time_factor:.2f}",
        })
    else:
        trend = "stable"

    return {
        "current_price": dynamic_price,
        "base_price": base_price,
        "pricing_model": pricing_model,
        "demand_score": demand_score,
        "price_trend": trend,
    }


async def recalculate_all_dynamic_prices() -> list[dict]:
    """Recalculate prices for all dynamic-priced products."""
    products, _ = await db.fetch_products(page_size=1000)
    results = []
    for p in products:
        if p.get("pricing_model") == "dynamic":
            result = await calculate_dynamic_price(p)
            results.append(result)
    return results


async def get_price_analysis(product_id: int) -> dict:
    """Get price analysis for a product including history."""
    product = await db.fetch_product_by_id(product_id)
    if not product:
        return None

    pricing_info = await calculate_dynamic_price(product)
    history = await db.fetch_price_history(product_id)

    return {
        **pricing_info,
        "price_history": history[:20],
    }
