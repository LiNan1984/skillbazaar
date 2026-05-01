from __future__ import annotations
"""
Gate Skills Hub 爬虫
数据源: https://github.com/gate/gate-skills
策略: 解析 README 获取技能列表 → 逐个抓取 SKILL.md
"""
import re
import json
import httpx
from typing import Optional
from .base import BaseCrawler, CrawlerResult

GITHUB_RAW = "https://raw.githubusercontent.com/gate/gate-skills/master"
GITHUB_API = "https://api.github.com/repos/gate/gate-skills/contents/skills"
README_URL = "https://raw.githubusercontent.com/gate/gate-skills/master/README.md"

# 技能复杂度 → 价格映射
PRICE_MAP = {
    "read-only": (19, 59),
    "query": (19, 59),
    "simple": (19, 59),
    "trading": (99, 199),
    "transaction": (99, 199),
    "analysis": (79, 149),
    "composite": (99, 199),
    "installer": (0, 0),
    "default": (49, 129),
}

# 关键词 → 复杂度分类
COMPLEXITY_KEYWORDS = {
    "read-only": ["查询", "只读", "query", "read-only", "overview", "listing", "briefing"],
    "query": ["status", "balance", "fee", "rate", "check", "tracker", "scanner", "monitor"],
    "simple": ["guide", "installer", "setup", "kyc", "portal"],
    "trading": ["trading", "trade", "buy", "sell", "swap", "spot", "futures", "position", "order"],
    "transaction": ["transfer", "pay", "payment", "send", "withdraw"],
    "analysis": ["analysis", "analyze", "overview", "compare", "trend", "risk", "sentiment"],
    "composite": ["manager", "research", "copilot", "end-to-end"],
    "installer": ["installer", "install"],
}


def classify_complexity(desc: str, name: str) -> str:
    text = (desc + " " + name).lower()
    for category, keywords in COMPLEXITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "default"


def get_price_range(complexity: str) -> tuple[int, int]:
    return PRICE_MAP.get(complexity, PRICE_MAP["default"])


class GateSkillsCrawler(BaseCrawler):
    source_name = "gate"
    source_platform = "Gate Skills Hub"

    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={
            "User-Agent": "SkillBazaar-Crawler/1.0"
        })

    def fetch_list(self) -> list[dict]:
        """从 README 解析技能列表"""
        resp = self.client.get(README_URL)
        resp.raise_for_status()
        readme = resp.text

        # 提取技能表格行: | skill-name | description | version | status |
        skills = []
        # Format: | [gate-exchange-tradfi](#-gate-exchange-tradfi) | description | `version` | status |
        pattern = r'\|\s*\[?`?([\w-]+)`?\]?\s*\|.*?\|\s*`?([\d.]+-?\d*)`?\s*\|\s*(\S+)\s*\|'
        for match in re.finditer(pattern, readme):
            name, version, status = match.groups()
            if name.startswith("---") or name.lower() in ("skill", "name"):
                continue
            # Extract description from the same line
            line = match.group(0)
            parts = line.split('|')
            desc = parts[2].strip() if len(parts) > 2 else ""
            skills.append({
                "name": name.strip(),
                "description": desc.strip(),
                "version": version.strip(),
                "status": status.strip(),
            })
        return skills

    def fetch_detail(self, item: dict) -> Optional[CrawlerResult]:
        """抓取 SKILL.md 详情"""
        name = item["name"]
        skill_md_url = f"{GITHUB_RAW}/skills/{name}/SKILL.md"

        content_preview = ""
        try:
            resp = self.client.get(skill_md_url)
            if resp.status_code == 200:
                content_preview = resp.text[:800]
        except Exception:
            pass

        desc = item.get("description", "")
        complexity = classify_complexity(desc, name)
        lo, hi = get_price_range(complexity)
        price = (lo + hi) // 2
        original_price = int(price * 1.3) if price > 0 else 0

        # 从描述提取标签
        tags = []
        tag_keywords = {
            "交易": ["trading", "trade", "buy", "sell", "spot", "futures", "order"],
            "分析": ["analysis", "analyze", "overview", "market"],
            "DeFi": ["defi", "tvl", "yield", "liquidity", "staking"],
            "新闻": ["news", "briefing", "sentiment", "community"],
            "安全": ["risk", "security", "audit"],
            "钱包": ["wallet", "address", "on-chain"],
            "管理": ["manager", "assets", "account", "sub-account"],
            "自动化": ["auto", "cron", "monitor", "alert"],
        }
        text_lower = (desc + " " + name).lower()
        for tag, kws in tag_keywords.items():
            if any(kw in text_lower for kw in kws):
                tags.append(tag)
        if not tags:
            tags = ["工具"]

        # 生成中文名
        display_name = self._to_display_name(name, desc)

        return CrawlerResult(
            source="gate",
            name=name,
            display_name=display_name,
            description=desc if desc else display_name,
            category="Skill",
            sub_category=tags[0] if tags else "工具",
            price=price,
            original_price=original_price,
            seller_name="Gate.io",
            seller_avatar="https://api.dicebear.com/7.x/bottts/svg?seed=gate",
            tags=tags[:5],
            source_platform=self.source_platform,
            github_url="https://github.com/gate/gate-skills",
            content_preview=content_preview,
            source_url=f"https://github.com/gate/gate-skills/tree/master/skills/{name}",
            version=item.get("version", ""),
        )

    @staticmethod
    def _to_display_name(name: str, desc: str) -> str:
        """从技能名生成中文展示名"""
        mapping = {
            "spot": "现货交易", "futures": "合约交易", "trading": "端到端交易",
            "assets": "资产查询", "marketanalysis": "市场分析", "affiliate": "推荐返佣",
            "unified": "统一账户", "transfer": "内部转账", "pay": "支付",
            "dex-market": "DEX行情", "dex-trade": "DEX交易", "dex-wallet": "DEX钱包",
            "coinanalysis": "币种分析", "coincompare": "多币对比",
            "defianalysis": "DeFi分析", "marketoverview": "市场概览",
            "trendanalysis": "趋势分析", "riskcheck": "风险检测",
            "tokenonchain": "链上分析", "addresstracker": "地址追踪",
            "briefing": "新闻简报", "communityscan": "社区情绪",
            "eventexplain": "事件解读", "listing": "上币追踪",
            "macroimpact": "宏观影响", "dual": "双币投资",
            "staking": "质押查询", "autoinvest": "定投管理",
            "subaccount": "子账户", "simpleearn": "活期理财",
            "tradfi": "传统金融", "flashswap": "闪兑",
            "smallbalance": "小额资产", "vipfee": "VIP费率",
            "liveroomlocation": "直播", "referral": "邀请奖励",
            "assets-manager": "资产管理", "research": "研究助手",
            "welfare": "福利中心", "launchpool": "LaunchPool",
            "kyc": "KYC引导", "collateralloan": "抵押借贷",
            "activitycenter": "活动中心", "coupon": "优惠券",
            "alpha": "Alpha代币", "crossex": "跨交易所",
            "installer": "安装器",
        }
        for key, val in mapping.items():
            if key in name.lower().replace("-", "").replace("_", ""):
                return f"Gate {val}"
        if desc:
            return f"Gate {desc[:20]}"
        return name
