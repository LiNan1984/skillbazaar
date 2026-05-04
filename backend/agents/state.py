from __future__ import annotations

import operator
from typing import TypedDict, Optional, List, Dict, Any, Annotated


class AgentState(TypedDict):
    messages: Annotated[List[dict], operator.add]  # accumulates across turns
    intent: str                    # search / publish / bounty / analyze / chat / slot_update
    card: Optional[dict]           # {type, step, data}
    card_updates: dict             # slot updates from user text
    search_params: dict
    search_results: list
    final_reply: str
    products_json: str
