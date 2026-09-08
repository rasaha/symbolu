# Changelog

## 0.6.0 — 2026-09-06 — front-door seam 7 (FD-11)

Contract `governed_review_service.v6`: the six routes plus one ledger read.

- `GET /review/audit/{correlation_id}` (`review_read_audit`): the deployment's own
  tenant's control-plane audit-ledger rows for one correlation id, in chain order,
  each as the ledger stored it (seq, entry_ref, kind, recorded_at, recorded_by,
  correlation_id, payload, prev_digest, record_digest), with the chain verification
  as the typed field `chain_verified`. A chain that does not verify is the typed
  `REFUSED_INTEGRITY` (409) with the entries withheld; a ledger at another schema
  version is `REFUSED_SCHEMA`; no composed reader is `REFUSED_UNCONFIGURED`; an unknown
  correlation id is 404; a malformed one is 422. There is no list-all route and no
  write. Requires `ugence-control-plane-root` 0.2.0 (`read_entries`).
- `ReviewService(ledger_reader=...)`, `read_audit`, `AuditLedgerReader`,
  `AuditReadOutcome`, `AuditReadResult`, `audit_view`.

## 0.5.0 — 2026-09-06 — front-door seam 6 (FD-10)

Contract `governed_review_service.v5`: the same five routes plus one start relay.

- `POST /review/runs` (`review_start_shadow_run`): asks the composition root's
  `ShadowRunStarter` for the deployment's own shadow run. The body carries at most a
  typed `correlation_id` and the word `mode: "shadow"`; any other key is 422, so no
  workflow, task, provider, mode or digest crosses (FD-10.3). Any other mode is the
  typed `REFUSED_MODE`; no composed starter is `REFUSED_UNCONFIGURED`; the starter
  reports `STARTED`, `REPLAYED` (the adapter's idempotency rule), `REFUSED_DEFINITION`
  or `REFUSED_CONFLICT`. Refusals answer 409 with the typed outcome.
- `ReviewService(starter=...)`, `start_shadow_run`, `StartOutcome`, `StartResult`,
  `ShadowRunStarter`, `start_view`. The service still holds no definition, provider or
  adapter `start` of its own: signal and resume remain the only adapter calls here.

## 0.4.0 — 2026-09-05 — AI-D (approver-identity ruling ID-2)

Contract `governed_review_service.v4`: the same five routes; the approval view and the
linkage view carry `authentication_reference`.

- A proven decision's `authentication_reference` is passed to the ledger's `decide()`
  and so recorded on the approval and in its hash-linked event; the outcome reports
  what the ledger recorded, so a replay under a fresh proof reports the standing
  reference.
- Linkages are appended as `governed_review.linkage.v2` (`LINKAGE_KIND`).
- `verify_authentication_reference(claims, recorded)`: identity-ADR row 9's recompute
  check, constant-time.

## 0.3.0 — 2026-09-05 — AI-A (approver identity port and proof shape)

Contract `governed_review_service.v3`: the same five routes; the decision route reads
one opaque proof header. Implements step AI-A of
`ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md` under rulings ID-2 to ID-5.

- `identity.py`: the service-local `ApproverIdentityPort` (ID-3), structurally
  compatible with Decision Authority's seam and importing nothing from it, with
  `VerifiedClaims`, `ApproverIdentity`, `ActorKind`, `TenantMode` and
  `RecordedAssurance`. `subject_reference` is issuer-qualified and percent-encoded;
  `authentication_reference` is a sha256 over the canonical verified claims and never
  over the proof (ID-2). `StaticApproverIdentityAdapter` is a fixture: it labels every
  answer `PRESENTED_UNPROVEN` and is refused in production mode.
- `service.py`: with a port configured, a proof is resolved and bound to the presented
  approver before any record is read or changed (identity-ADR rows 1, 2, 5, 6, 7); the
  tenant comes from the proof under an explicit tenant mode with the labelled
  `SINGLE_TENANT` fallback (ID-4, rows 4, 11, 12); `acr`/`amr` are recorded and never
  enforced (ID-5, row 10); replay is per proven subject (row 8).
  `authentication_reference`, `tenant_source` and `assurance` are carried on the
  outcome and on the durable `EXTERNAL_SIGNAL:review_decision` payload. Without a port
  nothing changes.
- `http.py`: the decision route reads one opaque proof header
  (`X-Ugence-Approver-Proof`), never echoed, logged or stored.
- `IDENTITY_PROOF` stays `PRESENTED_UNPROVEN`: no real adapter exists yet (AI-C), and
  the approval record and the linkage carry no reference yet (AI-D).

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
