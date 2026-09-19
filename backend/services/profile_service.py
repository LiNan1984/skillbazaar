from __future__ import annotations

from models import ProfileResponse, ProfileUpdate, UserProductResponse
import database as db
from services.notification_service import notify


async def get_public_profile(username: str, viewer_id: str | None = None) -> dict | None:
    return await db.get_public_profile(username, viewer_id)


async def update_profile(user_id: str, data: dict) -> dict:
    updated = await db.update_user_profile_extended(user_id, data)
    if not updated:
        return {}
    # Also update users table for display_name if provided
    if "display_name" in data:
        await _update_user_display_name(user_id, data["display_name"])
    return updated


async def _update_user_display_name(user_id: str, display_name: str) -> None:
    db_conn = await db.get_db()
    try:
        await db_conn.execute(
            "UPDATE users SET nickname = ? WHERE id = ?",
            (display_name, user_id),
        )
        await db_conn.commit()
    finally:
        await db_conn.close()


async def follow_user(follower_id: str, following_id: str) -> dict:
    if follower_id == following_id:
        raise ValueError("不能关注自己")
    await db.follow_user(follower_id, following_id)
    # Send notification
    try:
        await notify(
            user_id=following_id,
            notif_type="follow",
            title="新粉丝",
            content="有人关注了你",
        )
    except Exception:
        pass
    return {"following_id": following_id, "is_following": True}


async def unfollow_user(follower_id: str, following_id: str) -> dict:
    await db.unfollow_user(follower_id, following_id)
    return {"following_id": following_id, "is_following": False}


async def get_followers(user_id: str, page: int = 1, page_size: int = 20) -> dict:
    rows, total = await db.get_followers(user_id, page, page_size)
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 1,
    }


async def get_following(user_id: str, page: int = 1, page_size: int = 20) -> dict:
    rows, total = await db.get_following(user_id, page, page_size)
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 1,
    }


async def get_user_products_service(user_id: str, page: int = 1, page_size: int = 20) -> dict:
    products, total = await db.get_user_products(user_id, page, page_size)
    return {
        "items": [UserProductResponse(**p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 1,
    }
