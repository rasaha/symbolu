# Evidence Model (v0.1)

Every validated relationship exposes an `EvidenceRecord` (source: `model.py`).

> Scope: synthetic, deterministic, self-contained. See
> `CLAIM_VALIDATION_PREREGISTRATION.md` §Scope boundary.

---

## 1. EvidenceRecord fields (required by the brief)

| Field | Meaning |
|---|---|
| `relationship_id` | claim id |
| `relationship_type` | claimed type |
| `source_node` / `target_node` | claimed entities |
| `supporting_document_ids` | documents Judge A used as support |
| `supporting_spans` | spans Judge A used as support |
| `contradicting_spans` | spans Judge B used to contradict |
| `missing_predicates` | core predicates with no support |
| `confidence_vector` | per-predicate deterministic confidence [0,1] |
| `validation_status` | one of the six statuses (`CLAIM_STATUS_SPEC.md`) |
| `recommended_action` | retain / narrow / remove / abstain / manual_review |
| `predicate_verdicts` | per-predicate verdict (supported/…/contradicted/unknown) |
| `adjudicated` | True iff Judge C ran |
| `deterministic_removed` | True iff resolved by the pre-judge layer |

## 2. Validation predicates (each evaluated independently)

`entity_correctness`, `relationship_wording`, `direction`, `scope`,
`temporal_applicability`, `authority_applicability`, `document_provenance`,
`support_completeness`, `contradiction`, `missing_evidence`.

**Core** predicates (must be affirmatively supported for SUPPORTED):
entity_correctness, relationship_wording, direction, document_provenance.
**Narrowing** predicates (absence narrows rather than kills): scope, temporal,
authority.

## 3. Confidence vector

Deterministic map from predicate verdict to a score
(`supported=1.0`, `not_applicable=0.75`, `not_supported=0.25`, `contradicted=0.0`,
`unknown=0.5`). No randomness; the overall is the mean. It is an explainability
aid, not a probabilistic claim.

## 4. Provenance requirement

Support and contradiction are always tied to concrete spans
(`supporting_spans` / `contradicting_spans`). A status is never assigned without a
span-level or deterministic-check basis; the evidence record is the audit trail.
