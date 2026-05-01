# BS买卖助手 Copilot 设计文档

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 BS买卖助手 改造为真正的 AI Copilot——在聊天窗口内通过 H5 卡片完成搜索、发布商品、发布悬赏、技能分析等全部操作。

**Architecture:** LangGraph StateGraph 多意图路由 + 内存会话持久化。前端 ChatPanel 支持渲染内嵌表单卡片，用户可在卡片上直接编辑、预览、提交。后端通过意图识别自动切换路由，返回卡片 JSON 给前端渲染。

**Tech Stack:** LangGraph 0.6 + MemorySaver (内存) + FastAPI SSE (流式可选) + React 卡片组件 + httpx async

---

## 一、参考设计（小易银行助手模式）

聊天助手首页展示：
1. **欢迎语 + 快捷入口卡片**（搜索商品、发布 Skill、发布 Agent、发悬赏、上传 Cron）
2. **功能列表**（点击快捷入口直接进入对应表单卡片）
3. **内嵌表单卡片**（在聊天气泡中渲染，可编辑、可预览、可提交）
4. **文字填槽**（用户说"名字叫XX"自动填入卡片对应字段）
5. **会话持久化**（关闭重开恢复上下文，继续编辑未完成的卡片）

---

## 二、后端架构

### 2.1 LangGraph 状态定义

```python
class AgentState(TypedDict):
    messages: list[dict]          # 对话历史
    intent: str                   # search/publish/bounty/analyze/chat
    card: dict | None             # 当前活跃卡片 {type, data, step}
    search_params: dict           # 搜索参数
    search_results: list          # 搜索结果
    final_reply: str              # 回复文本
    products_json: str            # 商品JSON
```

### 2.2 图结构

```
用户消息 → classify_intent (1次快速LLM, max_tokens=16)
                │
    ┌───────────┼──────────┬──────────┬──────────┐
    │           │          │          │          │
  "search"  "publish"  "bounty"  "analyze"  "chat"
    │           │          │          │          │
  do_search  do_publish  do_bounty  do_analyze  do_chat
  (1次LLM)   (提取卡片)  (提取卡片)  (1次LLM)   (1次LLM)
    │           │          │          │          │
    └───────────┴──────────┴──────────┴──────────┘
                         │
                      END
```

**节点说明：**
- `classify_intent`: 快速意图分类，返回 search/publish/bounty/analyze/chat
- `do_search`: 一次 LLM 调用提取搜索参数 + 搜索商品 + 生成推荐回复
- `do_publish`: 从消息中提取已有信息，返回 publish 卡片 JSON（预填充）
- `do_bounty`: 从消息中提取已有信息，返回 bounty 卡片 JSON（预填充）
- `do_analyze`: 分析用户需求，返回应该开发什么 Skill 的建议
- `do_chat`: 闲聊回复

### 2.3 会话持久化

用 LangGraph `MemorySaver` 按 `user_id` 存储 thread：
```python
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()
graph = build_graph().compile(checkpointer=checkpointer)

# 调用时
config = {"configurable": {"thread_id": user_id}}
result = await graph.ainvoke(state, config)
```

支持：
- 多轮对话间保持卡片状态
- 关闭重开恢复上下文
- 用户可以在新消息中用文字修改卡片字段

### 2.4 卡片 JSON 格式

**发布商品卡片：**
```json
{
  "reply": "好的！帮您发布商品，请确认以下信息：",
  "products": [],
  "card": {
    "type": "publish",
    "step": "fill",
    "data": {
      "name": "用户提到的名字",
      "description": "",
      "category": "Skill",
      "sub_category": "",
      "price": null,
      "skill_type": "prompt",
      "tags": [],
      "content_preview": "",
      "github_url": ""
    }
  }
}
```

**发布悬赏卡片：**
```json
{
  "reply": "帮您发布悬赏任务！",
  "card": {
    "type": "bounty",
    "step": "fill",
    "data": {
      "title": "用户提到的标题",
      "description": "",
      "category": "Agent",
      "budget_min": null,
      "budget_max": null,
      "deadline": "",
      "skill_type": "code",
      "requirements": ""
    }
  }
}
```

**技能分析卡片：**
```json
{
  "reply": "基于您的需求分析如下：",
  "card": {
    "type": "analysis",
    "step": "result",
    "data": {
      "market_demand": "高需求",
      "suggested_type": "Agent",
      "suggested_price": "200-500",
      "competition": "中等",
      "recommendation": "建议开发一个实时监控类Agent...",
      "similar_products": [{"id": 68, "name": "...", "price": 89}]
    }
  }
}
```

**卡片 step 流转：**
- `fill` → 用户编辑中
- `preview` → 预览确认中
- `done` → 已提交（显示结果链接）
- `edit` → 用户要求修改（从 preview 回到 fill）

### 2.5 文字填槽机制

当用户在对话中补充信息时（如 "价格改成200"、"分类是Agent"），LLM 提取结构化信息：
```json
{"slot_updates": {"price": 200, "category": "Agent"}}
```
后端合并到当前卡片的 data 中，返回更新后的卡片。

### 2.6 API 改动

**修改 `POST /api/chat`：**
- 请求体增加 `card` 字段（前端传回当前卡片状态）
- 响应体增加 `card` 字段（后端返回新/更新的卡片）

```python
class ChatRequest(BaseModel):
    message: str
    user_id: str
    card: dict | None = None  # 前端传回当前卡片状态

class ChatResponse(BaseModel):
    reply: str
    products: List[ProductResponse] = []
    card: dict | None = None  # 返回卡片
```

---

## 三、前端架构

### 3.1 ChatPanel 改造

**新增状态：**
```javascript
const [card, setCard] = useState(null)  // {type, step, data}
```

**消息类型扩展：**
```javascript
// 消息可以是：
{ role: 'user', content: '...' }
{ role: 'bot', content: '...' }
{ role: 'bot', content: '...', card: { type: 'publish', step: 'fill', data: {...} } }
```

### 3.2 首页快捷入口

打开聊天时展示欢迎语 + 快捷按钮（类似小易银行）：

```
🤖 您好！我是 BS买卖助手，您的 AI 交易 Copilot。

[🔍 搜索商品]  [📦 发布 Skill]
[🤖 发布 Agent] [⏰ 上传 Cron]
[🎯 发悬赏]    [📊 Skill 分析]
```

点击按钮直接触发对应意图，助手返回对应卡片。

### 3.3 内嵌表单卡片组件

**PublishCard 组件（嵌入在聊天气泡中）：**

```
┌─────────────────────────────────┐
│ 📦 发布商品                      │
├─────────────────────────────────┤
│ 商品名称  [可编辑输入框]          │
│ 商品描述  [可编辑文本域]          │
│ 分类      [下拉选择]             │
│ 定价      [数字输入] 金币         │
│ 技能类型  [Prompt/Code/SDK]      │
│ 文件上传  [选择文件按钮]          │
├─────────────────────────────────┤
│         [预览]  [取消]           │
└─────────────────────────────────┘
```

**BountyCard 组件（嵌入在聊天气泡中）：**
```
┌─────────────────────────────────┐
│ 🎯 发布悬赏                      │
├─────────────────────────────────┤
│ 任务标题  [可编辑输入框]          │
│ 任务描述  [可编辑文本域]          │
│ 分类      [下拉选择]             │
│ 预算范围  [最小] - [最大] 金币    │
│ 截止日期  [日期选择]             │
├─────────────────────────────────┤
│         [预览]  [取消]           │
└─────────────────────────────────┘
```

**预览模式：**
```
┌─────────────────────────────────┐
│ ✅ 确认发布                      │
├─────────────────────────────────┤
│ 名称: 交易策略 Skill             │
│ 分类: Skill / 交易               │
│ 价格: ¥299 金币                  │
│ 类型: Prompt                     │
├─────────────────────────────────┤
│    [← 修改]  [确认发布]          │
└─────────────────────────────────┘
```

**完成模式：**
```
┌─────────────────────────────────┐
│ ✅ 发布成功！                    │
│ 商品「交易策略 Skill」已上架      │
│ [查看商品详情]  [继续发布]        │
└─────────────────────────────────┘
```

### 3.4 卡片交互流程

1. 用户输入/点击快捷按钮 → 发送消息到后端
2. 后端返回 `card` → ChatPanel 渲染卡片组件
3. 用户在卡片上编辑字段 → 更新本地 card state
4. 用户点「预览」→ 卡片 step 变为 preview
5. 用户点「确认发布」→ 前端直接调用 `createProduct` + `uploadSkill` / `createBounty` API
6. 成功后 → 卡片变为 done 模式，显示结果链接

### 3.5 文字填槽交互

用户输入文字修改卡片字段：
1. 用户: "价格改成200"
2. 前端将当前 `card` 连同消息一起发送到后端
3. 后端识别为 slot_update → 合并到卡片 data → 返回更新后的卡片
4. 前端重新渲染卡片（价格字段已变为200）

### 3.6 会话持久化

- 前端: `card` state 存入 `localStorage`（key: `skillbazaar_card_${userId}`）
- 打开聊天时检查 localStorage → 恢复未完成的卡片
- 后端: LangGraph MemorySaver 按 thread_id 保持对话历史

---

## 四、文件改动清单

### 后端新增/修改
| 文件 | 改动 |
|------|------|
| `agents/state.py` | 重写 AgentState，增加 card、intent 等字段 |
| `agents/nodes.py` | 重写节点：classify_intent, do_search, do_publish, do_bounty, do_analyze, do_chat |
| `agents/bs_agent.py` | 新建 LangGraph 图（替代 shopping_agent.py） |
| `services/chat_service.py` | 重写为调用 LangGraph agent，支持 card 传入传出 |
| `models.py` | ChatRequest 增加 card 字段，ChatResponse 增加 card 字段 |
| `routers/chat.py` | 修改 chat endpoint 传入 card |

### 前端新增/修改
| 文件 | 改动 |
|------|------|
| `components/ChatPanel.jsx` | 大幅改造：首页快捷入口、card state、卡片渲染 |
| `components/PublishCard.jsx` | 新建：发布商品内嵌表单卡片组件 |
| `components/BountyCard.jsx` | 新建：发布悬赏内嵌表单卡片组件 |
| `components/AnalysisCard.jsx` | 新建：技能分析结果卡片组件 |
| `components/WelcomeCard.jsx` | 新建：首页快捷入口卡片 |
| `services/api.js` | 修改 sendChat 增加 card 参数 |
| `styles/index.css` | 新增卡片样式 |

---

## 五、性能考虑

**解决之前 LangGraph 慢的问题：**
1. `classify_intent` 用 max_tokens=16 的快速调用，约2秒
2. `do_search` 合并参数提取+搜索+回复为一次 LLM 调用，约10秒
3. `do_publish/bounty` 只做信息提取不调LLM时可以走规则匹配（更快）
4. 前端超时设为60秒（已设置）
5. 意图分类可以考虑本地规则优先（正则匹配关键词），只在模糊时调LLM

**会话存储：**
- MemorySaver 内存存储，不依赖外部服务
- 清理策略：超过24小时未活跃的会话自动清理
