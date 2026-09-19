# SkillBazaar 改造方案：从「技能货架」到「可被雇佣的 Agent 劳动力市场」

> 日期: 2026-09-08  
> 依据: 外部 AI-for-hire / agent marketplace 调研 + 本仓库 `README.md` / `PROJECT_ROADMAP.md` / 现网能力  
> 研究笔记与原文摘录: 会话 scratch `agent_hire_research_notes.md` + `sources/`（含 Agensi、Virtuals、Olas、ClawHire、MCP/A2A/x402/AP2 等 URL）

---

## 0. 一句话结论

SkillBazaar 已具备 **Skill/Agent/Cron/Workflow 商品市场、悬赏（bounty）、Cron 订阅、智能体工作台、BS 导购、积分金币、沙盒/SDK 方向**。外部「让 AI 给别人打工」产品的分水岭不在 UI，而在：

1. **能力可机器发现**（SKILL.md / Agent Card / MCP tools）  
2. **工作可委托与验收**（任务/交付协议，接近悬赏但可 Agent↔Agent）  
3. **结算可自动化**（按次/按结果；x402 或法币授权）  
4. **执行不绑死在平台算力**（与路书「SDK+自部署」一致）

改造应 **保留交易与悬赏内核**，补齐 **协议暴露层**，把「人买技能」扩展为「人/Agent 雇佣能力」。

---

## 1. 外部对标摘要（≥4）

下列产品均在研究 scratch `sources/` 中有可核验摘录（见文末「出处文件」）。

| 产品 | 能力表面 | 协议/清单 | 对 SkillBazaar 的启示 |
|------|----------|-----------|----------------------|
| [Agensi](https://www.agensi.io/skills) | 买卖 `SKILL.md` 技能包（付费/免费） | Agent Skills / SKILL.md | 强化 Skill 标准对齐；导出/导入 SKILL.md |
| [Virtuals Protocol](https://www.virtuals.io/) | Agent 社会：身份、资本、工作、市场、治理；aGDP | 主站叙事 + RNWY 所述 Agent Commerce / Base 发射 | 「打工」= 有身份与收入的 Agent；中期声誉/分成，不必先上全链 |
| [Olas](https://olas.network/) | 共有并变现 AI Agent；Agent 间雇佣/卖服务（Mech） | 链上服务；Agent 作 ERC-721（RNWY 摘录） | Agent 商品应声明「可提供的服务」 |
| [ClawHire](https://clawhire.work/) | 2,520+ MCP Server 目录与安装命令 | **MCP** | 把 SkillBazaar 能力做成 MCP，让 Claude/Cursor「逛店」 |
| [Agoragentic](https://agoragentic.com/) | 权限/预算/审批门控下的 Agent 路由市场；USDC 结算 | **A2A Agent Card** + MCP 工具 | 悬赏/雇佣流程机器化；Card 作为卖方 Agent 名片 |
| [Agentbazaar](https://mcp.so/servers/agentbazaar-mcp) | Agent↔Agent 市场；搜索/调用/雇佣；29 MCP tools | **MCP + A2A** | 悬赏升级为可被 Agent 调用的 work exchange |
| [Synmerco](https://mcp.so/servers/synmerco) | 托管、声誉、争议、协议网关 | MCP + A2A/x402/ERC-8004（列表页声明） | 结算与信任层可插拔，勿绑死单一链 |
| [CrewAI Marketplace](https://marketplace.crewai.com/) | Crew/Flow 模板上架企业店 | 提交页**未**声明 MCP/A2A | Workflow 组合商品对标模板店 |

协议家族（至少两类）：**MCP**、**A2A**；结算族 **x402 / AP2** 为可选第三层。

**已从初稿删除（scratch 中无对应摘录）：** 0xHire、WorkProtocol、MeshLedger。

---

## 2. 协议与能力分层图（勿混为一谈）

```
┌─────────────────────────────────────────────────────────┐
│  D. Settlement / Escrow                                 │
│     x402 (HTTP 402 按次结算) · AP2 (授权凭证) · 积分/金币 │
│     影响：Cron 拉取、Skill 调用、悬赏放款可否自动化        │
├─────────────────────────────────────────────────────────┤
│  C. Discovery / Identity                                │
│     SKILL.md · A2A Agent Card · 可选 ERC-8004 声誉       │
│     影响：商品如何被机器发现、信任如何跨平台携带            │
├─────────────────────────────────────────────────────────┤
│  B. Agent ↔ Agent                                       │
│     A2A Task/Message · /.well-known/agent-card.json     │
│     影响：买方 Agent 直接把活派给卖方 Agent/Cron Worker   │
├─────────────────────────────────────────────────────────┤
│  A. Agent ↔ Tool                                        │
│     MCP tools/resources/prompts                         │
│     影响：把「逛市场/下单/交悬赏」变成工具调用             │
└─────────────────────────────────────────────────────────┘
         ▲
         │  SkillBazaar 今日主战场：人用 Web UI + 虚拟币
         │  明日增量：A/B/C 协议暴露；D 按阶段接入
```

**与现网映射**

| 现网模块 | 今日形态 | 协议层落点 |
|----------|----------|------------|
| Skill 市场 | 人浏览购买，加密源码（虾塘） | C: SKILL.md 元数据；A: MCP `search_skills` / `get_skill` |
| Agent 工作台 | 装配已购 Skill、平台 LLM 执行 | B: 发布为 A2A Agent；A: 运行结果工具化 |
| Cron 订阅 | 发布者执行、订阅者付费拉取 | A: MCP `subscribe_cron`；D: 按次 x402 可选 |
| 悬赏市场 | 人发单/接单/交付/验收 | A+B: `create_bounty` / `submit_delivery`；远期 Agent 投标 |
| 沙盒 / SDK 路书 | 平台沙盒受限；目标 SDK 自部署 | 执行留在用户侧；平台做授权与目录（与 B 方案一致） |

---

## 3. Keep / Add / Defer

### Keep（巩固，不推倒）

- **四类商品市场**（Skill / Agent / Cron / Workflow）与虚拟币、积分等级  
- **悬赏闭环**（发布→申请→交付→验收）——这是「打工」最接近的产品骨架  
- **Cron 订阅**推拉双模  
- **BS 导购（LangGraph）**作为人机入口；后续可让 BS 调 MCP 同源工具  
- **路书方向：SDK + 自部署 / 平台少跑重计算**（避免单机沙盒 concurrent 瓶颈）  
- **外部目录同步**（Gate / BitMart / AgentSkillsHub / Agensi）继续作为供给侧管道  

### Add（改造主线，分阶段）

见 §4 阶段。核心增量：

1. **能力声明标准**：上架物必须可导出为 SKILL.md 或 Agent Card 字段  
2. **SkillBazaar MCP Server**：只读发现 + 受鉴权的购买/悬赏/订阅工具  
3. **Hire / Work Exchange API**：在悬赏之上增加「任务规格、报价、交付物哈希、超时」机器字段  
4. **可选结算适配器**：积分仍默认；x402 用于 metered API；法币走现有/未来 Stripe，不绑死链  

### Defer（明确不做或很晚做）

- 全量 Virtuals 式代币发射与「Agent GDP」叙事  
- 强制所有卖家上 ERC-8004 / 全链托管（合规与 Gas 成本）  
- 自建完整 A2A 多 Agent 编排运行时替代 LangGraph（先做 Card + 委托，不重写编排内核）  
- 复制每一个 MCP.so 上的 hire MCP（只吸收模式，不追目录数量）  
- 一次性重写前端为「纯 Agent 操作系统」  

---

## 4. 分阶段改造方案（结果导向）

### Phase 0 — 对齐与度量（1–2 周）

**结果：** 每个在售 Skill/Agent 有一份机器可读能力摘要；缺口清单可统计。

- 扩展 `products` / seed 字段：`skill_manifest`（对齐 SKILL.md frontmatter）、`input_modes` / `output_modes`、`tools_required`、`execution_locus`=`platform|sdk|cron`  
- 从现有 Agensi 同步管道学习：外部 SKILL.md ↔ 内部商品字段映射表  
- 文档：上架规范「最小 SKILL.md」  

**验收：** 抽样 N 个商品可生成合法 SKILL.md；BS 推荐能读到结构化 tags/modes。

### Phase 1 — MCP 发现与轻交易（2–4 周）**【优先】**

**结果：** Claude Code / Cursor 用户可通过 MCP **搜索并查看** SkillBazaar 商品；登录后可发起购买/订阅意图。

- 实现 `skillbazaar-mcp`（可独立进程）：  
  - `search_catalog` / `get_product` / `list_bounties` / `list_cron_products`  
  - 鉴权后：`purchase_product`、`apply_bounty`、`get_my_library`  
- 与现有 FastAPI `routers/products|bounties|cron` 复用，不平行造一套业务  
- 在 ClawHire/mcp.so 类目录提交条目（运营动作）  

**验收：** 本地 Claude Code `claude mcp add` 后能搜到线上/预发环境商品；购买走现有金币账本。

### Phase 2 — Hire / Work Exchange（与悬赏合流）（3–6 周）

**结果：** 「发活→接活→交活→验收放款」字段对 Agent 友好；人仍可用 Web。

- 悬赏模型增加：`task_spec`（JSON Schema）、`acceptance_tests`、`delivery_artifact_uri`、`sla_hours`  
- MCP/A2A 工具：`create_job`、`bid_job`、`submit_delivery`、`release_payment`  
- 卖家 Agent（平台托管或用户 SDK 回调 URL）可自动 `bid`/`deliver`  

**验收：** 一条端到端「人发悬赏 → MCP 客户端代接 → 交付哈希验收 → 金币释放」；失败路径有超时退款。

### Phase 3 — A2A 发现（并行可裁剪）（2–4 周）

**结果：** 精选 Agent/Cron Worker 暴露 `/.well-known/agent-card.json`（或平台统一域名下的 card 路由）。

- Card 含 `skills[]`、`url`、`authentication`、与商品 ID 的关联  
- 买方 Agent 用 A2A 发 Task，平台做鉴权与计费网关  

**验收：** 外部 A2A 客户端能解析 Card 并完成一次受控任务（可先 mock worker）。

### Phase 4 — 结算升级（按需）（4+ 周）

**结果：** 高价值 metered 调用支持 x402；法币场景评估 AP2，默认仍积分/微信支付宝（路书缺口）。

- Cron 结果拉取、付费 Skill API：`402 + pay → 200`  
- 保持「平台金币」为默认 UX；链上支付为高级卖家选项  
- **不做**：一上来全站 crypto-only  

**验收：** 一次付费 API 调用走通 x402 测试网或模拟器；账本与商品权限一致。

### Phase 5 — SDK 执行外置（与路书 Phase 2 对齐）

**结果：** 重计算在用户 Claude Code / Hermes / 自有沙盒；平台卖授权与协议。

- `pip install skillbazaar`：拉取已购 Skill、校验 license、本地执行  
- 平台沙盒仅 Pro/Team（路书 TIER_LIMITS）  

**验收：** 无平台沙盒也能完成「购买→本地运行→回传可选 telemetry」。

---

## 5. 目标架构草图（改造后）

```
[Human Web UI]     [Claude/Cursor via MCP]     [Remote Agent via A2A]
       │                      │                          │
       └──────────┬───────────┴────────────┬─────────────┘
                  ▼                        ▼
           SkillBazaar API (FastAPI)
           ├─ Catalog / Wallet / Bounty / Cron / Agents
           ├─ Manifest service (SKILL.md ↔ DB)
           └─ Settlement adapters (coins | x402 | later AP2)
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
  SQLite DB   Seed/Crawl   User SDK / optional Sandbox
```

---

## 6. 风险与原则

1. **协议跟风风险** — 只把 MCP/A2A 当适配器，业务真相仍在悬赏与商品表。  
2. **安全** — MCP/A2A 暴露购买与交割必须强鉴权；Skill 源码继续虾塘加密，协议只暴露能力描述与授权句柄。  
3. **合规** — 链上支付/ERC-8004 延后；中国大陆用户默认法币/积分路径。  
4. **供给质量** — 对齐 Agensi 式扫描再上架，避免「可雇佣」变成「可投毒」。  
5. **算力** — 严格执行路书：平台不承诺无限沙盒并发。  

---

## 7. 建议的「最小可感知成功」

**6 周内交付：** Phase 0 + Phase 1 + 悬赏字段增强（Phase 2 的一半）。  

用户故事：开发者在 Claude Code 里说「帮我在 SkillBazaar 找一个能做代码审查的 Skill 并买下」，MCP 完成搜索与购买；另有一条悬赏可被 MCP 列出并申请。

这比「再做一个 Agent 聊天站」更贴近外部「打工」市场，且咬合现有 **Skill 市场 / 悬赏 / Cron / SDK 路书**。

---

## 8. 参考链接与 scratch 出处文件

| 主题 | URL | Scratch 文件 |
|------|-----|----------------|
| Agensi | https://www.agensi.io/skills | `sources/agensi2.txt` |
| Virtuals 主站 | https://www.virtuals.io/ | `sources/virtuals2.txt` |
| Virtuals/Olas 列表细节 | https://rnwy.com/blog/where-to-list-ai-agent | `sources/rnwy_full.txt` → `rnwy_virtuals_olas_excerpt.txt` |
| Olas 主站 | https://olas.network/ | `sources/olas2.txt` |
| ClawHire | https://clawhire.work/ | `sources/clawhire.txt` |
| Agoragentic | https://agoragentic.com/ | `sources/agoragentic.txt` |
| Agoragentic A2A Card | GitHub `rhein1/agoragentic-integrations` | `sources/a2a_card_sample.txt` |
| Agentbazaar | https://mcp.so/servers/agentbazaar-mcp | `sources/agentbazaar_mcp.txt` |
| Synmerco | https://mcp.so/servers/synmerco | `sources/synmerco.txt` |
| CrewAI Marketplace | https://marketplace.crewai.com/ | `sources/crewai_mkt.txt` |
| MCP intro | https://modelcontextprotocol.io/introduction | `sources/mcp2.txt` |
| A2A discovery | a2aproject/A2A docs | `sources/a2a_discovery_raw.md` |
| x402 | https://github.com/x402-foundation/x402 | `sources/x402_readme.md` |
| AP2 | google-agentic-commerce/AP2 | `sources/ap2_index.md` |
| Agent Skills | https://agentskills.io/ | `sources/agent_skills.txt` |
| mcp.so #marketplace 索引 | https://mcp.so/tag/marketplace | `sources/workprotocol_mcp.txt` |

研究笔记: scratch `agent_hire_research_notes.md`

---

*本文为研究型改造方案，不包含协议服务端/支付实现代码（目标 Non-goals）。*
