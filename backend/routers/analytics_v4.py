"""Analytics Dashboard v4 router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from routers.user_v2 import get_current_user

import services.analytics_v4_service as analytics_v4_service
from models import (
    ProductAnalyticsDashboard,
    CategoryAnalyticsResponse,
    PlatformOverviewResponse,
)


router = APIRouter(prefix="/api/v4/analytics", tags=["analytics-v4"])


@router.get("/products/{product_id}", response_model=ProductAnalyticsDashboard)
async def get_product_analytics(
    product_id: int,
    user: dict = Depends(get_current_user),
):
    """Get analytics for a single product.

    Returns views, purchases, conversion rate, and revenue.
    Only the seller of the product can view its analytics.
    """
    try:
        return await analytics_v4_service.get_product_analytics_dashboard(
            product_id=product_id,
            user_id=user["username"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized to view this product's analytics")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=CategoryAnalyticsResponse)
async def get_category_analytics(
    user: dict = Depends(get_current_user),
):
    """Get analytics grouped by product category.

    Returns product count and revenue for each category for the current seller's products.
    """
    try:
        return await analytics_v4_service.get_category_analytics(user["username"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", response_model=PlatformOverviewResponse)
async def get_platform_overview(
    user: dict = Depends(get_current_user),
):
    """Get platform-wide overview metrics.

    Returns total products, users, revenue, and top categories.
    """
    try:
        return await analytics_v4_service.get_platform_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
