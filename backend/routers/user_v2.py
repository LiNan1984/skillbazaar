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

router = APIRouter(prefix="/api/v2", tags=["user-v2"])


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(401, "未登录")
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    user = await auth_service.verify_token(token)
    if not user:
        raise HTTPException(401, "登录已过期")
    return user


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
        seller = user.get("username") or user.get("nickname") or ""
        cursor = await db_conn.execute(
            "SELECT * FROM products WHERE seller_name = ? ORDER BY created_at DESC",
            (seller,),
        )
        rows = await cursor.fetchall()
        return {"products": [dict(r) for r in rows]}
    finally:
        await db_conn.close()


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

    seller = user.get("username") or user.get("nickname") or ""
    if product["seller_name"] != seller and user.get("role") != "admin":
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
    seller = user.get("username") or user.get("nickname") or ""
    db_conn = await db.get_db()
    try:
        cur = await db_conn.execute("SELECT COUNT(*) FROM products WHERE seller_name = ?", (seller,))
        product_count = (await cur.fetchone())[0]
        cur = await db_conn.execute("SELECT COUNT(*) FROM products WHERE seller_name = ? AND status = 'active'", (seller,))
        active_count = (await cur.fetchone())[0]
        cur = await db_conn.execute("SELECT COALESCE(SUM(sales), 0) FROM products WHERE seller_name = ?", (seller,))
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
    seller = user.get("username") or user.get("nickname") or ""
    if product["seller_name"] != seller and user.get("role") != "admin":
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
