# TAP-E3 — Metrics

Each relationship dimension is measured **separately** (never hidden behind aggregate F1).
Predicted assertions are matched to gold by unordered normalized entity pair (so direction
reversal is detected), then each dimension is scored on the matched pairs.

- **relationship_precision / recall / f1** (predicate counts as correct if in the gold's
  acceptable ontology set).
- **subject / predicate / object / direction accuracy** (direction = correct ordered pair).
- **polarity / modality / temporality / scope / condition / exception accuracy.**
- **ontology_normalization_accuracy**, **exact_triple_accuracy** (subject+predicate+object),
  **full_structure_accuracy** (all dimensions).
- **provenance_completeness.**
- **conflict_detection precision / recall / f1.**
- **gap_detection_accuracy** (all expected gap codes present).
- **cooccurrence_false_positive_rate** (co-occurrence cases that wrongly emit a relationship).
- **unsupported_relationship_rate** (assertions resting on unsupported inference).

## Critical failures (reported independently)

OWNERSHIP_INVENTED, AUTHORIZATION_INVERTED, PROHIBITION_DROPPED, NEGATION_LOST,
DIRECTION_REVERSED, MUST_MAY_COLLAPSE, ALLEGATION_TREATED_AS_FACT,
SUPERSEDED_RELATION_TREATED_AS_CURRENT, CONDITION_DROPPED, EXCEPTION_DROPPED,
CONFLICT_HIDDEN, PROVENANCE_MISSING, UNSUPPORTED_RELATIONSHIP_EMITTED, UPSTREAM_GAP_IGNORED.
A critical failure stays visible even if aggregate metrics pass; the severe-failure gate
requires zero on the selected baseline.

## Preregistered gates

f1≥0.80, predicate≥0.85, direction≥0.90, polarity≥0.95, modality≥0.85,
provenance==1.00, conflict_f1≥0.75, gap_accuracy≥0.75, cooccurrence_fp≤0.10,
unsupported≤0.10, severe==0. Selection = the simplest baseline (A..F) satisfying **all**
gates on dev; the locked eval is scored once. Thresholds are fixed before final
evaluation and are not relaxed after seeing results; any metric-definition correction
preserves the earlier definition and is documented.
