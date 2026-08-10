# Evaluation Protocol (Phase 15)

*`reviewer_calibration_pilot/verify_evaluation_freeze.py` → `eval_results/evaluation_freeze.json`. Freezes
the sets, config, thresholds, and stop conditions before outcome-bearing review. The final set and the
frozen policy are not altered after evaluation begins.*

## Frozen surface (4 artifacts)

`training_v1/training.json`, `final_review_v1/final_review.json`, `data/manifest.json`,
`eval_results/dry_run.json`. `verify()` fails on drift.

## Frozen config

- **Frozen minimal policy** `minimal_evidence_policy_v1`; vocabulary E0–ER (read-only, never modified).
- Interface / runner / orchestrator versions; reviewer-guide version.
- **Reviewer roster: [] (empty); reviewer_count 0; training_completed False** — no real reviewers.
- Metrics, thresholds (acceptable-agreement ≥ 0.70, unsafe-allow disagreement ≤ 0.02, high-risk agreement
  ≥ 0.80, stricter-override ≤ 0.40, explanation usefulness ≥ 2.5, unresolved ≤ 0.20), stop conditions,
  adjudication rule, subgroup analyses.
- `human_validation = NOT_EVALUATED`; `external_pilot = BLOCKED`; `no_final_set_tuning = True`;
  `no_policy_change_during_review = True`.

## Freeze discipline

- The **final set is frozen** and never used to tune the policy.
- The **frozen minimal policy is not modified** during (the would-be) outcome-bearing review.
- Thresholds and stop conditions are frozen before review and not changed after it begins.

## Status

The evaluation is frozen and ready. Because the reviewer roster is empty, the outcome-bearing review
(Phase 16) does not run and `human_validation` is pre-committed as `NOT_EVALUATED` with `external_pilot =
BLOCKED` — frozen here, before any review, so the terminus cannot be adjusted after the fact.
