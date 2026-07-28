# Agentic Framework

A code-first Python framework for building **governed** agentic
applications on top of any LLM.

Every action an agent takes is observable, auditable, and
controllable — turn-level safety gating, per-tool risk
classification, human-in-the-loop approvals, budget enforcement,
and full event tracing are wired into the execution path, not
bolted on.

---

## Quickstart

```bash
pip install -e .
```

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, ToolSpec, ToolRiskLevel, format_trace,
)

agent = build_agent(
    adapter=MockLLMAdapter(default_response="Python is versatile."),
    tools={
        "search": ToolSpec(
            handler=lambda p: [f"Result for: {p.get('query', '')}"],
            description="Search for information",
            risk_level=ToolRiskLevel.READ_ONLY,
        ),
    },
)
agent.new_session()

trace = agent.run_with_trace("Tell me about Python")
print(format_trace(trace))
```

No API keys or GPU required. Replace `MockLLMAdapter` with
`OpenAIAdapter`, `AnthropicAdapter`, or `MistralCGAdapter` to use
a real LLM — no other wiring changes needed.

---

## Who is this for?

- **AI / backend engineers** building agent-powered features that
  need governed execution, not just "call the LLM and hope."
- **Platform engineers** who need approval workflows, budget caps,
  and audit trails on agentic actions.
- **Teams evaluating agent frameworks** who want runtime control
  that goes beyond tool calling and prompt loops.

---

## Key capabilities

| Capability | What it does | Status |
|-----------|-------------|--------|
| **Governed execution** | Two-layer safety: turn-level `SafetyGate` + per-tool `SafeMCPGateway` with risk classification | Tested (1550+ tests) |
| **Human-in-the-loop approvals** | `ApprovalPolicy` gates actions by type; callback receives approve/deny decision | Tested + 2 pilots |
| **Budget enforcement** | Hard caps on tokens and cost; budget exceeded is a terminal event | Tested |
| **Streaming events** | 17 structured event types covering the full agent lifecycle | Tested |
| **Tracing** | `AgentRunTrace` captures every event; `format_trace()` renders readable output | Tested |
| **Structured outputs** | Schema-enforced responses with dataclass, dict, or Pydantic validation | Tested |
| **Tool discovery** | `ToolCatalog` — read-only introspection with filtering by risk, capability, confirmation | Tested |
| **Async + cancellation** | Cooperative cancellation at action boundaries via `CancellationToken` | Tested |
| **Approval coverage** | `describe_approval_coverage()` shows which actions are gated before running | Tested |
| **Signal enrichment** | CG-capable adapters enrich governance with model-internal entropy/coherence signals | Tested (CG path operator-validated) |

---

## How governed execution works

```
user_input
    ↓
GoalDecomposition → ActionItems
    ↓
ReflectiveGenerator → LLM response (optional self-revision)
    ↓
SafetyGate → eligible actions (turn-level pre-gate)
    ↓
For each action:
    ├── Cancellation check
    ├── Budget check
    ├── Approval gate
    ├── ACTION_STARTED → execute via SafeMCPGateway → ACTION_COMPLETED
    ↓
RUN_COMPLETED + AgentRunTrace
```

The action loop ordering is fixed and tested: cancellation →
budget → approval → execute. This is not configurable — it is
part of the runtime contract.

---

## Examples

| Example | What it shows |
|---------|--------------|
| [`minimal_governed_agent.py`](../../examples/minimal_governed_agent.py) | **Start here.** Build + run + trace in ~10 lines |
| [`first_governed_agent.py`](../../examples/first_governed_agent.py) | Streaming events + tool discovery |
| [`governed_agent_with_approval_and_budget.py`](../../examples/governed_agent_with_approval_and_budget.py) | Approval gates + budget + structured output |
| [`pilot_research_assistant.py`](../../examples/pilot_research_assistant.py) | **Pilot 1:** Custom tools, approval, budget, structured output, audit |
| [`pilot_internal_copilot.py`](../../examples/pilot_internal_copilot.py) | **Pilot 2:** Per-action-type approval boundary, approve + deny paths |
| [`iterate_until_done_agent.py`](../../examples/iterate_until_done_agent.py) | **Iterate-until-done:** governed re-planning loop — tool results fed back, controller decides DONE vs CONTINUE, bounded by `max_iterations`/budget |
| [`multi_agent_handoff.py`](../../examples/multi_agent_handoff.py) | **Multi-agent:** researcher → writer → reviewer handoff, each a fully governed agent, bounded by `max_handoffs` |
| [`run_budget_workflow.py`](../../examples/run_budget_workflow.py) | **Cumulative RunBudget (H11):** one shared budget across iterations + handoffs, deterministic `BUDGET_EXHAUSTED` termination |
| [`observation_driven_replanning.py`](../../examples/observation_driven_replanning.py) | **Replanning (H12):** same goal + different observations → different plans; tool-failure recovery; reconstructable revision trace |
| [`assumption_aware_planning.py`](../../examples/assumption_aware_planning.py) | **Plan validity (H13):** same observation + different assumptions → different decisions; non-invalidating observations skip replanning; selective invalidation |
| [`working_memory_continuity.py`](../../examples/working_memory_continuity.py) | **Working memory (H14):** stored state drives outcomes; versioned append-only records; cross-agent sharing; memory→assumption bridge |
| [`authority_aware_coordination.py`](../../examples/authority_aware_coordination.py) | **Coordination (H16):** capability + authority delegation; worker-failure recovery; goal-ownership transfers; one shared memory + budget |
| [`hierarchical_planning.py`](../../examples/hierarchical_planning.py) | **Hierarchical planning (H15):** deterministic goal tree; dependency release; H16 reused unchanged; localized subtree replanning |
| [`event_driven_workflow.py`](../../examples/event_driven_workflow.py) | **Event workflows (H17):** suspend on wait condition; resume on matching event (memory + assumption effects); waiting is budget-free; subtree-selective resume |
| [`durable_workflow_recovery.py`](../../examples/durable_workflow_recovery.py) | **Durability (H18):** checkpoint, destroy runtime, restore from disk, resume without re-running; cross-restart idempotency; corruption rejected |

Run any example from the repo root:

```bash
python examples/minimal_governed_agent.py
python examples/pilot_internal_copilot.py
```

All examples use stub/mock adapters — no API keys required.

---

## Developer API at a glance

| What you want | Use this |
|---------------|----------|
| Build a governed agent | `build_agent(adapter=..., tools={...})` |
| Define a tool with governance | `ToolSpec(handler=fn, risk_level=..., ...)` |
| Run and get a trace | `agent.run_with_trace(prompt)` |
| Stream lifecycle events | `agent.run_stream(prompt, ...)` |
| Add approval gates | `ApprovalPolicy` + `ApprovalController` |
| Add budget limits | `BudgetPolicy(max_total_tokens=..., max_cost=...)` |
| Force structured output | `agent.run_structured(prompt, schema=MyDataclass)` |
| Discover registered tools | `ToolCatalog.from_agent(agent)` |
| Preview approval coverage | `describe_approval_coverage(...)` |
| Format a trace for display | `format_trace(trace)` |

---

## Autonomy & multi-agent (experimental)

Two capabilities layer on top of the single-agent runtime **without
weakening governance** — every step is still a full governed
`run_with_trace()` call:

| Capability | API | What it adds | Safety bound |
|-----------|-----|-------------|--------------|
| **Iterate-until-done loop** | `IterativeAgentRunner`, `run_until_done`, `LLMCompletionChecker` | Feeds tool observations back to the model to pick the next step, re-planning until a `CompletionChecker` says done | `max_iterations` + shared `RunBudget` |
| **Multi-agent handoff** | `AgentRegistry`, `MultiAgentOrchestrator`, `KeywordRouter`/`LLMRouter` | Routes a query across several governed agents with agent-to-agent handoff and a combined transcript | `max_handoffs` + shared `RunBudget` |
| **Cumulative RunBudget (H11)** | `RunBudget`, `RunBudgetLimits`, `attach_run_budget` | One immutable-limit budget created once and shared across every iteration and handoff; reserve-before-execute over 9 dimensions (model/tool calls, tokens, cost, time, iterations, handoffs) with deterministic `BUDGET_EXHAUSTED` termination | is the bound |
| **Observation-driven replanning (H12)** | `ReplanningRunner`, `Plan`, `PlanObservation`, `DeterministicReplanPolicy`, `RuleBasedReplanner` | Executes an explicit plan step-by-step and adapts the *future* from structured observations (CONTINUE/REVISE/ABORT/COMPLETE); completed work is immutable, revisions are deterministic and fully traceable, stagnation is detected | `max_iterations` / `max_revisions` + shared `RunBudget` |
| **Plan validity & assumptions (H13)** | `PlanAssumption`, `AssumptionContext`, `AssumptionAwareReplanPolicy`, `build_assumption_aware_runner` | Plans declare the assumptions they depend on; observations are evaluated *against assumptions* so replanning fires only when an assumption is invalidated; selective invalidation reconsiders only dependent future steps; append-only, fully traceable | same as H12 (strategy-agnostic) |
| **Governed working memory (H14)** | `WorkingMemory`, `MemoryRecord`, `MemoryAwareObservationBuilder`, `MemoryAssumptionBridge` | Run-scoped, append-only, versioned state shared across iterations, replanning, and agent handoffs; deterministic retrieval (ACTIVE → version → confidence → recency); memory invalidation bridges to H13 assumptions; every read is traced | strategy-agnostic; runs under the shared `RunBudget` |
| **Authority-aware coordination (H16)** | `Coordinator`, `AgentProfile`, `CapabilityRegistry`, `DelegationContract`, `AuthorityModel` | A deterministic coordinator delegates mission goals to worker agents behind capability + authority + budget + ownership checks and immutable contracts; every goal has one owner; all agents share one `WorkingMemory` and one `RunBudget`; the coordinator never executes worker tasks | `max_delegations` + shared `RunBudget` |
| **Hierarchical planning (H15)** | `HierarchyExecutor`, `GoalTree`, `Goal`, `StaticDecomposer`, `MissionPlan` | Deterministically decomposes a mission into an acyclic goal tree and feeds READY leaf goals to the **unchanged** H16 coordinator wave-by-wave; dependency-gated execution, localized subtree replanning, H13 assumption gating; shares one `WorkingMemory` + one `RunBudget` | `max_waves` + shared `RunBudget` |
| **Event-driven workflows (H17)** | `WorkflowEngine`, `WorkflowInstance`, `WaitCondition`, `WorkflowEvent` | Long-lived missions suspend on wait conditions and resume deterministically when a matching event arrives, applying memory (H14) + assumption (H13) effects before continuing; waiting consumes no budget; only the affected subtree resumes; H16 coordination reused unchanged | shared `RunBudget`; waiting is free |
| **Durable checkpoint & recovery (H18)** | `DurableWorkflowEngine`, `WorkflowCheckpoint`, `CheckpointStore`, `WorkflowRestorer` | Deterministic **local** durability: a waiting workflow serializes its full state (canonical JSON + integrity digest), survives process loss, restores into a new runtime with no hidden state, resumes without re-running completed work; cross-restart event idempotency, atomic event transactions, compare-and-save, corruption fail-closed. Not distributed / not exactly-once external | preserves the same `RunBudget` |

See [`iterate_until_done_agent.py`](../../examples/iterate_until_done_agent.py),
[`multi_agent_handoff.py`](../../examples/multi_agent_handoff.py),
[`run_budget_workflow.py`](../../examples/run_budget_workflow.py),
[`observation_driven_replanning.py`](../../examples/observation_driven_replanning.py),
[`assumption_aware_planning.py`](../../examples/assumption_aware_planning.py),
[`working_memory_continuity.py`](../../examples/working_memory_continuity.py),
[`authority_aware_coordination.py`](../../examples/authority_aware_coordination.py),
[`hierarchical_planning.py`](../../examples/hierarchical_planning.py),
[`event_driven_workflow.py`](../../examples/event_driven_workflow.py), and
[`durable_workflow_recovery.py`](../../examples/durable_workflow_recovery.py).
These are **experimental** — composed on the public agent API, tested, and run
without an API key, but not yet hardened to the level of the core runtime.
Design docs: [RunBudget (H11)](../docs/RUN_BUDGET.md) ·
[Replanning (H12)](../docs/REPLANNING.md) ·
[Plan Validity (H13)](../docs/PLAN_VALIDITY.md) ·
[Working Memory (H14)](../docs/WORKING_MEMORY.md) ·
[Hierarchical Planning (H15)](../docs/HIERARCHICAL_PLANNING.md) ·
[Coordination (H16)](../docs/COORDINATION.md) ·
[Event Workflows (H17)](../docs/EVENT_WORKFLOWS.md) ·
[Workflow Durability (H18)](../docs/WORKFLOW_DURABILITY.md).

---

## What it is not (yet)

- **Not a managed multi-agent platform.** The `MultiAgentOrchestrator`
  above adds agent-to-agent handoff, but there is no shared blackboard,
  parallel fan-out, or hierarchical sub-teams yet.
- **Not a managed service.** A Python library, not a hosted
  platform.
- **Not a no-code builder.** Developer-facing, code-first. A
  low-code console is [designed](../docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md)
  but not yet built.
- **Not broadly production-deployed.** Validated by 1550+ tests
  and two pilots. Production adoption is emerging.
- **Not an external telemetry system.** Tracing is in-memory.
  No built-in OpenTelemetry or cloud export.

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [Quickstart](../docs/QUICKSTART.md) | Prerequisites, first agent, API orientation, two approval layers |
| [Mock → Real LLM](../docs/MOCK_TO_REAL_LLM.md) | Switch from MockLLMAdapter to OpenAI/Anthropic — what changes, what stays |
| [Goal Decomposition & Action Mapping](../docs/GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md) | How prompts become governed actions — types, mapping, normalization |
| [Examples Overview](../docs/EXAMPLES_OVERVIEW.md) | All examples with recommended reading order |
| [What Is Agentic Framework](../docs/WHAT_IS_AGENTIC_FRAMEWORK.md) | Overview and positioning |
| [Why Agentic Is Different](../docs/WHY_AGENTIC_IS_DIFFERENT.md) | Table-stakes vs differentiators, execution path, signal enrichment |
| [First Governed Agent](../docs/FIRST_GOVERNED_AGENT.md) | Feature-by-feature build guide |
| [Framework Status](../docs/FRAMEWORK_STATUS.md) | What is proved, what is deferred |
| [Pilot: Research Assistant](../docs/PILOT_RESEARCH_ASSISTANT.md) | First adoption pilot — tool composition + governance |
| [Pilot: Internal Copilot](../docs/PILOT_INTERNAL_COPILOT.md) | Second adoption pilot — approval boundary clarity |
| [Low-Code Interface Spec](../docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md) | Design spec for future developer console (not yet built) |

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  LLM Adapter        (any: OpenAI, Anthropic, …)  │
│  AgenticLLMWrapper  (orchestration + action loop) │
│  SafetyGate         (turn-level coherence gate)   │
│  CGToolDispatcher   (routes to tool gateway)      │
│  SafeMCPGateway     (per-tool governance + audit)  │
└──────────────────────────────────────────────────┘
```

- **`build_agent()`** composes this stack in one call.
- **`ToolSpec`** bundles a tool handler with its governance metadata.
- **`ApprovalPolicy`** + **`BudgetPolicy`** are passed at run time.
- **`TraceCollector`** captures events; **`format_trace()`** renders
  them.

---

## Version

**1.9.0** — Governed runtime complete. Developer ergonomics
(`build_agent`, `ToolSpec`), trace viewer, approval coverage
helper, two adoption pilots. See
[Framework Status](../docs/FRAMEWORK_STATUS.md) for details.
