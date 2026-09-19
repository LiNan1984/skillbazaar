"""Advanced search v4 endpoints.

Endpoints
---------
POST   /api/v4/search            – full-text search with optional filters
POST   /api/v4/search/saved      – save a search for later re-use
GET    /api/v4/search/saved      – list all saved searches for the current user
POST   /api/v4/search/saved/{id}/run  – re-run a saved search
DELETE /api/v4/search/saved/{id} – delete a saved search
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Depends

import database as db
import services.auth_service as auth_service
import services.search_service as search_service
from models import (
    SearchRequest, SearchResponse,
    SavedSearchCreate, SavedSearchResponse,
)

router = APIRouter(prefix="/api/v4/search", tags=["search-v4"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(401, "未登录")
    token = (
        authorization.replace("Bearer ", "")
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(401, "登录已过期")
    return user


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Full-text search across product name, description, and content_preview.

    Optional ``filters`` dict keys:
        category  – exact category match
        min_price – minimum price (inclusive)
        max_price – maximum price (inclusive)
    """
    return await search_service.execute_search(req)


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------

@router.post("/saved", response_model=SavedSearchResponse, status_code=201)
async def save_search(
    req: SavedSearchCreate,
    user: dict = Depends(get_current_user),
):
    """Save the current search query + filters for later re-use."""
    search_id = await db.save_search(
        user_id=user["id"],
        name=req.name,
        query=req.query or "",
        filters=req.filters or {},
    )
    return SavedSearchResponse(
        id=search_id,
        user_id=user["id"],
        name=req.name,
        query=req.query or "",
        filters=req.filters or {},
    )


@router.get("/saved", response_model=dict)
async def list_saved_searches(user: dict = Depends(get_current_user)):
    """Return all saved searches for the current user."""
    items = await db.get_saved_searches(user["id"])
    return {"saved_searches": items}


@router.post("/saved/{search_id}/run", response_model=SearchResponse)
async def run_saved_search(
    search_id: int,
    user: dict = Depends(get_current_user),
):
    """Re-execute a previously saved search and return current results."""
    saved = await db.fetch_saved_search(search_id, user["id"])
    if not saved:
        raise HTTPException(404, "已保存的搜索不存在")

    filters: dict[str, Any] = saved.get("filters") or {}
    req = SearchRequest(query=saved.get("query") or "", filters=filters)
    return await search_service.execute_search(req)


@router.delete("/saved/{search_id}")
async def delete_saved_search(
    search_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove a saved search."""
    ok = await db.delete_saved_search(search_id, user["id"])
    if not ok:
        raise HTTPException(404, "已保存的搜索不存在")
    return {"success": True}
