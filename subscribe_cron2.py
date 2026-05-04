import httpx
import asyncio

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        # Login
        r1 = await client.post("http://localhost:8000/api/v2/auth/login", json={
            "username": "skillbazaar_official",
            "password": "sbz2026official"
        })
        token = r1.json().get("token", "")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Check current coins
        r2 = await client.get("http://localhost:8000/api/v2/auth/me", headers=headers)
        print("My info:", r2.text[:300])
        
        # Subscribe to cron 2 (should have 9999 coins, need 1)
        r3 = await client.post("http://localhost:8000/api/cron/subscribe/2?payment_method=coins", headers=headers)
        print("Subscribe cron2:", r3.status_code, r3.text[:400])
        
        # List my subscriptions
        r4 = await client.get("http://localhost:8000/api/cron/my-subscriptions", headers=headers)
        print("My subs:", r4.status_code, r4.text[:600])

asyncio.run(main())
