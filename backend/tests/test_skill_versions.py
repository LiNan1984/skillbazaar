"""Skill Versioning tests (v4 P0).

Tests the skill_versions API:
  POST /api/v4/products/{id}/versions   - create new version
  GET  /api/v4/products/{id}/versions   - list all versions
  GET  /api/v4/products/{id}/versions/{v} - get specific version
  PUT  /api/v4/products/{id}/versions/{v} - update changelog
  POST /api/v4/products/{id}/versions/rollback - rollback to version
"""
from __future__ import annotations

import asyncio
import json
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


class TestSkillVersioning(unittest.TestCase):
    """New versions of a skill: create, list, retrieve, update, rollback."""

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
        username = f"sv_{suffix}"
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
        return {"id": uid, "token": login.json()["token"],
                "nickname": nick, "username": username}

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

    def _db_versions(self, product_id: int) -> list[dict]:
        return asyncio.run(_fetchall(
            "SELECT * FROM skill_versions WHERE product_id = ? ORDER BY id ASC",
            (product_id,),
        ))

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

        rows = self._db_versions(prod["id"])
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
        """PUT on a version updates changelog but not content."""
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

        rows = self._db_versions(prod["id"])
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

        rows = self._db_versions(prod["id"])
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
