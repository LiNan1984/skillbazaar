import httpx
import asyncio
import json

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        # Register an official account via v2 auth
        r0 = await client.post("http://localhost:8000/api/v2/auth/register", json={
            "username": "skillbazaar_official",
            "password": "sbz2026official",
            "nickname": "SkillBazaar官方"
        })
        print("Register:", r0.status_code, r0.text[:300])

        # Login
        r1 = await client.post("http://localhost:8000/api/v2/auth/login", json={
            "username": "skillbazaar_official",
            "password": "sbz2026official"
        })
        print("Login:", r1.status_code, r1.text[:300])
        login_data = r1.json()
        token = login_data.get("token", "")
        print(f"Token: {token[:30]}...")

        headers = {"Authorization": f"Bearer {token}"}

        # Register product 174 as cron
        r2 = await client.post("http://localhost:8000/api/cron/register", 
            json={"product_id": 174, "schedule_cron": "0 9 * * *", "result_format": "json"},
            headers=headers)
        print("Cron1 register:", r2.status_code, r2.text[:400])

        # Register product 175 as cron
        r3 = await client.post("http://localhost:8000/api/cron/register",
            json={"product_id": 175, "schedule_cron": "0 9 * * *", "result_format": "json"},
            headers=headers)
        print("Cron2 register:", r3.status_code, r3.text[:400])

        # List my crons
        r4 = await client.get("http://localhost:8000/api/cron/my-crons", headers=headers)
        print("My crons:", r4.status_code, r4.text[:500])

        # Subscribe to cron 1 (with email webhook for daily push)
        r5 = await client.post("http://localhost:8000/api/cron/subscribe/1?payment_method=coins", headers=headers)
        print("Subscribe cron1:", r5.status_code, r5.text[:400])

        # Subscribe to cron 2
        r6 = await client.post("http://localhost:8000/api/cron/subscribe/2?payment_method=coins", headers=headers)
        print("Subscribe cron2:", r6.status_code, r6.text[:400])

asyncio.run(main())
