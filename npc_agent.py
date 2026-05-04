#!/usr/bin/env python3
"""
SkillBazaar NPC Agent — 定时上传新商品、发布新悬赏、触发弹窗推送
作为systemd服务运行，每小时执行一次
"""
import requests
import json
import random
import time
import logging
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger('NPCAgent')

BASE = "http://localhost:8000/api"

# NPC credentials
NPCS = [
    ("quant_alice", "npc2024alice"),
    ("llm_bob", "npc2024bob"),
    ("dev_charlie", "npc2024charlie"),
    ("data_diana", "npc2024diana"),
    ("security_eve", "npc2024eve"),
    ("product_frank", "npc2024frank"),
    ("ml_grace", "npc2024grace"),
    ("infra_heidi", "npc2024heidi"),
    ("content_ivan", "npc2024ivan"),
    ("api_judy", "npc2024judy"),
]

# Rotating product pool — each cycle picks from these
NEW_PRODUCTS = [
    {"name": "FinGPT金融分析Agent", "description": "基于FinGPT的金融数据分析Agent，支持A股/港股/美股财报解析、K线形态识别、新闻情绪分析。自动生成投资建议报告，支持回测验证。", "category": "Agent", "sub_category": "金融", "price": 499, "original_price": 899, "seller_name": "量化Alice", "tags": "FinGPT,金融分析,A股,投资", "source_platform": "原创", "pricing_model": "subscription"},
    {"name": "自动化测试Agent", "description": "自动生成单元测试和E2E测试的AI Agent。分析代码逻辑→生成测试用例→执行验证→覆盖率报告。支持pytest/Jest/Playwright，覆盖率提升40%+。", "category": "Agent", "sub_category": "测试", "price": 199, "original_price": 399, "seller_name": "全栈Charlie", "tags": "测试,自动化,pytest,覆盖率", "source_platform": "原创", "pricing_model": "one_time"},
    {"name": "PDF智能解析Workflow", "description": "多格式文档智能解析Workflow：PDF/Word/Excel→OCR→结构化提取→知识图谱→摘要生成。支持表格、图表、公式识别。", "category": "Workflow", "sub_category": "文档处理", "price": 249, "original_price": 499, "seller_name": "数据Diana", "tags": "PDF,OCR,文档解析,结构化", "source_platform": "原创", "pricing_model": "one_time"},
    {"name": "社交媒体监控Cron", "description": "定时监控微博/知乎/X/Twitter关键词，AI分析热点趋势、用户情感、竞品动态。每日9点推送报告到邮箱/飞书。", "category": "Cron", "sub_category": "社媒监控", "price": 99, "original_price": 199, "seller_name": "内容Ivan", "tags": "社媒,监控,情感分析,定时", "source_platform": "原创", "pricing_model": "subscription"},
    {"name": "API网关安全审计Skill", "description": "自动审计API网关安全配置：JWT验证、速率限制、CORS策略、SQL注入防护。生成OWASP Top 10合规报告。", "category": "Skill", "sub_category": "安全", "price": 149, "original_price": 299, "seller_name": "安全Eve", "tags": "API安全,OWASP,审计,JWT", "source_platform": "原创", "pricing_model": "one_time"},
    {"name": "LLM Fine-tune自动化Workflow", "description": "从数据清洗到模型部署的完整fine-tune流程：数据版本→LoRA训练→评估→合并→vLLM部署。支持 Unsloth 2x加速。", "category": "Workflow", "sub_category": "MLOps", "price": 399, "original_price": 799, "seller_name": "ML Grace", "tags": "fine-tune,LoRA,Unsloth,vLLM", "source_platform": "原创", "pricing_model": "one_time"},
]

NEW_BOUNTIES = [
    {"title": "短视频脚本生成Agent开发", "description": "开发一个AI短视频脚本生成Agent：输入主题→分析热门视频→生成脚本（含分镜、文案、配乐建议）→自动排版。支持抖音/小红书风格。", "category": "Agent", "tags": ["短视频", "内容生成", "抖音"], "budget_min": 3000, "budget_max": 8000, "deadline": "2026-06-15", "skill_type": "agent", "requirements": "有短视频内容创作经验，熟悉LLM生成"},
    {"title": "企业知识图谱构建Workflow", "description": "构建企业知识图谱自动化Workflow：文档抽取→实体识别→关系建模→图数据库存储→智能问答。支持Neo4j/ArangoDB。", "category": "Workflow", "tags": ["知识图谱", "NLP", "Neo4j"], "budget_min": 15000, "budget_max": 40000, "deadline": "2026-07-01", "skill_type": "workflow", "requirements": "3年NLP经验，熟悉知识图谱构建"},
    {"title": "电商价格监控Cron", "description": "定时监控淘宝/京东/拼多多商品价格变动，价格低于阈值自动通知。支持历史价格曲线、比价报告。", "category": "Cron", "tags": ["电商", "价格监控", "爬虫"], "budget_min": 2000, "budget_max": 6000, "deadline": "2026-05-20", "skill_type": "cron", "requirements": "熟悉电商爬虫和反爬策略"},
]

npc_tokens = {}
npc_ids = {}

def login_npcs():
    """Login all NPCs and cache tokens"""
    for username, password in NPCS:
        try:
            r = requests.post(f"{BASE}/v2/auth/login", json={"username": username, "password": password})
            if r.status_code == 200:
                data = r.json()
                npc_tokens[username] = data["token"]
                npc_ids[username] = data["user_id"]
        except:
            pass
    logger.info(f"Logged in {len(npc_tokens)} NPCs")

def upload_product():
    """Random NPC uploads a new product"""
    if not npc_tokens:
        return
    prod = random.choice(NEW_PRODUCTS)
    seller = prod["seller_name"]
    # Find NPC matching seller
    username_map = {
        "量化Alice": "quant_alice", "大模型Bob": "llm_bob", "全栈Charlie": "dev_charlie",
        "数据Diana": "data_diana", "安全Eve": "security_eve", "产品Frank": "product_frank",
        "ML Grace": "ml_grace", "运维Heidi": "infra_heidi", "内容Ivan": "content_ivan",
        "API Judy": "api_judy"
    }
    username = username_map.get(seller, random.choice(list(npc_tokens.keys())))
    token = npc_tokens.get(username)
    if not token:
        username = random.choice(list(npc_tokens.keys()))
        token = npc_tokens[username]
    
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE}/products", json=prod, headers=headers)
    if r.status_code in (200, 201):
        logger.info(f"✅ {seller} uploaded: {prod['name']} ¥{prod['price']}")
    else:
        logger.warning(f"❌ Upload failed: {r.text[:100]}")

def post_bounty():
    """Random NPC posts a new bounty"""
    if not npc_tokens:
        return
    bounty = random.choice(NEW_BOUNTIES)
    username = random.choice(list(npc_tokens.keys()))
    token = npc_tokens[username]
    headers = {"Authorization": f"Bearer {token}"}
    # Fix tags to be a list
    if isinstance(bounty.get("tags"), list):
        bounty["tags"] = bounty["tags"]
    r = requests.post(f"{BASE}/bounties", json=bounty, headers=headers)
    if r.status_code in (200, 201):
        logger.info(f"✅ {username} posted bounty: {bounty['title']} ¥{bounty['budget_min']}-{bounty['budget_max']}")
    else:
        logger.warning(f"❌ Bounty failed: {r.text[:100]}")

def run_cycle():
    """One cycle: upload 1-2 products + 0-1 bounties"""
    logger.info(f"🔄 NPC Agent cycle @ {datetime.now().isoformat()}")
    login_npcs()
    
    # Upload 1-2 products
    for _ in range(random.randint(1, 2)):
        upload_product()
        time.sleep(0.5)
    
    # Post 0-1 bounties (30% chance)
    if random.random() < 0.3:
        post_bounty()
    
    logger.info("✅ Cycle complete")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_cycle()
    else:
        # Run as daemon: execute every hour
        logger.info("🤖 NPC Agent daemon started (hourly cycle)")
        while True:
            try:
                run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")
            time.sleep(3600)  # 1 hour
