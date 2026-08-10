# EDGE_REJECTION_ANALYSIS — Proposal Validation Experiment v0.1

Every edge the validator rejected on the hidden pilot, with its confidence
vector and whether the (src,dst) pair is a genuine gold relationship.

## Rejected edges (all four)

| case | proposed edge | reason | in gold? | confidence vector |
|---|---|---|---|---|
| HX59d7a3eb1c | Policy P-7 p.2 --same_as--> Policy P-8 (effective 2024) p.1 | relationship_ambiguity | no | lex 0.7, struct 1.0, auth 1.0, ref 1.0 |
| HP6f0fac771c | Policy N-1 p.2 --same_as--> Standard S-9 p.1 | relationship_ambiguity | no | lex 0.7, struct 1.0, auth 1.0, ref 1.0 |
| HP7d8d12efac | Policy T-1 p.2 --same_as--> Policy T-2 (effective 2025) p.1 | relationship_ambiguity | no | lex 0.7, struct 1.0, auth 1.0, ref 1.0 |
| HPb3463204c9 | Policy V-1 p.2 --same_as--> Policy V-2 (effective 2025) p.1 | relationship_ambiguity | no | lex 0.7, struct 1.0, auth 1.0, ref 1.0 |

All four rejections are spurious `same_as` proposals linking two *different*
policies (e.g. `Policy P-7` ↔ `Policy P-8`). v0.1's rename/migration branch fired
on a migration cue and paired policies that share neither a version lineage nor a
section number; the alias-validity gate (`relationship_ambiguity`) removed each.
Their confidence vectors are instructive: lexical/structural/authority/reference
all look healthy (0.7 / 1.0 / 1.0 / 1.0) — a single blended score would have
**kept** them. The decomposed vector plus the type-specific predicate is what
distinguishes a real alias from an ambiguous one.

## Correct proposals mistakenly rejected

**None (0).** No gold edge was removed by any gate; discovery recall is unchanged.

## Residual spurious edges the validator did NOT catch (honest limitation)

4 spurious edges survived validation: `governs_over`×3, `overrides`×1.
These have real destinations and consistent authority/ordering, so the current
structural gates accept them. Catching them would need a governance-aware check
(does this `governs_over`/`overrides` edge actually change the resolved outcome?)
which is beyond this experiment's frozen rulebook and is logged as future work.
