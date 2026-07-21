# TAP-E4 — Schema

`schema.py`, version **`tap-e4-governance/1.0.0`**; authority model
**`tap-e4-authority/1.0.0`**. The `GovernanceRecord` is the **sole output** of the layer and
the provisional frozen downstream interface. Every structure is a frozen dataclass with
`to_dict()`; the record adds `to_json()` (sorted keys, compact) and round-trips.

## GovernanceRecord

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | str | `tap-e4-governance/1.0.0` |
| `authority_model_version` | str | `tap-e4-authority/1.0.0` |
| `governance_record_id` | str | stable id (`gov::<request_id>::<config>`) |
| `intent_record_id` / `retrieval_record_id` / `relationship_record_id` | str | upstream refs |
| `created_at` | str | `"N/A (deterministic run)"` — no wall-clock |
| `governing_authorities` | tuple[GoverningDecision] | the decision(s) |
| `governing_relationships` | tuple[str] | supporting assertion ids |
| `governance_conflicts` | tuple[GovernanceConflict] | unresolved ties, surfaced |
| `governance_gaps` | tuple[GovernanceGap] | what could not be resolved / preserved upstream |
| `confidence_vector` | GovernanceConfidence | 8-axis, min-floored band |
| `processing_trace` | tuple[str] | append-only stage log |

## GoverningDecision

| Field | Meaning |
|---|---|
| `decision_id` | id within the record |
| `selected_authority` | authority name, or **`None`** (conflicted / no-governing / exempt) |
| `tier` | `AuthorityTier` of the winner (`UNKNOWN` when none) |
| `selection_reason` | human-readable why (tier, contract/emergency override, count beaten) |
| `supporting_relationships` | assertion ids grounding the selection |
| `rejected_relationships` | tuple[RejectedAuthority] — every excluded candidate + reason |
| `precedence_chain` | ordered authority names considered |
| `jurisdiction` / `scope` / `temporal_basis` | the winner's applicability basis |
| `exception_basis` | matched exemptions (never flattened away) |
| `provenance` | tuple[GovProvenance] back to assertion → evidence unit → source |
| `confidence` | the decision's confidence vector |
| `status` | `GovStatus` |

### GovStatus

`GOVERNING` · `GOVERNING_WITH_EXCEPTION` · `CONFLICTED` · `NO_GOVERNING_AUTHORITY` ·
`INSUFFICIENT_BASIS` · `UNRESOLVED`. A conflict yields `CONFLICTED` with
`selected_authority = None`; an exempted situation with no residual obligation yields
`GOVERNING_WITH_EXCEPTION` with `selected_authority = None`.

## GovProvenance

`authority_name`, `relationship_assertion_id`, `evidence_unit_id`, `source_id`,
`source_location`, `relationship_record_id`. `is_complete()` requires every id present.
**Every selected authority must carry complete provenance** — enforced by `validate_record`
and by the `provenance_completeness == 1.0` gate.

## GovernanceConflict

`conflict_id`, `conflict_type` (`AUTHORITY_CONFLICT` / `JURISDICTION_CONFLICT` /
`CONTRACT_POLICY_CONFLICT` / `EXCEPTION_CONFLICT` / `VERSION_CONFLICT`), `authority_names`,
`explanation`, `status` (`OPEN`). Emitted only when ≥2 authorities share the top precedence
key with **incompatible obligation values**.

## GovernanceGap

`gap_code` (`NO_GOVERNING_POLICY`, `CONFLICTING_AUTHORITIES`, `AMBIGUOUS_JURISDICTION`,
`MISSING_VERSION`, `UNRESOLVED_SCOPE`, `UNRESOLVED_EXCEPTION`, `EXPIRED_AUTHORITY`,
`MISSING_TEMPORAL_BASIS`, `INSUFFICIENT_UPSTREAM_RELATIONSHIPS`), `description`, `detail`.
Upstream `RelationshipGap`s are preserved as `INSUFFICIENT_UPSTREAM_RELATIONSHIPS` gaps —
never dropped, never repaired.

## GovernanceConfidence (8 axes)

`authority_confidence`, `jurisdiction_confidence`, `scope_confidence`,
`temporal_confidence`, `exception_confidence`, `precedence_confidence`,
`conflict_confidence`, `provenance_completeness`. `band()` returns HIGH / MEDIUM / LOW /
UNRESOLVED and is **floored by the minimum axis** — a single weak dimension cannot be
averaged into a high band (a conflicted decision never reports HIGH).

## AuthorityTier (frozen hierarchy)

`LAW(8) > REGULATION(7) > CORPORATE_POLICY(6) > DEPARTMENT_POLICY(5) > SOP(4) >
WORK_INSTRUCTION(3) > RECOMMENDATION(2) > DRAFT(1) > UNKNOWN(0)`. `LAW`/`REGULATION` are
immutable (never overridable by contract/policy); `DRAFT` is never selectable.
`tier_from_evidence(authority_level, doc_type, explicit_tier)` is the only interpreter of
upstream authority metadata.

## validate_record

Checks schema/authority versions, non-empty id, that any selected authority has complete
provenance, and JSON round-trip. Returns `(ok, problems)`.
