# SkillBazaar Agent Team — 迭代状态

| 字段 | 值 |
|------|-----|
| 当前版本 | v3(实现中) |
| 已完成版本 | 2 / 12 目标 |
| 阶段 | Wave 3: DEV TDD 实现 v3(限流→截断→前端按钮→评测/标注) |

## 团队分工
- **产品 (PM)**: 维护 docs/agent-team/spec.md,每版选定 1-3 个可落地改进项
- **测试 (QA)**: 根据当版 spec 写测试案例 → docs/agent-team/test-cases-vN.md
- **开发 (DEV)**: 按测试案例实现,经 code-reviewer 审查
- **营销 (GTM)**: 调研痛点 → docs/agent-team/marketing-insights.md,反哺下版 spec

## 版本日志
(迭代时追加: vN — 改动摘要 — 测试结果)

## 时间线
- [Wave1] PM spec v1 完成:商品评价体系 / BS助手会话持久化 / 站内通知真实化(docs/agent-team/spec.md)
- [Wave1] QA 开始写测试案例(test-cases-v1.md);营销调研仍在进行
- [Wave1] 营销调研完成(docs/agent-team/marketing-insights.md):Top3 机会 = BS助手撮合闭环 / Skill交付即验证 / 防泄露交付+卖家看板。结论:下一版应做「描述任务→沙箱试用→一键购买装配」闭环。已作为 v2 spec 的输入素材。
- [Wave1] 当前:QA 写测试案例中,完成后进入 DEV 实现 v1
- [Wave1] QA 完成:25 条案例(P0 17),后端 19 条测试先行,风险提示:chat 路由鉴权需统一
- [Wave1] DEV 开始 TDD 实现 v1(先写测试再实现,含 code review 前置)
- [Wave1] DEV 中断(输出损坏):评价体系✅ 会话持久化✅ 通知❌。实测 pytest:31/36 过,5 条通知测试失败。已让 DEV agent 带上下文续修。
- [Wave1] DEV 完成 v1(续修后):36/36 后端测试过,前端 build 成功。交付:评价体系+会话持久化+通知中心;chat 鉴权统一为 Bearer(破坏性变更,前端已同步);LLM 503 期间加了规则兜底搜索。遗留:6 条前端手动验收案例待 QA 浏览器实测;卖家金币结算未做(超范围)。
- [Wave1] code-reviewer 开始审查 v1 改动
- [Wave1] code review 完成(协调者亲审,review agent 因 429 配额失败):无 CRITICAL/HIGH。LOW x2:评价重复校验竞态会 500(有 DB 唯一约束兜底)、list_reviews 串行查询。v1 ✅ 收官。
- [v1 总结] 交付:评价体系/会话持久化/通知中心;36/36 测试过;build 过。改文件:database.py models.py routers/{products,chat}.py services/{product,chat,transaction,bounty,cron,notification}_service.py agents/{bs_agent,nodes}.py 前端 6 组件+api.js
- [Wave2] 启动:PM 写 spec v2,方向=营销 Top1(BS 助手撮合闭环:描述任务→拆解→Skill 组合推荐→一键购买;无解引导发悬赏)
- [Wave2] PM spec v2 完成(docs/agent-team/spec-v2.md):FR1 拆解+match卡 / FR2 一键购买(需先修 buy 无鉴权!) / FR3 无匹配引导发悬赏 / FR4 历史回显。风险:buy 零鉴权、products 卡不渲染、兜底掩盖零结果、LLM 编造、GLM key 明文 nodes.py:8
- [Wave2] QA 写测试案例 v2 中
- [Wave2] QA 完成:22 条案例(P0 18),B-01/S-01 当前即 RED。最大风险:do_search 三级兜底会永久掩盖零结果,Z-01 必须先行转 RED
- [Wave2] DEV 开始 TDD 实现 v2(含 buy 鉴权修复、GLM key 迁移环境变量)
- [Wave2] DEV 完成 v2:51/51 测试过+build 成功(协调者已实测复核)。交付:match 卡+一键购买、buy 鉴权修复、零结果悬赏引导(删三级兜底)、5 处明文 key 全部环境变量化、防 LLM 编造。运营项:旧 GLM key 已入 git 历史,须平台侧轮换作废;建议补 .env.example
- [Wave2] code-reviewer 审查 v2 中
- [Wave2] v2 review:0C/1H/6M/2L。HIGH=match 卡当轮不显示(ChatPanel 入栈不带 card)。已让 DEV 修复 H1+M2/3/5/6/7+LOW IDOR+M4 低成本部分
- [⚠️ 中断] DEV 修复 v2 review 问题时 429 配额耗尽(重置 15:21)。工作区处于修复中间态:40 passed/11 failed(M#2 半成品相关)。修复进度与接手指引见 docs/agent-team/HANDOVER.md
- [Wave2] v2 ✅ 收官:review 全部修复(H1 当轮卡片就地入栈 / M2 参数归一化+异常分离 / M3 steps上限 / M4 key缺失可观测+风控不写伪数据 / M5 表单卡派生状态 / M6 只读摘要 / M7 isComposing / LOW IDOR 403)。54/54 测试过+build 过(协调者实测复核)。进度 2/12
- [Wave3] 启动:PM 写 spec v3,方向=营销 Top2「Skill 交付即验证」(上架评测报告+免登录沙箱试用+兼容性标注)
- [Wave3] PM spec v3 完成(docs/agent-team/spec-v3.md):①上架自动评测报告 ②免登录 30s 试用(限流先行!) ③兼容性标注。关键勘察:execute 端点本就免登录可复用,sandbox 因 users.sandbox_quota 不适用匿名。最大风险:免登录执行成本裸奔,FR2.1 限流必须先于前端入口
- [Wave3] QA 写测试案例 v3 中
- [Wave3] QA 完成:23 条(P0 21),证据:execute 裸奔且 max_calls=3 只发证不拦截,限流闸门必须先行
- [Wave3] DEV 开始 TDD 实现 v3,强制顺序:限流→截断脱敏→前端试用按钮→评测/标注
- [Wave3] DEV agent(a89215a) 启动 TDD 实现:3 个新测试文件(test_skill_eval/test_trial_rate_limit/test_compat_labels) + 6 个服务/路由/模型改动
- [Wave3] 营销调研 v4 方向已定:防泄露交付(运行时调用拿结果不拿源码) + 卖家收入看板(marketing-insights.md Top3 剩余两项)
