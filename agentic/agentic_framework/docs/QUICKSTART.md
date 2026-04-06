# Quickstart

The Agentic Framework is a Python library for building LLM-powered
agents whose actions are governed — gated by safety contracts, risk
classification, human approvals, and budget limits, with every step
traceable. It wraps any LLM adapter (OpenAI, Anthropic, Mistral,
Gemini) and adds a structured execution path on top.

---

## Prerequisites

- Python 3.10+
- Install the repo in editable mode: `pip install -e .` from the repo root
- For API-based adapters: an API key for your LLM provider
- For the stub/dev path (no API key needed): nothing else

---

## Fastest path: stub agent with tracing

This runs entirely locally with no API key, using a mock adapter:

```python
from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.llm_adapters import MockLLMAdapter

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
from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
agent = AgenticLLMWrapper(MockLLMAdapter(default_response='Paris.'))
agent.new_session()
trace = agent.run_with_trace('Capital of France?')
print(f'Status: {trace.status}, Events: {trace.event_count}, Tokens: {trace.total_tokens}')
"
```

---

## Next step: governed agent with tool governance

This adds the full governed path — SafetyGate (turn-level) +
SafeMCPGateway (per-tool) — using the stub CG adapter:

```python
from agentic.agentic_framework.cg_tool_dispatcher import build_cg_mcp_agent
from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter

agent = build_cg_mcp_agent(
    adapter=StubCGLLMAdapter(default_response="Quantum computing uses qubits."),
    allow_stub=True,
)
agent.new_session()

trace = agent.run_with_trace("Search for quantum computing")

print(f"Status:  {trace.status}")
print(f"Actions: {trace.actions_executed}")
print(f"Safety:  {'blocked' if trace.safety_blocked else 'passed'}")
```

What `build_cg_mcp_agent` composes for you:
- `StubCGLLMAdapter` — generates text + deterministic 32D state fixture
- `CGToolDispatcher` — reads CG metadata, routes to gateway
- `SafeMCPGateway` — per-tool risk classification + governance
- `SafetyGate` — turn-level coherence gate (runs before any action)

To switch from stub to real inference, replace the adapter:
```python
from agentic.agentic_framework.llm_adapters import MistralCGAdapter
agent = build_cg_mcp_agent(
    adapter=MistralCGAdapter(model_name="mistralai/Mistral-7B-v0.3"),
)
```
Nothing else changes. Real inference requires torch + GPU.

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
| Run a query, get a result | `agent.run(prompt)` → `AgentResult` |
| Stream lifecycle events | `agent.run_stream(prompt, ...)` → `Iterator[AgentRunEvent]` |
| Get a complete trace | `agent.run_with_trace(prompt, ...)` → `AgentRunTrace` |
| Force structured output | `agent.run_structured(prompt, schema)` → `StructuredRunResult` |
| Structured output + trace | `agent.run_structured_with_trace(prompt, schema, ...)` → `(StructuredRunResult, AgentRunTrace)` |
| Add approval gates | Pass `approval_controller=...` to `run_stream` / `run_with_trace` |
| Add budget limits | Pass `budget_policy=...` to `run_stream` / `run_with_trace` |
| Cancel a run | Pass `cancellation_token=...` to `run_stream` / `run_with_trace` |
| Discover registered tools | `ToolCatalog.from_gateway(gateway)` or `ToolCatalog.from_agent(agent)` |

### Key types at a glance

| Type | Module | Purpose |
|------|--------|---------|
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

## Where to go next

| Goal | Doc |
|------|-----|
| Understand each feature in depth | [First Governed Agent](FIRST_GOVERNED_AGENT.md) |
| See what makes this different | [Why Agentic Is Different](WHY_AGENTIC_IS_DIFFERENT.md) |
| Check what is proved / deferred | [Framework Status](FRAMEWORK_STATUS.md) |
| See example scripts | [Examples Overview](EXAMPLES_OVERVIEW.md) |
| Understand the CG/MCP runtime path | [Runtime MCP Path](RUNTIME_MCP_PATH.md) |
| Run the CLI with real inference | [CG Runtime Runbook](CG_RUNTIME_RUNBOOK.md) |
