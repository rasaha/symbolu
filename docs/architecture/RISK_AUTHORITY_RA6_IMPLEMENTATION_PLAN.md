# Risk Authority RA-6 — Implementation Plan (Design Companion)

> **Status:** DESIGN COMPANION to the ratified `RISK_AUTHORITY_RA6_SPEC.md`.
> **Type:** DOCUMENTATION ONLY. Nothing here is built by this document; it
> sequences a *future*, separately-reviewed implementation milestone. In any
> conflict, the SPEC governs.
> **Baseline:** default head `ad3a2a46`. RA-1→RA-4, RA-4.5, RA-5 merged.

This plan translates the SPEC's ratified decisions into a build order. It changes
no code. Section references (§) point into `RISK_AUTHORITY_RA6_SPEC.md`.

## A. Separation of concerns (what goes where)

| Layer | Package | RA-6 additions | Constraint |
|---|---|---|---|
| Neutral leaf | `ugence-risk-authority` | port Protocols `AuthorityStatusReader`, `AuthorityLifecycleWriter`, `AuthorityReassessmentSignalPort`; `AuthorityStatus` / `AuthorityReassessmentSignal` value types; keep `RevocationState` predicate pure | **stdlib-only**; no persistence/messaging/service clients |
| Control plane | `ugence-risk-authority-status-runtime` **(NEW sibling)** | persistence-backed reader + cache sync; authenticated writer service; signal-reassessment intake; driven case-state transitions | one-way import → leaf; owns all server deps |
| Hot path | `ugence-risk-authority-runtime` (RA-4.5) | **none** — consumes read-only `AuthorityStatusReader` (already threads `RevocationState`, `risk_authority_enforcer.py:71,95`) | unchanged; no write capability |

## B. Build order (each step independently reviewable & backward-compatible)

1. **Leaf ports & types (no behavior change).** Add the three neutral Protocols
   and the `AuthorityStatus` (+ freshness: `as_of`, `initialized`) and
   `AuthorityReassessmentSignal` value types to `risk_authority.integrations` /
   `risk_authority.services`. Leaf stays stdlib-only; existing 97-test baseline
   unchanged. (Closes R-1's leaf-side contract; the init/`as_of` metadata is
   carried by the production wrapper, §3.3.)

2. **Persisted authoritative store.** Implement the reserved DDL —
   `revocations(tenant_id, kind, target_id, epoch, created_at)` and tenant-epoch
   rows (`persistence/postgres.py:28`). Strongly-consistent, serialized-per-tenant,
   monotonic writes (§4). Seed `epoch=1` per tenant, empty revocation sets (§16).

3. **Status reader + edge cache sync.** Implement `AuthorityStatusReader` over a
   local bounded-stale snapshot fed by event propagation + periodic pull-sync
   (§4). Snapshot carries `as_of` and an **initialized** flag; UNINITIALIZED ⇒
   DENY (§3.3). Hot path reads the cache only (offline).

4. **Risk-tier staleness policy (behind a flag).** Wire Policy C (§3): derive tier
   from the envelope's case `residual_risk`; apply `max_staleness(T)` (tenant
   config under platform ceiling). Ship fail-closed defaults. Enable last, after
   caches are proven to sync (§16 rollout step 4).

5. **Authenticated lifecycle writer.** Implement `AuthorityLifecycleWriter`
   (§12.2): authenticated principal + `AuthorityLifecycleWriter` grant check
   (reuse `AuthorityRegistry`/`AuthorityGrant`), per-write append-only
   `GovernanceEvent`, tenant isolation, rate limiting, idempotent revoke (union)
   and idempotent `advance_epoch(change_id)` (closes R-2). Fail closed without an
   authenticated principal.

6. **Signal intake + reassessor.** Implement `AuthorityReassessmentSignalPort`
   (§12.3, §13): durable intake, dedupe by `event_id`, validate (malformed ⇒
   `IGNORE_EVENT` + DLQ), then run reassessment against **current** authoritative
   state → possibly call the writer. Default path = reassess (§6);
   `TENANT_EMERGENCY_STOP` = privileged direct write.

7. **Driven case-state transitions.** Wire the drivers of `ACTIVE →
   {EXPIRED,REVOKED,SUPERSEDED}` (§11): a time-based reaper for `EXPIRED`; the
   writer for `REVOKED`; re-issuance for `SUPERSEDED`. Reuse existing event types
   (§11) — no new type required.

8. **Last-mile recheck (consequential actions).** Extend the Agent Runtime
   clearance the runtime already re-validates per transition
   (`validate_clearance`, `decisions.py:76-123`) so the pre-effect check covers
   **epoch + revocation** via `AuthorityStatusReader`, not expiry alone (§8).
   Valid-through-commit-point semantics; no lease/nonce; no polling. (This is the
   one step that touches the Agent Runtime seam and must be scoped/reviewed
   accordingly — it is *out of scope for the ratification*, in scope for the
   milestone.)

## C. Conformance gate (the milestone is accepted iff)

- The 28-row deny-heavy matrix (SPEC §17) passes, deny-heavy rows fail-closed.
- Invariants I1–I14 (SPEC §15) hold, with adversarial tests for I3 (no epoch
  rollback), I4 (no revoked→ACTIVE), I11 (stale epoch), I12 (unauthorized write),
  I13/I14 (idempotent/monotonic).
- RA-1→RA-4 (97) and RA-4.5 (77) baselines remain green; RA-5 suites remain green.
- `ugence-risk-authority` remains a stdlib-only, independently-installable leaf
  (isolated `--no-index` install proof, mirroring RA-4.5/RA-5).
- No second authority artifact; the Ed25519 envelope remains the sole authority.

## D. Explicitly deferred (not this milestone)

Producer cryptographic attestation / signatures on signals and status; HSM/KMS;
per-workflow / per-policy epoch dimensions; Runtime Assurance productization;
Trajectory Control; ACP; Reconciliation→authority feedback; RA-7 / RA-8 (SPEC
§18).

## E. Scope statement

Documentation/design only. No production code changed, no package/ports created,
no persistence/API added, no envelope/ActionGate/Agent-Runtime change, no
RA-4.5/RA-5 change, no PR opened.
