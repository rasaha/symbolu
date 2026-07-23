# Execution Eligibility Specification

*Phase 2 deliverable. Defines the typed eligibility state for every
`(provider, model, request)` combination, the per-condition checks, criticality classes,
and the fail-closed / configurable resolution rules. Implemented in
`execution_gate/eligibility.py` + `gate.py`.*

## Core principle: separate "can execute" from "should execute"

- **ExecutionGate** decides *can execute* → produces an `EligibilityDecision`.
- **ModelPolicy** decides *should execute* → selects among ELIGIBLE (and, where configured,
  CONDITIONALLY_ELIGIBLE) candidates only. **ModelPolicy never routes to an
  ExecutionGate-ineligible model.**

## Final eligibility states

| State | Meaning | ModelPolicy may select? |
|---|---|---|
| `ELIGIBLE` | All required conditions PASS with fresh, sufficient evidence. | Yes |
| `INELIGIBLE` | ≥1 required condition FAILS (or a critical condition is UNKNOWN under fail-closed). | **Never** |
| `CONDITIONALLY_ELIGIBLE` | All critical conditions PASS; one or more *non-critical operational* conditions are UNKNOWN or degraded, and policy permits conditional use. | Only if policy `allow_conditional=true`, and ranked below ELIGIBLE |
| `INDETERMINATE` | Evidence insufficient to decide and policy does not fail-closed for the unknown condition(s). Distinct from INELIGIBLE (we do **not** know it cannot execute) and from ELIGIBLE (we do **not** know it can). | No (must resolve first) |

**Unknown is never collapsed into ELIGIBLE.** Absent evidence yields INDETERMINATE or, for
critical conditions, INELIGIBLE (fail-closed) — never a silent pass.

## Per-condition checks

Each condition evaluates to `PASS | FAIL | UNKNOWN`, carries a **reason code** (Phase 3),
and cites **evidence** (source, timestamp, confidence, TTL).

| # | Condition | Class | On FAIL | On UNKNOWN (default) |
|---|---|---|---|---|
| 1 | `provider_reachable` | CRITICAL-OP | INELIGIBLE (`NETWORK_BLOCKED`/`DNS_FAILURE`/`TLS_FAILURE`) | fail-closed → INELIGIBLE |
| 2 | `authenticated` | CRITICAL-OP | INELIGIBLE (`AUTH_MISSING`/`AUTH_INVALID`) | fail-closed → INELIGIBLE |
| 3 | `credential_expiry_valid` | CRITICAL-OP | INELIGIBLE (`AUTH_EXPIRED`) | INDETERMINATE |
| 4 | `billing_active` | CRITICAL-OP | INELIGIBLE (`BILLING_INACTIVE`/`FREE_TIER_ONLY`) | INDETERMINATE (or fail-closed if `require_billing`) |
| 5 | `quota_available` | OPERATIONAL | INELIGIBLE (`QUOTA_EXHAUSTED`/`RATE_LIMITED`) | CONDITIONALLY_ELIGIBLE |
| 6 | `model_available` | CRITICAL-OP | INELIGIBLE (`MODEL_NOT_FOUND`/`MODEL_DISABLED`) | fail-closed → INELIGIBLE |
| 7 | `region_allowed` | CRITICAL-GOV | INELIGIBLE (`REGION_UNAVAILABLE`) | fail-closed → INELIGIBLE |
| 8 | `network_policy_allowed` | CRITICAL-GOV | INELIGIBLE (`NETWORK_BLOCKED`) | fail-closed → INELIGIBLE |
| 9 | `enterprise_policy_allowed` | CRITICAL-GOV | INELIGIBLE (`PROVIDER_NOT_APPROVED`) | **fail-closed → INELIGIBLE** |
| 10 | `data_residency_allowed` | CRITICAL-GOV | INELIGIBLE (`DATA_RESIDENCY_VIOLATION`) | **fail-closed → INELIGIBLE** |
| 11 | `required_features_supported` | CRITICAL-OP | INELIGIBLE (`FEATURE_UNSUPPORTED`) | fail-closed → INELIGIBLE |
| 12 | `context_length_sufficient` | CRITICAL-OP | INELIGIBLE (`CONTEXT_TOO_SMALL`) | fail-closed → INELIGIBLE |
| 13 | `structured_output_supported` | conditional-CRITICAL | INELIGIBLE (`FEATURE_UNSUPPORTED`) when request requires it | fail-closed if required |
| 14 | `tool_use_supported` | conditional-CRITICAL | INELIGIBLE (`FEATURE_UNSUPPORTED`) when request requires it | fail-closed if required |
| 15 | `latency_within_limit` | OPERATIONAL | INELIGIBLE (`LATENCY_LIMIT_EXCEEDED`) | CONDITIONALLY_ELIGIBLE |
| 16 | `reliability_within_limit` | OPERATIONAL | INELIGIBLE (`RELIABILITY_BELOW_THRESHOLD`/`PROVIDER_DEGRADED`) | CONDITIONALLY_ELIGIBLE |
| 17 | `projected_cost_within_limit` | CRITICAL-OP | INELIGIBLE (`COST_LIMIT_EXCEEDED`) | fail-closed → INELIGIBLE |

**Criticality classes:**
- **CRITICAL-GOV** (governance/compliance/legal: enterprise policy, residency, region,
  network policy): **always fail-closed** — UNKNOWN ⇒ INELIGIBLE. Never route on unproven
  compliance.
- **CRITICAL-OP** (correctness/spend safety: reachability, auth, model availability,
  features, context, cost): fail-closed by default (UNKNOWN ⇒ INELIGIBLE or INDETERMINATE
  per the table); never a silent pass.
- **OPERATIONAL** (transient/quality-of-service: quota, latency, reliability): configurable.
  UNKNOWN/degraded ⇒ CONDITIONALLY_ELIGIBLE by default, so capacity is not needlessly
  discarded, but the condition is recorded and ranked down.

## Decision aggregation (deterministic)

```
evaluate all conditions → {condition: (verdict, reason_code, evidence)}
if any CRITICAL-GOV verdict != PASS:                    → INELIGIBLE
elif any CRITICAL-OP verdict == FAIL:                   → INELIGIBLE
elif any CRITICAL-OP verdict == UNKNOWN:
        (fail-closed conditions)                        → INELIGIBLE
        (indeterminate conditions e.g. billing/expiry)  → INDETERMINATE
elif any OPERATIONAL verdict in {FAIL}:                 → INELIGIBLE
elif any OPERATIONAL verdict == UNKNOWN or degraded:    → CONDITIONALLY_ELIGIBLE
else:                                                   → ELIGIBLE
```

Precedence is fixed and total, so the same evidence always yields the same state — a
requirement for audit and replay.

## Evidence and staleness

Every condition verdict cites **evidence**: `source ∈ {live_probe, cache, config,
telemetry, provider_declared}`, `timestamp`, `confidence ∈ [0,1]`, `ttl_seconds`.
- Evidence older than its TTL is **stale** → the condition becomes UNKNOWN (it does not
  silently retain its last value). `TELEMETRY_STALE` is emitted.
- Conflicting evidence (two sources disagree) resolves by a fixed precedence:
  `live_probe > telemetry > cache > config > provider_declared`; the losing source is
  recorded for audit. A critical conflict with no live_probe ⇒ fail-closed.

## Configuration surface (non-scientific; operational policy)

- `allow_conditional` (bool): may ModelPolicy consider CONDITIONALLY_ELIGIBLE candidates.
- `require_billing` (bool): treat unknown billing as INELIGIBLE rather than INDETERMINATE.
- per-condition `ttl_seconds`, `latency_limit_ms`, `reliability_floor`, `cost_cap`.
- `fail_closed_conditions` (set): defaults include all CRITICAL-GOV and CRITICAL-OP
  correctness/spend conditions; may be tightened, never loosened below the CRITICAL-GOV set.

## Invariants (enforced by tests)

1. A CRITICAL-GOV UNKNOWN can never yield ELIGIBLE or CONDITIONALLY_ELIGIBLE.
2. INDETERMINATE is never selectable by ModelPolicy.
3. Every non-ELIGIBLE candidate exits with ≥1 reason code and cited evidence.
4. Given identical evidence + config, the decision is identical (determinism).
5. Stale evidence degrades to UNKNOWN, not to its last cached verdict.
