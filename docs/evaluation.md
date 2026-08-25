# v0.2 evaluation

This release separates retrieval diagnostics from real end-to-end model behavior. It does not claim that the interrupted 440-turn experiment completed.

## Suites

### Retrieval regression

`questions.json` contains 40 fast internal-search cases. It measures Recall@5, Recall@8, MRR@8, and route accuracy. It does not prove model tool selection, session memory, citation behavior, or answer quality.

```bash
make eval
```

### Five-turn local-model gate

Before the release suite, one real session validates explicit guest resolution, follow-up context, model-originated transcript search, no-think transport behavior, citations, fallback state, and latency.

### v0.2 release suite

`v02_sessions.json` contains 10 distinct guests and episodes with exactly five turns each: 50 real calls through `POST /api/chat`.

```bash
make eval-v02
```

The runner records provider, exact model, dataset checksum, run ID, per-turn sources, gold evidence, route, tool origin, context retention, citation state, execution mode, fallback reason, and latency. Checkpoints are written atomically. Resume is refused when provider, model, or dataset identity changes.

## Automated gates

- 10 sessions and exactly 50 turns complete.
- Episode Recall@5 >= 0.80.
- Episode Recall@8 >= 0.90.
- Route accuracy >= 0.90.
- Context retention >= 0.90.
- Model-originated transcript search >= 0.90.
- Citation presence = 1.00 on supported answers.
- Evidence-only fallback rate <= 0.10.

Automated success is stored as `automated_passed`. Overall `passed` remains false until manual support review is complete.

## Manual support review

For every accepted factual answer:

1. Open each bound source excerpt.
2. Verify guest/speaker attribution and timestamp.
3. Confirm every material claim is supported nearby.
4. Check that qualifications and disagreements were preserved.
5. Confirm follow-up referents stayed within the intended session.
6. Label failures as intent, context, route, lexical, dense, fusion/rerank, sufficiency, tool selection, citation, synthesis, artifact, or provider metadata.

Release requires zero accepted unsupported material claims. Generated fixtures remain labelled pending manual review until this check is recorded.

## Historical evidence

- The 40-case retrieval result remains a diagnostic baseline.
- The 14B direct/model gate and clean five-turn probe remain historical qualification evidence.
- The interrupted multi-session 14B file remains incomplete and must not be resumed or mixed with 8B results.
- Qwen3 8B has its own model-identified gate and release files.

## Cloud canary

When `ANTHROPIC_API_KEY` is available, run one five-turn development canary through the same Pi tools. Do not claim cloud parity without a live run, and do not run a paid 50-turn suite without an explicit cost budget.
