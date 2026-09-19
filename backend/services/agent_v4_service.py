"""Agent v4 service."""
from __future__ import annotations

import json

import database as db
from models import UserAgentResponse, AgentSkillInfo


async def create_agent_v4(user_id: str, name: str, description: str, model: str, skill_ids: list[int]) -> dict:
    """Create an agent with model field and separate skill tracking."""
    agent_id = await db.create_agent_v4(user_id, name, description, model)

    # Add skills to agent_skills table
    for sid in skill_ids:
        await db.add_agent_skill(agent_id, sid)

    # Build response
    skills = await db.get_agent_skills(agent_id)
    skill_list = []
    for s in skills:
        skill_list.append(AgentSkillInfo(
            product_id=s["product_id"],
            name=s.get("product_name", ""),
            price=s.get("product_price", 0),
            category=s.get("category", ""),
        ))

    return {
        "id": agent_id,
        "owner_id": user_id,
        "name": name,
        "description": description,
        "model": model,
        "skills": [sk.dict() for sk in skill_list],
        "created_at": None,
    }


async def list_agents_v4(user_id: str) -> list[dict]:
    """List all agents for a user with their skills."""
    agents = await db.fetch_user_agents(user_id)
    result = []
    for agent in agents:
        agent_config = {}
        if agent.get("agent_config"):
            try:
                agent_config = json.loads(agent["agent_config"])
            except Exception:
                pass

        model = agent_config.get("model", "default")
        skills = await db.get_agent_skills(agent["id"])
        skill_list = []
        for s in skills:
            skill_list.append({
                "product_id": s["product_id"],
                "name": s.get("product_name", ""),
                "price": s.get("product_price", 0),
                "category": s.get("category", ""),
            })

        result.append({
            "id": agent["id"],
            "owner_id": agent["user_id"],
            "name": agent["name"],
            "description": agent.get("description", ""),
            "model": model,
            "skills": skill_list,
            "created_at": agent.get("created_at"),
        })
    return result


async def get_agent_v4(agent_id: int, user_id: str) -> dict | None:
    """Get a single agent with its skills."""
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return None

    agent_config = {}
    if agent.get("agent_config"):
        try:
            agent_config = json.loads(agent["agent_config"])
        except Exception:
            pass

    model = agent_config.get("model", "default")
    skills = await db.get_agent_skills(agent_id)
    skill_list = []
    for s in skills:
        skill_list.append({
            "product_id": s["product_id"],
            "name": s.get("product_name", ""),
            "price": s.get("product_price", 0),
            "category": s.get("category", ""),
        })

    return {
        "id": agent["id"],
        "owner_id": agent["user_id"],
        "name": agent["name"],
        "description": agent.get("description", ""),
        "model": model,
        "skills": skill_list,
        "created_at": agent.get("created_at"),
    }


async def update_agent_v4(agent_id: int, user_id: str, **fields) -> dict | None:
    """Update an agent's metadata."""
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return None

    # Handle model field specially (stored in agent_config)
    model = fields.pop("model", None)
    if model is not None:
        agent_config = {}
        if agent.get("agent_config"):
            try:
                agent_config = json.loads(agent["agent_config"])
            except Exception:
                pass
        agent_config["model"] = model
        fields["agent_config"] = json.dumps(agent_config)

    await db.update_user_agent(agent_id, **fields)
    return await get_agent_v4(agent_id, user_id)


async def add_skill_to_agent_v4(agent_id: int, user_id: str, product_id: int) -> dict | None:
    """Add a skill to an agent."""
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return None

    await db.add_agent_skill(agent_id, product_id)
    return await get_agent_v4(agent_id, user_id)


async def remove_skill_from_agent_v4(agent_id: int, user_id: str, product_id: int) -> dict | None:
    """Remove a skill from an agent."""
    agent = await db.fetch_user_agent(agent_id, user_id)
    if not agent:
        return None

    await db.remove_agent_skill(agent_id, product_id)
    return await get_agent_v4(agent_id, user_id)
