# Autonomous Robotics — VC Brief (v2)

**Cognade Labs | BCVF Autonomy Runtime**
*Portable predictor-trust layer between multi-predictor robotics stacks and their planner*
*Version 0.7 — Prepared May 2026*

> **Status.** v0.7 closes the audit's #4 next-step — the
> **apples-to-apples baseline shootout** the v0.3 brief was
> missing. Built four arbitrators at the same predictor-
> arbitration interface (`BCVFArbitrator`, `EKFArbitrator` with
> Mahalanobis 3-sigma outlier rejection, `MajorityVoteArbitrator`
> with cluster-based mode selection, `AnchorArbitrator` as the
> null floor), ran them across all seven characterization
> families × N=10 seeds, and produced the comparison table the
> brief now points at. **Headline finding: BCVF is the only
> arbitrator with non-zero false-attribution suppression on
> Lemma-1-invariant disagreements** — Majority-Vote false-
> attribution score on `constant_bias` is **16.7** (catastrophic),
> EKF is 1.1, BCVF is 0.0. **EKF's Mahalanobis gate also misses
> the heavy-quadratic outlier** (0.0 hit rate vs BCVF / Majority's
> 1.0). BCVF is 8–19× faster per tick than EKF / Majority. v0.6's
> V2 chatter-reduction sweep result is preserved unchanged. The
> characterization primary grid is now certification-grade — 22
> configs × 60 seeds = 1320 cells, every per-config Wilson 95% CI
> lower bound ≥ 0.90 (current min ≈ 0.940). The Q3 SOTIF / ISO
> 26262 traceability template (12 clauses, **25 indexed BCVF
> artifacts**, machine-checked snapshot) landed early in
> `safety_case/`. The fleet harness gained a `StreamingFleetMonitor`
> with rolling-window summaries + threshold alert rules, lifting
> the post-hoc triage tool to a runtime SRE surface. The two
> deferred CSV / Markdown report writers landed —
> `GridSummary.to_csv` / `to_markdown_report` and
> `FleetSummary.to_csv` / `to_markdown_report` emit the frozen
> auditor-facing artifacts the safety-case workstream depends on.
> **507 tests passing**, up from 400 in v0.6 (12 audit pinning
> tests + 15 statistical-significance tests + 20 safety-case-
> traceability tests + 29 streaming-monitor tests + 16 report-
> writer tests added post-v0.7). v1 file at
> `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` is preserved for historical
> reference.

---

## Page 1 — The Problem

### Modern autonomy stacks disagree internally. The planner has no principled way to decide who to trust.

Every modern autonomous-vehicle, drone, mobile-robot, and humanoid
stack converged on the same pattern: **multiple predictors feeding a
planner.** A typical stack combines an HD-map prior, a learned
trajectory predictor, a classical kinematic model, and one or more
redundant sensor channels. When the predictors agree, planning is
routine. **When they disagree, the planner has no principled way to
decide which predictor to trust** — and predictor disagreement is the
regime where the failures that matter live.

That gap is where disengagements, safety-case escalations, and
in-house engineering rebuild-per-program costs concentrate. Programs
we've reviewed treat predictor-disagreement handling as bespoke glue
code rebuilt per stack, per program, and per release. The four
questions that come up earliest in safety review are the ones current
stacks answer least crisply:

| Question a safety case asks | Typical answer in current stacks | What v0.3 ships |
|---|---|---|
| *When two predictors disagree, can the system identify which one is failing — not which the heuristic prefers?* | Designated-primary or majority vote; both fail when the primary or majority is the one drifting. | Per-predictor BCVF cost attribution + outlier-alignment metrics (hit / margin / rank), structurally tested against a seven-family failure taxonomy. |
| *Is there a stated invariance property — something that provably ignores benign disagreement and only fires on genuine failure?* | Threshold-tuned heuristics, calibrated empirically per stack. No formal invariance. | Lemma 1 invariance proof (constant + linear-drift disagreement → exactly zero cost), regression-tested by `run_ablation_grid` across cost orders. |
| *When a predictor is down-weighted at runtime, can an operator reconstruct why?* | Per-component logs; no causal trace from the disagreement signal to the trust decision. | Frame-by-frame `TrustShapedEpisodeRecord` artifact + six observable probes (agreement, spread, coherence, per-step max, predictor-specific, uncertainty-gated) that surface exactly which signal moved the trust distribution. |
| *Can the trust mechanism be tuned without retraining predictors or rewiring the planner?* | Trust logic is entangled with the predictors that feed it; tuning is a release-cycle event. | Planner-agnostic `TrustWeightComputer` (§6.3) + opt-in Consumer V2 Schmitt trigger; both tunable through dataclasses, neither requires retraining. |
| *Can the safety team aggregate signals across the fleet to spot near-failures before they escalate?* | Manual log mining; near-miss detection lives in custom scripts per program. | `aggregate_fleet` harness over JSON-dumped trip records — surfaces argmax flips, near-vetoes, V2 state transitions per vehicle / scenario. |

### Why the gap is structural, not a tooling oversight

Fusion layers — Kalman filters, weighted averages, late-fusion
ensembles — were designed to *combine* honest noisy signals, not to
*distrust* a predictor that is silently wrong. Bolt-on uncertainty
estimators (deep ensembles, MC dropout, evidential networks) produce
numbers but offer **no formal invariance property**; their behaviour
on unseen failure shapes is the unknown a safety case was supposed to
bound.

ISO 21448 (SOTIF) and emerging functional-safety regimes increasingly
call for explicit handling of *silent predictor miscalibration*, not
just sensor failure. Operators and certification bodies want a runtime
layer that can say — under a stated mathematical invariance — "this
predictor is no longer trustworthy, here is the signal, here is the
attribution." A portable, testable runtime for that regime does not
exist today.

### The category we are building for

A **portable predictor-trust runtime** — a first-class layer between
predictor outputs and the planner — with a stated invariance
property, context-normalized trust construction, and a tested
integration contract. Not a replacement for perception, fusion,
prediction, or planning. The missing layer that sits between them.

---

## Page 2 — The Architecture

### What the runtime does, in four steps

BCVF Autonomy Runtime sits between the predictor stack and the
planner. At every planning step it:

1. **Detects disagreement shape.** Distinguishes harmless patterns
   (constant offset between predictors, linear drift) from
   *accelerating* divergence — the disagreement shape that signals
   real failure. The detector has a mathematically proven invariance:
   constant and linear-drift disagreement produce **exactly zero**
   trust signal; only acceleration above the noise floor produces a
   positive one.
2. **Normalizes for context.** Each scenario has its own baseline
   level of disagreement (different prompts, different sensor regimes,
   different geometries). The runtime subtracts a per-source running
   average so a noisy environment does not look like a failure.
3. **Down-weights suspect predictors.** A significance gate filters
   noise residuals; only disagreement that is meaningfully outside
   the per-source noise envelope shifts the trust distribution.
4. **Plans against the weighted consensus.** The planner consumes a
   trust-weighted consensus trajectory rather than a single
   predictor's output, with the per-source trust distribution
   available as a live diagnostic.

### The execution path (pinned by tests, not configurable)

```
  perception / prediction outputs
            │
            ▼
  M predictor trajectories per MPPI rollout  ──►  (K rollouts, M predictors)
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  BCVF kernel       — detect disagreement (Lemma 1 invariant)│
  │  Normalization     — per-source EMA mean centering          │
  │  Significance gate — suppress noise residuals               │
  │  Trust softmin     — per-rollout trust distribution         │
  │  Weighted consensus— SE(2)-safe consensus trajectory        │
  └─────────────────────────────────────────────────────────────┘
            │
            ▼
  Planner cost on consensus  ──►  MPPI control selection  ──►  applied control
            │
            ▼
  Per-step trust trace (kernel signal, weights, consensus, decision)
```

The ordering — **predict → score → normalize → trust → consensus →
plan → act** — is a runtime invariant verified by the test suite, not
a configurable option. A predictor whose disagreement is flat or
linearly drifting cannot affect trust weights. A residual below the
significance threshold cannot shape the softmin. A trust distribution
cannot bypass the consensus stage. This is the runtime contract a
safety case can point to.

### Three layers, independently tunable and testable

| Layer | Scope | What it answers |
|---|---|---|
| **Detection kernel** | Per planning step, all predictor pairs | *What is the disagreement signal under the stated invariance?* |
| **Trust shaper** | Per planning step, single trust distribution | *Given the signal and the per-context baseline, which predictors should the consensus down-weight right now?* |
| **Inspection surface** *(v0.3)* | Per tick + per episode + per fleet | *Why did the shaper produce these weights, when did it flip its mind, and how many vehicles in the fleet are close to failing?* |

The detection kernel is pure mathematics with a published proof. The
trust shaper is the autonomy-validated configuration: per-source mean
centering, then a significance gate, with all-pairs (non-anchor)
predictor enumeration. The inspection surface is the v0.3 SOTIF
deliverable — every tick produces a typed structured record, every
episode rolls up into an `EpisodeSummary`, every fleet of episodes
aggregates into a `FleetSummary` with named events (argmax flips,
near-vetoes, V2 state transitions). Any layer can be replaced or
re-tuned without touching the others.

### Actuator-grade chatter immunity (Consumer V2)

The default V1 softmin is a smooth function — designed for
inference-time logit blending where smoothness is a virtue. On
borderline disagreements driving a physical actuator, smoothness
becomes chatter: the trust-weighted consensus can flip its lead
predictor tick-to-tick. v0.3 ships an opt-in **Schmitt-trigger
state machine** wrapping the V1 shaping pipeline:

* The signal must rise above `engage_threshold` for `T_engage`
  consecutive ticks to engage shaping.
* Once engaged, the signal must drop below a strictly lower
  `disengage_threshold` for `T_disengage` consecutive ticks to
  revert to uniform weights.
* While disengaged, the EMA continues tracking the cost baseline
  (so the deadband / softmin start *warm* on first engagement);
  the §6.6a exclusion counters freeze (so transient spikes don't
  accumulate toward veto in safe-default territory).

This is the standard control-safety pattern that's been keeping
thermostats from flickering for fifty years; v0.3 brings it to the
trust pipeline, with the entire transition history captured in the
typed diagnostic record for post-hoc audit.

### Developer surface — one factory call

```python
from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig, MPPIConfig, MPPIPlanner, CostOrder,
)

bcvf_cfg = BCVFConfig(
    gate_threshold=0.05, gate_beta=400.0, huber_delta=0.5,
    cost_order=CostOrder.SECOND, use_anchor_pairing=False,
)
mppi_cfg = MPPIConfig(
    num_rollouts=256, horizon=20, lambda_c=1.0, bcvf_config=bcvf_cfg,
)
planner = MPPIPlanner(mppi_cfg, perf_cfg, predictors, road, obstacles)
planner.set_ema_alpha(0.05)         # per-context normalization
planner.set_deadband_k_sigma(2.0)   # significance gate
result = planner.plan()
```

Same code runs against synthetic predictors (no compute, no sensors)
and live perception/prediction stacks with no wiring changes — which
makes the library evaluable before any procurement conversation. The
runtime is **pure NumPy, runs on CPU in milliseconds per step, and
has no dependency on torch, ROS, or any platform-specific stack.**

---

## Page 3 — Where We Fit

BCVF Autonomy Runtime sits at a layer that exists in every production
multi-predictor robotics stack but is almost always in-house
engineering glue: the arbitration between disagreeing predictors.
We are **complementary to** the perception, fusion, prediction, and
planning components around that layer, not competitive with them.

### The competitor families and how we relate

| Category | Representative players | What we do differently |
|---|---|---|
| **Classical sensor / state fusion** | Kalman / EKF / UKF, ROS `robot_localization`, MRPT, Apollo perception fusion | Classical fusion combines noisy-but-honest signals into a single estimate. We sit one level up, arbitrating between *predictors* whose outputs the fusion layer fed into — the regime classical fusion is not designed to cover. Composes cleanly: keep the fusion layer, add us at the planner-arbitration boundary. |
| **ML uncertainty estimation** | Deep ensembles, MC dropout, evidential deep learning, conformal prediction | These produce empirically-calibrated uncertainty *numbers*. We produce a per-source trust distribution under a stated mathematical invariance (Lemma 1). Additive: a stack can keep its per-model uncertainty and feed it into our trust-weighting layer as additional context. |
| **Closed AV platform stacks** | Waymo, Cruise, Mobileye, NVIDIA DRIVE, Apollo, Toyota Woven Driver | These are end-to-end stacks with proprietary, non-portable internal arbitration logic. We ship the arbitration layer as a portable, inspectable runtime — an integrator using DRIVE (or similar) can adopt our layer without giving up the rest of their stack. |
| **Open-source AV / robotics stacks** | Autoware, Apollo OSS, OpenPilot, Nav2, MoveIt | These ship stack components and leave predictor-arbitration as glue code in `behavior_planner` / `decision_maker` modules, configured per integrator. We provide a tested runtime dependency for that specific glue — `pip install`-ready (and ROS 2 adapter in progress, §6.4). |
| **Functional-safety tooling** | ANSYS Medini, Vector vTESTstudio, dSPACE SystemDesk, Foretify, Applied Intuition | These document *what* the system should do. We provide the runtime artifact the documentation can refer to — SOTIF's "silent predictor miscalibration handling" question gets a structural answer (Lemma 1 proof) instead of an empirical one ("we tested N scenarios"). Complementary, not competing. |

### The one-sentence statement of fit

Classical fusion combines signals. ML uncertainty estimates noise.
Closed AV stacks bury arbitration inside proprietary code. Open-
source stacks leave it to integrators. We are the missing runtime
**between** predictor outputs and the planner, with a mathematical
invariance a safety case can point to and an extracted consumer
pattern that — as of the §6.3 refactor — is planner-agnostic by
construction.

### What we are not trying to claim

- Not replacing any perception, prediction, fusion, or planning
  component. We arbitrate between predictors; we do not produce
  them.
- Not a full-AV platform. An integrator still needs their sensing,
  localization, prediction, control, and safety-monitor stack; we
  add one missing layer.
- Not universal. The §6.1 multi-scenario scout identified that the
  runtime is **applicable where failure manifests as predictor
  disagreement** — which covers most map-error, multipath, and
  degrading-sensor cases in our suite, but not (e.g.) a camera
  failure that drops a dimension the predictors don't model. We
  document that boundary explicitly in our experimental reports.

---

## Page 4 — Evidence & Roadmap

### Four proof points to know (as of May 2026)

- **507 tests passing** (+286 since v0.2; +12 audit pinning tests + 15 statistical-significance tests + 20 SOTIF / ISO 26262 traceability tests + 29 streaming-monitor tests + 16 CSV/Markdown report-writer tests added post-v0.7 — the Q3 traceability template was pulled forward (12 clauses × 25 indexed BCVF artifacts × machine-checked markdown snapshot), the fleet harness gained a `StreamingFleetMonitor` with rolling-window summaries + threshold alerts that turn it from a triage tool into an SRE one, and the two deferred report writers landed so a SOTIF audit pack ships frozen artifacts instead of Python dataclasses) across the autonomy
  kernel, MPPI planner, trust-weight computer, non-MPPI adapter,
  dataset scaffolds, ROS 2 bridge, the v0.3 SOTIF-readiness
  layer, the v0.4 vectorized predict_batch path, the v0.5 pilot
  runner, the v0.6 V2 promotion-gate sweep, and the v0.7
  apples-to-apples baseline shootout. All committed,
  reproducible, CPU-only.
- **Seven-family characterization sweep — 0% FPR / 0% FNR with a
  Wilson 95% CI lower-bound floor of 0.90 across 22 configs ×
  60 seeds (1320 cells).** Every named sensor-failure class
  (constant bias, linear drift, accelerating divergence, noise
  floor, outlier, sensor dropout, baseline) is validated to fire
  or stay quiet on cue across primary, sensitivity, and ablation
  grids. The primary grid is now sized for a stated statistical
  contract: per-(family, magnitude) Wilson 95% CI lower bound
  must clear 0.90 — the floor is calibrated so two of 60 seed
  failures at any single config trip the alarm, exactly the
  threshold-edge regime (e.g. `accelerating[accel_mag=0.3]`)
  where a small kernel change is most likely to flip pass→fail.
  Current min-CI-lower-bound across the grid: **~0.940** at
  60-of-60 pass; floor headroom: **0.04**. The 567-cell
  sensitivity grid still winner-tuples the V1 defaults as the
  closest-to-canonical all-pass configuration.
- **Apples-to-apples baseline shootout (v0.7).** Four arbitrators
  at the same predictor-arbitration interface (BCVF, EKF with
  Mahalanobis 3-sigma outlier rejection, Majority-Vote, Anchor)
  × seven characterization families × N=10 seeds. **Two
  differentiating findings:** (a) BCVF is the only arbitrator
  with zero false-attribution on Lemma-1-invariant disagreements
  — Majority-Vote scores **16.7** on `constant_bias` and **4.1**
  on `linear_drift`; EKF scores **1.1** and **0.5**; BCVF scores
  **0.000** on both. (b) EKF's Mahalanobis gate misses the
  heavy-quadratic outlier (hit rate **0.0** vs BCVF / Majority
  at **1.0**). BCVF is **8–19× faster** per tick (≈3.7 µs vs EKF
  ≈70 µs / Majority ≈28 µs).
- **§6.2 pilot runner executed end-to-end (v0.5).** N = 21 paired
  scenes, A3 win rate **1.000** vs A0 with Wilson-CI 0.566–1.000
  and one-sided sign-test **p = 0.0312** on the responsive
  failure class (camera-degradation-shape within-horizon
  high-frequency disagreement). Attribution accuracy on the
  injected outlier: **100%**. Lemma-1 negative control passes
  exactly (max BCVF cost = 0.000000 on `constant_bias_sanity`).
  Pilot ran against the documented `RealisticNoiseAdapter`
  bridge — the runner / metrics / FleetSummary / sign test are
  dataset-agnostic and unchanged across adapters.
- **Two synthetic-predictor scenarios independently validated at
  p < 0.05**: `S3_map_error_accel` (N = 21, p = 0.0072) and
  `S3_map_error` (N = 19, p = 0.0192).

Full detail and caveats below.

### What is proved today (v0.2, internal evidence)

| Area | Current state |
|---|---|
| **Test suite** | 507 passing across 22 test modules (+12 pinning tests from the post-v0.7 audit pass; +15 statistical-significance tests for the certification-grade primary grid; +20 SOTIF / ISO 26262 traceability tests; +29 StreamingFleetMonitor tests; +16 CSV/Markdown report-writer tests: 8 grid-writer (header / column order / round-trip / failed-config / regulator sections / failing-config-listed / determinism / mkdir-parents) and 8 fleet-writer (header / round-trip / None-as-blank / required sections / classification table / empty-roster sentinels / determinism / mkdir-parents); reproducible on CPU in < 4 min (4 host-speed-dependent perf benchmarks + 4 long-running sweep / timing tests deselected) |
| **Kernel modules** | `core.py` (V3.1 §3.3–§3.5 + Lemma 1), `manifold.py`, `mppi_planner.py` (delegates to `trust.py`), `runner.py`, `scenarios.py` (S1–S6), `predictors/` (M1–M4 variants with failure injection), pure NumPy, ~4,700 LOC |
| **Consumer-layer extraction (§6.3)** | `trust.py` — planner-agnostic `TrustWeightComputer`. `integrations/` package with `argmin_selector.py` reference adapter + API-contract README. Extraction preserves 190 pre-existing tests bit-identical (behavior-preserving refactor) |
| **Non-MPPI adapter demonstrated** | `integrations/argmin_selector.py` — ArgminSelectorPlanner shares `TrustWeightComputer` with `MPPIPlanner` with **zero code duplication**. 7 integration tests proving Lemma 1 propagates through the non-MPPI path |
| **Multi-scenario validation (§6.1)** | Scout pass identified 2/6 scenarios as responsive (S3-variant family) + 4/6 benign + 1/6 BCVF-inapplicable. Both responsive scenarios pass p < 0.05 |
| **Architectural variant tested and rejected (§6.6a)** | Dynamic predictor exclusion implemented, run at N=21 S3_accel, rejected under strict multi-metric promotion gate. Rotates catastrophes, doesn't reduce the count. Rejection strengthens V1 claim: "V1 is not just simplest, it's what one non-trivial variant failed to improve upon" |
| **Observables framework (v0.3)** | `observables/` — six probes (`PredictorAgreement`, `EnsembleSpread`, `EnsembleHeadingEntropy`, `BCVFPerStepMax`, `BCVFPredictorPerStepMax`, `CoherenceAnchoredBCVF`, `UncertaintyGatedBCVFPerStepMax`). Each consumes the predictor trajectory tensor and returns a typed `ObservableValue` with metadata. Probe harness (`probe_observable`) runs against a labelled corpus and classifies the observable into SAFETY_CORRELATED / UNCORRELATED / ANTI_CORRELATED / NULL bands (AUC + Pearson + Spearman). 36 tests. |
| **Per-step trust diagnostics (v0.3)** | `trust_diagnostics.py` — `TrustStepRecord` per tick + `TrustShapedEpisodeRecord` `(T, M)` stacked arrays + JSON `to_dict()`. Captures weights, residuals (against pre-update EMA, exact), EMA mean/std snapshots, deadband activations, exclusion state, gate counts, V2 state + signal, and exclusion `consec_suspect` / `consec_ok` counters. Wired into `MPPIPlanner.set_trust_diagnostics_enabled` and `Runner` via three `RunConfig` knobs (`trust_diagnostics_enabled`, `trust_diagnostics_path`, `trust_diagnostics_aggregation`). |
| **Characterization sweep (v0.3, certification-grade in v0.7)** | `characterization/` — seven SE(2) trace families (baseline, constant_bias, linear_drift, accelerating, noise_floor, outlier, sensor_dropout) + outlier-attribution metrics (hit / margin / rank). Three grids: `run_primary_grid` (**1320 cells = 22 configs × 60 seeds**, 0% FPR / 0% FNR at V1 defaults, every per-config Wilson 95% CI lower bound ≥ 0.90 with min observed ≈ 0.940), `run_sensitivity_grid` (567-cell `(T, β, δ)` sweep, V1 defaults selected as winner-tuple), `run_ablation_grid` (linear_drift × CostOrder ablation confirms only SECOND order rejects linear drift). The summary returns a typed `GridSummary` exposing per-config Wilson CIs, `min_ci_lower_bound`, and `cells_below_certification_floor` — the stated SOTIF contract is machine-checkable per cell. **`GridSummary.to_csv(path)` and `GridSummary.to_markdown_report(path)`** emit the frozen audit-pack deliverables (the v0.3 deferral note in the DESIGN was retired); the markdown report carries headline gate / per-(family, magnitude) Wilson-CI table / per-family roll-up / failed-config list / methodology block, and renders deterministically up to the timestamp. Three sabotage tests confirm the suite would fail on a broken kernel; one additional sabotage test confirms a synthetic-failure injection at a single config trips `cells_below_certification_floor`. |
| **Consumer V2 — Schmitt-triggered softmin (v0.3)** | `trust.py` ConsumerV2Config + ConsumerState. Top-level state machine wraps the V1 shaping layer (deadband + softmin + §6.6a exclusion); EMA learning continues during UNIFORM so the deadband / softmin start warm on the first ENGAGED tick. Hysteresis defaults: `engage_threshold=0.5`, `disengage_threshold=0.2`, `T_engage=3`, `T_disengage=5`. Opt-in via `ConsumerV2Config(enabled=True)`; default-off preserves bit-for-bit V1 behavior. 21 tests. |
| **Post-hoc fleet analysis harness (v0.3, streaming-grade post-v0.7, audit-pack-grade post-v0.7)** | `analysis/` — `find_argmax_flips` (with `weight_drop` + `max_abs_weight_delta` magnitude metrics), `find_v2_state_flips`, `find_near_vetoes` (predictors that crested 70% of `exclusion_T` without crossing). Batch aggregators `summarize_episode` and `aggregate_fleet` consume per-episode `TrustShapedEpisodeRecord`s and return a `FleetSummary` with per-classification counts, argmax-flip percentile statistics, per-predictor exclusion-incidence rate, and a typed near-veto roster (each event carrying per-episode metadata for triage). `load_episode_from_json` reverses the Runner's diagnostics dump with strict shape validation; corrupt artifacts fail loudly rather than silently producing zero-fill records. **`StreamingFleetMonitor` (post-v0.7)** lifts the harness from triage-time to runtime: `.observe_episode(record)` / `.observe_summary(...)` ingest, `.summary(window=timedelta(hours=24))` returns rolling-window `WindowedFleetSummary`, `.evaluate_alerts([rule])` fires `AlertRule` threshold rules with dotted-path metric paths (`argmax_flips_per_step.p95`, `deadband_fired_rate`, ...) — the runtime SRE surface a deployment partner wires into alertmanager / Grafana. Batch parity is the load-bearing contract: a window-bounded streaming summary is byte-identical to `aggregate_fleet` over the same episodes. **`FleetSummary.to_csv(path)` and `FleetSummary.to_markdown_report(path)` (post-v0.7)** retire the v0.3 deferral note and emit the SOTIF clause-10 frozen artifacts: per-episode CSV (RFC-4180-quoted, pinned column order) and a fleet-level narrative markdown (headline aggregates / classification breakdown / per-predictor exclusion incidence / near-veto + V2-state-flip rosters / top-K per-episode index / methodology block); both work identically on batch and streaming-windowed summaries. 26 batch tests + 29 streaming tests + 8 report-writer tests. |
| **Real-sensor pilot — runner + first execution (§6.2, v0.5)** | `pilot/` package: `scene_evaluator` (Mode A open-loop A0 / A3 paired evaluation), `sign_test` (Wilson CI + one-sided sign test, no scipy), `runner` (writes paired-comparison CSV + `FleetSummary` JSON + markdown report). Executed end-to-end against `RealisticNoiseAdapter` at N = 21: A3 win rate 1.000 with Wilson-CI lower bound 0.566 and sign-test p = 0.0312 on the responsive class; Lemma-1 negative control passes exactly. Three artifacts written to `results/phase_6_2_pre_pilot/`. 16 pilot tests + 11 prior dataset-adapter tests. `datasets/nuscenes.py` stub documents the one-line adapter swap; full execution pending dataset access + the M1–M4 predictor implementations the pilot plan estimates at 3–4 weeks. |
| **Apples-to-apples baseline shootout (v0.7)** | `baselines/` package: `BCVFArbitrator`, `EKFArbitrator` (with `robot_localization`-style Mahalanobis 3-sigma outlier rejection), `MajorityVoteArbitrator` (cluster-mode), `AnchorArbitrator` (null floor), all sharing the same `Arbitrator` protocol consuming `(M, H, 3)` predictor trajectories. Shootout runs every arbitrator × every characterization family × N seeds. Three artifacts (`shootout.csv`, `shootout.json`, `shootout_report.md`) in `results/baseline_shootout/`. The Lemma-1 false-attribution differentiator is the BD-grade headline; the EKF Mahalanobis miss on outlier is the *"this isn't a solved problem with the existing toolkit"* finding. 19 baseline tests, including pinned BD assertions (BCVF false-attr < 1e-6 on constant_bias, EKF > 0.1, Majority > 1.0). |
| **SOTIF / ISO 26262 traceability template (Q3 pulled to post-v0.7)** | `safety_case/` — `traceability.py` builds a clause-by-clause `TraceabilityMatrix` mapping 19 BCVF artifacts (kernel, characterization sweep, V2 hysteresis, fleet harness, per-step diagnostic record, baseline shootout, pilot runner, Wilson CI primitive, ...) to 12 standard clauses: SOTIF (ISO 21448) clauses 5/6/7/8/9/10 and ISO 26262 Part 6 §7/§8/§9/§9.4.4/§10/§11. The on-disk `SOTIF_TRACEABILITY.md` is a deterministic snapshot of the matrix (the test suite pins byte-equality between snapshot and renderer so the doc cannot drift). Every evidence reference is import-time-resolved by the test suite (`module_path::symbol` must exist, or the test fails loudly). The template is the Q3 "regulator-facing template" half of the brief item; the regulator workshop remains a Q3 deliverable. **The artifact half is now BD-callable on day one of a diligence engagement** instead of waiting for "after the safety case is ready." 20 traceability tests. |
| **V2 promotion-gate sweep + decision (v0.6)** | `v2_chatter_sweep.py`: paired V1 vs V2 runner with two-gate decision logic (chatter-reduction Wilson + rescue-preservation McNemar). Executed at N=5 on `S1_normal_driving` (chatter scenario) and `S3_map_error_accel` (rescue scenario), at default thresholds and at 50×-lower thresholds. **Finding: V2 reduces chatter by ≤ 0.6% on autonomy data because BCVF kernel cost exceeds V2's engage threshold even on nominal scenarios → V2 stays ENGAGED → V1 pipeline runs unchanged.** Honest non-promotion. The empirical result upgrades the v0.5 "V2 is opt-in" caveat from defensive to evidence-backed; threshold recalibration is a scoped Q2 followup. 12 sweep-module tests + artifacts in `results/v2_chatter_S1_n5/` and `results/v2_rescue_S3_n5/`. |
| **ROS 2 adapter scaffold (§6.4)** | `symbolu_bcvf_ros2` package with framework-agnostic core + lazy `rclpy` shim. Message dataclasses, bridge class, and 13 tests. `.msg` files + colcon build + real pub/sub pending ~3–4 weeks ROS-environment work |
| **Latency benchmark (§6.5)** | 18-cell (M × K × H) sweep, plus a v0.4 re-run after `predict_batch` vectorization. Smallest config (M=4, K=128, H=10) now p99 ≈ 38 ms (was 76). Per-predictor rollout cost dropped 52–77× across M1–M4 at K=1000, H=50; the new dominant cost is the BCVF kernel and perf-cost evaluation — the next vectorization targets. Production integrators should re-run on their substrate. |
| **`predict_batch` vectorization (v0.4)** | All four reference predictors (M1 IMU, M2 LiDAR, M3 VO, M4 GNSS — including all four GNSS failure modes and M3's tracking-loss freeze branch) ship with vectorized `predict_batch` overrides; default `BasePredictor.predict_batch` falls back to a per-rollout loop so custom predictors without an override still work. Bit-for-bit equivalent to the per-rollout loop (asserted by 11 parametrized tests + 4 ≥ 2× speedup gates). 18 new tests; bumps the per-predictor speedup the audit recommended item #1 from "1–2 weeks of work" to "landed." |
| **Diagnostic-consistency CI (§6.7)** | 18 parametrized invariant tests guarding `total_cost == Σ pair_costs` and `per_predictor.sum() == 2 × bcvf_total` across every (pairing, cost_order) combination |
| **Design specification** | Autonomy DESIGN.md Phase 6 (V2 roadmap) records per-item completion status; v0.3 adds five per-module DESIGN docs (`observables/DESIGN.md`, `characterization/DESIGN.md`, `analysis/DESIGN.md`, `CONSUMER_V2_DESIGN.md`, plus updated `trust_diagnostics` notes). Each module landed with an independent design doc + audit trail. |

All numbers are from our own repository and CI — not third-party
benchmarks. External multi-platform validation and a real-sensor
pilot are the next scheduled steps.

### Honest scope caveats (to preserve credibility)

- **Validated on disagreement-detectable failure modes.** S4
  (camera degradation) produces catastrophes but no predictor
  disagreement — BCVF is inapplicable there. 4/6 scenarios in our
  synthetic suite are benign (A0 handles them). The v0.3
  characterization sweep makes this explicit: seven failure
  families *are* covered, families that don't manifest as
  disagreement still aren't.
- **Validated on synthetic M1–M4 + the realistic-noise adapter
  bridge; real automotive sensor data still pending.** The v0.5
  pilot ran against `RealisticNoiseAdapter` (correlated AR(1)
  noise + 2% non-Gaussian outliers + the four canonical pilot
  failure shapes). The runner / metrics / FleetSummary / sign
  test are dataset-agnostic by construction; rerunning on real
  nuScenes-mini is a `NuScenesAdapter` implementation away. The
  pilot plan §scope-caveats remain in force for any real-data
  result — single-city, single-weather, synthetic ego dynamics.
- **Predictor rollout vectorization landed (v0.4).** All four
  reference predictors (M1–M4) ship with `predict_batch` overrides
  that run K rollouts through the H sequential dynamics steps with
  `(K,)`-shaped state arrays — observed **52–77× per-predictor
  speedup** at K=1000, H=50 vs the prior per-rollout Python loop,
  bit-for-bit equivalent to the reference loop (asserted by 11
  parametrized equivalence tests across all failure modes).
  Custom predictors without an override fall back to the default
  loop. The audit caveat in v0.2/v0.3 ("dominant cost is the
  Python-level per-rollout predictor loop") is now resolved; the
  remaining latency budget is the BCVF kernel and the MPPI
  perf-cost evaluation, which are the next vectorization targets.
- **Drone / industrial rates remain partially out of reach on the
  largest configs.** Automotive 10 Hz now fits at the small config
  (K=128, H=10, p99 ≈ 38 ms). 50 Hz / 100 Hz still need kernel-
  side vectorization; production integrators should re-run the
  benchmark on their target compute substrate.
- **No production deployment.** No operator runs V1 on their
  stack today. §6.8 is the Series-A-gated BD milestone.
- **The 3-catastrophe floor on S3 is scenario-structural.**
  §6.6a empirically confirmed that trust-shaping alternatives
  rotate which seeds fail but do not reduce the count. v0.3
  Consumer V2 reduces *chatter* on borderline disagreements but
  does not, by itself, change this floor. Structural improvement
  requires either a richer predictor set or a higher-level
  safety-monitor layer — both out of V1 scope.
- **Consumer V2 is opt-in, not the default — empirically
  validated as the right call.** The v0.6 chatter-reduction
  sweep (`v2_chatter_sweep.py`, N=5 paired) measured V1 vs V2 on
  `S1_normal_driving`. Median per-seed flip-rate reduction:
  **0.6%** at the default thresholds, **0.5%** at 50×-lower
  thresholds (`engage_threshold=0.01`). Reason: BCVF kernel cost
  on autonomy scenarios — even nominal ones — exceeds V2's
  engage threshold across K=64+ rollouts, so V2 stays ENGAGED
  ~99% of ticks and the V1 pipeline runs unchanged. **The V2
  Schmitt-trigger design is correct (UNIFORM forces uniform
  weights → zero argmax flips); the threshold calibration is
  wrong for the autonomy domain.** Promotion deferred until the
  engage signal / threshold are recalibrated against measured
  autonomy BCVF magnitudes — a Q2 followup, scoped at ~1 week.
  V2 stays an opt-in safety feature for integrators whose
  BCVF magnitudes match the LLM-domain hysteresis design.
- **The fleet analysis harness has been validated end-to-end on
  synthetic episodes only.** Multi-episode aggregation across
  thousands of real trips is the §Q1 + §Q2 follow-on; the
  harness ingests JSON dumps the Runner already produces, so
  this is execution work, not research.
- **LLM-domain transfer is not claimed.** An internal research
  track (`docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md` §13)
  tested whether the same BCVF math applies to LLM
  hallucination detection. The N=100 TruthfulQA probe across
  11 candidate observables returned AUC in [0.476, 0.527] —
  a clean null. BCVF does **not** currently transfer to LLM
  trust routing, and we do not position it as a hallucination
  detector. The autonomy result above is not predicated on
  LLM transfer and stands independently.

### 12-month roadmap (de-risking sequence, matches §6.10 — refreshed v0.3)

**Quarter 1 — External validation**
- **§6.2 execution.** Pilot **runner** landed in v0.5; first paired
  execution against `RealisticNoiseAdapter` shipped (N=21, win
  rate 1.000, p=0.0312, Lemma-1 PASS). Q1 follow-on:
  nuScenes-mini download → fill in `datasets/nuscenes.py`
  load_scene() → M1 HD-map / M2 Kalman / M3 lightweight LSTM /
  M4 failure-injected predictor wrappers → re-run the same
  unchanged pilot runner on real data → publish the
  paired-comparison CSV + FleetSummary JSON. Code path is
  identical to the synthetic-noise pre-pilot; the swap is one
  line.
- **§6.3 parity audit.** Re-run §6.1 S3_accel sweep against the
  post-refactor branch to confirm bit-accurate behavior-preservation.
  ~25 min compute. Strengthens the "extraction was zero-risk" claim.
- **§6.5 production-substrate benchmarks.** Re-run latency sweep on
  a TDA4VH / Orin / AMD EPYC sample to produce numbers an
  integrator can plan against. 1–2 days per target.
- ~~**Consumer V2 chatter-reduction sweep.** Re-run §6.1 S3_accel with
  V2 enabled; quantify per-step argmax-flip rate reduction; promote
  V2 to default once chatter reduction is statistically significant
  without harming rescue-pattern reproduction. 1 week.~~ **Landed in
  v0.6 — non-promotion result. The threshold recalibration follow-on
  moves to Q2.**

**Q2 — V2 threshold recalibration (new, was Q1's V2 promotion).**
The v0.6 sweep showed V2's engage threshold doesn't correspond to
autonomy BCVF cost magnitudes. Recalibration paths to investigate:
(a) drive engage signal off `bcvf_total.min(axis=0)` instead of
the mean — least-noisy rollout instead of population view;
(b) threshold against per-tick BCVF distribution mean over a
trailing window instead of a fixed magnitude; (c) ladder of
thresholds calibrated per-scenario class. ~1 week.

**Quarter 2 — Platform integration**
- **§6.4 execution.** `.msg` + colcon + real rclpy pub/sub, Nav2
  `CriticPlugin`, example launch files, rosbag integration test.
  3–4 weeks in a ROS 2 Humble / Jazzy environment.
- **First external-integrator confirmation.** OSS contributor or
  design-partner drops the package into their Nav2 / Autoware
  stack and confirms install + run. Required for §6.4 acceptance.
- ~~**`predict_batch` vectorization** (unblocks drone / industrial
  rates). 1–2 weeks.~~ **Landed in v0.4 — per-predictor cost down
  52–77× at K=1000, H=50.** Follow-on: kernel-side vectorization
  for the now-dominant BCVF + perf-cost evaluation cost.

**Quarter 2 — Pulled forward from Q3**
- ~~**SOTIF / ISO 26262 traceability template.** Map Lemma 1
  invariance + the v0.3 characterization-sweep failure taxonomy +
  per-step diagnostic record + Consumer V2 chatter-immunity proof
  to a safety-case narrative. The five v0.3 artifacts cover the
  bulk of what an auditor's clause-by-clause walk requires; the
  Q3 work is the regulator-facing template + workshop, not new
  code. 2–3 weeks + regulator workshop.~~ **Template half landed
  post-v0.7 in `safety_case/` — 12 clauses (SOTIF 5/6/7/8/9/10 +
  ISO 26262 Part 6 §7/§8/§9/§9.4.4/§10/§11), 19 indexed BCVF
  artifacts, machine-checked snapshot in
  `safety_case/SOTIF_TRACEABILITY.md`. Regulator workshop remains
  a Q3 deliverable; the artifact-half is now BD-callable on day one.**

**Quarter 3 — Safety-case + adjacent-domain pilot**
- **First paid design-partner engagement** (adjacent domain —
  drone / warehouse / industrial mobile robot). Not full AV.

**Quarter 4 — Production reference**
- **§6.8 first production reference customer.** Running V2 (post-
  real-sensor-pilot) on their own stack in their own environment.
  Reference letter or published case study. The fleet analysis
  harness lets the partner publish a *fleet-level* trust-pipeline
  report at handover, not just a single integration report.

### The ask

Seed capital to convert a CI-validated research prototype with one
statistically significant autonomy companion result into a
portable, multi-platform predictor-trust runtime that at least one
external operator runs in production. The technology is live —
221 tests, two scenarios validated, planner-agnostic runtime
extracted, real-sensor and ROS 2 scaffolds shipped — and everything
on the remaining roadmap is execution work against known dependencies
(dataset access, ROS 2 install, target hardware, BD engagement),
not open research.

Capital is earmarked for:

1. **External validation** — nuScenes pilot execution (Q1) +
   production-substrate latency re-runs (Q1) + first external-
   integrator confirmation of the ROS 2 adapter (Q2).
2. **Platform integration** — ROS 2 adapter execution (Q2) +
   `predict_batch` vectorization (Q2) + Autoware / Apollo
   reference integrations (Q2–Q3).
3. **Safety-case readiness** — SOTIF / ISO 26262 traceability
   template **landed post-v0.7** (12 clauses, 19 indexed
   artifacts, machine-checked snapshot in
   `safety_case/SOTIF_TRACEABILITY.md`); regulator engagement
   stays Q3.
4. **First production reference** — adjacent-domain design partner
   (Q3) + production reference (Q4).

Series A is conditional on §6.8 (one production reference) landing.
Seed covers the 12 months of de-risking work that makes §6.8
reachable.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `symbolu_robotics/bcvf_autonomous/`*
*v0.7 · 507 internal tests (audit pinning tests included; published numbers unchanged; characterization primary grid now certification-grade at 1320 cells with Wilson 95% CI lower-bound floor 0.90 per (family, magnitude) config — current min ≈ 0.940; Q3 SOTIF / ISO 26262 traceability template pulled forward — 12 clauses across SOTIF 5/6/7/8/9/10 and ISO 26262 Part 6 §7/§8/§9/§9.4.4/§10/§11, 25 indexed BCVF artifacts, machine-checked snapshot in `safety_case/SOTIF_TRACEABILITY.md`; `StreamingFleetMonitor` with rolling-window summaries + threshold alerts lifts the fleet harness from triage to runtime; the two deferred CSV / Markdown report writers landed — `GridSummary.to_csv` / `to_markdown_report` and `FleetSummary.to_csv` / `to_markdown_report` emit the frozen auditor-facing artifacts a SOTIF audit pack depends on) · apples-to-apples baseline shootout landed (BCVF zero false-attribution on Lemma-1 vs Majority 16.7 / EKF 1.1; EKF misses heavy-quadratic outlier; BCVF 8–19× faster per tick) · V2 promotion-gate sweep landed (median chatter reduction 0.6%, non-promotion, Q2 recalibration scoped) · §6.2 pilot runner executed end-to-end (N=21, win rate 1.000, p=0.0312 on responsive class, Lemma-1 negative control PASS, three artifacts on disk) · 2 synthetic-predictor scenarios p < 0.05 · planner-agnostic runtime extracted (§6.3) · per-step diagnostics + fleet analysis harness · Consumer V2 (Schmitt-triggered) chatter-immunity opt-in (evidence-backed) · `predict_batch` vectorization 52–77× per-predictor speedup · `NuScenesAdapter` stub documents one-line real-data swap*
