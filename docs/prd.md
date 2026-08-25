# Product requirements

## Product

Lenny's Growth Assistant is a conversational research workspace over Lenny's Podcast transcripts. It helps users recover useful ideas quickly, ask follow-up questions, verify answers against timestamped evidence, and turn grounded research into downloadable Markdown.

The evaluator can run the complete repository on localhost with Docker Compose. A separate hosted demo uses the same product contracts with cloud infrastructure and isolated profiles.

## User and problem

The primary user is a growth manager, product manager, or founder who wants to learn from long podcast episodes but may not have time to watch them. Even after watching, it is difficult to extract clear points and later recall where a specific idea appeared.

The experience should feel like having a trusted friend who studied the same mathematics lecture. You can ask that friend questions repeatedly instead of replaying the entire lecture, and the friend can show which part of the lesson supports the answer. Here, the conversation provides recall while transcript excerpts provide proof.

## Success metrics

- **Groundedness:** zero accepted unsupported material claims after manual review; every accepted podcast claim has a relevant guest, episode, timestamp, and excerpt.
- **Retrieval:** Recall@5 of at least 0.80 and Recall@8 of at least 0.90 on the curated research set.
- **Multi-turn memory:** five distinct three-turn sessions retain the correct subject, persist after refresh, and do not leak context across sessions or profiles.
- **Artifacts:** grounded Markdown opens beside the chat, remains connected to its source message and evidence, and downloads as a valid `.md` file.
- **Ship 30:** the dedicated skill produces a transcript-grounded 1,100–1,400 word essay with a strong hook, clear progression, skimmable formatting, and a useful takeaway.
- **Truthfulness:** the UI and stored metadata show the actual provider/model, tools, fallback reason, and failures. Interrupted runs are not counted as passes.

## Assumptions

1. The supplied transcripts are materially correct; parsing may remove structural noise but must not rewrite speaker meaning.
2. The UI should be clean and credible because the target user is a senior product, growth, or company leader.
3. The architecture should be able to grow beyond the MVP through stateless services, PostgreSQL ownership, rebuildable indexes, user-scoped sessions, and server-side secrets.
4. Guest folders and topic indexes help route retrieval, but timestamped transcript passages remain the evidence.
5. Local Ollama is mandatory. Evaluators may also configure Claude or Groq and select them from the localhost UI; the hosted deployment remains a separate environment.

## Scope

### Included

- Self-contained episode and topic data in the repository
- One-command Docker Compose application after documented Docker/Ollama prerequisites
- FastAPI, Pi agent harness, PostgreSQL sessions, and hybrid transcript retrieval
- Independent multi-turn sessions with persisted messages, sources, providers, and artifacts
- Explicit localhost provider selection between configured Ollama, Anthropic, and Groq options
- Direct answers for ordinary questions and transcript tools only when podcast evidence is needed
- Timestamped sources, abstention on insufficient evidence, and claim-to-excerpt validation
- Dedicated Ship 30 tool and beside-chat Markdown artifact viewer/download
- Separate hosted demo with Supabase, Groq, and isolated fixed profiles

### Excluded or deferred

- Production signup, billing, teams, and organization administration
- General web search or treating model memory as podcast evidence
- Rewriting or LLM-normalizing the supplied transcripts
- Executable JavaScript in generated artifacts
- Large evaluation runs that cannot be completed and manually reviewed
- A guarantee that every small local model can produce strong long-form editorial writing

## Core flows

1. **Choose a model:** start localhost, select Ollama or a configured cloud provider, and retain that choice per session.
2. **Ask normally:** answer ordinary questions directly without transcript tools or sources.
3. **Research:** resolve the guest/topic, retrieve timestamped transcript passages, and answer only from sufficient evidence.
4. **Follow up:** use the current session's conversation and resolved subject without leaking another session's context.
5. **Create an artifact:** convert grounded research into a Ship 30 Markdown essay, inspect it beside the chat, and download it.
6. **Return later:** restore persisted sessions, messages, sources, provider selection, and artifacts from PostgreSQL.

## Key risks and tradeoffs

- **Hallucination:** citation syntax alone does not prove support. The system checks claim/excerpt overlap and requires manual review for release evidence.
- **Retrieval quality:** fixed-size chunks can separate questions, answers, and qualifications. Question-aware evidence units preserve conversational structure while guest/topic metadata narrows search.
- **Latency and model quality:** research and long-form writing require more steps than direct chat. Small local models may be slower or weaker; provider and failure metadata remain visible.
- **Cost and rate limits:** cloud calls may be limited. Only a genuine Groq rate limit can trigger the disclosed fallback model.
- **Data leakage:** provider keys remain server-side, sessions are user-scoped, and operational logs exclude prompts, answers, transcript text, and secrets.
- **Artifact safety:** Markdown and HTML are allowlist-sanitized, wrapped in a restrictive CSP, and shown in an iframe without script permissions.
- **Deployment separation:** localhost and hosted environments share code but not credentials or infrastructure; results must never be represented as coming from a different provider.

## Acceptance criteria

- A fresh clone runs using the documented setup and reaches healthy ingestion parity.
- Ordinary questions do not invoke retrieval or show sources.
- Guest/topic questions retrieve relevant timestamped evidence and unsupported questions abstain.
- Follow-ups retain the correct session context, and user/profile data remains isolated.
- Ollama works locally; configured Anthropic and Groq providers can use the same Pi tools.
- Valid Ship 30 results satisfy grounding, citation, word-range, viewing, and Markdown-download requirements.
- Automated tests and the PostgreSQL isolation test pass.
- Evaluation answers and evidence are saved for manual review before any quality pass is claimed.

## Implementation plan

1. Parse and index the bundled corpus into timestamped, question-aware evidence units.
2. Persist sessions, messages, tool runs, evidence metadata, and artifacts in PostgreSQL.
3. Connect Pi to catalog, transcript search, source expansion, and Ship 30 tools across supported providers.
4. Enforce grounding, safe errors, provider disclosure, and artifact isolation at the API boundary.
5. Deliver the responsive chat, session rail, fixed composer, evidence workspace, and Markdown download.
6. Run automated checks, the bounded multi-turn evaluation, manual evidence review, and a fresh-clone verification before submission.
