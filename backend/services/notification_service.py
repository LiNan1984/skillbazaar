from __future__ import annotations

import logging

import database as db

logger = logging.getLogger(__name__)


async def notify(user_id: str, notif_type: str, title: str,
                 content: str = "", metadata: dict | None = None) -> None:
    """Insert an in-app notification. Never raises into the caller's flow:
    notification delivery must not break the underlying business action."""
    try:
        await db.insert_notification({
            "user_id": user_id,
            "type": notif_type,
            "title": title,
            "content": content,
            "metadata": metadata or {},
        })
    except Exception:
        logger.exception(
            "Failed to create notification user=%s type=%s", user_id, notif_type,
        )
