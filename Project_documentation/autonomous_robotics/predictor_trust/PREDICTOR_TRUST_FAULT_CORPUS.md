# Predictor-Trust Fault Corpus

**Milestone:** Robotics reliability redesign — Part 4 (held-out fault families)
**Status:** Frozen. Generator: `robotics_reliability_bench/fault_corpus.py`
**Scope note:** This corpus is **synthetic**. It is a controlled discriminator
for detector *logic*, not a real-sensor validation. No claim here transfers to
real-sensor safety (see caveats).

---

## 1. Purpose

A deterministic, seeded set of SE(2) predictor-trajectory bundles `(M, H, 3)`
(`[x, y, theta]`) that lets us score fault-detection *logic* — the real BCVF
predictor-trust kernel and a deterministic baseline — under identical inputs
with known ground truth.

It exists because the kernel's own `characterization/traces.py` has **8**
families; the milestone requires **14** and, more importantly, requires fault
classes the kernel's own suite does not contain (stuck / delayed / stale /
correlated / common-mode / precise-biased / noisy-unbiased / calibration
drift). The overlapping families are **reproduced independently** so the
benchmark does not inherit the kernel's generator assumptions.

## 2. Ground-truth carried on every bundle

| field | meaning |
|---|---|
| `trajectories` | `(M, H, 3)` SE(2) predictor outputs |
| `truth_label` | index of the faulty predictor, or `None` (nominal / common-mode) |
| `onset_tick` | first tick the fault is active (for detection-delay scoring) |
| `fault_active` | is there a real fault a safety layer must catch? |
| `harm_class` | `harmful_state_error` / `benign` / `common_mode` |
| `bcvf_visible` | does the fault, by BCVF's 2nd-order invariance, produce a non-transient kernel signal *at all*? |
| `valid_masks` | per-tick validity `(M, H)` (freshness / missing data) |

**Why `harm_class` and `bcvf_visible` matter.** The load-bearing question of
Part 2 is not "does BCVF fire" but "does BCVF fire on the faults that
physically matter." A constant lateral bias is `harmful_state_error` (the robot's
position estimate is permanently wrong) yet `bcvf_visible=False` (BCVF is
invariant to constant offset by construction). That pairing — harmful **and**
invariant-hidden — is the crux of the safety argument, and only a corpus that
labels both axes can expose it.

## 3. The 14 families

Fixed generation params: `M=3, H=50, dt=0.1, base_velocity=5.0`. Nominal =
three predictors tracking one straight constant-velocity path with small IID
noise (σ=0.01 unless stated).

| family | fault? | harm_class | bcvf_visible | what it injects | why it is here |
|---|---|---|---|---|---|
| `gaussian_noise` | no | benign | no | σ=0.05 IID on all | nominal / false-alarm floor |
| `constant_bias` | yes | harmful_state_error | **no** | +0.5 m lateral on P1 | Lemma-1 trapdoor #1: harmful, invariant |
| `slow_bias` | yes | harmful_state_error | **no** | lateral ramp 0.02 m/tick | near-linear; ~invariant |
| `linear_drift` | yes | harmful_state_error | **no** | lateral 0.05·t on P1 | Lemma-1 trapdoor #2 |
| `accelerating` | yes | harmful_state_error | **yes** | ½·0.5·t² lateral on P1 | the class BCVF is designed for |
| `abrupt_jump` | yes | harmful_state_error | yes (1-tick) | +0.8 m step at t=25 | transient-only kernel spike |
| `stuck_sensor` | yes | harmful_state_error | **no** | P1 frozen from t=15 | freeze → *linear* disagreement → invariant |
| `delayed_predictor` | yes | harmful_state_error | **no** | P1 lagged 6 ticks | lag of const-vel path = const offset |
| `stale_predictor` | yes | harmful_state_error | **no** | P2 stops updating t=20; mask false | freshness observable, not disagreement-dynamic |
| `correlated_failure` | yes | harmful_state_error | **no** | +0.5 m on P1 **and** P2 | 2-of-3 common-mode; corrupts the consensus |
| `all_wrong` | yes | common_mode | **no** | all 3 drift identically | zero cross-disagreement; undetectable by any disagreement method |
| `precise_biased` | yes | harmful_state_error | **no** | P1 very-low-noise + 0.4 m bias | the confident-but-wrong sensor |
| `noisy_unbiased` | no | benign | yes | σ=0.15 zero-mean on P1 | high-variance benign; false-alarm probe |
| `calibration_drift` | no | benign | yes | P1 variance grows after t=20 | uncertainty degrades, estimate stays unbiased |

**Seven of the twelve fault families are `bcvf_visible=False`** — harmful state
errors that BCVF's 2nd-order invariance does not represent as a positive signal
in the noiseless limit.

## 4. Held-out split (anti-overfitting)

No family appears in both. Thresholds are tuned **only** on TUNE families +
seeds `0..19`; the scored benchmark runs on seeds `100..149`, which never
touch tuning.

* **TUNE:** `gaussian_noise`, `constant_bias`, `linear_drift`, `accelerating`,
  `noisy_unbiased`.
* **TEST (held out):** `slow_bias`, `abrupt_jump`, `stuck_sensor`,
  `delayed_predictor`, `stale_predictor`, `correlated_failure`, `all_wrong`,
  `precise_biased`, `calibration_drift`.

## 5. Known, deliberate limitations

* **Synthetic straight-line SE(2).** No real vehicle dynamics, no curved
  reference paths, no real sensor-noise spectra. Absolute detection numbers do
  not transfer to real sensors.
* **M=3.** With three predictors the robust consensus is a 3-sample median;
  2-of-3 correlated failure (`correlated_failure`) is a genuinely hard,
  arguably undetectable, case for *any* disagreement-only method — kept in the
  corpus precisely to expose that shared blind spot, not to be "won."
* **`noisy_unbiased` σ=0.15** is a design choice: at σ≈0.25 a zero-mean noisy
  predictor's windowed mean rivals a real 0.2 m bias, making the family an
  unfair probe rather than a clean one. σ=0.15 keeps it a genuine "noisy but
  not broken" sensor. Both detectors' false-alarm behaviour is reported against
  it.
* **Common-mode is not "solved" here.** `all_wrong` is undetectable from
  cross-predictor disagreement by construction; the corpus uses it to check
  that a detector does **not** fabricate a confident attribution, not to reward
  detection.
