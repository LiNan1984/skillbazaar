"""JSON-RPC MCP surface for SkillBazaar discovery tools (no extra SDK)."""
from __future__ import annotations

import json

from services import discovery_service

SERVER_INFO = {"name": "skillbazaar", "version": "1.0.0"}
PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "search_catalog",
        "description": "Search SkillBazaar catalog of Agent / Skill / Cron / Workflow products.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword"},
                "category": {"type": "string", "description": "Agent, Skill, Cron, or Workflow"},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 50},
            },
        },
    },
    {
        "name": "get_product",
        "description": "Get one catalog product including generated SKILL.md.",
        "inputSchema": {
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        },
    },
    {
        "name": "list_bounties",
        "description": "List SkillBazaar hire/bounty jobs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "page_size": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_cron_products",
        "description": "List Cron subscription products on SkillBazaar.",
        "inputSchema": {
            "type": "object",
            "properties": {"page_size": {"type": "integer"}},
        },
    },
]


def _ok(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _tool_text(payload) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}


async def handle_mcp(message: dict) -> dict:
    req_id = message.get("id")
    method = message.get("method") or ""
    params = message.get("params") or {}

    if method == "initialize":
        return _ok(
            req_id,
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )
    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method == "tools/list":
        return _ok(req_id, {"tools": TOOLS})
    if method == "ping":
        return _ok(req_id, {})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "search_catalog":
                data = await discovery_service.search_catalog(
                    query=args.get("query") or "",
                    category=args.get("category") or None,
                    page_size=int(args.get("page_size") or 10),
                )
            elif name == "get_product":
                data = await discovery_service.get_product(int(args["product_id"]))
                if data is None:
                    return _err(req_id, -32004, "product not found")
            elif name == "list_bounties":
                data = await discovery_service.list_bounties(
                    status=args.get("status") or "open",
                    page_size=int(args.get("page_size") or 10),
                )
            elif name == "list_cron_products":
                data = await discovery_service.list_cron_products(
                    page_size=int(args.get("page_size") or 10),
                )
            else:
                return _err(req_id, -32601, f"unknown tool {name}")
        except (KeyError, TypeError, ValueError) as exc:
            return _err(req_id, -32602, str(exc))
        return _ok(req_id, _tool_text(data))
    return _err(req_id, -32601, f"unknown method {method}")
