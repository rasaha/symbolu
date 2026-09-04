# Predictor-Trust V2 — Preregistration

**Milestone:** Robotics reliability redesign.
**Rule:** This document is committed **before** the final benchmark is executed.
Everything below (hypotheses, metrics, thresholds, families, seeds, decision
rules) is frozen at commit time. Deviations are recorded in a post-hoc
"Deviations" section, never by silently editing the frozen values.

---

## 0. Question

Do the two BCVF-named robotics mechanisms earn their place, or should they be
replaced/augmented by deterministic robotics reliability logic?

* **Action BCVF** — `symbolu_robotics/formulas/bcvf.py` (forward/backward
  consistency Lagrangian) used in `tiers/deliberative.py`,
  `coordination/conflict_resolution.py`, `coordination/task_allocation.py`.
* **Predictor-trust BCVF** — `symbolu_robotics/bcvf_autonomous/` (2nd-order
  cross-predictor disagreement kernel).

They are evaluated as **two separate systems**.

## 1. Hypotheses (frozen)

* **H1 (action).** The direct forward/backward action scorer adds no measurable
  decision value over deterministic constrained ranking, and can rank an
  unsafe/infeasible candidate into the winning slot because it applies no
  non-compensatory hard gate. *Predicted verdict: `REPLACE_ACTION_BCVF`.*
* **H2 (predictor, standalone).** As a standalone predictor-trust layer, BCVF
  does not beat a deterministic innovation + EWMA/CUSUM + freshness baseline on
  the frozen metric set, primarily because (a) it is invariant to constant
  offset / linear drift (harmful but hidden classes) and (b) its raw signal is
  noise-dominated, producing false alarms on benign high-variance predictors.
* **H3 (predictor, feature).** BCVF's dynamic-disagreement (2nd-order) signal
  *may* reduce detection latency on the accelerating/abrupt classes it is built
  for, and can be retained as an **optional feature** layered on the
  deterministic baseline **iff** it lowers detection delay without raising
  dangerous misses or false interventions.

Null result is an allowed outcome. A V2 fusion result is **not** forced.

## 2. Systems under test (frozen)

1. `DeterministicBaseline` — `predictor_trust_baseline.DeterministicTrustBaseline`.
2. `BCVF` — the real kernel via `detectors.BCVFDetector` (margin-based, the
   kernel's intended relative attribution).
3. `Fusion(Baseline+BCVF)` — baseline decision; BCVF permitted only to shorten
   detection delay on a same-predictor agreement; it may not override an
   ABSTAIN, silence a SUSPECT, or force a winner.

## 3. Frozen thresholds

**Deterministic baseline** (`TrustBaselineConfig`, tuned on TUNE seeds 0..19):
`lever_arm=2.5, scale_floor=0.05, ewma_alpha=0.3, degraded_z=3.0,
cusum_k=1.0, cusum_h=8.0, bias_window=12, bias_z=4.0, bias_min_m=0.20,
bias_sustain=8, stale_frac=0.3, abstain_suspect_frac=0.5`.

**BCVF detector:** `margin_threshold=1.5` (separates benign `gaussian_noise`
margin ≈1.07 from faults ≈2.0 on TUNE), `window=12`, kernel config
`use_anchor_pairing=False, cost_order=SECOND`, all other `BCVFConfig` defaults.

**Action baselines** (`action_baselines.py`): hard floors
`COLLISION_FLOOR_M=0.20`, `STABILITY_FLOOR=0.10`; `ConstrainedOpt MIN_MARGIN=0.30`;
`WeightedUtility` weights `margin=1.0, goal=1.0, cost=0.5`.

**Corpus:** `M=3, H=50, dt=0.1, base_velocity=5.0`. TUNE seeds `0..19`;
**evaluation seeds `100..149`** (held out from all tuning).

Rationale for every threshold: derived from the TUNE-only sweep recorded in the
implementation audit; none was chosen after observing TEST-family results.

## 4. Metrics (frozen — see `metrics.py`)

Per family, aggregated over the 50 eval seeds:

1. **fault_detection_recall** — over `harmful_state_error` families: fraction
   detected. (Common-mode families are excluded; they are undetectable by any
   disagreement-only method.)
2. **false_alarm_rate** — over benign families: fraction where a fault was
   surfaced. Lower is better.
3. **common_mode_false_detection_rate** — over `common_mode` families:
   detecting one is a *false* attribution; lower is better.
4. **detection_delay_ticks** — over correctly-attributed faults:
   `mean(max(0, detection_tick − onset_tick))`.
5. **attribution_accuracy** — over single-culprit families: `flagged == truth`.
6. **abstention_correctness** — abstains iff it should
   (common-mode/insufficient-evidence), not otherwise.
7. **runtime_us_per_episode** — wall-clock per `detect()` (eval code, not a
   production perf claim).

## 5. Decision rules (frozen)

Applied to the **held-out TEST aggregate** (with ALL-family aggregate as a
consistency check). Let Δrecall, ΔFA, Δdelay be BCVF/Fusion minus deterministic
baseline.

* **`REPLACE_ACTION_BCVF`** if the action counterexamples reproduce (unsafe
  candidate can win; ranking depends on temperature/scale; no `NO_SAFE_ACTION`)
  AND deterministic selectors never select a hard-inadmissible candidate.
* **`BCVF_NO_INCREMENTAL_VALUE`** (predictor, standalone) if BCVF's recall is
  not higher AND its false_alarm_rate or common_mode_false_detection_rate is
  materially worse than the baseline.
* **`AUGMENT_PREDICTOR_TRUST`** if Fusion strictly improves detection delay over
  the baseline (Δdelay < 0 by ≥ 3 ticks) **without** worsening recall,
  false_alarm_rate, or common_mode_false_detection_rate. BCVF survives only as
  an optional feature under this verdict.
* **`REPLACE_PREDICTOR_BCVF`** if the baseline dominates on recall AND FA AND
  common-mode AND Fusion adds no delay benefit.
* **`RETAIN_CURRENT`** only if BCVF (standalone) is ≥ baseline on recall and FA
  and common-mode and delay.
* **`INSUFFICIENT_EVIDENCE`** if results are within noise on the load-bearing
  metrics.

"Materially worse" = the benign/common-mode false-rate at least doubles, given
the large expected effect sizes.

## 6. Anti-gaming commitments

* Tuning only on TUNE families + seeds 0..19; scoring only on seeds 100..149.
* No threshold is edited after observing TEST results; any change is a logged
  deviation.
* Deterministic RNG (`numpy.default_rng(seed)`); the whole harness is
  reproducible, so the committed numbers are byte-stable.
* No claim that this synthetic corpus proves real-sensor safety.
* The 1,560-cell kernel characterization is **not** cited as real-world
  evidence.

## 7. Deviations (append-only, post-hoc)

*(none at preregistration commit)*

* **D1 — additional systems under test (post-hoc extension).** Three
  detectors not listed in §2 were added to `run_incremental_value.py`:
  `LLTKalman`, `LLTKalman(strict-tick)`, and `Fusion(LLT+BCVF)`
  (`robotics_reliability_bench/llt_kalman_trust.py`). Their thresholds were
  tuned on TUNE families / seeds 0..19 only (`results/llt_kalman_tune.json`)
  and frozen before TEST scoring; a TEST-family false positive seen during
  test authoring was not used to adjust them. The three frozen systems, their
  thresholds, metrics, and decision rules are unchanged, and their committed
  numbers remain byte-stable. Results and an exploratory (non-frozen) verdict:
  `ROBOTICS_LLT_KALMAN_TRUST_RESULTS.md`.
