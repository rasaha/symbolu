# Qwen2.5-14B primary real-LLM result (verdict: LIMITED_GO)

Cross-model replication run of ActionGate Context Minimization on RunPod
(1× A100-80GB) with the **frozen** compressor/detector/extractor/gate — identical
benchmark surface to the Qwen2.5-7B primary run (same frozen fingerprint
`ac4e0692…`, same system-prompt hash `0131598f…`, same methods/budgets/scoring).
Provenance is in `run_manifest.json` (model revision `cf98f3b3…`, code commit
`0e593103`, per-file checksums). The committed `results.json` is **byte-identical**
to the pod output — its sha256 matches `checksums.results.json` in the manifest.

> **Manifest label note (authentic artifact, known bug):** the manifest's *top-level*
> `model_id` reads `Qwen/Qwen2.5-7B-Instruct`. That is a defect in `run_manifest.py`
> (it fell back to the default `MODEL_ID` because `collect_results.sh` ran without the
> env set). The **authoritative** identity is `run_config.model_id =
> Qwen/Qwen2.5-14B-Instruct`, and the distinct revision `cf98f3b3…` and distinct
> per-task numbers confirm this is genuine 14B output. The manifest is committed
> verbatim (not hand-edited) for provenance; the generator and the cross-model reader
> have both been fixed to use `run_config.model_id`.

## Verdict

`LIMITED_GO` — three of four frozen success criteria met; the fourth
(`tool_argument_correctness ≥ 98%`) fails on an **absolute model-capability ceiling**,
not a compression regression:

- **zero decision flips** (protected): 100% ActionGate decision preservation at 20/30/40%.
- **envelope preservation** (protected): 100% at every budget.
- **task-accuracy degradation < 2%**: worst change = **−1.6%** (protected was *slightly
  better* than original at every budget).
- **tool-argument correctness ≥ 98%**: **fails** — protected tool-call correctness is
  ~89.9% (original itself is ~91.7%; the 14B model does not reach 98% even uncompressed).

## What is genuinely validated

- Removing 32–50% of tokens with protected compression did **not** degrade Qwen-14B
  task accuracy (58.1–58.8% vs 56.4% original), with **~12–18% cost reduction**.
- The protection matters, measured head-to-head: **`protection_unaware` flips
  ActionGate decisions in 1.3%→2.6% of contexts** (98.7%→97.4%) as it compresses,
  while `protected` flips **zero** — the same qualitative result as Qwen-7B.

## Honest caveats — do NOT over-read the absolute accuracy

1. `decision_preservation` / `envelope_preservation` are **structural** (frozen gate on
   the compressed context), not LLM-measured. The LLM's contribution is task-accuracy.
2. Absolute task accuracy (~56–59%) is dragged down by the same three ill-posed items
   as the 7B run (`instruction_following = 0%`, `actiongate_envelope_extraction ≈ 25–32%`
   ask for information absent from the prompt; `extraction ≈ 41%` is exact-match strict).
   These are **identical** across `original`/`protected`, so the **delta** this milestone
   tests is ≈0 (in fact slightly positive). The verdict rests on that delta and the
   structural guarantees, not on the ~56% absolute.

**Net:** at 14B scale, protected minimization removes 32–50% of tokens, changes zero
ActionGate decisions, and does not degrade task accuracy on answerable tasks, while the
protection-blind compressor corrupts 1–3% of decisions — replicating the 7B finding at a
larger scale.

## Files
- `results.json` — full per-cell metrics (frozen `to_json`); sha256 matches the manifest.
- `run_manifest.json` — provenance + checksums (committed verbatim; see label note above).
- Not committed (in the pod archive; `records.jsonl` sha256 `4d2b3a5b…`):
  `records.jsonl` (3808 raw per-example records), `results.csv`, `REAL_LLM_RESULTS.md`,
  `plots/*.png`, `environment_probe.json`, `verify_report.json`.
