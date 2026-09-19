from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from models import SkillVersionCreate, SkillVersionResponse, SkillVersionList, SkillRollbackRequest
from routers.user_v2 import get_current_user
from services import version_service
import database as db


router = APIRouter(prefix="/api/v4", tags=["skill-versions"])


def _verify_owner(product: dict, user: dict) -> None:
    seller = user.get("username") or user.get("nickname") or ""
    if product.get("seller_name") != seller and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权操作他人的商品")


@router.post("/products/{product_id}/versions", response_model=SkillVersionResponse, status_code=201)
async def create_version_endpoint(
    product_id: int,
    version_data: SkillVersionCreate,
    user: dict = Depends(get_current_user),
):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    _verify_owner(product, user)
    return await version_service.create_version(str(product_id), user["id"], version_data)


@router.get("/products/{product_id}/versions", response_model=SkillVersionList)
async def list_versions_endpoint(product_id: int):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return await version_service.get_product_versions(str(product_id))


@router.get("/products/{product_id}/versions/{version}", response_model=SkillVersionResponse)
async def get_version_endpoint(product_id: int, version: str):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    row = await version_service.get_version(str(product_id), version)
    if row is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    return row


@router.put("/products/{product_id}/versions/{version}", response_model=SkillVersionResponse)
async def update_version_endpoint(
    product_id: int,
    version: str,
    version_data: SkillVersionCreate,
    user: dict = Depends(get_current_user),
):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    _verify_owner(product, user)
    row = await version_service.update_version_changelog(
        str(product_id), version, version_data.changelog
    )
    if row is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    return row


@router.post("/products/{product_id}/versions/rollback", response_model=SkillVersionResponse)
async def rollback_version_endpoint(
    product_id: int,
    body: SkillRollbackRequest,
    user: dict = Depends(get_current_user),
):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    _verify_owner(product, user)
    row = await version_service.rollback_to_version(
        str(product_id), body.target_version, user["id"]
    )
    if row is None:
        raise HTTPException(status_code=404, detail="目标版本不存在")
    return row
