# ACP Phase 3 — Preregistration

**Committed BEFORE the final Phase-3 shadow benchmark runs.** Frozen: selected
live path, corpus, provenance, thresholds, adapter mappings, stale limits,
latency criteria, missing-data rules, verdict rules, exclusions, success
criteria. Deviations appended post-hoc, never edited.

**Constraints:** ACP shadow-only; current runtime authoritative; no BCVF
replacement; no actuation through ACP; no VC-brief change; no real-sensor claim;
no fabricated candidate or physical evidence.

---

## 1. Selected live path (frozen)

`symbolu_robotics.tiers.deliberative.TaskPlanner.plan()` — deterministic, no
existing physical gate, milestone-preferred. Secondary source:
seeded `MPCPlanner.plan_with_validation` as `RECORDED_PLANNER_OUTPUT` only. Other
call sites unsupported (see `ACP_LIVE_PATH_AUDIT.md`).

## 2. Thresholds / adapter mappings (frozen)

Physical thresholds are the REAL `TrajectoryValidator` defaults (unchanged):
velocity 1.8 rad/s, accel 5.0, jerk 20.0, collision 0.1 m, workspace ±2 m, human
0.5 m, position ±π. Bridge: constant-velocity forward Euler, `dt=0.1`, `steps=5`,
6 joints. `max_stale_s = 0.2 s`. No threshold is tuned on the corpus.

## 3. Missing-data / fail-closed rules (frozen)

`MISSING_TRAJECTORY`, `UNSUPPORTED_COMMAND` (gripper / non-joint), `DIMENSION_MISMATCH`,
`NONFINITE`, `IDENTITY_MISMATCH`, `STALE`, `EVALUATOR_FAILED` → all fail closed
(inadmissible, never EXECUTE). No missing physical value is interpolated.

## 4. Corpus + provenance (frozen)

`robotics_reliability_bench/acp_shadow3/corpus.py`, 17 shadow scenarios + 2
commit-revalidation scenarios:
- `LIVE_PATH_TEST_FIXTURE` (3): real `TaskPlanner.plan()` at run time.
- `RECORDED_PLANNER_OUTPUT` (2): seeded MPC (deterministic).
- `AUTHORED_EDGE_CASE` (12): required violation/edge cases the stub planners do
  not emit.
- `REPOSITORY_INTEGRATION_SCENARIO` / `SIMULATOR_GENERATED`: 0 (none exist for the
  joint-space manipulator domain; reported, not fabricated).

## 5. Latency criteria (frozen)

**No validated cycle-time budget exists in the repository for
`TaskPlanner.plan`.** This is reported as a MISSING PRODUCTION REQUIREMENT, not
invented. The R3 tier docstring target (< 100 ms) is used only as a soft
reference bound. We report mean / p95 / max shadow latency against it.

## 6. Metrics (frozen, provenance-stratified)

live-path adapter coverage; physical-evidence coverage; missing/unsupported rate;
ACP inadmissible-selection count; current-runtime physically-inadmissible count;
ACP-vs-validator agreement (LIVE/RECORDED oracle = the validator); authored
detection recall + false-rejection (independent ground truth); NO_SAFE_ACTION
rate; commit state / modified-trajectory rejection; deterministic rerun identity;
authoritative behavior-change count; latency mean/p95/max; shadow error rate;
memory growth; sink drop count. **The Phase-2 "67%" is NOT reused as a headline;
Phase-3 frequencies are reported only within this corpus.**

Recall / false-rejection are computed over `AUTHORED_EDGE_CASE` only (independent
labels). For LIVE / RECORDED the validator is the oracle ACP consumes, so
agreement (should be 1.0) is reported instead — measuring recall against the
validator's own verdict would be tautological.

## 7. Exclusions (frozen)

`LIVE` / `RECORDED` scenarios are excluded from authored-recall / false-rejection
(no independent oracle). Non-finite / malformed inputs fail loudly. Commit-reval
scenarios are evaluated separately from the classification metrics.

## 8. Success criteria (frozen)

1. rerun identity 100%; 2. ACP never admits a validator-failed trajectory (count
0); 3. all missing/stale/malformed/evaluator-failure fail closed; 4. commit
state-change + modified-trajectory rejected; 5. hook OFF ⇒ byte-identical plan;
6. hook exceptions contained; 7. sink bounded (dropped countable, capacity fixed);
8. authoritative behavior-change count 0; 9. no actuation.

## 9. Verdict rules (frozen)

**Live integration:** `LIVE_TRAJECTORY_INTEGRATION_SUPPORTED` if a real current
planner path is covered end-to-end with realistic trajectory diversity;
`…_LIMITED` if covered but the planner emits stub trajectories / diversity comes
from recorded+authored; `…_NOT_SUPPORTED` if no real path can be wired.

**Operational shadow:** `SHADOW_OPERATION_SUPPORTED` if the hook is default-OFF,
byte-identical, exception-contained, bounded, deterministic, and non-actuating;
`…_LIMITED` / `…_NOT_SUPPORTED` otherwise.

**Canary readiness** — `READY_FOR_MANIPULATION_CANARY` requires ALL of milestone
§11 (genuine planner path; 0 ACP physical violations; 100% determinism; 0
behavior changes; bounded latency+storage; missing/stale fail-closed; binding
verified; rollback+kill-switch tested; no unresolved high-severity defect;
adequate repository-native/simulator coverage). Else `SHADOW_CONTINUE` /
`NOT_READY_FOR_CANARY`. No full migration recommended.

## 10. Deviations (append-only)

*(none at preregistration commit)*
