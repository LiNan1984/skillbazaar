from __future__ import annotations

from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes import (
    understand_intent,
    extract_params,
    search_products,
    evaluate_results,
    generate_reply,
)


def _should_search(state: dict) -> str:
    if state.get("intent") == "chat":
        return "end"
    return "search"


def _should_retry(state: dict) -> str:
    results = state.get("search_results", [])
    iteration = state.get("iteration", 0)
    if len(results) < 3 and iteration < 2:
        return "retry"
    return "reply"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("extract_params", extract_params)
    graph.add_node("search_products", search_products)
    graph.add_node("evaluate_results", evaluate_results)
    graph.add_node("generate_reply", generate_reply)

    graph.set_entry_point("understand_intent")
    graph.add_conditional_edges("understand_intent", _should_search, {
        "search": "extract_params",
        "end": END,
    })
    graph.add_edge("extract_params", "search_products")
    graph.add_edge("search_products", "evaluate_results")
    graph.add_conditional_edges("evaluate_results", _should_retry, {
        "retry": "search_products",
        "reply": "generate_reply",
    })
    graph.add_edge("generate_reply", END)
    return graph.compile()


_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_graph()
    return _agent
