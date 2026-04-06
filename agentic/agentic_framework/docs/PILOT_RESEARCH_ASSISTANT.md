# Pilot: Governed Research Assistant

First real adoption use case for the Agentic Framework.

---

## What it does

A research assistant that takes a question and:
1. Discovers available research tools (search, compute, validate,
   save) via `ToolCatalog`
2. Decomposes the question into governed tool calls via LLM-driven
   goal decomposition
3. Executes tool calls through `SafeMCPGateway` with per-tool risk
   classification and governance gating
4. Gates every action through an approval callback — read-only
   actions are approved, write-risk actions are denied
5. Enforces a token/cost budget across the full run
6. Produces a structured research answer validated against a
   dataclass schema
7. Reports a full execution trace and governance audit log

---

## Why this use case fits the framework

The governed research assistant exercises the framework's
**differentiating capabilities**, not just table-stakes tool calling:

| Capability | How the pilot exercises it |
|-----------|--------------------------|
| Custom tool handlers | 4 domain-specific tools registered on `MockMCPClient` with realistic return data |
| Per-tool risk classification | `search`/`compute`/`validate` are READ_ONLY; `save_report` is WRITE with `requires_confirmation=True` |
| Approval gates | `ApprovalPolicy(require_all=True)` — callback approves read-only, denies write-risk |
| Budget enforcement | `BudgetPolicy(max_total_tokens=10000, max_cost=0.50)` — checked after generation and before actions |
| Structured output | `ResearchAnswer` dataclass with 5 typed fields, validated via `run_structured_with_trace` |
| Tracing | `TraceCollector` captures all events; trace summary shows approval counts, budget status, action counts |
| Tool discovery | `ToolCatalog.from_gateway()` lists tools with capabilities, risk levels, confirmation requirements |
| Governance audit | `gateway.get_audit_log()` records every tool-call decision with confidence scores |
| Turn-level safety gate | `SafetyGate` evaluates coherence metrics before any action executes |

---

## How to run it

```bash
pip install -e .  # if not already installed
python examples/pilot_research_assistant.py
```

No API keys, GPU, or external services required. The pilot uses
`SequentialMockAdapter` with pre-scripted responses and
`MockMCPClient` with custom tool handlers.

---

## What the pilot proves

1. **The framework is usable for a real use case.** A developer can
   build a governed research assistant using the current API surface
   without inventing workarounds or bypassing the framework.

2. **Custom tool registration works cleanly.** `MockMCPClient.register_tool()`
   + `gateway.register_tool(MCPToolDefinition(...))` is a two-step
   process but it works and gives full control over risk metadata.

3. **The governance pipeline is non-bypassable.** Every tool call
   goes through risk classification, confidence gating, and audit
   logging — there is no shortcut path.

4. **Approval gates fire on real tool-mapped actions.** The
   `SequentialMockAdapter` + LLM decomposition pattern produces
   action types that map to real MCP tools, so the approval
   callback genuinely fires.

5. **Structured output + tracing work together.** `run_structured_with_trace`
   returns both a validated `ResearchAnswer` and a complete
   `AgentRunTrace` with correct `status="completed"`.

6. **Budget enforcement works across the workflow.** The budget is
   checked after generation and before each action. Budget exceedance
   is a terminal event.

---

## What this does NOT prove

- **Real LLM integration.** The adapter is a mock. In production,
  replace with `OpenAIAdapter`, `AnthropicAdapter`, or
  `MistralCGAdapter` — but the response format and tool-call flow
  will differ from the scripted mock.

- **Real tool execution.** Tool handlers return simulated data. In
  production, wire real search APIs, databases, or computation
  services into the handlers.

- **Multi-agent coordination.** This is a single-agent pilot. The
  framework does not support agent-to-agent handoffs.

- **Production deployment.** The pilot runs as a script. Production
  use would require an API server, error handling, persistent state,
  and external telemetry.

- **CG signal enrichment.** The mock adapter does not produce real
  32D sovereign state. The governance pipeline works without it
  (uses text-level signals), but the CG enrichment path is not
  exercised.

---

## Framework components exercised

| Component | Module | Role in pilot |
|-----------|--------|--------------|
| `AgenticLLMWrapper` | `agent.py` | Main agent orchestrator |
| `CGToolDispatcher` | `cg_tool_dispatcher.py` | Routes tool calls to gateway |
| `SafeMCPGateway` | `mcp_gateway.py` | Per-tool governance + audit |
| `MockMCPClient` | `mcp_gateway.py` | Custom tool handler host |
| `SafetyGate` | `safety_contract.py` | Turn-level coherence gate |
| `ApprovalController` | `approval.py` | Human-in-the-loop gate |
| `BudgetPolicy` | `token_budget.py` | Token/cost enforcement |
| `TraceCollector` | `tracing.py` | Event capture |
| `AgentRunTrace` | `tracing.py` | Run summary |
| `ToolCatalog` | `tool_discovery.py` | Tool introspection |
| `StructuredRunResult` | `structured_output.py` | Schema-validated output |
| `SequentialMockAdapter` | `llm_adapters.py` | Scripted LLM responses |

---

## Developer friction discovered

See the friction audit section in the commit that added this pilot.
Key findings:

1. **Two-step tool registration** — register handler on
   `MockMCPClient`, then register metadata on `SafeMCPGateway`.
   A single `register_tool(name, handler, metadata)` on the
   gateway would be cleaner.

2. **SequentialMockAdapter + reflective generation is hard to
   script** — the critic/revision cycle consumes unpredictable
   numbers of adapter responses. Workaround: use
   `use_llm_for_decomposition=False` for structured output, or
   provide enough responses with `loop=True`.

3. **No `build_agent` helper that takes custom tools** — the
   developer must manually compose `MockMCPClient` →
   `create_safe_mcp_gateway` → `CGToolDispatcher` →
   `AgenticLLMWrapper`. A `build_agent(adapter, tools={...})`
   factory would reduce boilerplate.

4. **Action results don't flow back into the LLM context** — the
   MCP tool result is stored in `action.result` but is not fed
   back to the LLM for synthesis. The research narrative is
   generated before tool calls, not after.

---

## See also

- [`examples/pilot_research_assistant.py`](../../../examples/pilot_research_assistant.py) — the pilot script
- [Quickstart](QUICKSTART.md) — framework setup
- [First Governed Agent](FIRST_GOVERNED_AGENT.md) — progressive build guide
- [Framework Status](FRAMEWORK_STATUS.md) — maturity status
