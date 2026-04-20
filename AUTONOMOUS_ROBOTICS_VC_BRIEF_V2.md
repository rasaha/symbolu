# Autonomous Robotics — VC Brief (v2, partial revision)

**Cognade Labs | BCVF Autonomy Runtime**
*Portable predictor-trust layer between multi-predictor robotics stacks and their planner*
*Version 0.2 (partial) — Prepared April 2026*

> **Status.** Pages 1–2 revised to the tighter, more investor-ready framing
> requested. Pages 3 (Competitive Landscape) and 4 (Evidence & Roadmap) remain
> in the v1 file at `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` and will be ported into
> v2 once the new framing is approved.

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
