from __future__ import annotations

from typing import Optional

from models import ChatResponse
from agents.bs_agent import get_agent


async def handle_chat(user_id: str, message: str, card: Optional[dict] = None) -> ChatResponse:
    agent = get_agent()
    # Only send the new message — LangGraph checkpointer accumulates history
    state = {
        "messages": [{"role": "user", "content": message}],
        "card": card,
    }
    config = {"configurable": {"thread_id": user_id}}

    result = await agent.ainvoke(state, config)

    reply = result.get("final_reply", "让我想想...")
    card_result = result.get("card")

    return ChatResponse(
        reply=reply,
        products=[],
        card=card_result,
    )
