# Policy Model

The evaluator consumes an **already-resolved** immutable `ClearancePolicy`. This
package implements no mutable policy database, no source registry, no enterprise
policy administration, and no remote policy loading.

Fields:

| Field | Meaning |
|---|---|
| `policy_id`, `policy_version` | identity; `policy_ref = id:version` |
| `required_signal_types` | mandatory signal types (missing → fail closed) |
| `minimum_signal_trust_levels` | per-type minimum `SignalTrustLevel` |
| `maximum_signal_age_s` | freshness window (stale → HOLD) |
| `maximum_clearance_lifetime_s` | upper bound on clearance validity |
| `clock_skew_tolerance_s` | widens freshness only, never expiry |
| `incident_response` | HOLD or ESCALATE for `ACTIVE_INCIDENT` |
| `consumption_reserved_response` | HOLD or BLOCK for a `RESERVED` prior-consumption signal |
| `constraint_conflict_response` | ESCALATE or BLOCK for a constraint conflict |
| `clearance_constraints` | structured narrowing constraints (never broaden) |
| `added_obligations` | narrower operational obligations clearance adds |
| `approved_source_kinds`, `approved_adapter_versions` | presence-checked allowlists (no network) |
| `trust_required_signal_types` | signal types that require an integrity/provenance proof |

Trust level and one-time-use are **policy inputs**, evaluated identically for all
three integrity levels from day one (level is policy, not code).
