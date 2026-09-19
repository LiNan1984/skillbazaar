"""Smart Pricing Suggestions endpoints v4.5.1.

Endpoints
---------
POST /api/v4/pricing/suggest   — get price suggestion for a product
GET  /api/v4/pricing/trends/{category} — get category price trends
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

import services.smart_pricing_service as pricing_service
from models import (
    PricingSuggestionResponse,
    PricingTrendResponse,
    PricingSuggestRequest,
)

router = APIRouter(prefix="/api/v4/pricing", tags=["pricing-v4"])


@router.post("/suggest", response_model=PricingSuggestionResponse)
async def suggest_price(req: PricingSuggestRequest):
    """Return a data-informed price suggestion based on market data."""
    try:
        result = await pricing_service.get_price_suggestion(
            product_id=req.product_id,
            category=req.category,
        )
        return PricingSuggestionResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "不存在" in msg or "暂无" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.get("/trends/{category}", response_model=PricingTrendResponse)
async def get_price_trends(
    category: str,
    days: int = Query(30, ge=1, le=365),
):
    """Return price statistics and trend direction for a category."""
    try:
        result = await pricing_service.get_category_trends(category, days)
        return PricingTrendResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "days" in msg:
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=404, detail=msg)
