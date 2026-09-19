# SkillBazaar Spec v1(本轮迭代)

> 范围:2-3 个「小而完整、可测试」的改进项 | 日期:2026-09-17 | 依据:README.md、PROJECT_ROADMAP.md、代码实测

## 一、现状盘点(已有能力)

- **商品市场**:`backend/routers/products.py` — 列表/详情/发布/分类,`database.fetch_products` 已支持关键词、价格区间、6 种排序(downloads/rating/price_asc/price_desc/sales/newest),前端 `HomePage.jsx` 已接 sort/价格筛选。
- **机器发现层**:`backend/routers/discovery.py` + `services/discovery_service.py` + `/api/mcp`(JSON-RPC),对外暴露 manifest 与 skill.md。
- **悬赏市场**:`routers/bounties.py` 发布→申请→选人→交付→验收全链路。
- **Cron 订阅**:`routers/cron.py` 注册/订阅/推送/拉取(`/cron/results/{subscription_id}`)/邮件订阅,`cron_execution_logs` 已落库。
- **智能体工作台**:`routers/agents.py` 创建/运行/运行记录(`agent_runs`),前端 `MyLibraryPage.jsx` 已展示。
- **BS 导购助手**:`agents/bs_agent.py`(LangGraph + MemorySaver)、`routers/chat.py` 单接口 `POST /api/chat`。
- **积分/钱包/通知读取**:`routers/activities.py`、`routers/user_v2.py`(含 `GET /api/v2/notifications` 未读数)、`db.insert_notification` 已存在但无业务事件调用。
- **明显缺口**:① rating 全是种子随机数据,无评价表/接口/UI;② BS 助手历史存于进程内 MemorySaver,重启即丢,前端无历史;③ 通知只有读接口,购买/悬赏/Cron 等关键事件不产生通知,前端无消费 UI(PushNotification.jsx 为假定时弹窗)。

## 二、本版目标(3 个改进项)

### 改进项 1:商品评价体系(真实评分闭环)

**动机**:商品 `rating` 由 `database.py:_rand_rating()` 随机生成,用户无法评价;路书 Phase 2「Skill 质量评分—用户评价」以此为前置。

**用户故事**:作为已购用户,我想给买过的 Skill 打分写评价,帮别人决策;作为浏览者,我想在详情页看到真实评价列表。

**功能需求(FR)**:
- FR1 新表 `product_reviews`(id, product_id, user_id, order_ref, rating 1-5, content≤500, created_at;UNIQUE(product_id, user_id))。
- FR2 `POST /api/products/{product_id}/reviews`:仅已购用户可评(`purchases`/licenses 校验),一人一评,重复提交返回 409。
- FR3 `GET /api/products/{product_id}/reviews`:分页返回评价列表(含昵称)与 `{avg_rating, total}`。
- FR4 评价写入后重算均值并回写 `products.rating`(事务内 UPDATE)。
- FR5 `ProductDetailPage.jsx` 新增评价区:展示列表+均分;已购者显示评分表单,未购显示「购买后可评价」。

**接口/页面改动点**:`backend/database.py`(建表 + fetch/insert)、`backend/routers/products.py`(2 个新端点)、`backend/services/product_service.py`(业务逻辑)、`frontend/src/pages/ProductDetailPage.jsx`、`frontend/src/services/api.js`(getProductReviews / createProductReview)。

**边界与非目标**:不做卖家回复、图片评价、审核流;不迁移历史种子评分(种子 rating 保留,随真实评价逐步覆盖)。

**验收标准**:
1. 未购用户 POST 评价 → 403,响应含错误信息;已购用户 POST → 200,GET 可见该条与昵称。
2. 同一用户重复 POST → 409。
3. rating 填 0 或 6 → 422(Pydantic 校验)。
4. 评 1 星后商品列表 `rating` 字段随之变化(与均值一致,误差≤0.1)。
5. 详情页未登录/未购不出现表单,出现引导文案;提交后列表无需刷新即出现新评价。

### 改进项 2:BS 助手会话持久化与历史回看

**动机**:`bs_agent.py` 用 MemorySaver(进程内存),README 宣称「会话持久化」但重启即丢;`ChatPanel.jsx` 刷新即空,多轮导购体验断裂。

**用户故事**:作为买家,我刷新页面或隔天回来,还能看到和 BS 助手的上次对话,继续追问推荐结果。

**功能需求(FR)**:
- FR1 新表 `chat_messages`(id, user_id, role user/assistant, content, card JSON NULL, created_at, thread_id)。
- FR2 `POST /api/chat` 在返回前把用户消息与助手回复(含推荐卡片)各写一行。
- FR3 `GET /api/chat/history?limit=20`:按当前用户返回最近消息(倒序转正序);`DELETE /api/chat/history` 清空并重置 LangGraph thread。
- FR4 `ChatPanel.jsx` 挂载时拉取历史渲染(推荐卡片可回显);新增「清空对话」按钮;空历史保持现有欢迎语。
- FR5 单用户消息上限保护:历史拉取默认 ≤20 条,写入不阻塞主响应(失败仅打日志)。

**接口/页面改动点**:`backend/database.py`(建表+读写)、`backend/routers/chat.py`(2 个新端点)、`backend/services/chat_service.py`(落库)、`frontend/src/components/ChatPanel.jsx`、`frontend/src/services/api.js`(getChatHistory / clearChatHistory)。

**边界与非目标**:不做多会话切换(thread 固定 per user)、不做跨端同步语义保证、不迁移旧内存会话。

**验收标准**:
1. 对话 2 轮 → `chat_messages` 出现 4 行(role 正确,卡片轮含非空 card)。
2. 重启后端进程 → 前端重新打开仍能显示刚才 2 轮对话。
3. 点「清空对话」→ 前端恢复欢迎语,`GET history` 返回空,再发消息 thread 上下文不残留旧话题。
4. 未登录(user_id 为空)调用 history → 401。
5. 历史 20+ 条时,GET 默认只返回最近 20 条且顺序为时间正序。

### 改进项 3:站内通知中心真实化(关键事件触达)

**动机**:`notifications` 表与读取接口(`GET /api/v2/notifications`、未读数、已读)齐全,但仅 operations_service/proactive_agent 写入演示数据;真实交易/悬赏/Cron 事件零触达;前端无任何消费 UI。

**用户故事**:作为卖家,我的 Skill 被购买时想在站内收到通知;作为悬赏主,开发者交付时能立刻知道去验收。

**功能需求(FR)**:
- FR1 三类事件写入通知(复用 `db.insert_notification`):① 购买成功→通知买家+卖家;② 悬赏状态变更(新申请→悬赏主、被选中→申请者、交付提交→悬赏主、验收通过/拒绝→开发者);③ Cron 推送结果→通知订阅者(`cron.py: push` 成功后)。
- FR2 `frontend/src/components/Navbar.jsx` 增加铃铛入口 + 未读数徽标(轮询 60s,登录态才轮询)。
- FR3 下拉列表展示最近 10 条(标题/内容/相对时间),点击单条调 `POST /api/v2/notifications/{id}/read` 并清徽标。
- FR4 全部已读按钮可选(FR3 之外的加分项,不做不阻塞验收)。

**接口/页面改动点**:`backend/services/transaction_service.py`(购买埋点)、`backend/services/bounty_service.py`(4 处埋点)、`backend/routers/cron.py` 或 `services/cron_service.py`(推送埋点)、`frontend/src/components/Navbar.jsx`、新建 `frontend/src/components/NotificationBell.jsx`、`frontend/src/services/api.js`(已有 getNotifications/markNotificationRead 直接复用)。

**边界与非目标**:不做邮件/WebSocket 实时推送、不做通知偏好设置;轮询而非长连接。

**验收标准**:
1. 用户 A 购买用户 B 的商品 → A、B 各收到 1 条通知,类型正确,内容含商品名。
2. 悬赏全流程 4 个节点 → 对应角色各收到对应通知(共≥4 条)。
3. Cron `POST /api/cron/push/{cron_id}` 成功 → 该 cron 全部 active 订阅者各收到 1 条通知。
4. 铃铛未读数与 `unread_count` 一致;点击一条后未读数 -1,再次轮询不回弹。
5. 未登录不显示铃铛;通知接口 401 时不报错、控制台无红字。

## 三、里程碑与依赖

三项相互独立,可并行;建议顺序:1 → 3 → 2(评价依赖最少的表结构,通知复用现成读接口)。全部改动不引入新依赖,SQLite 建表走 `database.py` 现有 `CREATE TABLE IF NOT EXISTS` 模式,零迁移成本。

## 四、后续版本候选池

1. **Cron 订阅到期提醒与一键续订** — `cron_subscriptions.expires_at` 已有字段,前端 MyLibraryPage 已展示;到期前 3 天通知 + 续订按钮。
2. **MCP/discovery 端点对齐排序与价格筛选** — `discovery_service.search_catalog` 未透传 `sort_by/min_price/max_price`,机器侧能力落后于 REST 侧。
3. **Skill 执行成功率展示** — `GET /api/products/{id}/stats`(`skills.py`)已有数据,详情页/卡片展示成功率,衔接 Phase 2 质量评分。
4. **促销码充值前端入口** — `promo_codes` 表与 `rechargeCoins` API(api.js:146)已有,缺 WalletPanel 入口与兑换记录。
5. **沙盒执行队列与超时控制** — `routers/sandbox.py`(345 行)无排队/超时,单机并发 5-8 上限(路书结论),需排队 + 强制回收。
6. **商品收藏夹** — `user_behavior` 已记录 view/buy,补 favorite 行为 + 我的收藏页签。
7. **卖家中心销售趋势图** — `SellerDashboard.jsx` 仅数字卡片,基于 `wallet_transactions` 出 7/30 天趋势。
8. **LLM 调用配额与计费预览** — Phase 2 计费闭环的第一步:Agent 运行前预估消耗、余额不足拦截。
