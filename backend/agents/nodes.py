from __future__ import annotations

import json
import re
import httpx

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = "sk-bV3TVx9azStj8KJe3oW0rsqpaIZKX8E21wyXMtHYCjWBxly1"
LLM_MODEL = "GLM-5.1-FP8"

SYSTEM_PROMPT = """你是 SkillBazaar 市场的 AI 导购助手"小B"。SkillBazaar 是一个 AI Agent、Skill（技能包）、Cron（定时任务）和 Workflow（工作流）的交易市场。

你的职责：
1. 理解用户想找什么类型的商品（Agent/Skill/Cron/Workflow）
2. 提取用户提到的关键词、功能需求、价格范围
3. 返回 JSON 格式的搜索参数，系统会自动搜索匹配商品

回复规则：
- 用中文回复
- 热情专业，像私人导购一样
- 使用 Markdown 格式美化回复（加粗价格、列表推荐等）
- 每次回复必须包含一个 JSON 块（用 ```json ``` 包裹），格式如下：

```json
{
  "category": "Agent 或 Skill 或 Cron 或 Workflow 或空字符串",
  "keyword": "搜索关键词",
  "min_price": 最低价或null,
  "max_price": 最高价或null,
  "sort": "rating 或 downloads 或 price_asc 或 price_desc"
}
```

如果是打招呼或闲聊，不需要返回 JSON，直接热情回复即可。
如果用户说的不够明确，主动追问。
多轮对话时要结合上下文理解用户意图。"""

INTENT_PROMPT = """分析用户意图，返回以下之一：
- search: 用户想搜索商品
- chat: 闲聊或打招呼
- followup: 追问上一次搜索的结果
- buy: 用户想购买某个商品

只返回意图关键词，不要其他内容。

对话历史：
{history}

用户最新消息：{message}"""

RESULT_EVAL_PROMPT = """你是搜索结果评估器。评估搜索结果是否满足用户需求。

用户搜索条件：{params}
搜索结果数量：{count}

如果结果为空或太少（少于3个），建议放宽条件的 JSON：
```json
{{"category": "...", "keyword": "...", "min_price": null, "max_price": null, "sort": "..."}}
```

如果结果足够好，只回复 "GOOD"。"""

REPLY_PROMPT = """你是 SkillBazaar 的导购助手小B，根据搜索结果给用户推荐商品。

搜索结果：
{products}

用 Markdown 格式回复，要求：
1. 先用一句话总结找到的商品
2. 用列表推荐 2-3 个最佳选择，加粗价格
3. 询问用户是否想了解详情或购买
4. 风格热情亲切"""


async def _call_llm(messages: list[dict], max_tokens: int = 1024) -> str:
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(LLM_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    return msg.get("content", "") or msg.get("reasoning_content", "")


def _extract_json(text: str) -> dict:
    pattern = r"```json\s*(\{[^}]+\})\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    pattern2 = r'\{[^{}]*"category"[^{}]*\}'
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        try:
            return json.loads(match2.group())
        except json.JSONDecodeError:
            pass
    return {}


async def understand_intent(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""
    history_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in messages[-6:]
    )
    prompt = INTENT_PROMPT.format(history=history_text, message=user_msg)
    result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=32)
    intent = result.strip().lower()
    if intent not in ("search", "chat", "followup", "buy"):
        intent = "search"
    return {**state, "intent": intent}


async def extract_params(state: dict) -> dict:
    if state["intent"] == "chat":
        reply = await _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"][-10:],
            max_tokens=512,
        )
        return {**state, "final_reply": reply, "search_params": {}}

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"][-10:]
    reply = await _call_llm(messages, max_tokens=512)
    params = _extract_json(reply)
    if not params and state["intent"] == "followup" and state.get("search_params"):
        params = state["search_params"]
    return {**state, "search_params": params}


async def search_products(state: dict) -> dict:
    if not state.get("search_params"):
        return {**state, "search_results": []}
    import services.product_service as ps
    params = state["search_params"]
    try:
        result = await ps.get_products(
            category=params.get("category") or None,
            keyword=params.get("keyword") or None,
            min_price=params.get("min_price"),
            max_price=params.get("max_price"),
            sort_by=params.get("sort", "rating"),
            page=1,
            page_size=8,
        )
        products = result.products
    except Exception:
        products = []

    products_data = [
        {
            "id": p.id, "name": p.name, "category": p.category,
            "price": p.price, "rating": p.rating,
            "description": p.description[:60] if p.description else "",
            "source_platform": p.source_platform,
        }
        for p in products
    ]
    return {**state, "search_results": products_data}


async def evaluate_results(state: dict) -> dict:
    results = state.get("search_results", [])
    params = state.get("search_params", {})
    iteration = state.get("iteration", 0)
    if len(results) >= 3 or iteration >= 2:
        return state
    eval_prompt = RESULT_EVAL_PROMPT.format(
        params=json.dumps(params, ensure_ascii=False),
        count=len(results),
    )
    suggestion = await _call_llm([{"role": "user", "content": eval_prompt}], max_tokens=256)
    if "GOOD" in suggestion:
        return state
    new_params = _extract_json(suggestion)
    if new_params:
        return {**state, "search_params": new_params, "iteration": iteration + 1}
    return state


async def generate_reply(state: dict) -> dict:
    results = state.get("search_results", [])
    params = state.get("search_params", {})
    if state["intent"] == "chat":
        return state
    if not results:
        reply = "抱歉，暂时没有找到完全匹配的商品。\n\n"
        reply += "您可以试试：\n"
        reply += "- **换个关键词**搜索\n"
        reply += "- **放宽价格范围**\n"
        reply += "- 浏览我们的[热门商品](/)\n"
        return {**state, "final_reply": reply}

    products_text = json.dumps(results[:8], ensure_ascii=False, indent=2)
    reply = await _call_llm(
        [
            {"role": "system", "content": REPLY_PROMPT},
            {"role": "user", "content": f"搜索条件: {json.dumps(params, ensure_ascii=False)}\n\n搜索结果:\n{products_text}"},
        ],
        max_tokens=1024,
    )
    product_links = "\n".join(
        f"| [{p['name']}](/product/{p['id']}) | {p['category']} | **¥{p['price']}** | {p['rating']} |"
        for p in results[:8]
    )
    table = f"\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n{product_links}"
    return {**state, "final_reply": reply + table, "products_json": json.dumps(results)}
