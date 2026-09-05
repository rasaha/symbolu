# Changelog

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
