from uuid import UUID

from fastapi import APIRouter, Depends

from app.client_auth import current_user_id, enforce_chat_rate_limit

from app.chat_service import handle_chat
from app.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, user_id: UUID = Depends(current_user_id)
) -> ChatResponse:
    enforce_chat_rate_limit(user_id)
    return await handle_chat(payload, user_id)
