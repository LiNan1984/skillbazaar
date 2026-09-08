from __future__ import annotations
"""
Agensi 爬虫
数据源: https://www.agensi.io/skills
策略: 抓取技能列表页 → 逐个获取详情（价格以详情页 JSON-LD offers 为准）
"""
import re
import json
import httpx
from typing import Optional
from .base import BaseCrawler, CrawlerResult

BASE_URL = "https://www.agensi.io"
SKILLS_URL = f"{BASE_URL}/skills"
# Convert USD → marketplace coins
USD_TO_COINS = 5


class AgensiCrawler(BaseCrawler):
    source_name = "agensi"
    source_platform = "Agensi"

    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={
            "User-Agent": "SkillBazaar-Crawler/1.0"
        })

    def fetch_list(self) -> list[dict]:
        resp = self.client.get(SKILLS_URL)
        resp.raise_for_status()
        return self.parse_skills_html(resp.text)

    def parse_skills_html(self, html: str) -> list[dict]:
        """Parse Agensi /skills listing HTML into skill list items."""
        skills = []
        seen = set()
        noise = {
            "new", "popular", "trending", "free", "resources", "all",
            "skills", "pricing", "about", "login", "signup", "search",
            "browse", "agensi", "home", "docs", "blog",
        }

        def _valid_slug(name: str) -> bool:
            if not name or name.lower() in noise or len(name) < 3:
                return False
            if name.endswith("-") or name.startswith("-"):
                return False
            # Prefer real skill slugs: lowercase letters/digits/hyphens
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                return False
            return True

        # ONLY accept real /skills/<slug> hrefs. Never invent slugs from Free/$X
        # UI copy (e.g. "Browse Free Skills" → "rowse", "Agensi Free …" → "gensi").
        for match in re.finditer(r'(?:href|src)=["\'](?:https?://(?:www\.)?agensi\.io)?/skills/([a-z0-9-]+)/?["\']', html, re.I):
            name = match.group(1)
            if name in seen or not _valid_slug(name):
                continue
            seen.add(name)
            skills.append({"name": name, "price_str": "", "description": ""})

        # Optional: attach Free/$X text ONLY onto href-discovered slugs (never create new names)
        by_name = {s["name"]: s for s in skills}
        for match in re.finditer(
            r'([a-z0-9]+(?:-[a-z0-9]+)*)\s+(Free|\$\d+(?:\.\d+)?)\s+(.+?)(?:\s+\d+\s+\d+\s+[\d.]+)?',
            html,
        ):
            name, price_str, desc = match.groups()
            if name not in by_name:
                continue
            by_name[name]["price_str"] = price_str
            if desc.strip():
                by_name[name]["description"] = desc.strip()[:200]

        if not skills:
            raise RuntimeError("Agensi skills page parse returned 0 skills; site shape likely changed")
        return skills

    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        name = item["name"]
        detail_url = f"{BASE_URL}/skills/{name}"
        desc = item.get("description", "")
        tags: list[str] = []
        seller = "Agensi Creator"
        detail_html = ""

        try:
            resp = self.client.get(detail_url, follow_redirects=True)
            if resp.status_code != 200:
                # Drop fabricated / dead slugs — do not persist 404s
                print(f"[agensi] skip {name}: detail HTTP {resp.status_code}")
                return None
            detail_html = resp.text
        except Exception as e:
            print(f"[agensi] skip {name}: detail fetch error {e}")
            return None

        # Require a real product signal (JSON-LD Product/Offer or meta description)
        if not self._is_valid_skill_detail(detail_html):
            print(f"[agensi] skip {name}: detail missing Product JSON-LD / description")
            return None

        return self.build_result_from_detail(
            item,
            detail_html=detail_html,
            detail_url=detail_url,
            desc=desc,
            tags=tags,
            seller=seller,
        )

    @staticmethod
    def _is_valid_skill_detail(html: str) -> bool:
        if not html or len(html) < 200:
            return False
        if AgensiCrawler.extract_offers_price_usd(html) is not None:
            return True
        if re.search(r'<script[^>]*type=["\']application/ld\+json["\']', html, re.I):
            # Any Product-like ld+json (free skills may omit offers.price)
            blocks = re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html,
                re.I | re.S,
            )
            for block in blocks:
                if re.search(r'"@type"\s*:\s*"Product"', block) or '"offers"' in block:
                    return True
        if re.search(r'<meta\s+name="description"\s+content="[^"]{10,}"', html, re.I):
            return True
        return False

    def build_result_from_detail(
        self,
        item: dict,
        detail_html: str,
        detail_url: str = "",
        desc: str = "",
        tags: list[str] | None = None,
        seller: str = "Agensi Creator",
    ) -> CrawlerResult:
        """Normalize list item + detail HTML into a CrawlerResult (shipped persist path)."""
        name = item["name"]
        tags = list(tags or [])
        list_price_str = item.get("price_str", "") or ""

        if detail_html:
            # Description from meta
            desc_match = re.search(
                r'<meta\s+name="description"\s+content="([^"]+)"',
                detail_html,
                re.I,
            )
            if desc_match:
                desc = desc_match.group(1)[:200]
            # Tags / seller heuristics
            tag_matches = re.findall(r'>(\w[\w-]+)</a>\s*</div>\s*<div', detail_html)
            tags = [t for t in tag_matches if len(t) > 2 and len(t) < 20][:5] or tags
            seller_match = re.search(r'by\s+([\w\s]+?)(?:\s*[\·<])', detail_html)
            if seller_match:
                seller = seller_match.group(1).strip() or seller

        usd_price, price_str = self._resolve_price(list_price_str, detail_html)
        coins = self._usd_to_coins(usd_price)
        original_price = int(coins * 1.3) if coins > 0 else 0

        display_name = self._to_display_name(name, desc)
        if not desc:
            desc = f"{display_name} - 来自 Agensi 市场的 AI 编码助手技能包"

        sub_cat = self._classify(name, desc)
        if not tags:
            tags = self._auto_tags(name, desc)

        if not detail_url:
            detail_url = f"{BASE_URL}/skills/{name}"

        return CrawlerResult(
            source="agensi",
            name=name,
            display_name=display_name,
            description=desc,
            category="Skill",
            sub_category=sub_cat,
            price=coins,
            original_price=original_price,
            seller_name=seller,
            seller_avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={seller}",
            tags=tags,
            source_platform=self.source_platform,
            github_url="",
            content_preview=f"# {name}\n\n{desc}\n\nPrice: {price_str}",
            source_url=detail_url,
            version="",
            extra={"usd_price": usd_price, "price_str": price_str},
        )

    def _resolve_price(self, list_price_str: str, detail_html: str) -> tuple[float, str]:
        """Prefer JSON-LD offers.price from detail HTML; fall back to list price_str."""
        ld_usd = self.extract_offers_price_usd(detail_html) if detail_html else None
        if ld_usd is not None:
            if ld_usd <= 0:
                return 0.0, "Free"
            return float(ld_usd), f"${ld_usd:g}" if ld_usd != int(ld_usd) else f"${int(ld_usd)}"

        return self._parse_price_str(list_price_str)

    @staticmethod
    def extract_offers_price_usd(html: str) -> Optional[float]:
        """Extract schema.org Offer price (USD) from application/ld+json blocks."""
        blocks = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.I | re.S,
        )
        for block in blocks:
            try:
                data = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            price = AgensiCrawler._find_offer_price(data)
            if price is not None:
                return price
        return None

    @staticmethod
    def _find_offer_price(node) -> Optional[float]:
        if isinstance(node, list):
            for item in node:
                found = AgensiCrawler._find_offer_price(item)
                if found is not None:
                    return found
            return None
        if not isinstance(node, dict):
            return None

        offers = node.get("offers")
        if isinstance(offers, dict) and "price" in offers:
            try:
                return float(offers["price"])
            except (TypeError, ValueError):
                pass
        if isinstance(offers, list):
            for offer in offers:
                if isinstance(offer, dict) and "price" in offer:
                    try:
                        return float(offer["price"])
                    except (TypeError, ValueError):
                        continue

        if "@graph" in node:
            return AgensiCrawler._find_offer_price(node["@graph"])
        return None

    @staticmethod
    def _parse_price_str(price_str: str) -> tuple[float, str]:
        text = (price_str or "").strip()
        if not text:
            # Unknown until detail — treat as free only when explicitly Free/0
            return 0.0, "Free"
        if text.lower() == "free" or text == "0":
            return 0.0, "Free"
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return 0.0, text or "Free"
        usd = float(match.group(1))
        return usd, text if text.startswith("$") else f"${usd:g}"

    @staticmethod
    def _usd_to_coins(usd: float) -> int:
        if usd <= 0:
            return 0
        return max(1, int(round(usd * USD_TO_COINS)))

    @staticmethod
    def _to_display_name(name: str, desc: str) -> str:
        mapping = {
            "code-reviewer": "代码审查专家", "security-audit": "安全审计",
            "api-designer": "API 设计师", "dockerfile-gen": "Dockerfile 生成器",
            "readme-generator": "README 生成器", "git-commit-writer": "Git 提交信息生成",
            "env-doctor": "环境诊断医生", "pr-description-writer": "PR 描述生成",
            "changelog-generator": "更新日志生成", "prompt-engineer": "提示词工程师",
            "db-schema": "数据库设计器", "content-writer": "内容生成器",
            "skill-creator": "技能创建器", "dependency-auditor": "依赖审计",
            "test-gen": "测试生成器", "seo-optimizer": "SEO 优化器",
            "regex-builder": "正则表达式构建", "cron-builder": "Cron 表达式构建",
            "json-to-types": "JSON 类型转换", "nginx-config": "Nginx 配置生成",
            "github-actions-gen": "GitHub Actions 生成", "docker-compose": "Docker Compose 生成",
            "landing-copy": "落地页文案", "email-template": "邮件模板生成",
            "color-palette": "配色方案生成", "api-mock": "API Mock 生成",
        }
        if name in mapping:
            return mapping[name]
        return name.replace("-", " ").title()

    @staticmethod
    def _classify(name: str, desc: str) -> str:
        text = (name + " " + desc).lower()
        if any(k in text for k in ["review", "audit", "security"]):
            return "代码审查"
        if any(k in text for k in ["test", "qa", "coverage"]):
            return "测试"
        if any(k in text for k in ["deploy", "docker", "nginx", "ci/cd", "github-action"]):
            return "DevOps"
        if any(k in text for k in ["api", "rest", "graphql"]):
            return "API开发"
        if any(k in text for k in ["doc", "readme", "changelog"]):
            return "文档"
        if any(k in text for k in ["frontend", "css", "ui", "color"]):
            return "前端"
        if any(k in text for k in ["database", "sql", "schema"]):
            return "数据工程"
        if any(k in text for k in ["git", "commit", "pr"]):
            return "Git工具"
        if any(k in text for k in ["seo", "marketing", "content", "email"]):
            return "营销"
        if any(k in text for k in ["prompt", "llm", "ai"]):
            return "AI与LLM"
        return "开发工具"

    @staticmethod
    def _auto_tags(name: str, desc: str) -> list[str]:
        text = (name + " " + desc).lower()
        tags = []
        tag_map = {"代码审查": "review", "安全": "security", "测试": "test", "API": "api",
                    "DevOps": "docker|deploy|nginx", "文档": "readme|doc|changelog",
                    "AI": "prompt|llm|agent", "自动化": "automat|gen|builder"}
        for tag, kws in tag_map.items():
            if any(kw in text for kw in kws.split("|")):
                tags.append(tag)
        return tags[:4] if tags else ["开发工具"]
