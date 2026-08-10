# Control-Plane Invariants

*Phase 8. Twenty invariants the integrated architecture must hold. Each is enforced at
a named point and checked by a test (`control_plane/tests/`, Phase 14) and by the
scenario suite (`control_plane/scenarios.py`, Phase 9). The reference orchestrator
(`control_plane/orchestrator.py`) checks the structural ones at each hand-off and
terminates fail-closed on violation. "Test hook" names the scenario/test that would
fail if the invariant were violated.*

| # | Invariant | Enforced at | Violation code | Test hook |
|---|---|---|---|---|
| 1 | ModelPolicy cannot select an ExecutionGate-ineligible model | orchestrator post-selection check vs eligible_set | `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` | `inv1_selection_within_eligible` |
| 2 | A selected model must reference the exact eligibility decision used | contract C3 requires `eligibility_decision_id` | `MODEL.INVALID_SELECTION_INPUT` | `inv2_selection_cites_eligibility` |
| 3 | A provider adapter cannot change the selected model silently | orchestrator asserts `executed_candidate == selected_candidate` | `RUNTIME.UPSTREAM_EXCLUSION_BYPASSED` | `inv3_no_silent_substitution` |
| 4 | A technically successful output may still fail assertion governance | TAP runs after provider, independently of provider status | `ASSERT.ASSERTION_REJECTED` | `inv4_success_then_assert_reject` |
| 5 | Assertion approval does not imply action approval | ActionGate runs independently of assertion disposition | `ACTION.ACTION_DENIED` | `inv5_assert_ok_action_denied` |
| 6 | ActionGate cannot approve an action outside the request authority envelope | ActionGate checks `proposed_action ⊆ envelope.authority()` | `ACTION.ACTION_DENIED` | `inv6_action_within_authority` |
| 7 | A denied or escalated action cannot reach the action adapter | orchestrator gates adapter on `action_disposition == ALLOW` | `ACTION.ACTION_DENIED` / `ACTION.ACTION_APPROVAL_REQUIRED` | `inv7_denied_never_executes` |
| 8 | Human override must be explicit, attributable, and auditable | override requires `override_actor` + `override_rationale` in record | `AUDIT.UNAUTHORIZED_OVERRIDE` | `inv8_override_attributable` |
| 9 | Unknown critical policy state cannot become approval | unknown/indeterminate → fail-closed, never ALLOW | `POLICY.DATA_FLOW_NOT_APPROVED` | `inv9_unknown_not_approval` |
| 10 | A stale policy version cannot be silently upgraded mid-trace | versions pinned at layer 1, immutable for the trace | `POLICY.POLICY_VERSION_MISMATCH` | `inv10_versions_pinned` |
| 11 | Telemetry cannot rewrite prior decisions | AuditLog is append-only; no update API | `AUDIT.AUDIT_CHAIN_BROKEN` | `inv11_append_only` |
| 12 | Registry updates are prospective only | telemetry→registry contract C9 tags `target_registry_version` (future) | `RUNTIME.CIRCULAR_DEPENDENCY_DETECTED` | `inv12_registry_prospective` |
| 13 | Replay uses the historical policy and registry versions | replay engine reads pinned versions from records | `POLICY.REPLAY_VERSION_MISMATCH` | `inv13_replay_historical_versions` |
| 14 | Raw provider errors cannot substitute for normalized reason codes | only ProviderAdapter reads raw; normalizes to `RUNTIME.*` | `AUDIT.RAW_PROVIDER_ERROR_LEAKED` | `inv14_provider_error_normalized` |
| 15 | Audit failure blocks enforcement-mode execution where traceability is required | ENFORCEMENT checks audit write success before adapter | `AUDIT.TELEMETRY_WRITE_FAILED` | `inv15_audit_gates_enforcement` |
| 16 | No new external-provider data flow may be created implicitly | envelope carries `content_ref`; adapters fetch under policy only | `POLICY.DATA_FLOW_NOT_APPROVED` | `inv16_no_implicit_dataflow` |
| 17 | Assertions and actions must remain independently governable | separate TAP and ActionGate decisions, separate records | `POLICY.POLICY_CONFLICT` | `inv17_assert_action_independent` |
| 18 | Downstream success cannot retroactively validate an invalid upstream decision | each decision stands on its own record; no back-patching | `AUDIT.TRACE_INCOMPLETE` | `inv18_no_retroactive_validation` |
| 19 | Fallback must re-enter eligibility and policy evaluation | orchestrator routes fallback back to ExecutionGate, not around it | `RUNTIME.UPSTREAM_EXCLUSION_BYPASSED` | `inv19_fallback_reenters` |
| 20 | Every terminal outcome must be causally traceable | orchestrator writes a terminal record + verifies chain | `AUDIT.TRACE_INCOMPLETE` | `inv20_terminal_traceable` |

## Enforcement classes

- **Structural (orchestrator-checked at hand-off):** 1, 3, 6, 7, 9, 15, 19 — the orchestrator
  can detect and block these before the next component runs. These are the "downstream cannot
  bypass upstream" guarantees.
- **Contractual (contract-declared, validated at boundary):** 2, 10, 12, 13, 14 — encoded as
  required fields / version pins in `contracts.py`; a payload lacking them fails validation.
- **Component-owned (the authoritative component decides, orchestrator records):** 4, 5, 17 —
  the orchestrator must NOT pre-empt these; it only guarantees the decisions are made
  independently and both recorded.
- **Integrity (audit/telemetry substrate):** 8, 11, 16, 18, 20 — enforced by the append-only
  hash-chained log and content-minimization.

## Why these are the hard cases

Invariants 1, 3, 19 are the *bypass* guarantees — the entire reason an orchestrator exists
rather than a linear script: a downstream stage must never be able to reach past an upstream
exclusion. Invariants 4, 5, 17 are the *conflation* guarantees — the reason TAP and ActionGate
are separate components: "true" and "permitted to do" are different questions with different
owners. Invariants 11, 12, 20 are the *no-circularity* guarantees — telemetry improves future
routing without ever touching the decision in flight.

Falsification note (Phase 16): if a plain sequential script upheld all twenty as reliably as
the orchestrator, the orchestrator would add no value. The mock evaluation (Phase 15) tests
exactly that by running config (1) *disconnected glue* against these invariants.
