# Existing Implementation Disposition

## Robotics Autonomous Control Plane (`symbolu_robotics/autonomous_control_plane/`)

| Disposition tag | Value |
|---|---|
| Relationship | `SEPARATE_CAPABILITY` |
| Source treatment | `NOT_A_SOURCE_MOVE` |
| Compatibility | `NO_COMPATIBILITY_ALIAS` |
| Freeze | `LOCAL_FREEZE_UNCHANGED` (combined digest `8f8660e293308cf94c983a26a2ae69c9`; verified byte-accurate) |

Reusable **only as engineering-pattern evidence**:

- deterministic evaluation (pure functions of inputs),
- injected time (explicit `*_time_s` floats; no wall clock),
- fail-closed behavior,
- policy fixtures (fixed-clock authored scenarios),
- adapter separation (target logic in adapters, neutral core).

**Not reused:** the grant-minting authority semantics (`ControlAuthorization`, `ReferenceControlAuthorizer`).
Action Clearance is clear-only ([`AUTHORITY_BOUNDARY.md`](AUTHORITY_BOUNDARY.md)); it does not mint
grants. No robotics module is moved, imported, aliased, or re-exported; the robotics local freeze and the
`acp_k8s_integrated` pin are untouched.

## Console clearance (`ugence_console_api/capabilities/operational_safety.py`)

| Disposition tag | Value |
|---|---|
| Relationship | `BEHAVIORAL_REFERENCE` |
| Future role | `POTENTIAL_FUTURE_CONSUMER` |
| Canonical? | `NOT_AUTOMATIC_CANONICAL_SOURCE` |

Preserve the principle it already embodies: **Authorize → Clear → Record**. Its `clear(OperationalSignals)
→ ClearanceVerdict{CLEAR|HOLD}` is the literal clearance step, but it is 63 lines with hard-coded infra
thresholds — a domain reference, not a neutral core to lift.

**Future migration path** (after the canonical package exists): the console becomes a **consumer** of
`ugence_action_clearance` via a console profile + signal adapter (its `error_budget`/`cluster_health`/
`change_freeze` become `TrustedSignal`s); its `CLEAR`/`HOLD` maps onto the four core statuses. The
console's own types are **not** promoted to neutral contracts automatically; migration is a later,
separate, behavior-equivalence-verified step.

## Database clearance adapter (`cer_v0_3/acp_db/`)

Classification: a **future profile / adapter**. It already reuses the frozen robotics `compose()` and
adds DB-specific freshness/freeze/expiry checks. In the target architecture those become a **DB
clearance profile** + DB signal adapter over the neutral core. **No runtime migration occurs now**; it
is neither deprecated nor moved in this phase.

## Summary

Nothing is moved or migrated in this phase. All three are recorded as sources of *pattern* (robotics),
*behavior* (console), and *future profile* (acp_db). The canonical package is defined fresh; existing
implementations migrate onto it later, each behind a behavior-equivalence gate, with the robotics core
remaining a separate, frozen, uncoupled capability.
