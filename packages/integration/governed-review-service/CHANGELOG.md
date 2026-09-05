# Changelog

## 0.2.0 — 2026-09-05 — HE-1, HE-5

Contract `governed_review_service.v2`: the same five routes, two answers widened.

- `LinkageAppender`: after a recorded or replayed GRANT, and on every run-detail read,
  reconstructs the `ReviewLinkage` from the approval ledger, the durable event log and
  the checkpoint journal and appends it to the control-plane audit ledger
  (`ugence_control_plane_root`) as a `LedgerEntry` of kind `governed_review.linkage.v1`,
  payload `ReviewLinkage.to_dict()` plus `linkage_digest`, `recorded_by` the service,
  `recorded_at` from the injected clock. Returns G4's `AuditReference`.
- Idempotent per linkage digest: `LedgerLinkageIndex` reads the ledger's own rows,
  read-only, by the schema version the ledger declares, so a replayed decision or a
  repeated read never writes twice. `InMemoryLinkageIndex` is the reference port.
- Non-blocking: a `LinkageError` is the typed outcome `NOT_YET` on the decision and
  the run-detail read; the decision itself is never withheld or altered.
- `DecisionOutcome.linkage` and run detail's `linkages` expose the outcome, the
  linkage and the reference (HE-5). `RunReader.journal` added. No sixth route.
- Dependency added: `ugence-control-plane-root` (this package only; `governed-review`
  stays contract-only and its boundary test now forbids the import).

## 0.1.0 — 2026-09-05 — HR-C

First release. `REFERENCE_GRADE_SHADOW_ONLY`; `ENFORCEMENT_ENABLED = False`;
`IDENTITY_PROOF = "PRESENTED_UNPROVEN"`.

- `ReviewService`: queue listing (open proposal-bound approvals joined to the durable
  checkpoint; ESCALATE only, HR-5), run detail, run events, approval read, and
  `submit_decision`, which records a GRANT or REJECT by a presented approver through
  the ledger's own transitions and eligibility port, then delivers the adapter signal
  and, for a GRANT, the bounded resume for that instance only. Identical resubmission
  is a replay (row 1); any other second decision is refused.
- `DbosRunReader`: a read-only façade over the DBOS adapter's tables.
- `build_app`: the five audited routes, FastAPI as an optional extra.
- Tests: rows 1 and 5 at unit level; rows 5, 7, 8 and 9 inside the real DBOS adapter
  against a real PostgreSQL with the real ledger and the real approval-bound source;
  HTTP; boundaries.

Not in this release: an identity provider (no `decided_by` is proven), the studio
screens (HR-D), the receipt linkage (HR-E).
