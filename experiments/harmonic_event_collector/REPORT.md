# HarmonicEventCollector — Report

Protocol: `PREREGISTRATION.md` (frozen at commit b61187c0, before any
implementation). Hardware: 4 CPU cores, no GPU; micro scale. Isolation
contract honored: nothing under `symbolu/lightweight_phase/` imported or
modified; the collector is a classical mechanism and is not Phase.

## Stage A — E-GATE: **FAILED on the held-out set**

**Verdict (per the frozen failure condition): eventization NOT SUPPORTED at
tested scale. Stage B does not run and no reasoning verdict is issued.**

Discipline followed: all detector engineering and threshold fitting used only
the 64 training streams (generator seed 60000; the pre-freeze iteration is
summarized below). Thresholds were selected by a gate-aware criterion on
training data only, frozen (`results/frozen_thresholds.json`), and the 128
held-out streams (seed 61000) were evaluated **exactly once** per detector.
No re-runs, no post-hoc threshold changes. (Sequencing note: fit, freeze, and
the single held-out evaluation ran in one script invocation after the
preregistration commit; the code was committed after that invocation, with the
held-out set never touched during development.)

### Held-out results (frozen thresholds)

| Metric | E-GATE | HarmonicEventCollector | StatChangeDetector (baseline, informational) |
|---|---|---|---|
| `rare_aperiodic` recall | ≥ 0.95 | **0.929** ✗ | 0.893 |
| macro recall | ≥ 0.90 | **0.824** ✗ | 0.531 |
| min family recall | ≥ 0.85 | **0.699** ✗ (`periodic_deviation`) | 0.115 |
| reduction | ≥ 100× | **112.8×** ✓ | 124.9× |
| precision (informational) | — | 0.477 | 0.436 |

Per-family held-out recall (HEC): quasi_periodic 0.926 · rare_aperiodic 0.929
· regime_change 0.815 · phase_shift 0.753 · periodic_deviation 0.699.

### Reading the failure

- **Not overfitting.** Train macro 0.839 vs held-out 0.824 — the frozen
  thresholds generalized; the detector simply cannot reach the owner-set
  recall levels at ≥100× reduction on this stream distribution. Even on
  training data the best gate margin was negative (train min-family 0.768,
  rare 0.910).
- **Where it falls short.** The transient families are nearly there
  (quasi-periodic 0.93, rare 0.93 vs 0.95 required); the persistent/subtle
  families are the real gap — one-off periodic deviations (0.70) and phase
  shifts (0.75) get masked when they occur inside the disturbed window that
  follows an earlier event (the seasonal reference is invalid there), and
  amplitude-reduction regime changes on long-period signals reveal themselves
  more slowly than the ±24-sample matching tolerance allows.
- **The comparative claim survives, the absolute one does not.** HEC beats the
  statistical change detector decisively everywhere (macro 0.824 vs 0.531; on
  persistent families by 3–7×) — harmonic structure clearly helps
  eventization. But the preregistered question was absolute ("good enough to
  trust the event stream"), and the answer at this scale is no: at ~113×
  reduction, roughly 1 in 4 meaningful events is missed and half the emitted
  events are false alarms.

### Pre-freeze engineering record (training streams only)

Iterations before the freeze, recorded for audit: naive multi-clock
reconstruction (level-triggered) flooded emissions (~155/stream); quiet-window
edge triggering fixed the flood but exposed reconstruction quality as the
binding constraint; per-clock deconvolution of the exponential-average
attenuation was unstable (reconstruction error ~2× signal) and was abandoned;
the final detector uses the clock bank to select and refine the dominant
period (accumulator rotation rate + local autocorrelation refinement), a
median-of-3 seasonal reference as the expected value, a robust residual
variance tracker, and four trigger channels (surprise, surprise-CUSUM,
seasonal envelope ratio, gated dominant-clock angle change).

## What this closes and what it leaves open

Per the frozen failure condition this experiment is **closed** at Stage A:
eventization NOT SUPPORTED at tested scale; no reasoning (Stage B) verdict
exists, so nothing here speaks for or against harmonic summaries improving
event-based quadratic reasoning. The Sweep 3 result of
`experiments/phase_temporal_collector` (harmonic summaries beat statistical
summaries for a quadratic reader; G1 PROVISIONALLY SUPPORTED) stands
unaffected, as does the closed `experiments/phase_lc` verdict.

Any further eventization work is a **new experiment requiring new owner
ratification** — with a fresh held-out set, and either a materially stronger
detector (the per-family numbers above say where: post-event masking and
slow-reveal regime changes) or owner-reconsidered gate levels/tolerances if
0.95/0.90/0.85 at 100× was stricter than the intended operating point. This
report takes no position on which; that is the owner's call.
