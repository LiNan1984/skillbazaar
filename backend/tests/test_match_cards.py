"""FR1/FR4 match card tests (M-01 ~ M-03, H-01).

The LLM (_call_llm) is always mocked:
- normal state returns the frozen match-mode contract text: a search-params
  JSON block followed by a steps-selection JSON block;
- outage state raises httpx.TimeoutException so the rule fallback is used.
"""
from __future__ import annotations

import asyncio
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import httpx

import database as db_mod
import agents.bs_agent as bs_agent

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


async def _fetchall(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await conn.close()


def _contract_text(params: dict, steps: list[dict]) -> str:
    """Frozen LLM contract: search-params block + steps block."""
    return (
        "好的，我先把您的任务拆解成几个步骤，再为每步挑选合适的 Skill。\n"
        f"```json\n{json.dumps(params, ensure_ascii=False)}\n```\n"
        f"```json\n{json.dumps({'steps': steps}, ensure_ascii=False)}\n```\n"
    )


class _MatchBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()
        # Seed catalogs are irrelevant here: start from a deterministic empty shelf.
        asyncio.run(_clear_products())

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, suffix: str) -> dict:
        username = f"mc_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12",
                  "nickname": f"匹配_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"], "username": username}

    def _publish(self, seller_name: str, name: str, description: str,
                 price: int, category: str = "Skill") -> dict:
        r = self.client.post("/api/products", json={
            "name": name, "description": description,
            "category": category, "price": price, "seller_name": seller_name,
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def _send(self, token: str, message: str):
        return self.client.post(
            "/api/chat", json={"message": message}, headers=_auth(token))

    def _api_product(self, pid: int) -> dict:
        r = self.client.get(f"/api/products/{pid}")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class TestSearchParamNormalization(unittest.TestCase):
    # ---- review M#2 / M#3: pure unit checks ----
    def test_params_normalized(self):
        from agents.nodes import _normalize_search_params, _coerce_price

        self.assertEqual(_coerce_price("100"), 100)
        self.assertEqual(_coerce_price(100.0), 100)
        self.assertIsNone(_coerce_price("免费"))
        self.assertIsNone(_coerce_price(""))
        self.assertIsNone(_coerce_price(None))

        out = _normalize_search_params({
            "category": "量子神仙类目",
            "keyword": "  周报  ",
            "min_price": "50",
            "max_price": "很贵",
            "sort": "weird_sort",
        })
        self.assertEqual(out["category"], "")
        self.assertEqual(out["keyword"], "周报")
        self.assertEqual(out["min_price"], 50)
        self.assertIsNone(out["max_price"])
        self.assertEqual(out["sort"], "rating")

        self.assertEqual(
            _normalize_search_params({"category": "skill"})["category"], "")
        self.assertEqual(
            _normalize_search_params({"category": "Skill"})["category"], "Skill")

    def test_steps_capped_at_four_and_title_truncated(self):
        from agents.nodes import _validated_steps

        class P:
            def __init__(self, i):
                self.id = i
                self.name = f"商品{i}"
                self.description = f"描述{i}"

        full = {i: P(i) for i in range(1, 7)}
        raw = [{"title": f"步骤{i}-" * 30, "product_id": i,
                "reason": f"描述{i}"} for i in range(1, 7)]
        steps = _validated_steps(raw, full)
        self.assertEqual(len(steps), 4)
        self.assertLessEqual(len(steps[0]["title"]), 60)


class TestMatchCards(_MatchBase):
    # ---- M-01 ----
    def test_multistep_task_returns_match_card(self):
        seller = self._register("seller_m01")
        p1 = self._publish(seller["username"], "竞品价格抓取器",
                           "每日定时抓取竞品价格并输出差异报表", 100)
        p2 = self._publish(seller["username"], "自动周报生成 Skill",
                           "汇总数据并自动生成结构化周报文档", 200)
        self._publish(seller["username"], "多余的第三个商品",
                       "与任务无关的其他功能描述", 300)
        buyer = self._register("buyer_m01")

        params = {"category": "Skill", "keyword": None, "sort": "rating"}
        steps = [
            {"title": "第一步：抓取竞品价格", "product_id": p1["id"],
             "reason": p1["description"]},
            {"title": "第二步：自动生成周报", "product_id": p2["id"],
             "reason": p2["description"]},
        ]
        text = _contract_text(params, steps)

        with patch("agents.nodes._call_llm", new=AsyncMock(return_value=text)):
            r = self._send(buyer["token"], "我想找一个每天抓取竞品价格并生成周报的方案")
        self.assertEqual(r.status_code, 200, r.text)

        card = r.json()["card"]
        self.assertIsNotNone(card)
        self.assertEqual(card["type"], "match")
        self.assertGreaterEqual(len(card["steps"]), 2)

        total = 0
        selected_ids = []
        for step in card["steps"]:
            self.assertTrue(step["title"].strip())
            product = step["product"]
            self.assertTrue(step["reason"].strip())
            api_product = self._api_product(product["id"])
            self.assertEqual(product["name"], api_product["name"])
            self.assertEqual(product["price"], api_product["price"])
            self.assertEqual(product["rating"], api_product["rating"])
            total += product["price"]
            selected_ids.append(product["id"])
        self.assertEqual(card["total_price"], total)
        self.assertEqual(card["total_price"], 300)

        # Persisted as card JSON on the latest assistant chat message.
        rows = asyncio.run(_fetchall(
            """SELECT card FROM chat_messages
               WHERE user_id = ? AND role = 'assistant' AND card IS NOT NULL
               ORDER BY id DESC LIMIT 1""",
            (buyer["id"],),
        ))
        self.assertTrue(rows)
        persisted = json.loads(rows[0]["card"])
        self.assertEqual(persisted["type"], "match")
        self.assertEqual(persisted, card)

    # ---- M-02 ----
    def test_match_card_never_fabricates_products_or_reasons(self):
        seller = self._register("seller_m02")
        p1 = self._publish(
            seller["username"], "价格监控 Skill",
            "每日定时抓取竞品价格并输出差异报表，支持自动告警", 100)
        buyer = self._register("buyer_m02")

        params = {"category": "Skill", "keyword": None, "sort": "rating"}
        steps = [
            {"title": "库外幻影商品", "product_id": 999999,
             "reason": "这个不存在的商品能自动完成一切并飞天遁地"},
            {"title": "真实推荐", "product_id": p1["id"],
             "reason": "每日定时抓取竞品价格并输出差异报表"},
        ]
        text = _contract_text(params, steps)

        with patch("agents.nodes._call_llm", new=AsyncMock(return_value=text)):
            r = self._send(buyer["token"], "我想找一个每天抓取竞品价格的方案")
        self.assertEqual(r.status_code, 200, r.text)

        card = r.json()["card"]
        self.assertEqual(card["type"], "match")
        ids = [s["product"]["id"] for s in card["steps"]]
        self.assertNotIn(999999, ids)
        self.assertEqual(self.client.get("/api/products/999999").status_code, 404)

        for step in card["steps"]:
            api_product = self._api_product(step["product"]["id"])
            self.assertEqual(step["product"]["name"], api_product["name"])
            norm = lambda s: re.sub(r"\s+", "", s)
            self.assertIn(
                norm(step["reason"]), norm(api_product["description"]),
                "reason 必须是该商品 description 的直接引用/子串，禁止编造",
            )
            self.assertNotIn("飞天遁地", step["reason"])

    # ---- review M#2 ----
    def test_search_backend_error_does_not_emit_bounty_card(self):
        import services.product_service as ps

        seller = self._register("seller_mdb")
        product = self._publish(
            seller["username"], "数据库抖动时的周报 Skill",
            "即使搜索服务抖动也应宽查兜底", 80)
        buyer = self._register("buyer_mdb")

        real_get = ps.get_products
        calls = {"n": 0}

        async def flaky_get_products(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("simulated DB outage")
            return await real_get(*args, **kwargs)

        with patch("agents.nodes._call_llm",
                   new=AsyncMock(side_effect=httpx.TimeoutException("503"))), \
             patch.object(ps, "get_products", side_effect=flaky_get_products):
            r = self._send(buyer["token"], "推荐一个 skill 帮我写周报")
        self.assertEqual(r.status_code, 200, r.text)
        card = r.json()["card"]
        self.assertIsNotNone(card, "后端异常恢复后应给出推荐而非错误")
        self.assertEqual(card["type"], "match", "DB 故障不得被误判为零结果悬赏引导")
        self.assertGreaterEqual(len(card["steps"]), 1)
        for step in card["steps"]:
            self.assertEqual(self._api_product(step["product"]["id"])["id"],
                             step["product"]["id"])

    # ---- M-03 ----
    def test_llm_outage_falls_back_to_rule_based_match(self):
        seller = self._register("seller_m03")
        product = self._publish(
            seller["username"], "周报助手 Skill",
            "一键汇总本周工作并生成周报", 120)
        buyer = self._register("buyer_m03")

        with patch("agents.nodes._call_llm",
                   new=AsyncMock(side_effect=httpx.TimeoutException("503"))):
            r = self._send(buyer["token"], "推荐一个 skill 帮我写周报")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        card = body["card"]
        self.assertIsNotNone(card)
        self.assertEqual(card["type"], "match")
        self.assertGreaterEqual(len(card["steps"]), 1)
        for step in card["steps"]:
            self.assertEqual(self._api_product(step["product"]["id"])["id"],
                             step["product"]["id"])
        self.assertNotIn("Traceback", body["reply"])

        rows = asyncio.run(_fetchall(
            "SELECT role FROM chat_messages WHERE user_id = ? ORDER BY id",
            (buyer["id"],),
        ))
        self.assertEqual([r["role"] for r in rows], ["user", "assistant"])


class TestMatchCardPersistence(_MatchBase):
    # ---- H-01 ----
    def test_match_card_echoes_and_coexists_with_legacy_products_card(self):
        seller = self._register("seller_h01")
        p1 = self._publish(seller["username"], "H01 抓取器",
                           "抓取数据并清洗", 100)
        p2 = self._publish(seller["username"], "H01 报告器",
                           "生成可视化分析报告", 200)
        buyer = self._register("buyer_h01")

        text = _contract_text(
            {"category": "Skill", "keyword": None, "sort": "rating"},
            [
                {"title": "抓取", "product_id": p1["id"], "reason": p1["description"]},
                {"title": "报告", "product_id": p2["id"], "reason": p2["description"]},
            ],
        )
        with patch("agents.nodes._call_llm", new=AsyncMock(return_value=text)):
            r = self._send(buyer["token"], "推荐一套数据抓取与报告生成的方案")
        self.assertEqual(r.status_code, 200, r.text)
        live_card = r.json()["card"]
        self.assertEqual(live_card["type"], "match")

        # A v1-era legacy 'products' card stored directly in chat history.
        legacy_card = {"type": "products", "products": [{
            "id": p1["id"], "name": p1["name"], "category": "Skill",
            "price": p1["price"], "rating": p1["rating"],
            "description": p1["description"][:60],
        }]}
        asyncio.run(db_mod.insert_chat_message({
            "user_id": buyer["id"], "role": "assistant",
            "content": "旧版商品列表", "card": legacy_card,
        }))

        def _history_types():
            hist = self.client.get(
                "/api/chat/history?limit=20", headers=_auth(buyer["token"]))
            self.assertEqual(hist.status_code, 200, hist.text)
            cards = [m["card"] for m in hist.json()["messages"] if m["card"]]
            return cards

        cards = _history_types()
        self.assertIn("match", [c["type"] for c in cards])
        self.assertIn("products", [c["type"] for c in cards])
        match_cards = [c for c in cards if c["type"] == "match"]
        self.assertEqual(match_cards[-1], live_card)

        # Simulate a process restart: drop MemorySaver state and rebuild client.
        bs_agent.reset_state()
        self._client_cm.__exit__(None, None, None)
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

        cards_after = _history_types()
        match_after = [c for c in cards_after if c["type"] == "match"]
        products_after = [c for c in cards_after if c["type"] == "products"]
        self.assertTrue(match_after)
        self.assertTrue(products_after)
        for step in match_after[-1]["steps"]:
            api_product = self._api_product(step["product"]["id"])
            self.assertEqual(step["product"]["price"], api_product["price"])
            self.assertEqual(step["product"]["rating"], api_product["rating"])


if __name__ == "__main__":
    unittest.main()
