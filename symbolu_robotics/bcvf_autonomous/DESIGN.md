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

_End of Phase 1. Phase 2 (Predictor Framework) will be appended after Phase 1
implementation is complete._
