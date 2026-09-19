"""Review & Ratings service — v4.13.

Business logic for creating, updating, deleting, listing, voting on reviews,
and computing review summaries.
"""
from __future__ import annotations

import database as db
from fastapi import HTTPException


async def create_review(user_id: str, product_id: int, rating: int,
                        title: str | None, content: str, order_ref: str | None = None) -> dict:
    """Create a review for a purchased product.

    Rules:
    - User must have purchased the product (transactions table).
    - Seller cannot review their own product.
    - One review per (user, product) pair.
    """
    # Check purchase
    already_purchased = await db.check_already_purchased(user_id, product_id)
    if not already_purchased:
        raise HTTPException(status_code=403, detail="仅购买过的用户可以评价")

    # Check seller
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    if product.get("seller_name") == user_id:
        raise HTTPException(status_code=403, detail="无法评价自己的商品")

    # Check duplicate
    existing = await db.fetch_product_review(product_id, user_id)
    if existing:
        raise HTTPException(status_code=400, detail="您已评价过此商品")

    # Insert
    data = {
        "product_id": product_id,
        "user_id": user_id,
        "order_ref": order_ref,
        "rating": rating,
        "title": title,
        "content": content,
    }
    review_id = await db.insert_product_review(data)

    # Fetch the created review with user info
    review = await _fetch_review_detail(review_id)
    return review


async def update_review(review_id: int, user_id: str, rating: int | None,
                        title: str | None, content: str | None) -> dict:
    """Update an existing review. Only the author can update."""
    existing = await _fetch_review_by_id(review_id)
    if not existing:
        raise HTTPException(status_code=404, detail="评价不存在")
    if existing["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权修改此评价")

    update_data = {}
    if rating is not None:
        update_data["rating"] = rating
    if title is not None:
        update_data["title"] = title
    if content is not None:
        update_data["content"] = content

    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    ok = await db.update_product_review(review_id, user_id, update_data)
    if not ok:
        raise HTTPException(status_code=404, detail="评价不存在")

    # Recompute product rating
    product = await db.fetch_product_by_id(existing["product_id"])
    if product:
        await db.update_product_rating(existing["product_id"])

    updated = await _fetch_review_detail(review_id)
    return updated


async def delete_review(review_id: int, user_id: str) -> dict:
    """Soft-delete a review. Only the author can delete."""
    existing = await _fetch_review_by_id(review_id)
    if not existing:
        raise HTTPException(status_code=404, detail="评价不存在")
    if existing["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权删除此评价")

    ok = await db.soft_delete_product_review(review_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="评价不存在")

    # Recompute product rating
    product = await db.fetch_product_by_id(existing["product_id"])
    if product:
        await db.update_product_rating(existing["product_id"])

    return {"success": True}


async def list_reviews(product_id: int, page: int = 1, limit: int = 10) -> dict:
    """List active reviews for a product, sorted newest-first."""
    reviews, total = await db.fetch_product_reviews(product_id, page=page, page_size=limit)

    result = []
    for r in reviews:
        helpful_count = (await db.get_review_helpful_count(r["id"])).get("helpful", 0)
        result.append({
            "id": r["id"],
            "product_id": r["product_id"],
            "user_id": r["user_id"],
            "user_nickname": r.get("nickname", ""),
            "user_avatar": r.get("avatar"),
            "rating": r["rating"],
            "title": r.get("title"),
            "content": r["content"],
            "helpful_count": helpful_count,
            "created_at": r.get("created_at"),
        })

    return {
        "reviews": result,
        "total": total,
        "page": page,
        "limit": limit,
    }


async def vote_review(review_id: int, user_id: str, vote: str) -> dict:
    """Vote a review as helpful or unhelpful."""
    if vote not in ("helpful", "unhelpful"):
        raise HTTPException(status_code=400, detail="vote 必须为 helpful 或 unhelpful")

    existing = await _fetch_review_by_id(review_id)
    if not existing or existing.get("status") != "active":
        raise HTTPException(status_code=404, detail="评价不存在")

    await db.insert_review_vote(review_id, user_id, vote)

    helpful_count = (await db.get_review_helpful_count(review_id)).get("helpful", 0)
    return {"review_id": review_id, "vote": vote, "helpful_count": helpful_count}


async def get_review_summary(product_id: int) -> dict:
    """Get summary stats for a product's reviews."""
    summary = await db.fetch_review_summary(product_id)
    return {
        "product_id": product_id,
        "average_rating": summary["average_rating"],
        "total_reviews": summary["total_reviews"],
        "distribution": summary["distribution"],
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

async def _fetch_review_by_id(review_id: int) -> dict | None:
    """Fetch a single review by ID."""
    from database import get_db
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM product_reviews WHERE id = ?", (review_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def _fetch_review_detail(review_id: int) -> dict | None:
    """Fetch review detail with user info."""
    from database import get_db
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """
            SELECT r.*, u.nickname, u.avatar
            FROM product_reviews r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE r.id = ?
            """,
            (review_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        helpful_count = (await db.get_review_helpful_count(review_id)).get("helpful", 0)
        return {
            "id": d["id"],
            "product_id": d["product_id"],
            "user_id": d["user_id"],
            "user_nickname": d.get("nickname", ""),
            "user_avatar": d.get("avatar"),
            "rating": d["rating"],
            "title": d.get("title"),
            "content": d["content"],
            "helpful_count": helpful_count,
            "created_at": d.get("created_at"),
        }
    finally:
        await conn.close()
