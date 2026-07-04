# Track F Implementation — Status

**Implementation built; no real run.** No LLM/scorer call, no network, no model download, no
scoring in this environment. `frozen/manifest.json` remains NOT_READY; the base Track F smoke
manifest stays `run_enabled:false` / `NOT_APPROVED`; psr runner NOT_RUN; Stage A untouched;
four-sphere JSON parked/not integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no
Sanskrit privilege. Prior negatives (Track C / D0 / Track E-flat) are unchanged and unrescued.

## What was built

| File | Role |
|---|---|
| `track_f_harness.py` | Inference-steering mechanics over SYNTHETIC judge scores (no LLM): per-arm means (X/A/B/F/I/[R]), deltas (`A_vs_X` magnitude; `A_vs_B`/`A_vs_I`/`A_vs_F` distinctness), correctness-preservation + usefulness + poetic-noise + hallucination gates, and the 7 allowed labels. `run_real_pilot()` raises. |
| `toy_fixtures/track_f_toy_cases.json` | 9 synthetic cases (7 label-producing + malformed + contamination). |
| `test_track_f_harness.py` | Synthetic tests — all passing. |
| `track_f_smoke_tasks.jsonl` | 12 real smoke tasks across 5 task types (target word in a hidden dev field). |
| `track_f_smoke_boundaries.jsonl` | per-task boundary texts for A/B/F/I/R (A/B composed from the frozen en_gloss table for draft consonant sequences). |
| `track_f_smoke_prompt_arms.jsonl` | 72 (task × arm) prompt-arm specs, length-recorded. |
| `track_f_smoke_manifest.json` | `run_enabled:false`, `approval_status:NOT_APPROVED`, `model:mistralai/Mistral-7B-Instruct-v0.3`, `four_sphere_integrated:false`, `track_b_status:BLOCKED`, hashes. |
| `run_track_f_smoke_mistral.py` | GPU runner: dry-run packet emission + leak scan (no model calls); under a separate approved config + env token, runs Mistral over the 72 packets and optional judge, writes outputs. Not runnable in the sandbox. |
| `track_f_smoke_approved_run_config.json` | Separate approved run config (`run_enabled:true` / `APPROVED`); base manifest stays gated. |
| `TRACK_F_SMOKE_OPERATOR_RUNBOOK.md` | Exact RunPod commands + abort checks. |

## Status statements

- **Track F implementation built** (harness, fixtures/tests, smoke bundle, dry-run runner, operator
  package). Dry-run verified: **72 packets, leak-clean, arm-randomized, no hidden labels, no
  four-sphere, 0 model calls.**
- **No real run yet.** No Mistral call has been made; no `track_f_smoke_outputs.json` exists.
- **Mistral selected for the smoke** as the answer model (`mistralai/Mistral-7B-Instruct-v0.3`,
  temp 0, JSON-only).
- **Single-model mode is exploratory** if judge separation is absent: with no distinct judge model,
  Mistral judging its own anonymized outputs is **weaker / exploratory-only** and is labelled as
  such in the config, runner, and result.
- **Track B blocked.**
- **Prior negatives preserved** — Track C / D0 / Track E-flat unchanged; Track F is a new question
  (inference steering), not a rescue.
- **Four-sphere not integrated** — remains a parked candidate artifact; a four-sphere Track F
  variant would be a separate prereg/config.

## What this is NOT

Not a run, not scoring, not an LLM call in this environment. Not validation and not a claim that
varṇa meanings are true. Even a full positive would be an engineering/prompting effect on this
model in this setup, capped further by the single-model-judge weakness until a proper answer ≠ judge
run is done.

---

Track F Mistral smoke implementation package created. No real Track F run has been executed. Track B remains blocked. Structure, not validated meaning.
