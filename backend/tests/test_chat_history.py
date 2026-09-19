"""BS assistant chat persistence tests against the real FastAPI app.

Covers spec 改进项 2 (C-01 ~ C-06): message persistence, Bearer auth on all
chat routes, latest-20 ascending history, clear + thread reset, survival of a
simulated process restart, and persistence failures not blocking the reply.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite

import database as db_mod
import agents.bs_agent as bs_agent

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


class TestChatHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> tuple[str, str]:
        username = f"ch_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"聊天_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return uid, login.json()["token"]

    def _send(self, token: str, message: str, card=None):
        return self.client.post(
            "/api/chat",
            json={"message": message, "card": card},
            headers=_auth(token),
        )

    def _history(self, token: str, **params):
        return self.client.get("/api/chat/history", params=params,
                               headers=_auth(token))

    # ---- C-01 ----
    def test_two_turns_persist_four_messages_with_card(self):
        uid, token = self._register("c01")
        r1 = self._send(token, "推荐一个 Python 代码审查 skill")
        self.assertEqual(r1.status_code, 200, r1.text)
        body1 = r1.json()
        self.assertTrue(body1.get("reply"))
        self.assertIsInstance(body1.get("products"), list)
        self.assertGreater(len(body1["products"]), 0, "推荐轮应返回商品卡片")

        r2 = self._send(token, "谢谢，我知道了")
        self.assertEqual(r2.status_code, 200, r2.text)
        body2 = r2.json()
        self.assertTrue(body2.get("reply"))

        rows = asyncio.run(_fetchall(
            "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id", (uid,)))
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["role"] for r in rows],
                         ["user", "assistant", "user", "assistant"])
        self.assertEqual(len({r["thread_id"] for r in rows}), 1)
        self.assertEqual(rows[0]["content"], "推荐一个 Python 代码审查 skill")
        self.assertEqual(rows[1]["content"], body1["reply"])
        self.assertEqual(rows[3]["content"], body2["reply"])

        card1 = json.loads(rows[1]["card"])
        self.assertTrue(card1, "卡片轮 card 必须为非空 JSON")
        # v2: search turns persist a 'match' card (ids subset of the search
        # results); legacy 'products' cards carry the full result set.
        if card1.get("type") == "match":
            card_ids = {s["product"]["id"] for s in card1["steps"]}
        else:
            card_ids = {p["id"] for p in card1["products"]}
        resp_ids = {p["id"] for p in body1["products"]}
        self.assertTrue(card_ids)
        self.assertTrue(card_ids.issubset(resp_ids))
        self.assertIsNone(rows[3]["card"], "普通追问轮 card 必须为 NULL")

        for prev, nxt in zip(rows, rows[1:]):
            self.assertLessEqual(prev["created_at"], nxt["created_at"])
            self.assertLess(prev["id"], nxt["id"])

    # ---- C-02 ----
    def test_history_requires_auth(self):
        r_get = self.client.get("/api/chat/history")
        self.assertEqual(r_get.status_code, 401, r_get.text)
        r_del = self.client.delete("/api/chat/history")
        self.assertEqual(r_del.status_code, 401, r_del.text)
        self.assertNotIn("messages", r_get.json())

    # ---- C-03 ----
    def test_history_returns_latest_20_ascending(self):
        uid, token = self._register("c03")
        for i in range(12):
            r = self._send(token, f"测试消息序号{i:02d}")
            self.assertEqual(r.status_code, 200, r.text)

        r = self._history(token)
        self.assertEqual(r.status_code, 200, r.text)
        messages = r.json()["messages"]
        self.assertEqual(len(messages), 20)
        # oldest four rows dropped -> first surviving user message is index 02
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("02", messages[0]["content"])
        self.assertEqual(messages[-1]["role"], "assistant")
        self.assertIn("11", messages[-2]["content"])
        for prev, nxt in zip(messages, messages[1:]):
            self.assertLessEqual(prev["id"], nxt["id"])

        # limit out of [1, 20] -> 422 contract
        bad = self._history(token, limit=21)
        self.assertEqual(bad.status_code, 422, bad.text)

    # ---- C-04 ----
    def test_clear_history_resets_thread(self):
        uid, token = self._register("c04")
        r0 = self._send(token, "我叫张三")
        self.assertEqual(r0.status_code, 200, r0.text)
        before_rows = asyncio.run(_fetchall(
            "SELECT DISTINCT thread_id FROM chat_messages WHERE user_id = ?", (uid,)))
        old_thread = before_rows[0]["thread_id"]

        deleted = self.client.delete("/api/chat/history", headers=_auth(token))
        self.assertEqual(deleted.status_code, 200, deleted.text)

        empty = self._history(token)
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json()["messages"], [])

        remaining = asyncio.run(_fetchall(
            "SELECT COUNT(*) AS c FROM chat_messages WHERE user_id = ?", (uid,)))
        self.assertEqual(remaining[0]["c"], 0)

        after = self._send(token, "我叫什么名字？")
        self.assertEqual(after.status_code, 200, after.text)
        self.assertNotIn("张三", after.json()["reply"])

        after_rows = asyncio.run(_fetchall(
            "SELECT DISTINCT thread_id FROM chat_messages WHERE user_id = ?", (uid,)))
        self.assertEqual(len(after_rows), 1)
        self.assertNotEqual(after_rows[0]["thread_id"], old_thread)

    # ---- C-05 ----
    def test_history_survives_app_restart(self):
        uid, token = self._register("c05")
        r1 = self._send(token, "推荐一个 skill")
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertGreater(len(r1.json().get("products") or []), 0)
        r2 = self._send(token, "谢谢，我知道了")
        self.assertEqual(r2.status_code, 200, r2.text)

        # Simulate process restart: in-memory LangGraph state is gone
        bs_agent.reset_state()

        new_client = TestClient(app)
        with new_client:
            r = new_client.get("/api/chat/history", headers=_auth(token))
        self.assertEqual(r.status_code, 200, r.text)
        messages = r.json()["messages"]
        self.assertEqual(len(messages), 4)
        self.assertEqual([m["role"] for m in messages],
                         ["user", "assistant", "user", "assistant"])
        card = messages[1].get("card")
        self.assertIsInstance(card, dict)
        # v2 persists a 'match' card; legacy history may carry 'products'.
        self.assertTrue(card.get("steps") or card.get("products"))

    # ---- C-06 ----
    def test_persistence_failure_does_not_block_reply(self):
        uid, token = self._register("c06")
        with patch("database.insert_chat_message",
                   side_effect=aiosqlite.Error("disk full")):
            r = self._send(token, "推荐一个 skill")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json().get("reply"))

        during = asyncio.run(_fetchall(
            "SELECT COUNT(*) AS c FROM chat_messages WHERE user_id = ?", (uid,)))
        self.assertEqual(during[0]["c"], 0)

        r2 = self._send(token, "谢谢，我知道了")
        self.assertEqual(r2.status_code, 200, r2.text)
        after = asyncio.run(_fetchall(
            "SELECT COUNT(*) AS c FROM chat_messages WHERE user_id = ?", (uid,)))
        self.assertEqual(after[0]["c"], 2)


if __name__ == "__main__":
    unittest.main()
