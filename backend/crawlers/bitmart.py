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
        return self.parse_readme(resp.text)

    def parse_readme(self, readme: str) -> list[dict]:
        """Parse BitMart README markdown table into skill list items."""
        import re

        skills = []
        # Markdown table rows, name may be a link: | [name](#anchor) | desc | `ver` | status |
        # Parse line-by-line so separator rows cannot swallow the next skill via \s newlines.
        pattern = re.compile(
            r"^\|\s*(?:\[`?([\w.-]+)`?\]\([^)]+\)|`([\w.-]+)`|([\w.-]+))\s*"
            r"\|\s*([^|]+?)\s*"
            r"\|\s*`?([\d.]+(?:-\d+)?)`?\s*"
            r"\|\s*([^|]+)\|\s*$"
        )
        for line in readme.splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            name = match.group(1) or match.group(2) or match.group(3)
            if not name or re.fullmatch(r"-+", name) or name.lower() in ("skill", "name"):
                continue
            if not re.search(r"[A-Za-z]", name):
                continue
            skills.append({
                "name": name.strip(),
                "description": match.group(4).strip(),
                "version": match.group(5).strip(),
                "status": match.group(6).strip(),
            })

        if not skills:
            raise RuntimeError(
                "BitMart README table parse returned 0 skills; refusing hardcoded invent fallback"
            )
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
            sub_category = "合约交易"
        elif "wallet" in name_lower or "web3" in name_lower:
            display_name = "BitMart Web3 钱包"
            tags = ["钱包", "Web3", "链上", "智能资金"]
            price, original = 89, 129
            sub_category = "钱包"
        else:
            display_name = "BitMart 现货交易"
            tags = ["交易", "现货", "买卖", "订单"]
            price, original = 79, 109
            sub_category = "现货交易"

        return CrawlerResult(
            source="bitmart",
            name=name,
            display_name=display_name,
            description=item.get("description", display_name),
            category="Skill",
            sub_category=sub_category,
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
