import httpx
import asyncio
import sqlite3

# Fix coins in DB directly
db = sqlite3.connect("/root/skillbazaar/backend/data/skillbazaar.db")
db.execute("UPDATE users SET coins = 100000 WHERE username = 'skillbazaar_official'")
db.commit()
print("Coins fixed to 100000")

# Now subscribe to cron 2
async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        r1 = await client.post("http://localhost:8000/api/v2/auth/login", json={
            "username": "skillbazaar_official",
            "password": "sbz2026official"
        })
        token = r1.json().get("token", "")
        headers = {"Authorization": f"Bearer {token}"}
        
        r3 = await client.post("http://localhost:8000/api/cron/subscribe/2?payment_method=coins", headers=headers)
        print("Subscribe cron2:", r3.status_code, r3.text[:400])
        
        # List all subscriptions
        r4 = await client.get("http://localhost:8000/api/cron/my-subscriptions", headers=headers)
        import json
        subs = r4.json()
        print(f"Total subscriptions: {len(subs)}")
        for s in subs:
            print(f"  - {s.get('product_name')}: status={s.get('status')}, api_token={s.get('api_token', '')[:20]}...")

asyncio.run(main())
db.close()
