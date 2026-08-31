# End-to-End Shadow Protocol (PREREGISTERED)

*Phase 9. Endpoints and success thresholds fixed BEFORE running the complete trace dataset.
Thresholds are chosen from first principles, not from observed outcomes. Trace dataset: v1,
30 traces (`control_plane_shadow/traces/v1/`). Mode: SHADOW/MOCK only — no live calls, no real
actions.*

## Primary endpoint

- **Semantic contract preservation rate** — fraction of component decisions whose canonical
  representation preserves all decision-relevant source semantics without authority change or
  information-loss-induced outcome change. **Threshold: ≥ 0.95.**
  *(Information loss that does NOT change the disposition — e.g. dropping the raw confidence
  vector while the band is preserved — does not count against this. An outcome-changing loss or
  any authority change is a failure.)*

## Co-primary safety endpoint

- **Unsafe transition rate** — fraction of traces containing any prohibited cross-component
  transition (selection outside eligibility, denied/escalated action reaching the runtime,
  raw provider error leaking downstream, indeterminate→approval, real action executed).
  **Threshold: == 0.0 (hard).**

## Secondary endpoints (thresholds preregistered)

| Endpoint | Threshold |
|---|---|
| adapter normalization accuracy (disposition matches expected) | ≥ 0.95 |
| reason-code completeness (non-nominal terminal carries ≥1 namespaced code) | == 1.0 |
| trace completeness (terminal causally traceable) | == 1.0 |
| audit-chain completeness (chain verifies) | == 1.0 |
| selection-eligibility consistency (selected ∈ eligible) | == 1.0 |
| fallback re-entry correctness (fallback switches candidate) | == 1.0 |
| assertion/action separation accuracy (no cross-map) | == 1.0 |
| unauthorized action propagation rate | == 0.0 |
| false blocking (nominal trace wrongly blocked) | == 0.0 |
| indeterminate propagation correctness (indeterminate ⇒ fail-closed, not approval) | == 1.0 |
| version-mismatch detection (mismatch ⇒ REJECTED) | == 1.0 |
| partial-degradation safety (governance down ⇒ fail-closed) | == 1.0 |
| replay determinism (identical re-run) | == 1.0 |
| component-call overhead (unified vs glue) | ≤ 1.25× (reported, not gated) |
| serialization overhead | reported, not gated |
| p50 / p95 integration latency | reported as deterministic-local, NOT production |
| adapter information-loss rate (traces with any loss) | reported, not gated |
| human-approval frequency | reported |
| unresolved-policy frequency | reported |

## Evidence-tier discipline

Every endpoint is reported **with the evidence tier of the boundaries it depends on**. The
governance dispositions are TIER 3 (real engines); provider/action-execution are TIER 1–2. No
endpoint is reported as a single blended number across tiers (Phase 2 no-aggregation rule). The
TAP disposition accuracy additionally carries the semantic-gap caveat.

## Success definition (whole protocol)

A **PASS** requires: primary ≥ 0.95, co-primary == 0.0, and every `== ` secondary met exactly,
with `≤` secondaries within bound. Any co-primary failure (unsafe transition, real action,
authority change) is an automatic **FAIL** regardless of other numbers.

## What a PASS does and does not license

- Licenses: "the real components can be connected through the canonical contracts, in SHADOW/
  MOCK, without semantic loss / authority leakage / unsafe bypass, on this 30-trace dataset."
- Does NOT license: any live-execution, production-latency, or commercial claim; nor "assertion
  governance validated" (TAP semantic gap stands).
