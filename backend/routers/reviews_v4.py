"""Skill Reviews & Ratings API endpoints v4.13.

Endpoints
---------
POST   /api/v4/reviews/{product_id}          — create review
GET    /api/v4/reviews/{product_id}          — list reviews (paginated)
PUT    /api/v4/reviews/{review_id}           — update own review
DELETE /api/v4/reviews/{review_id}           — soft-delete own review
POST   /api/v4/reviews/{review_id}/vote      — vote helpful/unhelpful
GET    /api/v4/reviews/{product_id}/summary  — review summary stats
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import services.review_service as review_service
from models import (
    ReviewCreate,
    ReviewUpdate,
    ReviewResponse,
    ReviewVoteRequest,
    ReviewListResponse,
    ReviewSummaryResponse,
)

router = APIRouter(prefix="/api/v4/reviews", tags=["reviews-v4"])


def _get_user_id(request: Request) -> str:
    """Extract user_id from X-User-Id header."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return user_id


# ---------------------------------------------------------------------------
# Create Review
# ---------------------------------------------------------------------------

@router.post("/{product_id}", response_model=ReviewResponse, status_code=201)
async def create_review(product_id: int, data: ReviewCreate, request: Request):
    """Create a review for a purchased product.

    Buyer must have purchased the product. Cannot review own product.
    One review per (user, product) pair.
    """
    user_id = _get_user_id(request)
    try:
        result = await review_service.create_review(
            user_id=user_id,
            product_id=product_id,
            rating=data.rating,
            title=data.title,
            content=data.content,
        )
        return ReviewResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# List Reviews
# ---------------------------------------------------------------------------

@router.get("/{product_id}", response_model=ReviewListResponse)
async def list_reviews(product_id: int, request: Request, page: int = 1, limit: int = 10):
    """List active reviews for a product, newest first."""
    _get_user_id(request)  # auth required
    result = await review_service.list_reviews(product_id, page=page, limit=limit)
    return ReviewListResponse(**result)


# ---------------------------------------------------------------------------
# Update Review
# ---------------------------------------------------------------------------

@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(review_id: int, data: ReviewUpdate, request: Request):
    """Update own review (rating, title, content)."""
    user_id = _get_user_id(request)
    try:
        result = await review_service.update_review(
            review_id=review_id,
            user_id=user_id,
            rating=data.rating,
            title=data.title,
            content=data.content,
        )
        return ReviewResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Delete Review
# ---------------------------------------------------------------------------

@router.delete("/{review_id}")
async def delete_review(review_id: int, request: Request):
    """Soft-delete own review."""
    user_id = _get_user_id(request)
    try:
        result = await review_service.delete_review(review_id, user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Vote Helpful
# ---------------------------------------------------------------------------

@router.post("/{review_id}/vote")
async def vote_review(review_id: int, data: ReviewVoteRequest, request: Request):
    """Vote a review as helpful or unhelpful."""
    user_id = _get_user_id(request)
    try:
        result = await review_service.vote_review(review_id, user_id, data.vote)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------------------------------------------------------------------
# Review Summary
# ---------------------------------------------------------------------------

@router.get("/{product_id}/summary", response_model=ReviewSummaryResponse)
async def review_summary(product_id: int, request: Request):
    """Get review summary: average rating, total reviews, distribution."""
    _get_user_id(request)  # auth required
    result = await review_service.get_review_summary(product_id)
    return ReviewSummaryResponse(**result)
