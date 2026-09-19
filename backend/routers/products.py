from __future__ import annotations

import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from models import ProductCreate, ProductResponse, ProductList, ReviewCreate
import services.product_service as product_service
import database as db
from routers.user_v2 import get_current_user
import asyncio
from services import analytics_service

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductList)
async def list_products(
    category: Optional[str] = Query(None, description="商品类别: Agent/Skill/Cron/Workflow"),
    sub_category: Optional[str] = Query(None, description="子类别"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    min_price: Optional[int] = Query(None, description="最低价格"),
    max_price: Optional[int] = Query(None, description="最高价格"),
    sort_by: str = Query("downloads", description="排序: downloads/rating/price_asc/price_desc/sales/newest"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    runtime: Optional[str] = Query(None, description="Filter by compat runtime (e.g. prompt, code, sdk)"),
):
    return await product_service.get_products(
        category=category,
        sub_category=sub_category,
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        runtime=runtime,
    )


@router.get("/categories")
async def get_categories():
    tree = await product_service.get_category_tree()
    return {"categories": tree}


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    product = await product_service.get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    # Embed latest eval_report if available
    report = await db.fetch_eval_report(product_id)
    if report:
        # Parse JSON fields
        for field in ("flags", "static_flags"):
            raw = report.get(field)
            if isinstance(raw, str):
                try:
                    report[field] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    report[field] = []
        product.eval_report = report

    # Track view (non-blocking)
    asyncio.create_task(
        analytics_service.record_view(product_id, None, "direct", None)
    )

    return product


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(data: ProductCreate):
    product = await product_service.create_product(data.model_dump())
    # Trigger async evaluation only if no eval report exists yet
    import asyncio
    from services import eval_service
    import database as db
    existing_report = await db.fetch_eval_report(product.id)
    if existing_report is None:
        asyncio.create_task(eval_service.evaluate_product(product.id))
    return product


@router.get("/{product_id}/reviews")
async def list_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
):
    result = await product_service.list_reviews(product_id, page, page_size)
    if result is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return result


@router.post("/{product_id}/reviews")
async def create_product_review(
    product_id: int,
    body: ReviewCreate,
    user: dict = Depends(get_current_user),
):
    try:
        return await product_service.create_review(
            user, product_id, body.rating, body.content,
        )
    except product_service.ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except product_service.NotPurchasedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except product_service.DuplicateReviewError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{product_id}/eval-report")
async def get_eval_report(product_id: int):
    report = await db.fetch_eval_report(product_id)
    if report is None:
        return {"status": "pending", "product_id": product_id}
    # Parse JSON fields
    for field in ("flags", "static_flags"):
        raw = report.get(field)
        if isinstance(raw, str):
            try:
                report[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                report[field] = []
    return report
