# Examples Overview

Runnable examples and the patterns they demonstrate.

**Start here →** `examples/minimal_governed_agent.py` — five lines to
a governed agent with a custom tool.

---

## Example scripts

| Script | Pattern | Key APIs |
|--------|---------|----------|
| [`examples/minimal_governed_agent.py`](../../../examples/minimal_governed_agent.py) | **Start here.** Smallest useful governed agent | `build_agent`, `ToolSpec`, `run_with_trace` |
| [`examples/first_governed_agent.py`](../../../examples/first_governed_agent.py) | Governed agent with streaming + tool discovery | `build_cg_mcp_agent`, `run_stream`, `TraceCollector`, `ToolCatalog` |
| [`examples/governed_agent_with_approval_and_budget.py`](../../../examples/governed_agent_with_approval_and_budget.py) | Approval gates + budget enforcement + structured output | `ApprovalController`, `BudgetPolicy`, `run_structured_with_trace` |
| [`examples/pilot_research_assistant.py`](../../../examples/pilot_research_assistant.py) | **Pilot 1:** custom tools, approval, budget, structured output, discovery, audit | `build_agent`, `ToolSpec`, `ApprovalController`, `BudgetPolicy`, `ToolCatalog` |
| [`examples/pilot_internal_copilot.py`](../../../examples/pilot_internal_copilot.py) | **Pilot 2:** approval-gated internal copilot with read/write boundary | `build_agent`, `ToolSpec`, `ApprovalPolicy`, `format_trace`, `ToolCatalog` |
| [`examples/cg_tool_demo.py`](../../../examples/cg_tool_demo.py) | CG metadata enrichment (lower-level, pre-R-phase) | `SafeMCPGateway`, `build_governance_enrichment_kwargs`, audit log |

---

## Recommended reading order

1. **`minimal_governed_agent.py`** — build + run + trace in ~10 lines
2. **`first_governed_agent.py`** — streaming events + tool discovery
3. **`governed_agent_with_approval_and_budget.py`** — approval, budget, structured output
4. **`pilot_research_assistant.py`** — realistic multi-phase pilot with custom tools
5. **`pilot_internal_copilot.py`** — per-action-type approval, approve + deny paths, trace comparison

---

## Pattern index

### 1. Minimal governed agent (start here)
**Script:** `examples/minimal_governed_agent.py`

The absolute shortest path:
- `build_agent()` composes the full governed stack in one call
- `ToolSpec` bundles a handler with governance metadata
- `run_with_trace()` returns a complete execution summary
- No API key, no GPU, no configuration

### 2. Governed agent with streaming + discovery
**Script:** `examples/first_governed_agent.py`

Adds streaming and tool introspection:
- Uses `StubCGLLMAdapter` + `build_cg_mcp_agent()`
- Streams lifecycle events from `run_stream()`
- Builds a trace and inspects the summary
- Discovers registered tools via `ToolCatalog`

### 3. Approval + budget + structured output
**Script:** `examples/governed_agent_with_approval_and_budget.py`

Shows runtime primitives working together:
- Approval gate with auto-approve callback (action executes)
- Approval gate with auto-deny callback (action blocked)
- `BudgetPolicy(max_total_tokens=5000)` with enforcement
- `run_structured_with_trace()` with a dataclass schema
- Budget-exceeded terminal scenario

### 4. CG metadata enrichment (lower-level)
**Script:** `examples/cg_tool_demo.py`

Shows the CG/MCP enrichment path at a lower level:
- Creates a demo CG adapter with synthetic 32D state
- Calls `SafeMCPGateway.call_tool_simple(cg_metadata=...)`
- Prints the audit record showing `vritti_signal_source="real"`

This is a pre-R-phase demo. Most developers should start with
example 1 instead.

---

## Patterns not yet covered by examples

These capabilities are implemented and tested but do not have
standalone example scripts yet:

| Pattern | Where to find usage |
|---------|-------------------|
| Async streaming + cancellation | `tests/test_async_cancellation.py` |
| Custom approval callback (interactive) | `docs/FIRST_GOVERNED_AGENT.md` § 4 |
| Dict-of-types schema | `docs/FIRST_GOVERNED_AGENT.md` § 6 |
| Real `MistralCGAdapter` inference | `docs/CG_RUNTIME_RUNBOOK.md` |
| Budget-exceeded terminal behavior | `tests/test_audit_hardening.py` |
| Approval + cancellation interaction | `tests/test_audit_hardening.py` |

---

## Running examples

Install the repo first (`pip install -e .` from repo root), then
run from the repo root:

```bash
# Start here — minimal governed agent
python examples/minimal_governed_agent.py

# Governed agent with streaming + tool discovery
python examples/first_governed_agent.py

# Approval + budget + structured output
python examples/governed_agent_with_approval_and_budget.py

# Pilot 1 — custom tools, approval, budget, structured output
python examples/pilot_research_assistant.py

# Pilot 2 — approval-gated internal copilot (approve + deny paths)
python examples/pilot_internal_copilot.py

# CG metadata enrichment demo (lower-level)
python examples/cg_tool_demo.py
```

No API keys or GPU required. All examples use stub/mock adapters.
