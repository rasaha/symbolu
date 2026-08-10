# Predictor-Trust — Incremental-Value Results & Verdict (Parts 4–5)

**Milestone:** Robotics reliability redesign.
**Preregistered:** `PREDICTOR_TRUST_V2_PREREGISTRATION.md` (committed
`e7c0b69`, before this benchmark ran).
**Code/data:** `robotics_reliability_bench/run_incremental_value.py`,
`results/incremental_value.json`. Eval seeds 100–149 (held out from tuning).

---

## 1. Comparison: current BCVF vs deterministic baseline vs fusion

Three systems on identical inputs (the metric semantics are frozen in the
prereg). Aggregates below; per-family detail follows.

### 1.1 Aggregate over ALL detectable-harm / benign families

| system | recall ↑ | false-alarm ↓ | common-mode false-det ↓ | delay (ticks) ↓ | attribution ↑ | runtime µs |
|---|---|---|---|---|---|---|
| **Deterministic baseline** | **1.00** | **0.04** | **0.00** | 17.0 | 0.89 | 5562 |
| BCVF (kernel, standalone) | 0.90 | 0.67 | 0.86 | **5.0** | 0.89 | 603 |
| **Fusion (baseline + BCVF)** | **1.00** | **0.04** | **0.00** | 7.3 | 0.89 | 6073 |

### 1.2 Aggregate over HELD-OUT TEST families only

| system | recall ↑ | false-alarm ↓ | delay ↓ | attribution ↑ |
|---|---|---|---|---|
| Deterministic baseline | 1.00 | 0.02 | 15.8 | 0.83 |
| BCVF standalone | 0.86 | **1.00** | **2.4** | 0.83 |
| Fusion | 1.00 | 0.02 | 6.0 | 0.83 |

### 1.3 The two decisive per-family rows

**Benign false-alarm rate (detected_rate; lower better):**

| family | Deterministic | BCVF | Fusion |
|---|---|---|---|
| gaussian_noise | 0.00 | 0.00 | 0.00 |
| noisy_unbiased | 0.10 | **1.00** | 0.10 |
| calibration_drift | 0.02 | **1.00** | 0.02 |

**`precise_biased` (a confident, low-noise, biased sensor):**

| | Deterministic | BCVF | Fusion |
|---|---|---|---|
| detected | **1.00** | **0.00** | **1.00** |
| attribution | **1.00** | **0.00** | **1.00** |

### 1.4 Where BCVF actually helps — detection delay on visible faults

| family | Deterministic delay | BCVF delay | Fusion delay |
|---|---|---|---|
| accelerating | 21.1 | 6.0 | 6.0 |
| abrupt_jump | 9.8 | 0.0 | 0.0 |
| stuck_sensor | 10.0 | 0.0 | 0.0 |
| constant_bias | 18.0 | 11.0 | 11.0 |
| slow_bias | 23.2 | 1.0 | 1.0 |
| precise_biased | 18.0 | — (missed) | 18.0 |

BCVF's margin signal crosses earlier than the baseline's conservative
8-tick-sustain bias test, so it detects *visible* disagreement faster. Fusion
inherits that earlier tick **only when it agrees with the baseline's
attribution**, and keeps the baseline's detection on `precise_biased` (which
BCVF misses entirely).

## 2. Reading of the evidence

* **Recall:** deterministic 1.00 vs BCVF 0.90 — BCVF's shortfall is entirely
  `precise_biased`, a safety-relevant miss.
* **False alarms:** BCVF fires on **every** benign high-variance family
  (noisy_unbiased 1.0, calibration_drift 1.0); the baseline stays ≤0.10. In a
  fleet this is the difference between rare and constant spurious interventions.
* **Common-mode:** BCVF fabricates a detection on `all_wrong` 86% of the time
  (false confidence in an undetectable situation); the baseline stays silent.
* **Attribution tie (0.89):** the baseline wins `precise_biased` (1.0 vs 0.0);
  BCVF wins `stale_predictor` attribution (1.0 vs baseline 0.0 — but the
  baseline *does* surface the stale predictor, via ABSTAIN/exclusion, which the
  attribution metric under-credits). Net: a wash.
* **BCVF's sole real advantage is latency**, and it is **fully recoverable** as
  an optional feature: Fusion cuts baseline delay 17.0→7.3 while holding recall
  1.0, FA 0.04, common-mode 0.00.

## 3. Verdicts (against the frozen decision rules)

### Action track → **`REPLACE_ACTION_BCVF`**
Counterexamples all reproduce; deterministic selectors never pick a
hard-inadmissible candidate and BCVF picks unsafe in 3/4 scenarios
(`ROBOTICS_ACTION_SELECTION_BASELINES.md`). The forward/backward consistency
Lagrangian is replaced by a deterministic constrained selector.

### Predictor-trust track → **`AUGMENT_PREDICTOR_TRUST`**
Standalone, BCVF meets the `BCVF_NO_INCREMENTAL_VALUE` bar (no better recall;
false-alarm and common-mode rates far worse). It is **not** retained as the
primary trust mechanism. It **is** retained as an **optional, off-by-default
disagreement-dynamics feature** that reduces detection latency on
BCVF-visible faults (Δdelay −9.7 ticks in Fusion) **without** degrading recall,
false-alarm, or common-mode handling — exactly the augmentation the prereg's H3
allows. The deterministic innovation + EWMA/CUSUM + freshness detector becomes
the primary predictor-trust layer.

**Combined position:** option **D** from the milestone goal — rename and
reposition around a deterministic reliability architecture, with BCVF demoted
to a named internal feature (see naming in `ROBOTICS_V2_MIGRATION_PLAN.md`).

## 4. What would change these verdicts

* Real-sensor data where genuine failures are dominated by *accelerating*
  divergence and benign predictors are *low-variance* would narrow BCVF's
  false-alarm penalty and widen its latency edge — possibly to
  `AUGMENT` becoming `RETAIN` for the predictor feature. This is the pilot to
  run before productionizing either direction.
* A predictor stack that reports calibrated per-predictor covariance would let
  the deterministic baseline use true NIS (not a robust-MAD proxy), likely
  widening its lead further.

## 5. Caveats (binding)

* **Synthetic** straight-line SE(2); **no real-sensor claim**; the 1,560-cell
  characterization is not cited as real-world evidence.
* N=50 seeds/family. Effect sizes on the load-bearing metrics (FA 0.04 vs 0.67;
  precise_biased 1.0 vs 0.0) are large, but this is a decision-grade signal, not
  a certification.
* The deterministic baseline's runtime (≈5.5 ms) is unoptimized evaluation code
  (triple-nested Python), **not** a production latency claim; BCVF's ≈0.6 ms is
  the vectorized kernel. Latency is not a deciding factor either way.
* `correlated_failure` (2-of-3) and `all_wrong` are shared blind spots of *all*
  disagreement-only methods; neither system "wins" them, and the redesign must
  add an independent reference (map/GNSS cross-check) to cover them — out of
  scope for this study.
