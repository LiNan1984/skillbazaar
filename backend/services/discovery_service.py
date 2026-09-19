"""Machine-facing catalog discovery used by REST and MCP (reuses product/bounty services)."""
from __future__ import annotations

import services.bounty_service as bounty_service
import services.product_service as product_service
from services.manifest_service import product_to_manifest, product_to_skill_md


def _enrich(product) -> dict:
    data = product.model_dump() if hasattr(product, "model_dump") else dict(product)
    return {
        **data,
        "manifest": product_to_manifest(data),
        "skill_md": product_to_skill_md(data),
    }


async def search_catalog(
    query: str = "",
    category: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    result = await product_service.get_products(
        category=category or None,
        keyword=query or None,
        page=page,
        page_size=page_size,
    )
    payload = result.model_dump()
    payload["products"] = [_enrich(p) for p in result.products]
    return payload


async def get_product(product_id: int) -> dict | None:
    product = await product_service.get_product_by_id(product_id)
    if product is None:
        return None
    return _enrich(product)


async def list_bounties(status: str | None = "open", page: int = 1, page_size: int = 10) -> dict:
    return await bounty_service.get_bounties(status=status or None, page=page, page_size=page_size)


async def list_cron_products(page: int = 1, page_size: int = 10) -> dict:
    return await search_catalog(category="Cron", page=page, page_size=page_size)
