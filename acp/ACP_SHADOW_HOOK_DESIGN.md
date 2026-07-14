# ACP Shadow-Hook Design (Phase 3 §4, §7)

`safety_adapters/shadow_planner_hook.py` — the disabled-by-default shadow hook
around the live deliberative path, implemented by **composition** (no production
edit).

---

## 1. Components

- **`ShadowPlannerHook(enabled=False, sink, validator_adapter, …)`** — the hook.
  `observe(*, action_id, plan, world_state, q0, …)`: returns `None` when
  disabled; otherwise, inside a `try/except` that contains ALL exceptions, runs
  live-path adapter → real `TrajectoryValidator` → ACP selection → appends a
  `ShadowRecord3` to the sink. Never raises.
- **`InstrumentedTaskPlanner(real_planner, hook)`** — composes the REAL planner.
  `.plan(...)` calls `real_planner.plan(...)`, returns its `Plan`
  **byte-identical**, then fires the hook out-of-band. `__getattr__` delegates
  everything else. The planner's own exceptions propagate unchanged.
- **`BoundedShadowSink(maxlen)`** — a `deque(maxlen)` ring buffer: shadow logging
  cannot grow unbounded (no DoS path); evictions are counted (`dropped`).

## 2. §4 requirements — how each is met

| requirement | mechanism |
|---|---|
| default OFF | `enabled=False`; `observe` returns `None` when disabled |
| original output unchanged | `InstrumentedTaskPlanner.plan` returns the real plan; verified byte-identical (test + bench `hook_off_on_output_identical`) |
| original exception behaviour unchanged | the real `plan()` is called first; its exceptions propagate before the hook runs |
| ACP failure cannot block/alter the path | `observe` contains every exception → records `shadow_error=True`, never propagates |
| record marked `shadow_only=true` | every `ShadowRecord3.shadow_only == True` |
| no ACP authorization reaches actuator | the hook produces records only; no actuator/controller call exists |
| bounded queue/storage (no DoS) | `BoundedShadowSink(maxlen)`; `dropped` counted; bench `sink_dropped` reported |
| kill switch + rollback | `enabled=False` is the kill switch; rollback = delete the adapter subpackage (nothing in production depends on it) — see `ACP_PHASE3_RESULTS.md` §rollback |

## 3. Evidence integrity vs latency

The hook records **synchronously** in-line so the exact `(plan, world_state, q0)`
binding is preserved with the record — evidence integrity is not sacrificed for
latency. Because the shadow work is contained and bounded (~1 ms; §runtime), an
out-of-band thread is unnecessary; if one were added it would have to copy the
bound inputs first (documented, not implemented).

## 4. Commit-time revalidation (§7, no gate)

`ShadowPlannerHook.commit_revalidate(*, candidate, current_world_state, now_s,
evidence_time_s)` checks, before the runtime *would* send the action, whether the
earlier ACP evaluation would still hold:
- candidate/trajectory identity unchanged → else `AuthorizationBindingError`;
- world-state identity unchanged → else `StaleAuthorizationError`;
- evidence still fresh → else `StaleAuthorizationError`.

It returns `{revalidated: bool, reason}` and **does not gate execution**. The
bench exercises a state-change and a modified-trajectory scenario; both correctly
return `revalidated=False`.

## 5. Production wiring (documented, NOT enabled in Phase 3)

To enable later behind a flag: construct
`InstrumentedTaskPlanner(TaskPlanner(), ShadowPlannerHook(sink, enabled=<flag>))`
in place of `TaskPlanner()` in the R3 tier, passing a `shadow_context`. Default
`enabled=False`. Phase 3 does NOT edit the tier loop — the wrapper is exercised
only by the harness/tests, so production is untouched (rollback = delete).
