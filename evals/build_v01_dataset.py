from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.corpus import build_evidence_units, load_topic_map, parse_episode

ROOT = Path(__file__).resolve().parent


def _turns(guest: str, question: str, six_turns: bool) -> list[dict[str, object]]:
    seed = question.strip().rstrip("?")
    turns: list[dict[str, object]] = [
        {
            "prompt": f'In the conversation with {guest}, how do they answer: "{seed}?"',
            "expected_route": "guest",
            "requires_context": False,
        },
        {
            "prompt": "What concrete example do they use to make that point?",
            "expected_route": "guest",
            "requires_context": True,
        },
        {
            "prompt": "What caveat or qualification should I preserve?",
            "expected_route": "guest",
            "requires_context": True,
        },
        {
            "prompt": "Turn that into one practical lesson, but do not generalize beyond what they said.",
            "expected_route": "guest",
            "requires_context": True,
        },
        {
            "prompt": "Which exact transcript passage supports that summary?",
            "expected_route": "guest",
            "requires_context": True,
        },
    ]
    if six_turns:
        turns.append(
            {
                "prompt": "Give me a two-sentence final recap with the guest and source still explicit.",
                "expected_route": "guest",
                "requires_context": True,
            }
        )
    return turns


def build_sessions() -> list[dict[str, object]]:
    settings = get_settings()
    topic_map = load_topic_map(settings.topics_dir)
    candidates: list[dict[str, object]] = []
    seen_guests: set[str] = set()
    for path in sorted(settings.episodes_dir.glob("*/transcript.md")):
        episode = parse_episode(path)
        if episode.guest.casefold() in seen_guests:
            continue
        units = build_evidence_units(episode, topic_map.get(episode.id, []))
        unit = next(
            (
                item
                for item in units
                if len(item.question.split()) >= 7
                and 120 <= len(item.excerpt.split()) <= 520
                and item.speaker.casefold() != "unknown"
            ),
            None,
        )
        if unit is None:
            continue
        seen_guests.add(episode.guest.casefold())
        candidates.append(
            {
                "id": f"v01-{len(candidates) + 1:03d}-{episode.id}",
                "guest": episode.guest,
                "episode_id": episode.id,
                "title": episode.title,
                "topics": unit.topics[:3],
                "gold_evidence_ids": [unit.id],
                "gold_timestamp": unit.timestamp_label,
                "seed_question": unit.question,
                "turns": _turns(episode.guest, unit.question, len(candidates) % 2 == 1),
                "review_status": "generated_from_transcript_structure",
            }
        )
    if len(candidates) < 96:
        raise RuntimeError(f"Only {len(candidates)} unique-guest sessions could be generated")
    return candidates


def main() -> None:
    sessions = build_sessions()
    development = sessions[:16]
    acceptance = sessions[16:96]
    (ROOT / "development_sessions.json").write_text(
        json.dumps(development, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "acceptance_sessions.json").write_text(
        json.dumps(acceptance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    turns = sum(len(session["turns"]) for session in acceptance)
    if len(acceptance) != 80 or turns != 440:
        raise RuntimeError(f"Acceptance shape mismatch: {len(acceptance)} sessions, {turns} turns")
    print(json.dumps({"development_sessions": 16, "acceptance_sessions": 80, "acceptance_turns": turns}))


if __name__ == "__main__":
    main()
