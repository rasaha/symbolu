# Predictor-Trust — LLT-Kalman Variant Results (cross-domain port)

**Milestone:** Robotics reliability redesign, follow-up to
`ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md`.
**Code/data:** `robotics_reliability_bench/llt_kalman_trust.py`,
`detectors.py::LLTKalmanDetector`, `tune_llt_kalman.py`,
`results/llt_kalman_tune.json`, `results/incremental_value.json`.
**Status:** evaluation-only. No production path modified. Two stages: **A0**
(§2–§6) was added after `PREDICTOR_TRUST_V2_PREREGISTRATION.md` and is
exploratory; **A1** (§7) was preregistered as amendment §7 A1 before scoring
and carries a frozen decision rule. Headline verdict: **`A1_ADOPT`**.

---

## 1. Load-bearing question

Does the temporal channel that beat second-order BCVF in the cyber kill study
(`cyber_security/kill_study/detectors.py::llt_cusum_raw`, arm I) sharpen the
robotics deterministic baseline when ported into the predictor-trust layer?

**Answer:** yes, once the noise model is time-varying. A0 (whole-episode
noise estimate) cut detection delay by roughly two-thirds at equal recall,
attribution, and common-mode handling, but traded the baseline's
`noisy_unbiased` false alarms for `calibration_drift` false alarms. The
preregistered amendment A1 (forgetting noise estimate) removes that
regression: recall 1.00, false-alarm 0.000, common-mode 0.00, delay 6.3
ticks vs the baseline's 17.0, on held-out seeds. `[V]`

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

## 6. Verdict A0 (exploratory, not preregistered)

`LLT_KALMAN_PROMISING_NOT_DOMINANT`: A0 should not replace the frozen
baseline on this evidence, because of the `calibration_drift` regression.
That regression is the subject of amendment A1 below.

---

## 7. Amendment A1 — time-varying noise estimate (preregistered)

Preregistered in `PREDICTOR_TRUST_V2_PREREGISTRATION.md` §7 A1 and committed
(`7d2186d2`) before any A1 configuration was scored on evaluation seeds.

### 7.1 The single change `[V]`

`_robust_obs_noise` (one R per axis per episode) is replaced by
`forgetting_obs_noise`: a causal MAD warm-up over the first 6 fresh first
differences, then `s_t² = λ s_{t-1}² + (1-λ) clip(e_t², 0, 9 s_{t-1}²)` with
`e_t` the drift-compensated first difference over √2. The Kalman filter
consumes `R_t` per tick; `Q` stays a ratio of the current `R_t`. Nothing
else changed; `noise_forgetting=None` reproduces A0 exactly (pinned by test).

### 7.2 Tuning (TUNE families, seeds 0..19 only) `[V]`

486-config grid with `bias_sustain=4` carried over frozen and `λ ∈ {0.80,
0.90, 0.95}` added; 198 survivors; chosen by the same rule as A0 (min
strict-tick TUNE delay 8.28, ties to larger `cusum_h` then `bias_z`):
`q_level_ratio=0.01, q_slope_ratio=0.003, cusum_k=2.0, cusum_h=12.0,
bias_z=4.0, bias_min_m=0.20, bias_sustain=4, λ=0.9`. Frozen as
`llt_kalman_trust.A1_CONFIG`; recorded in `results/llt_kalman_tune_A1.json`.

### 7.3 Held-out results (seeds 100..149) `[V]`

| system | recall | FA all | FA TEST-only | common-mode | delay (default tick) | delay (strict tick) |
|---|---|---|---|---|---|---|
| Deterministic baseline | 1.00 | 0.040 | 0.02 | 0.00 | 17.0 | — |
| Fusion (baseline + BCVF) | 1.00 | 0.040 | 0.02 | 0.00 | 7.3 | — |
| LLT-Kalman A0 | 1.00 | 0.033 | 0.10 | 0.00 | 6.2 | 7.0 |
| **LLT-Kalman A1** | **1.00** | **0.000** | **0.00** | **0.00** | **6.3** | **7.0** |
| Fusion (LLT-A1 + BCVF) | 1.00 | 0.000 | 0.00 | 0.00 | 3.1 | — |

Per-family A1 rows: `calibration_drift` FA **0.00** (A0: 0.10; baseline:
0.02); `noisy_unbiased` FA 0.00; `gaussian_noise` FA 0.00. Delays:
`constant_bias` 3.0, `precise_biased` 3.1, `delayed_predictor` 4.0,
`linear_drift` 7.9, `abrupt_jump` 1.0, `stuck_sensor` 2.8, `slow_bias` 14.7,
`accelerating` 13.9. Attribution 0.89 (all) / 0.83 (TEST), identical to every
other system (the `stale_predictor` attribution under-credit noted in the
original study). All previously committed rows are byte-stable.

### 7.4 Decision rule applied `[V]`

Preregistered `A1_ADOPT` requires: TEST-only recall 1.00 ✅; TEST-only FA ≤
0.02 ✅ (0.00); ALL-family delay ≤ 8.0 under the default tick ✅ (6.30);
common-mode false detection 0.00 ✅.

**Verdict: `A1_ADOPT`.** `[V]` The forgetting noise estimate removes the
`calibration_drift` regression completely and costs 0.1 tick of delay. A1 now
dominates the frozen deterministic baseline on every load-bearing metric:
equal recall, attribution, and common-mode handling; false-alarm 0.000 vs
0.040; delay 6.3 vs 17.0 (strict-tick 7.0). `[V]`

### 7.5 What this means for the redesign `[I]`

* The mechanism hypothesis in §5 was correct: the A0 regression was the
  noise model, not the Kalman level test.
* The candidate primary statistic for PTR-V2 is now the A1 variant, not the
  windowed-mean baseline. This is a bench-level finding on synthetic data;
  it does not alter the production migration gates (real-sensor pilot,
  shadow logs, HIL reachability, external review).
* BCVF's residual value as an optional latency feature persists (fusion 3.1
  vs 6.3), concentrated in `slow_bias` and `accelerating`. The
  `AUGMENT_PREDICTOR_TRUST` position is unchanged in kind.

## 8. Next step

Carry A1 into the real-sensor pilot as the primary predictor-trust
statistic, with the same TUNE/TEST discipline. Where the predictor stack
reports calibrated covariance, feed it as `R_t` directly and re-run; the
forgetting estimator is the fallback when no covariance is reported.

## 9. Caveats (binding)

* Synthetic straight-line SE(2), M=3, H=50, 50 eval seeds per family. No
  real-sensor claim.
* `correlated_failure` and `all_wrong` remain shared blind spots of every
  disagreement-only method here; the independent map/GNSS reference is still
  required.
* A0 (its thresholds and §6 verdict) was not preregistered; treat it as a
  logged extension. A1 was preregistered before scoring (§7 A1 of the
  preregistration), but as an amendment to a study whose systems it was not
  part of; it is decision-grade evidence for the bench, not a safety case.
