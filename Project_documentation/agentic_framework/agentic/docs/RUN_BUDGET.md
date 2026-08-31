# RunBudget — Cumulative Run-Level Resource Governance (H11)

A single, shared resource envelope for one autonomous workflow.

The per-invocation `BudgetPolicy` (R9, `token_budget.py`) is evaluated
*inside each* `run_with_trace()` call and starts fresh every time. That is
correct for one turn — but an autonomous workflow re-enters
`run_with_trace()` many times (once per loop iteration, once per agent
handoff), so token/cost limits can be honoured per call yet blown
cumulatively.

**`RunBudget` closes that gap.** It is created **once** when a workflow
begins and shared, unchanged, across iterative execution, retries,
agent handoffs, and nested runtime invocations. Every step consumes from
the same object; all counters are monotonic and never reset until the
workflow completes.

This layer adds budgeting only. It does not modify policy, governance,
authorization, TAP, ActionGate, routing, or tool/LLM behaviour.

---

## Lifecycle

```python
from agentic.agentic_framework import (
    RunBudget, RunBudgetLimits, IterativeAgentRunner,
)

# 1. Create ONE budget at the start of the workflow.
budget = RunBudget(RunBudgetLimits(max_model_calls=20, max_total_tokens=8000))

# 2. Hand the SAME object to every runtime entry point.
runner = IterativeAgentRunner(agent, run_budget=budget, max_iterations=10)
result = runner.run("...")          # consumes from `budget`
# ... a later phase, same budget ...
team   = MultiAgentOrchestrator(registry, router, run_budget=budget)
team.run("...")                      # continues consuming from `budget`

# 3. Inspect deterministic outcome.
print(budget.status)                 # ACTIVE | BUDGET_EXHAUSTED | COMPLETED
print(budget.termination_reason)     # e.g. "MODEL_CALL_LIMIT" or None
```

The runtime **never creates a second budget** during iterations, retries,
handoffs, or recursive calls. `IterativeAgentRunner` and
`MultiAgentOrchestrator` call `attach_run_budget(agent, budget)` (idempotent)
and `budget.start()` once, then reserve/record against the object you passed
in.

---

## Dimensions

`RunBudgetLimits` (immutable; `None` = unconstrained) and the cumulative
`RunBudgetUsage` track:

| Dimension | Limit field | Reserved / recorded |
|-----------|-------------|---------------------|
| `model_calls` | `max_model_calls` | **reserved** before each real `adapter.call()` |
| `tool_calls` | `max_tool_calls` | recorded from the trace after each step |
| `prompt_tokens` | `max_prompt_tokens` | recorded after each model call |
| `completion_tokens` | `max_completion_tokens` | recorded after each model call |
| `total_tokens` | `max_total_tokens` | recorded (prompt + completion) |
| `cost` | `max_cost` | recorded after each model call |
| `elapsed_time` | `max_elapsed_s` | ticked from a monotonic clock |
| `iterations` | `max_iterations` | **reserved** before each loop iteration |
| `handoffs` | `max_handoffs` | **reserved** before each agent handoff |

All counters are **monotonically increasing**.

---

## Enforcement: reserve-before-execute

Before an operation runs, the runtime **reserves** the resource:

```python
res = budget.reserve(model_calls=1)   # or iterations=1, handoffs=1
if not res.ok:
    # rejected BEFORE the operation ran; res.reason is deterministic
    ...
```

`reserve()` checks every dimension in a **fixed order** and returns the
first violation without mutating any counter. On success it increments the
requested discrete counters. Cumulative dimensions (tokens/cost/time) are
recorded *after* the operation that produced them via `record_usage()`; if
that pushes a dimension over its limit the status flips to
`BUDGET_EXHAUSTED` so the **next** reservation gate blocks.

### Enforcement granularity per dimension

- **`model_calls`, `iterations`, `handoffs`** — hard reserve-before-execute.
  The operation is rejected *before it begins*. At the model-call seam a
  rejected reservation raises `BudgetExhausted` (a `BaseException`, so it
  unwinds cleanly past the runtime's internal `except Exception` fallbacks)
  and is caught at the workflow boundary.
- **`tool_calls`, `prompt/completion/total_tokens`, `cost`, `elapsed_time`** —
  cumulative. Recorded after the step that produced them; the gate blocks the
  *next* step. (These values are only known once the operation completes, so
  they cannot be reserved exactly beforehand.)

The result: `model_calls` / `iterations` / `handoffs` stop **exactly** at the
configured limit; the cumulative dimensions terminate the workflow at the
next step boundary after the limit is crossed.

### Deterministic termination

When exhausted, the workflow terminates gracefully and never continues:

```
status = BUDGET_EXHAUSTED
reason = MODEL_CALL_LIMIT
```

`TerminationReason` values: `MODEL_CALL_LIMIT`, `TOOL_CALL_LIMIT`,
`PROMPT_TOKEN_LIMIT`, `COMPLETION_TOKEN_LIMIT`, `TOKEN_LIMIT`, `COST_LIMIT`,
`TIME_LIMIT`, `ITERATION_LIMIT`, `HANDOFF_LIMIT`. The loop / orchestrator
surface this as `result.stop_reason == "budget_exhausted"` and
`result.termination_reason == "<REASON>"`.

---

## Shared budget architecture

```
              ┌──────────────── RunBudget (created once) ────────────────┐
              │  usage: model_calls, tool_calls, tokens, cost, time,     │
              │         iterations, handoffs   (monotonic, never reset)  │
              └───────▲──────────────────▲───────────────────▲──────────┘
                      │ reserve/record   │ reserve/record    │ reserve
        BudgetedAdapter (per model call) │        IterativeAgentRunner   MultiAgentOrchestrator
                      │                  │        (reserve iterations)   (reserve handoffs)
             agent.llm / generator.llm   trace.actions_executed
```

- `BudgetedAdapter` wraps the agent's shared adapter (installed by
  `attach_run_budget`) and repoints both `agent.llm` and
  `agent.generator.llm` at the wrapper, so **every** model call — decomposition
  and generation alike — is counted, without modifying `agent.py`.
- The loop reserves `iterations`; the orchestrator reserves `handoffs`.
- `tool_calls` are recorded from the governed trace's `actions_executed`.

---

## Trace output

Every executed step appends `budget.snapshot()` to `result.budget_timeline`,
and `result.run_budget` is the live object. A snapshot reconstructs complete
resource consumption:

```python
snap = budget.snapshot()
# {
#   "status": "BUDGET_EXHAUSTED",
#   "termination_reason": "MODEL_CALL_LIMIT",
#   "limits":   {...},
#   "consumed": {"model_calls": 5, "tool_calls": 3, "total_tokens": 992, ...},
#   "remaining":{"model_calls": 0, ...},
#   "violations":[{"dimension":"model_calls","reason":"MODEL_CALL_LIMIT","limit":5,"consumed":5,...}],
# }
```

`format_run_budget(budget)` renders a readable table (consumed / limit /
remaining per dimension, plus violations).

---

## Accounting examples

### Iterations consume cumulatively

```
Iteration 1  → model call #1
Iteration 2  → model call #2
Iteration 3  → model call #3   (max_model_calls = 3)
Iteration 4  → blocked before execution   → BUDGET_EXHAUSTED / MODEL_CALL_LIMIT
```

### Handoffs share one budget

```
Budget: max_model_calls = 5
Agent A turn 1,2,3   → model calls 1,2,3
handoff to Agent B
Agent B turn 4,5     → model calls 4,5
Agent B turn 6       → blocked before execution → BUDGET_EXHAUSTED / MODEL_CALL_LIMIT
```

Agent A and Agent B draw from the **same** object; the handoff does not buy
fresh budget.

---

## Failure modes (all deterministic)

| Scenario | `termination_reason` |
|----------|----------------------|
| Budget already spent before an iteration | matching dimension limit |
| Budget spent during a handoff | `MODEL_CALL_LIMIT` / `HANDOFF_LIMIT` |
| Token exhaustion | `TOKEN_LIMIT` (or prompt/completion) |
| Cost exhaustion | `COST_LIMIT` |
| Time exhaustion | `TIME_LIMIT` |
| Iteration cap reached | `ITERATION_LIMIT` |
| Handoff cap reached | `HANDOFF_LIMIT` |

---

## Relationship to `BudgetPolicy` (R9)

`BudgetPolicy` is unchanged and still enforced **inside** a single
`run_with_trace()` call (per-turn token/cost cap). `RunBudget` is the
**run-level** envelope spanning the whole workflow. They compose: pass
`budget_policy=` for per-turn caps and `run_budget=` for the cumulative
envelope. `RunBudget` does not alter `BudgetPolicy` behaviour.

---

## Example

See [`examples/run_budget_workflow.py`](../../examples/run_budget_workflow.py)
— an iterate-until-done loop and a multi-agent team, each bounded by a single
shared `RunBudget`, run with mock adapters and no API key.
