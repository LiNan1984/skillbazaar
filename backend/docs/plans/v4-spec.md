# SkillBazaar v4 产品需求规格书

> **版本**: 0.1.0-draft  
> **日期**: 2026-09-19  
> **作者**: SkillBazaar PM  
> **状态**: 待评审  

---

## 一、v3 现状回顾

v3 已交付 72 个全量测试，核心能力包括：

| 模块 | 状态 |
|------|------|
| LangGraph BS Copilot (6节点意图路由 + 卡片化表单) | 已上线 |
| 商品目录 (分类/搜索/排序/运行时过滤/compat标签) | 已上线 |
| 悬赏系统 (发布→竞标→选中→交付→验收→打款全流程) | 已上线 |
| Cron 定时任务订阅 (crontab + webhook推送 + 执行日志) | 已上线 |
| 技能资产加密存储 + 异步评估 (静态检查 + LLM冒烟测试) | 已上线 |
| SKILL.md 解析 + Agent-Skills 清单生成 | 已上线 |
| 匿名用户试用执行 (限速) | 已上线 |
| API Key 管理 + CLI 下载 | 已上线 |
| 通知事件系统 | 已上线 |
| 发现服务 / MCP 协议 (外部 Agent 可调用) | 已上线 |
| 活动中心 + 积分 + 签到 + 排行榜 | 已上线 |
| 动态定价模型 + 价格历史 | 已上线 |
| 风险检测 (LLM 内容安全) | 已上线 |
| 用户画像 + 主动推荐 Agent | 已上线 |

**架构栈**: FastAPI + SQLite (aiosqlite) + LangGraph 0.6 + MemorySaver + React + Vite + GLM-5.1 LLM

---

## 二、v4 愿景

> _从 "工具市场" 进化为 "AI 技能生态系统"_ — 让买家轻松找到、试用、购买最适合的技能；让卖家轻松发布、迭代、变现；让平台成为 AI Agent 开发者首选的技能分发渠道。

v4 聚焦 **商业闭环 + 增长飞轮 + 平台信任** 三个维度，选择 7 个最高 ROI 的功能。

---

## 三、功能优先级矩阵

| # | 功能 | 用户价值 | 实现难度 | 优先级 | 预估工期 |
|---|------|---------|---------|--------|---------|
| 1 | 支付系统 (Payment Integration) | ★★★★★ | ★★★★ | **P0** | 3-4 周 |
| 2 | 技能版本管理 (Skill Versioning) | ★★★★ | ★★★ | **P0** | 2 周 |
| 3 | 卖家分析看板 (Seller Analytics) | ★★★★ | ★★★ | **P0** | 2 周 |
| 4 | 用户主页 (User Profile Pages) | ★★★★ | ★★ | **P0** | 1.5 周 |
| 5 | 捆绑包与合集 (Product Bundles) | ★★★★ | ★★ | **P1** | 1.5 周 |
| 6 | 联盟营销系统 (Affiliate Program) | ★★★ | ★★★ | **P1** | 2 周 |
| 7 | 移动端适配 (Mobile / PWA) | ★★★★★ | ★★★ | **P1** | 2-3 周 |

**P0 (必须)**: 支付、版本管理、卖家看板、用户主页  
**P1 (应该)**: 捆绑包、联盟营销、移动端适配

---

## 四、P0 功能详细规格

### 4.1 支付系统 (Payment Integration)

#### 背景
当前交易仅使用内部金币系统 (coins)，无法对接真实货币。卖家收入停留在平台内部，无法提现；买家无法用信用卡/支付宝/微信支付购买。

#### 用户故事
- **卖家**: "我能把赚的金币提现到微信/支付宝吗？"
- **买家**: "我能直接用支付宝买这个 Agent 吗？"
- **平台**: "需要收取交易手续费 (5-10%) 作为营收"

#### 功能规格

**4.1.1 数据库层**

新增表 `payments`:

```sql
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    bounty_id INTEGER REFERENCES bounties(id),
    -- 支付方向: purchase(买家付款) / withdraw(卖家提现)
    direction TEXT NOT NULL CHECK(direction IN ('purchase', 'withdraw')),
    -- 支付渠道: wechat / alipay / stripe / coins(内部金币)
    channel TEXT NOT NULL DEFAULT 'coins',
    -- 渠道交易号 (第三方流水号)
    external_txn_id TEXT,
    -- 金额: 人民币分 (整数); 内部金币支付时填 coins_amount
    amount_cents INTEGER NOT NULL,
    coins_amount INTEGER DEFAULT 0,
    -- 汇率: 1 coins = X cents (用于汇率换算记录)
    exchange_rate REAL DEFAULT 1.0,
    -- 手续费 (平台抽成, 单位: cents)
    platform_fee_cents INTEGER DEFAULT 0,
    -- 状态: pending / processing / completed / failed / refunded / cancelled
    status TEXT DEFAULT 'pending',
    -- 支付网关返回的原始响应
    gateway_response TEXT DEFAULT '{}',
    -- 失败原因
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
    account_info TEXT NOT NULL,  -- 加密存储的收款账号
    status TEXT DEFAULT 'pending',
    processed_at TEXT,
    admin_note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    channel TEXT NOT NULL,  -- wechat / alipay / stripe
    account_ref TEXT NOT NULL,  -- 渠道侧账号标识 (脱敏)
    account_name TEXT DEFAULT '',
    is_verified INTEGER DEFAULT 0,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
```

**4.1.2 服务层 (`services/payment_service.py`)**

```python
# 核心接口
async def create_payment_order(user_id, product_id, channel, amount_cents) -> dict
async def query_payment_status(payment_id) -> dict
async def handle_payment_callback(channel, payload) -> dict  # 异步回调处理
async def request_withdrawal(user_id, amount_coins, channel, account_info) -> dict
async def get_payment_history(user_id, page, page_size) -> dict
async def get_earnings_summary(user_id) -> dict  # 总收入/可提现/已提现
```

**4.1.3 路由层 (`routers/payments.py`)**

```
POST   /api/payments/orders         创建支付订单
GET    /api/payments/orders/{id}    查询订单状态
POST   /api/payments/callback/{channel}  支付回调 (webhook)
POST   /api/payments/withdraw       申请提现
GET    /api/payments/history        交易历史
GET    /api/payments/earnings       收益概览
POST   /api/payments/methods        添加收款方式
GET    /api/payments/methods        收款方式列表
DELETE /api/payments/methods/{id}   删除收款方式
```

**4.1.4 适配现有交易流程**

修改 `services/transaction_service.py::buy_product`:
- 检测买家是否有足够金币
- 金币不足时跳转到支付订单创建
- 支付成功后扣减商品价格对应的金币 (或直接走真实支付)
- 卖家收入记录为 "待提现" 余额

**4.1.5 与现有架构的对齐**

| 现有模式 | v4 支付对齐 |
|---------|------------|
| `services/notification_service.py` 的 `notify()` | 支付成功/失败通知 |
| `database.wallet_transactions` 表 | 保留作为内部流水，新增 `payments` 作为真实支付 |
| `services/risk_detector.py` | 大额提现前二次风控扫描 |
| `routers/user_v2.py` 的 `get_current_user` | 支付路由复用 auth |

#### 验收标准
- [ ] 买家可用支付宝/微信/Stripe 创建支付订单
- [ ] 支付回调正确更新订单状态并发放商品
- [ ] 卖家可申请提现到绑定账户
- [ ] 平台自动扣除 5% 手续费
- [ ] 支付历史可按时间筛选分页
- [ ] 大额提现 (>1000 CNY) 触发风控审核
- [ ] 72 个现有测试全部通过 (不破坏已有功能)

---

### 4.2 技能版本管理 (Skill Versioning)

#### 背景
当前商品只有单一版本。卖家更新技能后，已购买用户获得的是最新版，无法回退；也无法区分 "v1.0 稳定版" 和 "v2.0 beta 版"。

#### 用户故事
- **卖家**: "我发布了一个新版，但老用户想继续用 v1.0"
- **买家**: "买的时候是 v1.2，现在卖家发了 v2.0，我需要确认兼容性"
- **平台**: "版本历史应该可追溯，便于审计和回滚"

#### 功能规格

**4.2.1 数据库层**

```sql
CREATE TABLE IF NOT EXISTS product_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    version TEXT NOT NULL,        -- semver: "1.0.0", "2.1.0-beta"
    changelog TEXT DEFAULT '',
    compat_override TEXT,         -- JSON: 覆盖继承的 compat 列表
    -- 版本状态: released / beta / deprecated / yanked
    status TEXT DEFAULT 'released',
    encrypted_blob BLOB,
    encryption_iv TEXT,
    encryption_salt TEXT,
    content_hash TEXT,
    file_size INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    created_by TEXT NOT NULL REFERENCES users(id),
    UNIQUE(product_id, version)
);

-- 用户的许可证关联到具体版本
ALTER TABLE licenses ADD COLUMN version_id INTEGER 
    REFERENCES product_versions(id);
```

**4.2.2 服务层**

```python
# services/versioning_service.py
async def create_version(product_id, user_id, version, changelog, file_bytes, compat_override) -> dict
async def get_product_versions(product_id) -> list[dict]
async def get_latest_version(product_id, status='released') -> dict
async def get_version(product_id, version) -> dict | None
async def yank_version(version_id, user_id) -> dict  # 撤回有问题的版本
async def get_user_licensed_versions(user_id, product_id) -> list  # 用户持有的版本
```

**4.2.3 路由层**

```
POST   /api/products/{id}/versions          创建新版本
GET    /api/products/{id}/versions          版本列表
GET    /api/products/{id}/versions/{ver}    版本详情
POST   /api/products/{id}/versions/{ver}/yank  撤回版本
GET    /api/my-library/versions             我的授权版本列表
```

**4.2.4 与现有架构的对齐**

| 现有模式 | v4 版本管理对齐 |
|---------|----------------|
| `services/skill_vault.py` 加密 | 每个版本独立加密 blob |
| `services/eval_service.py` 评估 | 新版本上传后自动触发异步评估 |
| `services/manifest_service.py` | 版本清单继承 + compat_override |
| `routers/products.py` create | 首次上传自动创建 v1.0.0 |
| `SkillAssetResponse.version` 字段 | 升级为关联 `product_versions` |

#### 验收标准
- [ ] 卖家发布商品时自动创建 v1.0.0
- [ ] 卖家可上传新版本并填写 changelog
- [ ] 已购买用户可选择继续使用旧版本或升级
- [ ] `beta` 状态版本仅在卖家主动分享时可见
- [ ] `yanked` 版本不可下载，已授权用户自动降级到最新非 yanked 版本
- [ ] 版本列表 API 返回兼容性信息
- [ ] 新版本上传触发异步评估 (复用 v3 eval_service)

---

### 4.3 卖家分析看板 (Seller Analytics Dashboard)

#### 背景
当前卖家没有任何数据可见性 — 不知道商品被浏览多少次、转化率如何、用户从哪里来。

#### 用户故事
- **卖家**: "我的商品上周有多少人看？多少人买了？"
- **卖家**: "搜索 '交易策略' 的用户有多少人最终买了我的商品？"

#### 功能规格

**4.3.1 数据库层**

```sql
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
```

**4.3.2 服务层**

```python
# services/analytics_service.py
async def record_view(product_id, user_id, source, session_id) -> None
async def get_seller_dashboard(user_id, period='30d') -> dict
async def get_product_analytics(product_id, period='30d') -> dict
async def get_top_products(user_id, metric='revenue', limit=10) -> list
```

**4.3.3 路由层**

```
GET    /api/seller/dashboard              卖家总览 (所有商品聚合)
GET    /api/seller/products/{id}/analytics 单商品分析
GET    /api/seller/analytics/export       导出 CSV
```

**4.3.4 看板指标**

| 指标 | 说明 |
|------|------|
| 总浏览量 (Views) | 商品详情页 UV |
| 转化率 | purchases / views |
| 收入趋势 | 按日的收入折线图 |
| 流量来源 | 搜索/聊天/直接/引荐占比 |
| 搜索关键词 | 带来点击的搜索词 TOP 10 |
| 聊天提及次数 | BS Copilot 推荐该商品的次数 |
| 评分趋势 | 近 30 天评分变化 |

**4.3.5 与现有架构的对齐**

| 现有模式 | v4 分析对齐 |
|---------|------------|
| `services/proactive_agent.py` 的 `track_user_action` | 扩展 action 类型: `view_product` |
| `user_behavior` 表 | 保留原始行为日志，analytics 表为聚合物化视图 |
| `routers/user_v2.py` | 新增 seller 角色验证中间件 |

#### 验收标准
- [ ] 卖家可查看近 7/30/90 天的商品分析
- [ ] 分析页面展示核心指标 (浏览量/转化率/收入/评分)
- [ ] 流量来源饼图 (搜索/聊天/直接/引荐)
- [ ] 支持导出 CSV
- [ ] 商品详情页浏览量实时记录 (不阻塞主流程)

---

### 4.4 用户主页 (User Profile Pages)

#### 背景
当前买家看不到卖家的历史记录和信誉。市场上最重要的是信任 — 用户需要知道 "这个卖家之前卖过什么？评价怎么样？"

#### 用户故事
- **买家**: "看看这个卖家的其他商品和评分"
- **买家**: "这个卖家可靠吗？卖了多久了？"
- **卖家**: "我的个人主页需要展示我的专业形象"

#### 功能规格

**4.3.1 数据库层**

扩展 `user_profiles` 表:

```sql
ALTER TABLE user_profiles ADD COLUMN display_name TEXT;
ALTER TABLE user_profiles ADD COLUMN bio TEXT DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN location TEXT DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN website_url TEXT DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN avatar_url TEXT DEFAULT '';
ALTER TABLE user_profiles ADD COLUMN social_links TEXT DEFAULT '{}';  -- {"github": "...", "twitter": "..."}
ALTER TABLE user_profiles ADD COLUMN badges TEXT DEFAULT '[]';       -- ["top_seller", "verified", "early_adopter"]
ALTER TABLE user_profiles ADD COLUMN verified INTEGER DEFAULT 0;
```

新增表:

```sql
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
    badge TEXT NOT NULL,        -- top_seller / verified / early_adopter / prolific_developer
    awarded_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, badge)
);
```

**4.3.2 服务层**

```python
# services/profile_service.py
async def get_public_profile(user_id, viewer_id=None) -> dict
async def update_profile(user_id, data) -> dict
async def follow_user(follower_id, following_id) -> dict
async def unfollow_user(follower_id, following_id) -> dict
async def get_followers(user_id, page, page_size) -> dict
async def get_following(user_id, page, page_size) -> dict
async def check_following(user_id, target_id) -> bool
```

**4.3.3 路由层**

```
GET    /api/u/{username}               公开用户主页
GET    /api/u/{username}/products      该用户的商品列表
GET    /api/u/{username}/followers     粉丝列表
GET    /api/u/{username}/following     关注列表
POST   /api/u/{username}/follow        关注
DELETE /api/u/{username}/follow        取消关注
GET    /api/profile/me                 当前用户资料 (编辑用)
PATCH  /api/profile/me                 更新资料
```

**4.3.4 主页展示内容**

```
┌──────────────────────────────────────┐
│  [Avatar]  Seller Name        [Follow] │
│  @username · 加入于 2024-03 · 📍上海   │
│  ─────────────────────────────────── │
│  Bio: 专注交易 Agent 开发，5年经验...   │
│  🏆 徽章: Top Seller | Verified       │
│                                      │
│  Stats:  12 商品 | 4.8 评分 | 1.2k 销售 │
│                                      │
│  ┌─────┐ ┌─────┐ ┌─────┐            │
│  │Item1│ │Item2│ │Item3│  (商品网格)  │
│  └─────┘ └─────┘ └─────┘            │
└──────────────────────────────────────┘
```

**4.3.5 与现有架构的对齐**

| 现有模式 | v4 主页对齐 |
|---------|------------|
| `user_profiles` 表 | 扩展字段 |
| `routers/users.py` | 用户名路由别名 |
| `services/notification_service.py` | 关注时发送通知 |
| `user_agents` 表 | 卖家的公开 Agent 可嵌入主页 |

#### 验收标准
- [ ] 每个用户有唯一公开主页 (`/u/{username}`)
- [ ] 主页展示头像、简介、统计数据、徽章
- [ ] 展示该用户的所有在架商品
- [ ] 支持关注/取消关注
- [ ] 关注后收到通知
- [ ] 卖家可编辑个人资料
- [ ] 未登录用户可浏览公开主页

---

## 五、P1 功能详细规格

### 5.1 捆绑包与合集 (Product Bundles)

#### 背景
单个技能售价通常在 50-200 金币，客单价低。通过捆绑相关技能可以提供折扣，提升客单价 3-5 倍。

#### 功能规格

**数据库层**

```sql
CREATE TABLE IF NOT EXISTS product_bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    bundle_price INTEGER NOT NULL,       -- 捆绑价 (金币)
    original_price INTEGER NOT NULL,     -- 原价总和
    discount_percent REAL DEFAULT 0,     -- 折扣百分比
    icon TEXT,
    status TEXT DEFAULT 'active',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bundle_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_id INTEGER NOT NULL REFERENCES product_bundles(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    sort_order INTEGER DEFAULT 0,
    UNIQUE(bundle_id, product_id)
);
```

**路由层**

```
POST   /api/bundles               创建合集
GET    /api/bundles               合集列表 (支持分类过滤)
GET    /api/bundles/{id}          合集详情 (含商品列表)
POST   /api/bundles/{id}/items    添加商品到合集
DELETE /api/bundles/{id}/items/{pid}  从合集移除
POST   /api/bundles/{id}/purchase 一键购买合集
```

**与 Copilot 集成**

在 BS Copilot 的 `do_search` 节点中，当检测到用户想购买多个相关技能时，推荐匹配的合集：
- 搜索 "交易" → 返回交易相关合集 (价格更低)
- ChatPanel 渲染 `BundleCard` 组件 (继承 `chat-card` 样式)

#### 验收标准
- [ ] 卖家可创建合集 (2-6 个商品)
- [ ] 合集展示原价和折扣价
- [ ] 一键购买合集 (原子事务: 扣款 → 授权所有子商品)
- [ ] 聊天中推荐匹配的合集
- [ ] 合集详情页展示包含商品列表

---

### 5.2 联盟营销系统 (Affiliate Program)

#### 背景
当前没有推荐机制。联盟营销是 SaaS/数字产品增长的标准做法 — 让 KOL/活跃用户通过推荐链接赚取佣金。

#### 功能规格

**数据库层**

```sql
CREATE TABLE IF NOT EXISTS affiliate_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    user_id TEXT NOT NULL REFERENCES users(id),  -- 推广人
    code TEXT UNIQUE NOT NULL,                    -- 推广码 (e.g. "alice-abc12")
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    earnings_cents INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now)')
);

CREATE TABLE IF NOT EXISTS affiliate_commissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL REFERENCES affiliate_links(id),
    buyer_id TEXT NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL,
    sale_amount_cents INTEGER NOT NULL,
    commission_rate REAL NOT NULL,      -- 0.05 ~ 0.30 (5%-30%)
    commission_cents INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',      -- pending / paid / cancelled
    paid_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS affiliate_tiers (
    tier TEXT PRIMARY KEY,  -- bronze / silver / gold / platinum
    min_conversions INTEGER NOT NULL,
    commission_rate REAL NOT NULL
);
-- 初始数据
INSERT OR IGNORE INTO affiliate_tiers VALUES ('bronze', 0, 0.10);
INSERT OR IGNORE INTO affiliate_tiers VALUES ('silver', 20, 0.15);
INSERT OR IGNORE INTO affiliate_tiers VALUES ('gold', 100, 0.20);
INSERT OR IGNORE INTO affiliate_tiers VALUES ('platinum', 500, 0.30);
```

**路由层**

```
POST   /api/affiliate/links          创建推广链接
GET    /api/affiliate/links          我的推广链接列表
GET    /api/affiliate/links/{code}   推广详情 (公开)
GET    /api/affiliate/earnings       收益概览
GET    /api/affiliate/commissions    佣金明细
GET    /api/affiliate/leaderboard    推广排行榜
POST   /api/affiliate/withdraw       佣金提现 (合并到支付系统)
```

**追踪机制**

```python
# 推广链接格式: /product/{id}?ref={code}
# 通过 discovery 路由中间件追踪:
async def track_affiliate_click(request, product_id, ref_code):
    link = await db.fetch_affiliate_link_by_code(ref_code)
    if link:
        await db.increment_affiliate_clicks(link["id"])
        request.state.affiliate_link_id = link["id"]  # 传递给购买流程
```

**与 Copilot 集成**

BS Copilot 在推荐商品时，如果该商品有活跃推广链接，生成 `AffiliateCard`:
```
┌──────────────────────────────┐
│ 💰 专属推荐                    │
│ [商品封面] 交易策略 Agent        │
│ 价格: ¥99  |  推广人: @alice    │
│ 通过此链接购买可支持推广人       │
│ [通过此链接购买]               │
└──────────────────────────────┘
```

#### 验收标准
- [ ] 用户可为自己推广的商品创建推广链接
- [ ] 推广链接追踪点击和转化
- [ ] 佣金按 tier 阶梯比例自动计算
- [ ] 推广排行榜 (按转化数/收入排名)
- [ ] 佣金可合并提现

---

### 5.3 移动端适配 (Mobile / PWA)

#### 背景
当前前端为桌面 H5 设计，在移动端存在排版问题。预计 60-70% 的用户通过手机/平板访问。

#### 功能规格

**5.3.1 响应式布局改造**

重点改造的页面/组件:

| 组件/页面 | 当前问题 | v4 改造 |
|----------|---------|---------|
| `ChatPanel.jsx` | 卡片在小屏溢出 | 移动端全屏模式 + 底部输入栏 |
| `HomePage.jsx` | 商品网格固定 4 列 | 响应式: 1/2/3/4 列 |
| `ProductDetailPage.jsx` | 信息密度过高 | 折叠区 + sticky 购买按钮 |
| `Navbar.jsx` | 无移动端汉堡菜单 | 汉堡菜单 + 底部 Tab 栏 |
| `BountyCard.jsx` (chat) | 表单字段挤在一行 | 移动端堆叠排列 |

**5.3.2 PWA 配置**

```javascript
// vite.config.js - 新增 PWA 插件
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png'],
      manifest: {
        name: 'SkillBazaar - AI 技能市场',
        short_name: 'SkillBazaar',
        description: 'AI Agent/Skill/Cron 交易市场',
        theme_color: '#6366f1',
        background_color: '#0f172a',
        display: 'standalone',
        orientation: 'any',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ]
      },
      workbox: {
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/api\./,
            handler: 'NetworkFirst',
            options: { cacheName: 'api-cache', expiration: { maxEntries: 50, maxAgeSeconds: 300 } }
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: 'CacheFirst',
            options: { cacheName: 'images', expiration: { maxEntries: 100 } }
          }
        ]
      }
    })
  ]
})
```

**5.3.3 关键交互优化**

```css
/* 移动端底部安全区适配 */
.chat-input-area {
  padding-bottom: env(safe-area-inset-bottom, 0);
}

/* 移动端全屏聊天 */
@media (max-width: 640px) {
  .chat-panel.open {
    position: fixed;
    inset: 0;
    z-index: 100;
    border-radius: 0;
  }
}

/* 底部 Tab 栏 (移动端) */
.mobile-tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: var(--bg-surface-1);
  border-top: 1px solid var(--border);
  display: none;
}

@media (max-width: 768px) {
  .mobile-tab-bar { display: flex; }
}
```

**5.3.4 SEO 基础 (与移动端联动)**

```html
<!-- index.html head -->
<meta name="description" content="SkillBazaar - AI Agent、Skill、Cron 交易市场" />
<meta property="og:title" content="SkillBazaar" />
<meta property="og:description" content="发现最好的 AI 技能" />
<meta property="og:image" content="/og-image.png" />
<meta name="theme-color" content="#6366f1" />
<link rel="canonical" href="https://skillbazaar.ai/" />
```

**5.3.5 与现有架构的对齐**

| 现有模式 | v4 移动端对齐 |
|---------|-------------|
| `frontend/src/styles/index.css` | 已有响应式基础样式，扩展移动端断点 |
| `frontend/vite.config.js` | 添加 VitePWA 插件 |
| `FloatingAssistant.jsx` | 移动端改为底部 FAB 按钮 |
| `services/discovery_service.py` | 服务端渲染 (SSR) 为后续 SEO 打基础 |

#### 验收标准
- [ ] 所有页面在 375px (iPhone SE) 宽度下正常显示
- [ ] 聊天面板在移动端全屏展示
- [ ] PWA 可添加到主屏幕
- [ ] 离线可浏览已缓存的商品列表
- [ ] 移动端 Lighthouse Performance > 80
- [ ] 底部 Tab 栏导航 (首页/发现/发布/消息/我的)

---

## 六、跨功能需求

### 6.1 测试策略

```
v4 目标: 80%+ 测试覆盖率 (继承 v3 的 72 个测试)
新增测试:
  tests/test_payment_service.py      (~15 tests)
  tests/test_versioning_service.py   (~10 tests)
  tests/test_analytics_service.py    (~8 tests)
  tests/test_profile_service.py      (~8 tests)
  tests/test_bundle_service.py       (~6 tests)
  tests/test_affiliate_service.py    (~10 tests)
  tests/test_mobile_api.py           (~5 tests)
```

### 6.2 数据库迁移

```bash
# scripts/migrate_v4.py
# 所有 v4 新增表通过 CREATE TABLE IF NOT EXISTS + ALTER TABLE 实现
# 向后兼容: v3 数据无需迁移，v4 功能可选启用
```

### 6.3 API 兼容性

- 所有新增路由挂载在 `/api/` 前缀下，不修改现有路由签名
- 现有 `ProductResponse` 通过继承/扩展字段实现向后兼容
- 支付/版本等新功能通过 feature flag 控制

### 6.4 性能要求

| 指标 | 目标 |
|------|------|
| API p95 延迟 | < 200ms (不含 LLM 调用) |
| 支付回调处理 | < 500ms |
| 卖家看板数据聚合 | < 1s (30天范围) |
| 联盟链接跳转 | < 100ms |
| 前端首屏加载 (移动端) | < 3s |

---

## 七、实施路线图

```
Phase 1 (Weeks 1-4):   P0-1 支付系统 (支付+提现+手续费)
Phase 2 (Weeks 3-4):   P0-2 技能版本管理 (并行)
Phase 3 (Weeks 5-6):   P0-3 卖家分析看板 + P0-4 用户主页 (并行)
Phase 4 (Weeks 7-8):   P1-1 捆绑包 + P1-2 联盟营销 (并行)
Phase 5 (Weeks 9-11):  P1-3 移动端适配 + SEO
```

每个 Phase 结束后执行:
1. 单元测试 + 集成测试 (目标: 新增功能 80% 覆盖率)
2. 现有 72 个 v3 测试全量通过 (回归)
3. API 契约验证 (OpenAPI schema diff)
4. 功能开关切换验证

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 支付渠道对接复杂度 | 延期 1-2 周 | Phase 1 先做 "内部金币→微信/支付宝" 最小可行支付，Stripe 后续补充 |
| SQLite 并发写入瓶颈 | 性能下降 | 分析/联盟等写密集操作用批量 + 异步队列 |
| 移动端适配碎片化 | 体验不一致 | 采用 Tailwind 响应式 + 少量自定义断点，统一设计 token |
| 卖家冷启动 (无分析数据) | 看板空数据 | 上线前预填充 30 天模拟数据 |
| 联盟推广被滥用 | 虚假佣金 | 设置购买后 7 天结算窗口，退款自动取消佣金 |

---

## 九、成功指标 (v4 Launch Criteria)

| 指标 | 目标 |
|------|------|
| 支付成功率 | > 95% |
| 版本切换零停机 | 100% |
| 卖家看板数据准确性 | > 99% |
| 移动端可用性 (Lighthouse) | > 80 |
| 联盟转化率 | > 3% |
| 捆绑包客单价提升 | > 2.5x |
| 回归测试通过率 | 100% (72/72) |

---

## 附录 A: 与 v3 架构模式对照

| v3 模式 | v4 应用 |
|---------|---------|
| `services/*_service.py` 单职责服务 | v4 新增 `payment_service`, `versioning_service`, `analytics_service`, `profile_service`, `bundle_service`, `affiliate_service` |
| `database.py` 集中式 SQL | 新增表通过 `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` |
| `models.py` Pydantic schema | 新增对应 Request/Response model |
| `routers/*.py` APIRouter | 新增 `payments.py`, `versions.py`, `analytics.py`, `profiles.py`, `bundles.py`, `affiliate.py` |
| `services/notification_service.py` 事件通知 | 支付/关注/版本发布等场景复用 notify() |
| `services/risk_detector.py` 风控 | 大额提现前调用风控扫描 |
| `agents/nodes.py` LangGraph 节点 | 搜索节点增加捆绑包/AffiliateCard 渲染逻辑 |
| `services/manifest_service.py` 清单派生 | 版本化清单继承 + compat override |

---

## 附录 B: 数据流图 (支付系统)

```
买家                    平台                      卖家
  │                      │                        │
  │── 选择商品 ──────────►│                        │
  │                      │── 创建支付订单 ────────►│
  │                      │   (status=pending)      │
  │◄── 返回支付参数 ──────│                        │
  │                      │                        │
  │── 完成支付 ──────────►│                        │
  │   (支付宝/微信回调)    │                        │
  │                      │── 验证回调签名 ────────►│
  │                      │── 扣款 + 手续费 ───────►│
  │                      │── 授权商品 ────────────►│
  │◄── 支付成功通知 ──────│                        │
  │                      │                        │
  │                      │◄── 申请提现 ───────────│
  │                      │── 风控审核 ────────────│
  │                      │── 打款 ───────────────►│
  │                      │── 通知到账 ────────────►│
```

---

## 附录 C: 参考文档

- v3 架构计划: `docs/plans/2026-05-01-bs-copilot-plan.md`
- BS Copilot 设计: `docs/plans/2026-05-01-bs-copilot-design.md`
- 活动/订阅计划: `docs/plans/2026-05-01-activity-cron-subscription-plan.md`
- 活动/订阅设计: `docs/plans/2026-05-01-activity-cron-subscription-design.md`
