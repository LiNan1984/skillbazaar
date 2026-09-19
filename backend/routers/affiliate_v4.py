"""Affiliate program endpoints v4.4.

Endpoints
---------
POST   /api/v4/affiliate/generate/{product_id}  – generate affiliate link
GET    /api/v4/affiliate/click/{code}            – track click & redirect
GET    /api/v4/affiliate/stats/{product_id}      – get affiliate stats
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Depends, Request

import database as db
import services.auth_service as auth_service
import services.affiliate_service as affiliate_service
from models import AffiliateLinkResponse, AffiliateStatsResponse

router = APIRouter(prefix="/api/v4/affiliate", tags=["affiliate-v4"])


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(401, "未登录")
    token = (
        authorization.replace("Bearer ", "")
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(401, "登录已过期")
    return user


@router.post("/generate/{product_id}", response_model=AffiliateLinkResponse, status_code=201)
async def generate_link(
    product_id: int,
    user: dict = Depends(get_current_user),
):
    """Generate an affiliate link for a product (seller only)."""
    # Verify seller owns the product
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    if product.get("seller_name") != user["username"]:
        raise HTTPException(403, "Only the seller can generate affiliate links")

    link = await affiliate_service.generate_affiliate_link(user["username"], product_id)
    base_url = "http://localhost:8000"  # TODO: make configurable
    link["link"] = f"{base_url}/api/v4/affiliate/click/{link['code']}"
    return AffiliateLinkResponse(**link)


@router.get("/click/{code}")
async def click_affiliate_link(request: Request, code: str):
    """Track affiliate click and redirect to product page."""
    link = await db.get_affiliate_link_by_code(code)
    if not link:
        raise HTTPException(404, "Invalid affiliate link")

    if not link.get("is_active", 1):
        raise HTTPException(404, "Affiliate link is inactive")

    # Track click
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await db.track_affiliate_click(link["id"], ip_address, user_agent)

    # Set affiliate cookie (30 days) and redirect to product page
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url=f"/api/products/{link['product_id']}", status_code=302)
    response.set_cookie(
        key="affiliate_code",
        value=code,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
    )
    return response


@router.get("/stats/{product_id}", response_model=AffiliateStatsResponse)
async def get_stats(
    product_id: int,
    user: dict = Depends(get_current_user),
):
    """Get affiliate statistics for a product (seller only)."""
    stats = await affiliate_service.get_affiliate_statistics(product_id, user["username"])
    return AffiliateStatsResponse(**stats)
