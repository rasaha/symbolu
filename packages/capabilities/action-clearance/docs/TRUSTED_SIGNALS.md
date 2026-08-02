# Trusted Signals

A `TrustedSignal` is an immutable, tenant-bound, subject-bound, time-bound,
source-identified, integrity-verifiable, freshness-evaluable, deterministically
serializable current-state fact. Action Clearance **receives** signals; it never
fetches external state, holds credentials, or contacts identity/adapter systems.

## Signal types and neutral value conventions

Each signal's normalized `value` is interpreted per `signal_type`:

| `signal_type` | value convention | negative → reason (default status) |
|---|---|---|
| `ACTOR_STATUS` | `{"state": "ACTIVE"\|"DISABLED"\|"UNKNOWN"}` | DISABLED → `ACTOR_INVALID` (BLOCK); UNKNOWN → `ACTOR_STATUS_UNKNOWN` (HOLD) |
| `ARTIFACT_IDENTITY` | `{"action_fingerprint": "…", "target_ref": "…"}` | fp≠authorized → `ACTION_FINGERPRINT_MISMATCH` (BLOCK); target≠ → `TARGET_MISMATCH` (BLOCK) |
| `CHANGE_FREEZE` | `{"active": bool}` | active → `ACTIVE_CHANGE_FREEZE` (HOLD) |
| `ACTIVE_INCIDENT` | `{"active": bool}` | active → `ACTIVE_INCIDENT` (HOLD/ESCALATE by policy) |
| `REQUIRED_CONTROL` | `{"satisfied": bool}` | not satisfied → `REQUIRED_CONTROL_UNSATISFIED` (BLOCK) |
| `TARGET_AVAILABILITY` | `{"available": bool}` | unavailable → `TARGET_UNAVAILABLE` (HOLD) |
| `PRIOR_CONSUMPTION` | `{"state": "UNUSED"\|"RESERVED"\|"CONSUMED"\|"UNKNOWN"}` | CONSUMED → `ALREADY_CONSUMED` (BLOCK); RESERVED → `CONSUMPTION_RESERVED` (HOLD/BLOCK by policy); UNKNOWN → fail closed (HOLD) |
| `POLICY_VALIDITY` | `{"accepted": bool}` | rejected → `POLICY_VERSION_REJECTED` (BLOCK) |
| `AUTHORIZATION_VALIDITY` | `{"state": "VALID"\|"INVALID"\|"STALE"}` | invalid/stale → `AUTHORIZATION_STALE` (HOLD) |

## Structural, freshness, and trust checks (fail-closed)

- tenant match (`TENANT_MISMATCH`), subject/authorization/action binding
  (`SUBJECT_MISMATCH`, `SIGNAL_AUTHORIZATION_MISMATCH`, `SIGNAL_ACTION_MISMATCH`);
- liveness (`status == UNKNOWN` on a required signal → `SIGNAL_MISSING`);
- freshness — `captured_at ≤ evaluation_time` (future beyond skew is malformed),
  `valid_until > evaluation_time` (inclusive-expiry is expired → `SIGNAL_EXPIRED`),
  age ≤ policy max (`SIGNAL_STALE`); a required time-bounded signal with no
  `valid_until` fails closed;
- trust (policy-gated): missing provenance/integrity → `SIGNAL_PROVENANCE_MISSING`
  / `SIGNAL_UNTRUSTED`; unapproved source/adapter → `SIGNAL_SOURCE_UNAPPROVED` /
  `SIGNAL_ADAPTER_VERSION_UNAPPROVED`; below the required `SignalTrustLevel`
  (`LEVEL_1_TRUSTED_INGESTION` < `LEVEL_2_AUTHENTICATED_ENVELOPE` <
  `LEVEL_3_SIGNED_PRODUCER`) → `SIGNAL_TRUST_LEVEL_INSUFFICIENT`; a supplied
  `integrity_digest` that does not match the content fingerprint →
  `SIGNAL_CONTENT_MISMATCH`.

The evaluator validates that required provenance fields and trust levels are
present and policy-compliant — it does **not** verify PKI, retrieve keys, or
contact registries.

Two present signals of one type with disagreeing content → `SIGNAL_CONFLICT`
(ESCALATE). Signals are never averaged into a risk score (non-compensatory).
