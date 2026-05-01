from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncRequest(BaseModel):
    sources: Optional[list[str]] = None  # None = all sources


class SyncResponse(BaseModel):
    status: str
    message: str
    sources: list[str] = []


@router.post("/start", response_model=SyncResponse)
async def start_sync(request: SyncRequest, background_tasks: BackgroundTasks):
    """触发后台数据同步"""
    from crawlers.sync_service import run_sync

    sources = request.sources or ["gate", "bitmart", "agentskillshub", "agensi"]
    background_tasks.add_task(run_sync, sources)

    return SyncResponse(
        status="started",
        message=f"Sync started for: {', '.join(sources)}",
        sources=sources,
    )


@router.get("/status")
async def sync_status():
    """获取数据源状态"""
    import database
    products, total = await database.fetch_products(page_size=1)

    from collections import Counter
    all_products, _ = await database.fetch_products(page_size=500)
    sources = Counter(p.get("source_platform", "") for p in all_products)

    return {
        "total_products": total,
        "sources": {s: c for s, c in sources.most_common()},
        "available_crawlers": ["gate", "bitmart", "agentskillshub", "agensi"],
    }


@router.post("/reload-seeds")
async def reload_seeds(background_tasks: BackgroundTasks):
    """从种子文件重新加载数据到数据库"""
    from crawlers.sync_service import SyncService

    async def _reload():
        service = SyncService()
        count = await service.load_seeds_to_db()
        print(f"[Sync] Reloaded {count} items")

    background_tasks.add_task(_reload)
    return {"status": "started", "message": "Seed reload started in background"}
