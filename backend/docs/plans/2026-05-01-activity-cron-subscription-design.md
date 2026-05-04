# Activity Task Center + Cron Subscription Marketplace Design

**Goal:** Build a complete infrastructure for Cron task subscription marketplace (publisher-server execution with push+pull delivery) and a dual-layer activity/points system to drive user retention and engagement.

**Architecture:** Publisher servers execute Cron tasks and push results to SkillBazaar via Webhook. Platform distributes results to subscribers via WebSocket + Webhook + API pull. Activity center uses daily check-in + monthly tasks dual-layer points system with level progression.

**Tech Stack:** FastAPI + SQLite (aiosqlite) + Redis Streams + WebSocket + React + Vite

---

## 1. Cron Subscription Marketplace

### 1.1 Data Model

**`cron_products`** — Cron product extension (1:1 with products table)
```
id INTEGER PK
product_id INTEGER FK -> products.id
schedule_cron TEXT          -- cron expression, e.g. "0 9 * * *"
webhook_secret TEXT         -- secret for publisher to authenticate pushes
result_format TEXT          -- json/text/file
status TEXT DEFAULT 'active'  -- active/paused/error
last_executed_at TEXT
avg_duration_ms INTEGER DEFAULT 0
subscriber_count INTEGER DEFAULT 0
execution_count INTEGER DEFAULT 0
created_at TEXT
```

**`cron_subscriptions`** — Subscription relationships
```
id INTEGER PK
cron_product_id INTEGER FK -> cron_products.id
subscriber_id TEXT FK -> users.id
status TEXT DEFAULT 'active'  -- active/expired/cancelled
subscribed_at TEXT
expires_at TEXT              -- subscription period end
monthly_price INTEGER        -- coins per month
webhook_url TEXT             -- subscriber's own callback URL
api_token TEXT UNIQUE        -- token for API pull access
last_result_at TEXT
created_at TEXT
```

**`cron_execution_logs`** — Execution records
```
id INTEGER PK
cron_product_id INTEGER FK
subscription_id INTEGER FK NULL  -- NULL means broadcast to all subscribers
payload TEXT                   -- JSON result data
status TEXT                    -- success/failed/timeout
executed_at TEXT
duration_ms INTEGER
```

**`cron_webhook_deliveries`** — Push delivery records
```
id INTEGER PK
execution_log_id INTEGER FK
target_url TEXT
status TEXT DEFAULT 'pending'  -- pending/sent/failed/retry
response_code INTEGER
attempts INTEGER DEFAULT 0
delivered_at TEXT
```

### 1.2 Core Flow

```
Publisher registers Cron product
  → POST /api/cron/register {product_id, schedule_cron, webhook_secret, result_format}
  → Creates cron_products entry linked to existing product (category=Cron)

Subscriber subscribes
  → POST /api/cron/subscribe/{cron_id}  (deducts monthly coins)
  → Generates api_token, records webhook_url if provided
  → Increments cron_products.subscriber_count

Publisher executes task on their server
  → POST /api/cron/push/{cron_id}
     Headers: X-Webhook-Secret: <secret>
     Body: {payload: {...}, executed_at: "...", duration_ms: 1500}
  → Validates secret, stores execution_log
  → Pushes to all active subscriptions via:
    1. WebSocket (real-time, if subscriber online)
    2. Webhook delivery (to subscriber's webhook_url)
  → Increments execution_count, updates last_executed_at

Subscriber pulls results
  → GET /api/cron/results/{subscription_id}?limit=20
     Headers: Authorization: Bearer <api_token>
  → Returns recent execution_logs for this subscription

Monthly auto-renewal
  → Scheduler checks expiring subscriptions
  → Auto-deducts coins, extends expires_at
  → If insufficient balance: status → expired, notify user
```

### 1.3 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/cron/register | Bearer token | Register Cron product |
| PUT | /api/cron/{cron_id} | Bearer token | Update Cron config |
| POST | /api/cron/push/{cron_id} | Webhook secret | Publisher pushes result |
| POST | /api/cron/subscribe/{cron_id} | Bearer token | Subscribe to Cron |
| GET | /api/cron/results/{sub_id} | API token | Pull execution results |
| PUT | /api/cron/subscription/{sub_id} | Bearer token | Update subscription (webhook_url) |
| DELETE | /api/cron/subscription/{sub_id} | Bearer token | Cancel subscription |
| GET | /api/cron/my-subscriptions | Bearer token | List my subscriptions |
| GET | /api/cron/my-crons | Bearer token | List my published Crons |
| GET | /api/cron/{cron_id}/subscribers | Bearer token | List subscribers (publisher only) |
| GET | /api/cron/{cron_id}/stats | Bearer token | Execution stats |

---

## 2. Activity Task Center — Dual-Layer Points System

### 2.1 Data Model

**`point_accounts`** — User point accounts
```
id INTEGER PK
user_id TEXT FK -> users.id UNIQUE
balance INTEGER DEFAULT 0
total_earned INTEGER DEFAULT 0
total_spent INTEGER DEFAULT 0
level INTEGER DEFAULT 1
continuous_checkin_days INTEGER DEFAULT 0
last_checkin_at TEXT
created_at TEXT
```

**`activities`** — Monthly/weekly activities
```
id INTEGER PK
title TEXT
description TEXT
type TEXT              -- monthly/weekly/special
start_at TEXT
end_at TEXT
banner_image TEXT
status TEXT DEFAULT 'draft'  -- draft/active/ended
created_at TEXT
```

**`activity_tasks`** — Tasks within activities
```
id INTEGER PK
activity_id INTEGER FK -> activities.id
task_key TEXT UNIQUE    -- e.g. "publish_3_skills"
name TEXT
description TEXT
task_type TEXT          -- daily/monthly/achievement
action TEXT             -- publish/buy/subscribe/checkin/apply_bounty/...
target_count INTEGER   -- e.g. 3 for "publish 3 skills"
reward_points INTEGER
reward_coins INTEGER DEFAULT 0
icon TEXT
sort_order INTEGER DEFAULT 0
```

**`user_task_progress`** — Per-user task progress
```
id INTEGER PK
user_id TEXT FK
task_id INTEGER FK -> activity_tasks.id
progress INTEGER DEFAULT 0   -- completed count
completed INTEGER DEFAULT 0  -- boolean
reward_claimed INTEGER DEFAULT 0
created_at TEXT
UNIQUE(user_id, task_id)
```

**`point_transactions`** — Point ledger
```
id INTEGER PK
user_id TEXT FK
amount INTEGER            -- positive=earn, negative=spend
type TEXT                 -- earn/spend
reason TEXT               -- "checkin", "task_reward", "redeem"
ref_type TEXT             -- "task", "checkin", "redeem"
ref_id INTEGER            -- task_id or redemption id
created_at TEXT
```

### 2.2 Daily Layer

| Action | Points | Limit |
|--------|--------|-------|
| Check-in | +10 | 1/day |
| Continuous check-in 7-day bonus | +50 | Weekly |
| Browse product detail | +2 | 5/day max |
| Purchase product | +5 | No limit |
| Leave review | +10 | 3/day max |

### 2.3 Monthly Layer (Activity Tasks)

| Task Key | Target | Reward Points | Reward Coins |
|----------|--------|---------------|--------------|
| publish_3_skills | 3 publishes | 500 | 200 |
| complete_2_bounties | 2 deliveries | 800 | 500 |
| subscribe_5_crons | 5 subscriptions | 300 | 100 |
| receive_5star | 1 five-star review | 600 | 300 |
| invite_3_friends | 3 signups | 1000 | 0 |
| publish_1_cron | 1 Cron publish | 400 | 150 |
| daily_checkin_7 | 7 consecutive days | 200 | 100 |
| spend_1000_coins | 1000 coins spent | 500 | 200 |

### 2.4 Level System

| Level | Title | Points Required | Benefits |
|-------|-------|----------------|----------|
| 1 | 新手 | 0-499 | Base |
| 2 | 熟手 | 500-1999 | 5% fee discount |
| 3 | 专家 | 2000-4999 | 10% fee discount, 10 products max |
| 4 | 大师 | 5000-14999 | 15% fee discount, 20 products max, priority listing |
| 5 | 传奇 | 15000+ | 20% fee discount, unlimited products, featured badge |

### 2.5 Point Redemption

- 100 points = 10 coins
- 500 points = 50 coins + 5% discount coupon
- 2000 points = 200 coins + 1 free Cron subscription month
- Points expire after 12 months of inactivity

### 2.6 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/activities | Public | Current activities list |
| GET | /api/activities/{id}/tasks | Bearer token | Tasks + my progress |
| POST | /api/activities/checkin | Bearer token | Daily check-in |
| POST | /api/activities/tasks/{id}/claim | Bearer token | Claim task reward |
| GET | /api/points/balance | Bearer token | My points + level |
| GET | /api/points/history | Bearer token | Point transaction history |
| POST | /api/points/redeem | Bearer token | Redeem points for coins/coupons |
| GET | /api/points/leaderboard | Public | Top users by points |

### 2.7 Event-Driven Task Tracking

When user actions occur (publish, buy, subscribe, etc.), the system automatically:
1. Records the action as a behavior log (existing `/v2/behavior` endpoint)
2. Checks all active activity_tasks with matching action type
3. Increments `user_task_progress.progress`
4. If `progress >= target_count`: marks completed, sends WebSocket notification
5. When user claims reward: adds points + coins, records point_transaction

---

## 3. My Library Enhancement

### 3.1 Three-Tab Layout

**Tab 1: 我的商品** (existing)
- Purchased products with licenses

**Tab 2: Cron订阅** (new)
- Subscribed Cron tasks with status badges
- Latest execution result per subscription
- Webhook URL configuration per subscription
- API Token copy button
- Execution history with timeline view
- Subscribe/Cancel actions

**Tab 3: 悬赏任务** (new)
- Accepted bounties with deadline countdown
- Delivery progress (developing → submitted → reviewing → approved)
- Overdue warnings (red badge)
- Deliver/Submit buttons

### 3.2 Frontend Pages

- `/activities` — Activity center page (new)
  - Current activity banner
  - Check-in button with streak counter
  - Task grid (completed/available/locked)
  - Points balance + level badge
  - Redemption shop
  - Leaderboard sidebar

- `/library` — Enhanced with tabs (modify existing)

---

## 4. WebSocket Real-Time Push

### 4.1 Architecture

```
Frontend WS Client ←→ FastAPI WebSocket Endpoint
                           ↓
                    WebSocket Manager (in-memory + Redis)
                           ↓
                    Event Bus (Redis Streams)
                           ↓
                    Backend services emit events
```

### 4.2 Connection

- Endpoint: `WS /ws/{user_id}?token=<auth_token>`
- Authentication via JWT token in query param
- Heartbeat: 30s ping/pong
- Auto-reconnect: exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Multi-tab: shared connection via BroadcastChannel API

### 4.3 Event Types

```json
{"type": "cron.result", "data": {"cron_id": 1, "payload": {...}}}
{"type": "subscription.expiring", "data": {"subscription_id": 5, "days_left": 3}}
{"type": "activity.completed", "data": {"task_id": 3, "task_name": "发布3个Skill"}}
{"type": "bounty.deadline", "data": {"bounty_id": 2, "days_left": 1}}
{"type": "level.up", "data": {"new_level": 3, "title": "专家"}}
{"type": "points.earned", "data": {"amount": 50, "reason": "checkin"}}
```

### 4.4 Redis Streams

- Stream: `skillbazaar:events:{user_id}`
- Consumer groups for WebSocket manager
- TTL: 7 days for event history
- Fallback: if Redis unavailable, events stored in SQLite and delivered on next API call

---

## 5. Backend Service Architecture

### New Files

```
backend/
├── services/
│   ├── cron_service.py        # Cron registration, push, subscription management
│   ├── activity_service.py    # Activity/task CRUD, check-in, progress tracking
│   ├── points_service.py      # Points ledger, redemption, level calculation
│   └── notification_service.py # WebSocket push, webhook delivery
├── routers/
│   ├── cron.py                # Cron API endpoints
│   ├── activities.py          # Activity API endpoints
│   └── ws.py                  # WebSocket endpoint
├── database.py                # New tables + helpers
└── models.py                  # New Pydantic models
```

### Modified Files

```
backend/main.py                # Include new routers + WS lifecycle
backend/database.py            # Add new tables
backend/models.py              # Add new models
backend/routers/user_v2.py     # Behavior endpoint triggers task progress
frontend/src/services/api.js   # New API functions
frontend/src/App.jsx           # New routes
frontend/src/components/Navbar.jsx  # Activity center nav item
frontend/src/pages/MyLibraryPage.jsx # Tab enhancement
frontend/src/pages/ActivitiesPage.jsx # New page
frontend/src/styles/index.css  # New styles
```

---

## 6. Implementation Phases

### Phase 1: Database + Core Services (3 days)
- New tables in database.py
- Cron service (register, push, subscribe, results)
- Activity service (CRUD, check-in, progress)
- Points service (ledger, redemption, levels)

### Phase 2: API Routers + Integration (2 days)
- Cron router
- Activities router
- Behavior → task progress auto-tracking
- Monthly auto-renewal scheduler

### Phase 3: WebSocket + Real-Time (2 days)
- WebSocket manager
- Redis Streams integration
- Notification service
- Frontend WebSocket client hook

### Phase 4: Frontend (3 days)
- ActivitiesPage (check-in, tasks, points shop, leaderboard)
- MyLibraryPage tabs (Cron subscriptions, bounty tracking)
- Navbar activity indicator
- Cron product detail enhancement

### Phase 5: Testing + Polish (2 days)
- E2E tests for Cron subscription flow
- E2E tests for activity/points flow
- Performance testing for WebSocket connections
- Bug fixes and polish
