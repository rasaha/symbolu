# Evaluation Protocol (Phase 20)

*`minimal_evidence_policy/verify_evaluation_freeze.py` → `eval_results/evaluation_freeze.json`. Freezes
the dataset, artifacts, config, and criteria before the final evaluation. Criteria are not altered after
it begins.*

## Frozen surface (11 artifacts)

Dataset: development / held_out_natural / adversarial_invariants / human_review_set / manifest. Eval:
baselines / error_propagation / frontier / ablation / review_study / internal_pilot. `verify()` fails on
any drift.

## Frozen config

Policy `minimal_evidence_policy_v1`; vocabulary E0–ER; risk mapping low→E1…critical→E4, unknown→ER; 7
modifiers; 12 invariants; baselines A–O + Full_minimal; safety + utility endpoints; `human_validation =
NOT_EVALUATED`; `score_once`, `no_tuning_on_held_out`, `no_threshold_mutation_of_frozen_components`.

## Preregistered success criteria

| Criterion | Threshold |
|---|---|
| clean allow above prior 0% | > 0.20 |
| over-qualification reduced | < 0.65 |
| no high-risk unsafe allows | == 0 |
| no action unsafe allows | == 0 |
| zero self-verification escape | == 0 |
| monotonic | 0 violations |
| within complexity budget | policy-logic rules ≤ 20 |
| bounded review burden | review_rate < 0.25 |
| beats risk-only and rich on safety | fewer total unsafe than D and I |
| no frozen-component changes | guard passes |

## Kill criteria

Any high-risk/action unsafe allow; any self-verification escape; any monotonicity violation; no utility
improvement (clean ≤ prior 0). Any one halts the pilot.

## External pilot

`external_pilot = BLOCKED` — human validation is NOT EVALUATED, so the protocol pre-commits that the
final evaluation cannot recommend an external customer pilot regardless of the technical result. This is
frozen before the final evaluation, not decided after seeing it.
