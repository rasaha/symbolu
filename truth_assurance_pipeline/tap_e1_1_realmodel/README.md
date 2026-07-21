# TAP-E1.1 — Real Model Validation

A validation track (not a new layer) for the frozen **TAP-E1 Intent Understanding
Layer**. The only variable under study is the interpretation engine: the deterministic
placeholder is replaced with a **real LLM**. Everything else (schema, deterministic
extraction, provenance, ambiguity, conflict, clarification, metrics) is imported
**unchanged** from `../tap_e1_intent/`.

> **Question:** does real-model reasoning genuinely improve intent understanding
> without increasing unsupported assumptions or reducing constraint preservation?

## Honesty (read first)

- No Anthropic API key exists here, so the real-model interpretations were produced by
  the **in-session agent model (`claude-opus-4-8`)** from the prompt only, and cached to
  `cache/agent_model_outputs.jsonl`. Real LLM interpretation — but **not** an
  independent API run.
- The **same model authored the corpus and interpreted it** (author==interpreter
  confound). This is the largest limitation and caps the claim.
- Corpus is synthetic and below the target size; latency is not measured; token counts
  are estimates.

## Layout

```
tap_e1_1_realmodel/
├── model_client.py     # AnthropicModelClient (real API) | CachedModelClient | MockModelClient
├── prompts.py          # the interpret-don't-answer prompt
├── llm_interpreter.py  # model core + frozen TAP-E1 layers; baselines A–F
├── metrics_e11.py      # 2 documented, uniform metric corrections (E1 metrics.py untouched)
├── harness.py          # comparison, dev-only selection, preregistered gates, verdict
├── leakage_audit.py    # automated leakage checks
├── metric_audit.py     # verifies E1 metrics unchanged + only 2 fields corrected
├── loader.py           # gold-free public loader
├── corpus_v11/         # NEW independent 101-case corpus (hidden split locked)
├── cache/              # 68 genuine agent-model interpretations (scored, frozen)
├── experiments/        # runner, preregistration, locks, results
└── tests/
```

## Run

```bash
# full experiment (deterministic, offline; replays the cached model outputs)
python -m truth_assurance_pipeline.tap_e1_1_realmodel.experiments.run_experiment_v11
# audits
python -m truth_assurance_pipeline.tap_e1_1_realmodel.leakage_audit
python -m truth_assurance_pipeline.tap_e1_1_realmodel.metric_audit
# tests
python -m pytest truth_assurance_pipeline/tap_e1_1_realmodel/tests/ -q
# regenerate the agent-model cache (idempotent; contents are agent-authored)
python -m truth_assurance_pipeline.tap_e1_1_realmodel.experiments.build_agent_cache
```

To run against a **real API**, set `ANTHROPIC_API_KEY`; `model_client.default_client`
then uses `AnthropicModelClient`, records outputs to the cache, and the harness scores
them identically.

## Result

Selected baseline **D** (LLM + deterministic extraction + provenance). All preregistered
gates pass on the hidden eval; verdict **`PASS_WITH_LIMITED_CLAIM`**. The real model
lifts constraint preservation 0.60 → 1.00, fidelity 0.54 → 0.94, and severe failures
7 → 0 vs the deterministic interpreter — but raw LLM without the schema (A) is the worst
configuration, and the clarification layer (F) regresses. See
[`E1_1_EXPERIMENT_REPORT.md`](../../docs/truth_assurance_pipeline/experiments/tap_e1_intent_understanding/E1_1_EXPERIMENT_REPORT.md).
