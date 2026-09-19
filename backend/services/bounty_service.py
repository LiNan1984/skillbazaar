from __future__ import annotations

from datetime import datetime

import database as db
from services.skill_vault import encrypt_content
from services.notification_service import notify


async def create_bounty(user_id: str, data: dict) -> dict:
    bounty_id = await db.insert_bounty({
        "poster_id": user_id,
        **data,
    })
    bounty = await db.fetch_bounty_by_id(bounty_id)
    return bounty


async def get_bounties(status: str = None, category: str = None,
                       keyword: str = None, page: int = 1, page_size: int = 20) -> dict:
    bounties, total = await db.fetch_bounties(
        status=status, category=category, keyword=keyword,
        page=page, page_size=page_size,
    )
    for b in bounties:
        apps = await db.fetch_bounty_applications(b["id"])
        b["application_count"] = len(apps)
    return {"total": total, "page": page, "page_size": page_size, "bounties": bounties}


async def get_bounty_detail(bounty_id: int) -> dict | None:
    bounty = await db.fetch_bounty_by_id(bounty_id)
    if not bounty:
        return None
    apps = await db.fetch_bounty_applications(bounty_id)
    deliveries = await db.fetch_bounty_deliveries(bounty_id)
    bounty["applications"] = apps
    bounty["deliveries"] = deliveries
    return bounty


async def apply_for_bounty(developer_id: str, data: dict) -> dict:
    bounty = await db.fetch_bounty_by_id(data["bounty_id"])
    if not bounty:
        raise ValueError("Bounty not found")
    if bounty["status"] != "open":
        raise ValueError("Bounty is not open for applications")
    if bounty["poster_id"] == developer_id:
        raise ValueError("Cannot apply to your own bounty")

    existing_apps = await db.fetch_bounty_applications(data["bounty_id"])
    for app in existing_apps:
        if app["developer_id"] == developer_id and app["status"] == "pending":
            raise ValueError("Already applied to this bounty")

    app_id = await db.insert_bounty_application({
        "bounty_id": data["bounty_id"],
        "developer_id": developer_id,
        "proposal": data["proposal"],
        "estimated_days": data.get("estimated_days", 7),
        "quoted_price": data["quoted_price"],
        "portfolio": data.get("portfolio", ""),
    })

    dev = await db.fetch_user(developer_id)
    await notify(
        bounty["poster_id"], "bounty_application",
        f"悬赏收到新申请：{bounty['title']}",
        f"开发者 {dev.get('nickname') if dev else developer_id} 申请了您的悬赏「{bounty['title']}」，报价 {data['quoted_price']} 金币。",
        {"bounty_id": data["bounty_id"], "application_id": app_id,
         "developer_id": developer_id},
    )
    return {"id": app_id, "status": "pending"}


async def select_developer(poster_id: str, application_id: int) -> dict:
    apps = await db.fetch_bounty_applications(0)  # Will filter below
    # Find the application
    db_conn = await db.get_db()
    try:
        cursor = await db_conn.execute(
            "SELECT * FROM bounty_applications WHERE id = ?", (application_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise ValueError("Application not found")
        app = dict(row)
    finally:
        await db_conn.close()

    bounty = await db.fetch_bounty_by_id(app["bounty_id"])
    if not bounty or bounty["poster_id"] != poster_id:
        raise ValueError("Not authorized")

    if bounty["status"] != "open":
        raise ValueError("Bounty is not open")

    # Accept selected application, reject others
    await db.update_bounty_application(application_id, "accepted")
    await db.update_bounty(app["bounty_id"], {
        "status": "in_progress",
        "selected_developer_id": app["developer_id"],
        "final_price": app["quoted_price"],
    })

    # Reject other pending applications
    all_apps = await db.fetch_bounty_applications(app["bounty_id"])
    for a in all_apps:
        if a["id"] != application_id and a["status"] == "pending":
            await db.update_bounty_application(a["id"], "rejected")

    await notify(
        app["developer_id"], "bounty_selected",
        f"您已被选中：{bounty['title']}",
        f"悬赏主已选中您承接「{bounty['title']}」，成交价 {app['quoted_price']} 金币，请尽快提交交付。",
        {"bounty_id": app["bounty_id"], "application_id": application_id},
    )

    return {"status": "in_progress", "developer_id": app["developer_id"]}


async def deliver_bounty(developer_id: str, bounty_id: int, description: str = "", content: bytes = None) -> dict:
    bounty = await db.fetch_bounty_by_id(bounty_id)
    if not bounty:
        raise ValueError("Bounty not found")
    if bounty["selected_developer_id"] != developer_id:
        raise ValueError("Not the selected developer")
    if bounty["status"] != "in_progress":
        raise ValueError("Bounty is not in progress")

    encrypted = {}
    if content:
        encrypted = encrypt_content(content)

    delivery_id = await db.insert_bounty_delivery({
        "bounty_id": bounty_id,
        "developer_id": developer_id,
        "encrypted_blob": encrypted.get("encrypted_blob"),
        "encryption_iv": encrypted.get("encryption_iv"),
        "encryption_salt": encrypted.get("encryption_salt"),
        "content_hash": encrypted.get("content_hash"),
        "description": description,
    })

    await db.update_bounty(bounty_id, {"status": "delivered"})

    dev = await db.fetch_user(developer_id)
    await notify(
        bounty["poster_id"], "bounty_delivered",
        f"悬赏有新交付：{bounty['title']}",
        f"开发者 {dev.get('nickname') if dev else developer_id} 已提交「{bounty['title']}」的交付，请及时验收。",
        {"bounty_id": bounty_id, "delivery_id": delivery_id,
         "developer_id": developer_id},
    )
    return {"id": delivery_id, "status": "delivered"}


async def review_delivery(poster_id: str, delivery_id: int, accept: bool) -> dict:
    db_conn = await db.get_db()
    try:
        cursor = await db_conn.execute(
            "SELECT * FROM bounty_deliveries WHERE id = ?", (delivery_id,)
        )
        row = await cursor.fetchone()
        delivery = dict(row) if row else None
    finally:
        await db_conn.close()

    if not delivery:
        raise ValueError("Delivery not found")

    bounty = await db.fetch_bounty_by_id(delivery["bounty_id"])
    if not bounty or bounty["poster_id"] != poster_id:
        raise ValueError("Not authorized")

    if accept:
        await db.update_bounty_delivery(delivery_id, {
            "status": "accepted",
            "reviewed_at": datetime.now().isoformat(),
        })
        await db.update_bounty(delivery["bounty_id"], {"status": "completed"})

        # Transfer payment from poster to developer
        price = bounty.get("final_price", 0)
        if price > 0:
            poster = await db.fetch_user(bounty["poster_id"])
            dev = await db.fetch_user(delivery["developer_id"])
            if poster and dev and poster.get("coins", 0) >= price:
                await db.update_user_coins(poster["id"], poster["coins"] - price)
                await db.update_user_coins(dev["id"], dev["coins"] + price)
                await db.insert_wallet_transaction({
                    "user_id": poster["id"],
                    "amount": -price,
                    "balance_after": poster["coins"] - price,
                    "type": "bounty_payment",
                    "ref_type": "bounty",
                    "ref_id": str(delivery["bounty_id"]),
                    "description": f"悬赏付款: {bounty['title']}",
                })
                await db.insert_wallet_transaction({
                    "user_id": dev["id"],
                    "amount": price,
                    "balance_after": dev["coins"] + price,
                    "type": "bounty_income",
                    "ref_type": "bounty",
                    "ref_id": str(delivery["bounty_id"]),
                    "description": f"悬赏收入: {bounty['title']}",
                })
    else:
        await db.update_bounty_delivery(delivery_id, {
            "status": "rejected",
            "reviewed_at": datetime.now().isoformat(),
        })
        await db.update_bounty(delivery["bounty_id"], {"status": "in_progress"})

    await notify(
        delivery["developer_id"],
        "bounty_accepted" if accept else "bounty_rejected",
        f"交付{'已通过验收' if accept else '被拒绝'}：{bounty['title']}",
        (f"恭喜！您对「{bounty['title']}」的交付已通过验收。"
         if accept else
         f"您对「{bounty['title']}」的交付未通过验收，请根据反馈修改后重新提交。"),
        {"bounty_id": delivery["bounty_id"], "delivery_id": delivery_id},
    )

    return {"status": "accepted" if accept else "rejected"}
