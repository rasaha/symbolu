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
