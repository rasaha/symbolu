# CG/MCP Runtime Path — End-to-End

**Scope:** this is the concrete wiring every CG-enriched MCP tool
call takes at runtime today. It is the implementation companion to
`AGENTIC_ARCHITECTURE.md` § "Inference CG Metadata ↔ MCP Gateway:
Enrichment Seam" and to `REQUEST_BOUNDARY_CONVENTION.md`.

**Status:** live. The MCP-side enrichment path is real — not a
scaffold. Governance consumes CG-derived `entropy_result` and
`vritti_result` produced from the adapter's 32D sovereign state on
every dispatched tool call.

---

## The path, in one diagram

```
user_input
    │
    ▼
AgenticLLMWrapper.run(user_input)
    │
    ├─▶ GoalDecomposition  ──▶  GoalState{actions: [ActionItem(type="search"), …]}
    │
    ├─▶ ReflectiveGenerator ──▶  adapter.call(prompt)
    │                                │
    │                                └─▶ adapter.last_cg_metadata
    │                                    = {state:[...32], delta_S, ...}
    │
    ├─▶ CoherenceEngine ──▶ CoherenceState
    │
    ├─▶ SafetyGate.check(state, goal, action_types)  (turn-level pre-gate)
    │       │
    │       ├─ contract.eligible=False  ──▶  actions blocked, dispatcher never called
    │       │
    │       └─ contract.eligible=True  ──▶  allowed_types
    │
    ├─▶ _execute_actions(actions, allowed_types)
    │       │
    │       │ for each action in actions:
    │       │   if (dispatcher is not None
    │       │       and action.type in action_type_to_tool
    │       │       and action.type in allowed_types):
    │       │
    │       └─▶ _dispatch_via_mcp(tool_name, params)
    │               │
    │               ▼
    │           CGToolDispatcher.dispatch(tool_name, params)
    │               │
    │               │ reads adapter.last_cg_metadata (current)
    │               ▼
    │           SafeMCPGateway.call_tool_simple(
    │               tool_name=..., parameters=...,
    │               cg_metadata=adapter.last_cg_metadata,
    │               tier="consumer",
    │           )
    │               │
    │               ▼
    │           build_governance_enrichment_kwargs(cg_metadata=..., tier=...)
    │               │
    │               │  splits 32D state → entropy_result + vritti_result
    │               ▼
    │           MCPToolCall{entropy_result=..., vritti_result=..., ...}
    │               │
    │               ▼
    │           governance evaluation (JEPA + domain + shadow + confidence gate)
    │               │
    │               ▼
    │           MCPToolResult + AuditEntry{vritti_signal_source="real",
    │                                      entropy_available=True, ...}
    │
    └─▶ AgentResult{actions_executed, safety_contract, coherence, ...}
```

Every arrow above is live code on `claude/add-cg-metadata-enrichment-5J7il`.
No placeholders, no mocked bridges on this path.

---

## Component roles

| Component                        | File                                | Role                                                                                 |
|----------------------------------|-------------------------------------|--------------------------------------------------------------------------------------|
| `AgenticLLMWrapper`              | `agent.py`                          | Runtime host. Owns adapter (as `llm_client`), dispatcher, action-type mapping.       |
| `SafetyGate`                     | `safety_contract.py`                | Turn-level coherence pre-gate. Runs BEFORE the dispatcher.                           |
| `_execute_actions`               | `agent.py`                          | Routes eligible, mapped actions through the dispatcher.                              |
| `CGToolDispatcher`               | `cg_tool_dispatcher.py`             | Owner component. Reads `adapter.last_cg_metadata`, forwards to gateway.              |
| `SafeMCPGateway.call_tool_simple`| `mcp_gateway.py`                    | Per-call governance. Consumes `cg_metadata` via `build_governance_enrichment_kwargs`.|
| `build_governance_enrichment_kwargs` | `request_enrichment.py`         | Request-boundary helper. Attaches `entropy_result` + `vritti_result` only when live. |
| `sovereign_bridge`               | `sovereign_bridge.py`               | Translates 32D state → `EntropyResult` + `ChittaVrittiResult`.                       |

---

## Layered governance on this path

Two governance surfaces fire per turn. They are complementary, not
redundant:

1. **`SafetyGate`** — turn-level. Uses coherence-state thresholds
   (`internal_consistency`, `goal_alignment`, `prediction_reversal_risk`,
   `identity_stability`) plus agency level. Determines whether ANY
   action may execute this turn. Runs once per turn.

2. **`SafeMCPGateway`** — per-call. Uses CG-derived
   `entropy_result`/`vritti_result` plus confidence + JEPA + domain +
   shadow-AI checks. Determines whether THIS tool call may proceed.
   Runs once per dispatched action.

The runtime enforces ordering: `SafetyGate` first; if its contract is
ineligible `_execute_actions` is never called, so the dispatcher and
gateway cannot be reached. This ordering is pinned by
`tests/test_agent_cg_dispatcher.py`.

---

## The substitution seam: stub adapter ↔ real adapter

The one-knob factory `build_cg_mcp_agent(...)` in
`cg_tool_dispatcher.py` composes the full runtime and takes `adapter`
as the only variable that changes between dev/test and production:

```python
from agentic.agentic_framework.cg_tool_dispatcher import build_cg_mcp_agent

# Dev / test — explicit acknowledgement.
from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter
agent = build_cg_mcp_agent(
    adapter=StubCGLLMAdapter(default_response="OK"),
    allow_stub=True,
)

# Production — same wiring, real inference.
from agentic.agentic_framework.llm_adapters import MistralCGAdapter
agent = build_cg_mcp_agent(
    adapter=MistralCGAdapter(model_name="mistralai/Mistral-7B-v0.3"),
)
```

No other wiring changes. `SafetyGate`, `_execute_actions`, the
dispatcher, the gateway, the enrichment seam, the audit log — all
identical.

### Why `allow_stub` exists

`StubCGLLMAdapter` emits a **deterministic fixture** for its 32D
sovereign state, not a live inference signal (class-level
`IS_STUB = True`, `STATE_PROVENANCE = "deterministic_stub"`).
It is legitimate for tests and dev loops, but silently wiring it
into a runtime that looks like production is a known footgun.

`build_cg_mcp_agent` checks `adapter.IS_STUB`; when truthy and
`allow_stub=False` (default), it logs a WARNING. Real adapters
(`MistralCGAdapter`) don't carry `IS_STUB`, so the warning never
fires on the production path.

### What a "real" adapter must provide

Any object that satisfies both:

- **`_CGCapableAdapter` protocol** — `last_cg_metadata: dict`
  refreshed per `call()` with at least a 32D `state` list (optionally
  `delta_S`, `delta_bhava`, `intent_phase`).
- **`LLMClient` protocol** — `call(prompt: str) -> str`.

`MistralCGAdapter` (`llm_adapters.py`) is the canonical implementation.
Any future adapter wrapping a different CG-capable backend just needs
to honor the same two protocols — no changes to the runtime path.

---

## What this path does NOT do

- Does **not** attach `sovereign_projection_metadata`. That field
  requires a real `SovereignProjectionResult` from an upstream
  producer; no such producer is wired on the MCP/tool-use path yet.
  See `REQUEST_BOUNDARY_CONVENTION.md` for the omission rule.
- Does **not** enrich `AuthorizationRequest`-style calls. Only MCP
  tool calls. Authorization-side enrichment is deferred.
- Does **not** run a reflective-agent loop inside the dispatcher.
  The dispatcher is a two-line compose: read adapter metadata,
  forward to gateway.

---

## Verification evidence

| Test                                             | What it pins                                               |
|--------------------------------------------------|------------------------------------------------------------|
| `test_cg_tool_dispatcher.py`                     | Dispatcher reads current adapter metadata per call         |
| `test_agent_cg_dispatcher.py`                    | `_execute_actions` routes through dispatcher; ordering     |
| `test_agent_full_run_integration.py`             | Full `run()` pipeline → MCP audit with `vritti_signal_source="real"` |
| `test_cg_mcp_runtime_factory.py`                 | `build_cg_mcp_agent` substitution seam + stub warning      |
| `test_cg_tool_demo.py`                           | End-to-end demo smoke (regression guard)                   |

All five suites are part of the regression baseline for this path.

---

## See also

- `agentic/agentic_framework/agent.py` — `AgenticLLMWrapper`, the runtime host.
- `agentic/agentic_framework/cg_tool_dispatcher.py` — dispatcher + factory.
- `agentic/agentic_framework/request_enrichment.py` — request-boundary helper.
- `Project_documentation/agentic_framework/agentic/docs/REQUEST_BOUNDARY_CONVENTION.md` — attach/omit rules.
- `Project_documentation/agentic_framework/agentic/docs/CG_RUNTIME_RUNBOOK.md` — runbook for the
  `inference_mistral.py --cg` CLI (real-inference requirements, stub
  fallback, proved-vs-experimental status).
- `Project_documentation/agentic_framework/agentic/AGENTIC_ARCHITECTURE.md` § "Inference CG Metadata ↔ MCP Gateway".
- `examples/cg_tool_demo.py` — minimal end-to-end demo.
