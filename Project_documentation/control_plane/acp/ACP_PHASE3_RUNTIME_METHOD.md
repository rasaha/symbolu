# ACP Phase 3 Runtime Method (§6)

How the live-path shadow benchmark runs and measures runtime/determinism. Code:
`robotics_reliability_bench/acp_shadow3/run_shadow3_bench.py`.

---

## 1. Feed modes

- **LIVE**: build a real `TaskPlanner`, wrap in `InstrumentedTaskPlanner(hook)`,
  call `.plan()` with a `shadow_context` → the hook records out-of-band. The plan
  is returned unchanged; a separate compat check runs the same live scenario with
  the hook OFF vs ON and asserts byte-identical output.
- **RECORDED**: seed `np.random`, call `MPCPlanner.plan_with_validation`,
  reconstruct the exact joint `TrajectoryPoint`s the production method validated,
  feed them to the real Phase-2 adapter.
- **AUTHORED command**: a synthetic `Plan` (real `ActuatorCommand`) fed through
  the live-path adapter + bridge via `hook.observe`.
- **AUTHORED trajectory**: `TrajectoryPoint`s fed straight to the real adapter
  (for accel/jerk/collision/position/stale/evaluator-exception cases).

## 2. Runtime & determinism measures (§6)

| measure | how |
|---|---|
| adapter latency | `perf_counter` around the live-path adapter |
| validator latency | `perf_counter` around the real `validate()` |
| complete ACP shadow latency | `perf_counter` around the whole `observe`/eval |
| memory growth | `tracemalloc` delta over the run (dominated by transient numpy/validator allocations, not the sink) |
| logging overhead | `BoundedShadowSink` (`deque(maxlen)`) — `dropped` + capacity reported |
| deterministic rerun identity | whole corpus run twice; `content_dict()` compared (latency excluded) |
| current-runtime output identity | LIVE hook OFF vs ON byte-identical plan |
| shadow error rate | fraction of records with `shadow_error=True` |

Latency is measured but there is **no validated repository cycle budget** for
`TaskPlanner.plan`; that gap is reported as a missing production requirement. The
R3 tier `< 100 ms` docstring target is a soft reference only.

## 3. Commit-time revalidation (§7)

For the two mutate scenarios the harness evaluates, then mutates the world
version / candidate identity, and calls `commit_revalidate` — recording whether
the earlier ACP evaluation would remain valid. It does not gate execution.

## 4. Zero-impact guarantees (verified)

- `authoritative_runtime_behavior_change_count = 0` — the harness makes no
  production call that mutates state (LIVE calls the real planner read-only; the
  plan is returned unchanged).
- The robotics baseline suite is byte-identical before/after; no production
  module imports ACP.
- Every record is `shadow_only`; no `ControlAuthorization`/actuator is invoked.
