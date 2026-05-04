from fastapi import APIRouter, HTTPException, Depends

from models import UserAgentCreate, UserAgentUpdate, AgentRunRequest
from services import agent_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("")
async def create_agent(data: UserAgentCreate, user: dict = Depends(get_current_user)):
    try:
        return await agent_service.create_agent(
            user["id"], data.name, data.description, data.system_prompt, data.skill_ids
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("")
async def list_agents(user: dict = Depends(get_current_user)):
    return await agent_service.get_user_agents(user["id"])


@router.get("/{agent_id}")
async def get_agent(agent_id: int, user: dict = Depends(get_current_user)):
    result = await agent_service.get_agent_detail(agent_id, user["id"])
    if not result:
        raise HTTPException(404, "智能体不存在")
    return result


@router.put("/{agent_id}")
async def update_agent(agent_id: int, data: UserAgentUpdate, user: dict = Depends(get_current_user)):
    fields = {k: v for k, v in data.dict().items() if v is not None}
    if not fields:
        raise HTTPException(400, "没有需要更新的字段")
    ok = await agent_service.update_agent(agent_id, user["id"], **fields)
    if not ok:
        raise HTTPException(404, "智能体不存在")
    return {"ok": True}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, user: dict = Depends(get_current_user)):
    ok = await agent_service.delete_agent(agent_id, user["id"])
    if not ok:
        raise HTTPException(404, "智能体不存在")
    return {"ok": True}


@router.post("/{agent_id}/run")
async def run_agent(agent_id: int, data: AgentRunRequest, user: dict = Depends(get_current_user)):
    try:
        return await agent_service.run_agent(agent_id, user["id"], data.input_text)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{agent_id}/runs")
async def get_runs(agent_id: int, limit: int = 20, user: dict = Depends(get_current_user)):
    try:
        return await agent_service.get_agent_runs(agent_id, user["id"], limit)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{agent_id}/schedule")
async def schedule_agent(agent_id: int, cron_expression: str = "0 9 * * *", user: dict = Depends(get_current_user)):
    try:
        return await agent_service.schedule_agent_cron(agent_id, user["id"], cron_expression)
    except ValueError as e:
        raise HTTPException(400, str(e))
