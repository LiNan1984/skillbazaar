from __future__ import annotations
"""
SkillBazaar 数据爬虫服务
支持 Gate Skills、BitMart Skills、AgentSkillsHub、Agensi 的长期数据同步
"""
from .base import BaseCrawler, CrawlerResult
from .gate import GateSkillsCrawler
from .bitmart import BitMartSkillsCrawler
from .agentskillshub import AgentSkillsHubCrawler
from .agensi import AgensiCrawler
from .sync_service import SyncService

__all__ = [
    "BaseCrawler",
    "CrawlerResult",
    "GateSkillsCrawler",
    "BitMartSkillsCrawler",
    "AgentSkillsHubCrawler",
    "AgensiCrawler",
    "SyncService",
]
