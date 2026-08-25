import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_v01_acceptance_set_has_required_shape_and_diversity() -> None:
    sessions = json.loads((ROOT / "evals/acceptance_sessions.json").read_text())

    assert len(sessions) == 80
    assert len({session["guest"] for session in sessions}) == 80
    assert len({session["episode_id"] for session in sessions}) == 80
    assert sum(len(session["turns"]) for session in sessions) == 440
    assert {len(session["turns"]) for session in sessions} == {5, 6}
    assert all(session["gold_evidence_ids"] for session in sessions)


def test_v02_set_has_ten_distinct_five_turn_sessions() -> None:
    sessions = json.loads((ROOT / "evals/v02_sessions.json").read_text())

    assert len(sessions) == 10
    assert len({session["guest"] for session in sessions}) == 10
    assert len({session["episode_id"] for session in sessions}) == 10
    assert sum(len(session["turns"]) for session in sessions) == 50
    assert {len(session["turns"]) for session in sessions} == {5}
    assert all(session["gold_evidence_ids"] for session in sessions)


def test_mixed_routing_acceptance_dataset_remains_a_dynamic_agent_fixture() -> None:
    sessions = json.loads((ROOT / "evals/routing_acceptance.json").read_text())

    assert len(sessions) >= 3
    assert all(len(session["turns"]) == 5 for session in sessions)
    assert all(
        turn["expected_intent"]
        in {
            "social",
            "app_help",
            "general",
            "corpus_browse",
            "transcript_research",
            "transcript_followup",
        }
        for session in sessions
        for turn in session["turns"]
    )
