# PRIORITY_VECTOR_SPEC — Edge Prioritization Experiment v0.1

Priority is an explicit, deterministic, **decomposable vector** over each competing
governance-source node. It is never a single opaque scalar; decisions read the
components in a fixed lexicographic order, so every winner is explainable.

## The seven components

```
priority_vector = { authority, temporal, specificity, reference,
                    structural, confidence, support }
```

| component | domain | meaning | derivation |
|---|---|---|---|
| `authority` | [0,1] | authority hierarchy — later instrument dominates | parsed `order` / max order in the case |
| `temporal` | [0,1] | temporal precedence — more recent effective date dominates | effective year normalized to the case's year range |
| `specificity` | {0.5,0.75,1.0} | relationship specificity | 1.0 named-section supersede target · 0.75 governs_over · 0.5 default-base |
| `reference` | (0,1] | reference distance — directly governing beats reached-via-reference | 1 / (1 + incoming `references` edges) |
| `structural` | [0,1] | graph centrality — more governance out-edges = more central | min(1, governance out-degree / 3) |
| `confidence` | [0,1] | relationship confidence — strongest supporting cue | max lexical confidence over the node's governance edges (from v0.2) |
| `support` | [0,1] | supporting evidence count | min(1, total out-edges / 4) |

## Determinism
Every component is a pure function of parsed structure and the v0.2 confidence
vector. No model, no sampling, no fitting; identical inputs yield an identical vector,
and two full experiment repetitions are byte-identical.

## How decisions use the vector (lexicographic, no collapse)
Among competing governance sources, the winner is the node with the lexicographically
greatest tuple over the **enabled** components in the fixed order

```
authority > temporal > specificity > reference > structural > confidence > support
```

Ablations disable trailing components (P1 keeps only `authority`; P2 adds `temporal`;
P3 adds `specificity`; P4 keeps all seven). A disabled component contributes 0 to the
comparison key, so it cannot break a tie. The decisive component — the first on which
the winner strictly beats a competitor — is recorded for every competition, so no
decision is an unexplained scalar threshold.

## What the vector drives
The ranking reorders the nodes of the graph handed to the frozen governance in the
full pipeline, so the top-ranked governance source becomes the frozen packet's
`primary`. The vector never adds/removes/retypes an edge and never runs in Mode G /
Mode P — discovery, governance Mode G, and packet Mode P are unaffected.
