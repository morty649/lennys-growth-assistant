# Demo Script (2-3 minutes)

1. Introduce the problem: podcast answers lose nuance when transcripts are treated as anonymous fixed-size chunks.
2. Show `docker compose ps`, the `qwen3:8b` Ollama model, and the ready localhost UI.
3. Create a new investigation and ask a guest-specific question.
4. Ask a referential follow-up without repeating the guest; point out session-scoped context.
5. Open a timestamp citation and show the transcript passage in the side workspace.
6. Open a saved Markdown or HTML artifact beside the conversation and switch between Preview, Code, and Sources.
7. Show the provider selector: Ollama works locally; Anthropic becomes available only with an evaluator-supplied API key and never silently replaces Ollama.
8. Close with the trade-off: the local path is private and reproducible, but Qwen3 8B latency is roughly 50 seconds at p50 on the measured machine and the safety fallback was used on 16% of the frozen evaluation turns.

Do not claim the 50-turn suite passed every gate. State that it completed, passed six of seven automated gates, and failed only the strict fallback-rate threshold.
