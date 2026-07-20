# UPDATED_CAPABILITY_COVERAGE (seed + accepted pilot)

Combined coverage after the pilot. Every capability now has **≥3 total** cases
(no single-example capabilities remain).

| Capability | seed | pilot | total |
|---|---:|---:|---:|
| appendix_precedence | 1 | 5 | 6 |
| conditional_applicability | 1 | 5 | 6 |
| effective_date_precedence | 2 | 4 | 6 |
| hierarchical_governance | 2 | 4 | 6 |
| multiple_authorities | 3 | 3 | 6 |
| scoped_exceptions | 2 | 4 | 6 |
| transitive_authority | 4 | 2 | 6 |
| conflicting_amendments | 3 | 2 | 5 |
| cross_document_reference | 2 | 3 | 5 |
| definition_inheritance | 3 | 2 | 5 |
| policy_migration | 2 | 3 | 5 |
| table_vs_text | 1 | 4 | 5 |
| version_supersession | 2 | 3 | 5 |
| circular_reference | 1 | 3 | 4 |
| entity_renaming | 1 | 3 | 4 |
| implicit_references | 2 | 2 | 4 |
| multi_hop | 1 | 3 | 4 |
| nested_exceptions | 1 | 3 | 4 |
| parallel_overrides | 1 | 3 | 4 |
| unresolvable_conflict | 1 | 3 | 4 |
| insufficient_evidence | 1 | 2 | 3 |
| multiple_valid_interpretations | 1 | 2 | 3 |
| no_relationship | 1 | 2 | 3 |
| partial_overrides | 1 | 2 | 3 |

## Relationship types (accepted pilot edges)
references 17 · exception_to 13 · governs_over 7 · overrides 6 · supersedes 5 ·
conflicts_with 4 · same_as 4 · amends 2 · effective_after 1.

## Difficulty (adjudicated pilot): L1 4 · L2 9 · L3 13 · L4 7 · L5 5
## Negative controls (pilot new): no_relationship 2 · unresolvable_conflict 3 · insufficient_evidence 2 · circular_reference 3 · multiple_valid_interpretations 2 (each ≥3 counting seed)

## Remaining gaps
- `effective_after` edge type still single-example (1); `amends` only 2.
- Variation dimensions now include `sentence_structure` and `clause_numbering`
  (previously uncovered).
- Depth density: L5 has 5 (target met) but is still thin relative to a
  certification corpus.
