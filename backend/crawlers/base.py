from __future__ import annotations
"""
SkillBazaar Scrapy 爬虫 - 基础类
"""
import json
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

SEED_DIR = Path(__file__).parent.parent / "seeds"
SEED_DIR.mkdir(exist_ok=True)


@dataclass
class CrawlerResult:
    source: str
    name: str
    display_name: str
    description: str
    category: str = "Skill"
    sub_category: str = ""
    price: int = 99
    original_price: int = 129
    seller_name: str = ""
    seller_avatar: str = ""
    tags: list = field(default_factory=list)
    source_platform: str = ""
    github_url: str = ""
    content_preview: str = ""
    source_url: str = ""
    version: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        raw = f"{self.source}:{self.name}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_seed_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "sub_category": self.sub_category,
            "price": self.price,
            "original_price": self.original_price,
            "seller_name": self.seller_name,
            "seller_avatar": self.seller_avatar,
            "tags": self.tags,
            "source_platform": self.source_platform,
            "github_url": self.github_url,
            "content_preview": self.content_preview,
            "source_url": self.source_url,
            "version": self.version,
            "crawled_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


class BaseCrawler(ABC):
    source_name: str = ""
    source_platform: str = ""

    @abstractmethod
    def fetch_list(self) -> list[dict]:
        """获取商品列表（元数据）"""
        ...

    @abstractmethod
    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        """获取单个商品详情"""
        ...

    def crawl(self) -> list[CrawlerResult]:
        """执行完整爬取"""
        items = self.fetch_list()
        results = []
        for item in items:
            try:
                result = self.fetch_detail(item)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"[{self.source_name}] Error crawling {item.get('name', '?')}: {e}")
        return results

    def save_seeds(self, results: list[CrawlerResult], filename: str = ""):
        """保存种子数据为 JSON"""
        if not filename:
            filename = f"seed_{self.source_name}.json"
        filepath = SEED_DIR / filename
        data = [r.to_seed_dict() for r in results]
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{self.source_name}] Saved {len(data)} items to {filepath}")
        return filepath

    def load_existing_seeds(self, filename: str = "") -> list[dict]:
        """加载已有种子数据（用于增量对比）"""
        if not filename:
            filename = f"seed_{self.source_name}.json"
        filepath = SEED_DIR / filename
        if filepath.exists():
            return json.loads(filepath.read_text(encoding="utf-8"))
        return []

    def incremental_save(self, results: list[CrawlerResult], filename: str = ""):
        """增量保存：合并新旧数据，去重"""
        existing = self.load_existing_seeds(filename)
        existing_map = {item["name"]: item for item in existing}

        for r in results:
            d = r.to_seed_dict()
            existing_map[r.name] = d  # 覆盖更新

        if not filename:
            filename = f"seed_{self.source_name}.json"
        filepath = SEED_DIR / filename
        merged = sorted(existing_map.values(), key=lambda x: x.get("crawled_at", ""), reverse=True)
        filepath.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{self.source_name}] Incremental save: {len(merged)} items ({len(results)} updated)")
        return filepath
