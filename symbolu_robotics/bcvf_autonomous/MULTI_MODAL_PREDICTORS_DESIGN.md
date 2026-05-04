# Multi-modal predictor inputs — design + Lemma 1 carry-through analysis

**Status:** thin-shim adapter implemented and exposed in
`PROVISIONAL_API`; native multi-modal kernel remains research-tier.

## §1 Why this exists

Today every predictor in the production stack outputs an SE(2)
world-frame trajectory `(H, 3)` and the BCVF kernel computes
all-pairs body-frame error directly. Production sensor stacks
include predictors whose **native** output is not SE(2) world-frame:

* **HD-map-anchored predictors** report `(s, d, psi)` lane-frame
  coordinates — arc length along the lane centerline, signed
  lateral offset, heading relative to the lane direction.
* **Lane-detection cameras** report similar lane-relative output.
* **Map-relative SLAM** reports pose in the map frame, related to
  the world frame by a rigid-body transform.

If the multi-modal stack is to be arbitrated by BCVF, the kernel
needs a defensible answer to two questions:

1. How do non-SE(2) trajectories enter the kernel without
   breaking the existing all-pairs interface?
2. Does the kernel's Lemma 1 invariance — second-order zero on
   constant offset, linear drift — survive when one of the
   predictors lives in a different state space?

The brief's framing was *"worth investigating whether BCVF's
invariance proofs extend"*. This doc is the investigation; the
implementation that backs it up is the thin-shim adapter
(`predictors/state_space.py` + `predictors/multi_modal.py`).

## §2 Two architectural options

### 2.1 Thin-shim adapter (this commit)

Convert at the boundary. Each non-SE(2) predictor is paired with
the geometric metadata needed to lift its native trajectory to
SE(2) world-frame; the kernel runs unchanged.

```python
from symbolu_robotics.bcvf_autonomous.predictors import (
    MultiModalPredictor, PredictorStateSpace, LaneAnchor,
    unify_to_se2_bundle,
)

bundle = [
    MultiModalPredictor(p_lidar_se2, PredictorStateSpace.SE2_WORLD),
    MultiModalPredictor(p_camera_se2, PredictorStateSpace.SE2_WORLD),
    MultiModalPredictor(p_hdmap_lane, PredictorStateSpace.LANE_FRAME, anchor),
]
trajs_M_H_3 = unify_to_se2_bundle(bundle)   # (M, H, 3) SE(2) tensor
result = compute_bcvf_cost(list(trajs_M_H_3), cfg)
```

The shim is pure NumPy; no kernel change required. **The Lemma 1
carry-through analysis in §4 is the load-bearing finding.**

### 2.2 Native multi-modal kernel (research, out of scope)

Define disagreement directly on a chosen common manifold rather
than lifting to SE(2) first. The second-derivative invariance
properties on a curved manifold (e.g. a lane-frame Riemannian
structure) are a non-trivial extension of the SE(2) Lemma 1 proof.
Worth the investment only if the thin-shim turns out to lose
material information at an integration partner — the §6
ship-when-ready criteria gate the promotion.

## §3 Thin-shim mechanics

### 3.1 State-space taxonomy

`PredictorStateSpace` enumerates the supported native output
spaces:

* `SE2_WORLD` — standard SE(2) world-frame `(x, y, theta)`. The
  kernel's canonical input space — passed through unchanged.
* `LANE_FRAME` — lane-frame `(s, d, psi)`. Requires a paired
  `LaneAnchor`.

Adding a new state space (e.g. map-frame with a rigid-body
transform) is a localised change: extend the enum, add the
transform function, dispatch in `unify_to_se2_bundle`. No kernel
change.

### 3.2 LaneAnchor

A polyline of SE(2) world-frame waypoints + cumulative arc
lengths. Two factory methods cover the V1 deployment cases:

* `LaneAnchor.straight_x_axis(length=100.0)` — the Lemma-1-clean
  baseline (every waypoint has `theta = 0`).
* `LaneAnchor.constant_curvature(radius=50.0, arc_length=50.0)`
  — the case where the prior mental model said "Lemma 1 should
  break"; §4.2 records the corrected finding (it doesn't).

Real deployment uses `LaneAnchor.from_waypoints(...)` against the
map provider's polyline.

### 3.3 Lift `(s, d, psi) → (x, y, theta)`

```
(x, y) = lane_position(s) + d * left_normal(s)
theta  = lane_tangent(s) + psi
```

Where `lane_position(s)` and `lane_tangent(s)` are looked up by
linear interpolation between waypoints; heading interpolation is
atan2-safe (interpolates `sin`/`cos` rather than the raw angle).

The inverse `se2_to_lane_frame` projects each pose onto the
nearest centerline segment, extracting `(s, d, psi)` for
round-trip identity tests + as a building block for cross-modal
verification at the deployment-partner layer (UN ECE R155
defence-in-depth).

## §4 Lemma 1 carry-through — the load-bearing finding

### 4.1 Straight-lane case (trivial)

For a straight lane along `+x` at `y = 0`, `theta_lane = 0`
everywhere, so the lift is just `(s, d, psi) → (s, d, psi)`.
Constant lane-frame offset `(0, D, 0)` between two predictors
becomes constant SE(2) offset `(0, D, 0)` between them. Second
derivative = 0. **BCVF cost = 0 exactly** — pinned by
`test_lemma_1_carries_on_straight_lane`.

### 4.2 Curved-lane case (the corrected finding)

Pre-implementation hypothesis: a constant lateral offset `d` in
lane-frame would produce a curved SE(2) trajectory with non-zero
second-derivative; Lemma 1 invariance would break on curved lanes.

**Empirical finding: the hypothesis is wrong.** Lemma 1
invariance carries through on curved lanes too, because the
kernel's body-frame error primitive transforms correctly:

* Two predictors at the same `s` differing only by `(d, psi)`
  trace SE(2) trajectories that follow parallel offset curves
  (predictor 0 on the centerline, predictor 1 at lateral offset `D`).
* In **either predictor's body frame** (which is rotated by
  `theta_lane(s)` along the path), the offset to the other
  predictor is **constant** `(0, ±D, 0)`.
* The body-frame error trajectory is therefore constant in time,
  and the second derivative is exactly zero.
* The kernel's gate fires (constant body-frame offset exceeds
  `T`), but the gated cost on a zero second-derivative is zero.

**Pinned by `test_lemma_1_carries_on_curved_lane`** — both
predictors track the same curved lane at different `d`, and BCVF
total cost is exactly zero regardless of curvature radius.

The intuition that was wrong: the body-frame primitive
**rotates with the lane**, so a constant lane-frame offset stays
constant in body-frame regardless of how the lane curves. The
SE(2) trajectory of the offset point IS curved, but the
disagreement BETWEEN the two predictors at each step is constant
in body-frame.

### 4.3 The case where the kernel does fire (and should)

When two predictors track **genuinely different paths** — e.g.,
an SE(2)-claiming-straight predictor vs a lane-frame predictor
on a curved lane — the body-frame error grows with the
divergence between paths. The kernel correctly fires; this is
desired behaviour, not a Lemma 1 violation. **Pinned by
`test_different_reference_paths_fires_kernel`.**

### 4.4 The honest residual concern — cybersecurity (Lemma-1 trapdoor)

A lane-frame predictor with a constant biased `d` (e.g. a
spoofed HD-map predictor reporting consistent 0.1 m lateral
error) is **invisible to BCVF** at the kernel layer — the same
Lemma-1 trapdoor the adversarial_consistent_bias family already
characterizes. The multi-modal mode does not change this
boundary. Defence in depth (cross-modal sensor attestation,
calibration drift monitoring) per UN ECE R155 §7.3.4 is the
mitigation layer.

## §5 What the multi-modal mode does NOT do

* Does not handle out-of-anchor `s` values. The transform clips
  `s` to `[0, total_length]`; predictors emitting `s` outside the
  anchor must be rejected at the deployment-partner layer.
* Does not handle non-flat lanes (3-D terrain). The lift is
  strictly SE(2); a 3-D extension is research-tier.
* Does not detect bias in the underlying lane geometry. If the
  HD map itself is wrong, the lift is wrong consistently for
  every lane-frame predictor — invisible to BCVF.
* Does not promote any non-SE(2) state space to a stable API
  surface. Every multi-modal symbol is in `PROVISIONAL_API` —
  the signature may evolve as deployment partners exercise it.

## §6 Ship-when-ready criteria — promotion to STABLE_API

Multi-modal symbols promote from `PROVISIONAL_API` to `STABLE_API`
when all three of:

1. **A deployment partner exercises lane-frame predictors in
   production** for at least one quarter without an API change
   request.
2. **The certification grid extends with a `multi_modal_consistency`
   characterization family** asserting BCVF stays quiet on
   matched-path lane + SE(2) predictors and fires on different-
   path mixes — i.e. the §4 carry-through is regression-locked.
3. **Round-trip identity holds** to fp64 noise (`< 1e-9`) on
   every supported state space, pinned at every commit.

Until all three trigger, the multi-modal surface stays
provisional.

## §7 What's deliberately not in this commit

* No `multi_modal_consistency` characterization family. The §6
  criterion #2 — extending the certification grid — is the
  promotion gate, not the v1 deliverable.
* No native multi-modal kernel. §2.2 is research-tier.
* No 3-D / SE(3) extension. The lift is strictly SE(2)-to-SE(2).
* No graduation to `STABLE_API`. Per the policy in
  `API_STABILITY.md`, every new surface starts provisional.

## §8 API sketch

```python
from symbolu_robotics.bcvf_autonomous.predictors import (
    LaneAnchor,
    PredictorStateSpace,
    MultiModalPredictor,
    lane_frame_to_se2,
    se2_to_lane_frame,
    unify_to_se2_bundle,
)

# Build lane geometry from your HD map.
anchor = LaneAnchor.from_waypoints(centerline_xy)

# Mix SE(2) and lane-frame predictors in one bundle.
bundle = [
    MultiModalPredictor(lidar_se2, PredictorStateSpace.SE2_WORLD),
    MultiModalPredictor(camera_se2, PredictorStateSpace.SE2_WORLD),
    MultiModalPredictor(hdmap_lane, PredictorStateSpace.LANE_FRAME, anchor),
]

# Lift to the kernel boundary.
trajs = unify_to_se2_bundle(bundle)   # (3, H, 3) SE(2)

# Run BCVF unchanged.
from symbolu_robotics.bcvf_autonomous import compute_bcvf_cost, BCVFConfig
result = compute_bcvf_cost(list(trajs), cfg)
```

The point of the API sketch is to make the integration concrete:
the only new code in the integrator's stack is the
`MultiModalPredictor` wrapper at the boundary. Everything below
the kernel call is byte-identical to the single-modal V1 path.
