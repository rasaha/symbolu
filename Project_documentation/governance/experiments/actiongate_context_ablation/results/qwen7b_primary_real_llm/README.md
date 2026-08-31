# Qwen2.5-7B primary real-LLM result (verdict: GO)

First genuine real-LLM validation of ActionGate Context Minimization, run on RunPod
(1× A100-80GB) with the **frozen** compressor/detector/extractor/gate. Provenance is
in `run_manifest.json` (model revision, code commit `51284a39`, frozen fingerprint
`ac4e0692…`, per-file checksums). Files here were transcribed from the pod run
outputs; the authoritative content-hashes are those recorded in `run_manifest.json`.

## Verdict

`GO` — all four frozen success criteria met (evaluated automatically by
`real_llm_bench._success`, unchanged):

- **zero decision flips** (protected): 100% ActionGate decision preservation at 20/30/40%.
- **envelope preservation** (protected): 100% at every budget.
- **task-accuracy degradation < 2%**: worst drop = **−1.3%** (i.e. `protected` was
  *slightly better* than `original`, not worse).
- **tool-argument correctness ≥ 98%**: 100% for `protected` at every budget.

## What is genuinely validated (the new real-LLM signal)

- Removing 32–50% of tokens with protected compression did **not** degrade Qwen-7B
  task accuracy (55.0–55.5% vs 53.7% original — a slight improvement from dropping
  filler noise), with **~15–21% cost reduction** and flat latency.
- The protection matters, measured head-to-head: **`protection_unaware` flips
  ActionGate decisions in 1.3%→2.6% of contexts** (98.7%→97.4%) as it compresses,
  while `protected` flips **zero**.

## Honest caveats — do NOT over-read the absolute accuracy

1. `decision_preservation` and `envelope_preservation` are **structural** (computed
   by the frozen gate on the compressed context), not LLM-measured. The LLM's new
   contribution is the **task-accuracy** columns.
2. **Absolute task accuracy (~54%) is low and is a task/scorer-design artifact, not a
   compression or model failure.** `tool_selection`, `tool_argument_generation`, and
   `factual_qa` are all **100%**; the average is dragged down by three ill-posed items
   that ask for information **absent from the context**:
   - `instruction_following = 0%` and `actiongate_envelope_extraction ≈ 20–23%` ask for
     the ActionGate **operation enum** (e.g. `DB_MUTATION`), an internal mapping not
     present in the prompt — near-unanswerable by any model.
   - `extraction ≈ 33%` is exact-match strictness (Qwen says "a signed build artifact";
     the scorer wants `signed_artifact`).
   These low scores are **identical** for `original` and `protected`, so the **delta**
   (what this milestone tests) is ≈0. The `GO` rests on that delta and the structural
   guarantees — both sound — not on the ~54% absolute, which is uninformative.

**Net:** protected context minimization removes 32–50% of tokens, changes zero
ActionGate decisions, and does not degrade real Qwen-7B task accuracy on the
answerable tasks, while a protection-blind compressor corrupts 1–3% of decisions.
A meaningful *absolute*-utility number requires repairing the three mis-specified
tasks (drop/relax the operation-enum items; semantic-match `extraction`) and re-running
— a recommended next milestone, not a change to this frozen result.

## Files
- `REAL_LLM_RESULTS.md` — report + method×budget table + per-task breakdown.
- `results.json` — full per-cell metrics (frozen `to_json`).
- `run_manifest.json` — provenance + checksums.
- Not committed (available in the pod archive `primary_qwen7b.tar.gz`, records.jsonl
  sha256 `be4cae21…`): `records.jsonl` (3808 raw per-example records), `results.csv`,
  `plots/*.png`, `environment_probe.json`, `verify_report.json`, `SHA256SUMS`.
