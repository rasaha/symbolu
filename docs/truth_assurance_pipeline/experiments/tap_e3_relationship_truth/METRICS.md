# TAP-E3 — Metrics

Each relationship dimension is measured **separately** (never hidden behind aggregate F1).
Predicted assertions are matched to gold by unordered normalized entity pair (so direction
reversal is detected), then each dimension is scored on the matched pairs.

## Two metric families — do not conflate them

**End-to-end detection metrics** have *all gold relationships* in the denominator and
penalize any that are missed:

```
relationship_recall    = correctly recovered gold relationships ÷ all gold relationships
relationship_precision = correct predicted relationships       ÷ all predicted relationships
relationship_f1        = harmonic mean of the two
```

**Matched-only (conditional) metrics** have *the number of matched predicted↔gold pairs*
in the denominator, so they describe the quality of the assertions the layer *did*
produce, not coverage:

```
matched_predicate_accuracy      = correct predicates          ÷ matched pairs
matched_triple_accuracy         = correct (subject,predicate,object) ÷ matched pairs
matched_full_structure_accuracy = fully-correct assertions (all dims) ÷ matched pairs
direction / polarity / modality / temporality / scope / condition / exception accuracy
                                = correct on that dimension    ÷ matched pairs
```

**A perfect matched-structure score does not mean every gold relationship was recovered.**
In the recorded run, `relationship_recall = 0.91` (one out-of-lexicon sentence yields no
assertion) while `matched_triple_accuracy = matched_full_structure_accuracy = 1.00`. The
stored result keys in `results_v3.json` keep their original names
(`exact_triple_accuracy`, `full_structure_accuracy`, `predicate_accuracy`,
`ontology_normalization_accuracy`); this documentation uses the clearer **display labels**
`matched_triple_accuracy`, `matched_full_structure_accuracy`, and
`matched_predicate_accuracy` while the underlying artifact names are unchanged for
reproducibility.

## Metric list

- **relationship_precision / recall / f1** *(end-to-end)* — predicate counts as correct if
  in the gold's acceptable ontology set.
- **subject / predicate / object / direction accuracy** *(matched)* — direction = correct
  ordered pair.
- **polarity / modality / temporality / scope / condition / exception accuracy** *(matched)*.
- **ontology_normalization_accuracy**, **matched_triple_accuracy** (subject+predicate+object),
  **matched_full_structure_accuracy** (all dimensions) — *matched-only*.
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
