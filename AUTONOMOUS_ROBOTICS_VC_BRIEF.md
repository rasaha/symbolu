# Autonomous Robotics — VC Brief

**Cognade Labs | BCVF Autonomy Runtime — Trust-Weighted Predictor Consensus for Safety-Critical Robotics**
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
