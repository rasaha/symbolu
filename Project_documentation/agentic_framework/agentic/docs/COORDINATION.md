# Authority-Aware Multi-Agent Coordination (H16)

Governed multi-agent coordination: a deterministic **coordinator** assigns
mission goals to **worker** agents through explicit authority, capability, and
immutable delegation contracts, while every agent shares the same H14
`WorkingMemory` and the same H11 `RunBudget`.

```
Mission → Coordinator → Assign Goal → Worker Agent → Shared State
       → Coordinator → Next Assignment
```

This is the step from *sequential agent handoff* to *governed collaborative
execution*: agents now have explicit roles, capabilities, permissions, and
contracts, so delegation knows **who is allowed to do what**.

> **Note on H15.** H16 was built before H15 and is deliberately
> **planning-strategy agnostic** — the coordinator advances a mission's goals
> and sits below any planner. H15 (hierarchical planning) was subsequently
> added and plugs into this coordinator **without any change to it**; see
> [Hierarchical Planning (H15)](./HIERARCHICAL_PLANNING.md).

This layer adds coordination only. It does not modify RunBudget, WorkingMemory,
replanning, plan validity, governance, authorization, ActionGate, TAP, routing,
tool execution, or LLM providers — it composes on their public APIs.

Excluded by design: autonomous organization creation, self-modifying agents,
voting, negotiation, reinforcement learning.

---

## Three separated concerns

- **coordination** — the `Coordinator` chooses who does what. It **never**
  executes a worker task itself.
- **execution** — worker agents run the delegated goal under the shared memory
  and shared budget.
- **authorization** — every assignment must pass capability, authority, budget,
  and goal-ownership checks *before* a worker runs.

---

## Agent model & capability registry

An **`AgentProfile`** is immutable during execution:

| Field | Meaning |
|-------|---------|
| `agent_id` | unique identifier |
| `role` | human-readable role |
| `capabilities` | what the agent can do (`search`, `summarize`, `invoke`, …) |
| `permissions` | authority the agent holds (`pii_access`, …) |
| `owned_tools` | tools the agent owns |
| `supported_goals` | goal types it accepts (empty = any) |
| `execution_limits` | per-agent limits |
| `trust_level` | tiebreak / ranking |

The **`CapabilityRegistry`** maps each agent id to its profile and a
`WorkerExecutor`, and tracks availability. `candidates_for(goal)` returns the
agents that support the goal and hold the required capabilities, ordered
deterministically by `(-trust_level, agent_id)` so selection is reproducible.

---

## Authority model

Every assignment is authorized by the deterministic **`AuthorityModel`**,
which evaluates checks in a fixed order and returns the first failure:

1. **goal support** — the agent supports the goal type (`GOAL_UNSUPPORTED`);
2. **capability** — `goal.required_capabilities ⊆ agent.capabilities` (`CAPABILITY_MISMATCH`);
3. **authority** — `goal.authority_scope ⊆ agent.permissions` (`AUTHORITY_DENIED`);
4. **ownership** — the goal is not already owned by a worker (`OWNERSHIP_CONFLICT`);
5. **budget** — the shared `RunBudget` can afford the delegation (`BUDGET_EXHAUSTED`).

Failure produces a deterministic rejection with an explicit reason.

---

## Delegation contract (immutable)

Each delegation is governed by an immutable **`DelegationContract`**:

```
contract_id, goal_id, goal_description, assigned_agent,
required_inputs, expected_outputs, required_memory, assumptions,
authority_scope, timeout, completion_criteria
```

The coordinator builds one contract per delegation and passes it to the
worker's executor. Contracts are `frozen` — they cannot change after issue.

---

## Coordinator lifecycle

For each goal (respecting `depends_on`):

1. gate on the shared budget;
2. `candidates_for(goal)` → deterministic list of qualified agents;
3. for each candidate, `AuthorityModel.authorize(...)` → the first authorized
   agent is selected (rejections are recorded);
4. **reserve** the delegation from the shared budget (the `handoffs` dimension);
5. issue the `DelegationContract`, create an `AgentAssignment`, transfer goal
   ownership to the worker, and advance the assignment through its lifecycle;
6. invoke the worker's `WorkerExecutor.execute(contract, memory, budget)` — the
   coordinator itself runs nothing;
7. on **success**, commit the declared outputs to shared memory and return goal
   ownership to the coordinator; on **failure / timeout / unavailable**, recover
   by trying the next qualified candidate.

Assignment lifecycle (append-only): `CREATED → ASSIGNED → ACCEPTED → EXECUTING
→ COMPLETED | FAILED | CANCELLED`.

---

## Goal ownership

`GoalOwnershipLedger` guarantees **every active goal has exactly one owner**.
Initially the coordinator owns every mission goal. A delegation explicitly
transfers ownership to the worker; completion (or any failure) transfers it
back. A second delegation of a worker-owned goal is rejected
(`OWNERSHIP_CONFLICT`). Every transfer is recorded and reconstructable.

---

## Shared working memory

All participating agents share the **one** `WorkingMemory` instance passed to
the coordinator — no local copies, no divergent private state. Worker outputs
are committed to that store by the coordinator (on success only), so
downstream agents read the same governed, versioned state (H14 semantics).

---

## Failure handling (deterministic)

| Failure | Handling |
|---------|----------|
| capability mismatch | no qualified agent → goal fails |
| authority denied | candidate rejected; try next; else goal fails |
| agent unavailable (`WorkerUnavailable`) | mark unavailable; recover to next candidate |
| delegation timeout (`timed_out` or `duration > timeout`) | assignment FAILED; recover to next candidate |
| worker failure (`success=False`) | assignment FAILED; **outputs not committed**; recover |
| budget exhaustion | mission stops with `BUDGET_EXHAUSTED` |

A mandatory goal that no candidate can complete fails the mission
(`MISSION_FAILED`). Crucially, **a failed worker never writes to shared
memory** — the coordinator commits declared outputs only on success, so
failures cannot corrupt shared state or execution history.

---

## Replanning integration

Worker observations flow into the existing H12/H13 machinery unchanged (a
worker can itself be an assumption-aware replanning runner). After collecting a
result the coordinator may continue, delegate elsewhere, or — using the
unmodified replanning engine — abort. The replanning engine is not touched.

---

## Budget integration

The entire coordination shares **one** `RunBudget`. The coordinator attaches it
to every `AgentWorker`'s agent (via H11's `attach_run_budget`), reserves one
`handoffs` unit per delegation, and each worker's model calls are counted on the
same budget. Delegation never creates a new budget object; all agents consume
from the same execution envelope, and exhaustion stops the mission
deterministically.

---

## Trace reconstruction

`CoordinationTrace` appends a `CoordinationTraceEntry` for every decision:

```
Mission → Coordinator → Delegation (contract) → Worker (result)
       → Memory Update → Ownership Transfer → Coordinator Decision
```

Each entry records the goal, the selected agent (and any rejections), the
contract, the worker result, the memory writes, the ownership transfer, and the
resulting state. `CoordinationResult.to_dict()` serialises the whole mission —
assignments, ownership ledger, trace, and budget snapshot — so every delegation
is reconstructable. `format_coordination_trace(result)` renders it.

---

## Deterministic guarantees

- Candidate ordering, authority checks, and selection are pure functions of the
  registry, mission, budget, and ownership ledger.
- The same mission against the same registry produces identical assignments,
  ownership transfers, and traces.
- No wall-clock time or randomness is used.

---

## Quickstart

```python
from agentic.agentic_framework import (
    WorkingMemory, RunBudget, RunBudgetLimits,
    AgentProfile, CapabilityRegistry, CoordinationGoal, Mission, Coordinator,
    ScriptedWorker, WorkerResult,
)

registry = CapabilityRegistry()
registry.register(AgentProfile("research", capabilities=frozenset({"search"}), trust_level=5),
                  ScriptedWorker(WorkerResult(success=True, outputs={"findings": "..."})))
registry.register(AgentProfile("writer", capabilities=frozenset({"write"}),
                               permissions=frozenset({"pii_access"})),
                  ScriptedWorker(WorkerResult(success=True, outputs={"report": "report.pdf"})))

mission = Mission.of("report", [
    CoordinationGoal("g1", "research", required_capabilities=frozenset({"search"}), expected_outputs=("findings",)),
    CoordinationGoal("g2", "write PII report", required_capabilities=frozenset({"write"}),
                     authority_scope=frozenset({"pii_access"}), required_memory=("findings",), expected_outputs=("report",)),
])

memory = WorkingMemory()
result = Coordinator(registry, memory, run_budget=RunBudget(RunBudgetLimits())).run(mission)
print(result.status, memory.peek("report").value)
```

See [`examples/authority_aware_coordination.py`](../../examples/authority_aware_coordination.py)
— capability selection, authority rejection, worker-failure recovery, shared
memory + budget, and full trace reconstruction, with scripted workers and one
real governed `AgentWorker`, no API key.
