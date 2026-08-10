# CG Wrapper Ablation — Results

> **STATUS: TEMPLATE (no GPU run yet).** Fill this in *verbatim* from
> `runs/cg_wrapper_ablation/<timestamp>/summary.json` after the RunPod run. Do not edit the
> pre-registered plan or kill criteria to fit the numbers — report the honest result, including
> "inert" / "no effect". No success is claimed on subjective grounds.

## Run metadata

| Field | Value |
|-------|-------|
| Run timestamp | `<fill>` |
| `MODEL_ID` | `<fill>` |
| `CG_CHECKPOINT` | `<fill>` |
| Checkpoint verdict (trained / untrained) | `<fill — from cg_checkpoint.verify>` |
| `DTYPE` / `DEVICE` | `<fill>` |
| Seeds | `<fill>` |
| Eval sets (N) | gsm8k_style (30), format_constraints (24), json_format (16) |
| Arms run | A_base, B_full, C_phase_off, D_gate0 [, E_csr if CSR present] |
| GPU | `<fill>` |

## Pre-registered sanity checks

| Check | Threshold | Observed | Pass? |
|-------|-----------|----------|-------|
| **K0** gate0 (arm D) == base | `max|Δlogit| ≤ 1e-4` | `<fill>` | `<fill>` |
| C − A (constant adapter bias) | reported, not a pass/fail | `<fill>` | — |

> If K0 fails: **STOP and investigate hidden coupling** before trusting any other number.

## Diagnostics (arm B / C / D vs base)

| Arm | mean logit KL | top-1 flip | mean gate | corr/hidden ratio | mean ΔBhava norm |
|-----|---------------|------------|-----------|-------------------|------------------|
| B_full | `<fill>` | `<fill>` | `<fill>` | `<fill>` | `<fill>` |
| C_phase_off | `<fill>` | `<fill>` | `<fill>` | `<fill>` | `<fill>` |
| D_gate0 | ~0 | ~0 | 0 | 0 | 0 |

## Task / format metrics (pass rate per arm)

| Set | A_base | B_full | C_phase_off | D_gate0 |
|-----|--------|--------|-------------|---------|
| gsm8k_style (exact-match) | `<fill>` | `<fill>` | `<fill>` | `<fill>` |
| format_constraints | `<fill>` | `<fill>` | `<fill>` | `<fill>` |
| json_format (parse+keys) | `<fill>` | `<fill>` | `<fill>` | `<fill>` |
| seed agreement (mean) | `<fill>` | `<fill>` | `<fill>` | `<fill>` |

## Paired comparisons (per set; Δ = cand − ref)

**B vs A** — does the active wrapper change task metrics vs base.

| Set | rate A | rate B | Δ(B−A) | 95% CI | McNemar p | Sig? | Dir |
|-----|--------|--------|--------|--------|-----------|------|-----|
| gsm8k_style | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |
| format_constraints | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |
| json_format | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |

**B vs C — DECISIVE** (ref = C phase-off / static offset; cand = B full). Δ>0 sig ⇒ CG-dynamic.

| Set | rate C | rate B | Δ(B−C) | 95% CI | McNemar p | Sig? | Dir |
|-----|--------|--------|--------|--------|-----------|------|-----|
| gsm8k_style | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |
| format_constraints | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |
| json_format | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |

**C vs A** — size of the static offset's own effect.

| Set | rate A | rate C | Δ(C−A) | 95% CI | McNemar p | Sig? | Dir |
|-----|--------|--------|--------|--------|-----------|------|-----|
| gsm8k_style | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |
| format_constraints | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |
| json_format | `<fill>` | `<fill>` | `<fill>` | `[<>,<>]` | `<fill>` | `<fill>` | `<fill>` |

**B vs C logit separation:** `KL(B‖C) = <fill>`, top-1 flip `= <fill>`. (≈0 ⇒ phase dynamics add
nothing beyond the static offset.)

## Training-side activation evidence (from the bootstrap probe log)

| Quantity | Final value | Note |
|----------|-------------|------|
| gate (σ) | `<fill>` | active ≈ 0.27+; pinned at 0.119 ⇒ ORIGINAL slipped through |
| corr/hidden ratio | `<fill>` | > 1e-2 ⇒ non-inert |
| adapter_weight_norm | `<fill>` | grew from ~2.0 ⇒ adapter trained |
| state_projector grad (sp_gn) | `<fill>` | collapsed to ~1e-8 ⇒ correction is largely static |

## Verdict (from `metrics_report.py`)

**DECISION:** `<INERT | ACTIVE_NO_EFFECT | REGRESSION | STATIC_OFFSET_NO_CG_DYNAMIC | WEAK_OBJECTIVE_GAIN | CG_DYNAMIC_SIGNAL | INVESTIGATE_K0_HIDDEN_COUPLING>`

- **K0 gate0==base:** `<pass/fail>`  **K1 inert:** `<yes/no>`  **B≈C:** `<yes/no>`
- **Warnings:** `<copy verdict.warnings, e.g. STATIC OFFSET / REGRESSION>`

Interpretation guide (which result continues vs parks the research):

- `CG_DYNAMIC_SIGNAL` (B>A **and** B>C, objective) → **continue** CG-wrapper research.
- `STATIC_OFFSET_NO_CG_DYNAMIC` (B≈C) → the CG dynamics do nothing; at best a constant bias. **Park.**
- `REGRESSION` → wrapper hurts. **Kill / retrain.**
- `ACTIVE_NO_EFFECT` / `WEAK_OBJECTIVE_GAIN` → no robust objective gain. **Deprioritize.**
- `INERT` (on a *trained* head) → checkpoint untrained/mis-loaded; re-verify before concluding.

## Honest interpretation

`<2–4 sentences. State plainly what the OBJECTIVE metrics support. If the decision is
STATIC_OFFSET / ACTIVE_NO_EFFECT / REGRESSION, say so — do NOT claim CG-dynamic or coherence gains
the metrics don't show. Note caveats: gate parked at init, state-projector grad collapse (static
offset), no-KV-cache generation, single dataset.>`

## Provenance

- Raw artifacts: `runs/cg_wrapper_ablation/<timestamp>/`
  (`config.json`, `raw_generations.jsonl`, `per_example_scores.jsonl`, `diagnostics.jsonl`,
  `summary.json`).
- Plan (pre-registered): `RESEARCH_PLAN.md`. Audit: `TASK1_AUDIT_FINDINGS.md`.
