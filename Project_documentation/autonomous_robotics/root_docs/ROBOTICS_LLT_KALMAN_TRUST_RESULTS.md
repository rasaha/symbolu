# Predictor-Trust — LLT-Kalman Variant Results (cross-domain port)

**Milestone:** Robotics reliability redesign, follow-up to
`ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md`.
**Code/data:** `robotics_reliability_bench/llt_kalman_trust.py`,
`detectors.py::LLTKalmanDetector`, `tune_llt_kalman.py`,
`results/llt_kalman_tune.json`, `results/incremental_value.json`.
**Status:** evaluation-only. No production path modified. **Not
preregistered** — this detector was added after
`PREDICTOR_TRUST_V2_PREREGISTRATION.md`; it follows the same TUNE/TEST and
seed discipline, but its verdict is exploratory, not a frozen decision.

---

## 1. Load-bearing question

Does the temporal channel that beat second-order BCVF in the cyber kill study
(`cyber_security/kill_study/detectors.py::llt_cusum_raw`, arm I) sharpen the
robotics deterministic baseline when ported into the predictor-trust layer?

**Answer:** it cuts detection delay by roughly two-thirds at equal recall,
attribution, and common-mode handling, and it removes the baseline's
`noisy_unbiased` false alarms — but it trades those for more false alarms on
the held-out `calibration_drift` family. Not a clean dominance. `[V]`

## 2. What was ported

Same state machine and global abstain rules as `DeterministicTrustBaseline`
(copied in semantics; `_global_decision`). Only the statistics changed:

| channel | baseline | LLT-Kalman variant |
|---|---|---|
| noise scale | pooled robust MAD over all predictors | per-predictor, per-axis, from robust first differences |
| variance / change | EWMA of standardized magnitude → DEGRADED | one-sided CUSUM on Kalman normalized-innovation surprise → DEGRADED |
| bias → SUSPECT | trailing-window mean, window 12, sustain 8 | filtered level vs its posterior variance, sustain 4 |

Kalman state `[level, slope]`, `F=[[1,1],[0,1]]`, `H=[1,0]`, missing ticks
predict-only. Q is expressed as a ratio of R so the filter is scale-free.

## 3. Tuning (TUNE families, seeds 0..19 only) `[V]`

486-config grid; 372 met the hard rule (zero TUNE false alarms, recall and
attribution 1.0); the survivor with minimum *strict-tick* delay was frozen:
`q_level_ratio=0.003, q_slope_ratio=0.001, cusum_k=2.0, cusum_h=12.0,
bias_z=4.0, bias_min_m=0.20, bias_sustain=4`. Recorded in
`results/llt_kalman_tune.json`. No threshold was changed after TEST families
were scored (a `calibration_drift` false positive observed on seed 3 while
writing tests was left as-is and is reported below).

## 4. Held-out results (seeds 100..149) `[V]`

### 4.1 Aggregate, ALL families

| system | recall ↑ | false-alarm ↓ | common-mode false-det ↓ | delay ↓ | attribution |
|---|---|---|---|---|---|
| Deterministic baseline | 1.00 | 0.040 | 0.00 | 17.0 | 0.89 |
| Fusion (baseline + BCVF) | 1.00 | 0.040 | 0.00 | 7.3 | 0.89 |
| **LLT-Kalman** | 1.00 | **0.033** | 0.00 | **6.2** | 0.89 |
| LLT-Kalman (strict tick) | 1.00 | 0.033 | 0.00 | 7.0 | 0.89 |
| Fusion (LLT + BCVF) | 1.00 | 0.033 | 0.00 | **3.1** | 0.89 |
| BCVF standalone | 0.90 | 0.667 | 0.86 | 5.0 | 0.89 |

### 4.2 Aggregate, held-out TEST families only

| system | recall | false-alarm | delay |
|---|---|---|---|
| Deterministic baseline | 1.00 | 0.02 | 15.8 |
| Fusion (baseline + BCVF) | 1.00 | 0.02 | 6.0 |
| LLT-Kalman | 1.00 | **0.10** | 5.0 |
| Fusion (LLT + BCVF) | 1.00 | 0.10 | 1.6 |

### 4.3 The decisive rows

| family | baseline | LLT-Kalman | note |
|---|---|---|---|
| `noisy_unbiased` FA | 0.10 | **0.00** | per-predictor noise scale fixes the baseline's leak |
| `calibration_drift` FA | 0.02 | **0.10** | whole-episode noise estimate under-scales late variance growth |
| `constant_bias` delay | 18.0 | **3.0** | level state converges in a few ticks |
| `precise_biased` delay | 18.0 | **3.0** | detected, unlike BCVF (missed) |
| `delayed_predictor` delay | 18.0 | **4.0** | |
| `slow_bias` delay | 23.2 | 15.0 | still the slowest; BCVF onset transient gets it to 1 in fusion |
| `accelerating` delay | 21.1 | 14.0 | fusion with BCVF: 6 |

## 5. Reading of the evidence

* **Delay gain is mostly the level test, not the CUSUM tick.** Strict-tick
  delay is 7.0 vs 6.2 with the accelerated tick; the CUSUM crossing buys under
  one tick on average. `[V]` The honest online number is therefore ~7 ticks,
  still 10 ticks better than the baseline. `[I]`
* **BCVF's residual value shrinks but does not vanish.** Over the baseline,
  BCVF fusion saved 9.7 ticks; over LLT-Kalman it saves 3.1, concentrated in
  `slow_bias` and `accelerating`. `[V]` The `AUGMENT_PREDICTOR_TRUST` position
  is unchanged in kind, smaller in size. `[I]`
* **False alarms move, not shrink.** Overall FA improves (0.040 → 0.033) but
  the TEST-only FA is five times the baseline's (0.10 vs 0.02), all from
  `calibration_drift`. Under the preregistration's "materially worse =
  doubles" rule, applied to the TEST aggregate, this is a regression on one
  benign family. `[V]`
* **Mechanism of the regression** `[I]`: `_robust_obs_noise` estimates one
  per-axis R from the whole episode. `calibration_drift` grows variance only
  after tick 20, so R is under-estimated late, the posterior level variance
  shrinks accordingly, and a 4-tick wander above 0.20 m passes the
  significance test. The baseline's 12-tick window happens to average this
  out. The principled fix is a time-varying (forgetting) noise estimate, which
  is exactly what a calibrated per-predictor covariance would supply. `[G]`
* **Runtime** is ~13 ms per episode of unoptimised Python (three scalar
  Kalman loops per predictor); not a latency claim. `[V]`

## 6. Verdict (exploratory, not preregistered)

`LLT_KALMAN_PROMISING_NOT_DOMINANT`: it should not replace the frozen
baseline on this evidence, because of the `calibration_drift` regression. It
should be carried forward as the candidate primary statistic for PTR-V2,
conditional on a preregistered rerun with an adaptive noise estimate.

## 7. Next step

Preregister and run one amendment: replace the whole-episode R with an
exponentially-forgetting robust estimate (or reported covariance when the
real-sensor pilot supplies it), re-tune on TUNE only, and require TEST-only FA
≤ baseline before any replacement claim. Keep `bias_sustain` and
`bias_min_m` frozen across that rerun so the comparison isolates the noise
model.

## 8. Caveats (binding)

* Synthetic straight-line SE(2), M=3, H=50, 50 eval seeds per family. No
  real-sensor claim.
* `correlated_failure` and `all_wrong` remain shared blind spots of every
  disagreement-only method here; the independent map/GNSS reference is still
  required.
* The added detector, its thresholds, and this verdict were not part of the
  frozen preregistration; treat them as a logged extension, not a frozen
  decision.
