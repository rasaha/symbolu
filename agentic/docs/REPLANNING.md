# Observation-Driven Replanning (H12)

Bounded **adaptive** autonomous execution. The runtime changes its *future*
plan based on structured observations — while never rewriting completed work
and staying inside the shared `RunBudget` (H11).

This is the step from *bounded autonomous execution* (repeat safely under a
budget) to *bounded adaptive autonomous execution* (change the plan in
response to what you observe).

This layer adds replanning only. It does not modify governance,
authorization, ActionGate, TAP, routing, tool execution, LLM providers, or
the budget implementation. Excluded by design: parallel agents, graph
orchestration, negotiation, shared memory, distributed planning, learning/RL.

---

## The loop

```
Goal → Plan → Execute Step → Observation → Evaluate
                                              │
                   ┌──────────────┬───────────┼───────────┐
                CONTINUE        REVISE       ABORT      COMPLETE
              (plan valid)  (change future)(impossible)(goal met)
```

Three things are kept strictly separate:

- **History** — completed / failed / removed steps. **Immutable.** Revision
  never touches them.
- **Future** — pending steps. The replanning engine may reorder, remove,
  insert, or modify *only these*.
- **Decision** — a deterministic verdict derived solely from the structured
  observation.

---

## Observation lifecycle

After each executed step the runtime builds a **`PlanObservation`** — the
*only* input that drives the replanning decision and stagnation detection:

| Field | Meaning |
|-------|---------|
| `status` | `success` / `partial` / `failure` / `blocked` / `constraint` / `impossible` |
| `summary` | short human-readable description |
| `evidence` | supporting details |
| `tool_results` | results returned by the step's tools |
| `goal_progress` | `[0.0, 1.0]` estimate of progress |
| `new_constraints` | restrictions discovered during the step |
| `confidence` | `[0.0, 1.0]` |
| `timestamp` | sequence index (set by the runner) |

Observations are produced by an **`ObservationBuilder`**:

- `DefaultObservationBuilder` — derives a best-effort observation from the
  governed `AgentRunTrace` (status from error/blocked/actions; tool results
  from the agent's goal-state).
- `ScriptedObservationBuilder` — returns pre-scripted observations in order;
  deterministic, used for tests/demos and for proving "same goal, different
  observations → different plans".

`PlanObservation.signature()` is a hashable fingerprint (status, summary,
constraints, progress) used for stagnation detection — deliberately excluding
`timestamp`/`confidence` so a genuinely repeated observation compares equal.

---

## Plan lifecycle

A **`Plan`** is explicit and inspectable, split into two lists:

- `history: List[PlanStep]` — append-only; completed / failed / removed steps.
- `future: List[PlanStep]` — ordered pending steps.

Each **`PlanStep`** carries `objective`, `action`, `expected_outcome`,
`state`, `dependencies`, and `metadata` (with `inserted` flagged on steps
added during revision).

The runtime always knows: `completed_steps()`, `pending_steps()`,
`removed_steps()`, `inserted_steps()`. Execution transition:
`mark_executed(step, state)` moves a step from `future` into immutable
`history`. `next_step()` returns the first pending step whose dependencies
are all completed.

---

## Replanning algorithm

```
for each iteration (bounded by max_iterations):
    reserve one iteration from the shared RunBudget      # H11
    step = plan.next_step()                              # dependency-aware
    trace = agent.run_with_trace(step.action)            # governed execution
    observation = observation_builder.build(...)         # structured
    decision, reason = policy.decide(goal, plan, observation)   # deterministic
    plan.mark_executed(step, COMPLETED or FAILED)        # history is append-only
    if decision == REVISE and revisions < max_revisions:
        new_future = replanner.revise(goal, plan, observation)   # FUTURE only
        plan.apply_revision(new_future)                  # dropped→REMOVED, new→inserted
    record trace entry (plan_before, observation, decision, reason, plan_after)
    if decision == COMPLETE: stop GOAL_COMPLETED (discard remaining future)
    if decision == ABORT:    stop GOAL_IMPOSSIBLE
    if stagnation detected:  stop with its reason
    if budget exhausted:     stop BUDGET_EXHAUSTED
    if plan exhausted:       stop GOAL_COMPLETED / NO_VALID_PLAN
```

### Decision engine (`DeterministicReplanPolicy`)

Reads only the observation (plus whether pending steps remain):

- `IMPOSSIBLE` → **ABORT**
- `SUCCESS` and `goal_progress ≥ completion_threshold` (default `1.0`) → **COMPLETE**
- `SUCCESS` with no pending steps left → **COMPLETE**
- `new_constraints` present, or status in `FAILURE` / `BLOCKED` / `CONSTRAINT` → **REVISE**
- otherwise → **CONTINUE**

The decision is a pure function of the observation — same observation, same
decision, every time.

### Replanning engine (`RuleBasedReplanner`)

Bounded and **future-only**. A caller-supplied `strategy(plan, observation)
-> List[PlanStep]` returns the new future step list. The engine then:

- preserves all `history` steps exactly (completed / failed);
- marks dropped pending steps `REMOVED` (kept in history for the audit trail);
- flags genuinely new steps `inserted`;
- reorders / replaces the `future`.

It may reorder remaining steps, remove invalid steps, insert replacement
steps, and modify future actions — but it **never rewrites execution
history**, and completed steps are immutable.

---

## Revision constraints

Every revision preserves: completed work, governance decisions (each step
still runs through the governed path), authorization history, the audit
trail, and the cumulative `RunBudget`. **No replanning resets runtime
state.** History is append-only; revision touches only `future`.

---

## Interaction with RunBudget (H11)

All replanning occurs under the **existing shared RunBudget** — it is never
re-created. `ReplanningRunner` calls `attach_run_budget(agent, run_budget)`
(idempotent) and `run_budget.start()` once, then:

- reserves one **iteration** before each step (reserve-before-execute);
- each governed execution consumes **model calls** / tokens / cost through the
  budgeted adapter;
- records **tool calls** from the trace after each step.

Every revised execution continues accounting from existing usage. When a
limit is hit the run stops with `stop_reason = BUDGET_EXHAUSTED` and the
budget's deterministic `termination_reason`.

Model-backed planning (if you plug in a model-driven replanner) consumes the
same budget; rule-based planning is deterministic and free.

---

## Stop conditions

Every termination is explicit (`StopReason`):

| Reason | When |
|--------|------|
| `GOAL_COMPLETED` | observation `COMPLETE`, or all steps done without failures |
| `GOAL_IMPOSSIBLE` | observation `ABORT` (`status=impossible`) |
| `NO_VALID_PLAN` | revision left nothing to do, or `max_revisions` exceeded |
| `BUDGET_EXHAUSTED` | the shared RunBudget rejected an operation |
| `ITERATION_LIMIT` | `max_iterations` reached |
| `REPEATED_FAILURES` | consecutive-failure threshold crossed |
| `NO_PROGRESS` | `goal_progress` flat for N steps |
| `STAGNATION_DETECTED` | same observation, or same revised plan, repeated |

---

## Stagnation detection

`StagnationDetector` deterministically flags repeated ineffective execution,
with configurable `StagnationConfig` thresholds:

- **same observation repeated** `max_repeated_observations` times → `STAGNATION_DETECTED`
- **consecutive failures** `max_consecutive_failures` → `REPEATED_FAILURES`
- **no measurable progress** for `max_no_progress` steps → `NO_PROGRESS`
- **same revised plan** produced `max_repeated_plans` times → `STAGNATION_DETECTED`

All are pure counters over the observation/plan signatures — deterministic and
reconstructable.

---

## Trace reconstruction

Every executed step appends a trace entry, and every revision is recorded as
a `PlanRevision`. Each entry reconstructs the full story:

```
Original Plan (plan_before)
  → Observation
  → Decision + Reason
  → Revised Plan (plan_after)
  → Execution continues
```

`ReplanningResult` exposes `trace` (per-step), `revisions` (per-revision
with before/after plan snapshots), `decisions`, the final `plan.snapshot()`,
`run_budget`, and `budget_timeline`. `format_replanning_trace(result)`
renders the whole sequence.

---

## Quickstart

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, Plan, PlanStep, PlanObservation,
    ObservationStatus, ReplanningRunner, RuleBasedReplanner,
    ScriptedObservationBuilder, RunBudget, RunBudgetLimits,
)

agent = build_agent(adapter=MockLLMAdapter(default_response="ok"),
                    use_llm_for_decomposition=False, max_revisions=0)

plan = Plan.from_steps("produce a report", [
    PlanStep("collect", "collect data", "collect the raw data"),
    PlanStep("analyze", "analyze data", "analyze it"),
    PlanStep("report", "write report", "write the report"),
])

# Insert a constraint-handling step whenever an observation reports one.
def strategy(plan, obs):
    if obs.new_constraints:
        return [PlanStep("satisfy", "satisfy", "satisfy " + obs.new_constraints[0])] + list(plan.future)
    return list(plan.future)

runner = ReplanningRunner(
    agent,
    replanner=RuleBasedReplanner(strategy),
    observation_builder=ScriptedObservationBuilder([
        PlanObservation(status=ObservationStatus.SUCCESS, new_constraints=["needs_approval"], goal_progress=0.4),
        PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=0.7),
        PlanObservation(status=ObservationStatus.SUCCESS, goal_progress=1.0),
    ]),
    run_budget=RunBudget(RunBudgetLimits(max_model_calls=20)),
)
result = runner.run("produce a report", plan)
print(result.stop_reason, [s.step_id for s in result.plan.completed_steps()])
```

See [`examples/observation_driven_replanning.py`](../../examples/observation_driven_replanning.py)
— proves same-goal/different-observations → different plans, tool-failure
recovery, and shared-budget accounting, with mock adapters and no API key.
