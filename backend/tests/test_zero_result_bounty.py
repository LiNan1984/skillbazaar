"""FR3 zero-result -> bounty prefill card tests (Z-01 ~ Z-04).

The zero-match decision must be based on the search with the user's ORIGINAL
intent params; do_search's progressive broadening must never mask it.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import httpx

import database as db_mod

_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
db_mod.DB_PATH = _TMP.name

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _clear_products():
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        await conn.execute("DELETE FROM products")
        await conn.commit()
    finally:
        await conn.close()


def _contract_text(params: dict, steps: list[dict] | None = None) -> str:
    blocks = [f"```json\n{json.dumps(params, ensure_ascii=False)}\n```"]
    if steps is not None:
        blocks.append(f"```json\n{json.dumps({'steps': steps}, ensure_ascii=False)}\n```")
    return "我来帮您分析需求并搜索。\n" + "\n".join(blocks)


class TestZeroResultBounty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()
        asyncio.run(_clear_products())

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> dict:
        username = f"zb_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"零结果_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"], "username": username}

    def _publish_skill(self, seller_name: str, name: str, price: int = 50) -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 描述",
            "category": "Skill", "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _send(self, token: str, message: str):
        return self.client.post(
            "/api/chat", json={"message": message}, headers=_auth(token))

    def _assert_bounty_prefill(self, card: dict, original_message: str):
        self.assertEqual(card["type"], "bounty")
        self.assertEqual(card["step"], "fill")
        data = card["data"]
        self.assertEqual(data["description"], original_message)
        self.assertTrue(data["title"].strip())
        self.assertIn(data["category"], ("Agent", "Skill", "Cron", "Workflow"))

    # ---- Z-01 ----
    def test_rule_fallback_zero_hits_emits_bounty_prefill(self):
        seller = self._register("seller_z01")
        self._publish_skill(seller["username"], "Z01 普通 Skill A")
        self._publish_skill(seller["username"], "Z01 普通 Skill B")
        buyer = self._register("buyer_z01")

        message = "我想找一个能做量子宠物翻译的 cron 定时任务"
        with patch("agents.nodes._call_llm",
                   new=AsyncMock(side_effect=httpx.TimeoutException("503"))):
            r = self._send(buyer["token"], message)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self._assert_bounty_prefill(body["card"], message)
        self.assertEqual(body["card"]["data"]["category"], "Cron")
        self.assertEqual(body["products"], [])

    # ---- Z-02 ----
    def test_llm_zero_hits_emits_bounty_prefill_despite_broadening(self):
        seller = self._register("seller_z02")
        self._publish_skill(seller["username"], "Z02 普通 Skill A")
        self._publish_skill(seller["username"], "Z02 普通 Skill B")
        buyer = self._register("buyer_z02")

        message = "帮我找一个量子宠物翻译技能"
        text = _contract_text(
            {"keyword": "量子宠物翻译", "category": ""},
            steps=[{"title": "幻影步骤", "product_id": 999999,
                    "reason": "不存在的商品"}],
        )
        with patch("agents.nodes._call_llm", new=AsyncMock(return_value=text)):
            r = self._send(buyer["token"], message)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self._assert_bounty_prefill(body["card"], message)
        self.assertEqual(body["products"], [])
        self.assertIn("发布悬赏找人开发", body["reply"])

    # ---- Z-03 ----
    def test_no_bounty_guidance_when_matches_exist(self):
        seller = self._register("seller_z03")
        pid = self._publish_skill(seller["username"], "智能周报生成器 Z03")
        buyer = self._register("buyer_z03")

        message = "推荐一个能自动生成周报的技能"
        text = _contract_text(
            {"keyword": None, "category": "Skill"},
            steps=[{"title": "自动生成周报", "product_id": pid,
                    "reason": "智能周报生成器 Z03 描述"}],
        )
        with patch("agents.nodes._call_llm", new=AsyncMock(return_value=text)):
            r = self._send(buyer["token"], message)
        self.assertEqual(r.status_code, 200, r.text)
        card = r.json()["card"]
        self.assertEqual(card["type"], "match")
        self.assertIn(pid, [s["product"]["id"] for s in card["steps"]])
        self.assertNotIn("发布悬赏找人开发", r.json()["reply"])

    # ---- Z-04 ----
    def test_prefilled_bounty_card_submits_with_original_description(self):
        seller = self._register("seller_z04")
        self._publish_skill(seller["username"], "Z04 普通 Skill")
        buyer = self._register("buyer_z04")

        message = "我想找一个能做量子宠物翻译的 cron 定时任务"
        with patch("agents.nodes._call_llm",
                   new=AsyncMock(side_effect=httpx.TimeoutException("503"))):
            chat = self._send(buyer["token"], message)
        self.assertEqual(chat.status_code, 200, chat.text)
        prefill = chat.json()["card"]["data"]

        payload = {
            **prefill,
            "budget_min": 100,
            "budget_max": 300,
            "deadline": "2026-12-31",
        }
        created = self.client.post("/api/bounties", json=payload,
                                  headers=_auth(buyer["token"]))
        self.assertEqual(created.status_code, 200, created.text)

        # Anonymous submission must be rejected and never hit the database.
        anon = self.client.post("/api/bounties", json=payload)
        self.assertEqual(anon.status_code, 401, anon.text)

        listing = self.client.get(
            "/api/bounties?keyword=量子宠物",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(listing.status_code, 200, listing.text)
        bounties = listing.json()["bounties"]
        mine = [b for b in bounties
                if b["description"] == message and b["poster_id"] == buyer["id"]]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0]["title"].strip())


if __name__ == "__main__":
    unittest.main()
