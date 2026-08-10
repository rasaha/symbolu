# Hierarchical Planning & Goal Decomposition (H15)

Deterministic hierarchical planning that decomposes a mission into an explicit
tree of goals and subgoals, then feeds **ready** leaf goals to the **unchanged**
H16 coordinator for governed execution.

```
Mission → Mission Plan → Goal Tree → Ready Child Goals → H16 Coordinator → Workers
```

Planning decides **what** should be executed; H16 decides **who** executes it.
This is the layer H16 was intentionally designed to support: H16 is
planning-strategy agnostic, so H15 plugs in through its public API with **no
change to H16**.

This layer adds hierarchical planning only. It does not modify H10 iterative
execution, H11 RunBudget, H12 replanning, H13 plan validity, H14 WorkingMemory,
H16 coordination, governance, authorization, ActionGate, TAP, tool execution, or
LLM providers — it composes on their public APIs. The whole hierarchy shares one
`WorkingMemory` and one `RunBudget`.

Excluded by design: autonomous goal invention, planning search, Monte-Carlo
planning, reinforcement learning, parallel scheduling, negotiation.

---

## Hierarchy model

A **`Goal`** is an immutable declaration:

| Field | Meaning |
|-------|---------|
| `goal_id`, `description` | identity |
| `parent`, `children` | tree structure |
| `priority` | lower runs first within a wave |
| `dependencies` | predecessor goal ids (must complete first) |
| `assumptions` | H13 assumption ids the goal relies on |
| `required_memory`, `produced_memory` | H14 keys consumed / produced |
| `completion_criteria`, `mandatory` | completion semantics |
| `goal_type`, `required_capabilities`, `authority_scope`, `expected_outputs` | H16 execution attributes for leaf goals |

Runtime status lives on the mutable **`GoalNode`** (the `Goal` stays immutable),
with an **append-only** `history` of `GoalTransition`s. A **`GoalTree`** holds the
nodes, roots, parent/child links, and the dependency graph; it enforces
**acyclicity** (`validate_acyclic` rejects dependency cycles). A **`MissionPlan`**
pairs a mission id with its tree.

---

## Decomposition lifecycle

A **`GoalDecomposer`** turns a mission specification into a deterministic tree —
strategy-agnostic:

- **`StaticDecomposer`** — builds the tree from an explicit `List[Goal]` (parents
  inserted before children; the same list always yields the same tree).
- **`RuleBasedDecomposer`** — a pure `rules(spec) -> List[Goal]` callable, then
  `StaticDecomposer`. This is the seam for future symbolic or model-assisted
  decomposers: swap the callable, the runtime is unchanged.

The same mission always decomposes into the same hierarchy (deterministic).

---

## Goal lifecycle

`CREATED → READY → BLOCKED → EXECUTING → COMPLETED | FAILED | ABORTED`.
Transitions are append-only; history is immutable. `ABORTED` is distinct from
`FAILED`: it means *replaced by a localized replan*, so it neither blocks
dependents nor fails the mission.

---

## Dependency management & ready-goal discovery

A leaf goal is **READY** only when every dependency is `COMPLETED` and its
(inherited) assumptions are valid. If any dependency `FAILED`, or an inherited
assumption is `INVALID`/`EXPIRED`, it is `BLOCKED`. Ready goals are ordered
deterministically by `(priority, goal_id)`. Internal goals roll up to `COMPLETED`
when all their mandatory (non-aborted) children complete.

---

## Subtree execution (the wave loop)

`HierarchyExecutor.run(plan)`:

```
create ONE H16 Coordinator(registry, memory, run_budget)   # unchanged H16
loop (bounded by max_waves):
    ready = ready leaf goals               # dependency + assumption gated
    if none: break
    mission = Mission of CoordinationGoal(ready)   # depends_on empty within a wave
    coordination = coordinator.run(mission)         # H16 executes, unmodified
    mark COMPLETED / FAILED from the coordination result
    on FAILED: optionally replan ONLY that leaf's subtree (localized)
    roll up internal goals; release newly-ready dependents
    record the wave in the HierarchyTrace
mission status = COMPLETED iff all mandatory (non-aborted) leaves COMPLETED
```

Within a wave, ready goals have all dependencies already satisfied, so the H16
coordinator receives them with empty `depends_on` — **the tree, not H16,
sequences the hierarchy**.

---

## Interaction with H16 (coordination) — unchanged

Each wave builds an H16 `Mission` and calls `Coordinator.run(...)` exactly as-is.
Capability, authority, budget, and goal-ownership checks are enforced by H16;
worker selection, delegation contracts, ownership transfer, and failure recovery
all happen in H16. H15 only decides *which* goals are ready and reads back the
`CoordinationResult`. No H16 code is modified.

---

## Interaction with H12 (replanning) — localized

A failed leaf triggers replanning of **only its subtree**. The optional
`subtree_replanner(tree, failed_goal_id) -> List[Goal]` returns replacement leaves
under the same parent; `GoalTree.replace_leaf` aborts the failed leaf (history
kept), inserts the replacements, and rewires only that leaf's successors. Sibling
subtrees — their goals, statuses, and histories — are untouched. A failure inside
*Build UI* never replans *Build API*.

---

## Interaction with H13 (assumptions)

Goals inherit assumptions from their ancestors (a child's effective assumptions =
its own + parents'). When an `AssumptionContext` is supplied, a goal whose
inherited assumptions are `INVALID`/`EXPIRED` is `BLOCKED` (and, if mandatory,
fails the mission). H13's registry and evaluation are used read-only through their
public API — H13 is not modified. Memory-driven assumption invalidation
(H14 → H13 via `MemoryAssumptionBridge`) therefore propagates into hierarchy
gating automatically.

---

## Interaction with H14 (working memory)

All goals share the one `WorkingMemory` passed to the executor — no duplicated
stores. Child goals declare `required_memory` / `produced_memory`; the H16
coordinator commits worker outputs to that shared, versioned store, so sibling and
successor goals read the same governed state (H14 semantics).

---

## Interaction with H11 (RunBudget)

The whole hierarchy shares one `RunBudget`. It is passed to the single coordinator
and consumed cumulatively across every wave — one `handoffs` unit per delegation,
worker model calls counted on the same budget. Recursive decomposition never
creates additional budgets; exhaustion stops the hierarchy deterministically
(`BUDGET_EXHAUSTED`).

---

## Localized failure

Failures affect only the smallest valid subtree. A leaf failure blocks only its
dependents; independent subtrees continue to completion. The parent mission
remains intact unless a mandatory goal cannot be completed (or an inherited
assumption is invalidated), in which case the failure escalates.

---

## Trace reconstruction

`HierarchyTrace` records a `WaveRecord` per wave: the ready goals, their H16
assignments (agent + resulting state), completions, failures, localized replans,
and the goals released for the next wave. Combined with each `GoalNode`'s
append-only history and the H16 `CoordinationResult`s, the full parent–child
execution history reconstructs deterministically. `HierarchyResult.to_dict()`
serialises the tree, waves, and budget snapshot;
`format_goal_tree` / `format_hierarchy_trace` render them.

---

## Deterministic guarantees

- Decomposition, ready-goal ordering, and roll-up are pure functions of the goal
  declarations and prior statuses.
- The same mission produces the same tree, the same waves, and the same trace.
- No wall-clock time or randomness is used.

---

## Quickstart

```python
from agentic.agentic_framework import (
    WorkingMemory, RunBudget, RunBudgetLimits,
    AgentProfile, CapabilityRegistry, ScriptedWorker, WorkerResult,
    Goal, StaticDecomposer, HierarchyExecutor,
)

registry = CapabilityRegistry()
registry.register(AgentProfile("build_team", capabilities=frozenset({"build"}), trust_level=5),
                  ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))
registry.register(AgentProfile("release_team", capabilities=frozenset({"deploy"}), trust_level=5),
                  ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))

plan = StaticDecomposer().decompose("ship", [
    Goal("build_api", "API", required_capabilities=frozenset({"build"}), expected_outputs=("api",), priority=1),
    Goal("build_ui", "UI", required_capabilities=frozenset({"build"}), expected_outputs=("ui",), priority=2),
    Goal("deploy", "deploy", required_capabilities=frozenset({"deploy"}),
         dependencies=("build_api", "build_ui"), expected_outputs=("release",), priority=3),
])

result = HierarchyExecutor(registry, WorkingMemory(), run_budget=RunBudget(RunBudgetLimits())).run(plan)
print(result.status, result.completed_goals)
```

See [`examples/hierarchical_planning.py`](../../examples/hierarchical_planning.py)
— deterministic decomposition, dependency release, H16 execution, and localized
subtree replanning, with scripted workers and no API key.
