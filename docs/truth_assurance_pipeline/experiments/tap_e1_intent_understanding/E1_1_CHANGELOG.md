# TAP-E1.1 — Changelog

## v1.1 (LLM Integration Validation)

*Validates that the TAP-E1 architecture works correctly when an LLM supplies the
interpretation — not the reasoning capability of the LLM itself. The code module keeps
the name `tap_e1_1_realmodel` for reproducibility.*

**Added** a self-contained validation track under
`truth_assurance_pipeline/tap_e1_1_realmodel/`. It imports the TAP-E1 layer UNCHANGED
(schema, extraction, provenance, ambiguity, conflict, clarification, metrics) and
replaces only the interpretation engine with an LLM.

- `model_client.py` — `ModelClient` abstraction: `AnthropicModelClient` (real API,
  ready), `CachedModelClient` (replays recorded outputs), `MockModelClient` (offline,
  tests only).
- `prompts.py` — the exact interpret-don't-answer prompt.
- `llm_interpreter.py` — composes a model core with the frozen TAP-E1 layers, baselines
  A–F.
- `corpus_v11/cases.py` — NEW independent 101-case corpus (no TAP-E1 prompt reused),
  constraints phrased without the deterministic extractor's cues; eval split
  content-hash locked (locked from scoring, but seen by the interpreter — not
  double-blind).
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
preregistered gates pass on the locked eval; verdict **`PASS_WITH_LIMITED_CLAIM`**.

**Supported claim:** the TAP-E1 architecture can successfully constrain, structure, and
evaluate LLM-generated intent representations under the conditions tested. The experiment
does **not** independently validate the reasoning capability of any particular language
model.

**Headline findings (integration, not model-capability):** with the LLM supplying the
core, constraint preservation on naturally-phrased requests rises from 0.60
(deterministic) to 1.00, overall fidelity from 0.54 to 0.94, and severe failures from 7
to 0 (eval and adversarial); raw LLM without the schema (A) is the *worst* configuration;
the clarification layer (F) over-asks and regresses.

**Primary limitation / honesty:** new synthetic corpus; the "LLM" is the in-session agent
(`claude-opus-4-8`), not an independently accessed API; the same model authored the
corpus and produced the interpretations, and the locked eval was seen by the interpreter
(author==interpreter confound, not double-blind); corpus below target size; latency not
measured. Claim limited accordingly. **TAP-E1 is frozen as the baseline;** future work
should compare against it. TAP-E1 code, corpus, results, and 30 tests are unchanged.
