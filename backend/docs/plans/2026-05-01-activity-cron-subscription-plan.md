# Activity Task Center + Cron Subscription Marketplace Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Cron task subscription marketplace (publisher-server execution with push+pull delivery) and a dual-layer activity/points system (daily check-in + monthly tasks) to drive user retention and engagement.

**Architecture:** Publisher servers execute Cron tasks and push results to SkillBazaar via Webhook. Platform distributes results to subscribers via WebSocket + Webhook + API pull. Activity center uses Redis-free design — SQLite for all persistence, in-process WebSocket manager for real-time, with scheduled task runner for monthly auto-renewal and daily task reset.

**Tech Stack:** FastAPI + SQLite (aiosqlite) + WebSocket (FastAPI native) + React + Vite + Lucide Icons

---

### Task 1: Database Schema — Cron Tables

**Files:**
- Modify: `backend/database.py` (inside `_create_tables()` function after bounty_deliveries table)

**Step 1: Add 4 new Cron tables to database.py**

Add after the `bounty_deliveries` CREATE TABLE block:

```sql
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
```

**Step 2: Add helper functions to database.py**

After existing helper functions, add:

```python
async def insert_cron_product(product_id: int, schedule_cron: str, webhook_secret: str, result_format: str = "json") -> int:
    async with db.execute(
        "INSERT INTO cron_products (product_id, schedule_cron, webhook_secret, result_format) VALUES (?, ?, ?, ?)",
        (product_id, schedule_cron, webhook_secret, result_format),
    ) as cursor:
        await db.commit()
        return cursor.lastrowid

async def fetch_cron_product(product_id: int) -> dict | None:
    async with db.execute("SELECT * FROM cron_products WHERE product_id = ?", (product_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def fetch_cron_product_by_id(cron_id: int) -> dict | None:
    async with db.execute("SELECT * FROM cron_products WHERE id = ?", (cron_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def fetch_my_crons(publisher_id: str) -> list[dict]:
    async with db.execute(
        """SELECT cp.* FROM cron_products cp
        JOIN products p ON cp.product_id = p.id
        WHERE p.seller_name = (SELECT nickname FROM users WHERE id = ?)
        ORDER BY cp.created_at DESC""",
        (publisher_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def update_cron_product_status(cron_id: int, status: str):
    await db.execute("UPDATE cron_products SET status = ? WHERE id = ?", (status, cron_id))
    await db.commit()

async def increment_cron_execution(cron_id: int):
    await db.execute(
        """UPDATE cron_products
        SET execution_count = execution_count + 1, last_executed_at = datetime('now')
        WHERE id = ?""",
        (cron_id,),
    )
    await db.commit()

async def insert_cron_subscription(cron_product_id: int, subscriber_id: str, monthly_price: int, webhook_url: str | None = None) -> dict:
    import secrets
    from datetime import datetime, timedelta
    api_token = f"cs_{secrets.token_hex(16)}"
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
    async with db.execute(
        """INSERT INTO cron_subscriptions (cron_product_id, subscriber_id, monthly_price, webhook_url, api_token, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (cron_product_id, subscriber_id, monthly_price, webhook_url, api_token, expires_at),
    ) as cursor:
        await db.commit()
        # increment subscriber count
        await db.execute("UPDATE cron_products SET subscriber_count = subscriber_count + 1 WHERE id = ?", (cron_product_id,))
        await db.commit()
        return {"id": cursor.lastrowid, "api_token": api_token, "expires_at": expires_at}

async def fetch_cron_subscription(sub_id: int) -> dict | None:
    async with db.execute("SELECT * FROM cron_subscriptions WHERE id = ?", (sub_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def fetch_subscription_by_token(api_token: str) -> dict | None:
    async with db.execute("SELECT * FROM cron_subscriptions WHERE api_token = ?", (api_token,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None

async def fetch_active_subscriptions(cron_product_id: int) -> list[dict]:
    async with db.execute(
        "SELECT * FROM cron_subscriptions WHERE cron_product_id = ? AND status = 'active'",
        (cron_product_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def cancel_cron_subscription(sub_id: int):
    await db.execute("UPDATE cron_subscriptions SET status = 'cancelled' WHERE id = ?", (sub_id,))
    # decrement subscriber count
    await db.execute("""UPDATE cron_products SET subscriber_count = subscriber_count - 1
        WHERE id = (SELECT cron_product_id FROM cron_subscriptions WHERE id = ?)""", (sub_id,))
    await db.commit()

async def insert_execution_log(cron_product_id: int, payload: str, status: str, duration_ms: int = 0, subscription_id: int | None = None) -> int:
    async with db.execute(
        "INSERT INTO cron_execution_logs (cron_product_id, subscription_id, payload, status, duration_ms) VALUES (?, ?, ?, ?, ?)",
        (cron_product_id, subscription_id, payload, status, duration_ms),
    ) as cursor:
        await db.commit()
        return cursor.lastrowid

async def fetch_execution_logs(cron_product_id: int, limit: int = 20) -> list[dict]:
    async with db.execute(
        "SELECT * FROM cron_execution_logs WHERE cron_product_id = ? ORDER BY executed_at DESC LIMIT ?",
        (cron_product_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def fetch_subscription_logs(subscription_id: int, limit: int = 20) -> list[dict]:
    async with db.execute(
        "SELECT * FROM cron_execution_logs WHERE subscription_id = ? ORDER BY executed_at DESC LIMIT ?",
        (subscription_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def insert_webhook_delivery(execution_log_id: int, target_url: str) -> int:
    async with db.execute(
        "INSERT INTO cron_webhook_deliveries (execution_log_id, target_url) VALUES (?, ?)",
        (execution_log_id, target_url),
    ) as cursor:
        await db.commit()
        return cursor.lastrowid

async def update_webhook_delivery(delivery_id: int, status: str, response_code: int | None = None):
    await db.execute(
        "UPDATE cron_webhook_deliveries SET status = ?, response_code = ?, delivered_at = datetime('now'), attempts = attempts + 1 WHERE id = ?",
        (status, response_code, delivery_id),
    )
    await db.commit()
```

**Step 3: Verify DB init**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python3 -c "import asyncio, database; asyncio.run(database.init_db()); print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/database.py
git commit -m "feat: add Cron subscription tables and helpers"
```

---

### Task 2: Database Schema — Activity & Points Tables

**Files:**
- Modify: `backend/database.py` (add after Cron tables)

**Step 1: Add 5 new activity/points tables**

```sql
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
```

**Step 2: Add activity/points helper functions**

```python
async def get_or_create_point_account(user_id: str) -> dict:
    async with db.execute("SELECT * FROM point_accounts WHERE user_id = ?", (user_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            return dict(row)
    async with db.execute("INSERT INTO point_accounts (user_id) VALUES (?)", (user_id,)) as cursor:
        await db.commit()
        return {"id": cursor.lastrowid, "user_id": user_id, "balance": 0, "total_earned": 0, "total_spent": 0, "level": 1, "continuous_checkin_days": 0, "last_checkin_at": None}

async def add_points(user_id: str, amount: int, reason: str, ref_type: str | None = None, ref_id: int | None = None):
    await db.execute(
        "UPDATE point_accounts SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
        (amount, amount, user_id),
    )
    await db.execute(
        "INSERT INTO point_transactions (user_id, amount, type, reason, ref_type, ref_id) VALUES (?, ?, 'earn', ?, ?, ?)",
        (user_id, amount, reason, ref_type, ref_id),
    )
    await db.commit()

async def spend_points(user_id: str, amount: int, reason: str, ref_type: str | None = None, ref_id: int | None = None) -> bool:
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

async def fetch_point_history(user_id: str, limit: int = 50) -> list[dict]:
    async with db.execute(
        "SELECT * FROM point_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def insert_activity(title: str, description: str, act_type: str, start_at: str, end_at: str) -> int:
    async with db.execute(
        "INSERT INTO activities (title, description, type, start_at, end_at) VALUES (?, ?, ?, ?, ?)",
        (title, description, act_type, start_at, end_at),
    ) as cursor:
        await db.commit()
        return cursor.lastrowid

async def fetch_active_activities() -> list[dict]:
    async with db.execute(
        "SELECT * FROM activities WHERE status = 'active' AND end_at > datetime('now') ORDER BY start_at DESC"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def insert_activity_task(activity_id: int, task_key: str, name: str, description: str, task_type: str, action: str, target_count: int, reward_points: int, reward_coins: int = 0, icon: str | None = None, sort_order: int = 0) -> int:
    async with db.execute(
        """INSERT OR IGNORE INTO activity_tasks
        (activity_id, task_key, name, description, task_type, action, target_count, reward_points, reward_coins, icon, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (activity_id, task_key, name, description, task_type, action, target_count, reward_points, reward_coins, icon, sort_order),
    ) as cursor:
        await db.commit()
        return cursor.lastrowid

async def fetch_activity_tasks(activity_id: int) -> list[dict]:
    async with db.execute(
        "SELECT * FROM activity_tasks WHERE activity_id = ? ORDER BY sort_order", (activity_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def fetch_or_create_task_progress(user_id: str, task_id: int) -> dict:
    async with db.execute(
        "SELECT * FROM user_task_progress WHERE user_id = ? AND task_id = ?",
        (user_id, task_id),
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return dict(row)
    async with db.execute(
        "INSERT INTO user_task_progress (user_id, task_id) VALUES (?, ?)",
        (user_id, task_id),
    ) as cursor:
        await db.commit()
        return {"id": cursor.lastrowid, "user_id": user_id, "task_id": task_id, "progress": 0, "completed": 0, "reward_claimed": 0}

async def increment_task_progress(user_id: str, action: str):
    """Auto-increment progress for all active tasks matching the action."""
    tasks = await fetch_active_activities()
    if not tasks:
        return
    for act in tasks:
        act_tasks = await fetch_activity_tasks(act["id"])
        for t in act_tasks:
            if t["action"] == action:
                prog = await fetch_or_create_task_progress(user_id, t["id"])
                new_progress = prog["progress"] + 1
                completed = 1 if new_progress >= t["target_count"] else 0
                await db.execute(
                    "UPDATE user_task_progress SET progress = ?, completed = ? WHERE user_id = ? AND task_id = ?",
                    (new_progress, completed, user_id, t["id"]),
                )
    await db.commit()

async def claim_task_reward(user_id: str, task_id: int) -> dict | None:
    prog = await fetch_or_create_task_progress(user_id, task_id)
    if not prog["completed"] or prog["reward_claimed"]:
        return None
    async with db.execute(
        "SELECT * FROM activity_tasks WHERE id = ?", (task_id,),
    ) as cursor:
        row = await cursor.fetchone()
        task = dict(row) if row else None
    if not task:
        return None
    await db.execute("UPDATE user_task_progress SET reward_claimed = 1 WHERE user_id = ? AND task_id = ?", (user_id, task_id))
    if task["reward_points"] > 0:
        await add_points(user_id, task["reward_points"], "task_reward", "task", task_id)
    if task["reward_coins"] > 0:
        await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (task["reward_coins"], user_id))
    await db.commit()
    return {"points": task["reward_points"], "coins": task["reward_coins"]}

async def do_checkin(user_id: str) -> dict:
    """Daily check-in. Returns points earned and streak info."""
    account = await get_or_create_point_account(user_id)
    last = account.get("last_checkin_at")
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")

    if last and last.startswith(today):
        return {"ok": False, "message": "今天已经签到过了", "streak": account["continuous_checkin_days"]}

    streak = account["continuous_checkin_days"]
    if last:
        last_dt = datetime.fromisoformat(last)
        if (now - last_dt).days == 1:
            streak += 1
        else:
            streak = 1
    else:
        streak = 1

    bonus = 50 if streak >= 7 and streak % 7 == 0 else 0
    points = 10 + bonus

    await db.execute(
        "UPDATE point_accounts SET last_checkin_at = ?, continuous_checkin_days = ? WHERE user_id = ?",
        (now.isoformat(), streak, user_id),
    )
    await add_points(user_id, points, "checkin")
    await increment_task_progress(user_id, "checkin")
    return {"ok": True, "points": points, "streak": streak, "bonus": bonus}

async def update_user_level(user_id: str):
    account = await get_or_create_point_account(user_id)
    total = account["total_earned"]
    level = 1
    if total >= 15000: level = 5
    elif total >= 5000: level = 4
    elif total >= 2000: level = 3
    elif total >= 500: level = 2
    await db.execute("UPDATE point_accounts SET level = ? WHERE user_id = ?", (level, user_id))
    await db.commit()

async def seed_default_activity():
    """Create default monthly activity with tasks if none exists."""
    activities = await fetch_active_activities()
    if activities:
        return
    from datetime import datetime, timedelta
    now = datetime.utcnow()
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
    async with db.execute(
        "SELECT pa.*, u.nickname FROM point_accounts pa JOIN users u ON pa.user_id = u.id ORDER BY pa.total_earned DESC LIMIT ?",
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
```

**Step 2: Call `seed_default_activity()` in `init_db()` after table creation**

**Step 3: Verify**

Run: `python3 -c "import asyncio, database; asyncio.run(database.init_db()); print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add backend/database.py
git commit -m "feat: add activity/points tables and helpers"
```

---

### Task 3: Backend Models — Cron & Activity Pydantic Models

**Files:**
- Modify: `backend/models.py` (append at end of file)

**Step 1: Add new models**

```python
# ---------- Cron Subscription Models ----------

class CronProductCreate(BaseModel):
    product_id: int
    schedule_cron: str
    result_format: str = "json"

class CronProductResponse(BaseModel):
    id: int
    product_id: int
    schedule_cron: str
    result_format: str
    status: str
    last_executed_at: Optional[str] = None
    avg_duration_ms: int = 0
    subscriber_count: int = 0
    execution_count: int = 0
    created_at: Optional[str] = None

class CronSubscriptionResponse(BaseModel):
    id: int
    cron_product_id: int
    subscriber_id: str
    status: str
    subscribed_at: Optional[str] = None
    expires_at: Optional[str] = None
    monthly_price: int = 0
    webhook_url: Optional[str] = None
    api_token: Optional[str] = None
    last_result_at: Optional[str] = None

class CronPushRequest(BaseModel):
    payload: str
    executed_at: Optional[str] = None
    duration_ms: int = 0

class CronExecutionLogResponse(BaseModel):
    id: int
    cron_product_id: int
    subscription_id: Optional[int] = None
    payload: Optional[str] = None
    status: str
    executed_at: Optional[str] = None
    duration_ms: int = 0

# ---------- Activity & Points Models ----------

class ActivityResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: str
    start_at: str
    end_at: str
    status: str

class ActivityTaskResponse(BaseModel):
    id: int
    activity_id: int
    task_key: str
    name: str
    description: Optional[str] = None
    task_type: str
    action: str
    target_count: int
    reward_points: int
    reward_coins: int
    icon: Optional[str] = None
    progress: int = 0
    completed: bool = False
    reward_claimed: bool = False

class CheckinResponse(BaseModel):
    ok: bool
    message: str = ""
    points: int = 0
    streak: int = 0
    bonus: int = 0

class PointAccountResponse(BaseModel):
    user_id: str
    balance: int
    total_earned: int
    total_spent: int
    level: int
    continuous_checkin_days: int
    last_checkin_at: Optional[str] = None

class PointRedeemRequest(BaseModel):
    amount: int = Field(gt=0)
    redeem_type: str = "coins"  # coins, coupon

class LeaderboardEntry(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    total_earned: int
    level: int
```

**Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: add Cron subscription and Activity/Points Pydantic models"
```

---

### Task 4: Backend Service — Cron Service

**Files:**
- Create: `backend/services/cron_service.py`

**Step 1: Create cron_service.py**

```python
from __future__ import annotations

import json
import secrets
import httpx

import database as db
from models import (
    CronProductCreate, CronProductResponse, CronSubscriptionResponse,
    CronPushRequest, CronExecutionLogResponse,
)


async def register_cron_product(user_id: str, data: CronProductCreate) -> dict:
    """Register a product as a Cron with scheduling config."""
    product = await db.fetch_product_by_id(data.product_id)
    if not product:
        raise ValueError("商品不存在")
    existing = await db.fetch_cron_product(data.product_id)
    if existing:
        raise ValueError("该商品已注册为Cron")
    webhook_secret = f"whs_{secrets.token_hex(16)}"
    cron_id = await db.insert_cron_product(
        data.product_id, data.schedule_cron, webhook_secret, data.result_format,
    )
    return {"id": cron_id, "webhook_secret": webhook_secret}


async def subscribe_cron(user_id: str, cron_id: int, webhook_url: str | None = None) -> dict:
    """Subscribe to a Cron product."""
    cron = await db.fetch_cron_product_by_id(cron_id)
    if not cron:
        raise ValueError("Cron商品不存在")
    if cron["status"] != "active":
        raise ValueError("该Cron已暂停")
    product = await db.fetch_product_by_id(cron["product_id"])
    price = product["price"] if product else 0
    # Deduct coins
    user = await db.fetch_user(user_id)
    if not user or user["coins"] < price:
        raise ValueError("金币不足")
    await db.update_user_coins(user_id, -price)
    result = await db.insert_cron_subscription(cron_id, user_id, price, webhook_url)
    await db.increment_task_progress(user_id, "subscribe_cron")
    return result


async def push_cron_result(cron_id: int, secret: str, data: CronPushRequest) -> dict:
    """Publisher pushes execution result."""
    cron = await db.fetch_cron_product_by_id(cron_id)
    if not cron:
        raise ValueError("Cron不存在")
    if cron["webhook_secret"] != secret:
        raise ValueError("认证失败")
    # Store execution log
    log_id = await db.insert_execution_log(
        cron_id, data.payload, "success", data.duration_ms,
    )
    await db.increment_cron_execution(cron_id)
    # Deliver to subscribers
    subs = await db.fetch_active_subscriptions(cron_id)
    delivery_results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for sub in subs:
            if sub.get("webhook_url"):
                try:
                    resp = await client.post(
                        sub["webhook_url"],
                        json={"cron_id": cron_id, "payload": json.loads(data.payload) if data.payload else None},
                        headers={"X-Cron-Token": sub["api_token"]},
                    )
                    del_id = await db.insert_webhook_delivery(log_id, sub["webhook_url"])
                    await db.update_webhook_delivery(del_id, "sent" if resp.status_code < 400 else "failed", resp.status_code)
                    delivery_results.append({"sub_id": sub["id"], "status": "sent"})
                except Exception:
                    delivery_results.append({"sub_id": sub["id"], "status": "failed"})
            await db.execute(
                "UPDATE cron_subscriptions SET last_result_at = datetime('now') WHERE id = ?",
                (sub["id"],),
            )
    await db.commit()
    return {"log_id": log_id, "delivered_to": len(delivery_results), "results": delivery_results}


async def get_cron_results(subscription_id: int, api_token: str, limit: int = 20) -> list[dict]:
    """Subscriber pulls execution results."""
    sub = await db.fetch_cron_subscription(subscription_id)
    if not sub or sub["api_token"] != api_token:
        raise ValueError("无效的订阅或Token")
    return await db.fetch_subscription_logs(subscription_id, limit)


async def cancel_subscription(user_id: str, sub_id: int):
    sub = await db.fetch_cron_subscription(sub_id)
    if not sub or sub["subscriber_id"] != user_id:
        raise ValueError("无效的订阅")
    await db.cancel_cron_subscription(sub_id)


async def get_my_subscriptions(user_id: str) -> list[dict]:
    async with db.execute(
        """SELECT cs.*, cp.schedule_cron, cp.result_format, cp.execution_count, p.name as product_name
        FROM cron_subscriptions cs
        JOIN cron_products cp ON cs.cron_product_id = cp.id
        JOIN products p ON cp.product_id = p.id
        WHERE cs.subscriber_id = ?
        ORDER BY cs.subscribed_at DESC""",
        (user_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_my_crons(user_id: str) -> list[dict]:
    return await db.fetch_my_crons(user_id)
```

**Step 2: Commit**

```bash
git add backend/services/cron_service.py
git commit -m "feat: add Cron subscription service"
```

---

### Task 5: Backend Service — Activity Service

**Files:**
- Create: `backend/services/activity_service.py`

**Step 1: Create activity_service.py**

```python
from __future__ import annotations

import database as db
from models import (
    ActivityResponse, ActivityTaskResponse, CheckinResponse,
    PointAccountResponse, PointRedeemRequest, LeaderboardEntry,
)


async def get_activities_with_tasks(user_id: str) -> list[dict]:
    activities = await db.fetch_active_activities()
    result = []
    for act in activities:
        tasks = await db.fetch_activity_tasks(act["id"])
        task_list = []
        for t in tasks:
            prog = await db.fetch_or_create_task_progress(user_id, t["id"])
            task_list.append({
                **t,
                "progress": prog["progress"],
                "completed": bool(prog["completed"]),
                "reward_claimed": bool(prog["reward_claimed"]),
            })
        result.append({**act, "tasks": task_list})
    return result


async def checkin(user_id: str) -> dict:
    await db.get_or_create_point_account(user_id)
    result = await db.do_checkin(user_id)
    await db.update_user_level(user_id)
    return result


async def claim_reward(user_id: str, task_id: int) -> dict | None:
    reward = await db.claim_task_reward(user_id, task_id)
    if reward:
        await db.update_user_level(user_id)
    return reward


async def get_point_account(user_id: str) -> dict:
    return await db.get_or_create_point_account(user_id)


async def get_point_history(user_id: str, limit: int = 50) -> list[dict]:
    return await db.fetch_point_history(user_id, limit)


async def redeem_points(user_id: str, data: PointRedeemRequest) -> dict:
    account = await db.get_or_create_point_account(user_id)
    if data.redeem_type == "coins":
        cost = data.amount * 10  # 100 points = 10 coins
        if account["balance"] < cost:
            raise ValueError("积分不足")
        ok = await db.spend_points(user_id, cost, "redeem_coins", "redeem", None)
        if not ok:
            raise ValueError("积分扣除失败")
        await db.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (data.amount, user_id))
        await db.commit()
        await db.increment_task_progress(user_id, "spend")
        return {"coins_received": data.amount, "points_spent": cost}
    raise ValueError("不支持的兑换类型")


async def get_leaderboard(limit: int = 20) -> list[dict]:
    return await db.fetch_points_leaderboard(limit)
```

**Step 2: Commit**

```bash
git add backend/services/activity_service.py
git commit -m "feat: add Activity/Points service"
```

---

### Task 6: Backend Router — Cron Endpoints

**Files:**
- Create: `backend/routers/cron.py`
- Modify: `backend/main.py` (add router include)

**Step 1: Create cron router**

```python
from fastapi import APIRouter, Header, HTTPException, Depends

from models import CronProductCreate, CronPushRequest
from services import cron_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/cron", tags=["cron"])


@router.post("/register")
async def register_cron(data: CronProductCreate, user: dict = Depends(get_current_user)):
    try:
        return await cron_service.register_cron_product(user["id"], data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/subscribe/{cron_id}")
async def subscribe_cron(cron_id: int, user: dict = Depends(get_current_user), webhook_url: str | None = None):
    try:
        return await cron_service.subscribe_cron(user["id"], cron_id, webhook_url)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/push/{cron_id}")
async def push_result(cron_id: int, data: CronPushRequest, x_webhook_secret: str = Header(..., alias="X-Webhook-Secret")):
    try:
        return await cron_service.push_cron_result(cron_id, x_webhook_secret, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/results/{subscription_id}")
async def get_results(subscription_id: int, token: str, limit: int = 20):
    try:
        return await cron_service.get_cron_results(subscription_id, token, limit)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/subscription/{sub_id}")
async def cancel_subscription(sub_id: int, user: dict = Depends(get_current_user)):
    try:
        await cron_service.cancel_subscription(user["id"], sub_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/my-subscriptions")
async def my_subscriptions(user: dict = Depends(get_current_user)):
    return await cron_service.get_my_subscriptions(user["id"])


@router.get("/my-crons")
async def my_crons(user: dict = Depends(get_current_user)):
    return await cron_service.get_my_crons(user["id"])
```

**Step 2: Add to main.py**

In `backend/main.py`, add import and include:

```python
from routers.cron import router as cron_router
# ...
app.include_router(cron_router)
```

**Step 3: Commit**

```bash
git add backend/routers/cron.py backend/main.py
git commit -m "feat: add Cron subscription API endpoints"
```

---

### Task 7: Backend Router — Activity Endpoints

**Files:**
- Create: `backend/routers/activities.py`
- Modify: `backend/main.py` (add router include)

**Step 1: Create activities router**

```python
from fastapi import APIRouter, HTTPException, Depends

from models import PointRedeemRequest
from services import activity_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/activities", tags=["activities"])


@router.get("")
async def get_activities(user: dict = Depends(get_current_user)):
    return await activity_service.get_activities_with_tasks(user["id"])


@router.post("/checkin")
async def checkin(user: dict = Depends(get_current_user)):
    return await activity_service.checkin(user["id"])


@router.post("/tasks/{task_id}/claim")
async def claim_reward(task_id: int, user: dict = Depends(get_current_user)):
    result = await activity_service.claim_reward(user["id"], task_id)
    if not result:
        raise HTTPException(400, "任务未完成或已领取")
    return result


@router.get("/points/balance")
async def get_points(user: dict = Depends(get_current_user)):
    return await activity_service.get_point_account(user["id"])


@router.get("/points/history")
async def get_point_history(user: dict = Depends(get_current_user), limit: int = 50):
    return await activity_service.get_point_history(user["id"], limit)


@router.post("/points/redeem")
async def redeem_points(data: PointRedeemRequest, user: dict = Depends(get_current_user)):
    try:
        return await activity_service.redeem_points(user["id"], data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/leaderboard")
async def leaderboard(limit: int = 20):
    return await activity_service.get_leaderboard(limit)
```

**Step 2: Add to main.py**

```python
from routers.activities import router as activities_router
# ...
app.include_router(activities_router)
```

**Step 3: Commit**

```bash
git add backend/routers/activities.py backend/main.py
git commit -m "feat: add Activity/Points API endpoints"
```

---

### Task 8: Backend — Behavior Event → Task Progress Integration

**Files:**
- Modify: `backend/routers/user_v2.py` (in the behavior logging endpoint)

**Step 1: Add auto-increment to behavior logging**

In the `/v2/behavior` endpoint, after logging the behavior, add:

```python
# Auto-increment task progress based on action
await database.increment_task_progress(user["id"], action)
if action in ("buy",):
    await database.increment_task_progress(user["id"], "spend")
```

**Step 2: Also add to product creation, bounty creation, bounty delivery endpoints**

In each of these routers, after the successful action, call `increment_task_progress`.

**Step 3: Commit**

```bash
git add backend/routers/user_v2.py backend/routers/products.py backend/routers/bounties.py
git commit -m "feat: wire behavior events to activity task progress"
```

---

### Task 9: Frontend API — New API Functions

**Files:**
- Modify: `frontend/src/services/api.js` (append new functions)

**Step 1: Add Cron API functions**

```javascript
// ---- Cron Subscriptions ----

export async function registerCronProduct(data, token) {
  return api.post('/cron/register', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function subscribeCron(cronId, webhookUrl, token) {
  return api.post(`/cron/subscribe/${cronId}${webhookUrl ? `?webhook_url=${encodeURIComponent(webhookUrl)}` : ''}`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getCronResults(subscriptionId, apiToken, limit = 20) {
  return api.get(`/cron/results/${subscriptionId}?token=${apiToken}&limit=${limit}`)
}

export async function cancelCronSubscription(subId, token) {
  return api.delete(`/cron/subscription/${subId}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyCronSubscriptions(token) {
  return api.get('/cron/my-subscriptions', { headers: { Authorization: `Bearer ${token}` } })
}

export async function getMyCrons(token) {
  return api.get('/cron/my-crons', { headers: { Authorization: `Bearer ${token}` } })
}

// ---- Activities & Points ----

export async function getActivities(token) {
  return api.get('/activities', { headers: { Authorization: `Bearer ${token}` } })
}

export async function doCheckin(token) {
  return api.post('/activities/checkin', {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function claimTaskReward(taskId, token) {
  return api.post(`/activities/tasks/${taskId}/claim`, {}, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getPointsBalance(token) {
  return api.get('/activities/points/balance', { headers: { Authorization: `Bearer ${token}` } })
}

export async function getPointsHistory(token, limit = 50) {
  return api.get(`/activities/points/history?limit=${limit}`, { headers: { Authorization: `Bearer ${token}` } })
}

export async function redeemPoints(data, token) {
  return api.post('/activities/points/redeem', data, { headers: { Authorization: `Bearer ${token}` } })
}

export async function getLeaderboard(limit = 20) {
  return api.get(`/activities/leaderboard?limit=${limit}`)
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add Cron and Activity frontend API functions"
```

---

### Task 10: Frontend Page — Activity Center

**Files:**
- Create: `frontend/src/pages/ActivitiesPage.jsx`
- Modify: `frontend/src/App.jsx` (add route)
- Modify: `frontend/src/components/Navbar.jsx` (add nav item)

**Step 1: Create ActivitiesPage.jsx**

Build a page with:
- Header: "活动任务中心" with points balance badge
- Check-in section: big button showing streak count, daily bonus
- Activity tasks grid: cards showing task name, progress bar, reward, claim button
- Points section: balance, level badge, history list
- Leaderboard sidebar: top 10 users
- Redemption section: exchange points for coins

Use patterns from BountyPage.jsx for layout (header, grid, status badges).
Use dark theme CSS variables from existing codebase.

**Step 2: Add route to App.jsx**

```jsx
const ActivitiesPage = lazy(() => import('./pages/ActivitiesPage'))
// In Routes:
<Route path="/activities" element={<ActivitiesPage userId={userId} authToken={authToken} />} />
```

**Step 3: Add nav item to Navbar.jsx**

```jsx
import { Trophy } from 'lucide-react'
// In navbar-actions:
<button className="btn btn-ghost btn-sm" onClick={() => navigate('/activities')}>
  <Trophy size={16} />
  <span className="btn-text">活动中心</span>
</button>
```

**Step 4: Add CSS to index.css**

Activity center styles: task card grid, check-in button with pulse animation, progress bars, level badges, leaderboard table.

**Step 5: Verify frontend build**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add frontend/src/pages/ActivitiesPage.jsx frontend/src/App.jsx frontend/src/components/Navbar.jsx frontend/src/styles/index.css
git commit -m "feat: add Activity Center page with check-in, tasks, points, leaderboard"
```

---

### Task 11: Frontend Page — My Library Enhancement (Tabs)

**Files:**
- Modify: `frontend/src/pages/MyLibraryPage.jsx`

**Step 1: Add tab navigation**

Add 3 tabs at the top:
1. **我的商品** — existing purchased products list
2. **Cron订阅** — subscribed cron tasks with status, latest result, webhook config
3. **悬赏任务** — accepted bounties with deadline countdown, delivery progress

Each tab renders different content. Use the existing page layout pattern.

**Cron订阅 Tab:**
- Card list of subscriptions: product name, schedule, status badge, expires_at countdown
- Latest result preview (expandable)
- Webhook URL input per subscription
- API Token copy button
- Cancel subscription button

**悬赏任务 Tab:**
- Card list of accepted bounties: title, deadline countdown, status
- Deliver/Submit button
- Progress indicator

**Step 2: Verify frontend build**

**Step 3: Commit**

```bash
git add frontend/src/pages/MyLibraryPage.jsx
git commit -m "feat: enhance My Library with Cron subscriptions and bounty tracking tabs"
```

---

### Task 12: Backend — Smoke Test All New Endpoints

**Step 1: Start backend**

```bash
cd /Users/linan/Desktop/aicode/skillbazaar/backend && python3 main.py
```

**Step 2: Test Cron endpoints**

```bash
# Register + login
TOKEN=$(curl -s http://localhost:8000/api/v2/auth/login -X POST -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Check activities
curl -s http://localhost:8000/api/activities -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Check-in
curl -s http://localhost:8000/api/activities/checkin -X POST -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Points balance
curl -s http://localhost:8000/api/activities/points/balance -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Register a cron (assume product_id=1)
curl -s http://localhost:8000/api/cron/register -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"product_id":1,"schedule_cron":"0 9 * * *","result_format":"json"}' | python3 -m json.tool
```

**Step 3: Test Activity task progress**

```bash
# Publish a product → should increment "publish" tasks
# Buy a product → should increment "spend" tasks
```

**Step 4: Verify all return 200 OK**

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Activity Task Center + Cron Subscription Marketplace complete"
```
