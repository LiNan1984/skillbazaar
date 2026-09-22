from __future__ import annotations

import io
import json
import zipfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

import database as db
from services.skill_vault import encrypt_content, decrypt_content, verify_integrity
from services.license_service import create_license, check_user_access, verify_license
from services.execution_service import execute_skill
from services.pricing_service import calculate_dynamic_price, get_price_analysis, recalculate_all_dynamic_prices
from services.trial_limiter import check_rate_limit, record_request
from models import (
    SkillAssetResponse, LicenseResponse, LicenseCreate,
    LicenseVerifyRequest, LicenseVerifyResponse, SkillExecutionRequest,
    PricingUpdate, LicenseType,
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
async def execute_skill_endpoint(product_id: int, req: SkillExecutionRequest, request: Request):
    # --- Identity ---
    user_id = req.user_id or "anonymous"
    is_anonymous = req.user_id is None

    # --- IP extraction for rate limiting (test: X-Forwarded-For; prod: client host) ---
    forwarded = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")

    # --- Rate limit (anonymous only) ---
    if is_anonymous:
        allowed, retry_after = check_rate_limit(client_ip, product_id)
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "今日试用次数已达上限", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

    # --- License check / create trial ---
    license_id = None
    access = await check_user_access(user_id, product_id)
    if access.get("has_access"):
        license_id = access.get("license", {}).get("id")

    if license_id is None:
        trial = await create_license(
            user_id=user_id, product_id=product_id,
            license_type=LicenseType.TRIAL, max_calls=3,
        )
        license_id = trial.get("id")

    # --- Enforce max_calls BEFORE execution (authenticated users only) ---
    # Anonymous users are rate-limited (10/hour per product); trial license
    # max_calls is enforced for authenticated trial users.
    if license_id and not is_anonymous:
        lic = await db.fetch_license_by_id(license_id)
        if lic and lic.get("max_calls") and lic.get("calls_count", 0) >= lic["max_calls"]:
            return {"error": "试用次数已用完，购买后可继续使用", "trial_remaining": 0, "status": "trial_exhausted"}

    # --- Input length check for trial ---
    if is_anonymous and req.input_params and len(req.input_params) > 2000:
        raise HTTPException(400, "试用输入不能超过 2000 字符")

    # --- Skill asset ---
    skill_asset = await db.fetch_skill_asset(product_id)
    if not skill_asset:
        raise HTTPException(404, "No skill asset found for this product")

    # --- Execute ---
    try:
        result = await execute_skill(
            user_id=user_id,
            product_id=product_id,
            license_id=license_id,
            skill_asset=skill_asset,
            input_params=req.input_params,
            trial_mode=is_anonymous,
        )
    except Exception as e:
        return {"error": str(e), "skill_type": skill_asset.get("skill_type", "unknown")}

    # --- Post-execution bookkeeping ---
    if is_anonymous:
        record_request(client_ip, product_id)

    trial_remaining = None
    if license_id:
        lic = await db.fetch_license_by_id(license_id)
        if lic:
            remaining = (lic.get("max_calls") or 0) - lic.get("calls_count", 0)
            trial_remaining = max(0, remaining)

    result["trial_remaining"] = trial_remaining
    return result


@router.get("/{product_id}/download")
async def download_skill_package(
    product_id: int,
    license_token: str = Query(None, description="License token，已购买用户可用"),
    user_id: str = Query(None, description="用户 ID，与登录 token 二选一"),
    authorization: str = None,
):
    """下载 Skill 包（zip）。

    - 已购买 / 持有有效 license：下载完整包（code 类型为上传时的 zip 原包，
      prompt 类型自动打包为含 SKILL.md 的 zip）。
    - 未购买：仅 prompt 类型允许预览下载；code / sdk 返回 403。
    """
    from services.license_service import verify_license as _verify_license

    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    asset = await db.fetch_skill_asset(product_id)
    if not asset:
        raise HTTPException(404, "No skill asset found for this product")

    # --- 授权校验：license_token 或 user_id 任一通过即可 ---
    # 购买记录（transactions）与 license 都算数： buy_product 只写交易不建 license。
    has_access = False
    if license_token:
        verified = await _verify_license(license_token, product_id)
        has_access = bool(verified.get("valid"))
    if not has_access and user_id:
        access = await check_user_access(user_id, product_id)
        has_access = bool(access.get("has_access"))
    if not has_access and user_id and await db.check_already_purchased(user_id, product_id):
        has_access = True
    if not has_access and asset.get("skill_type") != "prompt":
        raise HTTPException(403, "购买后可下载 Skill 包")

    content = decrypt_content(
        asset["encrypted_blob"],
        asset["encryption_iv"],
        asset["encryption_salt"],
    )
    if asset.get("content_hash") and not verify_integrity(content, asset["content_hash"]):
        raise HTTPException(500, "Skill 包完整性校验失败")

    name = product.get("name") or f"skill-{product_id}"
    if content[:4] == b"PK\x03\x04":
        payload, filename = content, f"{name}.zip"
    else:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("SKILL.md", content)
        payload, filename = buf.getvalue(), f"{name}-skill.zip"

    try:
        await db.increment_product_downloads(product_id)
    except Exception:
        pass  # 计数失败不影响下载

    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(payload)),
            "X-Skill-Sha256": asset.get("content_hash") or "",
        },
    )


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
