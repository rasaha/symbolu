# Operational Signals

> Machine-readable: `clearance_signal_mapping.json`.

Operational signals are **supplied, offline snapshots** — Code Governance implements
no live client for identity / incident / change-management / GitHub / CI / cloud /
database / Kubernetes / HR systems. The caller supplies a
`CodeGovernanceOperationalSnapshot`; each present fact maps to exactly one **canonical**
Action Clearance `SignalType`.

## Snapshot fact -> canonical SignalType

| Snapshot field | SignalType | Normalized value |
|---|---|---|
| `authorization_validity` | `AUTHORIZATION_VALIDITY` | `{"state": "VALID\|INVALID\|STALE"}` |
| `actor_state` | `ACTOR_STATUS` | `{"state": "ACTIVE\|DISABLED\|UNKNOWN"}` |
| `artifact_action_fingerprint` (+`artifact_target_ref`) | `ARTIFACT_IDENTITY` | `{"action_fingerprint": …, "target_ref": …}` |
| `policy_accepted` | `POLICY_VALIDITY` | `{"accepted": bool}` |
| `change_freeze_active` | `CHANGE_FREEZE` | `{"active": bool}` |
| `incident_active` | `ACTIVE_INCIDENT` | `{"active": bool}` |
| `target_available` | `TARGET_AVAILABILITY` | `{"available": bool}` |
| `required_control_satisfied` | `REQUIRED_CONTROL` | `{"satisfied": bool}` |
| `consumption_state` | `PRIOR_CONSUMPTION` | `{"state": "UNUSED\|RESERVED\|CONSUMED\|UNKNOWN"}` |

## Source-registry projection + trusted-signal adapter

`TrustedSignalSourceProjection` is an **immutable** per-signal-type projection (no
mutable registry service, no database). `build_trusted_signals` fails closed when:

- the source is unapproved (no projection entry),
- the adapter version is unapproved,
- the supplied trust level exceeds the source's authorized maximum,
- the tenant differs.

The evaluator additionally fails closed on subject / authorization / action /
content / provenance mismatches and on insufficient trust level. Each signal binds
`tenant_id`, `subject_ref` = repository, `authorization_ref` = ActionGate result
fingerprint, and `action_fingerprint` = prepared-action fingerprint; its
`integrity_digest` is the canonical `content_fingerprint` computed via the Action
Clearance public API. Consumption status is supplied by a caller/fixture — Code
Governance does **not** own the authoritative consumption ledger and implements no
reservation.
