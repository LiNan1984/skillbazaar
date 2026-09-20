"""Seller Dashboard API endpoints v4.14.

Endpoints
---------
GET /api/v4/seller/dashboard  — Seller overview stats
GET /api/v4/seller/products   — Seller's products with metrics
GET /api/v4/seller/trends     — Time-series trend data
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query

import services.seller_dashboard_service as seller_service
from models import (
    SellerDashboardResponse,
    SellerProductsResponse,
    SellerTrendResponse,
)

router = APIRouter(prefix="/api/v4/seller", tags=["seller-dashboard-v4"])


def _get_seller_name(request: Request) -> str:
    """Extract username from X-User-Id header."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return user_id


@router.get("/dashboard", response_model=SellerDashboardResponse)
async def get_dashboard(request: Request):
    """Get seller dashboard overview: total stats, top products, recent activity."""
    seller_name = _get_seller_name(request)
    try:
        result = await seller_service.get_dashboard(seller_name)
        return SellerDashboardResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products", response_model=SellerProductsResponse)
async def get_products(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("revenue", regex="^(revenue|views|purchases|rating)$"),
):
    """Get seller's products with performance metrics, sorted by specified field."""
    seller_name = _get_seller_name(request)
    try:
        result = await seller_service.get_products(seller_name, page=page, limit=limit, sort=sort)
        return SellerProductsResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends", response_model=SellerTrendResponse)
async def get_trends(
    request: Request,
    period: str = Query("30d", regex="^(7d|30d|90d)$"),
):
    """Get daily trend data for seller's products over the specified period."""
    seller_name = _get_seller_name(request)
    try:
        result = await seller_service.get_trends(seller_name, period=period)
        return SellerTrendResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
