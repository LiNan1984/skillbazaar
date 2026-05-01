from __future__ import annotations
"""
Agensi 爬虫
数据源: https://www.agensi.io/skills
策略: 抓取技能列表页 → 逐个获取详情
"""
import re
import json
import httpx
from typing import Optional
from .base import BaseCrawler, CrawlerResult

BASE_URL = "https://www.agensi.io"
SKILLS_URL = f"{BASE_URL}/skills"


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
        html = resp.text

        skills = []
        seen = set()

        # Parse skill cards from HTML
        # Pattern: name, price (Free/$X), popularity, rating, description
        # Try multiple patterns
        patterns = [
            r'([\w-]+)\s+(Free|\$\d+)\s+(.+?)(?:\s+\d+\s+\d+\s+[\d.]+)?',
            r'"([\w-]+)"[^}]*?"price":\s*"(Free|\$\d+)"',
            r'/skills/([\w-]+)',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, html):
                name = match.group(1)
                if name in seen or len(name) < 3:
                    continue
                seen.add(name)
                price_str = match.group(2) if len(match.groups()) > 1 else "Free"
                desc = match.group(3).strip()[:200] if len(match.groups()) > 2 else ""
                skills.append({
                    "name": name,
                    "price_str": price_str,
                    "description": desc,
                })

        # Fallback: parse known skills from page content
        if len(skills) < 10:
            # Extract from the skills listing page content
            for match in re.finditer(r'(/skills/)([\w-]+)', html):
                name = match.group(2)
                if name not in seen and name not in ("new", "popular", "trending"):
                    seen.add(name)
                    skills.append({"name": name, "price_str": "Free", "description": ""})

        return skills

    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        name = item["name"]
        price_str = item.get("price_str", "Free")

        # Parse price
        if "Free" in price_str or price_str == "0":
            price = 0
        else:
            try:
                price = int(re.search(r'\d+', price_str).group())
                # Convert USD to coins (1 USD ≈ 5 coins)
                price = price * 5
            except (AttributeError, ValueError):
                price = 0

        original_price = int(price * 1.3) if price > 0 else 0

        # Try to fetch detail page
        detail_url = f"{BASE_URL}/skills/{name}"
        desc = item.get("description", "")
        tags = []
        seller = "Agensi Creator"

        try:
            resp = self.client.get(detail_url, follow_redirects=True)
            if resp.status_code == 200:
                detail_html = resp.text
                # Extract description
                desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', detail_html)
                if desc_match:
                    desc = desc_match.group(1)[:200]
                # Extract tags
                tag_matches = re.findall(r'>(\w[\w-]+)</a>\s*</div>\s*<div', detail_html)
                tags = [t for t in tag_matches if len(t) > 2 and len(t) < 20][:5]
                # Extract seller
                seller_match = re.search(r'by\s+([\w\s]+?)(?:\s*[\·<])', detail_html)
                if seller_match:
                    seller = seller_match.group(1).strip()
        except Exception:
            pass

        display_name = self._to_display_name(name, desc)
        if not desc:
            desc = f"{display_name} - 来自 Agensi 市场的 AI 编码助手技能包"

        sub_cat = self._classify(name, desc)
        if not tags:
            tags = self._auto_tags(name, desc)

        return CrawlerResult(
            source="agensi",
            name=name,
            display_name=display_name,
            description=desc,
            category="Skill",
            sub_category=sub_cat,
            price=price,
            original_price=original_price,
            seller_name=seller,
            seller_avatar=f"https://api.dicebear.com/7.x/bottts/svg?seed={seller}",
            tags=tags,
            source_platform=self.source_platform,
            github_url="",
            content_preview=f"# {name}\n\n{desc}\n\nPrice: {price_str}",
            source_url=detail_url,
            version="",
        )

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
