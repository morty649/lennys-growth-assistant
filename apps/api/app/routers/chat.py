from fastapi import APIRouter

from app.chat_service import handle_chat
from app.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    return await handle_chat(payload)
