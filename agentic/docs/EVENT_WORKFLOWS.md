# Event-Driven Execution & Long-Lived Workflows (H17)

Turns the bounded, continuous execution engine (H10–H16) into a **persistent
orchestration engine**: a workflow can suspend, wait for an external event, and
resume deterministically — without losing state or violating any governance
guarantee from the earlier phases.

```
Mission → Execute → WAIT → External Event → Resume → Continue → Complete
```

Execution is no longer assumed to be continuous. This is the point where the
runtime evolves from a bounded execution engine into a persistent orchestration
engine.

This layer adds orchestration over time only. It does not modify H10–H16,
RunBudget, WorkingMemory, hierarchical planning, coordination, replanning, plan
validity, governance, authorization, ActionGate, TAP, tool execution, or LLM
providers — it composes on their public APIs. Everything is deterministic and
in-process.

Excluded by design: distributed queues, Kafka, webhooks, cloud schedulers,
async networking, cross-process retries.

---

## Workflow model

A **`WorkflowInstance`** is a long-lived, suspendable execution of one mission:

| Field | Meaning |
|-------|---------|
| `workflow_id` | identity |
| `plan` | the H15 `MissionPlan` (goal tree) |
| `current_goal` | the goal currently gating progress (when WAITING) |
| `status` | lifecycle status |
| `waiting_conditions` | the active `WaitCondition`s it is suspended on |
| `memory` | the shared H14 `WorkingMemory` |
| `assumption_context` | the shared H13 `AssumptionContext` (optional) |
| `run_budget` | the shared H11 `RunBudget` |
| `created_at`, `resumed_at` | timestamps |
| `history`, `trace`, `event_log` | append-only reconstruction |

---

## Workflow lifecycle

`CREATED → RUNNING → WAITING → RESUMED → COMPLETED | FAILED | CANCELLED | EXPIRED`.
Transitions are append-only; history is immutable. `WAITING ⇄ RESUMED` may repeat
many times over a long-lived mission.

---

## Event model

A **`WorkflowEvent`** carries identity/payload plus deterministic **effects** on
shared state applied *before* execution resumes:

| Field | Meaning |
|-------|---------|
| `event_id`, `type` | identity + kind (`approval_received`, `file_uploaded`, `timeout`, …) |
| `payload` | matched against a wait condition's `match` |
| `timestamp`, `source`, `confidence` | provenance |
| `memory_writes`, `memory_invalidations` | H14 effects |
| `assumption_signals`, `introduces` | H13 effects |

---

## Wait conditions

A **`WaitCondition`** is a first-class, deterministic gate on a goal:

| Field | Meaning |
|-------|---------|
| `condition_id`, `goal_id` | identity + the gated goal |
| `kind` | `WAIT_FOR_APPROVAL` / `WAIT_FOR_FILE` / `WAIT_FOR_TIMER` / `WAIT_FOR_EVENT` |
| `event_type` | the event type that can satisfy it |
| `match` | key/value pairs the event payload must contain (subset match) |
| `min_confidence` | minimum event confidence to accept |
| `on_timeout` | `satisfy` (proceed) or `fail` (fail the gated goal) |

When a READY goal (dependencies + assumptions cleared) has an unsatisfied wait
condition, the workflow suspends without losing state. A pending wait takes
precedence over an invalid assumption, because the awaited event may itself
satisfy the assumption.

---

## Suspension & resume

`WorkflowEngine.start(wf)` runs the workflow (driving the H15 goal tree through
the **unchanged** H16 coordinator, wave by wave) until it either completes or
reaches a goal gated by an unsatisfied wait condition — then it transitions to
`WAITING` and stops.

`WorkflowEngine.deliver(event)` implements the resume engine:

1. **Match** waiting workflows (deterministic routing, creation order): a
   workflow matches only if it is `WAITING` and holds a wait condition the event
   satisfies (type + payload subset + confidence).
2. **Validate** the event against the condition.
3. **Update `WorkingMemory`** — apply `memory_writes` / `memory_invalidations`
   (H14, versioned, traceable).
4. **Re-evaluate assumptions** — apply `assumption_signals` / `introduces` via
   H13's append-only `transition()` / registry (unchanged).
5. **Replan if necessary** — a failure or timeout may trigger the optional H15
   localized subtree replanner (H12 semantics).
6. **Continue execution** — `RESUMED → RUNNING`, advancing only the newly
   unblocked goals.

A **non-matching event leaves the workflow WAITING** (recorded as `WRONG_EVENT`).
`fire_timeout(wf, condition_id)` deterministically fires a timeout for one waiting
condition (satisfy or fail per `on_timeout`).

---

## Interaction with the earlier phases

- **H16 coordination (unchanged):** each advance builds an H16 `Mission` from the
  currently-ready goals and calls `Coordinator.run(...)` as-is; capability,
  authority, ownership, and budget checks all still apply.
- **H15 hierarchy (unchanged):** the workflow drives the same `GoalTree`; only
  goals whose dependencies + assumptions are cleared and whose wait is satisfied
  execute — so resume advances **only the affected subtree**. Independent waiting
  subtrees stay suspended until their own event arrives.
- **H14 memory (unchanged):** all goals and events share one `WorkingMemory`;
  events write new versions and are recorded with `producing_step=event:<id>`.
- **H13 assumptions (unchanged):** events satisfy / invalidate / introduce
  assumptions through H13's public API; an invalidation gates the affected
  subtree via the same inheritance rules as H15.
- **H11 budget (unchanged):** **waiting consumes no budget** — while suspended the
  engine makes no coordinator call, so no reserves or model calls occur. Resume
  continues on the *same* `RunBudget`; no new budget is created.

---

## Trace reconstruction

`WorkflowTrace` appends an entry for every lifecycle step:
`STARTED → WAVE(s) → SUSPENDED → EVENT → RESUMED → WAVE(s) → COMPLETED`
(with `WRONG_EVENT`, `TIMEOUT`, `REPLANNED`, `FAILED` as they occur). Combined
with the append-only workflow status `history`, the goal-tree node histories, and
the per-wave H16 `CoordinationResult`s, the entire long-lived lifecycle
reconstructs deterministically. `WorkflowInstance.to_dict()` serialises it all;
`format_workflow_trace(wf)` renders it.

---

## Deterministic guarantees

- Routing, matching, classification, and effect application are pure functions of
  the workflows, events, and prior state.
- The same event sequence always produces the same workflow history.
- All timestamps come from the events/creation (no wall clock, no randomness).

---

## Quickstart

```python
from agentic.agentic_framework import (
    WorkingMemory, RunBudget, RunBudgetLimits,
    AgentProfile, CapabilityRegistry, ScriptedWorker, WorkerResult,
    Goal, StaticDecomposer,
    WorkflowEngine, WaitCondition, WaitKind, WorkflowEvent, EventType, MemoryWrite,
)

registry = CapabilityRegistry()
registry.register(AgentProfile("ops", capabilities=frozenset({"do"}), trust_level=5),
                  ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))

plan = StaticDecomposer().decompose("close_deal", [
    Goal("collect", "collect docs", required_capabilities=frozenset({"do"}), expected_outputs=("docs",), priority=1),
    Goal("finalize", "finalize", required_capabilities=frozenset({"do"}), dependencies=("collect",), expected_outputs=("contract",), priority=2),
])

engine = WorkflowEngine(registry)
wf = engine.create_workflow("deal_42", plan, WorkingMemory(), run_budget=RunBudget(RunBudgetLimits()),
                            wait_conditions=[WaitCondition("await_approval", "finalize",
                                                           kind=WaitKind.WAIT_FOR_APPROVAL,
                                                           event_type=EventType.APPROVAL_RECEIVED,
                                                           match=(("deal", "42"),))])

engine.start(wf)                 # runs 'collect', then WAITING on approval
# ... hours or days later ...
engine.deliver(WorkflowEvent("appr", EventType.APPROVAL_RECEIVED, {"deal": "42"}, timestamp=2,
                             memory_writes=[MemoryWrite("approval", "signed")]))
print(wf.status)                 # COMPLETED
```

See [`examples/event_driven_workflow.py`](../../examples/event_driven_workflow.py)
— suspend/resume, non-matching events, memory + assumption effects, and
subtree-selective resume, with scripted workers and no API key.
