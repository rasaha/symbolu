# ACP Physical-Evidence Contract (Phase 2 §2)

`autonomous_control_plane/physical_evidence.py` — a stdlib-only, immutable,
deterministically-identifiable bundle of physical-safety evidence for ONE
candidate. The numpy/safety integration that *fills* it lives in the adapter
subpackage; the contract itself stays in the production-independent core.

---

## 1. `PhysicalEvidence` fields

Binding + provenance (all required): `candidate_identity`, `state_version`,
`evaluator`, `evaluator_version`, `observation_time_s`, `freshness_s`,
`coordinate_frame`, `validity`.

Booleans (`None` = not evaluated): `trajectory_valid`, `is_safe`, `velocity_ok`,
`accel_ok`, `jerk_ok`, `workspace_ok`, `collision_free`, `self_collision_free`,
`human_proximity_ok`, `kinematic_feasible`, `dynamic_stable`, `actuator_ok`,
`map_lane_valid`.

Numerics with units (`None` = not measured): `safety_score` [0,1],
`min_obstacle_clearance_m` (m), `time_to_collision_s` (s), `stopping_distance_m`
(m), `available_stopping_margin_m` (m), `max_velocity_ratio` / `max_accel_ratio`
/ `max_jerk_ratio` (fraction of limit, >1 = breach). `limit_violations` (tuple).

`validity ∈ {VALID, STALE, EVALUATOR_FAILED, MISSING}`. `coordinate_frame ∈
{joint, world_se2, ee}`.

## 2. Every value carries (milestone §2)

units (documented per field), evaluator source + version, `state_version`,
`candidate_identity`, `observation_time_s` + `freshness_s`, and a `validity`
status. The evidence has a content `identity` (domain-separated SHA-256).

## 3. Fails loudly on

| condition | mechanism |
|---|---|
| NaN / ±Inf in any numeric | `normalize_float` → `NonFiniteValueError` at construction |
| malformed field (empty binding, bad validity type, negative freshness) | `SchemaValidationError` |
| stale evidence | adapter sets `validity=STALE` + emits a failing HARD `STALE_PHYSICAL_EVIDENCE` |
| evidence bound to another action | `candidate_identity` mismatch; authorization binding check raises `AuthorizationBindingError` |
| missing safety-critical evidence | `validity=MISSING` + failing HARD `MISSING_TRAJECTORY` (never EXECUTE) |
| inconsistent coordinate frame | `coordinate_frame` is recorded; a consumer requiring `joint` rejects a mismatched frame |
| evaluator failure | `validity=EVALUATOR_FAILED` + failing HARD `EVALUATOR_FAILED` |

## 4. Usability gate

`PhysicalEvidence.is_usable` is `True` only when `validity == VALID`. Any other
validity is fail-closed: the adapter emits a failing HARD constraint, so the
candidate cannot be admitted on non-VALID evidence.

## 5. Determinism

The evidence is a deterministic function of the validator inputs. The validator's
only clock use (`validation_time_ms`) is never mapped into the evidence, so the
identity and all derived `ConstraintResult`s are byte-stable across reruns
(verified: rerun identity = 100%).

## 6. Non-claims

- Not real-sensor data — evidence is computed from candidate trajectories +
  authored/repository scenarios; no field is labeled a real-sensor measurement.
- Numerics whose real module is unavailable (stopping distance, stability,
  curvature) remain `None` — never fabricated.
