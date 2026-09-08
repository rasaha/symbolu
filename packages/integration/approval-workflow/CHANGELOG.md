# Changelog — ugence-approval-workflow

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

## 0.2.0 — 2026-09-05 — AI-D (approver-identity ruling ID-2)

- `ApprovalRecord.authentication_reference`: an additive, optional, digest-bound
  reference to the verified authentication claims behind `decided_by`; never a token.
  Serialised only when recorded, so every artifact digest computed before the field
  existed still re-derives. `signature_reference` stays unused.
- `decide(..., authentication_reference="")` on the port and both adapters. The SQLite
  ledger writes the reference into the hash-linked decision event's detail, so an
  altered reference breaks `verify_chain()` as an altered decision does; the record's
  artifact digest refuses an altered `decided_by` or reference on read.
- Nothing verifies the reference here: the package records it as it records
  `decided_authority_reference`.

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
- Composition-root integration tests for the Decision Authority seam
  (`complete_review` + `VersionedRef(kind="approval")`), skipped when pydantic is
  absent so the default suite runs dependency-free.
- Neighbours unmodified: Decision Authority 1.0.0, Policy Workflow Compiler,
  cloud-scaling-operations 0.2.0, execution-reservation 0.1.0 (its ledger shape is
  copied, never imported).
- No ServiceNow or Jira mirror ships in this release.
