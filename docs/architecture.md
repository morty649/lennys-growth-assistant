# Architecture and grounding design

## Runtime flow

```text
localhost browser
  -> FastAPI session/intent/context boundary
  -> Pi agent harness
     -> explicitly selected Qwen/Ollama, Groq GPT-OSS, or Claude backend
     -> catalog entity resolution
     -> search_transcripts / open_source_context / prepare_ship_30_essay
  -> FastAPI evidence sufficiency + source-token validation
  -> persisted answer, truthful execution metadata, and optional artifact
```

## Component boundaries

| Component | Responsibility |
|---|---|
| Web | Sessions, chat, provider selection, sources, and artifact workspace |
| FastAPI | Validation, authentication, persistence, retrieval, grounding, artifacts, and health |
| Pi agent | Model conversation, semantic routing, and bounded tool calls |
| PostgreSQL | Users, sessions, messages, evidence metadata, tool runs, and artifacts |
| Chroma/pgvector | Rebuildable dense retrieval index |
| Ollama/Anthropic/Groq | Explicitly selected inference provider |

## Agent routing

Every turn reaches the same adaptive Pi harness with recent session history and a compact map of `indexes/by-topic` and `episodes/by-guest`. A small model pass selects the required knowledge scope (direct, catalog, transcript, Ship 30 information, or Ship 30 generation) from meaning and conversation; the answer pass receives only the tools appropriate to that scope. Guest resolution is a deterministic metadata boundary: it scores normalized names, initials, typos, and episode slugs from the live catalog, asks with exact catalog candidates when ambiguous, and passes canonical episode IDs into retrieval when resolved. FastAPI derives the execution mode from tool calls that actually occurred, exposes transcript sources only after search, and enforces citation, scope, relevance, and artifact gates. No guest-specific alias table or keyword intent router is used.

## Model toggle

For Ollama, Pi injects `reasoning_effort: none` into every request and verifies its transport hook ran. The selected local tag is `qwen3:8b`; the previously qualified 14B tag is a fallback only if the smaller model fails the release gates. Claude and Groq use the same Pi tool registry when explicitly configured. The cloud profile selects Groq `openai/gpt-oss-120b`; the local profile keeps Groq disabled by default.

## Ingestion flow

Source Markdown remains authoritative. The parser reads frontmatter, named/anonymous timestamp blocks, carried speakers, and interview-region transitions. It excludes advertisements and outro material, then groups original turns into question-aware conversational evidence units. No LLM rewrites the transcript.

Each episode stores `evidence_build_version`; each Chroma collection stores its embedding version. Startup validates episode version/count and DB/vector parity. A changed parser or embedding backend triggers rebuild rather than silently reusing incompatible vectors. Full ingestion also removes records for deleted source episodes.

## Retrieval flow

- `episodes/<guest>/transcript.md` supplies canonical guest identity.
- `index/*.md` supplies a soft topic-to-episode prior, not passage-level truth.
- PostgreSQL full-text search and the selected dense backend produce independent candidates. Local uses Ollama `nomic-embed-text` in Chroma; the quota-free cloud default uses deterministic feature-hash vectors in pgvector, with Supabase `gte-small` available as an optional upgrade.
- Query decomposition, reciprocal-rank fusion, query/guest/topic overlap reranking, episode diversity, and comparison coverage produce the evidence set.
- Stable evidence IDs resolve exact sources and expanded local context.
- Resolved guest episode IDs are hard filters in lexical retrieval and post-fusion ranking, so unrelated guests cannot enter a guest-scoped evidence set.
- When a guest-only query has no substantive topic, the canonical episode title becomes the dynamic retrieval hint instead of searching the person's name or using hardcoded topic text.

Missing or weak evidence yields abstention. Sufficient evidence without valid `[[source:ID]]` tokens discards the synthesis and returns clearly labelled evidence-only passages. Guest constraints narrow the candidate set but do not impose a stricter sufficiency threshold than global search.

## Sessions and artifacts

PostgreSQL is the source of truth for isolated sessions, ordered history, resolved context, requested/actual execution metadata, tool origins, messages, and artifacts. Artifact creation binds an exact assistant message and copies its exact evidence bundle. Ship 30 creation requires a completed preparation tool, at least two passages from the resolved guest scope, and 1,100–1,400 words. Writing quality remains the responsibility of the versioned skill rather than a growing set of server heuristics. Rendered Markdown and HTML are allowlist-sanitized, wrapped in a restrictive CSP, and displayed in an iframe with an empty sandbox.

## Database schema

```text
users 1 ── * chat_sessions 1 ── * messages
                    │  ├────── * artifacts (optional source_message_id)
                    │  └────── * tool_runs (optional message_id)
episodes 1 ── * evidence_units
    └──── * episode_topics
ingestion_runs records rebuild lifecycle and failures
```

`chat_sessions.user_id` is required and every public session lookup is scoped by it. Messages preserve ordered conversation plus provider/model and JSON metadata. Artifacts copy their exact source evidence so later retrieval changes cannot rewrite provenance. Evidence units contain stable IDs, guest/speaker, timestamps, excerpt, full-text vector, topics, and—under the cloud migration—a 384-dimensional pgvector embedding. The executable schema is in `apps/api/app/database.py`; the cloud migration is in `supabase/migrations/`.

## API endpoints

- `POST /api/client` and `POST /api/login`: issue anonymous or fixed-profile tokens.
- `GET|POST /api/sessions`, `PATCH|DELETE /api/sessions/{id}`: user-scoped session lifecycle.
- `GET /api/sessions/{id}/messages`: ordered session history.
- `POST /api/chat`: validated adaptive turn; returns answer, sources, tool summaries, grounding, actual provider/model, fallback reason, and latency.
- `GET|POST /api/sessions/{id}/artifacts`: exact-message artifact lifecycle.
- `GET /api/sources/{id}`: resolve a stable evidence unit.
- `GET /health/live`, `GET /health/ready`, `GET /api/config`: process, dependency, corpus, model, and UI configuration state.
- `GET /api/ingest/status`, `GET /api/ingest/manifest`, `POST /api/ingest`: ingestion visibility and controlled refresh.
- `/internal/tools/*`: token-protected catalog, entity resolution, transcript search, and source expansion used only by Pi.

Pydantic request/response models reject invalid inputs. Expected authentication, validation, provider, timeout, rate-limit, and agent failures use stable status/code responses; untrusted upstream bodies are not passed to the client.

## Security

- All published Compose ports bind to `127.0.0.1`.
- Transcript text is evidence, never instructions.
- Pi can call only four declared application tools; the Ship 30 tool loads its versioned skill file and accepts only evidence IDs returned during the same run. Tool calls and history are bounded.
- Internal tool routes require the local shared token.
- Providers never switch implicitly. The Groq cloud profile may retry a genuine HTTP 429 on `openai/gpt-oss-20b`; the response records the actual model and `provider_rate_limited` reason. Configuration, timeout, and tool failures do not trigger this fallback.
- Raw provider bodies, headers, secrets, prompts, transcript passages, and complete histories are not stored as errors.
- UI provider state reflects configured model readiness rather than process reachability alone.

FastAPI emits redacted JSON request summaries and ingestion lifecycle events. Pi emits JSON run summaries containing only request ID, provider/model, tool names, fallback code, and duration. Full structured tool records and requested/actual execution metadata are also stored in PostgreSQL; prompts, answers, and secrets are excluded from operational logs.

## Local deployment topology

Docker Compose starts PostgreSQL, Chroma, FastAPI, Pi, and the web application. Ollama runs on the evaluator's host and is reached from the Pi/API containers through `host.docker.internal`. All published application/data ports bind to loopback.

The repository contains its own `episodes/` and `index/` directories. Compose mounts only those directories read-only under `/corpus`, so a fresh clone has no parent-repository dependency.

Anthropic is an outbound, explicitly selected inference dependency rather than a hosted-application requirement. Local PostgreSQL remains the local-profile default.

## Cloud deployment topology

```text
public Sites frontend
  -> same-origin backend proxy
  -> one Render Docker web service
     -> FastAPI public port
     -> Pi agent on loopback
     -> Groq GPT-OSS 120B
     -> Supabase PostgreSQL + pgvector
     -> local feature-hash embedding (default) or Supabase gte-small Edge Function (optional)
```

The cloud profile is selected only by environment. Supabase migrations are versioned under `supabase/migrations`; the embedding function lives under `supabase/functions/embed`; and the combined backend image lives under `deploy/cloud`. Signed profile tokens scope every session query to one stable profile identity. Passwords and signing secrets are configured only in Render. The frontend never receives the Groq key, database password, service-role key, internal tool token, profile passwords, or token-signing secret.
