# Risk Authority RA-6 — Canonical Specification (Ratified)

> **Status:** RATIFIED — canonical, in-repo RA-6 specification.
> **Type:** DOCUMENTATION / ARCHITECTURE ONLY. This document changes no
> production code, starts no RA-6 implementation, creates no package, adds no
> port to source, adds no persistence, modifies no envelope / ActionGate /
> Agent Runtime, and opens no PR.
> **Verdict:** `RA6_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION` (§20).
> **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
> default head `ad3a2a46` (merge of PR #1408). RA-1→RA-4, RA-4.5 (#1402) and
> RA-5 (#1408, #1409) are merged and treated as stable and closed. RA-6 reopens
> none of them.

RA-6 is the **authority-lifecycle operationalization** milestone named in the
roadmap as *"revocation/epoch propagation"* (`packages/risk_authority/README.md:31-32`;
RA-5 → RA-8). Every architectural claim below was re-verified against live code at
`ad3a2a46`; file:line anchors are cited so a reviewer can confirm each one.

---

## 0. Provenance & the central finding

### 0.1 Repository state (verified independently)

| Item | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default head | `ad3a2a46` (merge of PR #1408) |
| Working tree | clean |
| PR #1408 | **MERGED** — RA-5 trusted-evidence audit + F-1 (into default) |
| PR #1409 | **MERGED** — RA-5 implementation (into default) |
| PR #1410 | **OPEN** — RA-5 canonical spec docs (docs-only) |
| PR #1411 | **CLOSED, not merged** — RA-5 architecture discovery |
| Merged RA lineage | RA-1→RA-4, RA-4.5, RA-5 — confirmed on the default line |

No material Risk Authority / ActionGate / Agent Runtime change landed after the
RA-6 discovery that invalidates the analysis. RA-6 proceeds.

### 0.2 The central finding (re-confirmed)

**RA-6 is NOT a new authority system.** The Risk Authority leaf already contains
the entire authority-lifecycle *mechanism* — it is **test-proven but operationally
inert**. RA-6 is the milestone that makes the existing mechanism *operate* in
production. It adds no second authorization engine and no new machine-authority
artifact.

| Already implemented (leaf) | Anchor |
|---|---|
| Signed `authority_epoch` in the envelope | `domain/envelope.py:37-45` (`EnvelopeBindings.authority_epoch`), signed via `signing_payload()` / `canonical_bytes` (`:71-74`) |
| `RevocationState` (tenant epoch + targeted revoke) | `services/revocation.py` (whole) |
| Tenant epoch advancement | `services/revocation.py:38-43` (`advance_epoch`) |
| Targeted envelope / subject / model revocation | `services/revocation.py:45-51` |
| Offline verifier: expiry / revocation / stale epoch | `services/envelope_verifier.py:75-90` |
| Epoch bound into the envelope at issuance | `services/envelope_issuer.py:92` (`revocation_state.current_epoch(...)`) |
| `REVOKED / EXPIRED / SUPERSEDED` lifecycle states | `domain/enums.py:87-90`; `ACTIVE → {EXPIRED,REVOKED,SUPERSEDED}` `domain/risk_case.py:39-42` |
| `ENVELOPE_REVOKED` / `AUTHORITY_EPOCH_ADVANCED` event types | `domain/enums.py:166-167` |
| Append-only, tamper-evident audit lineage | `domain/events.py` (`payload_digest`, `prev_digest`) |

| Inert today — RA-6 must operationalize | Evidence at `ad3a2a46` |
|---|---|
| No production writer | `advance_epoch` / `revoke_*` have **zero non-test call sites**; every caller is `tests/adversarial/test_deny_matrix.py:225-246` and `risk-authority-runtime/tests/test_adversarial.py:129,137` |
| No authenticated trigger path | no `AuthorityLifecycleWriter`/auth boundary exists |
| No persistence | `RevocationState` is in-memory, per-app-instance (`api/dependencies.py:171` `revocation or RevocationState()`); Postgres factory raises `PostgresNotConfiguredError` and exposes **no** `revocations()` method (`persistence/postgres.py:42-67`) though the DDL reserves `revocations(tenant_id, kind, target_id, epoch, created_at)` (`postgres.py:28`) |
| No distribution / consistency model | the event bus is **in-process, synchronous, emit-only** (`observability/events.py`) — an audit fan-out, not an inbound signal or replication channel |
| No observer→RA invalidation loop | ActionGate provider, TAP provider, Agent Runtime carry **no** revocation/epoch/reassessment concept (verified by repo-wide grep) |
| No driven post-issuance case-state transitions | `ACTIVE → {EXPIRED,REVOKED,SUPERSEDED}` is legal but **nothing drives it** in production |
| No last-mile authority-freshness recheck | payload/scope are re-checked pre-effect (RA-4.5 F1, `composition.py:194-214`) and per-transition **expiry** is re-checked by Agent Runtime (`ugence_agent_runtime/governance/decisions.py:76-123`, `GOVERNANCE_CLEAR_EXPIRED`), but **authority epoch / revocation is not re-read immediately before an irreversible effect** |

### 0.3 Discovery conclusions — re-verification ledger

| # | Discovery conclusion | Holds? | Evidence |
|---|---|---|---|
| 1 | `authority_epoch` is signed into the envelope | ✅ | `domain/envelope.py:44`, `:71-74` |
| 2 | Verifier already rejects stale epoch | ✅ | `services/envelope_verifier.py:81-90`; `services/revocation.py:78-82` |
| 3 | Targeted revocation already exists | ✅ | `services/revocation.py:45-51`, `:72-77` |
| 4 | Revocation state is in-memory only | ✅ | `api/dependencies.py:171`; `persistence/postgres.py` has no revocation adapter |
| 5 | No production writer exists | ✅ | writes are test-only (§0.2) |
| 6 | No distributed backing state exists | ✅ | `observability/events.py` (in-process); no replication |
| 7 | No material-change signal reaches Risk Authority | ✅ | no inbound signal port; event bus is emit-only |
| 8 | Observer systems do not mint authority | ✅ | ActionGate/TAP/Agent-Runtime have no authority-write path |
| 9 | RA remains sole machine-authority owner | ✅ | Ed25519 `RiskAuthorizationEnvelope` is the only signed authority (`crypto/signing.py`, `domain/envelope.py`) |

**Three precision refinements recorded (refinements, not contradictions):**

- **R-1.** The leaf `RevocationState` cannot today distinguish **UNINITIALIZED**
  from **"loaded and empty"** — both return `current_epoch → _BASE_EPOCH` (1,
  `revocation.py:23,35-36`) and empty revocation sets. This is correct for
  reference mode but is precisely the *"no state loaded must not mean nothing
  revoked"* trap for production. RA-6 **must** add initialization/`as_of`
  freshness metadata — in the production status-cache wrapper, keeping the leaf
  predicate pure (§3, §12).
- **R-2.** `advance_epoch` is a naive `current + 1` with no idempotency key
  (`revocation.py:38-43`). The RA-6 writer **must** make epoch advancement
  idempotent under a caller-supplied change id (§5, invariant I13/I14).
- **R-3.** A per-transition **pre-invocation freshness seam already exists** in
  Agent Runtime (`GovernanceEvaluation.valid_until` + `validate_clearance`,
  `decisions.py:76-123`), and the ActionGate provider is `PROVIDER_EMITS_EXPIRY`
  (emits but does not enforce expiry — `providers/actiongate/docs/EXPIRY_AND_IDEMPOTENCY.md:11-16,25-28`).
  RA-6's last-mile recheck **extends** this existing seam from expiry-only to
  epoch+revocation; it does not invent a new lease primitive (§8).

---

## 1. Ratified RA-6 objective

> **RA-6 canonical question:** *"How does Ugence keep previously-issued machine
> authority valid only while the assumptions that justified it remain
> acceptable?"*

RA-6 **operationalizes the existing authority lifecycle**. It MUST NOT create a
second authorization engine, a `RuntimeAuthorization` / `AssuranceAuthorization`
/ `RevocationAuthorization` artifact, a new independent signer, or continuous
online authorization polling.

### 1.1 Ratified ownership direction (verified consistent with live code)

```
observer / evidence / policy / telemetry / Runtime Assurance
        │            (emit — never mint authority; §6, I2)
        ▼
      SIGNAL  (AuthorityReassessmentSignal — no ALLOW, no scope; §13)
        │
        ▼
Risk Authority reassessment            (validates the signal; reads CURRENT
        │                               authoritative evidence/policy/state)
        ▼
Authority Lifecycle Service (sole writer; authenticated; §5)
        │   revoke envelope/subject/model  |  advance tenant epoch  |  reissue
        ▼
persisted monotonic authority state  →  propagated to edge read caches (§4)
        │
        ▼
existing signed RiskAuthorizationEnvelope becomes invalid / superseded
        │   (offline verifier already enforces this — envelope_verifier.py:81-90)
        ▼
ActionGate / runtime enforcement  (read-only status; last-mile recheck §8)
```

Live code does not contradict this model: observers hold no authority-write path
(§0.2); RA already owns the revocation *read* seam and the epoch binding; the
Ed25519 envelope is already the sole enforced authority. RA-6 supplies the
missing **write side, persistence, distribution, signal intake, and last-mile
recheck** around an unchanged authority mechanism.

---

## 2. Scope fences

**RA-6 MUST:** operationalize the existing lifecycle (writer + persistence +
distribution + signal-driven reassessment + driven case-state transitions +
last-mile recheck), all behind neutral ports, with the RA leaf staying
stdlib-only.

**RA-6 MUST NOT:** introduce a second authority artifact or signer; poll for
authorization continuously; modify the envelope schema; modify ActionGate, Agent
Runtime, Decision Authority, or the RA-4.5 composition; let any observer mint,
widen, or directly revoke authority; implement Runtime Assurance, Trajectory
Control, ACP, Reconciliation, RA-7 or RA-8 (§18).

---

## 3. DECISION 1 — Stale revocation-state policy (ratified: **Policy C, risk-tiered**)

**Question.** ActionGate/runtime holds a valid signed envelope, not expired, but
the current revocation/epoch state cannot be proven fresh. What happens?

### 3.1 Ratified semantics

**Policy C (risk-tiered bounded staleness).** The hot path stays **offline**
(reads a local authority-status snapshot only — no synchronous central lookup;
§4). Each snapshot carries an `as_of` timestamp = the instant of its last
successful sync from the authoritative store. Let
`age = now − snapshot.as_of` and let `T` be the envelope's residual risk tier
(carried from the case's `residual_risk`, `domain/enums.py:66-71`).

| Tier | Behavior when the local status is *fresh* (`age ≤ max_staleness(T)`) | Behavior when *stale* (`age > max_staleness(T)`) or **uninitialized** |
|---|---|---|
| LOW / MEDIUM | honor a still-valid envelope → `ALLOW_WITH_BOUNDED_STALE_STATUS` | **DENY** |
| HIGH / CRITICAL | honor a still-valid envelope | **DENY** |

Rejected alternatives: **Policy A** (always DENY on any staleness) needlessly
fails-closed low-risk traffic during transient backing-store blips and pushes
operators toward disabling the control; **Policy B** (honor the unexpired
envelope regardless of freshness) reopens the exact post-issuance gap RA-6 exists
to close — a revoked high-risk authority would keep executing until TTL. Policy C
bounds worst-case exposure by tier while keeping low-risk availability.

### 3.2 What "fresh authority status" means

A snapshot is *fresh for tier T* iff it has been **initialized** (successfully
synced from the authoritative store at least once) **and** `age ≤
max_staleness(T)`. Freshness is a property of the **snapshot**, not of any
individual envelope. The offline check itself is unchanged — it is exactly
`EnvelopeVerifier.verify(...)` (`envelope_verifier.py:40-94`) run against the
snapshot's `RevocationState` at the current `now`.

### 3.3 "Never initialized" is not "nothing revoked" (closes R-1)

An **UNINITIALIZED** snapshot (cold start, cache wipe, never-synced node) MUST be
treated as **maximally stale ⇒ DENY for every tier**. It MUST NOT read as
`epoch=1, nothing revoked`. RA-6 adds an explicit init/`as_of` marker to the
production status snapshot; the neutral leaf `RevocationState` predicate stays
pure and the freshness/init metadata lives in the status-cache wrapper (§12).

### 3.4 Configuration ownership

- **Risk tier** is **not** chosen at the gate — it is derived from the envelope's
  case `residual_risk`. Operators cannot downgrade an envelope's tier to buy
  availability.
- **`max_staleness(T)`** is a **tenant governance** configuration, per tier,
  expressed as deployment policy (not per-request). RA-6 ships **fail-closed
  defaults**; a tenant governance principal may set tighter bounds. A **platform
  ceiling** caps the maximum permissible staleness; the runtime and tenant can
  only tighten below it, never widen. No numeric values are canonized here (they
  are a deployment/coherence decision, §10.2).
- The value is chosen by the **tenant governance principal**, bounded by the
  **platform ceiling**; ActionGate/runtime consume it read-only.

---

## 4. DECISION 2 — Consistency / distribution model (ratified: **persisted monotonic state + event propagation + bounded-stale local read cache + offline hot path**)

Ratified model (the strong candidate from discovery), option **E (hybrid)**:

```
Authority Lifecycle Service (single authorized writer, §5)
      │  strongly-consistent, serialized-per-tenant, monotonic writes
      ▼
Persisted authoritative authority state   (Postgres: `revocations`, epoch;
      │                                     DDL already reserved postgres.py:28)
      ├── event propagation (durable/replicated) ──┐
      └── periodic pull-sync ───────────────────────┤
                                                     ▼
                            Local read caches at each enforcement point
                            (RevocationState + as_of/init metadata, §3)
                                                     │  offline read only
                                                     ▼
                            Hot path: EnvelopeVerifier.verify(...) — no network
```

Rejected: **A** (synchronous central lookup per action) — unacceptable hot-path
latency and a hard availability coupling; **C** (event-only, no durable state) —
a restarted/added node has no authoritative source of truth and cannot
distinguish uninitialized from empty (R-1); **D** (DB read per verification) —
same coupling as A. The hybrid keeps the hot path offline and safe via §3.

### 4.1 Epoch semantics

- `current_epoch(tenant)` = **monotonic integer**, base `1` (`revocation.py:23`),
  bound into each envelope at issuance (`envelope_issuer.py:92`).
- **Replication conflict resolution:** `current_epoch = max(epoch)` per tenant;
  the targeted-revocation set is **grow-only** (union merge — a revocation never
  un-happens on merge).
- **Epoch rollback is never permitted** to revalidate old authority (I3, I11,
  I14). An update carrying a lower epoch than the local watermark is a no-op.

### 4.2 Failure-dimension evaluation

| Dimension | Ratified behavior |
|---|---|
| Latency | Hot path reads local cache only → no per-action network cost. |
| Availability | Hot path survives backing-store/propagation outage within `max_staleness(T)`; HIGH/CRITICAL fail-closed past the bound (§3). |
| Split-brain | `max(epoch)` + grow-only revoke union: a partition can only become **more** restrictive when it heals; meanwhile staleness/tier policy fails-closed the unhealed side. |
| Replay | Monotonic epoch + idempotent revoke union make replayed writes no-ops. |
| Region failure | Each region holds a read cache; writes require quorum/strong consistency at the authoritative store. |
| Cache restart | Starts **UNINITIALIZED** ⇒ DENY (all tiers) until first successful sync (§3.3). |
| Stale nodes | Bounded by `max_staleness(T)` + tier policy. |
| Ordering | Out-of-order lower-epoch updates ignored; revoke union is order-independent. |
| Idempotency | Revoke = set union (idempotent); epoch advance idempotent under `change_id` (R-2, §5). |
| Recovery | Resync from the authoritative store; re-establish `as_of`/watermark before authorizing HIGH/CRITICAL. |

**Ratified: this is the canonical RA-6 consistency/distribution model.**

---

## 5. DECISION 3 — Who may revoke / advance epoch (ratified: **single RA-authorized Authority Lifecycle Service; signal producers ≠ revocation authority**)

Arbitrary observer systems MUST NOT mutate Risk Authority state.

### 5.1 The two roles never blur

| Role | Who | May it write authority state? |
|---|---|---|
| **Signal producer** | evidence assurance, policy-management, Runtime Assurance, security operations, external risk telemetry, ActionGate observability | **No.** Emits an `AuthorityReassessmentSignal` (§13) only. |
| **Revocation authority (writer)** | the **Authority Lifecycle Service** — the single component holding the `AuthorityLifecycleWriter` capability | **Yes** — the sole mutator of revocation/epoch state. |

### 5.2 Ratified pattern

```
evidence / policy / Runtime Assurance / telemetry
        emits AuthorityReassessmentSignal        (§13; authenticated producer)
Risk Authority reassessor
        validates + reassesses against CURRENT authoritative state
Authority Lifecycle Service (authorized)
        performs revoke / epoch advance / triggers reissue     (§11 audit)
```

Allowed **initiators** of a lifecycle *write request*: (a) the RA automated
reassessor (on a validated signal, default path §6); (b) a human governance
principal / tenant administrator (privileged administrative & emergency path);
(c) the policy-management service (on policy supersession). All route through the
**one** authenticated writer contract and produce an audited attribution.

### 5.3 Contract boundary & deployment requirement (no auth implementation invented)

| Requirement | Ratified contract obligation |
|---|---|
| **Authentication** | Every write carries an authenticated principal identity, established **out of band by the deployment** (mTLS / workload identity / signed token) — the same delegated-trust maturity as RA-5's `TrustedEvidenceIngressPort`. RA ships the neutral seam and **fails closed** without it. |
| **Authorization** | The writer verifies the principal holds an `AuthorityLifecycleWriter` grant for the **target tenant/scope** (reuse `AuthorityGrant` / `AuthorityRegistry`, `domain/authority.py`, `persistence/repositories.py:53-58`). Least privilege: ActionGate/hot-path holds **read-only** capability (§12). |
| **Audit attribution** | Every write emits an append-only `GovernanceEvent` (`ENVELOPE_REVOKED` / `AUTHORITY_EPOCH_ADVANCED`, `enums.py:166-167`) with actor, reason, `correlation_id`, and the originating signal reference (§11). |
| **Tenant isolation** | A writer principal for tenant A can never mutate tenant B (keys are `(tenant, …)`, `persistence/in_memory.py`). |
| **Allowed target scopes** | `envelope_id` \| `(tenant, subject)` \| `(tenant, model)` \| `tenant epoch` \| *(FUTURE)* per-workflow / per-policy epoch (§9). |
| **Rate limiting / abuse** | Per-principal, per-tenant limits; epoch advancement is privileged and low-frequency; bulk revocation is guarded. Deployment requirement. |
| **Idempotency** | Revoke is idempotent (set union). Epoch advance MUST be idempotent under a caller-supplied `change_id` so a retried advance does not double-bump (closes R-2, I13/I14). |

---

## 6. DECISION 4 — Signal trust model (ratified: **signals trigger reassessment; emergency stop is a separate privileged path**)

A signal MUST NOT directly grant or revoke authority by itself.

- **Default (ratified): B — a signal triggers Risk Authority reassessment.** The
  reassessor reads the **current** authoritative evidence/policy/state and
  decides whether to revoke / advance epoch / reissue. Because reassessment is
  idempotent and reads current truth, duplicate / stale / out-of-order signals
  are safe (§14).
- **Emergency administrative kill-switch (ratified separate path):**
  `TENANT_EMERGENCY_STOP` is a **privileged human-governance** direct write
  (still via the authenticated writer, §5) that bypasses reassessment. It is the
  one path where a signal maps directly to a write, and it is gated on the
  administrative principal, not an observer.

A signal can only ever cause a **monotone, fail-closed** outcome: at worst it is
ignored (a malformed/duplicate signal cannot widen authority); it can never
upgrade a DENY or mint scope (I2).

---

## 7. DECISION 5 — Package ownership (ratified: **new sibling `risk-authority-status-runtime`**)

| Option | Verdict |
|---|---|
| 1 — fold into `risk-authority-runtime` | **Rejected.** That package is the RA-4.5 **hot-path composition** library (depends only on `risk_authority` + `ugence-decision-authority` + `ugence-actiongate-provider`). Injecting persistence/messaging/service-client dependencies would pollute a read-only per-action library with control-plane server deps and couple two very different deployment/scaling profiles. |
| 2 — **new sibling `packages/integration/risk-authority-status-runtime/` (`ugence-risk-authority-status-runtime`)** | **RATIFIED.** Mirrors the RA-5 precedent exactly (`risk-authority-evidence-runtime` is a new sibling, RA-5 SPEC §14). |
| 3 — another existing governance runtime | **Rejected.** No existing package owns authority-status distribution; overloading one would blur cohesion. |

**Rationale against the "prefer fewer packages" guidance:** the status runtime is
a **stateful control-plane service** (authenticated writer + persistence +
distribution + signal intake) with an independent deployment lifecycle and
scaling profile from the hot-path enforcement library. "Prefer fewer packages" is
honored by housing the reader-cache sync, the writer service, and the
signal-reassessment intake in **one** status-runtime package rather than three,
and by putting all *ports* in the RA leaf rather than spawning contract packages.

### 7.1 What lives where

- **`ugence-risk-authority` (leaf, `dependencies = []`):** neutral domain types,
  revocation **semantics** (`RevocationState` predicate), verifier behavior, and
  the **new neutral port Protocols** (`AuthorityStatusReader`,
  `AuthorityLifecycleWriter`, `AuthorityReassessmentSignalPort`, §12). Stays
  stdlib-only — no persistence, messaging, or service clients enter it.
- **`ugence-risk-authority-status-runtime` (NEW):** the production
  persistence-backed reader/cache-sync, the authenticated writer service, the
  signal-reassessment intake, and the driven case-state transitions — all
  implementing the leaf ports. One-way import (status-runtime → RA leaf), never
  the reverse.
- **`ugence-risk-authority-runtime` (RA-4.5): unchanged.** It consumes the
  read-only `AuthorityStatusReader` (it already threads a `RevocationState` into
  the enforcer, `risk_authority_enforcer.py:71,95`); it never gains write
  capability.

---

## 8. DECISION 6 — Last-mile TOCTOU (ratified: **pre-effect validity re-verification for consequential actions; valid through the commit point**)

**Response (narrow).** For **consequential / irreversible actions only**, perform
an **authority-status recheck immediately before the side effect**:

1. current clock vs `envelope.expires_at`;
2. current authority epoch vs `envelope.bindings.authority_epoch` (against the
   freshest available status; §3 tier policy governs "fresh enough");
3. targeted revocation (envelope / subject / model).

This is **validity re-verification, not reauthorization** — it re-runs the
existing offline `EnvelopeVerifier.verify(...)` with a fresh `now` and the
freshest status snapshot. It does **not** re-run Risk Authority reasoning, and it
adds **no lease or nonce primitive** (the envelope already owns nonce/session;
the runtime clearance already owns `valid_until`).

**Where it attaches (closes R-3):** the seam already exists — Agent Runtime's
`validate_clearance` (`ugence_agent_runtime/governance/decisions.py:76-123`)
already re-checks a clearance's `valid_until` per transition and emits
`GOVERNANCE_CLEAR_EXPIRED`. RA-6 **extends** the clearance the runtime holds so
the pre-effect check also covers **epoch + revocation**, not expiry alone. The
ActionGate provider remains `PROVIDER_EMITS_EXPIRY` (emits, does not enforce);
enforcement stays a runtime/execution-layer responsibility, unchanged in
placement.

**Long-running effects — ratified smallest defensible semantics: B, valid
through the commit point.**

| Option | Verdict |
|---|---|
| A — valid only at start | **Rejected** — this is exactly the exposure discovery flagged for long-running consequential actions. |
| **B — valid at start AND re-verified valid immediately before the commit point** | **RATIFIED.** Each irreversible commit point requires a fresh recheck; between commit points there is **no** continuous polling. |
| C — valid continuously throughout | **Rejected** — requires continuous leasing/polling, contradicting the offline model and the "no continuous authorization polling" fence. |

Ordinary synchronous action quanta already have a small window (RA-4.5 F1 rechecks
payload/scope pre-effect); RA-6 closes the remaining **authority-freshness**
window at the commit point for consequential actions only.

---

## 9. Revocation state model (ratified)

- **Lifecycle states: `ACTIVE`, `REVOKED`, `EXPIRED`, `SUPERSEDED` only.** No
  `SUSPENDED` / `RESTRICTED` (not required; would add state without a use case).
  These already exist (`enums.py:87-90`; `risk_case.py:39-42`).
- **`REVOKED` and `SUPERSEDED` are terminal for a specific envelope.** An old
  revoked/superseded envelope **never** returns to `ACTIVE` (I4). Restoration
  requires a **new reassessment → new envelope** (I5).
- **Dimensions (all already present):** envelope-specific revoke; subject-wide
  revoke `(tenant, subject)`; model-wide revoke `(tenant, model)`; tenant-wide
  invalidation via epoch advance.
- **Workflow-/policy-specific epochs: NOT required now.** Prefer **tenant epoch
  only**. Policy/workflow supersession is handled by (a) tenant epoch advance
  (broad) or (b) targeted revocation of affected envelopes/subjects/models. The
  reserved DDL already carries a generic `kind` column
  (`revocations(tenant_id, kind, target_id, epoch, …)`, `postgres.py:28`), so a
  `WORKFLOW` / `POLICY` kind is a **non-breaking FUTURE** addition if a
  narrower-blast-radius use case is demonstrated.

---

## 10. Expiry + revocation model (ratified hybrid)

```
short-lived signed envelope   (TTL backstop — bounds exposure if propagation fails)
        +
monotonic tenant epoch        (broad invalidation in one move)
        +
targeted revocation           (surgical invalidation without an epoch bump)
```

Re-issuance reruns **evidence → control assurance (RA-5) → Risk Authority**, then
mints a fresh envelope. **Continuous lease-renewal is explicitly rejected** unless
future evidence shows it is required.

### 10.1 Why the hybrid

- **Short TTL** is the ultimate backstop: even under LOW/MEDIUM bounded-stale
  honoring (§3), the envelope's own `expires_at` bounds worst-case exposure when
  propagation is degraded.
- **Epoch** invalidates everything bound to a prior epoch in one write.
- **Targeted revoke** invalidates a single envelope/subject/model without a
  tenant-wide blast radius.

### 10.2 Coherence constraint (no numbers canonized)

`max_staleness(T) ≤ envelope_TTL(T)` for every tier: the staleness bound is a
tighter, tier-specific control **inside** the hard TTL ceiling. Exact TTL and
staleness values are deployment decisions and are **not** fixed by this
architecture.

---

## 11. Case lifecycle & audit events (ratified drivers)

The states/events exist but are undriven (§0.2). RA-6 ratifies the drivers:

| Transition | Driven by | Actor | Event(s) |
|---|---|---|---|
| `ACTIVE → EXPIRED` | time — a lifecycle reaper transitions the case when `now > expires_at` (the *verifier* already enforces expiry offline regardless of case state; this transition is the audit reflection) | system/clock | `CASE_STATE_CHANGED` (`to=EXPIRED`) |
| `ACTIVE → REVOKED` | the Authority Lifecycle Service performing targeted revoke, or an epoch advance that invalidates the case's envelope | authenticated writer principal (§5) | `ENVELOPE_REVOKED` (+ `AUTHORITY_EPOCH_ADVANCED` for an epoch bump) |
| `ACTIVE → SUPERSEDED` | re-issuance — a new reassessment mints a replacement envelope for the same subject/purpose | writer / reassessor | `ENVELOPE_REVOKED` (supersession reason) + `CASE_STATE_CHANGED` (`to=SUPERSEDED`) |

**New event types required? No.** `ENVELOPE_REVOKED` + `AUTHORITY_EPOCH_ADVANCED`
+ `CASE_STATE_CHANGED` (whose payload already carries `from`/`to`,
`risk_case.py:183`) fully cover the transitions. An optional `ENVELOPE_SUPERSEDED`
type is noted as a **possible future audit-clarity refinement only**, not
required.

**State vs history (ratified):** *authority state* (current epoch + revocation
sets — the truth the hot path reads) is distinct from *audit/event history* (the
append-only `GovernanceEvent` log, `domain/events.py`). RA-6 keeps **append-only
history + immutable envelopes**; state changes are new writes, never edits.

---

## 12. Minimum canonical contracts (ratified — separate read/write for least privilege)

Interface segregation is ratified **over** a single `AuthorityLifecyclePort`,
because it materially enforces least privilege: **ActionGate/hot-path must not
hold write capability.** All three are **neutral Protocols owned by the RA leaf**;
concrete implementations live in `risk-authority-status-runtime` (§7).

### 12.1 `AuthorityStatusReader` (read)

| Aspect | Ratified |
|---|---|
| Owner package | `ugence-risk-authority` (leaf, Protocol) |
| Producer | `risk-authority-status-runtime` (persistence-backed + cache sync) |
| Consumer | ActionGate / RA-4.5 runtime / last-mile recheck (§8) — **read-only** |
| Methods | `current_epoch(tenant_id) -> int`; `status(*, tenant_id, envelope_id, subject_id, model_id, envelope_epoch, now) -> AuthorityStatus`; `is_revoked(...) -> Optional[str]` (the existing predicate); `as_of() -> datetime`; `is_initialized() -> bool` |
| Return | `AuthorityStatus` = one of `ACTIVE/REVOKED/EXPIRED/SUPERSEDED` + `reason` + freshness (`as_of`, `initialized`) |
| Persistence | reads a local bounded-stale snapshot (§4); never a synchronous central call |
| Auth | none required to **read**; least privilege (no write capability) |
| Replay | pure read; idempotent |
| Failure | uninitialized/stale ⇒ §3 tier policy (DENY or `ALLOW_WITH_BOUNDED_STALE_STATUS`); never silently "nothing revoked" (R-1) |

### 12.2 `AuthorityLifecycleWriter` (write)

| Aspect | Ratified |
|---|---|
| Owner package | `ugence-risk-authority` (leaf, Protocol) |
| Producer | the authenticated Authority Lifecycle Service in `risk-authority-status-runtime` |
| Consumer | RA reassessor + privileged administrative path **only** |
| Methods | `revoke_envelope(*, principal, tenant_id, envelope_id, reason, correlation_id)`; `revoke_subject(*, principal, tenant_id, subject_id, …)`; `revoke_model(*, principal, tenant_id, model_id, …)`; `advance_epoch(*, principal, tenant_id, change_id, reason, correlation_id)` |
| Return | an audited result (new state watermark + emitted `GovernanceEvent` id) |
| Persistence | strongly-consistent, serialized-per-tenant, monotonic (§4) |
| Auth | authenticated principal + `AuthorityLifecycleWriter` grant for the target scope (§5) — **fail closed** without it |
| Replay | revoke idempotent (union); `advance_epoch` idempotent under `change_id` (R-2) |
| Failure | unauthorized ⇒ reject, `NO_STATE_CHANGE`, audit (I12); rollback attempt ⇒ no-op (I3/I14) |

### 12.3 `AuthorityReassessmentSignalPort` (intake)

| Aspect | Ratified |
|---|---|
| Owner package | `ugence-risk-authority` (leaf, Protocol) |
| Producer | evidence/policy/Runtime Assurance/telemetry (authenticated signal producers) |
| Consumer | the RA reassessor in `risk-authority-status-runtime` |
| Method | `submit(signal: AuthorityReassessmentSignal) -> Ack` |
| Return | `Ack` (accepted-for-reassessment / ignored-with-reason) — **never** an authorization |
| Persistence | durable intake queue + dedupe by `event_id` |
| Auth | authenticated producer; a signal carries no authority (§13) |
| Replay | dedupe by `event_id`; reassessment idempotent (§14) |
| Failure | malformed ⇒ `IGNORE_EVENT` + DLQ + audit; never a state change from a bad signal (§14) |

---

## 13. Signal contract — `AuthorityReassessmentSignal` (ratified)

A neutral name is ratified deliberately so **Runtime Assurance does not own the
signal** — it is only one of several producers. (`AssuranceChangeEvent` is
recorded as a rejected name for that reason.)

| Field | Class | Trust purpose |
|---|---|---|
| `schema_version` | REQUIRED | reject unknown/incompatible schema fail-closed |
| `event_id` | REQUIRED | idempotency / dedupe / replay key (§14) |
| `tenant_id` | REQUIRED | tenant isolation; scopes reassessment |
| `target` | REQUIRED | one of `envelope_id` / `subject` / `model` / `workflow` / `policy` / `tenant` — what to reassess |
| `change_type` | REQUIRED | bounded category (below); drives which reassessment runs |
| `source` | REQUIRED | producer identity; provenance / authorization of the producer |
| `source_version` | REQUIRED | reproducibility / attribution of the emitter |
| `observed_at` | REQUIRED | when the change was observed; staleness/ordering anchor |
| `reason` | REQUIRED | human/audit explanation |
| `correlation_id` | REQUIRED | ties the signal → reassessment → write → event in the audit chain |
| `evidence_refs` / `control_refs` | OPTIONAL | point the reassessor at the changed artifacts (present when the producer scopes them) |
| `prior_state_ref` | OPTIONAL | the state the producer observed (out-of-order detection) |

**Bounded categories (only these):** `EVIDENCE_INVALIDATED`, `CONTROL_CHANGED`,
`POLICY_SUPERSEDED`, `WORKFLOW_SUPERSEDED`, `MODEL_INVALIDATED`,
`RUNTIME_RISK_ESCALATED`, `TENANT_EMERGENCY_STOP`.

**A signal MUST NEVER contain `ALLOW`, an authorization decision, or any machine-
authority scope.** No field is added without a stated trust purpose above.

---

## 14. Failure matrix (canonical, RA/RA-4.5-consistent terminology)

Outcome vocabulary: `DENY`, `ALLOW_WITH_BOUNDED_STALE_STATUS`, `IGNORE_EVENT`,
`ERROR_NON_EXECUTABLE`, `REASSESS`, `NO_STATE_CHANGE`. (`DENY` and
`ERROR_NON_EXECUTABLE` match `FinalDisposition`, `contracts.py:78-88`.)

| Condition | Ratified outcome |
|---|---|
| Revocation store unavailable (hot path) | LOW/MED & cache fresh: `ALLOW_WITH_BOUNDED_STALE_STATUS`; else `DENY` (§3) |
| Stale local cache | LOW/MED within bound: `ALLOW_WITH_BOUNDED_STALE_STATUS`; HIGH/CRIT or past bound: `DENY` |
| Cache never initialized | `DENY` (all tiers) — closes R-1 |
| Event malformed | `IGNORE_EVENT` + DLQ + audit → `NO_STATE_CHANGE` |
| Event duplicate | `IGNORE_EVENT` (dedupe by `event_id`) → `NO_STATE_CHANGE` |
| Event replay (old signal re-sent) | `REASSESS` (idempotent, monotonic) → `NO_STATE_CHANGE` if state already reflects it |
| Event out-of-order | `REASSESS` against current state; cannot lower epoch → `NO_STATE_CHANGE` for the stale ordering |
| Unauthorized revoke caller | `ERROR_NON_EXECUTABLE` at the write boundary → `NO_STATE_CHANGE` (I12) |
| Revocation write conflict | serialize per tenant; grow-only union / max-epoch merge → idempotent; loser `NO_STATE_CHANGE` |
| Epoch rollback attempt | rejected → `NO_STATE_CHANGE` (I3/I14) |
| Split-brain epoch | resolve `max(epoch)` + revoke union on heal (more-restrictive wins); hot path meanwhile fails-closed per §3 |
| ActionGate sees stale epoch (`envelope_epoch < current`) | `DENY` (already enforced, `revocation.py:78-82`) |
| Last-mile recheck fails (status unavailable at commit) | consequential action: `DENY` (HIGH/CRIT) / `ALLOW_WITH_BOUNDED_STALE_STATUS` (LOW/MED within bound) (§8) |
| Reassessment fails (reassessor error) | retry/DLQ + alert → `NO_STATE_CHANGE` (a failed reassessment never itself revokes or grants; exposure bounded by TTL) |
| Observer unavailable | `NO_STATE_CHANGE` (no signal ⇒ no reassessment; cannot widen; a delayed revoke is bounded by TTL) |

---

## 15. Security invariants (ratified)

| # | Invariant | Enforced by |
|---|---|---|
| I1 | Only the Authority Lifecycle Service may mutate revocation/epoch state | writer capability boundary (§5, §12.2) |
| I2 | Observers may signal but may not mint/widen/revoke authority directly (except the separately-authorized emergency path) | signal contract (§13); `VetoDisposition` has no ALLOW (`contracts.py:64-75`) |
| I3 | Authority epoch is monotonic; no rollback | `max(epoch)` merge; lower-epoch update is a no-op (§4.1) |
| I4 | A revoked/superseded envelope never returns to `ACTIVE` | terminal states (§9); `risk_case.py:26-42` |
| I5 | Restored permission requires a newly issued envelope | re-issuance path (§10) |
| I6 | `FinalAuthority ≤ RiskAuthority` | RA-4.5 composition, unchanged (`composition.py:31-38`) |
| I7 | `FinalScope ⊆ RiskAuthorityScope` | RA-4.5 composition, unchanged (`composition.py:31-38`) |
| I8 | No second machine-authority artifact is introduced | RA-6 adds ports/state/service only (§2, §7) |
| I9 | Revocation cannot increase authority | revoke only adds to the deny set / advances epoch (§4) |
| I10 | Failure to prove current status follows the ratified risk-tier policy | §3 |
| I11 | Old epoch + newer current epoch → DENY | `envelope_verifier.py:81-90`; `revocation.py:78-82` |
| I12 | Unauthorized revocation request → no state change | §5.3; §14 |
| I13 | Duplicate valid revocation request → idempotent | union / `change_id` (§4.1, §5.3) |
| I14 | Out-of-order epoch update cannot decrease current epoch | §4.1 |

---

## 16. Migration / compatibility (ratified)

- **Envelope schema change required? NO** — `authority_epoch` already exists and
  is signed (`domain/envelope.py:44`). RA-6 adds no envelope field.
- **Starting persisted epoch:** `1` (`_BASE_EPOCH`, `revocation.py:23`;
  `current_epoch` default), per tenant.
- **Pre-RA-6 envelopes:** remain valid under `epoch=1` until TTL expiry **unless
  explicitly invalidated**. **No silent mass-revocation at deployment.**
- **In-memory state migration:** none — prior `RevocationState` was ephemeral.
  Production bootstrap seeds the authoritative store with `epoch=1` + empty
  revocation sets per tenant.
- **Cache bootstrap:** every cache starts **UNINITIALIZED** ⇒ HIGH/CRITICAL
  fail-closed until first sync (a brief, accepted cold-start window; §3.3).
- **Versioning:** `schema_version` on the status snapshot and on the signal.
- **Rollout order (each step backward-compatible):** (1) deploy the authoritative
  store seeded `epoch=1`; (2) deploy the status-runtime reader/cache-sync (hot
  path now reads a cache that mirrors `epoch=1` → **no behavior change** vs
  today); (3) deploy the authenticated writer + reassessor; (4) enable tier
  staleness-policy enforcement.

---

## 17. Future conformance test matrix (design only — deny-heavy)

| # | Scenario | Expected |
|---|---|---|
| 1 | normal active envelope | accepted |
| 2 | envelope expired | DENY |
| 3 | targeted envelope revoke | DENY |
| 4 | subject revoke | DENY |
| 5 | model revoke | DENY |
| 6 | tenant epoch advance | DENY (prior-epoch envelopes) |
| 7 | old epoch replay | DENY (I11) |
| 8 | duplicate revoke | idempotent, no error (I13) |
| 9 | unauthorized revoke | rejected, `NO_STATE_CHANGE` (I12) |
| 10 | epoch rollback attempt | no-op (I3/I14) |
| 11 | stale cache, LOW-risk | `ALLOW_WITH_BOUNDED_STALE_STATUS` within bound |
| 12 | stale cache, HIGH-risk | DENY |
| 13 | cache never initialized | DENY (all tiers) |
| 14 | event duplicate | `IGNORE_EVENT`, `NO_STATE_CHANGE` |
| 15 | event out-of-order | `REASSESS`, cannot lower epoch |
| 16 | evidence invalidation signal | triggers reassessment |
| 17 | policy supersession signal | triggers epoch change (or targeted revoke) |
| 18 | tenant emergency stop | privileged direct write; broad invalidation |
| 19 | legitimate reassessment → new envelope | new authority works |
| 20 | old revoked envelope | remains denied (I4) |
| 21 | revoke after authorize, before effect | last-mile recheck → DENY (§8) |
| 22 | long-running consequential action crosses expiry | DENY at commit point (§8) |
| 23 | split-brain / stale-node | `max(epoch)` + revoke union; fail-closed while unhealed |
| 24 | state store unavailable | §3 tier policy |
| 25 | observer unavailable | `NO_STATE_CHANGE`; exposure bounded by TTL |
| 26 | RA-4.5 invariants | unchanged (I6/I7) |
| 27 | no second authority artifact | asserted (I8) |
| 28 | RA leaf remains independently installable | stdlib-only, isolated-install proof |

---

## 18. Explicit non-goals

RA-6 does **not** include (unless a future ratification changes this): RA-7 /
RA-8; Trajectory Control implementation; ACP; Reconciliation→authority feedback;
producer cryptographic attestation; HSM/KMS; evidence signatures; a
`policy_digest` envelope schema change; F-D scope enforcement (#1397); continuous
authorization polling; a second authority artifact; a new Decision Authority; a
new ActionGate; a generalized service-mesh / IAM replacement.

---

## 19. Final verdict

**`RA6_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`.**

| Authority-critical decision | Settled |
|---|---|
| Stale-state policy | ✅ §3 (Policy C, risk-tiered; uninitialized ⇒ DENY) |
| Distribution / consistency model | ✅ §4 (persisted monotonic + propagation + bounded-stale offline reads) |
| Revocation authority | ✅ §5 (single authenticated writer; producer ≠ authority) |
| Signal trust | ✅ §6, §13 (trigger reassessment; emergency path separate) |
| Package ownership | ✅ §7 (new `risk-authority-status-runtime`) |
| Last-mile semantics | ✅ §8 (pre-effect re-verification; valid through commit) |
| State model | ✅ §9 (ACTIVE/REVOKED/EXPIRED/SUPERSEDED; tenant epoch) |
| Migration | ✅ §16 (no schema change; epoch=1; no mass-revoke) |
| Failure semantics | ✅ §14 |
| Security invariants | ✅ §15 (I1–I14) |

No vague placeholders remain on authority-critical behavior. RA-6 *implementation*
is out of scope for this ratification and remains a separate, future,
separately-reviewed milestone.

---

## 20. Explicit confirmations

- No production code changed by this document (docs-only).
- No RA-6 implementation started; no package created; no port added to source;
  no persistence, revocation API, envelope, ActionGate, or Agent Runtime change.
- No RA-4.5 (`ugence-risk-authority-runtime`) or RA-5
  (`ugence-risk-authority-evidence-runtime`) code changed.
- RA-1→RA-4 authority spine, RA-4.5 composition, and RA-5 trusted-evidence
  architecture unchanged and not reopened.
- No PR opened; nothing merged.
