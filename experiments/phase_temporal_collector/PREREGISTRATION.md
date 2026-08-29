# Phase Temporal Collector — Preregistration

**Question:** do compact temporal summaries improve a matched quadratic reader over
ordinary statistical summaries — and if so, is the *learned Phase mechanism* the
part that earns the credit, or does fixed-clock harmonic feature engineering
suffice?

**Status:** preregistered before any training run. Numeric gates and failure
conditions below are frozen at the commit that introduces this file; results and
the report land in later commits. Hardware: 4 CPU cores, 15 GB RAM, no GPU —
micro scale. By repo protocol no verdict here can exceed PROVISIONALLY SUPPORTED.

**Isolation contract:** nothing under `symbolu/lightweight_phase/` is imported or
modified. Arm E re-implements the frozen equations of
`symbolu/lightweight_phase/reference_equations.md` (§2–§5: learned content-derived
phase/amplitude projections, complex decayed state, query readout with detached
normalizer) conceptually, at collector scale. A win by the fixed-clock harmonic
arm is a feature-engineering result and does **not** reverse the closed
`experiments/phase_lc` verdict (Phase semantic retrieval: FALSIFIED AT TESTED
SCALE), nor does any outcome here claim production readiness.

## Task

Synthetic scalar streams of length T=256, channels (value `x_t`, spacing `dt_t`),
cutoffs t_c ∈ {128, 192, 240}. At each cutoff the reader predicts the next H=8
values (MSE) and, for the rare-event family, whether an event onset occurs in
(t_c, t_c+8] (BCE/AUC). All arms additionally receive one query token holding the
8 future time offsets (needed for the irregular family; given to every arm
identically).

Five stream families: `periodic` (2 sinusoids), `drifting` (sinusoid + random
walk + slope), `phase_shift` (sinusoid with 1–2 random phase jumps),
`irregular` (sinusoid at irregularly spaced timestamps), `rare_event`
(noise + quasi-periodic decaying spikes). Train periods drawn from
[6,12]∪[20,36]∪[64,96]; **held-out-frequency** test periods from [14,18]∪[44,56]
(rare_event: train [64,96], held-out [44,56]). Fixed harmonic clock bank: K=8
periods log-spaced 4→128, chosen a priori (blind to the pools).

## Arms (matched)

| Arm | Collector state at cutoff | Learned collector |
|---|---|---|
| A `current` | current value only | no |
| B `stats` | decayed mean/variance/trend at 3 timescales | no |
| C `harmonic` | B + K=8 fixed-clock decayed complex accumulators `S_P ← γ_P S_P + x_t e^{−i2πτ_t/P}` | no |
| D `real_rec` | gated real diagonal learned recurrence `h ← γ⊙h + a_k(u)⊙v(u)` | yes |
| E `phase` | complex learned recurrence `S ← γ⊙S + a_k(u)e^{−iφ_k(u)}⊙v(u)`, query readout `Re(q⊙S)/Z`, detached Z | yes |
| F `raw_quad` | full raw history, quadratic attention (upper reference) | — |

Shared: identical 2-layer quadratic transformer reader (d=64, 4 heads) over the
arm's tokens; total trainable parameters matched across arms to <1% by tuning the
reader FFN width; identical data streams (shared generator seeds), optimizer,
step budget, cutoffs, and evaluation sets. Seeds: {0, 1, 2}. Model selection by
validation loss on a fixed validation set.

## Primary metric

Per family and split, nMSE = test MSE / variance of that cell's targets.
`E(arm)` = mean nMSE over the 4 forecast families {periodic, drifting,
phase_shift, irregular} × 2 splits {in-dist, held-out-frequency} (8 cells),
seed-averaged. Relative improvement RI(a vs b) = (E(b) − E(a)) / E(b).
Rare-event forecast nMSE and event AUC are reported but not gated.
Memory(arm) = floats of carried per-stream collector state at t_c=240 (raw
history counts as state for F).

## Gates (frozen)

- **G0 — validity:** RI(F vs B) ≥ 0.15. If G0 fails, the task is not
  history-dependent beyond ordinary statistics: outcome INVALID AT TESTED SCALE,
  no arm verdicts issued.
- **G1 — practical temporal collection (credited iff all hold):**
  1. RI(C vs B) ≥ 0.10 seed-averaged, and E(C) < E(B) in 3/3 seeds;
  2. gap closure (E(B) − E(C)) / (E(B) − E(F)) ≥ 0.70;
  3. Memory(C) ≤ 15% of Memory(F) at t_c=240, and O(1) in T by construction.
- **G2 — Phase mechanism (credited iff all hold):**
  RI(E vs C) ≥ 0.05 and RI(E vs D) ≥ 0.05, seed-averaged, and E(E) < E(C) and
  E(E) < E(D) in 3/3 seeds each.

## Failure conditions (frozen)

- G0 fails → INVALID AT TESTED SCALE; report and stop.
- G0 passes, G1 fails → practical temporal collection NOT SUPPORTED at tested
  scale.
- G1 passes, G2 fails → learned Phase collector NOT SUPPORTED at tested scale
  (fixed-clock harmonic features suffice); G1 credit stands but is credited to
  classical feature engineering, not to the Phase mechanism.
- G1 and G2 pass → both PROVISIONALLY SUPPORTED (micro scale; scale-up required
  before any stronger label).
- Under every outcome: no reversal of the `phase_lc` semantic-retrieval verdict;
  no capability described as implemented beyond what these runs measure.

Informational (not gated): held-out-frequency RI for C (does the fixed bank
interpolate between clock periods), rare-event AUC deltas, per-family tables.
