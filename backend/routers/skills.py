from __future__ import annotations

import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

import database as db
from services.skill_vault import encrypt_content
from services.license_service import create_license, check_user_access, verify_license
from services.execution_service import execute_skill
from services.pricing_service import calculate_dynamic_price, get_price_analysis, recalculate_all_dynamic_prices
from models import (
    SkillAssetResponse, LicenseResponse, LicenseCreate,
    LicenseVerifyRequest, LicenseVerifyResponse, SkillExecutionRequest,
    PricingUpdate,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.post("/upload")
async def upload_skill(
    product_id: int = Form(...),
    skill_type: str = Form(...),
    skill_meta: str = Form(None),
    file: UploadFile = File(None),
    seller_id: str = Form(...),
):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    if skill_type not in ("prompt", "code", "sdk"):
        raise HTTPException(400, "Invalid skill_type. Must be: prompt, code, sdk")

    existing = await db.fetch_skill_asset(product_id)
    if existing:
        raise HTTPException(400, "Skill already uploaded for this product")

    content = b""
    if file:
        content = await file.read()
    elif skill_meta:
        content = skill_meta.encode("utf-8") if isinstance(skill_meta, str) else json.dumps(skill_meta).encode("utf-8")
    else:
        raise HTTPException(400, "Must provide either file or skill_meta")

    encrypted = encrypt_content(content)

    asset_id = await db.insert_skill_asset({
        "product_id": product_id,
        "skill_type": skill_type,
        "encrypted_blob": encrypted["encrypted_blob"],
        "encryption_iv": encrypted["encryption_iv"],
        "encryption_salt": encrypted["encryption_salt"],
        "skill_meta": skill_meta,
        "content_hash": encrypted["content_hash"],
        "file_size": encrypted["file_size"],
    })

    return {"id": asset_id, "product_id": product_id, "skill_type": skill_type, "status": "encrypted"}


@router.post("/{product_id}/execute")
async def execute_skill_endpoint(product_id: int, req: SkillExecutionRequest):
    user_id = req.user_id or "anonymous"

    # Create trial license if user doesn't have one
    access = await check_user_access(user_id, product_id)
    license_id = None

    if not access.get("has_access"):
        try:
            license_data = await create_license(
                user_id=user_id,
                product_id=product_id,
                license_type="trial",
                max_calls=3,
            )
            license_id = license_data.get("id")
        except Exception:
            license_id = None
    else:
        license_id = access.get("license", {}).get("id")

    skill_asset = await db.fetch_skill_asset(product_id)
    if not skill_asset:
        raise HTTPException(404, "No skill asset found for this product")

    try:
        result = await execute_skill(
            user_id=user_id,
            product_id=product_id,
            license_id=license_id,
            skill_asset=skill_asset,
            input_params=req.input_params,
        )
    except Exception as e:
        return {"error": str(e), "skill_type": skill_asset.get("skill_type", "unknown")}

    return result


@router.post("/license")
async def create_license_endpoint(req: LicenseCreate):
    license_data = await create_license(
        user_id=req.user_id,
        product_id=req.product_id,
        license_type=req.license_type,
        max_calls=req.max_calls,
    )
    return license_data


@router.post("/license/verify")
async def verify_license_endpoint(req: LicenseVerifyRequest):
    result = await verify_license(req.license_token, req.product_id)
    return result


@router.get("/my")
async def my_skills(user_id: str):
    licenses = await db.fetch_user_licenses(user_id)
    return {"licenses": licenses}


@router.get("/{product_id}/stats")
async def skill_stats(product_id: int):
    executions = await db.fetch_user_executions("", limit=1000)
    product_execs = [e for e in executions if e["product_id"] == product_id]
    return {
        "product_id": product_id,
        "total_executions": len(product_execs),
        "success_count": sum(1 for e in product_execs if e["status"] == "success"),
        "failed_count": sum(1 for e in product_execs if e["status"] == "failed"),
    }


@router.get("/{product_id}/pricing")
async def get_pricing(product_id: int):
    analysis = await get_price_analysis(product_id)
    if not analysis:
        raise HTTPException(404, "Product not found")
    return analysis


@router.put("/{product_id}/pricing")
async def update_pricing(product_id: int, req: PricingUpdate):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    await db.update_product_pricing_model(product_id, req.pricing_model)
    if req.pricing_model == "dynamic":
        result = await calculate_dynamic_price(product)
        return result
    return {"product_id": product_id, "pricing_model": req.pricing_model}


@router.post("/pricing/recalculate")
async def recalculate_pricing():
    results = await recalculate_all_dynamic_prices()
    return {"recalculated": len(results), "prices": results}
