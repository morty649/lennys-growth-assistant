from app.agent_client import AgentResult
from app.chat_service import _context_from_result, artifact_available


def _result(
    tool_runs: list[dict], text: str = "answer", evidence: list[dict] | None = None
) -> AgentResult:
    return AgentResult(
        text=text,
        evidence=evidence or [],
        tool_runs=tool_runs,
        requested_provider="ollama",
        requested_model="qwen3:8b",
        actual_provider="ollama",
        actual_model="qwen3:8b",
        execution_mode="direct",
        grounding_state="not_applicable",
        used_fallback=False,
        fallback_reason_code=None,
        thinking_mode="off",
        latency_ms=1,
    )


def test_artifact_action_requires_completed_ship_30_tool() -> None:
    assert not artifact_available(_result([]))
    assert not artifact_available(
        _result([{"name": "search_transcripts", "status": "complete"}])
    )
    completed = [{
        "name": "prepare_ship_30_essay",
        "status": "complete",
        "input": {"scope_guest": "Dan Hockenmaier"},
    }]
    evidence = [
        {"id": "one", "guest": "Dan Hockenmaier"},
        {"id": "two", "guest": "Dan Hockenmaier"},
    ]
    valid = (
        "# Lessons from Dan Hockenmaier\n\n"
        "## The problem\n\n**Retention matters.** "
        + "word " * 600
        + "\n\n## What the evidence shows\n\n"
        + "word " * 500
        + "\n\n## The takeaway\n\nTake the next step."
    )
    assert artifact_available(_result(completed, valid, evidence))
    mismatched = [
        {"id": "one", "guest": "Shishir Mehrotra"},
        {"id": "two", "guest": "Jessica Lachs"},
    ]
    assert not artifact_available(_result(completed, valid, mismatched))
    assert not artifact_available(_result(completed, "word " * 1_099))
    assert not artifact_available(_result(completed, "word " * 1_401))
    assert not artifact_available(
        _result([{"name": "prepare_ship_30_essay", "status": "error"}])
    )


def test_resolved_context_keeps_scope_when_follow_up_has_no_evidence() -> None:
    previous = {
        "last_intent": "transcript_research",
        "guests": ["Ada Chen Rekhi"],
        "topics": ["onboarding"],
        "prior_evidence_ids": ["ada:1"],
        "episode_ids": ["ada-chen-rekhi"],
    }

    context = _context_from_result(_result([]), "transcript_research", previous)

    assert context == previous


def test_resolved_context_is_derived_from_current_evidence() -> None:
    evidence = [
        {"id": "one", "episode_id": "ada", "guest": "Ada Chen Rekhi"},
        {"id": "two", "episode_id": "ada", "guest": "Ada Chen Rekhi"},
    ]

    context = _context_from_result(
        _result([], evidence=evidence),
        "transcript_research",
        {"topics": ["onboarding"]},
    )

    assert context["guests"] == ["Ada Chen Rekhi"]
    assert context["topics"] == ["onboarding"]
    assert context["prior_evidence_ids"] == ["one", "two"]
    assert context["episode_ids"] == ["ada"]
