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

## Sweep 2 (4000 steps, Amendment 1) — INVALID AT TESTED SCALE

Raw results: `results/sweep2_4000steps/`. All 18 runs completed with no errors;
parameters matched to <0.13% (~74.4–74.5K); shared data streams as before.

**G0 failed again.** The raw-history quadratic upper reference F still finished
worse than plain statistics: E(F)=0.595 vs E(B)=0.464, RI(F vs B) = **−0.28**
(gate requires ≥ +0.15). This is a large improvement over Sweep 1 (RI went
−0.68 → −0.28 — the 5× step budget did help F substantially) but the upper
reference still has not overtaken even arm B, let alone established a ceiling
the other arms are being measured against. Per Amendment 1's own terms: *"If G0
fails again at 4000 steps, the outcome is INVALID AT TESTED SCALE
(compute-bound upper reference) and any further budget increase requires a new
amendment, again before its runs."*

**Verdict: INVALID AT TESTED SCALE.** No G1 or G2 credit is issued. Per the
preregistration's own discipline, a third budget increase is not applied
unilaterally — it requires a new amendment authored and committed before any
further run, which in turn requires a decision on whether to keep scaling
compute on this hardware (CPU, no GPU) or change the reference architecture.

E(arm) at 4000 steps (mean nMSE, lower is better): current 0.786 · stats 0.464
· harmonic 0.310 · real_rec 0.537 · phase 0.458 · raw_quad 0.595.

**Informational only (G0 gates the whole sweep; no arm credit follows from
these numbers):**
- Harmonic vs stats: RI = 0.331, 3/3 seeds, at 7.9% of F's state memory
  (38 vs 480 floats). This is the largest and most consistent margin in either
  sweep.
- Phase vs the matched real recurrence D: RI = 0.147, 3/3 seeds — Phase again
  beats the conventional linear-recurrence control.
- Phase vs harmonic C: RI = **−0.477**, 0/3 seeds — the learned Phase collector
  is *worse* than the fixed-clock harmonic features in both sweeps, by a wider
  margin at 4000 steps than at 800. This is the one result that held sign and
  grew stronger with more training, which weighs against it being a
  training-budget artifact.

## Interpretation

Two sweeps at increasing budget point the same direction on the part of the
question G0 does not gate: fixed-clock harmonic accumulators (arm C) beat
learned recurrences of any kind (D, E) on these synthetic families, at a
fraction of the memory. That is consistent with the periods being drawn from
known pools and the harmonic bank being tuned (log-spaced, K=8, 4→128) to
roughly span them — an advantage a truly unknown or continuously varying period
structure would not hand the fixed-clock arm. It is also consistent with the
`phase_lc` finding that Phase's learned content-derived phase is not obviously
better than simpler alternatives at this compute scale.

None of this can be promoted past INVALID AT TESTED SCALE while G0 fails: the
harness has not yet demonstrated that raw-history attention — the thing all
other arms are supposed to approximate — actually does better than a handful of
decayed statistics on this task. Until G0 passes, "harmonic beats phase" is a
comparison between two compression schemes with no proof either one is worth
compressing toward.

## Recommended next step (requires an owner decision, not taken unilaterally)

Options, in order of cost:
1. **New amendment, larger step budget** (e.g. 12,000–16,000 steps) on this
   CPU-only hardware — cheap to write, expensive to run (Sweep 2 already used
   ~2 hours of wall clock; a 3–4× increase is proportionally longer).
   Risk: F may still be compute/architecture-bound rather than step-bound.
2. **New amendment, change F's ceiling role** — e.g. give F more capacity
   headroom specifically (not matched to the other arms) so it functions as a
   true oracle ceiling rather than a parameter-matched arm, and re-derive G0
   against that unconstrained ceiling. This changes what G0 measures and should
   not be decided without ratification.
3. **Stop here.** Report INVALID AT TESTED SCALE as the final micro-scale
   verdict and flag GPU-scale replication as the exact-next-experiment, per the
   preregistration's own scope caveat (CPU micro scale cannot yield PROVEN
   regardless of gate outcome).

This report does not select among these — that is an owner decision per the
task-progression discipline (owner ratification before further implementation).
No claim here reverses the closed `experiments/phase_lc` semantic-retrieval
verdict, and no capability is described as implemented beyond what these 36
runs measured.
