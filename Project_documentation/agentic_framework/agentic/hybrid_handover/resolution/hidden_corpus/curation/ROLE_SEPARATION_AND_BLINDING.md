# ROLE_SEPARATION_AND_BLINDING

Three logically independent roles, kept artifact-wise separate. No separate human
identities are assumed; the guarantee is structural — the annotator artifact
carries none of the author-only fields.

## Roles and artifacts
| Role | Produces | Must NOT see |
|---|---|---|
| A Author | question, documents, intended capability, proposed difficulty, private rationale (+ private intended graph) | — |
| B Independent Annotator | graph, edge types+directions, governance, governing evidence, defeated evidence, packet expectation, abstention, ambiguity, confidence, evidence provenance | author rationale, intended graph, proposed difficulty, intended capability, expected answer, target weakness, template id, dev-case ref |
| C Adjudicator | accepted gold, governance, packet, final difficulty (rubric), ambiguity, confidence, accept/reject/quarantine rationale | (may see A and B only AFTER B is complete) |

## Blinding enforcement
`AnnotatorRecord` has no author-only field by construction; `blinding.annotator_is_blind`
asserts that the projected annotator record contains none of the banned keys.
Across all 43 candidates: **0 blinding violations**.

## Single-annotator caveat (honest)
In this environment one process authored all roles. The artifacts are separate and
blinding is structurally enforced, but true INTER-ANNOTATOR reliability requires
multiple independent human annotators. The reported agreement statistics
(ANNOTATOR_AGREEMENT.md) therefore measure author-intended vs blind-annotator
consistency within one process, not multi-human reliability — a documented
limitation, not a validated claim.
