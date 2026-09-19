"""SKILL.md export + MCP discovery against shipped services (no mocks of units under test)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.manifest_service import product_to_manifest, product_to_skill_md


SAMPLE = {
    "id": 42,
    "name": "Code Reviewer",
    "description": "Reviews pull requests and flags defects.",
    "category": "Skill",
    "sub_category": "文本处理",
    "price": 128,
    "tags": '["review","python"]',
    "source_platform": "Agensi",
    "github_url": "https://github.com/example/code-reviewer",
    "seller_name": "steipete",
    "status": "active",
}


class TestManifestExport(unittest.TestCase):
    def test_skill_md_has_frontmatter_and_name(self):
        md = product_to_skill_md(SAMPLE)
        self.assertTrue(md.startswith("---\n"), md[:80])
        self.assertIn("\n---\n", md)
        self.assertIn("name: code-reviewer", md)
        self.assertIn("description:", md)
        self.assertIn("Reviews pull requests", md)
        self.assertIn("skillbazaar_id: 42", md)
        self.assertIn("category: Skill", md)
        self.assertIn("price_coins: 128", md)

    def test_manifest_exposes_execution_locus(self):
        skill = product_to_manifest(SAMPLE)
        self.assertEqual(skill["execution_locus"], "sdk")
        cron = product_to_manifest({**SAMPLE, "category": "Cron"})
        self.assertEqual(cron["execution_locus"], "cron")
        agent = product_to_manifest({**SAMPLE, "category": "Agent"})
        self.assertEqual(agent["execution_locus"], "platform")


class TestMcpDiscoveryHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        import database as db_mod

        cls._old = db_mod.DB_PATH
        db_mod.DB_PATH = cls._tmp.name
        from fastapi.testclient import TestClient
        from main import app

        cls._cm = TestClient(app)
        cls.client = cls._cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._cm.__exit__(None, None, None)
        import database as db_mod

        db_mod.DB_PATH = cls._old
        Path(cls._tmp.name).unlink(missing_ok=True)

    def test_discovery_search_and_skill_md(self):
        listed = self.client.get("/api/discovery/search", params={"query": "", "page_size": 5})
        self.assertEqual(listed.status_code, 200, listed.text)
        body = listed.json()
        self.assertIn("products", body)
        self.assertGreaterEqual(body.get("total", 0), 1)
        pid = body["products"][0]["id"]
        self.assertIn("skill_md", body["products"][0])
        self.assertTrue(body["products"][0]["skill_md"].startswith("---\n"))

        detail = self.client.get(f"/api/discovery/products/{pid}")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["id"], pid)
        self.assertIn("skill_md", detail.json())
        self.assertIn("manifest", detail.json())

        md = self.client.get(f"/api/discovery/products/{pid}/skill.md")
        self.assertEqual(md.status_code, 200, md.text)
        self.assertIn("text/markdown", md.headers.get("content-type", ""))
        self.assertTrue(md.text.startswith("---\n"))

    def test_mcp_jsonrpc_search_catalog(self):
        init = self.client.post(
            "/api/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "unittest", "version": "0"},
                },
            },
        )
        self.assertEqual(init.status_code, 200, init.text)
        self.assertEqual(init.json()["result"]["serverInfo"]["name"], "skillbazaar")

        tools = self.client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(tools.status_code, 200, tools.text)
        names = {t["name"] for t in tools.json()["result"]["tools"]}
        for needed in ("search_catalog", "get_product", "list_bounties", "list_cron_products"):
            self.assertIn(needed, names)

        call = self.client.post(
            "/api/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "search_catalog", "arguments": {"query": "", "page_size": 3}},
            },
        )
        self.assertEqual(call.status_code, 200, call.text)
        text = call.json()["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertIn("products", payload)

    def test_list_bounties_and_cron_discovery(self):
        bounties = self.client.get("/api/discovery/bounties")
        self.assertEqual(bounties.status_code, 200, bounties.text)
        self.assertIn("bounties", bounties.json())
        cron = self.client.get("/api/discovery/cron")
        self.assertEqual(cron.status_code, 200, cron.text)
        self.assertIn("products", cron.json())


if __name__ == "__main__":
    unittest.main()
