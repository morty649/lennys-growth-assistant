from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.config import get_settings
from app.database import get_session

settings = get_settings()


def default_model(provider: str) -> str:
    if provider == "anthropic":
        return settings.anthropic_model
    if provider == "groq":
        return settings.groq_model
    return settings.ollama_model


def require_session(session_id: UUID) -> dict[str, Any]:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def verify_internal(token: str | None) -> None:
    if token != settings.internal_tool_token:
        raise HTTPException(status_code=403, detail="Invalid internal tool token")
