from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from services import discovery_service, mcp_protocol

router = APIRouter(tags=["discovery"])


@router.get("/api/discovery/search")
async def discovery_search(
    query: str = Query("", alias="query"),
    category: str | None = None,
    page: int = 1,
    page_size: int = 10,
):
    return await discovery_service.search_catalog(query, category, page, page_size)


@router.get("/api/discovery/products/{product_id}")
async def discovery_product(product_id: int):
    product = await discovery_service.get_product(product_id)
    if product is None:
        raise HTTPException(404, "商品不存在")
    return product


@router.get("/api/discovery/products/{product_id}/skill.md")
async def discovery_skill_md(product_id: int):
    product = await discovery_service.get_product(product_id)
    if product is None:
        raise HTTPException(404, "商品不存在")
    return PlainTextResponse(product["skill_md"], media_type="text/markdown; charset=utf-8")


@router.get("/api/discovery/bounties")
async def discovery_bounties(status: str | None = "open", page: int = 1, page_size: int = 10):
    return await discovery_service.list_bounties(status=status, page=page, page_size=page_size)


@router.get("/api/discovery/cron")
async def discovery_cron(page: int = 1, page_size: int = 10):
    return await discovery_service.list_cron_products(page=page, page_size=page_size)


@router.post("/api/mcp")
async def mcp_jsonrpc(message: dict):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        raise HTTPException(400, "expected JSON-RPC 2.0 object")
    return await mcp_protocol.handle_mcp(message)
