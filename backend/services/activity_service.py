from __future__ import annotations

from typing import Optional

import database as db


async def get_activities_with_tasks(user_id: str) -> list:
    activities = await db.fetch_active_activities()
    result = []
    for act in activities:
        tasks = await db.fetch_activity_tasks(act["id"])
        task_list = []
        for t in tasks:
            prog = await db.fetch_or_create_task_progress(user_id, t["id"])
            task_list.append({
                **t,
                "progress": prog["progress"],
                "completed": bool(prog["completed"]),
                "reward_claimed": bool(prog["reward_claimed"]),
            })
        result.append({**act, "tasks": task_list})
    return result


async def checkin(user_id: str) -> dict:
    await db.get_or_create_point_account(user_id)
    result = await db.do_checkin(user_id)
    await db.update_user_level(user_id)
    return result


async def claim_reward(user_id: str, task_id: int) -> Optional[dict]:
    reward = await db.claim_task_reward(user_id, task_id)
    if reward:
        await db.update_user_level(user_id)
    return reward


async def get_point_account(user_id: str) -> dict:
    return await db.get_or_create_point_account(user_id)


async def get_point_history(user_id: str, limit: int = 50) -> list:
    return await db.fetch_point_history(user_id, limit)


async def redeem_points(user_id: str, amount: int, redeem_type: str = "coins") -> dict:
    account = await db.get_or_create_point_account(user_id)
    if redeem_type == "coins":
        cost = amount * 10
        if account["balance"] < cost:
            raise ValueError("积分不足")
        ok = await db.spend_points(user_id, cost, "redeem_coins", "redeem", None)
        if not ok:
            raise ValueError("积分扣除失败")
        await db.update_user_coins(user_id, amount)
        await db.increment_task_progress(user_id, "spend")
        return {"coins_received": amount, "points_spent": cost}
    elif redeem_type == "sandbox":
        # 沙盒时长兑换: 100积分 = 1小时沙盒时长
        hours = amount
        cost = hours * 100
        if account["balance"] < cost:
            raise ValueError(f"积分不足，需要{cost}积分兑换{hours}小时沙盒时长")
        ok = await db.spend_points(user_id, cost, "redeem_sandbox", "redeem", None)
        if not ok:
            raise ValueError("积分扣除失败")
        # Add sandbox quota to user — use get_db() directly
        import aiosqlite
        _db = await aiosqlite.connect(db.DB_PATH)
        try:
            await _db.execute(
                "UPDATE users SET sandbox_quota = COALESCE(sandbox_quota, 0) + ? WHERE id = ?",
                (hours * 3600, user_id)
            )
            await _db.commit()
        finally:
            await _db.close()
        await db.increment_task_progress(user_id, "spend")
        return {"sandbox_hours_received": hours, "points_spent": cost, "message": f"🦐 获得{hours}小时沙盒时长！让你的虾去打工吧！"}
    raise ValueError("不支持的兑换类型")


async def get_leaderboard(limit: int = 20) -> list:
    return await db.fetch_points_leaderboard(limit)
