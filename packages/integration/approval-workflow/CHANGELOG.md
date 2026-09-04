# Changelog — ugence-approval-workflow

## 0.1.0 — wave 2, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_APPROVAL_WORKFLOW_SCOPING.md`.

- `ApprovalSubject` and the derived approval id: the artifact binds to
  `(tenant_id, subject_kind, subject_digest)`, never to a policy pack (D-3).
- The state machine: `REQUESTED → PENDING → GRANTED | REJECTED | CHANGES_REQUIRED |
  EXPIRED | WITHDRAWN`, the bounded exception branch, and `GRANTED → CONSUMED`.
  Forward-only; `CHANGES_REQUIRED` is terminal and re-review needs a new digest.
- `EXPIRED` derived at read time from `Validity.status_at(as_of)`; no clock is read
  anywhere, asserted over the AST.
- The bounded, time-boxed exception grant; an unbounded exception is refused (D-2).
- `ApproverEligibilityPort` with `StaticApproverEligibility` as its reference
  adapter: eligibility only, never an identity check. `HUMAN` and `COMMITTEE` are the
  only kinds that may ever approve.
- `ConsumptionKey` (`approval_key.v1:`), `ConsumeOutcome` and its projection onto
  `IdempotencyKey` / `IdempotencyResolution`; exactly one consumption per approval,
  proved under threads and under separate processes.
- Two adapters (D-4): `InMemoryApprovalWorkflowStore`, refused in production mode,
  and `SqliteApprovalWorkflowStore` — WAL, `BEGIN IMMEDIATE`, a unique consumption
  key, and one append-only hash-linked `ledger_events` table.
- Neighbours unmodified: Decision Authority 1.0.0, Policy Workflow Compiler,
  cloud-scaling-operations 0.2.0, execution-reservation 0.1.0 (its ledger shape is
  copied, never imported).
- No ServiceNow or Jira mirror ships in this release.
