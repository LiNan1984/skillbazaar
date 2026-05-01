from __future__ import annotations

import os
import aiosqlite
import json
import random
from datetime import datetime

DB_PATH = "/Users/linan/Desktop/aicode/skillbazaar/backend/skillbazaar.db"


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    try:
        await _create_tables(db)
        await _seed_products(db)
    finally:
        await db.close()


async def _create_tables(db: aiosqlite.Connection):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            sub_category TEXT,
            price INTEGER NOT NULL,
            original_price INTEGER,
            seller_name TEXT NOT NULL,
            seller_avatar TEXT,
            rating REAL DEFAULT 4.0,
            downloads INTEGER DEFAULT 0,
            sales INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            source_platform TEXT,
            github_url TEXT,
            icon TEXT,
            content_preview TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            auth_token TEXT,
            nickname TEXT NOT NULL,
            avatar TEXT NOT NULL,
            coins INTEGER DEFAULT 10000,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            last_active_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id TEXT NOT NULL,
            seller_id TEXT,
            product_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            created_at TEXT,
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS skill_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id),
            skill_type TEXT NOT NULL,
            encrypted_blob BLOB NOT NULL,
            encryption_iv TEXT NOT NULL,
            encryption_salt TEXT NOT NULL,
            skill_meta TEXT,
            content_hash TEXT NOT NULL,
            file_size INTEGER,
            version TEXT DEFAULT '1.0.0',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            license_type TEXT NOT NULL,
            license_token TEXT UNIQUE NOT NULL,
            expires_at TEXT,
            max_calls INTEGER,
            calls_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skill_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER REFERENCES licenses(id),
            user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            execution_type TEXT NOT NULL,
            input_params TEXT,
            output_summary TEXT,
            duration_ms INTEGER,
            status TEXT DEFAULT 'success',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL REFERENCES users(id),
            industry TEXT DEFAULT '',
            interests TEXT DEFAULT '[]',
            latitude REAL,
            longitude REAL,
            city TEXT DEFAULT '',
            language TEXT DEFAULT 'zh-CN',
            bio TEXT DEFAULT '',
            preferred_categories TEXT DEFAULT '[]',
            preferred_price_range TEXT DEFAULT '{}',
            total_spent INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_purchases INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            last_active_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            type TEXT NOT NULL,
            ref_type TEXT,
            ref_id TEXT,
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_behavior (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skill_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER REFERENCES products(id),
            action TEXT NOT NULL,
            actor_id TEXT,
            old_data TEXT,
            new_data TEXT,
            reason TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            coins INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            expires_at TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            old_price INTEGER NOT NULL,
            new_price INTEGER NOT NULL,
            pricing_model TEXT DEFAULT 'fixed',
            demand_score REAL DEFAULT 0,
            reason TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bounties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poster_id TEXT NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT DEFAULT 'Skill',
            tags TEXT DEFAULT '[]',
            budget_min INTEGER NOT NULL,
            budget_max INTEGER NOT NULL,
            deadline TEXT,
            status TEXT DEFAULT 'open',
            selected_developer_id TEXT,
            final_price INTEGER,
            skill_type TEXT DEFAULT 'prompt',
            requirements TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bounty_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bounty_id INTEGER NOT NULL REFERENCES bounties(id),
            developer_id TEXT NOT NULL REFERENCES users(id),
            proposal TEXT NOT NULL,
            estimated_days INTEGER DEFAULT 7,
            quoted_price INTEGER NOT NULL,
            portfolio TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bounty_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bounty_id INTEGER NOT NULL REFERENCES bounties(id),
            developer_id TEXT NOT NULL REFERENCES users(id),
            encrypted_blob BLOB,
            encryption_iv TEXT,
            encryption_salt TEXT,
            content_hash TEXT,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            reviewed_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    await db.commit()


def _rand_rating():
    return round(random.uniform(3.5, 5.0), 1)


def _rand_downloads():
    return random.randint(100, 50000)


def _rand_sales():
    return random.randint(10, 10000)


def _rand_avatar():
    styles = ["adventurer", "avataaars", "bottts", "croodles", "fun-emoji", "lorelei", "micah", "notionists", "open-peeps", "personas"]
    style = random.choice(styles)
    seed = random.randint(1, 9999)
    return f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}"


def _rand_date():
    year = random.choice([2024, 2025, 2026])
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def _load_seed_json(filename: str) -> list[dict]:
    filepath = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_seed_products():
    import glob as glob_mod
    seed_dir = os.path.dirname(__file__)
    products = []

    # Load all seed_*.json files
    for seed_file in sorted(glob_mod.glob(os.path.join(seed_dir, "seed_*.json"))):
        items = _load_seed_json(os.path.basename(seed_file))
        for item in items:
            product = {
                "name": item.get("name", ""),
                "description": item.get("description", item.get("display_name", "")),
                "category": item.get("category", "Skill"),
                "sub_category": item.get("sub_category", ""),
                "price": item.get("price", 99),
                "original_price": item.get("original_price", item.get("price", 99)),
                "seller_name": item.get("seller_name", "社区"),
                "seller_avatar": item.get("seller_avatar", f"https://api.dicebear.com/7.x/bottts/svg?seed={item.get('seller_name','default')}"),
                "rating": item.get("rating", round(random.uniform(4.0, 5.0), 1)),
                "downloads": item.get("downloads", random.randint(500, 50000)),
                "sales": item.get("sales", random.randint(50, 5000)),
                "tags": json.dumps(item.get("tags", []), ensure_ascii=False),
                "source_platform": item.get("source_platform", "社区"),
                "github_url": item.get("github_url", ""),
                "icon": item.get("icon"),
                "content_preview": item.get("content_preview", ""),
                "status": "active",
                "created_at": item.get("created_at", datetime.now().strftime("%Y-%m-%d")),
            }
            products.append(product)

    # Also add some Agent / Cron / Workflow if not enough variety
    existing_categories = set(p["category"] for p in products)

    if "Agent" not in existing_categories or sum(1 for p in products if p["category"] == "Agent") < 5:
        agents = [
            {"name": "crypto-trading-bot", "description": "加密货币自动交易Agent，支持多交易所、多策略并行执行", "sub_category": "交易", "price": 399, "tags": ["Agent", "交易", "自动化"]},
            {"name": "market-analysis-agent", "description": "市场分析智能体，综合技术指标、链上数据、新闻情绪生成分析报告", "sub_category": "分析", "price": 299, "tags": ["Agent", "分析", "报告"]},
            {"name": "defi-yield-hunter", "description": "DeFi收益猎人Agent，自动扫描各链流动性池，寻找最优年化收益", "sub_category": "DeFi", "price": 349, "tags": ["Agent", "DeFi", "收益"]},
            {"name": "portfolio-rebalancer", "description": "投资组合再平衡Agent，根据风险偏好和市场变化自动调整资产配置", "sub_category": "管理", "price": 259, "tags": ["Agent", "管理", "投资"]},
            {"name": "whale-tracker", "description": "巨鲸追踪Agent，实时监控大户链上转账和交易行为", "sub_category": "链上", "price": 199, "tags": ["Agent", "链上", "监控"]},
            {"name": "sentiment-analyzer", "description": "市场情绪分析Agent，聚合Twitter、Reddit、新闻的多维度情绪指标", "sub_category": "新闻", "price": 189, "tags": ["Agent", "情绪", "新闻"]},
            {"name": "smart-contract-auditor", "description": "智能合约审计Agent，自动检测重入攻击、溢出漏洞、权限问题等安全风险", "sub_category": "安全", "price": 449, "tags": ["Agent", "安全", "审计"]},
            {"name": "arbitrage-scanner", "description": "跨交易所套利扫描Agent，实时发现价差机会并计算扣除手续费后的利润", "sub_category": "交易", "price": 379, "tags": ["Agent", "套利", "交易"]},
        ]
        for a in agents:
            products.append({
                "name": a["name"], "description": a["description"],
                "category": "Agent", "sub_category": a["sub_category"],
                "price": a["price"], "original_price": int(a["price"] * 1.3),
                "seller_name": "社区", "seller_avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=community",
                "rating": round(random.uniform(4.2, 4.9), 1),
                "downloads": random.randint(1000, 30000),
                "sales": random.randint(100, 3000),
                "tags": json.dumps(a["tags"], ensure_ascii=False),
                "source_platform": "社区", "github_url": "",
                "icon": None, "content_preview": f"# {a['name']}\n\n{a['description']}\n\n## 功能特性\n- 自动化执行\n- 实时监控\n- 策略回测",
                "status": "active", "created_at": datetime.now().strftime("%Y-%m-%d"),
            })

    if "Cron" not in existing_categories or sum(1 for p in products if p["category"] == "Cron") < 3:
        crons = [
            {"name": "daily-market-summary", "description": "每日市场摘要定时任务，每天9点推送BTC/ETH等主流币种行情、涨跌幅、交易量", "sub_category": "定时报告", "price": 49, "tags": ["Cron", "报告", "每日"]},
            {"name": "price-alert-scanner", "description": "价格预警扫描器，每5分钟检查设定价格区间，触发时发送通知", "sub_category": "价格监控", "price": 79, "tags": ["Cron", "价格", "预警"]},
            {"name": "gas-fee-monitor", "description": "Gas费监控定时任务，每10分钟检查以太坊Gas价格，低于阈值时提醒", "sub_category": "链上监控", "price": 39, "tags": ["Cron", "Gas", "以太坊"]},
            {"name": "liquidity-checker", "description": "流动性检查定时任务，每小时扫描DEX流动性池变化，发现大额撤池预警", "sub_category": "DeFi监控", "price": 89, "tags": ["Cron", "DeFi", "流动性"]},
            {"name": "whale-activity-alert", "description": "巨鲸活动提醒，实时监控前100巨鲸地址的大额转账和交易", "sub_category": "链上监控", "price": 99, "tags": ["Cron", "巨鲸", "链上"]},
            {"name": "staking-rewards-tracker", "description": "质押收益追踪器，每天统计各链质押APY和实际收益", "sub_category": "DeFi收益", "price": 59, "tags": ["Cron", "质押", "收益"]},
            {"name": "news-digest-cron", "description": "加密新闻摘要定时任务，每6小时汇总主流媒体加密相关新闻", "sub_category": "新闻摘要", "price": 69, "tags": ["Cron", "新闻", "摘要"]},
            {"name": "portfolio-rebalance-cron", "description": "投资组合自动再平衡定时任务，每周检查并根据策略调整配置", "sub_category": "资产管理", "price": 129, "tags": ["Cron", "投资组合", "自动化"]},
        ]
        for c in crons:
            products.append({
                "name": c["name"], "description": c["description"],
                "category": "Cron", "sub_category": c["sub_category"],
                "price": c["price"], "original_price": int(c["price"] * 1.3),
                "seller_name": "社区", "seller_avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=community",
                "rating": round(random.uniform(4.0, 4.8), 1),
                "downloads": random.randint(500, 20000),
                "sales": random.randint(30, 2000),
                "tags": json.dumps(c["tags"], ensure_ascii=False),
                "source_platform": "社区", "github_url": "",
                "icon": None, "content_preview": f"# {c['name']}\n\n{c['description']}\n\n## 执行频率\n- 定时自动执行\n- 支持Webhook通知\n- 可自定义触发条件",
                "status": "active", "created_at": datetime.now().strftime("%Y-%m-%d"),
            })

    if "Workflow" not in existing_categories or sum(1 for p in products if p["category"] == "Workflow") < 3:
        workflows = [
            {"name": "trading-strategy-pipeline", "description": "交易策略流水线：市场分析→信号生成→风控检查→订单执行→结果通知", "sub_category": "交易", "price": 299, "tags": ["Workflow", "交易", "策略"]},
            {"name": "defi-analysis-flow", "description": "DeFi分析流程：TVL查询→协议对比→收益计算→风险评估→推荐生成", "sub_category": "DeFi", "price": 249, "tags": ["Workflow", "DeFi", "分析"]},
            {"name": "market-research-workflow", "description": "市场研究工作流：新闻聚合→情绪分析→技术指标→链上数据→综合报告", "sub_category": "研究", "price": 279, "tags": ["Workflow", "研究", "报告"]},
            {"name": "risk-assessment-pipeline", "description": "风控评估流水线：合约扫描→权限检查→资金分布→历史行为→风险评分", "sub_category": "风险", "price": 199, "tags": ["Workflow", "风险", "安全"]},
            {"name": "social-sentiment-monitor", "description": "社交媒体情绪监控流程：数据采集→NLP分析→趋势预测→异常检测→预警推送", "sub_category": "情绪", "price": 229, "tags": ["Workflow", "情绪", "监控"]},
        ]
        for w in workflows:
            products.append({
                "name": w["name"], "description": w["description"],
                "category": "Workflow", "sub_category": w["sub_category"],
                "price": w["price"], "original_price": int(w["price"] * 1.3),
                "seller_name": "社区", "seller_avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=community",
                "rating": round(random.uniform(4.3, 4.9), 1),
                "downloads": random.randint(500, 15000),
                "sales": random.randint(50, 1500),
                "tags": json.dumps(w["tags"], ensure_ascii=False),
                "source_platform": "社区", "github_url": "",
                "icon": None, "content_preview": f"# {w['name']}\n\n{w['description']}\n\n## 工作流步骤\n1. 数据采集\n2. 分析处理\n3. 结果输出",
                "status": "active", "created_at": datetime.now().strftime("%Y-%m-%d"),
            })

    return products


def _OLD_build_seed_products():
    products = []

    # ===== Gate Skills (46 skills) =====
    gate_skills = [
        ("Spot Trading", "现货交易技能", "spot-trading", '["交易", "现货"]'),
        ("Futures Trading", "期货交易技能，支持杠杆与合约操作", "futures-trading", '["交易", "期货"]'),
        ("DEX Market", "去中心化交易所市场数据查询", "dex-market", '["交易", "DEX", "市场"]'),
        ("DEX Trade", "去中心化交易所交易执行", "dex-trade", '["交易", "DEX"]'),
        ("DEX Wallet", "去中心化钱包管理工具", "dex-wallet", '["钱包", "DEX", "管理"]'),
        ("DeFi Analysis", "DeFi协议深度分析工具", "defi-analysis", '["分析", "DeFi"]'),
        ("Market Overview", "加密市场全景概览", "market-overview", '["分析", "市场"]'),
        ("Trend Analysis", "多维度趋势分析与预测", "trend-analysis", '["分析", "趋势"]'),
        ("Coin Analysis", "单一币种深度分析报告", "coin-analysis", '["分析", "币种"]'),
        ("Coin Compare", "多币种对比分析工具", "coin-compare", '["分析", "对比"]'),
        ("Risk Check", "投资风险评估与预警", "risk-check", '["安全", "风险"]'),
        ("Token On-chain", "代币链上数据追踪", "token-onchain", '["分析", "链上"]'),
        ("Address Tracker", "链上地址追踪与监控", "address-tracker", '["分析", "链上"]'),
        ("News Briefing", "加密行业新闻速报", "news-briefing", '["新闻", "资讯"]'),
        ("Community Scan", "社区热点与舆情扫描", "community-scan", '["新闻", "社区"]'),
        ("Event Explain", "重大事件解读与分析", "event-explain", '["新闻", "分析"]'),
        ("Listing Tracker", "新币上线追踪与提醒", "listing-tracker", '["交易", "新币"]'),
        ("Macro Impact", "宏观经济对加密市场影响分析", "macro-impact", '["分析", "宏观"]'),
        ("Affiliate", "推荐返佣管理工具", "affiliate", '["管理", "推荐"]'),
        ("Unified Account", "统一账户资产管理", "unified-account", '["管理", "资产"]'),
        ("Assets", "多链资产汇总视图", "assets", '["管理", "资产"]'),
        ("Dual Investment", "双币理财产品管理", "dual-investment", '["DeFi", "理财"]'),
        ("Staking", "质押挖矿收益管理", "staking", '["DeFi", "质押"]'),
        ("Auto-Invest", "定投策略自动化工具", "auto-invest", '["自动化", "定投"]'),
        ("Sub-account", "子账户管理工具", "sub-account", '["管理", "账户"]'),
        ("Simple Earn", "简单理财产品入口", "simple-earn", '["DeFi", "理财"]'),
        ("TradFi", "传统金融工具接入", "tradfi", '["交易", "传统金融"]'),
        ("Transfer", "跨链/站内转账工具", "transfer", '["钱包", "转账"]'),
        ("Flash Swap", "闪兑快速交易工具", "flash-swap", '["交易", "兑换"]'),
        ("Small Balance", "小额资产清理与兑换", "small-balance", '["管理", "资产"]'),
        ("VIP Fee", "VIP费率查询与优化", "vip-fee", '["交易", "费率"]'),
        ("Live Room", "直播交易室工具", "live-room", '["交易", "直播"]'),
        ("Spot", "现货快捷交易工具", "spot", '["交易", "现货"]'),
        ("Trading", "综合交易工具集", "trading", '["交易"]'),
        ("Alpha", "Alpha策略信号工具", "alpha", '["交易", "策略"]'),
        ("Coupon", "优惠券与手续费减免管理", "coupon", '["管理", "优惠"]'),
        ("Cross-exchange", "跨交易所套利工具", "cross-exchange", '["交易", "套利"]'),
        ("Pay", "加密支付工具", "pay", '["支付", "钱包"]'),
        ("Installer", "工具安装与部署助手", "installer", '["开发", "部署"]'),
        ("Futures", "期货合约高级工具", "futures", '["交易", "期货"]'),
        ("Referral", "邀请推荐奖励管理", "referral", '["管理", "推荐"]'),
        ("Assets Manager", "高级资产管理工具", "assets-manager", '["管理", "资产"]'),
        ("Research", "投研报告生成工具", "research", '["分析", "投研"]'),
        ("Welfare", "福利活动中心入口", "welfare", '["活动", "福利"]'),
        ("Launchpool", "新币挖矿参与工具", "launchpool", '["DeFi", "挖矿"]'),
        ("KYC", "身份认证辅助工具", "kyc", '["管理", "认证"]'),
        ("Collateral Loan", "抵押借贷管理工具", "collateral-loan", '["DeFi", "借贷"]'),
        ("Activity Center", "活动中心综合入口", "activity-center", '["活动"]'),
    ]

    for name, desc, sub_cat, tags in gate_skills:
        price = random.randint(29, 249)
        products.append({
            "name": name,
            "description": desc,
            "category": "Skill",
            "sub_category": sub_cat,
            "price": price,
            "original_price": price + random.randint(20, 80),
            "seller_name": "Gate.io",
            "seller_avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=gate",
            "rating": _rand_rating(),
            "downloads": _rand_downloads(),
            "sales": _rand_sales(),
            "tags": tags,
            "source_platform": "Gate Skills",
            "github_url": "https://github.com/gateio/gate-skills",
            "icon": None,
            "content_preview": f"# {name}\n\n## Overview\n{desc}\n\n## Usage\nThis skill is part of the Gate.io ecosystem.\n\n## Installation\n```bash\ngate install {sub_cat}\n```",
            "status": "active",
            "created_at": _rand_date(),
        })

    # ===== BitMart Skills (2 skills) =====
    bitmart_skills = [
        ("Spot Trading", "BitMart现货交易技能，支持多币种快速交易", "spot-trading", '["交易", "现货"]'),
        ("Futures Trading", "BitMart期货交易技能，支持USDT本位合约", "futures-trading", '["交易", "期货"]'),
    ]

    for name, desc, sub_cat, tags in bitmart_skills:
        price = random.randint(29, 149)
        products.append({
            "name": name,
            "description": desc,
            "category": "Skill",
            "sub_category": sub_cat,
            "price": price,
            "original_price": price + random.randint(10, 50),
            "seller_name": "BitMart",
            "seller_avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=bitmart",
            "rating": _rand_rating(),
            "downloads": _rand_downloads(),
            "sales": _rand_sales(),
            "tags": tags,
            "source_platform": "BitMart Skills",
            "github_url": "https://github.com/bitmart-com/bitmart-skills",
            "icon": None,
            "content_preview": f"# {name}\n\n## Overview\n{desc}\n\n## Usage\nThis skill integrates with BitMart exchange.\n\n## Installation\n```bash\nbitmart install {sub_cat}\n```",
            "status": "active",
            "created_at": _rand_date(),
        })

    # ===== AgentSkillsHub top 20 =====
    ash_skills = [
        ("self-improvement", "自我改进技能，持续优化Agent表现", "agent", '["开发", "Agent"]'),
        ("capability-evolver", "能力进化器，自动扩展Agent功能边界", "agent", '["开发", "Agent"]'),
        ("byterover", "ByteRover代码搜索与智能补全工具", "开发", '["开发", "代码"]'),
        ("agent-browser", "Agent浏览器自动化操控工具", "automation", '["自动化", "浏览器"]'),
        ("proactive-agent", "主动式Agent，自主决策与任务执行", "agent", '["开发", "Agent"]'),
        ("clawddocs", "ClawdDocs智能文档生成与管理工具", "docs", '["开发", "文档"]'),
        ("bird", "Bird消息通知与多渠道推送工具", "notification", '["自动化", "通知"]'),
        ("auto-updater", "自动更新工具，保持技能版本最新", "devops", '["自动化", "更新"]'),
        ("everything", "Everything万能搜索与聚合工具", "search", '["开发", "搜索"]'),
        ("fetch", "Fetch网络请求与数据抓取工具", "network", '["开发", "网络"]'),
        ("filesystem", "文件系统操作与管理工具集", "system", '["开发", "文件"]'),
        ("git", "Git版本控制操作工具", "vcs", '["开发", "Git"]'),
        ("memory", "Agent长期记忆与上下文管理工具", "agent", '["开发", "Agent"]'),
        ("sequential-thinking", "顺序思维推理引擎，增强Agent逻辑能力", "reasoning", '["开发", "推理"]'),
        ("time", "时间管理与定时任务工具", "utility", '["开发", "时间"]'),
        ("aws-bedrock", "AWS Bedrock大模型服务集成工具", "cloud", '["开发", "AWS"]'),
        ("aws-cdk", "AWS CDK基础设施即代码工具", "cloud", '["开发", "AWS"]'),
        ("aws-core", "AWS核心服务集成工具包", "cloud", '["开发", "AWS"]'),
    ]

    for name, desc, sub_cat, tags in ash_skills:
        price = random.randint(29, 199)
        products.append({
            "name": name,
            "description": desc,
            "category": "Skill",
            "sub_category": sub_cat,
            "price": price,
            "original_price": price + random.randint(10, 60),
            "seller_name": "AgentSkillsHub",
            "seller_avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=agentskillshub",
            "rating": _rand_rating(),
            "downloads": _rand_downloads(),
            "sales": _rand_sales(),
            "tags": tags,
            "source_platform": "AgentSkillsHub",
            "github_url": f"https://github.com/AgentSkillsHub/{name}",
            "icon": None,
            "content_preview": f"# {name}\n\n## Overview\n{desc}\n\n## Usage\nThis skill extends your agent capabilities.\n\n## Installation\n```bash\nash install {name}\n```",
            "status": "active",
            "created_at": _rand_date(),
        })

    # ===== Mock Agents (10) =====
    mock_agents = [
        ("加密交易机器人", "全自动加密货币交易机器人，支持多种策略配置、止损止盈、自动下单，适用于主流交易所。", "交易", '["交易", "自动化", "策略"]'),
        ("市场分析Agent", "实时分析加密市场数据，提供多维度技术指标、趋势判断和买卖信号建议。", "分析", '["分析", "市场", "技术指标"]'),
        ("新闻监控Agent", "24/7监控全球加密新闻源，自动过滤重要事件并推送定制化新闻摘要。", "新闻", '["新闻", "监控", "自动化"]'),
        ("DeFi收益猎手", "自动扫描各大DeFi协议，寻找最高收益的流动性挖矿和质押机会。", "DeFi", '["DeFi", "收益", "挖矿"]'),
        ("投资组合管家", "智能管理你的加密资产组合，自动再平衡、风险评估和收益追踪。", "管理", '["管理", "资产", "自动化"]'),
        ("风险评估Agent", "实时评估投资组合风险敞口，提供VaR计算、相关性分析和极端行情预警。", "安全", '["安全", "风险", "分析"]'),
        ("巨鲸追踪Agent", "监控大户钱包地址，实时追踪大额转账和链上操作，发现聪明钱动向。", "链上", '["分析", "链上", "监控"]'),
        ("套利扫描器", "跨交易所价差监控，自动发现套利机会并计算扣除手续费后的净利润。", "交易", '["交易", "套利", "自动化"]'),
        ("情绪分析Agent", "分析社交媒体、论坛和新闻的情感倾向，量化市场恐慌与贪婪指数。", "分析", '["分析", "情绪", "新闻"]'),
        ("智能合约审计Agent", "自动审计智能合约代码，检测常见漏洞、安全风险和Gas优化建议。", "安全", '["安全", "合约", "开发"]'),
    ]

    for name, desc, sub_cat, tags in mock_agents:
        price = random.randint(99, 599)
        products.append({
            "name": name,
            "description": desc,
            "category": "Agent",
            "sub_category": sub_cat,
            "price": price,
            "original_price": price + random.randint(50, 200),
            "seller_name": random.choice(["创意旅人", "代码诗人", "AI调教师", "自动化达人", "区块链先锋"]),
            "seller_avatar": _rand_avatar(),
            "rating": _rand_rating(),
            "downloads": _rand_downloads(),
            "sales": _rand_sales(),
            "tags": tags,
            "source_platform": "社区",
            "github_url": None,
            "icon": None,
            "content_preview": f"# {name}\n\n## 简介\n{desc}\n\n## 功能特点\n- 智能化自动运行\n- 多维度数据分析\n- 实时监控与推送\n\n## 使用方法\n配置参数后即可启动Agent自动运行。",
            "status": "active",
            "created_at": _rand_date(),
        })

    # ===== Mock Crons (8) =====
    mock_crons = [
        ("每日市场简报", "每日定时生成市场概览报告，涵盖主流币种涨跌幅、成交量、热点板块和重要事件。", "定时报告", '["自动化", "报告", "市场"]'),
        ("价格预警扫描器", "自定义价格阈值，当币种价格触及设定值时立即推送预警通知。", "价格监控", '["自动化", "预警", "价格"]'),
        ("投资组合再平衡器", "根据设定的资产配比，定期检查并建议再平衡操作，保持组合健康。", "资产管理", '["自动化", "资产", "管理"]'),
        ("新闻摘要生成器", "每日自动汇总加密领域重要新闻，生成结构化摘要并推送至指定渠道。", "新闻摘要", '["自动化", "新闻", "摘要"]'),
        ("Gas费监控器", "实时监控以太坊等链的Gas费水平，在低Gas时段提醒用户执行交易。", "链上监控", '["自动化", "Gas", "监控"]'),
        ("流动性检查器", "定期检查DEX流动性池变化，发现大额流动性撤出或新增事件。", "DeFi监控", '["自动化", "DeFi", "流动性"]'),
        ("质押收益追踪器", "追踪各质押协议的收益变化，自动计算复利收益并生成收益报告。", "DeFi收益", '["自动化", "DeFi", "质押"]'),
        ("巨鲸活动提醒", "监控指定巨鲸地址的链上活动，包括大额转账、DEX交易和合约交互。", "链上监控", '["自动化", "巨鲸", "监控"]'),
    ]

    for name, desc, sub_cat, tags in mock_crons:
        price = random.randint(19, 199)
        products.append({
            "name": name,
            "description": desc,
            "category": "Cron",
            "sub_category": sub_cat,
            "price": price,
            "original_price": price + random.randint(10, 80),
            "seller_name": random.choice(["效率专家", "数据探索者", "技能收集者", "策略交易员"]),
            "seller_avatar": _rand_avatar(),
            "rating": _rand_rating(),
            "downloads": _rand_downloads(),
            "sales": _rand_sales(),
            "tags": tags,
            "source_platform": "原创",
            "github_url": None,
            "icon": None,
            "content_preview": f"# {name}\n\n## 简介\n{desc}\n\n## 定时任务配置\n- 执行频率：可自定义\n- 支持多时区设置\n- 失败自动重试\n\n## 使用方法\n配置触发条件和通知方式即可启用。",
            "status": "active",
            "created_at": _rand_date(),
        })

    # ===== Mock Workflows (5) =====
    mock_workflows = [
        ("交易策略流水线", "从数据采集、信号生成、策略回测到自动执行的完整交易策略流水线，支持多策略并行。", "交易", '["交易", "策略", "自动化"]'),
        ("DeFi分析流程", "自动化的DeFi协议分析流程，涵盖TVL监控、收益率对比、风险评估和安全审计。", "DeFi", '["DeFi", "分析", "自动化"]'),
        ("市场研究工作流", "整合链上数据、社交媒体、新闻资讯的多维度市场研究工作流，生成深度研究报告。", "研究", '["分析", "研究", "自动化"]'),
        ("风险评估流水线", "从市场风险、流动性风险到合约风险的全面评估流水线，自动生成风险评分和建议。", "风险", '["安全", "风险", "分析"]'),
        ("社交情绪监控", "实时采集Twitter、Reddit等社交平台的加密相关讨论，量化分析市场情绪并生成情绪指标。", "情绪", '["分析", "情绪", "新闻"]'),
    ]

    for name, desc, sub_cat, tags in mock_workflows:
        price = random.randint(49, 399)
        products.append({
            "name": name,
            "description": desc,
            "category": "Workflow",
            "sub_category": sub_cat,
            "price": price,
            "original_price": price + random.randint(30, 150),
            "seller_name": random.choice(["市场观察家", "策略交易员", "数据探索者", "AI调教师"]),
            "seller_avatar": _rand_avatar(),
            "rating": _rand_rating(),
            "downloads": _rand_downloads(),
            "sales": _rand_sales(),
            "tags": tags,
            "source_platform": "社区",
            "github_url": None,
            "icon": None,
            "content_preview": f"# {name}\n\n## 简介\n{desc}\n\n## 工作流步骤\n1. 数据采集与清洗\n2. 多维度分析\n3. 结果聚合与报告生成\n4. 自动化执行与通知\n\n## 使用方法\n导入工作流模板，配置参数后启动。",
            "status": "active",
            "created_at": _rand_date(),
        })

    return products


async def _seed_products(db: aiosqlite.Connection):
    cursor = await db.execute("SELECT COUNT(*) FROM products")
    row = await cursor.fetchone()
    count = row[0]
    if count > 0:
        return

    products = _build_seed_products()

    for p in products:
        await db.execute(
            """
            INSERT INTO products (
                name, description, category, sub_category, price, original_price,
                seller_name, seller_avatar, rating, downloads, sales, tags,
                source_platform, github_url, icon, content_preview, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["name"], p["description"], p["category"], p["sub_category"],
                p["price"], p["original_price"], p["seller_name"], p["seller_avatar"],
                p["rating"], p["downloads"], p["sales"], p["tags"],
                p["source_platform"], p["github_url"], p["icon"], p["content_preview"],
                p["status"], p["created_at"],
            ),
        )

    await db.commit()

    # Add pricing columns to products if not exist
    try:
        await db.execute("ALTER TABLE products ADD COLUMN pricing_model TEXT DEFAULT 'fixed'")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE products ADD COLUMN base_price INTEGER")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE products ADD COLUMN demand_score REAL DEFAULT 0")
    except Exception:
        pass
    await db.commit()


# ---------- Query Helpers ----------

async def fetch_products(
    category: str | None = None,
    sub_category: str | None = None,
    keyword: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    sort_by: str = "downloads",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        conditions = ["status = 'active'"]
        params = []

        if category:
            conditions.append("category = ?")
            params.append(category)
        if sub_category:
            conditions.append("sub_category = ?")
            params.append(sub_category)
        if keyword:
            conditions.append("(name LIKE ? OR description LIKE ? OR tags LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if min_price is not None:
            conditions.append("price >= ?")
            params.append(min_price)
        if max_price is not None:
            conditions.append("price <= ?")
            params.append(max_price)

        where = " AND ".join(conditions)

        allowed_sorts = {
            "downloads": "downloads DESC",
            "rating": "rating DESC",
            "price_asc": "price ASC",
            "price_desc": "price DESC",
            "sales": "sales DESC",
            "newest": "created_at DESC",
        }
        order = allowed_sorts.get(sort_by, "downloads DESC")

        count_sql = f"SELECT COUNT(*) FROM products WHERE {where}"
        cursor = await db.execute(count_sql, params)
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        data_sql = f"SELECT * FROM products WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?"
        cursor = await db.execute(data_sql, params + [page_size, offset])
        rows = await cursor.fetchall()
        products = [dict(row) for row in rows]

        return products, total
    finally:
        await db.close()


async def fetch_product_by_id(product_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def insert_product(data: dict) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            INSERT INTO products (
                name, description, category, sub_category, price, original_price,
                seller_name, seller_avatar, tags, source_platform, github_url,
                icon, content_preview, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"], data["description"], data["category"],
                data.get("sub_category"), data["price"], data.get("original_price"),
                data["seller_name"], data.get("seller_avatar"), data.get("tags", "[]"),
                data.get("source_platform"), data.get("github_url"),
                data.get("icon"), data.get("content_preview"), "active",
                datetime.now().isoformat(),
            ),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_category_tree() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT category, COUNT(*) as count FROM products WHERE status='active' GROUP BY category"
        )
        rows = await cursor.fetchall()
        categories = []
        for row in rows:
            cat_name = row[0]
            count = row[1]
            sub_cursor = await db.execute(
                "SELECT sub_category, COUNT(*) as count FROM products WHERE status='active' AND category=? GROUP BY sub_category",
                (cat_name,),
            )
            sub_rows = await sub_cursor.fetchall()
            subs = [{"name": sr[0], "count": sr[1]} for sr in sub_rows if sr[0]]
            categories.append({
                "category": cat_name,
                "count": count,
                "sub_categories": subs,
            })
        return categories
    finally:
        await db.close()


# ---------- User Helpers ----------

async def fetch_user(user_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def insert_user(user_id: str, nickname: str, avatar: str) -> dict:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO users (id, nickname, avatar, coins, role, status, created_at) VALUES (?, ?, ?, 10000, 'user', 'active', ?)",
            (user_id, nickname, avatar, now),
        )
        await db.commit()
        return {"id": user_id, "nickname": nickname, "avatar": avatar, "coins": 10000, "created_at": now}
    finally:
        await db.close()


async def update_user_coins(user_id: str, coins: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE users SET coins = ? WHERE id = ?", (coins, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def insert_user_with_auth(user_id: str, username: str, password_hash: str, nickname: str) -> dict:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        avatar = f"https://api.dicebear.com/7.x/bottts/svg?seed={username}"
        await db.execute(
            "INSERT INTO users (id, username, password_hash, nickname, avatar, coins, role, status, created_at) VALUES (?, ?, ?, ?, ?, 10000, 'user', 'active', ?)",
            (user_id, username, password_hash, nickname, avatar, now),
        )
        await db.commit()
        return {"id": user_id, "username": username, "nickname": nickname}
    finally:
        await db.close()


async def fetch_user_by_username(username: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_user_by_token(token: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE auth_token = ? AND status = 'active'", (token,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_user_token(user_id: str, token: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("UPDATE users SET auth_token = ? WHERE id = ?", (token, user_id))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_last_active(user_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE users SET last_active_at = datetime('now') WHERE id = ?", (user_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------- Transaction Helpers ----------

async def insert_transaction(buyer_id: str, seller_id: str | None, product_id: int, amount: int, tx_type: str) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            "INSERT INTO transactions (buyer_id, seller_id, product_id, amount, type, status, created_at) VALUES (?, ?, ?, ?, ?, 'completed', ?)",
            (buyer_id, seller_id, product_id, amount, tx_type, now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_user_transactions(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        count_cursor = await db.execute(
            "SELECT COUNT(*) FROM transactions WHERE buyer_id = ?", (user_id,)
        )
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE buyer_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, page_size, offset),
        )
        rows = await cursor.fetchall()
        transactions = [dict(row) for row in rows]
        return transactions, total
    finally:
        await db.close()


async def fetch_user_library(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT p.*, t.created_at as purchased_at, t.amount as paid_amount
            FROM transactions t
            JOIN products p ON t.product_id = p.id
            WHERE t.buyer_id = ? AND t.type = 'buy' AND t.status = 'completed'
            ORDER BY t.created_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def check_already_purchased(user_id: str, product_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM transactions WHERE buyer_id = ? AND product_id = ? AND type = 'buy' AND status = 'completed'",
            (user_id, product_id),
        )
        count = (await cursor.fetchone())[0]
        return count > 0
    finally:
        await db.close()


# ---------- Skill Asset Helpers ----------

async def insert_skill_asset(data: dict) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO skill_assets
            (product_id, skill_type, encrypted_blob, encryption_iv, encryption_salt,
             skill_meta, content_hash, file_size, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["product_id"], data["skill_type"], data["encrypted_blob"],
             data["encryption_iv"], data["encryption_salt"], data.get("skill_meta"),
             data["content_hash"], data.get("file_size"), data.get("version", "1.0.0")),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_skill_asset(product_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM skill_assets WHERE product_id = ?", (product_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ---------- License Helpers ----------

async def insert_license(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO licenses
            (user_id, product_id, license_type, license_token, expires_at, max_calls, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
            (data["user_id"], data["product_id"], data["license_type"],
             data["license_token"], data.get("expires_at"), data.get("max_calls"), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_license_by_token(token: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM licenses WHERE license_token = ? AND status = 'active'", (token,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_user_licenses(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT l.*, p.name as product_name, p.category, sa.skill_type
            FROM licenses l
            JOIN products p ON l.product_id = p.id
            LEFT JOIN skill_assets sa ON l.product_id = sa.product_id
            WHERE l.user_id = ? AND l.status = 'active'
            ORDER BY l.created_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def increment_license_calls(license_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE licenses SET calls_count = calls_count + 1 WHERE id = ?", (license_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def check_user_has_license(user_id: str, product_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM licenses
            WHERE user_id = ? AND product_id = ? AND status = 'active'
            AND (expires_at IS NULL OR expires_at > datetime('now'))
            ORDER BY created_at DESC LIMIT 1""",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ---------- Execution Helpers ----------

async def insert_execution(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO skill_executions
            (license_id, user_id, product_id, execution_type, input_params,
             output_summary, duration_ms, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.get("license_id"), data["user_id"], data["product_id"],
             data["execution_type"], data.get("input_params"),
             data.get("output_summary"), data.get("duration_ms"),
             data.get("status", "success"), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_user_executions(user_id: str, limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT se.*, p.name as product_name
            FROM skill_executions se
            JOIN products p ON se.product_id = p.id
            WHERE se.user_id = ?
            ORDER BY se.created_at DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ---------- User Profile Helpers ----------

async def fetch_user_profile(user_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_user_profile(user_id: str, data: dict) -> bool:
    db = await get_db()
    try:
        fields = []
        values = []
        for key in ["industry", "interests", "latitude", "longitude", "city",
                     "language", "bio", "preferred_categories", "preferred_price_range"]:
            if key in data:
                val = data[key]
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                fields.append(f"{key} = ?")
                values.append(val)
        if not fields:
            return False
        fields.append("updated_at = datetime('now')")
        values.append(user_id)
        cursor = await db.execute(
            f"UPDATE user_profiles SET {', '.join(fields)} WHERE user_id = ?",
            values,
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def increment_user_stats(user_id: str, field: str, amount: int = 1) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE user_profiles SET {field} = {field} + ?, updated_at = datetime('now') WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------- Wallet Helpers ----------

async def insert_wallet_transaction(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO wallet_transactions
            (user_id, amount, balance_after, type, ref_type, ref_id, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["amount"], data["balance_after"],
             data["type"], data.get("ref_type"), data.get("ref_id"),
             data.get("description", ""), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_wallet_history(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        count_cursor = await db.execute(
            "SELECT COUNT(*) FROM wallet_transactions WHERE user_id = ?", (user_id,)
        )
        total = (await count_cursor.fetchone())[0]
        offset = (page - 1) * page_size
        cursor = await db.execute(
            "SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, page_size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total
    finally:
        await db.close()


# ---------- Behavior Tracking Helpers ----------

async def insert_behavior(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata, ensure_ascii=False)
        cursor = await db.execute(
            "INSERT INTO user_behavior (user_id, action, target_type, target_id, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (data["user_id"], data["action"], data.get("target_type"),
             data.get("target_id"), metadata, now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_user_behaviors(user_id: str, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM user_behavior WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ---------- Notification Helpers ----------

async def insert_notification(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata, ensure_ascii=False)
        cursor = await db.execute(
            "INSERT INTO notifications (user_id, type, title, content, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (data["user_id"], data["type"], data["title"],
             data.get("content", ""), metadata, now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_notifications(user_id: str, unread_only: bool = False) -> list[dict]:
    db = await get_db()
    try:
        sql = "SELECT * FROM notifications WHERE user_id = ?"
        params = [user_id]
        if unread_only:
            sql += " AND is_read = 0"
        sql += " ORDER BY created_at DESC LIMIT 50"
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def mark_notification_read(notif_id: int, user_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notif_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def count_unread_notifications(user_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        return (await cursor.fetchone())[0]
    finally:
        await db.close()


# ---------- Skill Lifecycle Helpers ----------

async def insert_lifecycle_event(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            "INSERT INTO skill_lifecycle (product_id, action, actor_id, old_data, new_data, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data["product_id"], data["action"], data.get("actor_id"),
             data.get("old_data"), data.get("new_data"),
             data.get("reason", ""), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_lifecycle_events(product_id: int = None, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        if product_id:
            cursor = await db.execute(
                "SELECT * FROM skill_lifecycle WHERE product_id = ? ORDER BY created_at DESC LIMIT ?",
                (product_id, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM skill_lifecycle ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ---------- Promo Code Helpers ----------

async def fetch_promo_code(code: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM promo_codes WHERE code = ? AND status = 'active'", (code,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def use_promo_code(code_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ? AND used_count < max_uses",
            (code_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def insert_promo_code(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            "INSERT INTO promo_codes (code, coins, max_uses, expires_at, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
            (data["code"], data["coins"], data.get("max_uses", 1),
             data.get("expires_at"), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


# ---------- Price History Helpers ----------

async def insert_price_history(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO price_history
            (product_id, old_price, new_price, pricing_model, demand_score, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["product_id"], data["old_price"], data["new_price"],
             data.get("pricing_model", "fixed"), data.get("demand_score", 0),
             data.get("reason", ""), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_price_history(product_id: int, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM price_history WHERE product_id = ? ORDER BY created_at DESC LIMIT ?",
            (product_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_product_price(product_id: int, new_price: int, demand_score: float = None) -> bool:
    db = await get_db()
    try:
        if demand_score is not None:
            cursor = await db.execute(
                "UPDATE products SET price = ?, demand_score = ? WHERE id = ?",
                (new_price, demand_score, product_id),
            )
        else:
            cursor = await db.execute(
                "UPDATE products SET price = ? WHERE id = ?", (new_price, product_id),
            )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_product_pricing_model(product_id: int, model: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE products SET pricing_model = ? WHERE id = ?", (model, product_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------- Bounty Helpers ----------

async def insert_bounty(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        tags = data.get("tags", [])
        if isinstance(tags, list):
            tags = json.dumps(tags, ensure_ascii=False)
        cursor = await db.execute(
            """INSERT INTO bounties
            (poster_id, title, description, category, tags, budget_min, budget_max,
             deadline, status, skill_type, requirements, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
            (data["poster_id"], data["title"], data["description"],
             data.get("category", "Skill"), tags,
             data["budget_min"], data["budget_max"], data.get("deadline"),
             data.get("skill_type", "prompt"), data.get("requirements", ""),
             now, now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_bounties(
    status: str = None, category: str = None, keyword: str = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("b.status = ?")
            params.append(status)
        if category:
            conditions.append("b.category = ?")
            params.append(category)
        if keyword:
            conditions.append("(b.title LIKE ? OR b.description LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_cursor = await db.execute(f"SELECT COUNT(*) FROM bounties b{where}", params)
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * page_size
        data_cursor = await db.execute(
            f"""SELECT b.*, u.nickname as poster_name, u.avatar as poster_avatar
            FROM bounties b LEFT JOIN users u ON b.poster_id = u.id
            {where} ORDER BY b.created_at DESC LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        )
        rows = await data_cursor.fetchall()
        return [dict(row) for row in rows], total
    finally:
        await db.close()


async def fetch_bounty_by_id(bounty_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT b.*, u.nickname as poster_name, u.avatar as poster_avatar
            FROM bounties b LEFT JOIN users u ON b.poster_id = u.id
            WHERE b.id = ?""",
            (bounty_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_bounty(bounty_id: int, data: dict) -> bool:
    db = await get_db()
    try:
        fields = []
        values = []
        for key in ["title", "description", "category", "tags", "budget_min",
                     "budget_max", "deadline", "status", "selected_developer_id",
                     "final_price", "skill_type", "requirements"]:
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    val = json.dumps(val, ensure_ascii=False)
                fields.append(f"{key} = ?")
                values.append(val)
        if not fields:
            return False
        fields.append("updated_at = datetime('now')")
        values.append(bounty_id)
        cursor = await db.execute(
            f"UPDATE bounties SET {', '.join(fields)} WHERE id = ?", values,
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------- Bounty Application Helpers ----------

async def insert_bounty_application(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO bounty_applications
            (bounty_id, developer_id, proposal, estimated_days, quoted_price, portfolio, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (data["bounty_id"], data["developer_id"], data["proposal"],
             data.get("estimated_days", 7), data["quoted_price"],
             data.get("portfolio", ""), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_bounty_applications(bounty_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT ba.*, u.nickname as developer_name, u.avatar as developer_avatar
            FROM bounty_applications ba LEFT JOIN users u ON ba.developer_id = u.id
            WHERE ba.bounty_id = ? ORDER BY ba.created_at DESC""",
            (bounty_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_bounty_application(app_id: int, status: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE bounty_applications SET status = ? WHERE id = ?", (status, app_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------- Bounty Delivery Helpers ----------

async def insert_bounty_delivery(data: dict) -> int:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO bounty_deliveries
            (bounty_id, developer_id, encrypted_blob, encryption_iv, encryption_salt,
             content_hash, description, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (data["bounty_id"], data["developer_id"],
             data.get("encrypted_blob"), data.get("encryption_iv"),
             data.get("encryption_salt"), data.get("content_hash"),
             data.get("description", ""), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_bounty_deliveries(bounty_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT bd.*, u.nickname as developer_name
            FROM bounty_deliveries bd LEFT JOIN users u ON bd.developer_id = u.id
            WHERE bd.bounty_id = ? ORDER BY bd.created_at DESC""",
            (bounty_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_bounty_delivery(delivery_id: int, data: dict) -> bool:
    db = await get_db()
    try:
        fields = []
        values = []
        for key in ["status", "reviewed_at", "description"]:
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if not fields:
            return False
        values.append(delivery_id)
        cursor = await db.execute(
            f"UPDATE bounty_deliveries SET {', '.join(fields)} WHERE id = ?", values,
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def fetch_user_bounties(user_id: str, role: str = "poster") -> tuple[list[dict], int]:
    db = await get_db()
    try:
        if role == "poster":
            cursor = await db.execute(
                """SELECT b.*, u.nickname as poster_name,
                (SELECT COUNT(*) FROM bounty_applications ba WHERE ba.bounty_id = b.id) as application_count
                FROM bounties b LEFT JOIN users u ON b.poster_id = u.id
                WHERE b.poster_id = ? ORDER BY b.created_at DESC""",
                (user_id,),
            )
        else:
            cursor = await db.execute(
                """SELECT b.*, u.nickname as poster_name, ba.status as my_status, ba.quoted_price as my_quote
                FROM bounty_applications ba
                JOIN bounties b ON ba.bounty_id = b.id
                LEFT JOIN users u ON b.poster_id = u.id
                WHERE ba.developer_id = ? ORDER BY ba.created_at DESC""",
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], len(rows)
    finally:
        await db.close()
