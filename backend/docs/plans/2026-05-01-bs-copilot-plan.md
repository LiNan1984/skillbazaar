# BS Copilot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform BS买卖助手 into a true AI Copilot with H5 inline form cards, LangGraph multi-intent routing, session persistence, and text-to-slot filling — all within one chat window.

**Architecture:** LangGraph StateGraph with 6 nodes (classify_intent → conditional edge → do_search/do_publish/do_bounty/do_analyze/do_chat). MemorySaver for session persistence by user_id. Frontend ChatPanel renders inline PublishCard/BountyCard/AnalysisCard components embedded in chat bubbles.

**Tech Stack:** LangGraph 0.6 + MemorySaver (in-memory) + FastAPI + React + httpx async + GLM-5.1 LLM

---

## Task 1: Rewrite Agent State and LangGraph Graph

**Files:**
- Rewrite: `backend/agents/state.py`
- Create: `backend/agents/bs_agent.py`

**Step 1: Rewrite `backend/agents/state.py`**

Replace the entire file with the new AgentState:

```python
from __future__ import annotations
from typing import TypedDict


class AgentState(TypedDict):
    messages: list[dict]
    intent: str                    # search / publish / bounty / analyze / chat
    card: dict | None              # {type, step, data}
    card_updates: dict             # slot updates from user text
    search_params: dict
    search_results: list
    final_reply: str
    products_json: str
```

**Step 2: Create `backend/agents/bs_agent.py`**

```python
from __future__ import annotations
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    classify_intent,
    do_search,
    do_publish,
    do_bounty,
    do_analyze,
    do_chat,
)


def route_by_intent(state: dict) -> str:
    return state.get("intent", "chat")


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("do_search", do_search)
    g.add_node("do_publish", do_publish)
    g.add_node("do_bounty", do_bounty)
    g.add_node("do_analyze", do_analyze)
    g.add_node("do_chat", do_chat)

    g.set_entry_point("classify_intent")
    g.add_conditional_edges("classify_intent", route_by_intent, {
        "search": "do_search",
        "publish": "do_publish",
        "bounty": "do_bounty",
        "analyze": "do_analyze",
        "chat": "do_chat",
    })
    g.add_edge("do_search", END)
    g.add_edge("do_publish", END)
    g.add_edge("do_bounty", END)
    g.add_edge("do_analyze", END)
    g.add_edge("do_chat", END)
    return g


_memory = MemorySaver()
_compiled = None


def get_agent():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile(checkpointer=_memory)
    return _compiled
```

**Step 3: Verify imports work**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python3 -c "from agents.state import AgentState; from agents.bs_agent import get_agent; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add agents/state.py agents/bs_agent.py
git commit -m "feat: add BS Copilot LangGraph state and graph skeleton"
```

---

## Task 2: Implement LangGraph Nodes

**Files:**
- Rewrite: `backend/agents/nodes.py`

**Step 1: Rewrite `backend/agents/nodes.py` with all 6 nodes**

This is the core file. Replace entirely:

```python
from __future__ import annotations

import json
import re
import httpx

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")  # rotated; inject via env
LLM_MODEL = "GLM-5.1-FP8"

INTENT_RULES = {
    "publish": ["上传", "发布", "上架", "卖", "发布商品", "我要上传", "发布skill", "上传skill", "上传agent", "上传cron"],
    "bounty": ["悬赏", "找人开发", "定制", "发需求", "发悬赏", "找人做"],
    "analyze": ["分析", "市场", "该开发什么", "什么skill好卖", "市场分析"],
    "search": ["搜索", "找", "推荐", "有没有", "看看", "想要", "帮我找"],
}

SYSTEM_PROMPT = """你是 SkillBazaar 市场的 AI 买卖助手"BS买卖助手"。SkillBazaar 是一个 AI Agent、Skill、Cron 和 Workflow 的交易市场。

你的职责：
1. 理解用户想找什么类型的商品，帮买家搜索推荐
2. 引导想卖商品的用户发布商品
3. 引导用户发布悬赏任务
4. 提取关键词、功能需求、价格范围
5. 分析市场趋势和技能开发建议

## 搜索模式
当用户想找商品时，返回 ```json ``` 包裹的搜索参数：
```json
{"category": "Agent或Skill或Cron或Workflow或空字符串", "keyword": "搜索关键词", "min_price": null, "max_price": null, "sort": "rating或downloads或price_asc或price_desc"}
```

## 发布卡片模式
当需要返回发布表单时，返回 ```card ``` 包裹的JSON：
```card
{"type": "publish", "data": {"name": "", "description": "", "category": "Skill", "price": null, "skill_type": "prompt", "tags": []}}
```

## 悬赏卡片模式
当需要返回悬赏表单时，返回 ```bounty ``` 包裹的JSON：
```bounty
{"title": "", "description": "", "category": "Agent", "budget_min": null, "budget_max": null, "skill_type": "code", "requirements": ""}
```

## 填槽更新
当用户补充信息修改卡片字段时，返回 ```slots ``` 包裹的JSON：
```slots
{"field_name": "new_value"}
```

## 分析模式
当用户问市场趋势、什么skill好卖时，返回分析建议。

回复规则：
- 用中文回复，热情专业
- 使用 Markdown 格式
- 搜索类回复包含 JSON 搜索参数
- 发布/悬赏类回复包含对应卡片JSON
- 不需要卡片的回复不要包含任何 ```card/bounty/slots``` 块"""

SLOT_UPDATE_PROMPT = """用户当前有一个{card_type}卡片，数据如下：
{card_data}

用户说：{message}

提取用户想要修改的字段，返回JSON格式的字段更新。只返回需要修改的字段。
格式：```slots\n{"field": "value"}\n```
如果没有修改意图，回复 NONE"""

ANALYZE_PROMPT = """你是 SkillBazaar 的市场分析师。分析用户的需求，给出技能开发建议。

用户需求：{message}
市场数据：{market_data}

请给出：
1. 市场需求评估（高/中/低）
2. 建议的技能类型（Agent/Skill/Cron/Workflow）
3. 建议定价范围
4. 竞争分析
5. 具体开发建议

用中文回复，Markdown格式。"""


async def _call_llm(messages: list[dict], max_tokens: int = 1024) -> str:
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(LLM_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    return msg.get("content", "") or msg.get("reasoning_content", "")


def _extract_json_block(text: str, tag: str) -> dict:
    pattern = rf"```{tag}\s*(\{{.*?\}})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


def _extract_json(text: str) -> dict:
    return _extract_json_block(text, "json")


def _classify_by_rules(message: str) -> str | None:
    msg_lower = message.lower()
    for intent, keywords in INTENT_RULES.items():
        for kw in keywords:
            if kw in msg_lower:
                return intent
    return None


async def classify_intent(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""
    card = state.get("card")

    # Rule-based fast path
    intent = _classify_by_rules(user_msg)
    if not intent:
        # If there's an active card, check for slot updates
        if card and card.get("step") in ("fill", "preview"):
            intent = "slot_update"
        else:
            intent = "chat"

    # For ambiguous cases, use LLM (but keep it fast)
    if intent == "chat" and len(user_msg) > 10:
        try:
            prompt = f"分类用户意图，只返回一个词：search/publish/bounty/analyze/chat\n用户说：{user_msg}"
            result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=8)
            result = result.strip().lower()
            if result in ("search", "publish", "bounty", "analyze"):
                intent = result
        except Exception:
            pass

    return {**state, "intent": intent}


async def do_search(state: dict) -> dict:
    messages = state["messages"]
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-10:]
        llm_reply = await _call_llm(msgs)
    except Exception:
        return {**state, "final_reply": "搜索暂时不可用，请稍后重试。"}

    params = _extract_json(llm_reply)
    products = []
    if params:
        try:
            import services.product_service as ps
            result = await ps.get_products(
                category=params.get("category") or None,
                keyword=params.get("keyword") or None,
                min_price=params.get("min_price"),
                max_price=params.get("max_price"),
                sort_by=params.get("sort", "rating"),
                page=1, page_size=8,
            )
            products = [
                {"id": p.id, "name": p.name, "category": p.category,
                 "price": p.price, "rating": p.rating, "description": p.description[:60]}
                for p in result.products
            ]
        except Exception:
            pass

    reply = re.sub(r"```json\s*\{[^}]+\}\s*```", "", llm_reply, flags=re.DOTALL).strip()
    if products:
        table = "\n".join(
            f"| [{p['name']}](/product/{p['id']}) | {p['category']} | **¥{p['price']}** | {p['rating']:.1f} |"
            for p in products[:8]
        )
        reply += f"\n\n🎉 **找到 {len(products)} 个推荐：**\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n{table}"
    elif params:
        reply += "\n\n😕 暂时没有找到完全匹配的商品，试试换个关键词？"

    return {**state, "final_reply": reply, "search_results": products,
            "products_json": json.dumps(products), "card": None}


async def do_publish(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""
    existing_card = state.get("card")

    if existing_card and existing_card.get("type") == "publish":
        # User wants to continue editing existing publish card
        return {**state, "final_reply": "继续编辑您的商品信息，请确认卡片内容：",
                "card": existing_card}

    # Extract info from user message
    extracted = {"name": "", "description": "", "category": "Skill", "price": None,
                 "skill_type": "prompt", "tags": [], "content_preview": "", "github_url": ""}

    # Simple extraction from message
    for cat in ["Agent", "Skill", "Cron", "Workflow"]:
        if cat.lower() in user_msg.lower():
            extracted["category"] = cat
            break

    # Try LLM extraction for name/description
    try:
        prompt = f"用户想发布商品，说了：{user_msg}\n提取商品名称和描述，返回JSON：{{\"name\": \"\", \"description\": \"\"}}"
        result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=128)
        info = _extract_json(result)
        if info.get("name"):
            extracted["name"] = info["name"]
        if info.get("description"):
            extracted["description"] = info["description"]
    except Exception:
        pass

    card = {"type": "publish", "step": "fill", "data": extracted}
    reply = "好的！帮您发布商品，请填写以下信息，完成后点「预览」："

    return {**state, "final_reply": reply, "card": card}


async def do_bounty(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""

    extracted = {"title": "", "description": "", "category": "Agent",
                 "budget_min": None, "budget_max": None, "deadline": "",
                 "skill_type": "code", "requirements": ""}

    for cat in ["Agent", "Skill", "Cron", "Workflow"]:
        if cat.lower() in user_msg.lower():
            extracted["category"] = cat
            break

    try:
        prompt = f"用户想发布悬赏任务，说了：{user_msg}\n提取标题和描述，返回JSON：{{\"title\": \"\", \"description\": \"\"}}"
        result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=128)
        info = _extract_json(result)
        if info.get("title"):
            extracted["title"] = info["title"]
        if info.get("description"):
            extracted["description"] = info["description"]
    except Exception:
        pass

    card = {"type": "bounty", "step": "fill", "data": extracted}
    reply = "帮您发布悬赏任务！请填写需求信息："

    return {**state, "final_reply": reply, "card": card}


async def do_analyze(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""

    # Get market data for context
    market_data = "暂无实时市场数据"
    try:
        import services.product_service as ps
        result = await ps.get_products(page=1, page_size=5, sort_by="downloads")
        products_text = ", ".join(f"{p.name}({p.category},¥{p.price})" for p in result.products[:5])
        market_data = f"热门商品: {products_text}"
    except Exception:
        pass

    try:
        prompt = ANALYZE_PROMPT.format(message=user_msg, market_data=market_data)
        reply = await _call_llm([
            {"role": "system", "content": "你是 SkillBazaar 市场分析师"},
            {"role": "user", "content": prompt},
        ])
    except Exception:
        reply = "市场分析暂时不可用。"

    card = {"type": "analysis", "step": "result", "data": {"recommendation": reply[:200]}}
    return {**state, "final_reply": reply, "card": card}


async def do_chat(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""
    existing_card = state.get("card")

    # Check for slot updates if there's an active card
    if existing_card and existing_card.get("step") in ("fill", "preview"):
        try:
            prompt = SLOT_UPDATE_PROMPT.format(
                card_type=existing_card.get("type", "publish"),
                card_data=json.dumps(existing_card.get("data", {}), ensure_ascii=False),
                message=user_msg,
            )
            result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=128)
            if "NONE" not in result.upper():
                updates = _extract_json_block(result, "slots")
                if not updates:
                    updates = _extract_json(result)
                if updates:
                    new_data = {**existing_card.get("data", {}), **updates}
                    new_card = {**existing_card, "data": new_data, "step": "fill"}
                    updated_fields = ", ".join(f"「{k}」→ {v}" for k, v in updates.items())
                    return {**state, "final_reply": f"已更新 {updated_fields}，请确认卡片：",
                            "card": new_card}
        except Exception:
            pass

    # Regular chat
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-10:]
        reply = await _call_llm(msgs)
    except Exception:
        reply = "我暂时无法回复，请稍后重试。"

    return {**state, "final_reply": reply, "card": existing_card}
```

**Step 2: Verify all nodes compile**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python3 -c "from agents.nodes import classify_intent, do_search, do_publish, do_bounty, do_analyze, do_chat; print('All nodes OK')"`
Expected: `All nodes OK`

**Step 3: Commit**

```bash
git add agents/state.py agents/nodes.py agents/bs_agent.py
git commit -m "feat: implement BS Copilot LangGraph nodes (classify, search, publish, bounty, analyze, chat)"
```

---

## Task 3: Rewrite Chat Service to Use LangGraph Agent

**Files:**
- Rewrite: `backend/services/chat_service.py`

**Step 1: Replace chat_service.py**

```python
from __future__ import annotations

import json

from models import ChatResponse, ProductResponse
from agents.bs_agent import get_agent
from agents.state import AgentState


def _build_initial_state(user_id: str, message: str, card: dict | None = None) -> AgentState:
    return {
        "messages": [{"role": "user", "content": message}],
        "intent": "",
        "card": card,
        "card_updates": {},
        "search_params": {},
        "search_results": [],
        "final_reply": "",
        "products_json": "[]",
    }


def _parse_products(products_json: str) -> list:
    try:
        items = json.loads(products_json)
        return items if isinstance(items, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def handle_chat(user_id: str, message: str, card: dict | None = None) -> ChatResponse:
    agent = get_agent()
    state = _build_initial_state(user_id, message, card)
    config = {"configurable": {"thread_id": user_id}}

    result = await agent.ainvoke(state, config)

    reply = result.get("final_reply", "让我想想...")
    products_raw = _parse_products(result.get("products_json", "[]"))
    card_result = result.get("card")

    return ChatResponse(
        reply=reply,
        products=[],  # Products are now in the reply markdown table
        card=card_result,
    )
```

**Step 2: Verify import**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python3 -c "from services.chat_service import handle_chat; print('chat_service OK')"`
Expected: `chat_service OK`

**Step 3: Commit**

```bash
git add services/chat_service.py
git commit -m "feat: rewrite chat_service to use LangGraph BS Copilot agent"
```

---

## Task 4: Update Models and Router for Card Support

**Files:**
- Modify: `backend/models.py` (lines 156-163)
- Modify: `backend/routers/chat.py`

**Step 1: Update ChatRequest and ChatResponse in `backend/models.py`**

Add `card` field to both:

```python
# Around line 156, replace ChatRequest:
class ChatRequest(BaseModel):
    message: str
    user_id: str
    card: Optional[dict] = None

# Around line 161, replace ChatResponse:
class ChatResponse(BaseModel):
    reply: str
    products: List[ProductResponse] = []
    card: Optional[dict] = None
```

**Step 2: Update `backend/routers/chat.py`**

```python
from fastapi import APIRouter
from models import ChatRequest, ChatResponse
import services.chat_service as chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    response = await chat_service.handle_chat(
        user_id=body.user_id,
        message=body.message,
        card=body.card,
    )
    return response
```

**Step 3: Verify API compiles**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/backend && python3 -c "from main import app; print('App OK')"`
Expected: `App OK`

**Step 4: Test with curl**

Run: `curl -s -X POST http://localhost:9527/api/chat -H "Content-Type: application/json" -d '{"user_id":"test","message":"你好"}' | python3 -m json.tool`

Expected: JSON with `reply` and `card: null`

**Step 5: Commit**

```bash
git add models.py routers/chat.py
git commit -m "feat: add card field to ChatRequest/ChatResponse, update chat router"
```

---

## Task 5: Update Frontend API and Create Card Components

**Files:**
- Modify: `frontend/src/services/api.js` (line 72-74)
- Create: `frontend/src/components/cards/PublishCard.jsx`
- Create: `frontend/src/components/cards/BountyCard.jsx`
- Create: `frontend/src/components/cards/AnalysisCard.jsx`
- Create: `frontend/src/components/cards/WelcomeCard.jsx`

**Step 1: Update `sendChat` in `frontend/src/services/api.js`**

Replace lines 72-74:

```javascript
export async function sendChat(userId, message, card = null) {
  return api.post('/chat', { user_id: userId, message, card }, { timeout: 60000 })
}
```

**Step 2: Create `frontend/src/components/cards/PublishCard.jsx`**

```jsx
import { useState } from 'react'
import { Eye, Check, Pencil, X, Upload } from 'lucide-react'
import { createProduct, uploadSkill } from '../../services/api'

const CATEGORIES = ['Agent', 'Skill', 'Cron', 'Workflow']
const SKILL_TYPES = [
  { value: 'prompt', label: 'Prompt 提示词' },
  { value: 'code', label: 'Code 代码包' },
  { value: 'sdk', label: 'SDK 接口' },
]

export default function PublishCard({ card, authToken, userId, onUpdate, onSubmit, onCancel }) {
  const [data, setData] = useState(card.data || {})
  const [step, setStep] = useState(card.step || 'fill')
  const [skillFile, setSkillFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const handleChange = (field, value) => {
    const updated = { ...data, [field]: value }
    setData(updated)
    onUpdate?.({ ...card, data: updated })
  }

  const handlePreview = () => {
    if (!data.name?.trim()) { setError('请输入商品名称'); return }
    if (!data.description?.trim()) { setError('请输入商品描述'); return }
    if (!data.price || data.price <= 0) { setError('请输入有效价格'); return }
    setError('')
    setStep('preview')
    onUpdate?.({ ...card, step: 'preview', data })
  }

  const handleEdit = () => {
    setStep('fill')
    onUpdate?.({ ...card, step: 'fill', data })
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const sellerName = localStorage.getItem('skillbazaar_nickname') || localStorage.getItem('skillbazaar_username') || '匿名卖家'
      const payload = {
        name: data.name.trim(),
        description: data.description.trim(),
        category: data.category || 'Skill',
        sub_category: data.sub_category || null,
        price: Number(data.price),
        tags: JSON.stringify(data.tags || []),
        content_preview: data.content_preview?.trim() || null,
        github_url: data.github_url?.trim() || null,
        seller_name: sellerName,
        source_platform: '原创',
      }
      const productResult = await createProduct(payload, authToken)
      const productId = productResult.id || productResult.product_id

      if (skillFile && productId) {
        try {
          await uploadSkill(productId, data.skill_type || 'prompt', skillFile, userId || 'anonymous', null)
        } catch (e) { /* non-fatal */ }
      }

      setStep('done')
      setResult({ productId, name: data.name })
      onSubmit?.({ productId, name: data.name })
    } catch (err) {
      setError(err?.detail || err?.message || '发布失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'done') {
    return (
      <div className="chat-card card-done">
        <div className="chat-card-header">
          <Check size={16} style={{ color: '#22c55e' }} />
          <span>发布成功</span>
        </div>
        <p>商品「{result?.name}」已上架！</p>
        <div className="chat-card-actions">
          <a href={`/product/${result?.productId}`} className="btn btn-sm btn-primary">查看商品</a>
          <button className="btn btn-sm btn-secondary" onClick={onCancel}>继续发布</button>
        </div>
      </div>
    )
  }

  if (step === 'preview') {
    return (
      <div className="chat-card">
        <div className="chat-card-header">
          <Eye size={16} />
          <span>确认发布信息</span>
        </div>
        <div className="chat-card-preview">
          <div className="preview-row"><strong>名称：</strong>{data.name}</div>
          <div className="preview-row"><strong>分类：</strong>{data.category}</div>
          <div className="preview-row"><strong>价格：</strong>¥{data.price} 金币</div>
          <div className="preview-row"><strong>类型：</strong>{SKILL_TYPES.find(t => t.value === (data.skill_type || 'prompt'))?.label}</div>
          {data.description && <div className="preview-row"><strong>描述：</strong>{data.description.slice(0, 100)}</div>}
        </div>
        {error && <div className="chat-card-error">{error}</div>}
        <div className="chat-card-actions">
          <button className="btn btn-sm btn-secondary" onClick={handleEdit} disabled={submitting}>
            <Pencil size={14} /> 修改
          </button>
          <button className="btn btn-sm btn-primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? '发布中...' : <><Check size={14} /> 确认发布</>}
          </button>
        </div>
      </div>
    )
  }

  // fill mode
  return (
    <div className="chat-card">
      <div className="chat-card-header">
        <Upload size={16} />
        <span>发布商品</span>
      </div>
      <div className="chat-card-form">
        <div className="card-field">
          <label>商品名称 *</label>
          <input className="card-input" placeholder="给商品起个名字"
            value={data.name || ''} onChange={e => handleChange('name', e.target.value)} />
        </div>
        <div className="card-field">
          <label>商品描述 *</label>
          <textarea className="card-textarea" placeholder="描述功能、用途"
            value={data.description || ''} onChange={e => handleChange('description', e.target.value)} rows={3} />
        </div>
        <div className="card-field-row">
          <div className="card-field">
            <label>分类 *</label>
            <select className="card-select" value={data.category || 'Skill'}
              onChange={e => handleChange('category', e.target.value)}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="card-field">
            <label>价格（金币）*</label>
            <input className="card-input" type="number" min="1" placeholder="99"
              value={data.price || ''} onChange={e => handleChange('price', +e.target.value)} />
          </div>
        </div>
        <div className="card-field-row">
          <div className="card-field">
            <label>技能类型</label>
            <select className="card-select" value={data.skill_type || 'prompt'}
              onChange={e => handleChange('skill_type', e.target.value)}>
              {SKILL_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="card-field">
            <label>上传文件</label>
            <input className="card-file" type="file" accept=".md,.py,.js,.zip,.json"
              onChange={e => setSkillFile(e.target.files[0])} />
          </div>
        </div>
        <div className="card-field">
          <label>标签</label>
          <input className="card-input" placeholder="交易,自动化,API"
            value={Array.isArray(data.tags) ? data.tags.join(',') : (data.tags || '')}
            onChange={e => handleChange('tags', e.target.value.split(',').map(t => t.trim()).filter(Boolean))} />
        </div>
      </div>
      {error && <div className="chat-card-error">{error}</div>}
      <div className="chat-card-actions">
        <button className="btn btn-sm btn-ghost" onClick={onCancel}><X size={14} /> 取消</button>
        <button className="btn btn-sm btn-primary" onClick={handlePreview}><Eye size={14} /> 预览</button>
      </div>
    </div>
  )
}
```

**Step 3: Create `frontend/src/components/cards/BountyCard.jsx`**

```jsx
import { useState } from 'react'
import { Eye, Check, Pencil, X, Target } from 'lucide-react'
import { createBounty } from '../../services/api'

const CATEGORIES = ['Agent', 'Skill', 'Cron', 'Workflow']

export default function BountyCard({ card, authToken, onUpdate, onSubmit, onCancel }) {
  const [data, setData] = useState(card.data || {})
  const [step, setStep] = useState(card.step || 'fill')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const handleChange = (field, value) => {
    const updated = { ...data, [field]: value }
    setData(updated)
    onUpdate?.({ ...card, data: updated })
  }

  const handlePreview = () => {
    if (!data.title?.trim()) { setError('请输入任务标题'); return }
    if (!data.description?.trim()) { setError('请输入任务描述'); return }
    if (!data.budget_min || !data.budget_max) { setError('请设置预算范围'); return }
    setError('')
    setStep('preview')
    onUpdate?.({ ...card, step: 'preview', data })
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const bountyData = {
        title: data.title.trim(),
        description: data.description.trim(),
        category: data.category || 'Agent',
        tags: [],
        budget_min: Number(data.budget_min),
        budget_max: Number(data.budget_max),
        deadline: data.deadline || null,
        skill_type: data.skill_type || 'code',
        requirements: data.requirements?.trim() || null,
      }
      const bounty = await createBounty(bountyData, authToken)
      setStep('done')
      setResult({ bountyId: bounty.id, title: data.title })
      onSubmit?.(bounty)
    } catch (err) {
      setError(err?.detail || err?.message || '发布失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (step === 'done') {
    return (
      <div className="chat-card card-done">
        <div className="chat-card-header">
          <Check size={16} style={{ color: '#22c55e' }} />
          <span>悬赏发布成功</span>
        </div>
        <p>悬赏「{result?.title}」已发布，等待开发者竞标！</p>
        <div className="chat-card-actions">
          <a href={`/bounty/${result?.bountyId}`} className="btn btn-sm btn-primary">查看悬赏</a>
          <button className="btn btn-sm btn-secondary" onClick={onCancel}>继续</button>
        </div>
      </div>
    )
  }

  if (step === 'preview') {
    return (
      <div className="chat-card">
        <div className="chat-card-header">
          <Eye size={16} />
          <span>确认悬赏信息</span>
        </div>
        <div className="chat-card-preview">
          <div className="preview-row"><strong>标题：</strong>{data.title}</div>
          <div className="preview-row"><strong>分类：</strong>{data.category}</div>
          <div className="preview-row"><strong>预算：</strong>{data.budget_min} - {data.budget_max} 金币</div>
          {data.deadline && <div className="preview-row"><strong>截止：</strong>{data.deadline}</div>}
          {data.description && <div className="preview-row"><strong>描述：</strong>{data.description.slice(0, 100)}</div>}
        </div>
        {error && <div className="chat-card-error">{error}</div>}
        <div className="chat-card-actions">
          <button className="btn btn-sm btn-secondary" onClick={() => { setStep('fill'); onUpdate?.({ ...card, step: 'fill', data }) }}>
            <Pencil size={14} /> 修改
          </button>
          <button className="btn btn-sm btn-primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? '发布中...' : <><Check size={14} /> 确认发布</>}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="chat-card">
      <div className="chat-card-header">
        <Target size={16} />
        <span>发布悬赏</span>
      </div>
      <div className="chat-card-form">
        <div className="card-field">
          <label>任务标题 *</label>
          <input className="card-input" placeholder="如：开发价格监控Agent"
            value={data.title || ''} onChange={e => handleChange('title', e.target.value)} />
        </div>
        <div className="card-field">
          <label>任务描述 *</label>
          <textarea className="card-textarea" placeholder="描述你需要的功能"
            value={data.description || ''} onChange={e => handleChange('description', e.target.value)} rows={3} />
        </div>
        <div className="card-field-row">
          <div className="card-field">
            <label>分类</label>
            <select className="card-select" value={data.category || 'Agent'}
              onChange={e => handleChange('category', e.target.value)}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="card-field">
            <label>技能类型</label>
            <select className="card-select" value={data.skill_type || 'code'}
              onChange={e => handleChange('skill_type', e.target.value)}>
              <option value="prompt">Prompt</option>
              <option value="code">Code</option>
              <option value="sdk">SDK</option>
            </select>
          </div>
        </div>
        <div className="card-field-row">
          <div className="card-field">
            <label>最低预算 *</label>
            <input className="card-input" type="number" min="1" placeholder="100"
              value={data.budget_min || ''} onChange={e => handleChange('budget_min', +e.target.value)} />
          </div>
          <div className="card-field">
            <label>最高预算 *</label>
            <input className="card-input" type="number" min="1" placeholder="500"
              value={data.budget_max || ''} onChange={e => handleChange('budget_max', +e.target.value)} />
          </div>
        </div>
        <div className="card-field">
          <label>截止日期</label>
          <input className="card-input" type="date"
            value={data.deadline || ''} onChange={e => handleChange('deadline', e.target.value)} />
        </div>
      </div>
      {error && <div className="chat-card-error">{error}</div>}
      <div className="chat-card-actions">
        <button className="btn btn-sm btn-ghost" onClick={onCancel}><X size={14} /> 取消</button>
        <button className="btn btn-sm btn-primary" onClick={handlePreview}><Eye size={14} /> 预览</button>
      </div>
    </div>
  )
}
```

**Step 4: Create `frontend/src/components/cards/AnalysisCard.jsx`**

```jsx
import { BarChart3 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function AnalysisCard({ card }) {
  return (
    <div className="chat-card card-analysis">
      <div className="chat-card-header">
        <BarChart3 size={16} />
        <span>Skill 市场分析</span>
      </div>
      <div className="card-analysis-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {card.data?.recommendation || card.data?.raw || '分析中...'}
        </ReactMarkdown>
      </div>
    </div>
  )
}
```

**Step 5: Create `frontend/src/components/cards/WelcomeCard.jsx`**

```jsx
const ACTIONS = [
  { icon: '🔍', label: '搜索商品', value: '帮我搜索热门商品' },
  { icon: '📦', label: '发布 Skill', value: '我要上传一个Skill' },
  { icon: '🤖', label: '发布 Agent', value: '我要发布一个Agent' },
  { icon: '⏰', label: '上传 Cron', value: '我要上传一个Cron定时任务' },
  { icon: '🎯', label: '发悬赏', value: '我想发布一个悬赏任务' },
  { icon: '📊', label: 'Skill 分析', value: '现在什么类型的Skill最好卖？给我分析一下' },
]

export default function WelcomeCard({ onAction }) {
  return (
    <div className="welcome-card">
      <div className="welcome-card-grid">
        {ACTIONS.map(a => (
          <button key={a.label} className="welcome-card-btn" onClick={() => onAction(a.value)}>
            <span className="welcome-card-icon">{a.icon}</span>
            <span className="welcome-card-label">{a.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
```

**Step 6: Commit**

```bash
mkdir -p frontend/src/components/cards
git add frontend/src/services/api.js frontend/src/components/cards/
git commit -m "feat: add card components (PublishCard, BountyCard, AnalysisCard, WelcomeCard)"
```

---

## Task 6: Rewrite ChatPanel with Card Support

**Files:**
- Rewrite: `frontend/src/components/ChatPanel.jsx`

**Step 1: Rewrite ChatPanel.jsx**

```jsx
import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { X, Send } from 'lucide-react'
import { sendChat } from '../services/api'
import PublishCard from './cards/PublishCard'
import BountyCard from './cards/BountyCard'
import AnalysisCard from './cards/AnalysisCard'
import WelcomeCard from './cards/WelcomeCard'

export default function ChatPanel({ open, onClose, userId, authToken }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeCard, setActiveCard] = useState(() => {
    try {
      const saved = localStorage.getItem(`skillbazaar_card_${userId}`)
      return saved ? JSON.parse(saved) : null
    } catch { return null }
  })
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([{
        role: 'bot',
        content: '您好！我是 **BS买卖助手**，您的 AI 交易 Copilot。\n\n我可以帮您搜索商品、发布 Skill、发悬赏、分析市场。点击下方快捷入口开始：',
        welcome: true,
      }])
    }
  }, [open, messages.length])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeCard])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 300)
  }, [open])

  useEffect(() => {
    if (activeCard && userId) {
      localStorage.setItem(`skillbazaar_card_${userId}`, JSON.stringify(activeCard))
    } else if (userId) {
      localStorage.removeItem(`skillbazaar_card_${userId}`)
    }
  }, [activeCard, userId])

  const handleSend = async (text) => {
    const message = text || input.trim()
    if (!message || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: message }])
    setLoading(true)

    try {
      const data = await sendChat(userId, message, activeCard)
      const reply = data.reply || ''

      if (reply) {
        setMessages(prev => [...prev, { role: 'bot', content: reply }])
      }

      if (data.card) {
        setActiveCard(data.card)
      }

      if (!reply && !data.card) {
        setMessages(prev => [...prev, { role: 'bot', content: '抱歉，请换个方式描述。' }])
      }
    } catch {
      setMessages(prev => [...prev, { role: 'bot', content: '网络异常，请稍后重试。' }])
    } finally {
      setLoading(false)
    }
  }

  const handleCardUpdate = (updatedCard) => {
    setActiveCard(updatedCard)
  }

  const handleCardSubmit = (result) => {
    setActiveCard(null)
    if (result?.productId) {
      setMessages(prev => [...prev, {
        role: 'bot',
        content: `✅ 商品「${result.name}」已成功发布！[查看商品](/product/${result.productId})`,
      }])
    }
  }

  const handleBountySubmit = (result) => {
    setActiveCard(null)
    if (result?.id) {
      setMessages(prev => [...prev, {
        role: 'bot',
        content: `✅ 悬赏「${result.title || ''}」已发布！[查看悬赏](/bounty/${result.id})`,
      }])
    }
  }

  const handleCardCancel = () => {
    setActiveCard(null)
  }

  const handleQuickAction = (value) => {
    handleSend(value)
  }

  const renderCard = () => {
    if (!activeCard) return null
    switch (activeCard.type) {
      case 'publish':
        return <PublishCard card={activeCard} authToken={authToken} userId={userId}
                  onUpdate={handleCardUpdate} onSubmit={handleCardSubmit} onCancel={handleCardCancel} />
      case 'bounty':
        return <BountyCard card={activeCard} authToken={authToken}
                  onUpdate={handleCardUpdate} onSubmit={handleBountySubmit} onCancel={handleCardCancel} />
      case 'analysis':
        return <AnalysisCard card={activeCard} />
      default:
        return null
    }
  }

  return (
    <div className={`chat-panel ${open ? 'open' : ''}`}>
      <div className="chat-header">
        <div className="chat-header-left">
          <div className="chat-header-avatar">🤖</div>
          <div className="chat-header-info">
            <span className="chat-header-name">BS买卖助手</span>
            <span className="chat-header-status">
              <span className="chat-header-status-dot" />
              在线
            </span>
          </div>
        </div>
        <button className="chat-close-btn" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.role === 'bot' && <div className="message-avatar">🤖</div>}
            <div className={`message-bubble ${msg.role}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              {msg.welcome && <WelcomeCard onAction={handleQuickAction} />}
            </div>
            {msg.role === 'user' && <div className="message-avatar">😊</div>}
          </div>
        ))}

        {activeCard && (
          <div className="chat-message bot">
            <div className="message-avatar">🤖</div>
            <div className="message-bubble bot card-bubble">
              {renderCard()}
            </div>
          </div>
        )}

        {loading && (
          <div className="chat-message bot">
            <div className="message-avatar">🤖</div>
            <div className="message-bubble bot typing">
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
              <span className="typing-dot">●</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          placeholder="输入您的问题..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
        >
          <Send size={18} />
        </button>
      </div>

      <div className="chat-footer">回复内容由 AI 助手生成，仅供参考</div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ChatPanel.jsx
git commit -m "feat: rewrite ChatPanel with card rendering, welcome screen, and session persistence"
```

---

## Task 7: Add Card CSS Styles

**Files:**
- Modify: `frontend/src/styles/index.css`

**Step 1: Append card styles to the end of `index.css`**

```css
/* ---- Chat Card Styles ---- */

.chat-card {
  background: var(--bg-surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  width: 100%;
  max-width: 340px;
}

.chat-card.card-done {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.05);
}

.chat-card.card-analysis {
  border-color: var(--accent-primary);
}

.chat-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.chat-card-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-field label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.card-field-row {
  display: flex;
  gap: 10px;
}

.card-field-row .card-field {
  flex: 1;
}

.card-input, .card-select, .card-textarea {
  padding: 8px 10px;
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font);
  outline: none;
  transition: var(--transition);
}

.card-input:focus, .card-select:focus, .card-textarea:focus {
  border-color: var(--accent-primary);
}

.card-input::placeholder, .card-textarea::placeholder {
  color: var(--text-muted);
}

.card-textarea {
  resize: vertical;
  min-height: 60px;
}

.card-file {
  font-size: 12px;
  color: var(--text-secondary);
}

.card-file::file-selector-button {
  padding: 4px 8px;
  background: var(--bg-surface-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 11px;
  cursor: pointer;
}

.chat-card-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.preview-row {
  font-size: 13px;
  color: var(--text-secondary);
}

.preview-row strong {
  color: var(--text-primary);
}

.chat-card-error {
  padding: 8px 10px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-radius: var(--radius-sm);
  font-size: 12px;
  margin-top: 8px;
}

.chat-card-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}

.card-bubble {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
}

.card-analysis-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.card-analysis-content strong {
  color: var(--text-primary);
}

/* ---- Welcome Card ---- */

.welcome-card {
  margin-top: 12px;
}

.welcome-card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.welcome-card-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  background: var(--bg-surface-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: var(--transition);
}

.welcome-card-btn:hover {
  border-color: var(--accent-primary);
  background: rgba(99, 102, 241, 0.08);
  transform: translateY(-1px);
}

.welcome-card-icon {
  font-size: 20px;
}

.welcome-card-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

@media (max-width: 768px) {
  .welcome-card-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .card-field-row {
    flex-direction: column;
  }
}
```

**Step 2: Commit**

```bash
git add frontend/src/styles/index.css
git commit -m "feat: add chat card CSS styles (publish, bounty, analysis, welcome)"
```

---

## Task 8: Update App.jsx to Pass authToken to ChatPanel

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: Update ChatPanel props**

Find the ChatPanel render (around line 76) and add `authToken`:

```jsx
{chatOpen && (
  <Suspense fallback={null}>
    <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} userId={userId} authToken={authToken} />
  </Suspense>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: pass authToken to ChatPanel for card-based publishing"
```

---

## Task 9: Integration Test and Build Verification

**Step 1: Build frontend**

Run: `cd /Users/linan/Desktop/aicode/skillbazaar/frontend && npx vite build`
Expected: Build succeeds with no errors

**Step 2: Restart backend and test full flow**

```bash
cd /Users/linan/Desktop/aicode/skillbazaar/backend
# Kill existing backend
lsof -ti:9527 | xargs kill 2>/dev/null
sleep 1
python3 -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=9527, reload=False)" &
sleep 3
```

**Step 3: Test chat API with curl**

Test 1 - Search:
```bash
curl -s -X POST http://localhost:9527/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"推荐一些交易类的Agent"}' | python3 -m json.tool
```
Expected: reply with product recommendations, card: null

Test 2 - Publish:
```bash
curl -s -X POST http://localhost:9527/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"我要上传一个交易策略Skill"}' | python3 -m json.tool
```
Expected: reply + card with type "publish", step "fill", data with name extracted

Test 3 - Bounty:
```bash
curl -s -X POST http://localhost:9527/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"我想找人开发一个价格监控Agent"}' | python3 -m json.tool
```
Expected: reply + card with type "bounty", step "fill"

Test 4 - Slot update:
```bash
curl -s -X POST http://localhost:9527/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"价格改成200","card":{"type":"publish","step":"fill","data":{"name":"测试","description":"","category":"Skill","price":null}}}' | python3 -m json.tool
```
Expected: card returned with price updated to 200

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: BS Copilot complete - LangGraph agent + H5 cards + session persistence"
```
