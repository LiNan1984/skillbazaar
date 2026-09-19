"""FR2 buy endpoint auth tests (B-01 ~ B-04, B-07, H-02).

POST /api/transactions/buy must authenticate via Bearer token only;
buyer identity comes from the token, never from the request body.
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
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def _fetchone(sql: str, params=()):
    rows = await _fetchall(sql, params)
    return rows[0] if rows else None


async def _execute(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        await conn.execute(sql, params)
        await conn.commit()
    finally:
        await conn.close()


class _BuyAuthBase(unittest.TestCase):
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
        username = f"ba_{suffix}"
        nick = nickname or f"买家_{suffix}"
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
        return {"id": uid, "token": login.json()["token"],
                "username": username, "nickname": nick}

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill") -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 的功能描述",
            "category": category, "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _buy(self, token: str | None, product_id: int, body_extra: dict | None = None):
        body = {"product_id": product_id}
        if body_extra:
            body.update(body_extra)
        kwargs = {"json": body}
        if token is not None:
            kwargs["headers"] = _auth(token)
        return self.client.post("/api/transactions/buy", **kwargs)

    def _coins(self, user_id: str) -> int:
        row = asyncio.run(_fetchone("SELECT coins FROM users WHERE id = ?", (user_id,)))
        return row["coins"]

    def _library_ids(self, user: dict) -> list[int]:
        r = self.client.get(f"/api/transactions/library/{user['id']}",
                            headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return [item["id"] for item in r.json()["data"]]

    def _notifs(self, user: dict) -> list[dict]:
        r = self.client.get("/api/v2/notifications", headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["notifications"]


class TestBuyAuth(_BuyAuthBase):
    # ---- B-01 ----
    def test_anonymous_buy_rejected(self):
        seller = self._register("seller_b01")
        pid = self._publish(seller["username"], "B01 鉴权商品", price=80)

        r = self._buy(None, pid)
        self.assertEqual(r.status_code, 401, r.text)

        tx_rows = asyncio.run(_fetchall(
            "SELECT * FROM transactions WHERE product_id = ?", (pid,)))
        wallet_rows = asyncio.run(_fetchall(
            "SELECT * FROM wallet_transactions WHERE ref_id = ? AND type = 'buy'",
            (str(pid),)))
        self.assertEqual(tx_rows, [])
        self.assertEqual(wallet_rows, [])

    # ---- B-02 ----
    def test_buyer_identity_comes_from_token_not_body(self):
        seller = self._register("seller_b02")
        pid = self._publish(seller["username"], "B02 身份商品", price=80)
        user_a = self._register("a_b02")
        user_b = self._register("b_b02")
        coins_b_before = self._coins(user_b["id"])

        # Old client shape: body still carries buyer_id (B's id), token is A's.
        r = self._buy(user_a["token"], pid, body_extra={"buyer_id": user_b["id"]})
        self.assertEqual(r.status_code, 200, r.text)

        self.assertIn(pid, self._library_ids(user_a))
        self.assertNotIn(pid, self._library_ids(user_b))

        self.assertEqual(self._coins(user_b["id"]), coins_b_before)
        self.assertEqual(self._coins(user_a["id"]), 10000 - 80)

        wallet_a = asyncio.run(_fetchall(
            "SELECT * FROM wallet_transactions WHERE user_id = ?", (user_a["id"],)))
        wallet_b = asyncio.run(_fetchall(
            "SELECT * FROM wallet_transactions WHERE user_id = ?", (user_b["id"],)))
        self.assertEqual(len(wallet_a), 1)
        self.assertEqual(wallet_a[0]["amount"], -80)
        self.assertEqual(wallet_b, [])

        b_notifs = self._notifs(user_b)
        self.assertFalse(
            any(n.get("type") == "product_bought" for n in b_notifs),
            "被伪造身份的用户 B 不应收到任何购买通知",
        )

    # ---- B-03 ----
    def test_authenticated_buy_happy_path(self):
        seller = self._register("seller_b03")
        pid = self._publish(seller["username"], "B03 全链路商品", price=50)
        buyer = self._register("buyer_b03")

        r = self._buy(buyer["token"], pid)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["remaining_balance"], 10000 - 50)

        wallet_rows = asyncio.run(_fetchall(
            "SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY id",
            (buyer["id"],),
        ))
        self.assertEqual(len(wallet_rows), 1)
        row = wallet_rows[0]
        self.assertEqual(row["type"], "buy")
        self.assertEqual(row["amount"], -50)
        self.assertEqual(row["balance_after"], 10000 - 50)

        self.assertIn(pid, self._library_ids(buyer))

        buyer_notifs = self._notifs(buyer)
        self.assertTrue(any(n.get("type") == "product_bought" for n in buyer_notifs))
        seller_notifs = self._notifs(seller)
        self.assertTrue(any(n.get("type") == "product_sold" for n in seller_notifs))

    # ---- B-04 ----
    def test_insufficient_balance_402_and_already_purchased_400(self):
        seller = self._register("seller_b04")
        pid = self._publish(seller["username"], "B04 边界商品", price=100)
        poor = self._register("poor_b04")
        asyncio.run(_execute("UPDATE users SET coins = 99 WHERE id = ?", (poor["id"],)))

        with self.subTest("insufficient balance -> 402"):
            r = self._buy(poor["token"], pid)
            self.assertEqual(r.status_code, 402, r.text)
            detail = r.json()["detail"]
            self.assertIn("99", detail)
            self.assertIn("100", detail)
            self.assertEqual(
                asyncio.run(_fetchall(
                    "SELECT * FROM transactions WHERE buyer_id = ?", (poor["id"],))),
                [],
            )
            self.assertEqual(self._coins(poor["id"]), 99)

        with self.subTest("already purchased -> 400"):
            owner = self._register("owner_b04")
            first = self._buy(owner["token"], pid)
            self.assertEqual(first.status_code, 200, first.text)
            second = self._buy(owner["token"], pid)
            self.assertEqual(second.status_code, 400, second.text)

            txs = asyncio.run(_fetchall(
                "SELECT * FROM transactions WHERE buyer_id = ? AND type='buy'",
                (owner["id"],),
            ))
            self.assertEqual(len(txs), 1)
            self.assertEqual(self._coins(owner["id"]), 10000 - 100)

    # ---- B-07 ----
    def test_invalid_token_rejected(self):
        seller = self._register("seller_b07")
        pid = self._publish(seller["username"], "B07 坏 token 商品", price=10)

        for header_value in ("Bearer not.a.real.token", "Bearer ", "Basic abc123"):
            with self.subTest(header=header_value):
                r = self.client.post(
                    "/api/transactions/buy",
                    json={"product_id": pid},
                    headers={"Authorization": header_value},
                )
                self.assertEqual(r.status_code, 401, r.text)

        # All attempts rejected: no transaction for this product was created.
        rows = asyncio.run(_fetchall(
            "SELECT * FROM transactions WHERE product_id = ?", (pid,)))
        self.assertEqual(rows, [])


class TestPurchasedStateServerSide(_BuyAuthBase):
    # ---- H-02 ----
    def test_library_is_per_user_and_repurchase_400(self):
        seller = self._register("seller_h02")
        pid = self._publish(seller["username"], "H02 隔离商品", price=30)
        user_a = self._register("a_h02")
        user_b = self._register("b_h02")

        first = self._buy(user_a["token"], pid)
        self.assertEqual(first.status_code, 200, first.text)

        self.assertIn(pid, self._library_ids(user_a))
        self.assertNotIn(pid, self._library_ids(user_b))

        # Same product can be independently bought by another user.
        b_buy = self._buy(user_b["token"], pid)
        self.assertEqual(b_buy.status_code, 200, b_buy.text)
        self.assertIn(pid, self._library_ids(user_b))

        # Server-side "already purchased" guard.
        a_rebuy = self._buy(user_a["token"], pid)
        self.assertEqual(a_rebuy.status_code, 400, a_rebuy.text)

        # Library/transaction endpoints must not leak across users (IDOR fix).
        anon = self.client.get(f"/api/transactions/library/{user_a['id']}")
        self.assertEqual(anon.status_code, 401, anon.text)
        cross = self.client.get(
            f"/api/transactions/library/{user_a['id']}",
            headers=_auth(user_b["token"]),
        )
        self.assertEqual(cross.status_code, 403, cross.text)
        cross_tx = self.client.get(
            f"/api/transactions/user/{user_a['id']}",
            headers=_auth(user_b["token"]),
        )
        self.assertEqual(cross_tx.status_code, 403, cross_tx.text)


if __name__ == "__main__":
    unittest.main()
