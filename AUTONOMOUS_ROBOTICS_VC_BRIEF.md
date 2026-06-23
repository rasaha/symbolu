# Autonomous Robotics — VC Brief

**Xozence Labs | BCVF Autonomy Runtime — Trust-Weighted Predictor Consensus for Safety-Critical Robotics**
*Version 0.1 — Prepared April 2026*

---

## Page 1 — The Problem

### Operators want autonomous robots. Predictor disagreement is blocking deployment in safety-critical settings.

Modern autonomous-vehicle, drone, mobile-robot, and humanoid stacks all
arrived at the same architectural pattern: **fuse multiple predictors**.
A typical stack runs an HD-map prior, a learned end-to-end predictor, a
classical kinematic model, and at least one redundant sensor channel.
When the predictors agree, planning is easy. **When they disagree, the
planner has no principled way to decide which one to trust** — and
predictor disagreement is exactly the regime where the failures that
matter live.

Industry has converged on a small set of ad-hoc responses to this:
majority voting across redundant channels, weighted averages with
hand-tuned weights, a designated "primary" predictor that the others
back up, and threshold-switching heuristics that escalate to a fallback
controller. Each of these works in nominal regimes and degrades — often
silently — in exactly the corner cases that drive disengagement
statistics, recall events, and safety-case escalations.

In safety reviews and AV-operator post-mortems we and our design
partners have read, four questions consistently come up early — and
most current stacks answer them only partially:

| The question a safety case asks | What most current autonomy stacks offer |
|---|---|
| *"When two predictors disagree, can the system identify which one is failing — not which one the heuristic prefers?"* | Designated primary or majority vote; both fail when the primary or majority is the one drifting. |
| *"Is there a mathematically defined invariance property — something that provably ignores benign disagreement and only fires on genuine failure?"* | Threshold-tuned heuristics with no formal invariance; behavior characterized empirically per stack. |
| *"When the system down-weights a predictor at runtime, can the operator reconstruct *why* that predictor was distrusted at that moment?"* | Per-component logs with no causal trace tying the trust decision to the underlying disagreement signal. |
| *"Can the trust mechanism be tuned without retraining any of the predictor models or rewiring the planner?"* | Most fusion layers are entangled with the predictors that feed them; tuning is a release-cycle event. |

In practice, most AV / robotics programs we have visited treat
predictor-disagreement handling as an in-house engineering problem
rebuilt per stack, per program, and per release. Disagreement detection,
trust weighting, and arbitration are scattered across the perception
output, the planner cost function, and the safety monitor — and the
seam between them is where corner-case regressions hide. The problem
is not lack of redundancy; it is lack of a *principled, testable
runtime contract* for what should happen in the disagreement regime.

### Why retrofitting trust-weighting onto existing fusion loops is hard

In most current stacks, predictor outputs feed into a fusion layer
(weighted average, Kalman blend, late-fusion ensemble) that was
designed primarily to *combine* predictions, not to *distrust* them. A
designated-primary scheme is easy to reason about until the primary is
the failure source; a majority vote is easy until two redundant
predictors fail in correlated ways (a common pattern when they share
training data or sensor modality). Bolt-on uncertainty estimators
(ensemble disagreement scores, Monte-Carlo dropout, evidential layers)
produce numbers, but those numbers have **no formal invariance
property** — they are calibrated empirically and their behavior in
unseen regimes is the unknown the stack was supposed to defend
against.

Safety-case engineering against ISO 21448 (SOTIF — Safety of the
Intended Functionality) and the emerging UNECE / ISO 26262 functional
safety regimes increasingly asks for explicit handling of *predictor
miscalibration and silent model error*, not just sensor failure.
Operators and certification bodies want a runtime layer that can say,
under a stated mathematical invariance, "this predictor is no longer
trustworthy — here is the signal, here is the threshold, here is the
attribution to the specific source." That layer does not exist as a
portable, testable runtime today.

Our view is that the market needs a runtime where predictor-trust is
a **first-class property of the planning loop itself** — where
disagreement detection is performed by a kernel with a *proven*
invariance (constant disagreement and linear drift produce zero
signal; only accelerating divergence does), where the trust-weight
construction is normalized for context-dependent baselines, and where
the integration into the planner's consensus is a tested runtime
contract rather than per-stack glue code. That is the category we are
building for.

---

## Page 2 — The Architecture

### BCVF Autonomy Runtime — predictor-trust wired into the planning loop

BCVF Autonomy Runtime is a **pure-NumPy Python library** that wraps any
multi-predictor robotics stack (vision/LiDAR/radar fusion, multi-model
trajectory predictors, classical-plus-learned ensembles) and turns
predictor disagreement into a trust-weighted planning consensus. The
disagreement detector has a **mathematically proven invariance
property**, the consumer-layer normalization is the result of paired
N=21 ablation experiments on a controlled failure scenario, and the
integration into the planner is a tested runtime contract — not glue
code rebuilt per stack.

### The trust-weighted planning loop (pinned by the test suite)

```
  perception/prediction outputs at time t
      │
      ▼
  M predictor trajectories  ──► (M, H, 3) per MPPI rollout
      │
      ▼
  K MPPI rollouts × M predictors ──► (K, M, H, 3)
      │
      ▼
  BCVFKernel              ──► per_source_cost  (K, M)
      │   (Lemma 1: constant + linear drift → 0; only accel → positive)
      ▼
  ConsumerNormalization   ──► EMA mean centering, then significance gate
      │   (per §2.7.11 / §5.1 — autonomy-validated two-stage pattern)
      ▼
  TrustSoftmin            ──► trust weights (K, M)
      │
      ▼
  WeightedConsensus       ──► consensus trajectory (K, H, 3)
      │   (atan2-safe SE(2) heading composition)
      ▼
  PlannerCost on consensus ──► (K,) performance cost per rollout
      │
      ▼
  MPPI softmax             ──► applied control u_t
      │
      ▼
  RUN_COMPLETED  +  AgentRunTrace  (per-step BCVF, weights, consensus)
```

The ordering — **predict → score → normalize → trust → consensus →
plan → act** — is a runtime invariant verified by the test suite, not
a configurable option. A predictor whose 2nd-order disagreement is
zero (constant offset or linear drift) cannot affect the trust weights.
A residual below the significance threshold cannot shape the softmin.
A trust distribution cannot bypass the consensus stage. This is a
deliberately narrow, tested contract — the property an autonomy safety
case can point to during certification review.

### Two complementary layers

| Layer | Scope | What it decides |
|---|---|---|
| **BCVFKernel** | Per outer step, all (K, M) rollouts | *"What is the per-source disagreement signal under the Lemma 1 invariance?"* |
| **ConsumerNormalization + TrustSoftmin** | Per outer step, single trust distribution | *"Given the kernel signal and the per-context baseline, which predictors should the consensus down-weight right now?"* |

The two layers compose but are **independently testable and
independently tunable**. The kernel is pure math: a 2nd-order
finite-difference operator on per-pair body-frame errors, a sigmoid
gate, a pseudo-Huber penalty, a per-source attribution sum. Its output
is provably invariant under constant and linear-drift disagreement
(Lemma 1, V3.1 §3.5) and provably positive under accelerating
divergence above the noise gate. The consumer layer is the autonomy-
validated pattern from §2.7.11 / §5.1: per-source EMA mean
subtraction, then a significance gate (or hinge-φ shaping) before
softmin, then non-anchor pairwise enumeration at M ≥ 3.

### The Lemma 1 invariance is our differentiation

When a multi-predictor robotics stack uses BCVF Autonomy Runtime,
disagreement decisions can be enriched with a *mathematically
guaranteed* invariance — constant offsets between predictors (different
calibration, fixed bias) produce **exactly zero** trust signal; linear
drifts (predictors disagreeing at a constant rate) produce **exactly
zero** trust signal; only **accelerating** divergence produces a
positive signal. This is a structural property of the 2nd-order
operator on the vector-valued disagreement, formally stated and
proven in §2.6 of the design specification (`docs/design/
BCVF_LLM_TRUST_ROUTING_DESIGN.md`).

No bolt-on uncertainty estimator (ensemble disagreement, MC dropout,
evidential layers) currently shipping in autonomy stacks has this
property. They produce calibrated numbers in regimes the calibration
data covers; their behavior on unseen failure shapes is the unknown
that safety cases struggle to bound. The Lemma 1 invariance is what
lets a safety reviewer say "this signal cannot fire on the benign
patterns enumerated in §2.6 — therefore a non-zero signal is
informative" — a property no current autonomy-stack uncertainty layer
can match because none of them are derived from a 2nd-order operator
in the first place.

When the runtime is composed with a non-CG-instrumented predictor
stack (which is most production stacks today), the same kernel runs
against the predictor trajectories themselves. When future stacks
expose model-internal coherence signals — entropy, attention
inconsistency, latent disagreement — the consumer-normalization layer
can absorb them with the same pattern. Customers can therefore start
on existing predictor stacks today and absorb internal-signal sources
later without rewiring.

### Developer surface — one factory call, full BCVF planning loop

```python
from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig, MPPIConfig, MPPIPlanner, CostOrder,
)

bcvf_cfg = BCVFConfig(
    gate_threshold=0.05,        # autonomy-validated default
    gate_beta=400.0,
    huber_delta=0.5,
    cost_order=CostOrder.SECOND,
    use_anchor_pairing=False,    # all-pairs at M >= 3 (§2.4.5)
)
mppi_cfg = MPPIConfig(
    num_rollouts=256, horizon=20, lambda_c=1.0, bcvf_config=bcvf_cfg,
)

planner = MPPIPlanner(mppi_cfg, perf_cfg, predictors, road, obstacles)
planner.set_ema_alpha(0.05)         # per-source baseline normalization
planner.set_deadband_k_sigma(2.0)   # significance gate

result = planner.plan()
# result.first_control       — applied to the actuator
# result.bcvf_cost           — diagnostic per-step BCVF total
# result.predictor_trajectories — full M-predictor rollouts for trace
```

One factory call composes the full stack: BCVF kernel, MPPI sampler,
consumer-layer normalization, weighted-consensus planner, and the
per-step diagnostic trace. The same code runs against a synthetic
multi-predictor harness (no compute, no sensors) and a live perception/
prediction stack with no wiring changes — which makes the library
easy to evaluate before any procurement conversation. The kernel
itself is **pure NumPy with 166 passing tests**, runs in milliseconds
per outer step on a single CPU core, and has no dependency on torch,
ROS, or any robotics-platform-specific stack.

---

## Page 3 — Competitive Landscape

BCVF Autonomy Runtime sits in a category that does not yet have a
clean name in the autonomy market — the layer between *"the predictor
stack produced multiple disagreeing trajectories"* and *"the planner
chose a control input."* That layer exists in every production AV /
robotics stack, but it is almost universally **in-house engineering
glue** rather than a portable runtime with a stated mathematical
property. The table below positions us against each family of
adjacent technology, stating for every row both *how* we differ and
*why* that difference matters for an operator building a defensible
safety case.

| Category | Representative players | What they ship | How BCVF Autonomy Runtime differs — and why it is better |
|---|---|---|---|
| **Classical sensor / state fusion** | Kalman / EKF / UKF filters, particle filters, late-fusion ensembles, ROS `robot_localization`, MRPT, Apollo perception fusion | Deterministic blending of redundant sensor / state channels with hand-tuned weights or covariance models. Strong at combining noisy-but-honest signals into a single estimate. | We do not *fuse* signals — we **detect predictor disagreement** with a formal invariance and gate trust accordingly. **Better because:** classical fusion assumes the predictors are noisy-but-correctly-modeled; the failure mode our runtime targets (a predictor that is silently wrong) is exactly the case the Kalman covariance model cannot represent. We compose with classical fusion: the fusion layer can still combine sensors, and BCVF Autonomy Runtime sits one level up arbitrating between *predictors* whose outputs the fusion layer fed into. |
| **ML uncertainty estimation** | Deep ensembles, Monte-Carlo dropout, evidential deep learning, conformal prediction, Bayesian deep learning libraries | Bolt-on uncertainty scores attached to per-prediction outputs, calibrated against held-out data and used as inputs to a downstream decision rule. | These produce *numbers* but **no formal invariance property** — their behavior on unseen failure shapes is exactly the unknown the safety case was supposed to bound. **Better because:** the Lemma 1 invariance gives a safety reviewer a structural statement ("this signal cannot fire on constant or linear-drift disagreement — therefore a non-zero signal is informative") that no empirically-calibrated uncertainty score can match. We are additive: a stack can keep its existing per-model uncertainty and feed it into our trust-weighting layer as additional context. |
| **Closed AV / robotics platform stacks** | Waymo Driver, Cruise, Mobileye REM, Tesla Autopilot, NVIDIA DRIVE, Apollo (Baidu), Toyota Woven Driver | Full closed perception → prediction → planning stacks, often with proprietary internal arbitration logic between competing predictors. | These are end-to-end stacks with **proprietary, non-portable** internal trust mechanisms — the customer cannot inspect, certify, or substitute the predictor-arbitration logic. **Better because:** we ship the arbitration layer as a *portable, inspectable runtime* with a published Lemma 1 proof. A customer using NVIDIA DRIVE today can adopt our runtime as an explicit predictor-trust layer between DRIVE's perception output and the customer's own planning code, without giving up the rest of their stack — a capability no closed platform offers because none of them sell their internal arbitration as a separable component. |
| **Open-source AV / robotics stacks** | Autoware (TIER IV), Apollo OSS, OpenPilot, CARLA, NAV2, MoveIt | Reference open-source autonomy stacks providing perception, prediction, and planning modules with community-developed glue between them. | They ship **stack components** and leave predictor-arbitration as glue code in `behavior_planner` / `decision_maker` modules that are configured per integrator, not pinned by tests. **Better because:** we provide the missing tested runtime contract for the disagreement regime. We integrate as a planning-layer dependency (`pip install symbolu_robotics`) and produce a structured `MPPIResult` that an Autoware or Apollo planning node can consume directly — replacing per-integrator decision-maker glue with a tested kernel + consumer pattern. |
| **Functional-safety tooling** | ANSYS Medini Analyze, Vector vTESTstudio, dSPACE SystemDesk, Foretellix Foretify, Applied Intuition | Safety-case authoring, requirements traceability, FMEA / HARA / SOTIF documentation, scenario-based regression testing. | These tools document *what* the system should do; they do not enforce it at runtime. **Better because:** we provide the runtime artifact that those documents need to refer to. A SOTIF safety case asks "how does the system handle silent predictor miscalibration?" — without a runtime layer with a stated invariance, the answer has to be empirical ("we tested N scenarios"); with our runtime, the answer can be structural ("Lemma 1 guarantees no false trust shift on benign disagreement, and the consumer-layer pattern is validated to N=21 paired"). The two are complementary, not competing. |
| **Robotics simulation + verification** | NVIDIA Isaac Sim, MathWorks Automated Driving Toolbox, CARLA, LGSVL, MORAI | Scenario libraries, simulation environments, regression-test infrastructure for autonomy stacks. | Simulation platforms test *whether* a stack passes a scenario; they do not provide a portable runtime *property* to test against. **Better because:** we ship the property (Lemma 1 invariance + autonomy-validated consumer pattern). The simulation platforms become a *consumer* of our test surface — they instantiate the BCVF kernel, run scenarios against it, and report regressions against a known mathematical baseline rather than against an opaque stack. |

### Feature-level differentiation on predictor-trust primitives

For autonomy program leads who want the one-page side-by-side on the
primitives that come up in safety-review conversations, here is the
honest comparison against the two most common competitor families:

| Area | BCVF Autonomy Runtime | Classical fusion (Kalman / late-fusion) | ML uncertainty (ensemble / MC dropout / evidential) |
|---|---|---|---|
| Lemma 1 invariance proof (constant + linear drift → 0) | **Yes** | Not applicable (no invariance concept) | No — calibrated empirically |
| Per-source attribution at M ≥ 3 (2:1 outlier discrimination) | **Yes** (symmetric all-pairs) | Partial (per-channel residuals) | Partial (per-model variance) |
| Per-context baseline normalization (EMA mean centering) | **Yes** (autonomy-validated, §2.7.11) | Static covariance | Static calibration |
| Significance gate / hinge-φ to suppress noise residuals | **Yes** (k=2σ default, §5.1) | No | No |
| Non-anchor pairing at M ≥ 3 (avoids anchor-failure collusion) | **Yes** (default) | Often anchor-biased | Not applicable |
| Pure-NumPy kernel, no GPU / torch dependency | **Yes** (166 tests, ms/step on CPU) | Varies; typically C++ | Typically requires torch/tf |
| Tested runtime contract (predict→score→normalize→trust→consensus→plan→act) | **Yes** (pinned by tests) | No (per-stack glue) | No (per-stack glue) |
| Drop-in to existing AV stacks | Drop-in to MPPI-style planners; adapter needed for non-MPPI planners | Mature | Mature |
| Production AV deployments | Not yet — pilots in design | **Mature** (decades of deployment) | **Mature** (multiple production stacks) |
| Ecosystem breadth (sensor drivers, simulation, perception primitives) | Narrow, focused on the arbitration layer | **Broad** | **Broad** |
| Multi-stack platform integrations (ROS / Apollo / Autoware / DRIVE) | Not yet — on roadmap | **Mature** | **Mature** |

### Why the overall bet is better, not just different

- **The Lemma 1 invariance is a structural property no incumbent can match.** It is not a tuning improvement on existing uncertainty estimators — it is a *different kind of guarantee*. A 2nd-order operator on vector-valued disagreement is provably zero on constant offsets and linear drifts; the proof is dimension-agnostic and three pages of algebra (§2.6). No bolt-on uncertainty layer in the competitive table is derived from a structurally-zero-on-benign operator, because they are all calibration-based rather than invariance-based.
- **We arbitrate predictors; we do not replace stacks.** A customer using Autoware for perception, Mobileye REM for HD-map priors, and a custom learned predictor can adopt BCVF Autonomy Runtime at the planning-layer arbitration boundary without giving up any of those investments. We are the missing layer for the disagreement regime, not a rival to perception/prediction or to planning.
- **The autonomy-validated consumer-layer pattern is non-obvious and now empirically published.** EMA-mean centering + significance gate + non-anchor pairing was the configuration that produced the first statistically significant improvement (sign test p < 0.01) over a no-shaping baseline in our N=21 paired companion experiment. Each component alone underperforms; the combination is the result. A competitor would have to either reproduce the experiment or guess the same recipe — neither is fast.
- **Pure-NumPy kernel, no GPU dependency.** Autonomy validation, regression testing, and CI for the kernel run on a laptop in seconds. Customers can add the runtime to their CI pipeline without provisioning GPU runners or modifying their build environment — a procurement-friendly property that closed AV stacks and torch-dependent uncertainty libraries do not match.
- **Composes with, rather than replaces, the rest of the stack.** A customer can keep their existing classical fusion for sensor-level blending, their existing per-model uncertainty estimator for prediction-level scoring, and their existing functional-safety tooling for documentation — and still put BCVF Autonomy Runtime at the planner-arbitration boundary. We are additive at the layer where additive is hardest to provide today.
- **Honest scope on where we do not compete (year one).** We are not trying to win on perception, on sensor drivers, on full-stack ecosystem breadth, on production-AV deployment count, or on multi-stack platform integrations in the first twelve months. We are trying to win on the one property that an autonomy safety case currently has no portable answer for: a runtime layer with a *proven* invariance for predictor-trust, validated end-to-end on a controlled failure scenario, with a pure-NumPy implementation that any program can drop into its existing planner without giving up the rest of its stack.

### In one sentence

Classical fusion combines signals. ML uncertainty estimates noise.
Closed AV stacks bury arbitration inside proprietary code. Open-source
stacks leave it to integrators. BCVF Autonomy Runtime gives the
planner a **provably invariant trust signal for its competing
predictors** — and that is a different product category than any of
the incumbents in this table are building for.

---

## Page 4 — Evidence & Roadmap

### What is proved today (v0.1, internal evidence)

| Area | Current state |
|---|---|
| **Test suite** | 166 tests passing across kernel, MPPI planner, runner, scenarios, predictors, manifold, traces, metrics, experiments |
| **Kernel modules shipped** | `core.py` (BCVF cost functional, V3.1 §3.3–§3.5 + Lemma 1), `manifold.py` (SE(2) body-frame error), `mppi_planner.py` (MPPI + Ketu→Rahu trust-weighted consensus), `runner.py`, `scenarios.py` (6 failure scenarios S1–S6), `predictors/` (M1–M4 SE(2) variants with failure injection) |
| **Lines of code** | ~4,100 LOC across 11 modules + tests, pure NumPy |
| **Lemma 1 invariance** | Mathematically proven (V3.1 §3.5; LLM analogue restated in `docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md` §2.6) and verified by unit tests on constructed constant-bias and linear-drift inputs |
| **Cost-order ablation** | ZEROTH / FIRST / SECOND empirically validated on linear-drift family — FIRST fails on linear drift as Lemma 1 case 2 predicts; SECOND passes; ZEROTH gates correctly |
| **Runtime contract ordering** | `predict → score → normalize → trust → consensus → plan → act` is pinned by tests, not configurable |
| **Companion experiment (autonomy validation)** | N=21 paired, scenario `S3_map_error_accel`, M=4 predictors, M4 failing-anchor injected. Final config: T=0.05, β=400, EMA α=0.05, deadband k=2σ, non-anchor pairing. Result: catastrophe rate 14.3% vs A0 23.8%; mean lateral deviation 1.79 m vs 4.30 m (best of all variants tested); std 5.76 vs 8.01; **sign test p = 0.0072** (17/21 seeds improve, 4 worsen). First statistically significant improvement over no-shaping baseline. |
| **Iterative ablation evidence** | Six bounded experiments traced the path from "additive-cost BCVF — directionless" to the validated config, with each architectural step (Ketu→Rahu refactor, EMA centering, deadband gate, non-anchor pairing) isolated and individually committed. Per-step trust-state logs available for the four resistant seeds. |
| **Design specification** | `docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md` — §0–§3 closed end-to-end (~3700 lines), §5.1/§5.2 autonomy-validated consumer pattern committed, §4/§6+ skeleton-only awaiting LLM-domain execution |
| **Known gaps** | No real-sensor data (synthetic predictors only); no multi-platform integration (ROS / Autoware / Apollo adapters not yet shipped); only the `S3_map_error_accel` scenario family deeply validated; LLM-domain transfer is design-stage only, no execution evidence yet |

All numbers above are from our own repository and CI — not third-party
benchmarks. An external multi-scenario benchmark and at least one
real-sensor-data pilot are planned (see roadmap).

### Empirical iteration that arrived at the validated config

| Experiment | Config | N | Headline | Outcome |
|---|---|---|---|---|
| Initial Ketu→Rahu smoke | T=0.2, β=100, raw cost softmin, anchor pairing | 26 | A3 vs A0 directionless | 4/26 cat (vs 5 A0); McNemar p = 1.00 |
| Lower-T sweep | T=0.1, β=200, raw cost softmin, anchor pairing | 26 | Worse than baseline (active-floor regression) | 8/26 cat; McNemar p = 0.55 |
| Add EMA centering | T=0.1, β=200, EMA α=0.05, anchor pairing | 26 | Rescued all 5 A0 catastrophes but 4 new regressions | 4/26 cat; McNemar p = 0.73 |
| Add deadband gate | T=0.05, β=400, EMA α=0.05, deadband k=2σ, anchor pairing | 21 | Best mean / std among single-fix variants | 3/21 cat; McNemar p = 0.625; mean 2.13 m |
| **Add non-anchor pairing (validated)** | T=0.05, β=400, EMA α=0.05, deadband k=2σ, **non-anchor pairing** | 21 | First statistically significant improvement | **3/21 cat; sign test p = 0.0072; mean 1.79 m** |

The trajectory above — published in our session repo with per-experiment
seed-by-seed traces and a deep-dive trust-state log on the resistant
seed set — is the empirical record an external reviewer can replay
end-to-end without GPU or sensor-data access. Each architectural
addition (EMA, deadband, non-anchor pairing) was isolated and committed
individually so the ablation is per-step inspectable.

### Developer-ergonomics and design improvements (this development cycle)

| Measure | Before BCVF runtime | After |
|---|---|---|
| Lines to compose a trust-weighted multi-predictor MPPI planner | Hand-written per stack (typically 200–500 LOC of arbitration glue) | ~10 lines (one factory call + two setters) |
| Empirically-validated trust-weighting recipe | None published | `T=0.05, β=400, ema_alpha=0.05, deadband_k_sigma=2.0, use_anchor_pairing=False` (autonomy-validated, sign p<0.01) |
| Replayable per-step trust-state trace | Custom logging per integration | First-class `set_trust_log_enabled(True)` + JSON dump |
| Per-source attribution at M ≥ 3 | Per-stack derivation | Shipped: `BCVFLLMResult.per_source_costs` with symmetric all-pairs sum |
| Lemma 1 verification in CI | Implicit / per-stack | Explicit unit tests on constructed invariance inputs |
| Switching between cost orders for ablation | Code change + retest | `cost_order = CostOrder.ZEROTH / FIRST / SECOND` config flag |

### 12-month roadmap

**Quarter 1 — External validation and ROS adapter**
- 2–3 external design-partner pilots in adjacent robotics domains
  (drones, mobile robots, manipulator arms — domains where the
  multi-predictor pattern exists and the safety-case pressure is
  real but the AV-program inertia is lower)
- ROS 2 adapter — the most common gap raised by robotics integrators
  in our early conversations; lets the runtime drop into a Nav2 /
  MoveIt planning node as a single dependency
- Multi-scenario validation: extend the N=21 sign-test result to all
  six S1–S6 scenarios at the validated config; publish per-scenario
  results

**Quarter 2 — Platform integrations and real-sensor pilot**
- Autoware perception → BCVF arbitrator → Autoware planner integration
  spike with a TIER IV-compatible reference customer
- Apollo OSS adapter (Baidu's open-source AV stack)
- KITTI / nuScenes replay pilot — validate the runtime on real-sensor
  multi-predictor traces rather than only synthetic SE(2) trajectories
- Begin the second domain track: drone-swarm trajectory arbitration
  (M = 5–10 predictor case where per-source attribution becomes more
  discriminative)

**Quarter 3 — Safety case template and certification path**
- Publish a safety-case template for the predictor-trust gap that maps
  the Lemma 1 invariance and the autonomy-validated consumer pattern
  to SOTIF (ISO 21448) and ISO 26262 traceability
- Regulator workshop preparation with two operators in BFSI-adjacent
  industrial-robotics or drone-delivery contexts
- First-party benchmark suite: extend S1–S6 with community-contributed
  scenarios and publish baseline numbers

**Quarter 4 — Production reference and managed offering**
- Target a production reference customer in an adjacent robotics domain
  (industrial mobile robot, drone delivery, warehouse automation)
- Optional managed runtime preview for teams that prefer a hosted
  trust-arbitration service over a library
- Begin SOC 2 process if the managed runtime is part of the offering
- Generalization beyond MPPI planners: adapter pattern for MPC, hybrid
  A*, sampling-based planners — kernel stays pure NumPy, integration
  layer adds adapters

### The ask

We are raising seed to evolve BCVF Autonomy Runtime from a pure-Python
research-grade kernel with one statistically-significant validated
configuration into a portable, multi-platform predictor-trust runtime
that operators can adopt without giving up their existing perception/
planning stack. The technology is live, internally tested with 166
passing tests, and validated end-to-end on a controlled failure
scenario with a published statistically-significant result. The
capital is earmarked for: external design-partner pilots in adjacent
robotics domains, ROS / Autoware / Apollo adapters, real-sensor-data
pilots (KITTI / nuScenes), the safety-case template work required for
SOTIF / ISO 26262 traceability, and the multi-scenario benchmark
expansion needed to make the validated configuration claim hold across
families beyond `S3_map_error_accel`.

Predictor disagreement handling is a structural gap in every modern
multi-model autonomy stack. The next 12–24 months are the right window
to establish a credible portable default for that layer — before the
incumbent AV platforms calcify their proprietary in-house solutions
into vendor-locked dependencies, and before the open-source robotics
stacks bake decision-maker glue code into their reference modules in
ways that are hard to displace later. We believe the combination of a
mathematically-proven invariance, an autonomy-validated consumer
pattern, and a pure-NumPy kernel that drops into any planner gives
BCVF Autonomy Runtime a defensible position in that window.

---

*Contact: Rakesh Mohan — Xozence Labs*
*Repo: `rasaha/symbolu` · Module: `symbolu_robotics/bcvf_autonomous/`*
*v0.1 · 166 internal tests · autonomy-validated at sign-test p<0.01 (N=21)*

