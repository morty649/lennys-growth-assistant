import math

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


def test_guest_resolution_ignores_unrelated_topic_queries() -> None:
    episodes = [{"id": "dan-hockenmaier", "guest": "Dan Hockenmaier"}]
    result = match_guest_reference("How should startups improve retention?", episodes)
    assert result["status"] == "none"
