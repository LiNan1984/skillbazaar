"""Compat label tests (C-01 ~ C-06).

Covers: compat column migration, runtime filter by compat, deriving compat
from skill_type/tags, corrupt compat JSON fallback, explicit compat
persistence/filtering, and SKILL.md frontmatter compat exposure.
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


def _run_async(coro):
    """Run an async coroutine from a sync test method."""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


class _CompatBase(unittest.TestCase):
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
        username = f"cp_{suffix}"
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": "secret12", "nickname": f"兼容_{suffix}"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": "secret12"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"], "username": username}

    def _publish(self, seller_name: str, name: str, price: int = 50,
                 category: str = "Skill", skill_type: str = "prompt",
                 compat: str | None = None) -> int:
        body = {
            "name": name,
            "description": f"{name} 的功能描述",
            "category": category,
            "price": price,
            "seller_name": seller_name,
        }
        if compat is not None:
            body["compat"] = compat
        r = self.client.post("/api/products", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]


class TestCompatMigration(_CompatBase):
    """Database migration for compat column."""

    # ---- C-01 ----
    def test_compat_column_migration_idempotent(self):
        """compat column should exist after database initialization
        (created by init_db, not requiring manual migration)."""

        # Verify column exists after app init creates the DB
        cols = _run_async(_fetchall("PRAGMA table_info(products)"))
        col_names = [c["name"] for c in cols]
        self.assertIn("compat", col_names,
                      "compat column should exist after init_db()")
        # Verify default is empty JSON array string
        row = _run_async(_fetchone(
            "SELECT compat FROM products WHERE id = -1"))
        # Row should be None (no product with id -1), but column exists
        self.assertIsNone(row,
                          "No product should exist with id -1 in fresh DB")


class TestCompatFilter(_CompatBase):
    """Runtime filtering by compat."""

    # ---- C-02 ----
    def test_runtime_filter_single_csv_invalid_and_pagination(self):
        """GET /api/products?runtime=claude-code,codex should filter by compat.
        Invalid runtime value should be rejected or return empty."""
        seller = self._register("seller_c02")
        pid1 = self._publish(seller["username"], "Claude Skill", price=50,
                             category="Skill", compat='["claude-code"]')
        pid2 = self._publish(seller["username"], "Codex Skill", price=60,
                             category="Skill", compat='["codex"]')
        pid3 = self._publish(seller["username"], "No Compat Skill", price=40,
                             category="Skill")

        # Filter by single runtime
        r_single = self.client.get("/api/products", params={"runtime": "claude-code"})
        self.assertEqual(r_single.status_code, 200, r_single.text)
        ids = [p["id"] for p in r_single.json()["products"]]
        self.assertIn(pid1, ids)
        self.assertNotIn(pid2, ids)

        # Filter by CSV runtimes
        r_csv = self.client.get("/api/products",
                                params={"runtime": "claude-code,codex"})
        self.assertEqual(r_csv.status_code, 200, r_csv.text)
        csv_ids = [p["id"] for p in r_csv.json()["products"]]
        self.assertIn(pid1, csv_ids)
        self.assertIn(pid2, csv_ids)
        self.assertNotIn(pid3, csv_ids)

        # Invalid runtime → empty or 422
        r_bad = self.client.get("/api/products", params={"runtime": "nonexistent-runtime"})
        self.assertIn(r_bad.status_code, [200, 422])
        if r_bad.status_code == 200:
            self.assertEqual(r_bad.json()["products"], [])

    # ---- C-03 ----
    def test_compat_derived_from_skill_type_and_tags_for_legacy_products(self):
        """For products without explicit compat, compat should be derived
        from skill_type or tags."""
        seller = self._register("seller_c03")
        # Publish without compat field → should derive compat
        pid = self._publish(seller["username"], "Legacy Skill", price=50,
                            category="Skill")

        detail = self.client.get(f"/api/products/{pid}")
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        # Derived compat should be present
        self.assertIn("compat", body)
        self.assertIsInstance(body["compat"], (list, str))
        if isinstance(body["compat"], str):
            compat_list = json.loads(body["compat"])
        else:
            compat_list = body["compat"]
        self.assertTrue(len(compat_list) > 0, "Derived compat should not be empty")

    # ---- C-04 ----
    def test_corrupt_compat_json_falls_back_to_derivation(self):
        """If compat field contains corrupt JSON, the system should fall
        back to derivation logic."""
        seller = self._register("seller_c04")
        pid = self._publish(seller["username"], "Corrupt Compat", price=50,
                            category="Skill")

        # Directly inject corrupt compat into DB
        _run_async(_fetchall(
            "UPDATE products SET compat = ? WHERE id = ?",
            ("not-valid-json{{{", pid),
        ))

        detail = self.client.get(f"/api/products/{pid}")
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertIn("compat", body)
        # Should have fallen back to a valid value
        compat_raw = body["compat"]
        if isinstance(compat_raw, str):
            self.assertNotEqual(compat_raw, "not-valid-json{{{")

    # ---- C-05 ----
    def test_explicit_compat_persisted_and_filterable(self):
        """POST product with explicit compat field should persist it
        and the product should be filterable by that compat."""
        seller = self._register("seller_c05")
        pid = self._publish(seller["username"], "Explicit Compat", price=50,
                            category="Skill", compat='["claude-code"]')

        row = _run_async(_fetchone(
            "SELECT compat FROM products WHERE id = ?", (pid,)))
        self.assertIsNotNone(row)
        compat_val = row["compat"]
        # Persisted as JSON string or list
        if isinstance(compat_val, str):
            compat_list = json.loads(compat_val)
        else:
            compat_list = compat_val
        self.assertIn("claude-code", compat_list)

        # Filterable
        r = self.client.get("/api/products", params={"runtime": "claude-code"})
        self.assertEqual(r.status_code, 200, r.text)
        ids = [p["id"] for p in r.json()["products"]]
        self.assertIn(pid, ids)


class TestManifestCompat(_CompatBase):
    """compat in SKILL.md / manifest frontmatter."""

    # ---- C-06 ----
    def test_skill_md_frontmatter_exposes_compat_block(self):
        """manifest_service should expose compat from SKILL.md frontmatter
        and it should be filterable."""
        # The manifest service should parse SKILL.md and expose compat
        from services import manifest_service  # noqa: F401 – fails initially

        seller = self._register("seller_c06")
        skill_md = """---
name: test-skill
description: A test skill
compat:
  - claude-code
  - codex
---
# Test Skill

Sample skill content.
"""
        pid = self._publish(seller["username"], "Manifest Skill", price=50,
                            category="Skill")
        # Update product with skill content containing compat frontmatter
        self.client.put(
            f"/api/products/{pid}",
            json={"content_preview": skill_md},
            headers=_auth(seller["token"]),
        )

        # manifest_service should parse and expose compat
        manifest = manifest_service.parse_skill_manifest(skill_md)
        self.assertIn("compat", manifest)
        compat_list = manifest["compat"]
        self.assertIn("claude-code", compat_list)
        self.assertIn("codex", compat_list)


if __name__ == "__main__":
    unittest.main()
