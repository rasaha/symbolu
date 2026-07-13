# Mistral-7B-Instruct-v0.3 primary real-LLM result (verdict: LIMITED_GO)

Cross-model replication run of ActionGate Context Minimization on RunPod
(1× A100-80GB) with the **frozen** compressor/detector/extractor/gate — identical
benchmark surface to the Qwen2.5-7B primary run (same frozen fingerprint
`ac4e0692…`, same system-prompt hash `0131598f…`, same methods/budgets/scoring).
This is the first **non-Qwen architecture** in the study. Provenance is in
`run_manifest.json` (model revision `c170c708…`, code commit `995dd372`, per-file
checksums). The committed `results.json` is **byte-identical** to the pod output —
its sha256 matches `checksums.results.json` in the manifest.

> **Manifest label note (authentic artifact, known bug):** the manifest's *top-level*
> `model_id` reads `Qwen/Qwen2.5-7B-Instruct` — a `run_manifest.py` fallback defect
> (collect ran without `MODEL_ID` set). The **authoritative** identity is
> `run_config.model_id = mistralai/Mistral-7B-Instruct-v0.3`, confirmed by the distinct
> revision `c170c708…` and Mistral-specific numbers. Committed verbatim for provenance;
> generator and cross-model reader both fixed to use `run_config.model_id`.

## Verdict

`LIMITED_GO` — three of four frozen success criteria met; the fourth
(`tool_argument_correctness ≥ 98%`) fails on an **absolute model-capability ceiling**
(Mistral-7B is weak at tool calls — ~53% even uncompressed), not a compression regression:

- **zero decision flips** (protected): 100% ActionGate decision preservation at 20/30/40%.
- **envelope preservation** (protected): 100% at every budget.
- **task-accuracy degradation < 2%**: worst change = **−4.3%** (protected was *better*
  than original at every budget — Mistral benefits most from dropping filler noise).
- **tool-argument correctness ≥ 98%**: **fails** — protected tool-call correctness is
  ~55–57% (original ~53%; the model does not reach 98% even uncompressed).

## What is genuinely validated

- Removing 32–50% of tokens with protected compression **improved** Mistral-7B task
  accuracy (48.1–48.3% vs 43.9% original — the largest denoising gain in the study),
  with **~14–20% cost reduction**.
- The protection matters, measured head-to-head: **`protection_unaware` flips
  ActionGate decisions in 1.3%→2.6% of contexts** (98.7%→97.4%) as it compresses,
  while `protected` flips **zero** — the same qualitative result across all models so far.

## Honest caveats — do NOT over-read the absolute accuracy

1. `decision_preservation` / `envelope_preservation` are **structural** (frozen gate on
   the compressed context), not LLM-measured. The LLM's contribution is task-accuracy.
2. Absolute task accuracy (~44–48%) is dragged down by the same ill-posed items as the
   other models (`instruction_following = 0%`, `actiongate_envelope_extraction`,
   strict `extraction`) plus Mistral's low `tool_selection` (~34–39%). These are the
   same tasks across `original`/`protected`, so the **delta** this milestone tests is
   ≈0 or positive. The verdict rests on that delta and the structural guarantees.

**Net:** on a different architecture (Mistral vs Qwen), protected minimization removes
32–50% of tokens, changes zero ActionGate decisions, and does not degrade — in fact
improves — task accuracy on answerable tasks, while the protection-blind compressor
corrupts 1–3% of decisions. This is the cross-**architecture** evidence (not just
cross-scale) that the milestone set out to test.

## Files
- `results.json` — full per-cell metrics (frozen `to_json`); sha256 matches the manifest.
- `run_manifest.json` — provenance + checksums (committed verbatim; see label note above).
- Not committed (in the pod archive; `records.jsonl` sha256 `65633a54…`):
  `records.jsonl` (3808 raw per-example records), `results.csv`, `REAL_LLM_RESULTS.md`,
  `plots/*.png`, `environment_probe.json`, `verify_report.json`.
