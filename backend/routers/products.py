from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from models import ProductCreate, ProductResponse, ProductList
import services.product_service as product_service

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
    return product


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(data: ProductCreate):
    product = await product_service.create_product(data.model_dump())
    return product
