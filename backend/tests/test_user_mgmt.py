"""User management + agent-team session tests against the real FastAPI app.

Uses a temp SQLite file (not the production DB). Does not mock auth_service,
admin_service, agent_service, or the routers under test.
"""
from __future__ import annotations

import asyncio
import os
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


class TestUserManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _register(self, username: str, password: str = "secret12", nickname: str = "") -> dict:
        r = self.client.post(
            "/api/v2/auth/register",
            json={"username": username, "password": password, "nickname": nickname or username},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _login(self, username: str, password: str = "secret12"):
        return self.client.post(
            "/api/v2/auth/login",
            json={"username": username, "password": password},
        )

    def _promote_admin(self, user_id: str) -> None:
        async def _run():
            conn = await aiosqlite.connect(db_mod.DB_PATH)
            try:
                await conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
                await conn.commit()
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_register_login_me_admin_ban_unban_and_agents(self):
        alice = self._register("alice_mgmt")
        login = self._login("alice_mgmt")
        self.assertEqual(login.status_code, 200, login.text)
        body = login.json()
        self.assertTrue(body.get("token"))
        alice_token = body["token"]
        alice_id = body["user_id"]
        self.assertEqual(alice_id, alice["user_id"])

        me = self.client.get("/api/v2/auth/me", headers=_auth(alice_token))
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["user_id"], alice_id)
        self.assertEqual(me.json()["username"], "alice_mgmt")

        admin = self._register("admin_mgmt")
        self._promote_admin(admin["user_id"])
        admin_login = self._login("admin_mgmt")
        self.assertEqual(admin_login.status_code, 200, admin_login.text)
        admin_token = admin_login.json()["token"]

        listed = self.client.get("/api/v2/admin/users", headers=_auth(admin_token))
        self.assertEqual(listed.status_code, 200, listed.text)
        users = listed.json().get("users") or []
        ids = {u.get("id") or u.get("user_id") for u in users}
        self.assertIn(alice_id, ids)
        for u in users:
            self.assertNotIn("password_hash", u)
            self.assertNotIn("auth_token", u)

        forbidden = self.client.get("/api/v2/admin/users", headers=_auth(alice_token))
        self.assertEqual(forbidden.status_code, 403)

        ban = self.client.put(
            f"/api/v2/admin/users/{alice_id}/status",
            params={"status": "banned"},
            headers=_auth(admin_token),
        )
        self.assertEqual(ban.status_code, 200, ban.text)
        self.assertEqual(ban.json().get("status"), "banned")

        banned_login = self._login("alice_mgmt")
        self.assertIn(banned_login.status_code, (401, 403), banned_login.text)
        self.assertFalse((banned_login.json() or {}).get("token"))

        stale_me = self.client.get("/api/v2/auth/me", headers=_auth(alice_token))
        self.assertEqual(stale_me.status_code, 401, stale_me.text)

        stale_agents = self.client.get("/api/agents", headers=_auth(alice_token))
        self.assertEqual(stale_agents.status_code, 401, stale_agents.text)

        unban = self.client.put(
            f"/api/v2/admin/users/{alice_id}/status",
            params={"status": "active"},
            headers=_auth(admin_token),
        )
        self.assertEqual(unban.status_code, 200, unban.text)

        restored = self._login("alice_mgmt")
        self.assertEqual(restored.status_code, 200, restored.text)
        new_token = restored.json()["token"]
        self.assertTrue(new_token)

        agents = self.client.get("/api/agents", headers=_auth(new_token))
        self.assertEqual(agents.status_code, 200, agents.text)
        self.assertIsInstance(agents.json(), list)

        created = self.client.post(
            "/api/agents",
            json={"name": "team-alpha", "description": "user-bound agent", "system_prompt": "", "skill_ids": []},
            headers=_auth(new_token),
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertTrue(created.json().get("id"))
        self.assertEqual(created.json().get("name"), "team-alpha")

        after = self.client.get("/api/agents", headers=_auth(new_token))
        self.assertEqual(after.status_code, 200)
        names = [a.get("name") for a in after.json()]
        self.assertIn("team-alpha", names)

        anon = self.client.get("/api/agents")
        self.assertEqual(anon.status_code, 401, anon.text)

        anon_admin = self.client.get("/api/v2/admin/users")
        self.assertEqual(anon_admin.status_code, 401)

        non_admin_ban = self.client.put(
            f"/api/v2/admin/users/{admin['user_id']}/status",
            params={"status": "banned"},
            headers=_auth(new_token),
        )
        self.assertEqual(non_admin_ban.status_code, 403)


if __name__ == "__main__":
    unittest.main()
