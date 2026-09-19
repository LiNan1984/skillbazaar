"""Product review system tests against the real FastAPI app.

Covers spec 改进项 1 (R-01 ~ R-07): create/list reviews, auth, purchase
eligibility, duplicate conflict, pydantic validation, rating recompute,
pagination and 404. Uses a temp SQLite file, does not mock routers/services.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

import aiosqlite

import database as db_mod

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _fetchall(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await conn.close()


class TestProductReviews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Re-point at this module's temp DB before the app lifespan initialises it
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str, nickname: str = "") -> tuple[str, str, str]:
        username = f"rv_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": nickname or f"昵称_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return uid, login.json()["token"], login.json()["nickname"]

    def _publish_product(self, seller_name: str, name: str, price: int = 100) -> int:
        r = self.client.post(
            "/api/products",
            json={
                "name": name,
                "description": f"{name} 的描述",
                "category": "Skill",
                "price": price,
                "seller_name": seller_name,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _buy(self, token: str, product_id: int):
        r = self.client.post(
            "/api/transactions/buy",
            json={"product_id": product_id},
            headers=_auth(token),
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def _get_reviews(self, product_id: int, token: str | None = None, **params):
        headers = _auth(token) if token else {}
        return self.client.get(f"/api/products/{product_id}/reviews",
                               params=params, headers=headers)

    # ---- R-01 ----
    def test_purchased_user_can_create_review(self):
        seller_id, seller_token, seller_name = self._register("seller_r01")
        product_id = self._publish_product(seller_name, "评价测试商品 R01", 50)
        buyer_id, buyer_token, buyer_nick = self._register("buyer_r01")
        self._buy(buyer_token, product_id)

        r = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 5, "content": "很好用，推荐"},
            headers=_auth(buyer_token),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        review = body.get("review") or body
        self.assertTrue(review.get("id"))
        self.assertEqual(review["rating"], 5)
        self.assertEqual(review["content"], "很好用，推荐")
        self.assertEqual(review.get("nickname"), buyer_nick)
        self.assertTrue(review.get("created_at"))

        listed = self._get_reviews(product_id)
        self.assertEqual(listed.status_code, 200, listed.text)
        lbody = listed.json()
        items = lbody.get("items") or lbody.get("reviews")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["nickname"], buyer_nick)
        self.assertEqual(lbody["summary"]["total"], 1)
        self.assertAlmostEqual(lbody["summary"]["avg_rating"], 5.0, places=1)

        rows = asyncio.run(_fetchall(
            "SELECT * FROM product_reviews WHERE product_id = ?", (product_id,)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user_id"], buyer_id)

    # ---- R-02 ----
    def test_anonymous_review_rejected(self):
        product_id = self._publish_product("rv_anon_seller", "匿名评价拦截 R02")
        r = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 4, "content": "x"},
        )
        self.assertEqual(r.status_code, 401, r.text)
        rows = asyncio.run(_fetchall(
            "SELECT COUNT(*) AS c FROM product_reviews WHERE product_id = ?",
            (product_id,)))
        self.assertEqual(rows[0]["c"], 0)

    # ---- R-03 ----
    def test_non_buyer_review_forbidden(self):
        _, seller_token, seller_name = self._register("seller_r03")
        product_id = self._publish_product(seller_name, "未购评价拦截 R03")
        _, stranger_token, _ = self._register("stranger_r03")

        r = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 4, "content": "没买过"},
            headers=_auth(stranger_token),
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertTrue(r.json().get("detail") or r.json().get("message"))
        rows = asyncio.run(_fetchall(
            "SELECT COUNT(*) AS c FROM product_reviews WHERE product_id = ?",
            (product_id,)))
        self.assertEqual(rows[0]["c"], 0)

    # ---- R-04 ----
    def test_duplicate_review_conflict(self):
        _, _, seller_name = self._register("seller_r04")
        product_id = self._publish_product(seller_name, "重复评价拦截 R04")
        buyer_id, buyer_token, _ = self._register("buyer_r04")
        self._buy(buyer_token, product_id)

        first = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 5, "content": "第一次"},
            headers=_auth(buyer_token),
        )
        self.assertEqual(first.status_code, 200, first.text)

        product_before = self.client.get(f"/api/products/{product_id}").json()

        second = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 1, "content": "改主意了"},
            headers=_auth(buyer_token),
        )
        self.assertEqual(second.status_code, 409, second.text)

        rows = asyncio.run(_fetchall(
            "SELECT * FROM product_reviews WHERE product_id = ? AND user_id = ?",
            (product_id, buyer_id)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["rating"], 5)

        product_after = self.client.get(f"/api/products/{product_id}").json()
        self.assertAlmostEqual(product_before["rating"], product_after["rating"], places=6)

    # ---- R-05 ----
    def test_invalid_rating_and_content_422(self):
        _, _, seller_name = self._register("seller_r05")
        product_id = self._publish_product(seller_name, "非法评价参数 R05")
        buyer_id, buyer_token, _ = self._register("buyer_r05")
        self._buy(buyer_token, product_id)

        cases = [
            {"rating": 0, "content": "ok"},
            {"rating": 6, "content": "ok"},
            {"rating": "5", "content": "ok"},
            {"rating": 5, "content": "x" * 501},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                r = self.client.post(
                    f"/api/products/{product_id}/reviews",
                    json=payload, headers=_auth(buyer_token),
                )
                self.assertEqual(r.status_code, 422, r.text)

        rows = asyncio.run(_fetchall(
            "SELECT COUNT(*) AS c FROM product_reviews WHERE product_id = ?",
            (product_id,)))
        self.assertEqual(rows[0]["c"], 0)

    # ---- R-06 ----
    def test_review_recomputes_product_rating(self):
        _, _, seller_name = self._register("seller_r06")
        product_id = self._publish_product(seller_name, "均分回写商品 R06", 10)

        b1_id, b1_token, _ = self._register("buyer1_r06")
        b2_id, b2_token, _ = self._register("buyer2_r06")
        self._buy(b1_token, product_id)
        self._buy(b2_token, product_id)

        r1 = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 1, "content": "差"},
            headers=_auth(b1_token),
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        detail_one = self.client.get(f"/api/products/{product_id}").json()
        self.assertAlmostEqual(detail_one["rating"], 1.0, delta=0.1)

        r2 = self.client.post(
            f"/api/products/{product_id}/reviews",
            json={"rating": 3, "content": "一般"},
            headers=_auth(b2_token),
        )
        self.assertEqual(r2.status_code, 200, r2.text)

        detail = self.client.get(f"/api/products/{product_id}").json()
        listed = self.client.get(
            "/api/products", params={"keyword": "均分回写商品 R06"}).json()
        listed_product = next(p for p in listed["products"] if p["id"] == product_id)
        self.assertAlmostEqual(detail["rating"], 2.0, delta=0.1)
        self.assertAlmostEqual(listed_product["rating"], 2.0, delta=0.1)

        summary = self._get_reviews(product_id).json()["summary"]
        self.assertAlmostEqual(summary["avg_rating"], detail["rating"], places=2)
        self.assertEqual(summary["total"], 2)

    # ---- R-07 ----
    def test_review_list_pagination_summary_and_404(self):
        _, _, seller_name = self._register("seller_r07")
        product_id = self._publish_product(seller_name, "评价分页 R07", 10)
        for i in range(3):
            bid, token, _ = self._register(f"buyer_r07_{i}")
            self._buy(token, product_id)
            r = self.client.post(
                f"/api/products/{product_id}/reviews",
                json={"rating": i + 3, "content": f"评价{i}"},
                headers=_auth(token),
            )
            self.assertEqual(r.status_code, 200, r.text)

        page1 = self._get_reviews(product_id, page=1, page_size=2)
        self.assertEqual(page1.status_code, 200, page1.text)
        b1 = page1.json()
        self.assertEqual(len(b1["items"]), 2)
        self.assertEqual(b1["total"], 3)
        self.assertGreaterEqual(b1["pages"], 2)
        self.assertAlmostEqual(b1["summary"]["avg_rating"], 4.0, places=1)
        self.assertEqual(b1["summary"]["total"], 3)

        page2 = self._get_reviews(product_id, page=2, page_size=2)
        self.assertEqual(page2.status_code, 200, page2.text)
        self.assertEqual(len(page2.json()["items"]), 1)

        missing = self._get_reviews(999999)
        self.assertEqual(missing.status_code, 404, missing.text)


if __name__ == "__main__":
    unittest.main()
