"""Skill Bundles v4 router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from routers.user_v2 import get_current_user

import services.bundle_service as bundle_service
from models import BundleCreate, BundleListResponse, BundlePurchaseResponse, BundleResponse


router = APIRouter(prefix="/api/v4/bundles", tags=["bundles-v4"])


@router.post("/", response_model=BundleResponse, status_code=201)
async def create_bundle(
    data: BundleCreate,
    user: dict = Depends(get_current_user),
):
    """Create a new bundle of skills/products."""
    try:
        return await bundle_service.create_bundle(
            seller_id=user["id"],
            name=data.name,
            description=data.description,
            product_ids=data.product_ids,
            discount_percent=data.discount_percent,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=BundleListResponse)
async def list_bundles():
    """List all active bundles."""
    try:
        bundles = await bundle_service.list_bundles()
        return BundleListResponse(bundles=bundles)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{bundle_id}/purchase", response_model=BundlePurchaseResponse)
async def purchase_bundle(
    bundle_id: int,
    user: dict = Depends(get_current_user),
):
    """Purchase a bundle - grants licenses for all included products."""
    try:
        return await bundle_service.purchase_bundle(
            bundle_id=bundle_id,
            buyer_id=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{bundle_id}/skills", response_model=BundleResponse)
async def add_skill_to_bundle(
    bundle_id: int,
    data: dict,
    user: dict = Depends(get_current_user),
):
    """Add a skill/product to an existing bundle."""
    product_id = data.get("product_id")
    if product_id is None:
        raise HTTPException(status_code=422, detail="product_id required")

    try:
        return await bundle_service.add_skill_to_bundle(
            bundle_id=bundle_id,
            product_id=product_id,
            seller_id=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{bundle_id}/skills/{product_id}", response_model=BundleResponse)
async def remove_skill_from_bundle(
    bundle_id: int,
    product_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove a skill/product from an existing bundle."""
    try:
        return await bundle_service.remove_skill_from_bundle(
            bundle_id=bundle_id,
            product_id=product_id,
            seller_id=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
