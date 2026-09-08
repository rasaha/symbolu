# Changelog

## [Unreleased] — the suite runs on Python 3.10, which this package already declared

No source change and no API change: `src/` is untouched and nothing about the package's
behaviour moves. The packaging/boundary test read `pyproject.toml` with a bare
`import tomllib`, stdlib only from 3.11 — so the whole module failed to import on 3.10
and, with every CI job pinned to 3.11, nothing ever noticed that
`requires-python >= 3.10` was a claim no job checked. The import now falls back to the
`tomli` backport, and the workflow's suite job runs the full matrix 3.10, 3.11, 3.12.
The fallback is a hard import rather than `pytest.importorskip`: a missing backport must
fail the run loudly, not quietly drop the packaging assertions from the 3.10 leg.

## 0.3.1 — 2026-09-08 — declared floor corrected

Metadata only: no source, contract or behaviour change.

- `ugence-approval-workflow` floor raised `>=0.1.0` -> `>=0.2.0`. `linkage.py` copies
  `ApprovalRecord.authentication_reference`, which arrived in approval-workflow 0.2.0
  (AI-D, ruling ID-2); the old floor could resolve a ledger with no such field. The
  source tree puts siblings on `PYTHONPATH`, so this was invisible to CI and would
  only have failed on a wheel install.
- `tests/test_boundaries.py` now pins the floor itself, not just the dependency name,
  so lowering it fails the suite.

## 0.3.0 — 2026-09-05 — AI-D (approver-identity ruling ID-2)

- `ReviewLinkage.authentication_reference`, copied from the approval record by
  `reconstruct()`; empty when the decision was recorded without a proof; part of the
  linkage digest like every other field.
- `LINKAGE_VERSION` is `governed_review.linkage.v2`: a field was added, so the shape is
  a new version. A v1 entry in a control-plane ledger stays valid and is not rewritten.

## 0.2.0 — 2026-09-05 — HR-E (contract only)

- `linkage`: `ReviewLinkage`, a frozen, digest-bound join of one parked-approved-resumed
  round trip across the approval ledger, the durable engine's event log and the
  checkpoint's execution-state journal; `reconstruct`, which performs that join by the
  ids HR-3 ratified and refuses, with a typed `LinkageError`, any join the stores do not
  support; projections onto the G4 contracts (`EvidenceReference` for the linkage,
  one `AuditReference` per joined entry). `LINKAGE_MATURITY = "CONTRACT_ONLY"`.
- Reads three stores, writes none. No store gains a column; clearance receipts are
  untouched; nothing is appended to the control-plane audit ledger (owner decision
  HE-1 in the human-review ADR).
- Tests: every refusal at unit level over the real SQLite ledger; one instance parked,
  decided, signalled, resumed and run, reconstructed from the real stores against a
  real PostgreSQL, with a deterministic digest across two reconstructions.

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
