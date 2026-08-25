from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
API_URL = os.getenv("EVAL_API_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("INTERNAL_TOOL_TOKEN", "local-dev-tool-token-change-me")


def main() -> None:
    cases = json.loads((ROOT / "questions.json").read_text())
    results: list[dict] = []
    with httpx.Client(base_url=API_URL, timeout=30, trust_env=False) as client:
        for case in cases:
            response = client.post(
                "/internal/tools/search",
                headers={"X-Internal-Token": TOKEN},
                json={"query": case["retrieval_query"], "limit": 8},
            )
            response.raise_for_status()
            payload = response.json()
            episode_ids = [item["episode_id"] for item in payload["evidence"]]
            expected = set(case["expected_episode_ids"])
            expected_route = case.get("expected_route", payload["route"])
            route_correct = (
                payload["route"] in {"guest", "guest+topic", "multi-guest"}
                if expected_route == "guest"
                else payload["route"] == expected_route
            )
            first_rank = next(
                (
                    index
                    for index, episode_id in enumerate(episode_ids, 1)
                    if episode_id in expected
                ),
                None,
            )
            results.append(
                {
                    "id": case["id"],
                    "recall_at_5": bool(expected & set(episode_ids[:5])),
                    "recall_at_8": bool(expected & set(episode_ids[:8])),
                    "reciprocal_rank_at_8": 1 / first_rank if first_rank else 0,
                    "route_correct": route_correct,
                    "actual_route": payload["route"],
                    "top_episode_ids": episode_ids,
                }
            )

    count = len(results)
    summary = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "cases": count,
        "recall_at_5": sum(item["recall_at_5"] for item in results) / count,
        "recall_at_8": sum(item["recall_at_8"] for item in results) / count,
        "mrr_at_8": sum(item["reciprocal_rank_at_8"] for item in results) / count,
        "route_accuracy": sum(item["route_correct"] for item in results) / count,
    }
    output = {"summary": summary, "results": results}
    destination = ROOT / "results" / "latest.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if summary["recall_at_8"] < 0.85:
        raise SystemExit("Recall@8 is below the 0.85 MVP gate")


if __name__ == "__main__":
    main()
