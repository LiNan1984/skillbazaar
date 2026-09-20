from __future__ import annotations

import json
from typing import Optional

import database as db
from agents.nodes import _call_llm, SYSTEM_PROMPT


async def create_agent(user_id: str, name: str, description: str, system_prompt: str, skill_ids: list[int]) -> dict:
    agent_id = await db.insert_user_agent(user_id, name, description, system_prompt, skill_ids)
    return {"id": agent_id, "name": name}


async def get_user_agents(user_id: str) -> list[dict]:
    agents = await db.fetch_user_agents(user_id)
    for a in agents:
        if isinstance(a.get("skill_ids"), str):
            try:
                a["skill_ids"] = json.loads(a["skill_ids"])
            except Exception:
                a["skill_ids"] = []
        # Fetch skill names
        skill_names = []
        for sid in a.get("skill_ids", []):
            p = await db.fetch_product_by_id(sid)
            if p:
                skill_names.append({"id": sid, "name": p["name"], "category": p["category"]})
        a["skills"] = skill_names
    return agents


async def get_agent_detail(agent_id: int, user_id: str) -> Optional[dict]:
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return None
    if isinstance(agent.get("skill_ids"), str):
        try:
            agent["skill_ids"] = json.loads(agent["skill_ids"])
        except Exception:
            agent["skill_ids"] = []
    skill_names = []
    for sid in agent.get("skill_ids", []):
        p = await db.fetch_product_by_id(sid)
        if p:
            skill_names.append({"id": sid, "name": p["name"], "category": p["category"]})
    agent["skills"] = skill_names
    return agent


async def update_agent(agent_id: int, user_id: str, **fields) -> bool:
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return False
    await db.update_user_agent(agent_id, **fields)
    return True


async def delete_agent(agent_id: int, user_id: str) -> bool:
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return False
    await db.delete_user_agent(agent_id, user_id)
    return True


async def run_agent(agent_id: int, user_id: str, input_text: str, trigger_type: str = "manual") -> dict:
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        raise ValueError("智能体不存在")

    # Build prompt with skill context
    skill_ids = json.loads(agent["skill_ids"]) if isinstance(agent["skill_ids"], str) else agent["skill_ids"]
    skill_context = ""
    for sid in skill_ids:
        p = await db.fetch_product_by_id(sid)
        if p:
            skill_context += f"\n- {p['name']} ({p['category']}): {p.get('description', '')[:200]}"

    system = agent.get("system_prompt") or SYSTEM_PROMPT
    if skill_context:
        system += f"\n\n你可以使用以下技能：{skill_context}"

    messages = [{"role": "system", "content": system}]
    if input_text:
        messages.append({"role": "user", "content": input_text})
    else:
        messages.append({"role": "user", "content": "请基于你的技能和配置执行任务。"})

    try:
        reply = await _call_llm(messages, max_tokens=1024)
        status = "success"
    except Exception:
        # LLM unavailable - generate skill-based fallback
        if skill_ids:
            parts = []
            for sid in skill_ids:
                p = await db.fetch_product_by_id(sid)
                if p:
                    parts.append(f"- [{p['name']}](/product/{p['id']}) — {p.get('description', '')[:100]}")
            reply = f"## {agent['name']} 执行报告\n\n已装配技能：\n\n" + "\n".join(parts)
            if input_text:
                reply += f"\n\n**输入:** {input_text}\n\n> AI引擎暂时不可用，请点击技能链接查看详情。"
        else:
            reply = f"## {agent['name']}\n\n尚未装配技能。请前往 [我的库](/library) 购买技能后装配。\n\n> AI引擎暂时不可用。"
        status = "partial"

    await db.increment_agent_runs(agent_id)
    run_id = await db.insert_agent_run(agent_id, trigger_type, input_text, reply, 0, status)
    return {"id": run_id, "output": reply, "status": status}


async def get_agent_runs(agent_id: int, user_id: str, limit: int = 20) -> list[dict]:
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        raise ValueError("智能体不存在")
    return await db.fetch_agent_runs(agent_id, limit)


async def schedule_agent_cron(agent_id: int, user_id: str, cron_expression: str) -> dict:
    """Register an agent as a Cron product so it can be scheduled."""
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        raise ValueError("智能体不存在")
    # Create a pseudo product for this agent's cron
    import secrets
    product_id = await db.insert_product({
        "name": f"[Cron] {agent['name']}",
        "description": agent.get("description", ""),
        "category": "Cron",
        "price": 0,
        "seller_name": user_id,
        "tags": "[]",
    })
    cron_id = await db.insert_cron_product(product_id, cron_expression, f"whs_{secrets.token_hex(16)}", "json")
    await db.update_user_agent(agent_id, agent_config=json.dumps({"cron_id": cron_id, "cron_expression": cron_expression, "product_id": product_id}))
    return {"cron_id": cron_id, "product_id": product_id}
