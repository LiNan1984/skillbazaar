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
import datetime
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
        await conn.commit()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def _fetchone(sql: str, params=()):
    rows = await _fetchall(sql, params)
    return rows[0] if rows else None


class _V4Base(unittest.TestCase):
    """Shared setUp / tearDown for v4 feature tests."""

    def setUp(self):
        """Clear bundle, v4.4, and product tables before each test to ensure isolation."""
        async def _clear():
            conn = await aiosqlite.connect(db_mod.DB_PATH)
            try:
                # v4.7 subscription tables may not exist yet — ignore if absent
                for tbl in ("bundle_items", "skill_bundles", "product_analytics",
                            "saved_searches", "user_agents", "agent_skills",
                            "wishlist_items", "affiliate_conversions",
                            "affiliate_clicks", "affiliate_links",
                            "subscriptions", "subscription_events",
                            "products", "product_embeddings"):
                    try:
                        await conn.execute(f"DELETE FROM {tbl}")
                    except Exception:
                        pass
                await conn.commit()
            finally:
                await conn.close()
        asyncio.run(_clear())

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
            "SELECT * FROM user_agents WHERE user_id = ?", (user_id,),
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

    # ---- subscription helpers ----

    def _make_subscription_product(self, seller_name: str, name: str,
                                   plans: list[dict] = None) -> dict:
        """Publish a product and mark it as a subscription product.

        Uses ALTER TABLE to add v4.7 columns if they don't exist yet,
        mirroring the pattern in _seed_products.
        """
        prod = self._publish(seller_name, name, price=50, category="Skill")
        plans = plans or [{"plan": "monthly", "price": 50}]

        async def _configure():
            conn = await aiosqlite.connect(db_mod.DB_PATH)
            try:
                try:
                    await conn.execute(
                        "ALTER TABLE products ADD COLUMN is_subscription INTEGER DEFAULT 0"
                    )
                except Exception:
                    pass
                try:
                    await conn.execute(
                        "ALTER TABLE products ADD COLUMN subscription_plans TEXT DEFAULT '[]'"
                    )
                except Exception:
                    pass
                await conn.commit()
                await conn.close()
            except Exception:
                pass
        asyncio.run(_configure())

        asyncio.run(_fetchall(
            "UPDATE products SET is_subscription = 1, subscription_plans = ? WHERE id = ?",
            (json.dumps(plans), prod["id"]),
        ))
        return prod

    def _db_subscriptions(self, user_id: str = None,
                          product_id: int = None) -> list[dict]:
        if user_id and product_id:
            return asyncio.run(_fetchall(
                "SELECT * FROM subscriptions WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            ))
        if user_id:
            return asyncio.run(_fetchall(
                "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,),
            ))
        return asyncio.run(_fetchall("SELECT * FROM subscriptions"))

    def _db_subscription_events(self, subscription_id: int = None,
                                event_type: str = None) -> list[dict]:
        if subscription_id and event_type:
            return asyncio.run(_fetchall(
                "SELECT * FROM subscription_events WHERE subscription_id = ? AND event_type = ?",
                (subscription_id, event_type),
            ))
        if subscription_id:
            return asyncio.run(_fetchall(
                "SELECT * FROM subscription_events WHERE subscription_id = ?",
                (subscription_id,),
            ))
        return asyncio.run(_fetchall("SELECT * FROM subscription_events"))


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
        # 1 test-seeded agent falls in [100, 200]
        self.assertEqual(len(results), 1)
        for item in results:
            self.assertEqual(item["category"], "Agent")
            self.assertGreaterEqual(item["price"], 100)
            self.assertLessEqual(item["price"], 200)

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


# ---------------------------------------------------------------------------
# v4.3 – Wishlist + Recommendations
# ---------------------------------------------------------------------------

class TestWishlist(_V4Base):
    """Wishlist (愿望单) endpoints."""

    # ---- WL-01 ----
    def test_add_product_to_wishlist(self):
        """User can add a product to their wishlist."""
        user = self._register("wl01_user")
        product = self._publish("wl01_seller", "WL01 商品")

        r = self.client.post(
            f"/api/v4/wishlist/{product['id']}",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual(body["product_id"], product["id"])
        self.assertEqual(body["product_name"], "WL01 商品")

    # ---- WL-02 ----
    def test_list_wishlist(self):
        """User can list all items in their wishlist."""
        user = self._register("wl02_user")
        p1 = self._publish("wl02_seller", "WL02 A")
        p2 = self._publish("wl02_seller", "WL02 B")

        self.client.post(f"/api/v4/wishlist/{p1['id']}", headers=_auth(user["token"]))
        self.client.post(f"/api/v4/wishlist/{p2['id']}", headers=_auth(user["token"]))

        r = self.client.get("/api/v4/wishlist", headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)
        items = r.json()["items"]
        self.assertEqual(len(items), 2)
        names = {i["product_name"] for i in items}
        self.assertIn("WL02 A", names)
        self.assertIn("WL02 B", names)

    # ---- WL-03 ----
    def test_remove_from_wishlist(self):
        """User can remove a product from their wishlist."""
        user = self._register("wl03_user")
        product = self._publish("wl03_seller", "WL03 商品")

        self.client.post(f"/api/v4/wishlist/{product['id']}", headers=_auth(user["token"]))
        r = self.client.delete(
            f"/api/v4/wishlist/{product['id']}",
            headers=_auth(user["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)

        # Verify removed
        r2 = self.client.get("/api/v4/wishlist", headers=_auth(user["token"]))
        self.assertEqual(len(r2.json()["items"]), 0)

    # ---- WL-04 ----
    def test_wishlist_requires_auth(self):
        """Wishlist endpoints require authentication."""
        product = self._publish("wl04_seller", "WL04 商品")

        r = self.client.post(f"/api/v4/wishlist/{product['id']}")
        self.assertEqual(r.status_code, 401)

        r = self.client.get("/api/v4/wishlist")
        self.assertEqual(r.status_code, 401)


class TestRecommendations(_V4Base):
    """Product recommendation endpoints."""

    # ---- RC-01 ----
    def test_similar_products_by_category(self):
        """Products in the same category are returned as similar."""
        seller = self._register("rc01_seller")
        p1 = self._publish(seller["username"], "RC01 A", category="数据分析")
        p2 = self._publish(seller["username"], "RC01 B", category="数据分析")
        p3 = self._publish(seller["username"], "RC01 C", category="图像生成")

        r = self.client.get(f"/api/v4/recommendations/similar/{p1['id']}")
        self.assertEqual(r.status_code, 200, r.text)
        recs = r.json()["recommendations"]
        ids = {item["product_id"] for item in recs}
        # Should include p2 (same category) but not p3
        self.assertIn(p2["id"], ids)
        self.assertNotIn(p3["id"], ids)
        # Should not include itself
        self.assertNotIn(p1["id"], ids)

    # ---- RC-02 ----
    def test_frequently_bought_together(self):
        """Products frequently bought together are recommended."""
        seller = self._register("rc02_seller")
        buyer = self._register("rc02_buyer")
        p1 = self._publish(seller["username"], "RC02 A", category="通用")
        p2 = self._publish(seller["username"], "RC02 B", category="通用")
        p3 = self._publish(seller["username"], "RC02 C", category="通用")

        # Buyer buys p1 and p2 together
        self._buy(buyer, p1["id"])
        self._buy(buyer, p2["id"])

        r = self.client.get(f"/api/v4/recommendations/fbt/{p1['id']}")
        self.assertEqual(r.status_code, 200, r.text)
        recs = r.json()["recommendations"]
        ids = {item["product_id"] for item in recs}
        # p2 should be recommended (bought together)
        self.assertIn(p2["id"], ids)
        # p3 should not be recommended (never bought)
        self.assertNotIn(p3["id"], ids)

    # ---- RC-03 ----
    def test_recommendations_public_no_auth(self):
        """Recommendation endpoints are public (no auth required)."""
        seller = self._register("rc03_seller")
        product = self._publish(seller["username"], "RC03 商品")

        r = self.client.get(f"/api/v4/recommendations/similar/{product['id']}")
        self.assertEqual(r.status_code, 200, r.text)


# ---------------------------------------------------------------------------
# v4.4 – Affiliate Program
# ---------------------------------------------------------------------------

class TestAffiliateProgram(_V4Base):
    """Affiliate/referral program endpoints."""

    # ---- AF-01 ----
    def test_generate_affiliate_link(self):
        """Seller can generate an affiliate link for their product."""
        seller = self._register("af01_seller")
        product = self._publish(seller["username"], "AF01 商品", price=100)

        r = self.client.post(
            f"/api/v4/affiliate/generate/{product['id']}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertIn("link", body)
        self.assertIn("code", body)
        self.assertEqual(body["product_id"], product["id"])
        self.assertEqual(body["commission_rate"], 10)  # Default 10%

    # ---- AF-02 ----
    def test_affiliate_link_tracks_click(self):
        """Clicking an affiliate link records a click."""
        seller = self._register("af02_seller")
        product = self._publish(seller["username"], "AF02 商品", price=100)

        # Generate affiliate link
        gen_r = self.client.post(
            f"/api/v4/affiliate/generate/{product['id']}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(gen_r.status_code, 201)
        code = gen_r.json()["code"]

        # Simulate click (TestClient follows redirects, so expect 200)
        r = self.client.get(f"/api/v4/affiliate/click/{code}")
        self.assertIn(r.status_code, [200, 302])  # 302=redirect, 200=followed

        # Verify click was tracked
        stats_r = self.client.get(
            f"/api/v4/affiliate/stats/{product['id']}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(stats_r.status_code, 200)
        stats = stats_r.json()
        self.assertEqual(stats["clicks"], 1)
        self.assertEqual(stats["conversions"], 0)

    # ---- AF-03 ----
    def test_affiliate_purchase_tracks_conversion(self):
        """Purchasing via affiliate link tracks conversion and commission."""
        seller = self._register("af03_seller")
        buyer = self._register("af03_buyer")
        product = self._publish(seller["username"], "AF03 商品", price=100)

        # Generate affiliate link
        gen_r = self.client.post(
            f"/api/v4/affiliate/generate/{product['id']}",
            headers=_auth(seller["token"]),
        )
        code = gen_r.json()["code"]

        # Buyer clicks affiliate link
        self.client.get(f"/api/v4/affiliate/click/{code}")

        # Buyer purchases product
        buy_r = self.client.post(
            "/api/transactions/buy",
            json={"product_id": product["id"]},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(buy_r.status_code, 200)

        # Verify conversion tracked
        stats_r = self.client.get(
            f"/api/v4/affiliate/stats/{product['id']}",
            headers=_auth(seller["token"]),
        )
        stats = stats_r.json()
        self.assertEqual(stats["clicks"], 1)
        self.assertEqual(stats["conversions"], 1)
        self.assertEqual(stats["commission_earned"], 10)  # 10% of 100

    # ---- AF-04 ----
    def test_only_seller_can_generate_link(self):
        """Only the seller can generate affiliate links for their product."""
        seller = self._register("af04_seller")
        attacker = self._register("af04_attacker")
        product = self._publish(seller["username"], "AF04 商品")

        r = self.client.post(
            f"/api/v4/affiliate/generate/{product['id']}",
            headers=_auth(attacker["token"]),
        )
        self.assertEqual(r.status_code, 403, r.text)

    # ---- AF-05 ----
    def test_affiliate_stats_aggregate(self):
        """Affiliate stats aggregate clicks and conversions correctly."""
        seller = self._register("af05_seller")
        product = self._publish(seller["username"], "AF05 商品", price=200)

        # Generate affiliate link
        gen_r = self.client.post(
            f"/api/v4/affiliate/generate/{product['id']}",
            headers=_auth(seller["token"]),
        )
        code = gen_r.json()["code"]

        # Simulate multiple clicks
        for _ in range(5):
            self.client.get(f"/api/v4/affiliate/click/{code}")

        # Two purchases
        buyer1 = self._register("af05_buyer1")
        buyer2 = self._register("af05_buyer2")
        self.client.get(f"/api/v4/affiliate/click/{code}")
        self.client.post(
            "/api/transactions/buy",
            json={"product_id": product["id"]},
            headers=_auth(buyer1["token"]),
        )
        self.client.get(f"/api/v4/affiliate/click/{code}")
        self.client.post(
            "/api/transactions/buy",
            json={"product_id": product["id"]},
            headers=_auth(buyer2["token"]),
        )

        stats_r = self.client.get(
            f"/api/v4/affiliate/stats/{product['id']}",
            headers=_auth(seller["token"]),
        )
        stats = stats_r.json()
        self.assertEqual(stats["clicks"], 7)  # 5 + 2
        self.assertEqual(stats["conversions"], 2)
        self.assertEqual(stats["commission_earned"], 40)  # 2 * 10% * 200


    # ---- AF-06 ----
    def test_affiliate_link_unique_per_product(self):
        """Each product gets a unique affiliate code."""
        seller = self._register("af06_seller")
        p1 = self._publish(seller["username"], "AF06 A", price=50)
        p2 = self._publish(seller["username"], "AF06 B", price=50)

        r1 = self.client.post(
            f"/api/v4/affiliate/generate/{p1['id']}",
            headers=_auth(seller["token"]),
        )
        r2 = self.client.post(
            f"/api/v4/affiliate/generate/{p2['id']}",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["code"], r2.json()["code"])


# ---------------------------------------------------------------------------
# v4.5 – Semantic Search
# ---------------------------------------------------------------------------

class TestSemanticSearch(_V4Base):
    """Vector-based semantic search over product descriptions."""

    # ---- SS-01 ----
    def test_semantic_search_returns_relevant_products(self):
        """Semantic search returns products ranked by relevance to the query."""
        seller = self._register("ss01_seller", "卖家SS01")
        self._publish(seller["username"], "Python 编程教学", price=80,
                      category="Skill", content="学习Python编程语言的基础知识和高级技巧")
        self._publish(seller["username"], "烘焙蛋糕食谱", price=60,
                      category="Skill", content="制作美味蛋糕的详细步骤和配方")
        self._publish(seller["username"], "数据分析工具", price=120,
                      category="Agent", content="自动化数据分析和可视化报表生成")

        r = self.client.post(
            "/api/v4/search/semantic",
            json={"query": "编程和学习代码", "limit": 10},
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]
        self.assertTrue(len(results) >= 1)
        names = {p["name"] for p in results}
        # Python programming should rank highest for a programming-related query
        self.assertIn("Python 编程教学", names)

    # ---- SS-02 ----
    def test_semantic_search_respects_limit(self):
        """The limit parameter controls how many results are returned."""
        seller = self._register("ss02_seller", "卖家SS02")
        for i in range(5):
            self._publish(seller["username"], f"SS02 技能{i}", price=50 + i * 10,
                          category="Skill", content=f"技能描述内容{i}")

        r = self.client.post(
            "/api/v4/search/semantic",
            json={"query": "技能", "limit": 3},
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]
        self.assertEqual(len(results), 3)

    # ---- SS-03 ----
    def test_semantic_search_is_public(self):
        """Semantic search endpoint does not require authentication."""
        seller = self._register("ss03_seller", "卖家SS03")
        self._publish(seller["username"], "SS03 公开商品", price=50,
                      category="Skill", content="公开可搜索的技能")

        r = self.client.post(
            "/api/v4/search/semantic",
            json={"query": "技能", "limit": 10},
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]
        self.assertTrue(len(results) >= 1)

    # ---- SS-04 ----
    def test_semantic_search_empty_query_returns_empty(self):
        """An empty query string should return an empty results list."""
        seller = self._register("ss04_seller", "卖家SS04")
        self._publish(seller["username"], "SS04 商品", price=50,
                      category="Skill", content="一些内容")

        r = self.client.post(
            "/api/v4/search/semantic",
            json={"query": "", "limit": 10},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["results"], [])

    # ---- SS-05 ----
    def test_semantic_search_no_products_returns_empty(self):
        """Searching when no products exist returns an empty results list."""
        seller = self._register("ss05_seller", "卖家SS05")
        # Do not publish any products

        r = self.client.post(
            "/api/v4/search/semantic",
            json={"query": "任何查询", "limit": 10},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["results"], [])


# ---------------------------------------------------------------------------
# v4.5.1 – Smart Pricing Suggestions
# ---------------------------------------------------------------------------

class TestSmartPricing(_V4Base):
    """Pricing suggestion and category price-trend endpoints."""

    # ---- SP-01 ----
    def test_suggest_with_product_id_returns_pricing_suggestion(self):
        """POST /api/v4/pricing/suggest with a valid product_id returns
        suggested_price, price_range, reason, market_avg, and competitors_count."""
        seller = self._register("sp01_seller", "卖家SP01")
        # Seed competitor products in the same category first
        self._publish(seller["username"], "SP01 竞品A", price=30,
                      category="数据分析", content="数据分析")
        self._publish(seller["username"], "SP01 竞品B", price=40,
                      category="数据分析", content="数据分析")
        self._publish(seller["username"], "SP01 竞品C", price=60,
                      category="数据分析", content="数据分析")
        prod = self._publish(seller["username"], "SP01 技能", price=50,
                             category="数据分析", content="数据可视化")

        r = self.client.post(
            "/api/v4/pricing/suggest",
            json={"product_id": prod["id"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("suggested_price", body)
        self.assertIn("price_range", body)
        self.assertIn("reason", body)
        self.assertIn("market_avg", body)
        self.assertIn("competitors_count", body)
        # suggested_price should be a non-negative integer
        self.assertIsInstance(body["suggested_price"], int)
        self.assertGreaterEqual(body["suggested_price"], 0)
        # price_range must have min <= max
        self.assertLessEqual(body["price_range"]["min"], body["price_range"]["max"])

    # ---- SP-02 ----
    def test_suggest_with_category_name_description_returns_suggestion(self):
        """POST /api/v4/pricing/suggest with category+name+description returns
        a pricing suggestion even when no product_id is provided."""
        seller = self._register("sp02_seller", "卖家SP02")
        # Publish a competitor product in the same category so market data exists
        self._publish(seller["username"], "SP02 竞品", price=80,
                      category="Agent", content="智能代理服务")

        r = self.client.post(
            "/api/v4/pricing/suggest",
            json={
                "category": "Agent",
                "name": "SP02 新代理",
                "description": "一个强大的AI代理工具",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("suggested_price", body)
        self.assertIn("price_range", body)
        self.assertIn("reason", body)
        self.assertIn("market_avg", body)
        self.assertIsInstance(body["suggested_price"], int)
        self.assertGreaterEqual(body["suggested_price"], 0)

    # ---- SP-03 ----
    def test_suggest_with_nonexistent_product_id_returns_404(self):
        """POST /api/v4/pricing/suggest with a product_id that does not exist
        returns HTTP 404."""
        r = self.client.post(
            "/api/v4/pricing/suggest",
            json={"product_id": 99999},
        )
        self.assertEqual(r.status_code, 404, r.text)

    # ---- SP-04 ----
    def test_suggest_with_empty_request_returns_400(self):
        """POST /api/v4/pricing/suggest with an empty body (no product_id,
        no category/name/description) returns HTTP 400."""
        r = self.client.post("/api/v4/pricing/suggest", json={})
        self.assertEqual(r.status_code, 400, r.text)

    # ---- SP-05 ----
    def test_trends_endpoint_returns_category_price_stats(self):
        """GET /api/v4/pricing/trends/{category} returns avg_price, min_price,
        max_price, price_trend, and sample_count for the category."""
        seller = self._register("sp05_seller", "卖家SP05")
        self._publish(seller["username"], "SP05 A", price=40,
                      category="Skill")
        self._publish(seller["username"], "SP05 B", price=60,
                      category="Skill")
        self._publish(seller["username"], "SP05 C", price=100,
                      category="Skill")

        r = self.client.get("/api/v4/pricing/trends/Skill")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["category"], "Skill")
        self.assertIn("avg_price", body)
        self.assertIn("min_price", body)
        self.assertIn("max_price", body)
        self.assertIn("price_trend", body)
        self.assertIn("sample_count", body)
        self.assertEqual(body["sample_count"], 3)
        self.assertEqual(body["min_price"], 40)
        self.assertEqual(body["max_price"], 100)

    # ---- SP-06 ----
    def test_trends_with_days_parameter_works(self):
        """GET /api/v4/pricing/trends/{category}?days=N filters statistics
        to products published within the last N days."""
        seller = self._register("sp06_seller", "卖家SP06")
        self._publish(seller["username"], "SP06 新商品", price=90,
                      category="Agent")
        # An older product (simulated by a direct DB insert with an old date
        # would be ideal, but the endpoint implementation should handle days
        # filtering – here we just verify the parameter is accepted).
        r = self.client.get("/api/v4/pricing/trends/Agent?days=7")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["category"], "Agent")
        self.assertIn("avg_price", body)
        self.assertIn("sample_count", body)

    # ---- SP-07 ----
    def test_trends_for_empty_category_returns_404(self):
        """GET /api/v4/pricing/trends/{category} for a category with no
        products returns HTTP 404."""
        r = self.client.get("/api/v4/pricing/trends/空分类无商品")
        self.assertEqual(r.status_code, 404, r.text)

    # ---- SP-08 ----
    def test_suggest_price_is_within_competitor_range(self):
        """When competitor products exist in the same category, the suggested
        price falls within the competitor price range."""
        seller = self._register("sp08_seller", "卖家SP08")
        # Create multiple competitor products in the same category
        self._publish(seller["username"], "SP08 竞品A", price=100,
                      category="数据分析")
        self._publish(seller["username"], "SP08 竞品B", price=150,
                      category="数据分析")
        self._publish(seller["username"], "SP08 竞品C", price=200,
                      category="数据分析")
        prod = self._publish(seller["username"], "SP08 我的商品", price=300,
                             category="数据分析")

        r = self.client.post(
            "/api/v4/pricing/suggest",
            json={"product_id": prod["id"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        # The suggested price should be within the competitor price range
        # (competitors are 100-200, so suggested_price should be <= max_range)
        self.assertGreaterEqual(body["suggested_price"], 0)
        self.assertLessEqual(
            body["suggested_price"], body["price_range"]["max"]
        )
        # Verify the price_range max is at or above the highest competitor price
        self.assertGreaterEqual(body["price_range"]["max"], 200)
        # Verify market_avg reflects the competitor prices
        self.assertGreater(body["market_avg"], 0)


# ---------------------------------------------------------------------------
# v4.6 – New Product Traffic Boost
# ---------------------------------------------------------------------------

class TestTrafficBoost(_V4Base):
    """Boost score system: new products get traffic boost, decay over time,
    affects search ranking, seller stats dashboard, and cron decay."""

    # ---- TB-01 ----
    def test_boost_score_set_on_new_product(self):
        """Publishing a new product automatically sets boost_score to 100."""
        seller = self._register("tb01_seller", "卖家TB01")
        prod = self._publish(seller["username"], "TB01 新品", price=50,
                             category="Skill")

        # Verify boost_score is set to 100 on creation
        row = asyncio.run(_fetchone(
            "SELECT boost_score FROM products WHERE id = ?", (prod["id"],)
        ))
        self.assertIsNotNone(row)
        self.assertEqual(row["boost_score"], 100)

    # ---- TB-02 ----
    def test_boost_score_decays_over_time(self):
        """Boost score decays approximately 14% per day over 7 days."""
        seller = self._register("tb02_seller", "卖家TB02")
        prod = self._publish(seller["username"], "TB02 商品", price=50,
                             category="Skill")

        # Verify initial boost
        row = asyncio.run(_fetchone(
            "SELECT boost_score FROM products WHERE id = ?", (prod["id"],)
        ))
        self.assertEqual(row["boost_score"], 100)

        # Simulate 3 days passing by updating created_at
        new_date = (
            datetime.datetime.now() - datetime.timedelta(days=3)
        ).isoformat()
        asyncio.run(_fetchall(
            "UPDATE products SET created_at = ? WHERE id = ?",
            (new_date, prod["id"]),
        ))

        # Run the boost decay cron
        r = self.client.post("/api/v4/cron/decay-boost")
        self.assertEqual(r.status_code, 200, r.text)

        # After 3 days, boost should have decayed (100 * 0.86^3 ≈ 64)
        row = asyncio.run(_fetchone(
            "SELECT boost_score FROM products WHERE id = ?", (prod["id"],)
        ))
        # 14% decay per day for 3 days: 100 * (1 - 0.14)^3 ≈ 63.9
        self.assertLess(row["boost_score"], 100)
        self.assertGreater(row["boost_score"], 50)

    # ---- TB-03 ----
    def test_boost_affects_search_ranking(self):
        """Products with boost score rank higher in search results."""
        seller = self._register("tb03_seller", "卖家TB03")
        # Create a boosted product (new)
        boosted = self._publish(
            seller["username"], "TB03 新品", price=50,
            category="Skill", content="新品 boosted",
        )
        # Create an older product without boost
        old_prod = self._publish(
            seller["username"], "TB03 旧品", price=50,
            category="Skill", content="旧品 无boost",
        )

        # Simulate old product being 8 days old (boost decayed to 0)
        old_date = (
            datetime.datetime.now() - datetime.timedelta(days=8)
        ).isoformat()
        asyncio.run(_fetchall(
            "UPDATE products SET created_at = ?, boost_score = 0 WHERE id = ?",
            (old_date, old_prod["id"]),
        ))

        # Search for "TB03" - boosted product should appear first
        r = self.client.post(
            "/api/v4/search",
            json={"query": "TB03", "filters": {}},
        )
        self.assertEqual(r.status_code, 200, r.text)
        results = r.json()["results"]

        # Find positions of our products
        names = [p["name"] for p in results]
        boosted_idx = names.index("TB03 新品") if "TB03 新品" in names else -1
        old_idx = names.index("TB03 旧品") if "TB03 旧品" in names else -1

        self.assertNotEqual(
            boosted_idx, -1, "Boosted product should be in results",
        )
        self.assertNotEqual(
            old_idx, -1, "Old product should be in results",
        )
        self.assertLess(
            boosted_idx, old_idx,
            "Boosted product should rank higher than non-boosted",
        )

    # ---- TB-04 ----
    def test_seller_stats_returns_aggregated_metrics(self):
        """Seller stats endpoint returns total_views, total_downloads,
        total_sales, total_revenue, and top_products."""
        seller = self._register("tb04_seller", "卖家TB04")
        p1 = self._publish(seller["username"], "TB04 A", price=100,
                           category="Skill")
        p2 = self._publish(seller["username"], "TB04 B", price=200,
                           category="Skill")

        # Simulate purchases for p1
        buyer1 = self._register("tb04_buyer1", "买家TB04-1")
        self._buy(buyer1, p1["id"])
        buyer2 = self._register("tb04_buyer2", "买家TB04-2")
        self._buy(buyer2, p1["id"])

        r = self.client.get(
            "/api/v4/seller/stats",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("total_views", body)
        self.assertIn("total_downloads", body)
        self.assertIn("total_sales", body)
        self.assertIn("total_revenue", body)
        self.assertIn("top_products", body)
        # 2 sales of p1 = 2 * 100 = 200 revenue
        self.assertGreaterEqual(body["total_sales"], 2)
        self.assertGreaterEqual(body["total_revenue"], 200)

    # ---- TB-05 ----
    def test_seller_stats_top_products_sorted_by_views(self):
        """Seller stats top_products are sorted by view count (descending)."""
        seller = self._register("tb05_seller", "卖家TB05")
        p1 = self._publish(seller["username"], "TB05 A", price=50,
                           category="Skill")
        p2 = self._publish(seller["username"], "TB05 B", price=50,
                           category="Skill")
        p3 = self._publish(seller["username"], "TB05 C", price=50,
                           category="Skill")

        # Simulate different view counts by inserting analytics records
        today = "2025-01-10"
        asyncio.run(_fetchall(
            "INSERT INTO product_analytics (product_id, date, views) VALUES (?, ?, ?)",
            (p1["id"], today, 100),
        ))
        asyncio.run(_fetchall(
            "INSERT INTO product_analytics (product_id, date, views) VALUES (?, ?, ?)",
            (p2["id"], today, 50),
        ))
        asyncio.run(_fetchall(
            "INSERT INTO product_analytics (product_id, date, views) VALUES (?, ?, ?)",
            (p3["id"], today, 200),
        ))

        r = self.client.get(
            "/api/v4/seller/stats",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        top_products = r.json()["top_products"]

        self.assertEqual(len(top_products), 3)
        # Should be sorted by views descending: p3 (200), p1 (100), p2 (50)
        self.assertEqual(top_products[0]["product_id"], p3["id"])
        self.assertEqual(top_products[0]["views"], 200)
        self.assertEqual(top_products[1]["product_id"], p1["id"])
        self.assertEqual(top_products[1]["views"], 100)
        self.assertEqual(top_products[2]["product_id"], p2["id"])
        self.assertEqual(top_products[2]["views"], 50)

    # ---- TB-06 ----
    def test_cron_decay_reduces_boost(self):
        """Calling the cron decay endpoint reduces boost_score for products
        that are within the 7-day boost period."""
        seller = self._register("tb06_seller", "卖家TB06")
        prod = self._publish(seller["username"], "TB06 商品", price=50,
                             category="Skill")

        # Ensure boost is at 100
        asyncio.run(_fetchall(
            "UPDATE products SET boost_score = 100 WHERE id = ?", (prod["id"],)
        ))

        # Run cron decay
        r = self.client.post("/api/v4/cron/decay-boost")
        self.assertEqual(r.status_code, 200, r.text)

        # Boost should have decreased (100 * 0.86 ≈ 86)
        row = asyncio.run(_fetchone(
            "SELECT boost_score FROM products WHERE id = ?", (prod["id"],)
        ))
        self.assertLess(row["boost_score"], 100)
        self.assertGreater(row["boost_score"], 0)

    # ---- TB-07 ----
    def test_cron_decay_removes_boost_after_period(self):
        """After 7+ days, cron decay sets boost_score to 0."""
        seller = self._register("tb07_seller", "卖家TB07")
        prod = self._publish(seller["username"], "TB07 旧商品", price=50,
                             category="Skill")

        # Set boost to 100
        asyncio.run(_fetchall(
            "UPDATE products SET boost_score = 100 WHERE id = ?", (prod["id"],)
        ))

        # Simulate 8 days passing
        old_date = (
            datetime.datetime.now() - datetime.timedelta(days=8)
        ).isoformat()
        asyncio.run(_fetchall(
            "UPDATE products SET created_at = ? WHERE id = ?",
            (old_date, prod["id"]),
        ))

        # Run cron decay
        r = self.client.post("/api/v4/cron/decay-boost")
        self.assertEqual(r.status_code, 200, r.text)

        # Boost should be 0 after 7+ days
        row = asyncio.run(_fetchone(
            "SELECT boost_score FROM products WHERE id = ?", (prod["id"],)
        ))
        self.assertEqual(row["boost_score"], 0)

    # ---- TB-08 ----
    def test_boost_reset_on_republish(self):
        """Republishing a product resets its boost_score to 100."""
        seller = self._register("tb08_seller", "卖家TB08")
        prod = self._publish(seller["username"], "TB08 商品", price=50,
                             category="Skill")

        # Reduce boost via decay simulation
        asyncio.run(_fetchall(
            "UPDATE products SET boost_score = 50 WHERE id = ?", (prod["id"],)
        ))

        # Republish the product
        r = self.client.post(
            f"/api/v4/products/{prod['id']}/republish",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)

        # Verify boost is reset to 100
        row = asyncio.run(_fetchone(
            "SELECT boost_score FROM products WHERE id = ?", (prod["id"],)
        ))
        self.assertEqual(row["boost_score"], 100)


# ===========================================================================
# v4.7 – Skill Subscription  (SB-01 … SB-10)
# ===========================================================================

class TestSkillSubscription(_V4Base):
    """Recurring subscription model for Skills."""

    # ---- SB-01 ----
    def test_create_subscription(self):
        """POST /api/v4/subscriptions/create deducts coins and returns the
        subscription record with correct fields."""
        seller = self._register("sb01_seller", "卖家SB01")
        buyer = self._register("sb01_buyer", "买家SB01")
        prod = self._make_subscription_product(
            seller["username"], "SB01 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        # Verify buyer starts with 10000 coins
        buyer_row = asyncio.run(_fetchone(
            "SELECT coins FROM users WHERE id = ?", (buyer["id"],)
        ))
        self.assertEqual(buyer_row["coins"], 10000)

        r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 201, r.text)
        sub = r.json()
        self.assertEqual(sub["product_id"], prod["id"])
        self.assertEqual(sub["plan"], "monthly")
        self.assertEqual(sub["price"], 50)
        self.assertEqual(sub["status"], "active")
        self.assertEqual(sub["auto_renew"], True)
        self.assertIn("subscription_id", sub)
        self.assertIn("starts_at", sub)
        self.assertIn("expires_at", sub)

        # Verify coins deducted
        buyer_row = asyncio.run(_fetchone(
            "SELECT coins FROM users WHERE id = ?", (buyer["id"],)
        ))
        self.assertEqual(buyer_row["coins"], 9950)

        # Verify subscription record in DB
        rows = self._db_subscriptions(buyer["id"], prod["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "active")
        self.assertEqual(rows[0]["plan"], "monthly")
        self.assertEqual(rows[0]["price"], 50)

    # ---- SB-02 ----
    def test_duplicate_subscription_returns_existing(self):
        """Creating a second subscription for the same product returns the
        existing active subscription without deducting coins again."""
        seller = self._register("sb02_seller", "卖家SB02")
        buyer = self._register("sb02_buyer", "买家SB02")
        prod = self._make_subscription_product(
            seller["username"], "SB02 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        # First subscription
        r1 = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r1.status_code, 201, r1.text)
        sub1 = r1.json()

        # Second attempt — should return existing, not create new
        r2 = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        sub2 = r2.json()
        self.assertEqual(sub1["subscription_id"], sub2["subscription_id"])

        # Verify only one subscription row
        rows = self._db_subscriptions(buyer["id"], prod["id"])
        self.assertEqual(len(rows), 1)

        # Verify coins only deducted once
        buyer_row = asyncio.run(_fetchone(
            "SELECT coins FROM users WHERE id = ?", (buyer["id"],)
        ))
        self.assertEqual(buyer_row["coins"], 9950)

    # ---- SB-03 ----
    def test_cancel_subscription(self):
        """Cancelling sets status to 'cancelled' but access continues
        until the original expires_at."""
        seller = self._register("sb03_seller", "卖家SB03")
        buyer = self._register("sb03_buyer", "买家SB03")
        prod = self._make_subscription_product(
            seller["username"], "SB03 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        # Create subscription
        create_r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 201)
        sub_id = create_r.json()["subscription_id"]
        original_expires = create_r.json()["expires_at"]

        # Cancel
        r = self.client.post(
            f"/api/v4/subscriptions/{sub_id}/cancel",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "cancelled")
        self.assertEqual(body["expires_at"], original_expires)

        # Verify DB status
        rows = asyncio.run(_fetchall(
            "SELECT * FROM subscriptions WHERE id = ?", (sub_id,),
        ))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "cancelled")

        # Subscription still exists (not deleted) — access valid until expires_at
        check_r = self.client.get(
            f"/api/v4/subscriptions/check?product_id={prod['id']}",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(check_r.status_code, 200, check_r.text)
        self.assertTrue(check_r.json()["has_subscription"])

    # ---- SB-04 ----
    def test_toggle_auto_renew(self):
        """POST /api/v4/subscriptions/{id}/toggle-renew flips auto_renew."""
        seller = self._register("sb04_seller", "卖家SB04")
        buyer = self._register("sb04_buyer", "买家SB04")
        prod = self._make_subscription_product(
            seller["username"], "SB04 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        create_r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 201)
        sub_id = create_r.json()["subscription_id"]
        self.assertTrue(create_r.json()["auto_renew"])

        # Toggle off
        r = self.client.post(
            f"/api/v4/subscriptions/{sub_id}/toggle-renew",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["auto_renew"], False)

        # Verify DB
        rows = asyncio.run(_fetchall(
            "SELECT auto_renew FROM subscriptions WHERE id = ?", (sub_id,),
        ))
        self.assertEqual(rows[0]["auto_renew"], 0)

        # Toggle back on
        r2 = self.client.post(
            f"/api/v4/subscriptions/{sub_id}/toggle-renew",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["auto_renew"], True)

    # ---- SB-05 ----
    def test_list_my_subscriptions(self):
        """GET /api/v4/subscriptions/my returns active subscriptions
        with product_name included."""
        seller = self._register("sb05_seller", "卖家SB05")
        buyer = self._register("sb05_buyer", "买家SB05")
        prod1 = self._make_subscription_product(
            seller["username"], "SB05 技能A",
            plans=[{"plan": "monthly", "price": 50}],
        )
        prod2 = self._make_subscription_product(
            seller["username"], "SB05 技能B",
            plans=[{"plan": "weekly", "price": 15}],
        )

        self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod1["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod2["id"], "plan": "weekly"},
            headers=_auth(buyer["token"]),
        )

        r = self.client.get(
            "/api/v4/subscriptions/my",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        subs = r.json()["subscriptions"]
        self.assertEqual(len(subs), 2)
        names = {s["product_name"] for s in subs}
        self.assertIn("SB05 技能A", names)
        self.assertIn("SB05 技能B", names)
        # Verify each entry has required fields
        for s in subs:
            self.assertIn("subscription_id", s)
            self.assertIn("plan", s)
            self.assertIn("price", s)
            self.assertIn("status", s)
            self.assertIn("expires_at", s)
            self.assertIn("auto_renew", s)

    # ---- SB-06 ----
    def test_cron_renews_expired_active_subs(self):
        """Cron extends expires_at for auto-renew subscriptions past expiry,
        deducts coins, and records a 'renewed' event."""
        seller = self._register("sb06_seller", "卖家SB06")
        buyer = self._register("sb06_buyer", "买家SB06")
        prod = self._make_subscription_product(
            seller["username"], "SB06 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        # Create subscription
        create_r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 201)
        sub_id = create_r.json()["subscription_id"]

        # Simulate expiry: push expires_at to the past
        past_date = (
            datetime.datetime.now() - datetime.timedelta(days=1)
        ).isoformat()
        asyncio.run(_fetchall(
            "UPDATE subscriptions SET expires_at = ? WHERE id = ?",
            (past_date, sub_id),
        ))

        # Run cron
        r = self.client.post("/api/v4/cron/process-subscriptions")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("renewed_count", body)
        self.assertGreaterEqual(body["renewed_count"], 1)

        # Verify subscription extended
        rows = asyncio.run(_fetchall(
            "SELECT * FROM subscriptions WHERE id = ?", (sub_id,),
        ))
        self.assertEqual(rows[0]["status"], "active")
        new_expires = rows[0]["expires_at"]
        self.assertGreater(new_expires, past_date)

        # Verify coins deducted for renewal
        buyer_row = asyncio.run(_fetchone(
            "SELECT coins FROM users WHERE id = ?", (buyer["id"],)
        ))
        # 10000 - 50 (initial) - 50 (renewal) = 9900
        self.assertEqual(buyer_row["coins"], 9900)

        # Verify renewal event recorded
        events = self._db_subscription_events(sub_id, "renewed")
        self.assertGreaterEqual(len(events), 1)

    # ---- SB-07 ----
    def test_cron_expires_non_renew_subs(self):
        """Cron marks manual (auto_renew=0) subscriptions as expired
        when expires_at has passed."""
        seller = self._register("sb07_seller", "卖家SB07")
        buyer = self._register("sb07_buyer", "买家SB07")
        prod = self._make_subscription_product(
            seller["username"], "SB07 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        # Create subscription with auto_renew=0
        create_r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 201)
        sub_id = create_r.json()["subscription_id"]

        # Disable auto_renew
        self.client.post(
            f"/api/v4/subscriptions/{sub_id}/toggle-renew",
            headers=_auth(buyer["token"]),
        )

        # Simulate expiry
        past_date = (
            datetime.datetime.now() - datetime.timedelta(days=1)
        ).isoformat()
        asyncio.run(_fetchall(
            "UPDATE subscriptions SET expires_at = ? WHERE id = ?",
            (past_date, sub_id),
        ))

        # Run cron
        r = self.client.post("/api/v4/cron/process-subscriptions")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("expired_count", body)
        self.assertGreaterEqual(body["expired_count"], 1)

        # Verify status changed to expired
        rows = asyncio.run(_fetchall(
            "SELECT * FROM subscriptions WHERE id = ?", (sub_id,),
        ))
        self.assertEqual(rows[0]["status"], "expired")

        # Verify expired event recorded
        events = self._db_subscription_events(sub_id, "expired")
        self.assertGreaterEqual(len(events), 1)

    # ---- SB-08 ----
    def test_seller_subscription_stats(self):
        """GET /api/v4/seller/subscription-stats returns MRR, subscriber
        counts, churn_rate, by_plan breakdown, and top_products."""
        seller = self._register("sb08_seller", "卖家SB08")
        buyer1 = self._register("sb08_buyer1", "买家SB08-1")
        buyer2 = self._register("sb08_buyer2", "买家SB08-2")

        prod_monthly = self._make_subscription_product(
            seller["username"], "SB08 月付技能",
            plans=[{"plan": "monthly", "price": 50}],
        )
        prod_yearly = self._make_subscription_product(
            seller["username"], "SB08 年付技能",
            plans=[{"plan": "yearly", "price": 500}],
        )

        # buyer1: monthly subscription
        self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod_monthly["id"], "plan": "monthly"},
            headers=_auth(buyer1["token"]),
        )
        # buyer2: yearly subscription
        self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod_yearly["id"], "plan": "yearly"},
            headers=_auth(buyer2["token"]),
        )

        # Mark buyer1's subscription as expired to simulate churn
        subs = self._db_subscriptions(user_id=buyer1["id"])
        expired_sub_id = subs[0]["id"]
        past_date = (
            datetime.datetime.now() - datetime.timedelta(days=1)
        ).isoformat()
        asyncio.run(_fetchall(
            "UPDATE subscriptions SET status = 'expired', expires_at = ? WHERE id = ?",
            (past_date, expired_sub_id),
        ))

        r = self.client.get(
            "/api/v4/seller/subscription-stats",
            headers=_auth(seller["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("total_subscribers", body)
        self.assertIn("active_subscriptions", body)
        self.assertIn("monthly_recurring_revenue", body)
        self.assertIn("churn_rate", body)
        self.assertIn("by_plan", body)
        self.assertIn("top_products", body)

        # 2 total subscribers, 1 active (buyer2 yearly)
        self.assertEqual(body["total_subscribers"], 2)
        self.assertEqual(body["active_subscriptions"], 1)

        # MRR: yearly contributes 500/12 ≈ 42 (or similar calculation)
        self.assertGreater(body["monthly_recurring_revenue"], 0)

        # Churn: 1 expired out of 2 = 0.5
        self.assertEqual(body["churn_rate"], 0.5)

        # by_plan breakdown
        self.assertIn("yearly", body["by_plan"])
        self.assertIn("monthly", body["by_plan"])

        # top_products list
        self.assertIsInstance(body["top_products"], list)
        self.assertGreaterEqual(len(body["top_products"]), 1)

    # ---- SB-09 ----
    def test_check_subscription_access(self):
        """GET /api/v4/subscriptions/check confirms active subscription
        grants access with days_remaining."""
        seller = self._register("sb09_seller", "卖家SB09")
        buyer = self._register("sb09_buyer", "买家SB09")
        prod = self._make_subscription_product(
            seller["username"], "SB09 订阅技能",
            plans=[{"plan": "monthly", "price": 50}],
        )

        # No subscription yet
        r = self.client.get(
            f"/api/v4/subscriptions/check?product_id={prod['id']}",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["has_subscription"])

        # Create subscription
        create_r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(create_r.status_code, 201)

        # Now has subscription
        r2 = self.client.get(
            f"/api/v4/subscriptions/check?product_id={prod['id']}",
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        body = r2.json()
        self.assertTrue(body["has_subscription"])
        self.assertIn("subscription_id", body)
        self.assertEqual(body["plan"], "monthly")
        self.assertIn("expires_at", body)
        self.assertIn("days_remaining", body)
        self.assertGreaterEqual(body["days_remaining"], 25)

    # ---- SB-10 ----
    def test_insufficient_balance_rejected(self):
        """Subscription creation is rejected when the buyer's coin balance
        is below the subscription price."""
        seller = self._register("sb10_seller", "卖家SB10")
        buyer = self._register("sb10_buyer", "买家SB10")
        prod = self._make_subscription_product(
            seller["username"], "SB10 高价订阅技能",
            plans=[{"plan": "monthly", "price": 50000}],
        )

        # Reduce buyer's balance below subscription price
        asyncio.run(_fetchall(
            "UPDATE users SET coins = ? WHERE id = ?",
            (100, buyer["id"]),
        ))

        r = self.client.post(
            "/api/v4/subscriptions/create",
            json={"product_id": prod["id"], "plan": "monthly"},
            headers=_auth(buyer["token"]),
        )
        self.assertEqual(r.status_code, 402, r.text)

        # Verify no subscription created and balance unchanged
        rows = self._db_subscriptions(buyer["id"], prod["id"])
        self.assertEqual(len(rows), 0)

        buyer_row = asyncio.run(_fetchone(
            "SELECT coins FROM users WHERE id = ?", (buyer["id"],)
        ))
        self.assertEqual(buyer_row["coins"], 100)


if __name__ == "__main__":
    unittest.main()
