# Quickstart

The Agentic Framework is a Python library for building LLM-powered
agents whose actions are governed — gated by safety contracts, risk
classification, human approvals, and budget limits, with every step
traceable. It wraps any LLM adapter (OpenAI, Anthropic, Mistral,
Gemini) and adds a structured execution path on top.

---

## Prerequisites

- Python 3.10+
- Install the repo: `pip install -e .` from the repo root
  (this automatically installs core dependencies: numpy, pydantic)
- For real LLM adapters: `pip install -e ".[openai]"` or
  `pip install -e ".[anthropic]"` — see
  [Mock → Real LLM](MOCK_TO_REAL_LLM.md) for details
- For the stub/dev path (no API key needed): nothing else

---

## Fastest path: stub agent with tracing

This runs entirely locally with no API key, using a mock adapter:

```python
from agentic.agentic_framework import AgenticLLMWrapper, MockLLMAdapter

agent = AgenticLLMWrapper(MockLLMAdapter(default_response="Paris is the capital of France."))
agent.new_session()

trace = agent.run_with_trace("What is the capital of France?")

print(f"Status:  {trace.status}")
print(f"Events:  {trace.event_count}")
print(f"Actions: {trace.actions_executed}")
print(f"Tokens:  {trace.total_tokens} ({trace.accounting_mode})")
```

Run it:
```bash
python -c "
from agentic.agentic_framework import AgenticLLMWrapper, MockLLMAdapter
agent = AgenticLLMWrapper(MockLLMAdapter(default_response='Paris.'))
agent.new_session()
trace = agent.run_with_trace('Capital of France?')
print(f'Status: {trace.status}, Events: {trace.event_count}, Tokens: {trace.total_tokens}')
"
```

---

## Next step: governed agent with custom tools

This adds the full governed path — SafetyGate (turn-level) +
SafeMCPGateway (per-tool) — with custom tool handlers:

```python
from agentic.agentic_framework import (
    build_agent, ToolSpec, ToolRiskLevel, MockLLMAdapter,
)

agent = build_agent(
    adapter=MockLLMAdapter(default_response="Quantum computing uses qubits."),
    tools={
        "search": ToolSpec(
            handler=lambda p: [f"Result for {p.get('query', '')}"],
            description="Search for papers",
            risk_level=ToolRiskLevel.READ_ONLY,
        ),
    },
)
agent.new_session()

trace = agent.run_with_trace("Search for quantum computing")

print(f"Status:  {trace.status}")
print(f"Actions: {trace.actions_executed}")
print(f"Safety:  {'blocked' if trace.safety_blocked else 'passed'}")
```

`build_agent()` composes the full governed stack for you:
- `MockMCPClient` — hosts your custom tool handlers
- `SafeMCPGateway` — per-tool risk classification + governance
- `CGToolDispatcher` — routes tool calls through the gateway
- `SafetyGate` — turn-level coherence gate (runs before any action)
- `AgenticLLMWrapper` — orchestrates the pipeline

`ToolSpec` bundles a handler with its governance metadata (risk
level, capabilities, confirmation requirements) in one object —
no more two-step registration.

To switch to a real LLM, replace the adapter:
```python
from agentic.agentic_framework import OpenAIAdapter
agent = build_agent(
    adapter=OpenAIAdapter(api_key="sk-...", model="gpt-4"),
    tools={...},
)
```

---

## How action types map to tools

When the agent decomposes a prompt into actions, each action gets an
`action_type` (e.g. `"search"`, `"execute"`, `"generate"`). The
`action_type_to_tool` mapping tells the runtime which registered tool
to invoke for each action type.

**Default behavior:** When you pass `tools={"search": ToolSpec(...)}`,
`build_agent()` creates an identity mapping: `{"search": "search"}`.
This works when the LLM produces action types that exactly match your
tool names.

**When you need an explicit mapping:** Real LLMs often produce generic
action types (`"search"`, `"execute"`, `"generate"`, `"compute"`,
`"validate"`) from the decomposition prompt. If your tool names are
domain-specific (like `"check_alerts"` or `"save_draft"`), you need
to map them:

```python
agent = build_agent(
    adapter=my_adapter,
    tools={
        "check_alerts": ToolSpec(handler=check_fn, ...),
        "save_draft": ToolSpec(handler=save_fn, ...),
    },
    action_type_to_tool={
        "check_alerts": "check_alerts",   # identity
        "save_draft": "save_draft",       # identity
        "search": "check_alerts",         # generic → domain
        "execute": "save_draft",          # generic → domain
    },
)
```

The framework also has context-aware normalization: when a generic
type like `"execute"` appears and the action description contains
keywords like "send", "save", or "escalate", it can automatically
route to the right domain tool. See `normalize_action_type()` for
details.

**With `MockLLMAdapter`:** The mock adapter returns a fixed string.
If that string is valid JSON matching the decomposition format, the
framework parses it and uses the action types from the JSON. If not,
it falls back to rule-based extraction which produces generic types
like `"generate"`.

---

## What to look for in the output

| Field | What it tells you |
|-------|-------------------|
| `trace.status` | `"completed"`, `"cancelled"`, `"budget_exceeded"`, or `"error"` |
| `trace.actions_executed` | How many tool calls actually ran |
| `trace.safety_blocked` | Whether SafetyGate blocked all actions |
| `trace.approvals_requested` / `trace.approvals_denied` | Approval gate activity |
| `trace.total_tokens` | Token usage (exact or estimated) |
| `trace.accounting_mode` | `"exact"`, `"estimated"`, `"mixed"`, or `"none"` |
| `trace.budget_exceeded` | Whether the run hit a budget limit |

---

## Mental model

```
adapter  →  AgenticLLMWrapper  →  SafetyGate  →  action loop  →  trace
                                                      │
                                         ┌────────────┼────────────┐
                                         │            │            │
                                    cancel check  budget check  approval gate
                                                      │
                                              CGToolDispatcher
                                                      │
                                              SafeMCPGateway
                                            (per-tool governance)
```

- **SafetyGate** runs once per turn. If coherence metrics are too
  low, all actions are blocked before the loop starts.
- **The action loop** runs for each eligible action. At each step
  it checks: is the run cancelled? Is the budget exceeded? Does
  this action need approval? Only then does it execute.
- **SafeMCPGateway** evaluates each tool call individually against
  risk classification, confidence thresholds, and (when available)
  model-internal signals.

---

## API orientation

| What you want | Use this |
|---------------|----------|
| Build a governed agent | `build_agent(adapter=..., tools={...})` → `AgenticLLMWrapper` |
| Run a query, get a result | `agent.run(prompt)` → `AgentResult` |
| Stream lifecycle events | `agent.run_stream(prompt, ...)` → `Iterator[AgentRunEvent]` |
| Get a complete trace | `agent.run_with_trace(prompt, ...)` → `AgentRunTrace` |
| Force structured output | `agent.run_structured(prompt, schema)` → `StructuredRunResult` |
| Structured output + trace | `agent.run_structured_with_trace(prompt, schema, ...)` → `(StructuredRunResult, AgentRunTrace)` |
| Add approval gates | Pass `approval_controller=...` to `run_stream` / `run_with_trace` |
| Add budget limits | Pass `budget_policy=...` to `run_stream` / `run_with_trace` |
| Cancel a run | Pass `cancellation_token=...` to `run_stream` / `run_with_trace` |
| Discover registered tools | `ToolCatalog.from_gateway(gateway)` or `ToolCatalog.from_agent(agent)` |
| Preview approval coverage | `describe_approval_coverage(action_type_to_tool=..., approval_policy=..., catalog=...)` |

### Key types at a glance

| Type | Module | Purpose |
|------|--------|---------|
| `build_agent()` | `agent_builder.py` | High-level factory — adapter + tools → governed agent |
| `ToolSpec` | `mcp_gateway.py` | Bundles a tool handler with its governance metadata |
| `AgenticLLMWrapper` | `agent.py` | Main agent — orchestrates the full pipeline |
| `AgentResult` | `agent.py` | Return value of `run()` — response, quality, actions, coherence |
| `AgentRunEvent` | `streaming_events.py` | Single lifecycle event (17 types) |
| `AgentRunTrace` | `tracing.py` | Complete run summary with counters and usage stats |
| `TraceCollector` | `tracing.py` | Records events during streaming; builds trace |
| `ApprovalController` | `approval.py` | Approval gate with policy + callback |
| `ApprovalPolicy` | `approval.py` | Which actions need approval |
| `BudgetPolicy` | `token_budget.py` | Token/cost caps |
| `StructuredRunResult` | `structured_output.py` | Schema-validated output |
| `ToolCatalog` | `tool_discovery.py` | Read-only tool introspection |
| `SafetyGate` | `safety_contract.py` | Turn-level coherence gate |
| `SafeMCPGateway` | `mcp_gateway.py` | Per-tool governance gateway |
| `CGToolDispatcher` | `cg_tool_dispatcher.py` | Routes tool calls with CG metadata |
| `CancellationToken` | `cancellation.py` | Cooperative cancellation |

---

## `build_agent` vs `build_cg_mcp_agent`

The framework provides two agent factories:

| Factory | Module | When to use |
|---------|--------|-------------|
| `build_agent()` | `agent_builder.py` | **Default.** Works with any adapter. Accepts a `tools` dict of `ToolSpec` objects. |
| `build_cg_mcp_agent()` | `cg_tool_dispatcher.py` | When your adapter exposes `last_cg_metadata` (e.g. `MistralCGAdapter`, `StubCGLLMAdapter`). Uses CG signals for richer governance. |

Both produce an `AgenticLLMWrapper` with the same runtime
capabilities (streaming, approval, budget, tracing, structured
output). The difference is in how governance signals are sourced:

- **`build_agent`** — governance uses risk classification and
  confidence thresholds from `ToolSpec`. Works with any LLM adapter
  (OpenAI, Anthropic, Mistral API, mock/stub).
- **`build_cg_mcp_agent`** — governance also consumes model-internal
  CG metadata (sovereign state tensors) for richer per-tool gating.
  Requires a CG-capable adapter.

**If you are not sure which to use, use `build_agent()`.**

---

## Two approval layers

The framework has two independent approval mechanisms. They serve
different purposes and operate at different levels:

### Layer 1: R4 orchestration approval (`ApprovalPolicy`)

- **Where:** Before the action starts, in the `run_stream()` action loop
- **Scope:** Action-type oriented — you specify which action types
  need approval (e.g. `"save"`, `"send"`, `"escalate"`)
- **Control:** Your `ApprovalCallback` receives a `PendingApproval`
  and returns approve/deny
- **Use when:** You want explicit human-in-the-loop before selected
  actions execute

```python
policy = ApprovalPolicy(require_approval_for=frozenset({"save", "send"}))
ctrl = ApprovalController(policy=policy, callback=my_callback)
agent.run_stream(prompt, approval_controller=ctrl)
```

### Layer 2: Gateway confirmation (`requires_confirmation`)

- **Where:** Inside `SafeMCPGateway`, when the tool call executes
- **Scope:** Tool-definition oriented — set on `ToolSpec` or
  `MCPToolDefinition`
- **Control:** The gateway's `EscalationHandler` decides (default
  handler auto-denies; use `InteractiveEscalationHandler` for
  custom logic)
- **Use when:** A tool is inherently dangerous and should always
  require confirmation at the gateway level, regardless of the
  orchestration policy

```python
ToolSpec(
    handler=delete_handler,
    risk_level=ToolRiskLevel.DESTRUCTIVE,
    requires_confirmation=True,  # gateway-level gate
)
```

### Guidance

| Scenario | Use |
|----------|-----|
| "I want human approval before saves/sends" | `ApprovalPolicy` (Layer 1) |
| "This tool is always dangerous" | `requires_confirmation` (Layer 2) |
| "I want both" | Set both — the action is gated twice (first R4, then gateway) |
| "I'm not sure" | Use `ApprovalPolicy` — it is the simpler, more visible layer |

**Do not set both casually.** If both are active for the same
action/tool, the developer must approve via the R4 callback *and*
the gateway's escalation handler must also confirm. The default
escalation handler auto-denies, so the action would be blocked
even after R4 approval.

### Preview coverage before running

Use `describe_approval_coverage()` to see which layers are active:

```python
from agentic.agentic_framework import (
    describe_approval_coverage,
    format_approval_coverage,
)

coverage = describe_approval_coverage(
    action_type_to_tool={"search": "search", "save": "save_draft"},
    approval_policy=policy,
    catalog=ToolCatalog.from_agent(agent),
)
print(format_approval_coverage(coverage))
```

---

## Where to go next

| Goal | Doc |
|------|-----|
| Understand each feature in depth | [First Governed Agent](FIRST_GOVERNED_AGENT.md) |
| Switch from mock to real LLM | [Mock → Real LLM](MOCK_TO_REAL_LLM.md) |
| Understand action types and mapping | [Goal Decomposition & Action Mapping](GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md) |
| See what makes this different | [Why Agentic Is Different](WHY_AGENTIC_IS_DIFFERENT.md) |
| Check what is proved / deferred | [Framework Status](FRAMEWORK_STATUS.md) |
| See example scripts | [Examples Overview](EXAMPLES_OVERVIEW.md) |
| Understand the CG/MCP runtime path | [Runtime MCP Path](RUNTIME_MCP_PATH.md) |
| Run the CLI with real inference | [CG Runtime Runbook](CG_RUNTIME_RUNBOOK.md) |
