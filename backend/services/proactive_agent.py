from __future__ import annotations

import json
from datetime import datetime

import database as db
import services.product_service as product_service

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = "sk-bV3TVx9azStj8KJe3oW0rsqpaIZKX8E21wyXMtHYCjWBxly1"
LLM_MODEL = "GLM-5.1-FP8"


async def analyze_user_preferences(user_id: str) -> dict:
    """Analyze user behavior to build a preference profile."""
    behaviors = await db.fetch_user_behaviors(user_id, limit=100)
    profile = await db.fetch_user_profile(user_id)

    categories = {}
    keywords = set()
    price_range = {"min": float("inf"), "max": 0}

    for b in behaviors:
        action = b["action"]
        meta = b.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        if action == "browse" and meta.get("category"):
            cat = meta["category"]
            categories[cat] = categories.get(cat, 0) + 1
        if action == "search" and meta.get("keyword"):
            keywords.add(meta["keyword"])
        if action == "buy":
            price = meta.get("price", 0)
            if price > 0:
                price_range["min"] = min(price_range["min"], price)
                price_range["max"] = max(price_range["max"], price)

    preferred_cats = sorted(categories.keys(), key=lambda x: categories[x], reverse=True)[:3]

    return {
        "user_id": user_id,
        "preferred_categories": preferred_cats,
        "search_keywords": list(keywords)[-10:],
        "price_range": {
            "min": price_range["min"] if price_range["min"] != float("inf") else 0,
            "max": price_range["max"] if price_range["max"] > 0 else 1000,
        },
        "total_behaviors": len(behaviors),
        "profile": profile,
    }


async def find_recommendations_for_user(user_id: str, limit: int = 5) -> list[dict]:
    """Find products matching user preferences."""
    prefs = await analyze_user_preferences(user_id)

    all_products = []
    for cat in prefs["preferred_categories"][:2]:
        try:
            result = await product_service.get_products(
                category=cat,
                sort_by="rating",
                page=1,
                page_size=limit,
            )
            all_products.extend([{
                "id": p.id, "name": p.name, "category": p.category,
                "price": p.price, "rating": p.rating,
                "description": p.description[:80] if p.description else "",
            } for p in result.products])
        except Exception:
            pass

    for kw in prefs["search_keywords"][:3]:
        try:
            result = await product_service.get_products(
                keyword=kw,
                sort_by="rating",
                page=1,
                page_size=3,
            )
            all_products.extend([{
                "id": p.id, "name": p.name, "category": p.category,
                "price": p.price, "rating": p.rating,
                "description": p.description[:80] if p.description else "",
            } for p in result.products])
        except Exception:
            pass

    seen = set()
    unique = []
    for p in all_products:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)

    return unique[:limit]


async def generate_push_message(user_id: str, products: list[dict]) -> str:
    """Generate personalized push message using LLM."""
    if not products:
        return ""

    import httpx

    products_text = "\n".join(
        f"- {p['name']} ({p['category']}) ¥{p['price']} 评分{p['rating']}"
        for p in products
    )

    prompt = f"""根据用户偏好推荐商品，生成一条简短的推送消息（50字以内），要吸引人点击查看。

推荐商品：
{products_text}

要求：用中文，亲切自然，像朋友推荐一样。"""

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(LLM_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return msg.get("content", "") or msg.get("reasoning_content", "") or "发现了一些你可能感兴趣的新商品！"
    except Exception:
        return "发现了一些你可能感兴趣的新商品！"


async def push_recommendations_to_user(user_id: str) -> dict:
    """Main entry: analyze user, find products, generate push notification."""
    products = await find_recommendations_for_user(user_id)
    if not products:
        return {"pushed": False, "reason": "no_matching_products"}

    message = await generate_push_message(user_id, products)

    product_ids = ",".join(str(p["id"]) for p in products)
    await db.insert_notification({
        "user_id": user_id,
        "type": "recommendation",
        "title": "为你推荐",
        "content": message,
        "metadata": {"product_ids": product_ids},
    })

    return {"pushed": True, "message": message, "product_count": len(products)}


async def track_user_action(user_id: str, action: str, target_type: str = None,
                             target_id: str = None, metadata: dict = None) -> None:
    """Track user behavior for preference analysis."""
    await db.insert_behavior({
        "user_id": user_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata or {},
    })

    await db.update_last_active(user_id)
