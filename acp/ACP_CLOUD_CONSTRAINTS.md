# ACP Cloud Hard Constraints (V2 §6)

Code: `symbolu_robotics/autonomous_control_plane/cloud/constraints.py`
(`CloudConstraintEvaluator`). Every constraint is **HARD** and
**non-compensatory** — a single failed HARD result makes the candidate
inadmissible, and no soft score can rescue it (enforced by the frozen
`action_selection.filter_admissible`). Every result is a frozen-core
`ConstraintResult`, binding to `candidate.identity` (via the constraint set) and
`world.version` (via `evidence_ref`).

## Fail-closed contract

`world is None` ⇒ `MISSING`; `origin_state_version ≠ world.version` ⇒ `MISSING`
(binding mismatch); `freshness_s > 30 s` or `< 0` ⇒ `STALE`; any exception from a
real `cloud_controller` evaluator ⇒ `EVALUATOR_FAILED`. In every case the
evaluator returns a **single failing HARD result**, so the candidate is
inadmissible — never a silent pass.

## The constraint set

| id | kind | source | rule | units | missing-data | reason on fail |
|---|---|---|---|---|---|---|
| `STATE_FRESH` | HARD | AUTHORED | `freshness_s ≤ 30` | seconds | fail-closed `STALE` | `STATE_STALE` |
| `TARGET_BOUND` | HARD | AUTHORED | candidate ns+deployment == state | — | fail-closed | `TARGET_MISMATCH` |
| `READINESS_OK` | HARD | **REAL** `ReadinessChecker.check` | `.ready` (plasticity ≥ 0.3, action-age ≥ 120 s, no rollback watch) | — | fail-closed | `NOT_READY` |
| `REPLICA_WITHIN_LIMIT` | HARD | **REAL** `PolicyEngine.check` | `min ≤ target ≤ max` | replicas | fail-closed | `REPLICA_LIMIT_VIOLATION` |
| `BLAST_RADIUS_WITHIN_BOUND` | HARD | **REAL** `SafetyConfig` fractions | `blast ≤ max(1, ⌊current·frac⌋)`; frac = 0.50 out / 0.25 in | replicas | fail-closed | `BLAST_RADIUS_EXCEEDED` |
| `MIN_AVAILABILITY_PRESERVED` | HARD | **REAL** `SafetyConfig.min_replicas` | `target ≥ min_replicas` | replicas | fail-closed | `BELOW_MIN_REPLICAS` |
| `NO_ACTIVE_FREEZE` | HARD | **REAL** `BlackoutWindow` (flag) | `¬freeze_active` | bool | fail-closed | `FREEZE_WINDOW_ACTIVE` |
| `DEPENDENCY_HEALTHY` | HARD | AUTHORED | `dependency_healthy` | bool | fail-closed | `DEPENDENCY_UNHEALTHY` |
| `CAPACITY_SUFFICIENT` | HARD | AUTHORED | `available ≥ min_replicas` | replicas | fail-closed | `INSUFFICIENT_CAPACITY` |
| `ROLLBACK_AVAILABLE` | HARD (rollout/config/delete) | AUTHORED | `rollback_ref ≠ ""` | bool | fail-closed | `NO_ROLLBACK_REF` |

`frac` for `BLAST_RADIUS_WITHIN_BOUND` is taken **directly from the real
`SafetyConfig`** (`max_scale_out_fraction` / `max_scale_in_fraction`), not a
re-authored constant. `READINESS_OK`, `REPLICA_WITHIN_LIMIT`, and the min/fraction
bounds are computed by **calling the real `cloud_controller` objects** — the
evaluator is a thin binding layer over them, not a reimplementation.

## How the real modules are invoked (per candidate)

```
ReadinessChecker(ReadinessConfig()).check(
    plasticity=world.readiness_plasticity, stability=…,
    last_action_time=now_s − world.seconds_since_last_action,
    active_rollback_watches=world.active_rollback_watches, current_time=now_s)
PolicyEngine(PolicyConfig(DeploymentPolicy(min, max))).check(
    deployment, namespace, current_replicas, target_replicas, current_time=now_s)
SafetyBounds(SafetyConfig()).check(
    current_replicas, proposed_delta=target−current, current_time=now_s)
```

All three are pure-Python, deterministic, and touch no Kubernetes client. The
evaluator is a pure function of `(candidate, world, now_s, freshness_s)` + config
— no wall clock, no randomness, no I/O — so runs are byte-for-byte reproducible.

## Why these and not others

Only constraints with a **real repository source** or an **explicit, documented
authored fixture** are implemented. Constraints that would need fabricated
telemetry (live latency SLOs, error-budget burn, per-node capacity) are **not**
implemented — that is a limitation, recorded in `ACP_V2_RESULTS.md`, not a gap
filled with invented numbers.
