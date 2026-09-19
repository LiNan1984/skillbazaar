"""Semantic Search v4.5 endpoints.

Endpoints
---------
POST /api/v4/search/semantic – semantic similarity search (public)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models import SemanticSearchRequest, SemanticSearchResponse
import services.semantic_search_service as semantic_search_service

router = APIRouter(prefix="/api/v4/search/semantic", tags=["semantic-search-v4.5"])


@router.post("", response_model=SemanticSearchResponse)
async def semantic_search(req: SemanticSearchRequest):
    """Semantic similarity search across all products.

    The query is converted to a deterministic hash-based embedding and
    compared (cosine similarity) against every indexed product embedding.
    Results are returned sorted by descending similarity score.

    **Request body**
        - ``query``: search text (minimum 2 characters)
        - ``limit``: max results to return (default 10, max 50)
    """
    query = (req.query or "").strip()
    if len(query) < 2:
        return SemanticSearchResponse(results=[])

    limit = min(req.limit or 10, 50)
    results = await semantic_search_service.search_by_text(query, limit=limit)
    return SemanticSearchResponse(results=results)
