# BCVF for Autonomous Systems — Engineering Design Document

**Product Line:** `bcvf_autonomous`
**Source Specification:** BCVF V3.1 Reviewer-Hardened (Rakesh Mohan, Symbol-U Patent Portfolio)
**Author:** Symbolu Engineering
**Status:** Phase 0 — Scope Lock

---

## Preface: Evaluation of the Layered Phase Plan

A layered phase plan was proposed with five phases: (0) scope lock, (1) core math
engine, (2) predictor framework, (3) MPPI planner integration, (4) scenario and
metrics harness, followed by (5) packaging. The overall structure is sound. The
dependency chain is correct — math kernel has no dependencies, predictors depend
on the manifold types, the planner depends on both, and the scenario harness
depends on all three.

However, the plan has gaps and underspecifications that this document corrects
before implementation begins. The corrections fall into three categories:

### A. Relationship to Existing Codebase (Not Addressed)

The plan correctly states "build beside existing robotics code, not inside the
current BCVF path" but does not specify _how_. The existing codebase has:

- `formulas/bcvf.py` — B1-B3 forward/backward consistency scorer (347 lines).
  This is a **different mathematical object**. B1-B3 scores a single action's
  feasibility vs. goal achievement. The V3.1 BCVF penalizes acceleration of
  cross-model trajectory disagreement. They share a name but not a function.
- `planning/mpc_planner.py` — gradient-free MPC with `CostFunction` class that
  has `compute_stage_cost(state, action, stage, coherence)`. The new MPPI planner
  must follow a compatible cost-injection pattern but must not subclass or modify
  this existing planner.
- `learning/dynamics_model.py` — ensemble of bootstrap-sampled linear models with
  `ensemble_disagreement` metric. This is 0th-order disagreement (magnitude of
  spread). The new predictor framework computes 2nd-order disagreement
  (acceleration of cross-model trajectory divergence). The existing ensemble
  pattern is a useful reference for interface design but must not be reused
  directly — it operates on a fundamentally different quantity.
- `safety/trajectory_validator.py` — 963-line pre-execution safety layer. V3.1
  Part 6 positions BCVF as Layer 4 in a defense-in-depth stack. The existing
  validator covers Layers 1-3. The new BCVF must produce output that the existing
  safety infrastructure can consume, but V1 does not require wiring them together.
- `core/types.py` — `RobotPose` uses Euclidean (x, y, z, roll, pitch, yaw). The
  new manifold module introduces SE(2) Lie group operations. These are separate
  types for V1; a future version may unify them.

The plan must specify that `bcvf_autonomous` imports _nothing_ from the existing
`formulas/bcvf.py`, `planning/mpc_planner.py`, or `learning/dynamics_model.py`.
It is a self-contained product line with its own types, its own planner, and its
own predictor abstraction.

### B. V3.1 Specification Details (Underspecified)

The plan omits several implementation-critical details from the V3.1 document:

1. **Body-frame error formula** (V3.1 Section 3.2): the disagreement operator on
   SE(2) uses `e = [R(theta_j)^T (p_i - p_j); wrap(theta_i - theta_j) * L]`
   with lever-arm length L. This is not a generic "log map" — it is a specific
   formula that homogenizes yaw error into linear displacement risk. The plan
   says "log map to tangent space" without this detail.

2. **Gate parameter guidance** (V3.1 Section 3.4.1): beta must be in [20/T, 50/T]
   to balance smoothness vs. transition sharpness. The plan does not capture this.

3. **Ring buffer for second-difference** (V3.1 Section 4.5): computing a(k)
   requires e(k-1), e(k), e(k+1) — a 3-step history per model pair. Total memory
   is O(P * 3 * dim(e)) where P is the number of pairs. The plan does not mention
   this data structure.

4. **Kinematic bicycle model** (V3.1 Appendix E.2): each predictor runs a
   simplified kinematic bicycle model forward from its own state estimate using
   the candidate control sequence. The plan says "simplified state estimators /
   forward predictors" without specifying the shared dynamics model.

5. **Lambda_c sweep** (V3.1 Section E.6): the validation protocol requires a
   9-value sweep of lambda_c in {0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0,
   20.0}. The plan mentions "ablations" generically.

### C. Missing Engineering Decisions

1. **Dependency policy**: V1 should be NumPy-only. No JAX, no PyTorch, no GPU.
   JAX-accelerated MPPI is a V2 concern. The plan mentions "GPU-accelerated MPPI
   rollouts" in the code architecture table, which contradicts "hardware
   acceleration explicitly out of scope."

2. **Internal simulator specification**: The plan says "start with a lightweight
   internal simulator" but does not define it. V1 needs a 2D kinematic bicycle
   model environment with configurable obstacle injection and sensor failure
   hooks. This is ~200 lines, not a production simulator.

3. **Timing budget**: V3.1 specifies 50Hz planning. At K=1000 rollouts, H=50
   steps, M=4 models with anchor pairing, that is 1000 * 50 * 3 = 150K
   evaluations per cycle. Pure NumPy can do this in ~15ms on modern hardware.
   Phase 3 must include a timing benchmark that validates this.

---

## Phase 0 — Scope Lock

### 0.1 Purpose

Lock the boundaries of V1 so implementation does not sprawl. Every decision below
is motivated by one principle: **build the smallest system that can demonstrate
the V3.1 core innovation** — penalizing the acceleration of cross-model
disagreement in trajectory selection.

### 0.2 V1 Target

| Dimension          | V1 Choice                                    | Rationale                                                              |
|--------------------|----------------------------------------------|------------------------------------------------------------------------|
| Domain             | Ground vehicle only                          | SE(2) is simplest manifold; matches V3.1 primary validation domain     |
| Manifold           | SE(2)                                        | 3-dimensional tangent space (dx, dy, L*dtheta); avoids SO(3) concerns  |
| Planner            | MPPI (sampling-based)                        | Gradient-free; handles gate non-convexity natively (V3.1 Appendix D)   |
| Predictor count    | M = 4 heterogeneous                         | Matches V3.1 Appendix E.2 specification exactly                       |
| Predictor types    | IMU+odom, LiDAR-SLAM proxy, VO proxy, GNSS  | Covers 4 distinct sensor modalities with distinct failure modes        |
| Pairing mode       | Anchor pairing (M1 as anchor)               | O(K*H*M) complexity; M1 (IMU+odom) is most stable baseline            |
| Environment        | Internal 2D kinematic bicycle simulator      | Self-contained; no external dependencies; ~200 lines                   |
| Dependencies       | NumPy only                                   | No JAX, PyTorch, CARLA, ROS2 in V1                                    |
| Language           | Python 3.10+                                 | Matches existing `symbolu_robotics` requirement                        |
| Test framework     | pytest                                       | Matches existing `symbolu_robotics/tests/` convention                  |

### 0.3 Predictor Specification (V3.1 Appendix E.2)

Each predictor shares a common forward dynamics model — the **kinematic bicycle
model** — but starts from its own state estimate, which diverges under different
failure conditions. This is the key design insight from V3.1: realistic
heterogeneous disagreement without requiring full SLAM/VO implementations.

| Model ID | Predictor Type               | Sensor Basis           | Characteristic Failure Mode                         |
|----------|------------------------------|------------------------|-----------------------------------------------------|
| M1       | IMU + wheel odometry         | IMU, wheel encoders    | Drift over time (no absolute correction)            |
| M2       | LiDAR-SLAM proxy             | LiDAR point cloud      | Degrades in glass/reflective, rain, fog             |
| M3       | Visual odometry proxy        | RGB camera             | Fails in low light, texture-poor environments       |
| M4       | GNSS + map matching proxy    | GPS receiver, HD map   | Multipath in urban canyons, outdated maps           |

Each predictor is a _proxy_ — it simulates the characteristic noise and failure
profile of its real-world counterpart, not the full localization algorithm.

### 0.4 MPPI Configuration Defaults (V3.1 Appendix D.6)

These are the starting parameters, not final-tuned values. Phase 3 will validate
and Phase 4 will sweep.

| Parameter              | Default     | Source                    |
|------------------------|-------------|---------------------------|
| Rollouts K             | 1000        | V3.1 Appendix D.6         |
| Horizon H              | 50 steps    | V3.1 Appendix E.1 (5s)    |
| Time step dt           | 0.1s        | V3.1 Appendix E.2         |
| Temperature lambda     | 5.0         | V3.1 Appendix D.6 midpoint|
| BCVF weight lambda_c   | 1.0         | V3.1 Table, SE(2) range   |
| Gate threshold T       | 0.1m        | Noise floor estimate      |
| Gate steepness beta    | 200.0       | 20/T = 20/0.1 = 200       |
| Huber delta            | 0.5         | V3.1 Section 3.4          |
| Lever-arm L            | 2.5m        | Typical passenger vehicle  |
| Anchor model           | M1          | IMU+odom is most stable    |
| Warm-start             | Enabled     | V3.1 Appendix D.6         |

### 0.5 Explicitly Out of Scope for V1

| Item                                  | Why Deferred                                                     |
|---------------------------------------|------------------------------------------------------------------|
| SE(3) manifold                        | Requires SO(3) Log map with pi-singularity handling              |
| Drones / marine / space domains       | SE(3) prerequisite; different sensor suites                      |
| CARLA integration                     | External dependency; internal sim proves the math first          |
| ROS2 deployment                       | Production concern; V1 is evaluation/research                    |
| GPU acceleration (JAX/CUDA)           | NumPy validates correctness; JAX is a V2 optimization            |
| Production SLAM/VO implementations    | Proxy predictors are sufficient for V1 validation                |
| Fault detection dashboards            | Visualization is Phase 5 packaging; not core to the innovation   |
| All-pairs mode as default             | Anchor pairing is O(M) vs O(M^2); all-pairs is a test option    |
| Integration with existing safety stack| V1 validates BCVF in isolation; wiring to trajectory_validator.py is V2 |
| Patent-claim breadth implementation   | V1 proves the narrow (Tier 1) claim; breadth follows evidence    |
| Journal-grade statistical protocol    | V1 targets directional results; statistical rigor is Phase 4+    |

### 0.6 Naming and Namespace Decisions

The existing `formulas/bcvf.py` implements B1-B3 (forward/backward consistency
scoring). The new `bcvf_autonomous/` implements V3.1 (second-order cross-model
disagreement regularization). These are different systems.

**Rules:**

1. `bcvf_autonomous/` is a top-level subdirectory of `symbolu_robotics/`, peer to
   `formulas/`, `planning/`, `safety/`, etc.
2. `bcvf_autonomous/` imports **nothing** from `formulas/bcvf.py`.
3. `bcvf_autonomous/` imports **nothing** from `planning/mpc_planner.py` or
   `learning/dynamics_model.py`.
4. `bcvf_autonomous/` MAY import from `core/types.py` for shared types
   (`RobotPose`, `Layer12D`) if convenient, but is not required to.
5. The existing `formulas/bcvf.py` is not modified, renamed, or deprecated.
6. Test files go in `bcvf_autonomous/tests/`, not in the existing
   `symbolu_robotics/tests/` directory.

**Import path:** `from symbolu_robotics.bcvf_autonomous import ...`

### 0.7 Repository Structure (V1)

```
symbolu_robotics/
  bcvf_autonomous/
    __init__.py                  # Package init, version, public API
    DESIGN.md                    # This document
    core.py                      # Definitions 1-7: disagreement, velocity,
                                 #   acceleration, gate, Huber, J_BCVF
                                 #   (~150 lines, Phase 1)
    manifold.py                  # SE(2) Lie group: compose, inverse, log_map,
                                 #   body_frame_error, wrap_angle
                                 #   (~120 lines, Phase 1)
    predictors/
      __init__.py
      base.py                    # Abstract predictor interface + bicycle model
                                 #   (~100 lines, Phase 2)
      imu_odometry.py            # M1: dead reckoning with drift
                                 #   (~80 lines, Phase 2)
      lidar_slam.py              # M2: proxy with glass/rain failure
                                 #   (~80 lines, Phase 2)
      visual_odometry.py         # M3: proxy with low-light failure
                                 #   (~80 lines, Phase 2)
      gnss_map.py                # M4: proxy with multipath/map-error failure
                                 #   (~80 lines, Phase 2)
    mppi_planner.py              # MPPI with J_perf + lambda_c * J_BCVF
                                 #   (~300 lines, Phase 3)
    simulator.py                 # Lightweight 2D bicycle model environment
                                 #   (~200 lines, Phase 3)
    scenarios.py                 # Failure injection definitions
                                 #   (~150 lines, Phase 4)
    metrics.py                   # Data collection and statistical analysis
                                 #   (~200 lines, Phase 4)
    run_experiments.py           # CLI orchestrator for sweeps and ablations
                                 #   (~100 lines, Phase 4)
    tests/
      __init__.py
      test_manifold.py           # SE(2) operations (Phase 1)
      test_core.py               # BCVF math kernel (Phase 1)
      test_predictors.py         # Predictor agreement/divergence (Phase 2)
      test_mppi.py               # Planner integration (Phase 3)
      test_scenarios.py          # End-to-end scenario runs (Phase 4)
  configs/
    bcvf_autonomous/
      default_se2.yaml           # Default parameters for SE(2) ground vehicle
```

**Estimated total:** ~1,540 lines of production code + ~600 lines of tests.

### 0.8 Dependency on V3.1 Document Sections

Each phase maps to specific V3.1 sections. Implementers must read these sections
before starting the corresponding phase.

| Phase   | V3.1 Sections Required                                              |
|---------|---------------------------------------------------------------------|
| Phase 1 | 3.1-3.6 (math formulation), 4.1 (convexity), Lemma 1 (bias tol.)  |
| Phase 2 | Appendix E.2 (predictor specs), E.3 (failure modes)                |
| Phase 3 | Appendix D (MPPI convergence), E.1 (platform), D.6 (MPPI config)  |
| Phase 4 | E.3-E.8 (scenarios, ablation, metrics), 7.1-7.5 (validation)      |
| Phase 5 | 5.1 (domain coverage), 6.3 (defense-in-depth), 9.2 (readiness)    |

### 0.9 Success Criteria for Phase 0

Phase 0 is complete when:

- [ ] This document is reviewed and committed
- [ ] The directory structure in Section 0.7 is created (empty `__init__.py` files)
- [ ] The `default_se2.yaml` config file contains the parameters from Section 0.4
- [ ] No code has been written yet — only structure and specification

### 0.10 Risk Register (V1 Scope)

| Risk                                           | Likelihood | Impact | Mitigation                                          |
|------------------------------------------------|------------|--------|-----------------------------------------------------|
| NumPy MPPI too slow for 1000 rollouts at 50Hz  | Medium     | High   | Profile in Phase 3; vectorize rollouts; reduce K     |
| Proxy predictors too simplistic for meaningful divergence | Low | Medium | Bicycle model + noise injection covers V3.1 scenarios |
| Gate non-convexity causes MPPI oscillation      | Low        | Medium | V3.1 Proposition 4 argues against; verify in Phase 3 |
| SE(2) wrap-angle edge cases at +/-pi           | Medium     | Low    | Explicit test cases in Phase 1; use atan2 consistently|
| Scope creep into SE(3) or CARLA                | Medium     | High   | This document; enforce in code review                |
| Confusion with existing B1-B3 BCVF naming      | High       | Low    | Section 0.6 naming rules; separate import paths      |

---

---

## Phase 1 — Core Math Engine

### 1.1 Purpose

Build the mathematical kernel that can score one candidate control sequence
against a set of predictor trajectories and return a scalar BCVF cost. This is
the irreducible core of the V3.1 innovation. Everything else — predictors,
planner, scenarios — is infrastructure around this kernel.

Phase 1 produces two files: `manifold.py` and `core.py`. Together they implement
V3.1 Definitions 1-7 and Lemma 1 with full test coverage.

### 1.2 Modules

#### 1.2.1 `manifold.py` — SE(2) Lie Group Operations

**V3.1 reference:** Section 3.1-3.2

This module provides the geometric foundation. SE(2) is the group of rigid-body
transformations in the plane: position (x, y) and heading (theta). All
disagreement computations happen in the tangent space of this group, not in
Euclidean space.

**Types to define:**

```python
@dataclass
class SE2Pose:
    """Pose on SE(2): position + heading."""
    x: float      # meters
    y: float      # meters
    theta: float   # radians, wrapped to [-pi, pi)
```

**Functions to implement:**

| Function              | Signature                                              | V3.1 Reference | Description                                                              |
|-----------------------|--------------------------------------------------------|----------------|--------------------------------------------------------------------------|
| `wrap_angle`          | `(angle: float) -> float`                              | Section 3.2    | Wrap to [-pi, pi) using atan2(sin, cos)                                  |
| `compose`             | `(a: SE2Pose, b: SE2Pose) -> SE2Pose`                  | —              | Group composition: rotate b's position by a's heading, add positions, add angles |
| `inverse`             | `(pose: SE2Pose) -> SE2Pose`                            | —              | Group inverse: negate rotated position, negate angle                     |
| `log_map`             | `(pose: SE2Pose) -> np.ndarray`                         | Section 3.2    | Map from SE(2) to tangent space se(2) in R^3                             |
| `body_frame_error`    | `(pose_i: SE2Pose, pose_j: SE2Pose, lever_arm: float) -> np.ndarray` | Section 3.2 | The V3.1 disagreement operator (Definition 1 specialized to SE(2))       |

**Critical formula — `body_frame_error`** (V3.1 Section 3.2):

```
e_ij(k) = [R(theta_j)^T (p_i - p_j);  wrap(theta_i - theta_j) * L]
```

Where:
- `R(theta_j)^T` is the 2x2 rotation matrix transposed (body frame of j)
- `p_i - p_j` is the position difference in world frame
- `L` is the lever-arm length (meters) that homogenizes yaw error into meters
- Result is in R^3: [dx_body, dy_body, dtheta_scaled]

This is the only manifold-aware operation that matters for V1. The `log_map`
function is provided for completeness but `body_frame_error` is the one called
in the hot path.

**Why lever-arm scaling matters:** Without L, a 0.1 radian yaw error and a 0.1
meter position error have the same norm, but at L=2.5m the yaw error maps to
0.25m of displacement risk at the vehicle front. This is the "homogenization"
the V3.1 document refers to. L=2.5m is a reasonable default for a passenger
vehicle (approximate distance from rear axle to front bumper).

**Implementation notes:**
- Use `math.atan2(math.sin(a), math.cos(a))` for angle wrapping, not modular
  arithmetic, to avoid edge cases at +/-pi.
- `compose` and `inverse` are used to construct `body_frame_error` but are also
  tested independently.
- All functions must be pure (no state), taking float/ndarray in and returning
  float/ndarray out. No classes with mutable state in this module.

**Estimated size:** ~120 lines including docstrings.

#### 1.2.2 `core.py` — BCVF Cost Functional

**V3.1 reference:** Sections 3.3-3.5, Lemma 1

This module implements the complete BCVF cost computation chain: disagreement
-> velocity -> acceleration -> gate -> penalty -> sum.

**Types to define:**

```python
@dataclass
class BCVFConfig:
    """All tunable parameters for the BCVF cost functional."""
    lambda_c: float = 1.0       # Coherence weight in total cost
    gate_threshold: float = 0.1  # T: noise floor (meters)
    gate_beta: float = 200.0     # Steepness (range: 20/T to 50/T)
    huber_delta: float = 0.5     # Pseudo-Huber transition point
    lever_arm: float = 2.5       # L: for SE(2) body-frame error
    weight_matrix: np.ndarray    # W_c diagonal: [w_dx, w_dy, w_dtheta]
    use_anchor_pairing: bool = True
    anchor_index: int = 0        # Which predictor is anchor (0 = M1)
    dt: float = 0.1              # Sampling period

@dataclass
class BCVFResult:
    """Detailed output from BCVF cost computation."""
    total_cost: float                          # J_BCVF(u)
    per_pair_costs: Dict[Tuple[int,int], float]  # Cost per model pair
    max_acceleration_norm: float               # Largest ||a_ij|| seen
    gate_activation_count: int                 # How many (pair, step) had g > 0.5
```

**Functions to implement (in dependency order):**

| Function                      | Signature                                                                       | V3.1 Def | Description |
|-------------------------------|---------------------------------------------------------------------------------|----------|-------------|
| `compute_disagreement`        | `(traj_i: ndarray, traj_j: ndarray, lever_arm: float) -> ndarray`               | Def 1    | e_ij(k) for all k; calls `body_frame_error` per step. Input shapes: (H, 3) each for SE(2) poses [x,y,theta]. Output shape: (H, 3). |
| `compute_disagreement_velocity` | `(disagreement: ndarray, dt: float) -> ndarray`                               | Def 2    | v_ij(k) = [e(k) - e(k-1)] / dt. Output shape: (H-1, 3). |
| `compute_disagreement_acceleration` | `(disagreement: ndarray, dt: float) -> ndarray`                           | Def 3    | a_ij(k) = [e(k+1) - 2*e(k) + e(k-1)] / dt^2. Output shape: (H-2, 3). This is the core innovation. |
| `smooth_gate`                 | `(disagreement: ndarray, threshold: float, beta: float, weight_matrix: ndarray) -> ndarray` | Def 4 | g_ij(k) = sigmoid(beta * (||W_g^{1/2} e_ij(k)|| - T)). Output shape: (H-2,) aligned with acceleration. |
| `pseudo_huber`                | `(r: ndarray, delta: float) -> ndarray`                                         | Def 5    | rho(r; delta) = delta^2 * (sqrt(1 + (r/delta)^2) - 1). Elementwise. |
| `compute_bcvf_cost`           | `(trajectories: List[ndarray], config: BCVFConfig) -> BCVFResult`               | Def 6    | Full J_BCVF(u). Orchestrates all above functions over model pairs (or anchor pairs). |

**Computation flow inside `compute_bcvf_cost`:**

```
For each model pair (i, j):        # anchor mode: j = anchor for all i != anchor
  1. disagreement = compute_disagreement(traj_i, traj_j, L)     # (H, 3)
  2. acceleration = compute_disagreement_acceleration(disagreement, dt)  # (H-2, 3)
  3. gate = smooth_gate(disagreement[1:-1], T, beta, W_g)       # (H-2,)
  4. accel_norms = ||W_c^{1/2} @ acceleration||  per step       # (H-2,)
  5. penalty = pseudo_huber(accel_norms, delta)                  # (H-2,)
  6. pair_cost = sum(gate * penalty) * dt                        # scalar

J_BCVF = sum of all pair_costs
```

**Step 3 alignment note:** The gate uses `disagreement[1:-1]` (steps 1 to H-2)
because the acceleration at step k requires e(k-1), e(k), e(k+1), so k ranges
from 1 to H-2. The gate must evaluate disagreement at the same k indices. This
is a subtle off-by-one that must be tested explicitly.

**Anchor pairing vs. all-pairs:**

- **Anchor mode** (default): Fix j = anchor_index. Iterate i over all other
  models. Produces M-1 pairs. Complexity: O(H * M).
- **All-pairs mode**: Iterate over all i < j. Produces M*(M-1)/2 pairs.
  Complexity: O(H * M^2).

Both modes use the same per-pair computation. The only difference is which pairs
are enumerated. Implement both behind the `use_anchor_pairing` flag.

**Weight matrices W_g and W_c:**

The V3.1 document uses two weight matrices:
- W_g (gate weighting): controls sensitivity of the gate to different
  disagreement dimensions. For V1, use identity.
- W_c (cost weighting): controls relative importance of dx, dy, dtheta
  disagreement acceleration. For V1, use the diagonal from config.

For V1, these can be the same matrix. Separate them in the interface so V2 can
diverge them without API changes.

**Implementation notes:**
- All trajectory inputs are NumPy arrays of shape (H, 3) where columns are
  [x, y, theta]. This is not the SE2Pose dataclass — that's for single poses.
  Trajectory-level operations work on raw arrays for performance.
- The `body_frame_error` function from `manifold.py` must be vectorizable:
  called once per step per pair, so H * P calls total. For H=50 and P=3
  (anchor mode, M=4), that's 150 calls per MPPI rollout. At K=1000 rollouts,
  150K calls. This must be fast — implement the inner loop as vectorized NumPy,
  not a Python for-loop over steps.
- Provide a **vectorized batch entry point** for MPPI: `compute_bcvf_cost_batch`
  that accepts K sets of M trajectories and returns K scalar costs. This avoids
  Python-level looping over rollouts.

```python
def compute_bcvf_cost_batch(
    trajectories_batch: List[List[np.ndarray]],  # K x M x (H, 3)
    config: BCVFConfig,
) -> np.ndarray:  # (K,) costs
```

**Estimated size:** ~150 lines including docstrings.

### 1.3 Test Specification

Tests go in `bcvf_autonomous/tests/test_manifold.py` and
`bcvf_autonomous/tests/test_core.py`.

#### 1.3.1 `test_manifold.py`

| Test                           | What It Validates                                                       |
|--------------------------------|-------------------------------------------------------------------------|
| `test_wrap_angle_identity`     | Angles in [-pi, pi) are unchanged                                       |
| `test_wrap_angle_overflow`     | 2*pi wraps to ~0, -3*pi wraps to ~pi                                   |
| `test_wrap_angle_boundary`     | pi wraps to -pi (half-open interval)                                    |
| `test_compose_identity`        | compose(a, identity) == a                                               |
| `test_compose_inverse`         | compose(a, inverse(a)) == identity (within tolerance)                   |
| `test_inverse_inverse`         | inverse(inverse(a)) == a                                                |
| `test_body_frame_error_zero`   | Same pose -> zero error                                                 |
| `test_body_frame_error_pure_translation` | Heading-aligned offset -> [dx, 0, 0]                          |
| `test_body_frame_error_pure_rotation`    | Same position, different heading -> [0, 0, L*dtheta]           |
| `test_body_frame_error_lever_arm`        | Doubling L doubles the yaw component of error                  |
| `test_body_frame_error_body_frame`       | Error is expressed in j's body frame, not world frame           |

#### 1.3.2 `test_core.py`

| Test                                     | What It Validates                                                  | V3.1 Ref     |
|------------------------------------------|--------------------------------------------------------------------|--------------|
| `test_constant_bias_zero_cost`           | Constant disagreement across all steps -> J_BCVF = 0              | Lemma 1      |
| `test_linear_drift_zero_cost`            | Linearly growing disagreement -> acceleration = 0 -> J_BCVF = 0   | Section 2.4.1 |
| `test_accelerating_divergence_nonzero`   | Quadratically growing disagreement -> positive J_BCVF              | Core innovation |
| `test_gate_below_threshold`              | Disagreement below T -> gate ≈ 0 -> cost ≈ 0 even with acceleration | Def 4      |
| `test_gate_above_threshold`              | Disagreement above T -> gate ≈ 1 -> cost reflects acceleration     | Def 4       |
| `test_huber_quadratic_near_zero`         | Small r -> rho ≈ r^2/2 (quadratic regime)                         | Def 5        |
| `test_huber_linear_large_r`             | Large r -> rho ≈ delta*|r| (linear regime)                        | Def 5        |
| `test_anchor_vs_all_pairs_consistent`    | For M=2, anchor and all-pairs produce identical cost               | Section 4.5  |
| `test_anchor_fewer_pairs`                | For M=4, anchor produces 3 pairs, all-pairs produces 6            | Section 4.5  |
| `test_perfect_agreement_zero_cost`       | All models predict identical trajectories -> J_BCVF = 0           | Def 6        |
| `test_batch_matches_sequential`          | `compute_bcvf_cost_batch` matches loop of `compute_bcvf_cost`     | —            |
| `test_cost_positive_semidefinite`         | J_BCVF >= 0 for random trajectories (property test, N=100)        | Theorem 3 step 1 |
| `test_off_by_one_alignment`              | Gate indices align with acceleration indices (H-2 elements each)  | Section 1.2.2 note |

#### 1.3.3 Specific Numerical Test Cases

These tests use hardcoded trajectories to validate against hand-computed values:

**Test A — Stationary with constant offset:**
```
traj_i = [[1.0, 0.0, 0.0]] * 10    # 10 steps, constant
traj_j = [[0.5, 0.0, 0.0]] * 10    # constant 0.5m offset
Expected: e = [0.5, 0, 0] at every step, a = [0,0,0], J_BCVF = 0
```

**Test B — Sudden jump at step 5:**
```
traj_i = [[0,0,0]] * 10
traj_j = [[0,0,0]] * 5 + [[1,0,0]] * 5
Expected: e jumps from [0,0,0] to [1,0,0] at step 5.
          a is nonzero at steps 4,5,6 (the second-difference stencil).
          J_BCVF > 0.
```

**Test C — Quadratic divergence:**
```
traj_i = [[0,0,0]] * 10
traj_j = [[0.01 * k**2, 0, 0] for k in range(10)]
Expected: e grows quadratically, v grows linearly, a is constant and nonzero.
          J_BCVF > 0 and scales with acceleration magnitude.
```

### 1.4 Design Constraints

1. **No predictor or planner dependencies.** `core.py` and `manifold.py` must be
   testable in isolation. They accept raw NumPy arrays of trajectories, not
   predictor objects or planner state.

2. **No YAML loading.** The `BCVFConfig` dataclass is populated by the caller
   (planner or test). Config file parsing is a Phase 3 concern.

3. **No mutable state.** All functions are pure. `compute_bcvf_cost` takes
   trajectories + config and returns a result. No object tracks history across
   calls — the ring buffer for real-time operation is a Phase 3 concern.

4. **Float64 precision.** Use numpy float64 throughout. The second-difference
   operator divides by dt^2 = 0.01, which amplifies numerical error. Float32
   is insufficient.

5. **Vectorized hot path.** The body-frame error computation over H steps must
   use NumPy broadcasting, not a Python for-loop. The batch entry point must
   use vectorized operations over K rollouts where possible.

### 1.5 Acceptance Criteria

Phase 1 is complete when:

- [ ] `manifold.py` implements all 5 functions from Section 1.2.1
- [ ] `core.py` implements all 6 functions + 1 batch function from Section 1.2.2
- [ ] All tests from Section 1.3 pass
- [ ] Lemma 1 (constant bias = zero cost) is verified numerically
- [ ] Linear drift = zero cost is verified numerically
- [ ] Accelerating divergence = positive cost is verified numerically
- [ ] `compute_bcvf_cost_batch` with K=1000, H=50, M=4 (anchor) completes in
  <50ms on a single CPU core (timing assertion in test)
- [ ] No imports from any other `symbolu_robotics` module

### 1.6 What Phase 1 Does NOT Build

- Predictor objects (Phase 2)
- MPPI planner or J_perf (Phase 3)
- Scenario injection or metrics collection (Phase 4)
- Config file loading (Phase 3)
- Real-time ring buffer for streaming disagreement history (Phase 3)
- Visualization or plotting (Phase 5)

---

## Phase 2 — Predictor Framework

### 2.1 Purpose

Build a set of 4 heterogeneous predictors that can generate divergent SE(2)
trajectories under injected failure conditions. These predictors feed into the
Phase 1 math kernel — they produce the trajectory arrays that `compute_bcvf_cost`
scores.

Phase 2 does NOT build real SLAM, visual odometry, or GPS receivers. It builds
_proxy predictors_: lightweight objects that simulate the characteristic noise
and failure profiles of their real-world counterparts. The key V3.1 design
insight (Appendix E.2) is that each predictor shares a common forward dynamics
model — the kinematic bicycle model — but starts from its own state estimate,
which diverges under different failure conditions. This produces realistic
heterogeneous disagreement without requiring full localization stacks.

Phase 2 produces 5 files: `base.py` + 4 predictor implementations.

### 2.2 Architecture

```
                    ┌───────────────────────────┐
                    │     BasePredictor          │
                    │  - bicycle_model(state, u) │
                    │  - predict(state, u_seq)   │
                    │  - inject_failure(params)  │
                    │  - reset()                 │
                    └─────────┬─────────────────┘
                              │ inherits
            ┌─────────────────┼─────────────────────┐
            │                 │                      │
    ┌───────┴───────┐ ┌──────┴────────┐  ┌──────────┴──────────┐
    │ IMUOdometry   │ │ LidarSLAM     │  │ VisualOdometry      │
    │ (M1 - anchor) │ │ (M2)          │  │ (M3)                │
    └───────────────┘ └───────────────┘  └─────────────────────┘
                                                    │
                                          ┌─────────┴──────────┐
                                          │ GNSSMap             │
                                          │ (M4)                │
                                          └────────────────────┘
```

All 4 predictors share the same `bicycle_model()` forward dynamics. They differ
only in:
1. **State estimate noise** — each has a different noise profile in nominal mode
2. **Failure injection** — each has a characteristic failure mode that can be
   triggered at runtime to cause its state estimate to diverge

### 2.3 Modules

#### 2.3.1 `predictors/base.py` — Abstract Base + Bicycle Model

**V3.1 reference:** Appendix E.2

**Types to define:**

```python
@dataclass
class BicycleConfig:
    """Kinematic bicycle model parameters."""
    wheelbase: float = 2.7       # L_wb: meters (rear axle to front axle)
    max_steering: float = 0.6    # radians (~34 degrees)
    max_velocity: float = 15.0   # m/s
    max_acceleration: float = 3.0  # m/s^2
    dt: float = 0.1              # seconds

@dataclass
class PredictorState:
    """Current state estimate held by a predictor."""
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    velocity: float = 0.0       # current forward velocity (m/s)
    timestamp: float = 0.0

@dataclass
class FailureConfig:
    """Failure injection parameters."""
    active: bool = False
    onset_time: float = 0.0     # when failure begins (seconds)
    severity: float = 1.0       # 0.0 = nominal, 1.0 = full failure
    ramp_duration: float = 0.0  # seconds to ramp from 0 to severity

class ControlInput:
    """Single control input for bicycle model."""
    velocity: float = 0.0       # desired forward velocity (m/s)
    steering: float = 0.0       # steering angle (radians)
```

**Abstract base class:**

```python
class BasePredictor(ABC):
    """
    Abstract predictor that forward-simulates trajectories from its own
    state estimate using a kinematic bicycle model.
    """

    def __init__(self, model_id: str, bicycle_config: BicycleConfig):
        ...

    def bicycle_step(self, state: PredictorState, control: ControlInput) -> PredictorState:
        """One step of kinematic bicycle model. Shared by all predictors."""
        ...

    @abstractmethod
    def apply_noise(self, state: PredictorState, step: int) -> PredictorState:
        """Apply predictor-specific noise to state estimate."""
        ...

    @abstractmethod
    def apply_failure(self, state: PredictorState, time: float) -> PredictorState:
        """Apply predictor-specific failure distortion."""
        ...

    def predict(self, control_sequence: np.ndarray) -> np.ndarray:
        """
        Forward-simulate trajectory from current state estimate.

        Args:
            control_sequence: (H, 2) array of [velocity, steering] per step

        Returns:
            trajectory: (H, 3) array of [x, y, theta] per step
        """
        ...

    def update_state(self, ground_truth: PredictorState) -> None:
        """Update internal state estimate from ground truth + noise."""
        ...

    def set_failure(self, config: FailureConfig) -> None:
        """Configure failure injection."""
        ...

    def reset(self) -> None:
        """Reset to initial state, clear failure."""
        ...
```

**Kinematic bicycle model** (`bicycle_step`):

```
x_{t+1}     = x_t + v * cos(theta_t) * dt
y_{t+1}     = y_t + v * sin(theta_t) * dt
theta_{t+1} = theta_t + (v / L_wb) * tan(delta) * dt
```

Where:
- `v` = forward velocity, clamped to `[-max_velocity, max_velocity]`
- `delta` = steering angle, clamped to `[-max_steering, max_steering]`
- `L_wb` = wheelbase
- `dt` = time step

This is the standard kinematic bicycle model used throughout the autonomous
driving literature. It is shared identically across all 4 predictors — the only
difference is the state estimate each predictor starts from.

**`predict()` method flow:**

```
1. Start from self._state (predictor's current state estimate)
2. For each step k in control_sequence:
   a. state = bicycle_step(state, control[k])
   b. state = apply_noise(state, k)      # predictor-specific noise
   c. state = apply_failure(state, time)  # if failure is active
   d. record state into trajectory array
3. Return trajectory as (H, 3) ndarray of [x, y, theta]
```

**Important:** `predict()` does NOT mutate `self._state`. It simulates forward
from a copy. The internal state only changes via `update_state()`, which is
called once per real time step by the simulation loop (Phase 3).

**Estimated size:** ~100 lines.

#### 2.3.2 `predictors/imu_odometry.py` — M1 (Anchor)

**V3.1 reference:** Appendix E.2 Model M1

**Sensor basis:** IMU + wheel encoders (dead reckoning)

**Nominal noise profile:**
- Position noise: N(0, 0.01) meters per step
- Heading noise: N(0, 0.001) radians per step
- Cumulative drift: 0.005 m/step (random walk, does not self-correct)

**Characteristic failure mode:** Drift over time. No absolute reference, so
errors accumulate. This is the _mildest_ failure — M1 is chosen as anchor
because it degrades slowly and predictably, never jumping or hallucinating.

**Failure injection:** Accelerated drift rate. When failure is active, drift
rate increases from 0.005 to `0.005 + severity * 0.05` m/step. This simulates
IMU bias instability or wheel slip.

**`apply_noise` implementation:**
```python
def apply_noise(self, state, step):
    state.x += self._rng.normal(0, 0.01)
    state.y += self._rng.normal(0, 0.01)
    state.theta += self._rng.normal(0, 0.001)
    # Cumulative drift (random walk)
    self._drift_x += self._rng.normal(0, self._drift_rate)
    self._drift_y += self._rng.normal(0, self._drift_rate)
    state.x += self._drift_x
    state.y += self._drift_y
    return state
```

**`apply_failure` implementation:**
```python
def apply_failure(self, state, time):
    if not self._failure.active or time < self._failure.onset_time:
        return state
    progress = min(1.0, (time - self._failure.onset_time) / max(self._failure.ramp_duration, 1e-6))
    boosted_rate = 0.005 + progress * self._failure.severity * 0.05
    self._drift_rate = boosted_rate
    return state
```

**Why M1 is the anchor:** The anchor model should be the one least likely to
experience sudden, large-scale failures. IMU+odometry degrades gracefully
(linear drift) rather than catastrophically (GPS jumps, camera blackout). Its
failure mode produces linearly growing disagreement — which BCVF ignores by
design (2nd-order is zero for linear drift). This means the anchor's own slow
degradation does not contaminate the BCVF cost signal.

**Estimated size:** ~80 lines.

#### 2.3.3 `predictors/lidar_slam.py` — M2

**V3.1 reference:** Appendix E.2 Model M2

**Sensor basis:** LiDAR point cloud

**Nominal noise profile:**
- Position noise: N(0, 0.02) meters per step
- Heading noise: N(0, 0.005) radians per step
- No cumulative drift (SLAM loop closure corrects drift)

**Characteristic failure mode:** Degrades in glass/reflective surfaces, rain,
and fog. LiDAR returns pass through glass or scatter in rain, causing the SLAM
algorithm to lose tracking or register false surfaces.

**Failure injection:** When active, position noise increases exponentially and
a systematic bias term grows quadratically (simulating the SLAM estimate
drifting as scan matching quality degrades).

**`apply_failure` implementation:**
```python
def apply_failure(self, state, time):
    if not self._failure.active or time < self._failure.onset_time:
        return state
    elapsed = time - self._failure.onset_time
    progress = min(1.0, elapsed / max(self._failure.ramp_duration, 1e-6))
    scale = progress * self._failure.severity

    # Noise inflation (scan matching uncertainty)
    noise_boost = 1.0 + scale * 10.0
    state.x += self._rng.normal(0, 0.02 * noise_boost)
    state.y += self._rng.normal(0, 0.02 * noise_boost)

    # Systematic drift (false surface registration)
    # Quadratic: simulates accelerating divergence
    state.x += scale * 0.5 * elapsed**2 * 0.01
    return state
```

**Key property:** The quadratic bias term produces _accelerating divergence_ —
exactly the signal that BCVF's second-order detector is designed to catch. This
is the primary scenario where BCVF should activate.

**Estimated size:** ~80 lines.

#### 2.3.4 `predictors/visual_odometry.py` — M3

**V3.1 reference:** Appendix E.2 Model M3

**Sensor basis:** RGB camera

**Nominal noise profile:**
- Position noise: N(0, 0.03) meters per step
- Heading noise: N(0, 0.008) radians per step
- Mild drift: 0.002 m/step (VO accumulates small errors without loop closure)

**Characteristic failure mode:** Fails in low light, texture-poor environments,
and during rapid motion (motion blur). Unlike LiDAR, camera failure is often
binary — tracking is either good or lost entirely.

**Failure injection:** When active, VO tracking quality degrades progressively.
Modeled as a two-phase process:
1. **Degradation phase** (severity 0-0.5): noise increases, small heading jumps
2. **Tracking loss phase** (severity 0.5-1.0): state estimate freezes (last
   known position) with random walk, simulating lost feature tracking

**`apply_failure` implementation:**
```python
def apply_failure(self, state, time):
    if not self._failure.active or time < self._failure.onset_time:
        return state
    elapsed = time - self._failure.onset_time
    progress = min(1.0, elapsed / max(self._failure.ramp_duration, 1e-6))
    scale = progress * self._failure.severity

    if scale < 0.5:
        # Degradation: increasing noise + occasional heading jumps
        noise_mult = 1.0 + scale * 8.0
        state.x += self._rng.normal(0, 0.03 * noise_mult)
        state.y += self._rng.normal(0, 0.03 * noise_mult)
        if self._rng.random() < scale * 0.1:
            state.theta += self._rng.normal(0, 0.2)  # heading jump
    else:
        # Tracking loss: freeze + random walk
        if self._frozen_state is None:
            self._frozen_state = PredictorState(
                x=state.x, y=state.y, theta=state.theta
            )
        state.x = self._frozen_state.x + self._rng.normal(0, 0.1)
        state.y = self._frozen_state.y + self._rng.normal(0, 0.1)
        state.theta = self._frozen_state.theta
    return state
```

**Key property:** The heading jumps in the degradation phase create sudden
changes in disagreement velocity, which produce acceleration spikes that BCVF
detects. The tracking loss phase creates growing position error that accelerates
as the true vehicle moves away from the frozen estimate.

**Estimated size:** ~80 lines.

#### 2.3.5 `predictors/gnss_map.py` — M4

**V3.1 reference:** Appendix E.2 Model M4

**Sensor basis:** GPS receiver + HD map

**Nominal noise profile:**
- Position noise: N(0, 0.5) meters per step (GPS is inherently noisier)
- Heading noise: N(0, 0.01) radians per step (derived from velocity vector)
- No cumulative drift (absolute reference)

**Characteristic failure mode:** GPS multipath in urban canyons and outdated
maps. Multipath causes position jumps of 2-5m with increasing frequency. Map
errors cause systematic position offset when the road layout has changed.

**Failure injection:** Two sub-modes controlled by a `failure_type` field:

**Mode A — GPS multipath:**
```python
def _apply_multipath(self, state, elapsed, scale):
    # Increasing frequency of position jumps
    jump_probability = scale * 0.3  # up to 30% of steps
    if self._rng.random() < jump_probability:
        jump_magnitude = 2.0 + self._rng.exponential(scale * 3.0)
        jump_angle = self._rng.uniform(0, 2 * np.pi)
        state.x += jump_magnitude * np.cos(jump_angle)
        state.y += jump_magnitude * np.sin(jump_angle)
    return state
```

**Mode B — Map error (construction zone):**
```python
def _apply_map_error(self, state, elapsed, scale):
    # Road layout differs from map: systematic lateral offset
    # that grows as vehicle proceeds into the changed area
    lateral_offset = scale * elapsed * 0.5  # meters
    # Offset is perpendicular to heading
    state.x += lateral_offset * np.cos(state.theta + np.pi/2)
    state.y += lateral_offset * np.sin(state.theta + np.pi/2)
    return state
```

**Key property:** GPS multipath produces _discrete jumps_ in disagreement — the
second difference operator sees these as large acceleration spikes at the jump
boundaries. Map error produces _smoothly accelerating_ lateral divergence. Both
trigger BCVF, but through different acceleration patterns.

**Estimated size:** ~80 lines.

### 2.4 Predictor Factory

A simple factory function in `predictors/__init__.py` creates the standard set:

```python
def create_predictor_set(
    bicycle_config: Optional[BicycleConfig] = None,
    seed: int = 42,
) -> Dict[str, BasePredictor]:
    """Create the standard 4-predictor set for SE(2) ground vehicle."""
    return {
        "M1": IMUOdometry(bicycle_config, seed=seed),
        "M2": LidarSLAM(bicycle_config, seed=seed + 1),
        "M3": VisualOdometry(bicycle_config, seed=seed + 2),
        "M4": GNSSMap(bicycle_config, seed=seed + 3),
    }
```

**Seeding:** Each predictor gets a deterministic RNG seeded from the base seed.
This ensures reproducible failure trajectories across experiment runs.

### 2.5 Integration with Phase 1

Phase 2 output plugs directly into Phase 1 input. The contract is:

```python
# Phase 2 produces:
control_sequence = np.array(...)        # (H, 2) — velocity + steering
trajectories = [
    predictors["M1"].predict(control_sequence),  # (H, 3)
    predictors["M2"].predict(control_sequence),  # (H, 3)
    predictors["M3"].predict(control_sequence),  # (H, 3)
    predictors["M4"].predict(control_sequence),  # (H, 3)
]

# Phase 1 consumes:
result = compute_bcvf_cost(trajectories, bcvf_config)
```

No adapters, no type conversion. Predictor output shape (H, 3) matches
`compute_bcvf_cost` input shape (H, 3) directly.

### 2.6 Test Specification

Tests go in `bcvf_autonomous/tests/test_predictors.py`.

#### 2.6.1 Bicycle Model Tests

| Test                                  | What It Validates                                                    |
|---------------------------------------|----------------------------------------------------------------------|
| `test_bicycle_straight_line`          | Zero steering + constant velocity -> straight-line trajectory        |
| `test_bicycle_constant_turn`          | Constant steering -> circular arc (check radius = L_wb / tan(delta)) |
| `test_bicycle_zero_velocity`          | Zero velocity -> stationary regardless of steering                   |
| `test_bicycle_clamps_velocity`        | Velocity above max is clamped                                        |
| `test_bicycle_clamps_steering`        | Steering above max is clamped                                        |
| `test_bicycle_reverse`                | Negative velocity -> backward motion                                 |

#### 2.6.2 Nominal Agreement Tests

| Test                                  | What It Validates                                                    |
|---------------------------------------|----------------------------------------------------------------------|
| `test_nominal_trajectories_close`     | All 4 predictors produce similar trajectories in nominal mode (no failure). Max pairwise disagreement < 2m over H=50 steps. |
| `test_nominal_bcvf_low`               | BCVF cost across all 4 nominal trajectories is near zero (gate suppresses noise-floor disagreement). |
| `test_predictor_determinism`          | Same seed -> same trajectory (reproducibility)                       |

#### 2.6.3 Failure Divergence Tests

| Test                                  | What It Validates                                                    |
|---------------------------------------|----------------------------------------------------------------------|
| `test_lidar_failure_accelerating`     | M2 with glass-corridor failure: disagreement vs M1 grows quadratically. Fit a quadratic to e(k) and verify R^2 > 0.9. |
| `test_vo_tracking_loss`              | M3 with tracking-loss failure: state freezes, growing displacement from true position.  |
| `test_gps_multipath_jumps`           | M4 with multipath: position jumps of 2-5m appear with increasing frequency. Count jumps > 2m.  |
| `test_gps_map_error_lateral`         | M4 with map error: systematic lateral offset grows over time.        |
| `test_imu_drift_linear`              | M1 accelerated drift: disagreement grows linearly (not quadratically). Important: BCVF should produce near-zero cost for this because acceleration of linear drift is zero.  |

#### 2.6.4 Integration Test with Phase 1

| Test                                  | What It Validates                                                    |
|---------------------------------------|----------------------------------------------------------------------|
| `test_nominal_all_predictors_bcvf_zero` | Create all 4 predictors in nominal mode, generate trajectories for a straight-line control sequence, pass to `compute_bcvf_cost`. Assert cost < epsilon. |
| `test_lidar_failure_bcvf_positive`   | Create predictors, inject LiDAR failure at t=2s, generate trajectories, assert `compute_bcvf_cost` > 0. |
| `test_failure_vs_nominal_ordering`   | BCVF cost with LiDAR failure > BCVF cost nominal (directional check). |

### 2.7 Design Constraints

1. **No planner dependency.** Predictors accept raw control sequences as (H, 2)
   arrays. They do not know about MPPI, J_perf, or planning costs.

2. **No simulator dependency.** Predictors do not interact with an environment.
   They forward-simulate from their internal state estimate. The simulation loop
   that feeds ground truth into `update_state()` is a Phase 3 concern.

3. **Deterministic by default.** All randomness flows through `numpy.random.Generator`
   instances seeded at construction. Same seed -> same trajectories.

4. **Failure is injectable, not automatic.** Predictors start in nominal mode.
   Failures are activated by calling `set_failure(FailureConfig(...))`. This
   separates the predictor mechanics from the scenario definitions (Phase 4).

5. **No internal state mutation during predict.** `predict()` returns a trajectory
   without changing the predictor's state. Only `update_state()` advances the
   internal estimate. This allows MPPI to call `predict()` on K candidate
   control sequences without corrupting the predictor's state between rollouts.

### 2.8 Acceptance Criteria

Phase 2 is complete when:

- [ ] `base.py` implements `BasePredictor` with `bicycle_step` and `predict`
- [ ] All 4 predictor implementations pass their nominal and failure tests
- [ ] Bicycle model tests verify straight-line, circular arc, clamping
- [ ] Nominal agreement test: all 4 predictors within 2m over H=50 steps
- [ ] LiDAR failure produces quadratic divergence (R^2 > 0.9 on quadratic fit)
- [ ] Integration test: nominal trajectories -> near-zero BCVF cost
- [ ] Integration test: LiDAR failure -> positive BCVF cost
- [ ] IMU drift failure -> near-zero BCVF cost (Lemma 1 invariance)
- [ ] `predict()` does not mutate predictor internal state
- [ ] All predictors are deterministic given the same seed

### 2.9 What Phase 2 Does NOT Build

- Simulation environment or time-stepping loop (Phase 3)
- Control sequence generation or sampling (Phase 3)
- Scenario orchestration or failure timing (Phase 4)
- Real sensor interfaces or ROS2 integration (out of V1 scope)
- Predictor health monitoring or automatic anchor selection (V2)

---

## Phase 3 — MPPI Planner Integration

Phase 3 is the largest phase. It connects the math kernel (Phase 1) to the
predictor framework (Phase 2) through an MPPI planner, and wraps the whole
system in a lightweight simulation environment. This plan is split into three
sub-sections to manage scope:

- **3A** — Simulator and environment (this section)
- **3B** — MPPI planner with J_perf + J_BCVF (next)
- **3C** — Planning loop, config loading, timing validation (next)

---

### 3A — Simulator and Environment

#### 3A.1 Purpose

Build a lightweight 2D simulation environment that:
1. Maintains ground-truth vehicle state
2. Steps the vehicle forward using the kinematic bicycle model
3. Feeds ground truth (with per-predictor noise) to the predictor set
4. Provides a lane/road geometry for the performance cost J_perf
5. Supports obstacle placement for collision cost
6. Records full state history for metrics (Phase 4)

This is NOT a production simulator. It is ~200 lines of deterministic,
NumPy-only code that provides the closed-loop test bed for BCVF.

#### 3A.2 Module

**File:** `bcvf_autonomous/simulator.py`

#### 3A.3 Types

```python
@dataclass
class Road:
    """Simple road geometry for J_perf computation."""
    centerline: np.ndarray      # (N, 2) waypoints [x, y] defining lane center
    width: float = 3.5          # lane width in meters
    speed_limit: float = 10.0   # m/s

@dataclass
class Obstacle:
    """Static circular obstacle."""
    x: float
    y: float
    radius: float = 1.0

@dataclass
class SimConfig:
    """Simulator configuration."""
    dt: float = 0.1                  # time step (matches planner dt)
    max_steps: int = 200             # 20 seconds at dt=0.1
    bicycle: BicycleConfig = field(default_factory=BicycleConfig)
    road: Road = field(default_factory=Road)
    obstacles: List[Obstacle] = field(default_factory=list)
    seed: int = 42

@dataclass
class SimState:
    """Complete simulation state at one time step."""
    step: int
    time: float
    ground_truth: PredictorState    # true vehicle pose + velocity
    predictor_states: Dict[str, PredictorState]  # each predictor's estimate
    applied_control: np.ndarray     # [velocity, steering] actually applied
    bcvf_cost: float = 0.0         # J_BCVF for the chosen control
    perf_cost: float = 0.0         # J_perf for the chosen control
    total_cost: float = 0.0        # J_perf + lambda_c * J_BCVF
    collision: bool = False
```

#### 3A.4 Simulator Class

```python
class Simulator:
    """
    Lightweight 2D ground-vehicle simulation environment.

    Responsibilities:
    - Owns the ground-truth vehicle state
    - Steps physics via kinematic bicycle model
    - Updates each predictor's state estimate (ground truth + noise)
    - Checks collision against obstacles
    - Records full history for post-hoc analysis
    """

    def __init__(self, config: SimConfig, predictors: Dict[str, BasePredictor]):
        ...

    def reset(self, initial_pose: Optional[PredictorState] = None) -> SimState:
        """Reset simulator and all predictors. Returns initial state."""
        ...

    def step(self, control: np.ndarray) -> SimState:
        """
        Advance one time step.

        Args:
            control: [velocity, steering] to apply

        Process:
        1. Apply control to ground-truth state via bicycle_step
        2. Check collision
        3. Update each predictor's state via predictor.update_state()
        4. Record and return SimState

        Returns:
            SimState with updated ground truth and predictor states
        """
        ...

    def get_history(self) -> List[SimState]:
        """Return full state history."""
        ...

    def is_done(self) -> bool:
        """True if max_steps reached or collision occurred."""
        ...
```

#### 3A.5 Road Geometry

For V1, roads are polylines — a sequence of (x, y) waypoints defining the lane
center. Three built-in road generators cover the needed scenarios:

```python
def make_straight_road(length: float = 200.0, spacing: float = 1.0) -> Road:
    """Straight road along x-axis. For nominal driving + GPS multipath."""
    ...

def make_curved_road(radius: float = 100.0, arc_degrees: float = 90.0) -> Road:
    """Constant-radius curve. For testing lateral dynamics."""
    ...

def make_urban_road(blocks: int = 4, block_size: float = 50.0) -> Road:
    """Grid-like urban road with turns. For GPS multipath scenarios."""
    ...
```

The performance cost J_perf (Section 3B) uses the road centerline to compute
lateral deviation and forward progress. The road does not need to be complex —
the interesting signal comes from the predictor failures, not the road geometry.

#### 3A.6 Collision Detection

Simple point-in-circle test against the obstacle list:

```python
def _check_collision(self, state: PredictorState) -> bool:
    for obs in self._config.obstacles:
        dx = state.x - obs.x
        dy = state.y - obs.y
        if dx*dx + dy*dy < obs.radius * obs.radius:
            return True
    return False
```

No swept-volume, no vehicle footprint. This is sufficient for V1 because
collision cost in J_perf uses a smooth distance-based penalty (not a binary
check), and the binary check here is only for episode termination.

#### 3A.7 Predictor State Update

Each simulation step, the simulator updates every predictor's internal state
estimate from ground truth:

```python
def _update_predictors(self, ground_truth: PredictorState, time: float):
    for name, predictor in self._predictors.items():
        predictor.update_state(ground_truth)
        # Failure injection is already configured on the predictor
        # via set_failure() — the predictor applies it internally
```

This is the only place where predictor internal state advances. Between
`update_state()` calls, `predict()` is called many times by MPPI (once per
rollout) without mutating state — per the Phase 2 design constraint.

#### 3A.8 State Recording

Every `step()` appends a `SimState` to an internal history list. This history
is the raw data source for Phase 4 metrics. No aggregation or analysis happens
in the simulator — it records, Phase 4 analyzes.

The history captures everything needed for post-hoc analysis:
- Ground truth trajectory (for path efficiency, collision timing)
- Per-predictor state estimates (for disagreement visualization)
- Applied controls (for comfort metrics — jerk, lateral acceleration)
- BCVF / J_perf costs (for cost curve analysis)
- Collision flag (for collision rate computation)

#### 3A.9 Design Constraints

1. **No planner dependency.** The simulator accepts control inputs via `step()`.
   It does not know about MPPI, J_perf, or BCVF. The planning loop (Section 3C)
   connects the planner to the simulator.

2. **Deterministic.** All randomness (noise in predictors, initial conditions)
   flows through seeded RNGs. Same config + same control sequence = same history.

3. **Real-time ratio irrelevant.** The simulator is not real-time. One `step()`
   call computes instantly. Clock time is `step * dt`, not wall time.

4. **Stateless road/obstacles.** Road geometry and obstacle positions are fixed
   at construction. Dynamic obstacles are a V2 concern.

#### 3A.10 Test Specification

Tests go in `bcvf_autonomous/tests/test_simulator.py`.

| Test                                   | What It Validates                                                   |
|----------------------------------------|---------------------------------------------------------------------|
| `test_straight_drive_no_collision`     | Drive straight on straight road with no obstacles -> no collision    |
| `test_collision_detection`             | Drive into an obstacle -> collision flag set, `is_done()` returns True |
| `test_predictor_states_updated`        | After `step()`, each predictor's internal state has advanced         |
| `test_history_length`                  | After N steps, `get_history()` has N+1 entries (initial + N steps)   |
| `test_deterministic_replay`            | Two simulators with same config + same controls produce identical histories |
| `test_road_centerline_geometry`        | `make_straight_road` produces waypoints along x-axis; `make_curved_road` produces arc |
| `test_reset_clears_state`             | After `reset()`, step count is 0, history is empty, predictors are reset |

#### 3A.11 Estimated Size

~200 lines for `simulator.py` including road generators and collision detection.

#### 3A.12 Acceptance Criteria for Sub-section 3A

- [ ] `simulator.py` implements `Simulator`, `SimConfig`, `SimState`, `Road`, `Obstacle`
- [ ] 3 road generators: straight, curved, urban
- [ ] Collision detection works for point-in-circle
- [ ] Predictor states advance each step
- [ ] Full history is recorded and retrievable
- [ ] Deterministic replay verified by test
- [ ] No imports from Phase 1 (`core.py`, `manifold.py`) — simulator is physics only

---

### 3B — MPPI Planner with J_perf + J_BCVF

#### 3B.1 Purpose

Build the MPPI (Model Predictive Path Integral) planner that selects control
sequences by minimizing:

```
J_total(u) = J_perf(u) + lambda_c * J_BCVF(u)
```

This is the module where Phase 1 and Phase 2 meet. The planner samples K
candidate control sequences, forward-simulates all M predictors for each
candidate, scores each candidate using both performance cost and BCVF coherence
cost, and returns the importance-weighted optimal control.

**V3.1 reference:** Section 3.5 (Definition 7), Appendix D (MPPI convergence),
Appendix D.6 (recommended configuration).

#### 3B.2 Module

**File:** `bcvf_autonomous/mppi_planner.py` (~300 lines)

#### 3B.3 MPPI Algorithm

MPPI is a sampling-based trajectory optimizer. It does not compute gradients —
it evaluates cost at K independently sampled control sequences and computes a
weighted average, where lower-cost rollouts receive higher weight.

**Algorithm per planning cycle:**

```
Input:  current predictor states, previous solution u_prev
Output: optimal control sequence u*

1. SAMPLE: Generate K candidate control sequences
   u_k = u_mean + epsilon_k,  epsilon_k ~ N(0, Sigma)
   where u_mean = shifted previous solution (warm start)

2. ROLLOUT: For each candidate k = 1..K:
   a. For each predictor m = 1..M:
      traj_m_k = predictor[m].predict(u_k)          # (H, 3)
   b. J_perf_k  = compute_perf_cost(traj_anchor_k, u_k, road)
   c. J_bcvf_k  = compute_bcvf_cost([traj_1_k, ..., traj_M_k], bcvf_config)
   d. J_total_k = J_perf_k + lambda_c * J_bcvf_k

3. WEIGHT: Compute importance weights
   w_k = exp(-J_total_k / temperature)
   W_k = w_k / sum(w_j)

4. UPDATE: Compute weighted mean
   u* = sum(W_k * u_k)

5. Return u*[0] as the control to execute (receding horizon)
   Save u* as u_prev for next cycle (warm start)
```

#### 3B.4 Types

```python
@dataclass
class MPPIConfig:
    """MPPI planner configuration."""
    # Sampling
    num_rollouts: int = 1000      # K
    horizon: int = 50             # H steps
    dt: float = 0.1               # seconds per step
    temperature: float = 5.0      # lambda (softmin sharpness)
    control_dim: int = 2          # [velocity, steering]

    # Noise distribution for sampling
    noise_std: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.15])
    )  # [velocity_std, steering_std]

    # Control limits
    velocity_bounds: Tuple[float, float] = (-2.0, 15.0)  # m/s
    steering_bounds: Tuple[float, float] = (-0.6, 0.6)   # rad

    # Warm start
    warm_start: bool = True

    # BCVF integration
    lambda_c: float = 1.0
    bcvf_config: BCVFConfig = field(default_factory=BCVFConfig)

@dataclass
class PerfCostConfig:
    """Performance cost J_perf configuration."""
    lane_deviation_weight: float = 1.0
    progress_weight: float = 0.5
    control_smoothness_weight: float = 0.1
    collision_weight: float = 1000.0
    collision_margin: float = 3.0     # meters: soft penalty starts here

@dataclass
class MPPIResult:
    """Result of one MPPI planning cycle."""
    optimal_control: np.ndarray       # (H, 2) full sequence
    first_control: np.ndarray         # (2,) control to execute now
    total_cost: float                 # J_total of the weighted mean
    perf_cost: float                  # J_perf component
    bcvf_cost: float                  # J_BCVF component
    solve_time_ms: float              # wall-clock time for this cycle
    effective_samples: float          # 1/sum(W_k^2), measures weight concentration
```

#### 3B.5 Performance Cost J_perf

J_perf is deliberately kept simple. The interesting signal comes from J_BCVF,
not from a sophisticated baseline planner. J_perf provides just enough
structure for the vehicle to follow a road and avoid obstacles.

```python
def compute_perf_cost(
    trajectory: np.ndarray,          # (H, 3) from anchor predictor
    control_sequence: np.ndarray,    # (H, 2)
    road: Road,
    obstacles: List[Obstacle],
    config: PerfCostConfig,
) -> float:
```

**Cost terms:**

**1. Lane deviation** (keeps vehicle on the road):
```
For each step k:
    d_k = perpendicular distance from trajectory[k] to nearest road segment
    cost += lane_deviation_weight * d_k^2
```

Finding the nearest road segment: project the vehicle position onto each
consecutive segment of `road.centerline`, keep the minimum distance. This is
O(H * N_segments) but N_segments is small for V1 roads.

**2. Progress** (rewards forward motion toward goal):
```
progress = arc-length distance along road from start to projection of final pose
cost -= progress_weight * progress
```

Negative cost = reward. The planner prefers control sequences that move the
vehicle further along the road.

**3. Control smoothness** (penalizes jerk for comfort):
```
For each step k = 1..H-1:
    du = control[k] - control[k-1]
    cost += control_smoothness_weight * ||du||^2
```

This is a first-difference penalty on control inputs, not a jerk penalty on
state. It keeps the MPPI sampling distribution smooth.

**4. Collision proximity** (soft penalty near obstacles):
```
For each step k, for each obstacle:
    dist = ||trajectory[k, :2] - obstacle.center|| - obstacle.radius
    if dist < collision_margin:
        cost += collision_weight * (1 - dist / collision_margin)^2
```

This is a smooth quadratic penalty that activates inside `collision_margin`
meters of any obstacle surface. It does not replace the binary collision check
in the simulator — that terminates the episode. This penalty steers the planner
away from obstacles before collision occurs.

**Which trajectory for J_perf?** The anchor predictor's trajectory
(`traj_anchor_k`). The performance cost evaluates the plan against one model's
prediction of reality. BCVF evaluates how much the other models disagree
with that prediction. This separation is intentional — J_perf says "is this a
good plan assuming M1 is right?" and J_BCVF says "do the other models agree
that M1 is right?"

#### 3B.6 MPPI Planner Class

```python
class MPPIPlanner:
    """
    Model Predictive Path Integral planner with BCVF coherence cost.

    Implements V3.1 Definition 7:
        u* = argmin_u [J_perf(u) + lambda_c * J_BCVF(u)]

    Uses importance-weighted sampling (no gradients).
    """

    def __init__(
        self,
        mppi_config: MPPIConfig,
        perf_config: PerfCostConfig,
        predictors: Dict[str, BasePredictor],
        road: Road,
        obstacles: List[Obstacle],
    ):
        ...

    def plan(self) -> MPPIResult:
        """
        Run one MPPI planning cycle.

        Returns optimal control sequence and diagnostics.
        """
        ...

    def _sample_controls(self) -> np.ndarray:
        """
        Sample K candidate control sequences.

        Returns: (K, H, 2) array

        Sampling distribution:
            u_k[h] = u_mean[h] + N(0, noise_std)
            clamped to [velocity_bounds, steering_bounds]

        u_mean is the warm-started previous solution (shifted by 1 step,
        last step duplicated) or zeros if no previous solution.
        """
        ...

    def _rollout_all(self, controls_batch: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Forward-simulate all predictors for all K candidates.

        Args:
            controls_batch: (K, H, 2)

        Returns:
            perf_costs: (K,) — J_perf for each candidate
            bcvf_costs: (K,) — J_BCVF for each candidate

        Implementation:
            For each k in K:
                trajs = [predictor.predict(controls_batch[k]) for predictor in predictors]
                perf_costs[k] = compute_perf_cost(trajs[anchor], controls_batch[k], ...)
                bcvf_costs[k] = compute_bcvf_cost(trajs, bcvf_config).total_cost
        """
        ...

    def _compute_weights(self, total_costs: np.ndarray) -> np.ndarray:
        """
        Compute normalized importance weights.

        w_k = exp(-(J_total_k - min(J_total)) / temperature)
        W_k = w_k / sum(w_k)

        The min-subtraction prevents numerical underflow when costs are large.
        """
        ...

    def _weighted_mean(self, controls_batch: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """
        Compute weighted mean control sequence.

        u* = sum_k(W_k * u_k)  — shape (H, 2)
        """
        ...

    def reset(self) -> None:
        """Clear warm-start state."""
        ...
```

#### 3B.7 Vectorization Strategy

The inner loop — K rollouts, each with M predictor forward-simulations — is the
performance bottleneck. The budget from Phase 0 is K=1000, H=50, M=4 (anchor
mode, 3 pairs), all in <20ms per planning cycle at 50Hz.

**Level 1 — Vectorize control sampling:**
`_sample_controls` generates the full (K, H, 2) noise tensor in one
`np.random.Generator.normal()` call, adds it to the (H, 2) mean, and clips.
No Python loop over K.

**Level 2 — Vectorize cost aggregation:**
`_compute_weights` and `_weighted_mean` are pure NumPy over (K,) arrays and
(K, H, 2) arrays. No Python loop.

**Level 3 — Batch BCVF scoring:**
Use `compute_bcvf_cost_batch` from Phase 1 (Section 1.2.2) to score all K
rollouts in a single call. The inner disagreement / acceleration / gate / Huber
chain is vectorized over K.

**Level 4 — Predictor rollouts (the bottleneck):**
Each predictor's `predict()` runs a sequential bicycle model simulation over H
steps — this cannot be vectorized across steps (each step depends on the
previous). However, it CAN be vectorized across K rollouts if the predictor
supports a batch interface.

For V1, the pragmatic approach:

```python
# Option A: Python loop over K (simple, correct, ~30ms for K=1000)
for k in range(K):
    for m, predictor in enumerate(predictors):
        trajs[k][m] = predictor.predict(controls_batch[k])

# Option B: Batch bicycle model (vectorize across K, loop over H)
# Requires BasePredictor.predict_batch(controls_batch: (K, H, 2)) -> (K, H, 3)
# Vectorizes the bicycle step across K rollouts at each time step
```

**Recommendation:** Implement Option A first. If the timing benchmark (Section
3C) fails the <20ms target, add `predict_batch()` to `BasePredictor` as Option
B. The bicycle step is 3 trig calls per step — at K=1000, H=50, M=4 that is
200K trig calls. NumPy vectorizes these to ~2ms for Option B vs ~15ms for
Option A. Option A is likely sufficient.

**Effective sample count:**

```python
effective_samples = 1.0 / np.sum(weights ** 2)
```

This diagnostic measures weight concentration. If effective_samples << K, the
temperature is too low (weights collapse to one rollout) or the cost landscape
has a very sharp minimum. Healthy range: effective_samples > K/10. Log this in
`MPPIResult` for tuning.

#### 3B.8 Warm Start

**V3.1 reference:** Appendix D.6 — "Critical for stability between planning
cycles."

At each planning cycle, the previous solution is shifted forward by one step:

```python
def _warm_start_mean(self) -> np.ndarray:
    if self._prev_solution is None:
        return np.zeros((self.config.horizon, self.config.control_dim))

    # Shift: drop first step, duplicate last step
    shifted = np.roll(self._prev_solution, -1, axis=0)
    shifted[-1] = shifted[-2]
    return shifted
```

This ensures the sampling distribution is centered on a reasonable control
sequence rather than zero. Without warm start, the first few planning cycles
after a scenario change waste most rollouts on irrelevant regions of control
space.

#### 3B.9 BCVF On/Off Switch

The planner must support running with `lambda_c = 0` (BCVF disabled) for
baseline comparison. When `lambda_c = 0`:
- Skip all non-anchor predictor rollouts (only M1 is needed for J_perf)
- Skip `compute_bcvf_cost_batch` entirely
- Report `bcvf_cost = 0.0` in `MPPIResult`

This is not just a performance optimization — it is the baseline condition (A0)
in the Phase 4 ablation protocol. The planner must produce identical J_perf
behavior regardless of whether BCVF is enabled, so the comparison is fair.

#### 3B.10 Ablation Variants

Phase 4 requires 0th-order and 1st-order ablation variants (V3.1 Section E.5).
Rather than building separate planners, support these via a `cost_order` field
on `BCVFConfig`:

```python
class CostOrder(Enum):
    ZEROTH = 0   # Penalize ||e_ij|| directly (disagreement magnitude)
    FIRST = 1    # Penalize ||v_ij|| (disagreement velocity)
    SECOND = 2   # Penalize ||a_ij|| (disagreement acceleration) — BCVF
```

When `cost_order` is ZEROTH or FIRST, `compute_bcvf_cost` substitutes the
corresponding quantity into the gate-penalty chain instead of the acceleration.
This reuses the same gate, Huber, and summation logic — only the input signal
changes. Implement this as a parameter on the Phase 1 `compute_bcvf_cost`
function, but specify it here because it affects planner configuration.

#### 3B.11 Test Specification

Tests go in `bcvf_autonomous/tests/test_mppi.py`.

| Test                                     | What It Validates                                                    |
|------------------------------------------|----------------------------------------------------------------------|
| `test_mppi_straight_road_tracks_lane`    | On straight road, no obstacles, no failures: vehicle follows lane center. Final lateral deviation < 1m. |
| `test_mppi_avoids_obstacle`              | Obstacle on road center: planner steers around it. No collision.     |
| `test_bcvf_zero_nominal`                | All predictors nominal: `MPPIResult.bcvf_cost` < epsilon.            |
| `test_bcvf_positive_under_failure`       | LiDAR failure injected: `MPPIResult.bcvf_cost` > 0.                 |
| `test_lambda_c_zero_skips_bcvf`          | With `lambda_c = 0`: only anchor predictor is rolled out, bcvf_cost = 0. |
| `test_warm_start_shift`                 | After one planning cycle, warm start mean is shifted previous solution. |
| `test_control_clamping`                  | Sampled controls respect velocity_bounds and steering_bounds.        |
| `test_weights_sum_to_one`               | Importance weights sum to 1.0 within floating-point tolerance.       |
| `test_effective_samples_healthy`         | With default temperature, effective_samples > K/10.                  |
| `test_perf_cost_rewards_progress`        | Control sequence with forward velocity scores lower J_perf than stationary. |
| `test_perf_cost_penalizes_deviation`     | Control sequence that drifts off-road scores higher J_perf.          |
| `test_ablation_zeroth_order`             | `cost_order=ZEROTH` penalizes constant bias (unlike BCVF 2nd-order). |
| `test_ablation_first_order`              | `cost_order=FIRST` penalizes linear drift (unlike BCVF 2nd-order).  |

#### 3B.12 Estimated Size

~300 lines for `mppi_planner.py` including `MPPIPlanner`, `compute_perf_cost`,
types, and ablation support.

#### 3B.13 Acceptance Criteria for Sub-section 3B

- [ ] `MPPIPlanner` implements sample, rollout, weight, update cycle
- [ ] `compute_perf_cost` implements lane deviation, progress, smoothness, collision
- [ ] Warm start shifts previous solution correctly
- [ ] `lambda_c = 0` skips BCVF rollouts and scoring
- [ ] Ablation variants (0th, 1st, 2nd order) configurable via `CostOrder` enum
- [ ] Vehicle tracks lane on straight road with no failures
- [ ] Vehicle avoids single obstacle on straight road
- [ ] BCVF cost is near-zero nominal, positive under failure
- [ ] Effective sample count is healthy (> K/10) at default temperature

---

### 3C — Planning Loop, Config Loading, and Timing Validation

#### 3C.1 Purpose

Phase 3C is the integration layer. It wires the simulator (3A), planner (3B),
predictors (Phase 2), and math kernel (Phase 1) into a single closed-loop
execution pipeline. It also adds config file loading so experiments can be
run from YAML without editing Python, and establishes the timing benchmark
that validates the 50Hz budget.

Phase 3C does NOT define scenarios or metrics — that is Phase 4. It provides
the machinery that Phase 4 drives.

#### 3C.2 Modules

Two concerns, two locations:

| File                          | Responsibility                                              | Est. Lines |
|-------------------------------|-------------------------------------------------------------|------------|
| `bcvf_autonomous/runner.py`   | Closed-loop planning loop + config loading                  | ~200       |
| `bcvf_autonomous/tests/test_runner.py` | Integration tests + timing benchmark              | ~150       |

#### 3C.3 The Planning Loop

The planning loop is the heartbeat of the system. Each iteration:

```
1. Planner observes predictor states (already updated by simulator)
2. Planner runs MPPI → returns MPPIResult
3. Simulator executes first_control → returns SimState
4. SimState is annotated with costs from MPPIResult
5. Repeat until done
```

```python
@dataclass
class RunConfig:
    """Complete configuration for one experiment run."""
    sim: SimConfig
    mppi: MPPIConfig
    perf: PerfCostConfig
    bcvf: BCVFConfig
    bicycle: BicycleConfig
    seed: int = 42
    # Failure injection (applied by Phase 4 scenarios, empty by default)
    failures: Dict[str, FailureConfig] = field(default_factory=dict)

@dataclass
class RunResult:
    """Complete output of one experiment run."""
    history: List[SimState]          # full time series
    collision: bool                  # did the vehicle collide?
    collision_step: Optional[int]    # when (if applicable)
    total_steps: int
    total_time: float                # simulated time (steps * dt)
    mean_perf_cost: float
    mean_bcvf_cost: float
    mean_solve_time_ms: float        # average planner wall-clock time
    max_solve_time_ms: float         # worst-case planner time
    p99_solve_time_ms: float         # 99th percentile
    effective_samples_mean: float    # average weight concentration

class Runner:
    """
    Closed-loop planning runner.

    Wires together: Simulator + MPPIPlanner + Predictors.
    """

    def __init__(self, config: RunConfig):
        ...

    def run(self) -> RunResult:
        """
        Execute one complete episode.

        Process:
        1. Build predictors from config
        2. Build simulator with predictors
        3. Build planner with predictors, road, obstacles
        4. Apply failure configs to predictors
        5. Reset simulator
        6. Loop: plan → step → record, until done
        7. Aggregate and return RunResult
        """
        ...
```

**`run()` implementation detail:**

```python
def run(self) -> RunResult:
    # 1. Build components
    predictors = create_predictor_set(self._config.bicycle, seed=self._config.seed)
    sim = Simulator(self._config.sim, predictors)
    planner = MPPIPlanner(
        self._config.mppi, self._config.perf,
        predictors, self._config.sim.road, self._config.sim.obstacles,
    )

    # 2. Inject failures
    for model_id, failure_cfg in self._config.failures.items():
        predictors[model_id].set_failure(failure_cfg)

    # 3. Reset
    sim_state = sim.reset()
    solve_times = []

    # 4. Closed loop
    while not sim.is_done():
        result = planner.plan()
        solve_times.append(result.solve_time_ms)

        sim_state = sim.step(result.first_control)

        # Annotate SimState with planner costs
        sim_state.bcvf_cost = result.bcvf_cost
        sim_state.perf_cost = result.perf_cost
        sim_state.total_cost = result.total_cost

    # 5. Aggregate
    history = sim.get_history()
    return RunResult(
        history=history,
        collision=any(s.collision for s in history),
        collision_step=next((s.step for s in history if s.collision), None),
        total_steps=len(history) - 1,
        total_time=(len(history) - 1) * self._config.sim.dt,
        mean_perf_cost=np.mean([s.perf_cost for s in history[1:]]),
        mean_bcvf_cost=np.mean([s.bcvf_cost for s in history[1:]]),
        mean_solve_time_ms=np.mean(solve_times),
        max_solve_time_ms=np.max(solve_times),
        p99_solve_time_ms=np.percentile(solve_times, 99),
        effective_samples_mean=np.mean([...]),  # from planner diagnostics
    )
```

**Failure injection timing:** The `FailureConfig.onset_time` field controls
when during the episode the failure activates. The runner does not manage this —
the predictor's `apply_failure()` checks the current simulation time against
`onset_time` internally (per Phase 2 spec). The runner just passes the
`FailureConfig` to each predictor at setup time.

#### 3C.4 Config Loading

Load `RunConfig` from the YAML file defined in Phase 0 (`default_se2.yaml`)
plus optional overrides.

```python
def load_config(
    config_path: str = "configs/bcvf_autonomous/default_se2.yaml",
    overrides: Optional[Dict[str, Any]] = None,
) -> RunConfig:
    """
    Load RunConfig from YAML with optional overrides.

    Overrides are dot-separated paths:
        {"mppi.num_rollouts": 500, "bcvf.lambda_c": 2.0}
    """
    ...
```

**Implementation:** Read YAML with `yaml.safe_load`, walk the nested dict to
populate dataclass fields. Apply overrides by splitting on `.` and setting the
nested field. This keeps the config surface flat for the Phase 4 sweep scripts.

**Dependency:** PyYAML. This is the only non-NumPy dependency in V1. It is
already present in the broader `symbolu` repo (used by existing config files
in `configs/`). If it is not installed, `load_config` raises `ImportError`
with a message; all other modules work without it.

**Override examples for Phase 4 sweeps:**

```python
# Lambda_c sweep
config = load_config(overrides={"bcvf.lambda_c": 5.0})

# Ablation: 0th-order
config = load_config(overrides={"bcvf.cost_order": "ZEROTH"})

# Reduce rollouts for fast iteration
config = load_config(overrides={"mppi.num_rollouts": 200})
```

#### 3C.5 Road and Obstacle Construction from Config

The YAML config specifies road type and obstacle positions. `load_config`
translates these into `Road` and `Obstacle` objects:

```yaml
# Added to default_se2.yaml for Phase 3C:
environment:
  road_type: straight         # straight | curved | urban
  road_length: 200.0          # meters (for straight)
  road_radius: 100.0          # meters (for curved)
  obstacles: []               # list of {x, y, radius}
```

```python
def _build_road(env_config: dict) -> Road:
    road_type = env_config.get("road_type", "straight")
    if road_type == "straight":
        return make_straight_road(env_config.get("road_length", 200.0))
    elif road_type == "curved":
        return make_curved_road(env_config.get("road_radius", 100.0))
    elif road_type == "urban":
        return make_urban_road()
    ...

def _build_obstacles(env_config: dict) -> List[Obstacle]:
    return [Obstacle(**obs) for obs in env_config.get("obstacles", [])]
```

#### 3C.6 Timing Validation

The timing benchmark validates the Phase 0 budget: one MPPI planning cycle must
complete in <20ms on a single CPU core at K=1000, H=50, M=4 with anchor
pairing.

**Why 20ms, not the 50Hz = 20ms total?** The planner is the dominant cost. The
simulator step, predictor state update, and bookkeeping are negligible (<1ms
combined). Allocating the full 20ms to the planner leaves margin for overhead.

**Benchmark approach:**

```python
def benchmark_planner(
    config: RunConfig,
    num_cycles: int = 100,
) -> Dict[str, float]:
    """
    Run num_cycles planning iterations and report timing statistics.

    Returns:
        {
            "mean_ms": float,
            "p50_ms": float,
            "p95_ms": float,
            "p99_ms": float,
            "max_ms": float,
            "within_budget": bool,   # p99 < 20ms
        }
    """
    ...
```

**What to measure:** Wall-clock time for `planner.plan()` only, excluding
simulator step and bookkeeping. Use `time.perf_counter()` for sub-millisecond
resolution.

**Timing breakdown (expected for K=1000, H=50, M=4 anchor, NumPy on modern
x86):**

| Component                                | Expected Time | Notes                               |
|------------------------------------------|---------------|--------------------------------------|
| Control sampling (K x H x 2)            | ~0.5ms        | One vectorized `normal()` call       |
| Predictor rollouts (K x M x H bicycle)  | ~12ms         | 200K bicycle steps (Option A loop)   |
| BCVF batch scoring (K x 3 pairs x H)    | ~3ms          | Vectorized disagreement + gate + Huber |
| J_perf batch scoring (K x H)            | ~1ms          | Lane projection + distance            |
| Weight computation + weighted mean       | ~0.5ms        | Pure NumPy over (K,) arrays          |
| **Total**                                | **~17ms**     | Within 20ms budget                   |

**If timing fails:** The primary lever is `predict_batch()` on `BasePredictor`
(Option B from Section 3B.7). Vectorizing the bicycle model across K rollouts
reduces the predictor rollout from ~12ms to ~2ms, bringing total to ~7ms. This
is the escalation path — implement Option B only if Option A exceeds budget.

**Secondary levers (V2, not V1):**
- Reduce K from 1000 to 500 (2x speedup, slight quality loss)
- JAX JIT compilation of the full planning cycle (~10x speedup)
- Reduce H from 50 to 30 (1.7x speedup, shorter prediction horizon)

#### 3C.7 Diagnostic Output

The runner produces structured diagnostic output for each episode, saved as
a Python dict (serializable to JSON). This is the interface between Phase 3
(execution) and Phase 4 (analysis).

```python
@dataclass
class EpisodeDiagnostics:
    """Structured diagnostics for one episode."""
    # Config snapshot
    config: Dict[str, Any]          # serialized RunConfig

    # Outcome
    collision: bool
    collision_step: Optional[int]
    total_steps: int

    # Time series (per step)
    ground_truth_trajectory: np.ndarray   # (T, 3) — [x, y, theta]
    predictor_trajectories: Dict[str, np.ndarray]  # model_id -> (T, 3)
    applied_controls: np.ndarray          # (T, 2) — [velocity, steering]
    bcvf_costs: np.ndarray                # (T,)
    perf_costs: np.ndarray                # (T,)
    total_costs: np.ndarray               # (T,)

    # Planner diagnostics (per step)
    solve_times_ms: np.ndarray            # (T,)
    effective_samples: np.ndarray         # (T,)

    # Aggregates
    mean_solve_time_ms: float
    p99_solve_time_ms: float
    path_length: float                    # total distance traveled
    path_efficiency: float                # path_length / road_length
    mean_lateral_deviation: float         # average distance from lane center
    rms_lateral_jerk: float               # comfort metric
```

**`path_efficiency`:** Ratio of actual path length to optimal (road centerline)
path length. A value of 1.0 means the vehicle followed the ideal path exactly.
Values > 1.0 indicate detours (obstacle avoidance, BCVF-induced conservatism).
Target from V3.1 Section 7.3: >= 0.95.

**`rms_lateral_jerk`:** Root-mean-square of the third derivative of lateral
position with respect to time. Computed from the ground-truth trajectory using
finite differences. This is the comfort metric from V3.1 Section 7.3 — BCVF
should not degrade ride comfort by more than 10% relative to baseline.

**Serialization:** `EpisodeDiagnostics` has a `to_dict()` method that converts
all numpy arrays to lists for JSON serialization. Phase 4 loads these dicts for
aggregation and plotting.

#### 3C.8 Config Update for Phase 3C

Add the `environment` section to `default_se2.yaml`:

```yaml
# --- Environment ---
environment:
  road_type: straight
  road_length: 200.0
  road_radius: 100.0          # used only for curved roads
  obstacles: []                # populated per-scenario in Phase 4
```

#### 3C.9 Test Specification

Tests go in `bcvf_autonomous/tests/test_runner.py`.

#### 3C.9.1 Integration Tests

| Test                                     | What It Validates                                                    |
|------------------------------------------|----------------------------------------------------------------------|
| `test_full_episode_completes`            | Runner executes a full episode (straight road, no failures, no obstacles) without error. Returns `RunResult` with `total_steps == max_steps`. |
| `test_episode_with_collision_terminates` | Obstacle placed on road center, no BCVF. Episode terminates early with `collision == True`. |
| `test_bcvf_prevents_collision`           | Same obstacle scenario but with BCVF enabled and LiDAR failure injected. Vehicle avoids collision (the BCVF signal steers the planner away from the failing model's prediction). |
| `test_config_loading`                    | `load_config("default_se2.yaml")` produces a valid `RunConfig` with expected default values. |
| `test_config_overrides`                  | `load_config(overrides={"bcvf.lambda_c": 5.0})` produces config with `lambda_c == 5.0`, all other values at defaults. |
| `test_config_dot_path_nested`            | Override with deep path `"mppi.noise_std"` correctly sets nested field. |
| `test_episode_diagnostics_shapes`        | `EpisodeDiagnostics` arrays have consistent shapes: all time-series arrays have length == total_steps. |
| `test_diagnostics_serializable`          | `diagnostics.to_dict()` produces a dict that survives `json.dumps` / `json.loads` round-trip. |
| `test_deterministic_episodes`            | Two `Runner` instances with same config produce identical `RunResult` (same collision, same path length, same cost time series). |
| `test_failure_onset_timing`              | Failure with `onset_time=5.0` produces zero BCVF cost before step 50 (5s / 0.1s) and positive cost after. |

#### 3C.9.2 Timing Benchmark

| Test                                     | What It Validates                                                    |
|------------------------------------------|----------------------------------------------------------------------|
| `test_planner_timing_budget`             | `benchmark_planner` with K=1000, H=50, M=4 anchor: p99 < 20ms. Mark as `@pytest.mark.slow` — skipped in normal test runs, run explicitly for performance validation. |
| `test_planner_timing_reduced`            | Same benchmark with K=200, H=30: p99 < 5ms. Runs in normal test suite as a fast sanity check that nothing is catastrophically slow. |

**pytest marker:** Timing tests are non-deterministic (depend on hardware).
Use `@pytest.mark.slow` for the full budget test so CI runs the fast variant
only. The full benchmark is run manually before milestone reviews.

#### 3C.10 Design Constraints

1. **Runner is stateless across episodes.** Each `run()` call creates fresh
   predictors, simulator, and planner from config. No state leaks between
   episodes. This is critical for the Phase 4 sweep protocol, which runs
   hundreds of episodes with varying parameters.

2. **Config is immutable during execution.** `RunConfig` is frozen after
   `load_config`. The runner does not modify config at runtime. Sweeps create
   new configs per run, they do not mutate a shared config.

3. **Diagnostics are comprehensive but raw.** The runner records everything;
   Phase 4 computes derived metrics (collision rate, early warning time,
   statistical tests). No analysis in the runner.

4. **No parallelism in V1.** Episodes run sequentially. The Phase 4 sweep
   of 7,000 episodes at ~10s each is ~20 hours sequential. Parallelism across
   episodes (multiprocessing) is a Phase 5 packaging concern, not a Phase 3
   concern. The stateless-runner design makes this trivially parallelizable
   when needed.

#### 3C.11 Acceptance Criteria for Sub-section 3C

- [ ] `runner.py` implements `Runner`, `RunConfig`, `RunResult`, `EpisodeDiagnostics`
- [ ] `load_config` reads `default_se2.yaml` and applies dot-path overrides
- [ ] Full episode completes on straight road with no errors
- [ ] Episode with obstacle terminates on collision
- [ ] BCVF-enabled episode avoids collision that baseline hits
- [ ] Failure onset timing is respected (zero BCVF cost before onset)
- [ ] `EpisodeDiagnostics.to_dict()` round-trips through JSON
- [ ] Deterministic replay: same config = same result
- [ ] Timing benchmark (K=200, H=30) passes p99 < 5ms in normal test suite
- [ ] Full timing benchmark (K=1000, H=50) passes p99 < 20ms (manual run)

#### 3C.12 Phase 3 Acceptance Criteria (All Sub-sections)

Phase 3 is complete when all of 3A, 3B, and 3C acceptance criteria are met,
plus the following end-to-end integration check:

- [ ] A single `Runner.run()` call on `default_se2.yaml` with no failures
  completes a 200-step episode, vehicle stays on road, no collision, BCVF
  cost near zero, solve time within budget
- [ ] Same run with `failures: {M2: {active: true, onset_time: 5.0, severity: 1.0}}`
  shows BCVF cost spike at t=5s and vehicle avoidance behavior
- [ ] `default_se2.yaml` updated with `environment` section

#### 3C.13 What Phase 3 Does NOT Build

- Scenario definitions (which failures, when, on which road) — Phase 4
- Statistical analysis, aggregation across runs, plots — Phase 4
- Sweep orchestration (lambda_c sweep, ablation matrix) — Phase 4
- CLI entry point (`run_experiments.py`) — Phase 4
- Packaging, demo notebooks, adapter interfaces — Phase 5

---

## Phase 4 — Scenario and Metrics Harness

Phase 4 is where the product becomes demonstrable. It defines the failure
scenarios, the metrics that measure BCVF's value, and the orchestration
machinery that runs sweeps and ablations at scale. This is the phase that
produces the evidence: does BCVF actually work?

This plan is split into three sub-sections:

- **4A** — Scenario definitions (this section)
- **4B** — Metrics and analysis (next)
- **4C** — Sweep orchestrator and CLI (next)

---

### 4A — Scenario Definitions

#### 4A.1 Purpose

Define a concrete set of failure scenarios that exercise BCVF's core properties:
bias tolerance, early warning of accelerating divergence, and action-conditional
cost shaping. Each scenario specifies a road geometry, obstacle layout, failure
injection (which predictor, when, what mode), and expected BCVF behavior.

Scenarios are data — they are not code. Each scenario is a `ScenarioConfig`
dataclass that the runner (Phase 3C) can execute without modification.

**V3.1 reference:** Appendix E.3-E.4 (scenario implementations), Section 7.2
(scenario design table).

#### 4A.2 Module

**File:** `bcvf_autonomous/scenarios.py` (~150 lines)

#### 4A.3 Types

```python
@dataclass
class ScenarioConfig:
    """Complete definition of one test scenario."""
    name: str                             # human-readable identifier
    description: str                      # what this scenario tests
    road_type: str = "straight"           # straight | curved | urban
    road_length: float = 200.0            # meters
    road_radius: float = 100.0            # for curved roads
    obstacles: List[Dict] = field(default_factory=list)  # [{x, y, radius}]
    failures: Dict[str, FailureConfig] = field(default_factory=dict)
    max_steps: int = 200                  # episode length
    initial_velocity: float = 8.0         # m/s starting speed

    # Expected behavior (for directional validation, not hard assertions)
    expect_bcvf_activation: bool = False  # should J_BCVF spike?
    expect_collision_baseline: bool = False  # would baseline (no BCVF) collide?
    expect_collision_bcvf: bool = False   # should BCVF-enabled vehicle collide?
```

#### 4A.4 Scenario Catalog

V3.1 Appendix E.3 defines 6 scenarios. Phase 0 scoped V1 to 4 initial
scenarios plus 2 added after the pipeline is working. This plan specifies all
6 upfront so the interface is stable; scenarios 5-6 are implemented last.

---

**Scenario S1 — Normal Driving (Control Case)**

```python
S1_NORMAL = ScenarioConfig(
    name="S1_normal_driving",
    description="Highway driving at 8 m/s, all sensors nominal. "
                "No failures, no obstacles. Measures false positive rate "
                "and baseline path efficiency.",
    road_type="straight",
    road_length=200.0,
    obstacles=[],
    failures={},
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=False,
    expect_collision_baseline=False,
    expect_collision_bcvf=False,
)
```

**Purpose:** Prove BCVF introduces zero overhead in normal operation. J_BCVF
should be near-zero at every step. Path efficiency should be >= 0.99. This is
the false-positive-rate measurement scenario.

**V3.1 reference:** Appendix E.3 Scenario 5.

---

**Scenario S2 — GPS Multipath (Urban Canyon)**

```python
S2_GPS_MULTIPATH = ScenarioConfig(
    name="S2_gps_multipath",
    description="Vehicle drives between tall buildings. GPS multipath causes "
                "M4 position jumps of 2-5m with increasing frequency. "
                "Other models unaffected.",
    road_type="straight",
    road_length=200.0,
    obstacles=[
        {"x": 100.0, "y": 3.0, "radius": 0.5},   # wall-like obstacle
    ],
    failures={
        "M4": FailureConfig(
            active=True,
            onset_time=3.0,       # failure begins at t=3s
            severity=0.8,
            ramp_duration=2.0,    # ramps over 2 seconds
        ),
    },
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,   # GPS-trusting planner swerves into wall
    expect_collision_bcvf=False,      # BCVF steers away from M4-consistent path
)
```

**Purpose:** GPS jumps create discrete spikes in disagreement acceleration.
BCVF should activate and steer the planner toward M1/M2/M3-consistent
trajectories, avoiding the wall that a GPS-trusting baseline would hit.

**V3.1 reference:** Appendix E.3 Scenario 2.

---

**Scenario S3 — Map Error (Construction Zone)**

```python
S3_MAP_ERROR = ScenarioConfig(
    name="S3_map_error",
    description="Road layout differs from HD map. M4 predicts road continues "
                "straight; M2/M3 perceive barriers. Systematic lateral offset "
                "grows as vehicle enters construction zone.",
    road_type="straight",
    road_length=200.0,
    obstacles=[
        {"x": 120.0, "y": 0.0, "radius": 1.5},  # construction barrier
        {"x": 130.0, "y": 0.5, "radius": 1.5},
        {"x": 140.0, "y": 1.0, "radius": 1.5},
    ],
    failures={
        "M4": FailureConfig(
            active=True,
            onset_time=5.0,
            severity=1.0,
            ramp_duration=5.0,    # gradual onset over 5 seconds
        ),
    },
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,   # map-trusting planner drives into barriers
    expect_collision_bcvf=False,
)
```

**Purpose:** Map error produces smoothly accelerating lateral divergence
between M4 and M1/M2/M3. BCVF detects the acceleration of disagreement before
the vehicle reaches the barriers.

**V3.1 reference:** Appendix E.3 Scenario 4.

---

**Scenario S4 — Gradual Camera Degradation (Rain/Fog)**

```python
S4_CAMERA_DEGRADATION = ScenarioConfig(
    name="S4_camera_degradation",
    description="Weather degrades progressively. M3 (visual odometry) tracking "
                "quality degrades over 10 seconds, eventually losing tracking. "
                "Other models unaffected. Tests graceful transition.",
    road_type="curved",
    road_length=200.0,
    road_radius=80.0,              # gentle curve to make VO failure visible
    obstacles=[],
    failures={
        "M3": FailureConfig(
            active=True,
            onset_time=2.0,
            severity=1.0,
            ramp_duration=10.0,   # slow degradation over 10 seconds
        ),
    },
    max_steps=200,
    initial_velocity=6.0,          # slower for curved road
    expect_bcvf_activation=True,
    expect_collision_baseline=False,  # no obstacles to hit
    expect_collision_bcvf=False,
)
```

**Purpose:** Tests BCVF's response to gradual failure. M3's degradation
produces increasing noise then tracking loss (Phase 2 two-phase failure model).
BCVF cost should rise smoothly as M3 diverges, demonstrating graceful detection
rather than a binary alarm. No collision expected because there are no
obstacles — the metric here is early warning time and smoothness of BCVF
activation.

**V3.1 reference:** Appendix E.3 Scenario 3.

---

**Scenario S5 — Constant Bias Validation (Lemma 1)**

```python
S5_CONSTANT_BIAS = ScenarioConfig(
    name="S5_constant_bias",
    description="Normal driving with M4 (GPS) injected with a constant 0.5m "
                "position bias throughout. Validates Lemma 1: constant "
                "disagreement produces zero BCVF cost. The critical "
                "invariance property that differentiates BCVF from "
                "0th-order methods.",
    road_type="straight",
    road_length=200.0,
    obstacles=[],
    failures={
        "M4": FailureConfig(
            active=True,
            onset_time=0.0,       # bias present from start
            severity=0.0,         # severity=0 with special bias_mode flag
            ramp_duration=0.0,
        ),
    },
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=False,  # constant bias -> a=0 -> J_BCVF=0
    expect_collision_baseline=False,
    expect_collision_bcvf=False,
)
```

**Implementation note for constant bias:** The standard `GNSSMap.apply_failure`
produces multipath jumps or map error (both non-constant). For S5, the
predictor needs a third failure sub-mode: **constant offset**. Add a
`failure_type` field to `GNSSMap` that selects between `multipath`, `map_error`,
and `constant_bias`. When `constant_bias` is active, apply a fixed 0.5m offset
to x position at every step, with no randomness and no growth.

```python
# In gnss_map.py:
def _apply_constant_bias(self, state, elapsed, scale):
    state.x += 0.5  # constant, no time-dependence
    return state
```

**Purpose:** This is the single most important validation scenario for BCVF's
novelty claim. It demonstrates the invariance property from V3.1 Lemma 1:
constant disagreement produces zero BCVF cost. The ablation comparison is
critical — 0th-order penalizes this (false positive), BCVF does not.

**V3.1 reference:** Appendix E.4 (constant bias validation).

---

**Scenario S6 — LiDAR Failure (Glass Corridor)**

```python
S6_GLASS_CORRIDOR = ScenarioConfig(
    name="S6_glass_corridor",
    description="Vehicle approaches a glass-walled corridor. M2 (LiDAR) state "
                "estimate drifts as LiDAR returns pass through glass. M1, M3, "
                "M4 remain consistent. Tests primary BCVF activation case.",
    road_type="straight",
    road_length=200.0,
    obstacles=[
        {"x": 130.0, "y": 2.5, "radius": 0.5},  # glass wall (invisible to LiDAR)
    ],
    failures={
        "M2": FailureConfig(
            active=True,
            onset_time=5.0,
            severity=1.0,
            ramp_duration=3.0,
        ),
    },
    max_steps=200,
    initial_velocity=8.0,
    expect_bcvf_activation=True,
    expect_collision_baseline=True,   # LiDAR-trusting planner enters corridor
    expect_collision_bcvf=False,
)
```

**Purpose:** The canonical BCVF scenario. LiDAR failure produces quadratic
divergence (Phase 2 design), which is exactly the signal BCVF's second-order
detector targets. Demonstrates early warning — BCVF cost spikes before the
vehicle reaches the glass wall.

**V3.1 reference:** Appendix E.3 Scenario 1.

---

#### 4A.5 Scenario Registry

A simple dictionary providing programmatic access to all scenarios:

```python
SCENARIOS: Dict[str, ScenarioConfig] = {
    "S1_normal_driving": S1_NORMAL,
    "S2_gps_multipath": S2_GPS_MULTIPATH,
    "S3_map_error": S3_MAP_ERROR,
    "S4_camera_degradation": S4_CAMERA_DEGRADATION,
    "S5_constant_bias": S5_CONSTANT_BIAS,
    "S6_glass_corridor": S6_GLASS_CORRIDOR,
}

def get_scenario(name: str) -> ScenarioConfig:
    """Look up scenario by name. Raises KeyError if not found."""
    return SCENARIOS[name]

def list_scenarios() -> List[str]:
    """Return all scenario names."""
    return list(SCENARIOS.keys())
```

#### 4A.6 Scenario-to-RunConfig Translation

Each scenario must be translated into a `RunConfig` that the runner can
execute. This is a pure function — no side effects:

```python
def scenario_to_run_config(
    scenario: ScenarioConfig,
    bcvf_config: BCVFConfig,
    mppi_config: MPPIConfig,
    perf_config: PerfCostConfig,
    bicycle_config: BicycleConfig,
    seed: int = 42,
) -> RunConfig:
    """
    Convert a ScenarioConfig into a RunConfig.

    The scenario provides: road, obstacles, failures, episode length.
    The caller provides: BCVF/MPPI/perf/bicycle tuning parameters.

    This separation is intentional — the same scenario can be run with
    different lambda_c values, different ablation orders, or different
    rollout counts, producing different RunConfigs from the same scenario.
    """
    road = _build_road_from_scenario(scenario)
    obstacles = [Obstacle(**o) for o in scenario.obstacles]

    return RunConfig(
        sim=SimConfig(
            dt=mppi_config.dt,
            max_steps=scenario.max_steps,
            bicycle=bicycle_config,
            road=road,
            obstacles=obstacles,
            seed=seed,
        ),
        mppi=mppi_config,
        perf=perf_config,
        bcvf=bcvf_config,
        bicycle=bicycle_config,
        seed=seed,
        failures=scenario.failures,
    )
```

**Why separate scenario from tuning?** The Phase 4 sweep matrix runs each
scenario across 9 lambda_c values and 4 ablation orders. If the scenario
contained tuning parameters, there would be 6 * 9 * 4 = 216 scenario objects.
By separating them, there are 6 scenarios and the sweep constructs 216
RunConfigs programmatically.

#### 4A.7 GNSSMap Predictor Update

Phase 4A requires a minor addition to the Phase 2 `gnss_map.py` predictor: a
`constant_bias` failure sub-mode for scenario S5. This is the only Phase 2
modification required by Phase 4.

```python
class GNSSFailureType(Enum):
    MULTIPATH = "multipath"
    MAP_ERROR = "map_error"
    CONSTANT_BIAS = "constant_bias"
```

The `FailureConfig` dataclass gains an optional `failure_type: str` field that
defaults to `"multipath"`. This is backwards-compatible — existing tests that
do not specify `failure_type` continue to use multipath.

#### 4A.8 Test Specification

Tests go in `bcvf_autonomous/tests/test_scenarios.py`.

| Test                                   | What It Validates                                                      |
|----------------------------------------|------------------------------------------------------------------------|
| `test_all_scenarios_loadable`          | Every entry in `SCENARIOS` produces a valid `ScenarioConfig`           |
| `test_scenario_to_run_config`          | `scenario_to_run_config` produces a `RunConfig` with correct road type, obstacles, and failures |
| `test_s1_no_failures`                  | S1_NORMAL has empty failures dict                                      |
| `test_s2_m4_failure`                   | S2_GPS_MULTIPATH has M4 failure with onset_time=3.0                    |
| `test_s5_constant_bias_flag`           | S5 failure config has `failure_type="constant_bias"`                   |
| `test_scenario_registry_complete`      | `list_scenarios()` returns 6 entries, all unique                       |
| `test_scenario_separation`             | Same scenario with two different lambda_c values produces two distinct RunConfigs with different bcvf_config |

#### 4A.9 Acceptance Criteria for Sub-section 4A

- [ ] `scenarios.py` defines all 6 scenarios as `ScenarioConfig` instances
- [ ] `SCENARIOS` registry provides programmatic access
- [ ] `scenario_to_run_config` translates scenario + tuning into `RunConfig`
- [ ] `GNSSMap` predictor extended with `constant_bias` failure sub-mode
- [ ] All tests pass
- [ ] Scenarios are data only — no execution logic in `scenarios.py`

---

### 4B — Metrics and Analysis

#### 4B.1 Purpose

Define the metrics that answer "does BCVF work?" and build the analysis
functions that compute them from `EpisodeDiagnostics` (Phase 3C). Metrics fall
into two categories:

1. **Per-episode metrics** — computed from a single run (e.g., did it collide?
   what was the path efficiency?)
2. **Aggregate metrics** — computed across N runs of the same configuration
   (e.g., collision rate with 95% confidence interval, mean early warning time)

Phase 4B builds the functions. Phase 4C calls them across the sweep matrix.

**V3.1 reference:** Section 7.3 (metrics table), Appendix E.7 (metrics
collection).

#### 4B.2 Module

**File:** `bcvf_autonomous/metrics.py` (~200 lines)

#### 4B.3 Per-Episode Metrics

These functions accept a single `EpisodeDiagnostics` and return a scalar or
small dict.

```python
@dataclass
class EpisodeMetrics:
    """All metrics computed from a single episode."""
    # Safety
    collision: bool
    collision_step: Optional[int]
    collision_time: Optional[float]            # collision_step * dt

    # Early warning
    early_warning_time: Optional[float]        # seconds before would-be collision
    first_bcvf_activation_step: Optional[int]  # first step where J_BCVF > threshold
    first_bcvf_activation_time: Optional[float]

    # Efficiency
    path_length: float                         # total distance traveled (meters)
    road_length: float                         # optimal distance (road centerline)
    path_efficiency: float                     # path_length / road_length (target >= 0.95)

    # Comfort
    rms_lateral_jerk: float                    # m/s^3
    rms_steering_rate: float                   # rad/s
    max_lateral_acceleration: float            # m/s^2

    # BCVF behavior
    mean_bcvf_cost: float
    max_bcvf_cost: float
    bcvf_activation_rate: float                # fraction of steps with J_BCVF > threshold
    mean_perf_cost: float

    # Planner health
    mean_solve_time_ms: float
    p99_solve_time_ms: float
    mean_effective_samples: float

def compute_episode_metrics(
    diagnostics: EpisodeDiagnostics,
    bcvf_activation_threshold: float = 0.01,
) -> EpisodeMetrics:
    """Compute all per-episode metrics from diagnostics."""
    ...
```

**Metric computation details:**

---

**Early warning time** (V3.1 Section 7.3: target >= 2 seconds)

The time between BCVF first activating and the vehicle reaching the point where
baseline (no BCVF) would have collided. This requires comparing against a
baseline run.

```python
def compute_early_warning_time(
    bcvf_diagnostics: EpisodeDiagnostics,
    baseline_diagnostics: EpisodeDiagnostics,
    bcvf_activation_threshold: float = 0.01,
) -> Optional[float]:
    """
    Compute early warning time.

    Args:
        bcvf_diagnostics: episode run WITH BCVF enabled
        baseline_diagnostics: same scenario run WITHOUT BCVF (lambda_c=0)

    Returns:
        Seconds between first BCVF activation and baseline collision time.
        None if baseline did not collide (no warning needed).
    """
    if not baseline_diagnostics.collision:
        return None  # baseline didn't collide, no warning to measure

    baseline_collision_time = baseline_diagnostics.collision_step * dt

    # Find first BCVF activation
    activation_steps = np.where(
        bcvf_diagnostics.bcvf_costs > bcvf_activation_threshold
    )[0]
    if len(activation_steps) == 0:
        return None  # BCVF never activated (missed detection)

    first_activation_time = activation_steps[0] * dt
    return baseline_collision_time - first_activation_time
```

**Why this needs a baseline run:** Early warning time is defined relative to
when a collision _would have happened_ without BCVF. The BCVF-enabled run
avoids the collision (ideally), so there is no collision time in that run to
reference. The baseline provides the counterfactual.

---

**Path efficiency** (V3.1 Section 7.3: target >= 0.95)

```python
def _compute_path_length(trajectory: np.ndarray) -> float:
    """Sum of Euclidean distances between consecutive poses."""
    diffs = np.diff(trajectory[:, :2], axis=0)
    return float(np.sum(np.linalg.norm(diffs, axis=1)))

def _compute_road_length(road_centerline: np.ndarray) -> float:
    """Arc length of the road centerline."""
    diffs = np.diff(road_centerline, axis=0)
    return float(np.sum(np.linalg.norm(diffs, axis=1)))
```

Path efficiency = `road_length / path_length`. Note the inversion from V3.1:
the document says "path_length / optimal_path_length" but since the vehicle
may take a longer path (detour around obstacle), this ratio can exceed 1.0.
We use `road_length / path_length` so the metric is in [0, 1] with 1.0 being
optimal. Values below 0.95 indicate excessive conservatism.

**Correction:** Actually V3.1 uses `path_length / optimal_path_length` where
values >= 1.0 mean detours. Both conventions work. We use the V3.1 convention
to match the document. Target: ratio <= 1.05 (path at most 5% longer than
optimal).

---

**Comfort metrics** (V3.1 Section 7.3: impact <= 10%)

Three comfort metrics, all computed from the ground-truth trajectory using
finite differences:

```python
def _compute_lateral_jerk(trajectory: np.ndarray, dt: float) -> float:
    """
    RMS of the third derivative of lateral position.

    Lateral position = perpendicular distance from road centerline at each step.
    Jerk = d^3(lateral) / dt^3, approximated by third-order finite difference.
    """
    # Compute lateral positions (requires road centerline)
    # Third finite difference: j[k] = (lat[k+3] - 3*lat[k+2] + 3*lat[k+1] - lat[k]) / dt^3
    ...

def _compute_steering_rate(controls: np.ndarray, dt: float) -> float:
    """RMS of steering angle rate of change."""
    steering = controls[:, 1]  # column 1 is steering
    steering_rate = np.diff(steering) / dt
    return float(np.sqrt(np.mean(steering_rate ** 2)))

def _compute_max_lateral_accel(trajectory: np.ndarray, dt: float) -> float:
    """Maximum lateral acceleration magnitude."""
    # Lateral acceleration from trajectory curvature and velocity
    velocities = np.linalg.norm(np.diff(trajectory[:, :2], axis=0), axis=1) / dt
    headings = trajectory[:, 2]
    heading_rate = np.diff(headings) / dt
    lateral_accel = velocities[:-1] * heading_rate[:-1]  # v * dtheta/dt
    return float(np.max(np.abs(lateral_accel)))
```

Comfort impact is measured as the ratio of the BCVF-enabled metric to the
baseline metric. Target: ratio <= 1.10 (at most 10% degradation).

---

**BCVF activation rate** (V3.1 Section 7.3: false positive rate <= 1%)

```python
bcvf_activation_rate = np.mean(bcvf_costs > bcvf_activation_threshold)
```

For S1 (normal driving), this is the false positive rate. Target: <= 0.01.
For failure scenarios, this measures how responsive BCVF is. Higher is not
necessarily better — activation should correlate with the failure onset, not
with noise.

---

#### 4B.4 Aggregate Metrics

These functions accept a list of `EpisodeMetrics` (from N runs of the same
configuration) and return population statistics with confidence intervals.

```python
@dataclass
class AggregateMetrics:
    """Statistics across N runs of one configuration."""
    n_runs: int

    # Safety
    collision_rate: float                   # fraction of runs with collision
    collision_rate_ci_low: float            # 95% Wilson CI lower bound
    collision_rate_ci_high: float           # 95% Wilson CI upper bound

    # Early warning
    early_warning_time_median: Optional[float]
    early_warning_time_iqr: Optional[Tuple[float, float]]  # 25th, 75th percentile

    # Efficiency
    path_efficiency_mean: float
    path_efficiency_std: float

    # Comfort
    rms_lateral_jerk_mean: float
    rms_lateral_jerk_std: float

    # BCVF
    false_positive_rate: float              # activation rate in S1 (normal)
    mean_bcvf_cost_mean: float
    mean_bcvf_cost_std: float

    # Planner
    solve_time_mean_ms: float
    solve_time_p99_ms: float

def compute_aggregate_metrics(
    episode_metrics_list: List[EpisodeMetrics],
) -> AggregateMetrics:
    """Aggregate N episode metrics into population statistics."""
    ...
```

**Wilson confidence interval for collision rate:**

The collision rate is a binomial proportion. The Wilson interval is preferred
over the Wald interval because it is accurate even for small N or extreme
proportions (near 0 or 1), which is the regime BCVF targets (near-zero
collision rate).

```python
def _wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """
    Wilson score interval for binomial proportion.

    Args:
        successes: number of "positive" outcomes (collisions)
        n: total number of trials
        z: z-score for confidence level (1.96 = 95%)

    Returns:
        (lower_bound, upper_bound) of the confidence interval
    """
    if n == 0:
        return (0.0, 1.0)
    p_hat = successes / n
    denominator = 1 + z**2 / n
    center = (p_hat + z**2 / (2*n)) / denominator
    margin = (z / denominator) * np.sqrt(p_hat*(1-p_hat)/n + z**2/(4*n**2))
    return (max(0.0, center - margin), min(1.0, center + margin))
```

**V3.1 reference:** Appendix E.7 — "95% Wilson confidence interval."

---

#### 4B.5 Comparative Analysis

The ablation study (V3.1 Section E.5) compares 4 variants across scenarios.
This requires pairwise comparison functions.

```python
@dataclass
class ComparisonResult:
    """Pairwise comparison between two configurations."""
    config_a_name: str
    config_b_name: str
    metric_name: str
    a_mean: float
    b_mean: float
    difference: float                      # b_mean - a_mean
    relative_change: float                 # difference / a_mean (if a_mean != 0)
    significant: bool                      # p < 0.05
    p_value: float

def compare_collision_rates(
    metrics_a: AggregateMetrics,
    metrics_b: AggregateMetrics,
) -> ComparisonResult:
    """
    Compare collision rates using Fisher's exact test.

    Used for: "Does BCVF reduce collision rate vs. baseline?"
    """
    ...

def compare_continuous_metric(
    values_a: List[float],
    values_b: List[float],
    metric_name: str,
    config_a_name: str,
    config_b_name: str,
) -> ComparisonResult:
    """
    Compare continuous metrics using paired or unpaired t-test.

    Used for: path efficiency, comfort metrics, solve time.
    """
    ...
```

**Statistical tests:**

| Metric | Test | Justification |
|--------|------|---------------|
| Collision rate | Fisher's exact test | Binary outcome, small expected counts |
| Path efficiency | Welch's t-test (unpaired) | Continuous, may have unequal variance |
| RMS lateral jerk | Welch's t-test (unpaired) | Continuous |
| Early warning time | Mann-Whitney U test | May not be normally distributed, often has outliers |
| Solve time | Welch's t-test (unpaired) | Continuous, approximately normal |

**Implementation note:** These tests use only `numpy` and basic math — no
`scipy.stats` dependency. The t-test and Fisher's exact test are implementable
in ~20 lines each using standard formulas. Mann-Whitney U uses the normal
approximation for N >= 20, which is always true for our N=100 runs.

---

#### 4B.6 Result Summary Table

The final output of Phase 4 analysis is a summary table matching V3.1 Appendix
E.8. This function produces a structured dict suitable for printing or JSON
export.

```python
def build_summary_table(
    results: Dict[Tuple[str, str], AggregateMetrics],
) -> Dict:
    """
    Build the V3.1 Appendix E.8 summary table.

    Args:
        results: mapping of (scenario_name, variant_name) -> AggregateMetrics
                 variant_name is one of: "A0_baseline", "A1_zeroth",
                 "A2_first", "A3_second_bcvf"

    Returns:
        Nested dict:
        {
            scenario: {
                variant: {
                    "collision_rate": "0.85 [0.77, 0.91]",
                    "path_efficiency": "1.02 +/- 0.03",
                    "early_warning_s": "3.1 [2.4, 4.0]",
                    "false_positive_rate": "0.00",
                    "rms_jerk_ratio": "1.04",
                    "solve_time_ms": "17.2 +/- 1.1",
                }
            }
        }
    """
    ...
```

**Expected table shape** (matches V3.1 Appendix E.8):

```
                   | Baseline (A0)  | 0th-Order (A1)  | 1st-Order (A2) | BCVF (A3)
-------------------+----------------+-----------------+----------------+----------
S1 Normal          | —              | —               | —              | —
S2 GPS multipath   | collision 85%  | avoids          | delayed        | early avoidance
S3 Map error       | collision 90%  | avoids (noisy)  | late           | early
S4 Camera degrade  | wrong lane     | noisy           | gradual        | smooth
S5 Constant bias   | optimal        | degraded (FP)   | optimal        | optimal (a=0)
S6 Glass corridor  | collision 95%  | avoids (FP)     | late avoidance | early, low FP
```

---

#### 4B.7 Test Specification

Tests go in `bcvf_autonomous/tests/test_metrics.py`.

| Test                                        | What It Validates                                                      |
|---------------------------------------------|------------------------------------------------------------------------|
| `test_path_length_straight_line`            | Straight trajectory of length 100m -> `path_length == 100.0`          |
| `test_path_efficiency_perfect`              | Path exactly on road centerline -> efficiency ~= 1.0                  |
| `test_path_efficiency_detour`               | Path 10% longer than road -> efficiency ~= 1.10                      |
| `test_lateral_jerk_constant_velocity`       | Straight line at constant speed -> lateral jerk ~= 0                  |
| `test_steering_rate_constant`               | Constant steering -> steering rate ~= 0                               |
| `test_bcvf_activation_rate_zero_nominal`    | All-zero BCVF costs -> activation rate = 0                            |
| `test_bcvf_activation_rate_half`            | Half of steps above threshold -> activation rate = 0.5               |
| `test_early_warning_time_basic`             | Baseline collides at step 100, BCVF activates at step 50 -> EWT = 5.0s |
| `test_early_warning_time_no_baseline_collision` | Baseline does not collide -> EWT is None                          |
| `test_wilson_ci_zero_rate`                  | 0 successes out of 100 -> CI includes 0.0, upper bound < 0.05       |
| `test_wilson_ci_full_rate`                  | 100 successes out of 100 -> CI includes 1.0, lower bound > 0.95     |
| `test_wilson_ci_half_rate`                  | 50 out of 100 -> CI approximately [0.40, 0.60]                       |
| `test_aggregate_metrics_shapes`             | 100 episode metrics aggregate correctly, all fields populated         |
| `test_compare_collision_rates_significant`  | 85/100 vs 5/100 -> significant=True, p < 0.001                       |
| `test_compare_continuous_metric`            | Two normal samples with different means -> detects difference         |
| `test_summary_table_structure`              | `build_summary_table` returns dict with all scenarios and variants   |

#### 4B.8 Design Constraints

1. **No scipy dependency.** Statistical tests are implemented from formulas
   using NumPy only. This matches the V1 NumPy-only policy from Phase 0.

2. **No plotting.** `metrics.py` computes numbers. Plotting is Phase 5
   packaging. The summary table dict is the visualization-ready output.

3. **No execution.** `metrics.py` does not run episodes. It accepts
   `EpisodeDiagnostics` or `EpisodeMetrics` lists and returns analysis. Phase 4C
   orchestrates the runs and passes results to these functions.

4. **Deterministic analysis.** Given the same diagnostics, `compute_episode_metrics`
   always returns the same result. No randomness in the analysis layer.

#### 4B.9 Acceptance Criteria for Sub-section 4B

- [ ] `metrics.py` implements `compute_episode_metrics`, `compute_aggregate_metrics`,
  `compute_early_warning_time`, `compare_collision_rates`,
  `compare_continuous_metric`, `build_summary_table`
- [ ] Wilson CI implemented without scipy
- [ ] Fisher's exact test implemented without scipy
- [ ] Welch's t-test implemented without scipy
- [ ] Path efficiency computed correctly for straight and detour trajectories
- [ ] Early warning time requires baseline comparison run
- [ ] Summary table matches V3.1 Appendix E.8 structure
- [ ] All 16 tests pass

---

_End of Phase 4B. Sub-section 4C (sweep orchestrator and CLI) will follow._
