# ACP Real-Scenario Corpus (Phase 2 §5)

`robotics_reliability_bench/acp_shadow2/corpus.py` — 17 scenarios driving the
REAL `TrajectoryValidator`. Provenance is labeled per the milestone priority
order; nothing is described as real-sensor evidence.

---

## 1. Provenance distribution

| provenance | count | source |
|---|---|---|
| `INTEGRATION_TEST` | 5 | reproduced from `tests/test_safety.py` `TrajectoryValidator` fixtures (real repository test code) |
| `AUTHORED_DETERMINISTIC` | 12 | required cases the fixtures don't cover |
| `SIMULATOR_SCENARIO` | 0 | only sim is a 2D driving sim (off-domain for manipulator safety) |
| `RECORDED_DATA` | 0 | no recorded trajectory/scene data exists in the repo |
| `SYNTHETIC_UNIT` | 0 | — |

Priority order followed: integration-test scenarios were used first
(highest-priority real source); simulator/recorded were genuinely absent for this
domain, so authored deterministic scenarios fill the remaining required cases.

## 2. Coverage of required cases

| required case | scenario(s) | provenance |
|---|---|---|
| clear safe maneuver | `safe_within_limits` | INTEGRATION_TEST |
| obstacle-too-close | `obstacle_too_close` | INTEGRATION_TEST |
| velocity-limit breach | `velocity_limit_breach` | INTEGRATION_TEST |
| acceleration/jerk breach | `acceleration_breach` | AUTHORED |
| invalid trajectory | `position_limit_violation` | INTEGRATION_TEST |
| stale perception state | `stale_perception_state` | AUTHORED |
| emergency-stop candidate | `emergency_stop_candidate`, `human_proximity` | AUTHORED / INTEGRATION_TEST |
| all candidates unsafe | `all_candidates_unsafe` | AUTHORED |
| recovery maneuver | `recovery_maneuver` | AUTHORED |
| planner/constraint disagreement | `planner_constraint_disagreement` | AUTHORED |
| abstract score disagrees with physical | `abstract_safe_physically_unsafe`, `abstract_unsafe_physically_safe`, `abstract_physical_agree_safe` | AUTHORED |
| missing physical evidence | `missing_physical_evidence` | AUTHORED |
| state changes between eval and commit | `state_changes_before_commit` | AUTHORED |
| modified trajectory after authorization | `modified_trajectory_after_auth` | AUTHORED |
| insufficient stopping distance | **NOT INCLUDED** — no per-candidate stopping-distance module exists (UNAVAILABLE; not fabricated) | — |

## 3. Families

- **physical** (12): single/multi-candidate joint trajectories with a
  human-known `ground_truth_safe` label; the real validator produces the measured
  verdict. Metrics: detection recall, false rejection, fail-closed.
- **abstract_vs_physical** (3): candidates carrying BOTH a legacy abstract
  `safety_score` AND a real physical trajectory — measures whether the abstract
  conflict score agrees with real physical checks.
- **authorization** (2): state-change and modified-trajectory revalidation.

## 4. Determinism & honesty

- Fully deterministic (fixed arrays, no RNG).
- The human-proximity scenario places the human at the default-FK end-effector
  location so the real check genuinely fires — faithful scenario construction
  (matches `test_safety.py:837`'s intent), not ACP tuning.
- Trajectories are stored as plain lists (machine-readable corpus); the harness
  builds `TrajectoryPoint`s at run time.
- No thresholds are tuned on the corpus (all PROD).
