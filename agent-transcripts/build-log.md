# Sanitized coding-agent build log

This is a sanitized operational record of important coding-agent attempts, failures, diagnosis, and corrections. API keys, authorization headers, raw provider payloads, and sensitive local values are intentionally omitted.

## 1. Initial local model timeout

Attempt: run a real FastAPI -> Pi -> Ollama `qwen3:14b-q4_K_M` transcript question while embedding/index work was competing for local resources.

Result: the request exceeded the evaluation wait window and returned a safe provider-timeout/evidence-only path.

Correction: finish the versioned semantic index first, verify database/vector parity, and run model qualification without concurrent ingestion load.

## 2. Model searched but did not cite

Attempt: give Qwen raw retrieval-internals JSON after a model-originated transcript tool call.

Result: the model treated the tool result as diagnostics, sometimes said there was no explicit question, or produced a synthesis without valid source tokens.

Correction: format tool results as answer-oriented evidence with guest, episode, timestamp, bounded excerpt, and a copy-ready exact `[[source:...]]` token. Add one bounded citation-rewrite attempt, then downgrade to evidence-only rather than accept unsupported synthesis.

## 3. Follow-up passage was incorrectly rejected

Attempt: ask, "Which exact transcript passage supports that summary?" after a successful multi-turn Ada Chen Rekhi conversation.

Result: Pi inherited the guest and search returned the exact gold passage at rank one, but the API rejected its score because guest-constrained retrieval had a stricter threshold than global retrieval.

Correction: use one conservative evidence floor across routes and add a regression test for the observed score boundary.

## 4. Oversized evaluation

Attempt: run 80 distinct sessions and 440 real Qwen 14B generations sequentially.

Result: observed latency averaged roughly one minute per turn, projecting many hours. The run was intentionally stopped after a checkpoint rather than reported as complete.

Correction: preserve the partial file, add model/dataset-safe result identity, and replace the submission gate with 10 distinct sessions of exactly five turns. Keep the 40-case retrieval regression separate.

## 5. Qwen3 8B qualification

Attempt: switch only the answer model to `qwen3:8b`, leaving `nomic-embed-text` and the corpus index unchanged.

Result: the direct Pi gate used a model-originated transcript search, exact citations, and no-think enforcement. The five-turn gate completed every automated check with no fallback and lower total latency than the comparable 14B probe.

Decision: select Qwen3 8B for the final local configuration and retain 14B as the documented fallback if multi-session quality regresses.

## 6. Docker registry timeout

Attempt: rebuild the complete Compose stack after switching defaults.

Result: Docker Hub base-image metadata requests timed out. No project build step had failed.

Correction: start existing local images with recreated environment for qualification, retain the external failure in this log, and keep a clean source rebuild as a final release gate.
