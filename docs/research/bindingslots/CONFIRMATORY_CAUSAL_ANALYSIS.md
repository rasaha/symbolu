# Confirmatory replication — causal analysis

Every CR1 seed classified as **formed** must collapse under **both** slots-off and randomized
addressing (frozen thresholds; never averaged across seeds). Source:
`experiments/bindingslots_confirmatory/results/causal_gate_output.json`.

## Per forming seed (needle@d96)

| seed | baseline | slots-off | randomized-address | shuffle-values | A+ | slots-off gate | rand-addr gate | verdict |
|---|---|---|---|---|---|---|---|---|
| 15 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | PASS | PASS | **clean** |
| 16 | 1.000 | 0.017 | **0.450** | 0.492 | 0.008 | PASS | **FAIL** | **unclean** |
| 17 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | PASS | PASS | **clean** |

Collapse threshold per ablation: drop ≥ 0.050 absolute **and** ≥ 50 % of the slot gain removed
**and** post-ablation ≤ max(A+ + 0.030, 0.050).

## Reading

- **Seeds 15 and 17** are cleanly slot-causal: disabling the slot contribution (slots-off) or
  disrupting slot addressing (randomized-address) each drops retrieval from 1.000 to 0.000. Retrieval
  is grounded in the slots.
- **Seed 16 is not causally clean.** Slots-off collapses it (0.017), but **randomized addressing
  leaves 0.450** — nearly half the retrieval survives when slot *addresses* are randomized. That is
  the signature of a pathway that uses slot *content* without depending on correct slot *addressing*
  (a shortcut/window-assisted route), not a cleanly address-routed slot circuit. `shuffle_values`
  0.492 corroborates a value-carrying but weakly-addressed pathway.

This is the same failure class the merged Stage A used to **reject the curriculum-only arm (C1)** —
retrieval that is not cleanly slot-attributable. Here it appears on one of the three fresh CR1
formers, so gate C9 fails.

## Discipline

The individual failure on seed 16 propagates to an aggregate causal failure; it is **not** averaged
away by the two clean seeds. One causally-unclean forming seed is sufficient to fail the confirmatory
replication.
