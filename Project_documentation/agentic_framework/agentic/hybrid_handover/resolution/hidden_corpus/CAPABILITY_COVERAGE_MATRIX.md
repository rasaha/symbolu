# CAPABILITY_COVERAGE_MATRIX

Coverage of each required capability in the hidden corpus (22 cases). Counts are
authored cases exercising the capability (a case may cover several).

| Capability | Cases | Depth |
|---|---:|---|
| transitive_authority | 4 | adequate seed |
| definition_inheritance | 3 | adequate seed |
| multiple_authorities | 3 | adequate seed |
| conflicting_amendments | 3 | adequate seed |
| version_supersession | 2 | thin |
| scoped_exceptions | 2 | thin |
| effective_date_precedence | 2 | thin |
| cross_document_reference | 2 | thin |
| implicit_references | 2 | thin |
| hierarchical_governance | 2 | thin |
| policy_migration | 2 | thin |
| partial_overrides | 1 | **single** |
| table_vs_text | 1 | **single** |
| appendix_precedence | 1 | **single** |
| entity_renaming | 1 | **single** |
| parallel_overrides | 1 | **single** |
| conditional_applicability | 1 | **single** |
| multi_hop | 1 | **single** |
| nested_exceptions | 1 | **single** |
| no_relationship (neg) | 1 | **single** |
| unresolvable_conflict (neg) | 1 | **single** |
| insufficient_evidence (neg) | 1 | **single** |
| circular_reference (neg) | 1 | **single** |
| multiple_valid_interpretations (neg) | 1 | **single** |

## Relationship-type coverage (gold edges)
references 6 · supersedes 4 · overrides 4 · exception_to 4 · governs_over 3 ·
conflicts_with 2 · effective_after 1 · same_as 1 · amends 1. All nine types present.

## Reading
- **Breadth: complete.** Every required capability appears at least once (zero
  uncovered).
- **Depth: shallow.** 13 of 24 capabilities have a SINGLE example, and several
  edge types (effective_after, same_as, amends) appear once. A single example
  cannot distinguish generalisation from memorisation — one case can be matched
  by a bespoke rule.

## Underrepresented capabilities (priority for expansion)
All single-example capabilities above, especially the structurally hard ones:
`parallel_overrides`, `nested_exceptions`, `multi_hop`, `conditional_applicability`,
`table_vs_text`, `partial_overrides`, and every negative control (each has one).
Target: ≥5 varied cases per capability before that capability's score is treated
as generalisation evidence.
