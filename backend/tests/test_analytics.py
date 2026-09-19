"""Seller Analytics Dashboard tests (v4 P0).

Tests the analytics API:
  GET /api/seller/dashboard                  - seller overview
  GET /api/seller/products/{id}/analytics   - single product analytics
  GET /api/seller/analytics/export           - export CSV

Follows existing test patterns:
  • Isolated temp SQLite DB (NamedTemporaryFile)
  • TestClient lifespan via setUpClass / tearDownClass
  • _auth(token) header helper
  • asyncio _fetchall / _fetchone DB verifiers
  • unittest.TestCase with descriptive docstrings
"""
from __future__ import annotations

import asyncio
import csv
import io
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _fetchall(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def _fetchone(sql: str, params=()):
    rows = await _fetchall(sql, params)
    return rows[0] if rows else None


class TestSellerAnalytics(unittest.TestCase):
    """Seller analytics: dashboard, product analytics, export, and tracking."""

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
        username = f"an_{suffix}"
        nick = nickname or f"分析师_{suffix}"
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
                 category: str = "Skill", content: str = "") -> dict:
        body: dict = {
            "name": name,
            "description": f"{name} 的功能描述",
            "category": category,
            "price": price,
            "seller_name": seller_name,
        }
        if content:
            body["content_preview"] = content
        r = self.client.post("/api/products", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def _buy(self, buyer: dict, product_id: int) -> dict:
        r = self.client.post(
            "/api/transactions/buy",
            json={"product_id": product_id},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # ---------------------------------------------------------------------------
    # AN-01: record_view_increments_analytics
    # ---------------------------------------------------------------------------

    def test_AN01_record_view_increments_analytics(self):
        """Viewing a product should increment analytics for that date."""
        seller = self._register("seller1", "卖家一")
        buyer = self._register("buyer1", "买家一")
        product = self._publish(seller["username"], "分析测试商品", price=100)

        # View the product (triggers analytics tracking)
        r = self.client.get(f"/api/products/{product['id']}")
        self.assertEqual(r.status_code, 200)

        # Wait a bit for async task to complete
        import time
        time.sleep(0.1)

        # Check that analytics were recorded
        analytics = asyncio.run(_fetchall(
            "SELECT * FROM product_analytics WHERE product_id = ?",
            (product["id"],),
        ))
        self.assertEqual(len(analytics), 1)
        self.assertEqual(analytics[0]["views"], 1)
        self.assertEqual(analytics[0]["product_id"], product["id"])

    # ---------------------------------------------------------------------------
    # AN-02: seller_dashboard_returns_aggregated_metrics
    # ---------------------------------------------------------------------------

    def test_AN02_seller_dashboard_returns_aggregated_metrics(self):
        """Seller dashboard should show aggregated metrics across all products."""
        seller = self._register("seller2", "卖家二")
        buyer = self._register("buyer2", "买家二")

        # Publish two products
        p1 = self._publish(seller["username"], "商品A", price=100)
        p2 = self._publish(seller["username"], "商品B", price=200)

        # View both products
        self.client.get(f"/api/products/{p1['id']}")
        self.client.get(f"/api/products/{p1['id']}")  # 2 views
        self.client.get(f"/api/products/{p2['id']}")

        # Buy one product
        self._buy(buyer, p1["id"])

        # Get dashboard
        r = self.client.get(
            "/api/seller/dashboard",
            headers=_auth(seller["token"]),
            params={"period": "30d"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()

        # Verify aggregated metrics
        self.assertIn("total_views", data)
        self.assertIn("total_purchases", data)
        self.assertIn("total_revenue_cents", data)
        self.assertIn("avg_conversion_rate", data)
        self.assertIn("top_products", data)

        self.assertEqual(data["total_views"], 3)
        self.assertEqual(data["total_purchases"], 1)
        self.assertEqual(data["total_revenue_cents"], 10000)  # 100 * 100

    # ---------------------------------------------------------------------------
    # AN-03: product_analytics_returns_daily_breakdown
    # ---------------------------------------------------------------------------

    def test_AN03_product_analytics_returns_daily_breakdown(self):
        """Product analytics should return daily breakdown with metrics."""
        seller = self._register("seller3", "卖家三")
        buyer = self._register("buyer3", "买家三")
        product = self._publish(seller["username"], "分析商品", price=50)

        # View and buy
        self.client.get(f"/api/products/{product['id']}")
        self.client.get(f"/api/products/{product['id']}")
        self._buy(buyer, product["id"])

        # Get product analytics
        r = self.client.get(
            f"/api/seller/products/{product['id']}/analytics",
            headers=_auth(seller["token"]),
            params={"period": "30d"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()

        self.assertIn("product_id", data)
        self.assertIn("product_name", data)
        self.assertIn("analytics", data)
        self.assertIsInstance(data["analytics"], list)
        self.assertGreater(len(data["analytics"]), 0)

        # Check daily metrics structure
        daily = data["analytics"][0]
        self.assertIn("date", daily)
        self.assertIn("views", daily)
        self.assertIn("purchases", daily)
        self.assertIn("revenue_cents", daily)
        self.assertIn("conversion_rate", daily)

    # ---------------------------------------------------------------------------
    # AN-04: top_products_sorted_by_revenue
    # ---------------------------------------------------------------------------

    def test_AN04_top_products_sorted_by_revenue(self):
        """Top products endpoint should sort by specified metric."""
        seller = self._register("seller4", "卖家四")
        buyer = self._register("buyer4", "买家四")

        # Publish products with different prices
        p1 = self._publish(seller["username"], "低价商品", price=10)
        p2 = self._publish(seller["username"], "高价商品", price=100)
        p3 = self._publish(seller["username"], "中价商品", price=50)

        # Buy each once
        self._buy(buyer, p1["id"])
        self._buy(buyer, p2["id"])
        self._buy(buyer, p3["id"])

        # Get top products by revenue
        r = self.client.get(
            "/api/seller/dashboard",
            headers=_auth(seller["token"]),
            params={"period": "30d", "metric": "revenue", "limit": 2},
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()

        self.assertIn("top_products", data)
        self.assertEqual(len(data["top_products"]), 2)

        # Highest revenue should be first
        self.assertEqual(data["top_products"][0]["product_id"], p2["id"])
        self.assertEqual(data["top_products"][0]["revenue_cents"], 10000)
        self.assertEqual(data["top_products"][1]["product_id"], p3["id"])
        self.assertEqual(data["top_products"][1]["revenue_cents"], 5000)

    # ---------------------------------------------------------------------------
    # AN-05: only_seller_can_view_own_analytics
    # ---------------------------------------------------------------------------

    def test_AN05_only_seller_can_view_own_analytics(self):
        """Only the seller should be able to view their own analytics."""
        seller = self._register("seller5", "卖家五")
        attacker = self._register("attacker5", "攻击者五")
        product = self._publish(seller["username"], "私有商品", price=100)

        # Attacker tries to view seller's analytics
        r = self.client.get(
            f"/api/seller/products/{product['id']}/analytics",
            headers=_auth(attacker["token"]),
            params={"period": "30d"},
        )
        self.assertEqual(r.status_code, 403, r.text)

        # Seller can view their own analytics
        r = self.client.get(
            f"/api/seller/products/{product['id']}/analytics",
            headers=_auth(seller["token"]),
            params={"period": "30d"},
        )
        self.assertEqual(r.status_code, 200, r.text)

    # ---------------------------------------------------------------------------
    # AN-06: analytics_tracks_search_clicks
    # ---------------------------------------------------------------------------

    def test_AN06_analytics_tracks_search_clicks(self):
        """Search clicks should be tracked in analytics."""
        seller = self._register("seller6", "卖家六")
        product = self._publish(seller["username"], "搜索商品", price=50)

        # Simulate search impression and click via analytics service
        # (We'll call the database functions directly since search integration
        # will be implemented separately)
        today = "2026-09-19"

        # Record search impression
        asyncio.run(db_mod.increment_search_impression(product["id"]))
        # Record search click
        asyncio.run(db_mod.increment_search_click(product["id"]))

        # Check analytics
        analytics = asyncio.run(_fetchone(
            "SELECT * FROM product_analytics WHERE product_id = ? AND date = ?",
            (product["id"], today),
        ))
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics["search_impressions"], 1)
        self.assertEqual(analytics["search_clicks"], 1)

    # ---------------------------------------------------------------------------
    # Additional: CSV export test
    # ---------------------------------------------------------------------------

    def test_analytics_export_csv(self):
        """Export endpoint should return valid CSV."""
        seller = self._register("seller_export", "导出测试")
        buyer = self._register("buyer_export", "购买测试")
        product = self._publish(seller["username"], "导出商品", price=75)

        # Create some activity
        self.client.get(f"/api/products/{product['id']}")
        self._buy(buyer, product["id"])

        # Export CSV
        r = self.client.get(
            "/api/seller/analytics/export",
            headers=_auth(seller["token"]),
            params={"period": "30d"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.headers["content-type"], "text/csv; charset=utf-8")

        # Parse CSV
        content = r.content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        self.assertGreater(len(rows), 0)
        self.assertIn("date", rows[0])
        self.assertIn("views", rows[0])


if __name__ == "__main__":
    unittest.main()
