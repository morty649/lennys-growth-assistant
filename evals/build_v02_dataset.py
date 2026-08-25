from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    development = json.loads((ROOT / "development_sessions.json").read_text(encoding="utf-8"))
    sessions = []
    for index, original in enumerate(development[:10], start=1):
        session = dict(original)
        session["id"] = f"v02-{index:03d}-{original['episode_id']}"
        session["turns"] = [dict(turn) for turn in original["turns"][:5]]
        session["review_status"] = "generated_from_transcript_structure_pending_manual_review"
        sessions.append(session)

    if len(sessions) != 10:
        raise RuntimeError(f"Expected 10 sessions, found {len(sessions)}")
    if len({session["guest"] for session in sessions}) != 10:
        raise RuntimeError("v0.2 sessions must have 10 distinct guests")
    if len({session["episode_id"] for session in sessions}) != 10:
        raise RuntimeError("v0.2 sessions must have 10 distinct episodes")
    if any(len(session["turns"]) != 5 for session in sessions):
        raise RuntimeError("Every v0.2 session must contain exactly five turns")

    destination = ROOT / "v02_sessions.json"
    destination.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"sessions": len(sessions), "turns": 50, "destination": str(destination)}))


if __name__ == "__main__":
    main()
