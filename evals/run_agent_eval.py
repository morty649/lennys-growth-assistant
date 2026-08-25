from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent
API_URL = os.getenv("EVAL_API_URL", "http://127.0.0.1:8000")


def _load(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _checkpoint(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _default_model(provider: str) -> str:
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    if provider == "groq":
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    return os.getenv("OLLAMA_MODEL", "qwen3:8b")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real multi-turn sessions through POST /api/chat")
    parser.add_argument(
        "--set",
        choices=("development", "acceptance", "release", "v02"),
        default="release",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--turn-limit", type=int)
    parser.add_argument("--provider", choices=("ollama", "anthropic", "groq"), default="ollama")
    parser.add_argument("--model")
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    model = args.model or _default_model(args.provider)
    dataset_name = "v02" if args.set == "release" else args.set
    dataset_path = ROOT / f"{dataset_name}_sessions.json"
    dataset = _load(dataset_path)
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be at least 1")
        dataset = dataset[: args.limit]
    if args.turn_limit is not None:
        if args.turn_limit < 1:
            raise SystemExit("--turn-limit must be at least 1")
        dataset = [{**case, "turns": case["turns"][: args.turn_limit]} for case in dataset]
    run_id = args.run_id or f"{args.set}-{args.provider}-{_slug(model)}"
    destination = ROOT / "results" / f"{_slug(run_id)}.json"
    identity = {
        "run_id": run_id,
        "dataset": args.set,
        "dataset_sha256": _checksum(dataset_path),
        "provider": args.provider,
        "model": model,
        "session_limit": args.limit,
        "turn_limit": args.turn_limit,
    }
    output: dict[str, Any] = {"identity": identity, "run": {}, "sessions": []}
    if args.resume and destination.exists():
        output = json.loads(destination.read_text(encoding="utf-8"))
        if output.get("identity") != identity:
            raise SystemExit("Refusing to resume: run identity does not match provider/model/dataset")
    existing_by_case = {item["case_id"]: item for item in output["sessions"]}
    started = perf_counter()

    with httpx.Client(base_url=API_URL, timeout=300, trust_env=False) as client:
        for case in dataset:
            session_result = existing_by_case.get(case["id"])
            if session_result and len(session_result["turns"]) == len(case["turns"]):
                continue
            eval_username = os.getenv("EVAL_USERNAME")
            eval_password = os.getenv("EVAL_PASSWORD")
            client_token = (
                client.post(
                    "/api/login",
                    json={"username": eval_username, "password": eval_password},
                )
                if eval_username and eval_password
                else client.post("/api/client")
            )
            client_token.raise_for_status()
            token = str(client_token.json().get("token") or "")
            headers = {"Authorization": f"Bearer {token}"} if token != "local" else {}
            # Anonymous cloud sessions belong to the token that created them.
            # Tokens are deliberately never checkpointed, so an interrupted
            # case restarts cleanly instead of persisting an identity secret.
            if session_result is not None:
                output["sessions"].remove(session_result)
                existing_by_case.pop(case["id"], None)
                session_result = None
            if session_result is None:
                created = client.post(
                    "/api/sessions",
                    json={
                        "title": f"eval:{run_id}:{case['id']}",
                        "provider": args.provider,
                        "model": model,
                    },
                    headers=headers,
                )
                created.raise_for_status()
                session_result = {
                    "case_id": case["id"],
                    "session_id": created.json()["id"],
                    "guest": case["guest"],
                    "turns": [],
                }
                output["sessions"].append(session_result)
                existing_by_case[case["id"]] = session_result
                _checkpoint(destination, output)
            session_id = session_result["session_id"]
            turn_results = session_result["turns"]
            completed_turns = len(turn_results)
            for turn_number, turn in enumerate(case["turns"][completed_turns:], start=completed_turns + 1):
                response = client.post(
                    "/api/chat",
                    json={
                        "session_id": session_id,
                        "message": turn["prompt"],
                        "provider": args.provider,
                        "model": model,
                    },
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                sources = payload.get("sources") or []
                evidence_ids = [source["id"] for source in sources]
                episode_ids = [source["episode_id"] for source in sources]
                expected_episode = case["episode_id"]
                gold_evidence = set(case.get("gold_evidence_ids") or [])
                tool_runs = payload.get("tool_runs") or []
                source_routes = list(dict.fromkeys(source.get("route") for source in sources))
                expected_route = turn.get("expected_route")
                route_correct = (
                    any(route in {"guest", "guest+topic", "multi-guest"} for route in source_routes)
                    if expected_route == "guest"
                    else expected_route in source_routes
                )
                answer_content = str((payload.get("message") or {}).get("content") or "")
                first_rank = next(
                    (index for index, episode_id in enumerate(episode_ids, 1) if episode_id == expected_episode),
                    None,
                )
                turn_results.append(
                    {
                        "turn": turn_number,
                        "prompt": turn["prompt"],
                        "answer": answer_content,
                        "evidence": [
                            {
                                "id": source.get("id"),
                                "episode_id": source.get("episode_id"),
                                "guest": source.get("guest"),
                                "title": source.get("title"),
                                "timestamp": source.get("timestamp"),
                                "excerpt": source.get("excerpt"),
                                "route": source.get("route"),
                                "score": source.get("score"),
                            }
                            for source in sources
                        ],
                        "manual_review": {
                            "status": "pending",
                            "answer_supported": None,
                            "context_correct": None,
                            "notes": "",
                        },
                        "expected_episode_id": expected_episode,
                        "gold_evidence_ids": sorted(gold_evidence),
                        "top_evidence_ids": evidence_ids,
                        "gold_recall_at_5": bool(gold_evidence & set(evidence_ids[:5])),
                        "gold_recall_at_8": bool(gold_evidence & set(evidence_ids[:8])),
                        "top_episode_ids": episode_ids,
                        "recall_at_5": expected_episode in episode_ids[:5],
                        "recall_at_8": expected_episode in episode_ids[:8],
                        "reciprocal_rank_at_8": 1 / first_rank if first_rank and first_rank <= 8 else 0,
                        "source_routes": source_routes,
                        "route_correct": route_correct,
                        "model_tool_call": any(
                            run.get("name") == "search_transcripts" and run.get("origin") == "model"
                            for run in tool_runs
                        ),
                        "context_retained": expected_episode in episode_ids if turn.get("requires_context") else True,
                        "grounding_state": payload.get("grounding_state"),
                        "citation_present": bool(sources) and any(
                            source.get("youtube_url") in answer_content for source in sources
                        ),
                        "used_fallback": bool(payload.get("used_fallback")),
                        "execution_mode": payload.get("execution_mode"),
                        "requested_provider": payload.get("requested_provider"),
                        "actual_provider": payload.get("actual_provider"),
                        "fallback_reason_code": payload.get("fallback_reason_code"),
                        "latency_ms": payload.get("latency_ms"),
                    }
                )
                _checkpoint(destination, output)

    turns = [turn for session in output["sessions"] for turn in session["turns"]]
    denominator = len(turns) or 1
    citation_turns = [turn for turn in turns if turn["grounding_state"] == "supported"]
    citation_denominator = len(citation_turns) or 1
    latencies = [float(turn.get("latency_ms") or 0.0) for turn in turns]
    output["run"] = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "dataset": args.set,
        "provider": args.provider,
        "model": model,
        "run_id": run_id,
        "dataset_sha256": identity["dataset_sha256"],
        "sessions": len(output["sessions"]),
        "turns": len(turns),
        "elapsed_seconds": perf_counter() - started,
        "recall_at_5": sum(turn["recall_at_5"] for turn in turns) / denominator,
        "recall_at_8": sum(turn["recall_at_8"] for turn in turns) / denominator,
        "mrr_at_8": sum(turn["reciprocal_rank_at_8"] for turn in turns) / denominator,
        "route_accuracy": sum(turn["route_correct"] for turn in turns) / denominator,
        "model_tool_call_rate": sum(turn["model_tool_call"] for turn in turns) / denominator,
        "context_retention_rate": sum(turn["context_retained"] for turn in turns) / denominator,
        "citation_presence_rate": sum(turn["citation_present"] for turn in citation_turns)
        / citation_denominator,
        "supported_rate": sum(turn["grounding_state"] == "supported" for turn in turns) / denominator,
        "fallback_rate": sum(
            turn["used_fallback"] or turn["execution_mode"] == "evidence_only" for turn in turns
        )
        / denominator,
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_ms": sorted(latencies)[max(0, round(0.95 * len(latencies)) - 1)],
    }
    expected_turns = sum(len(case["turns"]) for case in dataset)
    complete_run = len(output["sessions"]) == len(dataset) and len(turns) == expected_turns
    gates = {
        "recall_at_5": output["run"]["recall_at_5"] >= 0.80,
        "recall_at_8": output["run"]["recall_at_8"] >= 0.90,
        "route_accuracy": output["run"]["route_accuracy"] >= 0.90,
        "model_tool_call_rate": output["run"]["model_tool_call_rate"] >= 0.90,
        "context_retention_rate": output["run"]["context_retention_rate"] >= 0.90,
        "citation_presence_rate": output["run"]["citation_presence_rate"] >= 1.00,
        "fallback_rate": output["run"]["fallback_rate"] <= 0.10,
    }
    output["run"]["complete"] = complete_run
    output["run"]["gates"] = gates
    output["run"]["automated_passed"] = complete_run and all(gates.values())
    output["run"]["manual_support_review"] = "pending"
    output["run"]["passed"] = False
    _checkpoint(destination, output)
    print(json.dumps(output["run"], indent=2))
    if complete_run and not output["run"]["automated_passed"]:
        raise SystemExit("One or more end-to-end evaluation gates failed")


if __name__ == "__main__":
    main()
