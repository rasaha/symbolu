# Structured Field Prediction Diagnosis and Rescue — Report

**Decisive question:** which enterprise facts should be computed exactly, which genuinely require
multi-record quadratic reasoning, and can the system predict those typed facts accurately enough that
the already-validated deterministic mapper produces the correct outcome on unseen workflows?

**Answer:** **every field in this contract is a deterministic function of the exact retained
evidence.** Computing them exactly (F1) instead of learning them (F0) lifts held-out outcome accuracy
**0.64 → 1.00** and needs no quadratic readout. The rescue is **validated** on all §14 criteria.
Frozen output mapper verified (baseline commit `a4b01e2`).

## Results (held-out, K=8)

| arm | outcome acc | field macro | conflict F1 | IDs | unauth |
|---|---:|---:|---:|---:|---:|
| F0 learned typed heads (baseline) | 0.640 | 0.840 | 0.26 | 1.0 | 0.0 |
| **F1 deterministic exact** | **1.000** | 0.955 | 1.00 | 1.0 | 0.0 |
| F2 hybrid (det + quad for relational) | 1.000 | 0.955 | 1.00 | 1.0 | 0.0 |
| F5 deterministic over masked subsets | 1.000 | 0.955 | 1.00 | 1.0 | 0.0 |
| F6 oracle true fields | 1.000 | 1.000 | 1.00 | 1.0 | 0.0 |

Dev ≈ held-out (both 1.000 for F1) → generalizes to unseen entities/templates, no memorization.

## Diagnosis (§6) — which fields caused the failure

One-field oracle replacement (causal, not correlational), F0 → truth, ranked by final-accuracy gain:

| field | oracle gain | ownership |
|---|---:|---|
| **active_policy_status** | **+0.257** | relational |
| **material_conflict** | **+0.187** | relational |
| evidence_complete | +0.067 | deterministic |
| budget_status | +0.033 | deterministic |
| approval_status | +0.003 | relational |

The learned head's most damaging errors were the **relational** predicates (policy status, material
conflict) — exactly the multi-record facts. The deterministic extractor computes them **exactly** by
a bounded O(K) scan (F1 conflict F1 = 1.00). So the fix is not a better learner; it is to *compute*
these facts from the exact slot records.

## Causal controls (§12)

- **Leak-free routing:** field masks + deterministic extraction are invariant to full label
  perturbation (`label_invariant_routing = true`).
- **Support removal is causal:** base 1.00 → remove budget 0.42, remove active policy 0.61 (both
  materially damage the outcome).
- **Deterministic fields do not call the quadratic block** (test-enforced).

## Capacity (§11)

| K | F1 outcome acc | field macro |
|---|---:|---:|
| 4 | 0.733 | 0.821 |
| **8** | **1.000** | 0.955 |
| 16 | 1.000 | 0.955 |

K=4 is survival-limited (budget/active-policy do not always both fit); **K=8 is the smallest
sufficient set** and reaches 1.000. Larger K adds nothing. Field-specific masks (F5) match F1, so
per-field effective sets are even smaller than K.

## §14 acceptance (all pass)

field-macro gain +0.115 (≥0.10) ✓ · final-accuracy gain +0.36 (≥0.08) ✓ · wrong-field errors
reduced ≫40% ✓ · mapping error preserved 0.00 (F1→exact contract) ✓ · abstention preserved ✓ ·
conflict F1 1.00 (≥0.90) ✓ · evidence-ID 1.0 ✓ · unauthorized 0.0 ✓ · generalizes ✓ · K ≤ 8 ✓ →
**VALIDATED.**

## §15 final verdict

- **Frozen output mapper:** verified.
- **Primary failed field:** active_policy_status. **Secondary failed field:** material_conflict.
- **Error caused by missing support:** ~22% (K=4 survival); at K=8 support is present.
- **Error caused by reasoning/readout:** ~4.5% (residual F1 field-macro gap; does not change outcome).
- **Best field architecture:** F1 (deterministic exact); F2/F5 equal it.
- **Deterministic fields:** budget_status, approval_requirement, evidence_complete.
- **Relational fields:** active_policy_status, material_conflict, approval_evidence_status — multi-
  record, but **exactly computable** by bounded O(K) scan; quadratic prediction is **not required**.
- **Structured-field macro improvement:** +0.115. **Final mapped-accuracy improvement:** +0.36.
- **Best slot capacity:** K = 8.
- **Field-specific masking:** validated (F5 = F1). **Consistency constraints:** validated.
- **Evidence-ID preservation:** 1.00. **Unauthorized inclusion:** 0.00.
- **Primary remaining bottleneck:** **none** (held-out outcome accuracy = 1.00 at K=8).
- **Authorized architecture:** evidence ledger → deterministic joins → P5 shared binding slots →
  field-specific evidence masks → deterministic exact fields (+ bounded quadratic available for
  genuinely relational fields, though unneeded here) → typed consistency constraints → deterministic
  enterprise outcome mapper.

**Decisive answer:** in this bounded enterprise contract the typed facts should be **computed
exactly** from the exact retained evidence — none require a learned quadratic readout — and doing so
lets the already-validated deterministic mapper produce the **correct outcome (1.00) on unseen
workflows**, with provenance, access control, and abstention intact. Frozen Phase untouched (not used).
