# ACP Candidate-Trajectory Bridge (Phase 3 §2)

`safety_adapters/live_planner_adapter.py` +
`safety_adapters/candidate_bridge.py` — translate the real deliberative
planner's output (`Plan` → `ActuatorCommand`) into the existing `TrajectoryPoint`
representation the real `TrajectoryValidator` consumes, WITHOUT fabricating
information.

---

## 1. Mapping

`plan_to_trajectory_candidate(*, action_id, plan, world_version, q0, dt, steps,
planner_provenance, expected_state_version=None) -> LivePathResult`.

- Extracts the first `ActuatorCommand` from the real `Plan`.
- A constant joint-velocity command is rolled forward by **deterministic forward
  Euler** (`velocity_command_to_trajectory`): `q_k = q0 + v · (k·dt)`,
  `TrajectoryPoint(timestamp=k·dt, positions=q_k, velocities=v)`. This is the
  literal meaning of "apply velocity v for duration T" — not an inferred or
  interpolated physical value.
- An `emergency_stop` command → a zero-velocity (inherently safe) trajectory.

## 2. Preserved & bound (§2)

candidate/action id (`candidate_id`); trajectory points + timestamps (from the
bridge); joint ordering (6-joint count checked); coordinate frame (`joint`,
recorded in metadata); world-state identity (`origin_state_version`); planner
provenance (metadata `planner_provenance`); validator config/version (recorded by
the Phase-2 adapter). The candidate carries a content `identity` that binds all
of the above.

## 3. Fail-closed conditions (§2) → status

| condition | `LivePathStatus` |
|---|---|
| plan has no actions | `MISSING_TRAJECTORY` |
| command has no joint `target_velocities` (gripper / non-locomotion) | `UNSUPPORTED_COMMAND` |
| velocity/state not a 6-vector | `DIMENSION_MISMATCH` (unit ambiguity / inconsistent joint ordering) |
| NaN/Inf in command or state | `NONFINITE` |
| supplied `expected_state_version` ≠ `world_version` | `IDENTITY_MISMATCH` |
| stale (freshness > max) | handled downstream by the Phase-2 adapter → `STALE` |

Any non-`SUPPORTED` status makes the candidate inadmissible (the hook records a
fail-closed `NO_SAFE_ACTION`); **no missing physical value is interpolated or
inferred**.

## 4. What is NOT fabricated

- If the planner emits a gripper command, ACP does **not** invent a joint
  trajectory — it reports `UNSUPPORTED_COMMAND`.
- The bridge does not add dynamics, acceleration, or jerk the command does not
  specify (constant-velocity rollout has zero acceleration by construction) — so
  acceleration/jerk violations can only come from a trajectory that actually
  contains them (`AUTHORED_EDGE_CASE` / `RECORDED`), never from the bridge.
- The bridge is explicitly AUTHORED (`candidate_bridge.py`): a demonstration of
  obtaining physical evidence at the deliberative call site, not a production
  motion planner and not a claim of real robot dynamics.
