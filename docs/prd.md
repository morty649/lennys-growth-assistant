# Product requirements - v0.2

## Product

Lenny's Growth Assistant is a local-first research workspace for asking grounded questions across the Lenny's Podcast corpus without losing conversational context. The mandatory evaluator path is self-contained Docker Compose; an additive public demo uses three password-protected profiles with isolated sessions.

## Primary user jobs

1. Ask a guest-specific, topic-specific, or cross-corpus question and receive an evidence-backed answer.
2. Ask follow-up questions within one investigation without repeating context.
3. Keep multiple investigations separate and return to them later.
4. Inspect the exact guest, episode, speaker, timestamp, and excerpt behind an answer.
5. Turn a grounded answer into a reusable Markdown or HTML/CSS artifact.
6. Test whether local Qwen and explicitly configured Claude can reliably invoke the same tools through Pi.

## MVP requirements

- Web application runs at `localhost:3000` and all services bind to loopback only.
- One implicit local user can create, select, rename automatically, and delete sessions.
- Each session stores its own messages, selected provider, model, sources, and artifacts.
- FastAPI provides the public application API.
- PostgreSQL stores sessions and source metadata; Chroma stores dense retrieval vectors.
- The entire transcript corpus can be ingested without modifying source files.
- Pi is the only model/tool harness. The default backend is Ollama `qwen3:8b` with per-request no-think enforcement; 14B is retained only as a proven fallback option.
- Claude and Groq are explicit optional Pi backends. The public profile uses Groq GPT-OSS 120B with a disclosed 20B fallback only for provider rate limits.
- Answers cite transcript evidence; unsupported questions abstain.
- Users can inspect answer-bound evidence and exact-message artifacts in a responsive Preview/Code/Sources workspace.
- Ship 30 requests use an evidence-ID allowlist, structured word budgets, and 1,100–1,400 word artifact validation.
- A five-turn qualification gate and a 10-session/50-turn release set exercise the real chat, Pi, tool, context, grounding, and provider path. A separate 40-case suite measures retrieval regression.

## Non-goals for MVP

- Account signup, teams, or organization administration
- Product analytics or transcript editing workflows
- Editing/replacing the source transcripts
- General web search or answering from model memory
- JavaScript execution in generated artifacts

## Acceptance criteria

- Fresh setup uses the README commands with no undocumented service.
- Representative parser tests retain speaker and timestamp context while excluding sponsor reads.
- Guest and topic routing work as priors without making the legacy topic index a hard dependency.
- Retrieval fallback never presents an LLM synthesis when the model service is unavailable.
- Session history survives browser refresh and does not leak across sessions.
- All code builds and automated tests pass.
- Recall@8 reaches at least 0.90 on the v0.2 release set, context retention reaches 0.90, citations cover every accepted factual answer, and unsupported accepted claims remain zero before calling v0.2 quality complete.
