# Preregistration Amendment 1 — training budget only

**Written:** after observing Sweep 1's G0 validity failure
(`results/sweep1_800steps/`), and before any Sweep 2 run exists. The amendment
is frozen at the commit that introduces this file.

**What Sweep 1 showed.** G0 failed: the raw-history quadratic upper reference F
finished *worse* than the plain-statistics arm B (E(F)=0.881 vs E(B)=0.525,
RI(F vs B) = −0.68). Per the frozen failure conditions, Sweep 1 is **INVALID AT
TESTED SCALE** and no arm verdicts were issued. The proximate cause is
undertraining of the attention-over-raw-history reference at the 800-step
budget — consistent with `experiments/phase_lc`'s observation that retrieval
circuit formation in small quadratic models is near-threshold in compute.

**The only change.** Training steps per run: 800 → **4000** (validation cadence
250 steps; cosine LR horizon follows the step count, as already coded). Applied
identically to all six arms. Nothing else changes: gates G0–G2 and every
threshold, the arms, the metric E, the families and pools, parameter matching,
seeds {0,1,2}, batch size, learning rate, selection rule, and evaluation sets
are exactly as in `PREREGISTRATION.md`.

**What is not permitted off the back of Sweep 1.** Sweep 1's informational
observations (the harmonic arm's RI over stats, the phase arm's advantage over
the real recurrence) were seen before this amendment; they grant no credit and
soften no gate. If G0 fails again at 4000 steps, the outcome is INVALID AT
TESTED SCALE (compute-bound upper reference) and any further budget increase
requires a new amendment, again before its runs.
