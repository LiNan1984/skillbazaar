"""Product recommendation endpoints v4.3.

Endpoints
---------
GET /api/v4/recommendations/similar/{product_id}   – similar products by category
GET /api/v4/recommendations/fbt/{product_id}        – frequently bought together
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import services.recommendation_service as rec_service
from models import RecommendationsResponse

router = APIRouter(prefix="/api/v4/recommendations", tags=["recommendations-v4"])


@router.get("/similar/{product_id}", response_model=RecommendationsResponse)
async def similar_products(product_id: int):
    """Get products similar to the given product (same category)."""
    recs = await rec_service.get_similar_products(product_id)
    return {"recommendations": recs}


@router.get("/fbt/{product_id}", response_model=RecommendationsResponse)
async def frequently_bought_together(product_id: int):
    """Get products frequently bought together with the given product."""
    recs = await rec_service.get_frequently_bought_together(product_id)
    return {"recommendations": recs}
