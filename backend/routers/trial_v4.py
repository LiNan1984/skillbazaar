"""Trial Run API endpoints v4.9.

Endpoints
---------
POST /api/v4/trial/run                    — execute a trial run of a Skill
GET  /api/v4/trial/my                     — list current user's trial history
GET  /api/v4/trial/can-trial              — check if user can trial a product
POST /api/v4/cron/cleanup-trials          — cron: clean up old trial runs
"""
from __future__ import annotations

import datetime
from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse

import services.trial_service as trial_service
import services.auth_service as auth_service
from models import (
    TrialRunRequest,
    TrialRunResponse,
    TrialHistoryResponse,
    CanTrialResponse,
    TrialCleanupResponse,
)

router = APIRouter(tags=["trial-v4"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def get_current_user(authorization: str = Header(None)) -> dict:
    """Get current user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = (
        authorization.replace("Bearer ", "")
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/v4/trial/run", response_model=TrialRunResponse)
async def run_trial_endpoint(request: TrialRunRequest, user: dict = Depends(get_current_user)):
    """Execute a trial run of a Skill."""
    try:
        result = await trial_service.run_trial(
            user_id=user["id"],
            product_id=request.product_id,
            input_text=request.input_text,
        )
        return TrialRunResponse(**result)
    except ValueError as e:
        detail = str(e)
        return JSONResponse(
            status_code=400,
            content={"error": detail},
        )


@router.get("/api/v4/trial/my", response_model=TrialHistoryResponse)
async def get_my_trials_endpoint(
    product_id: int | None = None,
    user: dict = Depends(get_current_user),
):
    """List current user's trial history, optionally filtered by product."""
    trials = await trial_service.get_trial_history(user["id"], product_id)
    return TrialHistoryResponse(trials=trials)


@router.get("/api/v4/trial/can-trial", response_model=CanTrialResponse)
async def can_trial_endpoint(product_id: int, user: dict = Depends(get_current_user)):
    """Check if user can trial a product."""
    result = await trial_service.can_trial(user["id"], product_id)
    return CanTrialResponse(**result)


@router.post("/api/v4/cron/cleanup-trials", response_model=TrialCleanupResponse)
async def cleanup_trials_cron():
    """Cron: clean up old trial runs (>30 days). No auth required."""
    result = await trial_service.cleanup_old_trials()
    return TrialCleanupResponse(**result)
