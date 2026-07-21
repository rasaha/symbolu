# TAP-E1.1 — Changelog

## v1.1 (Real Model Validation)

**Added** a self-contained validation track under
`truth_assurance_pipeline/tap_e1_1_realmodel/`. It imports the TAP-E1 layer UNCHANGED
(schema, extraction, provenance, ambiguity, conflict, clarification, metrics) and
replaces only the interpretation engine with a real LLM.

- `model_client.py` — `ModelClient` abstraction: `AnthropicModelClient` (real API,
  ready), `CachedModelClient` (replays recorded outputs), `MockModelClient` (offline,
  tests only).
- `prompts.py` — the exact interpret-don't-answer prompt.
- `llm_interpreter.py` — composes a model core with the frozen TAP-E1 layers, baselines
  A–F.
- `corpus_v11/cases.py` — NEW independent 101-case corpus (no TAP-E1 prompt reused),
  constraints phrased without the deterministic extractor's cues; hidden split
  content-hash locked.
- `metrics_e11.py` — two documented, uniform metric corrections (paraphrase-invariant
  `invented_action`; material-ambiguity crediting). TAP-E1 `metrics.py` untouched.
- `harness.py` — baseline comparison, dev-only selection, preregistered comparative
  gates, verdict.
- `leakage_audit.py`, `metric_audit.py` — automated audits (both pass).
- `loader.py` — gold-free public loader.
- `cache/agent_model_outputs.jsonl` — 68 GENUINE in-session agent-model
  (`claude-opus-4-8`) interpretations (full eval/adversarial/negative + 20 dev).
- `experiments/` — `run_experiment_v11.py`, `preregistration_v11.json`,
  `eval_lock_v11.json`, `results_v11.json`, `build_agent_cache.py`.
- `tests/test_tap_e1_1.py` — 18 behavioral/audit/reproducibility tests.

**Result:** selected baseline **D** (LLM + deterministic extraction + provenance); all
preregistered gates pass on the hidden eval; verdict **`PASS_WITH_LIMITED_CLAIM`**.

**Headline findings:** the real model lifts constraint preservation on naturally-phrased
requests from 0.60 (deterministic) to 1.00, overall fidelity from 0.54 to 0.94, and
severe failures from 7 to 0 (eval and adversarial); raw LLM without the schema (A) is
the *worst* configuration; the clarification layer (F) over-asks and regresses.

**Honesty:** new synthetic corpus; the "real model" is the in-session agent
(`claude-opus-4-8`), not an independent API; the same model authored and interpreted the
corpus (author==interpreter confound); corpus below target size; latency not measured.
Claim limited accordingly. TAP-E1 code, corpus, results, and 30 tests are unchanged.
