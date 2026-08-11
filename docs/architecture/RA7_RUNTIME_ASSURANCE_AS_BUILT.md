# RA-7 Runtime / Trajectory Assurance — As-Built Implementation Status

> **Status:** IMPLEMENTED (reference milestone). Package
> `packages/integration/risk-authority-runtime-assurance/`.
> **Ratification:** `RISK_AUTHORITY_RA7_SPEC.md` + ADR, ratification commit
> `4d2776e79b48143abb453fa6f5e60b949e761d50` (docs-only child of default
> `e6aa6edf`, the RA-6 merge #1412).
> **Core invariant:** *RA-7 observes and assesses. RA-6 owns authority consequences.*
> **`RiskAuthorizationEnvelope` remains the sole signed machine-authority artifact.**

This records exactly what the RA-7 reference milestone implements, and — with
equal weight — what it deliberately does **not**. It is not production-ready
distributed telemetry; it is a reference-grade, event-driven observer that closes
the RA-6 feedback loop through existing seams.

## Package & dependency map

| Item | Value |
|---|---|
| Location | `packages/integration/risk-authority-runtime-assurance/` |
| Distribution | `ugence-risk-authority-runtime-assurance` |
| Import | `ugence_risk_authority_runtime_assurance` |
| Declared deps | `ugence-risk-authority>=0.1.0`, `ugence-risk-authority-status-runtime>=0.1.0` |
| Third-party runtime deps | **none** (stdlib-only) |
| Imports Agent Runtime? | **no** — observed via a neutral duck-typed event contract |

Dependency direction (one-way, spec §22):

```
risk_authority (stdlib-only leaf)  ◄──  ugence-risk-authority-status-runtime (RA-6)  ◄──  ugence-risk-authority-runtime-assurance (RA-7)
                                                                                              │ observes ▼ neutral event contract
                                                                                          agent-runtime (never imports RA)
```

## Modules

| Module | Responsibility |
|---|---|
| `contracts.py` | Neutral types: `RuntimeRiskLevel`, `ReasonCode`, `AssessmentOutcome`, `TrajectoryPolicyRef`, `TrajectoryObservation`, `TrajectoryAssessment` — evidence, no authority (I9) |
| `policy.py` | `TrajectoryPolicyReader` seam + `TrajectoryPolicy` content + reference reader (D2/§5) |
| `ingress.py` | `TrustedTelemetryIngress` trust boundary (D7/§10) — authenticate, validate bindings, expected-domain guard; reference authenticator refused in production (F-1) |
| `observer.py` | `RuntimeAssuranceObserver` + `Trajectory` — bounded per-`(tenant, workflow)` window; dedupe by `event_id`; re-sequence (§11,§13,§24) |
| `event_adapter.py` | `RuntimeEventAdapter` — neutral agent-runtime event → observation; imports no agent-runtime (§17) |
| `evaluator.py` | `ReferenceTrajectoryEvaluator` sequence-risk rules + `SafeEvaluator` malformed-return guard (§6,§12,§24) |
| `handoff.py` | `AuthorityReassessmentSignalEmitter` — material assessment → `RUNTIME_RISK_ESCALATED` signal → RA-6 intake (§15,§18) |
| `assurance.py` | `RuntimeAssuranceService` composition + assurance-required read seam (D4/§7,§16) |

## Trajectory (as implemented)

A trajectory is the ordered per-`(tenant_id, workflow_instance_id)` sequence of
runtime observations (spec §11). Derived on demand from the observer's bounded
window — **not** a second execution ledger (I13). Observations carry: runtime
event type, action/task id, sequence number, `observed_at`, source/version, the
bound `TrajectoryPolicyRef`, and a neutral `detail` (cumulative `exposure` totals,
`data_class`, `context_size`, `model_behavior_changed`). Post-effect
reconciliation is excluded (RA-8).

## What is implemented

- **Observer** over admitted observations: dedupe (idempotent by `event_id`),
  re-sequence (out-of-order converges), bounded window (marks `truncated`).
- **Trajectory evaluation** producing `NORMAL` / `ESCALATED` / `UNKNOWN`.
- **Sequence-risk interpretation** (D3): reads cumulative exposure and risk-types
  it — cumulative-exposure ceiling, near-boundary repeat, retry loop, data-class
  progression, context expansion, model-behavior change. Deterministic and
  explainable; no weighted risk score converts to authority.
- **Trust ingress** (D7): authenticated deployment seam (Option B), minimum
  bindings, wrong-tenant/workflow/envelope rejection, malformed-return guard,
  production refusal of the reference authenticator.
- **Policy reader** (D2): resolves the authority-bound `trajectory_policy_id` /
  `trajectory_version`; unknown/unresolvable/wrong-version ⇒ `UNKNOWN`.
- **Neutral assessment**: `TrajectoryAssessment` carries no ALLOW/scope/signature.
- **RA-6 signal handoff**: material `ESCALATED` → `AuthorityReassessmentSignal`
  (`RUNTIME_RISK_ESCALATED`, `target=ENVELOPE`) → existing intake port. No direct
  writer / revoke / epoch call.
- **Assurance-required** (D4): opt-in, read-only pre-effect gate; fails closed on
  absent/stale/not-NORMAL assurance; additive by default (never blocks the hot path).
- **SafeEvaluator**: strict plug-in return validation (the RA-6 F-1 lesson) — a
  malformed/faulty/ truthy-fake return can only degrade to `UNKNOWN`.

## What is NOT implemented (out of scope)

- Cryptographic per-event telemetry signing / attestation (delegated authenticated
  ingress only — no overclaim).
- Global / multi-region / distributed telemetry transport or persistence
  (bounded in-memory reference window only; no RA-7 canonical database).
- Zero-window / continuous real-time reassessment (bounded-latency; revocation
  bites at the next pre-effect recheck, spec §25).
- The additive signed-envelope bindings `trajectory_policy_digest` (D2) and
  `assurance_required` condition (D4) — **deferred**, backward-compatible schema
  adds; RA-7 operates against the existing `trajectory_policy_id` and an
  application-supplied `assurance_required` flag until they land. The signed
  envelope shape is unchanged by this milestone.
- **ACP** (per-tick physical actuator selection) — separate subsystem.
- **RA-8** (post-effect reconciliation, execution receipts, effect verification,
  Decision-Authority reconciliation wiring, compensation feedback) — a late event
  arriving after completion is handled only as a late runtime signal / ignored;
  no reconciliation is performed.
- HSM/KMS; full IAM.

## Failure semantics (spec §20 — as implemented)

| Condition | Outcome |
|---|---|
| Telemetry/observer unavailable | additive: `CONTINUE_UNDER_RA6` (default); `ERROR_NON_EXECUTABLE`/`DENY_IF_ASSURANCE_REQUIRED` under `assurance_required` |
| Policy unavailable / unknown version | `UNKNOWN_ASSESSMENT` → `NO_SIGNAL` |
| Telemetry malformed / wrong tenant / workflow / envelope | `IGNORE_EVENT` |
| Duplicate event | `IGNORE_EVENT` (idempotent) |
| Out-of-order event | re-sequenced; converges |
| Evaluator exception / malformed return | `UNKNOWN_ASSESSMENT` (SafeEvaluator) |
| RA-6 signal sink unavailable | deferred (`SINK_UNAVAILABLE`); assessment stands; authority unchanged |

**No failure widens authority.**

## Boundaries preserved

- ActionGate remains exact-action enforcement; RA-7 adds no per-action gate.
- Agent Runtime remains the execution owner and imports no Risk Authority.
- Risk Authority leaf stays stdlib-only and independently installable.
- No second machine-authority artifact; no second execution ledger; no new signal
  category (reuses `RUNTIME_RISK_ESCALATED` + structured reason codes).

## Tests

Deny-heavy suite covering spec §27 items 1–41: contracts / no-authority-field,
ingress trust boundary, observer dedupe/ordering, each sequence-risk rule,
`UNKNOWN` paths, SafeEvaluator adversarial malformed returns, signal handoff,
end-to-end observe→signal→**real RA-6 revoke**, idempotency, recovery-does-not-
resurrect, assurance-required, event adapter, packaging/boundary invariants, and
a clean-room `--no-index` isolated-install proof.

## Maturity statement

Reference-grade, event-driven runtime assurance that can cause previously-valid,
signed machine authority to be reassessed and invalidated through the existing
RA-6 lifecycle — bounded-latency, delegated persistence and producer trust. **Not**
production-distributed, cryptographically-attested, zero-window, ACP, or RA-8.
