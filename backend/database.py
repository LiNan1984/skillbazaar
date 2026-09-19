from __future__ import annotations

import os
import json
import random
import aiosqlite
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "skillbazaar.db")


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
    await seed_default_activity()
    await init_semantic_search()
    await init_trial_runs_table()


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
            compat TEXT,  -- JSON array of runtime compat strings, NULL if not set
            status TEXT DEFAULT 'active',
            created_at TEXT,
            boost_score INTEGER DEFAULT 0
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

        CREATE TABLE IF NOT EXISTS skill_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            eval_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            eval_version INTEGER DEFAULT 1,
            flags TEXT DEFAULT '[]',
            static_flags TEXT DEFAULT '[]',
            sample_output TEXT,
            reason TEXT,
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

        CREATE TABLE IF NOT EXISTS cron_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            schedule_cron TEXT NOT NULL,
            webhook_secret TEXT NOT NULL,
            result_format TEXT DEFAULT 'json',
            status TEXT DEFAULT 'active',
            last_executed_at TEXT,
            avg_duration_ms INTEGER DEFAULT 0,
            subscriber_count INTEGER DEFAULT 0,
            execution_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS cron_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cron_product_id INTEGER NOT NULL,
            subscriber_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            subscribed_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            monthly_price INTEGER DEFAULT 0,
            webhook_url TEXT,
            api_token TEXT UNIQUE,
            last_result_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cron_product_id) REFERENCES cron_products(id)
        );

        CREATE TABLE IF NOT EXISTS cron_execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cron_product_id INTEGER NOT NULL,
            subscription_id INTEGER,
            payload TEXT,
            status TEXT DEFAULT 'success',
            executed_at TEXT DEFAULT (datetime('now')),
            duration_ms INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cron_webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_log_id INTEGER NOT NULL,
            target_url TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            response_code INTEGER,
            attempts INTEGER DEFAULT 0,
            delivered_at TEXT,
            FOREIGN KEY (execution_log_id) REFERENCES cron_execution_logs(id)
        );

        CREATE TABLE IF NOT EXISTS point_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            balance INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            continuous_checkin_days INTEGER DEFAULT 0,
            last_checkin_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT DEFAULT 'monthly',
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            banner_image TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS activity_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            task_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            task_type TEXT DEFAULT 'monthly',
            action TEXT NOT NULL,
            target_count INTEGER DEFAULT 1,
            reward_points INTEGER DEFAULT 0,
            reward_coins INTEGER DEFAULT 0,
            icon TEXT,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (activity_id) REFERENCES activities(id)
        );

        CREATE TABLE IF NOT EXISTS user_task_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            progress INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            reward_claimed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, task_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (task_id) REFERENCES activity_tasks(id)
        );

        CREATE TABLE IF NOT EXISTS point_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            reason TEXT,
            ref_type TEXT,
            ref_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            system_prompt TEXT DEFAULT '',
            skill_ids TEXT DEFAULT '[]',
            agent_config TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            runs_count INTEGER DEFAULT 0,
            last_run_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            trigger_type TEXT DEFAULT 'manual',
            input_text TEXT DEFAULT '',
            output_text TEXT DEFAULT '',
            tokens_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (agent_id) REFERENCES user_agents(id)
        );

        CREATE TABLE IF NOT EXISTS agent_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL REFERENCES user_agents(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS affiliate_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            code TEXT NOT NULL UNIQUE,
            commission_rate REAL DEFAULT 10.0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS affiliate_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL REFERENCES affiliate_links(id),
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS affiliate_conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL REFERENCES affiliate_links(id),
            buyer_id TEXT NOT NULL REFERENCES users(id),
            transaction_id INTEGER NOT NULL REFERENCES transactions(id),
            commission_amount INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wishlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS product_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            user_id TEXT NOT NULL REFERENCES users(id),
            order_ref TEXT,
            rating INTEGER NOT NULL,
            content TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(product_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            role TEXT NOT NULL,
            content TEXT DEFAULT '',
            card TEXT,
            thread_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id TEXT NOT NULL REFERENCES users(id),
            following_id TEXT NOT NULL REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(follower_id, following_id)
        );

        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            badge TEXT NOT NULL,
            awarded_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, badge)
        );

        CREATE TABLE IF NOT EXISTS sandbox_sessions (
            sandbox_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            language TEXT DEFAULT 'python',
            image TEXT DEFAULT 'python:3.11-slim',
            status TEXT DEFAULT 'running',
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            timeout INTEGER DEFAULT 3600,
            pid INTEGER
        );

        CREATE TABLE IF NOT EXISTS skill_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES products(id),
            version TEXT NOT NULL,
            changelog TEXT DEFAULT '',
            content_preview TEXT,
            skill_asset BLOB,
            skill_asset_hash TEXT,
            is_current INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT REFERENCES users(id),
            UNIQUE(product_id, version)
        );

        CREATE TABLE IF NOT EXISTS product_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            date TEXT NOT NULL,  -- YYYY-MM-DD
            views INTEGER DEFAULT 0,
            unique_visitors INTEGER DEFAULT 0,
            cart_adds INTEGER DEFAULT 0,
            purchases INTEGER DEFAULT 0,
            revenue_cents INTEGER DEFAULT 0,
            search_impressions INTEGER DEFAULT 0,
            search_clicks INTEGER DEFAULT 0,
            chat_mentions INTEGER DEFAULT 0,
            bounce_rate REAL DEFAULT 0,
            avg_view_duration_sec INTEGER DEFAULT 0,
            UNIQUE(product_id, date)
        );

        CREATE TABLE IF NOT EXISTS product_traffic_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            date TEXT NOT NULL,
            source TEXT NOT NULL,  -- search / chat / direct / referral / social
            visits INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            UNIQUE(product_id, date, source)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            product_id INTEGER REFERENCES products(id),
            direction TEXT NOT NULL CHECK(direction IN ('purchase', 'withdraw')),
            channel TEXT NOT NULL DEFAULT 'coins',
            external_txn_id TEXT,
            amount_cents INTEGER NOT NULL,
            coins_amount INTEGER DEFAULT 0,
            exchange_rate REAL DEFAULT 1.0,
            platform_fee_cents INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            gateway_response TEXT DEFAULT '{}',
            failure_reason TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS withdrawal_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            amount_cents INTEGER NOT NULL,
            coins_deducted INTEGER NOT NULL,
            channel TEXT NOT NULL,
            account_info TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            processed_at TEXT,
            admin_note TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            channel TEXT NOT NULL,
            account_ref TEXT NOT NULL,
            account_name TEXT DEFAULT '',
            is_verified INTEGER DEFAULT 0,
            is_default INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            query TEXT DEFAULT '',
            filters TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skill_bundles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            discount_percent REAL DEFAULT 0,
            bundle_price INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bundle_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_id INTEGER NOT NULL REFERENCES skill_bundles(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trial_runs (
            trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            input_text TEXT,
            output_text TEXT,
            error_message TEXT,
            tokens_used INTEGER DEFAULT 0,
            execution_time_ms INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE INDEX IF NOT EXISTS idx_trial_runs_user ON trial_runs(user_id);
        CREATE INDEX IF NOT EXISTS idx_trial_runs_product ON trial_runs(product_id);
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

    # v4: extend user_profiles with display_name, location, website_url, avatar_url, social_links, badges, verified
    profile_migrations = [
        "ALTER TABLE user_profiles ADD COLUMN display_name TEXT",
        "ALTER TABLE user_profiles ADD COLUMN location TEXT",
        "ALTER TABLE user_profiles ADD COLUMN website_url TEXT",
        "ALTER TABLE user_profiles ADD COLUMN avatar_url TEXT",
        "ALTER TABLE user_profiles ADD COLUMN social_links TEXT DEFAULT '[]'",
        "ALTER TABLE user_profiles ADD COLUMN badges TEXT DEFAULT '[]'",
        "ALTER TABLE user_profiles ADD COLUMN verified INTEGER DEFAULT 0",
    ]
    for migration in profile_migrations:
        try:
            await db.execute(migration)
        except Exception:
            pass

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
    try:
        await db.execute("ALTER TABLE users ADD COLUMN sandbox_quota INTEGER DEFAULT 3600")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE products ADD COLUMN boost_score INTEGER DEFAULT 0")
    except Exception:
        pass
    # v4.8 – Eval score badge columns
    try:
        await db.execute("ALTER TABLE products ADD COLUMN eval_score REAL")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE products ADD COLUMN eval_status TEXT DEFAULT 'pending'")
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
    runtime: str | None = None,
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
        if runtime:
            # Filter by compat JSON containing the runtime value
            conditions.append("compat LIKE ?")
            params.append(f'%"{runtime}"%')

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
        # Boost-aware ranking: add boost_score as tiebreaker
        if "boost_score" not in order:
            order = f"{order}, COALESCE(boost_score, 0) DESC"

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
                icon, content_preview, compat, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"], data["description"], data["category"],
                data.get("sub_category"), data["price"], data.get("original_price"),
                data["seller_name"], data.get("seller_avatar"), data.get("tags", "[]"),
                data.get("source_platform"), data.get("github_url"),
                data.get("icon"), data.get("content_preview"),
                data.get("compat"), "active",
                datetime.now().isoformat(),
            ),
        )
        product_id = cursor.lastrowid
        await db.commit()
        # Create initial version 1.0.0 for the product
        await create_skill_version({
            "product_id": str(product_id),
            "changelog": "初始版本",
            "content_preview": data.get("content_preview"),
            "created_by": data.get("seller_name"),
        })
        await db.commit()
        return product_id
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


async def fetch_license_by_id(license_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM licenses WHERE id = ? AND status = 'active'", (license_id,)
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


async def update_product_boost_score(product_id: int, boost_score: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE products SET boost_score = ? WHERE id = ?", (boost_score, product_id),
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


# ---- Cron Subscription Helpers ----

async def insert_cron_product(product_id: int, schedule_cron: str, webhook_secret: str, result_format: str = "json") -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO cron_products (product_id, schedule_cron, webhook_secret, result_format) VALUES (?, ?, ?, ?)",
            (product_id, schedule_cron, webhook_secret, result_format),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_cron_product(product_id: int) -> dict | None:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM cron_products WHERE product_id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def fetch_cron_product_by_id(cron_id: int) -> dict | None:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM cron_products WHERE id = ?", (cron_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def fetch_my_crons(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            """SELECT cp.* FROM cron_products cp
            JOIN products p ON cp.product_id = p.id
            WHERE p.seller_name = (SELECT nickname FROM users WHERE id = ?)
            ORDER BY cp.created_at DESC""",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_cron_product_status(cron_id: int, status: str):
    db = await get_db()
    try:
        await db.execute("UPDATE cron_products SET status = ? WHERE id = ?", (status, cron_id))
        await db.commit()
    finally:
        await db.close()


async def increment_cron_execution(cron_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE cron_products SET execution_count = execution_count + 1, last_executed_at = datetime('now') WHERE id = ?",
            (cron_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def insert_cron_subscription(cron_product_id: int, subscriber_id: str, monthly_price: int, webhook_url: str | None = None) -> dict:
    import secrets as _secrets
    api_token = f"cs_{_secrets.token_hex(16)}"
    from datetime import timedelta
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO cron_subscriptions (cron_product_id, subscriber_id, monthly_price, webhook_url, api_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cron_product_id, subscriber_id, monthly_price, webhook_url, api_token, expires_at),
        )
        await db.commit()
        await db.execute("UPDATE cron_products SET subscriber_count = subscriber_count + 1 WHERE id = ?", (cron_product_id,))
        await db.commit()
        return {"id": cursor.lastrowid, "api_token": api_token, "expires_at": expires_at}
    finally:
        await db.close()


async def fetch_cron_subscription(sub_id: int) -> dict | None:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM cron_subscriptions WHERE id = ?", (sub_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def fetch_subscription_by_token(api_token: str) -> dict | None:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM cron_subscriptions WHERE api_token = ?", (api_token,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    finally:
        await db.close()


async def fetch_active_subscriptions(cron_product_id: int) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM cron_subscriptions WHERE cron_product_id = ? AND status = 'active'",
            (cron_product_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def cancel_cron_subscription(sub_id: int):
    db = await get_db()
    try:
        await db.execute("UPDATE cron_subscriptions SET status = 'cancelled' WHERE id = ?", (sub_id,))
        await db.execute(
            "UPDATE cron_products SET subscriber_count = subscriber_count - 1 WHERE id = (SELECT cron_product_id FROM cron_subscriptions WHERE id = ?)",
            (sub_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def update_subscription_last_result(sub_id: int):
    db = await get_db()
    try:
        await db.execute("UPDATE cron_subscriptions SET last_result_at = datetime('now') WHERE id = ?", (sub_id,))
        await db.commit()
    finally:
        await db.close()


async def insert_execution_log(cron_product_id: int, payload: str, status: str, duration_ms: int = 0, subscription_id: int | None = None) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO cron_execution_logs (cron_product_id, subscription_id, payload, status, duration_ms) VALUES (?, ?, ?, ?, ?)",
            (cron_product_id, subscription_id, payload, status, duration_ms),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_execution_logs(cron_product_id: int, limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM cron_execution_logs WHERE cron_product_id = ? ORDER BY executed_at DESC LIMIT ?",
            (cron_product_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def fetch_subscription_logs(subscription_id: int, limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM cron_execution_logs WHERE subscription_id = ? ORDER BY executed_at DESC LIMIT ?",
            (subscription_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def insert_webhook_delivery(execution_log_id: int, target_url: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO cron_webhook_deliveries (execution_log_id, target_url) VALUES (?, ?)",
            (execution_log_id, target_url),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_webhook_delivery(delivery_id: int, status: str, response_code: int | None = None):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE cron_webhook_deliveries SET status = ?, response_code = ?, delivered_at = datetime('now'), attempts = attempts + 1 WHERE id = ?",
            (status, response_code, delivery_id),
        )
        await db.commit()
    finally:
        await db.close()


# ---- Activity & Points Helpers ----

async def get_or_create_point_account(user_id: str) -> dict:
    db = await get_db()
    try:
        async with db.execute("SELECT * FROM point_accounts WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        cursor = await db.execute("INSERT INTO point_accounts (user_id) VALUES (?)", (user_id,))
        await db.commit()
        return {"id": cursor.lastrowid, "user_id": user_id, "balance": 0, "total_earned": 0, "total_spent": 0, "level": 1, "continuous_checkin_days": 0, "last_checkin_at": None}
    finally:
        await db.close()


async def add_points(user_id: str, amount: int, reason: str, ref_type: str | None = None, ref_id: int | None = None):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE point_accounts SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
            (amount, amount, user_id),
        )
        await db.execute(
            "INSERT INTO point_transactions (user_id, amount, type, reason, ref_type, ref_id) VALUES (?, ?, 'earn', ?, ?, ?)",
            (user_id, amount, reason, ref_type, ref_id),
        )
        await db.commit()
    finally:
        await db.close()


async def spend_points(user_id: str, amount: int, reason: str, ref_type: str | None = None, ref_id: int | None = None) -> bool:
    db = await get_db()
    try:
        async with db.execute("SELECT balance FROM point_accounts WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row or dict(row)["balance"] < amount:
                return False
        await db.execute(
            "UPDATE point_accounts SET balance = balance - ?, total_spent = total_spent + ? WHERE user_id = ?",
            (amount, amount, user_id),
        )
        await db.execute(
            "INSERT INTO point_transactions (user_id, amount, type, reason, ref_type, ref_id) VALUES (?, ?, 'spend', ?, ?, ?)",
            (-amount, user_id, reason, ref_type, ref_id),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def fetch_point_history(user_id: str, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM point_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def insert_activity(title: str, description: str, act_type: str, start_at: str, end_at: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO activities (title, description, type, start_at, end_at) VALUES (?, ?, ?, ?, ?)",
            (title, description, act_type, start_at, end_at),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_active_activities() -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM activities WHERE status = 'active' AND end_at > datetime('now') ORDER BY start_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def insert_activity_task(activity_id: int, task_key: str, name: str, description: str, task_type: str, action: str, target_count: int, reward_points: int, reward_coins: int = 0, icon: str | None = None, sort_order: int = 0) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT OR IGNORE INTO activity_tasks
            (activity_id, task_key, name, description, task_type, action, target_count, reward_points, reward_coins, icon, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (activity_id, task_key, name, description, task_type, action, target_count, reward_points, reward_coins, icon, sort_order),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_activity_tasks(activity_id: int) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM activity_tasks WHERE activity_id = ? ORDER BY sort_order", (activity_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def fetch_or_create_task_progress(user_id: str, task_id: int) -> dict:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM user_task_progress WHERE user_id = ? AND task_id = ?",
            (user_id, task_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
        cursor = await db.execute(
            "INSERT INTO user_task_progress (user_id, task_id) VALUES (?, ?)",
            (user_id, task_id),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "user_id": user_id, "task_id": task_id, "progress": 0, "completed": 0, "reward_claimed": 0}
    finally:
        await db.close()


async def increment_task_progress(user_id: str, action: str):
    """Auto-increment progress for all active tasks matching the action."""
    activities = await fetch_active_activities()
    if not activities:
        return
    db = await get_db()
    try:
        for act in activities:
            async with db.execute(
                "SELECT * FROM activity_tasks WHERE activity_id = ? AND action = ?",
                (act["id"], action),
            ) as cursor:
                tasks = await cursor.fetchall()
            for t in tasks:
                t = dict(t)
                async with db.execute(
                    "SELECT * FROM user_task_progress WHERE user_id = ? AND task_id = ?",
                    (user_id, t["id"]),
                ) as cursor:
                    row = await cursor.fetchone()
                if not row:
                    await db.execute(
                        "INSERT INTO user_task_progress (user_id, task_id, progress, completed) VALUES (?, ?, 1, ?)",
                        (user_id, t["id"], 1 if 1 >= t["target_count"] else 0),
                    )
                else:
                    prog = dict(row)
                    new_progress = prog["progress"] + 1
                    completed = 1 if new_progress >= t["target_count"] else 0
                    await db.execute(
                        "UPDATE user_task_progress SET progress = ?, completed = ? WHERE user_id = ? AND task_id = ?",
                        (new_progress, completed, user_id, t["id"]),
                    )
        await db.commit()
    finally:
        await db.close()


async def claim_task_reward(user_id: str, task_id: int) -> dict | None:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM user_task_progress WHERE user_id = ? AND task_id = ?",
            (user_id, task_id),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        prog = dict(row)
        if not prog["completed"] or prog["reward_claimed"]:
            return None
        async with db.execute("SELECT * FROM activity_tasks WHERE id = ?", (task_id,)) as cursor:
            trow = await cursor.fetchone()
        if not trow:
            return None
        task = dict(trow)
        await db.execute("UPDATE user_task_progress SET reward_claimed = 1 WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        await db.commit()
        if task["reward_points"] > 0:
            await add_points(user_id, task["reward_points"], "task_reward", "task", task_id)
        if task["reward_coins"] > 0:
            await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (task["reward_coins"], user_id))
            await db.commit()
        return {"points": task["reward_points"], "coins": task["reward_coins"]}
    finally:
        await db.close()


async def do_checkin(user_id: str) -> dict:
    """Daily check-in. Returns points earned and streak info."""
    from datetime import timedelta, timezone
    tz_cn = timezone(timedelta(hours=8))
    account = await get_or_create_point_account(user_id)
    last = account.get("last_checkin_at")
    now = datetime.now(tz_cn)
    today = now.strftime("%Y-%m-%d")

    if last and last.startswith(today):
        return {"ok": False, "message": "今天已经签到过了", "streak": account["continuous_checkin_days"]}

    streak = account["continuous_checkin_days"]
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=tz_cn)
            if (now.date() - last_dt.date()).days == 1:
                streak += 1
            else:
                streak = 1
        except Exception:
            streak = 1
    else:
        streak = 1

    bonus = 50 if streak >= 7 and streak % 7 == 0 else 0
    points = 10 + bonus

    db = await get_db()
    try:
        await db.execute(
            "UPDATE point_accounts SET last_checkin_at = ?, continuous_checkin_days = ? WHERE user_id = ?",
            (now.isoformat(), streak, user_id),
        )
        await db.commit()
    finally:
        await db.close()
    await add_points(user_id, points, "checkin")
    await increment_task_progress(user_id, "checkin")
    return {"ok": True, "points": points, "streak": streak, "bonus": bonus}


async def update_user_level(user_id: str):
    account = await get_or_create_point_account(user_id)
    total = account["total_earned"]
    level = 1
    if total >= 15000:
        level = 5
    elif total >= 5000:
        level = 4
    elif total >= 2000:
        level = 3
    elif total >= 500:
        level = 2
    db = await get_db()
    try:
        await db.execute("UPDATE point_accounts SET level = ? WHERE user_id = ?", (level, user_id))
        await db.commit()
    finally:
        await db.close()


async def seed_default_activity():
    """Create default monthly activity with tasks if none exists."""
    activities = await fetch_active_activities()
    if activities:
        return
    now = datetime.utcnow()
    from datetime import timedelta
    act_id = await insert_activity(
        title="五月挑战赛",
        description="完成每月任务赢取积分和金币奖励！",
        act_type="monthly",
        start_at=now.isoformat(),
        end_at=(now + timedelta(days=30)).isoformat(),
    )
    tasks = [
        ("publish_3_skills", "发布3个Skill", "发布3个Skill获得奖励", "monthly", "publish", 3, 500, 200, "📦"),
        ("complete_2_bounties", "完成2个悬赏", "完成2个悬赏任务获得奖励", "monthly", "deliver_bounty", 2, 800, 500, "🎯"),
        ("subscribe_5_crons", "订阅5个Cron", "订阅5个定时任务获得奖励", "monthly", "subscribe_cron", 5, 300, 100, "⏰"),
        ("receive_5star", "获得5星好评", "获得1个5星好评", "monthly", "receive_5star", 1, 600, 300, "⭐"),
        ("publish_1_cron", "发布1个Cron", "发布1个定时任务", "monthly", "publish_cron", 1, 400, 150, "🔄"),
        ("checkin_7", "连续签到7天", "连续签到7天", "monthly", "checkin", 7, 200, 100, "📅"),
        ("spend_1000", "消费1000金币", "累计消费1000金币", "monthly", "spend", 1000, 500, 200, "💰"),
    ]
    for i, (key, name, desc, ttype, action, target, pts, coins, icon) in enumerate(tasks):
        await insert_activity_task(act_id, key, name, desc, ttype, action, target, pts, coins, icon, i)


async def fetch_points_leaderboard(limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT pa.*, u.nickname FROM point_accounts pa JOIN users u ON pa.user_id = u.id ORDER BY pa.total_earned DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def fetch_user_cron_subscriptions(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            """SELECT cs.*, cp.schedule_cron, cp.result_format, cp.execution_count,
               cp.status as cron_status, p.name as product_name, p.icon as product_icon
            FROM cron_subscriptions cs
            JOIN cron_products cp ON cs.cron_product_id = cp.id
            JOIN products p ON cp.product_id = p.id
            WHERE cs.subscriber_id = ?
            ORDER BY cs.subscribed_at DESC""",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


# ---- User Agent Helpers ----

async def insert_user_agent(user_id: str, name: str, description: str, system_prompt: str, skill_ids: list, agent_config: dict | None = None) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO user_agents (user_id, name, description, system_prompt, skill_ids, agent_config) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, description, system_prompt, json.dumps(skill_ids), json.dumps(agent_config or {})),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_user_agents(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM user_agents WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


async def fetch_user_agent(agent_id: int, user_id: str | None = None) -> dict | None:
    db = await get_db()
    try:
        if user_id:
            async with db.execute("SELECT * FROM user_agents WHERE id = ? AND user_id = ?", (agent_id, user_id)) as cursor:
                row = await cursor.fetchone()
        else:
            async with db.execute("SELECT * FROM user_agents WHERE id = ?", (agent_id,)) as cursor:
                row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_user_agent(agent_id: int, **fields):
    db = await get_db()
    try:
        sets = []
        vals = []
        for k, v in fields.items():
            if k == "skill_ids" and isinstance(v, list):
                v = json.dumps(v)
            if k == "agent_config" and isinstance(v, dict):
                v = json.dumps(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(agent_id)
        await db.execute(f"UPDATE user_agents SET {', '.join(sets)} WHERE id = ?", vals)
        await db.commit()
    finally:
        await db.close()


async def delete_user_agent(agent_id: int, user_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM user_agents WHERE id = ? AND user_id = ?", (agent_id, user_id))
        await db.execute("DELETE FROM agent_runs WHERE agent_id = ?", (agent_id,))
        await db.commit()
    finally:
        await db.close()


async def increment_agent_runs(agent_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE user_agents SET runs_count = runs_count + 1, last_run_at = datetime('now') WHERE id = ?",
            (agent_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def insert_agent_run(agent_id: int, trigger_type: str, input_text: str, output_text: str, tokens_used: int = 0, status: str = "success") -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO agent_runs (agent_id, trigger_type, input_text, output_text, tokens_used, status) VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, trigger_type, input_text, output_text, tokens_used, status),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_agent_runs(agent_id: int, limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM agent_runs WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    finally:
        await db.close()


# ---- Product Review Helpers ----

async def user_has_purchased_product(user_id: str, product_id: int) -> bool:
    """Eligible to review: completed purchase OR an active license."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT 1 FROM transactions
            WHERE buyer_id = ? AND product_id = ? AND type = 'buy' AND status = 'completed'
            UNION ALL
            SELECT 1 FROM licenses
            WHERE user_id = ? AND product_id = ? AND status = 'active'
            LIMIT 1
            """,
            (user_id, product_id, user_id, product_id),
        )
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def fetch_product_review(product_id: int, user_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM product_reviews WHERE product_id = ? AND user_id = ?",
            (product_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def insert_product_review(data: dict) -> int:
    """Insert a review and recompute products.rating in one transaction."""
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """
            INSERT INTO product_reviews (product_id, user_id, order_ref, rating, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (data["product_id"], data["user_id"], data.get("order_ref"),
             data["rating"], data.get("content", ""), now),
        )
        review_id = cursor.lastrowid
        await db.execute(
            """
            UPDATE products
            SET rating = (SELECT ROUND(AVG(rating), 2) FROM product_reviews WHERE product_id = ?)
            WHERE id = ?
            """,
            (data["product_id"], data["product_id"]),
        )
        await db.commit()
        return review_id
    finally:
        await db.close()


async def fetch_product_reviews(product_id: int, page: int = 1, page_size: int = 10) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        count_cursor = await db.execute(
            "SELECT COUNT(*) FROM product_reviews WHERE product_id = ?",
            (product_id,),
        )
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            """
            SELECT r.*, u.nickname, u.avatar
            FROM product_reviews r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE r.product_id = ?
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ? OFFSET ?
            """,
            (product_id, page_size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total
    finally:
        await db.close()


async def fetch_review_summary(product_id: int) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS total, COALESCE(ROUND(AVG(rating), 2), 0) AS avg_rating "
            "FROM product_reviews WHERE product_id = ?",
            (product_id,),
        )
        row = await cursor.fetchone()
        return {"total": row[0], "avg_rating": row[1]}
    finally:
        await db.close()


async def fetch_user_by_name(name: str) -> dict | None:
    """Resolve a user by username or nickname (products only carry seller_name)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ? OR nickname = ? LIMIT 1",
            (name, name),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ---- Chat Message Helpers ----

async def insert_chat_message(data: dict):
    db = await get_db()
    try:
        card = data.get("card")
        if card is not None and not isinstance(card, str):
            card = json.dumps(card, ensure_ascii=False)
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """
            INSERT INTO chat_messages (user_id, role, content, card, thread_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (data["user_id"], data["role"], data.get("content", ""),
             card, data.get("thread_id"), now),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def fetch_chat_messages(user_id: str, limit: int = 20) -> list[dict]:
    """Return the latest `limit` messages for a user, ordered oldest -> newest."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT * FROM (
                SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def clear_chat_messages(user_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


# ---------- Eval Report Helpers ----------

async def fetch_eval_report(product_id: int) -> dict | None:
    """Get the latest eval report for a product."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM skill_evaluations
            WHERE product_id = ?
            ORDER BY id DESC LIMIT 1""",
            (product_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def upsert_eval_report(data: dict) -> int:
    """Insert a new eval report row (appends, version bumps in caller)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            INSERT INTO skill_evaluations (
                product_id, eval_score, status, eval_version,
                flags, static_flags, sample_output, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["product_id"],
                data.get("eval_score", 0),
                data.get("status", "pending"),
                data.get("eval_version", 1),
                json.dumps(data.get("flags", [])),
                json.dumps(data.get("static_flags", [])),
                data.get("sample_output", ""),
                data.get("reason"),
            ),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


# ---------- Compat Helpers ----------

async def fetch_products_by_runtime(runtime: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    """Filter products by compat runtime(s). Returns (products, total_count).

    Accepts single runtime or comma-separated values (e.g. "claude-code" or
    "claude-code,codex").  Each runtime is matched against the compat JSON
    column using LIKE patterns that handle both quoted and bare values.
    """
    db = await get_db()
    try:
        runtimes = [r.strip() for r in runtime.split(",") if r.strip()]
        if not runtimes:
            # No valid runtimes → return empty
            return [], 0

        # Build WHERE clause: (compat LIKE ? OR compat LIKE ? ...) for each runtime
        like_patterns = []
        params = []
        for rt in runtimes:
            like_patterns.append(
                "(compat LIKE ? OR compat LIKE ? OR compat LIKE ?)"
            )
            params.extend([f'%"{rt}"%', f'%"{rt}"%', f'%{rt}%'])

        where_clause = " OR ".join(like_patterns)

        # Count total matching
        count_cursor = await db.execute(
            f"""SELECT COUNT(*) as cnt FROM products
            WHERE status = 'active'
            AND ({where_clause})""",
            params,
        )
        count_row = await count_cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        # Fetch page
        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"""SELECT * FROM products
            WHERE status = 'active'
            AND ({where_clause})
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (*params, page_size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total
    finally:
        await db.close()


# ---------- User Profiles v4 Helpers ----------


async def get_or_create_user_profile(user_id: str, username: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        # Create with defaults
        now = datetime.now().isoformat()
        await db.execute(
            """INSERT INTO user_profiles (user_id, industry, interests, latitude, longitude,
               city, language, bio, preferred_categories, preferred_price_range,
               total_spent, total_earned, total_purchases, total_sales,
               last_active_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, "", "[]", None, None, "", "zh", "", "[]", "[]",
             0, 0, 0, 0, now, now, now),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def get_public_profile(username: str, viewer_id: str | None = None) -> dict | None:
    db = await get_db()
    try:
        # Look up user by username
        cursor = await db.execute("SELECT id, username, nickname, avatar, role FROM users WHERE username = ?", (username,))
        user_row = await cursor.fetchone()
        if not user_row:
            return None
        user = dict(user_row)

        # Get profile
        cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],))
        profile_row = await cursor.fetchone()
        if not profile_row:
            # Create default profile
            await get_or_create_user_profile(user["id"], user["username"])
            cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user["id"],))
            profile_row = await cursor.fetchone()
        profile = dict(profile_row)

        # Check if viewer is following
        is_following = False
        if viewer_id and viewer_id != user["id"]:
            cursor = await db.execute(
                "SELECT id FROM user_follows WHERE follower_id = ? AND following_id = ?",
                (viewer_id, user["id"]),
            )
            is_following = (await cursor.fetchone()) is not None

        # Build public profile dict
        public = {
            "id": user["id"],
            "username": user["username"],
            "nickname": user["nickname"],
            "avatar": user["avatar"],
            "role": user["role"],
            "display_name": profile.get("display_name") or user["nickname"],
            "bio": profile.get("bio", ""),
            "location": profile.get("location"),
            "website_url": profile.get("website_url"),
            "avatar_url": profile.get("avatar_url"),
            "social_links": json.loads(profile["social_links"]) if profile.get("social_links") else [],
            "badges": json.loads(profile["badges"]) if profile.get("badges") else [],
            "verified": bool(profile.get("verified", 0)),
            "industry": profile.get("industry"),
            "interests": json.loads(profile["interests"]) if profile.get("interests") else [],
            "city": profile.get("city"),
            "followers_count": await _get_followers_count(db, user["id"]),
            "following_count": await _get_following_count(db, user["id"]),
            "is_following": is_following,
        }
        return public
    finally:
        await db.close()


async def update_user_profile_extended(user_id: str, data: dict) -> dict:
    db = await get_db()
    try:
        # Ensure profile exists
        await get_or_create_user_profile(user_id, "")

        # Build SET clause dynamically
        allowed = ["display_name", "location", "website_url", "avatar_url", "social_links", "bio", "industry", "interests", "city", "language"]
        updates = {k: v for k, v in data.items() if k in allowed}
        if not updates:
            return {}

        # JSON serialize list/dict fields
        for field in ["social_links", "interests"]:
            if field in updates and isinstance(updates[field], (list, dict)):
                updates[field] = json.dumps(updates[field], ensure_ascii=False)

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values())
        values.append(datetime.now().isoformat())
        values.append(user_id)

        await db.execute(
            f"UPDATE user_profiles SET {set_clause}, updated_at = ? WHERE user_id = ?",
            values,
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else {}
    finally:
        await db.close()


async def follow_user(follower_id: str, following_id: str) -> bool:
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO user_follows (follower_id, following_id, created_at) VALUES (?, ?, ?)",
            (follower_id, following_id, now),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def unfollow_user(follower_id: str, following_id: str) -> bool:
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM user_follows WHERE follower_id = ? AND following_id = ?",
            (follower_id, following_id),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def get_followers(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT uf.id, uf.follower_id, u.username, u.nickname, u.avatar, uf.created_at
               FROM user_follows uf
               JOIN users u ON uf.follower_id = u.id
               WHERE uf.following_id = ?
               ORDER BY uf.created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, (page - 1) * page_size),
        )
        rows = await cursor.fetchall()

        count_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM user_follows WHERE following_id = ?",
            (user_id,),
        )
        count_row = await count_cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        return [dict(r) for r in rows], total
    finally:
        await db.close()


async def get_following(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT uf.id, uf.following_id, u.username, u.nickname, u.avatar, uf.created_at
               FROM user_follows uf
               JOIN users u ON uf.following_id = u.id
               WHERE uf.follower_id = ?
               ORDER BY uf.created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, (page - 1) * page_size),
        )
        rows = await cursor.fetchall()

        count_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM user_follows WHERE follower_id = ?",
            (user_id,),
        )
        count_row = await count_cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        return [dict(r) for r in rows], total
    finally:
        await db.close()


async def check_following(follower_id: str, following_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM user_follows WHERE follower_id = ? AND following_id = ?",
            (follower_id, following_id),
        )
        return (await cursor.fetchone()) is not None
    finally:
        await db.close()


async def _get_followers_count(db: aiosqlite.Connection, user_id: str) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM user_follows WHERE following_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    return row["cnt"] if row else 0


async def _get_following_count(db: aiosqlite.Connection, user_id: str) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM user_follows WHERE follower_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    return row["cnt"] if row else 0


async def get_user_products(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM products WHERE seller_name = (SELECT nickname FROM users WHERE id = ?) AND status = 'active'",
            (user_id,),
        )
        count_row = await cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        offset = (page - 1) * page_size
        cursor = await db.execute(
            """SELECT id, name, description, category, sub_category, price, original_price,
                      seller_name, seller_avatar, rating, downloads, sales, tags,
                      source_platform, github_url, icon, content_preview, status, created_at
               FROM products
               WHERE seller_name = (SELECT nickname FROM users WHERE id = ?) AND status = 'active'
               ORDER BY id DESC LIMIT ? OFFSET ?""",
            (user_id, page_size, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total
    finally:
        await db.close()


async def add_user_achievement(user_id: str, badge: str) -> bool:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO user_achievements (user_id, badge) VALUES (?, ?)",
            (user_id, badge),
        )
        await db.commit()
        return True
    finally:
        await db.close()


# ---------- Skill Version Helpers ----------


async def create_skill_version(data: dict) -> dict:
    """Create a new version for a product.

    Automatically computes the next version number (1.0.0, 2.0.0, ...),
    sets is_current=1 on the new version, and unsets previous versions.
    """
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        # Count existing versions to determine next version number
        cursor = await db.execute(
            "SELECT COUNT(*) FROM skill_versions WHERE product_id = ?",
            (data["product_id"],),
        )
        count = (await cursor.fetchone())[0]
        next_version = f"{(count + 1)}.0.0"

        # Unset all previous is_current flags
        await db.execute(
            "UPDATE skill_versions SET is_current = 0 WHERE product_id = ?",
            (data["product_id"],),
        )

        # Insert new version as current
        cursor = await db.execute(
            """INSERT INTO skill_versions
            (product_id, version, changelog, content_preview, skill_asset,
             skill_asset_hash, is_current, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                data["product_id"],
                next_version,
                data.get("changelog", ""),
                data.get("content_preview"),
                data.get("skill_asset"),
                data.get("skill_asset_hash"),
                data.get("created_by"),
                now,
            ),
        )
        await db.commit()
        version_id = cursor.lastrowid
        # Fetch and return the inserted row
        cursor = await db.execute(
            "SELECT * FROM skill_versions WHERE id = ?", (version_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_skill_versions(product_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM skill_versions WHERE product_id = ? ORDER BY id ASC",
            (product_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_skill_version(product_id: str, version: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM skill_versions WHERE product_id = ? AND version = ?",
            (product_id, version),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_version_changelog(product_id: str, version: str, changelog: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE skill_versions SET changelog = ? WHERE product_id = ? AND version = ?",
            (changelog, product_id, version),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
        cursor = await db.execute(
            "SELECT * FROM skill_versions WHERE product_id = ? AND version = ?",
            (product_id, version),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def rollback_to_version(product_id: str, target_version: str, user_id: str) -> dict | None:
    """Rollback: create a new version that copies the content of the target version."""
    db = await get_db()
    try:
        # Fetch the target version
        target = await get_skill_version(product_id, target_version)
        if target is None:
            return None

        now = datetime.now().isoformat()

        # Unset all previous is_current flags
        await db.execute(
            "UPDATE skill_versions SET is_current = 0 WHERE product_id = ?",
            (product_id,),
        )

        # Count existing to get next version number
        cursor = await db.execute(
            "SELECT COUNT(*) FROM skill_versions WHERE product_id = ?",
            (product_id,),
        )
        count = (await cursor.fetchone())[0]
        next_version = f"{(count + 1)}.0.0"

        # Build rollback changelog
        base_changelog = target.get("changelog", "")
        rollback_note = f"Rolled back to {target_version}"
        if base_changelog:
            changelog = f"{rollback_note}: {base_changelog}"
        else:
            changelog = rollback_note

        # Insert new version with content from target
        cursor = await db.execute(
            """INSERT INTO skill_versions
            (product_id, version, changelog, content_preview, skill_asset,
             skill_asset_hash, is_current, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                product_id,
                next_version,
                changelog,
                target.get("content_preview"),
                target.get("skill_asset"),
                target.get("skill_asset_hash"),
                user_id,
                now,
            ),
        )
        await db.commit()
        version_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT * FROM skill_versions WHERE id = ?", (version_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_current_version(product_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM skill_versions WHERE product_id = ? AND is_current = 1",
            (product_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# ---------- Analytics Helpers ----------

async def record_product_view(product_id: int, user_id: str | None, source: str, session_id: str | None) -> None:
    """Record a product view for analytics."""
    db = await get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        # Upsert: increment views, track unique visitor if first view today
        await db.execute("""
            INSERT INTO product_analytics (product_id, date, views, unique_visitors)
            VALUES (?, ?, 1, 1)
            ON CONFLICT(product_id, date) DO UPDATE SET
                views = views + 1,
                unique_visitors = unique_visitors + CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM product_analytics
                        WHERE product_id = ? AND date = ?
                        AND id != excluded.id
                        AND (unique_visitors > 0 OR views > 1)
                    ) THEN 1 ELSE 0 END
        """, (product_id, today, product_id, today))

        # Track traffic source
        await db.execute("""
            INSERT INTO product_traffic_sources (product_id, date, source, visits)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(product_id, date, source) DO UPDATE SET
                visits = visits + 1
        """, (product_id, today, source))

        await db.commit()
    finally:
        await db.close()


async def increment_search_impression(product_id: int) -> None:
    """Track a search impression for a product."""
    db = await get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        await db.execute("""
            INSERT INTO product_analytics (product_id, date, search_impressions)
            VALUES (?, ?, 1)
            ON CONFLICT(product_id, date) DO UPDATE SET
                search_impressions = search_impressions + 1
        """, (product_id, today))
        await db.commit()
    finally:
        await db.close()


async def increment_search_click(product_id: int) -> None:
    """Track a search click for a product."""
    db = await get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        await db.execute("""
            INSERT INTO product_analytics (product_id, date, search_clicks)
            VALUES (?, ?, 1)
            ON CONFLICT(product_id, date) DO UPDATE SET
                search_clicks = search_clicks + 1
        """, (product_id, today))
        await db.commit()
    finally:
        await db.close()


async def increment_purchase(product_id: int, amount_cents: int) -> None:
    """Track a purchase for a product."""
    db = await get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        await db.execute("""
            INSERT INTO product_analytics (product_id, date, purchases, revenue_cents)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(product_id, date) DO UPDATE SET
                purchases = purchases + 1,
                revenue_cents = revenue_cents + ?
        """, (product_id, today, amount_cents, amount_cents))
        await db.commit()
    finally:
        await db.close()


async def get_product_analytics_by_date(product_id: int, start_date: str, end_date: str) -> list[dict]:
    """Get daily analytics for a product within a date range."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT date, views, unique_visitors, cart_adds, purchases,
                   revenue_cents, search_impressions, search_clicks,
                   chat_mentions, bounce_rate, avg_view_duration_sec
            FROM product_analytics
            WHERE product_id = ? AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (product_id, start_date, end_date))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_traffic_sources(product_id: int, start_date: str, end_date: str) -> list[dict]:
    """Get traffic source breakdown for a product."""
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT source, SUM(visits) as visits, SUM(conversions) as conversions
            FROM product_traffic_sources
            WHERE product_id = ? AND date BETWEEN ? AND ?
            GROUP BY source
            ORDER BY visits DESC
        """, (product_id, start_date, end_date))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_top_products_for_seller(seller_name: str, metric: str, limit: int) -> list[dict]:
    """Get top performing products for a seller by metric."""
    db = await get_db()
    try:
        # Map metric to column
        metric_map = {
            "views": "COALESCE(SUM(a.views), 0)",
            "purchases": "COALESCE(SUM(a.purchases), 0)",
            "revenue": "COALESCE(SUM(a.revenue_cents), 0)",
        }
        order_col = metric_map.get(metric, "COALESCE(SUM(a.revenue_cents), 0)")

        cursor = await db.execute(f"""
            SELECT p.id, p.name, p.price,
                   COALESCE(SUM(a.views), 0) as views,
                   COALESCE(SUM(a.purchases), 0) as purchases,
                   COALESCE(SUM(a.revenue_cents), 0) as revenue_cents
            FROM products p
            LEFT JOIN product_analytics a ON p.id = a.product_id
            WHERE p.seller_name = ?
            GROUP BY p.id, p.name, p.price
            ORDER BY {order_col} DESC
            LIMIT ?
        """, (seller_name, limit))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_seller_products(seller_name: str) -> list[dict]:
    """Get all products for a seller."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, price FROM products WHERE seller_name = ?",
            (seller_name,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ---------- Payment Functions ----------

async def create_payment_order(user_id: str, product_id: int, channel: str, amount_cents: int) -> dict:
    """Create a payment order."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO payments (user_id, product_id, direction, channel, amount_cents, status)
               VALUES (?, ?, 'purchase', ?, ?, 'pending')""",
            (user_id, product_id, channel, amount_cents)
        )
        await db.commit()
        payment_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        row = await cursor.fetchone()
        result = dict(row)
        # Parse gateway_response from JSON string to dict
        if isinstance(result.get("gateway_response"), str):
            try:
                result["gateway_response"] = json.loads(result["gateway_response"])
            except (json.JSONDecodeError, TypeError):
                result["gateway_response"] = {}
        return result
    finally:
        await db.close()


async def get_payment_order(payment_id: int) -> dict | None:
    """Get a payment order by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            # Parse gateway_response from JSON string to dict
            if isinstance(result.get("gateway_response"), str):
                try:
                    result["gateway_response"] = json.loads(result["gateway_response"])
                except (json.JSONDecodeError, TypeError):
                    result["gateway_response"] = {}
            return result
        return None
    finally:
        await db.close()


async def update_payment_status(payment_id: int, status: str, external_txn_id: str = None, gateway_response: dict = None) -> dict | None:
    """Update payment order status."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """UPDATE payments
               SET status = ?, external_txn_id = COALESCE(?, external_txn_id),
                   gateway_response = COALESCE(?, gateway_response),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (status, external_txn_id, str(gateway_response) if gateway_response else None, payment_id)
        )
        await db.commit()
        if cursor.rowcount > 0:
            cursor = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
            row = await cursor.fetchone()
            result = dict(row)
            # Parse gateway_response from JSON string to dict
            if isinstance(result.get("gateway_response"), str):
                try:
                    result["gateway_response"] = json.loads(result["gateway_response"])
                except (json.JSONDecodeError, TypeError):
                    result["gateway_response"] = {}
            return result
        return None
    finally:
        await db.close()


async def get_payment_history(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    """Get user's payment history."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM payments WHERE user_id = ?",
            (user_id,)
        )
        total = (await cursor.fetchone())["total"]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            """SELECT * FROM payments WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (user_id, page_size, offset)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows], total
    finally:
        await db.close()


async def create_withdrawal(user_id: str, amount_cents: int, coins_deducted: int, channel: str, account_info: dict) -> dict:
    """Create a withdrawal request."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO withdrawal_records (user_id, amount_cents, coins_deducted, channel, account_info, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (user_id, amount_cents, coins_deducted, channel, json.dumps(account_info))
        )
        await db.commit()
        withdrawal_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM withdrawal_records WHERE id = ?", (withdrawal_id,))
        row = await cursor.fetchone()
        result = dict(row)
        # Parse account_info from JSON string to dict
        if isinstance(result.get("account_info"), str):
            try:
                result["account_info"] = json.loads(result["account_info"])
            except (json.JSONDecodeError, TypeError):
                result["account_info"] = {}
        return result
    finally:
        await db.close()


async def get_earnings_summary(user_id: str) -> dict:
    """Get earnings summary for a user."""
    db = await get_db()
    try:
        # Total earnings (completed purchases where user is seller)
        cursor = await db.execute(
            """SELECT COALESCE(SUM(amount_cents), 0) as total
               FROM payments
               WHERE product_id IN (SELECT id FROM products WHERE seller_name = (
                   SELECT username FROM users WHERE id = ?
               )) AND direction = 'purchase' AND status = 'completed'""",
            (user_id,)
        )
        total_earnings = (await cursor.fetchone())["total"]

        # Withdrawn amount
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) as total FROM withdrawal_records WHERE user_id = ? AND status = 'completed'",
            (user_id,)
        )
        withdrawn = (await cursor.fetchone())["total"]

        # Pending withdrawal
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) as total FROM withdrawal_records WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        pending = (await cursor.fetchone())["total"]

        return {
            "total_earnings_cents": total_earnings,
            "available_balance_cents": total_earnings - withdrawn - pending,
            "withdrawn_cents": withdrawn,
            "pending_withdrawal_cents": pending,
        }
    finally:
        await db.close()


async def create_payment_method(user_id: str, channel: str, account_ref: str, account_name: str = "") -> dict:
    """Create a payment method."""
    db = await get_db()
    try:
        # Check if this is the first method (make it default)
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM payment_methods WHERE user_id = ?",
            (user_id,)
        )
        is_first = (await cursor.fetchone())["count"] == 0

        cursor = await db.execute(
            """INSERT INTO payment_methods (user_id, channel, account_ref, account_name, is_default)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, channel, account_ref, account_name, 1 if is_first else 0)
        )
        await db.commit()
        method_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM payment_methods WHERE id = ?", (method_id,))
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def get_payment_methods(user_id: str) -> list[dict]:
    """Get user's payment methods."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM payment_methods WHERE user_id = ?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def delete_payment_method(method_id: int, user_id: str) -> bool:
    """Delete a payment method."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM payment_methods WHERE id = ? AND user_id = ?",
            (method_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ============================================================
# v4 Database Functions
# ============================================================


async def search_products(query: str = "", category: str = None,
                          min_price: int = None, max_price: int = None,
                          min_eval_score: float = None,
                          sort_by: str = "relevance",
                          page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    """Full-text search across products with optional filters."""
    db = await get_db()
    try:
        offset = (page - 1) * page_size
        where = ["p.status = 'active'"]
        params = []
        if query:
            where.append("(p.name LIKE ? OR p.description LIKE ? OR p.content_preview LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])
        if category:
            where.append("p.category = ?")
            params.append(category)
        if min_price is not None:
            where.append("p.price >= ?")
            params.append(min_price)
        if max_price is not None:
            where.append("p.price <= ?")
            params.append(max_price)
        if min_eval_score is not None:
            where.append("p.eval_score >= ?")
            params.append(min_eval_score)

        allowed_sorts = {
            "downloads": "p.downloads DESC",
            "rating": "p.rating DESC",
            "price_asc": "p.price ASC",
            "price_desc": "p.price DESC",
            "sales": "p.sales DESC",
            "newest": "p.created_at DESC",
            "eval_score": "p.eval_score DESC",
            "relevance": "p.boost_score DESC, p.created_at DESC",
        }
        order = allowed_sorts.get(sort_by, "p.boost_score DESC, p.created_at DESC")
        # Boost-aware tiebreaker for non-eval sorts
        if "boost_score" not in order:
            order = f"{order}, COALESCE(p.boost_score, 0) DESC"

        sql = f"SELECT p.* FROM products p WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?"
        cursor = await db.execute(sql, params + [page_size, offset])
        rows = await cursor.fetchall()
        results = [dict(r) for r in rows]

        count_sql = f"SELECT COUNT(*) FROM products p WHERE {' AND '.join(where)}"
        cursor = await db.execute(count_sql, params)
        total = (await cursor.fetchone())[0]
        return results, total
    finally:
        await db.close()


async def save_search(user_id: str, name: str, query: str, filters: dict) -> int:
    """Save a search for later re-use."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO saved_searches (user_id, name, query, filters) VALUES (?, ?, ?, ?)",
            (user_id, name, query, json.dumps(filters) if filters else "{}")
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_saved_searches(user_id: str) -> list[dict]:
    """Get all saved searches for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM saved_searches WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["filters"] = json.loads(row.get("filters") or "{}")
            result.append(row)
        return result
    finally:
        await db.close()


async def fetch_saved_search(search_id: int, user_id: str) -> dict | None:
    """Get a specific saved search."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM saved_searches WHERE id = ? AND user_id = ?",
            (search_id, user_id)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["filters"] = json.loads(result.get("filters") or "{}")
        return result
    finally:
        await db.close()


async def delete_saved_search(search_id: int, user_id: str) -> bool:
    """Delete a saved search."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM saved_searches WHERE id = ? AND user_id = ?",
            (search_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_seller_products(seller_name: str) -> list[dict]:
    """Get all products by a seller (by seller_name/username)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM products WHERE seller_name = ? ORDER BY created_at DESC",
            (seller_name,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def increment_product_view(product_id: int) -> None:
    """Increment view count for a product."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE products SET views = COALESCE(views, 0) + 1 WHERE id = ?",
            (product_id,)
        )
        await db.commit()
    finally:
        await db.close()


# ---- Bundle Functions ----


async def create_bundle(seller_id: str, name: str, description: str,
                        discount_percent: float, bundle_price: int) -> dict:
    """Create a new skill bundle."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO skill_bundles (seller_id, name, description, discount_percent, bundle_price)
               VALUES (?, ?, ?, ?, ?)""",
            (seller_id, name, description, discount_percent, bundle_price)
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "seller_id": seller_id,
            "name": name,
            "description": description,
            "discount_percent": discount_percent,
            "bundle_price": bundle_price,
            "is_active": 1,
        }
    finally:
        await db.close()


async def fetch_bundle_by_id(bundle_id: int) -> dict | None:
    """Get bundle by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM skill_bundles WHERE id = ?", (bundle_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_bundle_items(bundle_id: int) -> list[dict]:
    """Get all items in a bundle with product details."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT bi.*, p.name as product_name, p.price as product_price
               FROM bundle_items bi
               JOIN products p ON bi.product_id = p.id
               WHERE bi.bundle_id = ?""",
            (bundle_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def fetch_bundle_item(bundle_id: int, product_id: int) -> dict | None:
    """Check if a product is already in a bundle."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM bundle_items WHERE bundle_id = ? AND product_id = ?",
            (bundle_id, product_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_all_bundles() -> list[dict]:
    """Get all active bundles with seller info."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT b.*, u.username as seller_name
               FROM skill_bundles b
               JOIN users u ON b.seller_id = u.id
               WHERE b.is_active = 1
               ORDER BY b.created_at DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def add_bundle_item(bundle_id: int, product_id: int) -> None:
    """Add a product to a bundle."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO bundle_items (bundle_id, product_id) VALUES (?, ?)",
            (bundle_id, product_id)
        )
        await db.commit()
    finally:
        await db.close()


async def remove_bundle_item(bundle_id: int, product_id: int) -> None:
    """Remove a product from a bundle."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM bundle_items WHERE bundle_id = ? AND product_id = ?",
            (bundle_id, product_id)
        )
        await db.commit()
    finally:
        await db.close()


async def update_bundle_price(bundle_id: int, new_price: int) -> None:
    """Update bundle price."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE skill_bundles SET bundle_price = ? WHERE id = ?",
            (new_price, bundle_id)
        )
        await db.commit()
    finally:
        await db.close()


# ---- Agent v4 Helpers ----


async def create_agent_v4(user_id: str, name: str, description: str, model: str) -> int:
    """Create an agent (v4) with model field instead of system_prompt."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO user_agents (user_id, name, description, system_prompt, skill_ids) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, description, "", "[]"),
        )
        await db.commit()
        agent_id = cursor.lastrowid
        # Update with model in agent_config
        await db.execute(
            "UPDATE user_agents SET agent_config = ? WHERE id = ?",
            (json.dumps({"model": model}), agent_id)
        )
        await db.commit()
        return agent_id
    finally:
        await db.close()


async def get_agent_skills(agent_id: int) -> list[dict]:
    """Get skills for an agent."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT as_sk.*, p.name as product_name, p.price as product_price, p.category
               FROM agent_skills as_sk
               JOIN products p ON as_sk.product_id = p.id
               WHERE as_sk.agent_id = ?""",
            (agent_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def add_agent_skill(agent_id: int, product_id: int) -> None:
    """Add a skill to an agent."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO agent_skills (agent_id, product_id) VALUES (?, ?)",
            (agent_id, product_id)
        )
        await db.commit()
    finally:
        await db.close()


async def remove_agent_skill(agent_id: int, product_id: int) -> None:
    """Remove a skill from an agent."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM agent_skills WHERE agent_id = ? AND product_id = ?",
            (agent_id, product_id)
        )
        await db.commit()
    finally:
        await db.close()


# ===========================================================================
# v4.3 – Wishlist & Recommendations
# ===========================================================================

async def add_to_wishlist(user_id: str, product_id: int):
    """Add a product to user's wishlist. Returns the created item."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO wishlist_items (user_id, product_id) VALUES (?, ?)",
            (user_id, product_id),
        )
        await db.commit()
        row_id = cursor.lastrowid
        cursor = await db.execute(
            """SELECT wi.id, wi.product_id, p.name as product_name, p.price, p.category
               FROM wishlist_items wi
               JOIN products p ON wi.product_id = p.id
               WHERE wi.id = ?""",
            (row_id,),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0], "product_id": row[1], "product_name": row[2],
                "price": row[3], "category": row[4],
            }
        return None
    finally:
        await db.close()


async def remove_from_wishlist(user_id: str, product_id: int):
    """Remove a product from user's wishlist. Returns True if removed."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM wishlist_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_user_wishlist(user_id: str) -> list[dict]:
    """Get all items in user's wishlist with product details."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT wi.id, wi.product_id, p.name as product_name, p.price,
                      p.category, p.seller_name, wi.created_at
               FROM wishlist_items wi
               JOIN products p ON wi.product_id = p.id
               WHERE wi.user_id = ?
               ORDER BY wi.created_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0], "product_id": r[1], "product_name": r[2],
                "price": r[3], "category": r[4], "seller_name": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]
    finally:
        await db.close()


async def is_in_wishlist(user_id: str, product_id: int) -> bool:
    """Check if a product is in user's wishlist."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM wishlist_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def get_similar_products(product_id: int, limit: int = 5) -> list[dict]:
    """Get similar products by category (excluding the product itself)."""
    db = await get_db()
    try:
        # First get the product's category
        cursor = await db.execute(
            "SELECT category FROM products WHERE id = ?", (product_id,)
        )
        product = await cursor.fetchone()
        if not product:
            return []

        category = product[0]
        cursor = await db.execute(
            """SELECT id, name, price, category, seller_name, downloads, sales
               FROM products
               WHERE category = ? AND id != ?
               ORDER BY sales DESC, downloads DESC
               LIMIT ?""",
            (category, product_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            {
                "product_id": r[0], "name": r[1], "price": r[2],
                "category": r[3], "seller_name": r[4],
                "downloads": r[5], "sales": r[6],
            }
            for r in rows
        ]
    finally:
        await db.close()


async def get_frequently_bought_together(product_id: int, limit: int = 5) -> list[dict]:
    """Get products frequently bought together with the given product.

    Finds products that were purchased by the same buyer who also bought the
    given product (within the same day).
    """
    db = await get_db()
    try:
        # Find buyers who purchased the given product
        cursor = await db.execute(
            """SELECT buyer_id, created_at
               FROM transactions
               WHERE product_id = ? AND status = 'completed'""",
            (product_id,),
        )
        buyer_rows = await cursor.fetchall()

        if not buyer_rows:
            return []

        # For each buyer, find other products they bought (same day)
        other_product_ids: set[int] = set()
        for buyer_id, created_at in buyer_rows:
            if not created_at:
                continue
            # Extract date part (YYYY-MM-DD)
            date_part = created_at[:10]
            cursor = await db.execute(
                """SELECT DISTINCT t.product_id, p.name, p.price, p.category,
                          p.seller_name, COUNT(*) as co_count
                   FROM transactions t
                   JOIN products p ON t.product_id = p.id
                   WHERE t.buyer_id = ? AND t.product_id != ?
                     AND t.status = 'completed'
                     AND substr(t.created_at, 1, 10) = ?
                   GROUP BY t.product_id
                   ORDER BY co_count DESC""",
                (buyer_id, product_id, date_part),
            )
            rows = await cursor.fetchall()
            for row in rows:
                other_product_ids.add(row[0])

        if not other_product_ids:
            return []

        # Fetch details for the recommended products
        placeholders = ",".join("?" for _ in other_product_ids)
        cursor = await db.execute(
            f"""SELECT id, name, price, category, seller_name
               FROM products
               WHERE id IN ({placeholders})""",
            tuple(other_product_ids),
        )
        rows = await cursor.fetchall()
        return [
            {
                "product_id": r[0], "name": r[1], "price": r[2],
                "category": r[3], "seller_name": r[4],
            }
            for r in rows[:limit]
        ]
    finally:
        await db.close()


# ===========================================================================
# v4.4 – Affiliate Program
# ===========================================================================

async def create_affiliate_link(seller_id: str, product_id: int, commission_rate: float = 10.0) -> dict:
    """Create an affiliate link for a product. Returns the link details."""
    # Verify seller owns the product
    product = await fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")
    if product.get("seller_name") != seller_id:
        raise PermissionError("Not authorized")

    # Generate unique code
    import secrets
    code = secrets.token_urlsafe(8)

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO affiliate_links (seller_id, product_id, code, commission_rate) VALUES (?, ?, ?, ?)",
            (seller_id, product_id, code, commission_rate),
        )
        await db.commit()
        link_id = cursor.lastrowid

        # Build link URL
        base_url = "http://localhost:8000"  # TODO: make configurable
        link_url = f"{base_url}/api/v4/affiliate/click/{code}"

        return {
            "id": link_id,
            "product_id": product_id,
            "code": code,
            "link": link_url,
            "commission_rate": commission_rate,
        }
    finally:
        await db.close()


async def get_affiliate_link_by_code(code: str) -> dict | None:
    """Get affiliate link by code."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, seller_id, product_id, code, commission_rate, is_active FROM affiliate_links WHERE code = ?",
            (code,),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0], "seller_id": row[1], "product_id": row[2],
                "code": row[3], "commission_rate": row[4], "is_active": row[5],
            }
        return None
    finally:
        await db.close()


async def track_affiliate_click(link_id: int, ip_address: str = None, user_agent: str = None):
    """Track an affiliate link click."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO affiliate_clicks (link_id, ip_address, user_agent) VALUES (?, ?, ?)",
            (link_id, ip_address, user_agent),
        )
        await db.commit()
    finally:
        await db.close()


async def track_affiliate_conversion(link_id: int, buyer_id: str, transaction_id: int, product_price: int, commission_rate: float) -> dict:
    """Track an affiliate conversion (purchase)."""
    commission_amount = int(product_price * commission_rate / 100)

    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO affiliate_conversions (link_id, buyer_id, transaction_id, commission_amount) VALUES (?, ?, ?, ?)",
            (link_id, buyer_id, transaction_id, commission_amount),
        )
        await db.commit()
        conversion_id = cursor.lastrowid

        return {
            "id": conversion_id,
            "link_id": link_id,
            "buyer_id": buyer_id,
            "transaction_id": transaction_id,
            "commission_amount": commission_amount,
        }
    finally:
        await db.close()


async def get_affiliate_stats(product_id: int, seller_id: str) -> dict:
    """Get affiliate statistics for a product."""
    # Verify seller owns the product
    product = await fetch_product_by_id(product_id)
    if not product:
        raise ValueError("Product not found")
    if product.get("seller_name") != seller_id:
        raise PermissionError("Not authorized")

    db = await get_db()
    try:
        # Get link ID
        cursor = await db.execute(
            "SELECT id FROM affiliate_links WHERE product_id = ? AND seller_id = ?",
            (product_id, seller_id),
        )
        link_row = await cursor.fetchone()
        if not link_row:
            return {"clicks": 0, "conversions": 0, "commission_earned": 0, "conversion_rate": 0.0}

        link_id = link_row[0]

        # Count clicks
        cursor = await db.execute(
            "SELECT COUNT(*) FROM affiliate_clicks WHERE link_id = ?",
            (link_id,),
        )
        clicks = (await cursor.fetchone())[0]

        # Count conversions and sum commission
        cursor = await db.execute(
            "SELECT COUNT(*), COALESCE(SUM(commission_amount), 0) FROM affiliate_conversions WHERE link_id = ?",
            (link_id,),
        )
        conv_row = await cursor.fetchone()
        conversions = conv_row[0]
        commission_earned = conv_row[1]

        conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0.0

        return {
            "clicks": clicks,
            "conversions": conversions,
            "commission_earned": commission_earned,
            "conversion_rate": round(conversion_rate, 2),
        }
    finally:
        await db.close()


async def get_affiliate_link_for_product(product_id: int, seller_id: str) -> dict | None:
    """Get affiliate link for a product (if exists)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, product_id, code, commission_rate, is_active FROM affiliate_links WHERE product_id = ? AND seller_id = ?",
            (product_id, seller_id),
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0], "product_id": row[1], "code": row[2],
                "commission_rate": row[3], "is_active": row[4],
            }
        return None
    finally:
        await db.close()


# ===========================================================================
# v4.5 – Semantic Search (Embeddings)
# ===========================================================================

async def init_semantic_search() -> None:
    """Create the product_embeddings table if it does not already exist."""
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS product_embeddings (
                product_id INTEGER PRIMARY KEY REFERENCES products(id),
                embedding TEXT NOT NULL,
                model_version TEXT DEFAULT 'v1',
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()
    finally:
        await db.close()


async def save_product_embedding(product_id: int, embedding: list[float]) -> None:
    """Save or update the embedding vector for a product."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO product_embeddings (product_id, embedding, model_version, updated_at)
               VALUES (?, ?, 'v1', datetime('now'))
               ON CONFLICT(product_id) DO UPDATE SET
                   embedding = excluded.embedding,
                   model_version = 'v1',
                   updated_at = datetime('now')""",
            (product_id, json.dumps(embedding, ensure_ascii=False)),
        )
        await db.commit()
    finally:
        await db.close()


async def get_product_embedding(product_id: int) -> list[float] | None:
    """Retrieve the embedding vector for a single product, or None if not indexed."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT embedding FROM product_embeddings WHERE product_id = ?",
            (product_id,),
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
    finally:
        await db.close()


async def get_all_product_embeddings() -> list[dict]:
    """Return all (product_id, embedding) pairs from the embeddings table."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT product_id, embedding FROM product_embeddings",
        )
        rows = await cursor.fetchall()
        return [
            {"product_id": r[0], "embedding": json.loads(r[1])}
            for r in rows
        ]
    finally:
        await db.close()


# ===========================================================================
# v4.7 – Subscription Helpers
# ===========================================================================

async def create_subscription_table():
    """Create the subscriptions table if it does not exist."""
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                starts_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                auto_renew INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_product ON subscriptions(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)")
        await db.commit()
    finally:
        await db.close()


async def create_subscription_events_table():
    """Create the subscription_events table if it does not exist."""
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscription_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                amount INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
            )
        """)
        await db.commit()
    finally:
        await db.close()


async def add_subscription_columns_to_products():
    """Add subscription columns to products table if they don't exist."""
    db = await get_db()
    try:
        try:
            await db.execute("ALTER TABLE products ADD COLUMN subscription_plans TEXT DEFAULT '[]'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE products ADD COLUMN is_subscription INTEGER DEFAULT 0")
        except Exception:
            pass
        await db.commit()
    finally:
        await db.close()


# ---- Subscription CRUD ----

async def create_subscription_db(user_id: str, product_id: int, plan: str, price: int, starts_at: str, expires_at: str) -> dict:
    """Create a new subscription record. Returns the inserted row."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO subscriptions (user_id, product_id, plan, price, status, starts_at, expires_at, auto_renew)
               VALUES (?, ?, ?, ?, 'active', ?, ?, 1)""",
            (user_id, product_id, plan, price, starts_at, expires_at),
        )
        await db.commit()
        sub_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_subscription_by_id(sub_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_active_subscription(user_id: str, product_id: int) -> dict | None:
    """Fetch the active subscription for a user+product, or None."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM subscriptions
               WHERE user_id = ? AND product_id = ? AND status = 'active'
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_cancelled_subscription(user_id: str, product_id: int) -> dict | None:
    """Fetch the cancelled subscription for a user+product, or None."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM subscriptions
               WHERE user_id = ? AND product_id = ? AND status = 'cancelled'
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def fetch_user_subscriptions(user_id: str) -> list[dict]:
    """Fetch all active subscriptions for a user with product info."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT s.*, p.name as product_name, p.icon as product_icon, p.category as product_category
               FROM subscriptions s
               JOIN products p ON s.product_id = p.id
               WHERE s.user_id = ? AND s.status = 'active'
               ORDER BY s.created_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_subscription_status(sub_id: int, status: str) -> bool:
    """Update subscription status."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE subscriptions SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, sub_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_subscription_expiry(sub_id: int, expires_at: str) -> bool:
    """Update subscription expiry and set status to active."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE subscriptions SET expires_at = ?, status = 'active', updated_at = datetime('now') WHERE id = ?",
            (expires_at, sub_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def toggle_subscription_auto_renew_db(sub_id: int) -> dict | None:
    """Toggle auto_renew flag. Returns updated row or None."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE subscriptions SET auto_renew = (auto_renew + 1) % 2, updated_at = datetime('now') WHERE id = ?",
            (sub_id,),
        )
        await db.commit()
        if cursor.rowcount > 0:
            cursor = await db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
        return None
    finally:
        await db.close()


async def find_expired_subscriptions() -> list[dict]:
    """Find all active subscriptions where expires_at < now."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM subscriptions
               WHERE status = 'active' AND expires_at < datetime('now')"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_product_subscription_plans(product_id: int) -> list[dict]:
    """Get subscription plans configured for a product."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT subscription_plans FROM products WHERE id = ?",
            (product_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return []
        plans_str = row[0] or "[]"
        try:
            import json as _json
            return _json.loads(plans_str)
        except Exception:
            return []
    finally:
        await db.close()


async def update_product_subscription_config(product_id: int, plans: list, is_subscription: bool) -> bool:
    """Update subscription configuration for a product."""
    db = await get_db()
    try:
        import json as _json
        plans_json = _json.dumps(plans)
        cursor = await db.execute(
            "UPDATE products SET subscription_plans = ?, is_subscription = ? WHERE id = ?",
            (plans_json, 1 if is_subscription else 0, product_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def insert_subscription_event(subscription_id: int, event_type: str, amount: int = None) -> int:
    """Record a subscription lifecycle event."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO subscription_events (subscription_id, event_type, amount) VALUES (?, ?, ?)",
            (subscription_id, event_type, amount),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_seller_subscription_stats_db(seller_id: str) -> dict:
    """Get subscription analytics for a seller's products."""
    db = await get_db()
    try:
        # Resolve seller name
        user = await db.execute("SELECT username FROM users WHERE id = ?", (seller_id,))
        user_row = await user.fetchone()
        if not user_row:
            return {"error": "user not found"}
        seller_name = user_row[0]

        # Get seller's product IDs
        cursor = await db.execute(
            "SELECT id FROM products WHERE seller_name = ?",
            (seller_name,),
        )
        product_rows = await cursor.fetchall()
        product_ids = [r[0] for r in product_rows]

        if not product_ids:
            return {
                "total_subscribers": 0,
                "active_subscriptions": 0,
                "monthly_recurring_revenue": 0,
                "churn_rate": 0.0,
                "by_plan": {},
                "top_products": [],
            }

        placeholders = ",".join("?" for _ in product_ids)
        params = tuple(product_ids)

        # Count all-time subscribers (distinct user_id)
        cursor = await db.execute(
            f"SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE product_id IN ({placeholders})",
            params,
        )
        total_subscribers = (await cursor.fetchone())[0]

        # Active subscriptions
        cursor = await db.execute(
            f"""SELECT COUNT(*) FROM subscriptions
                WHERE product_id IN ({placeholders}) AND status = 'active' AND expires_at > datetime('now')""",
            params,
        )
        active_subscriptions = (await cursor.fetchone())[0]

        # Expired (for churn)
        cursor = await db.execute(
            f"""SELECT COUNT(*) FROM subscriptions
                WHERE product_id IN ({placeholders}) AND status IN ('expired', 'cancelled')""",
            params,
        )
        expired_count = (await cursor.fetchone())[0]

        churn_rate = round(expired_count / total_subscribers, 4) if total_subscribers > 0 else 0.0

        # Revenue by plan (all subscriptions regardless of status)
        cursor = await db.execute(
            f"""SELECT plan, COUNT(*) as cnt, SUM(price) as revenue
                FROM subscriptions
                WHERE product_id IN ({placeholders})
                GROUP BY plan""",
            params,
        )
        plan_rows = await cursor.fetchall()
        by_plan = {}
        mrr = 0
        for row in plan_rows:
            plan_name = row[0]
            count = row[1]
            revenue = row[2] or 0
            by_plan[plan_name] = {"count": count, "revenue": revenue}
            if plan_name == "monthly":
                mrr += revenue
            elif plan_name == "weekly":
                mrr += int(revenue * 4.33)
            elif plan_name == "yearly":
                mrr += int(revenue / 12)

        # Top products
        cursor = await db.execute(
            f"""SELECT s.product_id, p.name, COUNT(*) as sub_count, SUM(s.price) as mrr
                FROM subscriptions s
                JOIN products p ON s.product_id = p.id
                WHERE s.product_id IN ({placeholders}) AND s.status = 'active' AND s.expires_at > datetime('now')
                GROUP BY s.product_id
                ORDER BY sub_count DESC
                LIMIT 10""",
            params,
        )
        top_rows = await cursor.fetchall()
        top_products = []
        for row in top_rows:
            top_products.append({
                "product_id": row[0],
                "name": row[1],
                "subscribers": row[2],
                "mrr": row[3] or 0,
            })

        return {
            "total_subscribers": total_subscribers,
            "active_subscriptions": active_subscriptions,
            "monthly_recurring_revenue": mrr,
            "churn_rate": churn_rate,
            "by_plan": by_plan,
            "top_products": top_products,
        }
    finally:
        await db.close()


# ---------- Trial Run Helpers ----------

async def init_trial_runs_table():
    """Create indexes for the trial_runs table (table itself is in _create_tables)."""
    db = await get_db()
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_trial_runs_user ON trial_runs(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_trial_runs_product ON trial_runs(product_id)")
        await db.commit()
    finally:
        await db.close()


async def create_trial_run(user_id: str, product_id: int, input_text: str,
                            status: str = "running") -> dict:
    """Create a new trial run record. Returns the inserted row."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO trial_runs (user_id, product_id, status, input_text)
               VALUES (?, ?, ?, ?)""",
            (user_id, product_id, status, input_text),
        )
        await db.commit()
        trial_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM trial_runs WHERE trial_id = ?", (trial_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_trial_run(trial_id: int) -> dict | None:
    """Get a trial run by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM trial_runs WHERE trial_id = ?", (trial_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_trial_runs_by_user(user_id: str) -> list[dict]:
    """Get all trial runs for a user, with product name joined."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT tr.*, p.name as product_name
               FROM trial_runs tr
               LEFT JOIN products p ON tr.product_id = p.id
               WHERE tr.user_id = ?
               ORDER BY tr.created_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_trial_runs_by_user_and_product(user_id: str, product_id: int) -> list[dict]:
    """Get all trial runs for a user+product."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM trial_runs
               WHERE user_id = ? AND product_id = ?
               ORDER BY created_at DESC""",
            (user_id, product_id),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_trial_run(trial_id: int, status: str = None, output_text: str = None,
                            error_message: str = None, tokens_used: int = None,
                            execution_time_ms: int = None) -> dict | None:
    """Update a trial run record. Returns updated row or None."""
    db = await get_db()
    try:
        sets = []
        params = []
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if output_text is not None:
            sets.append("output_text = ?")
            params.append(output_text)
        if error_message is not None:
            sets.append("error_message = ?")
            params.append(error_message)
        if tokens_used is not None:
            sets.append("tokens_used = ?")
            params.append(tokens_used)
        if execution_time_ms is not None:
            sets.append("execution_time_ms = ?")
            params.append(execution_time_ms)

        if not sets:
            return await get_trial_run(trial_id)

        params.append(trial_id)
        sql = f"UPDATE trial_runs SET {', '.join(sets)} WHERE trial_id = ?"
        cursor = await db.execute(sql, params)
        await db.commit()
        if cursor.rowcount > 0:
            return await get_trial_run(trial_id)
        return None
    finally:
        await db.close()


async def count_trial_runs_by_user_and_product(user_id: str, product_id: int) -> int:
    """Count how many trial runs a user has done for a product."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM trial_runs WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await db.close()


async def cleanup_old_trials(days: int = 30) -> int:
    """Delete trial runs older than `days` days. Returns count deleted."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM trial_runs WHERE created_at < ?",
            (cutoff,),
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()
