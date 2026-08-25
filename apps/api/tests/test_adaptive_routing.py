from __future__ import annotations

import httpx
import pytest

from app import agent_client


def _payload(text: str, tool_runs: list[dict] | None = None) -> dict:
    return {
        "text": text,
        "toolRuns": tool_runs or [],
        "provider": "ollama",
        "model": "qwen3:8b",
        "thinkingMode": "off",
    }


@pytest.mark.asyncio
async def test_agent_error_preserves_safe_upstream_code(monkeypatch) -> None:
    async def fake_post(*_args, **_kwargs):
        request = httpx.Request("POST", "http://agent/run")
        return httpx.Response(
            502,
            request=request,
            json={"code": "provider_timeout", "detail": "The provider timed out"},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(agent_client.AgentServiceError) as error:
        await agent_client._call_agent("question", [], "groq", "model", "request", {})

    assert error.value.code == "provider_timeout"
    assert error.value.status_code == 504
    assert error.value.detail == "The provider timed out"


@pytest.mark.asyncio
async def test_no_tool_is_a_direct_answer_without_sources(monkeypatch) -> None:
    async def fake_call(*_args, **_kwargs):
        return _payload("WhatsApp is a messaging application.")

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent("What is WhatsApp?", [], "ollama", "qwen3:8b")

    assert result.execution_mode == "direct"
    assert result.evidence == []
    assert result.tool_runs == []


@pytest.mark.asyncio
async def test_catalog_tool_produces_catalog_mode_without_transcript_sources(monkeypatch) -> None:
    async def fake_call(*_args, **_kwargs):
        return _payload(
            "The corpus contains 303 guest episodes and 87 topic indexes.",
            [{
                "name": "browse_corpus_catalog",
                "status": "complete",
                "durationMs": 4,
                "args": {"query": ""},
                "origin": "model",
                "result": {"tree": {"episodes/by-guest": {"count": 303}}},
            }],
        )

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent(
        "What podcasts are available?", [], "ollama", "qwen3:8b"
    )

    assert result.execution_mode == "catalog"
    assert result.evidence == []
    assert [run["name"] for run in result.tool_runs] == ["browse_corpus_catalog"]


@pytest.mark.asyncio
async def test_search_tool_requires_and_exposes_valid_cited_evidence(monkeypatch) -> None:
    source = {
        "id": "dan:945:abc",
        "episode_id": "dan",
        "guest": "Dan Hockenmaier",
        "title": "Growth models",
        "speaker": "Dan Hockenmaier",
        "start_seconds": 945,
        "end_seconds": 960,
        "timestamp": "00:15:45-00:16:00",
        "youtube_url": "https://example.com?t=945",
        "excerpt": "Retention compounds through the rest of the growth model.",
        "score": 0.74,
        "route": "topic",
    }

    async def fake_call(*_args, **_kwargs):
        return _payload(
            "Dan says retention compounds through the wider growth model [[source:dan:945:abc]].",
            [{
                "name": "search_transcripts",
                "status": "complete",
                "durationMs": 8,
                "args": {"query": "retention growth model"},
                "origin": "model",
                "result": {"route": "topic", "evidence": [source]},
            }],
        )

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent(
        "Why can retention matter more than acquisition?", [], "ollama", "qwen3:8b"
    )

    assert result.execution_mode == "model"
    assert result.grounding_state == "supported"
    assert result.evidence == [source]


@pytest.mark.asyncio
async def test_search_tool_rejects_semantically_unsupported_cited_synthesis(monkeypatch) -> None:
    source = {
        "id": "casey:120:abc",
        "episode_id": "casey",
        "guest": "Casey Winters",
        "title": "Founder intuition",
        "speaker": "Casey Winters",
        "start_seconds": 120,
        "end_seconds": 140,
        "timestamp": "00:02:00-00:02:20",
        "youtube_url": "https://example.com?t=120",
        "excerpt": (
            "Founders should directly hire senior people until those leaders show they "
            "understand the business, and then the founder can back away."
        ),
        "score": 0.74,
        "route": "guest",
    }

    async def fake_call(*_args, **_kwargs):
        return _payload(
            "Casey says leaders should document strategic tradeoffs and explain their "
            "reasoning before delegating decisions. [[source:casey:120:abc]]",
            [{
                "name": "search_transcripts",
                "status": "complete",
                "durationMs": 8,
                "args": {"query": "senior leader delegation"},
                "origin": "model",
                "result": {"route": "guest", "evidence": [source]},
            }],
        )

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent(
        "What should a founder do before backing away?", [], "ollama", "qwen3:8b"
    )

    assert result.execution_mode == "evidence_only"
    assert result.grounding_state == "supported"
    assert result.used_fallback
    assert result.fallback_reason_code == "unsupported_claims"
    assert "document strategic tradeoffs" not in result.text


@pytest.mark.asyncio
async def test_ambiguous_guest_returns_catalog_clarification_without_sources(monkeypatch) -> None:
    async def fake_call(*_args, **_kwargs):
        return _payload(
            "ignored model text",
            [{
                "name": "search_transcripts",
                "status": "complete",
                "durationMs": 2,
                "args": {"query": "Use the episode with Dan"},
                "origin": "model",
                "result": {
                    "needs_clarification": True,
                    "clarification": "Which guest do you mean: Dan Hockenmaier or Dan Shipper?",
                    "evidence": [],
                },
            }],
        )

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent(
        "Use the episode with Dan", [], "ollama", "qwen3:8b"
    )

    assert result.text == "Which guest do you mean: Dan Hockenmaier or Dan Shipper?"
    assert result.execution_mode == "direct"
    assert result.evidence == []
    assert result.fallback_reason_code == "entity_clarification"


@pytest.mark.asyncio
async def test_ship30_preserves_cited_evidence_and_uncited_assistant_synthesis(monkeypatch) -> None:
    source = {
        "id": "dan:945:abc",
        "episode_id": "dan",
        "guest": "Dan Hockenmaier",
        "title": "Growth models",
        "speaker": "Dan Hockenmaier",
        "start_seconds": 945,
        "end_seconds": 960,
        "timestamp": "00:15:45-00:16:00",
        "youtube_url": "https://example.com?t=945",
        "excerpt": "Retention compounds through the wider growth model.",
        "score": 0.74,
        "route": "guest",
    }
    essay = (
        "Dan connects retention to the wider growth model [[source:dan:945:abc]].\n\n"
        "## What to try next\n\n"
        "Treat this as an experiment: map the model with your team, choose one uncertain "
        "relationship, and decide what evidence would change your current belief."
    )

    async def fake_call(*_args, **_kwargs):
        return _payload(
            essay,
            [
                {
                    "name": "search_transcripts",
                    "status": "complete",
                    "durationMs": 8,
                    "args": {"query": "growth model"},
                    "origin": "model",
                    "result": {"route": "guest", "evidence": [source]},
                },
                {
                    "name": "prepare_ship_30_essay",
                    "status": "complete",
                    "durationMs": 1,
                    "args": {"scope_guest": "Dan Hockenmaier"},
                    "origin": "model",
                    "result": {"target_words": 1250},
                },
            ],
        )

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent(
        "Write a Ship 30 essay about Dan's growth model", [], "ollama", "qwen3:8b"
    )

    assert result.text == essay
    assert "Treat this as an experiment" in result.text
    assert result.grounding_state == "supported"


@pytest.mark.asyncio
async def test_ship30_rejects_unsupported_factual_claim_but_not_takeaways(monkeypatch) -> None:
    source = {
        "id": "dan:945:abc",
        "episode_id": "dan",
        "guest": "Dan Hockenmaier",
        "title": "Growth models",
        "speaker": "Dan Hockenmaier",
        "start_seconds": 945,
        "end_seconds": 960,
        "timestamp": "00:15:45-00:16:00",
        "youtube_url": "https://example.com?t=945",
        "excerpt": "Retention compounds through the wider growth model.",
        "score": 0.74,
        "route": "guest",
    }
    essay = (
        "Dan recommends replacing acquisition teams with community moderators and "
        "abandoning paid channels. [[source:dan:945:abc]]\n\n"
        "## What to try next\n\nTreat this as an experiment with your team."
    )

    async def fake_call(*_args, **_kwargs):
        return _payload(
            essay,
            [
                {
                    "name": "search_transcripts",
                    "status": "complete",
                    "durationMs": 8,
                    "args": {"query": "growth model"},
                    "origin": "model",
                    "result": {"route": "guest", "evidence": [source]},
                },
                {
                    "name": "prepare_ship_30_essay",
                    "status": "complete",
                    "durationMs": 1,
                    "args": {"scope_guest": "Dan Hockenmaier"},
                    "origin": "model",
                    "result": {"target_words": 1250},
                },
            ],
        )

    monkeypatch.setattr(agent_client, "_call_agent", fake_call)
    result = await agent_client.run_adaptive_agent(
        "Write a Ship 30 essay about Dan's growth model", [], "ollama", "qwen3:8b"
    )

    assert result.execution_mode == "evidence_only"
    assert result.grounding_state == "unverified"
    assert result.fallback_reason_code == "unsupported_claims"
    assert "community moderators" not in result.text
