from __future__ import annotations

import json
import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)

LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.finmall.com/v1/chat/completions")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "GLM-5.1-FP8")

if not LLM_API_KEY:
    logging.getLogger(__name__).warning(
        "LLM_API_KEY 环境变量未配置：大模型调用不可用，导购/分析将自动降级为规则兜底。"
    )

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
当用户想找商品（包括一个需要多个步骤/多个 Skill 组合完成的复杂任务）时，返回 ```json ``` 包裹的搜索参数，用一组参数覆盖整个任务最核心的商品类别与关键词：
```json
{"category": "Agent或Skill或Cron或Workflow或空字符串", "keyword": "搜索关键词", "min_price": null, "max_price": null, "sort": "rating或downloads或price_asc或price_desc"}
```

回复规则：
- 用中文回复，热情专业
- 使用 Markdown 格式
- 搜索类回复包含 JSON 搜索参数
- 不需要搜索的回复不要包含任何 ```json``` 块"""

MATCH_SELECT_PROMPT = """你是 SkillBazaar 的方案导购。下面是用户任务与本次真实搜索结果（JSON 数组，唯一可选的数据源）。

请把用户任务拆解为 1-4 个有序步骤，每步从搜索结果中选择一个最匹配的商品。
硬性要求：
- product_id 必须来自搜索结果，严禁编造库外商品；
- reason 必须直接引用该商品 description 的原文片段，不得承诺 description 之外的功能；
- 同一商品不要重复选择。

只返回一个 ```json``` 块，格式：
```json
{"steps": [{"title": "步骤标题", "product_id": 1, "reason": "引用该商品 description 原文"}]}
```

用户任务：__MESSAGE__
搜索结果：__RESULTS__"""

VALID_CATEGORIES = ("Agent", "Skill", "Cron", "Workflow")

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
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 环境变量未配置，无法调用大模型（已切换规则兜底）")
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


def _extract_json_blocks(text: str) -> list[dict]:
    """All top-level JSON objects in ```json fences (nested objects OK)."""
    blocks = []
    for match in re.finditer(r"```json\s*(\{.*?\})\s*```", text or "", re.DOTALL):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            blocks.append(obj)
    return blocks


def _strip_fenced_json(text: str) -> str:
    return re.sub(r"```json\s*\{.*?\}\s*```", "", text or "", flags=re.DOTALL).strip()


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


def _fallback_search_params(message: str) -> dict:
    """Rule-based search params when the LLM is unavailable."""
    msg_lower = (message or "").lower()
    category = ""
    for cat in ("agent", "skill", "cron", "workflow"):
        if cat in msg_lower:
            category = cat.capitalize()
            break
    return {"category": category, "keyword": None, "sort": "rating"}


async def _run_product_search(p: dict) -> tuple[list, dict, Exception | None]:
    """Search with the given params.

    Returns (card dicts, full records by id, error). A DB/backend failure is
    kept distinct from a genuine zero-row result so callers never mistake an
    outage for "no matching product".
    """
    try:
        import services.product_service as ps
        result = await ps.get_products(
            category=p.get("category") or None,
            keyword=(p.get("keyword") or None) if isinstance(p.get("keyword"), str) else None,
            min_price=p.get("min_price"),
            max_price=p.get("max_price"),
            sort_by=p.get("sort", "rating"),
            page=1, page_size=8,
        )
        full = {prod.id: prod for prod in result.products}
        cards = [
            {"id": prod.id, "name": prod.name, "category": prod.category,
             "price": prod.price, "rating": prod.rating,
             "description": prod.description[:60] if prod.description else ""}
            for prod in result.products
        ]
        return cards, full, None
    except Exception as exc:  # backend failure, NOT an empty shelf
        logger.warning("product search failed: %s", exc)
        return [], {}, exc


def _coerce_price(value) -> int | None:
    """LLMs may emit prices as strings; non-numeric junk becomes None."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_search_params(params: dict) -> dict:
    """Validate LLM-produced params before they reach SQLite."""
    if not isinstance(params, dict):
        return {"category": "", "keyword": None, "sort": "rating"}
    category = str(params.get("category") or "").strip()
    if category not in VALID_CATEGORIES:
        # Hallucinated free-text categories silently match nothing -> drop it.
        category = ""
    keyword = params.get("keyword")
    keyword = str(keyword).strip() if isinstance(keyword, str) and keyword.strip() else None
    sort = params.get("sort")
    if sort not in ("rating", "downloads", "price_asc", "price_desc"):
        sort = "rating"
    return {
        "category": category,
        "keyword": keyword,
        "min_price": _coerce_price(params.get("min_price")),
        "max_price": _coerce_price(params.get("max_price")),
        "sort": sort,
    }


def _detect_category(message: str, params: dict) -> str:
    cat = (params.get("category") or "").strip()
    if cat in VALID_CATEGORIES:
        return cat
    msg_lower = (message or "").lower()
    for valid in VALID_CATEGORIES:
        if valid.lower() in msg_lower:
            return valid
    return "Agent"


def _safe_reason(reason: str, description: str, fallback_name: str) -> str:
    """Keep the LLM reason only if it directly quotes the real description."""
    desc = (description or "").strip()
    norm = lambda s: re.sub(r"\s+", "", s)
    if reason and desc and norm(reason) in norm(desc):
        return reason.strip()
    return desc[:80] if desc else f"推荐使用：{fallback_name}"


def _rule_step(product) -> dict:
    reason = (product.description or "")[:80].strip() or f"推荐使用：{product.name}"
    return {"title": f"推荐方案：{product.name}",
            "product_id": product.id, "reason": reason}


def _build_match_card(steps: list[dict], full: dict) -> dict:
    card_steps, total_price = [], 0
    for step in steps:
        product = full[step["product_id"]]
        total_price += product.price
        card_steps.append({
            "title": step["title"],
            "product": {
                "id": product.id, "name": product.name,
                "category": product.category, "price": product.price,
                "rating": product.rating,
            },
            "reason": step["reason"],
        })
    return {"type": "match", "steps": card_steps, "total_price": total_price}


def _validated_steps(raw_steps, full: dict) -> list[dict]:
    """Drop fabricated ids / duplicates; sanitise titles and reasons."""
    seen, steps = set(), []
    # At most 4 steps per match card.
    for item in (raw_steps or [])[:4]:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get("product_id"))
        except (TypeError, ValueError):
            continue
        if pid not in full or pid in seen:
            continue
        seen.add(pid)
        product = full[pid]
        title = str(item.get("title") or "").strip()[:60] or f"使用 {product.name}"
        reason = _safe_reason(str(item.get("reason") or ""),
                              product.description, product.name)
        steps.append({"title": title, "product_id": pid, "reason": reason})
    return steps


def _bounty_prefill_card(user_msg: str, params: dict) -> dict:
    category = _detect_category(user_msg, params)
    title_src = (user_msg or "").strip()
    title = title_src if len(title_src) <= 24 else title_src[:24]
    return {"type": "bounty", "step": "fill", "data": {
        "title": f"找人开发：{title}",
        "description": user_msg,
        "category": category,
        "budget_min": None, "budget_max": None, "deadline": "",
        "skill_type": "code", "requirements": "",
    }}


def _zero_result_reply(user_msg: str, params: dict, llm_reply: str) -> dict:
    card = _bounty_prefill_card(user_msg, params)
    guidance = (
        "\n\n市场上暂时没有能直接完成这个任务的现成商品。"
        "您可以**发布悬赏找人开发**——我已按您的原话预填好需求，"
        "在下方卡片补充预算即可提交；也可以前往[悬赏市场](/bounties)看看。"
    )
    prose = _strip_fenced_json(llm_reply)
    if prose:
        reply = prose.rstrip() + guidance
    else:
        reply = "暂时没有找到完全匹配的现成商品。" + guidance
    return {"final_reply": reply, "search_results": [],
            "products_json": "[]", "card": card}


async def do_search(state: dict) -> dict:
    messages = state["messages"]
    user_msg = messages[-1].get("content", "") if messages else ""

    llm_reply = ""
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-10:]
        llm_reply = await _call_llm(msgs)
    except Exception:
        params = _normalize_search_params(_fallback_search_params(user_msg))
    else:
        blocks = _extract_json_blocks(llm_reply)
        params = next(
            (b for b in blocks
             if "steps" not in b and ("keyword" in b or "category" in b)),
            None,
        )
        params = _normalize_search_params(
            params if params is not None else _fallback_search_params(user_msg))

    # The zero-match decision is based on the ORIGINAL intent params only.
    # Broadening the query afterwards must never mask it (spec risk 3).
    products, full, search_error = await _run_product_search(params)
    if not products:
        if search_error is not None:
            # Backend/DB failure: do NOT emit a bounty prefill as if the shelf
            # were empty. Retry once with a broad rule-based query instead.
            broad = _normalize_search_params(
                {"category": "", "keyword": None,
                 "min_price": None, "max_price": None, "sort": "rating"})
            products, full, search_error = await _run_product_search(broad)
            if search_error is not None:
                return {"final_reply": "商品搜索暂时不可用，请稍后重试。",
                        "search_results": [], "products_json": "[]", "card": None}
        if not products:
            return _zero_result_reply(user_msg, params, llm_reply)

    # Task decomposition + product selection: search results are the only
    # allowed data source; fabricated ids/reasons are filtered afterwards.
    blocks = _extract_json_blocks(llm_reply)
    raw_steps = next((b.get("steps") for b in blocks
                      if isinstance(b.get("steps"), list)), None)
    if raw_steps is None and llm_reply:
        try:
            results_payload = [
                {"id": p.id, "name": p.name, "category": p.category,
                 "price": p.price, "rating": p.rating, "description": p.description}
                for p in full.values()
            ]
            select_prompt = MATCH_SELECT_PROMPT.replace(
                "__MESSAGE__", user_msg
            ).replace(
                "__RESULTS__", json.dumps(results_payload, ensure_ascii=False)
            )
            select_reply = await _call_llm(
                [{"role": "user", "content": select_prompt}], max_tokens=512)
            select_blocks = _extract_json_blocks(select_reply)
            raw_steps = next((b.get("steps") for b in select_blocks
                              if isinstance(b.get("steps"), list)), None)
        except Exception:
            raw_steps = None

    steps = _validated_steps(raw_steps, full)
    if not steps:
        # Rule fallback: a single-step recommendation from the top hit.
        steps = [_rule_step(full[products[0]["id"]])]
    card = _build_match_card(steps, full)

    prose = _strip_fenced_json(llm_reply)
    reply = (prose + "\n\n" if prose else "为您找到以下推荐方案：\n\n")
    table = "\n".join(
        f"| [{p['name']}](/product/{p['id']}) | {p['category']} | **¥{p['price']}** | {p['rating']:.1f} |"
        for p in products[:8]
    )
    reply += (
        f"**找到 {len(products)} 个相关商品，建议分 {len(card['steps'])} 步完成：**\n\n"
        f"| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n{table}"
    )

    return {"final_reply": reply, "search_results": products,
            "products_json": json.dumps(products), "card": card}


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

    return {"final_reply": reply, "card": card, "search_results": [], "products_json": "[]"}


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

    return {"final_reply": reply, "card": card, "search_results": [], "products_json": "[]"}


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
    return {"final_reply": reply, "card": card, "search_results": [], "products_json": "[]"}


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
                    return {"final_reply": f"已更新 {updated_fields}，请确认卡片：", "card": new_card, "search_results": [], "products_json": "[]"}
        except Exception:
            pass

    # Regular chat. Only actionable form cards (publish/bounty fill flow) are
    # carried forward; terminal cards such as 'match' must not leak into the
    # next unrelated turn.
    active_card = existing_card if existing_card and existing_card.get("step") in ("fill", "preview") else None
    try:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-10:]
        reply = await _call_llm(msgs)
    except Exception:
        reply = "我暂时无法回复，请稍后重试。"

    return {"final_reply": reply, "card": active_card, "search_results": [], "products_json": "[]"}
