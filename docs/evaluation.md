# Evaluation

This release separates retrieval diagnostics from real end-to-end model behavior. It does not claim that the interrupted 440-turn experiment completed.

## Suites

### Retrieval regression

`questions.json` contains 40 fast internal-search cases. It measures Recall@5, Recall@8, MRR@8, and route accuracy. It does not prove model tool selection, session memory, citation behavior, or answer quality.

```bash
make eval
```

### Five-turn local-model gate

Before the release suite, one real session validates explicit guest resolution, follow-up context, model-originated transcript search, no-think transport behavior, citations, fallback state, and latency.

### Release suite

The frozen release dataset contains 10 distinct guests and episodes with exactly five turns each. A bounded submission check can select five sessions and three turns without changing the underlying cases.

```bash
make eval-release
```

The runner records provider, exact model, dataset checksum, run ID, per-turn answers, cited evidence excerpts, gold evidence, route, tool origin, context retention, citation state, execution mode, fallback reason, and latency. Checkpoints are written atomically. Resume is refused when provider, model, or dataset identity changes. Each turn includes a pending manual-review record so support and conversational context can be judged against the saved evidence rather than inferred from retrieval metrics.

### Ship 30 editorial suite

`ship30_content_cases.json` contains 10 transcript-backed writing assignments. The five `gold` cases include a reader, defensible thesis, four-part narrative, exact evidence window, and required takeaway. The five `challenge` cases test whether those editorial rules transfer to new guests and topics.

This suite is reviewed as writing, not reduced to keyword matching. For each generated essay, score 0-2 on each dimension:

1. **Grounding:** podcast claims preserve the speaker's meaning and carry the correct evidence token.
2. **Argument:** the essay advances one specific thesis instead of recapping sources.
3. **Progression:** each section moves the same argument from tension through evidence to application.
4. **Usefulness:** the reader receives a decision, diagnostic, experiment, or next action supported by the mechanism discussed.
5. **Execution:** the result is 1,100-1,400 words, skimmable Markdown, and free of generic openings, invented stories, and repeated conclusions.

An essay passes at 8/10 or better with no zero in Grounding. The suite passes when all five gold cases and at least four of five challenge cases pass. Record model, provider, source IDs, output, scores, and reviewer notes together; do not treat retrieval success alone as essay-quality success.

#### Current localhost result

On 2026-08-26, the 10 editorial cases achieved expected-episode Recall@8 of 10/10 against the self-contained corpus. Two bounded `qwen3:8b` generations were then run for the `retention-compounds` gold case:

- The first called transcript search and essay preparation, cited three passages, and returned 1,062 words. It failed the editorial review because it was below the hard word range, opened with generic “fast-paced world” language, repeated broad advice, and introduced unsupported framing. The artifact gate correctly withheld it.
- The second called both tools but produced no valid source tokens. The grounding guard replaced it with evidence-only output and withheld the artifact.

Therefore the local 8B model has **not** passed the Ship 30 editorial gate. Retrieval and evidence scoping pass; long-form synthesis remains model-limited and should be retested with a stronger local model or a configured cloud provider. Do not hide this failure with automatic padding, uncited prose, or server-authored fallback essays.

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

## PostgreSQL persistence and isolation

Run the opt-in integration test against the disposable database started by Compose. It creates two temporary users, verifies that each sees only its own session, confirms ordered message persistence, and removes its records afterward.

```bash
cd apps/api
RUN_POSTGRES_INTEGRATION=1 \
POSTGRES_INTEGRATION_URL=postgresql://lenny:lenny_local_password@127.0.0.1:5433/lenny_growth \
uv run pytest tests/test_database_integration.py -q
```

## Historical evidence

- The 40-case retrieval result remains a diagnostic baseline.
- The 14B direct/model gate and clean five-turn probe remain historical qualification evidence.
- The interrupted multi-session 14B file remains incomplete and must not be resumed or mixed with 8B results.
- Qwen3 8B has its own model-identified gate and release files.

## Cloud release run

The same 10-session, 50-turn suite can target the deployed Groq profile. The
runner signs in with an environment-supplied demo profile and does not persist
its signed tokens in the checkpoint.

```bash
cd apps/api
EVAL_API_URL=https://lennys-growth-api.onrender.com \
  EVAL_USERNAME=test1 EVAL_PASSWORD='<configured password>' \
  uv run python ../../evals/run_agent_eval.py --set release --provider groq \
  --model openai/gpt-oss-120b --limit 5 --turn-limit 3 \
  --run-id cloud-groq-release-5x3
```

Rate-limit fallback may use `openai/gpt-oss-20b`; each affected turn is
recorded with `fallback_reason_code=provider_rate_limited`. Do not count other
provider failures as successful fallback behavior.
