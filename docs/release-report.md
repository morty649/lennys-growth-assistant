# v0.2 Release Report

Date: 2026-08-25  
Boundary: localhost only; nothing was pushed, published, uploaded, or provisioned remotely.

## Outcome

The complete browser -> FastAPI -> PostgreSQL/Chroma -> Pi -> Ollama Qwen3 8B path is operational. The corpus manifest records 303 episodes and 16,469 evidence units, with 16,469 matching vectors. The default local model is `qwen3:8b`; `nomic-embed-text` remains the embedding model; Ollama thinking is forced off at transport level.

Anthropic is implemented behind the same Pi harness and explicitly selectable only when `ANTHROPIC_API_KEY` is configured. No key was present during this release, so live Anthropic inference is intentionally reported as unverified. Missing-key behavior returns a safe `provider_not_configured` response and leaves Ollama usable.

## Evaluation evidence

| Run | Scope | Result |
|---|---:|---|
| Retrieval regression | 40 curated cases | Recall@5 1.00, Recall@8 1.00, MRR@8 0.971, route accuracy 1.00 |
| Qwen3 8B qualification | 1 session / 5 turns | All automated gates passed; p50 50.9 s, p95 60.2 s |
| Qwen3 8B v0.2 | 10 sessions / 50 turns | Complete; 6 of 7 automated gates passed |

The frozen 50-turn run is `evals/results/v02-qwen3-8b-e2e.json`. Its exact identity is bound to run ID `v02-qwen3-8b-e2e`, provider `ollama`, model `qwen3:8b`, and dataset SHA-256 `a114240d9442d41b5479854cdecb40a7c62c52f7d86e6e68fa81c9db0f81ad60`.

Final observed metrics:

- 10/10 sessions completed and 50/50 turns persisted.
- Recall@5 0.96; Recall@8 0.96; MRR@8 0.96.
- Route accuracy 0.96; model-originated tool-call rate 1.00; context retention 0.96.
- Citation presence 1.00 on accepted supported answers; supported rate 0.96.
- Fallback rate 0.16, above the deliberately strict 0.10 gate.
- Latency p50 49.8 s; p95 84.2 s; elapsed time 45.7 minutes.

The run is therefore complete but not labelled a pass. Eight supported turns used the server's evidence-only safety fallback: six for missing valid citation tokens and two for incomplete sentence-level citation coverage. Two ambiguous follow-ups abstained rather than fabricate support. All retrieval, routing, tool-use, context, and citation-presence gates passed except fallback rate. The accepted-answer manual support review remains pending, so the project does not claim zero unsupported accepted claims from independent human review.

The running agent container used an older image during that frozen run because Docker Hub metadata requests stalled. The checked-in source already selects the newest assistant response after a citation-repair prompt. The current compiled bundle was copied into and restarted inside the localhost agent container for runtime verification. A reproducible clean image rebuild remains necessary when Docker Hub is reachable.

## Verification completed

- FastAPI: 18 tests passed; Ruff passed.
- Pi agent: 5 tests passed; TypeScript production build passed.
- Web: ESLint passed; Vinext production build passed.
- Production dependency audits: zero vulnerabilities reported for web and agent.
- Scoped credential-pattern scan: zero matching files; secret values were never printed.
- Browser check: app reached `localhost app · ready`, displayed `qwen3:8b`, showed Anthropic as unavailable, opened timestamped transcript evidence in the side workspace, and produced no console errors.
- Responsive fix: horizontal overflow is suppressed at document level for narrow layouts.

## Remaining handoff gates

1. Add an Anthropic key locally and save one five-turn canary if live cloud parity must be demonstrated.
2. Re-run `docker compose up -d --build` when Docker Hub is reachable; the attempt in this release stalled on base-image metadata.
3. Perform and record independent manual support review of all 50 accepted/abstained responses.
4. Create a candidate commit, then run the clean-clone rehearsal from that exact commit. This cannot be honestly completed while the application remains untracked and commits are outside the current instruction.
5. Record the required camera-enabled demo video and publish the repository/video only after explicit authorization.

These are release/handoff limitations, not hidden successes. Local implementation and source verification are complete; public submission work is not.
