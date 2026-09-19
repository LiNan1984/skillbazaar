# SkillBazaar spec v3 — Skill 交付即验证

> PM: v3 迭代 | 主题来源: marketing-insights.md 机会2(对症 GPT Store 式"信任崩塌":买家看不到能力真假)
> 前置阅读: spec-v2.md / STATE.md | 本版 3 个改进项,均围绕「让买家在购买前/购买时亲眼看到能力真实运行」

## 0. 现状勘察结论(已读代码,DEV 必读)

| 存量代码 | 状态 | v3 复用方式 |
|---|---|---|
| `backend/services/execution_service.py` | ✅ 可用:`execute_skill()` 支持 prompt(真实调 LLM)/code(占位)/sdk(转发 endpoint)三类,自动写 `skill_executions` 表 | 改进项1、2 的执行内核,不重写 |
| `backend/routers/skills.py` `POST /api/skills/{id}/execute` | ✅ 已存在且**本就免登录**(user_id 缺省 "anonymous"),自动建 trial license(max_calls=3) | 改进项2 直接在此之上加固,不新开沙箱 |
| `backend/routers/skills.py` `POST /api/skills/upload` | ✅ 上架上传入口(Fernet 加密入 `skill_assets` 表) | 改进项1 在此挂评测钩子 |
| `backend/services/sandbox_service.py` + `routers/sandbox.py` | ✅ 已注册(main.py:50)。⚠️ 但 `get_or_create_sandbox` 依赖 `users.sandbox_quota`(匿名用户无此行会返回 no_quota),且 `DB_PATH` 默认指向 `/root/skillbazaar/...`(与 database.py 的相对路径不一致) | **v3 不用于匿名试用**,仅登录沙箱沿用 |
| `backend/services/manifest_service.py` | ✅ 已从 catalog 派生 Agent-Skills SKILL.md(无额外列) | 改进项3 让 compat 字段透传进 manifest |
| `backend/database.py` | products 表无 compat 列;有 `skill_executions`、`skill_lifecycle` | 改进项3 加列,改进项1 加新表 |
| `frontend/src/pages/ProductDetailPage.jsx` 220-260 行 | 已有「trySkill」区块,但未购用户只看到购买按钮,无真实试用 | 改进项1/2/3 的展示位 |

---

## 改进项 1:上架自动评测报告

**动机**(营销画像 B1/B2):GPT Store 死于"零质量信号、spam 泛滥"。SkillBazaar 目前上架零校验——一段加密文本直接进库,买家无从判断真假好坏。评测报告 = 平台背书的第一信号。

**用户故事**:作为卖家,我上传 Skill 后无需任何操作,平台自动跑一遍检查,生成"通过项/风险项/示例输出"报告,帮我在买家提问前就自证可用;作为买家,我在详情页直接看到这份报告再决定买不买。

**FR 列表**:
- FR1.1 `POST /api/skills/upload` 成功后异步触发评测(不阻塞上传响应,后台任务 5 分钟内完成)
- FR1.2 静态检查:内容非空且 UTF-8 可解码、加密完整性(content_hash 校验)、prompt 类检查长度(>50 字符)与明显注入模式(`ignore previous|reveal your prompt`);code/sdk 类检查 sdk_endpoint 可达性(sdk 类)
- FR1.3 冒烟执行:prompt 类调 `execute_skill()` 用平台内置样例输入真实跑一次,截取输出前 500 字作为"示例输出";code 类标注"需沙箱运行"(本期不真实执行)
- FR1.4 结果落新表 `skill_eval_reports`(product_id 唯一,重复上传/重新评测覆盖,版本计数 +1),字段含:passed_items JSON、risk_items JSON、sample_output、status(pending/pass/warn/fail)、evaluated_at
- FR1.5 `GET /api/products/{id}` 与 `GET /api/products/{id}/eval-report` 返回报告;无报告返回 `{status: "pending"}`
- FR1.6 详情页展示报告卡:通过项绿勾/风险项黄叹号/示例输出折叠块;报告缺失显示"评测中"骨架

**后端改动点**:新 `backend/services/eval_service.py`(静态检查+冒烟,内部调 `execution_service.execute_skill`);`backend/routers/skills.py` upload 末尾挂 `asyncio.create_task`;`backend/routers/products.py` get_product 附带报告;`backend/database.py` 建表 + `insert_skill_eval_report/fetch_skill_eval_report`;`backend/models.py` 加 EvalReport 模型
**前端改动点**:`frontend/src/services/api.js` 加 `getEvalReport`;`frontend/src/pages/ProductDetailPage.jsx` trySkill 区块上方插入评测报告卡;`frontend/src/styles/index.css` 报告卡样式
**验收标准**:
1. 上架一个 prompt 类 Skill(mock LLM),`GET /api/products/{id}/eval-report` 在 5s 内可查到 `status` 非 pending,`sample_output` 非空
2. 上传含 "ignore previous instructions" 的 prompt,报告中 `risk_items` 包含 injection 命中项,`status` 为 warn(不拦截上架)
3. 空文件上传被静态检查标 fail,`passed_items` 为空
4. 重复评测同一商品,`skill_eval_reports` 中该 product_id 仍只有一行且 version 递增
5. 现有 54 条测试不回归;新增 ≥6 条 pytest(eval_service 单测 + upload 触发集成测试,mock httpx)
**非目标**:不做自动拦截下架(只标注);不做 LLM 打分;code 类不做真实沙箱执行;不做卖家申诉流

## 改进项 2:免登录 30 秒试用

**动机**(画像 B2/B4 + v2 已修的 buy 鉴权形成反差):试用的本质是"先验货后付款"。现状是反的——`POST /api/skills/{id}/execute` 本就免登录且自动发 trial license(max_calls=3),但**无任何限流**,等于把 LLM 成本裸露给全网刷接口;而前端详情页根本没接这个接口,买家看不到。v3 做两件事:把已有能力安全地暴露出去。

**用户故事**:作为未登录访客,我在商品详情页点「30 秒试用」,输入一句话,10 秒内看到该 Skill 的真实输出,不用注册、不用配任何 API Key。

**FR 列表**:
- FR2.1 复用 `POST /api/skills/{product_id}/execute`,user_id 缺省 anonymous;新增按 IP 的内存限流:同一 IP 对同一商品 10 次/小时,全局 30 次/小时/IP,超限 429 + Retry-After
- FR2.2 trial license 沿用现有 max_calls=3 逻辑(已有);响应增加 `trial_remaining` 字段(该匿名 license 剩余次数)
- FR2.3 输入限制:input_params ≤2000 字符;执行超时沿用 execution_service 内部 30s timeout;`max_tokens` 由 1024 降至 512(试用专用,正式购买后走全量)
- FR2.4 输出脱敏:试用输出截断至 500 字,尾部追加"购买后解锁完整输出";不回传 skill 源文(现状已满足,加 pytest 断言防回归)
- FR2.5 详情页「30 秒试用」按钮(免登录可见,已购用户保持现有入口),弹层输入→加载态→展示输出;429 时展示"今日试用次数已达上限"
- FR2.6 试用行为写 `skill_executions`(user_id=anonymous+IP后缀),供后续风控/统计

**后端改动点**:`backend/routers/skills.py` execute 端点加固(限流中间件函数 + trial_remaining);`backend/services/execution_service.py` 加 trial_mode 参数(512 token、500 字截断);`backend/services/risk_detector.py` 不动(限流独立小模块放 skills.py 或新 limiter 工具)
**前端改动点**:`frontend/src/pages/ProductDetailPage.jsx` trySkill 区块加试用按钮+弹层;`frontend/src/services/api.js` `executeSkill` 支持 anonymous 调用;`frontend/src/components/PurchaseModal.jsx` 不动
**验收标准**:
1. 未登录(无 Authorization 头)POST execute 正常返回 output;连续第 11 次同商品调用返回 429
2. 试用输出 ≤500 字且含截断提示;pytest 断言响应不含 skill 加密原文/明文 prompt 全文
3. 匿名 trial license 满 3 次后返回次数耗尽错误(前端文案可读)
4. 已登录用户走同一端点不受 IP 试用限流影响(以 user_id 优先)
5. 新增 ≥5 条 pytest(限流计数、截断、license 次数、脱敏),54 条存量不回归
**非目标**:不做验证码/设备指纹;code 类试用仍返回占位说明(依赖改进项3 标注"需购买后在沙箱运行");不做试用→购买的数据归因分析

## 改进项 3:兼容性标注(适用环境)

**动机**(Dify 教训,issue 41048:`minimum_dify_version` 是 no-op 装了就坏):"买来用不起来"是企业买家流失首因。SkillBazaar 商品目前无任何环境声明,prompt/code/sdk 三类的运行前提完全不同,买家无从预判。

**用户故事**:作为买家,我在搜索列表就能筛"只看 prompt 类/prompt+SDK 类",在详情页一眼看到"需要 GLM 兼容接口、输入为纯文本、无需本地依赖",避免买了装不上。

**FR 列表**:
- FR3.1 products 表新增 `compat` TEXT 列(JSON,默认 null),结构:`{runtime: "prompt|code|sdk", llm_required: bool, sdk_endpoint_required: bool, input_format: "text|json", note: string}`;建表语句用 `ALTER TABLE ... ADD COLUMN` 迁移(幂等,参照库内现有迁移风格)
- FR3.2 `ProductCreate`/`ProductResponse` 增加可选 `compat` 字段;上架/发布接口透传;未填时后端按 skill_type 自动推导默认值(prompt→llm_required:true 等,与 skill_assets 的 skill_type 一致)
- FR3.3 `GET /api/products` 新增查询参数 `runtime`(单值或逗号分隔),过滤逻辑进 `product_service.list_products`;无 compat 数据的老商品按 tags/skill_assets 推导兜底
- FR3.4 详情页 compat 徽章行(runtime 图标 + "需联网 LLM" + "输入格式:文本"等);发布页(PublishPage)增加可选"适用环境"表单区
- FR3.5 `manifest_service.py` 派生 SKILL.md 时把 compat 写入 frontmatter(`compat:` 块),MCP/discovery 消费方自动可见

**后端改动点**:`backend/database.py` 迁移+字段读写;`backend/models.py` ProductCreate/Response;`backend/routers/products.py` list 参数;`backend/services/product_service.py` 过滤与默认推导;`backend/services/manifest_service.py` frontmatter;新 `backend/tests/test_compat_filter.py`
**前端改动点**:`frontend/src/pages/ProductDetailPage.jsx` 徽章行;`frontend/src/pages/HomePage.jsx` 列表卡小徽章+筛选下拉(仅 runtime 一维,不做多维筛选);`frontend/src/pages/PublishPage.jsx` 表单区;`frontend/src/services/api.js` listProducts 带 runtime 参数
**验收标准**:
1. 建库脚本在新旧库(有/无历史数据)上均可执行,二次启动不重复加列
2. `GET /api/products?runtime=prompt` 只返回 prompt 类;`runtime=prompt,sdk` 返回两类
3. 未传 compat 的商品详情页仍显示由 skill_type 推导的默认徽章(不出现空白)
4. manifest 产物含 `compat:` frontmatter 且为合法 YAML 键值(test_manifest_mcp.py 风格的断言)
5. 新增 ≥5 条 pytest,存量不回归;前端 build 通过
**非目标**:不做版本号语义化校验(如 requires_glm>=5);不做多维组合筛选;不做兼容性自动探测(评测报告属改进项1,本期不联动)

---

## 依赖与顺序
改进项1/2 共享 execution_service 改动(trial_mode),1 与 2 可并行开发;3 完全独立。建议实现顺序:2(风险最低、复用最多)→ 1 → 3。评测(1)冒烟调用复用 2 的 trial_mode 限流参数。

## 全局风险
- **最大风险:免登录执行的成本面**。execute 端点现状全网裸奔(可刷 LLM),v3 上线的第一件事必须先落 FR2.1 限流再放开前端按钮,顺序颠倒会造成成本事故。内存限流重启即失效属已知取舍(单机部署),记录在案不做持久化。
- sandbox_service 的 DB_PATH 环境差异(`/root/...` vs 相对路径)未在本版修——匿名试用刻意绕开 sandbox,登录沙箱问题留 v4。
- LLM 不可用(503)时评测报告与试用都会失败:评测标 `fail` 并写入原因,试用返回友好错误,不做规则兜底(v2 已删兜底的教训保持)。

## v4 候选
1. 沙箱试用统一:登录用户的 code 类 Skill 真实进 sandbox_service 执行(需先修 sandbox DB_PATH 与匿名 quota 体系)
2. 试用确认期退款:购买后 N 小时内不满意,虚拟币原路退(营销报告机会2 第4条验收)
3. 评测报告 v2:code 类冒烟执行 + LLM 输出质量打分 + 定期复验("最近验证时间超 30 天标灰")
4. 卖家收入看板(营销机会3):销量/复购/悬赏引用
5. 一键导入 Claude/Codex 格式 skill 目录,自动推导 compat 标注
