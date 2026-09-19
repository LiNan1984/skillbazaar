from __future__ import annotations

import json
import logging
from typing import Optional

from models import ChatResponse
from agents.bs_agent import get_agent
import database

logger = logging.getLogger(__name__)

# Per-user thread generation; bumping it (on clear) starts a fresh LangGraph thread.
# In-memory is sufficient: a process restart already wipes the MemorySaver state.
_thread_generations: dict[str, int] = {}


def _thread_id(user_id: str) -> str:
    return f"chat:{user_id}:{_thread_generations.get(user_id, 0)}"


async def handle_chat(user_id: str, message: str, card: Optional[dict] = None) -> ChatResponse:
    agent = get_agent()
    # Only send the new message — LangGraph checkpointer accumulates history
    thread_id = _thread_id(user_id)
    state = {
        "messages": [{"role": "user", "content": message}],
        "card": card,
    }
    config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke(state, config)

    reply = result.get("final_reply") or "让我想想..."
    products = result.get("search_results") or []
    agent_card = result.get("card")

    persisted_card: Optional[dict] = None
    if agent_card:
        # v2: match / bounty-prefill / publish / analysis cards win over
        # the legacy flat products list.
        persisted_card = agent_card
    elif products:
        persisted_card = {"type": "products", "products": products}

    # Persistence must never block the main reply (spec FR5)
    try:
        await database.insert_chat_message({
            "user_id": user_id, "role": "user",
            "content": message, "card": None, "thread_id": thread_id,
        })
        await database.insert_chat_message({
            "user_id": user_id, "role": "assistant",
            "content": reply, "card": persisted_card, "thread_id": thread_id,
        })
    except Exception:
        logger.exception("Failed to persist chat messages for user %s", user_id)

    return ChatResponse(
        reply=reply,
        products=products,
        card=persisted_card,
    )


async def get_history(user_id: str, limit: int = 20) -> dict:
    rows = await database.fetch_chat_messages(user_id, limit)
    messages = []
    for row in rows:
        card = None
        if row.get("card"):
            try:
                card = json.loads(row["card"])
            except (ValueError, TypeError):
                card = None
        messages.append({
            "id": row["id"],
            "role": row["role"],
            "content": row.get("content", ""),
            "card": card,
            "thread_id": row.get("thread_id"),
            "created_at": row.get("created_at"),
        })
    return {"messages": messages}


async def clear_history(user_id: str) -> dict:
    await database.clear_chat_messages(user_id)
    _thread_generations[user_id] = _thread_generations.get(user_id, 0) + 1
    return {"success": True}
