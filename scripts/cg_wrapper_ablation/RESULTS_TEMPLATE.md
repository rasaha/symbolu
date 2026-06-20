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

## Paired B vs A (per set)

| Set | rate A | rate B | Δ (point) | 95% bootstrap CI | McNemar p | Significant? | Direction |
|-----|--------|--------|-----------|------------------|-----------|--------------|-----------|
| gsm8k_style | `<fill>` | `<fill>` | `<fill>` | `[<fill>, <fill>]` | `<fill>` | `<fill>` | `<fill>` |
| format_constraints | `<fill>` | `<fill>` | `<fill>` | `[<fill>, <fill>]` | `<fill>` | `<fill>` | `<fill>` |
| json_format | `<fill>` | `<fill>` | `<fill>` | `[<fill>, <fill>]` | `<fill>` | `<fill>` | `<fill>` |

## Verdict (from `metrics_report.py`)

**DECISION:** `<INERT_STOP | NO_EFFECT_DEPRIORITIZE | KILL_OR_RETRAIN | BENEFIT_RECORDED | INVESTIGATE_K0_HIDDEN_COUPLING>`

Mapping to pre-registered kill criteria:

- **K1 inert** (KL<1e-3 ∧ flip<0.5% ∧ corr/hidden<1e-2): `<yes/no>` → if yes, the wrapper is
  inert; it cannot help; **stop**.
- **K2 no measurable effect** (not inert; all CIs include 0 ∧ McNemar p>0.05): `<yes/no>` →
  deprioritize.
- **K3 regression** (any CI strictly negative ∧ p<0.05): `<yes/no>` → kill / flag retrain.
- **K4 benefit** (some CI strictly positive ∧ p<0.05 ∧ no K3): `<yes/no>` → benefit recorded
  with metric + effect size.

## Honest interpretation

`<2–4 sentences. State plainly what the objective metrics support. If inert/no-effect, say so.
Do NOT claim coherence/quality gains that the objective metrics do not show. Note any caveats
(e.g. untrained head, gate near init, no-KV-cache generation).>`

## Provenance

- Raw artifacts: `runs/cg_wrapper_ablation/<timestamp>/`
  (`config.json`, `raw_generations.jsonl`, `per_example_scores.jsonl`, `diagnostics.jsonl`,
  `summary.json`).
- Plan (pre-registered): `RESEARCH_PLAN.md`. Audit: `TASK1_AUDIT_FINDINGS.md`.
