from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.agent_client import AgentResult, run_adaptive_agent
from app.database import add_message, add_tool_run, list_messages, update_session
from app.dependencies import default_model, require_session, settings
from app.grounding import render_citations
from app.schemas import ChatRequest, ChatResponse, MessageView, SourceView, ToolRunView


async def handle_chat(payload: ChatRequest, user_id: UUID | None = None) -> ChatResponse:
    session = require_session(payload.session_id, user_id)
    provider = payload.provider or session["provider"]
    if provider == "groq" and not settings.enable_groq:
        raise HTTPException(status_code=409, detail="Groq is not enabled for this deployment")
    model = payload.model or session["model"] or default_model(provider)
    request_id = str(uuid4())
    add_message(payload.session_id, "user", payload.message, metadata={"request_id": request_id})
    history = list_messages(payload.session_id, limit=40)
    result = await run_adaptive_agent(
        payload.message,
        history,
        provider,
        model,
        request_id=request_id,
    )
    intent = _intent_from_result(result)
    update_session(
        payload.session_id,
        {"resolved_context": _context_from_result(result, intent)},
        user_id or UUID("00000000-0000-4000-8000-000000000001"),
    )
    assistant = _persist_assistant(
        payload,
        session,
        intent,
        request_id,
        result,
        user_id or UUID("00000000-0000-4000-8000-000000000001"),
    )
    return ChatResponse(
        message=MessageView(**assistant),
        sources=[SourceView(**source) for source in result.evidence],
        tool_runs=[ToolRunView(**tool_run) for tool_run in result.tool_runs],
        grounded=result.grounding_state == "supported" and bool(result.evidence),
        used_fallback=result.used_fallback,
        grounding_state=result.grounding_state,
        execution_mode=result.execution_mode,
        requested_provider=result.requested_provider,
        requested_model=result.requested_model,
        actual_provider=result.actual_provider,
        actual_model=result.actual_model,
        fallback_reason_code=result.fallback_reason_code,
        latency_ms=result.latency_ms,
    )


def _intent_from_result(result: AgentResult) -> str:
    if any(run["name"] == "prepare_ship_30_essay" for run in result.tool_runs):
        return "ship30"
    if any(run["name"] == "search_transcripts" for run in result.tool_runs):
        return "transcript_research"
    if any(run["name"] == "browse_corpus_catalog" for run in result.tool_runs):
        return "corpus_browse"
    return "general"


def _context_from_result(result: AgentResult, intent: str) -> dict[str, Any]:
    return {
        "last_intent": intent,
        "prior_evidence_ids": [item["id"] for item in result.evidence[:12]],
        "episode_ids": list(dict.fromkeys(item["episode_id"] for item in result.evidence[:8])),
    }


def artifact_available(result: AgentResult) -> bool:
    prepared = next(
        (
            run
            for run in result.tool_runs
            if run["name"] == "prepare_ship_30_essay" and run["status"] == "complete"
        ),
        None,
    )
    if not prepared or len(result.evidence) < 2:
        return False
    scope_guest = str(prepared.get("input", {}).get("scope_guest") or "").casefold()
    scope_matches = not scope_guest or all(
        str(source.get("guest") or "").casefold() == scope_guest
        for source in result.evidence
    )
    word_count = len(re.findall(r"\b[\w’'-]+\b", result.text))
    return scope_matches and 1_100 <= word_count <= 1_400


def _persist_assistant(
    payload: ChatRequest,
    session: dict[str, Any],
    intent: str,
    request_id: str,
    result: AgentResult,
    user_id: UUID,
) -> dict[str, Any]:
    rendered = render_citations(result.text, result.evidence) if result.evidence else result.text
    can_create_artifact = artifact_available(result)
    assistant = add_message(
        payload.session_id,
        "assistant",
        rendered,
        status="abstained" if result.execution_mode == "abstention" else "complete",
        provider=result.actual_provider,
        model=result.actual_model,
        metadata={
            "sources": result.evidence,
            "grounded": result.grounding_state == "supported" and bool(result.evidence),
            "grounding_state": result.grounding_state,
            "used_fallback": result.used_fallback,
            "execution_mode": result.execution_mode,
            "requested_provider": result.requested_provider,
            "requested_model": result.requested_model,
            "actual_provider": result.actual_provider,
            "actual_model": result.actual_model,
            "fallback_reason_code": result.fallback_reason_code,
            "thinking_mode": result.thinking_mode,
            "latency_ms": result.latency_ms,
            "request_id": request_id,
            "intent": intent,
            "artifact_available": can_create_artifact,
            "artifact_format": "markdown" if can_create_artifact else None,
        },
    )
    if session["title"] == "New investigation":
        title = re.sub(r"\s+", " ", payload.message).strip()[:72]
        update_session(payload.session_id, {"title": title}, user_id)
    for tool_run in result.tool_runs:
        add_tool_run(
            payload.session_id,
            assistant["id"],
            tool_run["name"],
            tool_run["status"],
            tool_run["duration_ms"],
            tool_run["input"],
            origin=tool_run.get("origin", "model"),
            error_code=tool_run.get("error_code"),
        )
    return assistant
