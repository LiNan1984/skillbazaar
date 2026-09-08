"""
Fixture-backed tests for crawl normalize → persist path.

HTTP responses are fixture files; SyncService.persist_results / results_from_seed_dicts
and crawler parsers are the real shipped units (not mocked).
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawlers.agensi import AgensiCrawler
from crawlers.agentskillshub import AgentSkillsHubCrawler
from crawlers.base import CrawlerResult
from crawlers.bitmart import BitMartSkillsCrawler
from crawlers.gate import GateSkillsCrawler
from crawlers.sync_service import SyncService, results_from_seed_dicts

FIXTURES = Path(__file__).parent / "fixtures"
PRODUCTS_DDL = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    sub_category TEXT,
    price INTEGER NOT NULL,
    original_price INTEGER,
    seller_name TEXT NOT NULL,
    seller_avatar TEXT,
    rating REAL DEFAULT 4.0,
    downloads INTEGER DEFAULT 0,
    sales INTEGER DEFAULT 0,
    tags TEXT DEFAULT '[]',
    source_platform TEXT,
    github_url TEXT,
    icon TEXT,
    content_preview TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT,
    pricing_model TEXT DEFAULT 'fixed',
    base_price INTEGER,
    demand_score REAL DEFAULT 0
)
"""


def _make_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute(PRODUCTS_DDL)
    conn.commit()
    conn.close()
    return tmp.name


def _fetch_product(db_path: str, name: str, platform: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM products WHERE name = ? AND source_platform = ?",
        (name, platform),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


class TestNormalizeFromFixtures(unittest.TestCase):
    def test_gate_readme_fixture_parses_skills(self):
        text = (FIXTURES / "gate_readme_snippet.md").read_text(encoding="utf-8")
        items = GateSkillsCrawler().parse_readme(text)
        self.assertGreaterEqual(len(items), 3)
        names = {i["name"] for i in items}
        self.assertIn("gate-exchange-tradfi", names)
        detail = GateSkillsCrawler().fetch_detail(items[0])
        self.assertIsInstance(detail, CrawlerResult)
        self.assertTrue(detail.name)
        self.assertTrue(detail.description)
        self.assertEqual(detail.source_platform, "Gate Skills Hub")

    def test_bitmart_readme_fixture_parses_skills(self):
        text = (FIXTURES / "bitmart_readme_snippet.md").read_text(encoding="utf-8")
        items = BitMartSkillsCrawler().parse_readme(text)
        self.assertEqual(len(items), 3)
        self.assertEqual(
            {i["name"] for i in items},
            {"bitmart-exchange-spot", "bitmart-exchange-futures", "bitmart-wallet-ai"},
        )

    def test_agentskillshub_rsc_fixture_parses_skills(self):
        html = (FIXTURES / "agentskillshub_openclaw_snippet.html").read_text(encoding="utf-8")
        items = AgentSkillsHubCrawler()._parse_rsc_skills(html)
        self.assertEqual(len(items), 2)
        by_name = {i["name"]: i for i in items}
        self.assertIn("fixture-new-skill", by_name)
        self.assertIn("UPDATED description", by_name["self-improvement"]["description"])

    def test_agensi_html_fixture_parses_skills(self):
        html = (FIXTURES / "agensi_skills_snippet.html").read_text(encoding="utf-8")
        items = AgensiCrawler().parse_skills_html(html)
        names = {i["name"] for i in items}
        self.assertIn("code-reviewer", names)
        self.assertIn("fixture-agensi-skill", names)
        self.assertNotIn("free", names)
        # List must not invent Free when the listing has no price text
        by_name = {i["name"]: i for i in items}
        self.assertEqual(by_name["fixture-agensi-skill"].get("price_str", ""), "")

    def test_agensi_browse_free_skills_does_not_invent_slugs(self):
        """UI copy like 'Browse Free Skills' / 'Agensi Free …' must not become catalog rows."""
        html = (FIXTURES / "agensi_skills_snippet.html").read_text(encoding="utf-8")
        self.assertIn("Browse Free Skills", html)
        self.assertIn("Agensi Free Skill Explorer", html)
        items = AgensiCrawler().parse_skills_html(html)
        names = {i["name"] for i in items}
        self.assertNotIn("rowse", names)
        self.assertNotIn("gensi", names)
        self.assertNotIn("browse", names)
        # Only real /skills/<slug> hrefs
        self.assertTrue(names <= {"code-reviewer", "fixture-agensi-skill", "1-klick-magnet-website"})

    def test_agensi_fetch_detail_skips_http_404(self):
        crawler = AgensiCrawler()

        class FakeResp:
            def __init__(self, status_code: int, text: str = ""):
                self.status_code = status_code
                self.text = text

        class FakeClient:
            def get(self, url, follow_redirects=True):
                if url.rstrip("/").endswith("/rowse"):
                    return FakeResp(404, "not found")
                return FakeResp(
                    200,
                    (FIXTURES / "agensi_detail_paid.jsonld.html").read_text(encoding="utf-8"),
                )

        crawler.client = FakeClient()
        self.assertIsNone(
            crawler.fetch_detail({"name": "rowse", "price_str": "Free", "description": "S"})
        )
        ok = crawler.fetch_detail(
            {"name": "1-klick-magnet-website", "price_str": "", "description": ""}
        )
        self.assertIsNotNone(ok)
        self.assertEqual(ok.price, 95)

    def test_agensi_detail_jsonld_extracts_paid_usd_price(self):
        html = (FIXTURES / "agensi_detail_paid.jsonld.html").read_text(encoding="utf-8")
        crawler = AgensiCrawler()
        usd = crawler.extract_offers_price_usd(html)
        self.assertEqual(usd, 19.0)

        # Empty list price_str must not force Free when detail offers.price > 0
        item = {"name": "1-klick-magnet-website", "price_str": "", "description": ""}
        result = crawler.build_result_from_detail(item, detail_html=html)
        self.assertEqual(result.price, 95)  # $19 * 5 coins
        self.assertGreater(result.price, 0)
        self.assertIn("$19", result.content_preview)

        live_html = (FIXTURES / "agensi_detail_design_philosophy.html").read_text(encoding="utf-8")
        live_usd = crawler.extract_offers_price_usd(live_html)
        self.assertIsNotNone(live_usd)
        self.assertGreater(live_usd, 0)
        live_item = {"name": "design-philosophy", "price_str": "Free", "description": ""}
        live_result = crawler.build_result_from_detail(live_item, detail_html=live_html)
        # Detail JSON-LD must override incorrect Free list default
        self.assertGreater(live_result.price, 0)
        self.assertEqual(live_result.price, crawler._usd_to_coins(live_usd))


class TestPersistInsertAndUpdate(unittest.TestCase):
    def test_results_from_seed_dicts_preserves_free_price(self):
        results = results_from_seed_dicts(
            [{"name": "free-skill", "description": "free", "price": 0, "original_price": 0}],
            source="agensi",
        )
        self.assertEqual(results[0].price, 0)
        self.assertEqual(results[0].original_price, 0)

    def test_agensi_paid_detail_persist_stores_nonzero_coins(self):
        """Detail HTML with offers.price>0 → normalize → persist non-zero coins."""
        db_path = _make_db()
        service = SyncService(db_path=db_path)
        crawler = AgensiCrawler()
        html = (FIXTURES / "agensi_detail_paid.jsonld.html").read_text(encoding="utf-8")

        # Seed an existing free row so we also exercise UPDATE of price
        seed = results_from_seed_dicts(
            [{
                "name": "1-klick-magnet-website",
                "description": "OLD free placeholder",
                "price": 0,
                "original_price": 0,
                "tags": ["旧"],
                "source_platform": "Agensi",
                "content_preview": "old",
            }],
            source="agensi",
        )
        a0, u0 = asyncio.run(service.persist_results(seed))
        self.assertEqual((a0, u0), (1, 0))
        before = _fetch_product(db_path, "1-klick-magnet-website", "Agensi")
        self.assertEqual(before["price"], 0)

        item = {"name": "1-klick-magnet-website", "price_str": "Free", "description": ""}
        result = crawler.build_result_from_detail(item, detail_html=html)
        self.assertGreater(result.price, 0)
        self.assertEqual(result.price, 95)

        added, updated = asyncio.run(service.persist_results([result]))
        self.assertEqual(added, 0)
        self.assertEqual(updated, 1)

        row = _fetch_product(db_path, "1-klick-magnet-website", "Agensi")
        self.assertIsNotNone(row)
        self.assertEqual(row["price"], 95)
        self.assertGreater(row["price"], 0)
        self.assertIn("Paid Agensi skill", row["description"])
        self.assertIn("$19", row["content_preview"])

    def test_insert_new_project_then_update_description_and_tags(self):
        db_path = _make_db()
        service = SyncService(db_path=db_path)

        # --- INSERT path: brand-new project from fixture-shaped payload ---
        new_items = [
            {
                "name": "fixture-new-skill",
                "display_name": "Fixture New Skill",
                "description": "Brand new fixture skill for insert path.",
                "category": "Skill",
                "sub_category": "Testing",
                "price": 99,
                "original_price": 129,
                "seller_name": "tester",
                "tags": ["测试", "Fixture"],
                "source_platform": "AgentSkillsHub",
                "github_url": "https://github.com/example/fixture-new-skill",
                "content_preview": "# fixture-new-skill\n\nBrand new",
            }
        ]
        results = results_from_seed_dicts(new_items, source="agentskillshub")
        added, updated = asyncio.run(service.persist_results(results))
        self.assertEqual(added, 1)
        self.assertEqual(updated, 0)

        row = _fetch_product(db_path, "fixture-new-skill", "AgentSkillsHub")
        self.assertIsNotNone(row)
        self.assertEqual(row["description"], "Brand new fixture skill for insert path.")
        self.assertEqual(json.loads(row["tags"]), ["测试", "Fixture"])
        self.assertEqual(row["status"], "active")

        # --- UPDATE path: same name+platform, newer description/tags ---
        updated_items = [
            {
                "name": "fixture-new-skill",
                "display_name": "Fixture New Skill",
                "description": "UPDATED description for fixture-new-skill after refresh.",
                "category": "Skill",
                "sub_category": "Testing",
                "price": 149,
                "original_price": 199,
                "seller_name": "tester",
                "tags": ["测试", "Fixture", "更新"],
                "source_platform": "AgentSkillsHub",
                "github_url": "https://github.com/example/fixture-new-skill",
                "content_preview": "# fixture-new-skill\n\nUPDATED",
            }
        ]
        results2 = results_from_seed_dicts(updated_items, source="agentskillshub")
        added2, updated2 = asyncio.run(service.persist_results(results2))
        self.assertEqual(added2, 0)
        self.assertEqual(updated2, 1)

        row2 = _fetch_product(db_path, "fixture-new-skill", "AgentSkillsHub")
        self.assertIsNotNone(row2)
        self.assertEqual(
            row2["description"],
            "UPDATED description for fixture-new-skill after refresh.",
        )
        self.assertEqual(json.loads(row2["tags"]), ["测试", "Fixture", "更新"])
        self.assertEqual(row2["price"], 149)
        self.assertIn("UPDATED", row2["content_preview"])

    def test_fixture_normalize_then_persist_insert_and_update(self):
        """End-to-end: fixture HTML → crawler normalize → persist insert + update."""
        db_path = _make_db()
        service = SyncService(db_path=db_path)

        html = (FIXTURES / "agentskillshub_openclaw_snippet.html").read_text(encoding="utf-8")
        crawler = AgentSkillsHubCrawler()
        items = crawler._parse_rsc_skills(html)
        self.assertEqual(len(items), 2)

        # Seed an existing self-improvement row so the second persist hits UPDATE
        seed_existing = results_from_seed_dicts(
            [
                {
                    "name": "self-improvement",
                    "description": "OLD description before crawl refresh",
                    "tags": ["旧标签"],
                    "price": 10,
                    "source_platform": "AgentSkillsHub",
                    "content_preview": "old",
                }
            ],
            source="agentskillshub",
        )
        a0, u0 = asyncio.run(service.persist_results(seed_existing))
        self.assertEqual((a0, u0), (1, 0))

        results = [crawler.fetch_detail(item) for item in items]
        results = [r for r in results if r is not None]
        self.assertEqual(len(results), 2)

        added, updated = asyncio.run(service.persist_results(results))
        # fixture-new-skill inserted; self-improvement updated
        self.assertEqual(added, 1)
        self.assertEqual(updated, 1)

        inserted = _fetch_product(db_path, "fixture-new-skill", "AgentSkillsHub")
        self.assertIsNotNone(inserted)
        self.assertIn("Brand new fixture skill", inserted["description"])
        self.assertTrue(inserted["description"].strip())

        updated_row = _fetch_product(db_path, "self-improvement", "AgentSkillsHub")
        self.assertIsNotNone(updated_row)
        self.assertIn("UPDATED description", updated_row["description"])
        self.assertNotEqual(updated_row["description"], "OLD description before crawl refresh")
        tags = json.loads(updated_row["tags"])
        self.assertIsInstance(tags, list)
        self.assertGreater(len(tags), 0)


if __name__ == "__main__":
    unittest.main()
