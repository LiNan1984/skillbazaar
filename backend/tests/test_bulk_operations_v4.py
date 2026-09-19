"""Bulk Operations tests — v4.12 (BO-01 ~ BO-10).

Run: cd backend && python3 -m pytest tests/test_bulk_operations_v4.py -q
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest

import aiosqlite

import database as db_mod

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _auth_headers(user_id: str) -> dict:
    return {"X-User-Id": user_id}


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


class TestBulkOperationsV4(unittest.TestCase):
    """Bulk Operations v4.12 feature tests."""

    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)

    def setUp(self):
        """Clear relevant tables before each test."""

        async def _clear():
            conn = await aiosqlite.connect(db_mod.DB_PATH)
            try:
                for tbl in ("bulk_operations", "transactions", "products", "users",
                            "price_history", "skill_versions"):
                    try:
                        await conn.execute(f"DELETE FROM {tbl}")
                    except Exception:
                        pass
                await conn.commit()
            finally:
                await conn.close()

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, _clear).result()
        except RuntimeError:
            asyncio.run(_clear())

    def _register(self, suffix: str) -> tuple[str, str]:
        username = f"bo_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"卖家_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        return uid, uid  # v4 uses X-User-Id header directly

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill", status: str = "inactive") -> int:
        """Create a product with given status (default inactive for publish tests)."""
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 的功能描述",
            "category": category, "price": price, "seller_name": seller_name,
            "status": status,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _get_product_status(self, product_id: int) -> str:
        rows = asyncio.run(_fetchall("SELECT status FROM products WHERE id = ?", (product_id,)))
        self.assertTrue(len(rows) > 0, f"Product {product_id} not found")
        return rows[0]["status"]

    def _get_product_price(self, product_id: int) -> int:
        rows = asyncio.run(_fetchall("SELECT price FROM products WHERE id = ?", (product_id,)))
        self.assertTrue(len(rows) > 0, f"Product {product_id} not found")
        return rows[0]["price"]

    # ---- BO-01 ----

    def test_bulk_publish_products(self):
        """BO-01: Bulk publish multiple unpublished products."""
        seller_id, _ = self._register("bo01")
        pid1 = self._publish(f"卖家_bo01", "BO01 商品A", status="inactive")
        pid2 = self._publish(f"卖家_bo01", "BO01 商品B", status="inactive")
        pid3 = self._publish(f"卖家_bo01", "BO01 商品C", status="inactive")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": [pid1, pid2, pid3]},
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["operation"], "publish")
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["succeeded"], 3)
        self.assertEqual(body["failed"], 0)
        self.assertIn("operation_id", body)

        # Verify products are now active
        self.assertEqual(self._get_product_status(pid1), "active")
        self.assertEqual(self._get_product_status(pid2), "active")
        self.assertEqual(self._get_product_status(pid3), "active")

        # Verify messages
        for res in body["results"]:
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["message"], "已发布")

    # ---- BO-02 ----

    def test_bulk_unpublish_products(self):
        """BO-02: Bulk unpublish multiple published products."""
        seller_id, _ = self._register("bo02")
        pid1 = self._publish(f"卖家_bo02", "BO02 商品A", status="active")
        pid2 = self._publish(f"卖家_bo02", "BO02 商品B", status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "unpublish", "product_ids": [pid1, pid2]},
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["succeeded"], 2)
        self.assertEqual(body["failed"], 0)

        # Verify products are now inactive
        self.assertEqual(self._get_product_status(pid1), "inactive")
        self.assertEqual(self._get_product_status(pid2), "inactive")

    # ---- BO-03 ----

    def test_bulk_price_update_percentage(self):
        """BO-03: Bulk price update by percentage."""
        seller_id, _ = self._register("bo03")
        pid1 = self._publish(f"卖家_bo03", "BO03 商品A", price=100, status="active")
        pid2 = self._publish(f"卖家_bo03", "BO03 商品B", price=200, status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={
                "operation": "price_update",
                "product_ids": [pid1, pid2],
                "params": {"percentage": 10},
            },
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["succeeded"], 2)
        self.assertEqual(body["failed"], 0)

        # Verify prices increased by 10%
        self.assertEqual(self._get_product_price(pid1), 110)
        self.assertEqual(self._get_product_price(pid2), 220)

    # ---- BO-04 ----

    def test_bulk_price_update_amount(self):
        """BO-04: Bulk price update by fixed amount."""
        seller_id, _ = self._register("bo04")
        pid1 = self._publish(f"卖家_bo04", "BO04 商品A", price=100, status="active")
        pid2 = self._publish(f"卖家_bo04", "BO04 商品B", price=100, status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={
                "operation": "price_update",
                "product_ids": [pid1, pid2],
                "params": {"amount": -20},
            },
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["succeeded"], 2)

        # Verify prices decreased by ¥20
        self.assertEqual(self._get_product_price(pid1), 80)
        self.assertEqual(self._get_product_price(pid2), 80)

    # ---- BO-05 ----

    def test_bulk_price_minimum_respected(self):
        """BO-05: Price doesn't go below ¥1."""
        seller_id, _ = self._register("bo05")
        pid1 = self._publish(f"卖家_bo05", "BO05 商品A", price=5, status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={
                "operation": "price_update",
                "product_ids": [pid1],
                "params": {"amount": -10},
            },
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["succeeded"], 1)
        # Price should be clamped to ¥1
        self.assertEqual(self._get_product_price(pid1), 1)

    # ---- BO-06 ----

    def test_bulk_delete_soft_delete(self):
        """BO-06: Delete is a soft delete (sets status='inactive')."""
        seller_id, _ = self._register("bo06")
        pid1 = self._publish(f"卖家_bo06", "BO06 商品A", status="active")
        pid2 = self._publish(f"卖家_bo06", "BO06 商品B", status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "delete", "product_ids": [pid1, pid2]},
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["succeeded"], 2)

        # Verify products are soft-deleted (status = inactive)
        self.assertEqual(self._get_product_status(pid1), "inactive")
        self.assertEqual(self._get_product_status(pid2), "inactive")

        # Verify they still exist in DB (not actually deleted)
        rows = asyncio.run(_fetchall("SELECT COUNT(*) as cnt FROM products WHERE id IN (?, ?)", (pid1, pid2)))
        self.assertEqual(rows[0]["cnt"], 2)

    # ---- BO-07 ----

    def test_bulk_rejects_other_sellers_products(self):
        """BO-07: Cannot operate on another seller's products."""
        seller_a_id, _ = self._register("bo07a")
        seller_b_id, _ = self._register("bo07b")

        # Seller A creates a product
        pid_a = self._publish(f"卖家_bo07a", "BO07 A的商品", status="active")
        # Seller B creates a product
        pid_b = self._publish(f"卖家_bo07b", "BO07 B的商品", status="active")

        # Seller A tries to bulk operate on both
        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": [pid_a, pid_b]},
            headers=_auth_headers(seller_a_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "partial")
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["failed"], 1)

        # Find the failed result
        failed_results = [res for res in body["results"] if res["status"] == "failed"]
        self.assertEqual(len(failed_results), 1)
        self.assertEqual(failed_results[0]["product_id"], pid_b)
        self.assertIn("无权操作", failed_results[0]["message"])

    # ---- BO-08 ----

    def test_bulk_more_than_fifty_rejected(self):
        """BO-08: 51+ products returns 400."""
        seller_id, _ = self._register("bo08")
        pids = []
        for i in range(51):
            pids.append(self._publish(f"卖家_bo08", f"BO08 商品{i+1}", status="inactive"))

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": pids},
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 400, r.text)
        body = r.json()
        self.assertIn("error", body)

    # ---- BO-09 ----

    def test_bulk_operation_history(self):
        """BO-09: History endpoint returns paginated results."""
        seller_id, _ = self._register("bo09")
        pid1 = self._publish(f"卖家_bo09", "BO09 商品A", status="inactive")
        pid2 = self._publish(f"卖家_bo09", "BO09 商品B", status="active")

        # Execute a publish operation
        r1 = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": [pid1]},
            headers=_auth_headers(seller_id),
        )
        self.assertEqual(r1.status_code, 200, r1.text)

        # Execute an unpublish operation
        r2 = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "unpublish", "product_ids": [pid2]},
            headers=_auth_headers(seller_id),
        )
        self.assertEqual(r2.status_code, 200, r2.text)

        # Get history
        r = self.client.get(
            "/api/v4/products/bulk/history?page=1&limit=20",
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["limit"], 20)
        self.assertEqual(len(body["operations"]), 2)

        # Verify operations are ordered newest first
        self.assertEqual(body["operations"][0]["operation"], "unpublish")
        self.assertEqual(body["operations"][1]["operation"], "publish")

        # Verify operation fields
        for op in body["operations"]:
            self.assertIn("id", op)
            self.assertIn("operation", op)
            self.assertIn("status", op)
            self.assertIn("total", op)
            self.assertIn("succeeded", op)
            self.assertIn("failed", op)
            self.assertIn("created_at", op)

    # ---- BO-10 ----

    def test_bulk_invalid_operation_rejected(self):
        """BO-10: Unknown operation type returns 400."""
        seller_id, _ = self._register("bo10")
        pid1 = self._publish(f"卖家_bo10", "BO10 商品A", status="inactive")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "invalid_op", "product_ids": [pid1]},
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 400, r.text)
        body = r.json()
        self.assertIn("error", body)

    # ---- Additional tests ----

    def test_bulk_requires_auth(self):
        """Missing X-User-Id header returns 401."""
        pid = self._publish("test_seller", "AuthTest 商品", status="inactive")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": [pid]},
        )

        self.assertEqual(r.status_code, 401, r.text)
        body = r.json()
        self.assertIn("error", body)

    def test_bulk_empty_product_ids_rejected(self):
        """Empty product_ids returns 400."""
        seller_id, _ = self._register("bo_empty")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": []},
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 400, r.text)
        body = r.json()
        self.assertIn("error", body)

    def test_bulk_mixed_ownership_results_in_partial(self):
        """Mixed ownership results in partial status with some failures."""
        seller_a_id, _ = self._register("bo_mix_a")
        seller_b_id, _ = self._register("bo_mix_b")

        pid_a = self._publish(f"卖家_bo_mix_a", "BO Mix A", status="active")
        pid_b = self._publish(f"卖家_bo_mix_b", "BO Mix B", status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "unpublish", "product_ids": [pid_a, pid_b]},
            headers=_auth_headers(seller_a_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "partial")
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["failed"], 1)

    def test_bulk_price_update_nonexistent_product(self):
        """Non-existent product ID is counted as failure."""
        seller_id, _ = self._register("bo_nonexist")
        pid_real = self._publish(f"卖家_bo_nonexist", "BO 真实", price=100, status="active")
        pid_fake = 99999

        r = self.client.post(
            "/api/v4/products/bulk",
            json={
                "operation": "price_update",
                "product_ids": [pid_real, pid_fake],
                "params": {"amount": 10},
            },
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["failed"], 1)

        failed_results = [res for res in body["results"] if res["status"] == "failed"]
        self.assertEqual(len(failed_results), 1)
        self.assertEqual(failed_results[0]["product_id"], pid_fake)
        self.assertIn("不存在", failed_results[0]["message"])

    def test_bulk_history_pagination(self):
        """History pagination works correctly."""
        seller_id, _ = self._register("bo_pag")
        pid1 = self._publish(f"卖家_bo_pag", "BO Pag 1", status="inactive")
        pid2 = self._publish(f"卖家_bo_pag", "BO Pag 2", status="inactive")

        # Create 2 operations
        self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": [pid1]},
            headers=_auth_headers(seller_id),
        )
        self.client.post(
            "/api/v4/products/bulk",
            json={"operation": "publish", "product_ids": [pid2]},
            headers=_auth_headers(seller_id),
        )

        # Get page 1 with limit 1
        r = self.client.get(
            "/api/v4/products/bulk/history?page=1&limit=1",
            headers=_auth_headers(seller_id),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["limit"], 1)
        self.assertEqual(len(body["operations"]), 1)

    def test_bulk_price_update_negative_percentage_decreases(self):
        """Negative percentage decreases price."""
        seller_id, _ = self._register("bo_negpct")
        pid1 = self._publish(f"卖家_bo_negpct", "BO NegPct", price=100, status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={
                "operation": "price_update",
                "product_ids": [pid1],
                "params": {"percentage": -20},
            },
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 200, r.text)
        # -20% of 100 = 80
        self.assertEqual(self._get_product_price(pid1), 80)

    def test_bulk_price_update_percentage_out_of_range(self):
        """Percentage > 100 returns 400."""
        seller_id, _ = self._register("bo_pctrange")
        pid1 = self._publish(f"卖家_bo_pctrange", "BO PctRange", price=100, status="active")

        r = self.client.post(
            "/api/v4/products/bulk",
            json={
                "operation": "price_update",
                "product_ids": [pid1],
                "params": {"percentage": 150},
            },
            headers=_auth_headers(seller_id),
        )

        self.assertEqual(r.status_code, 400, r.text)


if __name__ == "__main__":
    unittest.main()
