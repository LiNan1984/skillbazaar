"""Search service – thin async wrappers around database helpers."""

from __future__ import annotations

from typing import Any

import database as db
from models import SearchRequest, SearchResponse


async def execute_search(req: SearchRequest) -> SearchResponse:
    """Run a search query and return structured results."""
    filters: dict[str, Any] = req.filters or {}

    results, total = await db.search_products(
        query=req.query or "",
        category=filters.get("category"),
        min_price=filters.get("min_price"),
        max_price=filters.get("max_price"),
    )

    # Strip internal fields not needed by the client
    for row in results:
        row.pop("compat", None)

    return SearchResponse(results=results, total=total)
