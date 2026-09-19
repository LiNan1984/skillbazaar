"""Tests for v4.13 Skill Reviews & Ratings feature.

Tests cover:
  1. Create review for purchased product (201)
  2. Create review without purchase (403)
  3. Create duplicate review (400)
  4. Update review
  5. Delete review (soft-delete → 404 on re-list)
  6. List reviews (paginated, sorted newest-first)
  7. Vote helpful / unhelpful
  8. Review summary (avg rating + distribution)
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

import aiosqlite

import database as db_mod
from fastapi.testclient import TestClient

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _x_user_id(user_id: str) -> dict:
    return {"X-User-Id": user_id}


async def _fetchall(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        await conn.commit()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def _fetchone(sql: str, params=()):
    rows = await _fetchall(sql, params)
    return rows[0] if rows else None


class _ReviewsBase(unittest.TestCase):
    """Shared setUp / tearDown for review tests."""

    def setUp(self):
        """Clear review-related tables before each test."""
        async def _clear():
            conn = await aiosqlite.connect(db_mod.DB_PATH)
            try:
                for tbl in (
                    "review_votes",
                    "product_reviews",
                    "transactions",
                    "products",
                    "users",
                ):
                    try:
                        await conn.execute(f"DELETE FROM {tbl}")
                    except Exception:
                        pass
                await conn.commit()
            finally:
                await conn.close()
        asyncio.run(_clear())

    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str, nickname: str = "") -> dict:
        username = f"rev_{suffix}"
        nick = nickname or f"用户_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12", "nickname": nick},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {
            "id": uid,
            "token": login.json()["token"],
            "username": username,
            "nickname": nick,
        }

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill") -> dict:
        body = {
            "name": name,
            "description": f"{name} 的功能描述",
            "category": category,
            "price": price,
            "seller_name": seller_name,
        }
        r = self.client.post("/api/products", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def _buy(self, buyer: dict, product_id: int) -> dict:
        r = self.client.post(
            "/api/transactions/buy",
            json={"product_id": product_id},
            headers={"Authorization": f"Bearer {buyer['token']}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _db_reviews(self, product_id: int = None, user_id: str = None) -> list[dict]:
        if product_id and user_id:
            return asyncio.run(_fetchall(
                "SELECT * FROM product_reviews WHERE product_id = ? AND user_id = ?",
                (product_id, user_id),
            ))
        if product_id:
            return asyncio.run(_fetchall(
                "SELECT * FROM product_reviews WHERE product_id = ?", (product_id,),
            ))
        return asyncio.run(_fetchall("SELECT * FROM product_reviews"))

    def _db_review_votes(self, review_id: int = None) -> list[dict]:
        if review_id:
            return asyncio.run(_fetchall(
                "SELECT * FROM review_votes WHERE review_id = ?", (review_id,),
            ))
        return asyncio.run(_fetchall("SELECT * FROM review_votes"))


# ===========================================================================
# 1. Create Review
# ===========================================================================

class TestCreateReview(_ReviewsBase):
    """REV-01 … REV-03: Create review with and without purchase, duplicate check."""

    def test_create_review_for_purchased_product_returns_201(self):
        """Buyer who purchased a product can create a review (201)."""
        buyer = self._register("buyer01", "买家01")
        seller = self._register("seller01", "卖家01")
        prod = self._publish(seller["username"], "测试商品", price=50)
        self._buy(buyer, prod["id"])

        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 5, "title": "好评", "content": "非常棒的产品！"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        data = r.json()
        self.assertEqual(data["product_id"], prod["id"])
        self.assertEqual(data["user_id"], buyer["id"])
        self.assertEqual(data["rating"], 5)
        self.assertEqual(data["title"], "好评")
        self.assertEqual(data["content"], "非常棒的产品！")
        self.assertEqual(data["helpful_count"], 0)
        self.assertEqual(data["user_nickname"], buyer["nickname"])
        self.assertIn("created_at", data)
        self.assertIn("id", data)

        # Verify DB
        rows = self._db_reviews(prod["id"], buyer["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rating"], 5)
        self.assertEqual(rows[0]["title"], "好评")

    def test_create_review_without_purchase_returns_403(self):
        """User who did NOT purchase the product gets 403."""
        buyer = self._register("nobuy", "未购买者")
        seller = self._register("seller02", "卖家02")
        prod = self._publish(seller["username"], "未购商品", price=50)
        # Do NOT buy

        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 3, "content": "没买过的评价"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertIn("detail", r.json())

    def test_create_duplicate_review_returns_400(self):
        """Second review from same user for same product returns 400."""
        buyer = self._register("dupbuyer", "重复买家")
        seller = self._register("seller03", "卖家03")
        prod = self._publish(seller["username"], "重复评价商品", price=50)
        self._buy(buyer, prod["id"])

        # First review
        r1 = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 4, "content": "第一次评价"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r1.status_code, 201)

        # Duplicate
        r2 = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 5, "content": "第二次评价"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r2.status_code, 400, r2.text)
        self.assertIn("detail", r2.json())


# ===========================================================================
# 2. Update Review
# ===========================================================================

class TestUpdateReview(_ReviewsBase):
    """REV-04: Update own review."""

    def test_update_review_changes_fields(self):
        """Author can update rating, title, and content."""
        buyer = self._register("updater", "修改者")
        seller = self._register("seller04", "卖家04")
        prod = self._publish(seller["username"], "可修改商品", price=50)
        self._buy(buyer, prod["id"])

        # Create
        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 3, "title": "一般", "content": "还行吧"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r.status_code, 201)
        review_id = r.json()["id"]

        # Update
        r2 = self.client.put(
            f"/api/v4/reviews/{review_id}",
            json={"rating": 5, "title": "推荐", "content": "改主意了，很棒！"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        data = r2.json()
        self.assertEqual(data["rating"], 5)
        self.assertEqual(data["title"], "推荐")
        self.assertEqual(data["content"], "改主意了，很棒！")

        # DB verify
        rows = self._db_reviews(prod["id"], buyer["id"])
        self.assertEqual(rows[0]["rating"], 5)
        self.assertEqual(rows[0]["title"], "推荐")

    def test_update_nonexistent_review_returns_404(self):
        """Updating non-existent review returns 404."""
        buyer = self._register("badupdater", "坏修改者")
        r = self.client.put(
            "/api/v4/reviews/99999",
            json={"rating": 5},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r.status_code, 404, r.text)


# ===========================================================================
# 3. Delete Review
# ===========================================================================

class TestDeleteReview(_ReviewsBase):
    """REV-05: Soft-delete review."""

    def test_delete_review_sets_status_inactive(self):
        """Deleting a review sets its status to inactive."""
        buyer = self._register("deleter", "删除者")
        seller = self._register("seller05", "卖家05")
        prod = self._publish(seller["username"], "可删除商品", price=50)
        self._buy(buyer, prod["id"])

        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 2, "content": "不好用"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r.status_code, 201)
        review_id = r.json()["id"]

        # Delete
        r2 = self.client.delete(
            f"/api/v4/reviews/{review_id}",
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)

        # DB verify soft-delete
        rows = self._db_reviews(prod["id"], buyer["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "inactive")

    def test_list_excludes_deleted_reviews(self):
        """Deleted reviews do not appear in the list."""
        buyer = self._register("lister", "列取者")
        seller = self._register("seller06", "卖家06")
        prod = self._publish(seller["username"], "列取商品", price=50)
        self._buy(buyer, prod["id"])

        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 4, "content": "不错"},
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r.status_code, 201)
        review_id = r.json()["id"]

        # Delete
        self.client.delete(
            f"/api/v4/reviews/{review_id}",
            headers=_x_user_id(buyer["id"]),
        )

        # List should be empty
        r2 = self.client.get(
            f"/api/v4/reviews/{prod['id']}",
            headers=_x_user_id(buyer["id"]),
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["total"], 0)


# ===========================================================================
# 4. List Reviews
# ===========================================================================

class TestListReviews(_ReviewsBase):
    """REV-06: Paginated list of active reviews, sorted newest-first."""

    def test_list_reviews_returns_paginated_results(self):
        """Reviews are listed newest-first with pagination."""
        seller = self._register("listseller", "列卖家")
        prod = self._publish(seller["username"], "列取商品2", price=50)

        buyers = [self._register(f"lb{i}", f"买{i}") for i in range(5)]
        for idx, b in enumerate(buyers):
            self._buy(b, prod["id"])
            self.client.post(
                f"/api/v4/reviews/{prod['id']}",
                json={"rating": idx + 1, "content": f"评价{idx}"},
                headers=_x_user_id(b["id"]),
            )

        r = self.client.get(
            f"/api/v4/reviews/{prod['id']}?page=1&limit=3",
            headers=_x_user_id(buyers[0]["id"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["reviews"]), 3)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 3)
        # Newest first
        self.assertEqual(data["reviews"][0]["content"], "评价4")


# ===========================================================================
# 5. Vote Helpful
# ===========================================================================

class TestVoteHelpful(_ReviewsBase):
    """REV-07: Vote a review as helpful / unhelpful."""

    def test_vote_helpful_increments_count(self):
        """Voting helpful increments helpful_count."""
        reviewer = self._register("reviewee", "被评价者")
        voter = self._register("voter01", "投票者01")
        seller = self._register("seller07", "卖家07")
        prod = self._publish(seller["username"], "投票商品", price=50)
        self._buy(reviewer, prod["id"])
        self._buy(voter, prod["id"])

        # Create review
        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 5, "content": "推荐"},
            headers=_x_user_id(reviewer["id"]),
        )
        self.assertEqual(r.status_code, 201)
        review_id = r.json()["id"]

        # Vote helpful
        r2 = self.client.post(
            f"/api/v4/reviews/{review_id}/vote",
            json={"vote": "helpful"},
            headers=_x_user_id(voter["id"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)

        # Verify in DB
        votes = self._db_review_votes(review_id)
        self.assertEqual(len(votes), 1)
        self.assertEqual(votes[0]["vote"], "helpful")

    def test_vote_unhelpful_and_switch_vote(self):
        """User can switch vote from helpful to unhelpful."""
        reviewer = self._register("reviewee2", "被评价者2")
        voter = self._register("voter02", "投票者02")
        seller = self._register("seller08", "卖家08")
        prod = self._publish(seller["username"], "投票商品2", price=50)
        self._buy(reviewer, prod["id"])
        self._buy(voter, prod["id"])

        r = self.client.post(
            f"/api/v4/reviews/{prod['id']}",
            json={"rating": 4, "content": "还行"},
            headers=_x_user_id(reviewer["id"]),
        )
        self.assertEqual(r.status_code, 201)
        review_id = r.json()["id"]

        # Vote helpful
        self.client.post(
            f"/api/v4/reviews/{review_id}/vote",
            json={"vote": "helpful"},
            headers=_x_user_id(voter["id"]),
        )

        # Switch to unhelpful
        r2 = self.client.post(
            f"/api/v4/reviews/{review_id}/vote",
            json={"vote": "unhelpful"},
            headers=_x_user_id(voter["id"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)

        # DB verify only one row, updated
        votes = self._db_review_votes(review_id)
        self.assertEqual(len(votes), 1)
        self.assertEqual(votes[0]["vote"], "unhelpful")


# ===========================================================================
# 6. Review Summary
# ===========================================================================

class TestReviewSummary(_ReviewsBase):
    """REV-08: Review summary with average rating and distribution."""

    def test_review_summary_computes_average_and_distribution(self):
        """Summary returns correct avg, total, and distribution."""
        seller = self._register("sumseller", "总结卖家")
        prod = self._publish(seller["username"], "总结商品", price=50)

        buyers = [self._register(f"sb{i}", f"买{i}") for i in range(5)]
        ratings = [5, 4, 5, 3, 4]
        for b, rating in zip(buyers, ratings):
            self._buy(b, prod["id"])
            self.client.post(
                f"/api/v4/reviews/{prod['id']}",
                json={"rating": rating, "content": f"评{rating}星"},
                headers=_x_user_id(b["id"]),
            )

        r = self.client.get(
            f"/api/v4/reviews/{prod['id']}/summary",
            headers=_x_user_id(buyers[0]["id"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["total_reviews"], 5)
        self.assertAlmostEqual(data["average_rating"], 4.2, places=1)

        dist = data["distribution"]
        self.assertEqual(dist["5"], 2)
        self.assertEqual(dist["4"], 2)
        self.assertEqual(dist["3"], 1)
        self.assertEqual(dist.get("2", 0), 0)
        self.assertEqual(dist.get("1", 0), 0)


if __name__ == "__main__":
    unittest.main()
