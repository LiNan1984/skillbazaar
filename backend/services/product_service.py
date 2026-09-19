from __future__ import annotations

import json
import math

from models import ProductResponse, ProductList, EvalReportResponse
import database
from services.manifest_service import derive_compat


class ProductNotFoundError(Exception):
    pass


class NotPurchasedError(Exception):
    pass


class DuplicateReviewError(Exception):
    pass


async def get_products(
    category: str | None = None,
    sub_category: str | None = None,
    keyword: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    sort_by: str = "downloads",
    page: int = 1,
    page_size: int = 20,
    runtime: str | None = None,
) -> ProductList:
    if runtime:
        # Use runtime filter - product_service doesn't know about compat derivation
        products, total = await database.fetch_products_by_runtime(runtime, page, page_size)
        # Derive compat for products that don't have it set
        derived = []
        for p in products:
            if not p.get("compat"):
                p["compat"] = json.dumps(derive_compat(p), ensure_ascii=False)
            derived.append(ProductResponse(**p))
        return ProductList(total=total, page=page, page_size=page_size, products=derived)

    products, total = await database.fetch_products(
        category=category,
        sub_category=sub_category,
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    products = [dict(p) for p in products]
    for p in products:
        p["tags"] = _normalize_tags(p.get("tags"))
    return ProductList(
        total=total,
        page=page,
        page_size=page_size,
        products=[ProductResponse(**p) for p in products],
    )


def _normalize_tags(tags):
    if not tags:
        return "[]"
    if isinstance(tags, list):
        return json.dumps(tags, ensure_ascii=False)
    if isinstance(tags, str):
        tags = tags.strip()
        if tags.startswith('['):
            return tags
        if tags.startswith('{'):
            return tags
        return json.dumps([t.strip() for t in tags.split(',') if t.strip()], ensure_ascii=False)
    return json.dumps(list(tags), ensure_ascii=False)


async def get_product_by_id(product_id: int) -> ProductResponse | None:
    product = await database.fetch_product_by_id(product_id)
    if product is None:
        return None
    # Derive compat if not set (read-side derivation, no DB write)
    if not product.get("compat"):
        product["compat"] = json.dumps(derive_compat(product), ensure_ascii=False)
    product["tags"] = _normalize_tags(product.get("tags"))
    return ProductResponse(**product)


async def create_product(data: dict) -> ProductResponse:
    product_id = await database.insert_product(data)
    # Set boost_score=100 for new products (v4.6 traffic boost)
    await database.update_product_boost_score(product_id, 100)
    product = await database.fetch_product_by_id(product_id)
    if product and not product.get("compat"):
        product["compat"] = json.dumps(derive_compat(product), ensure_ascii=False)
    product["tags"] = _normalize_tags(product.get("tags"))
    return ProductResponse(**product)


async def get_category_tree() -> list[dict]:
    return await database.fetch_category_tree()


# ---------- Reviews ----------

def _serialize_review(row: dict) -> dict:
    return {
        "id": row["id"],
        "product_id": row["product_id"],
        "user_id": row["user_id"],
        "rating": row["rating"],
        "content": row.get("content", ""),
        "nickname": row.get("nickname"),
        "avatar": row.get("avatar"),
        "created_at": row.get("created_at"),
    }


async def list_reviews(product_id: int, page: int = 1, page_size: int = 10) -> dict | None:
    product = await database.fetch_product_by_id(product_id)
    if product is None:
        return None
    rows, total = await database.fetch_product_reviews(product_id, page, page_size)
    summary = await database.fetch_review_summary(product_id)
    return {
        "items": [_serialize_review(r) for r in rows],
        "summary": summary,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size else 1,
    }


async def create_review(user: dict, product_id: int, rating: int, content: str) -> dict:
    product = await database.fetch_product_by_id(product_id)
    if product is None:
        raise ProductNotFoundError("商品不存在")

    eligible = await database.user_has_purchased_product(user["id"], product_id)
    if not eligible:
        raise NotPurchasedError("只有购买过该商品的用户才能评价")

    existing = await database.fetch_product_review(product_id, user["id"])
    if existing is not None:
        raise DuplicateReviewError("您已评价过该商品")

    await database.insert_product_review({
        "product_id": product_id,
        "user_id": user["id"],
        "rating": rating,
        "content": (content or "").strip(),
    })
    row = await database.fetch_product_review(product_id, user["id"])
    summary = await database.fetch_review_summary(product_id)
    item = _serialize_review({**row, "nickname": user.get("nickname"),
                              "avatar": user.get("avatar")})
    return {"review": item, "summary": summary}
