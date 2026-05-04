from __future__ import annotations

import json
import re
import httpx

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = "sk-bV3TVx9azStj8KJe3oW0rsqpaIZKX8E21wyXMtHYCjWBxly1"
LLM_MODEL = "GLM-5.1-FP8"

INTENT_RULES = {
    "analyze": ["分析", "市场分析", "该开发什么", "什么好卖", "趋势", "什么skill好卖"],
    "bounty": ["悬赏", "找人开发", "定制", "发需求", "发悬赏", "找人做"],
    "publish": ["上传", "发布", "上架", "我要上传", "发布skill", "上传skill", "上传agent", "上传cron", "发布商品", "我要卖"],
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

回复规则：
- 用中文回复，热情专业
- 使用 Markdown 格式
- 搜索类回复包含 JSON 搜索参数
- 不需要搜索的回复不要包含任何 ```json``` 块"""

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
    async with httpx.AsyncClient(timeout=60) as client:
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

    intent = _classify_by_rules(user_msg)
    if not intent:
        if card and card.get("step") in ("fill", "preview"):
            intent = "slot_update"
        else:
            intent = "chat"

    if intent == "chat" and len(user_msg) > 10:
        try:
            prompt = f"分类用户意图，只返回一个词：search/publish/bounty/analyze/chat\n用户说：{user_msg}"
            result = await _call_llm([{"role": "user", "content": prompt}], max_tokens=8)
            result = result.strip().lower()
            if result in ("search", "publish", "bounty", "analyze"):
                intent = result
        except Exception:
            pass

    return {"intent": intent}


async def do_search(state: dict) -> dict:
    messages = state["messages"]
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-10:]
        llm_reply = await _call_llm(msgs)
    except Exception:
        return {"final_reply": "搜索暂时不可用，请稍后重试。"}

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
                 "price": p.price, "rating": p.rating, "description": p.description[:60] if p.description else ""}
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
        reply += f"\n\n**找到 {len(products)} 个推荐：**\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n{table}"
    elif params:
        reply += "\n\n暂时没有找到完全匹配的商品，试试换个关键词？"

    return {"final_reply": reply, "search_results": products,
            "products_json": json.dumps(products), "card": None}


async def do_publish(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""
    existing_card = state.get("card")

    if existing_card and existing_card.get("type") == "publish":
        return {"final_reply": "继续编辑您的商品信息，请确认卡片内容：", "card": existing_card}

    extracted = {"name": "", "description": "", "category": "Skill", "price": None,
                 "skill_type": "prompt", "tags": [], "content_preview": "", "github_url": ""}

    for cat in ["Agent", "Skill", "Cron", "Workflow"]:
        if cat.lower() in user_msg.lower():
            extracted["category"] = cat
            break

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

    return {"final_reply": reply, "card": card}


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

    return {"final_reply": reply, "card": card}


async def do_analyze(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1]["content"] if messages else ""

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
    return {"final_reply": reply, "card": card}


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
                    return {"final_reply": f"已更新 {updated_fields}，请确认卡片：", "card": new_card}
        except Exception:
            pass

    # Regular chat
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-10:]
        reply = await _call_llm(msgs)
    except Exception:
        reply = "我暂时无法回复，请稍后重试。"

    return {"final_reply": reply, "card": existing_card}
