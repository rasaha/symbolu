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

## E. Scope statement (original ratification doc)

Documentation/design only. No production code changed, no package/ports created,
no persistence/API added, no envelope/ActionGate/Agent-Runtime change, no
RA-4.5/RA-5 change, no PR opened.

---

## F. As-built implementation record (added at implementation time)

> Implemented against the ratified architecture (SHA `e4b548a1`). In any conflict
> the SPEC governs; nothing below silently changes a ratified decision.

### F.1 Packages created / modified

| Package | Change |
|---|---|
| `ugence-risk-authority` (leaf) | **Additive, stdlib-only.** New neutral value types + ports, `RevocationState` predicate **unchanged**. |
| `ugence-risk-authority-status-runtime` (**NEW** sibling, `packages/integration/risk-authority-status-runtime/`) | The RA-6 control plane: reference persistence, bounded-stale cache, authenticated writer, reassessor, driven case-state transitions, status-aware enforcement + last-mile recheck. Depends only on the leaf. |
| `ugence-agent-runtime` | **Additive, backward-compatible.** One optional neutral `authority_recheck` hook on `validate_clearance` + `AgentRuntimeConfig`, threaded at the existing pre-effect call site. Default `None` ⇒ identical behavior. Imports nothing from Risk Authority. |
| `ugence-risk-authority-runtime` (RA-4.5) | **Unchanged** (0 files). ActionGate integration composes the leaf's `ReferenceActionGate`, not the RA-4.5 runtime. |
| `ugence-risk-authority-evidence-runtime` (RA-5) | **Unchanged** (0 files). |

### F.2 Contracts implemented (leaf ports)

- `AuthorityStatusReader` (READ): `snapshot(tenant_id)`, `current_epoch`,
  `is_initialized`, `as_of`. → `AuthorityStatusCache`.
- `AuthorityLifecycleWriter` (WRITE): `advance_epoch(change_id)`,
  `revoke_envelope/subject/model`. → `AuthorityLifecycleService`
  (+ privileged `emergency_stop`).
- `AuthorityReassessmentSignalPort` (INTAKE): `submit(signal) -> SignalAck`. →
  `AuthorityReassessor`.
- Value types: `AuthorityStatus`, `AuthorityStatusSnapshot`, `StalenessPolicy`,
  `AuthorityReassessmentSignal` (+ `SignalChangeType`/`SignalTarget`),
  `WriterPrincipal`, `LifecycleWriteResult`, `SignalAck`.

### F.3 Persistence / status model

`ReferenceAuthorityStore` (in-memory reference): per-tenant monotonic epoch
(base 1, idempotent under `change_id`), grow-only envelope/subject/model revoke
unions, per-tenant locks, `merge()` convergence (`max(epoch)` + union, lower-epoch
no-op). Production Postgres delegated in `postgres.py` (completes the reserved DDL;
raises `PostgresNotConfiguredError`, never silently degrades). `AuthorityStatusCache`
holds a point-in-time `RevocationState` copy + `as_of` + covered-tenant set; starts
**UNINITIALIZED** ⇒ DENY until first `sync()`.

### F.4 Freshness / writer / signal / case semantics

- **Freshness (Policy C):** uninitialized (globally or per-tenant) ⇒ DENY all
  tiers; `age > max_staleness(tier)` ⇒ DENY; else ALLOW /
  `ALLOW_WITH_BOUNDED_STALE_STATUS`. Platform-ceiling clamp; unknown tier ⇒
  CRITICAL/fail-closed. Fail-closed defaults, not canonized policy.
- **Writer authorization:** fail closed without an authenticated principal;
  capability + tenant-isolation checks via an injected `WriterAuthorizer` seam;
  `ReferenceWriterAuthorizer` **refused in production** (RA-5 F-1); append-only
  attributed `AUTHORITY_EPOCH_ADVANCED` / `ENVELOPE_REVOKED` events with actor /
  reason / correlation / idempotency key.
- **Signals:** validated (malformed ⇒ IGNORE), deduped by `event_id`, reassessed
  against current state; carry no ALLOW/scope (structural). `TENANT_EMERGENCY_STOP`
  refused on the ordinary observer intake (privileged direct-write path only).
- **Case state:** `ACTIVE → {EXPIRED,REVOKED,SUPERSEDED}` via the leaf's guarded
  transition + existing event types; no reactivation from terminal states; expiry
  distinct from revocation (no revocation record written for expiry).

### F.5 ActionGate + Agent-Runtime integration

- `StatusAwareActionGate` (READ ONLY): freshness gate first (distinguishes
  uninitialized / bounded-stale / stale-beyond-bound), then the **unchanged** RA
  enforcement (`ReferenceActionGate` → offline verifier: signature / nbf / expiry /
  tenant / session / epoch / targeted revocation) against the snapshot's
  `RevocationState`.
- Last-mile (SPEC §8): `make_pre_effect_recheck` builds the neutral
  `authority_recheck` callable plugged into `validate_clearance`; it re-runs the
  offline `check_authority_status` at the commit point — no reauthorization, no
  lease, no nonce, no polling. Non-authority-bound actions pass through
  (low-latency preserved).

### F.6 Test counts (as-built, all green)

| Suite | Count | Δ |
|---|---|---|
| `ugence-risk-authority` (leaf) | 113 | +16 (RA-6 leaf contracts) |
| `ugence-risk-authority-status-runtime` (**new**) | 72 | new |
| `ugence-risk-authority-runtime` (RA-4.5) | 77 | unchanged |
| `ugence-risk-authority-evidence-runtime` (RA-5) | 87 | unchanged |
| `ugence-agent-runtime` | 319 (+2 skipped) | unchanged |
| TAP / governance-contracts / decision-authority / actiongate | 82 / 48 / 79 / 62 | unchanged |

RA-6 conformance covers task §20 A–Z (deny-heavy), §19 idempotency/concurrency,
writer authorization + F-1 + emergency stop, signal intake/dedupe, case-state
transitions, last-mile + resume/recovery regressions, and packaging boundaries.
Isolated `--no-index` clean-venv install proof passes (leaf stays stdlib-only; no
out-of-scope package importable).

### F.7 Limitations / delegated / FUTURE

Reference in-memory persistence (production Postgres delegated); in-process
propagation (durable/replicated event bus delegated); authentication/authorization
delegated to the deployment (reference authorizer refused in production);
per-workflow/per-policy epochs, producer cryptographic attestation, HSM/KMS,
multi-region consistency — all FUTURE (SPEC §18). No overclaim: this is
code-level lifecycle enforcement, not production-solved global revocation.
