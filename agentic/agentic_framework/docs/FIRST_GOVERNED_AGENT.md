# First Governed Agent — Build Guide

This guide walks through building your first governed agent with the
Agentic Framework. It covers the core components, a minimal setup,
and progressive additions of streaming, tracing, approvals,
structured outputs, budget policies, and tool discovery.

---

## Mental model

The framework has five layers that compose into one execution path:

```
┌──────────────────────────────────────────────────┐
│  LLM Adapter          (talks to the LLM)         │
│  AgenticLLMWrapper    (orchestrates the pipeline) │
│  SafetyGate           (turn-level gating)         │
│  CGToolDispatcher     (routes to tool gateway)    │
│  SafeMCPGateway       (per-tool governance)       │
└──────────────────────────────────────────────────┘
```

For a minimal agent, you only need the first two. The governance
layers activate when you wire in a dispatcher and gateway.

---

## 1. Minimal agent (no governance)

```python
from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.llm_adapters import OpenAIAdapter

# 1. Create an LLM adapter
llm = OpenAIAdapter(api_key="sk-...", model="gpt-4")

# 2. Wrap it in the agent
agent = AgenticLLMWrapper(llm)

# 3. Start a session
agent.new_session()

# 4. Run a query
result = agent.run("What is the capital of France?")
print(result.response)
print(f"Quality: {result.quality_score}, Revisions: {result.revision_count}")
```

This gives you goal decomposition, reflective generation (the agent
critiques and optionally revises its own output), coherence tracking,
and memory across turns — but no tool governance.

Other adapters work the same way:

```python
from agentic.agentic_framework.llm_adapters import AnthropicAdapter
llm = AnthropicAdapter(api_key="sk-ant-...", model="claude-sonnet-4-20250514")

from agentic.agentic_framework.llm_adapters import MistralAdapter
llm = MistralAdapter(api_key="...", model="mistral-large-latest")
```

---

## 2. Streaming events

`run_stream()` yields structured `AgentRunEvent` objects as the
agent progresses through its execution path:

```python
from agentic.agentic_framework.streaming_events import (
    RUN_STARTED, GENERATION_COMPLETED, ACTION_STARTED,
    ACTION_COMPLETED, RUN_COMPLETED,
)

for event in agent.run_stream("Search for quantum computing"):
    if event.event_type == GENERATION_COMPLETED:
        print(f"Generated: {event.payload.get('response', '')[:80]}...")
    elif event.event_type == ACTION_STARTED:
        print(f"Action: {event.payload.get('action_type')}")
    elif event.event_type == RUN_COMPLETED:
        print("Done.")
```

There are 17 event types covering the full lifecycle — see the
[event reference](#event-reference) at the end of this guide.

---

## 3. Tracing

`TraceCollector` records every event emitted during a run.
`run_with_trace()` is a convenience wrapper that creates the
collector for you:

```python
trace = agent.run_with_trace("Explain quantum entanglement")

print(f"Status: {trace.status}")
print(f"Events: {trace.event_count}")
print(f"Actions executed: {trace.actions_executed}")
print(f"Tokens: {trace.total_tokens} ({trace.accounting_mode})")
print(f"Cost: ${trace.estimated_cost:.4f}")
```

For more control, create the collector yourself:

```python
from agentic.agentic_framework.tracing import TraceCollector

collector = TraceCollector()
for event in agent.run_stream("Hello", trace_collector=collector):
    pass  # events are recorded automatically

trace = collector.build_trace()
print(trace.summary)  # dict of summary fields (no raw events)
```

---

## 4. Human-in-the-loop approvals

The approval system gates specific actions behind a callback before
they execute:

```python
from agentic.agentic_framework.approval import (
    ApprovalController, ApprovalPolicy, ApprovalResponse,
)

# Require approval for all actions
policy = ApprovalPolicy(require_all=True)

# Or require approval for specific action types only
policy = ApprovalPolicy(require_approval_for=frozenset({"execute", "delete"}))

# The callback receives a PendingApproval and returns a decision
def my_approval_callback(pending):
    print(f"Action: {pending.action_type} — {pending.description}")
    answer = input("Approve? (y/n): ")
    return ApprovalResponse(
        approved=(answer.lower() == "y"),
        reason="User decision",
    )

ctrl = ApprovalController(policy=policy, callback=my_approval_callback)

for event in agent.run_stream("Delete old records", approval_controller=ctrl):
    pass
```

The approval gate runs **after** the budget check and **before**
the action executes. If the approval callback returns
`approved=False`, the action is skipped and an `approval_resolved`
event is emitted with the denial.

`run_with_trace()` also accepts `approval_controller`:

```python
trace = agent.run_with_trace(
    "Delete old records",
    approval_controller=ctrl,
)
print(f"Approvals requested: {trace.approvals_requested}")
print(f"Approvals denied: {trace.approvals_denied}")
```

---

## 5. Budget enforcement

`BudgetPolicy` sets hard caps on token usage and estimated cost:

```python
from agentic.agentic_framework.token_budget import BudgetPolicy

policy = BudgetPolicy(
    max_total_tokens=4000,
    max_cost=0.05,
)

for event in agent.run_stream("Write a long essay", budget_policy=policy):
    if event.event_type == "budget_exceeded":
        print(f"Budget exceeded: {event.payload.get('reason')}")
        break
    if event.event_type == "usage_updated":
        print(f"Tokens so far: {event.payload.get('total_tokens')}")
```

Budget is checked at two points:
1. **After each generation** — if the LLM response pushes usage
   over the cap, a `BUDGET_EXCEEDED` event is emitted and the run
   terminates before any actions execute.
2. **Before each action** — if cumulative usage exceeds the cap
   between actions, the run stops.

`BUDGET_EXCEEDED` is a terminal event — no further actions or
generations happen after it.

Token accounting has four modes:
- **exact** — the adapter reports real token counts via
  `get_last_usage()` (OpenAI, Anthropic, Mistral API adapters)
- **estimated** — fallback heuristic (`len(text) / 4`) when the
  adapter doesn't report usage
- **mixed** — some generations used exact counts, others used
  estimation (tracked across all generations, not just the last)
- **none** — no generation has been recorded yet

---

## 6. Structured outputs

Force the LLM to produce output matching a schema:

```python
from dataclasses import dataclass

@dataclass
class City:
    name: str
    country: str
    population: int

result = agent.run_structured("Capital of France?", schema=City)
if result.success:
    city = result.parsed_output  # City(name='Paris', ...)
    print(f"{city.name}, {city.country} — pop. {city.population}")
else:
    print(f"Validation failed: {result.validation_error}")
```

`run_structured()` uses the non-streaming `run()` path — it does
not support cancellation, approvals, or budget enforcement.

For full runtime primitive support, use
`run_structured_with_trace()`:

```python
result, trace = agent.run_structured_with_trace(
    "Capital of France?",
    schema=City,
    approval_controller=ctrl,
    budget_policy=policy,
)
```

Dict-of-types schemas also work:

```python
schema = {"name": str, "country": str, "population": int}
result = agent.run_structured("Capital of France?", schema=schema)
```

---

## 7. Tool discovery

`ToolCatalog` provides read-only introspection of tools registered
in a `SafeMCPGateway`:

```python
from agentic.agentic_framework.tool_discovery import ToolCatalog

# From a gateway
catalog = ToolCatalog.from_gateway(gateway)

# Or from an agent that has a dispatcher
catalog = ToolCatalog.from_agent(agent)

# List all tools
for tool in catalog.list_tools():
    print(f"{tool.name} [{tool.risk_level}] — {tool.description}")

# Filter
dangerous = catalog.find_tools(risk_level="destructive")
needs_confirm = catalog.find_tools(requires_confirmation=True)

# Describe a specific tool
tool = catalog.describe_tool("compute")
if tool:
    print(tool.input_schema)
```

---

## 8. Full governed agent (with MCP gateway)

To get the full governed path — safety gate + per-tool governance +
CG signal enrichment — use the `build_cg_mcp_agent()` factory:

```python
from agentic.agentic_framework.cg_tool_dispatcher import build_cg_mcp_agent
from agentic.agentic_framework.llm_adapters import MistralCGAdapter

# Real local inference (requires torch + GPU + checkpoint)
adapter = MistralCGAdapter(
    model_name="mistralai/Mistral-7B-v0.3",
    quantize="4bit",
)

agent = build_cg_mcp_agent(adapter=adapter)
agent.new_session()

result = agent.run("Compare self-attention and linear attention")
```

The factory composes:
- `MistralCGAdapter` → generates text + 32D sovereign state
- `CGToolDispatcher` → reads CG metadata, forwards to gateway
- `SafeMCPGateway` → per-tool governance with entropy/vritti
  enrichment
- `SafetyGate` → turn-level coherence pre-gate

For development without a GPU, use the stub adapter:

```python
from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter

agent = build_cg_mcp_agent(
    adapter=StubCGLLMAdapter(default_response="OK"),
    allow_stub=True,  # required — makes the dev-mode explicit
)
```

The stub emits a deterministic fixture for CG metadata. It is
useful for wiring tests but does not produce real inference signals.

---

## Event reference

| Event type | Phase | Payload |
|-----------|-------|---------|
| `run_started` | R1 | session/turn info |
| `generation_started` | R1 | prompt metadata |
| `text_chunk` | R1 | partial text |
| `generation_completed` | R1 | full response, quality score |
| `safety_gate_result` | R1 | eligible actions, scores |
| `action_started` | R1 | action_type, parameters |
| `action_completed` | R1 | action_type, result |
| `run_completed` | R1 | final result summary |
| `run_error` | R1 | error message, traceback |
| `revision_started` | R1 | revision count |
| `revision_completed` | R1 | final revised result |
| `run_cancelled` | R2 | cancellation reason |
| `approval_requested` | R4 | PendingApproval dict |
| `approval_resolved` | R4 | ApprovalResponse dict |
| `structured_validation` | R6 | validation result |
| `usage_updated` | R9 | UsageStats dict |
| `budget_exceeded` | R9 | violation reason |

---

## See also

- [What Is Agentic Framework](WHAT_IS_AGENTIC_FRAMEWORK.md) —
  overview
- [Why Agentic Is Different](WHY_AGENTIC_IS_DIFFERENT.md) —
  differentiator doc
- [Framework Status](FRAMEWORK_STATUS.md) — maturity status
- [RUNTIME_MCP_PATH.md](RUNTIME_MCP_PATH.md) — internal CG/MCP
  wiring diagram
