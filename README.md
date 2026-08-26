# Lenny's Growth Assistant

A conversational research agent over Lenny's Podcast transcripts. FastAPI owns sessions, retrieval, citations, and artifacts; Pi owns the model/tool loop. The local profile uses Qwen on Ollama. The cloud profile uses Groq GPT-OSS 120B, Supabase PostgreSQL, and pgvector through the same tools and grounding boundary.

## Architecture overview

```text
Web UI -> FastAPI -> Pi agent -> selected Ollama, Anthropic, or Groq model
              |          |
              |          -> catalog, transcript search, source, and Ship 30 tools
              -> PostgreSQL sessions/artifacts + Chroma or pgvector retrieval
```

The downloaded application is self-contained and local-first. The separately hosted demo uses the same API and agent boundaries with Supabase and Groq. See [architecture.md](docs/architecture.md) for schemas, endpoints, routing, security, and deployment topology.

## Capabilities

- Independent PostgreSQL sessions with bounded multi-turn context. One adaptive Pi agent decides from meaning and recent conversation whether to answer directly, inspect the corpus catalog, or search transcript evidence; there is no keyword intent router.
- Structural transcript parsing that preserves original wording and speaker/timestamp boundaries while excluding sponsor/outro regions.
- Versioned hybrid retrieval: PostgreSQL full text plus local `nomic-embed-text` vectors in Chroma, reciprocal-rank fusion, query decomposition, guest/topic routes, comparison coverage, and evidence thresholds.
- Pi tools: `browse_corpus_catalog`, `search_transcripts`, `open_source_context`, and the grounded `prepare_ship_30_essay` skill tool.
- Guest references are resolved dynamically from the episode catalog before retrieval. Confident matches hard-scope search to canonical episode IDs; ambiguous names return catalog candidates without transcript search.
- Ship 30 artifacts fail closed unless the preparation tool completed, at least two scoped evidence passages were cited, and the draft contains 1,100–1,400 words.
- Exact local model `qwen3:8b`; every Pi/Ollama request adds `reasoning_effort: none`, and the run fails if the transport hook was not applied. The proven 14B model remains a documented fallback.
- Validated source tokens, explicit abstention, truthful requested/actual provider metadata, typed safe failures, and no silent provider switching.
- Physical Intelligence-inspired UI with Claude-like contextual workspace behavior: answer-bound Sources, inline artifacts, Preview/Code/Sources tabs, expand/close controls, mobile session drawer, and mobile full-screen workspace.
- Exact source-message artifact provenance, sanitized HTML, a sandboxed iframe, and a restrictive preview CSP.
- A finishable release set of 10 distinct guests/episodes with exactly five real chat turns each, plus the separate 40-case retrieval regression.

The localhost deployment remains the reproducible evaluator path. A separate cloud profile can publish the same product without changing the local Docker Compose topology.

## Repository and corpus

The repository is self-contained: `episodes/` and `index/` live at its root and are mounted read-only into the API container.

## Prerequisites

- Docker Desktop
- Ollama running on the host
- Enough disk space for the repository corpus, containers, `qwen3:8b`, and `nomic-embed-text`
- Optional Anthropic or Groq API key when testing those providers locally

## Installation

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
cp .env.example .env   # only if .env does not already exist
make up
```

Open [http://localhost:3000](http://localhost:3000). All published application and data ports bind to `127.0.0.1`.

## Environment variables

Copy `.env.example` to `.env`. Important settings are:

| Variable | Purpose |
|---|---|
| `DEFAULT_PROVIDER` | Initial session provider; defaults to `ollama` |
| `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` | Local answer and embedding models |
| `LOCAL_MODEL_THINKING` | Must remain `off` for the Qwen local path |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Enables Claude in the localhost provider selector |
| `GROQ_API_KEY`, `GROQ_MODEL`, `ENABLE_GROQ` | Enables Groq in the localhost provider selector |
| `DATABASE_URL` | PostgreSQL connection used by FastAPI |
| `VECTOR_BACKEND` | `chroma` locally or `pgvector` in the hosted profile |
| `AUTO_INGEST`, `CORPUS_ROOT` | Corpus loading behavior and mounted data location |
| `AUTH_MODE` | `local` for localhost or `profiles` for the protected demo |
| `INTERNAL_TOOL_TOKEN` | Protects Pi's internal retrieval endpoints |

Safe defaults and the complete list are documented in `.env.example`; hosted-only settings are in `.env.cloud.example`. Never commit `.env`.

## Local and cloud model setup

- **Local Ollama:** pull `qwen3:8b` and `nomic-embed-text`; no inference API key is required.
- **Claude on localhost:** set `ANTHROPIC_API_KEY` and optionally `ANTHROPIC_MODEL`, then restart the API and agent services. Claude uses the same Pi tools and local PostgreSQL/retrieval services.
- **Groq on localhost:** set `ENABLE_GROQ=true` and `GROQ_API_KEY`, then restart the API and agent services.
- **Hosted demo:** configured independently with Groq on Render and PostgreSQL/pgvector on Supabase. Hosted credentials do not configure or replace the evaluator's localhost providers.

## Hosted deployment

The cloud profile is intentionally additive:

- The frontend deploys independently and proxies same-origin `/api/backend/*` requests to the configured backend URL.
- One Docker web service runs FastAPI and Pi internally; only FastAPI is public.
- Supabase PostgreSQL stores sessions, messages, transcript evidence, artifacts, and 384-dimensional `pgvector` embeddings.
- The free cloud profile uses deterministic local feature-hash embeddings in pgvector, avoiding external embedding quotas; the included Supabase `gte-small` Edge Function remains an optional upgrade.
- Groq `openai/gpt-oss-120b` is the explicit default model and calls the same Pi tools.
- A genuine Groq HTTP 429 retries once on `openai/gpt-oss-20b`; responses expose the actual model and fallback reason. Other failures are not silently retried on a different model.
- Three environment-configured demo profiles use signed tokens and isolated PostgreSQL session ownership; passwords never enter the repository. Chat is rate-limited and ingestion requires the private internal token.
- Redacted JSON logs cover API requests, ingestion lifecycle, model/model-fallback metadata, tool names, and latency without storing prompts or secrets.

Cloud configuration is documented in `.env.cloud.example`, `render.yaml`, `deploy/cloud/`, and `supabase/`. Secrets belong in Supabase/Render/Sites settings, never Git.

For the private public demo, set `PROFILE_TEST1_PASSWORD`,
`PROFILE_TEST2_PASSWORD`, and `PROFILE_LENNY_PASSWORD` in Render. Keep
`AUTH_MODE=profiles` and use a unique 32+ character
`ANONYMOUS_TOKEN_SECRET` to sign profile sessions.

Readiness and ingestion:

```bash
curl --noproxy '*' http://127.0.0.1:8000/health/ready
curl --noproxy '*' http://127.0.0.1:8000/api/ingest/status
curl --noproxy '*' http://127.0.0.1:8000/api/ingest/manifest
```

The first run builds the versioned semantic index and can take several minutes. Do not evaluate until the manifest reports matching evidence-unit and vector counts.

## Run commands

```bash
make up       # build and run localhost
make logs     # follow API, agent, and web logs
make ingest   # explicitly rebuild the transcript index
make down     # stop the stack without deleting volumes
```

## Tests

```bash
make test
make build
make eval
make eval-release
```

The release evaluation checkpoints after every turn. Resume safety is bound to the dataset checksum, provider, and exact model. Evaluation is separate from the fast test/build commands:

```bash
cd apps/api
uv run python ../../evals/run_agent_eval.py --set release --provider ollama --model qwen3:8b --resume
```

The dataset is mechanically grounded in actual transcript Q&A units and frozen for repeatability. Its `review_status` records that origin. Automated success remains separate from manual support review.

Run the same release suite against the public Groq deployment with:

```bash
cd apps/api
EVAL_API_URL=https://lennys-growth-api.onrender.com \
  EVAL_USERNAME=test1 EVAL_PASSWORD='<configured password>' \
  uv run python ../../evals/run_agent_eval.py --set release --provider groq \
  --model openai/gpt-oss-120b --limit 5 --turn-limit 3 \
  --run-id cloud-groq-release
```

## Project layout

```text
apps/web/        React/Vinext localhost UI
apps/api/        FastAPI, PostgreSQL, parsing, retrieval, grounding, artifacts
services/agent/  Pi runtime, provider adapters, and model-callable tools
deploy/cloud/    Combined FastAPI/Pi cloud image
supabase/        Versioned PostgreSQL/pgvector migration and embedding function
evals/           retrieval regression, model gates, and 10-by-5 release suite
docs/            PRD, design, architecture, evaluation, and manual verification
agent-transcripts/ sanitized failures, corrections, and decisions
```

## Privacy and providers

- In the local profile, Ollama inference, transcripts, vectors, sessions, and artifacts remain local.
- In the cloud profile, transcript passages and sessions are stored in the configured Supabase project and bounded prompt/evidence data is sent to the explicitly selected Groq model.
- Claude is disabled until `ANTHROPIC_API_KEY` is set in local `.env`. Selecting it explicitly sends only bounded session context and evidence needed for that run.
- Groq remains disabled in the local profile unless `ENABLE_GROQ=true`; the cloud profile enables it explicitly.
- `.env` is ignored. API responses and persisted failure fields use stable codes rather than upstream bodies or secrets.

Codex CLI/ChatGPT credentials are not used as an application provider.

## Troubleshooting

- **Ollama unavailable:** confirm `ollama list` contains `qwen3:8b` and `nomic-embed-text`, then recreate API and agent services.
- **Database/vector mismatch:** inspect `/api/ingest/status` and `/api/ingest/manifest`; let the resumable ingestion finish before evaluation.
- **Claude unavailable:** add a real `ANTHROPIC_API_KEY` only to `.env`; missing-key behavior is expected and never triggers silent fallback.
- **Model timeout or missing citation:** the API returns a safe failure code and, when possible, a clearly labelled evidence-only response rather than an unverified synthesis.
- **Docker registry timeout:** retry the clean build when registry access recovers. Starting cached images is useful for diagnosis but is not a clean-build release gate.

## Handoff documents

- [Founder and PM research questions](docs/founder-pm-research-questions.md)
- [Product requirements](docs/prd.md)
- [Design](docs/design.md)
- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Manual test plan](docs/manual-test.md)
- [Sanitized coding-agent log](agent-transcripts/build-log.md)
- [Cloud recovery and deployment decision](docs/what-we-messed-up-and-recovery-plan.md)

## Online demo

You can access the hosted application at [Lenny's Growth Assistant](https://lennys-growth-assistant.maruthi-enugula.chatgpt.site/).

- Username: `lenny`
- Password: `podcast`
