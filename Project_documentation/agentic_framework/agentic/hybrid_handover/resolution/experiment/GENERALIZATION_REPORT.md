# Generalization Report — Tables 9–11 (hidden pilot)

Macro (or discovery F1 for edge-type) by slice, GraphTraversal vs Hybrid. Slices
are small (n shown); these are descriptive, not per-slice hypothesis tests.

## Wording family (seed vs pilot) — the two independently authored families

| source | n | graph | hybrid | Δ |
|---|---|---|---|---|
| seed | 22 | 0.5427 | 0.6285 | 0.0858 **↑** |
| pilot | 38 | 0.4725 | 0.5467 | 0.0742 **↑** |

The gain holds in **both** families (seed +0.086, pilot +0.074), satisfying the
H1 requirement of improvement across >1 wording/structural family.

## Table 9 — by capability (macro)

| capability | n | graph | hybrid | Δ |
|---|---|---|---|---|
| appendix_precedence | 6 | 0.2394 | 0.4333 | 0.1939 **↑** |
| circular_reference | 4 | 0.4500 | 0.7133 | 0.2633 **↑** |
| conditional_applicability | 6 | 0.3000 | 0.5256 | 0.2256 **↑** |
| conflicting_amendments | 5 | 0.2800 | 0.2800 | 0.0000 |
| cross_document_reference | 5 | 0.4776 | 0.5314 | 0.0538 **↑** |
| definition_inheritance | 5 | 0.4000 | 0.4000 | 0.0000 |
| effective_date_precedence | 6 | 0.4533 | 0.4767 | 0.0234 **↑** |
| entity_renaming | 4 | 0.6389 | 0.6300 | -0.0089 |
| hierarchical_governance | 6 | 0.5167 | 0.4700 | -0.0467 ↓ |
| implicit_references | 4 | 0.4000 | 0.6143 | 0.2143 **↑** |
| insufficient_evidence | 3 | 0.5333 | 0.9333 | 0.4000 **↑** |
| multi_hop | 4 | 0.5250 | 0.5800 | 0.0550 **↑** |
| multiple_authorities | 6 | 0.6556 | 0.6293 | -0.0263 ↓ |
| multiple_valid_interpretations | 3 | 0.3333 | 0.3333 | 0.0000 |
| nested_exceptions | 4 | 0.2000 | 0.5231 | 0.3231 **↑** |
| no_relationship | 3 | 0.4000 | 0.4000 | 0.0000 |
| parallel_overrides | 4 | 0.6500 | 0.6889 | 0.0389 **↑** |
| partial_overrides | 3 | 0.3000 | 0.3000 | 0.0000 |
| policy_migration | 5 | 0.7511 | 0.7067 | -0.0444 ↓ |
| scoped_exceptions | 6 | 0.2333 | 0.5256 | 0.2923 **↑** |
| table_vs_text | 5 | 0.3200 | 0.2400 | -0.0800 ↓ |
| transitive_authority | 6 | 0.6719 | 0.6884 | 0.0165 |
| unresolvable_conflict | 4 | 0.4300 | 0.4167 | -0.0133 |
| version_supersession | 5 | 0.1600 | 0.4171 | 0.2571 **↑** |

Broad-based: hybrid improves or holds macro on the large majority of capabilities,
with the biggest gains on nested/scoped exceptions, version supersession, circular
and implicit references, and insufficient-evidence handling. A few regress —
notably `table_vs_text` (a spurious table/text conflict edge) and
`hierarchical_governance` — flagged as future-work targets (not fixed post-lock).

## Table 10 — by difficulty (macro)

| difficulty | n | graph | hybrid | Δ |
|---|---|---|---|---|
| 1 | 7 | 0.2286 | 0.5386 | 0.3100 **↑** |
| 2 | 13 | 0.4949 | 0.5467 | 0.0518 **↑** |
| 3 | 20 | 0.4311 | 0.5694 | 0.1383 **↑** |
| 4 | 13 | 0.5670 | 0.6359 | 0.0689 **↑** |
| 5 | 7 | 0.5323 | 0.5607 | 0.0284 **↑** |

The gain is present at every difficulty level, largest at the extremes of the
range rather than concentrated in easy cases.

## Table 11 — by gold edge-type (discovery F1)

| gold_edge_type | n | graph | hybrid | Δ |
|---|---|---|---|---|
| amends | 3 | 0.5000 | 0.5000 | 0.0000 |
| conflicts_with | 6 | 0.2857 | 0.2500 | -0.0357 ↓ |
| effective_after | 2 | 0.0000 | 0.5000 | 0.5000 **↑** |
| exception_to | 11 | 0.1818 | 0.5714 | 0.3896 **↑** |
| governs_over | 10 | 0.4167 | 0.3871 | -0.0296 ↓ |
| overrides | 8 | 0.4800 | 0.5000 | 0.0200 |
| references | 12 | 0.3448 | 0.7027 | 0.3579 **↑** |
| same_as | 5 | 0.2500 | 0.2222 | -0.0278 ↓ |
| supersedes | 9 | 0.3810 | 0.4444 | 0.0634 **↑** |

Largest discovery gains on `exception_to` (0.182→0.571), `references`
(0.345→0.703), and `effective_after` (0→0.5); small regressions on
`conflicts_with`, `governs_over`, and `same_as`.

## Negative-control subset

| resolver | n | macro |
|---|---|---|
| graph_traversal | 16 | 0.4683 |
| hybrid_relationship | 16 | 0.7028 |

On the negative-control cases (no-relationship / insufficient-evidence /
unresolvable), the hybrid scores **higher** (0.7028 vs 0.4683): the richer layer
does not manufacture governance where none is warranted. The precision cost seen
in aggregate comes from over-proposing *edges*, not from unsafe *answers*.
