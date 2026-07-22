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

- **direction:** SUBJECT_TO_OBJECT, OBJECT_TO_SUBJECT, UNDIRECTED, UNCLEAR.
- **polarity:** POSITIVE, NEGATED, UNKNOWN (negation never discarded).
- **modality:** ASSERTED, REQUIRED, PERMITTED, RECOMMENDED, POSSIBLE, CONDITIONAL,
  ALLEGED, UNKNOWN (`may`≠`must`).
- **temporality:** CURRENT, HISTORICAL, FUTURE, SUPERSEDED, CONDITIONAL_TIME, UNRESOLVED,
  plus explicit `valid_from`/`valid_until`.
- **explicitness:** EXPLICIT, STRUCTURALLY_INFERRED, LINGUISTICALLY_INFERRED,
  UNSUPPORTED_INFERENCE (surfaced, never silently accepted).

## Assertion status — precise semantics

Every `status` value refers to the **quality and completeness of the evidence-grounded
relationship representation**, NOT to universal or real-world truth.

- **SUPPORTED** — the cited evidence explicitly states, or validly supports through bounded
  structural normalization, the represented relationship and its recorded dimensions. This
  means *the representation is supported by the cited evidence*. It does **not** mean the
  proposition has been independently proven true in the real world.
- **PARTIALLY_SUPPORTED** — the cited evidence establishes part of the relationship but one
  or more dimensions remain unresolved (e.g. subject+predicate clear but object scope
  incomplete; relationship stated but temporal scope missing; obligation exists but the
  exact condition is unresolved; base relationship explicit but direction or exception scope
  ambiguous).
- **AMBIGUOUS** — the evidence permits more than one materially different relationship
  interpretation and TAP-E3 cannot deterministically resolve them.
- **CONTRADICTED** — one or more cited evidence units assert an incompatible relationship
  under sufficiently comparable subject, object, scope, and temporal conditions. This means
  *conflicting evidence exists*; it does **not** mean TAP-E3 has determined which source is
  correct.
- **INSUFFICIENT_EVIDENCE** — the retrieved evidence does not establish the requested or
  candidate relationship with adequate provenance and relational specificity.
- **UNRESOLVED** — processing cannot assign a more specific status because of unresolved
  references, unsupported inference, missing upstream evidence, or incompatible ambiguity.

> **Downstream warning.** Layers consuming this record must **not** interpret `SUPPORTED`
> as equivalent to *factually verified*, *legally controlling*, *currently applicable*, or
> *safe to include in a final answer without further validation*. Those determinations
> belong to Governance Resolution (TAP-E4), Claim Validation, and Response Validation.

## Conflict semantics

`RelationshipConflict` identifies **incompatible evidence-stated relationships** (comparable
subject/object, compatible/overlapping scope, overlapping temporal range, and a logically
incompatible polarity/modality/value). It does **not adjudicate which source wins.** For
"passwords must be ≥12 characters" vs "≥14 characters" TAP-E3 may emit a `VALUE_CONFLICT`;
it must **not** decide which requirement governs the current user, system, jurisdiction, or
effective period. Authority hierarchy, applicability, supersession control, jurisdiction,
and governing-rule selection belong to **TAP-E4 Governance Resolution**.

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

## Provisional interface freeze

The `RelationshipRecord` schema (`tap-e3-relationship/1.0.0`) is the **provisional frozen
interface** for TAP-E4. Future work should **consume** it rather than modify TAP-E3. A
schema change should occur **only if TAP-E4 exposes a genuine architectural deficiency**,
and any such change must carry:

1. an explicit schema-version increment;
2. a migration note;
3. a downstream compatibility analysis;
4. an explanation of why the existing interface was insufficient.

The schema is **not** changed in this task.
