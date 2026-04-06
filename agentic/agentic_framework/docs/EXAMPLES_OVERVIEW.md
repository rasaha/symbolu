# Examples Overview

Runnable examples and the patterns they demonstrate.

---

## Example scripts

| Script | Pattern | Runtime primitives used |
|--------|---------|------------------------|
| [`examples/first_governed_agent.py`](../../../examples/first_governed_agent.py) | Minimal governed agent with stub adapter, streaming, and tracing | `build_cg_mcp_agent`, `run_stream`, `TraceCollector`, `ToolCatalog` |
| [`examples/governed_agent_with_approval_and_budget.py`](../../../examples/governed_agent_with_approval_and_budget.py) | Approval gates + budget enforcement + structured output + trace | `ApprovalController`, `BudgetPolicy`, `run_structured_with_trace`, `run_with_trace` |
| [`examples/cg_tool_demo.py`](../../../examples/cg_tool_demo.py) | CG metadata enrichment end-to-end (lower-level, pre-R-phase) | `SafeMCPGateway`, `build_governance_enrichment_kwargs`, audit log |

---

## Pattern index

### 1. Minimal governed agent
**Script:** `examples/first_governed_agent.py`

Shows the shortest path to a working governed agent:
- Uses `StubCGLLMAdapter` (no API key, no GPU)
- Composes via `build_cg_mcp_agent(allow_stub=True)`
- Streams events and prints lifecycle progress
- Builds a trace and prints the summary
- Discovers registered tools via `ToolCatalog`

Start here if you are new to the framework.

### 2. Approval + budget + structured output
**Script:** `examples/governed_agent_with_approval_and_budget.py`

Shows runtime primitives working together:
- Approval gate with auto-approve callback (action executes)
- Approval gate with auto-deny callback (action blocked)
- `BudgetPolicy(max_total_tokens=5000)` with enforcement
- `run_structured_with_trace()` with a dataclass schema
- Budget-exceeded terminal scenario
- Prints trace summaries including approval counts and budget status

Uses `SequentialMockAdapter` + `build_cg_mcp_agent` to produce a
`"search"` action that maps to a real MCP tool, so the approval
gate genuinely fires.

Use this after the first example to see the richer execution
controls.

### 3. CG metadata enrichment (lower-level)
**Script:** `examples/cg_tool_demo.py`

Shows the CG/MCP enrichment path at a lower level than the agent
wrapper:
- Creates a demo CG adapter with synthetic 32D state
- Calls `SafeMCPGateway.call_tool_simple(cg_metadata=...)`
- Prints the audit record showing `vritti_signal_source="real"`

This is a pre-R-phase demo that exercises the governance enrichment
seam directly. Most developers should start with example 1 instead.

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
# First governed agent (stub, no dependencies)
python examples/first_governed_agent.py

# Approval + budget + structured output
python examples/governed_agent_with_approval_and_budget.py

# CG metadata enrichment demo
python examples/cg_tool_demo.py
```

No API keys or GPU required for the first two. They use stub/mock
adapters.
