from __future__ import annotations

from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    messages: list[dict]
    intent: str
    search_params: dict
    search_results: list[dict]
    iteration: int
    final_reply: str
    products_json: str
