from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header

import database as db
from services.bounty_service import (
    create_bounty, get_bounties, get_bounty_detail,
    apply_for_bounty, select_developer, deliver_bounty, review_delivery,
)
from services.auth_service import verify_token
from models import (
    BountyCreate, BountyApplicationCreate,
    BountyAcceptRequest, BountyReviewRequest,
)

router = APIRouter(prefix="/api/bounties", tags=["bounties"])


@router.get("")
async def list_bounties(
    status: str = None, category: str = None, keyword: str = None,
    page: int = 1, page_size: int = 20,
):
    return await get_bounties(status=status, category=category, keyword=keyword,
                             page=page, page_size=page_size)


@router.get("/{bounty_id}")
async def bounty_detail(bounty_id: int):
    bounty = await get_bounty_detail(bounty_id)
    if not bounty:
        raise HTTPException(404, "Bounty not found")
    return bounty


@router.post("")
async def post_bounty(req: BountyCreate, authorization: str = Header(None)):
    user_id = await _resolve_user(authorization)
    if not user_id:
        raise HTTPException(401, "Login required")
    bounty = await create_bounty(user_id, req.model_dump())
    return bounty


@router.post("/{bounty_id}/apply")
async def apply_bounty(bounty_id: int, req: BountyApplicationCreate, authorization: str = Header(None)):
    user_id = await _resolve_user(authorization)
    if not user_id:
        raise HTTPException(401, "Login required")
    try:
        req.bounty_id = bounty_id
        result = await apply_for_bounty(user_id, req.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{bounty_id}/select")
async def select_dev(bounty_id: int, req: BountyAcceptRequest, authorization: str = Header(None)):
    user_id = await _resolve_user(authorization)
    if not user_id:
        raise HTTPException(401, "Login required")
    try:
        result = await select_developer(user_id, req.application_id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{bounty_id}/deliver")
async def deliver(
    bounty_id: int, authorization: str = Header(None),
    description: str = Form(""),
    file: UploadFile = File(None),
):
    user_id = await _resolve_user(authorization)
    if not user_id:
        raise HTTPException(401, "Login required")
    content = b""
    if file:
        content = await file.read()
    try:
        result = await deliver_bounty(user_id, bounty_id, description, content if content else None)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{bounty_id}/review")
async def review(bounty_id: int, req: BountyReviewRequest, authorization: str = Header(None)):
    user_id = await _resolve_user(authorization)
    if not user_id:
        raise HTTPException(401, "Login required")
    try:
        result = await review_delivery(user_id, req.delivery_id, req.accept)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/my/posted")
async def my_posted_bounties(user_id: str, authorization: str = Header(None)):
    uid = await _resolve_user(authorization) or user_id
    bounties, total = await db.fetch_user_bounties(uid, "poster")
    return {"bounties": bounties, "total": total}


@router.get("/my/applied")
async def my_applied_bounties(user_id: str, authorization: str = Header(None)):
    uid = await _resolve_user(authorization) or user_id
    bounties, total = await db.fetch_user_bounties(uid, "developer")
    return {"bounties": bounties, "total": total}


async def _resolve_user(authorization: str | None) -> str | None:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    user = await verify_token(token)
    return user.get("id") if user else None
