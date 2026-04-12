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

_End of Phase 0. Phases 1-5 will be appended to this document as implementation
proceeds._
