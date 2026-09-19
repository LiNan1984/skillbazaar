"""v4 feature tests — Skill Versioning, User Agents, Analytics, Advanced Search, Bundles.

All 15 tests target API endpoints that do NOT yet exist.  They are written
so that they will pass once the corresponding v4 routers/services are
implemented.  The patterns follow the existing v3 test conventions:
  • Isolated temp SQLite DB (NamedTemporaryFile)
  • TestClient lifespan via setUpClass / tearDownClass
  • _auth(token) header helper
  • asyncio _fetchall / _fetchone DB verifiers
  • unittest.TestCase with descriptive docstrings

Endpoint contracts assumed (implementer can adjust):
  POST /api/v4/products/{id}/versions        → create new version
  GET  /api/v4/products/{id}/versions        → list versions
  GET  /api/v4/products/{id}/versions/{v}    → get specific version
  PUT  /api/v4/products/{id}/versions/{v}    → update version content
  POST /api/v4/agents                         → create agent
  GET  /api/v4/agents                         → list my agents
  GET  /api/v4/agents/{id}                    → get agent
  PUT  /api/v4/agents/{id}                    → update agent
  DELETE /api/v4/agents/{id}/skills/{pid}     → remove skill from agent
  POST /api/v4/agents/{id}/skills             → add skill to agent
  GET  /api/v4/analytics/products/{id}        → product analytics
  GET  /api/v4/analytics/categories           → category analytics
  GET  /api/v4/analytics/overview             → platform overview
  POST /api/v4/search                         → advanced search
  POST /api/v4/search/saved                   → save search
  GET  /api/v4/search/saved                   → list saved searches
  POST /api/v4/bundles                        → create bundle
  GET  /api/v4/bundles                        → list bundles
  POST /api/v4/bundles/{id}/purchase          → purchase bundle
  POST /api/v4/bundles/{id}/skills            → add skill to bundle
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


class _V4Base(unittest.TestCase):
    """Shared setUp / tearDown for v4 feature tests."""

    @classmethod
    def setUpClass(cls):
        db_mod.DB_PATH = _TMP.name
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    # ---- user helpers ----

    def _register(self, suffix: str, nickname: str = "") -> dict:
        username = f"v4_{suffix}"
        nick = nickname or f"用户_{suffix}"
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

    # ---- product helpers ----

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

    # ---- DB verifier shortcuts ----

    def _db_product_versions(self, product_id: int) -> list[dict]:
        return asyncio.run(_fetchall(
            "SELECT * FROM skill_versions WHERE product_id = ?", (product_id,),
        ))

    def _db_agents(self, user_id: str) -> list[dict]:
        return asyncio.run(_fetchall(
            "SELECT * FROM user_agents WHERE owner_id = ?", (user_id,),
        ))

    def _db_saved_searches(self, user_id: str) -> list[dict]:
        return asyncio.run(_fetchall(
            "SELECT * FROM saved_searches WHERE user_id = ?", (user_id,),
        ))

    def _db_bundles(self) -> list[dict]:
        return asyncio.run(_fetchall("SELECT * FROM skill_bundles"))

    def _db_bundle_items(self, bundle_id: int) -> list[dict]:
        return asyncio.run(_fetchall(
            "SELECT * FROM bundle_items WHERE bundle_id = ?", (bundle_id,),
        ))

    def _db_analytics_views(self, product_id: int) -> list[dict]:
        return asyncio.run(_fetchall(
            "SELECT * FROM product_analytics WHERE product_id = ?", (product_id,),
        ))


# ===========================================================================
# 1. Skill Versioning  (SV-01 … SV-06)
# ===========================================================================

class TestSkillVersioning(_V4Base):
    """New versions of a skill: create, list, retrieve, update, rollback."""

    # ---- SV-01 ----
    def test_create_new_version_appends_history(self):
        """Publishing a second version creates a new row with incremented version
        number and keeps the previous version intact."""
        seller = self._register("sv01", "卖家SV01")
        prod = self._publish(seller["username"], "SV01 技能", price=80,
                             category="Skill", content="v1 content")

        r = self.client.post(
            f"/api/v4/products/{prod['id']}/versions",
            json={"changelog": "修复了Bug", "content_preview": "v2 更新内容"},
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        ver = r.json()
        self.assertEqual(ver["version"], "2.0.0")
        self.assertEqual(ver["changelog"], "修复了Bug")
        self.assertEqual(ver["content_preview"], "v2 更新内容")
        self.assertIn("created_at", ver)

        rows = self._db_product_versions(prod["id"])
        self.assertEqual(len(rows), 2)
        versions = [row["version"] for row in rows]
        self.assertIn("1.0.0", versions)
        self.assertIn("2.0.0", versions)

    # ---- SV-02 ----
    def test_list_versions_returns_chronological_history(self):
        """GET versions returns all versions sorted ascending (oldest first)."""
        seller = self._register("sv02", "卖家SV02")
        prod = self._publish(seller["username"], "SV02 技能", price=60,
                             category="Skill", content="initial")

        for note in ("v2 changelog", "v3 changelog"):
            self.client.post(
                f"/api/v4/products/{prod['id']}/versions",
                json={"changelog": note, "content_preview": f"content {note}"},
                headers=_auth(seller["token"]),
            )

        r = self.client.get(
            f"/api/v4/products/{prod['id']}/versions",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        versions = r.json()["versions"]
        self.assertEqual(len(versions), 3)
        self.assertEqual(versions[0]["version"], "1.0.0")
        self.assertEqual(versions[-1]["version"], "3.0.0")
        for v in versions:
            self.assertIn("changelog", v)
            self.assertIn("created_at", v)

    # ---- SV-03 ----
    def test_get_specific_version_returns_correct_content(self):
        """GET version by version string returns the right snapshot."""
        seller = self._register("sv03", "卖家SV03")
        prod = self._publish(seller["username"], "SV03 技能", price=40,
                             category="Skill", content="v1 only")
        self.client.post(
            f"/api/v4/products/{prod['id']}/versions",
            json={"changelog": "v2 changes", "content_preview": "v2 content"},
            headers=_auth(seller["token"]),
        )

        r = self.client.get(
            f"/api/v4/products/{prod['id']}/versions/1.0.0",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["version"], "1.0.0")
        self.assertEqual(body["content_preview"], "v1 only")

        r2 = self.client.get(
            f"/api/v4/products/{prod['id']}/versions/2.0.0",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["content_preview"], "v2 content")

    # ---- SV-04 ----
    def test_update_version_changelog_only(self):
        """PATCH/PUT on a non-latest version updates changelog but not content."""
        seller = self._register("sv04", "卖家SV04")
        prod = self._publish(seller["username"], "SV04 技能", price=50,
                             category="Skill", content="v1")
        self.client.post(
            f"/api/v4/products/{prod['id']}/versions",
            json={"changelog": "v2 notes", "content_preview": "v2"},
            headers=_auth(seller["token"]),
        )

        r = self.client.put(
            f"/api/v4/products/{prod['id']}/versions/1.0.0",
            json={"changelog": "修正了v1的说明文档"},
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["changelog"], "修正了v1的说明文档")
        self.assertEqual(r.json()["content_preview"], "v1")

    # ---- SV-05 ----
    def test_rollback_to_previous_version_makes_it_latest(self):
        """Rolling back promotes a historical version to current (latest)."""
        seller = self._register("sv05", "卖家SV05")
        prod = self._publish(seller["username"], "SV05 技能", price=70,
                             category="Skill", content="v1 original")
        self.client.post(
            f"/api/v4/products/{prod['id']}/versions",
            json={"changelog": "v2 bad", "content_preview": "v2 broken"},
            headers=_auth(seller["token"]),
        )

        r = self.client.post(
            f"/api/v4/products/{prod['id']}/versions/rollback",
            json={"target_version": "1.0.0"},
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        new_ver = r.json()
        self.assertEqual(new_ver["version"], "3.0.0")
        self.assertEqual(new_ver["content_preview"], "v1 original")
        self.assertIn("rolled", new_ver["changelog"].lower())

        rows = self._db_product_versions(prod["id"])
        self.assertEqual(len(rows), 3)

    # ---- SV-06 ----
    def test_non_owner_cannot_create_version(self):
        """Only the product owner (seller) may create a new version."""
        seller = self._register("sv06_seller", "卖家SV06")
        prod = self._publish(seller["username"], "SV06 技能", price=30,
                             category="Skill", content="v1")
        attacker = self._register("sv06_attacker", "攻击者SV06")

        r = self.client.post(
            f"/api/v4/products/{prod['id']}/versions",
            json={"changelog": "恶意版本", "content_preview": "hacked"},
            headers=_auth(attacker["token"]),
        )
        self.assertEqual(r.status_code, 403, r.text)

        rows = self._db_product_versions(prod["id"])
        self.assertEqual(len(rows), 1)


# ===========================================================================
# 2. User Agents  (UA-01 … UA-06)
# ===========================================================================

class TestUserAgents(_V4Base):
    """Create/manage custom AI agents composed of selected skills."""

    # ---- UA-01 ----
    def test_create_agent_with_skills(self):
        """Create an agent with name, description, and a list of skill IDs."""
        user = self._register("ua01", "用户UA01")
        p1 = self._publish(user["username"], "UA01 技能A", price=10,
                           category="Skill")
        p2 = self._publish(user["username"], "UA01 技能B", price=20,
                           category="Skill")

        r = self.client.post(
            "/api/v4/agents",
            json={
                "name": "我的助手",
                "description": "一个综合助手",
                "skill_ids": [p1["id"], p2["id"]],
                "model": "gpt-4",
            },
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        agent = r.json()
        self.assertEqual(agent["name"], "我的助手")
        self.assertEqual(agent["model"], "gpt-4")
        self.assertEqual(agent["owner_id"], user["id"])
        self.assertEqual(len(agent["skills"]), 2)
        skill_ids = {s["product_id"] for s in agent["skills"]}
        self.assertIn(p1["id"], skill_ids)
        self.assertIn(p2["id"], skill_ids)

        rows = self._db_agents(user["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "我的助手")

    # ---- UA-02 ----
    def test_add_remove_skills_from_agent(self):
        """Dynamically add and remove skills from an existing agent."""
        user = self._register("ua02", "用户UA02")
        p1 = self._publish(user["username"], "UA02 技能A", price=10,
                           category="Skill")
        p2 = self._publish(user["username"], "UA02 技能B", price=20,
                           category="Skill")
        p3 = self._publish(user["username"], "UA02 技能C", price=30,
                           category="Skill")

        agent_r = self.client.post(
            "/api/v4/agents",
            json={"name": "UA02 代理", "description": "", "skill_ids": [p1["id"]]},
            headers=_auth(user["token"]),
        )
        self.assertEqual(agent_r.status_code, 201, agent_r.text)
        agent_id = agent_r.json()["id"]

        # Add p2
        add_r = self.client.post(
            f"/api/v4/agents/{agent_id}/skills",
            json={"product_id": p2["id"]},
            headers=_auth(user["token"]),
        )
        self.assertEqual(add_r.status_code, 200, add_r.text)
        self.assertEqual(len(add_r.json()["skills"]), 2)

        # Remove p1
        rm_r = self.client.delete(
            f"/api/v4/agents/{agent_id}/skills/{p1['id']}",
            headers=_auth(user["token"]),
        )
        self.assertEqual(rm_r.status_code, 200, rm_r.text)
        remaining_ids = {s["product_id"] for s in rm_r.json()["skills"]}
        self.assertNotIn(p1["id"], remaining_ids)
        self.assertIn(p2["id"], remaining_ids)

    # ---- UA-03 ----
    def test_list_my_agents(self):
        """GET /api/v4/agents returns all agents owned by the authenticated user."""
        user = self._register("ua03", "用户UA03")
        for i in range(3):
            self.client.post(
                "/api/v4/agents",
                json={"name": f"UA03 代理{i}", "description": "", "skill_ids": []},
                headers=_auth(user["token"]),
            )

        r = self.client.get("/api/v4/agents", headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        agents = r.json()["agents"]
        self.assertEqual(len(agents), 3)
        names = {a["name"] for a in agents}
        for i in range(3):
            self.assertIn(f"UA03 代理{i}", names)

    # ---- UA-04 ----
    def test_get_agent_detail_includes_skill_details(self):
        """Agent detail response embeds product metadata for each skill."""
        user = self._register("ua04", "用户UA04")
        p1 = self._publish(user["username"], "UA04 技能", price=15,
                           category="Skill", content="skill content here")
        agent_r = self.client.post(
            "/api/v4/agents",
            json={"name": "UA04 代理", "description": "", "skill_ids": [p1["id"]]},
            headers=_auth(user["token"]),
        )
        agent_id = agent_r.json()["id"]

        r = self.client.get(f"/api/v4/agents/{agent_id}",
                            headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["id"], agent_id)
        self.assertEqual(len(body["skills"]), 1)
        skill = body["skills"][0]
        self.assertEqual(skill["name"], "UA04 技能")
        self.assertEqual(skill["price"], 15)

    # ---- UA-05 ----
    def test_update_agent_metadata(self):
        """PUT /api/v4/agents/{id} updates name and description."""
        user = self._register("ua05", "用户UA05")
        agent_r = self.client.post(
            "/api/v4/agents",
            json={"name": "旧名称", "description": "旧描述", "skill_ids": []},
            headers=_auth(user["token"]),
        )
        agent_id = agent_r.json()["id"]

        r = self.client.put(
            f"/api/v4/agents/{agent_id}",
            json={"name": "新名称", "description": "新描述"},
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["name"], "新名称")
        self.assertEqual(r.json()["description"], "新描述")

    # ---- UA-06 ----
    def test_other_user_cannot_access_my_agent(self):
        """Agents are scoped to owner; other users get 404 or 403."""
        owner = self._register("ua06_owner", "所有者UA06")
        agent_r = self.client.post(
            "/api/v4/agents",
            json={"name": "UA06 代理", "description": "", "skill_ids": []},
            headers=_auth(owner["token"]),
        )
        agent_id = agent_r.json()["id"]

        stranger = self._register("ua06_stranger", "陌生人UA06")
        r = self.client.get(f"/api/v4/agents/{agent_id}",
                            headers=_auth(stranger["token"]))
        self.assertIn(r.status_code, (403, 404))


# ===========================================================================
# 3. Analytics Dashboard  (AN-01 … AN-06)
# ===========================================================================

class TestAnalyticsDashboard(_V4Base):
    """Product-level and platform-level analytics endpoints."""

    def _setup_popular_product(self, suffix: str) -> tuple[dict, int]:
        seller = self._register(f"seller_{suffix}", f"卖家{suffix}")
        pid = self._publish(seller["username"], f"{suffix} 热门商品",
                            price=100, category="Skill")["id"]
        # Simulate some purchases / views
        for i in range(5):
            buyer = self._register(f"buyer_{suffix}_{i}", f"买家{i}")
            self._buy(buyer, pid)
        return seller, pid

    # ---- AN-01 ----
    def test_product_analytics_returns_views_and_conversions(self):
        """GET analytics for a product returns view count, purchase count,
        conversion rate, and revenue."""
        seller = self._register("an01_seller", "卖家AN01")
        prod = self._publish(seller["username"], "AN01 商品", price=50,
                             category="Skill")
        pid = prod["id"]

        for i in range(4):
            buyer = self._register(f"an01_buyer_{i}", f"买家{i}")
            self._buy(buyer, pid)

        r = self.client.get(
            f"/api/v4/analytics/products/{pid}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("views", body)
        self.assertIn("purchases", body)
        self.assertIn("conversion_rate", body)
        self.assertIn("revenue", body)
        self.assertGreaterEqual(body["purchases"], 4)
        self.assertEqual(body["revenue"], 4 * 50)

    # ---- AN-02 ----
    def test_category_analytics_aggregates_across_products(self):
        """Category analytics groups products by category with totals."""
        seller = self._register("an02_seller", "卖家AN02")
        self._publish(seller["username"], "AN02 技能A", price=30,
                      category="Skill")
        self._publish(seller["username"], "AN02 技能B", price=40,
                      category="Skill")
        self._publish(seller["username"], "AN02 AgentA", price=100,
                      category="Agent")

        r = self.client.get(
            "/api/v4/analytics/categories",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        cats = {c["category"]: c for c in r.json()["categories"]}
        self.assertIn("Skill", cats)
        self.assertIn("Agent", cats)
        self.assertEqual(cats["Skill"]["product_count"], 2)
        self.assertEqual(cats["Agent"]["product_count"], 1)

    # ---- AN-03 ----
    def test_platform_overview_returns_key_metrics(self):
        """GET /api/v4/analytics/overview returns total products, users,
        revenue, and top categories."""
        # Seed a few products
        seller = self._register("an03_seller", "卖家AN03")
        for i in range(3):
            self._publish(seller["username"], f"AN03 商品{i}", price=50,
                          category="Skill")

        r = self.client.get(
            "/api/v4/analytics/overview",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("total_products", body)
        self.assertIn("total_users", body)
        self.assertIn("total_revenue", body)
        self.assertIn("top_categories", body)
        self.assertGreaterEqual(body["total_products"], 3)

    # ---- AN-04 ----
    def test_non_owner_cannot_view_seller_analytics(self):
        """Only the seller of a product can view its detailed analytics."""
        seller = self._register("an04_seller", "卖家AN04")
        prod = self._publish(seller["username"], "AN04 商品", price=50,
                             category="Skill")
        pid = prod["id"]
        stranger = self._register("an04_stranger", "陌生人AN04")

        r = self.client.get(
            f"/api/v4/analytics/products/{pid}",
            headers=_auth(stranger["token"]),
        )
        self.assertEqual(r.status_code, 403, r.text)

    # ---- AN-05 ----
    def test_analytics_tracks_view_on_product_detail(self):
        """Each GET /api/products/{id} increments the view counter."""
        seller = self._register("an05_seller", "卖家AN05")
        prod = self._publish(seller["username"], "AN05 商品", price=50,
                             category="Skill")
        pid = prod["id"]

        for _ in range(5):
            self.client.get(f"/api/products/{pid}")

        r = self.client.get(
            f"/api/v4/analytics/products/{pid}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertGreaterEqual(r.json()["views"], 5)

    # ---- AN-06 ----
    def test_empty_catalog_returns_zero_metrics(self):
        """Analytics for a product with no activity should return zeros."""
        seller = self._register("an06_seller", "卖家AN06")
        prod = self._publish(seller["username"], "AN06 冷门商品", price=50,
                             category="Skill")
        pid = prod["id"]

        r = self.client.get(
            f"/api/v4/analytics/products/{pid}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["purchases"], 0)
        self.assertEqual(body["revenue"], 0)
        self.assertEqual(body["conversion_rate"], 0.0)


# ===========================================================================
# 4. Advanced Search  (AS-01 … AS-06)
# ===========================================================================

class TestAdvancedSearch(_V4Base):
    """Full-text search, combined filters, and saved searches."""

    def _seed_searchable_products(self, seller_name: str):
        self._publish(seller_name, "Python 代码审查助手", price=80,
                      category="Skill", content="自动审查Python代码风格与bug")
        self._publish(seller_name, "周报自动生成器", price=60,
                      category="Skill", content="汇总工作数据生成周报")
        self._publish(seller_name, "数据分析 Agent", price=120,
                      category="Agent", content="智能数据分析与可视化")
        self._publish(seller_name, "GitHub 自动同步", price=40,
                      category="Cron", content="定时同步GitHub仓库")

    # ---- AS-01 ----
    def test_fulltext_search_matches_name_and_content(self):
        """A keyword query should match against product name and content."""
        seller = self._register("as01_seller", "卖家AS01")
        self._seed_searchable_products(seller["username"])

        r = self.client.post(
            "/api/v4/search",
            json={"query": "代码审查", "filters": {}},
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]
        self.assertTrue(len(results) >= 1)
        names = {p["name"] for p in results}
        self.assertIn("Python 代码审查助手", names)

    # ---- AS-02 ----
    def test_combined_filters_category_and_price(self):
        """Category + price range filters should narrow results."""
        seller = self._register("as02_seller", "卖家AS02")
        self._seed_searchable_products(seller["username"])

        r = self.client.post(
            "/api/v4/search",
            json={
                "query": "",
                "filters": {
                    "category": "Agent",
                    "min_price": 100,
                    "max_price": 200,
                },
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["category"], "Agent")
        self.assertGreaterEqual(results[0]["price"], 100)

    # ---- AS-03 ----
    def test_save_and_retrieve_search(self):
        """Saving a search stores filters; listing returns all saved searches."""
        user = self._register("as03_user", "用户AS03")

        payload = {
            "name": "我的代码搜索",
            "query": "代码审查",
            "filters": {"category": "Skill", "min_price": 50},
        }
        r = self.client.post(
            "/api/v4/search/saved",
            json=payload,
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        saved = r.json()
        self.assertEqual(saved["name"], "我的代码搜索")

        r2 = self.client.get(
            "/api/v4/search/saved", headers=_auth(user["token"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        items = r2.json()["saved_searches"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "我的代码搜索")

    # ---- AS-04 ----
    def test_re_run_saved_search(self):
        """Saved search can be re-executed and returns current results."""
        user = self._register("as04_user", "用户AS04")
        seller = self._register("as04_seller", "卖家AS04")
        pid = self._publish(seller["username"], "AS04 商品", price=50,
                            category="Skill")["id"]

        save_r = self.client.post(
            "/api/v4/search/saved",
            json={"name": "重跑测试", "query": "AS04 商品", "filters": {}},
            headers=_auth(user["token"]),
        )
        self.assertEqual(save_r.status_code, 201, save_r.text)
        search_id = save_r.json()["id"]

        r = self.client.post(
            f"/api/v4/search/saved/{search_id}/run",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]
        self.assertTrue(any(p["id"] == pid for p in results))

    # ---- AS-05 ----
    def test_delete_saved_search(self):
        """Deleting a saved search removes it from the user's list."""
        user = self._register("as05_user", "用户AS05")
        save_r = self.client.post(
            "/api/v4/search/saved",
            json={"name": "待删除搜索", "query": "x", "filters": {}},
            headers=_auth(user["token"]),
        )
        search_id = save_r.json()["id"]

        r = self.client.delete(
            f"/api/v4/search/saved/{search_id}",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)

        rows = self._db_saved_searches(user["id"])
        self.assertEqual(len(rows), 0)

    # ---- AS-06 ----
    def test_search_with_no_results_returns_empty_list(self):
        """A query with zero matches should return an empty results array."""
        seller = self._register("as06_seller", "卖家AS06")
        self._seed_searchable_products(seller["username"])

        r = self.client.post(
            "/api/v4/search",
            json={"query": "量子纠缠翻译器", "filters": {}},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["results"], [])


# ===========================================================================
# 5. Skill Bundles  (SB-01 … SB-06)
# ===========================================================================

class TestSkillBundles(_V4Base):
    """Group skills into bundles with discounted pricing."""

    # ---- SB-01 ----
    def test_create_bundle_with_skills_and_discount(self):
        """Seller creates a bundle of 3 skills with a 20 % discount."""
        seller = self._register("sb01_seller", "卖家SB01")
        p1 = self._publish(seller["username"], "SB01 技能A", price=100,
                           category="Skill")
        p2 = self._publish(seller["username"], "SB01 技能B", price=80,
                           category="Skill")
        p3 = self._publish(seller["username"], "SB01 技能C", price=60,
                           category="Skill")

        r = self.client.post(
            "/api/v4/bundles",
            json={
                "name": "SB01 开发包",
                "description": "三个技能打包优惠",
                "product_ids": [p1["id"], p2["id"], p3["id"]],
                "discount_percent": 20,
            },
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        bundle = r.json()
        self.assertEqual(bundle["name"], "SB01 开发包")
        self.assertEqual(bundle["discount_percent"], 20)
        expected = int((100 + 80 + 60) * 0.8)
        self.assertEqual(bundle["bundle_price"], expected)
        self.assertEqual(len(bundle["items"]), 3)

        rows = self._db_bundles()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "SB01 开发包")

    # ---- SB-02 ----
    def test_purchase_bundle_grants_all_skills(self):
        """Buying a bundle grants the buyer licenses for every included skill."""
        seller = self._register("sb02_seller", "卖家SB02")
        p1 = self._publish(seller["username"], "SB02 技能A", price=100)
        p2 = self._publish(seller["username"], "SB02 技能B", price=80)

        bundle_r = self.client.post(
            "/api/v4/bundles",
            json={
                "name": "SB02 包",
                "description": "",
                "product_ids": [p1["id"], p2["id"]],
                "discount_percent": 10,
            },
            headers=_auth(seller["token"]),
        )
        bundle_id = bundle_r.json()["id"]

        buyer = self._register("sb02_buyer", "买家SB02")
        buy_r = self.client.post(
            f"/api/v4/bundles/{bundle_id}/purchase",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(buy_r.status_code, 200, buy_r.text)
        self.assertEqual(buy_r.json()["status"], "completed")

        # Buyer should have licenses for both products
        licenses_p1 = asyncio.run(_fetchall(
            "SELECT * FROM licenses WHERE product_id = ? AND user_id = ?",
            (p1["id"], buyer["id"]),
        ))
        licenses_p2 = asyncio.run(_fetchall(
            "SELECT * FROM licenses WHERE product_id = ? AND user_id = ?",
            (p2["id"], buyer["id"]),
        ))
        self.assertGreaterEqual(len(licenses_p1), 1)
        self.assertGreaterEqual(len(licenses_p2), 1)

    # ---- SB-03 ----
    def test_list_bundles_shows_active_bundles(self):
        """GET bundles returns all published bundles with item counts."""
        seller = self._register("sb03_seller", "卖家SB03")
        p1 = self._publish(seller["username"], "SB03 A", price=50)
        p2 = self._publish(seller["username"], "SB03 B", price=50)

        self.client.post(
            "/api/v4/bundles",
            json={
                "name": "SB03 包",
                "description": "",
                "product_ids": [p1["id"], p2["id"]],
                "discount_percent": 15,
            },
            headers=_auth(seller["token"]),
        )

        r = self.client.get("/api/v4/bundles")
        self.assertEqual(r.status_code, 200, r.text)
        bundles = r.json()["bundles"]
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0]["name"], "SB03 包")
        self.assertEqual(bundles[0]["item_count"], 2)

    # ---- SB-04 ----
    def test_add_skill_to_existing_bundle(self):
        """POST /api/v4/bundles/{id}/skills adds a skill and recalculates price."""
        seller = self._register("sb04_seller", "卖家SB04")
        p1 = self._publish(seller["username"], "SB04 A", price=100)
        p2 = self._publish(seller["username"], "SB04 B", price=100)
        p3 = self._publish(seller["username"], "SB04 C", price=100)

        bundle_r = self.client.post(
            "/api/v4/bundles",
            json={
                "name": "SB04 包",
                "description": "",
                "product_ids": [p1["id"], p2["id"]],
                "discount_percent": 20,
            },
            headers=_auth(seller["token"]),
        )
        bundle_id = bundle_r.json()["id"]

        r = self.client.post(
            f"/api/v4/bundles/{bundle_id}/skills",
            json={"product_id": p3["id"]},
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(len(body["items"]), 3)
        # Price should be recalculated: (100+100+100) * 0.8 = 240
        self.assertEqual(body["bundle_price"], 240)

    # ---- SB-05 ----
    def test_remove_skill_from_bundle(self):
        """DELETE removes a skill and recalculates bundle price."""
        seller = self._register("sb05_seller", "卖家SB05")
        p1 = self._publish(seller["username"], "SB05 A", price=100)
        p2 = self._publish(seller["username"], "SB05 B", price=100)

        bundle_r = self.client.post(
            "/api/v4/bundles",
            json={
                "name": "SB05 包",
                "description": "",
                "product_ids": [p1["id"], p2["id"]],
                "discount_percent": 10,
            },
            headers=_auth(seller["token"]),
        )
        bundle_id = bundle_r.json()["id"]

        r = self.client.delete(
            f"/api/v4/bundles/{bundle_id}/skills/{p2['id']}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(len(body["items"]), 1)
        # Price recalculated: 100 * 0.9 = 90
        self.assertEqual(body["bundle_price"], 90)

    # ---- SB-06 ----
    def test_only_seller_can_modify_bundle(self):
        """Bundle management (add/remove skills) is restricted to seller."""
        seller = self._register("sb06_seller", "卖家SB06")
        attacker = self._register("sb06_attacker", "攻击者SB06")
        p1 = self._publish(seller["username"], "SB06 A", price=50)

        bundle_r = self.client.post(
            "/api/v4/bundles",
            json={
                "name": "SB06 包",
                "description": "",
                "product_ids": [p1["id"]],
                "discount_percent": 0,
            },
            headers=_auth(seller["token"]),
        )
        bundle_id = bundle_r.json()["id"]

        # Add skill as attacker → 403
        p2 = self._publish(seller["username"], "SB06 B", price=50)
        r = self.client.post(
            f"/api/v4/bundles/{bundle_id}/skills",
            json={"product_id": p2["id"]},
            headers=_auth(attacker["token"]),
        )
        self.assertEqual(r.status_code, 403, r.text)

        # Remove skill as attacker → 403
        r2 = self.client.delete(
            f"/api/v4/bundles/{bundle_id}/skills/{p1['id']}",
            headers=_auth(attacker["token"]),
        )
        self.assertEqual(r2.status_code, 403, r2.text)


if __name__ == "__main__":
    unittest.main()
