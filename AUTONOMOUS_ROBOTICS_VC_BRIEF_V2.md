# Autonomous Robotics — VC Brief (v2)

**Cognade Labs | BCVF Autonomy Runtime**
*Portable predictor-trust layer between multi-predictor robotics stacks and their planner*
*Version 0.2 — Prepared April 2026*

> **Status.** All four pages landed. Pages 1–2 apply the tighter,
> investor-ready framing requested in the v2 rewrite brief; Pages
> 3–4 are grounded in the §6 V2-roadmap execution evidence
> (autonomy companion experiments committed through `d9cc30a`).
> v1 file at `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` is preserved for
> historical reference.

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

| Question a safety case asks | Typical answer in current stacks |
|---|---|
| *When two predictors disagree, can the system identify which one is failing — not which the heuristic prefers?* | Designated-primary or majority vote; both fail when the primary or majority is the one drifting. |
| *Is there a stated invariance property — something that provably ignores benign disagreement and only fires on genuine failure?* | Threshold-tuned heuristics, calibrated empirically per stack. No formal invariance. |
| *When a predictor is down-weighted at runtime, can an operator reconstruct why?* | Per-component logs; no causal trace from the disagreement signal to the trust decision. |
| *Can the trust mechanism be tuned without retraining predictors or rewiring the planner?* | Trust logic is entangled with the predictors that feed it; tuning is a release-cycle event. |

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

### Two layers, independently tunable and testable

| Layer | Scope | What it answers |
|---|---|---|
| **Detection kernel** | Per planning step, all predictor pairs | *What is the disagreement signal under the stated invariance?* |
| **Trust shaper** | Per planning step, single trust distribution | *Given the signal and the per-context baseline, which predictors should the consensus down-weight right now?* |

The detection kernel is pure mathematics with a published proof. The
trust shaper is the autonomy-validated configuration: per-source mean
centering, then a significance gate, with all-pairs (non-anchor)
predictor enumeration. Either layer can be replaced or re-tuned
without touching the other.

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

### Three proof points to know (as of April 2026)

- **221 tests passing** across the autonomy kernel, MPPI planner,
  trust-weight computer, non-MPPI adapter, dataset scaffolds, and
  ROS 2 bridge. All committed, reproducible, CPU-only.
- **Two scenarios independently validated at p < 0.05**:
  `S3_map_error_accel` (N = 21, sign-test p = 0.0072) and
  `S3_map_error` (N = 19, sign-test p = 0.0192). Same rescue
  pattern in both — evidence the V1 configuration generalizes
  across the scenario family rather than overfitting to one case.
- **Planner-agnostic runtime**: the trust-shaping pipeline has
  been extracted into a standalone callable (`TrustWeightComputer`)
  that any planner family — MPPI, sampling-based, MPC, or custom —
  can consume. Demonstrated by a second reference adapter
  (argmin-selection) that differs from MPPI only in action
  selection, not in trust logic.

Full detail and caveats below.

### What is proved today (v0.2, internal evidence)

| Area | Current state |
|---|---|
| **Test suite** | 221 passing across 13 test modules; reproducible on CPU in < 1 min |
| **Kernel modules** | `core.py` (V3.1 §3.3–§3.5 + Lemma 1), `manifold.py`, `mppi_planner.py` (delegates to `trust.py`), `runner.py`, `scenarios.py` (S1–S6), `predictors/` (M1–M4 variants with failure injection), pure NumPy, ~4,700 LOC |
| **Consumer-layer extraction (§6.3)** | `trust.py` — planner-agnostic `TrustWeightComputer`. `integrations/` package with `argmin_selector.py` reference adapter + API-contract README. Extraction preserves 190 pre-existing tests bit-identical (behavior-preserving refactor) |
| **Non-MPPI adapter demonstrated** | `integrations/argmin_selector.py` — ArgminSelectorPlanner shares `TrustWeightComputer` with `MPPIPlanner` with **zero code duplication**. 7 integration tests proving Lemma 1 propagates through the non-MPPI path |
| **Multi-scenario validation (§6.1)** | Scout pass identified 2/6 scenarios as responsive (S3-variant family) + 4/6 benign + 1/6 BCVF-inapplicable. Both responsive scenarios pass p < 0.05 |
| **Architectural variant tested and rejected (§6.6a)** | Dynamic predictor exclusion implemented, run at N=21 S3_accel, rejected under strict multi-metric promotion gate. Rotates catastrophes, doesn't reduce the count. Rejection strengthens V1 claim: "V1 is not just simplest, it's what one non-trivial variant failed to improve upon" |
| **Real-sensor pilot scaffold (§6.2)** | Dataset adapter interface + `RealisticNoiseAdapter` bridge (AR(1)-correlated noise, 2% outlier frames, 4 failure patterns). Pilot plan in place for nuScenes-mini + KITTI fallback. 11 tests on the adapter layer. Execution pending dataset access |
| **ROS 2 adapter scaffold (§6.4)** | `symbolu_bcvf_ros2` package with framework-agnostic core + lazy `rclpy` shim. Message dataclasses, bridge class, and 13 tests. `.msg` files + colcon build + real pub/sub pending ~3–4 weeks ROS-environment work |
| **Latency benchmark (§6.5)** | 18-cell (M × K × H) sweep. Smallest config (M=3, K=128, H=10) fits automotive 10 Hz (p99 = 76 ms, 24 ms headroom). Industrial 50 Hz and drone 100 Hz not met; dominant cost is Python-level per-rollout predictor loop (vectorization is a documented V2 target) |
| **Diagnostic-consistency CI (§6.7)** | 18 parametrized invariant tests guarding `total_cost == Σ pair_costs` and `per_predictor.sum() == 2 × bcvf_total` across every (pairing, cost_order) combination |
| **Design specification** | Autonomy DESIGN.md Phase 6 (V2 roadmap) records per-item completion status + pending work (`d9cc30a`); LLM-domain transfer pattern §5.1/§5.2 committed to `BCVF_LLM_TRUST_ROUTING_DESIGN.md` with autonomy evidence |

All numbers are from our own repository and CI — not third-party
benchmarks. External multi-platform validation and a real-sensor
pilot are the next scheduled steps.

### Honest scope caveats (to preserve credibility)

- **Validated on disagreement-detectable failure modes.** S4
  (camera degradation) produces catastrophes but no predictor
  disagreement — BCVF is inapplicable there. 4/6 scenarios in our
  synthetic suite are benign (A0 handles them).
- **Validated on synthetic M1–M4 predictors.** Real sensor traces
  (§6.2) have correlated noise and non-Gaussian tails not in the
  synthetic harness. Bridge adapter (`RealisticNoiseAdapter`)
  partially covers this; full nuScenes validation pending.
- **Latency is not yet at drone / industrial-robot rates.** V1
  fits 10 Hz at the smallest (M, K, H). 50 Hz / 100 Hz need
  vectorized `predict_batch` (known V2 target, ~1–2 weeks work).
  Production integrators should re-run the benchmark on their
  target compute substrate.
- **No production deployment.** No operator runs V1 on their
  stack today. §6.8 is the Series-A-gated BD milestone.
- **The 3-catastrophe floor on S3 is scenario-structural.**
  §6.6a empirically confirmed that trust-shaping alternatives
  rotate which seeds fail but do not reduce the count. Structural
  improvement requires either a richer predictor set or a
  higher-level safety-monitor layer — both out of V1 scope.
- **LLM-domain transfer is not claimed.** An internal research
  track (`docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md` §13)
  tested whether the same BCVF math applies to LLM
  hallucination detection. The N=100 TruthfulQA probe across
  11 candidate observables returned AUC in [0.476, 0.527] —
  a clean null. BCVF does **not** currently transfer to LLM
  trust routing, and we do not position it as a hallucination
  detector. The autonomy result above is not predicated on
  LLM transfer and stands independently.

### 12-month roadmap (de-risking sequence, matches §6.10)

**Quarter 1 — External validation**
- **§6.2 execution.** nuScenes-mini download → `datasets/nuscenes.py`
  adapter → M1–M4 real-sensor predictor implementations → N≥21
  paired sweep on real data → pilot report. 3–4 weeks FTE.
- **§6.3 parity audit.** Re-run §6.1 S3_accel sweep against the
  post-refactor branch to confirm bit-accurate behavior-preservation.
  ~25 min compute. Strengthens the "extraction was zero-risk" claim.
- **§6.5 production-substrate benchmarks.** Re-run latency sweep on
  a TDA4VH / Orin / AMD EPYC sample to produce numbers an
  integrator can plan against. 1–2 days per target.

**Quarter 2 — Platform integration**
- **§6.4 execution.** `.msg` + colcon + real rclpy pub/sub, Nav2
  `CriticPlugin`, example launch files, rosbag integration test.
  3–4 weeks in a ROS 2 Humble / Jazzy environment.
- **First external-integrator confirmation.** OSS contributor or
  design-partner drops the package into their Nav2 / Autoware
  stack and confirms install + run. Required for §6.4 acceptance.
- **`predict_batch` vectorization** (unblocks drone / industrial
  rates). 1–2 weeks.

**Quarter 3 — Safety-case + adjacent-domain pilot**
- **SOTIF / ISO 26262 traceability template.** Map Lemma 1
  invariance + the autonomy-validated consumer pattern to a
  safety-case narrative. 2–3 weeks + regulator workshop.
- **First paid design-partner engagement** (adjacent domain —
  drone / warehouse / industrial mobile robot). Not full AV.

**Quarter 4 — Production reference**
- **§6.8 first production reference customer.** Running V2 (post-
  real-sensor-pilot) on their own stack in their own environment.
  Reference letter or published case study.

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
   template (Q3) + regulator engagement (Q3).
4. **First production reference** — adjacent-domain design partner
   (Q3) + production reference (Q4).

Series A is conditional on §6.8 (one production reference) landing.
Seed covers the 12 months of de-risking work that makes §6.8
reachable.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `symbolu_robotics/bcvf_autonomous/`*
*v0.2 · 221 internal tests · 2 scenarios p < 0.05 · planner-agnostic runtime extracted (§6.3)*
