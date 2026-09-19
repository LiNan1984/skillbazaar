# SkillBazaar Spec v1 测试案例文档

> 对应需求文档:`docs/agent-team/spec.md`(改进项 1 商品评价 / 改进项 2 BS 助手会话持久化 / 改进项 3 通知中心真实化)
> 日期:2026-09-17 | 案例总数:25(P0 17 条,P1 8 条)| 编写人:QA agent

## 0. 通用约定

### 0.1 后端自动化测试风格(与 `backend/tests/` 现有风格一致)

- 框架:`unittest.TestCase`(pytest 可直接收集运行),`fastapi.testclient.TestClient` 打真实 app。
- 数据库:每个测试文件 `setUpClass` 用 `tempfile.NamedTemporaryFile` 替换 `database.DB_PATH`(参考 `tests/test_user_mgmt.py:18-24`),**不用生产 DB**,不 mock 被测路由/服务。
- 鉴权:`POST /api/v2/auth/register` + `/login` 拿 token,请求头 `{"Authorization": f"Bearer {token}"}`。
- 运行方式:
  ```bash
  cd backend && python -m pytest tests/test_product_reviews.py tests/test_chat_history.py tests/test_notification_events.py -v
  ```
- 新增测试文件(3 个,全部可在实现开始前先行落库,初始应为 RED):
  - `backend/tests/test_product_reviews.py`
  - `backend/tests/test_chat_history.py`
  - `backend/tests/test_notification_events.py`

### 0.2 测试先行(TDD)说明

| 可否先行 | 范围 |
|---|---|
| **实现前全部可写(RED)** | 所有标注「可自动化」的后端案例(共 19 条)。接口契约(路径、方法、状态码、响应字段)已由 spec 冻结;购买/悬赏/Cron 的前置流程走现有端点,只需在流程末端断言新表/新通知,实现未完成时断言必然失败 |
| **需实现后手动执行** | 所有前端案例(共 6 条),均为手动验收步骤,无法先于 UI 实现 |

---

## 一、改进项 1:商品评价体系(9 条;后端 7 + 前端 2)

接口基线:`POST /api/products/{product_id}/reviews`、`GET /api/products/{product_id}/reviews`;新表 `product_reviews`。
建议测试文件:`backend/tests/test_product_reviews.py`,类 `TestProductReviews`。

### R-01 [P0] 已购用户发表评价成功并可被查询(可自动化)

- **前置条件**:用户 seller 发布商品 P(或用种子商品);用户 buyer 注册登录,并通过 `POST /api/transactions/buy` 完成购买。
- **请求**:`POST /api/products/{P}/reviews`,Header 带 buyer token;Body `{"rating": 5, "content": "很好用,推荐"}`。
- **期望响应**:HTTP 200;Body 含新评价 `id`、`rating=5`、`content`、买家昵称、`created_at`。
- **断言点**:
  1. 随后 `GET /api/products/{P}/reviews` 200,`items`(或 `reviews`)中含该条且 `nickname` 为买家昵称;
  2. `summary.total == 1`、`summary.avg_rating == 5.0`;
  3. 直连临时库查 `product_reviews` 恰有 1 行,`user_id == buyer_id`。
- **pytest**:`test_product_reviews.py::TestProductReviews::test_purchased_user_can_create_review`

### R-02 [P0] 未登录发表评价被拒(可自动化)

- **前置条件**:存在商品 P;无 Authorization 头。
- **请求**:`POST /api/products/{P}/reviews`,Body `{"rating": 4, "content": "x"}`。
- **期望响应**:HTTP 401。
- **断言点**:状态码 401(与现有 `get_current_user` 行为一致,参考 `test_user_mgmt.py:147-148`);库中无新行。
- **pytest**:`...::test_anonymous_review_rejected`

### R-03 [P0] 未购买用户发表评价返回 403(可自动化)

- **前置条件**:用户 buyer 登录但与 P 无任何 purchase/license 记录。
- **请求**:同 R-01。
- **期望响应**:HTTP 403,Body 含错误信息(spec 验收 1 要求"响应含错误信息")。
- **断言点**:403 且 JSON 中存在 message/detail 字段;`product_reviews` 无该用户行。
- **pytest**:`...::test_non_buyer_review_forbidden`

### R-04 [P0] 同一用户重复评价返回 409(可自动化)

- **前置条件**:R-01 已完成(buyer 已对 P 评过一次)。
- **请求**:buyer 再次 `POST /api/products/{P}/reviews`,`{"rating": 1, "content": "改主意了"}`。
- **期望响应**:HTTP 409。
- **断言点**:409;库中该 (product_id, user_id) 仍只有 1 行(UNIQUE 约束 + 服务层预检各防一道);`products.rating` 未被第二次提交改变。
- **pytest**:`...::test_duplicate_review_conflict`

### R-05 [P0] 参数非法:rating 越界 / content 超长 → 422(可自动化)

- **前置条件**:同 R-01 的已购 buyer。
- **请求**(子例参数化,数据驱动 4 组):
  1. `{"rating": 0, "content": "ok"}`
  2. `{"rating": 6, "content": "ok"}`
  3. `{"rating": "5", "content": "ok"}`(类型非法,若 Pydantic 为 int 严格模式)
  4. `{"rating": 5, "content": "x"*501}`
- **期望响应**:全部 HTTP 422(Pydantic 校验,spec 验收 3)。
- **断言点**:422;库中无任何新行;均值未变化。
- **pytest**:`...::test_invalid_rating_and_content_422`(用 `subTest` 覆盖 4 组入参)

### R-06 [P0] 评价写入后商品均分在事务内回写(可自动化)

- **前置条件**:买家 b1、b2 均已购买 P;P 种子/初始 rating 记为 `r0`。
- **请求**:b1 评 1 星,b2 评 3 星(各一次成功 POST)。
- **期望响应**:两次 POST 均 200。
- **断言点**:
  1. `GET /api/products/{P}` 与商品列表接口中 `rating == 2.0`(均值,误差 ≤ 0.1,对齐 spec 验收 4;一星单评场景即 |rating-1.0|≤0.1);
  2. `GET reviews` 的 `summary.avg_rating` 与 `products.rating` 一致;
  3. 校验评价插入与 UPDATE 为同一事务(可在评审中核对代码;自动化侧以"两值恒一致"间接保证,无中间态泄漏)。
- **pytest**:`...::test_review_recomputes_product_rating`

### R-07 [P1] 评价列表分页/汇总/404/公开可读(可自动化)

- **前置条件**:3 个已购用户对 P 分别评价;另有不存在的商品 id `999999`。
- **请求**:
  1. `GET /api/products/{P}/reviews?page=1&page_size=2`(不带 token)
  2. `GET /api/products/{P}/reviews?page=2&page_size=2`
  3. `GET /api/products/999999/reviews`
- **期望响应**:
  1. 200,返回 2 条,带分页字段(total/pages 或 has_next),`summary.avg_rating/total` 正确;
  2. 200,返回剩余 1 条;
  3. 404。
- **断言点**:未登录 GET 200(浏览者可见);分页条数与页码正确;404 针对不存在商品。
- **pytest**:`...::test_review_list_pagination_summary_and_404`

### R-08 [P0] 前端:详情页评价区显隐与引导文案(手动)

- **步骤**:
  1. 未登录打开任一商品详情页 → 评价区显示列表与均分,**不出现**评分表单,显示"购买后可评价"类引导(spec 验收 5);
  2. 登录一个未购买该商品的账号 → 仍无表单,引导文案在;
  3. 登录一个已购买账号 → 出现星级选择 + 文本框 + 提交按钮;
  4. 已评过的账号再进详情页 → 表单替换为"我的评价"展示,不允许再次提交。
- **期望**:四种身份看到的 UI 与上述一致;不发多余的 403 请求(已购状态应驱动渲染而非提交后报错)。

### R-09 [P1] 前端:提交后评价即时出现(手动)

- **步骤**:已购用户在详情页选 5 星、输入内容、点提交。
- **期望**:无需手动刷新页面,新评价即时插入列表顶部/尾部,均分与总条数即时更新;提交期间按钮有 loading/禁用态,防重复点击;成功后表单消失或变为"我的评价"。

---

## 二、改进项 2:BS 助手会话持久化(8 条;后端 6 + 前端 2)

接口基线:`POST /api/chat`(改造,落库)、`GET /api/chat/history`、`DELETE /api/chat/history`;新表 `chat_messages`。
约定:history 两端点按 spec 验收 4 使用 Bearer token 鉴权(现有 `POST /api/chat` 仍从 body 取 `user_id`,测试照现状调用)。
建议测试文件:`backend/tests/test_chat_history.py`,类 `TestChatHistory`。

### C-01 [P0] 两轮对话落库 4 行,role 与 card 正确(可自动化)

- **前置条件**:用户 u 登录;准备一条会触发推荐卡片的消息(如"推荐一个 Python 代码审查 skill"),以及一条普通追问。
- **请求**:按顺序两次 `POST /api/chat`,body 带 `user_id=u`,第一次预期返回 `products` 非空。
- **期望响应**:两次均 200,`reply` 非空。
- **断言点**(直连临时库查 `chat_messages`):
  1. 共 4 行,role 依次为 `user/assistant/user/assistant`,`user_id` 全为 u,`thread_id` 同一值;
  2. 助手回复的 content 与响应 `reply` 一致;
  3. 卡片轮的 assistant 行 `card` 为非空 JSON 且与响应 `products` 对应,非卡片轮 `card IS NULL`;
  4. `created_at` 单调递增。
- **pytest**:`test_chat_history.py::TestChatHistory::test_two_turns_persist_four_messages_with_card`

### C-02 [P0] 未登录拉取/清空历史 → 401(可自动化)

- **前置条件**:无 token。
- **请求**:`GET /api/chat/history`;`DELETE /api/chat/history`。
- **期望响应**:均 401(spec 验收 4)。
- **断言点**:两个端点独立校验均 401;不返回任何消息内容。
- **pytest**:`...::test_history_requires_auth`

### C-03 [P0] 历史超 20 条只返回最近 20 条且为时间正序(可自动化)

- **前置条件**:同一用户连续 `POST /api/chat` 12 轮(产生 24 行)。
- **请求**:`GET /api/chat/history`(默认 limit)。
- **期望响应**:200,恰好返回 20 条消息。
- **断言点**(spec 验收 5):
  1. 长度 == 20,内容为**最近** 20 行(最早 4 行被截掉,用 content 序号比对);
  2. 数组顺序为时间正序(旧→新),首条 user、末条 assistant 交替正确;
  3. `limit=21` 等越界入参要么 422 要么被钳制为 20(实现二选一,测试按实际契约固定,建议 422 或静默 clamp 都可,但需有断言)。
- **pytest**:`...::test_history_returns_latest_20_ascending`

### C-04 [P0] 清空历史后归零且 thread 上下文重置(可自动化)

- **前置条件**:u 已进行至少一轮带具体上下文的对话(如先说"我叫张三",再问"我叫什么")。
- **请求**:
  1. `DELETE /api/chat/history`(带 token)→ 期望 200;
  2. `GET /api/chat/history` → 期望空列表;
  3. 清空后再 `POST /api/chat` 问"我叫什么名字?"。
- **期望响应**:DELETE 200;GET 200 且 `messages == []`;新回复**不再引用**"张三"(thread 上下文已重置,spec 验收 3)。
- **断言点**:库中该用户 `chat_messages` 为 0 行;新消息使用新的 `thread_id`(与清空前不同)或同 thread 但 LangGraph checkpointer 状态已清空——以"回复不含旧上下文"为行为断言主线。
- **pytest**:`...::test_clear_history_resets_thread`

### C-05 [P1] 重启后端进程后历史仍在(可自动化)

- **前置条件**:u 完成 2 轮对话(4 行落库)。
- **请求**:关闭并重新创建 `TestClient(app)`(等价于进程重启,MemorySaver 状态随之丢失),再 `GET /api/chat/history`。
- **期望响应**:200,4 条消息完整、正序、card 可解析。
- **断言点**(spec 验收 2):数据来自 SQLite 而非内存;card JSON 在跨"进程"后仍非空。
- **pytest**:`...::test_history_survives_app_restart`

### C-06 [P1] 落库失败不阻塞主响应(可自动化)

- **前置条件**:`unittest.mock.patch("database.insert_chat_message", side_effect=aiosqlite.Error("disk full"))`(仅 mock 落库函数,不 mock 被测服务,符合现有"不 mock 被测单元"底线)。
- **请求**:`POST /api/chat` 正常发问。
- **期望响应**:仍 200,`reply` 正常返回(spec FR5:写入失败仅打日志)。
- **断言点**:响应不包含 5xx;patch 停止后新对话恢复落库。
- **pytest**:`...::test_persistence_failure_does_not_block_reply`

### C-07 [P0] 前端:挂载回显、卡片回显与清空按钮(手动)

- **步骤**:
  1. 登录后发 2 轮对话(其中一轮带推荐卡片),刷新整个浏览器页面;
  2. 重新打开 BS 助手面板;
  3. 点「清空对话」。
- **期望**:刷新后面板自动渲染刚才 2 轮对话,文字气泡与推荐卡片均完整回显(spec 验收 2);点清空后立即恢复欢迎语、气泡全空;清空按钮有二次确认或直接清空但不报错。

### C-08 [P1] 前端:空历史与未登录态(手动)

- **步骤**:
  1. 新注册(从未对话)用户登录,打开助手面板;
  2. 未登录状态下打开面板(若入口可见)。
- **期望**:空历史显示现有欢迎语,不发渲染错误;未登录态不调 `GET history`(或收到 401 后面板保持欢迎语,控制台无红字)。

---

## 三、改进项 3:站内通知中心真实化(8 条;后端 6 + 前端 2)

接口基线:复用 `GET /api/v2/notifications`、`POST /api/v2/notifications/{id}/read`(已存在);在交易/悬赏/Cron 三处埋点写入。
建议测试文件:`backend/tests/test_notification_events.py`,类 `TestNotificationEvents`。

### N-01 [P0] 购买成功后买卖双方各收 1 条通知(可自动化)

- **前置条件**:seller(昵称可识别)发布商品 P,名称含可断言文本如"告警机器人 Alpha";buyer 注册登录并充值足够金币。
- **请求**:buyer 调 `POST /api/transactions/buy` 完成购买。
- **期望响应**:购买接口 200(沿用现有契约)。
- **断言点**(spec 验收 1):
  1. `GET /api/v2/notifications`(buyer token)有 1 条未读,内容/标题含商品名;
  2. seller token 同样有 1 条未读,类型为"商品被购买",含商品名与买家信息;
  3. 两条 `is_read=0`,类型字段可区分(如 `product_sold` / `product_bought`)。
- **pytest**:`test_notification_events.py::TestNotificationEvents::test_buy_notifies_buyer_and_seller`

### N-02 [P0] 悬赏全流程 4 个节点各产生对应通知(可自动化)

- **前置条件**:owner 发布悬赏;dev 申请;owner 选中 dev;dev 提交交付;owner 验收通过(拒绝分支见断言 4)。
- **请求**:按 `routers/bounties.py` 现有流程依次调用申请/选人/交付/验收接口。
- **期望响应**:各流程接口沿用现有成功状态码。
- **断言点**(spec 验收 2):
  1. 新申请 → owner 收 1 条;
  2. 被选中 → 该 dev 收 1 条,未被选中的其他申请者**不**收选中通知(防误发);
  3. 交付提交 → owner 收 1 条;
  4. 验收通过 → dev 收 1 条;另跑一条拒绝支线,断言 dev 收到"验收拒绝"通知;
  5. owner 侧合计 ≥3 条、dev 侧 ≥2 条,通知均与本人相关(不串号)。
- **pytest**:`...::test_bounty_lifecycle_emits_notifications`

### N-03 [P0] Cron 推送成功后通知全部 active 订阅者(可自动化)

- **前置条件**:准备 cron 商品 C;用户 s1、s2 为 active 订阅,s3 为退订/过期订阅;具备 `X-Webhook-Secret` 头所需密钥(参考 `routers/cron.py:27-30`)。
- **请求**:`POST /api/cron/push/{cron_id}`,Header 带正确 webhook secret,Body 为合法 payload。
- **期望响应**:200(推送成功)。
- **断言点**(spec 验收 3):
  1. s1、s2 各收 1 条未读通知,内容含 cron/商品名与结果摘要;
  2. s3 **不**收;
  3. 推送失败(错误 secret → 401/403)时不产生任何通知。
- **pytest**:`...::test_cron_push_notifies_active_subscribers`

### N-04 [P0] 未读数一致、点击已读后 -1 且不回弹(可自动化)

- **前置条件**:制造 buyer 的 3 条未读(如连续触发 3 个通知事件)。
- **请求**:
  1. `GET /api/v2/notifications`;
  2. `POST /api/v2/notifications/{id1}/read`;
  3. 再次 `GET /api/v2/notifications` 与 `GET /api/v2/notifications?unread_only=true`。
- **期望响应**:read 接口 200 `{"success": true}`。
- **断言点**(spec 验收 4):初始 `unread_count==3`;已读后 `==2` 且列表中该条 `is_read=1`;`unread_only=true` 不再包含它;重复 GET 计数稳定不回弹(幂等)。
- **pytest**:`...::test_unread_count_and_mark_read`
- **备注**:此案例只依赖现有读接口 + 任意一个埋点,是三项中最早可转 GREEN 的,建议最先写。

### N-05 [P1] 通知接口未登录 → 401 且无泄漏(可自动化)

- **请求**:不带 token 调 `GET /api/v2/notifications` 与 `POST /api/v2/notifications/1/read`。
- **期望响应**:均 401。
- **断言点**:不返回任何通知体;与现有 `get_current_user` 401 契约一致。
- **pytest**:`...::test_notifications_require_auth`

### N-06 [P1] 标记不存在或他人通知为已读 → 404(可自动化)

- **前置条件**:u1 有 1 条通知;u2 为另一登录用户;`999999` 不存在。
- **请求**:u2 调 `POST /api/v2/notifications/{u1的通知id}/read`;u1 调 `POST /api/v2/notifications/999999/read`。
- **期望响应**:均 404(现有 `mark_notification_read` 按 id+user 过滤,`routers/user_v2.py:143-148`)。
- **断言点**:404 且 u1 的通知仍为未读(防越权已读);不暴露"存在但不属于你"与"不存在"的差异(统一 404)。
- **pytest**:`...::test_mark_read_404_for_missing_or_other_user`

### N-07 [P0] 前端:铃铛、徽标、下拉与点击已读(手动)

- **步骤**:
  1. 登录 buyer,另一窗口/账号完成对其商品的购买(或触发任一通知事件);
  2. 观察 Navbar 铃铛(≤60s 轮询窗口内)。
- **期望**:
  1. 铃铛出现红色未读徽标,数字与接口 `unread_count` 一致;
  2. 点开下拉展示最近 10 条,含标题/内容/相对时间,超 10 条不显示更旧的;
  3. 点单条后该条置灰/移除未读态,徽标数字 -1,下次轮询不回弹;
  4. 轮询只在登录态进行(可在 Network 面板核对 60s 节奏)。

### N-08 [P1] 前端:未登录隐藏铃铛与 401 静默(手动)

- **步骤**:未登录浏览任意页面;再用过期/伪造 token 登录态(可选,localStorage 改坏 token)打开页面。
- **期望**:未登录时 Navbar 无铃铛、不发 notifications 请求;token 失效导致 401 时 UI 不弹错误、控制台无未捕获红字(与 spec 验收 5 一致)。

---

## 四、覆盖矩阵与优先级汇总

| 改进项 | 后端自动化 | 前端手动 | P0 | P1 |
|---|---|---|---|---|
| 1 评价体系 | R-01~R-07(7) | R-08、R-09 | 7 | 2 |
| 2 会话持久化 | C-01~C-06(6) | C-07、C-08 | 5 | 3 |
| 3 通知中心 | N-01~N-06(6) | N-07、N-08 | 5 | 3 |
| **合计** | **19** | **6** | **17** | **8** |

### 异常流覆盖自查

- 未登录 401:R-02、C-02、N-05
- 已登录无权限:R-03(403)、N-06(404 越权)
- 冲突/参数非法/资源不存在:R-04(409)、R-05(422)、R-07(404)
- 边界值:评价 rating 0/5/6、content 500/501 字;history 20/21/24 条
- 错误路径:落库失败不阻塞(C-06)、cron secret 错误不发通知(N-03)
- 数据隔离:不串号(N-02)、不串用户(N-06)、空历史/空列表(C-08、C-04)

### 未纳入本版(显式排除,避免 scope 蔓延)

- 卖家回复评价、评价图片/审核流(spec 非目标);
- 多会话切换、跨端同步、旧内存会话迁移(spec 非目标);
- 邮件/WebSocket 实时推送、通知偏好、全部已读按钮(FR4 加分项,非阻塞);
- 性能压测(10k 评价/消息)留待接口稳定后单独补充。
