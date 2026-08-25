# Local verification checklist

1. Start Ollama and `make up`; wait for `/api/ingest/status` to say `complete` and confirm the manifest's vector count equals its evidence-unit count.
2. Confirm `/health/ready` reports PostgreSQL, Chroma, Ollama `qwen3:8b`, `nomic-embed-text`, and Pi as ready.
3. Ask `hey`; confirm no source panel or transcript tool run is created.
4. Ask an Aparna question; confirm a model-origin `search_transcripts` run, supported answer, timestamp citations, and `thinking_mode=off` in stored metadata.
5. Ask two pronoun follow-ups; confirm the resolved guest stays Aparna. Explicitly switch guests and confirm the old constraint clears.
6. Start another session, verify isolation, return to the first, and verify persistence.
7. Click an answer's source badge/citation; confirm the exact answer-bound source bundle opens in the side workspace.
8. Create a Markdown artifact from a grounded answer; confirm its inline card opens the correct Preview/Code/Sources bundle and **Save Markdown** downloads a non-empty `.md` file.
9. Test workspace close/expand, the mobile session drawer, and mobile full-screen artifact/source workspace.
10. Confirm Claude is visibly unavailable without a key. No request may silently switch provider.
11. Stop Pi or Ollama and submit a transcript question; confirm truthful evidence-only/abstention metadata and a safe failure code.
12. Run API tests, the PostgreSQL isolation test, Pi tests/build, web lint/build, the 40-case retrieval regression, and the bounded five-session/three-turn release evaluation with manual evidence review.
