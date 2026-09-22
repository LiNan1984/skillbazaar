"""Skill 包 zip 下载端点测试。

覆盖 GET /api/skills/{product_id}/download：
  · 未购买时 code / sdk 类型返回 403，prompt 类型允许预览下载
  · 购买后下载 code 类型返回上传时的 zip 原包（字节一致）
  · prompt 类型自动打包为含 SKILL.md 的 zip
  · license_token 与 user_id 两条授权路径都可用
  · 下载计数累加
"""
from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
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


async def _fetchone(sql: str, params=()):
    conn = await aiosqlite.connect(db_mod.DB_PATH)
    try:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        return dict(rows[0]) if rows else None
    finally:
        await conn.close()


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


class _DownloadBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        Path(_TMP.name).unlink(missing_ok=True)

    def _user(self, suffix: str) -> dict:
        r = self.client.post("/api/v2/auth/register", json={
            "username": f"dl_{suffix}", "password": "secret12", "nickname": f"下载_{suffix}",
        })
        self.assertEqual(r.status_code, 200, r.text)
        uid = r.json()["user_id"]
        login = self.client.post("/api/v2/auth/login",
                                 json={"username": f"dl_{suffix}", "password": "secret12"})
        self.assertEqual(login.status_code, 200, login.text)
        return {"id": uid, "token": login.json()["token"]}

    def _product(self, name: str) -> int:
        r = self.client.post("/api/products", json={
            "name": name, "description": f"{name} 描述",
            "category": "Skill", "price": 10, "seller_name": "测试卖家",
        })
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def _upload(self, product_id: int, skill_type: str, data: bytes) -> None:
        r = self.client.post(
            "/api/skills/upload",
            data={"product_id": str(product_id), "skill_type": skill_type,
                  "seller_id": "seller-1"},
            files={"file": (f"{skill_type}.zip", data, "application/zip")},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "encrypted")

    def _buy(self, user: dict, product_id: int) -> None:
        r = self.client.post("/api/transactions/buy",
                             json={"product_id": product_id}, headers=_auth(user["token"]))
        self.assertEqual(r.status_code, 200, r.text)

    def _downloads(self, product_id: int) -> int:
        import asyncio
        row = asyncio.run(_fetchone("SELECT downloads FROM products WHERE id = ?", (product_id,)))
        return row["downloads"] if row else -1


class TestSkillZipDownload(_DownloadBase):
    def test_dl01_code_requires_purchase(self):
        """未购买时 code 类型不可下载。"""
        pid = self._product("dl01-code")
        self._upload(pid, "code", _zip_bytes({"SKILL.md": b"# code skill\n"}))
        r = self.client.get(f"/api/skills/{pid}/download")
        self.assertEqual(r.status_code, 403, r.text)

    def test_dl02_prompt_preview_allowed(self):
        """未购买时 prompt 类型允许预览下载，且为 zip。"""
        pid = self._product("dl02-prompt")
        self._upload(pid, "prompt", "---\nname: dl02\n---\n\n# 预览\n".encode("utf-8"))
        r = self.client.get(f"/api/skills/{pid}/download")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            self.assertIn("SKILL.md", z.namelist())
            self.assertIn("预览", z.read("SKILL.md").decode("utf-8"))

    def test_dl03_code_download_roundtrip(self):
        """购买后下载 code 类型，字节与上传的 zip 完全一致。"""
        user = self._user("rt")
        pid = self._product("dl03-code")
        original = _zip_bytes({"SKILL.md": "# 往返一致性\n".encode(), "extra/data.json": b'{"a":1}'})
        self._upload(pid, "code", original)
        self._buy(user, pid)

        r = self.client.get(f"/api/skills/{pid}/download",
                            params={"user_id": user["id"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.content, original)
        self.assertIn("attachment", r.headers.get("content-disposition", ""))

    def test_dl04_prompt_download_wraps_skill_md(self):
        """prompt 类型购买后下载为含 SKILL.md 的 zip。"""
        user = self._user("wrap")
        pid = self._product("dl04-prompt")
        self._upload(pid, "prompt", "---\nname: dl04\n---\n\n# 被打包的提示词\n".encode("utf-8"))
        self._buy(user, pid)

        r = self.client.get(f"/api/skills/{pid}/download",
                            params={"user_id": user["id"]})
        self.assertEqual(r.status_code, 200, r.text)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            self.assertIn("SKILL.md", z.namelist())
            self.assertIn("被打包的提示词", z.read("SKILL.md").decode("utf-8"))

    def test_dl05_license_token_grants_download(self):
        """license_token 路径同样可下载。"""
        user = self._user("lic")
        pid = self._product("dl05-license")
        original = _zip_bytes({"SKILL.md": b"# license token\n"})
        self._upload(pid, "code", original)

        created = self.client.post("/api/skills/license", json={
            "user_id": user["id"], "product_id": pid, "license_type": "permanent",
        })
        self.assertEqual(created.status_code, 200, created.text)
        token = created.json()["license_token"]

        r = self.client.get(f"/api/skills/{pid}/download", params={"license_token": token})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.content, original)

    def test_dl06_unknown_product_and_missing_asset(self):
        """不存在的商品 / 未上传技能返回 404。"""
        r = self.client.get("/api/skills/999999/download")
        self.assertEqual(r.status_code, 404, r.text)

        pid = self._product("dl06-empty")
        r = self.client.get(f"/api/skills/{pid}/download")
        self.assertEqual(r.status_code, 404, r.text)

    def test_dl07_download_counter_increments(self):
        """成功下载使商品 downloads 计数 +1。"""
        user = self._user("cnt")
        pid = self._product("dl07-count")
        self._upload(pid, "code", _zip_bytes({"SKILL.md": "# 计数\n".encode("utf-8")}))
        self._buy(user, pid)
        before = self._downloads(pid)

        r = self.client.get(f"/api/skills/{pid}/download", params={"user_id": user["id"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._downloads(pid), before + 1)


if __name__ == "__main__":
    unittest.main()
