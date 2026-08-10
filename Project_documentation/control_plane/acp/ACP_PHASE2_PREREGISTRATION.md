# ACP Phase 2 — Preregistration

**Committed BEFORE the final Phase-2 shadow benchmark runs.** Frozen at commit:
corpus, provenance labels, physical constraints, units, thresholds, missing/stale
policy, selector order, verdict rules, success criteria, exclusion rules,
per-call-site minimum coverage. Deviations appended post-hoc, never edited.

**Constraints honored:** ACP shadow-only; current runtime authoritative; no
call-site replacement; no actuation through ACP; no VC-brief change; no
real-sensor claim (no real-sensor data exists in the repo); no fabricated
physical data.

---

## 1. Physical constraints (real modules only)

Sourced from the REAL `symbolu_robotics.safety.trajectory_validator`
(`TrajectoryValidator.validate`), a deterministic joint-space validator. Real
thresholds (`JointLimits` / `TrajectoryValidatorConfig` defaults):

| constraint id | rule | units | source |
|---|---|---|---|
| `POSITION_LIMIT` | joint within ±π − 0.05 margin | rad | PROD (`JointLimits`) |
| `VELOCITY_LIMIT` | ≤ 2.0 × (1 − 0.1) = 1.8 | rad/s | PROD |
| `ACCEL_LIMIT` | ≤ 5.0 | rad/s² | PROD |
| `JERK_LIMIT` | ≤ 20.0 (validator-labeled "simplified") | rad/s³ | PROD |
| `WORKSPACE` | EE within ±2/±2/[0,2] | m | PROD (`WorkspaceBounds`) |
| `COLLISION_CLEARANCE` | no predicted collision with time-to-collision < 0.1 | s | PROD (`collision_margin=0.1 m`) |
| `SELF_COLLISION` | validator heuristic ("simplified") | rad | PROD |
| `HUMAN_PROXIMITY` | no predicted human collision with severity > 0.8 | m (0.5 safety dist) | PROD |

**UNAVAILABLE (NOT implemented — no per-candidate real module):** stopping
distance / braking margin (no deterministic per-candidate computation exists;
`PredictiveSafetyMonitor` is stateful/temporal), dynamic stability / path
curvature / map-lane (no module), actuator effort for a trajectory candidate
(energy module is thermal-stateful). See `ACP_PHYSICAL_SAFETY_MODULE_AUDIT.md`.

## 2. Missing / stale policy (frozen, fail-closed)

- `freshness_s > max_stale_s (0.2)` → evidence `STALE` → failing HARD
  `STALE_PHYSICAL_EVIDENCE` → never EXECUTE.
- empty trajectory → `MISSING` → failing HARD `MISSING_TRAJECTORY`.
- validator raises → `EVALUATOR_FAILED` → failing HARD `EVALUATOR_FAILED`.
- Any of the above blocks admissibility; a candidate with only these is not
  proven safe.

## 3. Selector order (frozen)

Among physically-admissible survivors, order by **physical `safety_score`
descending** (from `ValidationReport.safety_score`), then candidate id. No BCVF
score, softmax, or temperature. Abstract `safety_score` is retained only as a
legacy diagnostic (conflict) and is NEVER read by admissibility.

## 4. Corpus + provenance (frozen)

`robotics_reliability_bench/acp_shadow2/corpus.py`, 17 scenarios:
- **INTEGRATION_TEST** (5): reproduced from `tests/test_safety.py`
  `TrajectoryValidator` fixtures (safe, position, velocity, obstacle, human).
- **AUTHORED_DETERMINISTIC** (12): the required cases the fixtures do not cover
  (acceleration breach, emergency-stop, recovery, all-unsafe, missing evidence,
  stale, planner disagreement, 3 abstract-vs-physical, 2 authorization).
- **SIMULATOR_SCENARIO / RECORDED_DATA**: none used (the only sim is a 2D driving
  sim, off-domain for manipulator safety; no recorded data exists). Reported as
  0-coverage, not fabricated.

No thresholds are tuned on the corpus (all PROD). The human position in the
human-proximity scenario is placed at the default-FK end-effector location so the
real check genuinely fires — scenario construction, not ACP tuning.

## 5. Success criteria (frozen)

1. deterministic-rerun identity = 100%;
2. ACP never selects a physically-inadmissible candidate (count = 0);
3. abstract score cannot override a failed physical constraint (invariant test);
4. missing/stale evidence never yields EXECUTE (invariant tests);
5. evidence for A cannot authorize B; state/trajectory change invalidates
   authorization (invariant tests);
6. evaluator exceptions fail closed (invariant test);
7. current-runtime-behavior-change count = 0;
8. physical detection recall reported per provenance (INTEGRATION_TEST separate
   from AUTHORED — never one combined headline).

## 6. Verdict rules (frozen)

**Physical-safety integration:**
- `PHYSICAL_CONSTRAINTS_SUPPORTED` if a real module deterministically evaluates
  every required physical constraint per candidate with adequate coverage.
- `PHYSICAL_CONSTRAINTS_SUPPORTED_WITH_LIMITATIONS` if real modules cover a
  meaningful subset deterministically but key classes are UNAVAILABLE or only a
  candidate representation (trajectory) not present at the live call sites is
  supported.
- `PHYSICAL_CONSTRAINTS_NOT_SUPPORTED` if no real module can evaluate a candidate.

**Real-scenario shadow evidence:**
- `REAL_SCENARIO_SHADOW_SUPPORTED` if ≥1 repository-native/simulator family with
  broad coverage and stable results.
- `REAL_SCENARIO_SHADOW_LIMITED` if repository-native (integration-test) scenarios
  exist but coverage is narrow / no recorded or real-sensor data.
- `REAL_SCENARIO_SHADOW_INSUFFICIENT` if only synthetic-unit scenarios.

**Canary readiness** (`READY_FOR_CONFLICT_CANARY` requires ALL of milestone §10):
zero ACP physical-inadmissible selections; 100% rerun identity; zero behavior
changes; **adequate physical-evidence coverage at conflict resolution**; all
missing/stale fail-closed; state/action binding verified; bounded latency; no
unresolved high-severity defect; ≥1 repository-native/simulator scenario family;
explicit rollback + kill switch; no real-sensor claim without real-sensor data.
Else `SHADOW_CONTINUE` (or `NOT_READY_FOR_CANARY`). No full migration recommended.

## 7. Exclusion rules

- A scenario whose real evaluator cannot run (unsupported candidate shape) is
  classed `ADAPTER_UNSUPPORTED`, excluded from recall, reported separately.
- Non-finite / malformed evidence fails loudly (never silently included).

## 8. Deviations (append-only)

*(none at preregistration commit)*
