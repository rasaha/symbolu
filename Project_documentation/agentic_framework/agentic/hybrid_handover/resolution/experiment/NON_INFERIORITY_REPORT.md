# Non-Inferiority Report — Table 3 (hybrid vs GraphTraversal)

Frozen margins from the preregistration. A macro gain does NOT count as success
if any constraint is violated.

| constraint | candidate | base | delta | margin | violated |
|---|---|---|---|---|---|
| discovery_precision | 0.8140 | 1.0000 | -0.1860 | 0.0500 | **YES** |
| governance_accuracy_modeG | 0.6000 | 0.6000 | 0.0000 | 0.0300 | no |
| packet_realization_accuracy_modeP | 0.5167 | 0.5167 | 0.0000 | 0.0300 | no |
| selective_accuracy | 0.2982 | 0.3333 | -0.0351 | 0.0300 | **YES** |
| false_abstention_rate | 0.0000 | 0.0000 | 0.0000 | 0.0500 | no |
| missed_abstention_rate | 0.2167 | 0.2667 | -0.0500 | 0.0500 | no |
| answer_coverage | 0.9500 | 1.0000 | -0.0500 | 0.1000 | no |
| unsafe_answers | 2 | 2 | 0 | — | no |

**Passes non-inferiority: no.**

Two constraints are violated: discovery precision falls 0.186 (margin 0.05) —
the broad proposal lexicon over-fires on the more varied hidden wording — and
selective accuracy falls 0.0351 (margin 0.03), because the richer graph leads the
frozen governance to answer a few more cases, some of them wrong. Critically, the
unsafe/overconfident answer count does NOT increase (2 vs 2), false-abstention
does not rise, and determinism holds. The failure is a precision/selectivity
trade-off, not a safety regression.
