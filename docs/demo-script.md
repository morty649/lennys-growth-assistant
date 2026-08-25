# Demo Script (2–3 minutes)

## Recording prerequisite

Record this demo only after the public Adam and Casey research checks pass, Ship 30 creates a downloadable artifact, and the submitted commit passes a fresh-clone rehearsal. The earlier clean-clone check predates the current changes, so this remains a prepared script rather than evidence of a successful release.

## Script

1. **Frame the problem (15 seconds).** Explain that Lenny's Podcast contains hundreds of long, conversational transcripts. The assistant preserves guest, topic, timestamp, and multi-turn context instead of treating every passage as an anonymous chunk.

2. **Show the hosted product and sign in (20 seconds).** Open <https://lennys-growth-assistant.maruthi-enugula.chatgpt.site/>, sign in with one of the prepared demo profiles, and point out that profiles have isolated private sessions. Do not display or read the password aloud.

3. **Show direct conversation (15 seconds).** Ask a normal greeting or product question. Point out that it answers directly and does not attach transcript citations when retrieval was not used.

4. **Show grounded transcript research (30 seconds).** Ask one already-verified guest-specific research question. Open a returned source and show the episode, timestamp, and transcript passage beside the conversation. Do not use the unresolved Adam or Casey cases until they pass retesting.

5. **Show multi-turn memory (20 seconds).** Ask a follow-up such as “What did they recommend doing first?” without repeating the guest. Explain that the resolved guest/topic context is persisted for this session rather than hard-coded for a named guest.

6. **Show the Ship 30 capability (30 seconds).** Ask the assistant to turn the grounded answer into a Ship 30 for 30–style essay. Open the Markdown artifact beside the chat, briefly show its hook, progression, skimmable structure, transcript-grounded claims, and specific takeaway, then use **Save Markdown** to download the `.md` file. Skip this step if the public 502 remains unresolved; never edit around the failure during the recording.

7. **Explain the architecture (25 seconds).** State that the live Sites frontend calls FastAPI on Render, while Supabase PostgreSQL/pgvector stores profiles, sessions, evidence, and vectors. Groq `openai/gpt-oss-120b` is primary; `openai/gpt-oss-20b` is used only after a genuine HTTP 429 rate limit.

8. **Show local reproducibility (20 seconds).** Show the final clean-clone terminal running `docker compose up --build`, the healthy services, the complete 303-episode/16,469-unit ingestion, and one local Ollama answer. This demonstrates that an evaluator can run the stack without depending on the hosted model path.

9. **Close honestly (10 seconds).** Summarize the final 5-session/3-turn hosted evaluation and manual review using the recorded results. Mention only checks that actually passed; do not reuse the interrupted pre-fix cloud run as release evidence.

## Claims to avoid

- Do not say the current public browser checklist passed while the Adam, Casey, or Ship 30 failures remain open.
- Do not call the 20B model a general fallback; it is rate-limit-only.
- Do not claim independent support review until all 15 final hosted turns are manually checked.
- The clean clone passed for historical commit `71a2b3b`; repeat it for the submitted commit because application source changed afterward.
- Do not expose profile passwords, API keys, database credentials, or signed tokens on camera.
