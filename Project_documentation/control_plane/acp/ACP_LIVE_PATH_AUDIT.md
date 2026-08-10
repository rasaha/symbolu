# ACP Live-Path Audit (Phase 3 §1)

Selection of the one live integration point and why the others remain
unsupported. Evidence-based against the real code.

---

## 1. Selected live path

**`symbolu_robotics.tiers.deliberative.TaskPlanner.plan()`** (deliberative /
manipulation path).

| §1 criterion | deliberative `TaskPlanner.plan` |
|---|---|
| produces an actual candidate trajectory | **partial** — emits an `ActuatorCommand` (joint velocity), deterministically rolled to a `TrajectoryPoint` sequence by the production-shaped adapter (not fabrication; §2/bridge doc) |
| has access to current world state | yes (`WorldModel`, `Layer12D`) |
| can call the existing TrajectoryValidator | yes (via the Phase-2 adapter) |
| executes in current robotics code | yes (R3 deliberative tier) |
| deterministic test/simulator coverage | yes — deterministic (no RNG); `test_tiers.py` covers it |
| instrumentable without changing its result | yes — wrapped by composition (`InstrumentedTaskPlanner`); plan returned byte-identical |

**Why deliberative:** it is the milestone-preferred path, it is deterministic,
and — critically — it has **no existing physical gate** (BCVF-only selection), so
an ACP physical shadow adds genuine value exactly where Phase 2 found the gap.

## 2. Why the other paths remain unsupported / secondary

| path | status | reason |
|---|---|---|
| `coordination.conflict_resolution` | **unsupported** | abstract strategy candidates; **no candidate trajectory** (Phase 2). `safety_score` is an unreliable proxy (Phase 2 agreement 0.333). |
| `coordination.task_allocation` | **unsupported** | bids, no trajectory; hard filter duplicates existing pre-filters (Phase 1). |
| `MPCPlanner.plan_with_validation` | **secondary (RECORDED only)** | produces a genuine varied trajectory AND **already calls the TrajectoryValidator internally** (`mpc_planner.py:547`) — so ACP would only *wrap* an existing gate, not add one. It also uses `np.random` (`:463`), so it is **non-deterministic** unless seeded. Used only as a seeded source of `RECORDED_PLANNER_OUTPUT` trajectories, not as the live hook. |

## 3. Honest limitation of the selected path

`TaskPlanner._plan_move` is a documented **stub** — "Simplified: single velocity
command" (`deliberative.py:272`), emitting a fixed `[0.5, 0,…]` velocity
regardless of goal. Consequently the live path only ever emits **safe** move /
stop trajectories (or an unsupported gripper command). It cannot itself produce a
violating trajectory, so violation coverage comes from `RECORDED_PLANNER_OUTPUT`
(real MPC) and `AUTHORED_EDGE_CASE`. This is the central reason the live-integration
verdict is *LIMITED*, not *SUPPORTED*: the integration mechanism works
end-to-end on a real path, but the current planner's trajectory realism is low.

## 4. No generic bridge built

Per §1, no generic multi-path bridge is built. Exactly one concrete path
(deliberative) is wired, plus a seeded read-only capture of MPC outputs. Other
call sites are left explicitly unsupported.
