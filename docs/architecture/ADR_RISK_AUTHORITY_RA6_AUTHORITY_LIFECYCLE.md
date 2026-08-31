# ADR — RA-6: Authority Lifecycle (Post-Issuance Validity) for Risk Authority

- **Status:** **Accepted (ratified).** The architecture decisions are settled in
  the canonical spec `RISK_AUTHORITY_RA6_SPEC.md` (its §19 readiness gate).
  Acceptance is of the *design*; RA-6 *implementation* remains a separate,
  future, reviewed milestone.
- **Date:** 2026-08-11 (ratified same day)
- **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
  default head `ad3a2a46` (merge of PR #1408). RA-1→RA-4, RA-4.5 (#1402) and
  RA-5 (#1408, #1409) merged and stable.
- **Verdict:** `RA6_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`.

## Context

The Risk Authority leaf already contains the **entire** authority-lifecycle
mechanism — signed `authority_epoch` in the envelope (`domain/envelope.py:44`),
`RevocationState` with tenant epoch + targeted envelope/subject/model revocation
(`services/revocation.py`), an offline verifier that rejects expiry / revocation /
stale epoch (`services/envelope_verifier.py:75-90`), the `REVOKED/EXPIRED/
SUPERSEDED` states (`domain/enums.py:87-90`; `domain/risk_case.py:39-42`), and the
`ENVELOPE_REVOKED` / `AUTHORITY_EPOCH_ADVANCED` event types (`domain/enums.py:166-167`).

It is **test-proven but operationally inert**: the write side (`advance_epoch`,
`revoke_*`) has **zero non-test call sites** (only `tests/adversarial/
test_deny_matrix.py:225-246` and `risk-authority-runtime/tests/test_adversarial.py:129,137`);
`RevocationState` is in-memory per-app-instance (`api/dependencies.py:171`); the
Postgres factory raises and exposes no revocation adapter (`persistence/postgres.py`);
the event bus is in-process, emit-only (`observability/events.py`); no observer
system carries any revocation/epoch/reassessment concept; and no post-issuance
authority-freshness recheck runs immediately before an irreversible effect.

RA-6 ("revocation/epoch propagation", `README.md:31-32`) is the milestone that
makes the existing mechanism *operate* in production. The discovery verdict was
`RA6_ARCHITECTURE_DECISION_REQUIRED`; this ADR records the resolved decisions.

## Decision

1. **RA-6 operationalizes the existing lifecycle; it is not a new authority
   system.** No second authorization engine, no `RuntimeAuthorization` /
   `AssuranceAuthorization` / `RevocationAuthorization` artifact, no new signer,
   no continuous authorization polling. The Ed25519-signed
   `RiskAuthorizationEnvelope` remains the sole machine-execution authority.

2. **Ownership direction is one-way:** observers/evidence/policy/telemetry *emit
   signals*; Risk Authority *reassesses*; a single authorized Authority Lifecycle
   Service *writes* (revoke / advance epoch / reissue); the existing signed
   envelope becomes invalid/superseded; ActionGate/runtime enforce read-only.
   Live code does not contradict this — observers hold no authority-write path.

3. **Stale-state policy = Policy C (risk-tiered bounded staleness).** The hot path
   stays offline against a local status snapshot carrying `as_of`. LOW/MEDIUM may
   honor a still-valid envelope while `now − as_of ≤ max_staleness(tier)`;
   HIGH/CRITICAL DENY past the bound. An **UNINITIALIZED** snapshot is maximally
   stale ⇒ DENY for all tiers — "no state loaded" is never "nothing revoked".
   Thresholds are tenant-governance configuration under a platform ceiling; the
   tier is derived from the envelope, not chosen at the gate.

4. **Consistency model = persisted monotonic state + event propagation +
   bounded-stale local read cache + offline hot path.** `current_epoch` is a
   monotonic integer; replication resolves by `max(epoch)` and a grow-only
   revocation-set union; epoch rollback is never permitted to revalidate old
   authority.

5. **Write authority = a single, RA-authorized Authority Lifecycle Service.**
   Signal producers are never revocation authorities. The writer requires an
   authenticated principal + an `AuthorityLifecycleWriter` grant for the target
   tenant/scope, emits an append-only audit event per write, is tenant-isolated,
   rate-limited, and idempotent (revoke = set union; `advance_epoch` idempotent
   under a caller-supplied `change_id`). RA defines the contract boundary and the
   deployment requirement; it invents no auth implementation.

6. **Signals trigger reassessment (default), never direct grants/revokes.** The
   neutral `AuthorityReassessmentSignal` carries no `ALLOW` and no scope; the
   reassessor reads current authoritative state and decides. A privileged
   administrative `TENANT_EMERGENCY_STOP` is the one separate direct-write path.

7. **Package = new sibling `packages/integration/risk-authority-status-runtime/`
   (`ugence-risk-authority-status-runtime`).** Mirrors the RA-5 evidence-runtime
   precedent. The RA leaf keeps neutral domain types, revocation semantics,
   verifier behavior, and the **new neutral port Protocols**
   (`AuthorityStatusReader`, `AuthorityLifecycleWriter`,
   `AuthorityReassessmentSignalPort`) and stays stdlib-only; persistence,
   messaging, and service clients live in the status runtime. The RA-4.5 runtime
   is unchanged and consumes only the read port.

8. **Contracts are read/write-segregated for least privilege.** ActionGate/hot-path
   holds `AuthorityStatusReader` only; the writer is a distinct capability.

9. **Last-mile TOCTOU = pre-effect validity re-verification for consequential /
   irreversible actions, valid through the commit point.** It re-runs the
   existing offline verifier (clock, epoch, targeted revocation) — not full RA
   reasoning — by **extending the pre-invocation freshness seam that already
   exists** in Agent Runtime (`validate_clearance` / `GOVERNANCE_CLEAR_EXPIRED`,
   `decisions.py:76-123`) from expiry-only to epoch+revocation. No new lease or
   nonce primitive; no continuous polling.

10. **State model unchanged in shape:** `ACTIVE/REVOKED/EXPIRED/SUPERSEDED`
    (`REVOKED`/`SUPERSEDED` terminal; restoration requires a new envelope);
    dimensions are envelope/subject/model/tenant-epoch; workflow-/policy-specific
    epochs are a non-breaking FUTURE (the reserved `revocations.kind` column
    already generalizes).

11. **No envelope schema change; no mass-revocation at deployment.** Starting
    epoch = 1 per tenant; pre-RA-6 envelopes remain valid under epoch=1 until TTL
    unless explicitly invalidated; caches start UNINITIALIZED (HIGH/CRITICAL
    fail-closed until first sync).

## Rejected alternatives

- **Policy A (always DENY on any staleness)** — rejected: fails-closed low-risk
  traffic on transient blips and incentivizes disabling the control.
- **Policy B (honor unexpired envelope regardless of freshness)** — rejected:
  reopens the exact post-issuance gap RA-6 exists to close.
- **Synchronous central revocation lookup / DB read per action** — rejected:
  unacceptable hot-path latency and a hard availability coupling.
- **Event-only propagation with no durable authoritative state** — rejected: a
  restarted/new node has no source of truth and cannot distinguish uninitialized
  from empty.
- **Let observers (evidence/telemetry/Runtime Assurance/ActionGate) write
  authority state** — rejected: violates the ownership direction (I1/I2); a
  signal must never mint, widen, or directly revoke authority.
- **Signals as direct revoke commands (Option A)** — rejected as the default:
  brittle to malformed/stale/out-of-order signals; reassessment against current
  truth is monotone and fail-safe. (Emergency stop is the single, privileged,
  human-gated exception.)
- **Fold RA-6 into `risk-authority-runtime` (RA-4.5)** — rejected: pollutes a
  read-only hot-path composition library with control-plane persistence/messaging
  deps and couples incompatible deployment/scaling profiles.
- **A single `AuthorityLifecyclePort` (read+write together)** — rejected: would
  hand ActionGate/hot-path write capability; segregated read/write enforces least
  privilege.
- **Continuous lease-renewal / polling for long-running actions** — rejected:
  contradicts the offline model; commit-point re-verification (Option B) is the
  smallest defensible semantics.
- **A new machine-authority artifact / new signer** — rejected: RA remains the
  sole authority mint (I8).

## Consequences

- Post-issuance invalidation becomes real and bounded: broad (tenant epoch),
  surgical (targeted revoke), and time-boxed (short TTL backstop), with a
  risk-tiered availability/exposure trade-off under degraded propagation.
- The RA leaf stays stdlib-only; a new status-runtime package owns the stateful
  control plane; the RA-4.5 runtime is untouched.
- RA-4.5 invariants (`FinalAuthority ≤ RiskAuthority`, `FinalScope ⊆
  RiskAuthorityScope`) hold unchanged; RA-6 can only *subtract* authority.
- Two precise leaf refinements are required at implementation time: an
  init/`as_of` marker so "uninitialized" ≠ "nothing revoked" (R-1), and an
  idempotent `advance_epoch` under a `change_id` (R-2). Both live in the
  production status wrapper/writer, keeping the leaf predicate pure.
- No new state and (barring an optional `ENVELOPE_SUPERSEDED` audit refinement)
  no new event types are required — the existing states/events cover the driven
  transitions.

## Scope statement

Documentation/design only. No production code changed, no RA-6 package or ports
created, no persistence/revocation-API added, no envelope/ActionGate/Agent-Runtime
change, no RA-4.5/RA-5 code changed, no #1397 (F-D) work folded in, no PR opened,
nothing merged.
