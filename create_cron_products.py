import httpx
import asyncio
import json

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        # Product 1: 每日AI Agent盈利案例推送
        p1 = {
            "name": "daily-ai-profit-cases",
            "description": "每日精选个人开发者利用AI Agent盈利的真实案例。涵盖SaaS产品、自动化服务、AI工具变现等，每天9点推送，支持邮箱订阅。",
            "category": "Cron",
            "sub_category": "每日推送",
            "price": 1,
            "original_price": 1,
            "seller_name": "SkillBazaar官方",
            "tags": json.dumps(["AI赚钱", "独立开发者", "每日推送", "邮箱订阅", "Agent盈利"]),
            "source_platform": "Hermes CronJob",
            "content_preview": "每日精选个人开发者利用AI Agent盈利的真实案例，每天9点推送到邮箱。"
        }
        r1 = await client.post("http://localhost:8000/api/products", json=p1)
        print("P1:", r1.status_code, r1.text[:500])
        
        # Product 2: GitHub Trending AI/LLM 每日精选
        p2 = {
            "name": "github-trending-ai-daily",
            "description": "GitHub Trending AI/LLM每日精选，自动追踪最新热门AI开源项目。涵盖LLM框架、Agent工具、RAG系统等，每天9点推送，支持邮箱订阅。",
            "category": "Cron",
            "sub_category": "每日推送",
            "price": 1,
            "original_price": 1,
            "seller_name": "SkillBazaar官方",
            "tags": json.dumps(["GitHub", "Trending", "AI", "LLM", "开源", "邮箱订阅"]),
            "source_platform": "Hermes CronJob",
            "content_preview": "自动追踪GitHub Trending中最热门的AI/LLM开源项目，每天9点推送到邮箱。"
        }
        r2 = await client.post("http://localhost:8000/api/products", json=p2)
        print("P2:", r2.status_code, r2.text[:500])

asyncio.run(main())
