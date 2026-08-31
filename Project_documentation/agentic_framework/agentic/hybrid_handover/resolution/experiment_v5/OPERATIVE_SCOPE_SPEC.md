# OPERATIVE_SCOPE_SPEC — Competing Operative Resolution Experiment v0.1

Scope is modelled across deterministic dimensions. Where a dimension cannot be derived
its value is `UNKNOWN`; a missing value implies **neither** overlap **nor** non-overlap.

## Dimensions
| dimension | derivation | UNKNOWN when |
|---|---|---|
| entity / actor | `contract_parties` (the benchmark's fixed matter) | — |
| governed action | `terminate_for_convenience` | — |
| governed object | `the_agreement` | — |
| authority domain | instrument type → REGULATORY / CORPORATE_POLICY / CONTRACT | none of the markers present |
| temporal year | first 4-digit year in key/text | no year present |
| triggering condition | `exception` if the node is an Exception; else UNKNOWN | not derivable |
| amendment / override target | parsed `supersede_target` | absent |

Because the benchmark asks a single decision (termination-for-convenience of the
agreement by the parties), subject/action/object are the same matter across clauses and
are treated as overlapping. The discriminating dimensions on this corpus are therefore
**authority domain** and **temporal year**, plus the presence of a resolving relationship.

## Non-fabrication rule
The layer never invents a missing scope value to force either overlap or non-overlap.
Genuine conflict requires overlap to be POSITIVELY established (same authority domain,
temporal overlap, no resolving edge); if a required dimension is UNKNOWN the competition is
classified `INSUFFICIENT_SCOPE_EVIDENCE`, and the layer does **not** abstain on that basis
alone (it answers with the G3 operative), preserving coverage.
