"""Bulk Trial Run tests — v4.11 (BT-01 ~ BT-08).

Run: cd backend && python3 -m pytest tests/test_bulk_trial_v4.py -q
"""
from __future__ import annotations

import tempfile
import unittest

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
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def _fetchone(sql: str, params=()):
    rows = await _fetchall(sql, params)
    return rows[0] if rows else None


class TestBulkTrialV4(unittest.TestCase):
    """Bulk Trial v4.11 feature tests."""

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
                for tbl in ("trial_runs", "transactions", "products"):
                    try:
                        await conn.execute(f"DELETE FROM {tbl}")
                    except Exception:
                        pass
                await conn.commit()
            finally:
                await conn.close()

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, _clear).result()
        except RuntimeError:
            asyncio.run(_clear())

    def _register(self, suffix: str) -> tuple[str, str]:
        username = f"bt_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"批量_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return uid, login.json()["token"]

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill") -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 的功能描述",
            "category": category, "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _buy(self, product_id: int, buyer_token: str) -> bool:
        r = self.client.post(
            "/api/transactions/buy",
            json={"product_id": product_id},
            headers=_auth(buyer_token),
        )
        self.assertEqual(r.status_code, 200, r.text)
        return True

    def _trial_single(self, product_id: int, token: str, input_text: str = "test") -> dict:
        r = self.client.post(
            "/api/v4/trial/run",
            json={"product_id": product_id, "input_text": input_text},
            headers=_auth(token),
        )
        return r

    # ---- BT-01 ----

    def test_bulk_trial_two_products(self):
        """BT-01: Both products trialed successfully."""
        seller_id, _ = self._register("seller_bt01")
        pid1 = self._publish(seller_id, "BT01 商品A", price=50)
        pid2 = self._publish(seller_id, "BT01 商品B", price=50)

        buyer_id, buyer_token = self._register("buyer_bt01")

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": [pid1, pid2], "input_text": "帮我分析"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["succeeded"], 2)
        self.assertEqual(body["skipped"], 0)
        self.assertEqual(len(body["results"]), 2)

        for res in body["results"]:
            self.assertEqual(res["status"], "completed")
            self.assertIsNotNone(res["output_text"])
            self.assertIsNotNone(res["trial_id"])

    # ---- BT-02 ----

    def test_bulk_trial_five_products(self):
        """BT-02: Max 5 products allowed."""
        seller_id, _ = self._register("seller_bt02")
        pids = []
        for i in range(5):
            pids.append(self._publish(seller_id, f"BT02 商品{i+1}", price=50))

        buyer_id, buyer_token = self._register("buyer_bt02")

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": pids, "input_text": "批量测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 5)
        self.assertEqual(body["succeeded"], 5)
        self.assertEqual(body["skipped"], 0)
        self.assertEqual(len(body["results"]), 5)

    # ---- BT-03 ----

    def test_bulk_trial_more_than_five_rejected(self):
        """BT-03: 6+ products returns 400."""
        seller_id, _ = self._register("seller_bt03")
        pids = []
        for i in range(6):
            pids.append(self._publish(seller_id, f"BT03 商品{i+1}", price=50))

        buyer_id, buyer_token = self._register("buyer_bt03")

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": pids, "input_text": "超限测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 400, r.text)
        body = r.json()
        self.assertIn("error", body)

    # ---- BT-04 ----

    def test_bulk_trial_skips_purchased(self):
        """BT-04: Purchased products are skipped."""
        seller_id, _ = self._register("seller_bt04")
        pid1 = self._publish(seller_id, "BT04 可试用", price=50)
        pid2 = self._publish(seller_id, "BT04 已购买", price=50)

        buyer_id, buyer_token = self._register("buyer_bt04")
        self._buy(pid2, buyer_token)

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": [pid1, pid2], "input_text": "测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["skipped"], 1)

        # Find the skipped result
        skipped_results = [res for res in body["results"] if res["status"] == "skipped"]
        self.assertEqual(len(skipped_results), 1)
        self.assertEqual(skipped_results[0]["product_id"], pid2)
        self.assertIn("已购买", skipped_results[0]["skip_reason"])

    # ---- BT-05 ----

    def test_bulk_trial_skips_over_limit(self):
        """BT-05: Products at trial limit are skipped."""
        seller_id, _ = self._register("seller_bt05")
        pid1 = self._publish(seller_id, "BT05 可试用", price=50)
        pid2 = self._publish(seller_id, "BT05 已达上限", price=50)

        buyer_id, buyer_token = self._register("buyer_bt05")

        # Exhaust trials for pid2 (max 3)
        for _ in range(3):
            self._trial_single(pid2, buyer_token)

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": [pid1, pid2], "input_text": "测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["skipped"], 1)

        skipped_results = [res for res in body["results"] if res["status"] == "skipped"]
        self.assertEqual(len(skipped_results), 1)
        self.assertEqual(skipped_results[0]["product_id"], pid2)
        self.assertIn("已达上限", skipped_results[0]["skip_reason"])

    # ---- BT-06 ----

    def test_bulk_trial_mixed_results(self):
        """BT-06: Some succeed, some skip."""
        seller_id, _ = self._register("seller_bt06")
        pid_ok = self._publish(seller_id, "BT06 可用", price=50)
        pid_bought = self._publish(seller_id, "BT06 已买", price=50)
        pid_limit = self._publish(seller_id, "BT06 上限", price=50)

        buyer_id, buyer_token = self._register("buyer_bt06")

        # Buy one, exhaust trials for another
        self._buy(pid_bought, buyer_token)
        for _ in range(3):
            self._trial_single(pid_limit, buyer_token)

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": [pid_ok, pid_bought, pid_limit], "input_text": "混合测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["skipped"], 2)
        self.assertEqual(len(body["results"]), 3)

    # ---- BT-07 ----

    def test_bulk_eligibility_check(self):
        """BT-07: Returns correct eligibility for each product."""
        seller_id, _ = self._register("seller_bt07")
        pid_ok = self._publish(seller_id, "BT07 可用", price=50)
        pid_bought = self._publish(seller_id, "BT07 已买", price=50)
        pid_limit = self._publish(seller_id, "BT07 上限", price=50)

        buyer_id, buyer_token = self._register("buyer_bt07")

        # Buy one, exhaust trials for another
        self._buy(pid_bought, buyer_token)
        for _ in range(3):
            self._trial_single(pid_limit, buyer_token)

        r = self.client.get(
            f"/api/v4/trial/bulk/eligibility?product_ids={pid_ok},{pid_bought},{pid_limit}",
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["eligible_count"], 1)
        self.assertEqual(body["total_count"], 3)
        self.assertEqual(len(body["products"]), 3)

        # Check individual product eligibility
        product_map = {p["product_id"]: p for p in body["products"]}
        self.assertTrue(product_map[pid_ok]["can_trial"])
        self.assertFalse(product_map[pid_bought]["can_trial"])
        self.assertIn("已购买", product_map[pid_bought]["reason"])
        self.assertFalse(product_map[pid_limit]["can_trial"])
        self.assertIn("已达上限", product_map[pid_limit]["reason"])

    # ---- BT-08 ----

    def test_bulk_trial_nonexistent_product(self):
        """BT-08: Handles non-existent product IDs."""
        seller_id, _ = self._register("seller_bt08")
        pid_real = self._publish(seller_id, "BT08 真实", price=50)
        pid_fake = 99999  # Non-existent

        buyer_id, buyer_token = self._register("buyer_bt08")

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": [pid_real, pid_fake], "input_text": "测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["succeeded"], 1)
        self.assertEqual(body["skipped"], 1)

        skipped_results = [res for res in body["results"] if res["status"] == "skipped"]
        self.assertEqual(len(skipped_results), 1)
        self.assertEqual(skipped_results[0]["product_id"], pid_fake)
        self.assertEqual(skipped_results[0]["skip_reason"], "商品不存在")

    # ---- Additional: empty product_ids ----

    def test_bulk_trial_empty_product_ids_rejected(self):
        """Empty product_ids list returns 400."""
        _, buyer_token = self._register("buyer_bt_empty")

        r = self.client.post(
            "/api/v4/trial/bulk",
            json={"product_ids": [], "input_text": "测试"},
            headers=_auth(buyer_token),
        )

        self.assertEqual(r.status_code, 400, r.text)
        body = r.json()
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
