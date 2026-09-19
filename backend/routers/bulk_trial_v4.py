"""Bulk Trial Run API endpoints v4.11.

Endpoints
---------
POST /api/v4/trial/bulk                        — execute bulk trial runs (max 5 products)
GET  /api/v4/trial/bulk/eligibility            — check bulk trial eligibility
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse

import services.trial_service as trial_service
import services.auth_service as auth_service
from models import (
    BulkTrialRequest,
    BulkTrialResponse,
    BulkTrialEligibilityResponse,
)

router = APIRouter(tags=["trial-bulk-v4"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def get_current_user(authorization: str = Header(None)) -> dict:
    """Get current user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = (
        authorization.replace("Bearer ", "")
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/v4/trial/bulk", response_model=BulkTrialResponse)
async def run_bulk_trial_endpoint(
    request: BulkTrialRequest,
    user: dict = Depends(get_current_user),
):
    """Execute bulk trial runs for up to 5 products."""
    # Enforce max 5 products
    if len(request.product_ids) > 5:
        return JSONResponse(
            status_code=400,
            content={"error": f"最多同时试用5个商品，当前选择了{len(request.product_ids)}个"},
        )

    if not request.product_ids:
        return JSONResponse(
            status_code=400,
            content={"error": "请至少选择一个商品"},
        )

    result = await trial_service.run_bulk_trial(
        user_id=user["id"],
        product_ids=request.product_ids,
        input_text=request.input_text,
    )
    return BulkTrialResponse(**result)


@router.get("/api/v4/trial/bulk/eligibility", response_model=BulkTrialEligibilityResponse)
async def bulk_trial_eligibility_endpoint(
    product_ids: str,
    user: dict = Depends(get_current_user),
):
    """Check bulk trial eligibility for a list of products.

    Query param: product_ids — comma-separated list of product IDs.
    """
    # Parse comma-separated product IDs
    try:
        ids = [int(pid.strip()) for pid in product_ids.split(",") if pid.strip()]
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "商品ID格式错误，请使用逗号分隔的数字"},
        )

    if not ids:
        return JSONResponse(
            status_code=400,
            content={"error": "请至少选择一个商品"},
        )

    if len(ids) > 5:
        return JSONResponse(
            status_code=400,
            content={"error": f"最多同时检查5个商品，当前选择了{len(ids)}个"},
        )

    result = await trial_service.get_bulk_trial_eligibility(user["id"], ids)
    return BulkTrialEligibilityResponse(**result)
