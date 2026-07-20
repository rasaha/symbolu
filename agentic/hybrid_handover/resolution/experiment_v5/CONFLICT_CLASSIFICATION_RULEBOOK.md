# CONFLICT_CLASSIFICATION_RULEBOOK — Competing Operative Resolution Experiment v0.1

Every apparent competition between two operative candidates is classified into exactly one
PRIMARY category, evaluated in this fixed deterministic order (first match wins).

| order | condition | category |
|---|---|---|
| 1 | outcomes are compatible (not {PROHIBITED,PERMITTED}) | `COMPATIBLE_OPERATIVES` |
| 2 | a `supersedes` edge resolves it | `RESOLVED_BY_SUPERSESSION` |
| 3 | an `overrides` edge resolves it | `RESOLVED_BY_OVERRIDE` |
| 4 | an `exception_to` edge resolves it | `RESOLVED_BY_EXCEPTION` |
| 5 | a `governs_over`/`same_as`/`amends` edge resolves it | `GENUINE_RESOLVED_CONFLICT` |
| 6 | positively temporally separated | `TEMPORALLY_SEPARATED` |
| 7 | an exception condition separates them | `CONDITIONALLY_SEPARATED` |
| 8 | authority domains derived and different | `DIFFERENT_AUTHORITY_DOMAIN` |
| 9 | authority overlap not positively established | `INSUFFICIENT_SCOPE_EVIDENCE` |
| 10 | all conflict predicates pass | `GENUINE_UNRESOLVED_CONFLICT` |

Secondary categories (`PARALLEL_APPLICABILITY`, `CUMULATIVE_REQUIREMENT`,
`NO_SCOPE_OVERLAP`) may also be recorded on the candidates' role sets; the primary
category above drives the abstention decision.

## Resolution semantics
- **Supersession / temporal:** the superseding operative controls within the superseded
  scope; a dated split makes the two temporally separated, not conflicting.
- **Scoped override:** the override displaces the other only inside the documented conflict
  scope; both may remain applicable elsewhere.
- **Exception:** controls only where its condition applies; the general rule is not globally
  suppressed.
- **Parallel / different domain:** candidates governing distinct authority domains are
  preserved as parallel — never forced into a single winner.
- **Cumulative:** two compatible requirements are both retained.
- **Genuine unresolved conflict:** two simultaneously applicable, same-domain,
  temporally-overlapping, incompatible operatives with no resolving relationship → the only
  category that triggers governance-stage abstention.
