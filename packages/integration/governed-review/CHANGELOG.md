# Changelog

## 0.1.0 — 2026-09-05 — HR-A

First release. `REFERENCE_GRADE_SHADOW_ONLY`; `ENFORCEMENT_ENABLED = False`.

- `ApprovalBoundInputSource`: the production `GovernanceInputSource` that binds a
  human approval to a parked proposal's fingerprint (HR-3), raises the request on
  park, consumes a GRANTED approval exactly once under a per-instance, per-task
  consumption key before the engine advances, treats a same-holder
  `ALREADY_CONSUMED` as satisfied, and releases only the Decision Authority HOLD
  whose `required_approvals` the approval satisfied. ESCALATE only (HR-5).
- `binding`: the subject, consumer-reference and approval-id derivation.
- `composition`: helpers that wire the approval ledger over the authority
  directory's eligibility adapter.
- Tests: binding at unit level on the real SQLite ledger; failure-matrix rows 2, 3,
  6, 8 and 10 inside the real DBOS adapter against a real PostgreSQL; boundaries.

Not in this release: the review service (HR-C), the studio screens (HR-D), the
receipt linkage (HR-E), and the bounded adapter resume (HR-B, a durable-execution
change).
