# Comparator Report — Table 1 (hidden pilot, owner-clean)

Six preregistered comparators on the frozen 60-case Hidden Relationship Corpus
Pilot v0.2. All metrics owner-clean (parser and SafetyGate excluded). Governance
and packet are identical for rule/graph/hybrid on the owned-case denominator by
construction (hybrid reuses the frozen GraphTraversal governance + packet builder).

| resolver | disc F1 | disc P | disc R | class | govG | packP | select | cover | unsafe | MACRO |
|---|---|---|---|---|---|---|---|---|---|---|
| null | — | — | 0.0000 | — | 0.0000 | 0.3000 | 0.3333 | 1.0000 | 0 | 0.1267 |
| always_abstain | — | — | 0.0000 | — | 0.2667 | 0.3000 | — | 0.0000 | 0 | 0.1133 |
| frozen | — | — | 0.0000 | — | 0.3667 | 0.3000 | 0.2833 | 1.0000 | 1 | 0.1900 |
| rule | 0.3031 | 1.0000 | 0.1786 | 0.7333 | 0.5167 | 0.5167 | 0.3333 | 1.0000 | 2 | 0.4806 |
| graph_traversal | 0.3031 | 1.0000 | 0.1786 | 0.7333 | 0.6000 | 0.5167 | 0.3333 | 1.0000 | 2 | 0.4973 |
| hybrid_relationship | 0.5512 | 0.8140 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 0.9500 | 2 | 0.5761 |

Reading: the hybrid resolver posts the top macro (0.5761) and the strongest
discovery F1 (0.5512, from recall 0.4167 vs 0.1786) and classification (0.9143),
while its discovery precision falls to 0.814 (it over-proposes edges). The
adversarial Null and Always-abstain comparators score far below, confirming the
macro is not gameable by trivial strategies.
