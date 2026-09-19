"""Search service – thin async wrappers around database helpers."""

from __future__ import annotations

from typing import Any

import database as db
from models import SearchRequest, SearchResponse, compute_eval_badge


async def execute_search(req: SearchRequest) -> SearchResponse:
    """Run a search query and return structured results."""
    filters: dict[str, Any] = req.filters or {}
    # Top-level sort takes precedence over filters.sort_by
    sort_by = req.sort or filters.get("sort_by", "relevance")

    results, total = await db.search_products(
        query=req.query or "",
        category=filters.get("category"),
        min_price=filters.get("min_price"),
        max_price=filters.get("max_price"),
        min_eval_score=filters.get("min_eval_score"),
        sort_by=sort_by,
    )

    # Strip internal fields not needed by the client and compute eval_badge
    for row in results:
        row.pop("compat", None)
        row["eval_badge"] = compute_eval_badge(
            row.get("eval_score"), row.get("eval_status")
        )

    return SearchResponse(results=results, total=total)
