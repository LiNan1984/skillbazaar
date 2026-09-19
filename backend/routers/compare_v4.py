"""Comparison Tool API endpoints v4.10.

Endpoints
---------
GET /api/v4/compare — Get comparison data for up to 4 products
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import services.comparison_service as comparison_service
from models import CompareResponse

router = APIRouter(tags=["compare-v4"])


@router.get("/api/v4/compare", response_model=CompareResponse)
async def get_comparison(request: Request):
    """Get comparison data for up to 4 products.

    Query params:
        product_ids: Comma-separated list of product IDs (e.g., ?product_ids=1,2,3)

    Business rules:
        - Max 4 products per comparison
        - Returns 400 if more than 4 product_ids
        - Returns 404 if any product_id doesn't exist
    """
    # Extract user_id from header (optional auth)
    user_id = request.headers.get("X-User-Id")

    # Parse product_ids from query params (supports multiple ?product_ids=X&product_ids=Y)
    product_ids_list = request.query_params.getlist("product_ids")
    if not product_ids_list:
        return JSONResponse(status_code=400, content={"error": "请提供 product_ids 参数"})

    try:
        product_ids = [int(pid.strip()) for pid in product_ids_list if pid.strip()]
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "product_ids 格式错误，请使用逗号分隔的数字"})

    if not product_ids:
        return JSONResponse(status_code=400, content={"error": "请至少提供 1 个产品 ID"})

    try:
        result = await comparison_service.get_comparison_data(product_ids, user_id)
    except ValueError as e:
        detail = str(e)
        if "不存在" in detail:
            return JSONResponse(status_code=404, content={"error": detail})
        return JSONResponse(status_code=400, content={"error": detail})

    return CompareResponse(**result)
