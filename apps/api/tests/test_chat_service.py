from app.agent_client import AgentResult
from app.chat_service import artifact_available


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
