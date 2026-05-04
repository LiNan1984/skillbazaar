from fastapi import APIRouter, HTTPException, Depends, Query

from models import PointRedeemRequest
from services import activity_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/activities", tags=["activities"])


@router.get("")
async def get_activities(user: dict = Depends(get_current_user)):
    return await activity_service.get_activities_with_tasks(user["id"])


@router.post("/checkin")
async def checkin(user: dict = Depends(get_current_user)):
    return await activity_service.checkin(user["id"])


@router.post("/tasks/{task_id}/claim")
async def claim_reward(task_id: int, user: dict = Depends(get_current_user)):
    result = await activity_service.claim_reward(user["id"], task_id)
    if not result:
        raise HTTPException(400, "任务未完成或已领取")
    return result


@router.get("/points/balance")
async def get_points(user: dict = Depends(get_current_user)):
    return await activity_service.get_point_account(user["id"])


@router.get("/points/history")
async def get_point_history(user: dict = Depends(get_current_user), limit: int = 50):
    return await activity_service.get_point_history(user["id"], limit)


@router.post("/points/redeem")
async def redeem_points(data: PointRedeemRequest, user: dict = Depends(get_current_user)):
    try:
        return await activity_service.redeem_points(user["id"], data.amount, data.redeem_type)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/leaderboard")
async def leaderboard(limit: int = 20):
    return await activity_service.get_leaderboard(limit)
