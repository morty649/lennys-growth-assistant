# Lenny's Growth Assistant v0.2

A conversational research agent over Lenny's Podcast transcripts. FastAPI owns sessions, retrieval, citations, and artifacts; Pi owns the model/tool loop; local Qwen on Ollama is the default backend. Claude is an explicit optional backend through the same Pi harness. Groq is deferred and hidden.

## What is implemented

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

The required deployment is localhost. A public application URL and Supabase are not prerequisites for this submission.

## Repository and corpus

The repository is self-contained: `episodes/` and `index/` live at its root and are mounted read-only into the API container.

## Start on localhost

Prerequisites: Docker Desktop and Ollama running on the host.

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
cp .env.example .env   # only if .env does not already exist
make up
```

Open [http://localhost:3000](http://localhost:3000). All published application and data ports bind to `127.0.0.1`.

Readiness and ingestion:

```bash
curl --noproxy '*' http://127.0.0.1:8000/health/ready
curl --noproxy '*' http://127.0.0.1:8000/api/ingest/status
curl --noproxy '*' http://127.0.0.1:8000/api/ingest/manifest
```

The first run builds the versioned semantic index and can take several minutes. Do not evaluate until the manifest reports matching evidence-unit and vector counts.

## Verification

```bash
make test
make build
make eval
make eval-v02
```

The v0.2 evaluation makes 50 real `POST /api/chat` turns and checkpoints after every turn. Resume safety is bound to the dataset checksum, provider, and exact model:

```bash
cd apps/api
uv run python ../../evals/run_agent_eval.py --set v02 --provider ollama --model qwen3:8b --resume
```

The dataset is mechanically grounded in actual transcript Q&A units and frozen for repeatability. Its `review_status` records that origin. Automated success remains separate from manual support review.

## Project layout

```text
apps/web/        React/Vinext localhost UI
apps/api/        FastAPI, PostgreSQL, parsing, retrieval, grounding, artifacts
services/agent/  Pi runtime, provider adapters, and model-callable tools
evals/           retrieval regression, model gates, and 10-by-5 release suite
docs/            PRD, design, architecture, evaluation, and manual verification
agent-transcripts/ sanitized failures, corrections, and decisions
```

## Privacy and providers

- Ollama inference, transcripts, vectors, sessions, and artifacts remain local.
- Claude is disabled until `ANTHROPIC_API_KEY` is set in local `.env`. Selecting it explicitly sends only bounded session context and evidence needed for that run.
- Groq remains disabled for v0.2 even if an old key exists in `.env`.
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
- [Sanitized coding-agent log](agent-transcripts/v0.1-v0.2-build-log.md)
- [v0.2 implementation plan](v0.2.md)
