# Trusted Current-State Signal Model

## Evidence vs signal (the separation)

| | TAP evidence | Action Clearance signal |
|---|---|---|
| When | before the binding decision | after authorization, immediately before execution |
| Question | is the *claim* supported? | is the *current operational fact* true now? |
| Owner | TAP (`ASSERTION_GOVERNANCE`) | the source system, projected via an adapter |
| Examples | tests passed, scan passed, review completed, policy assessment satisfied | authorization not expired, actor active, artifact still matches, checks still valid, no freeze/incident, target available, policy version still accepted, not already consumed |

Action Clearance does **not** re-adjudicate TAP evidence, unless a clearance policy explicitly requires
freshness validation of an evidence-derived signal (then it evaluates the *freshness* of a signal that
references the evidence, not the evidence itself).

## `TrustedSignal` — neutral fields

| Field | Type | Required in core? | Fingerprinted? | Notes |
|---|---|---|---|---|
| `signal_id` | str | yes | yes | stable id within the bundle |
| `signal_type` | str (enum-like) | yes | yes | e.g. `AUTHORIZATION_VALIDITY`, `ACTOR_STATUS`, `CHANGE_FREEZE`, `ACTIVE_INCIDENT`, `ARTIFACT_IDENTITY`, `REQUIRED_CONTROL`, `TARGET_AVAILABILITY`, `PRIOR_CONSUMPTION`, `POLICY_VALIDITY` |
| `tenant_id` | str | yes | yes | must match the request tenant |
| `subject_ref` | str | yes | yes | the subject the signal is about (actor / artifact / target) |
| `source_ref` | str | yes | yes | identifier of the emitting source instance |
| `source_kind` | str | yes | yes | identity provider / incident system / change mgmt / execution ledger / GitHub adapter … |
| `captured_at` | timestamp (caller-supplied) | yes | yes | when the source observed the fact |
| `valid_until` | timestamp | conditionally | yes | freshness bound; required for signals whose policy marks them time-bounded |
| `status` | str | yes | yes | `PRESENT` / `ABSENT` / `UNKNOWN` (structural liveness of the signal) |
| `value` | normalized scalar/struct | yes | yes | the normalized state (e.g. `active`/`disabled`; a SHA for identity) |
| `provenance_ref` | str | yes | yes | reference to how the value was obtained (for audit) |
| `integrity_digest` | str | conditionally | yes | integrity proof over the signal payload; required for `trust_required` signals |
| `policy_ref` | str | optional (adapter) | yes | policy/version the signal was captured under |

**Core-required** (every profile): `signal_id`, `signal_type`, `tenant_id`, `subject_ref`, `source_ref`,
`source_kind`, `captured_at`, `status`, `value`, `provenance_ref`. **Conditionally required by policy**:
`valid_until` (time-bounded signals), `integrity_digest` (trust-required signals). **Adapter-scoped**:
`policy_ref` and any profile-specific payload live in an adapter extension map, not the neutral core.

## Signal requirements (all mandatory)

A trusted signal is: tenant-bound · subject-bound · time-bound · source-identified ·
integrity-verifiable · freshness-evaluable · deterministic after normalization · serializable ·
immutable after creation.

Normalization is total and canonical (see [`DETERMINISM_AND_FINGERPRINTS.md`](DETERMINISM_AND_FINGERPRINTS.md)):
NaN/Inf rejected, `-0.0 → 0.0`, mapping keys sorted, enums encoded by value, timestamps as integer
epoch-nanoseconds or RFC3339 (one canonical form).

## Condition handling (fail-closed table)

| Condition | Detection | Result contribution | Reason code |
|---|---|---|---|
| signal missing (mandatory) | required `signal_type` absent from bundle | **HOLD** (fail closed) | `SIGNAL_MISSING` |
| signal stale | `captured_at` older than policy freshness window | **HOLD** (default) / BLOCK (policy) | `SIGNAL_STALE` |
| signal expired | `valid_until < evaluation_time` | **HOLD** | `SIGNAL_STALE` |
| signal contradictory | two signals of same type disagree | **ESCALATE** | `SIGNAL_CONFLICT` |
| signal untrusted | `integrity_digest` missing/invalid where trust required | **BLOCK** | `SIGNAL_UNTRUSTED` |
| source unavailable | `status == UNKNOWN` on a required signal | **HOLD** (fail closed) | `SIGNAL_MISSING` |
| tenant mismatch | `signal.tenant_id != request.tenant_id` | **BLOCK** | `TENANT_MISMATCH` |
| subject mismatch | `signal.subject_ref` not bound to the action identity | **BLOCK** | `SUBJECT_MISMATCH` |

**Missing mandatory signals must fail closed** — never CLEAR. A structurally malformed request (the
required signal *slot* is not even declared) is a `NON_RETRYABLE_ERROR` exception, distinct from a
declared-but-absent signal (a `HOLD` result).

## Scope discipline

Action Clearance is **not** a generalized enterprise telemetry platform. It evaluates a bounded set of
clearance-relevant signals supplied by adapters; it does not ingest arbitrary metrics, does not store
signal history, and does not become the source of truth for any operational system.
