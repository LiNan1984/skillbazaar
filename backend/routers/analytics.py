"""Seller Analytics Dashboard router."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response
import csv
import io

import services.analytics_service as analytics_service
from routers.user_v2 import get_current_user
from models import SellerDashboardResponse


router = APIRouter(prefix="/api/seller", tags=["seller"])


@router.get("/dashboard", response_model=SellerDashboardResponse)
async def get_dashboard(
    period: str = Query("30d", description="Period: 7d, 30d, 90d"),
    metric: str = Query("revenue", description="Metric for top products: views, purchases, revenue"),
    limit: int = Query(10, ge=1, le=50, description="Number of top products"),
    user: dict = Depends(get_current_user),
):
    """Get seller dashboard with aggregated metrics across all products."""
    username = user.get("username", "")
    try:
        return await analytics_service.get_seller_dashboard(
            user_id=user["id"],
            username=username,
            period=period,
            metric=metric,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/analytics")
async def get_product_analytics(
    product_id: int,
    period: str = Query("30d", description="Period: 7d, 30d, 90d"),
    user: dict = Depends(get_current_user),
):
    """Get detailed analytics for a single product."""
    username = user.get("username", "")
    try:
        result = await analytics_service.get_product_analytics(
            product_id=product_id,
            seller_name=username,
            period=period,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not authorized to view this product's analytics")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/export")
async def export_analytics(
    period: str = Query("30d", description="Period: 7d, 30d, 90d"),
    user: dict = Depends(get_current_user),
):
    """Export seller analytics as CSV."""
    username = user.get("username", "")
    try:
        dashboard = await analytics_service.get_seller_dashboard(
            user_id=user["id"],
            username=username,
            period=period,
        )

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "date", "product_id", "product_name", "views", "unique_visitors",
            "cart_adds", "purchases", "revenue_cents", "conversion_rate"
        ])

        # Data rows
        for top_product in dashboard.top_products:
            # For CSV export, include summary data
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d"),
                top_product.product_id,
                top_product.product_name,
                top_product.views,
                0,  # unique_visitors not in top_products
                0,  # cart_adds not in top_products
                top_product.purchases,
                top_product.revenue_cents,
                round((top_product.purchases / top_product.views * 100) if top_product.views > 0 else 0.0, 2),
            ])

        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_{datetime.now().strftime('%Y%m%d')}.csv"
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
