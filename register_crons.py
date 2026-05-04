import httpx
import asyncio
import json

USER_ID = "874cb09d-74bb-4233-abe5-6e77d35bb979"

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        # Register product 174 as cron (每天9点)
        r1 = await client.post("http://localhost:8000/api/cron/register", json={
            "user_id": USER_ID,
            "product_id": 174,
            "schedule_cron": "0 9 * * *",
            "result_format": "json"
        })
        print("Cron1 register:", r1.status_code, r1.text[:400])
        
        # Register product 175 as cron (每天9点)
        r2 = await client.post("http://localhost:8000/api/cron/register", json={
            "user_id": USER_ID,
            "product_id": 175,
            "schedule_cron": "0 9 * * *",
            "result_format": "json"
        })
        print("Cron2 register:", r2.status_code, r2.text[:400])

        # List all cron products
        r3 = await client.get("http://localhost:8000/api/cron/products")
        print("Cron products:", r3.status_code, r3.text[:500])

asyncio.run(main())
