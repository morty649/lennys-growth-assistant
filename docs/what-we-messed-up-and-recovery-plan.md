# What we messed up and what we changed

Date: 2026-08-26  
Status: local and cloud implementations are running; final evaluation evidence is incomplete

This is a technical retrospective, not a release claim. It separates problems we fixed from validation work that still remains.

## Current product shape

- **Local:** Docker Compose runs the web UI, FastAPI, Pi agent, PostgreSQL, Chroma, and a host-based Ollama model. Groq and Claude are optional, explicitly selected providers.
- **Cloud:** the public UI calls a Render backend using Supabase PostgreSQL and pgvector. Groq is the configured hosted model; Claude remains optional.
- **Shared behavior:** both profiles use the same session, routing, retrieval, grounding, source, artifact, and tool contracts.

## 1. We kept changing the target

### What went wrong

We moved repeatedly between localhost, public hosting, Railway, Supabase, Ollama, Codex, Claude, Groq, and several model sizes. Configuration, documentation, and actual verification stopped describing the same product.

### What changed

The product now has two explicit profiles instead of one shifting topology. Local remains self-contained and evaluator-run. Cloud uses the hosted UI, Render, Supabase, and Groq. Supabase was deliberately chosen over Railway for managed PostgreSQL. The two profiles share application code but keep independent infrastructure and model configuration.

## 2. We treated implemented code as proven behavior

### What went wrong

Adapters, routes, or UI controls were sometimes described as complete before a real end-to-end result existed. This was most visible with provider support, Ship 30 generation, and deployment readiness.

### What changed

We distinguish **implemented**, **automatically tested**, **deployed**, and **release-passing**. The current backend deployment is live and healthy, all 303 episodes are ingested, and persistence works. Ship 30 and the final multi-turn evaluation are still not release-passing because their intended live evidence has not been completed and reviewed.

## 3. We made every question look like a RAG question

### What went wrong

Early routing sent greetings and general questions toward transcript retrieval. The assistant then abstained or displayed sources when no podcast evidence was necessary.

### What changed

Every turn now passes through adaptive semantic routing. Direct conversation uses no transcript tool. Corpus questions browse the catalog. Research questions retrieve evidence. Ship 30 requests use their dedicated skill and evidence preparation tool. Sources appear only when retrieval was actually used.

## 4. We reached for hardcoded fixes

### What went wrong

Some proposed fixes were framed around specific guests, phrases, or example questions. That approach could make a demo case pass while failing across the other episodes.

### What changed

Guest and topic resolution now operates from the generated corpus catalog. Canonical episode IDs become dynamic retrieval constraints. Lexical and vector results are filtered and reranked generically. Named guests remain in tests as regression examples, not as production routing rules.

## 5. We optimized evaluation volume instead of learning speed

### What went wrong

Large local evaluations were started before individual failure modes were understood. Qwen latency turned them into multi-hour runs, while repeated failures added little information.

### What changed

Evaluation now follows a ladder: unit tests, focused routing checks, one research canary, then five distinct three-turn sessions. Retrieval Recall@5 and Recall@8 are measured separately from expensive generation. Runs save checkpoints and detailed answer/evidence records. Two interrupted Groq result files remain intentionally untracked and must not be presented as final evidence.

## 6. We expected one small local model to do every job

### What went wrong

Qwen 8B was expected to handle fast conversation, reliable tool routing, grounded synthesis, and a polished 1,250-word essay. Its latency and long-form reliability do not justify that claim.

### What changed

The local profile demonstrates Ollama-based operation and tool use. The same local UI can explicitly select Groq or Claude when configured; those are separate providers, not silent fallbacks. The cloud profile uses Groq for the hosted demonstration. Actual provider and model metadata are shown and persisted with every response.

## 7. Ship 30 is safe but not yet proven

### What went wrong

The skill and artifact UI existed, but early drafts were generic, short, or missing valid evidence tokens. Having a button and a prompt did not demonstrate a successful writing workflow.

### What changed

Ship 30 is a versioned skill with a bounded preparation tool. Generation requires grounded passages, a strong hook, narrative progression, skimmable structure, an actionable takeaway, and approximately 1,250 words. The server withholds artifacts that fail structural or citation gates. One strong live artifact still needs manual review before this capability is called release-passing.

## 8. Evaluation sessions polluted the product experience

### What went wrong

Automated sessions were written into the same profile used for manual demonstrations. The sidebar became noisy and made the product appear unfinished.

### What changed

Profiles now isolate user sessions and the evaluator supports a distinct run identity. Future automated runs should use a dedicated test profile or database. Existing evaluation sessions still visible in the demo profile should be cleaned only after preserving any evidence needed for the final report.

## 9. We confused database hosting with application hosting

### What went wrong

Railway and Supabase were discussed as if either automatically hosted the database, backend, agent, model, and frontend. This obscured the real boundaries and repeatedly broke deployment configuration.

### What changed

Supabase owns cloud PostgreSQL and pgvector. Render runs FastAPI and Pi in one Docker service. The public frontend is hosted separately. Groq or Claude performs cloud inference. Locally, PostgreSQL and Chroma remain Docker services while Ollama runs on the host. These flows are now shown separately in `docs/architecture.md`.

## 10. Provider integration was temporarily inconsistent

### What went wrong

At one stage Pi understood Groq while the API schemas and UI did not. Model names also drifted between environment files, documentation, and deployed behavior.

### What changed

Provider configuration now flows through the API, Pi contract, UI selector, persistence metadata, health/config endpoints, and tests. The hosted default is Groq GPT-OSS 120B with a smaller Groq fallback only for a genuine rate-limit response. Local model names remain environment-configurable. Claude is visible only when its key is supplied.

## 11. Authentication was added before the sign-in experience

### What went wrong

The backend began requiring profile authentication while the public UI did not expose a usable sign-in screen. Users saw “Profile sign-in required” with no clear recovery path.

### What changed

The public UI now has a dedicated profile sign-in state and profile switching. Sessions and artifacts are scoped to a stable user identity. Passwords, signing secrets, provider keys, database credentials, and internal tool tokens remain server-side.

## 12. Documentation became dense and environment-biased

### What went wrong

Architecture documentation grew into a local-heavy implementation dump. The combined local/cloud diagram was cluttered, and important product boundaries were harder to see than the details.

### What changed

`docs/architecture.md` now begins with a concise query dataflow and gives local and cloud deployments separate diagrams. The remaining prose covers only component ownership, ingestion/retrieval, agent tools, persistence, APIs, and security. README, PRD, design, and architecture documents have distinct responsibilities.

## 13. “One command” was stated too casually

### What went wrong

`docker compose up` was described as completely self-sufficient even though Docker, Ollama, and the required local models are host prerequisites. First-run ingestion also has a real startup cost.

### What changed

The repository contains its transcripts and indexes, and Compose starts all application and data services. The README must continue to state the Ollama prerequisite and model pulls explicitly. The current stack is healthy, but the latest exact commit still needs one clean-clone Compose rehearsal before the evaluator path is called fully certified.

## 14. Verification evidence lagged behind the code

### What went wrong

Test totals, provider status, and deployment claims changed faster than the handoff documents. Old statements remained technically historical but looked current.

### What changed

The current automated evidence is:

- 42 API tests passed and one skipped;
- one real PostgreSQL integration test passed;
- 17 Pi-agent tests and the TypeScript build passed;
- frontend lint and production build passed;
- Render successfully deployed the current backend;
- readiness reports PostgreSQL, pgvector, Pi, and all 303 ingested episodes as healthy.

These checks prove infrastructure and contracts, not answer quality. The remaining release evidence is a reviewed Ship 30 artifact, the five-session/three-turn evaluation, and a fresh-clone Compose rehearsal from the final commit.
