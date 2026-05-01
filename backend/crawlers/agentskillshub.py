from __future__ import annotations
"""
AgentSkillsHub 爬虫
数据源: https://agentskillshub.dev/
策略: 抓取首页 Top Skills + 分页获取更多
"""
import re
import json
import httpx
from typing import Optional
from .base import BaseCrawler, CrawlerResult

BASE_URL = "https://agentskillshub.dev"


class AgentSkillsHubCrawler(BaseCrawler):
    source_name = "agentskillshub"
    source_platform = "AgentSkillsHub"

    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={
            "User-Agent": "SkillBazaar-Crawler/1.0"
        })

    def fetch_list(self) -> list[dict]:
        """从首页和分类页抓取技能列表"""
        skills = []
        seen = set()

        # Fetch homepage
        resp = self.client.get(BASE_URL)
        resp.raise_for_status()
        html = resp.text

        # Parse skill entries from HTML (ranked list)
        # Pattern: number + name + grade + description + installs + heat
        pattern = r'(\d+)\s+([\w-]+)\s+([A-F])\s+(.+?)(?:\s+(\d[\d,]*)\s+Installs)?\s+(\d[\d,]*)\s+Heat'
        for match in re.finditer(pattern, html, re.DOTALL):
            rank, name, grade, desc, installs, heat = match.groups()
            if name in seen:
                continue
            seen.add(name)
            skills.append({
                "name": name.strip(),
                "description": desc.strip()[:200],
                "grade": grade.strip(),
                "installs": int(installs.replace(",", "")) if installs else 0,
                "heat": int(heat.replace(",", "")),
                "rank": int(rank),
            })

        # If regex failed, try parsing JSON-LD or structured data
        if not skills:
            skills = self._parse_structured(html, seen)

        return skills

    def _parse_structured(self, html: str, seen: set) -> list[dict]:
        """备用解析：从结构化数据提取"""
        skills = []
        # Try to find skill names in common patterns
        for match in re.finditer(r'"name":\s*"([\w-]+)"', html):
            name = match.group(1)
            if name not in seen and not name.startswith(("Open", "Fetch", "Filesystem", "Git ", "Memory ", "Sequential")):
                seen.add(name)
                skills.append({
                    "name": name,
                    "description": "",
                    "grade": "B",
                    "installs": 0,
                    "heat": 100,
                    "rank": len(skills) + 1,
                })
        return skills

    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        name = item["name"]
        heat = item.get("heat", 100)

        # Price based on heat score
        if heat > 170:
            price = 149 + (heat - 170)
        elif heat > 100:
            price = 89 + (heat - 100) // 2
        else:
            price = 49 + heat // 5

        original_price = int(price * 1.3)

        # Generate Chinese description
        desc_en = item.get("description", "")
        display_name = self._generate_display_name(name, desc_en)
        desc_zh = self._generate_description(name, desc_en)

        # Determine sub-category
        sub_cat = self._classify_category(name, desc_en)

        # Tags
        tags = self._extract_tags(name, desc_en)

        return CrawlerResult(
            source="agentskillshub",
            name=name,
            display_name=display_name,
            description=desc_zh,
            category="Skill",
            sub_category=sub_cat,
            price=min(price, 299),
            original_price=min(original_price, 399),
            seller_name="AgentSkillsHub",
            seller_avatar="https://api.dicebear.com/7.x/bottts/svg?seed=agentskillshub",
            tags=tags,
            source_platform=self.source_platform,
            github_url="",
            content_preview=f"# {name}\n\n{desc_zh}\n\nSecurity Grade: {item.get('grade', 'B')}\nInstalls: {item.get('installs', 0):,}\nHeat: {heat}",
            source_url=f"{BASE_URL}",
            version="",
            extra={"grade": item.get("grade", "B"), "heat": heat, "installs": item.get("installs", 0)},
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
            return desc[:100]
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
