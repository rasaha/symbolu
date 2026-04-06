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
from agentic.agentic_framework.agent_builder import build_agent
from agentic.agentic_framework.mcp_gateway import ToolSpec, ToolRiskLevel
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.trace_viewer import format_trace

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

## What it is not (yet)

- **Not a multi-agent platform.** Governs a single agent's
  execution path. No agent-to-agent handoffs or orchestration.
- **Not a managed service.** A Python library, not a hosted
  platform.
- **Not a no-code builder.** Developer-facing, code-first. A
  low-code console is [designed](docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md)
  but not yet built.
- **Not broadly production-deployed.** Validated by 1550+ tests
  and two pilots. Production adoption is emerging.
- **Not an external telemetry system.** Tracing is in-memory.
  No built-in OpenTelemetry or cloud export.

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [Quickstart](docs/QUICKSTART.md) | Prerequisites, first agent, API orientation, two approval layers |
| [Examples Overview](docs/EXAMPLES_OVERVIEW.md) | All examples with recommended reading order |
| [What Is Agentic Framework](docs/WHAT_IS_AGENTIC_FRAMEWORK.md) | Overview and positioning |
| [Why Agentic Is Different](docs/WHY_AGENTIC_IS_DIFFERENT.md) | Table-stakes vs differentiators, execution path, signal enrichment |
| [First Governed Agent](docs/FIRST_GOVERNED_AGENT.md) | Feature-by-feature build guide |
| [Framework Status](docs/FRAMEWORK_STATUS.md) | What is proved, what is deferred |
| [Pilot: Research Assistant](docs/PILOT_RESEARCH_ASSISTANT.md) | First adoption pilot — tool composition + governance |
| [Pilot: Internal Copilot](docs/PILOT_INTERNAL_COPILOT.md) | Second adoption pilot — approval boundary clarity |
| [Low-Code Interface Spec](docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md) | Design spec for future developer console (not yet built) |

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
[Framework Status](docs/FRAMEWORK_STATUS.md) for details.
