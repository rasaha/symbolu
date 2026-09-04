# Predictor-Trust — LLT-Kalman Variant Results (cross-domain port)

**Milestone:** Robotics reliability redesign, follow-up to
`ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md`.
**Code/data:** `robotics_reliability_bench/llt_kalman_trust.py`,
`detectors.py::LLTKalmanDetector`, `tune_llt_kalman.py`,
`results/llt_kalman_tune.json`, `results/incremental_value.json`.
**Status:** evaluation-only. No production path modified. Three stages:
**A0** (§2–§6) was added after `PREDICTOR_TRUST_V2_PREREGISTRATION.md` and
is exploratory; **A1** (§7) was preregistered and passed its decision rule
(`A1_ADOPT`) on the white-noise corpus; **A2** (§8), a preregistered
realistic-noise pilot, **failed** (`A2_FAILS`) and scopes `A1_ADOPT` to
white noise. The real-sensor gate is **not discharged**.

---

## 1. Load-bearing question

Does the temporal channel that beat second-order BCVF in the cyber kill study
(`cyber_security/kill_study/detectors.py::llt_cusum_raw`, arm I) sharpen the
robotics deterministic baseline when ported into the predictor-trust layer?

**Answer:** on white noise, yes; on correlated noise, not as frozen. A1
(forgetting noise estimate) dominates the baseline on the held-out
straight-line corpus: recall 1.00, false-alarm 0.000, common-mode 0.00,
delay 6.3 vs 17.0 ticks. `[V]` On the realistic-noise pilot (AR(1)
α=0.8), A1's false-alarm rate rises to 0.222 against the baseline's 0.156,
its attribution falls to 0.50, and it flags 83 % of benign 400-tick
scenes; the preregistered verdict is `A2_FAILS`. `[V]` The cause is the
difference-based noise estimate plus the short sustain, both of which are
over-confident under correlated wander (§8.4). `[I]`

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

---

## 8. Amendment A2 — realistic-noise pilot (preregistered; `A2_FAILS`)

**Header label: `REAL_SENSOR_GATE_NOT_DISCHARGED`.** Preregistered in the
preregistration §7 A2 (commit `1ef40fd0`) before any bundle was scored.
Code/data: `robotics_reliability_bench/a2_realistic_pilot.py`,
`results/a2_realistic_pilot.json`, `test_a2_realistic_pilot.py`.

### 8.1 Why this is not a real-sensor pilot `[V]`

`NuScenesAdapter` is scaffolding that raises `NotImplementedError`; no
nuScenes or KITTI data exists on disk; `nuscenes.org` is unreachable from
the execution environment. The pilot therefore uses the repository's
`RealisticNoiseAdapter` (AR(1) correlated noise α=0.8, σ=0.02 on all three
axes; 2 % outlier frames at 5×) plus bench-side dropouts. It is
**synthetic-realistic**, and the migration gate "real-sensor pilot" remains
open. `[G]`

### 8.2 Setup `[V]`

No tuning: every system ran its frozen configuration on fresh seeds
200..229 (30 per family), scored by `metrics.py` unchanged.
R1 = the 14 corpus families injected on realistic nominal streams (M=3,
T=100, dropouts P=0.2). R2 = adapter-native scenes (M=4, T=400).
Covariance arm: not applicable, the adapter reports none. `[G]`

### 8.3 Results `[V]`

R1 aggregate (all families):

| system | recall | false-alarm | common-mode false-det | delay | attribution |
|---|---|---|---|---|---|
| Deterministic baseline | 1.00 | 0.156 | 0.00 | 18.0 | 0.67 |
| **LLT-Kalman A1** | 1.00 | **0.222** | **0.233** | 6.6 | **0.50** |
| BCVF standalone | 0.20 | 0.667 | 0.00 | 12.3 | 0.19 |
| Fusion (LLT-A1 + BCVF) | 1.00 | 0.222 | 0.233 | 6.4 | 0.50 |

R2 (adapter-native), A1 vs baseline:

| family | baseline det / attr / delay | A1 det / attr / delay |
|---|---|---|
| gps_multipath | 1.00 / 1.00 / 18.3 | 1.00 / **0.43** / 10.0 |
| map_misalignment (same injection as above) | 1.00 / 1.00 / 18.2 | 1.00 / **0.17** / 10.2 |
| constant_bias_sanity | 1.00 / 1.00 / 18.0 | 1.00 / **0.37** / 3.0 |
| camera_degradation (variance fault; M4 ≥ DEGRADED rate) | 1.00 | 1.00 |
| **benign_native** (T=400) FA | 0.00 | **0.83** |

Decision rule: C1 recall ✅, C2 false-alarm ❌ (0.222 > 0.156), C3
common-mode ❌ (0.233), C4 delay ✅, C5 H2-reproduces ✅ (BCVF recall 0.20,
FA 0.667), C6 native attribution ❌, C7 native benign ❌. **`A2_FAILS`.**
Frozen thresholds were not changed after scoring.

### 8.4 Mechanism (post-hoc diagnostic, no tuning) `[I]`

Ablation on benign R1-style streams, A1 suspect-any rate over 30 seeds:
iid noise 0.00; **AR(1) only 0.20**; outliers only 0.00; AR(1)+outliers
0.23; AR(1)+outliers at T=400 0.80. The baseline is 0.00 in every cell.
`[V]` So the failure is correlated noise, not heavy tails or dropouts.

Why: A1 estimates `R_t` from first differences, which under AR(1) measures
the innovation scale, not the stationary wander (median `R_t` σ=0.05 at
the floor vs stationary 0.029 m on y; 0.078 m-equivalent on heading after
the 2.5 lever arm, with excursions to 0.6). With a small `Q`, the Kalman
level state follows a slow correlated excursion as if it were an offset;
it crosses the 0.20 m physical floor on the lever-scaled heading axis,
`z ≥ 4` is trivially met, and `bias_sustain=4` confirms it in four ticks.
Every false SUSPECT is a `bias(0.21–0.29 m)` on that mechanism. The
baseline's 12-tick window, sustain 8, and pooled scale average the same
wander out. `[I]` Spurious SUSPECTs on two predictors then trigger the
global no-trusted-majority ABSTAIN, which is what collapses attribution
(A1 abstain rate 0.4–0.57 on harm families) and produces the
common-mode false detections on `all_wrong`. `[V]`

The baseline is not immune either: `noisy_unbiased` FA rises to 0.40 and
attribution falls to 0.67 on the same streams. `[V]` BCVF collapses
outright (recall 0.20). `[V]`

### 8.5 What this changes `[I]`

* **`A1_ADOPT` (§7) is scoped to white noise.** On correlated noise the
  A1 statistic is over-confident and should not be the primary PTR-V2
  statistic as frozen. The synthetic held-out win (§7.3) was real but
  narrow: the A1 corpus and the realistic adapter differ exactly on the
  axis that matters.
* The two knobs that bought A1's delay win, `bias_sustain=4` and a
  difference-based `R_t`, are the two that fail under AR(1). This is the
  expected trade, now measured.
* Nothing here supports or refutes any real-sensor claim. `[G]`

### 8.6 Recommended next amendment (A3, to be preregistered)

Model the correlated noise instead of averaging over it: augment the LLT
state with an AR(1) noise component (level, slope, coloured-noise state),
so the level test's posterior variance is calibrated under correlated
wander, and apply the physical bias floor per axis (heading in radians,
not lever-scaled). Keep `bias_sustain`, `bias_z`, `bias_min_m` frozen.
Tune on the A1 TUNE families **plus** an AR(1) benign family (TUNE only),
then require A2's C1–C7 on fresh seeds before any adoption claim. Do not
re-tune A1 against the A2 seeds.

## 9. Next step

Preregister and run A3 as described in §8.6. The real-sensor pilot remains
blocked on dataset access (`NuScenesAdapter` implementation and an
authenticated nuScenes-mini download), which no amendment here discharges.

## 10. Caveats (binding)

* Synthetic straight-line SE(2), M=3, H=50, 50 eval seeds per family. No
  real-sensor claim.
* `correlated_failure` and `all_wrong` remain shared blind spots of every
  disagreement-only method here; the independent map/GNSS reference is still
  required.
* A0 (its thresholds and §6 verdict) was not preregistered; treat it as a
  logged extension. A1 was preregistered before scoring (§7 A1 of the
  preregistration), but as an amendment to a study whose systems it was not
  part of; it is decision-grade evidence for the bench, not a safety case.
