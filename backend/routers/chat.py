from fastapi import APIRouter
from models import ChatRequest, ChatResponse
import services.chat_service as chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    response = await chat_service.handle_chat(body.user_id, body.message)
    return response
