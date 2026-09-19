from __future__ import annotations

from typing import Optional

import database as db
from models import (
    SkillVersionCreate,
    SkillVersionResponse,
    SkillVersionList,
    SkillRollbackRequest,
)


async def create_version(product_id: str, user_id: str, version_data: SkillVersionCreate) -> dict:
    row = await db.create_skill_version({
        "product_id": product_id,
        "changelog": version_data.changelog,
        "content_preview": version_data.content_preview,
        "created_by": user_id,
    })
    if row is None:
        raise ValueError("Failed to create skill version")
    return row


async def get_product_versions(product_id: str) -> SkillVersionList:
    rows = await db.get_skill_versions(product_id)
    versions = [SkillVersionResponse(**r) for r in rows]
    return SkillVersionList(versions=versions)


async def get_version(product_id: str, version: str) -> SkillVersionResponse | None:
    row = await db.get_skill_version(product_id, version)
    if row is None:
        return None
    return SkillVersionResponse(**row)


async def update_version_changelog(product_id: str, version: str, changelog: str) -> SkillVersionResponse | None:
    row = await db.update_version_changelog(product_id, version, changelog)
    if row is None:
        return None
    return SkillVersionResponse(**row)


async def rollback_to_version(product_id: str, target_version: str, user_id: str) -> SkillVersionResponse | None:
    row = await db.rollback_to_version(product_id, target_version, user_id)
    if row is None:
        return None
    return SkillVersionResponse(**row)
