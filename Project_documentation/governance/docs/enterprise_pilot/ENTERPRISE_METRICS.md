# Enterprise Metrics

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This defines *how success would be measured on real data*. It reports **no**
numbers — every value below is a **definition and a placeholder**. Filling these in
requires real records, real controls, and enterprise-supplied ground truth. We do
**not** fabricate or estimate any of them.

---

## 1. Principle

Metrics are only computed on **real** historical records with **enterprise ground
truth** ([`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md)) and against the
**enterprise's real baseline**
([`BASELINE_COMPARISON_FRAMEWORK.md`](BASELINE_COMPARISON_FRAMEWORK.md)). Until
then every cell is `TBD — requires real pilot data`. The synthetic shadow numbers
describe fixtures only and are never reported as enterprise metrics.

## 2. Metric families

### 2.1 Correctness (needs ground truth)

| Metric | Definition | Source | Value |
|---|---|---|---|
| Precision | TP / (TP + FP) over labeled instances | ground truth × findings | `TBD` |
| Recall | TP / (TP + FN) over `problematic` labeled instances | ground truth × findings | `TBD` |
| False-positive rate | FP findings / clean instances | frozen clean-workflow guard, real clean cases | `TBD` |
| Coverage of unknowns | findings on `unknown`-labeled instances | reported separately, not scored | `TBD` |
| Architecture-coverage gap | `problematic` classes that map to **no** frozen failure code | ground-truth adjudication | `TBD` |

TP/FP/FN are defined in [`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md) §5.

### 2.2 Net-new value (needs real baseline)

| Metric | Definition | Source | Value |
|---|---|---|---|
| Net-new findings | findings whose code ∉ `enterprise_baseline_codes` | `ShadowEvaluator` × real baseline | `TBD` |
| Net-new ratio | net-new / total findings | `shadow.py` `net_new_ratio` | `TBD` |
| Confirmed net-new | net-new ∧ ground-truth-confirmed problematic ∧ not caught existing | joint adjudication | `TBD` |
| Redundant findings | findings whose code ∈ `enterprise_baseline_codes` | `duplicate_of_existing_controls` | `TBD` |

The evaluator already emits `net_new_findings`, `net_new_codes`,
`duplicate_of_existing_controls`, and `net_new_ratio` (`shadow.py`); the pilot fills
the values from real runs.

### 2.3 Reuse / scalability (structural — measurable without ground truth, still on real workflows)

| Metric | Definition | Source | Value |
|---|---|---|---|
| Shared-invariant reuse | invariants (of the 11) firing unchanged across ≥2 real workflows | `shadow.py` `invariants_reused_across_workflows` | `TBD` |
| Workflows governed by same invariants | count of real workflows evaluated by the unchanged suite | `workflows_governed_by_same_invariants` | `TBD` |
| Adapter effort | new source dataclass + `evidence()` per source; no model change | onboarding log | `TBD` |

Reuse is the frozen scalability claim: the same 11 invariants (`INVARIANTS`) run
over every workflow without modification. On real data this is an **observation**,
not an efficacy claim.

### 2.4 Data honesty (always reportable)

| Metric | Definition | Source | Value |
|---|---|---|---|
| Missing-data rate | evidence records with `status == MISSING` / total | `shadow.py` `missing_data_rate` | `TBD` |
| Invented-value rate | must be **0 by construction** | adapter contract | `0` (invariant) |
| Disputed-verification rate | evidence with `verification == DISPUTED` | model | `TBD` |

`missing_data_rate > 0` is *good*: gaps are surfaced, not filled. `invented-value
rate` is structurally zero because adapters emit MISSING instead of guessing
([`SOURCE_ADAPTER_SPECIFICATION.md`](SOURCE_ADAPTER_SPECIFICATION.md) §1).

### 2.5 Disposition / promotion profile (operational)

| Metric | Definition | Source | Value |
|---|---|---|---|
| Net-new by disposition | counts across preventive/blocking/escalating/audit-only | `net_new_disposition` | `TBD` |
| Net-new by default promotion | counts across audit-only/warning/approval-required/hard-enforce | `net_new_default_promotion` | `TBD` |
| Preventive-before-invalid-execution | net-new `PREVENTIVE`/`BLOCKING` findings on instances that later materialized impact | ground truth × dispositions | `TBD` |

The last row is the strongest possible signal (a finding that *would have* preceded
a real bad outcome) and is exactly what the pilot success criteria call for. It is
`TBD` and cannot be asserted on synthetic data.

## 3. Success thresholds are set WITH the enterprise, not here

This document does **not** hard-code pass/fail thresholds. Per the pilot success
criteria ([`ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../actiongate/ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md) §8),
proceeding toward productization requires that real-data validation show: findings
not trivially available already; low, explainable false positives; shared
invariants reused across multiple real workflows; clear authority provenance;
actionable cross-vertical dependencies; measurable reconciliation/audit
improvement; and at least one preventive finding before an invalid execution. The
enterprise and the pilot team agree the concrete thresholds **before** the run,
recorded in the checklist ([`REAL_ENTERPRISE_PILOT_CHECKLIST.md`](REAL_ENTERPRISE_PILOT_CHECKLIST.md)).

## 4. Reporting rules

- Every reported number carries its **denominator, sample, and date**.
- Redundant (already-caught) findings are reported **before** net-new.
- `unknown`-labeled instances and architecture-coverage gaps are reported, never
  hidden.
- No metric is extrapolated beyond the sample; no ROI, detection-rate, or readiness
  claim is made from a single pilot.
- If a metric cannot be computed (missing labels, missing baseline), it stays `TBD`
  with the reason — it is never filled with a plausible guess.

## 5. Cross-references

- Ground truth: [`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md).
- Baseline / net-new: [`BASELINE_COMPARISON_FRAMEWORK.md`](BASELINE_COMPARISON_FRAMEWORK.md).
- Evaluator emitting these fields: `agentic/enterprise_governance/shadow.py`.
- Frozen success criteria: [`ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../actiongate/ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md) §8.
- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md).
