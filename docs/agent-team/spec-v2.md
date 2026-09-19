# SkillBazaar Spec v2:BS 导购助手 → 需求撮合闭环

> 范围:1 个主题 4 条 FR | 日期:2026-09-18 | 依据:docs/agent-team/marketing-insights.md Top1 机会 + 代码实测

## 一、现状与差距(简)

- BS 助手已有 LangGraph 意图路由(`backend/agents/bs_agent.py`:search/publish/bounty/analyze/chat + 规则兜底),`do_search` 返回 Markdown 表格 + `{type:'products', products[]}` 卡片(含 id/价格/评分,来自真实 `product_service.get_products`)。
- **差距**:① 推荐是"平铺列表",无任务拆解与组合逻辑;② `ChatPanel.jsx` 的 `INTERACTIVE_CARD_TYPES` 不含 `'products'`,`renderCard` 对其返回 null——**推荐卡是纯展示,无任何购买/发悬赏动作**;③ 无匹配时只回一句"换个关键词",没有把需求导向悬赏市场的通路。
- v1 已铺好的地基可直接复用:Bearer 鉴权(chat 路由已统一)、虚拟币购买全流程(`transaction_service.buy_product` 含通知埋点)、评价体系(products.rating 已是真实均值)、会话持久化(chat_messages.card JSON)、通知中心(铃铛 + 未读数)。

## 二、功能需求(FR)

### FR1 任务拆解 + Skill 组合推荐卡

用户用自然语言描述任务("帮我每天抓取竞品价格并生成周报"),助手输出**分步拆解**,每步推荐 1 个具体 Skill(从真实搜索结果中选取,带价格与评分)。

- 拆解数据源必须来自 `do_search` 的真实搜索结果:LLM 只负责「拆步骤 + 选 result id + 写推荐理由」,理由须引用该商品 `description` 字段原文,不得编造库外商品。
- 卡片结构:`{type:'match', steps:[{title, product:{id,name,price,rating}, reason}], total_price}`,经 `chat_service` 持久化为 card JSON(v1 机制)。
- LLM 不可用时(503/超时)规则兜底:按关键词搜出 ≥1 个结果即出单步推荐卡;完全无结果走 FR3。
- 改动点:`backend/agents/nodes.py`(SYSTEM_PROMPT 增加 match 模式 + `do_search` 输出 match 卡,或新增 `do_match` 节点)、`backend/agents/bs_agent.py`(节点注册)、`backend/services/chat_service.py`(persisted_card 类型透传,现有逻辑已兼容)。
- **验收标准**:
  1. 准备 20 条真实中文任务描述(测试用例集),≥80% 返回含 ≥2 个可购项的 match 卡(营销验收雏形①)。
  2. 卡内每个 product 的 id 在 products 表中存在,reason 是该商品 description 的子串或直接引用(抽验 10 条,0 编造)。
  3. 停掉 LLM(mock 503)发任务描述 → 仍返回 match 卡或 FR3 引导,不抛 500。
  4. 卡内价格与评分与 `GET /api/products` 返回一致。

### FR2 推荐卡内「一键购买」

match 卡每个推荐项带「一键购买」按钮,复用 v1 虚拟币购买流程,路径 ≤3 步(点按钮 → 确认 → 成功回执)。

- 前端:点击购买 → 携 Bearer token 调购买接口 → 成功后该项置「已购 ✅」并展示剩余余额;失败分支:402 余额不足(提示充值入口)/ 400 已购过(置已购态)/ 网络错误(按钮恢复可点)。
- 后端:**购买接口必须改为 Bearer 鉴权**——`POST /api/transactions/buy` 现从 body 取 `buyer_id`,无任何鉴权(实测),一键购买前必须修掉,否则聊天卡内购买可被伪造身份。改法与 v1 chat 统一:身份取自 token,弃 `TransactionCreate.buyer_id`。
- 成功通知零新增工作:`buy_product` 已对买家/卖家各发一条站内通知(v1 埋点),铃铛自然触达。
- 改动点:`backend/routers/transactions.py`(buy 加 `Depends(get_current_user)`,复用 `routers/user_v2.get_current_user`)、`backend/services/transaction_service.py`(buyer_id 来自 token)、`backend/models.py`(TransactionCreate 删 buyer_id)、`frontend/src/components/cards/MatchCard.jsx`(新建)、`frontend/src/components/ChatPanel.jsx`(renderCard 注册 `'match'`,加入 INTERACTIVE_CARD_TYPES)、`frontend/src/services/api.js`(buyProduct 签名改 token,修现有调用点 ProductDetailPage.jsx)。
- **验收标准**:
  1. 余额充足的登录用户点「一键购买」→ 200,`coins` 减少 `price`,`wallet_transactions` 新增 1 条,通知中心出现购买通知。
  2. 余额不足 → 402,卡片显示余额与所需金额,不发交易。
  3. 已购用户再点 → 该项显示已购且按钮禁用(前端),直接调接口返回 400(后端兜底)。
  4. 未登录(无 token)调购买接口 → 401(此前是 200,破坏性变更需回归 ProductDetailPage 购买按钮)。
  5. 从输入任务描述到完成一次购买,用户操作 ≤3 步(营销验收雏形②)。

### FR3 无匹配 → 引导发布悬赏(预填任务描述)

拆解后无任何可购项(或用户任务在库内零搜索结果)时,回复附「发布悬赏找人开发」按钮。

- 点击后**不离开会话**:复用现有 bounty 卡机制(`do_bounty` 已有 `type:'bounty'` 卡 + BountyCard 提交链路),把任务描述预填进 `card.data.description`、生成 title 预填 `card.data.title`,用户在卡内补预算/分类后直接提交。
- 兜底跳转:若用户说"带我去悬赏页",引导文案给 `/bounty` 路由链接(现有 Markdown 链接渲染已支持)。
- 改动点:`backend/agents/nodes.py`(do_search 零结果分支输出 bounty 预填卡,title/description 取自用户任务消息)、`frontend/src/components/ChatPanel.jsx`(bounty 卡已在 INTERACTIVE_CARD_TYPES,无改动或仅文案)。
- **验收标准**:
  1. 输入一条库内零匹配的任务 → 回复含「发布悬赏」按钮(营销验收雏形③的前半:需求进入悬赏通路)。
  2. 点击按钮 → bounty 卡出现,description 与用户任务描述一致,title 非空;提交 → `GET /api/bounties` 可见新悬赏,poster 为当前用户。
  3. 有匹配结果的任务 → 不出现该按钮。

### FR4 会话历史回显时卡片动作仍可用

match 卡随 `chat_messages.card` 持久化(v1 已有),历史回显后购买/发悬赏动作必须可用,且「已购」状态以服务端为准而非本地状态。

- 已购判定:MatchCard 渲染时对当前用户查 `GET /api/transactions/library/{user_id}`(已有接口)或首次购买失败 400 时同步置已购;刷新/重进后状态仍正确。
- 改动点:`frontend/src/components/ChatPanel.jsx`(历史回显路径将 `'match'` 卡传给 renderCard——与实时消息同函数,天然一致)、`frontend/src/components/cards/MatchCard.jsx`(挂载时校验已购)。
- **验收标准**:
  1. 购买成功 → 刷新页面重开助手 → 历史中该 match 卡完整渲染,已购项按钮禁用显示「已购」。
  2. 历史中的 match 卡点「一键购买」另一项 → 走通完整购买链路(通知到账)。
  3. 历史回显的 bounty 预填卡(FR3)仍可编辑并提交成功。
  4. 换一个账号登录 → 同一张历史卡不显示任何「已购」(按用户隔离)。

## 三、明确不做(留给 v3/v4)

- **沙箱试用与交付即验证**(营销 Top2):评测报告、30 秒免登录试用、兼容性标注、试用确认期退款。
- **防泄露交付 + 卖家收入看板**(营销 Top3):运行时调用交付、注入探测、三种计价模式。
- 悬赏按标签推送给开发者(撮合闭环的卖侧半环,依赖悬赏标签体系,先记录需求)。
- 组合购买的"打包价/购物车"(单步购买已闭环,打包留待量数据支撑)。

## 四、风险与依赖(实测发现)

1. **购买接口零鉴权是前置必修项**(FR2):`transactions.py` 的 buy 以 body.buyer_id 计身份,回归范围含 ProductDetailPage 的现有购买调用。
2. **LLM 编造商品**:match 卡必须以搜索结果为唯一数据源,LLM 仅做选择与措辞;验收 1.2 专测此项。
3. **"无匹配"判定要在真实搜索参数上**:do_search 现有三级兜底(去 keyword、去 category)会掩盖零结果,FR3 的触发条件须基于"原始意图参数下零结果",否则引导按钮永远不出现。
4. GLM API key 硬编码在 `backend/agents/nodes.py:8`(明文入库历史),建议本版顺手迁到环境变量。
5. match 卡新增 card type,需与 v1 历史数据共存:旧 `'products'` 卡在回显时降级为纯列表(渲染 null 的现状保持或简单列表化),不阻塞。

## 五、v3 候选

1. **Skill 交付即验证**:上架自动评测报告 + 沙箱 30 秒试用 + 试用确认期退款(营销 Top2 全量)。
2. **防泄露交付 + 卖家收入看板**:运行时调用、收入趋势、按次/订阅/买断计价(营销 Top3)。
3. **悬赏标签撮合**:悬赏按 category/tag 推送给匹配开发者,补全撮合闭环卖侧。
4. 沿用 v1 候选池未做项:Cron 到期续订、MCP 端点对齐排序筛选、执行成功率展示、促销码充值入口。
