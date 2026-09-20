from __future__ import annotations

import json
import logging
import os
import re

import httpx

LLM_API_URL = "https://api.finmall.com/v1/chat/completions"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = "GLM-5.1-FP8"

RISK_PROMPT = """你是 SkillBazaar 平台的内容安全审核AI。分析以下内容是否包含风险。

检查维度：
1. 欺诈（fraud）- 虚假宣传、钓鱼、骗取用户信息
2. 恶意软件（malware）- 包含恶意代码、后门、病毒
3. 垃圾信息（spam）- 重复内容、无意义填充、广告骚扰
4. 违法内容（illegal）- 涉及违法交易、洗钱、非法活动
5. 版权侵犯（copyright）- 盗用他人作品、未授权转载

回复JSON格式（用```json ```包裹）：
```json
{{
  "risk_score": 0-100的整数,
  "risk_tags": ["标签列表"],
  "reason": "判定理由"
}}
```

内容类型：{content_type}
标题：{title}
描述：{description}
"""


class RiskScanUnavailable(Exception):
    """LLM unavailable (missing key/outage); scan must fail open without fake data."""


async def _call_llm(messages: list[dict], max_tokens: int = 512) -> str:
    if not LLM_API_KEY:
        raise RiskScanUnavailable("LLM_API_KEY 未配置，跳过 AI 风控扫描")
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
    pattern2 = r'\{[^{}]*"risk_score"[^{}]*\}'
    match2 = re.search(pattern2, text, re.DOTALL)
    if match2:
        try:
            return json.loads(match2.group())
        except json.JSONDecodeError:
            pass
    return {}


async def scan_bounty_risks(bounty: dict) -> dict:
    prompt = RISK_PROMPT.format(
        content_type="悬赏需求",
        title=bounty.get("title", ""),
        description=bounty.get("description", ""),
    )
    try:
        result = await _call_llm([{"role": "user", "content": prompt}])
        parsed = _extract_json(result)
        return {
            "item_type": "bounty",
            "item_id": bounty.get("id"),
            "title": bounty.get("title", ""),
            "risk_score": parsed.get("risk_score", 0),
            "risk_tags": parsed.get("risk_tags", []),
            "reason": parsed.get("reason", ""),
        }
    except Exception as exc:
        # Fail open: no pseudo "scan failed" record written; caller skips it.
        logging.warning("bounty risk scan skipped for %s: %s", bounty.get("id"), exc)
        return None


async def scan_skill_risks(skill_asset: dict) -> dict:
    prompt = RISK_PROMPT.format(
        content_type="技能资产",
        title=skill_asset.get("product_name", ""),
        description=skill_asset.get("skill_meta", ""),
    )
    try:
        result = await _call_llm([{"role": "user", "content": prompt}])
        parsed = _extract_json(result)
        return {
            "item_type": "skill",
            "item_id": skill_asset.get("id"),
            "title": skill_asset.get("product_name", ""),
            "risk_score": parsed.get("risk_score", 0),
            "risk_tags": parsed.get("risk_tags", []),
            "reason": parsed.get("reason", ""),
        }
    except Exception as exc:
        logging.warning("skill risk scan skipped for %s: %s", skill_asset.get("id"), exc)
        return None


async def scan_all_risks() -> list[dict]:
    import database as db

    flagged: list[dict] = []

    # Scan open bounties
    bounties, _ = await db.fetch_bounties(status="open", page=1, page_size=100)
    for bounty in bounties:
        result = await scan_bounty_risks(bounty)
        if result and result["risk_score"] > 70:
            flagged.append(result)

    # Scan active skills
    skills, _ = await list_skills_with_meta(page=1, page_size=100)
    for skill in skills:
        result = await scan_skill_risks(skill)
        if result and result["risk_score"] > 70:
            flagged.append(result)

    # Sort by risk_score descending
    flagged.sort(key=lambda x: x["risk_score"], reverse=True)
    return flagged


async def list_skills_with_meta(
    page: int = 1, page_size: int = 100
) -> tuple[list[dict], int]:
    import database as db

    db_conn = await db.get_db()
    try:
        count_cursor = await db_conn.execute("SELECT COUNT(*) FROM skill_assets")
        total = (await count_cursor.fetchone())[0]
        offset = (page - 1) * page_size
        data_cursor = await db_conn.execute(
            """SELECT sa.*, p.name as product_name
            FROM skill_assets sa
            LEFT JOIN products p ON sa.product_id = p.id
            ORDER BY sa.created_at DESC LIMIT ? OFFSET ?""",
            (page_size, offset),
        )
        rows = await data_cursor.fetchall()
        return [dict(r) for r in rows], total
    finally:
        await db_conn.close()
