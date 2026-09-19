# SkillBazaar Spec v2 测试案例文档

> 对应需求文档:`docs/agent-team/spec-v2.md`(FR1 任务拆解+match 卡 / FR2 卡内一键购买+buy 鉴权 / FR3 零结果引导悬赏 / FR4 历史回显动作可用)
> 日期:2026-09-18 | 案例总数:22(P0 18 条,P1 4 条)| 编写人:QA agent

## 0. 通用约定

### 0.1 后端自动化测试风格(沿用 v1)

- 框架:`unittest.TestCase` + `fastapi.testclient.TestClient`,pytest 收集;运行:`cd backend && python3 -m pytest tests/ -q`。
- 数据库:每个测试文件 `setUpClass` 用 `tempfile` 替换 `database.DB_PATH`(参考 `tests/test_chat_history.py:14-24`),不碰生产库。
- 鉴权:`POST /api/v2/auth/register` + `/login` 拿 token,Header `{"Authorization": f"Bearer {token}"}`。
- 发商品:`POST /api/products`(参考 `tests/test_notification_events.py:57-64` 的 `_publish` 辅助)。

### 0.2 新增测试文件(4 个)

| 文件 | 覆盖案例 | 类建议 |
|---|---|---|
| `backend/tests/test_buy_auth.py` | B-01~B-04、B-07、H-02 | `TestBuyAuth`、`TestPurchasedStateServerSide` |
| `backend/tests/test_match_cards.py` | M-01~M-03、H-01 | `TestMatchCards`、`TestMatchCardPersistence` |
| `backend/tests/test_zero_result_bounty.py` | Z-01~Z-04 | `TestZeroResultBounty` |
| `backend/tests/test_no_hardcoded_secrets.py` | S-01 | `TestNoHardcodedSecrets` |

### 0.3 LLM mock 策略(确定性的关键)

- **不真实调用 GLM**:统一 `patch("agents.nodes._call_llm", new=AsyncMock(...))`(被测的是路由/节点/服务,不 mock)。
- LLM 正常态:`return_value` 按实现冻结后的 match 模式 prompt 契约返回文本(含搜索参数 JSON + 选品 JSON,选品引用本测试种子商品的真实 id);行为断言(卡结构、id 必须存在于 products 表、reason 引用 description)不依赖文本细节,prompt 落地后只调整 fixture 文本。
- LLM 故障态:`side_effect=httpx.TimeoutException("503")` 或 `httpx.HTTPStatusError`,走 `_fallback_search_params` 规则兜底。
- 触发 search 意图:消息含规则关键词"找/推荐"(见 `nodes.py:INTENT_RULES`),避免 classify 分支干扰。
- 每个用例注册独立用户名,天然隔离 LangGraph thread。

### 0.4 测试先行(TDD)说明

| 可否先行 | 范围 |
|---|---|
| **实现前即为 RED,应先写** | B-01(现状 200,改造后 401,第一个红灯)、B-02~B-04、B-07、M-01~M-03、Z-01~Z-04、H-01、S-01(当前 `nodes.py:8` 明文 key,立刻红) |
| **现在即为 GREEN(特征/回归锁定先行)** | H-02(library 接口 v1 已存在,先锁住"已购状态按用户隔离"的服务端基线) |
| **实现后再跑** | M-04(依赖真实 LLM 的评测集,标记 `@pytest.mark.llm_live`,无 `REAL_LLM_KEY` 时 skip,不卡 CI) |
| **手动** | 全部前端案例 6 条(M-05、B-05、B-06、Z-05、H-03、H-04) |

---

## 一、FR1 任务拆解 + Skill 组合推荐卡(5 条;后端 4 + 前端 1)

接口基线:`POST /api/chat`(Bearer,已鉴权)→ `card` 新类型 `match`;卡结构契约:
`{type:'match', steps:[{title, product:{id,name,price,rating}, reason}], total_price}`,经 `chat_messages.card` 持久化。
建议文件:`backend/tests/test_match_cards.py`,类 `TestMatchCards`。

### M-01 [P0] 多步任务返回 match 卡,结构/价格/持久化全部正确(可自动化,先行)

- **前置条件**:seller 发布 3 个商品 P1/P2/P3(名称/描述可断言,价格分别 100/200/300,均有评分);buyer 登录;mock `_call_llm` 返回 match 模式契约文本,选中 P1、P2 两步。
- **请求**:`POST /api/chat`,Bearer buyer;Body `{"message":"我想找一个每天抓取竞品价格并生成周报的方案"}`。
- **期望响应**:200,`card.type == "match"`,`steps` 长度 ≥2。
- **断言点**:
  1. 每步含 `title`(非空)、`product.{id,name,price,rating}`、`reason`(非空);
  2. 每个 `product.id` 在 products 表真实存在(`GET /api/products/{id}` 200),price/rating 与该接口返回值**逐字段相等**(spec 验收 1.4);
  3. `total_price == sum(steps[*].product.price) == 300`;
  4. 直连临时库查最近一条 assistant `chat_messages.card`,JSON 解析后 `type=="match"` 且与响应 card 一致(持久化透传)。
- **pytest**:`test_match_cards.py::TestMatchCards::test_multistep_task_returns_match_card`

### M-02 [P0] 推荐不编造:库外 id 被丢弃,reason 必须引用真实 description(可自动化,先行;风险②)

- **前置条件**:发布商品 P1,description 用特征文本如"每日定时抓取竞品价格并输出差异报表";mock `_call_llm` 返回的选品 JSON 中**混入不存在的 id 999999** 与真实 P1,且给 999999 配了华丽理由。
- **请求**:同 M-01。
- **期望响应**:200。
- **断言点**(spec 验收 1.2,抽验 0 编造):
  1. card 中**绝不出现** id=999999,`GET /api/products/999999` 404;所有 step 的 id 均为当次真实搜索结果子集;
  2. 对每步取库内该商品完整 `description`,断言 `step.reason` 文本是其**子串/直接引用**(去空白后包含匹配),不得出现 description 之外的功能承诺;
  3. 卡内不出现搜索结果之外的商品名(name 必须与库内一致)。
- **pytest**:`...::test_match_card_never_fabricates_products_or_reasons`

### M-03 [P0] LLM 503/超时走规则兜底,不抛 500 且仍出推荐卡(可自动化,先行)

- **前置条件**:发布至少 1 个 Skill 商品;`patch _call_llm` 为 `side_effect=httpx.TimeoutException`。
- **请求**:`POST /api/chat`,`{"message":"推荐一个 skill 帮我写周报"}`(含"推荐"+"skill",规则兜底参数 category=Skill)。
- **期望响应**:200(spec 验收 1.3)。
- **断言点**:
  1. 返回 `card.type=="match"` 且 steps ≥1(规则兜底:关键词搜出 ≥1 结果即出单步推荐卡),或在完全无库时走 FR3 卡——二者必居其一,绝不允许 5xx;
  2. 卡内 id 均真实存在;回复文案不包含 Python 堆栈/Traceback;
  3. `chat_messages` 正常落库 2 行。
- **pytest**:`...::test_llm_outage_falls_back_to_rule_based_match`

### M-04 [P1] 20 条真实任务描述 ≥80% 返回 ≥2 个可购项(评测集,真实 LLM)

- **前置条件**:种子目录就位;`tests/fixtures/v2_task_descriptions.txt` 准备 20 条真实中文任务(如"每天抓取竞品价格并生成周报""自动回复客户投诉邮件"等);提供真实 `REAL_LLM_KEY` 环境变量,否则 skip。
- **请求**:逐条 `POST /api/chat`(可复用同一用户)。
- **期望响应**:20 条全部 200。
- **断言点**(spec 验收 1.1):
  1. ≥16 条(80%)返回 `card.type=="match"` 且可购 steps ≥2;
  2. 全部 card 的 product id 真实存在;抽 10 条 reason 引用 description(复用 M-02 校验函数),0 编造;
  3. 输出失败明细(哪条不达标及实际意图),作为营销验收雏形数据。
- **pytest**:`...::test_20_real_tasks_80pct_multi_step`(`@pytest.mark.llm_live`,手动/预发触发,非 CI 门禁)

### M-05 [P0] 前端:match 卡分步渲染与总价展示(手动)

- **步骤**:登录后向助手发送"帮我每天抓取竞品价格并生成周报"。
- **期望**:
  1. 回复先出现文字拆解,下方 match 卡按步骤分块展示(步骤标题、商品名、分类、价格、评分、推荐理由);
  2. 卡底显示总价,数值=各步价格之和;每项有「一键购买」按钮;
  3. 商品名可点进 `/product/{id}`;卡内不出现库外/占位商品。

---

## 二、FR2 推荐卡内一键购买 + buy 接口加 Bearer 鉴权(7 条;后端 5 + 前端 2)

接口基线(破坏性变更):`POST /api/transactions/buy` 增加 `Depends(get_current_user)`,身份只取 token;`TransactionCreate` 删除 `buyer_id` 字段(参考 chat 路由 v1 做法 `routers/chat.py:9-15`);401/400/402/404 状态码维持其余契约。
建议文件:`backend/tests/test_buy_auth.py`,类 `TestBuyAuth`。

### B-01 [P0] 无 token 调购买接口 → 401(可自动化,先行;当前实测 200,第一个红灯;风险①)

- **前置条件**:存在商品 P;无 Authorization 头。
- **请求**:`POST /api/transactions/buy`,Body `{"product_id": P}`。
- **期望响应**:HTTP 401。
- **断言点**:401;库中无新 transaction/wallet_transaction 行;任何买家金币不变。
- **pytest**:`test_buy_auth.py::TestBuyAuth::test_anonymous_buy_rejected`

### B-02 [P0] body 伪造 buyer_id 无效,成交身份只认 token(可自动化,先行)

- **前置条件**:用户 A、B 均登录;P 在售;记录 B 的金币初值。
- **请求**:用 A 的 token 调 buy,Body 故意带 `"buyer_id": B`(旧客户端形态)+ `"product_id": P`。
- **期望响应**:HTTP 200。
- **断言点**(防伪造身份的核心):
  1. 交易归属 A:`GET /api/transactions/library/A` 含 P、library/B 不含;
  2. A 的 coins 减少 price,B 的 coins 分文不变;wallet_transactions 记在 A 名下;
  3. 通知发给 A(及卖家),B 无任何通知。
- **pytest**:`...::test_buyer_identity_comes_from_token_not_body`

### B-03 [P0] 持 token 余额足:购买成功全链路回归(可自动化,先行)

- **前置条件**:seller 发布 P(价格 50,名称可识别);buyer 登录,金币充足。
- **请求**:Bearer buyer 调 `POST /api/transactions/buy`,`{"product_id": P}`。
- **期望响应**:200,`success=true`,data 含交易信息。
- **断言点**:
  1. buyer coins 减少 50;`wallet_transactions` 新增 1 条 `type=buy`、`amount=-50`、`balance_after` 正确;
  2. buyer、seller 各收到 1 条站内通知(锁 v1 埋点在鉴权改造后不回归,对齐 N-01);
  3. `GET library` 含 P。
- **pytest**:`...::test_authenticated_buy_happy_path`

### B-04 [P0] 异常流:余额不足 402 / 重复购买 400(可自动化,先行)

- **前置条件**:P 价格 100;poor 注册后金币耗尽(买尽或用边界:coins=99);owner 已买过一次 P。
- **请求**:① poor token 买 P;② owner token 再买 P。
- **期望响应**:① 402,detail 含当前余额与所需金额;② 400。
- **断言点**:
  1. 两种情况下均不新增 transaction/wallet_transactions,金币不变;
  2. 402/400 响应不泄漏其他用户信息;错误文案可被前端直接展示;
  3. owner 首次购买确实成功(对照),library 仅 1 条,不重复扣款。
- **pytest**:`...::test_insufficient_balance_402_and_already_purchased_400`(subTest 两分支)

### B-05 [P0] 前端回归:ProductDetailPage 购买弹窗改造后行为(手动;风险①回归面)

- **步骤**:
  1. 未登录打开商品详情页,点「立即购买」;
  2. 登录余额充足账号,打开 `PurchaseModal`,核对余额展示后点「确认购买」;
  3. 登录余额不足账号打开同一弹窗。
- **期望**:
  1. 未登录不发起购买请求(或 401 被静默拦截),弹窗引导去登录,**无白屏/无未捕获异常**(`PurchaseModal.jsx:18` 旧调用 `buyProduct(userId, id)` 已改为携 token);
  2. 登录态走通成功回执,成功后金币余额刷新;
  3. 余额不足时按钮禁用并提示充值,与 v1 视觉一致。

### B-06 [P0] 前端:match 卡一键购买的成功与三种失败分支(手动;spec 验收路径 ≤3 步)

- **步骤**:在 match 卡上依次/分别构造:余额足购买;余额不足(402);已购再点(400);断网点按钮(网络错误)。
- **期望**:
  1. 点按钮 →(确认)→ 成功回执,≤3 步;成功后该项置「已购」禁用并展示剩余余额,铃铛出现购买通知;
  2. 402:卡内显示余额与所需金额及充值入口,不发交易;
  3. 400:该项同步置「已购」禁用;
  4. 网络错误:按钮恢复可点、可重试,不错误置为已购;购买中有 loading 防连点。

### B-07 [P1] 伪造/过期 token → 401(可自动化,先行)

- **请求**:`POST /api/transactions/buy`,Header 分别带 `Bearer not.a.real.token`、`Bearer `(空)、非法 Scheme。
- **期望响应**:均 401。
- **断言点**:与 `get_current_user`(`routers/user_v2.py:20-27`)契约一致;无交易落库;响应体不区分"token 伪造"与"过期"(统一 401)。
- **pytest**:`...::test_invalid_token_rejected`

---

## 三、FR3 零结果 → 引导发布悬赏(预填卡)(5 条;后端 4 + 前端 1)

判定基线:**零结果判定基于用户原始意图参数下的首次搜索**;`do_search` 现有三级放宽(去 keyword → 去 category)只用于决定"是否还有推荐可展示",不得掩盖 FR3 引导(`nodes.py:175-181` 现状会在第三级返回全库商品——这是本风险的复现点)。
建议文件:`backend/tests/test_zero_result_bounty.py`,类 `TestZeroResultBounty`。

### Z-01 [P0] LLM 挂掉走规则兜底时,原始意图零结果仍出 bounty 预填卡(可自动化,先行;风险③核心)

- **前置条件**:临时库内**只发布 2 个 Skill 商品**,无任何 Cron;`patch _call_llm` 为 `side_effect=httpx.TimeoutException`(规则兜底产出 category=Cron、keyword=None)。
- **请求**:`POST /api/chat`,`{"message":"我想找一个能做量子宠物翻译的 cron 定时任务"}`。
- **期望响应**:200。
- **断言点**:
  1. `card.type=="bounty"`,`card.step=="fill"`;**即使三级兜底实际能搜出 Skill 商品,也必须出引导**(证明判定取自原始参数 category=Cron 的零结果,而非放宽结果);
  2. `card.data.description` 与用户原话逐字一致;`card.data.title` 非空;`card.data.category` 预填合理(Agent/Cron 之一);
  3. 响应 `products` 为空或不渲染可购推荐,不允许用不相关的 Skill 冒充匹配。
- **pytest**:`test_zero_result_bounty.py::TestZeroResultBounty::test_rule_fallback_zero_hits_emits_bounty_prefill`

### Z-02 [P0] LLM 正常但原始搜索参数零结果 → bounty 卡,不被放宽兜底掩盖(可自动化,先行)

- **前置条件**:库内仅有 Skill 商品;mock `_call_llm` 返回的搜索参数 JSON 为冷门关键词(如 `{"keyword":"量子宠物翻译","category":""}`)+ 正常话术。
- **请求**:`POST /api/chat`,`{"message":"帮我找一个量子宠物翻译技能"}`。
- **期望响应**:200,`card.type=="bounty"`。
- **断言点**:
  1. 首次搜索(原始 keyword)零结果即触发引导;放宽后虽能列出 Skill 商品,引导仍出现(风险③的 LLM 在场版本);
  2. 预填 description==用户原话,title 非空;
  3. 回复文案含「发布悬赏找人开发」语义。
- **pytest**:`...::test_llm_zero_hits_emits_bounty_prefill_despite_broadening`

### Z-03 [P0] 有匹配结果时不出现悬赏引导(可自动化,先行)

- **前置条件**:发布名称/描述高度匹配的 Skill 商品;mock LLM 返回命中该商品的搜索参数与选品。
- **请求**:`POST /api/chat` 发明确能命中的任务。
- **期望响应**:200,`card.type=="match"`(或 LLM 故障时的单步推荐)。
- **断言点**:card 不是 bounty 类型;回复不含「发布悬赏」按钮语义(spec 验收 3.3);steps 中含目标商品 id。
- **pytest**:`...::test_no_bounty_guidance_when_matches_exist`

### Z-04 [P0] 预填卡补预算后提交,悬赏落库且 poster 为当前用户(可自动化,先行)

- **前置条件**:复现 Z-01 拿到 bounty 卡;用户已登录。
- **请求**:
  1. 用卡内 `data` 补 `budget_min=100、budget_max=300、deadline` 等字段,调 `POST /api/bounties`(Bearer;该端点现状为 Header 鉴权 `routers/bounties.py:36-43`);
  2. `GET /api/bounties?keyword=量子宠物`。
- **期望响应**:POST 200;GET 列表含新悬赏。
- **断言点**(spec 验收 3.2):
  1. 新悬赏 `poster_id == 当前用户 id`,`description` 与聊天中的任务原话一致,title 非空;
  2. 未带 token 提交 → 401,不落库;
  3. 整条链路(聊天 → 预填 → 提交)中用户任务文本零丢失、未被兜底文案替换。
- **pytest**:`...::test_prefilled_bounty_card_submits_with_original_description`

### Z-05 [P1] 前端:零结果引导不离开会话 + /bounty 兜底链接(手动)

- **步骤**:
  1. 发一条库内零匹配任务,点回复中的「发布悬赏找人开发」;
  2. 在卡内补预算/分类后提交;
  3. 另发"带我去悬赏页"。
- **期望**:
  1. 点击后**会话不跳转**,bounty 卡就地出现且 description 为原话、title 已预填;提交成功后卡内有成功态,铃铛可收到悬赏相关通知;
  2. 有匹配结果的回复不出现该按钮;
  3. "带我去悬赏页"回复给出可点的 `/bounty` Markdown 链接(现有渲染已支持)。

---

## 四、FR4 历史回显动作可用 + 新旧卡共存(4 条;后端 2 + 前端 2)

### H-01 [P0] match 卡持久化回显,且与旧 'products' 卡在同一历史中共存(可自动化,先行;风险⑤)

- **前置条件**:buyer 登录;走通一次 M-01 产生 match 卡;再用 `database.insert_chat_message` 直接插入一条 v1 旧卡 assistant 行 `card={"type":"products","products":[{...真实商品}]}`。
- **请求**:
  1. `GET /api/chat/history`(Bearer);
  2. 关闭并重建 `TestClient(app)`(等价进程重启,清掉 MemorySaver)后再 GET。
- **期望响应**:两次均 200。
- **断言点**:
  1. 历史(时间正序、≤20 条)中同时存在 `card.type=="match"`(steps/total_price 完整、可 JSON 解析)与 `card.type=="products"` 旧卡,互不覆盖、互不报错;
  2. 跨"重启"后两张卡仍完整(`chat_service.get_history` 对未知 card type 不崩、不静默吞掉 match 卡);
  3. match 卡的 product 字段(id/price/rating)与落库时一致。
- **pytest**:`test_match_cards.py::TestMatchCardPersistence::test_match_card_echoes_and_coexists_with_legacy_products_card`

### H-02 [P0] 已购状态以服务端为准且按用户隔离(现在即可写,GREEN 基线锁定)

- **前置条件**:P 在售;A 完成购买,B 从未购买。
- **请求**:`GET /api/transactions/library/A`、`GET /api/transactions/library/B`;随后 B 持 token 调 buy(P)。
- **期望响应**:library/A 含 P;library/B 不含;B 购买 200(同商品对不同用户可各自成交)。
- **断言点**(spec FR4 已购判定的服务端依据):
  1. library 内容严格按路径用户隔离,A/B 结果互不串;
  2. A 再买 P → 400(服务端兜底"已购",前端首次失败可据此同步状态);
  3. 本用例不依赖任何前端 localStorage,为 H-03 的"换账号无已购态"提供接口级证据。
- **pytest**:`test_buy_auth.py::TestPurchasedStateServerSide::test_library_is_per_user_and_repurchase_400`

### H-03 [P0] 前端:刷新重开后历史卡动作全可用,已购态按账号隔离(手动)

- **步骤**:
  1. 在 match 卡购买第 1 步后,整页刷新并重开助手;
  2. 在历史 match 卡点第 2 步「一键购买」;
  3. 找到历史中的 FR3 bounty 预填卡,补字段提交;
  4. 退出换另一个账号登录,重开同一会话入口(各自历史)查看。
- **期望**(spec 验收 4.1-4.4):
  1. 历史 match 卡完整渲染,第 1 步按钮禁用显示「已购 ✅」(挂载时查 library 或曾收 400 同步,**不信本地状态**);
  2. 第 2 步购买链路走通,余额刷新、通知到账;
  3. 历史 bounty 卡仍可编辑并提交成功;
  4. 换账号后同卡不显示任何「已购」(用户隔离)。

### H-04 [P1] 前端现状基线:旧 'products' 卡不渲染交互、不报错(手动;风险②)

- **步骤**:触发一条 v1 形态搜索回复(markdown 表格 + products 卡数据),分别在实时消息与刷新后历史中查看;v2 上线后重复一次。
- **期望**(现状验证 + 防回归):
  1. `ChatPanel.jsx:17` 的 `INTERACTIVE_CARD_TYPES` 仍不含 `'products'`,`renderCard` default 分支返回 null——旧卡区域**无任何购买按钮**,markdown 推荐表格正常可见,控制台无红字;
  2. v2 引入 MatchCard 后,旧 products 卡维持"纯展示/null 降级"现状(或实现选择的简单列表化),不与 match 卡抢渲染、不阻塞消息流。

---

## 五、安全案例:GLM API key 迁移环境变量(1 条,后端)

### S-01 [P0] 代码库中不再出现明文 LLM key,统一从环境变量读取(可自动化,先行;当前 RED)

- **前置条件**:完成 spec 风险④整改:`nodes.py:8` 的 `LLM_API_KEY = "sk-bV3..."` 改为 `os.environ.get("LLM_API_KEY")`(或 settings/config),旧 key 作废轮换。
- **静态检查(自动化)**:`backend/tests/test_no_hardcoded_secrets.py`
  1. 遍历 `backend/` 下全部 `.py`(排除本测试文件与 fixtures)读源码,断言不含旧 key 片段 `sk-bV3`、也不匹配通用 `sk-[A-Za-z0-9]{20,}` 字面量;
  2. 断言 `agents/nodes.py` 源码中出现 `environ`/`getenv`(key 来自环境),且不存在 `LLM_API_KEY = "sk-` 形式赋值;
  3. 命令行复核:`! grep -rn "sk-bV3" backend/ frontend/ --exclude-dir=node_modules` 应零命中(含 `.env.example` 也只能留占位符)。
- **当前状态**:用例现在即失败(key 硬编码于 `agents/nodes.py:8`),整改后转 GREEN。
- **备注**:git 历史中的明文 key 已泄露,必须在 GLM 平台**轮换作废**,仅改代码不等于止血;部署环境通过环境变量/密钥管理注入,缺失时启动或首次调用给出明确错误。
- **pytest**:`test_no_hardcoded_secrets.py::TestNoHardcodedSecrets::test_no_plaintext_llm_api_key_in_source`

---

## 六、覆盖矩阵与风险自查

### 6.1 汇总

| FR | 后端自动化 | 前端手动 | P0 | P1 |
|---|---|---|---|---|
| FR1 match 卡 | M-01~M-04(4) | M-05 | 4 | 1 |
| FR2 一键购买+鉴权 | B-01~B-04、B-07(5) | B-05、B-06 | 6 | 1 |
| FR3 零结果悬赏 | Z-01~Z-04(4) | Z-05 | 4 | 1 |
| FR4 历史回显 | H-01、H-02(2) | H-03、H-04 | 3 | 1 |
| 安全 | S-01(1) | — | 1 | 0 |
| **合计** | **16** | **6** | **18** | **4** |

### 6.2 spec 五大风险 + 安全项覆盖对照

| 风险(spec 第四节) | 覆盖案例 |
|---|---|
| ① buy 零鉴权 + ProductDetailPage 回归 | B-01、B-02、B-03、B-05 |
| ② 旧 products 卡不渲染(现状验证) | H-04(前端基线)、H-01(共存不崩) |
| ③ 零结果判定被三级兜底掩盖(含 LLM 挂掉的规则兜底) | Z-01(规则兜底)、Z-02(LLM 在场)、Z-03(反例) |
| ④ 推荐不编造,reason 引用 description | M-02、M-04(抽验) |
| ⑤ 旧 products 卡与 match 卡共存回显 | H-01、H-03 |
| 附加:GLM key 明文入库 | S-01(含 key 轮换提醒) |

### 6.3 异常流/边界自查

- 未登录/伪造身份:B-01(401)、B-02(身份伪造)、B-07(坏 token)、Z-04(悬赏 401)
- 资金异常:B-04(402 余额边界 coins=price-1 / 400 重复购买,且验证不扣款)
- 空结果/降级:Z-01、Z-02、M-03(LLM 超时不 500)
- 数据隔离:H-02、B-02(library/交易/通知不串号)、H-03(换账号)
- 持久化与兼容:H-01(跨重启、新旧卡共存、JSON 可解析)
- 网络错误分支:B-06(按钮恢复可重试,防误置已购)

### 6.4 显式不纳入本版

- 打包价/购物车、沙箱试用、卖家看板、悬赏标签推送(spec 第三节明确留给 v3/v4);
- match 卡的并发抢购/库存竞争(商品为数字内容无限量,无库存语义);
- 真实 LLM 的 10k 消息性能压测(接口稳定后另立专项,M-04 仅为 20 条功能评测)。
