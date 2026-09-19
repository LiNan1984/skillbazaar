"""Bulk Operations API endpoints v4.12.

Endpoints
---------
POST /api/v4/products/bulk              — execute bulk operation on products
GET  /api/v4/products/bulk/history      — get operation history for current seller
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import services.bulk_operation_service as bulk_service
from models import (
    BulkOperationRequest,
    BulkOperationResponse,
    BulkOperationHistoryResponse,
)

router = APIRouter(tags=["bulk-operations-v4"])

MAX_BULK_PRODUCTS = 50


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/v4/products/bulk", response_model=BulkOperationResponse)
async def execute_bulk_operation(request: BulkOperationRequest, req: Request):
    """Execute a bulk operation on up to 50 products.

    Auth: X-User-Id header required.

    Operations: "publish", "unpublish", "price_update", "delete"

    Price update params:
      - {"percentage": 10}   — increase price by 10%
      - {"amount": -5}       — decrease price by ¥5

    Delete is a soft delete (sets status='inactive').
    """
    user_id = req.headers.get("X-User-Id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    # Validate operation type
    valid_ops = {"publish", "unpublish", "price_update", "delete"}
    if request.operation not in valid_ops:
        return JSONResponse(
            status_code=400,
            content={"error": f"不支持的操作类型: {request.operation}。支持的类型: {', '.join(sorted(valid_ops))}"},
        )

    # Validate product count
    if not request.product_ids:
        return JSONResponse(
            status_code=400,
            content={"error": "请至少选择一个商品"},
        )

    if len(request.product_ids) > MAX_BULK_PRODUCTS:
        return JSONResponse(
            status_code=400,
            content={"error": f"单次批量操作最多支持{MAX_BULK_PRODUCTS}个商品，当前选择了{len(request.product_ids)}个"},
        )

    # Validate price_update params
    if request.operation == "price_update":
        params = request.params or {}
        if "percentage" not in params and "amount" not in params:
            return JSONResponse(
                status_code=400,
                content={"error": "price_update 操作需要 params 中包含 'percentage' 或 'amount'"},
            )
        if "percentage" in params:
            try:
                pct = float(params["percentage"])
                if pct < -100 or pct > 100:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"百分比必须在-100到100之间，当前值: {pct}"},
                    )
            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={"error": f"percentage 必须是数字，当前值: {params['percentage']}"},
                )
        if "amount" in params:
            try:
                int(params["amount"])
            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={"error": f"amount 必须是整数，当前值: {params['amount']}"},
                )

    try:
        result = await bulk_service.execute_bulk_operation(
            user_id=user_id,
            operation=request.operation,
            product_ids=request.product_ids,
            params=request.params,
        )
        return BulkOperationResponse(**result)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@router.get("/api/v4/products/bulk/history", response_model=BulkOperationHistoryResponse)
async def get_bulk_history(request: Request, page: int = 1, limit: int = 20):
    """Get paginated history of bulk operations for the current seller.

    Query params:
        page: page number (default 1)
        limit: items per page (default 20)
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "未登录"})

    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 20

    result = await bulk_service.get_bulk_operation_history(user_id, page=page, limit=limit)
    return BulkOperationHistoryResponse(**result)
