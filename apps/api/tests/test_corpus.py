from collections import Counter
from pathlib import Path

from app.corpus import build_evidence_units, parse_episode

CORPUS_ROOT = Path(__file__).resolve().parents[3]


def test_aparna_transcript_is_structurally_parsed_without_rewriting() -> None:
    episode = parse_episode(CORPUS_ROOT / "episodes/aparna-chennapragada/transcript.md")
    regions = Counter(turn.region for turn in episode.turns)
    units = build_evidence_units(episode, ["artificial intelligence", "product management"])

    assert episode.guest == "Aparna Chennapragada"
    assert regions["interview"] > 100
    assert regions["advertisement"] > 0
    assert 40 <= len(units) <= 100
    assert max(len(unit.excerpt.split()) for unit in units) < 700
    assert all("this episode is brought to you by" not in unit.excerpt.casefold() for unit in units)
    assert any("stand-up comedy" in unit.excerpt for unit in units)


def test_evidence_units_keep_speaker_and_timestamp_context() -> None:
    episode = parse_episode(CORPUS_ROOT / "episodes/aparna-chennapragada/transcript.md")
    units = build_evidence_units(episode, [])

    first = units[0]
    assert first.id.startswith("aparna-chennapragada:")
    assert first.timestamp_label.count(":") == 4
    assert "Lenny Rachitsky [" in first.excerpt
    assert "Aparna Chennapragada [" in first.excerpt


def test_two_component_timestamps_are_supported_without_normalizing_source() -> None:
    episode = parse_episode(CORPUS_ROOT / "episodes/gibson-biddle/transcript.md")
    units = build_evidence_units(episode, [])

    assert len(episode.turns) > 100
    assert len(units) >= 20
    assert episode.turns[0].timestamp == "00:04"
    assert episode.turns[0].seconds == 4
