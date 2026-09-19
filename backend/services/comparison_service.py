"""Comparison service v4.10.

Implements:
- Side-by-side comparison data fetching for up to 4 products
- Comparison matrix computation (min/max/avg for numeric fields)
"""
from __future__ import annotations

from typing import Any

import database as db
from models import CompareResponse, CompareProductResponse, compute_eval_badge


def _parse_product_plans(raw: str | None) -> list[dict]:
    """Parse subscription_plans JSON from a product row."""
    if not raw:
        return []
    try:
        import json as _json
        plans = _json.loads(raw)
        if isinstance(plans, list):
            return plans
        return []
    except Exception:
        return []


async def get_comparison_data(product_ids: list[int], user_id: str | None = None) -> dict:
    """Get comparison data for up to 4 products.

    Raises ValueError if more than 4 products or if any product is not found.
    Returns dict matching CompareResponse structure.
    """
    if len(product_ids) > 4:
        raise ValueError(f"最多比较 4 个产品，当前选择了 {len(product_ids)} 个")

    if len(product_ids) == 0:
        raise ValueError("请至少选择 1 个产品进行对比")

    # Fetch all products
    products = []
    for pid in product_ids:
        product = await db.fetch_product_by_id(pid)
        if not product:
            raise ValueError(f"产品 {pid} 不存在")
        products.append(product)

    # Fetch aggregated analytics for each product
    analytics_map: dict[int, dict] = {}
    for pid in product_ids:
        analytics_map[pid] = await db.get_product_analytics_aggregate(pid)

    # Build product responses
    result_products = []
    comparison_matrix: dict[str, list] = {
        "price": [],
        "eval_score": [],
        "sales": [],
        "downloads": [],
    }

    for product in products:
        pid = product["id"]
        analytics = analytics_map.get(pid, {})

        eval_score = product.get("eval_score")
        eval_status = product.get("eval_status")
        eval_badge = compute_eval_badge(eval_score, eval_status)

        sales = product.get("sales", 0) or 0
        downloads = product.get("downloads", 0) or 0

        # Use analytics data if available (from product_analytics)
        analytics_purchases = analytics.get("purchases", 0) or 0
        sales = max(sales, analytics_purchases)

        analytics_views = analytics.get("views", 0) or 0
        downloads = max(downloads, analytics_views)

        subscription_plans = _parse_product_plans(product.get("subscription_plans"))

        product_data = {
            "id": pid,
            "name": product.get("name", ""),
            "price": product.get("price", 0),
            "seller_name": product.get("seller_name", ""),
            "eval_score": eval_score,
            "eval_status": eval_status,
            "eval_badge": eval_badge,
            "category": product.get("category", ""),
            "sales": sales,
            "downloads": downloads,
            "description": product.get("description", ""),
            "features": [],
            "subscription_plans": subscription_plans,
            "created_at": product.get("created_at", ""),
        }
        result_products.append(product_data)

        # Collect raw values for comparison matrix (in product order)
        comparison_matrix["price"].append(product_data["price"])
        comparison_matrix["eval_score"].append(
            eval_score if eval_score is not None else 0.0
        )
        comparison_matrix["sales"].append(sales)
        comparison_matrix["downloads"].append(downloads)

    return {
        "products": result_products,
        "comparison_matrix": comparison_matrix,
    }

