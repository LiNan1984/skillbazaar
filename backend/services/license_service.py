from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

import database as db
from models import LicenseType


async def create_license(
    user_id: str,
    product_id: int,
    license_type: LicenseType = LicenseType.PERMANENT,
    max_calls: Optional[int] = None,
) -> dict:
    token = str(uuid.uuid4())
    expires_at = None
    if license_type == LicenseType.TRIAL:
        expires_at = (datetime.now() + timedelta(days=7)).isoformat()
        max_calls = max_calls or 3
    elif license_type == LicenseType.SUBSCRIPTION:
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()

    license_id = await db.insert_license({
        "user_id": user_id,
        "product_id": product_id,
        "license_type": license_type.value,
        "license_token": token,
        "expires_at": expires_at,
        "max_calls": max_calls,
    })
    return {
        "id": license_id,
        "license_token": token,
        "license_type": license_type.value,
        "expires_at": expires_at,
        "max_calls": max_calls,
    }


async def verify_license(token: str, product_id: int) -> dict:
    license_data = await db.fetch_license_by_token(token)
    if not license_data:
        return {"valid": False, "reason": "License not found"}
    if license_data["product_id"] != product_id:
        return {"valid": False, "reason": "Product mismatch"}
    if license_data["status"] != "active":
        return {"valid": False, "reason": "License revoked"}
    if license_data["expires_at"]:
        expires = datetime.fromisoformat(license_data["expires_at"])
        if datetime.now() > expires:
            return {"valid": False, "reason": "License expired"}
    calls_remaining = None
    if license_data["max_calls"]:
        calls_remaining = license_data["max_calls"] - license_data["calls_count"]
        if calls_remaining <= 0:
            return {"valid": False, "reason": "Call limit reached"}
    return {
        "valid": True,
        "license_id": license_data["id"],
        "license_type": license_data["license_type"],
        "calls_remaining": calls_remaining,
        "expires_at": license_data["expires_at"],
    }


async def check_user_access(user_id: str, product_id: int) -> dict:
    license_data = await db.check_user_has_license(user_id, product_id)
    if not license_data:
        return {"has_access": False}
    return {"has_access": True, "license": license_data}
