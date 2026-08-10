# ADVERSARIAL_RESOLVERS — Which Metrics Can a Cheat Max?

Six deliberately weak "cheating" resolvers that do NO genuine relationship
reasoning. If any maxes a component metric, that metric is not evidence of
relationship reasoning. Run via `run_audit.adversarial_audit`.

## The cheats
`always_abstain` · `always_first_document` · `always_latest` ·
`always_override` (last-word-wins) · `always_allowed` · `null` (empty).

## Results (Mode A; gold: 5 abstain / 11 non-abstain)

| Metric | Maxed (≥0.99) by | Verdict |
|---|---|---|
| `relationship_edge_recall` | — (0.00 for all) | **ROBUST** |
| `relationship_edge_precision` | — | **ROBUST** |
| `precedence_resolution_accuracy` | — (0.00) | **ROBUST** |
| `override_resolution_accuracy` | — | **ROBUST** |
| `version_selection_accuracy` | — (max 0.50) | robust-ish (half-gameable) |
| `conflict_resolution_accuracy` | — | **ROBUST** |
| `cross_document_link_accuracy` | — | **ROBUST** |
| `abstention_accuracy` | `always_abstain` | **GAMEABLE** |
| `cycle_detection_accuracy` | `always_abstain` | **GAMEABLE** |
| `coverage_abstention_accuracy` | `always_abstain` | **GAMEABLE** |
| `definition_resolution_accuracy` | first / latest / override / allowed | **GAMEABLE** |
| `exception_resolution_accuracy` | first / latest / override / allowed | **GAMEABLE** |
| `negation_interpretation_accuracy` | first / latest / override | **GAMEABLE** |
| `relationship_type_accuracy` | ALL cheats incl. `null` | **NON-DISCRIMINATING** |

`always_abstain` reaches 1.0 on cycle/abstention **while falsely abstaining on
11/11 non-abstain cases**. `always_latest` and `always_override` reach **6/16**
end-to-end — equal to the weak FrozenResolver — so 6/16 is the trivial floor.

## Why each gameable metric fails
- **abstention / cycle / coverage-abstention**: computed only over cases whose
  correct answer *is* abstain, so a resolver that abstains on everything scores
  1.0. There is no penalty for false abstention. → add a false-abstention rate;
  condition detection credit on it.
- **definition / exception resolution**: these cases' expected *answers*
  (a notice period) do not depend on the definition/exception, which is a
  distractor. A resolver that ignores it entirely still gets the answer. → these
  outcome metrics don't test the capability; measure the `conflicts_with` /
  `exception_to` **edge** instead.
- **negation interpretation**: single-node; the shared answer-deriver reads the
  negation attribute, so any node-picker passes. → it is a packet-construction /
  logical metric, not relationship reasoning; reclassify.
- **relationship_type_accuracy**: node typing is done by the shared parser, so it
  is ~1.0 for every resolver including `null`. → it measures the parser, not the
  resolver; reclassify as a parser sanity metric.

## Takeaway
The **discovery** metrics (edge precision/recall) and the genuine
governance/outcome metrics (precedence, override, version, conflict, cross-doc)
are trustworthy. The **abstention-linked** and **distractor-based** capability
metrics, and the shared-stage metrics (negation, type accuracy), are not — and
must be corrected before freeze.
