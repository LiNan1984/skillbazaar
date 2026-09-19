"""Real notification event tests against the real FastAPI app.

Covers spec 改进项 3 (N-01 ~ N-06): buy notifies buyer+seller, bounty
lifecycle notifications at 4 nodes, cron push notifies active subscribers
only, unread count + mark-read consistency, auth 401 and 404 isolation.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database as db_mod

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestNotificationEvents(unittest.TestCase):
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
        username = f"nt_{suffix}"
        nick = nickname or f"昵称_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": nick},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"],
                "nickname": nick, "username": username}

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill") -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 描述",
            "category": category, "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _buy(self, buyer: dict, product_id: int):
        r = self.client.post("/api/transactions/buy",
                             json={"product_id": product_id},
                             headers=_auth(buyer["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def _notifs(self, user: dict, unread_only: bool = False) -> list[dict]:
        r = self.client.get(
            "/api/v2/notifications",
            params={"unread_only": str(unread_only).lower()},
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["notifications"]

    def _unread_count(self, user: dict) -> int:
        r = self.client.get("/api/v2/notifications", headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["unread_count"]

    # ---- N-01 ----
    def test_buy_notifies_buyer_and_seller(self):
        seller = self._register("seller_n01", "卖家N01")
        product_name = "告警机器人 Alpha N01"
        product_id = self._publish(seller["username"], product_name, price=30)
        buyer = self._register("buyer_n01", "买家N01")

        self._buy(buyer, product_id)

        buyer_notifs = self._notifs(buyer)
        bought = [n for n in buyer_notifs if n["type"] == "product_bought"]
        self.assertEqual(len(bought), 1)
        self.assertFalse(bought[0]["is_read"])
        self.assertIn(product_name, bought[0]["title"] + bought[0]["content"])

        seller_notifs = self._notifs(seller)
        sold = [n for n in seller_notifs if n["type"] == "product_sold"]
        self.assertEqual(len(sold), 1)
        self.assertFalse(sold[0]["is_read"])
        self.assertIn(product_name, sold[0]["title"] + sold[0]["content"])
        self.assertIn(buyer["nickname"], sold[0]["content"])

    # ---- N-02 ----
    def test_bounty_lifecycle_emits_notifications(self):
        owner = self._register("owner_n02", "悬赏主N02")
        dev1 = self._register("dev1_n02", "开发者N02甲")
        dev2 = self._register("dev2_n02", "开发者N02乙")

        bounty_id = self._create_bounty(owner, "通知全流程悬赏 N02")
        app1 = self._apply(dev1, bounty_id, "甲的方案")
        self._apply(dev2, bounty_id, "乙的方案")

        # node 1: new application -> owner
        owner_after_apply = self._notifs(owner)
        self.assertTrue(any(n["type"] == "bounty_application" for n in owner_after_apply))

        # node 2: selected -> only the chosen developer
        r = self.client.post(
            f"/api/bounties/{bounty_id}/select",
            json={"application_id": app1}, headers=_auth(owner["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        dev1_notifs = self._notifs(dev1)
        self.assertTrue(any(n["type"] == "bounty_selected" for n in dev1_notifs))
        dev2_notifs = self._notifs(dev2)
        self.assertFalse(any(n["type"] == "bounty_selected" for n in dev2_notifs))

        # node 3: delivery submitted -> owner
        delivery_id = self._deliver(dev1, bounty_id, "交付物说明")
        owner_after_deliver = self._notifs(owner)
        self.assertTrue(any(n["type"] == "bounty_delivered" for n in owner_after_deliver))

        # node 4a: accepted -> developer
        r = self.client.post(
            f"/api/bounties/{bounty_id}/review",
            json={"delivery_id": delivery_id, "accept": True},
            headers=_auth(owner["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        dev1_after = self._notifs(dev1)
        self.assertTrue(any(n["type"] == "bounty_accepted" for n in dev1_after))

        # totals: owner >= 3, dev1 >= 2
        self.assertGreaterEqual(
            len([n for n in self._notifs(owner)
                 if n["type"].startswith("bounty")]), 3)
        self.assertGreaterEqual(
            len([n for n in self._notifs(dev1)
                 if n["type"].startswith("bounty")]), 2)

        # node 4b: rejection branch -> developer gets bounty_rejected
        owner2 = self._register("owner2_n02", "悬赏主N02乙")
        dev3 = self._register("dev3_n02", "开发者N02丙")
        bounty2 = self._create_bounty(owner2, "拒绝分支悬赏 N02")
        app3 = self._apply(dev3, bounty2, "丙的方案")
        self.client.post(
            f"/api/bounties/{bounty2}/select",
            json={"application_id": app3}, headers=_auth(owner2["token"]))
        delivery2 = self._deliver(dev3, bounty2, "再次交付")
        r = self.client.post(
            f"/api/bounties/{bounty2}/review",
            json={"delivery_id": delivery2, "accept": False},
            headers=_auth(owner2["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        dev3_notifs = self._notifs(dev3)
        self.assertTrue(any(n["type"] == "bounty_rejected" for n in dev3_notifs))

    def _create_bounty(self, owner: dict, title: str) -> int:
        r = self.client.post("/api/bounties", json={
            "title": title,
            "description": f"{title} 描述",
            "category": "Skill",
            "budget_min": 100,
            "budget_max": 200,
        }, headers=_auth(owner["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def _apply(self, dev: dict, bounty_id: int, proposal: str) -> int:
        r = self.client.post(
            f"/api/bounties/{bounty_id}/apply",
            json={"bounty_id": bounty_id, "proposal": proposal,
                  "estimated_days": 5, "quoted_price": 150},
            headers=_auth(dev["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def _deliver(self, dev: dict, bounty_id: int, description: str) -> int:
        r = self.client.post(
            f"/api/bounties/{bounty_id}/deliver",
            data={"description": description},
            headers=_auth(dev["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    # ---- N-03 ----
    def test_cron_push_notifies_active_subscribers(self):
        seller = self._register("seller_n03", "Cron卖家N03")
        product_name = "每日行情播报 Cron N03"
        product_id = self._publish(seller["username"], product_name,
                                   price=10, category="Cron")
        reg = self.client.post("/api/cron/register", json={
            "product_id": product_id,
            "schedule_cron": "0 9 * * *",
            "result_format": "json",
        }, headers=_auth(seller["token"]))
        self.assertEqual(reg.status_code, 200, reg.text)
        cron_id = reg.json()["id"]
        secret = reg.json()["webhook_secret"]

        subscribers = []
        for suffix in ("s1_n03", "s2_n03", "s3_n03"):
            user = self._register(suffix)
            sub = self.client.post(
                f"/api/cron/subscribe/{cron_id}",
                headers=_auth(user["token"]))
            self.assertEqual(sub.status_code, 200, sub.text)
            subscribers.append((user, sub.json()["id"]))
        s1, s2, s3 = subscribers[0][0], subscribers[1][0], subscribers[2][0]
        cancel = self.client.delete(
            f"/api/cron/subscription/{subscribers[2][1]}",
            headers=_auth(s3["token"]))
        self.assertEqual(cancel.status_code, 200, cancel.text)

        payload = '{"summary": "今日行情播报已生成"}'
        push = self.client.post(
            f"/api/cron/push/{cron_id}",
            json={"payload": payload, "duration_ms": 12},
            headers={"X-Webhook-Secret": secret})
        self.assertEqual(push.status_code, 200, push.text)

        for user in (s1, s2):
            cron_notifs = [n for n in self._notifs(user) if n["type"] == "cron_result"]
            self.assertEqual(len(cron_notifs), 1)
            self.assertIn(product_name, cron_notifs[0]["title"] + cron_notifs[0]["content"])
            self.assertFalse(cron_notifs[0]["is_read"])

        s3_cron = [n for n in self._notifs(s3) if n["type"] == "cron_result"]
        self.assertEqual(len(s3_cron), 0)

        # failed push (wrong secret) must not notify anybody
        before_s1 = len(self._notifs(s1))
        bad = self.client.post(
            f"/api/cron/push/{cron_id}",
            json={"payload": payload},
            headers={"X-Webhook-Secret": "wrong-secret"})
        self.assertGreaterEqual(bad.status_code, 400)
        after_s1 = len(self._notifs(s1))
        self.assertEqual(before_s1, after_s1)

    # ---- N-04 ----
    def test_unread_count_and_mark_read(self):
        seller = self._register("seller_n04", "卖家N04")
        buyer = self._register("buyer_n04", "买家N04")
        for i in range(3):
            pid = self._publish(seller["username"], f"未读计数商品 {i} N04", price=5)
            self._buy(buyer, pid)

        self.assertEqual(self._unread_count(buyer), 3)
        notifs = self._notifs(buyer)
        target = notifs[0]

        marked = self.client.post(
            f"/api/v2/notifications/{target['id']}/read",
            headers=_auth(buyer["token"]))
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertTrue(marked.json().get("success"))

        self.assertEqual(self._unread_count(buyer), 2)
        unread = self._notifs(buyer, unread_only=True)
        self.assertNotIn(target["id"], [n["id"] for n in unread])
        all_notifs = self._notifs(buyer)
        refreshed = next(n for n in all_notifs if n["id"] == target["id"])
        self.assertTrue(refreshed["is_read"])

        # idempotent: polling again must not bounce the count back
        self.assertEqual(self._unread_count(buyer), 2)

    # ---- N-05 ----
    def test_notifications_require_auth(self):
        r = self.client.get("/api/v2/notifications")
        self.assertEqual(r.status_code, 401, r.text)
        self.assertNotIn("notifications", r.json())
        r2 = self.client.post("/api/v2/notifications/1/read")
        self.assertEqual(r2.status_code, 401, r2.text)

    # ---- N-06 ----
    def test_mark_read_404_for_missing_or_other_user(self):
        seller = self._register("seller_n06", "卖家N06")
        u1 = self._register("u1_n06", "用户N06甲")
        u2 = self._register("u2_n06", "用户N06乙")
        pid = self._publish(seller["username"], "越权已读商品 N06", price=5)
        self._buy(u1, pid)
        u1_notif = self._notifs(u1)[0]

        other = self.client.post(
            f"/api/v2/notifications/{u1_notif['id']}/read",
            headers=_auth(u2["token"]))
        self.assertEqual(other.status_code, 404, other.text)

        missing = self.client.post(
            "/api/v2/notifications/999999/read",
            headers=_auth(u1["token"]))
        self.assertEqual(missing.status_code, 404, missing.text)

        still_unread = [n for n in self._notifs(u1) if n["id"] == u1_notif["id"]][0]
        self.assertFalse(still_unread["is_read"])


if __name__ == "__main__":
    unittest.main()
