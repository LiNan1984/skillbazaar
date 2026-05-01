from __future__ import annotations
"""
BitMart Skills 爬虫
数据源: https://github.com/bitmartexchange/bitmart-skills
"""
import httpx
from typing import Optional
from .base import BaseCrawler, CrawlerResult

GITHUB_RAW = "https://raw.githubusercontent.com/bitmartexchange/bitmart-skills/master"
README_URL = "https://raw.githubusercontent.com/bitmartexchange/bitmart-skills/master/README.md"


class BitMartSkillsCrawler(BaseCrawler):
    source_name = "bitmart"
    source_platform = "BitMart Skills"

    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={
            "User-Agent": "SkillBazaar-Crawler/1.0"
        })

    def fetch_list(self) -> list[dict]:
        resp = self.client.get(README_URL)
        resp.raise_for_status()
        readme = resp.text

        skills = []
        # Parse skill entries from README
        import re
        pattern = r'\|\s*`?([\w-]+)`?\s*\|\s*(.+?)\s*\|\s*`?([\d.]+)`?\s*\|\s*(\S+)\s*\|'
        for match in re.finditer(pattern, readme):
            name, desc, version, status = match.groups()
            if name.startswith("---") or name.lower() in ("skill", "name"):
                continue
            skills.append({
                "name": name.strip(),
                "description": desc.strip(),
                "version": version.strip(),
                "status": status.strip(),
            })

        # Fallback if README parsing fails
        if not skills:
            skills = [
                {"name": "bitmart-exchange-spot", "description": "Spot trading: buy/sell, order management, account queries", "version": "2026.3.13", "status": "Active"},
                {"name": "bitmart-exchange-futures", "description": "USDT perpetual futures: open/close position, TP/SL, plan orders", "version": "2026.3.13", "status": "Active"},
            ]
        return skills

    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        name = item["name"]
        skill_md_url = f"{GITHUB_RAW}/skills/{name}/SKILL.md"

        content_preview = ""
        try:
            resp = self.client.get(skill_md_url)
            if resp.status_code == 200:
                content_preview = resp.text[:1000]
        except Exception:
            pass

        name_lower = name.lower()
        if "futures" in name_lower:
            display_name = "BitMart 合约交易"
            tags = ["交易", "合约", "永续", "杠杆"]
            price, original = 99, 139
        else:
            display_name = "BitMart 现货交易"
            tags = ["交易", "现货", "买卖", "订单"]
            price, original = 79, 109

        return CrawlerResult(
            source="bitmart",
            name=name,
            display_name=display_name,
            description=item.get("description", display_name),
            category="Skill",
            sub_category="现货交易" if "spot" in name_lower else "合约交易",
            price=price,
            original_price=original,
            seller_name="BitMart",
            seller_avatar="https://api.dicebear.com/7.x/bottts/svg?seed=bitmart",
            tags=tags,
            source_platform=self.source_platform,
            github_url="https://github.com/bitmartexchange/bitmart-skills",
            content_preview=content_preview,
            source_url=f"https://github.com/bitmartexchange/bitmart-skills/tree/master/skills/{name}",
            version=item.get("version", ""),
        )
