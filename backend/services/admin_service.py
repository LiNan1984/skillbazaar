from __future__ import annotations

import database as db


async def list_bounties_for_admin(
    status: str | None = None, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    db_conn = await db.get_db()
    try:
        conditions = []
        params: list = []
        if status:
            conditions.append("b.status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_cursor = await db_conn.execute(
            f"SELECT COUNT(*) FROM bounties b{where}", params
        )
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * page_size
        data_cursor = await db_conn.execute(
            f"""SELECT b.*, u.nickname as poster_name, u.username as poster_username,
                u.avatar as poster_avatar, u.status as poster_status
            FROM bounties b
            LEFT JOIN users u ON b.poster_id = u.id
            {where} ORDER BY b.created_at DESC LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        )
        rows = await data_cursor.fetchall()
        return [dict(r) for r in rows], total
    finally:
        await db_conn.close()


async def update_bounty_status(
    bounty_id: int, status: str, reason: str = ""
) -> dict | None:
    bounty = await db.fetch_bounty_by_id(bounty_id)
    if not bounty:
        return None
    success = await db.update_bounty(bounty_id, {"status": status})
    if not success:
        return None
    return {"id": bounty_id, "status": status, "reason": reason}


async def list_skills_for_admin(
    page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    db_conn = await db.get_db()
    try:
        count_cursor = await db_conn.execute("SELECT COUNT(*) FROM skill_assets")
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * page_size
        data_cursor = await db_conn.execute(
            """SELECT sa.*, p.name as product_name, p.category, p.status as product_status
            FROM skill_assets sa
            LEFT JOIN products p ON sa.product_id = p.id
            ORDER BY sa.created_at DESC LIMIT ? OFFSET ?""",
            (page_size, offset),
        )
        rows = await data_cursor.fetchall()
        return [dict(r) for r in rows], total
    finally:
        await db_conn.close()


async def update_skill_status(asset_id: int, status: str) -> dict | None:
    db_conn = await db.get_db()
    try:
        # Add status column to skill_assets if not present
        try:
            await db_conn.execute("ALTER TABLE skill_assets ADD COLUMN status TEXT DEFAULT 'active'")
            await db_conn.commit()
        except Exception:
            pass

        cursor = await db_conn.execute(
            "UPDATE skill_assets SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, asset_id),
        )
        await db_conn.commit()
        if cursor.rowcount == 0:
            return None
        return {"id": asset_id, "status": status}
    finally:
        await db_conn.close()


async def list_users_for_admin(
    page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    db_conn = await db.get_db()
    try:
        count_cursor = await db_conn.execute("SELECT COUNT(*) FROM users")
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * page_size
        data_cursor = await db_conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )
        rows = await data_cursor.fetchall()
        # Strip sensitive fields
        users = []
        for r in rows:
            u = dict(r)
            u.pop("password_hash", None)
            u.pop("auth_token", None)
            users.append(u)
        return users, total
    finally:
        await db_conn.close()


async def update_user_status(user_id: str, status: str) -> dict | None:
    db_conn = await db.get_db()
    try:
        cursor = await db_conn.execute(
            "UPDATE users SET status = ? WHERE id = ?", (status, user_id)
        )
        await db_conn.commit()
        if cursor.rowcount == 0:
            return None
        return {"id": user_id, "status": status}
    finally:
        await db_conn.close()
