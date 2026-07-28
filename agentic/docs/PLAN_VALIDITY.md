# Plan Validity & Assumption Tracking (H13)

Elevates the runtime from *replan whenever something changes* (H12) to
**replan only when the reasoning behind the current plan is no longer
valid**. This significantly reduces unnecessary replanning and gives the
runtime a semantic basis for future memory and hierarchical planning.

```
Goal → Plan + Assumptions → Observation → Assumption Evaluation
    → Plan Valid?  →  Continue | Replan | Abort | Complete
```

The runtime reasons about **assumptions**, not raw observations. An
observation that changes nothing about the assumptions does **not** trigger
replanning.

This layer is **additive and strategy-agnostic**. It does not modify the
replanning engine, RunBudget, governance, authorization, ActionGate, TAP,
routing, tool execution, or LLM providers. It plugs into the two seams
`ReplanningRunner` already exposes — a `ReplanPolicy` and a replanner
strategy — which cooperate through a shared `AssumptionContext`.

---

## Assumption lifecycle

A **`PlanAssumption`** is an explicit precondition a plan depends on:

| Field | Meaning |
|-------|---------|
| `assumption_id` | unique identifier |
| `description` | human-readable statement |
| `category` | e.g. `resource`, `data`, `authorization`, `network` |
| `state` | `VALID` / `INVALID` / `UNKNOWN` / `SATISFIED` / `EXPIRED` |
| `confidence` | `[0.0, 1.0]` |
| `evidence` | supporting observations |
| `mandatory` | is this a critical precondition? |
| `recoverable` | can a failure be repaired by replanning? |
| `created_at` / `last_validated_at` | timestamps |
| `history` | **append-only** list of `AssumptionTransition` |

Assumptions are **append-only**: `transition(new_state, ...)` records an
`AssumptionTransition(from_state, to_state, reason, evidence, confidence,
timestamp)` and updates the current state. The full trail is always
reconstructable; assumptions are never deleted.

States: `VALID` (believed true), `SATISFIED` (actively confirmed),
`INVALID` (observed false), `UNKNOWN` (not yet established — e.g. a newly
required assumption), `EXPIRED` (validity window lapsed). `INVALID` and
`EXPIRED` are the *failed* states that can make dependent future steps unsafe.

The **`AssumptionRegistry`** is an append-only, id-keyed collection.

---

## Plan lifecycle & the dependency graph

Each plan step declares which assumptions it depends on via
`PlanStep.metadata["assumptions"]` — so `PlanStep`/`Plan` (the H12 replanning
module) are used **unmodified**. The **`AssumptionDependencyGraph`** is built
from that metadata:

```
download → db_reachable
train    → dataset_available
report   → approval
```

`AssumptionDependencyGraph.from_plan(plan)` builds the graph;
`assumptions_for_step(step_id)` and `steps_depending_on(assumption_id)` query
it. Inserted (repair) steps are synced back into the graph.

---

## Observation evaluation

Observations carry assumption effects via **`AssumptionObservation`** (a
`PlanObservation` subclass, so it flows through the existing machinery
unchanged):

- `assumption_signals: Dict[id, state]` — assumptions observed to change.
- `introduces: List[PlanAssumption]` — brand-new required assumptions.

The **`RuleBasedAssumptionEvaluator`** (deterministic) computes, for each
observation, which assumptions were **tested**, which **changed**, which are
**unchanged**, and which were **introduced**:

1. **Explicit signals** set the new state directly (precise / test-friendly).
2. **Heuristic fallback** — for a plain observation with no signals, the
   assumptions the *executed step* depends on become `SATISFIED` on success
   or `INVALID` on failure/blocked.

An observation that neither carries signals nor tests any step assumption
changes nothing — and therefore triggers no replanning.

---

## Validity evaluation algorithm (deterministic)

`PlanValidityEvaluator.evaluate(plan, registry, graph)` returns a
`PlanValidityResult(validity, affected_steps, failed_assumptions,
required_assumptions, reason)`:

```
failed        = assumptions in INVALID/EXPIRED
unrecoverable = failed ∧ mandatory ∧ ¬recoverable
required      = mandatory ∧ (UNKNOWN|INVALID) ∧ introduced-this-run
affected      = FUTURE steps depending on a failed assumption

if unrecoverable:                      PLAN_IMPOSSIBLE
elif no failed and no required:        PLAN_COMPLETED (if no future) else PLAN_VALID
elif no affected and no required:      PLAN_VALID          # selective: failure only hit the past
elif affected == all future:           PLAN_INVALID
else:                                  PLAN_PARTIALLY_VALID
```

Outputs: `PLAN_VALID`, `PLAN_INVALID`, `PLAN_PARTIALLY_VALID`,
`PLAN_COMPLETED`, `PLAN_IMPOSSIBLE`. The current (just-executed) step is
excluded from the future when computing `affected_steps`.

### Dependency analysis & selective invalidation

Only future steps depending on failed assumptions are affected. A failure
whose only dependents are **completed** steps leaves the plan `PLAN_VALID`
(no replanning). When multiple assumptions fail, `affected_steps` is the
union of their dependent future steps — full (`PLAN_INVALID`) vs partial
(`PLAN_PARTIALLY_VALID`).

---

## Decision → replanning

`AssumptionAwareReplanPolicy` (a `ReplanPolicy`) maps validity to a decision:

| Situation | Decision |
|-----------|----------|
| observation reports done / impossible | COMPLETE / ABORT (precedence) |
| `PLAN_IMPOSSIBLE` | ABORT |
| `PLAN_COMPLETED` | COMPLETE |
| `PLAN_INVALID` / `PLAN_PARTIALLY_VALID` | REVISE |
| `PLAN_VALID` | CONTINUE |

Replanning is triggered **only** when assumptions become invalid/expired,
when new mandatory assumptions appear, or when evidence contradicts an
assumption. Abort is deterministic when a mandatory, unrecoverable assumption
fails.

### Selective replanner

`selective_replanner(context, repair=...)` returns a replanner strategy that:

- **preserves** future steps not depending on failed assumptions;
- inserts a `satisfy_<id>` step for each newly-required mandatory assumption
  (declaring that assumption as a dependency);
- re-queues (or, via the optional `repair` callback, replaces) only the
  affected steps;
- never touches completed history.

`build_assumption_aware_runner(agent, context, ...)` wires an
assumption-aware `ReplanningRunner` from these pieces — the replanning
engine, RunBudget and governance are used unmodified.

---

## Interaction with RunBudget (H11)

Assumption evaluation runs under the **existing shared RunBudget** — no new
budget objects are created. `build_assumption_aware_runner` forwards
`run_budget` to the `ReplanningRunner`, so every executed step (and any
model-assisted assumption reasoning) consumes the same cumulative budget.
Rule-based evaluation is deterministic and adds no model calls. All H10–H12
budget guarantees are unchanged.

---

## Abort conditions

Deterministic termination (via `StopReason`):

- **mandatory, unrecoverable assumption fails** → `GOAL_IMPOSSIBLE`
- required dependency disappears permanently → `GOAL_IMPOSSIBLE`
- otherwise the H12 stop conditions still apply (budget, iteration limit,
  stagnation, no valid plan, etc.)

---

## Trace reconstruction

Every iteration appends a `ValidityTraceEntry` to `context.trace`:

```
Original Plan (implicit in plan_before via the H12 trace)
  → Observation
  → Assumption Evaluation (tested / changed / unchanged / introduced)
  → Assumption Transitions (append-only)
  → Validity Decision (+ affected steps + reason)
  → Replanning (optional)
  → Execution continues
```

Each assumption's own `history` is the append-only transition trail.
`format_validity_trace(context)` and `format_assumptions(registry)` render
the whole lifecycle. Every transition is deterministic and reconstructable.

---

## Deterministic guarantees

- The evaluator, validity evaluator, and decision policy are **pure
  functions** of (observation, assumption states, dependency graph).
- Identical observations produce identical validity decisions and
  transitions.
- Timestamps are the iteration index (from `observation.timestamp`), so runs
  are reproducible without wall-clock time.

---

## Quickstart

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, Plan, PlanStep, ObservationStatus,
    ScriptedObservationBuilder, PlanAssumption, AssumptionState,
    AssumptionRegistry, AssumptionDependencyGraph, AssumptionObservation,
    AssumptionContext, build_assumption_aware_runner,
)

plan = Plan.from_steps("produce a report", [
    PlanStep("download", "download", "download data", metadata={"assumptions": ["db"]}),
    PlanStep("train", "train", "train model", metadata={"assumptions": ["data"]}),
    PlanStep("report", "report", "write report", metadata={"assumptions": ["approval"]}),
])

registry = AssumptionRegistry([
    PlanAssumption("db", "database reachable", "resource"),
    PlanAssumption("data", "dataset available", "data"),
    PlanAssumption("approval", "approval obtained", "authorization", mandatory=True),
])
context = AssumptionContext(registry, AssumptionDependencyGraph.from_plan(plan))

runner = build_assumption_aware_runner(
    build_agent(adapter=MockLLMAdapter(default_response="ok"),
                use_llm_for_decomposition=False, max_revisions=0),
    context,
    observation_builder=ScriptedObservationBuilder([
        AssumptionObservation(status=ObservationStatus.SUCCESS,
                              assumption_signals={"data": AssumptionState.INVALID}, goal_progress=0.3),
        AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.6),
        AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=0.8),
        AssumptionObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
    ]),
)
result = runner.run(plan.goal, plan)
print(result.stop_reason, context.trace.entries[0].validity, context.trace.entries[0].affected_steps)
```

See [`examples/assumption_aware_planning.py`](../../examples/assumption_aware_planning.py)
— proves same-observation/different-assumptions → different decisions,
non-invalidating observations → no replanning, and selective invalidation,
with mock adapters and no API key.
