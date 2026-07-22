# TAP-E4 — Metrics

Every metric is reported **separately** (never one aggregate score), and the ten
critical-failure classes are counted **independently** of the pass/fail metrics — a high
average can never hide a safety-critical governance error.

## Accuracy metrics

| Metric | Denominator | Definition |
|---|---|---|
| `governing_authority_accuracy` | all cases | selected authority == gold (`None` matches `None`) |
| `jurisdiction_accuracy` | jurisdiction + no_governing cases | correct selection under jurisdiction filtering |
| `scope_accuracy` | scope cases | correct selection under scope filtering |
| `temporal_accuracy` | expired + superseded + future cases | never selects a non-effective authority |
| `version_accuracy` | version cases | selects the most recent version |
| `exception_accuracy` | exception cases | status `GOVERNING_WITH_EXCEPTION` + no residual obligation |
| `precedence_accuracy` | override + law + draft cases | correct precedence winner |
| `governance_conflict_f1` | all cases | binary conflict present/absent, P/R/F1 |
| `governance_gap_accuracy` | all cases | expected gaps ⊆ emitted; no fabricated blocking gap |
| `provenance_completeness` | selected-authority cases | complete provenance chain |

> **Denominator note (honesty).** The per-dimension accuracies are computed **only over the
> family that exercises that dimension** (e.g. `temporal_accuracy` over the expired/
> superseded/future cases). This is a *matched-family* denominator, not an end-to-end one:
> it measures whether the mechanism handles that dimension correctly where it is tested, not
> that governance is solved in general. `governing_authority_accuracy` is the end-to-end
> number over all cases.

## Safety-rate metrics

| Metric | Definition |
|---|---|
| `unsupported_governance_rate` | fraction with a selected authority but no supporting relationship |
| `incorrect_override_rate` | fraction where a contract/policy wrongly overrode a higher authority (incl. law) |
| `expired_policy_selection_rate` | fraction selecting an expired authority |

## Independent critical failures (all severe)

`EXPIRED_POLICY_SELECTED`, `SUPERSEDED_POLICY_SELECTED`, `DRAFT_SELECTED`,
`WRONG_JURISDICTION`, `EXCEPTION_IGNORED`, `CUSTOMER_OVERRIDE_IGNORED`,
`LAW_OVERRIDDEN_BY_POLICY`, `MISSING_PROVENANCE`, `UPSTREAM_GAP_IGNORED`,
`UNSUPPORTED_GOVERNANCE_DECISION`. Their sum is `severe_critical_failure_count`, gated to
`== 0`. Each is detected from the case's gold disqualifiers and the actual decision — not
inferred from the accuracy numbers.

## Preregistered gates (14) and results (locked eval, selected baseline F)

| Gate | Op | Threshold | F |
|---|---|---|---|
| governing_authority_accuracy | ≥ | 0.90 | **1.00** |
| jurisdiction_accuracy | ≥ | 0.90 | **1.00** |
| scope_accuracy | ≥ | 0.90 | **1.00** |
| temporal_accuracy | ≥ | 0.95 | **1.00** |
| version_accuracy | ≥ | 0.90 | **1.00** |
| exception_accuracy | ≥ | 0.90 | **1.00** |
| precedence_accuracy | ≥ | 0.90 | **1.00** |
| governance_conflict_f1 | ≥ | 0.75 | **1.00** |
| governance_gap_accuracy | ≥ | 0.75 | **1.00** |
| provenance_completeness | == | 1.00 | **1.00** |
| unsupported_governance_rate | ≤ | 0.05 | **0.00** |
| incorrect_override_rate | == | 0.00 | **0.00** |
| expired_policy_selection_rate | == | 0.00 | **0.00** |
| severe_critical_failure_count | == | 0.00 | **0.00** |

## Ablation ladder (DEV) — why F is required

| Metric | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| governing_authority_accuracy | 0.13 | 0.27 | 0.47 | 0.73 | 0.93 | **1.00** |
| jurisdiction_accuracy | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| scope_accuracy | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| temporal_accuracy | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | **1.00** |
| version_accuracy | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | **1.00** |
| exception_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| precedence_accuracy | 0.00 | 0.50 | 0.50 | 0.50 | 1.00 | **1.00** |
| governance_conflict_f1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |
| governance_gap_accuracy | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 | **1.00** |
| severe_critical_failure_count | 9 | 7 | 5 | 3 | 1 | **0** |

Each rung fixes exactly what it adds and no more: C fixes jurisdiction/scope but still
selects expired/superseded/future; D fixes temporal/version but ignores exceptions and
customer/emergency override; E resolves precedence but silently picks a winner on genuine
ties and drops conflict/gap reporting (leaving one severe `UPSTREAM_GAP_IGNORED`); only F
surfaces conflicts, preserves gaps, and reaches zero severe failures. **F is the simplest
configuration passing all gates.**
