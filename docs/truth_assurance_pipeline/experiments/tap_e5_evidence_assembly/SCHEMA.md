# TAP-E5 — Schema

`schema.py`, version **`tap-e5-evidence-packet/1.0.0`**. The `EvidencePacket` is the **sole
output** of the layer and the **frozen downstream interface** consumed by TAP-E6. Every
structure is a frozen dataclass with `to_dict()`; the packet adds `to_json()` (sorted keys,
compact) and round-trips.

## EvidencePacket

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | str | `tap-e5-evidence-packet/1.0.0` |
| `packet_id` | str | stable id (`packet::<request_id>::<config>`) |
| `intent` | PacketIntent | intent reference (identifiers + required metadata only) |
| `intent_record_id` / `retrieval_record_id` / `relationship_record_id` / `governance_record_id` | str | upstream refs |
| `evidence_units` | tuple[PacketEvidence] | the required evidence |
| `relationships` | tuple[PacketRelationship] | relationships supported by included evidence |
| `governance_decisions` | tuple[PacketGovernance] | governing + rejected authorities |
| `conflicts` | tuple[PacketConflict] | every upstream conflict, unchanged |
| `gaps` | tuple[PacketGap] | every upstream gap, unchanged |
| `dependency_edges` | tuple[DependencyEdge] | explicit dependency graph |
| `confidence_summary` | mapping | carried confidence (never recomputed) |
| `provenance_index` | mapping[id → descriptor] | per-object provenance |
| `processing_trace` | tuple[str] | append-only stage log |

## Sub-structures

- **PacketIntent** — `request_id`, `primary_objective`, `task_type`. Identifiers + required
  metadata only; large payloads are never duplicated.
- **PacketEvidence** — `unit_id`, `source_id`, `source_location`, `doc_type`,
  `authority_level`, `retrieval_rank`, `retrieval_method`, `retrieval_score`,
  `extraction_method`, `confidence`.
- **PacketRelationship** — `assertion_id`, `relationship_type`, `direction`, `polarity`,
  `modality`, `temporality`, `valid_from`, `valid_until`, `scope`, `evidence_unit_ids`,
  `confidence_band`, `status`.
- **PacketGovernance** — `decision_id`, `selected_authority`, `tier`, `status`,
  `precedence_chain`, `rejected_authorities` (each `PacketRejectedAuthority` with a link to
  its minority relationship when present), `exception_basis`, `temporal_basis`,
  `jurisdiction`, `scope`, `supporting_relationships`, `confidence`, `governance_record_id`.
  **No governance reasoning occurs here** — the decision is carried, not recomputed.
- **PacketConflict** — `conflict_id`, `origin` (`E3`/`E4`), `conflict_type`, `member_ids`
  (in-packet object ids; E4 authority names are translated to their relationship ids),
  `explanation`, `status`. Carried unchanged; **never resolved, never discarded**.
- **PacketGap** — `gap_id`, `origin` (`E2`/`E3`/`E4`), `gap_code`, `description`, `detail`.
  Carried unchanged; **never filled, never hidden**.
- **DependencyEdge** — `src_id`/`src_kind` → `dst_id`/`dst_kind`, `edge_type`
  (`answers_intent` | `supported_by_relationship` | `supported_by_evidence`). Every
  downstream dependency is reconstructible from these edges.

## Provenance

Every object in the packet preserves provenance: the `provenance_index` maps each evidence /
relationship / governance / intent id to a descriptor (source, refs). No object is orphaned;
every relationship points to evidence; every governance decision points to relationships and
(transitively) evidence.

## Validation

`packet_validator.validate_packet(packet)` returns `(ok, problems)` and checks: no dangling
references; relationship→evidence grounding; governance support (or explicit no-support
terminal); conflict members present; connected acyclic dependency graph; no duplicate ids; no
provenance loss; minimality; schema round-trip. The interface is **frozen** for TAP-E6.
