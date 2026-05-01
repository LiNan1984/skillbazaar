from __future__ import annotations

import json
import re
import httpx

from models import ChatResponse, ProductResponse
import services.product_service as product_service

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = "sk-bV3TVx9azStj8KJe3oW0rsqpaIZKX8E21wyXMtHYCjWBxly1"
LLM_MODEL = "GLM-5.1-FP8"

SYSTEM_PROMPT = """你是 SkillBazaar 市场的 AI 买卖助手"BS买卖助手"。SkillBazaar 是一个 AI Agent、Skill、Cron 和 Workflow 的交易市场。

你的职责：
1. 理解用户想找什么类型的商品，帮买家搜索推荐
2. 引导想卖商品的用户去发布商品或发布悬赏
3. 提取关键词、功能需求、价格范围
4. 回复包含搜索参数（JSON格式）

## 搜索模式
当用户想找商品时，返回 ```json ``` 包裹的搜索参数：
```json
{"category": "Agent或Skill或Cron或Workflow或空字符串", "keyword": "搜索关键词", "min_price": null, "max_price": null, "sort": "rating或downloads或price_asc或price_desc"}
```

## 上传/发布引导
当用户说"我要上传商品"、"我想卖"、"怎么发布"、"我要上架"等类似意图时：
- 热情引导用户前往发布页面，告诉用户：
  1. 点击页面顶部的「发布商品」按钮，或访问 /publish 页面
  2. 支持三种技能类型：Prompt（提示词）、Code（代码包）、SDK（接口对接）
  3. 上传后自动加密保护，设置价格即可上架
  4. 也支持去「悬赏市场」(/bounties) 发布需求让别人开发
- 不要说"帮不了"，你是全能助手，要主动给出操作步骤

## 悬赏引导
当用户说"我想找人开发"、"有没有人能做"、"需要定制"时：
- 引导用户前往悬赏市场 (/bounties) 发布悬赏任务
- 说明流程：发布需求 → 开发者竞标 → 选定开发 → 交付验收 → 自动付款

回复规则：
- 用中文回复，热情专业
- 使用 Markdown 格式
- 搜索类回复必须包含 JSON 搜索参数
- 打招呼、闲聊、上传引导、悬赏引导不需要返回 JSON"""

_sessions: dict[str, list[dict]] = {}


def _get_history(user_id: str) -> list[dict]:
    if user_id not in _sessions:
        _sessions[user_id] = []
    return _sessions[user_id]


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
    async with httpx.AsyncClient(timeout=20) as client:
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


async def handle_chat(user_id: str, message: str) -> ChatResponse:
    history = _get_history(user_id)
    history.append({"role": "user", "content": message})

    # Single LLM call to get reply + search params
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-10:]
        llm_reply = await _call_llm(messages)
    except Exception:
        llm_reply = ""

    if llm_reply:
        history.append({"role": "assistant", "content": llm_reply})

    if len(history) > 20:
        _sessions[user_id] = history[-16:]

    # Extract params and search
    params = _extract_json(llm_reply) if llm_reply else {}
    products = []

    if params:
        try:
            result = await product_service.get_products(
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
            pass

    # Build reply
    if llm_reply:
        reply = re.sub(r"```json\s*\{[^}]+\}\s*```", "", llm_reply, flags=re.DOTALL).strip()
    else:
        reply = "让我为您搜索一下..."

    if products:
        table_rows = "\n".join(
            f"| [{p.name}](/product/{p.id}) | {p.category} | **¥{p.price}** | {p.rating:.1f} |"
            for p in products[:8]
        )
        reply += f"\n\n🎉 **找到 {len(products)} 个推荐：**\n\n| 名称 | 分类 | 价格 | 评分 |\n|------|------|------|------|\n{table_rows}"
    elif params and not products:
        reply += "\n\n😕 暂时没有找到完全匹配的商品，试试换个关键词？"

    return ChatResponse(reply=reply, products=products)
