from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from app.database import (
    create_session,
    delete_session,
    list_messages,
    list_sessions,
    update_session,
)
from app.dependencies import default_model, require_session
from app.schemas import MessageView, SessionCreate, SessionUpdate, SessionView

router = APIRouter()


@router.get("/api/sessions", response_model=list[SessionView])
def sessions_list():
    return list_sessions()


@router.post("/api/sessions", response_model=SessionView, status_code=201)
def sessions_create(payload: SessionCreate):
    model = payload.model or default_model(payload.provider)
    return create_session(payload.title, payload.provider, model)


@router.patch("/api/sessions/{session_id}", response_model=SessionView)
def sessions_update(session_id: UUID, payload: SessionUpdate):
    require_session(session_id)
    updates = payload.model_dump(exclude_none=True)
    if payload.provider and not payload.model:
        updates["model"] = default_model(payload.provider)
    return update_session(session_id, updates)


@router.delete("/api/sessions/{session_id}", status_code=204)
def sessions_delete(session_id: UUID):
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@router.get("/api/sessions/{session_id}/messages", response_model=list[MessageView])
def messages_list(session_id: UUID):
    require_session(session_id)
    return list_messages(session_id)
