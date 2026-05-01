from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from models import UserCreate, UserResponse
import services.user_service as user_service

router = APIRouter(prefix="/api/users", tags=["users"])


class CoinUpdateRequest(BaseModel):
    amount: int


@router.post("/init", response_model=UserResponse, status_code=201)
async def init_user(body: Optional[UserCreate] = Body(default=None)):
    nickname = body.nickname if body and body.nickname else None
    avatar = body.avatar if body and body.avatar else None
    user = await user_service.create_anonymous_user(nickname=nickname, avatar=avatar)
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    user = await user_service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}/coins", response_model=UserResponse)
async def update_coins(user_id: str, body: CoinUpdateRequest):
    user = await user_service.update_coins(user_id, body.amount)
    if user is None:
        raise HTTPException(status_code=400, detail="更新失败，请检查用户是否存在或余额是否足够")
    return user
