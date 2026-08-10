# Robotics BCVF Implementation Audit

**Milestone:** Robotics reliability redesign — Parts 1 & 2.
**Method:** evidence-first. Every claim is backed by the real implementation and
by executable checks in `robotics_reliability_bench/` (run against production
code, not mocks). Machine-readable outputs:
`robotics_reliability_bench/results/action_counterexamples.json`,
`.../kernel_audit.json`.
**Two systems, evaluated separately.** They share the "BCVF" name and nothing
else (`bcvf_autonomous/DESIGN.md:30` — "share a name but not a function").

---

## Part 1 — Direct action-ranking BCVF (`formulas/bcvf.py`)

### 1.1 What it is

`compute_consistency_lagrangian` (`formulas/bcvf.py:58`):
`L = λf(1−sf)² + λb(1−sb)² + λc(sf−sb)²`, then `w = exp(−βL)`
(`:103`), normalized `W(i)=w(i)/(Σw+1e-10)` (`:125`). Defaults
`λf=λb=1.0, λc=0.5, β=2.0` (`:39`). `score_action_candidates` (`:142`) loops
sf/sb → L → w → normalize. **No filtering, no threshold, no abstain path.**

### 1.2 Call-site inventory (grep-verified, real/non-test)

| # | Site | sf / sb source | consumption | hard gate before BCVF? | abstain? |
|---|---|---|---|---|---|
| 1 | `tiers/deliberative.py` (`TaskPlanner.plan`, `:109`; scorer `:150`; argmax `:154`) | `_compute_forward_score` `:188` (soft; safety is a **subtraction** `sf -= state[11]*0.3`), `_compute_backward_score` `:221` (keyword match) | **pure argmax** → `best_action` → `plan_fn` → `ActuatorCommand(target_velocities=…)` `:269` | **NO** | no (always emits a winner) |
| 2 | `coordination/conflict_resolution.py:392` | **hardcoded per-strategy constants** `:444` (e.g. `MUTUAL_STOP sf=1.0, sb=0.3, safety=1.0`) | normalized weight **× (1+priority)(1+safety)** post-multiplier `:402`, then argmax `:410` → per-robot `stop/yield/proceed` actions | **NO** (safety is a soft multiplier) | only if candidate set empty |
| 3 | `coordination/task_allocation.py:358` | `_score_bid` `:264` (capability/load/coherence/distance) | normalized weight **× (1+priority)** `:366`, argmax `:373` → `assigned_robot` | **YES, at bid intake** (`capability<0.5`, `load>0.9`, `min_bid_score=0.3`, coherence gate) | only if `< min_bids` |

**Direct actuation reach:** sites 1 and 2 turn a BCVF argmax into motion
commands with no hard safety gate in between. Site 3 is the only one with hard
pre-filters, and they run at bid intake, not at final selection.

### 1.3 Executable counterexamples (all reproduce — `action_counterexamples.json`)

| ID | Finding | Evidence |
|---|---|---|
| CE1 | β leaves the pure-argmax winner fixed but moves the winner's normalized confidence across a downstream gate (0.484→0.924 as β 0.5→20), so a "act only if top weight > 0.6" gate flips on temperature alone | reproduced |
| CE2 | The consistency term makes the **safest** action lose. Action A `sf=1.0, sb=0.5` (L=0.375) loses to mediocre-consistent B `sf=sb=0.7` (L=0.18). A is charged a 0.125 consistency penalty for being honestly feasible-but-not-goal-complete | reproduced |
| CE3 | A trust-weighted **blended** command swings 1.9 m/s² (0.09→2.00) across β∈{0.5,2,10} with no new evidence | reproduced |
| CE4 | All-unsafe candidates (`sf,sb≈0.05–0.1`) still normalize to a confident winner summing to 1.0; **no `NO_SAFE_ACTION`** | reproduced |
| CE5 | Uncalibrated sf scale across modules (×0.6) flips the winner with identical physics | reproduced |
| CE6 | Modeling the real coordination post-multiplier `argmax(exp(−βL)·bonus)`: winner flips on β alone (β=0.3→idx0, β≥2→idx1); and the emergency-stop profile (`sf=1.0, sb=0.3`, L=0.735) is the **worst-scored** by BCVF because the consistency term punishes it — at the default β=2 it **loses** to the efficient maneuver, rescued only if the ad-hoc safety multiplier is large enough | reproduced |

### 1.4 Value vs deterministic alternatives

The port provides no property that a deterministic constrained ranker lacks,
and removes one the ranker guarantees (a non-compensatory hard gate). Against
the four references:

* **Hard feasibility filtering** — BCVF has none (sites 1–2); a good soft score
  buys back a hard violation. A filter is strictly safer.
* **Lexicographic ranking** — deterministic, temperature-free, scale-free,
  auditable; BCVF's ranking is β- and scale-sensitive (CE1/CE3/CE5/CE6).
* **Weighted utility** — equivalent expressiveness without the safety-adverse
  `(sf−sb)²` term that demotes emergency-stop (CE2/CE6).
* **Constrained optimization** — expresses "maximize goal s.t. margin ≥ floor,"
  which is what the domain wants; BCVF cannot express a hard constraint at all.

**Part 1 conclusion:** the direct action BCVF adds no measurable decision value
and carries a real safety-adverse failure mode. → supports `REPLACE_ACTION_BCVF`
(see `ROBOTICS_ACTION_SELECTION_BASELINES.md` for the head-to-head).

---

## Part 2 — Predictor-trust kernel (`bcvf_autonomous/`)

Tested against the real kernel (`compute_bcvf_cost` / `compute_bcvf_cost_batch`,
`use_anchor_pairing=False, cost_order=SECOND`) on the 14-family corpus,
seeds 100–149. Full data: `kernel_audit.json`.

### 2.1 The central invariance — is it real, and is it *safe*?

**Noiseless: the invariance holds exactly.**

| disagreement shape | noiseless total cost |
|---|---|
| constant offset (0.7 m) | **0.000e+00** |
| linear drift (0.3 m/s) | **0.000e+00** |
| accelerating (0.3 m/s²) | 3.349e-01 (nonzero) |

**With realistic noise (σ=0.01) the gate leaks.** The zeroth-order smooth gate
`sigmoid(β(‖e‖−T))` (`core.py:101`) opens on the *magnitude* of a constant
offset, letting the biased predictor's own residual noise pass the
second-difference penalty:

| shape (σ=0.01) | per-predictor cost `[P0,P1,P2]` | argmax = biased P1? |
|---|---|---|
| constant offset | `[21.4, 40.5, 19.1]` | **yes** |
| linear drift | `[19.9, 36.0, 16.2]` | **yes** |

**Interpretation.** The advertised "constant + linear disagreement → exactly
zero" is a **noiseless idealization**. In deployment (always noisy) the kernel
*does* produce a constant-bias attribution — but through an unadvertised side
channel (gate-opening amplifies the biased predictor's noise), **not** the
2nd-order acceleration mechanism the safety case rests on. This is why it fails
`precise_biased` (§2.3): a low-noise biased predictor has no noise to leak.

**Is the invariance a safety property? No.** Per the milestone rule, an
invariance is a safety property only if the protected class is formally tied to
*harmless* physical behavior. The protected class here is *constant position
offset* and *linear position drift* — both are **`harmful_state_error`** in the
corpus (a persistent or growing position error is exactly what causes a
collision). The invariance protects a **harmful** class, so it must **not** be
described as a safety property. It is a blind spot that noisy data partially,
and unreliably, papers over.

### 2.2 Per-family kernel behaviour (margin = top cost / peer mean; seeds 100–149)

| family | harm | bcvf_visible | median margin | attr hit |
|---|---|---|---|---|
| gaussian_noise | benign | no | 1.07 | – |
| constant_bias | harmful | no | 1.99 | 1.00 |
| slow_bias | harmful | no | 1.98 | 1.00 |
| linear_drift | harmful | no | 1.99 | 1.00 |
| accelerating | harmful | **yes** | 1.98 | 1.00 |
| abrupt_jump | harmful | yes | 1.98 | 1.00 |
| stuck_sensor | harmful | no | 1.99 | 1.00 |
| delayed_predictor | harmful | no | 1.99 | 1.00 |
| stale_predictor | harmful | no | 1.98 | 1.00 |
| correlated_failure | harmful | no | 1.99 | – (flags honest P0) |
| all_wrong | common_mode | no | 1.90 | – (false) |
| **precise_biased** | harmful | no | **1.10** | **0.00** |
| **noisy_unbiased** | **benign** | yes | **2.00** | – (false alarm) |
| **calibration_drift** | **benign** | yes | 1.73 | – (false alarm) |

### 2.3 Faults the invariance/kernel hides or mishandles

1. **`precise_biased` — dangerous miss + mis-blame.** The confident (low-noise)
   biased sensor is invisible (margin 1.10, attr 0.00); the kernel instead
   points at the honest *noisy* predictors, whose noise leaks through the gate
   the bias opened.
2. **`noisy_unbiased` / `calibration_drift` — benign flagged as fault.** Both
   score margin 1.73–2.00, indistinguishable from real faults. The kernel
   cannot separate high-variance-benign from a genuine failure.
3. **`correlated_failure` (2-of-3) — confident mis-attribution.** The corrupted
   consensus makes the honest predictor look like the outlier; the kernel flags
   it (shared blind spot with any disagreement method).
4. **`all_wrong` (common-mode) — fabricated detection.** Zero cross-disagreement,
   yet margin 1.90 → the kernel "detects" a culprit that does not exist.

### 2.4 Part 2 conclusion

The kernel's headline invariance is real only noiseless and protects a *harmful*
class, so it is not a safety property. On noisy data the kernel attributes many
faults via an unadvertised gate-leak, but that same mechanism causes a dangerous
miss on the precise-biased sensor and false alarms on benign high-variance
predictors. Whether this is worth keeping is an *incremental-value* question,
answered in `ROBOTICS_BCVF_INCREMENTAL_VALUE_RESULTS.md`.

### Scope caveats (binding)

* All numbers are **synthetic** straight-line SE(2). Nothing here proves
  real-sensor safety.
* The 1,560-cell kernel characterization is **not** cited as real-world
  evidence.
* N=50 seeds/family; effect sizes are large but this is a decision-grade signal,
  not a certification.
