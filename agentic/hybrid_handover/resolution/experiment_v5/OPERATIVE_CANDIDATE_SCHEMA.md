# OPERATIVE_CANDIDATE_SCHEMA — Competing Operative Resolution Experiment v0.1

Each governing clause becomes a typed, machine-readable `OperativeCandidate`. Semantics
are derived deterministically from parsed structure — never reduced to keyword presence
for the conflict decision (keywords only seed polarity/domain, which are then combined
with structural predicates).

## Fields
| field | meaning | derivation |
|---|---|---|
| `node` | node identifier | the clause key |
| `polarity` | operative polarity (see below) | tfc signal (`policy_override`/`negation`/`Policy` → PROHIBITED; `allows` → PERMITTED; notice/penalty only → CONDITIONALLY_PERMITTED; else NON_OPERATIVE) |
| `operative_action` | the governed action | the benchmark's single matter: `terminate_for_convenience` |
| `operative_subject` | the governed actor | `contract_parties` |
| `operative_object` | the governed object | `the_agreement` |
| `scope` | scope dimensions | see OPERATIVE_SCOPE_SPEC.md |
| `answer_bearing_term` | the term the packet reads | prohibited/allowed/notice/penalty |
| `provenance` | provenance present | any outgoing validated edge |
| `relationship_path` / `support_nodes` | supporting nodes | outgoing edge destinations |
| `evidence_vector` | decomposable evidence | see below |

## Polarity categories
`REQUIRED`, `PROHIBITED`, `PERMITTED`, `CONDITIONALLY_REQUIRED`,
`CONDITIONALLY_PROHIBITED`, `CONDITIONALLY_PERMITTED`, `UNDETERMINED`, `NON_OPERATIVE`.
On this corpus the observed polarities are PROHIBITED, PERMITTED, CONDITIONALLY_PERMITTED,
and NON_OPERATIVE; the remaining categories are defined for completeness and future data.

## Evidence vector (decomposable; never a single opaque scalar)
`lexical_operative_support`, `subject_match`, `action_match`, `object_match`,
`scope_overlap`, `temporal_applicability`, `authority_applicability`,
`condition_applicability`, `graph_resolution_support`, `provenance_complete`,
`answer_term_support`. The conflict decision reads these components through the explicit
predicate battery (CONFLICT_PREDICATE_SPEC.md), not a blended probability.
