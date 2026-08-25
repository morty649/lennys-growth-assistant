import math
from contextlib import contextmanager
from typing import Any

from app import retrieval
from app.indexing import hash_embedding
from app.retrieval import decompose_query, match_guest_reference


def test_hash_embedding_is_deterministic_and_normalized() -> None:
    first = hash_embedding("solve before scale product growth")
    second = hash_embedding("solve before scale product growth")

    assert first == second
    assert len(first) == 384
    assert math.isclose(sum(value * value for value in first), 1.0, rel_tol=1e-6)


def test_comparison_queries_are_decomposed() -> None:
    parts = decompose_query(
        "Compare how Aparna approaches prototypes versus how another guest approaches MVPs"
    )
    assert len(parts) == 2
    assert "Aparna" in parts[0]
    assert "MVPs" in parts[1]


def test_guest_resolution_is_catalog_driven_and_typo_tolerant() -> None:
    episodes = [
        {"id": "dan-hockenmaier", "guest": "Dan Hockenmaier"},
        {"id": "dan-shipper", "guest": "Dan Shipper"},
        {"id": "jess-lachs", "guest": "Jessica Lachs"},
    ]
    result = match_guest_reference(
        "Can you use the podcast with Don H and make it?", episodes
    )
    assert result["status"] == "resolved"
    assert result["match"]["guest"] == "Dan Hockenmaier"
    assert result["match"]["episode_ids"] == ["dan-hockenmaier"]


def test_guest_resolution_does_not_guess_between_equal_first_names() -> None:
    episodes = [
        {"id": "dan-hockenmaier", "guest": "Dan Hockenmaier"},
        {"id": "dan-shipper", "guest": "Dan Shipper"},
    ]
    result = match_guest_reference("Use the episode with Dan", episodes)
    assert result["status"] == "ambiguous"
    assert {item["guest"] for item in result["candidates"]} == {
        "Dan Hockenmaier",
        "Dan Shipper",
    }


def test_exact_catalog_name_wins_over_a_similar_initial_match() -> None:
    episodes = [
        {"id": "crystal-w", "guest": "Crystal W"},
        {"id": "christina-wodtke", "guest": "Christina Wodtke"},
    ]
    result = match_guest_reference("Use the Crystal W episode", episodes)

    assert result["status"] == "resolved"
    assert result["match"]["guest"] == "Crystal W"


def test_guest_resolution_ignores_unrelated_topic_queries() -> None:
    episodes = [{"id": "dan-hockenmaier", "guest": "Dan Hockenmaier"}]
    result = match_guest_reference("How should startups improve retention?", episodes)
    assert result["status"] == "none"


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


def test_natural_adam_fishman_paraphrase_uses_partial_term_coverage(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeConnection:
        def execute(self, sql: str, params: list[Any]) -> _Rows:
            captured.update(sql=sql, params=params)
            return _Rows([
                {
                    "id": "adam-fishman:retention",
                    "lexical_score": 0.68,
                    "lexical_coverage": 0.4,
                }
            ])

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(retrieval, "connection", fake_connection)
    query = (
        "What does Adam Fishman say about improving onboarding "
        "to reduce early retention problems?"
    )

    candidates = retrieval._lexical_candidates(
        query,
        "Adam Fishman",
        20,
        {"adam-fishman"},
    )

    assert candidates[0]["id"] == "adam-fishman:retention"
    assert captured["params"][0] == (
        "improving | onboarding | reduce | early | retention | problems"
    )
    assert query not in captured["params"]
    assert "to_tsquery('english', %s)" in captured["sql"]
    assert "ORDER BY term_coverage DESC" in captured["sql"]
    assert "search_document ILIKE" not in captured["sql"]


def test_lexical_guest_and_episode_scope_are_catalog_driven(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeConnection:
        def execute(self, sql: str, params: list[Any]) -> _Rows:
            captured.update(sql=sql, params=params)
            return _Rows([])

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(retrieval, "connection", fake_connection)
    retrieval._lexical_candidates(
        "What does Casey Winters recommend about senior growth leaders?",
        "Casey Winters",
        12,
        {"casey-winters-a", "casey-winters-b"},
    )

    assert "lower(guest) = lower(%s)" in captured["sql"]
    assert "episode_id = ANY(%s)" in captured["sql"]
    assert "Casey Winters" in captured["params"]
    assert "Casey Winters %" in captured["params"]
    assert ["casey-winters-a", "casey-winters-b"] in captured["params"]
    assert "casey" not in captured["params"][0]
    assert "winters" not in captured["params"][0]
