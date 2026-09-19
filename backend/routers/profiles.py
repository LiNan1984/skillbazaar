from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from models import ProfileUpdate, ProfileResponse, UserProductResponse
from routers.user_v2 import get_current_user
from services import profile_service
import database as db


router = APIRouter(prefix="/api", tags=["profiles"])


async def _resolve_username(username: str) -> str:
    """Look up user_id from username. Raises 404 if not found."""
    db_conn = await db.get_db()
    try:
        cursor = await db_conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return row["id"]
    finally:
        await db_conn.close()


async def _optional_user(authorization: str = Header(None)) -> Optional[dict]:
    """Try to get current user, return None if not authenticated."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    user = await get_current_user(token)
    return user


@router.get("/u/{username}")
async def get_public_profile_endpoint(
    username: str,
    user: Optional[dict] = Depends(_optional_user),
):
    viewer_id = user["id"] if user else None
    profile = await profile_service.get_public_profile(username, viewer_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return profile


@router.get("/u/{username}/products")
async def get_user_products(
    username: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    user_id = await _resolve_username(username)
    return await profile_service.get_user_products_service(user_id, page, page_size)


@router.get("/u/{username}/followers")
async def get_user_followers(
    username: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    user_id = await _resolve_username(username)
    return await profile_service.get_followers(user_id, page, page_size)


@router.get("/u/{username}/following")
async def get_user_following(
    username: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    user_id = await _resolve_username(username)
    return await profile_service.get_following(user_id, page, page_size)


@router.post("/u/{username}/follow")
async def follow_user_endpoint(
    username: str,
    user: dict = Depends(get_current_user),
):
    following_id = await _resolve_username(username)
    try:
        return await profile_service.follow_user(user["id"], following_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/u/{username}/follow")
async def unfollow_user_endpoint(
    username: str,
    user: dict = Depends(get_current_user),
):
    following_id = await _resolve_username(username)
    return await profile_service.unfollow_user(user["id"], following_id)


@router.get("/profile/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    profile = await profile_service.get_public_profile(user["username"], user["id"])
    if profile is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return profile


@router.patch("/profile/me", response_model=ProfileResponse)
async def update_my_profile(
    data: ProfileUpdate,
    user: dict = Depends(get_current_user),
):
    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无有效更新内容")
    updated = await profile_service.update_profile(user["id"], update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="用户不存在")
    # Return updated public profile
    profile = await profile_service.get_public_profile(user["username"], user["id"])
    return ProfileResponse(**profile)
