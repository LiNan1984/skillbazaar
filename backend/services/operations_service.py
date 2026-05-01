from __future__ import annotations

import json
from datetime import datetime

import database as db


async def log_skill_event(
    product_id: int,
    action: str,
    actor_id: str = None,
    old_data: dict = None,
    new_data: dict = None,
    reason: str = "",
) -> int:
    """Log a skill lifecycle event."""
    return await db.insert_lifecycle_event({
        "product_id": product_id,
        "action": action,
        "actor_id": actor_id,
        "old_data": json.dumps(old_data, ensure_ascii=False) if old_data else None,
        "new_data": json.dumps(new_data, ensure_ascii=False) if new_data else None,
        "reason": reason,
    })


async def notify_seller_followers(seller_id: str, product_id: int, event_type: str) -> None:
    """Notify users who bought from this seller about new products."""
    library = await db.fetch_user_library("")
    buyers = set()
    for item in library:
        if item.get("seller_id") == seller_id:
            buyers.add(item["buyer_id"])

    for buyer_id in buyers:
        await db.insert_notification({
            "user_id": buyer_id,
            "type": "seller_update",
            "title": "关注的卖家有新动态",
            "content": f"卖家发布了新的商品，快来看看吧！",
            "metadata": {"product_id": product_id, "event": event_type},
        })


async def get_skill_lifecycle_timeline(product_id: int) -> list[dict]:
    """Get full lifecycle timeline for a skill."""
    events = await db.fetch_lifecycle_events(product_id, limit=100)
    for event in events:
        if event.get("old_data"):
            try:
                event["old_data"] = json.loads(event["old_data"])
            except Exception:
                pass
        if event.get("new_data"):
            try:
                event["new_data"] = json.loads(event["new_data"])
            except Exception:
                pass
    return events


async def check_and_notify_price_drop(product_id: int, old_price: int, new_price: int) -> None:
    """Notify users who browsed this product if the price dropped."""
    if new_price >= old_price:
        return

    behaviors = await db.fetch_user_behaviors("", limit=10000)
    interested_users = set()
    for b in behaviors:
        if b["action"] == "browse" and str(b.get("target_id")) == str(product_id):
            interested_users.add(b["user_id"])

    for uid in interested_users:
        await db.insert_notification({
            "user_id": uid,
            "type": "price_drop",
            "title": "价格下降提醒",
            "content": f"你关注的商品降价了！从 ¥{old_price} 降至 ¥{new_price}",
            "metadata": {"product_id": product_id, "old_price": old_price, "new_price": new_price},
        })
