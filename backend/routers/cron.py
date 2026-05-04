from fastapi import APIRouter, Header, HTTPException, Depends, Query
from typing import Optional

from models import CronProductCreate, CronPushRequest
from services import cron_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/cron", tags=["cron"])


@router.post("/register")
async def register_cron(data: CronProductCreate, user: dict = Depends(get_current_user)):
    try:
        return await cron_service.register_cron_product(user["id"], data.product_id, data.schedule_cron, data.result_format)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/subscribe/{cron_id}")
async def subscribe_cron(cron_id: int, webhook_url: Optional[str] = Query(None), payment_method: str = Query("coins"), user: dict = Depends(get_current_user)):
    try:
        return await cron_service.subscribe_cron(user["id"], cron_id, webhook_url, payment_method)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/push/{cron_id}")
async def push_result(cron_id: int, data: CronPushRequest, x_webhook_secret: str = Header(..., alias="X-Webhook-Secret")):
    try:
        result = await cron_service.push_cron_result(cron_id, x_webhook_secret, data.payload, data.duration_ms)
    except ValueError as e:
        raise HTTPException(400, str(e))
    
    # Async email push to email subscribers
    try:
        import database as db
        import asyncio
        from services.email_service import send_cron_push_email
        
        db_conn = await db.get_db()
        cursor = await db_conn.execute(
            "SELECT email FROM email_subscriptions WHERE cron_id = ? AND status = 'active'",
            (cron_id,))
        email_rows = await cursor.fetchall()
        await db_conn.close()
        
        if email_rows:
            cron = await db.fetch_cron_product_by_id(cron_id)
            product = await db.fetch_product_by_id(cron["product_id"]) if cron else None
            product_name = product["name"] if product else f"Cron#{cron_id}"
            
            for row in email_rows:
                try:
                    await send_cron_push_email(row["email"], product_name, data.payload, cron_id)
                except Exception as e:
                    print(f"[CronPush] Email to {row['email']} failed: {e}")
            
            result["emails_sent"] = len(email_rows)
    except Exception as e:
        print(f"[CronPush] Email batch failed: {e}")
    
    return result


@router.get("/results/{subscription_id}")
async def get_results(subscription_id: int, token: str, limit: int = 20):
    try:
        return await cron_service.get_cron_results(subscription_id, token, limit)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/subscription/{sub_id}")
async def cancel_subscription(sub_id: int, user: dict = Depends(get_current_user)):
    try:
        await cron_service.cancel_subscription(user["id"], sub_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/my-subscriptions")
async def my_subscriptions(user: dict = Depends(get_current_user)):
    return await cron_service.get_my_subscriptions(user["id"])


@router.get("/my-crons")
async def my_crons(user: dict = Depends(get_current_user)):
    return await cron_service.get_my_crons(user["id"])


@router.get("/shop")
async def cron_shop(category: str = None):
    """公开Cron商店列表，无需登录"""
    import database as db
    db_conn = await db.get_db()
    try:
        if category:
            cursor = await db_conn.execute(
                "SELECT cp.*, p.name as product_name, p.description, p.icon, p.price, p.category, p.sub_category, p.tags "
                "FROM cron_products cp JOIN products p ON cp.product_id = p.id "
                "WHERE cp.status = 'active' AND p.category = ? ORDER BY cp.created_at DESC", (category,))
        else:
            cursor = await db_conn.execute(
                "SELECT cp.*, p.name as product_name, p.description, p.icon, p.price, p.category, p.sub_category, p.tags "
                "FROM cron_products cp JOIN products p ON cp.product_id = p.id "
                "WHERE cp.status = 'active' ORDER BY cp.created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db_conn.close()


@router.post("/email-subscribe/{cron_id}")
async def email_subscribe(cron_id: int, email: str = Query(..., description="订阅邮箱")):
    """公开邮箱订阅，无需登录，任何用户可用邮箱订阅Cron推送"""
    import re
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(400, "邮箱格式不正确")
    
    import database as db
    db_conn = await db.get_db()
    try:
        # 检查cron是否存在且active
        cron = await db.fetch_cron_product_by_id(cron_id)
        if not cron or cron["status"] != "active":
            raise HTTPException(404, "Cron商品不存在或已下架")
        
        # 检查是否已订阅
        cursor = await db_conn.execute(
            "SELECT id FROM email_subscriptions WHERE cron_id = ? AND email = ? AND status = 'active'",
            (cron_id, email))
        if await cursor.fetchone():
            raise HTTPException(400, "该邮箱已订阅此Cron")
        
        # 创建邮箱订阅记录
        import secrets
        verify_token = secrets.token_hex(16)
        await db_conn.execute(
            "INSERT INTO email_subscriptions (cron_id, email, verify_token, status, created_at) VALUES (?, ?, ?, 'active', datetime('now'))",
            (cron_id, email, verify_token))
        await db_conn.commit()
        
        product = await db.fetch_product_by_id(cron["product_id"])
        product_name = product["name"] if product else f"Cron#{cron_id}"
        
        return {
            "success": True,
            "message": f"邮箱 {email} 已成功订阅「{product_name}」，每天9点将自动推送",
            "cron_id": cron_id,
            "email": email
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"订阅失败: {str(e)}")
    finally:
        await db_conn.close()


@router.delete("/email-unsubscribe")
async def email_unsubscribe(email: str = Query(...), cron_id: int = Query(...)):
    """取消邮箱订阅"""
    import database as db
    db_conn = await db.get_db()
    try:
        await db_conn.execute(
            "UPDATE email_subscriptions SET status = 'cancelled' WHERE email = ? AND cron_id = ?",
            (email, cron_id))
        await db_conn.commit()
        return {"success": True, "message": "已取消订阅"}
    finally:
        await db_conn.close()
