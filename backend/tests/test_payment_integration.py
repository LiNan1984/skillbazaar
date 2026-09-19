"""Payment Integration tests (PI-01 ~ PI-09).

Covers: create payment order, query order status, withdrawal request,
payment history, earnings summary, payment methods CRUD.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from fastapi.testclient import TestClient

import database as db_mod

# Isolated temp SQLite DB
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from main import app  # noqa: E402


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class _PaymentBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> dict:
        username = f"pay_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12", "nickname": f"支付_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"], "username": username}

    def _publish(self, seller_name: str, name: str, price: int = 100) -> int:
        r = self.client.post("/api/products", json={
            "name": name,
            "description": f"{name} 的描述",
            "category": "Skill",
            "price": price,
            "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]


class TestPaymentIntegration(_PaymentBase):
    """TDD tests for Payment Integration feature."""

    # ---- PI-01 ----
    def test_create_payment_order_returns_order_details(self):
        """POST /api/payments/orders creates a payment order with status=pending."""
        buyer = self._register("buyer_pi01")
        seller = self._register("seller_pi01")
        pid = self._publish(seller["username"], "PI01 商品", price=100)

        r = self.client.post(
            "/api/payments/orders",
            json={"product_id": pid, "channel": "alipay"},
            headers=_auth(buyer["token"]),
        )
        # Will fail with 404 until router is registered
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["channel"], "alipay")
        self.assertIn("id", body)

    # ---- PI-02 ----
    def test_query_payment_status_returns_current_state(self):
        """GET /api/payments/orders/{id} returns order status."""
        buyer = self._register("buyer_pi02")
        seller = self._register("seller_pi02")
        pid = self._publish(seller["username"], "PI02 商品", price=200)

        create_r = self.client.post(
            "/api/payments/orders",
            json={"product_id": pid, "channel": "wechat"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 200, create_r.text)
        payment_id = create_r.json()["id"]

        query_r = self.client.get(
            f"/api/payments/orders/{payment_id}",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(query_r.status_code, 200, query_r.text)
        self.assertIn(query_r.json()["status"], ["pending", "completed", "failed"])

    # ---- PI-03 ----
    def test_payment_callback_updates_order_status(self):
        """POST /api/payments/callback/{channel} processes payment callback."""
        buyer = self._register("buyer_pi03")
        seller = self._register("seller_pi03")
        pid = self._publish(seller["username"], "PI03 商品", price=300)

        create_r = self.client.post(
            "/api/payments/orders",
            json={"product_id": pid, "channel": "alipay"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 200, create_r.text)
        payment_id = create_r.json()["id"]

        # Simulate successful payment callback
        callback_r = self.client.post(
            f"/api/payments/callback/alipay",
            json={
                "payment_id": payment_id,
                "external_txn_id": "alipay_123456",
                "status": "success",
                "amount": 30000,  # 300 CNY in cents
            },
        )
        self.assertEqual(callback_r.status_code, 200, callback_r.text)
        self.assertEqual(callback_r.json()["status"], "completed")

    # ---- PI-04 ----
    def test_withdrawal_creates_withdrawal_record(self):
        """POST /api/payments/withdraw creates a withdrawal request."""
        seller = self._register("seller_pi04")
        # Add some coins to seller's balance first
        r = self.client.post(
            "/api/payments/withdraw",
            json={
                "amount_coins": 1000,
                "channel": "alipay",
                "account_info": {"account": "test@example.com"},
            },
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["channel"], "alipay")

    # ---- PI-05 ----
    def test_payment_history_returns_paginated_list(self):
        """GET /api/payments/history returns paginated payment history."""
        user = self._register("user_pi05")

        r = self.client.get(
            "/api/payments/history?page=1&page_size=10",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("items", body)
        self.assertIn("total", body)
        self.assertIn("page", body)

    # ---- PI-06 ----
    def test_earnings_summary_shows_balance_breakdown(self):
        """GET /api/payments/earnings returns earnings summary."""
        seller = self._register("seller_pi06")

        r = self.client.get(
            "/api/payments/earnings",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("total_earnings_cents", body)
        self.assertIn("available_balance_cents", body)
        self.assertIn("withdrawn_cents", body)


class TestPaymentMethods(_PaymentBase):
    """TDD tests for Payment Methods CRUD."""

    def test_add_payment_method(self):
        """POST /api/payments/methods adds a new payment method."""
        user = self._register("user_pm01")

        r = self.client.post(
            "/api/payments/methods",
            json={
                "channel": "alipay",
                "account_ref": "user@example.com",
                "account_name": "Test User",
            },
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["channel"], "alipay")
        self.assertTrue(body["is_default"])

    def test_list_payment_methods(self):
        """GET /api/payments/methods returns user's payment methods."""
        user = self._register("user_pm02")

        r = self.client.get(
            "/api/payments/methods",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsInstance(r.json(), list)

    def test_delete_payment_method(self):
        """DELETE /api/payments/methods/{id} removes a payment method."""
        user = self._register("user_pm03")

        # First add a method
        add_r = self.client.post(
            "/api/payments/methods",
            json={"channel": "wechat", "account_ref": "wechat_123"},
            headers=_auth(user["token"]),
        )
        self.assertEqual(add_r.status_code, 200, add_r.text)
        method_id = add_r.json()["id"]

        # Then delete it
        delete_r = self.client.delete(
            f"/api/payments/methods/{method_id}",
            headers=_auth(user["token"]),
        )
        self.assertEqual(delete_r.status_code, 200, delete_r.text)

        # Verify it's gone
        list_r = self.client.get(
            "/api/payments/methods",
            headers=_auth(user["token"]),
        )
        self.assertEqual(list_r.status_code, 200, list_r.text)
        self.assertEqual(len(list_r.json()), 0)


if __name__ == "__main__":
    unittest.main()
