# Phase Temporal Collector — Report

Gates and failure conditions: `PREREGISTRATION.md` (frozen at d8947260, before
implementation); budget amendment: `PREREGISTRATION_AMENDMENT_1.md`. Hardware:
4 CPU cores, no GPU; micro scale — no verdict here can exceed PROVISIONALLY
SUPPORTED. Isolation contract honored: nothing under `symbolu/lightweight_phase/`
was imported or modified.

## Sweep 1 (800 steps) — INVALID AT TESTED SCALE

Raw results: `results/sweep1_800steps/`. All 18 runs (6 arms × 3 seeds)
completed; parameters matched to <0.1% (~74.4K); shared data streams verified by
construction (shared generator seeds).

**G0 failed.** The raw-history quadratic upper reference F finished worse than
the plain-statistics arm B: E(F)=0.881 vs E(B)=0.525, RI(F vs B) = **−0.68**
(gate required ≥ +0.15). Per the frozen failure conditions: **INVALID AT TESTED
SCALE — no arm verdicts issued.** The 800-step budget did not train the
attention-over-240-raw-tokens reference past even the current-value arm
(E=0.795), consistent with `experiments/phase_lc`'s finding that retrieval
circuit formation in small quadratic models is near-threshold in compute.

E(arm) at 800 steps (mean nMSE over 4 forecast families × 2 splits; lower is
better): current 0.795 · stats 0.525 · harmonic 0.450 · real_rec 0.844 ·
phase 0.629 · raw_quad 0.881.

Observations from Sweep 1 are informational only and grant no credit (seen
before Amendment 1 was written; recorded here for audit): harmonic beat stats
in 3/3 seeds with RI 0.144 at 7.9% of F's state memory; phase beat the matched
real recurrence in 3/3 seeds but lost to fixed-clock harmonic in 3/3.

## Sweep 2 (4000 steps, Amendment 1)

*(to be appended after the amended sweep completes; the amendment commit
precedes every Sweep 2 result)*
