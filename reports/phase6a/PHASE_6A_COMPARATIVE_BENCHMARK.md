# Phase 6A — Comparative Governance Benchmark

- **Dataset:** `enterprise_pilot_v1` (hash `4d6de4294324a7b4…`, 90 scenarios, 3 domains) — reused unchanged from Phase 5I
- **Substantive digest:** `c180a0b9f0db8851…`
- **Fairness controls:** ALL PASS · **Benchmark invariants:** ALL PASS

## Measured result — normal mode

| Metric | No Governance | Action Only | Assertion Only | Full |
|---|---|---|---|---|
| Unsafe outcomes (total) | 27 | 6 | 15 | 0 |
| Unsupported assertion promotion | 1.0 | 0.666667 | 0.0 | 0.0 |
| Unsafe dispatch rate | 1.0 | 0.222222 | 0.555556 | 0.0 |
| Constraint violations | 3 | 0 | 3 | 0 |
| Obligation failures detected | 3 | 3 | 3 | 3 |
| Qualifier preservation rate | 0.0 | 0.0 | 1.0 | 1.0 |
| Governance-compliance visibility | 0.0 | 1.0 | 0.0 | 1.0 |
| Avg trace links | 0.0 | 6.0 | 4.0 | 5.3667 |
| Provider invocations (total) | 0 | 90 | 93 | 168 |
| Human reviews (total) | 0 | 9 | 3 | 12 |
| Total governance operations | 90 | 2805 | 1293 | 2718 |

## Scenario-class winners

- **ACTION_PROVIDER_FAILURE** — all strategies reached the same safe outcome
- **ASSERTION_PROVIDER_FAILURE** — all strategies reached the same safe outcome
- **BOTH_PROVIDERS_AVAILABLE** — all strategies reached the same safe outcome
- **CONSTRAINED_ASSERTION_CONSTRAINED_ACTION** — all strategies reached the same safe outcome
- **INDETERMINATE_ASSERTION_HUMAN_REVIEW** — best (fewest unsafe=0): Action Only, Full
- **ONE_PROVIDER_DEGRADED** — all strategies reached the same safe outcome
- **SUPPORTED_ASSERTION_ACTION_DENIED** — best (fewest unsafe=0): Action Only, Full
- **SUPPORTED_ASSERTION_AUTHORIZED_ACTION** — best (fewest unsafe=0): Action Only, Full
- **UNSUPPORTED_ASSERTION_NO_ACTION** — best (fewest unsafe=0): Assertion Only, Full

## Paired comparisons (net unsafe reduction, first vs second)

- **full_governance_vs_no_governance**: net unsafe reduction **27** (prevented 27, introduced 0) (mean 0.3, 95% CI [0.2111, 0.3889], seed 12345)
- **full_governance_vs_action_only**: net unsafe reduction **6** (prevented 6, introduced 0) (mean 0.0667, 95% CI [0.0222, 0.1222], seed 12345)
- **full_governance_vs_assertion_only**: net unsafe reduction **15** (prevented 15, introduced 0) (mean 0.1667, 95% CI [0.0889, 0.2444], seed 12345)
- **action_only_vs_no_governance**: net unsafe reduction **21** (prevented 21, introduced 0) (mean 0.2333, 95% CI [0.1444, 0.3222], seed 12345)
- **assertion_only_vs_no_governance**: net unsafe reduction **12** (prevented 12, introduced 0) (mean 0.1333, 95% CI [0.0667, 0.2111], seed 12345)

## Governance cost-effectiveness (structural workload, not ROI)

- **No Governance**: +0 ops vs No Governance, preventing 0 unsafe outcomes → None extra ops per unsafe prevented
- **Action Only**: +2715 ops vs No Governance, preventing 21 unsafe outcomes → 129.2857 extra ops per unsafe prevented
- **Assertion Only**: +1203 ops vs No Governance, preventing 12 unsafe outcomes → 100.25 extra ops per unsafe prevented
- **Full**: +2628 ops vs No Governance, preventing 27 unsafe outcomes → 97.3333 extra ops per unsafe prevented

## Failure-mode summary (fail-safe rate, applicable strategies)

| Profile | No Governance | Action Only | Assertion Only | Full |
|---|---|---|---|---|
| ACTIONGATE_MALFORMED_RESULT | n/a | 1.0 | n/a | 1.0 |
| ACTIONGATE_TIMEOUT | n/a | 1.0 | n/a | 1.0 |
| ACTIONGATE_UNAVAILABLE | n/a | 1.0 | n/a | 1.0 |
| EXECUTION_BUSINESS_REJECTION | 1.0 | 1.0 | 1.0 | 1.0 |
| EXECUTION_TIMEOUT | 1.0 | 1.0 | 1.0 | 1.0 |
| EXECUTION_UNAVAILABLE | 1.0 | 1.0 | 1.0 | 1.0 |
| MISSING_OBLIGATION_EVIDENCE | n/a | 1.0 | n/a | 1.0 |
| RECONCILIATION_MISMATCH | n/a | 1.0 | n/a | 1.0 |
| REGISTRY_RESOLUTION_FAILURE | n/a | 1.0 | n/a | 1.0 |
| TAP_MALFORMED_RESULT | n/a | n/a | 1.0 | 1.0 |
| TAP_TIMEOUT | n/a | n/a | 1.0 | 1.0 |
| TAP_UNAVAILABLE | n/a | n/a | 1.0 | 1.0 |

## Interpretation

**Measured result:** the full architecture prevented every unsafe outcome the no-governance baseline allowed (27 → 0); Action Only and Assertion Only each prevented a strict subset, and were additive — neither alone matched the full architecture.

**Benchmark-design consequence:** rates are shaped by the synthetic scenario prevalence in `enterprise_pilot_v1`; they are not real-world base rates.

**Architectural inference:** TAP and ActionGate govern disjoint failure modes (unsupported assertions vs unsafe/out-of-envelope actions); the full architecture is the only strategy with zero unsafe outcomes, at a measurable additional workload.

**Unvalidated real-world claim:** none. Deterministic reference providers are being measured — not production model accuracy. No regulatory-compliance or customer-ROI claim is made; a superior result here does not prove universal superiority.

