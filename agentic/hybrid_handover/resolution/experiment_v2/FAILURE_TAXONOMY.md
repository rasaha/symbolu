# FAILURE_TAXONOMY — Proposal Validation Experiment v0.1

Frequency of each rejection category when the full validator (V4) runs over the
hidden pilot. Every rejected proposal is categorized by the single gate that
rejected it (gates are evaluated in the fixed order of the rulebook).

| category | rejections |
|---|---|
| unsupported_wording | 0 |
| authority_mismatch | 0 |
| temporal_mismatch | 0 |
| missing_destination_evidence | 0 |
| missing_source_evidence | 0 |
| graph_contradiction | 0 |
| duplicate_edge | 0 |
| relationship_ambiguity | 4 |
| low_evidence | 0 |
| type_conflict | 0 |

- **Total proposals evaluated:** 43
- **Rejected:** 4 (incorrect removed: 4; correct mistakenly rejected: 0)
- **Accepted:** 39 (correct: 35; still-spurious: 4)

Every rejection on the hidden set falls in a single category —
`relationship_ambiguity` — all four being spurious `same_as` alias proposals
between distinct policies. No correct edge was rejected in any category. The
authority/temporal, duplicate, evidence, and low-confidence gates did not fire on
this corpus (the v0.1 proposals do not violate those constraints here), which is
itself informative: on this pilot the precision leak is concentrated in ambiguous
alias proposals, not in wrong-direction or unsupported edges.
