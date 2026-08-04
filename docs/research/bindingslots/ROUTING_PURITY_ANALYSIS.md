# Routing-purity analysis

Every final former's frozen causal ablations at step 1200. Purity = collapses under **both**
slots-off and randomized-addressing (frozen thresholds; never averaged). Source:
`results/causal_purity_analysis.json` and `results/routing_metric_analysis.json`.

## Per-arm causal summary (final formers)

| arm | formers | slots-off collapses | randomized-address collapses | causally clean |
|---|---|---|---|---|
| R0 | s19, s21, s22 | 3/3 | 3/3 | **3/3** |
| O1 | s18–22 | 5/5 | **1/5** (only s21) | 1/5 |
| O2 | s18–22 | 2/5 | **0/5** | 0/5 |
| H3 | s19, s20, s22 | 3/3 | 1/3 | 1/3 |

The discriminating failure is **randomized-addressing**: O1/O2 retrieval survives it (retrieval does
not depend on *correct* addressing), while it collapses under slots-off (the slots are still used).
That is a diffuse / address-independent slot-read pathway, not a window-only or token-leak shortcut —
slots-off would not collapse a window shortcut.

## O1 detail

| seed | needle | slots-off | rand-addr | prob@1200 | rank | margin | overlap |
|---|---|---|---|---|---|---|---|
| 18 | 0.94 | 0.00 | 0.96 | 0.14 | 8.9 | 1.0 | 0.08 |
| 19 | 1.00 | 0.00 | 1.00 | 0.23 | 4.7 | 1.0 | 0.12 |
| 20 | 1.00 | 0.03 | 1.00 | 0.27 | 7.5 | 2.2 | 0.13 |
| 21 | 1.00 | 0.00 | 0.04 | 0.28 | 5.6 | 1.4 | 0.22 |
| 22 | 1.00 | 0.02 | 1.00 | 0.15 | 8.4 | 1.2 | 0.08 |

Low correct-slot prob (0.14–0.28), poor rank (4.7–8.9), weak margin (1.0–2.2), low overlap — the read
address is diffuse at 1200, so randomizing it barely changes the (blended) retrieved representation.

## O2 detail

O2 keeps a higher address margin early and seed 18 retains prob 0.66 at 1200, but slots-off leaves
0.058–0.37 on 3/5 (fails the ≤0.05 post-ablation bound) and randomized-address survives on 4/5. O2 is
directionally better than O1 on routing retention but still fails the frozen causal gate on every
seed.

## Interpretation

R0 (frozen CR1), when it forms, is causally clean (3/3) — its problem is *reliability/retention*
(forms 3/5, 2 collapses). O1/O2 fix reliability but at the cost of purity: they convert non-formers
into address-independent formers. Net, neither resolves purity, and none produces more clean-stable
seeds than R0. This is why the mechanical verdict is `ROUTING_PURITY_NOT_RESOLVED`.
