# Preregistration Amendment 2 — structural corrections, final micro-scale sweep

**Written:** after Sweep 2's second G0 failure, before any Sweep 3 run exists;
frozen at the commit that introduces this file. Owner-ratified: one final
structurally corrected sweep; **no further budget-only increases**. If G0 fails
again, this micro-scale experiment closes with INVALID AT TESTED SCALE and the
exact-next-experiment is GPU-scale replication.

## The four structural changes (owner-ratified)

1. **Dense supervision.** Sweep 1–2 gave each stream only 3 supervised targets.
   Now: arm F trains as a *causal* transformer with forecast/event loss at every
   position t ∈ [16, 240); summary arms (A–E, G) train at 16 cutoff positions
   sampled uniformly per batch from [32, 240] (vs 3 fixed). This asymmetry is
   declared: it favors making F a valid ceiling, which is G0's purpose.
   **Evaluation is unchanged** — the gated metric E is still computed at the
   frozen cutoffs {128, 192, 240} on the frozen test sets, so E remains
   comparable across sweeps.
2. **Multi-frequency time encoding for F.** F's input gains sinusoidal features
   of τ at the same log-spaced periods as the clock bank (4→128), so attention
   can phase-match rather than regress on one scalar time channel. Declared
   plainly: this hands F fixed-clock Fourier features — arm C's mechanism.
3. **Log-spaced decay horizons for D and E.** Sweep 1–2 initialized every decay
   channel at γ ≈ 0.953 (horizon ≈ 21 steps) against periods up to 96 and
   cutoffs to 240. Now: per-channel init log-spaced over horizons 8 → 512.
4. **New arm G `learned_complex_oscillator` (`osc`).** Complex diagonal state
   transition — rotation lives in the *state*, not the input:
   `S_t = exp((−1/h + iω)·dt_t) ⊙ S_{t−1} + a_k(u_t) ⊙ v(u_t)`, with per-channel
   learnable horizon h (init log-spaced 8→512) and frequency ω (init 2π/P,
   P log-spaced 4→128). Input gating identical to arm D. This is diagonal-SSM /
   LRU-style architecture. **It is not Phase and is never labeled Phase:** the
   frozen Phase equations put rotation on the input with a real-decay state; if
   G wins, the honest finding is that moving rotation into the state transition
   produced a useful temporal collector, consistent with diagonal state-space
   models — not a validation of the frozen Phase equations.

Unchanged: families and period pools, seeds {0,1,2}, batch 24 streams,
4000 steps, lr 2e-3 cosine, val-based selection, <1% parameter matching (target
recomputed over the 7 arms), isolation contract (nothing under
`symbolu/lightweight_phase/` imported or modified).

## Gates

G0 and G1: **unchanged** from PREREGISTRATION.md.

G2 is extended for the presence of G, stated as explicit nMSE inequalities
(lower is better; RI(a vs b) = (E(b) − E(a))/E(b) with E(arm) the frozen metric):

- **G2′ — Phase mechanism (credited iff all hold):**
  RI(phase vs harmonic) ≥ 0.05, RI(phase vs real_rec) ≥ 0.05, and
  RI(phase vs osc) ≥ 0.05, each seed-averaged; and
  nMSE E(phase) < E(harmonic), E(phase) < E(real_rec), E(phase) < E(osc)
  in 3/3 seeds each.
- **G3 — Oscillator utility (new; credited iff all hold):**
  RI(osc vs harmonic) ≥ 0.05 and RI(osc vs real_rec) ≥ 0.05, seed-averaged;
  and E(osc) < E(harmonic) and E(osc) < E(real_rec) in 3/3 seeds each.

A G3 pass credits the diagonal-SSM architecture, not Phase. A G3 pass with a
G2′ failure reads: SSM succeeds; Phase does not.

## New informational splits (never gated)

The gated metric E keeps its frozen definition (4 forecast families × in-dist +
held-out-frequency splits). Two additional test splits are reported
informationally, per the owner's correction that a learned oscillator does not
automatically generalize to unseen periods:

- **extrapolation:** periods from [108, 140] — outside the training span
  [6, 96] and at/beyond the clock bank's upper edge (128);
- **freq_drift:** a sinusoid whose period drifts linearly by up to ±30% across
  the stream (phase integrated), built from train-pool base periods; appears
  only at test time, never in training.

These diagnose whether C's fixed bank, G's learned ω, and E's content-derived
phase interpolate, extrapolate, or merely memorize the synthetic pools.

## Outcome classification (frozen)

| Result | Meaning |
|---|---|
| G0 fails | micro-benchmark still invalid → **close the experiment** (no further amendments; GPU-scale replication is the exact-next-experiment) |
| G0 passes, C best | fixed harmonic collector remains best → pursue the classical collector |
| G0 + G3 pass, G2′ fails | learned oscillator/diagonal SSM promising; Phase is not → continue as SSM research |
| G0 + G2′ pass | original Phase mechanism earns renewed investigation |
| G0 passes, G1 fails | compact summaries (all of them) fail to approach the valid ceiling |

Sweep 1–2 results remain archived and untouched; no observation from them
gains credit retroactively. Verdicts remain capped at PROVISIONALLY SUPPORTED
(CPU micro scale). Nothing here reverses the closed `experiments/phase_lc`
semantic-retrieval verdict.
