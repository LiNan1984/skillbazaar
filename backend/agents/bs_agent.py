from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    classify_intent,
    do_search,
    do_publish,
    do_bounty,
    do_analyze,
    do_chat,
)


def route_by_intent(state: dict) -> str:
    return state.get("intent", "chat")


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("do_search", do_search)
    g.add_node("do_publish", do_publish)
    g.add_node("do_bounty", do_bounty)
    g.add_node("do_analyze", do_analyze)
    g.add_node("do_chat", do_chat)

    g.set_entry_point("classify_intent")
    g.add_conditional_edges("classify_intent", route_by_intent, {
        "search": "do_search",
        "publish": "do_publish",
        "bounty": "do_bounty",
        "analyze": "do_analyze",
        "chat": "do_chat",
        "slot_update": "do_chat",
    })
    g.add_edge("do_search", END)
    g.add_edge("do_publish", END)
    g.add_edge("do_bounty", END)
    g.add_edge("do_analyze", END)
    g.add_edge("do_chat", END)
    return g


_memory = MemorySaver()
_compiled = None


def get_agent():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile(checkpointer=_memory)
    return _compiled


def reset_state():
    """Drop the compiled graph and its in-memory checkpoints (process-restart equivalent)."""
    global _compiled, _memory
    _compiled = None
    _memory = MemorySaver()
