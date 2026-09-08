"""
数据同步服务
将爬取的数据同步到 SQLite 数据库
支持增量更新、去重、自动定价
"""
from __future__ import annotations
import json
import asyncio
import aiosqlite
from datetime import datetime
from pathlib import Path

from .base import BaseCrawler, CrawlerResult
from .gate import GateSkillsCrawler
from .bitmart import BitMartSkillsCrawler
from .agentskillshub import AgentSkillsHubCrawler
from .agensi import AgensiCrawler

# Must match database.DB_PATH — API reads backend/data/skillbazaar.db
BACKEND_DIR = Path(__file__).parent.parent
DB_PATH = BACKEND_DIR / "data" / "skillbazaar.db"
SEED_DIR = BACKEND_DIR / "seeds"

CRAWLERS: dict[str, type[BaseCrawler]] = {
    "gate": GateSkillsCrawler,
    "bitmart": BitMartSkillsCrawler,
    "agentskillshub": AgentSkillsHubCrawler,
    "agensi": AgensiCrawler,
}


def results_from_seed_dicts(items: list[dict], source: str) -> list[CrawlerResult]:
    """Normalize seed/fixture dicts into CrawlerResult for persist path testing."""
    platform = {
        "gate": "Gate Skills Hub",
        "bitmart": "BitMart Skills",
        "agentskillshub": "AgentSkillsHub",
        "agensi": "Agensi",
    }.get(source, source)
    results: list[CrawlerResult] = []
    for item in items:
        tags = item.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except json.JSONDecodeError:
                tags = [tags]
        results.append(
            CrawlerResult(
                source=source,
                name=item["name"],
                display_name=item.get("display_name", item["name"]),
                description=item.get("description", item.get("display_name", item["name"])),
                category=item.get("category", "Skill"),
                sub_category=item.get("sub_category", ""),
                price=int(item["price"]) if item.get("price") is not None else 99,
                original_price=(
                    int(item["original_price"])
                    if item.get("original_price") is not None
                    else (int(item["price"]) if item.get("price") is not None else 99)
                ),
                seller_name=item.get("seller_name", "社区"),
                seller_avatar=item.get("seller_avatar", ""),
                tags=list(tags) if isinstance(tags, list) else [],
                source_platform=item.get("source_platform", platform),
                github_url=item.get("github_url", ""),
                content_preview=item.get("content_preview", ""),
                source_url=item.get("source_url", ""),
                version=item.get("version", ""),
            )
        )
    return results


class SyncService:
    def __init__(self, db_path: str = ""):
        self.db_path = db_path or str(DB_PATH)
        self.seed_dir = SEED_DIR
        self.seed_dir.mkdir(exist_ok=True)
        self.last_source_status: dict[str, dict] = {}

    async def sync_all(self, sources: list[str] | None = None):
        """同步所有或指定数据源"""
        if sources is None:
            sources = list(CRAWLERS.keys())

        total_added = 0
        total_updated = 0
        self.last_source_status = {}

        for source in sources:
            if source not in CRAWLERS:
                print(f"[Sync] Unknown source: {source}")
                self.last_source_status[source] = {"ok": False, "error": "unknown source"}
                continue

            print(f"\n[Sync] === Crawling {source} ===")
            crawler = CRAWLERS[source]()

            try:
                results = await asyncio.to_thread(crawler.crawl)
                print(f"[Sync] {source}: crawled {len(results)} items")

                if not results:
                    # Honest failure: do not treat empty crawl as success
                    msg = f"{source} crawl returned 0 items — keeping prior seeds, no DB wipe"
                    print(f"[Sync] ERROR: {msg}")
                    self.last_source_status[source] = {
                        "ok": False,
                        "error": msg,
                        "fallback": "kept_prior_seeds",
                        "crawled": 0,
                    }
                    continue

                # Save seeds to seeds/ and committed backend/seed_*.json
                await asyncio.to_thread(crawler.incremental_save, results)
                await asyncio.to_thread(self._write_committed_seed, source, results)

                # Sync to DB
                added, updated = await self.persist_results(results)
                total_added += added
                total_updated += updated
                self.last_source_status[source] = {
                    "ok": True,
                    "crawled": len(results),
                    "added": added,
                    "updated": updated,
                }

            except Exception as e:
                print(f"[Sync] {source} error: {e}")
                # Fallback: reload existing seed file into DB for missing rows only
                fallback_count = await self.load_seeds_to_db(sources=[source])
                self.last_source_status[source] = {
                    "ok": False,
                    "error": str(e),
                    "fallback": "reload_existing_seeds",
                    "fallback_inserted": fallback_count,
                }

        print(f"\n[Sync] Done! Added: {total_added}, Updated: {total_updated}")
        print(f"[Sync] Source status: {json.dumps(self.last_source_status, ensure_ascii=False)}")
        return total_added, total_updated

    def _write_committed_seed(self, source: str, results: list[CrawlerResult]):
        """Mirror crawl output to backend/seed_{source}.json (committed catalog)."""
        filepath = BACKEND_DIR / f"seed_{source}.json"
        data = [r.to_seed_dict() for r in results]
        # Merge with existing committed seed so we don't drop fields on partial crawls
        existing_map: dict[str, dict] = {}
        if filepath.exists():
            try:
                for item in json.loads(filepath.read_text(encoding="utf-8")):
                    if isinstance(item, dict) and item.get("name"):
                        existing_map[item["name"]] = item
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Sync] Warning: could not read {filepath}: {e}")

        for d in data:
            prev = existing_map.get(d["name"], {})
            merged = {**prev, **d}
            # Prefer non-empty new fields
            for key in ("description", "content_preview", "github_url", "tags"):
                if not merged.get(key) and prev.get(key):
                    merged[key] = prev[key]
            existing_map[d["name"]] = merged

        merged_list = sorted(
            existing_map.values(),
            key=lambda x: x.get("crawled_at", ""),
            reverse=True,
        )
        filepath.write_text(json.dumps(merged_list, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Sync] Wrote committed seed {filepath} ({len(merged_list)} items)")

    async def persist_results(self, results: list[CrawlerResult]) -> tuple[int, int]:
        """Public persist entry used by sync and tests (insert + update)."""
        return await self._sync_to_db(results)

    async def _sync_to_db(self, results: list[CrawlerResult]) -> tuple[int, int]:
        """将爬取结果同步到数据库"""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        added = 0
        updated = 0

        try:
            for r in results:
                # Check if product exists by name + source_platform
                cursor = await db.execute(
                    "SELECT id FROM products WHERE name = ? AND source_platform = ?",
                    (r.name, r.source_platform),
                )
                row = await cursor.fetchone()

                import random
                tags_json = json.dumps(r.tags, ensure_ascii=False)

                if row:
                    # Update existing
                    await db.execute(
                        """UPDATE products SET
                            description=?, price=?, original_price=?, tags=?,
                            content_preview=?, github_url=?, status='active',
                            sub_category=?, seller_name=?
                        WHERE id=?""",
                        (r.description, r.price, r.original_price, tags_json,
                         r.content_preview, r.github_url, r.sub_category, r.seller_name, row[0]),
                    )
                    updated += 1
                else:
                    # Insert new
                    await db.execute(
                        """INSERT INTO products (
                            name, description, category, sub_category, price, original_price,
                            seller_name, seller_avatar, rating, downloads, sales, tags,
                            source_platform, github_url, icon, content_preview, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            r.name, r.description, r.category, r.sub_category,
                            r.price, r.original_price, r.seller_name, r.seller_avatar,
                            round(random.uniform(4.0, 5.0), 1),
                            random.randint(500, 50000),
                            random.randint(50, 5000),
                            tags_json, r.source_platform, r.github_url, None,
                            r.content_preview, "active",
                            datetime.now().strftime("%Y-%m-%d"),
                        ),
                    )
                    added += 1

            await db.commit()
        finally:
            await db.close()

        return added, updated

    async def load_seeds_to_db(self, sources: list[str] | None = None):
        """从种子 JSON 文件加载到数据库（首次初始化或失败回退）"""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        count = 0
        source_files = None
        if sources:
            source_files = {f"seed_{s}.json" for s in sources}

        try:
            parent_seeds = BACKEND_DIR
            seed_paths = sorted(parent_seeds.glob("seed_*.json"))
            seed_paths += sorted(self.seed_dir.glob("seed_*.json"))

            seen_files: set[str] = set()
            for seed_file in seed_paths:
                if source_files and seed_file.name not in source_files:
                    continue
                # Prefer first occurrence (committed backend/ over seeds/)
                if seed_file.name in seen_files:
                    continue
                seen_files.add(seed_file.name)

                data = json.loads(seed_file.read_text(encoding="utf-8"))
                for item in data:
                    import random
                    name = item.get("name", "")
                    source_platform = item.get("source_platform", "")

                    cursor = await db.execute(
                        "SELECT id FROM products WHERE name = ? AND source_platform = ?",
                        (name, source_platform),
                    )
                    if await cursor.fetchone():
                        continue

                    tags = item.get("tags", [])
                    if isinstance(tags, list):
                        tags_json = json.dumps(tags, ensure_ascii=False)
                    else:
                        tags_json = str(tags)

                    await db.execute(
                        """INSERT INTO products (
                            name, description, category, sub_category, price, original_price,
                            seller_name, seller_avatar, rating, downloads, sales, tags,
                            source_platform, github_url, icon, content_preview, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            name,
                            item.get("description", item.get("display_name", "")),
                            item.get("category", "Skill"),
                            item.get("sub_category", ""),
                            item.get("price", 99),
                            item.get("original_price", item.get("price", 99)),
                            item.get("seller_name", "社区"),
                            item.get("seller_avatar", ""),
                            item.get("rating", round(random.uniform(4.0, 5.0), 1)),
                            item.get("downloads", random.randint(500, 50000)),
                            item.get("sales", random.randint(50, 5000)),
                            tags_json,
                            source_platform,
                            item.get("github_url", ""),
                            item.get("icon"),
                            item.get("content_preview", ""),
                            "active",
                            item.get("created_at", datetime.now().strftime("%Y-%m-%d")),
                        ),
                    )
                    count += 1

            await db.commit()
            print(f"[Sync] Loaded {count} new items from seed files")
        finally:
            await db.close()

        return count


async def run_sync(sources: list[str] | None = None):
    """运行同步（供外部调用）"""
    service = SyncService()
    return await service.sync_all(sources)


def run_sync_cli(sources: list[str] | None = None):
    """CLI 入口"""
    asyncio.run(run_sync(sources))


if __name__ == "__main__":
    import sys
    sources = sys.argv[1:] if len(sys.argv) > 1 else None
    run_sync_cli(sources)
