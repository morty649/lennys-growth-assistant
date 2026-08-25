# Release Readiness Report

Date: 2026-08-26
Status: deployed candidate with unresolved acceptance checks

## Current deployment

The project now supports two real execution paths:

- **Hosted demo:** the frontend is published with Sites at <https://lennys-growth-assistant.maruthi-enugula.chatgpt.site/>. It calls the FastAPI service on Render, which persists profiles, sessions, messages, transcript evidence, and vectors in Supabase PostgreSQL with pgvector.
- **Self-contained local demo:** `docker compose up --build` starts the frontend, FastAPI API, PostgreSQL, Chroma, and Pi agent. Ollama is a documented host prerequisite reached through `host.docker.internal`; the local generation model is `qwen3:8b` and local embeddings use `nomic-embed-text`.

The hosted Groq provider uses `openai/gpt-oss-120b` as its primary model. `openai/gpt-oss-20b` is a narrow fallback and is selected only after an actual Groq HTTP 429/rate-limit response. It is not a general quality or error fallback.

Hosted access is protected by three configured profiles: `test1`, `test2`, and `lenny`. Each signed profile receives a stable identity, and conversations are persisted and isolated by that identity. Password values belong in deployment secrets and are not stored in this report or committed source.

## Corpus and retrieval

The repository contains the transcript corpus needed for the self-contained path. The recorded corpus manifest contains:

- 303 podcast episodes
- 16,469 evidence units
- 16,469 corresponding local vectors after a complete local ingestion

The assistant can route normal conversation directly to the model and route transcript research through model-originated tools. Research answers are expected to cite episode and timestamp evidence; normal conversation should not fabricate or display transcript sources. Session context is persisted so referential follow-ups can retain a dynamically resolved guest or topic without guest-specific hard-coding.

The hosted path uses the Supabase/pgvector store and the cloud-safe embedding configuration recorded by the deployment. The local path continues to exercise Ollama and the bundled corpus independently of the hosted provider.

## Latest recorded source checks

The latest completed checks on the current working tree are:

- FastAPI: 42 tests passed and the opt-in database test was skipped in the ordinary suite.
- PostgreSQL integration: 1 persistence/isolation test passed separately against the localhost database.
- Pi agent: 17 tests passed; TypeScript production build passed.
- Web: ESLint passed; production build passed.
- The current local stack reached 303 episodes, 16,469 evidence units, and matching vectors.
- Its direct canary used `qwen3:8b` with no sources. Its Adam Fishman canary returned only Adam Fishman evidence with supported grounding and no fallback.
- A previous public commit, `71a2b3b8995518c455155cc83f7b1dc729c5e802`, passed an isolated clean-clone Compose rehearsal. The current working-tree changes were made afterward, so that rehearsal is historical and must be repeated for the submitted commit.
- A local Ship 30 attempt produced only a short answer and was correctly denied an artifact. A bounded completion repair and static gate were added afterward, but the post-fix live attempt was stopped at the user's request and is not a pass.

These checks establish current component health and local direct/retrieval behavior. They do **not** establish final clean-clone reproducibility, hosted browser acceptance, Ship 30 acceptance, or evaluation completion.

## Evaluation evidence

The earlier local Qwen3 evaluation completed 10 sessions and 50 turns, but it remains historical evidence rather than the hosted release acceptance run. It passed six of seven automated gates and exceeded the deliberately strict fallback-rate threshold. Independent manual support review was not completed, so it must not be described as proof of zero unsupported claims.

The current release acceptance scope is intentionally smaller to reduce exposure to Groq rate limits:

- 5 distinct sessions
- 3 turns per session
- 15 total hosted turns
- manual review of answer correctness, guest/episode identity, timestamp support, and conversational context

The existing `evals/results/v02-cloud-groq.json` is an interrupted, pre-context-fix diagnostic. It is not release evidence and must not be presented as a passing result. A new post-fix run and its manual review remain pending.

## Browser findings that remain unresolved

The public browser regression exposed three concrete failures. Source fixes now have automated coverage, but none is marked as publicly retested:

1. **Adam Fishman follow-ups abstained despite answerable transcript context.** Dynamic lexical coverage and guest/episode scoping now pass unit and localhost checks; the matching source is not yet deployed and retested publicly.
2. **Casey Winters produced a semantically unsupported synthesis.** Claim-to-excerpt validation now rejects the reproduced mismatch in tests; the public behavior is not yet retested.
3. **Ship 30 artifact generation returned an internal error or incomplete draft.** Typed error propagation and a bounded completion gate now exist in source, but no post-fix live Ship 30 artifact has passed end to end.

Profile sign-in is deployed, but authentication alone does not make the full browser checklist pass. The final browser run still needs to verify direct chat, grounded research, referential follow-up, new-session isolation, cross-profile isolation, Ship 30 generation, Markdown download, narrow-screen layout, and absence of console errors.

## Requirements and remaining handoff gates

Implemented assignment capabilities include FastAPI, the Pi agent harness, PostgreSQL session persistence, mandatory local Ollama support, a cloud LLM provider, transcript ingestion/retrieval, timestamp citations, multi-turn conversations, the Ship 30 writing capability, beside-chat artifacts, Docker Compose, environment examples, tests, design/architecture documentation, and observable request/ingestion summaries.

The remaining release work is:

1. Commit the intended working-tree changes and repeat the clean-clone Compose rehearsal from that exact commit.
2. Deploy that exact revision and complete the public browser regression, including Adam, Casey, Ship 30 creation, workspace viewing, and Markdown download.
3. Run the 5-session/3-turn hosted evaluation and manually review all 15 saved answers against their saved excerpts.
4. Update this report with the submitted commit, deployed revision, exact evaluation artifact, and observed results.
5. Repeat the secret scan and confirm no profile password, provider key, production database credential, or signed token is committed.
6. Record and share the required 2–3 minute camera-enabled demo video. This remains a user-owned submission task and is intentionally kept outside the current engineering run.

Do not claim release completion until gates 1–5 are closed. Do not claim the hosted evaluation or Ship 30 path passed without their recorded end-to-end evidence.
