# ANNOTATOR_AGREEMENT

Agreement between the author's private intended graph and the blind annotator's
graph, reported on SEPARATE dimensions (never collapsed).

| Dimension | Metric | Value |
|---|---|---|
| Edge presence | precision / recall / F1 | 0.984 / 0.984 / 0.984 |
| Edge presence | exact-match rate | 0.977 |
| Governing nodes | precision / recall / F1 | 0.973 / 0.973 / 0.973 |
| Governing nodes | exact-match rate | 0.953 |
| Packet membership | exact-match rate | 0.953 |
| Abstention | exact-match rate | 0.953 |
| Abstention | Cohen's κ | 0.884 |

Node, edge-type, and edge-direction agreement are also computed per case
(`agreement.compare`). Disagreement is non-trivial: the deliberately-defective
REJECTED candidates (e.g. `rej_nonunique_gold`, `rej_resolvable_abstain`) create
genuine author↔annotator divergence, which is exactly what the adjudicator
resolves — so agreement is < 1.0 by design.

## Cohen's kappa scope (documented limitation)
κ is reported ONLY for the binary abstention decision, where chance-correction is
well-defined. It is deliberately NOT used for edge agreement: the edge universe is
sparse and open-ended (any pair of nodes, any of 12 types), so the marginal
probabilities κ needs are ill-defined. For edges we report precision/recall/F1 and
exact-match instead.

## Single-annotator caveat
As noted in ROLE_SEPARATION_AND_BLINDING.md, one process produced all roles, so
these figures measure author-intended vs blind-annotator consistency, not
multi-human inter-annotator reliability. True reliability estimation requires
independent human annotators and is future work.
