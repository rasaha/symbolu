# H5 — Fairness Analysis Report (read-only, analysis-only)

## Boundary (§8–§9)
Fairness analysis is **read-only** and **strictly separated from decision authority**.
H5 adds no automated fairness approval, demographic rules, quotas, retraining, outcome
correction, fairness-based ActionGate policy, protected-class inference, or compliance
certification. Group labels / protected attributes are **analysis-only**, joined
separately (`CaseSpec.group_label` / `protected_attributes`) and **never** passed into
synthesis, recommendation, TAP, ActionGate, or execution.

## Leakage / counterfactual verification (§12)
- **Counterfactual invariance:** for a fixed case, varying only the analysis-only group
  label produces the **identical governed evidence-package fingerprint**
  (`test_h5_fairness::test_counterfactual_invariance…`, `…test_protected_attributes_never_enter_pipeline`).
- The operational pipeline is blind to prohibited attributes: the recommendation inputs,
  claims, authorization, and execution paths depend only on evidence, versions, policy,
  and provider results — not on group labels.

## Metrics (§10) — descriptive
Computed per analysis-only group (`ai_hiring/validation/fairness.py`): recommendation
review-ready rate, evidence-insufficiency rate, advancement/hold/reject rate, override
rate, authorization-denial rate, execution-failure rate, reconciliation-mismatch rate.
Reference-outcome metrics (precision/recall/FPR/FNR/calibration) are supported where a
labeled reference exists; the synthetic cohort does not assert a ground-truth reference,
so those are reported as not-applicable here.

## Interpretation discipline (§11)
Every result distinguishes observed vs statistically-supported vs operationally-meaningful
differences, and possible data-quality / evidence-availability / reviewer-behavior /
model / authorization artifacts. Sub-threshold groups (n < 10) are flagged
**descriptive only** with an explicit warning. The system is **not** labeled
"fair"/"unfair"/"unbiased"/"compliant".

## Finding (bounded cohort)
> Cohort too small for a statistically supported fairness conclusion; findings are
> descriptive only.

For a balanced synthetic cohort (≥10 per group, identical behavior) the analyzer emits:
> No material disparity was detected in this bounded validation cohort.
This wording is validated by `test_h5_fairness::test_no_material_disparity_wording_when_balanced`.
No aggregate fairness conclusion is drawn from the pilot.
