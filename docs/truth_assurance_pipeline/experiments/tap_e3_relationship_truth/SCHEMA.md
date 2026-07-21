# TAP-E3 — Schema (`tap-e3-relationship/1.0.0`)

The `RelationshipRecord` is the sole output. Every dimension is represented separately —
never collapsed into a binary true/false.

## RelationshipRecord

`schema_version`, `ontology_version`, `relationship_record_id`, `intent_record_id`,
`retrieval_record_id`, `created_at`, `relationship_assertions[]`,
`relationship_conflicts[]`, `unresolved_relationship_gaps[]`, `provenance_summary`,
`confidence_summary`, `processing_trace[]`.

## RelationshipAssertion

`assertion_id`, raw `subject/predicate/object`, `normalized_subject/predicate/object`,
`relationship_type`, `direction`, `polarity`, `modality`, `temporality`, `scope`,
`conditions[]`, `exceptions[]`, `explicitness`, `evidence_unit_ids[]`,
`source_provenance[]`, `extraction_method`, `confidence_vector`, `ambiguities[]`,
`conflicts[]`, `status`, `valid_from`, `valid_until`.

- **status:** SUPPORTED, PARTIALLY_SUPPORTED, AMBIGUOUS, CONTRADICTED,
  INSUFFICIENT_EVIDENCE, UNRESOLVED.
- **direction:** SUBJECT_TO_OBJECT, OBJECT_TO_SUBJECT, UNDIRECTED, UNCLEAR.
- **polarity:** POSITIVE, NEGATED, UNKNOWN (negation never discarded).
- **modality:** ASSERTED, REQUIRED, PERMITTED, RECOMMENDED, POSSIBLE, CONDITIONAL,
  ALLEGED, UNKNOWN (`may`≠`must`).
- **temporality:** CURRENT, HISTORICAL, FUTURE, SUPERSEDED, CONDITIONAL_TIME, UNRESOLVED,
  plus explicit `valid_from`/`valid_until`.
- **explicitness:** EXPLICIT, STRUCTURALLY_INFERRED, LINGUISTICALLY_INFERRED,
  UNSUPPORTED_INFERENCE (surfaced, never silently accepted).

## SourceProvenance (mandatory per assertion)

`evidence_unit_id`, `source_id`, `source_location`, `retrieval_record_id`,
`retrieval_rank`, `retrieval_method`, `extraction_span`, `extraction_method`, and a
`role` (PRIMARY_SUPPORT / QUALIFIER / EXCEPTION / TEMPORAL_CONTEXT / CONTRADICTION). No
assertion may exist without evidence provenance; identifiers are never synthesized.

## RelationshipConfidence (multidimensional)

`subject_resolution`, `object_resolution`, `predicate_resolution`, `direction_confidence`,
`polarity_confidence`, `modality_confidence`, `temporal_confidence`, `scope_confidence`,
`condition_confidence`, `provenance_completeness`, `cross_evidence_consistency`. The
summary band (HIGH/MEDIUM/LOW/UNRESOLVED) is **floored by the minimum component**, so a
low component can never be hidden by a high average.

## RelationshipConflict / RelationshipGap

Conflict: `conflict_id`, `assertion_ids`, `conflict_type` (POLARITY/MODALITY/VALUE/
TEMPORAL/DIRECTION/ONTOLOGY/SCOPE), `scope_overlap`, `temporal_overlap`, `severity`,
`explanation`, `status`. Gap codes: NO_RELATIONSHIP_ESTABLISHED, AMBIGUOUS_PREDICATE/
DIRECTION, UNRESOLVED_SUBJECT/OBJECT, NEGATION/TEMPORAL/CONDITION_SCOPE_UNCLEAR,
CONFLICTING_RELATIONSHIPS, INSUFFICIENT_RETRIEVAL_EVIDENCE, UNSUPPORTED_INFERENCE.

The schema is the **provisional frozen downstream interface**; changes require explicit
version bumps and a demonstrated TAP-E4 deficiency.
