# ACP Safety-Adapter Design (Phase 2 §3)

`autonomous_control_plane/safety_adapters/` — the integration layer that calls
the REAL safety modules and maps their output to ACP `ConstraintResult`s +
`PhysicalEvidence`. It imports numpy + `symbolu_robotics.safety.*` and is **NOT**
imported by the ACP core `__init__`, so `import autonomous_control_plane` stays
production-independent (milestone §3: environment-specific integrations live in
adapter packages). No ROS / simulator / hardware dependency is introduced.

---

## 1. `TrajectoryValidatorAdapter`

`safety_adapters/trajectory_adapter.py`. Wraps the real
`TrajectoryValidator`.

```
evaluate(*, candidate, trajectory_points, obstacles=None, human_position=None,
         human_velocity=None, world_version, now_s, observation_time_s,
         freshness_s) -> (PhysicalEvidence, Tuple[ConstraintResult, ...])
```

Pipeline:
1. **Stale gate** — `freshness_s > max_stale_s (0.2)` → `STALE` evidence +
   failing HARD `STALE_PHYSICAL_EVIDENCE`. **Missing gate** — empty trajectory →
   `MISSING` + failing HARD `MISSING_TRAJECTORY`.
2. **Call the real validator** — `set_obstacles` / `set_human_state` / `validate`
   inside a `try/except`; any exception → `EVALUATOR_FAILED` + failing HARD
   `EVALUATOR_FAILED` (fail closed).
3. **Map `ValidationReport`** → per-category HARD `ConstraintResult`s
   (`POSITION_LIMIT`, `VELOCITY_LIMIT`, `ACCEL_LIMIT`, `JERK_LIMIT`, `WORKSPACE`,
   `COLLISION_CLEARANCE`, `SELF_COLLISION`, `HUMAN_PROXIMITY`), derived by parsing
   `limit_violations` + `collision_predictions` (by type + time-to-collision).
   Granular, so the dispositive rejection names the exact physical check.
4. **Bind** — every result's `evidence_ref = "TrajectoryValidator|{world_version}|
   {candidate.identity}"`; evidence carries `candidate_identity` + `state_version`.

Design rules honored:
- **Calls real repository logic** — no collision/velocity/jerk formula is
  re-implemented; the validator does the work.
- **Preserves original thresholds** — uses the module's own config defaults.
- **Exposes unavailable constraints honestly** — stopping distance / stability /
  curvature / map-lane / per-trajectory actuator are left `None` (not emitted as
  constraints), documented UNAVAILABLE.
- **Fails closed** — every non-VALID validity emits a failing HARD result.

## 2. `candidate_bridge.velocity_command_to_trajectory` (AUTHORED)

`safety_adapters/candidate_bridge.py`. The deliberative call site emits a single
constant-velocity `ActuatorCommand` (`_plan_move`), not a trajectory. This bridge
integrates it (forward Euler over `dt`) into `TrajectoryPoint`s the validator can
check. It is explicitly **AUTHORED** (a demonstration of how physical evidence
*could* be obtained at that call site without fabricating safety data) — not a
production motion planner and not claimed to model real dynamics.

## 3. Determinism & isolation

- Deterministic: no RNG; the validator's only clock use is report metadata, never
  mapped into results (rerun identity = 100%).
- Isolation: the adapter never mutates a production object; it constructs its own
  `TrajectoryValidator` instance. Running it changes no runtime state
  (behavior-change count = 0).
- Core purity preserved: `test_acp_module_sources_are_stdlib_only` /
  `test_acp_core_sources_still_stdlib_only` exclude `safety_adapters/` and assert
  the rest of the ACP core imports no numpy / safety / torch / ROS.

## 4. Extending to other evaluators

Additional adapters (e.g. `ConstraintMonitor.check_command_safety` for an
`ActuatorCommand` candidate) follow the same shape: real call → per-category
`ConstraintResult`s + `PhysicalEvidence`, fail-closed, identity-bound. Only the
`TrajectoryValidatorAdapter` is shipped in Phase 2.
