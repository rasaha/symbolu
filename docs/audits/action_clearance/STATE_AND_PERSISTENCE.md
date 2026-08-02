# ACP State, Persistence & One-Time-Use Semantics

## Current state model

| Aspect | Finding | Evidence |
|---|---|---|
| Core evaluation | **Stateless / purely functional** | selectors, `filter_admissible`, authorizer, revalidator, `compose`, `cloud_recommendation` are pure functions of inputs |
| In-memory state (where any) | Bounded, ephemeral | `InMemoryDecisionTraceSink` (append-only tuple), `FailureStateMachine` (in-memory posture+history), `BoundedShadowSink`/`BoundedCloudSink` (`deque(maxlen)` ring buffers), hook `_last` (bounded to 1) |
| Durable persistence | **None** | no DB, no file, no network in the core |
| Clearance ID store | **None** | `grant_id` is computed on demand, not stored |
| Consumption / replay prevention | **None** | "one-shot" is a documentation label only; a replayed authorization within TTL and unchanged state re-passes revalidation |
| Dispatch / observation / reconciliation linkage | **None** in ACP | those live downstream (execution/observation), by design |

## Audit of the requested state fields

| Field | Present? | Notes |
|---|---|---|
| clearance ID | Partial | `grant_id` content hash, not persisted |
| request fingerprint | Yes | `CanonicalActionCandidate.identity`, `CanonicalWorldState.version` |
| result fingerprint | Partial | `grant_id`, `CompositionResult` identity |
| issue time | Yes | `issued_time_s` (injected) |
| expiry | Yes | `expiry_time_s`; `now_s > expiry_time_s` → stale |
| supersession | No | no supersession chain |
| consumption | **No** | no nonce/consumption marker |
| replay prevention | **No** | none in the core (bench reproduces ActionGate-side only) |
| dispatch linkage | No | downstream |
| observation linkage | No | downstream |
| reconciliation linkage | No | downstream |

## Where one-time-use should live

The robotics ACP documents an authorization as "one-shot" but enforces it only through **content-binding +
expiry**, not through a consumption ledger (`authorization.py:36`). A governance ACP must decide ownership of
one-time-use explicitly:

- **Recommendation:** consumption / replay-prevention / duplicate-dispatch belong to an **execution or
  idempotency ledger** (downstream of clearance), **not** inside ACP. The neutral contracts already carry an
  `idempotency_key` on `ActionGovernanceRequest`, and the platform has execution-side guards
  (`decision_governance/services/execution_validation_service.py` blocks `AUTHORIZATION_EXPIRED` /
  `CER_EXPIRED` / `INTENT_EXPIRED`). ACP should *evaluate* prior-consumption as a **received signal**, not
  *own* the ledger.

Do **not** move durable workflow or execution-ledger responsibilities into ACP to simplify packaging. Doing
so would make ACP a stateful workflow/idempotency system — a role the authority boundary forbids
(`AUTHORITY_BOUNDARY.md`).

## Implication for packaging

The stateless, injected-time core is **package-friendly** (it is a deterministic leaf). But the **missing
consumption/replay semantics** are a governance-clearance gap: a real ACP product needs a defined
(received-signal) contract for prior-consumption and duplicate-dispatch before it can claim to prevent
replay. This is a **PREREQUISITE**, and it must be satisfied without ACP absorbing the ledger. See
`RISK_REGISTER.md` (missing durable clearance references; unclear one-time-use ownership; missing replay
prevention).
