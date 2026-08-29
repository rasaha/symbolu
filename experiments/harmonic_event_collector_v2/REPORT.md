# HarmonicEventCollector V2 — Report

Protocol: `PREREGISTRATION.md` (frozen at commit 3d9efaaa, before
implementation). Fresh data throughout (train seed 70000, held-out seed
71000); V1's held-out set was never touched. Isolation, naming, and non-claim
contracts honored.

## Stage A — E-GATE: **FAILED on the fresh held-out set. This line is closed
permanently** per the owner-ratified terminal rule: no Stage B, no V3, no
threshold changes, no reasoning verdict.

### Held-out results (frozen parameters and thresholds)

| Metric | E-GATE | HEC V2 | HEC V1 (its own held-out, for reference) | Stat baseline (unchanged) |
|---|---|---|---|---|
| rare_aperiodic recall | ≥ 0.95 | **0.897** ✗ | 0.929 | 0.821 |
| macro recall | ≥ 0.90 | **0.803** ✗ | 0.824 | 0.484 |
| min family recall | ≥ 0.85 | **0.730** ✗ | 0.699 | 0.189 |
| reduction | ≥ 100× | **110.3×** ✓ | 112.8× | 122.0× |
| precision (informational) | — | 0.454 | 0.477 | 0.391 |

Per-family held-out recall (V2): quasi_periodic 0.881 · rare 0.897 ·
phase_shift 0.770 · regime_change 0.737 · periodic_deviation 0.730.
Frozen config: res 4.0 · ang 0.8 · env 0.7 · cus 10 · ecus 7 · mag disabled ·
refractory 24 · protect 32 (`results/frozen_thresholds.json`).

### Reading the result

- **The corrections did not help.** V2's held-out macro (0.803) is slightly
  below V1's (0.824). Train (0.801) and held-out (0.803) agree almost exactly
  — the protocol held and the fit generalized; the mechanisms themselves are
  the shortfall. Pre-freeze diagnostics on training data had already shown the
  imputation-based protection roughly neutral (small gain on phase_shift,
  small losses elsewhere, extra false positives eroding the reduction budget)
  and the envelope-ratio CUSUM adding little at viable thresholds.
- **A process lesson recorded for future preregistrations.** V2's
  preregistration froze the *mechanism internals* (imputation form, flag
  threshold, channel definitions), not just the gates, data discipline, and
  one-shot evaluation. When training-data diagnostics later suggested a better
  form of "protection" (masking disturbed lags out of the seasonal median
  rather than imputing values), the freeze correctly barred it. Preregister
  what counts as evidence; leave implementation internals iterable on training
  data until the threshold freeze, as V1 did.
- **What survives.** The comparative claim is confirmed a second time on fresh
  data: harmonic structure beats plain change detection at eventization by a
  wide margin (macro 0.803 vs 0.484; persistent families by 3–4×). The
  absolute claim — a ≥100×-compressed event stream trustworthy enough
  (0.95/0.90/0.85) to be reasoning's only input — has now failed twice at this
  scale, on honest one-shot evaluations both times.

## Standing conclusions for the research program

1. Continuous harmonic summaries for a quadratic reader: PROVISIONALLY
   SUPPORTED (`experiments/phase_temporal_collector`, Sweep 3, G1) — the
   durable positive result.
2. Harmonic eventization better than statistical change detection:
   supported comparatively (V1 and V2, informational).
3. An event-bottleneck-only pipeline at 100× compression: NOT SUPPORTED at
   tested scale (V1 and V2, preregistered one-shot evaluations). This
   empirically supports the original two-memory design constraint: compact
   summaries and raw-evidence retrieval, not a detected-events-only stream.
4. No reasoning (Stage B) verdict exists in either V1 or V2; nothing here
   touches Sweep 3's G1, and nothing reverses `experiments/phase_lc`.

The recorded next experiment for the program remains validation on real data
(telemetry or varṇa-aligned acoustics), where the proven component —
continuous harmonic summary tokens plus raw-evidence retrieval — applies
directly and ground-truth event labels are not required. Any return to
synthetic eventization would require new owner ratification and would be a new
experiment, not a continuation of this one.
