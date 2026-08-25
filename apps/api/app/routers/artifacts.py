from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.client_auth import current_user_id

from app.artifacts import render_artifact
from app.database import (
    create_artifact_record,
    get_message,
    list_artifacts,
    list_messages,
)
from app.dependencies import require_session
from app.retrieval import get_source
from app.schemas import ArtifactCreate, ArtifactView, SourceView

router = APIRouter()


@router.get("/api/sources/{source_id:path}", response_model=SourceView)
def source_get(source_id: str):
    source = get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/api/sessions/{session_id}/artifacts", response_model=list[ArtifactView])
def artifacts_list(session_id: UUID, user_id: UUID = Depends(current_user_id)):
    require_session(session_id, user_id)
    return list_artifacts(session_id)


@router.post("/api/sessions/{session_id}/artifacts", response_model=ArtifactView, status_code=201)
def artifacts_create(
    session_id: UUID, payload: ArtifactCreate, user_id: UUID = Depends(current_user_id)
):
    require_session(session_id, user_id)
    source_content, source_message_id, source_evidence, ship30_requested = _artifact_source(
        session_id, payload
    )
    rendered = render_artifact(payload.format, source_content, payload.title)
    word_count = len(re.findall(r"\b\w+\b", source_content))
    if ship30_requested and not 1_100 <= word_count <= 1_400:
        raise HTTPException(
            status_code=422,
            detail="Ship 30 artifact must contain 1,100–1,400 grounded words",
        )
    validation = {
        "source_message_bound": source_message_id is not None,
        "source_count": len(source_evidence),
        "sanitized": True,
        "word_count": word_count,
        "ship30_requested": ship30_requested,
        "word_range_valid": not ship30_requested or 1_100 <= word_count <= 1_400,
    }
    return create_artifact_record(
        session_id,
        source_message_id,
        payload.format,
        payload.title,
        source_content,
        rendered,
        source_evidence,
        validation,
    )


def _artifact_source(
    session_id: UUID, payload: ArtifactCreate
) -> tuple[str, UUID | None, list[dict[str, Any]], bool]:
    source_content = payload.content
    source_message_id = payload.source_message_id
    source_evidence: list[dict[str, Any]] = []
    ship30_requested = False
    if source_message_id is not None:
        selected = get_message(session_id, source_message_id)
        if not selected or selected["role"] != "assistant":
            raise HTTPException(status_code=400, detail="Source must be an assistant message in this session")
        source_content = source_content if source_content is not None else selected["content"]
        source_evidence = list((selected.get("metadata") or {}).get("sources") or [])
        session_messages = list_messages(session_id)
        selected_index = next(
            (index for index, message in enumerate(session_messages) if message["id"] == source_message_id),
            -1,
        )
        if selected_index > 0:
            prior = session_messages[selected_index - 1]
            ship30_requested = bool(
                prior["role"] == "user"
                and re.search(
                    r"\b(?:ship\s*30|growth brief|1[,.]?100|1[,.]?400)\b",
                    prior["content"],
                    re.I,
                )
            )
    elif source_content is None:
        candidates = [message for message in list_messages(session_id) if message["role"] == "assistant"]
        if not candidates:
            raise HTTPException(status_code=400, detail="No assistant answer is available")
        latest = candidates[-1]
        source_content = latest["content"]
        source_message_id = latest["id"]
        source_evidence = list((latest.get("metadata") or {}).get("sources") or [])
    return source_content or "", source_message_id, source_evidence, ship30_requested
