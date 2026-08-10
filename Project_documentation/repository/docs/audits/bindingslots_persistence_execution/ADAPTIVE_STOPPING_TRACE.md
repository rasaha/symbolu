# Adaptive stopping trace

The merged adaptive controller (`adaptive_plan.next_action`) drove execution. Verified by replay:
`build_execution_report.py` reconstructs the exact run sequence from committed evidence
(`replay_reproducible: true`).

## Sequence (24 runs; max 30)

| order | run | clean_stable | note |
|---|---|---|---|
| 0–4 | A+ 23–27 | — | mandatory reference (no futility) |
| 5–9 | R0 23–27 | 2/5 | mandatory reference (no futility) |
| 10–12 | O1R 23,24,25 | CS,x,x | **2nd failure at s25 → futile**, s26/s27 `ARM_FUTILITY_REACHED` |
| 13–15 | H1 23,24,25 | CS,x,x | **2nd failure at s25 → futile**, s26/s27 skipped |
| 16–18 | H2 23,24,25 | x,CS,x | **2nd failure at s25 → futile**, s26/s27 skipped |
| 19–23 | O1 23–27 | diagnostic | frozen O1 trigger (all candidates failed); **not selectable** |
| — | TERMINAL | — | `NO_PERSISTENCE_INTERVENTION_SELECTED` |

## Futility mathematics

Each candidate stopped at its **second** non-CLEAN_STABLE seed: with two failures, clean-stable ≥ 4/5
is impossible. O1R, H1, H2 each ran 3 seeds instead of 5 → **6 runs saved** vs the full matrix (24 vs
30). No seed was stopped before step 1200; futility applied only *between* completed seeds.

## Discipline

Unrun seeds (O1R/H1/H2 s26,s27) are `ARM_FUTILITY_REACHED`, **not** failed or inferior. O1 ran only
because all three candidates failed, and is never selectable. No best-checkpoint selection, no
outcome-based seed reordering, no tuning.
