from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.client_auth import current_user_id

from app.database import (
    create_session,
    delete_session,
    list_messages,
    list_sessions,
    update_session,
)
from app.dependencies import default_model, require_session, settings
from app.schemas import MessageView, SessionCreate, SessionUpdate, SessionView

router = APIRouter()


@router.get("/api/sessions", response_model=list[SessionView])
def sessions_list(user_id: UUID = Depends(current_user_id)):
    return list_sessions(user_id)


@router.post("/api/sessions", response_model=SessionView, status_code=201)
def sessions_create(payload: SessionCreate, user_id: UUID = Depends(current_user_id)):
    provider = payload.provider or settings.default_provider
    model = payload.model or default_model(provider)
    return create_session(payload.title, provider, model, user_id)


@router.patch("/api/sessions/{session_id}", response_model=SessionView)
def sessions_update(
    session_id: UUID, payload: SessionUpdate, user_id: UUID = Depends(current_user_id)
):
    require_session(session_id, user_id)
    updates = payload.model_dump(exclude_none=True)
    if payload.provider and not payload.model:
        updates["model"] = default_model(payload.provider)
    return update_session(session_id, updates, user_id)


@router.delete("/api/sessions/{session_id}", status_code=204)
def sessions_delete(session_id: UUID, user_id: UUID = Depends(current_user_id)):
    if not delete_session(session_id, user_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@router.get("/api/sessions/{session_id}/messages", response_model=list[MessageView])
def messages_list(session_id: UUID, user_id: UUID = Depends(current_user_id)):
    require_session(session_id, user_id)
    return list_messages(session_id)
