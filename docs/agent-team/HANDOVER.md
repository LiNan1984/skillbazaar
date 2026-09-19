# SkillBazaar Agent Team 交接文档

> 生成时间:2026-09-18 12:00 前后 · 交接原因:API 5 小时配额耗尽(429),DEV 修复中断,配额重置于 **15:21:57 +0800**
> 团队协作全记录见 `docs/agent-team/STATE.md`(时间线)与各 spec / test-cases / marketing-insights 文档

---

## 一、项目与团队机制

- **项目**:SkillBazaar — AI Agent/Skill/Cron/Workflow 交易平台,FastAPI(backend/,aiosqlite,SQLite 单文件)+ React+Vite(frontend/src/)+ LangGraph BS 导购助手
- **团队流水线**(每版一轮):营销 GTM 调研痛点 → PM 写 spec → QA 写测试案例(TDD 先行)→ DEV 实现 → code review → 修 CRITICAL/HIGH → 收官记账 → 下一版
- **目标**:迭代 12 版 · **已完成 1 版(v1)**,v2 进行到 review 修复阶段
- **测试命令**:`cd backend && python3 -m pytest tests/ -q` · **构建**:`cd frontend && npm run build`

## 二、版本状态

### v1 ✅ 已收官(36/36 测试通过,review 通过)
交付:①商品评价体系(`product_reviews` 表 + 仅已购可评 + 均分事务回写)②BS 助手会话持久化(`chat_messages` 表 + Bearer 统一,破坏性变更已同步前端)③站内通知中心(购买/悬赏 4 节点/Cron 推送埋点 + NotificationBell 铃铛)
遗留 LOW:评价重复校验竞态(DB 唯一约束兜底)、list_reviews 串行查询

### v2 ⚠️ 中断在 review 修复阶段(当前工作区 **40 passed / 11 failed**)
**已完成**(51/51 全绿时):
- FR1 match 组合推荐卡(两阶段 LLM:拆步→真实搜索选品,reason 强制引用 description 防编造,规则兜底)
- FR2 buy 接口 Bearer 鉴权修复(原信任 body.buyer_id,零鉴权)+ MatchCard 卡内一键购买(402 余额/400 已购/confirm 三步成交)
- FR3 零结果悬赏预填卡(删除三级放宽兜底,基于原始意图参数判定)
- FR4 历史回显(FORM_CARD_TYPES/INTERACTIVE_CARD_TYPES 分离)
- S-01:**5 处明文 API key 全部迁环境变量**(`LLM_API_KEY` 等,涉 nodes/execution_service/risk_detector/sandbox_service/proactive_agent)

**Review 结论**:0 CRITICAL / 1 HIGH / 6 MEDIUM / 2 LOW。DEV 按清单修复时被 429 打断。

**修复进度**(实测核实):
| 项 | 内容 | 状态 |
|---|---|---|
| HIGH#1 | ChatPanel 当轮机器人消息不带 card,match 卡刷新才可见 | ⚠️ 未确认(git diff 显示 ChatPanel 已改 166 行,但 isComposing 即 #7 未找到,入栈带卡需人工核验) |
| M#2 | 搜索参数归一化(_coerce_price/category 白名单)+ 异常与真零行分离 | ❌ 未做(grep 无 _coerce_price),**11 条失败测试可能与此半成品改动有关** |
| M#3 | steps 截断 [:4] / title [:60] | ❌ 未做 |
| M#4 | LLM_API_KEY 空 key 启动 WARNING + risk_detector 不写伪结果 | ❌ 未做 |
| M#5 | activeCard 悬挂(每轮 setActiveCard(card?.step==='fill' ? card : null)) | ❌ 未做 |
| M#6 | 历史回放仅最后一张同类型表单卡可交互,其余只读 | ❌ 未做 |
| M#7 | Enter 发送判 `e.nativeEvent.isComposing`(输入法误发) | ❌ 未做 |
| LOW | transactions.py GET /user/{id}、/library/{id} 存量 IDOR 加 Bearer | ⚠️ transactions.py 有 20 行改动,需核验 |

**11 条失败测试**(均为 v2 新增文件,属修复中断态,非回归):test_chat_history 3 条、test_match_cards 4 条、test_zero_result_bounty 4 条

## 三、接手人下一步(按序)

1. **恢复 DEV**:可直接 `SendMessage` 续原 DEV agent(有完整上下文),或新开 agent 重发修复清单(见 STATE.md 尾部与 v2 review 报告)。修完标准:pytest 全绿(51 条)+ build 成功
2. **v2 收官**:STATE.md 记账(注意 git 工作区含 v0 之前的存量未提交改动,本团队改动不 commit,由用户决定)
3. **v3 spec**(方向已定,营销 Top2):**Skill 交付即验证** — 上架自动评测报告 + 30 秒免登录沙箱试用 + 兼容性标注(素材:marketing-insights.md Top3;候选池:spec.md 尾部)
4. v4 候选(营销 Top3):防泄露交付(运行时调用拿结果不拿源码)+ 卖家收入看板

## 四、需要用户决策/操作的运营项

1. 🔴 **旧 GLM key 轮换**:`sk-bV3…` 与 `sk-QW108…` 已入 git 历史,代码已迁环境变量但 key 本身必须平台侧作废;部署时注入 `LLM_API_KEY`
2. 建议补 `.env.example`(仅占位符,团队未越权创建)
3. v1/v2 共 12 条前端手动验收案例待人工过一遍(test-cases-v1.md / test-cases-v2.md 中标注手动者)
4. M-04(20 条真实任务 LLM 评测)需真实 key 在预发跑,`@pytest.mark.llm_live`
5. 上游 LLM `api.finmall.com` 开发期间多次 503,已有规则兜底,但生产需确认其可用性

## 五、文档索引

| 文件 | 内容 |
|---|---|
| docs/agent-team/STATE.md | 全时间线(每版进展逐条) |
| docs/agent-team/marketing-insights.md | 竞品与痛点调研(Top3 机会,真实来源链接) |
| docs/agent-team/spec.md / spec-v2.md | v1/v2 开发文档 |
| docs/agent-team/test-cases-v1.md / -v2.md | 测试案例(含风险对照表) |
