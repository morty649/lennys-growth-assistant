# What we messed up and how we recover

Date: 2026-08-26  
Status: local implementation checkpoint; cloud work has not started

## The decision

We will keep two explicit product tracks instead of repeatedly converting one environment into the other.

1. **Local demo:** the current self-contained repository stays Docker Compose + local PostgreSQL + Chroma + Ollama `qwen3:8b`. It is the mandatory local-model demonstration and the evaluator can run it from a clone. The transcripts and topic indexes remain inside the repository.
2. **Cloud demo:** a later, separate deployment will use managed Supabase PostgreSQL, Supabase `pgvector`, hosted FastAPI/Pi services, and Groq. Its default model will be the explicit, configurable `openai/gpt-oss-120b`. Anthropic remains an optional adapter, not a release dependency.

We deliberately choose **Supabase instead of Railway for managed PostgreSQL**. The application still needs somewhere to run the web, FastAPI, and Pi services: Supabase is the database and vector store, not the application host. No Supabase, Groq, or public-hosting changes belong in the local-only checkpoint.

```text
LOCAL
Browser -> web -> FastAPI -> Pi -> Ollama
                    |-> local PostgreSQL
                    `-> local Chroma

CLOUD
Browser -> hosted web -> hosted FastAPI -> hosted Pi -> Groq GPT-OSS 120B
                            |
                            `-> Supabase PostgreSQL + pgvector
```

For a public demo, we configure one server-side Groq key and protect it with rate limits. For a cloned repository, the evaluator supplies `GROQ_API_KEY` in `.env`. We should not ask public visitors to paste keys into the browser, and keys must never be shipped in Git.

## What already has real value

- The nested repository is self-contained: 303 episode directories and 89 topic/index files are tracked with the application.
- The local product path exists: web UI, FastAPI, Pi agent, PostgreSQL sessions, hybrid retrieval, Chroma vectors, Ollama, citations, and artifacts.
- Session, message, artifact, tool-run, episode, evidence, and ingestion records have PostgreSQL schemas.
- Retrieval has a useful diagnostic baseline: the recorded 40-case suite reached Recall@5 1.00 and Recall@8 1.00.
- The source checkpoint passes 28 API tests, 14 agent tests, web lint, and a production web build.
- Failure behavior is generally conservative: weak or uncited transcript answers are withheld instead of presented as grounded facts.

Those assets should be preserved. The recovery is mostly about proving the product, simplifying the deployment story, and removing contradictions—not rewriting everything.

## 1. We kept changing the target

### What went wrong

The project moved between localhost, a public website, Railway, Supabase, Ollama, Codex, Anthropic, Groq, 8B, and 14B without freezing one accepted baseline. Each pivot introduced partial configuration and documentation, so “implemented,” “enabled,” and “verified” became different states.

### How we solve it

Freeze the current repository as the local-only baseline. Build cloud support afterward in small commits with separate acceptance gates. Do not alter the local Compose topology merely to make cloud hosting easier. Both tracks share domain code and tools, but have different deployment configuration.

## 2. We treated code presence as product success

### What went wrong

Several capabilities exist in source but were described too confidently. Anthropic has an adapter but no live canary. Groq has partial agent code but is excluded by API and UI types. Artifact viewing exists, but strong end-to-end Ship 30 generation has not passed.

### How we solve it

Use four labels everywhere: **planned**, **implemented**, **verified**, and **release-passing**. A provider becomes verified only after a real five-turn canary. A feature becomes release-passing only after its user-visible output meets the stated quality gate.

## 3. We optimized retrieval before the basic assistant experience

### What went wrong

The assistant initially behaved like every message required podcast evidence. Greetings and ordinary questions triggered abstentions or irrelevant sources. That made good retrieval metrics meaningless to a user whose first two chat turns felt broken.

### How we solve it

Keep one adaptive agent with clearly described tools and a compact live corpus catalog. The model can answer ordinary conversation directly, browse the catalog when scope is unclear, and retrieve only for transcript claims. Add a small regression suite covering greetings, identity, general help, research, follow-ups, and unsupported questions.

## 4. We replaced dynamic reasoning with patches

### What went wrong

Some fixes were framed around individual guests, example phrases, or special cases. Even where later code removed those patches, the design process repeatedly leaned toward hardcoded routing. That does not generalize across 303 episodes.

### How we solve it

Resolve guests and topics from the generated episode/index catalog, then pass canonical filters into a generic retrieval tool. Tests may use named examples, but production logic must not contain guest-specific answers or topic keyword response templates.

## 5. We chose evaluation volume before evaluation economics

### What went wrong

The 50-turn local run took 45.7 minutes, with p50 latency of 49.8 seconds and p95 of 84.2 seconds. Earlier plans proposed much larger runs before individual failures were understood. This consumed time while producing repetitive evidence.

### How we solve it

Use a ladder: unit tests, six-turn routing smoke, one five-turn research session, ten distinct five-turn sessions, then a larger suite only if needed. Run cheap retrieval regression separately. Stop a suite early when a gate clearly fails, fix the failure class, and resume from checkpoints.

## 6. We selected a local model that does not meet every job

### What went wrong

`qwen3:8b` proves local tool use, but it is slow on this machine and has not produced a passing long-form Ship 30 essay. The recorded 50-turn run also exceeded the evidence-only fallback target: 0.16 versus 0.10.

### How we solve it

Keep Qwen 8B for the mandatory local demonstration and short grounded research. State its limits. Use Groq `openai/gpt-oss-120b` for the cloud quality demonstration and Ship 30 test. Do not silently switch providers; show the actual provider/model with each response.

## 7. The Ship 30 feature is implemented but not complete

### What went wrong

The skill, preparation tool, grounding validation, and artifact gate exist. However, the tested 8B drafts were generic, short, unsupported, or missing citation tokens. The gate correctly withheld them, which is safe behavior but not a successful assignment demonstration.

### How we solve it

First run one hand-reviewed gold case on GPT-OSS 120B. Require valid transcript evidence, 1,100–1,400 words, a specific thesis, narrative progression, skimmability, and an actionable takeaway. Only after that passes should we run the remaining nine editorial cases and record their scores.

## 8. Evaluation data polluted the demo UI

### What went wrong

Automated evaluation sessions were stored beside human demo sessions, leaving a noisy sidebar full of machine-generated investigations. This makes the interface look unfinished and makes it difficult to inspect a clean user journey.

### How we solve it

Give evaluations a separate database, schema, or test user. Seed the demo with no sessions or two carefully chosen examples. Never run automated suites against the same identity and database shown in the recorded demo.

## 9. Provider support is contradictory

### What went wrong

The agent contract knows `groq`, but FastAPI request schemas, provider discovery, and frontend types accept only Ollama and Anthropic. The environment example still names Qwen 3.6 while documentation says Groq is deferred. This is a half-integration, not cloud support.

### How we solve it

Add Groq vertically in one slice: shared provider contract, configuration endpoint, session schema, UI selector, exact model metadata, Pi model adapter, error mapping, and tests. Default to `openai/gpt-oss-120b`, but permit `GROQ_MODEL` override. Do not expose it until a live tool-call canary passes.

## 10. We did not separate database hosting from application hosting

### What went wrong

Railway and Supabase were discussed as though either one automatically hosted the entire product. Supabase provides managed PostgreSQL and related services; it does not run this FastAPI/Pi application or the Ollama model. The current Dockerfiles also rely on local mounts that a cloud host will not have.

### How we solve it

Use Supabase for PostgreSQL and vectors. Host the frontend and backend services separately. During cloud deployment, bake required skills into the agent image and run corpus ingestion as a controlled one-time job from the tracked transcript files. Do not mount a developer laptop path in production.

## 11. Chroma creates an unnecessary second cloud stateful service

### What went wrong

Chroma is sensible locally, but hosting both Supabase PostgreSQL and a persistent Chroma service makes the cloud version harder to provision, back up, and explain. It also creates two sources of ingestion state.

### How we solve it

Keep Chroma unchanged locally. For cloud only, enable `pgvector` in Supabase and store embeddings with evidence IDs in PostgreSQL. Preserve the retrieval interface so lexical search, vector search, fusion, and reranking do not care which vector backend is selected.

## 12. The public version has no user boundary

### What went wrong

The local MVP uses one fixed local user, loopback-only ports, a development internal token, and localhost CORS. That is acceptable for a laptop demo but unsafe for a public URL: visitors would share sessions and could consume the configured model quota.

### How we solve it

For cloud, assign each browser an anonymous Supabase-authenticated identity or require a simple sign-in, enforce ownership on every session/artifact query, use real service secrets, restrict CORS, rate-limit chat, and disable public ingestion/deletion administration. Keep this out of the local-only checkpoint.

## 13. “One command” is not yet literally one command

### What went wrong

`make up` starts the containers, but Ollama and two model downloads are host prerequisites. First-run embedding also takes time. A fresh-clone rehearsal from the exact commit has not been recorded, so the README path is plausible rather than independently proven.

### How we solve it

Be precise: the evaluator installs Docker and Ollama, pulls the two named models, then runs `docker compose up --build`. Add a preflight that reports missing models clearly. Before submission, test from a clean clone, wait for ingestion parity, and record exact elapsed time and commands.

## 14. Documentation and current behavior drifted apart

### What went wrong

The README previously linked to a nonexistent planning document. Some older reports describe fewer tests than now exist, and “Claude implemented,” “Groq deferred,” and “cloud version” are easy to misread as verified provider parity. The current containers are also stopped even though prior reports describe a running stack.

### How we solve it

Make one release-status page the source of truth. Update it only from a repeatable verification checklist and link historical reports as historical. Remove broken links, date provider canaries, and distinguish source verification from a currently running deployment.

## Supabase translation of the earlier Railway idea

| Earlier Railway-shaped responsibility | Supabase-based decision |
|---|---|
| Managed PostgreSQL service | Supabase managed PostgreSQL |
| PostgreSQL session/message/artifact tables | Same schema migrated with versioned SQL migrations |
| Hosted Chroma volume | Replace in cloud with Supabase `pgvector`; retain Chroma locally |
| Internal database URL | Supabase direct connection for a long-lived IPv6 backend, or Supavisor session pooler when the host is IPv4-only |
| Secrets | Backend-host secrets; never frontend environment variables |
| Authentication/user IDs | Supabase Auth anonymous or signed-in identities for the public version |
| FastAPI/Pi containers | A separate container host; Supabase does not run them |
| Frontend | A separate static/frontend host pointing only to the public FastAPI URL |
| Corpus ingestion | Controlled one-time/admin job from the repository corpus into Supabase |

## Recovery order

### Checkpoint A — local only

- Preserve the current code and corpus in Git.
- Record passing unit/lint/build gates.
- Re-start Compose later and run one clean manual demo session.
- Do not add Supabase or Groq behavior to this checkpoint.

### Checkpoint B — prove the cloud model locally

- Complete the Groq provider contract end to end.
- Configure `openai/gpt-oss-120b` through `.env`, never in Git.
- Run general-chat, transcript-tool, multi-turn, and one Ship 30 canary.
- Keep local PostgreSQL/Chroma during this step so only one variable changes.

### Checkpoint C — move cloud data to Supabase

- Create versioned SQL migrations for current tables and `pgvector`.
- Implement a selectable vector-store adapter.
- Ingest the corpus once and verify record/vector parity and Recall@8.
- Keep local Compose behavior unchanged.

### Checkpoint D — host the application

- Deploy web, FastAPI, and Pi with production secrets and health checks.
- Add user/session ownership, CORS restrictions, and rate limits.
- Run a five-turn cloud canary, then the ten-session suite.
- Publish only after a clean-clone local rehearsal and a clean public-demo rehearsal.

## Explicit non-goals for the next step

- No Railway provisioning.
- No deletion of local PostgreSQL or Chroma.
- No public key-entry form.
- No automatic provider fallback.
- No 50-turn paid evaluation before a five-turn canary passes.
- No claim that Ship 30 passes until a generated artifact is manually scored.
- No push or public deployment without explicit authorization.
