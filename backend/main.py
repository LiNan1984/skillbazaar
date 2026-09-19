from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database
from routers import products, users, transactions, chat
from routers.sync import router as sync_router
from routers.skills import router as skills_router
from routers.user_v2 import router as user_v2_router
from routers.bounties import router as bounties_router
from routers.cron import router as cron_router
from routers.activities import router as activities_router
from routers.agents import router as agents_router
from routers.agents_v4 import router as agents_v4_router
from routers.sandbox import router as sandbox_router
from routers.discovery import router as discovery_router
from routers.profiles import router as profiles_router
from routers.versions import router as versions_router
from routers.analytics import router as analytics_router
from routers.analytics_v4 import router as analytics_v4_router
from routers.payments import router as payments_router
from routers.search_v4 import router as search_v4_router
from routers.bundles_v4 import router as bundles_v4_router
from routers.wishlist_v4 import router as wishlist_v4_router
from routers.recommendations_v4 import router as recommendations_v4_router
from routers.affiliate_v4 import router as affiliate_v4_router
from routers.semantic_search_v4 import router as semantic_search_v4_router
from routers.pricing_v4 import router as pricing_v4_router
from routers.traffic_boost_v4 import router as traffic_boost_v4_router
from routers.subscription_v4 import router as subscription_v4_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    # Initialize subscription tables
    await database.create_subscription_table()
    await database.create_subscription_events_table()
    await database.add_subscription_columns_to_products()
    yield


app = FastAPI(
    title="SkillBazaar API",
    description="AI Agent/Skill/Cron Marketplace Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(users.router)
app.include_router(transactions.router)
app.include_router(chat.router)
app.include_router(sync_router)
app.include_router(skills_router)
app.include_router(user_v2_router)
app.include_router(bounties_router)
app.include_router(cron_router)
app.include_router(activities_router)
app.include_router(agents_router)
app.include_router(agents_v4_router)
app.include_router(sandbox_router)
app.include_router(discovery_router)
app.include_router(profiles_router)
app.include_router(versions_router)
app.include_router(analytics_router)
app.include_router(analytics_v4_router)
app.include_router(payments_router)
app.include_router(search_v4_router)
app.include_router(bundles_v4_router)
app.include_router(wishlist_v4_router)
app.include_router(recommendations_v4_router)
app.include_router(affiliate_v4_router)
app.include_router(semantic_search_v4_router)
app.include_router(pricing_v4_router)
app.include_router(traffic_boost_v4_router)
app.include_router(subscription_v4_router)


@app.get("/")
async def root():
    return {
        "name": "SkillBazaar API",
        "version": "1.0.0",
        "description": "AI Agent/Skill/Cron Marketplace",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
