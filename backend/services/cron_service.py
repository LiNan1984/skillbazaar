from __future__ import annotations

import json
import secrets
from typing import Optional

import httpx

import database as db
from services.notification_service import notify


async def register_cron_product(user_id: str, product_id: int, schedule_cron: str, result_format: str = "json") -> dict:
    product = await db.fetch_product_by_id(product_id)
    if not product:
        raise ValueError("商品不存在")
    existing = await db.fetch_cron_product(product_id)
    if existing:
        raise ValueError("该商品已注册为Cron")
    webhook_secret = f"whs_{secrets.token_hex(16)}"
    cron_id = await db.insert_cron_product(product_id, schedule_cron, webhook_secret, result_format)
    return {"id": cron_id, "webhook_secret": webhook_secret}


async def subscribe_cron(user_id: str, cron_id: int, webhook_url: Optional[str] = None, payment_method: str = "coins") -> dict:
    cron = await db.fetch_cron_product_by_id(cron_id)
    if not cron:
        raise ValueError("Cron商品不存在")
    if cron["status"] != "active":
        raise ValueError("该Cron已暂停")
    product = await db.fetch_product_by_id(cron["product_id"])
    price = product["price"] if product else 0

    if payment_method == "points":
        points_cost = price * 100
        account = await db.get_or_create_point_account(user_id)
        if account["balance"] < points_cost:
            raise ValueError(f"积分不足，需要 {points_cost} 积分")
        await db.spend_points(user_id, points_cost, "cron_subscribe", "cron", cron_id)
    else:
        user = await db.fetch_user(user_id)
        if not user or user["coins"] < price:
            raise ValueError("金币不足")
        await db.update_user_coins(user_id, -price)

    result = await db.insert_cron_subscription(cron_id, user_id, price, webhook_url)
    await db.increment_task_progress(user_id, "subscribe_cron")
    return result


async def push_cron_result(cron_id: int, secret: str, payload: str, duration_ms: int = 0) -> dict:
    cron = await db.fetch_cron_product_by_id(cron_id)
    if not cron:
        raise ValueError("Cron不存在")
    if cron["webhook_secret"] != secret:
        raise ValueError("认证失败")
    log_id = await db.insert_execution_log(cron_id, payload, "success", duration_ms)
    await db.increment_cron_execution(cron_id)
    subs = await db.fetch_active_subscriptions(cron_id)

    product = await db.fetch_product_by_id(cron["product_id"])
    product_name = product["name"] if product else f"Cron#{cron_id}"
    summary = (payload or "")[:120]
    for sub in subs:
        await notify(
            sub["subscriber_id"], "cron_result",
            f"定时任务新结果：{product_name}",
            f"您订阅的「{product_name}」有新的执行结果：{summary}",
            {"cron_id": cron_id, "log_id": log_id,
             "subscription_id": sub["id"], "product_id": cron["product_id"]},
        )

    delivery_results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for sub in subs:
            if sub.get("webhook_url"):
                try:
                    resp = await client.post(
                        sub["webhook_url"],
                        json={"cron_id": cron_id, "payload": json.loads(payload) if payload else None},
                        headers={"X-Cron-Token": sub["api_token"]},
                    )
                    del_id = await db.insert_webhook_delivery(log_id, sub["webhook_url"])
                    await db.update_webhook_delivery(del_id, "sent" if resp.status_code < 400 else "failed", resp.status_code)
                    delivery_results.append({"sub_id": sub["id"], "status": "sent"})
                except Exception:
                    delivery_results.append({"sub_id": sub["id"], "status": "failed"})
            await db.update_subscription_last_result(sub["id"])
    return {"log_id": log_id, "delivered_to": len(delivery_results), "results": delivery_results}


async def get_cron_results(subscription_id: int, api_token: str, limit: int = 20) -> list:
    sub = await db.fetch_cron_subscription(subscription_id)
    if not sub or sub["api_token"] != api_token:
        raise ValueError("无效的订阅或Token")
    return await db.fetch_subscription_logs(subscription_id, limit)


async def cancel_subscription(user_id: str, sub_id: int):
    sub = await db.fetch_cron_subscription(sub_id)
    if not sub or sub["subscriber_id"] != user_id:
        raise ValueError("无效的订阅")
    await db.cancel_cron_subscription(sub_id)


async def get_my_subscriptions(user_id: str) -> list:
    return await db.fetch_user_cron_subscriptions(user_id)


async def get_my_crons(user_id: str) -> list:
    return await db.fetch_my_crons(user_id)
