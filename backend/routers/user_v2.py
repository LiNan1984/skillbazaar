from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Depends

import database as db
import services.auth_service as auth_service
import services.operations_service as ops
from models import (
    RegisterRequest, LoginRequest, AuthResponse,
    ProfileUpdate, RechargeRequest, BehaviorLog,
)
import services.admin_service as admin_svc
import services.risk_detector as risk_detector

router = APIRouter(prefix="/api/v2", tags=["user-v2"])


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(401, "未登录")
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(401, "登录已过期")
    return user


def _seller_names(user: dict) -> list[str]:
    return [v for v in (user.get("username"), user.get("nickname")) if v]


def _owns_product(product: dict, user: dict) -> bool:
    return user.get("role") == "admin" or product.get("seller_name") in _seller_names(user)


@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    if len(req.username) < 3:
        raise HTTPException(400, "用户名至少3个字符")
    if len(req.password) < 6:
        raise HTTPException(400, "密码至少6个字符")
    result = await auth_service.register_user(req.username, req.password, req.nickname)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return AuthResponse(
        user_id=result["user_id"],
        username=result["username"],
        nickname=result["nickname"],
        token="",
        coins=10000,
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    result = await auth_service.login_user(req.username, req.password)
    if not result:
        raise HTTPException(401, "用户名或密码错误")
    if result.get("error"):
        raise HTTPException(403, result["error"])
    return AuthResponse(**result)


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    profile = await db.fetch_user_profile(user["id"])
    return {
        "user_id": user["id"],
        "username": user.get("username", ""),
        "nickname": user["nickname"],
        "avatar": user["avatar"],
        "coins": user["coins"],
        "role": user.get("role", "user"),
        "profile": profile,
    }


@router.put("/profile")
async def update_profile(req: ProfileUpdate, user: dict = Depends(get_current_user)):
    data = req.dict(exclude_none=True)
    success = await db.update_user_profile(user["id"], data)
    if not success:
        raise HTTPException(400, "更新失败")
    return {"success": True}


@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    return await db.fetch_user_profile(user["id"])


@router.post("/wallet/recharge")
async def recharge(req: RechargeRequest, user: dict = Depends(get_current_user)):
    promo = await db.fetch_promo_code(req.promo_code)
    if not promo:
        raise HTTPException(400, "充值码无效")
    if promo["used_count"] >= promo["max_uses"]:
        raise HTTPException(400, "充值码已用完")
    if promo["expires_at"] and datetime.fromisoformat(promo["expires_at"]) < datetime.now():
        raise HTTPException(400, "充值码已过期")

    success = await db.use_promo_code(promo["id"])
    if not success:
        raise HTTPException(400, "充值码使用失败")

    new_balance = user["coins"] + promo["coins"]
    await db.update_user_coins(user["id"], new_balance)
    await db.insert_wallet_transaction({
        "user_id": user["id"],
        "amount": promo["coins"],
        "balance_after": new_balance,
        "type": "recharge",
        "ref_type": "promo",
        "ref_id": str(promo["id"]),
        "description": f"充值码充值 +{promo['coins']} 金币",
    })

    return {"success": True, "coins_added": promo["coins"], "new_balance": new_balance}


@router.get("/wallet/history")
async def wallet_history(page: int = 1, page_size: int = 20, user: dict = Depends(get_current_user)):
    transactions, total = await db.fetch_wallet_history(user["id"], page, page_size)
    return {"total": total, "page": page, "transactions": transactions}


@router.post("/behavior")
async def log_behavior(req: BehaviorLog, user: dict = Depends(get_current_user)):
    await db.insert_behavior({
        "user_id": user["id"],
        "action": req.action,
        "target_type": req.target_type,
        "target_id": req.target_id,
        "metadata": req.metadata or {},
    })
    await db.increment_task_progress(user["id"], req.action)
    if req.action == "buy":
        await db.increment_task_progress(user["id"], "spend")
    return {"success": True}


@router.get("/notifications")
async def get_notifications(unread_only: bool = False, user: dict = Depends(get_current_user)):
    notifs = await db.fetch_notifications(user["id"], unread_only)
    unread_count = await db.count_unread_notifications(user["id"])
    return {"notifications": notifs, "unread_count": unread_count}


@router.post("/notifications/{notif_id}/read")
async def read_notification(notif_id: int, user: dict = Depends(get_current_user)):
    success = await db.mark_notification_read(notif_id, user["id"])
    if not success:
        raise HTTPException(404, "通知不存在")
    return {"success": True}


# ---- Seller Management ----

@router.get("/seller/products")
async def get_my_products(user: dict = Depends(get_current_user)):
    db_conn = await db.get_db()
    try:
        seller_names = _seller_names(user)
        placeholders = ",".join("?" for _ in seller_names)
        cursor = await db_conn.execute(
            f"SELECT * FROM products WHERE seller_name IN ({placeholders}) ORDER BY created_at DESC",
            seller_names,
        )
        rows = await cursor.fetchall()
        return {"products": [dict(r) for r in rows]}
    finally:
        await db_conn.close()


@router.delete("/seller/products/{product_id}")
async def delete_seller_product(product_id: int, user: dict = Depends(get_current_user)):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")
    if not _owns_product(product, user):
        raise HTTPException(403, "无权删除")
    await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    await db.commit()
    return {"ok": True}


@router.put("/seller/products/{product_id}/status")
async def update_product_status(
    product_id: int,
    status: str,
    reason: str = "",
    user: dict = Depends(get_current_user),
):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")

    if not _owns_product(product, user):
        raise HTTPException(403, "只能管理自己的商品")

    if status not in ("active", "inactive"):
        raise HTTPException(400, "无效状态，只支持 active/inactive")

    db_conn = await db.get_db()
    try:
        await db_conn.execute(
            "UPDATE products SET status = ? WHERE id = ?", (status, product_id)
        )
        await db_conn.commit()
    finally:
        await db_conn.close()

    action = "上架" if status == "active" else "下架"
    await ops.log_skill_event(
        product_id=product_id,
        action=status,
        actor_id=user["id"],
        old_data={"status": product["status"]},
        new_data={"status": status},
        reason=reason or f"卖家{action}",
    )

    return {"success": True, "product_id": product_id, "status": status, "action": action}


@router.get("/seller/stats")
async def seller_stats(user: dict = Depends(get_current_user)):
    seller_names = _seller_names(user)
    placeholders = ",".join("?" for _ in seller_names)
    db_conn = await db.get_db()
    try:
        cur = await db_conn.execute(f"SELECT COUNT(*) FROM products WHERE seller_name IN ({placeholders})", seller_names)
        product_count = (await cur.fetchone())[0]
        cur = await db_conn.execute(f"SELECT COUNT(*) FROM products WHERE seller_name IN ({placeholders}) AND status = 'active'", seller_names)
        active_count = (await cur.fetchone())[0]
        cur = await db_conn.execute(f"SELECT COALESCE(SUM(sales), 0) FROM products WHERE seller_name IN ({placeholders})", seller_names)
        total_sales = (await cur.fetchone())[0]
        return {
            "product_count": product_count,
            "active_count": active_count,
            "inactive_count": product_count - active_count,
            "total_sales": total_sales,
        }
    finally:
        await db_conn.close()


@router.get("/seller/products/{product_id}/lifecycle")
async def product_lifecycle(product_id: int, user: dict = Depends(get_current_user)):
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise HTTPException(404, "商品不存在")
    if not _owns_product(product, user):
        raise HTTPException(403, "只能查看自己的商品")
    events = await db.fetch_lifecycle_events(product_id, limit=50)
    return {"events": events}


# ---- Admin endpoints ----

@router.post("/admin/promo-code")
async def create_promo_code(
    code: str, coins: int, max_uses: int = 1,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    promo_id = await db.insert_promo_code({
        "code": code,
        "coins": coins,
        "max_uses": max_uses,
    })
    return {"id": promo_id, "code": code, "coins": coins}


@router.get("/admin/lifecycle")
async def get_lifecycle_events(product_id: int = None, limit: int = 50, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    events = await db.fetch_lifecycle_events(product_id, limit)
    return {"events": events}


@router.get("/admin/analytics")
async def get_analytics(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    db_conn = await db.get_db()
    try:
        cur = await db_conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cur.fetchone())[0]
        cur = await db_conn.execute("SELECT COUNT(*) FROM products WHERE status='active'")
        total_products = (await cur.fetchone())[0]
        cur = await db_conn.execute("SELECT COUNT(*) FROM transactions")
        total_tx = (await cur.fetchone())[0]
        cur = await db_conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='buy'")
        total_volume = (await cur.fetchone())[0]
        cur = await db_conn.execute("SELECT COUNT(*) FROM skill_assets")
        total_skills = (await cur.fetchone())[0]
        return {
            "total_users": total_users,
            "total_products": total_products,
            "total_transactions": total_tx,
            "total_volume": total_volume,
            "total_skills_uploaded": total_skills,
        }
    finally:
        await db_conn.close()


# ---- Admin Management ----

@router.get("/admin/bounties")
async def admin_list_bounties(
    status: str = None, page: int = 1, page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    bounties, total = await admin_svc.list_bounties_for_admin(status, page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "bounties": bounties}


@router.put("/admin/bounties/{bounty_id}/status")
async def admin_update_bounty_status(
    bounty_id: int,
    status: str,
    reason: str = "",
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    valid_statuses = ("open", "in_progress", "completed", "cancelled", "approved", "rejected")
    if status not in valid_statuses:
        raise HTTPException(400, f"无效状态，支持: {', '.join(valid_statuses)}")
    result = await admin_svc.update_bounty_status(bounty_id, status, reason)
    if not result:
        raise HTTPException(404, "悬赏不存在")
    return {"success": True, **result}


@router.get("/admin/skills")
async def admin_list_skills(
    page: int = 1, page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    skills, total = await admin_svc.list_skills_for_admin(page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "skills": skills}


@router.put("/admin/skills/{asset_id}/status")
async def admin_update_skill_status(
    asset_id: int,
    status: str,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    valid_statuses = ("active", "takedown", "pending")
    if status not in valid_statuses:
        raise HTTPException(400, f"无效状态，支持: {', '.join(valid_statuses)}")
    result = await admin_svc.update_skill_status(asset_id, status)
    if not result:
        raise HTTPException(404, "技能资产不存在")
    return {"success": True, **result}


@router.get("/admin/users")
async def admin_list_users(
    page: int = 1, page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    users, total = await admin_svc.list_users_for_admin(page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "users": users}


@router.put("/admin/users/{user_id}/status")
async def admin_update_user_status(
    user_id: str,
    status: str,
    user: dict = Depends(get_current_user),
):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    valid_statuses = ("active", "banned")
    if status not in valid_statuses:
        raise HTTPException(400, f"无效状态，支持: {', '.join(valid_statuses)}")
    if status == "banned" and user_id == user.get("id"):
        raise HTTPException(400, "不能封禁自己")
    result = await admin_svc.update_user_status(user_id, status)
    if not result:
        raise HTTPException(404, "用户不存在")
    return {"success": True, **result}


@router.post("/admin/scan-risks")
async def admin_scan_risks(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    flagged = await risk_detector.scan_all_risks()
    return {"success": True, "flagged_count": len(flagged), "flagged_items": flagged}
