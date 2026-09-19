"""Wishlist endpoints v4.3.

Endpoints
---------
POST   /api/v4/wishlist/{product_id}   – add product to wishlist
GET    /api/v4/wishlist                – list user's wishlist
DELETE /api/v4/wishlist/{product_id}   – remove product from wishlist
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Depends

import database as db
import services.auth_service as auth_service
import services.wishlist_service as wishlist_service
from models import WishlistItemResponse, WishlistListResponse

router = APIRouter(prefix="/api/v4/wishlist", tags=["wishlist-v4"])


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


@router.post("/{product_id}", response_model=WishlistItemResponse, status_code=201)
async def add_to_wishlist(
    product_id: int,
    user: dict = Depends(get_current_user),
):
    """Add a product to the current user's wishlist."""
    try:
        item = await wishlist_service.add_to_wishlist(user["id"], product_id)
        return WishlistItemResponse(**item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=WishlistListResponse)
async def list_wishlist(user: dict = Depends(get_current_user)):
    """List all items in the current user's wishlist."""
    items = await wishlist_service.get_user_wishlist(user["id"])
    return {"items": items}


@router.delete("/{product_id}")
async def remove_from_wishlist(
    product_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove a product from the current user's wishlist."""
    ok = await wishlist_service.remove_from_wishlist(user["id"], product_id)
    if not ok:
        raise HTTPException(404, "商品不在愿望单中")
    return {"success": True}
