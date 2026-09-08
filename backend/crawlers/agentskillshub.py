from __future__ import annotations
"""
AgentSkillsHub 爬虫
数据源: https://agentskillshub.dev/openclaw/skills/
策略: 解析 Next.js RSC flight payload 中的 skills 数组（含 name/desc/stars/grade）
"""
import re
import httpx
from typing import Optional
from .base import BaseCrawler, CrawlerResult

BASE_URL = "https://agentskillshub.dev"
OPENCLAW_SKILLS_URL = f"{BASE_URL}/openclaw/skills/"
# Cap catalog refresh size; prefer highest heat (stars + installs).
MAX_SKILLS = 200


class AgentSkillsHubCrawler(BaseCrawler):
    source_name = "agentskillshub"
    source_platform = "AgentSkillsHub"

    def __init__(self):
        self.client = httpx.Client(timeout=60, follow_redirects=True, headers={
            "User-Agent": "SkillBazaar-Crawler/1.0"
        })

    def fetch_list(self) -> list[dict]:
        """从 OpenClaw Skills 目录页提取结构化技能列表"""
        resp = self.client.get(OPENCLAW_SKILLS_URL)
        resp.raise_for_status()
        skills = self._parse_rsc_skills(resp.text)
        if not skills:
            # Sitemap-only slugs lack real descriptions; do not treat as a successful
            # crawl that would overwrite committed catalog rows with synthetic text.
            sitemap_count = len(self._parse_sitemap_skills())
            raise RuntimeError(
                "AgentSkillsHub RSC parse returned 0 skills"
                + (f" (sitemap had {sitemap_count} slugs, ignored as metadata-thin)" if sitemap_count else "")
                + "; site shape likely changed"
            )

        skills.sort(
            key=lambda s: (s.get("stars", 0) * 10 + s.get("installs", 0)),
            reverse=True,
        )
        return skills[:MAX_SKILLS]

    def _parse_rsc_skills(self, html: str) -> list[dict]:
        """Parse skill objects from Next.js flight / escaped JSON payloads."""
        skills: list[dict] = []
        seen: set[str] = set()

        # Prefer unescaped flight chunks when present
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
        payloads = [html]
        for c in chunks:
            try:
                payloads.append(bytes(c, "utf-8").decode("unicode_escape"))
            except Exception:
                payloads.append(
                    c.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
                )

        obj_pat = re.compile(
            r'\{\s*"id"\s*:\s*"openclaw:[^"]+"\s*,\s*'
            r'"name"\s*:\s*"([^"]+)"\s*,\s*'
            r'"slug"\s*:\s*"([^"]+)"\s*,\s*'
            r'"author"\s*:\s*"([^"]*)"\s*,\s*'
            r'"category"\s*:\s*"([^"]*)"\s*,\s*'
            r'"description"\s*:\s*"((?:\\.|[^"\\])*)"\s*,\s*'
            r'"stars"\s*:\s*(\d+)\s*,\s*'
            r'"install_count"\s*:\s*(\d+).*?'
            r'"securityGrade"\s*:\s*"([A-F])".*?'
            r'"source_url"\s*:\s*"([^"]*)"',
            re.DOTALL,
        )

        for payload in payloads:
            for match in obj_pat.finditer(payload):
                name, slug, author, category, desc, stars, installs, grade, source_url = match.groups()
                key = name.strip() or slug.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                desc = bytes(desc, "utf-8").decode("unicode_escape") if "\\" in desc else desc
                skills.append({
                    "name": key,
                    "slug": slug.strip(),
                    "description": desc.strip()[:300],
                    "grade": grade,
                    "installs": int(installs),
                    "stars": int(stars),
                    "heat": int(stars) * 10 + int(installs) // 100,
                    "rank": len(skills) + 1,
                    "author": author,
                    "category": category,
                    "source_url": source_url,
                })

        # Looser fallback if strict pattern misses (escaped quotes in raw HTML)
        if not skills:
            esc_pat = re.compile(
                r'\\"name\\":\\"([^\\"]+)\\".{0,80}?\\"slug\\":\\"([^\\"]+)\\".{0,200}?'
                r'\\"description\\":\\"((?:\\\\.|[^\\"\\])*)\\".{0,80}?'
                r'\\"stars\\":(\d+).{0,80}?\\"install_count\\":(\d+).{0,200}?'
                r'\\"securityGrade\\":\\"([A-F])\\".{0,200}?\\"source_url\\":\\"([^\\"]*)\\"',
                re.DOTALL,
            )
            for match in esc_pat.finditer(html):
                name, slug, desc, stars, installs, grade, source_url = match.groups()
                key = name.strip() or slug.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                desc = desc.replace('\\"', '"').replace("\\n", " ")
                skills.append({
                    "name": key,
                    "slug": slug.strip(),
                    "description": desc.strip()[:300],
                    "grade": grade,
                    "installs": int(installs),
                    "stars": int(stars),
                    "heat": int(stars) * 10 + int(installs) // 100,
                    "rank": len(skills) + 1,
                    "author": "",
                    "category": "",
                    "source_url": source_url,
                })
        return skills

    def _parse_sitemap_skills(self) -> list[dict]:
        resp = self.client.get(f"{BASE_URL}/sitemap.xml")
        resp.raise_for_status()
        locs = re.findall(
            r"<loc>(https://agentskillshub\.dev/skills/([\w.-]+)/?)</loc>",
            resp.text,
        )
        skills = []
        for url, slug in locs:
            skills.append({
                "name": slug,
                "slug": slug,
                "description": "",
                "grade": "B",
                "installs": 0,
                "stars": 0,
                "heat": 0,
                "rank": len(skills) + 1,
                "author": "",
                "category": "",
                "source_url": url,
            })
        return skills

    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        name = item["name"]
        heat = item.get("heat", 100)
        stars = item.get("stars", 0)
        installs = item.get("installs", 0)

        # Price based on heat / popularity
        if heat > 170:
            price = 149 + min(heat - 170, 100)
        elif heat > 100:
            price = 89 + (heat - 100) // 2
        else:
            price = 49 + max(heat, 0) // 5

        original_price = int(price * 1.3)

        desc_en = item.get("description", "")
        display_name = self._generate_display_name(name, desc_en)
        desc_zh = self._generate_description(name, desc_en)
        sub_cat = item.get("category") or self._classify_category(name, desc_en)
        tags = self._extract_tags(name, desc_en)
        grade = item.get("grade", "B")
        source_url = item.get("source_url") or f"{BASE_URL}/skills/{item.get('slug', name)}/"
        github_url = source_url if "github.com" in source_url else ""

        return CrawlerResult(
            source="agentskillshub",
            name=name,
            display_name=display_name,
            description=desc_zh,
            category="Skill",
            sub_category=sub_cat,
            price=min(price, 299),
            original_price=min(original_price, 399),
            seller_name=item.get("author") or "AgentSkillsHub",
            seller_avatar="https://api.dicebear.com/7.x/bottts/svg?seed=agentskillshub",
            tags=tags,
            source_platform=self.source_platform,
            github_url=github_url,
            content_preview=(
                f"# {name}\n\n{desc_zh}\n\n"
                f"Security Grade: {grade}\nStars: {stars}\nInstalls: {installs:,}\nHeat: {heat}"
            ),
            source_url=source_url,
            version="",
            extra={"grade": grade, "heat": heat, "installs": installs, "stars": stars},
        )

    @staticmethod
    def _generate_display_name(name: str, desc: str) -> str:
        known = {
            "self-improvement": "自我改进引擎", "capability-evolver": "能力进化器",
            "byterover": "代码搜索助手", "agent-browser": "Agent 浏览器",
            "proactive-agent": "主动式Agent", "clawddocs": "文档专家",
            "bird": "X/Twitter 工具", "auto-updater": "自动更新器",
            "everything": "通用测试服务器", "fetch": "网页内容获取",
            "filesystem": "文件系统工具", "git": "Git 仓库工具",
            "memory": "知识图谱记忆", "sequential-thinking": "顺序思维推理",
            "time": "时间时区转换", "aws-bedrock": "AWS Bedrock 查询",
            "aws-cdk": "AWS CDK 工具", "aws-core": "AWS 核心服务",
        }
        if name in known:
            return known[name]
        if desc:
            return desc[:30]
        return name.replace("-", " ").title()

    @staticmethod
    def _generate_description(name: str, desc: str) -> str:
        if desc and len(desc) > 10:
            return desc[:200]
        templates = {
            "browser": "浏览器自动化工具，支持页面导航、点击、输入和截图",
            "agent": "AI Agent 能力增强工具，提升智能体表现",
            "code": "代码分析和处理工具，辅助开发流程",
            "search": "智能搜索工具，快速定位信息",
            "doc": "文档生成和管理工具，提升文档质量",
            "test": "测试工具，自动化质量保障",
            "security": "安全审计工具，检测潜在风险",
            "deploy": "部署工具，简化发布流程",
        }
        name_lower = name.lower()
        for key, template in templates.items():
            if key in name_lower:
                return template
        return f"{name} 是一个 AI Agent 辅助工具，扩展智能体的功能"

    @staticmethod
    def _classify_category(name: str, desc: str) -> str:
        text = (name + " " + desc).lower()
        if any(k in text for k in ["browser", "scrape", "crawl", "automation"]):
            return "浏览器与自动化"
        if any(k in text for k in ["code", "develop", "ide", "coding"]):
            return "编码智能体与IDE"
        if any(k in text for k in ["search", "research", "web"]):
            return "搜索与研究"
        if any(k in text for k in ["doc", "readme", "changelog"]):
            return "文档"
        if any(k in text for k in ["test", "qa", "audit"]):
            return "测试与质量"
        if any(k in text for k in ["deploy", "devops", "ci/cd", "cloud"]):
            return "DevOps"
        if any(k in text for k in ["security", "auth", "permission"]):
            return "安全"
        if any(k in text for k in ["memory", "knowledge", "context"]):
            return "AI与LLM"
        if any(k in text for k in ["git", "github", "commit"]):
            return "Git工具"
        if any(k in text for k in ["productivity", "task", "workflow"]):
            return "效率与任务"
        return "开发工具"

    @staticmethod
    def _extract_tags(name: str, desc: str) -> list[str]:
        text = (name + " " + desc).lower()
        tags = []
        tag_map = {
            "MCP": ["mcp", "model context protocol"],
            "Agent": ["agent", "autonomous"],
            "开发": ["develop", "code", "coding", "ide"],
            "自动化": ["automat", "browser", "scrape"],
            "安全": ["security", "audit", "vuln"],
            "AI": ["ai", "llm", "model", "reasoning"],
            "文档": ["doc", "readme", "markdown"],
            "测试": ["test", "qa", "coverage"],
        }
        for tag, keywords in tag_map.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        return tags[:4] if tags else ["工具"]
