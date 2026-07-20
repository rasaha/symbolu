# GOVERNANCE_DIAGNOSTIC_SUBGROUPS — Governance Semantics Experiment v0.1

Diagnostic only (no implementation change from these). Selective accuracy on
answered cases; small cells, descriptive.

## Table 12 — seed vs pilot

| family | G0 selective | G4 selective |
|---|---|---|
| seed | 0.3810 | 0.5000 |
| pilot | 0.2500 | 0.5556 |

## Table 13 — by difficulty

| difficulty | G0 selective | G4 selective |
|---|---|---|
| 1 | 0.1429 | 0.0000 |
| 2 | 0.4167 | 1.0000 |
| 3 | 0.3158 | 0.3750 |
| 4 | 0.4167 | 0.5000 |
| 5 | 0.0000 | 1.0000 |

## By capability

| capability | G0 selective | G4 selective |
|---|---|---|
| appendix_precedence | 0.0000 | — |
| circular_reference | 0.6667 | — |
| conditional_applicability | 0.0000 | 1.0000 |
| conflicting_amendments | 0.4000 | 0.0000 |
| cross_document_reference | 0.0000 | — |
| definition_inheritance | 1.0000 | — |
| effective_date_precedence | 0.0000 | 1.0000 |
| entity_renaming | 0.7500 | 1.0000 |
| hierarchical_governance | 0.1667 | 1.0000 |
| implicit_references | 0.0000 | — |
| insufficient_evidence | 1.0000 | — |
| multi_hop | 0.0000 | — |
| multiple_authorities | 0.1667 | 1.0000 |
| multiple_valid_interpretations | 0.6667 | 0.0000 |
| nested_exceptions | 0.0000 | 0.0000 |
| no_relationship | 1.0000 | 1.0000 |
| parallel_overrides | 0.2500 | 0.7500 |
| partial_overrides | 0.0000 | 0.0000 |
| policy_migration | 0.4000 | 1.0000 |
| scoped_exceptions | 0.0000 | 0.5000 |
| table_vs_text | 0.0000 | 0.0000 |
| transitive_authority | 0.5000 | 1.0000 |
| unresolvable_conflict | 0.7500 | 0.0000 |
| version_supersession | 0.0000 | — |

Note: G4 cells reflect its reduced answered set (coverage collapse), so per-slice
G4 selective is not comparable to G0 on equal denominators; the clean comparison is
G3 (GOVERNANCE_ABLATIONS.md), which holds coverage fixed.
