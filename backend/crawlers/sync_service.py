"""
数据同步服务
将爬取的数据同步到 SQLite 数据库
支持增量更新、去重、自动定价
"""
from __future__ import annotations
import json
import time
import asyncio
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BaseCrawler, CrawlerResult
from .gate import GateSkillsCrawler
from .bitmart import BitMartSkillsCrawler
from .agentskillshub import AgentSkillsHubCrawler
from .agensi import AgensiCrawler

DB_PATH = Path(__file__).parent.parent / "skillbazaar.db"
SEED_DIR = Path(__file__).parent.parent / "seeds"

CRAWLERS: dict[str, type[BaseCrawler]] = {
    "gate": GateSkillsCrawler,
    "bitmart": BitMartSkillsCrawler,
    "agentskillshub": AgentSkillsHubCrawler,
    "agensi": AgensiCrawler,
}


class SyncService:
    def __init__(self, db_path: str = ""):
        self.db_path = db_path or str(DB_PATH)
        self.seed_dir = SEED_DIR
        self.seed_dir.mkdir(exist_ok=True)

    async def sync_all(self, sources: list[str] | None = None):
        """同步所有或指定数据源"""
        if sources is None:
            sources = list(CRAWLERS.keys())

        total_added = 0
        total_updated = 0

        for source in sources:
            if source not in CRAWLERS:
                print(f"[Sync] Unknown source: {source}")
                continue

            print(f"\n[Sync] === Crawling {source} ===")
            crawler = CRAWLERS[source]()

            try:
                results = await asyncio.to_thread(crawler.crawl)
                print(f"[Sync] {source}: crawled {len(results)} items")

                # Save seeds
                await asyncio.to_thread(crawler.incremental_save, results)

                # Sync to DB
                added, updated = await self._sync_to_db(results)
                total_added += added
                total_updated += updated

            except Exception as e:
                print(f"[Sync] {source} error: {e}")

        print(f"\n[Sync] Done! Added: {total_added}, Updated: {total_updated}")
        return total_added, total_updated

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

    async def load_seeds_to_db(self):
        """从种子 JSON 文件加载到数据库（首次初始化或全量重建）"""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        count = 0

        try:
            for seed_file in sorted(self.seed_dir.glob("seed_*.json")):
                # Also check the parent directory for seed files
                pass

            # Check both seed directories
            parent_seeds = Path(__file__).parent.parent
            for seed_file in sorted(parent_seeds.glob("seed_*.json")):
                data = json.loads(seed_file.read_text(encoding="utf-8"))
                for item in data:
                    import random
                    name = item.get("name", "")
                    source_platform = item.get("source_platform", "")

                    # Check if exists
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
