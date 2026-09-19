from fastapi import APIRouter, Depends, Query

from models import ChatRequest, ChatResponse
import services.chat_service as chat_service
from routers.user_v2 import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, user: dict = Depends(get_current_user)):
    # Identity always comes from the Bearer token; body.user_id is deprecated.
    response = await chat_service.handle_chat(
        user_id=user["id"],
        message=body.message,
        card=body.card,
    )
    return response


@router.get("/history")
async def get_history(
    limit: int = Query(20, ge=1, le=20, description="返回条数上限(1-20)"),
    user: dict = Depends(get_current_user),
):
    return await chat_service.get_history(user["id"], limit)


@router.delete("/history")
async def clear_history(user: dict = Depends(get_current_user)):
    return await chat_service.clear_history(user["id"])
