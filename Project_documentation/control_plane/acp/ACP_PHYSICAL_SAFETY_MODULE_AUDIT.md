# ACP Physical-Safety Module Audit (Phase 2 §1)

Audit of the repository's real physical-safety modules for per-candidate ACP
evaluation. A documentation mention is not an implemented check — every row is
verified against source (file:line). Deterministic = pure pass/fail given inputs
(a `time.time()` used only for a report metadatum is still deterministic for the
verdict).

---

## 1. Directly usable per-candidate (deterministic, numpy-only) — USED

| module.symbol | file:line | input | output | units | thresholds (source) | tested | deterministic |
|---|---|---|---|---|---|---|---|
| `TrajectoryValidator.validate` | `safety/trajectory_validator.py:214` | `List[TrajectoryPoint]` (joint positions/vel/accel) + `set_obstacles([(center,radius)])` + `set_human_state` | `ValidationReport(is_safe, safety_score, limit_violations, collision_predictions)` | rad, rad/s, rad/s², m | vel 1.8, accel 5.0, jerk 20.0, collision 0.1 m, human 0.5 m, workspace ±2 m (PROD defaults) | YES (`test_safety.py:691`) | YES (clock only for `validation_time_ms`) |
| `ConstraintMonitor.check_command_safety` | `safety/constraint_monitor.py:167` | `ActuatorCommand` | `(bool, [violations])` | rad/s, rad, Nm | vel 2.0, effort 100.0 (PROD) | YES | YES |
| `ConstraintChecker.check_*` | `mpc_planner.py:169-197` | velocity / position / 12D+action | `(bool, msg)` / `[msg]` | mixed | vel 1.0, accel 2.0, collision r 0.5 (PROD) | via integration | YES (the checker; `MPCPlanner.plan` around it is NOT — `np.random` at `:463`) |

**Chosen primary evaluator:** `TrajectoryValidator.validate` — the richest, most
tested, self-contained per-candidate deterministic validator. This is what the
Phase-2 adapter wraps.

## 2. Available but NOT per-candidate deterministic — NOT used on the decision path

| module.symbol | file:line | why excluded |
|---|---|---|
| `CollisionGuard.clear / get_safety_level` | `collision_guard.py:45,88` | needs a live `SensorFrame` (sensor arrays), carries internal state between calls — not a candidate trajectory |
| `HumanProximityMonitor.update / get_max_allowed_speed` | `human_proximity.py:47,106` | needs prior `update()` state; `SensorFrame`-driven |
| `EnergyBoundsMonitor.check_limits` (thermal) | `energy_bounds.py:59` | thermal branch depends on `_thermal_state` EMA history |
| `PredictiveSafetyMonitor.update` | `trajectory_validator.py:884` | `time.time()` + `start_monitoring` state — non-deterministic |
| `Watchdog` / `TierFallbackManager` | `watchdog.py`, `fallback.py` | wall-clock (`perf_counter`) + threads + mutable counters — compute stale-world/e-stop/min-risk but are inherently stateful/temporal |
| `MPCPlanner.plan` | `mpc_planner.py:290` | `np.random.randn` (`:463`) + `time.time()` |

## 3. Constraint-class coverage matrix

| physical constraint | real per-candidate module? | in Phase-2 adapter? |
|---|---|---|
| obstacle distance / collision risk | `TrajectoryValidator._predict_collisions` (ttc, severity) | **YES** (`COLLISION_CLEARANCE`) |
| trajectory validity | `TrajectoryValidator.validate.is_safe` | **YES** |
| velocity limit | `_check_velocity_limits` | **YES** |
| acceleration limit | `_check_acceleration_limits` | **YES** |
| jerk limit | `_check_jerk_limits` ("simplified") | **YES** (flagged) |
| position / kinematic limit | `_check_position_limits` | **YES** |
| workspace bounds | `_check_workspace_bounds` | **YES** |
| self-collision | `_check_self_collision` ("simplified") | **YES** (flagged) |
| human proximity | `_check_human_proximity` | **YES** |
| **stopping distance / braking margin** | none per-candidate deterministic | **NO — UNAVAILABLE** |
| **dynamic stability / ZMP** | none | **NO — UNAVAILABLE** |
| **path curvature** | none (A* exposes only `Path.is_valid`) | **NO — UNAVAILABLE** |
| **map / lane constraints** | none (manipulator domain) | **NO — UNAVAILABLE** |
| **actuator effort (per-trajectory)** | energy module is thermal-stateful | **NO — UNAVAILABLE** |
| stale world-state | ACP freshness gate (adapter-level) | **YES** (fail-closed) |
| emergency-stop / min-risk conditions | `Watchdog`/`fallback` (stateful) | **NO** — modeled as safe-fallback candidates only |

## 4. Load-bearing limitations (honest)

- The real validators are **manipulator joint-space** (6-DOF, generic ±π /
  ±2 m defaults — *not calibrated to any specific robot*). They evaluate a
  candidate expressed as a **joint trajectory**.
- The three BCVF call sites do **not** currently carry candidate joint
  trajectories: deliberative emits a single constant-velocity stub
  (`_plan_move`), conflict emits abstract strategies, task emits bids. So real
  physical evidence attaches at the **trajectory/manipulation** level, and
  integrating it into the live call sites needs a candidate→trajectory bridge
  (Phase-2 provides an AUTHORED demonstration bridge; production wiring is later).
- `_check_jerk_limits` and `_check_self_collision` are self-labeled "simplified".
- Stopping distance, dynamic stability, curvature, map/lane, per-trajectory
  actuator effort have **no deterministic per-candidate module** — genuinely
  unavailable, not fabricated.
