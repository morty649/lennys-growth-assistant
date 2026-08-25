from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from app.config import get_settings
from app.grounding import (
    SOURCE_TOKEN,
    claims_have_citations,
    clean_citations,
    collect_evidence,
    evidence_is_sufficient,
    fallback_answer,
    only_cited_evidence,
    retain_cited_claims,
)


@dataclass(slots=True)
class AgentResult:
    text: str
    evidence: list[dict[str, Any]]
    tool_runs: list[dict[str, Any]]
    requested_provider: str
    requested_model: str
    actual_provider: str | None
    actual_model: str | None
    execution_mode: str
    grounding_state: str
    used_fallback: bool
    fallback_reason_code: str | None
    thinking_mode: str | None
    latency_ms: float


async def run_adaptive_agent(
    query: str,
    history: list[dict[str, Any]],
    provider: str,
    model: str,
    *,
    request_id: str | None = None,
    resolved_context: dict[str, Any] | None = None,
) -> AgentResult:
    """Let Pi choose direct, catalog, or transcript research; enforce the chosen path here."""
    started = perf_counter()
    payload = await _call_agent(
        query,
        history,
        provider,
        model,
        request_id,
        resolved_context or {},
    )
    raw_runs = payload.get("toolRuns") or []
    public_runs = public_tool_runs(raw_runs)
    searched = any(run.get("name") == "search_transcripts" for run in raw_runs)
    browsed_catalog = any(run.get("name") == "browse_corpus_catalog" for run in raw_runs)

    clarification = next(
        (
            str(result["clarification"])
            for run in raw_runs
            if isinstance((result := run.get("result")), dict)
            and result.get("needs_clarification")
            and result.get("clarification")
        ),
        None,
    )
    if clarification:
        fallback_reason = payload.get("fallbackReasonCode")
        return AgentResult(
            text=clarification,
            evidence=[],
            tool_runs=public_runs,
            requested_provider=provider,
            requested_model=model,
            actual_provider=payload.get("provider") or provider,
            actual_model=payload.get("model") or model,
            execution_mode="direct",
            grounding_state="not_applicable",
            used_fallback=bool(fallback_reason),
            fallback_reason_code=fallback_reason or "entity_clarification",
            thinking_mode=payload.get("thinkingMode"),
            latency_ms=(perf_counter() - started) * 1000,
        )

    if searched:
        return _grounded_result(payload, raw_runs, public_runs, provider, model, started)

    text = SOURCE_TOKEN.sub("", str(payload.get("text") or "")).strip()
    if not text:
        raise RuntimeError("The local model returned an empty answer")
    fallback_reason = payload.get("fallbackReasonCode")
    return AgentResult(
        text=text,
        evidence=[],
        tool_runs=public_runs,
        requested_provider=provider,
        requested_model=model,
        actual_provider=payload.get("provider") or provider,
        actual_model=payload.get("model") or model,
        execution_mode="catalog" if browsed_catalog else "direct",
        grounding_state="not_applicable",
        used_fallback=bool(fallback_reason),
        fallback_reason_code=fallback_reason,
        thinking_mode=payload.get("thinkingMode"),
        latency_ms=(perf_counter() - started) * 1000,
    )


async def _call_agent(
    query: str,
    history: list[dict[str, Any]],
    provider: str,
    model: str,
    request_id: str | None,
    resolved_context: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    prior_history = (
        history[:-1]
        if history
        and history[-1].get("role") == "user"
        and str(history[-1].get("content") or "").strip() == query.strip()
        else history
    )
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds, trust_env=False
    ) as client:
        response = await client.post(
            f"{settings.agent_url.rstrip('/')}/run",
            json={
                "query": query,
                "history": [
                    {"role": item["role"], "content": item["content"]}
                    for item in prior_history[-12:]
                    if item["role"] in {"user", "assistant"}
                ],
                "provider": provider,
                "model": model,
                "mode": "adaptive",
                "requestId": request_id,
                "resolvedContext": {
                    "guests": resolved_context.get("guests") or [],
                    "topics": resolved_context.get("topics") or [],
                    "prior_evidence_ids": resolved_context.get("prior_evidence_ids") or [],
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("The Pi agent returned an invalid response")
    return payload


def _grounded_result(
    payload: dict[str, Any],
    raw_runs: list[dict[str, Any]],
    public_runs: list[dict[str, Any]],
    provider: str,
    model: str,
    started: float,
) -> AgentResult:
    evidence = collect_evidence(raw_runs)
    text, valid_citations = clean_citations(str(payload.get("text") or ""), evidence)
    ship30_prepared = any(
        run.get("name") == "prepare_ship_30_essay"
        and run.get("status") == "complete"
        for run in raw_runs
    )
    if not evidence_is_sufficient(evidence):
        return _result(
            fallback_answer([], "insufficient_evidence"),
            [],
            public_runs,
            provider,
            model,
            payload,
            "abstention",
            "insufficient",
            started,
            fallback_reason="insufficient_evidence",
        )
    if ship30_prepared:
        if not valid_citations:
            return _result(
                fallback_answer(evidence[:3], "missing_valid_citations"),
                evidence[:3],
                public_runs,
                provider,
                model,
                payload,
                "evidence_only",
                "unverified",
                started,
                used_fallback=True,
                fallback_reason="missing_valid_citations",
            )
        return _result(
            text,
            only_cited_evidence(evidence, valid_citations),
            public_runs,
            provider,
            model,
            payload,
            "model",
            "supported",
            started,
        )
    if valid_citations and not claims_have_citations(text):
        text = retain_cited_claims(text)
        valid_citations = {match.group("id") for match in SOURCE_TOKEN.finditer(text)}
    if not valid_citations or not claims_have_citations(text):
        reason = "missing_valid_citations" if not valid_citations else "incomplete_citation_coverage"
        fallback_evidence = evidence[:3]
        return _result(
            fallback_answer(fallback_evidence, reason),
            fallback_evidence,
            public_runs,
            provider,
            model,
            payload,
            "evidence_only",
            "supported",
            started,
            used_fallback=True,
            fallback_reason=reason,
            expose_model=False,
        )
    return _result(
        text,
        only_cited_evidence(evidence, valid_citations),
        public_runs,
        provider,
        model,
        payload,
        "model",
        "supported",
        started,
    )


def _result(
    text: str,
    evidence: list[dict[str, Any]],
    tool_runs: list[dict[str, Any]],
    provider: str,
    model: str,
    payload: dict[str, Any],
    execution_mode: str,
    grounding_state: str,
    started: float,
    *,
    used_fallback: bool = False,
    fallback_reason: str | None = None,
    expose_model: bool = True,
) -> AgentResult:
    provider_fallback_reason = payload.get("fallbackReasonCode")
    return AgentResult(
        text=text,
        evidence=evidence,
        tool_runs=tool_runs,
        requested_provider=provider,
        requested_model=model,
        actual_provider=(payload.get("provider") or provider) if expose_model else None,
        actual_model=(payload.get("model") or model) if expose_model else None,
        execution_mode=execution_mode,
        grounding_state=grounding_state,
        used_fallback=used_fallback or bool(provider_fallback_reason),
        fallback_reason_code=provider_fallback_reason or fallback_reason,
        thinking_mode=payload.get("thinkingMode"),
        latency_ms=(perf_counter() - started) * 1000,
    )


def public_tool_runs(tool_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": run.get("name", "unknown"),
            "status": run.get("status", "complete"),
            "duration_ms": float(run.get("durationMs") or 0.0),
            "input": run.get("args") or {},
            "origin": run.get("origin") or "model",
            "error_code": "tool_execution_failed" if run.get("status") == "error" else None,
        }
        for run in tool_runs
    ]
