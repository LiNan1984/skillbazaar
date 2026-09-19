"""Agent v4 router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from services.agent_v4_service import (
    create_agent_v4,
    list_agents_v4,
    get_agent_v4,
    update_agent_v4,
    add_skill_to_agent_v4,
    remove_skill_from_agent_v4,
)
from routers.user_v2 import get_current_user


class AgentListResponse(BaseModel):
    agents: list[dict]


class AgentSkillAdd(BaseModel):
    product_id: int


router = APIRouter(prefix="/api/v4/agents", tags=["agents-v4"])


@router.post("", status_code=201)
async def create_agent(data: dict, user: dict = Depends(get_current_user)):
    """Create a new agent with skills and model."""
    try:
        return await create_agent_v4(
            user_id=user["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            model=data.get("model", "default"),
            skill_ids=data.get("skill_ids", []),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_agents(user: dict = Depends(get_current_user)):
    """List all agents owned by the current user."""
    try:
        agents = await list_agents_v4(user["id"])
        return {"agents": agents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def get_agent(agent_id: int, user: dict = Depends(get_current_user)):
    """Get a specific agent with its skills."""
    try:
        agent = await get_agent_v4(agent_id, user["id"])
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}")
async def update_agent(agent_id: int, data: dict, user: dict = Depends(get_current_user)):
    """Update an agent's metadata."""
    try:
        agent = await update_agent_v4(
            agent_id=agent_id,
            user_id=user["id"],
            **{k: v for k, v in data.items() if v is not None},
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/skills")
async def add_skill(agent_id: int, data: AgentSkillAdd, user: dict = Depends(get_current_user)):
    """Add a skill to an agent."""
    try:
        agent = await add_skill_to_agent_v4(agent_id, user["id"], data.product_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/skills/{product_id}")
async def remove_skill(agent_id: int, product_id: int, user: dict = Depends(get_current_user)):
    """Remove a skill from an agent."""
    try:
        agent = await remove_skill_from_agent_v4(agent_id, user["id"], product_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
