# Low-Code Developer Interface — Design Spec

**Version:** 0.1.0 (design phase)
**Status:** Proposal — not yet implemented
**Target:** Technical developers, platform engineers, AI engineers

---

## A. Product Framing

The low-code developer interface is a configuration and inspection
layer that sits on top of the existing governed runtime. It lets
developers configure agents, register tools, set approval and budget
policies, run agents, and inspect execution traces — without writing
the full composition boilerplate, but without hiding the architecture.

**Who it is for:** A developer who knows what an LLM adapter is, what
tool governance means, and what a trace looks like — but wants less
boilerplate than raw Python and more visibility than print statements.

**What problem it solves:** Today, configuring a governed agent
requires knowing which classes to compose (`build_agent` helps, but
approval policies, budget policies, action mappings, and structured
output schemas still require code). Inspecting a trace requires
writing a print loop over events. The low-code layer makes these
tasks declarative and visual.

**What it is not:** This is not a no-code workflow builder, not a
visual planner, not a multi-agent orchestration platform, and not a
hosted service. It is a developer console that reads and writes the
same configuration objects the code API uses.

---

## B. Scope Boundaries

### In scope (first version)

| Surface | What it covers |
|---------|----------------|
| Tool catalog viewer | Browse registered tools, filter by risk/capability, view governance metadata |
| Action mapping editor | Map action types to tool names, validate mappings |
| Approval policy editor | Configure which actions need approval, toggle require-all |
| Budget policy editor | Set token/cost caps, choose accounting visibility |
| Trace viewer | Timeline of runtime events, summary counters, drill into payloads |
| Runtime mode selector | Choose `build_agent` vs `build_cg_mcp_agent`, stub vs real adapter |
| Structured output config | Select schema mode, view validation results |
| Config export | Export current configuration as Python code or JSON |

### Out of scope (first version)

| Item | Why deferred |
|------|-------------|
| Multi-agent orchestration | Framework is single-agent; no agent-to-agent handoff exists |
| Hosted deployment platform | Framework is a library, not a managed service |
| Remote tool marketplace | No remote MCP registry exists yet |
| No-code business-user builder | Target user is a developer, not a business analyst |
| Arbitrary workflow/DAG editor | No planner or workflow engine exists; goal decomposition is LLM-driven |
| Full visual planner | Goal decomposition is internal to the LLM; no user-facing planner to configure |
| External telemetry dashboard | Tracing is in-memory; OpenTelemetry integration is deferred |
| Policy track (P0-P4) surfaces | Policy track has no production callers yet |
| Sovereign signal inspector | S1-S4 signals are internal governance inputs, not developer-configured |
| Live agent editing mid-run | First version is configure-then-run, not hot-reconfigure |

---

## C. Proposed Information Architecture

The interface is organized as a single-page console with a sidebar
navigation and a main content area. Seven panels, each mapping to
one runtime concept.

```
┌─────────────────────────────────────────────────────────┐
│  Agentic Developer Console                              │
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  [Overview]  │   Main content area                     │
│  [Tools]     │   (one panel at a time)                 │
│  [Actions]   │                                          │
│  [Approvals] │                                          │
│  [Budget]    │                                          │
│  [Output]    │                                          │
│  [Run]       │                                          │
│  [Trace]     │                                          │
│              │                                          │
├──────────────┴──────────────────────────────────────────┤
│  Status bar: adapter type | tool count | last run status│
└─────────────────────────────────────────────────────────┘
```

### Panel 1: Agent Overview

**Purpose:** Entry point. Shows current agent configuration at a
glance.

**Content:**
- Agent factory in use: `build_agent` or `build_cg_mcp_agent`
- Adapter type and model (e.g. `MockLLMAdapter`, `OpenAIAdapter("gpt-4")`)
- Registered tool count
- Action mapping summary (N action types mapped to M tools)
- Approval policy summary (require-all: yes/no, N specific types)
- Budget policy summary (token cap, cost cap, or "no limit")
- Last run status (completed / error / not run yet)

**Actions:**
- "New Agent" — opens runtime mode selector
- "Load Config" — imports JSON config file
- "Export Config" — exports current state as JSON or Python code
- "Run Agent" — navigates to Run panel

**Grounding:** Reads from the same objects `build_agent()` produces:
adapter type from the adapter instance, tool count from
`ToolCatalog.from_agent(agent)`, mapping from
`agent._action_type_to_tool`, approval/budget from the controller
and policy objects passed to `run_stream`.

### Panel 2: Tool Catalog

**Purpose:** Browse and inspect registered tools. Read-only in first
version (tool registration stays in code via `ToolSpec`).

**Content — table view:**

| Column | Source |
|--------|--------|
| Name | `DiscoveredTool.name` |
| Description | `DiscoveredTool.description` |
| Risk Level | `DiscoveredTool.risk_level` — color-coded badge (green=read_only, yellow=write, orange=execute, red=destructive, purple=privileged) |
| Capabilities | `DiscoveredTool.capabilities` — tag chips |
| Confirmation | `DiscoveredTool.requires_confirmation` — checkbox icon |
| Min Confidence | `DiscoveredTool.min_confidence` — numeric |
| Timeout | `DiscoveredTool.timeout_seconds` — numeric |

**Filters (sidebar or toolbar):**
- Risk level dropdown (maps to `catalog.find_tools(risk_level=...)`)
- Capability search (maps to `catalog.find_tools(capability=...)`)
- Name search (maps to `catalog.find_tools(name=...)`)
- Confirmation required toggle

**Detail view (click a tool row):**
- All fields from `DiscoveredTool`
- Input schema (rendered as a JSON tree if present)
- Which action types map to this tool (cross-reference from action mapping)

**Actions:**
- None in first version. Tool registration is code-only.
- "Copy ToolSpec" button generates the Python `ToolSpec(...)` call
  for this tool, for use in code.

**What stays code-only:** Registering new tools, writing handler
functions, modifying `ToolSpec` fields. The console is read-only
for tool definitions — it inspects what code registered.

### Panel 3: Action Mapping

**Purpose:** Configure which goal-decomposition action types route
to which registered tools.

**Content — editable table:**

| Action Type | Mapped Tool | Status |
|-------------|-------------|--------|
| `search` | `search` | valid (tool exists) |
| `compute` | `compute` | valid |
| `save` | `save_report` | valid |
| `analyze` | — | unmapped (warning) |

**Editing:**
- Dropdown for "Mapped Tool" pulls from registered tool names
- "Add Row" to add a new action type mapping
- "Remove" to delete a mapping
- Identity mapping auto-suggested when tool names match action types

**Validation states:**
- **Valid:** mapped tool exists in catalog
- **Unmapped:** action type has no tool (warning — will fall through
  to placeholder execution)
- **Missing tool:** mapped tool name not found in catalog (error)
- **Duplicate:** two action types map to the same tool (info — allowed
  but flagged)

**Grounding:** Reads/writes `action_type_to_tool: Dict[str, str]`.
This is the same dict passed to `build_agent()` or
`AgenticLLMWrapper(action_type_to_tool=...)`. Default identity
mapping (`{name: name for name in tools}`) is shown when no
explicit mapping exists.

### Panel 4: Approval Policy

**Purpose:** Configure when human approval is required.

**Content:**
- **Require all** toggle — maps to `ApprovalPolicy(require_all=True)`
- **Per-action-type list** — checkboxes for each action type from
  the action mapping table. Maps to
  `ApprovalPolicy(require_approval_for=frozenset({...}))`.
- **Preview panel** — for each action type, shows "will require
  approval: yes/no" based on current policy. Calls
  `policy.requires_approval(action_type)` for each.

**Editing:**
- Toggle require-all on/off
- Check/uncheck individual action types
- Changes update the preview immediately

**What the developer cannot configure here (code-only):**
- The approval callback function itself (the logic that decides
  approve/deny). This is always a Python callable.
- Custom `PendingApproval` fields or reason text.

**Grounding:** Reads/writes `ApprovalPolicy` dataclass. The
callback is set in code and referenced by the console but not
editable. The console shows "Callback: <function name>" as
read-only text.

### Panel 5: Budget Policy

**Purpose:** Set token and cost limits for agent runs.

**Content — form:**

| Field | Input | Maps to |
|-------|-------|---------|
| Max total tokens | numeric input (or blank = no limit) | `BudgetPolicy.max_total_tokens` |
| Max input tokens | numeric input (or blank) | `BudgetPolicy.max_input_tokens` |
| Max output tokens | numeric input (or blank) | `BudgetPolicy.max_output_tokens` |
| Max cost ($) | numeric input (or blank) | `BudgetPolicy.max_cost` |

**Info panel (read-only, shown after a run):**
- Current usage: input/output/total tokens, estimated cost
- Accounting mode: exact / estimated / mixed / none
- Budget exceeded: yes/no + reason string

**Accounting mode explanation (tooltip or expandable):**
- **exact:** all generations reported exact token counts
- **estimated:** all generations used `len(text)//4` heuristic
- **mixed:** some exact, some estimated
- **none:** no generations recorded yet

**Grounding:** Reads/writes `BudgetPolicy` (frozen dataclass —
new instance created on each change). Usage display reads from
`UsageStats` on the last `AgentRunTrace`.

### Panel 6: Structured Output

**Purpose:** Configure schema-enforced output and view validation
results.

**Content:**
- **Schema mode selector:**
  - None (free-text response)
  - Dataclass (specify module path + class name)
  - Dict schema (inline JSON editor for `{"field": type}`)
  - Pydantic model (specify module path + class name)
- **Schema preview:** renders the expected fields and types
- **Last validation result (after a run):**
  - Success/failure badge
  - Raw LLM text (collapsible)
  - Parsed output (formatted JSON)
  - Validation error (if failed)
  - Quality score and revision count

**What stays code-only:**
- Defining the actual dataclass/Pydantic model (these are Python types)
- Custom validation logic beyond schema matching
- The schema itself — the console references it by import path,
  it does not define it

**Grounding:** The console calls `run_structured(prompt, schema=...)`
or `run_structured_with_trace(prompt, schema=...)`. Schema target
is resolved by import path at runtime. Validation display reads
from `StructuredRunResult` fields.

### Panel 7: Run + Trace

This is two sub-panels in one view: a run launcher and a trace
viewer.

#### Run sub-panel

**Content:**
- Prompt input (text area)
- "Run" button → calls `agent.run_stream(prompt, ...)`
- Live event stream display during execution
- Run controls: cancel button (sends `CancellationToken.cancel()`)

**Configuration applied at run time:**
- Approval controller (from Panel 4 config + code-defined callback)
- Budget policy (from Panel 5 config)
- Trace collector (always attached)

#### Trace sub-panel

**Content — summary card:**

| Field | Source |
|-------|--------|
| Status | `trace.status` — badge (completed=green, error=red, cancelled=yellow, budget_exceeded=orange) |
| Total events | `trace.event_count` |
| Actions executed | `trace.actions_executed` |
| Safety blocked | `trace.safety_blocked` — boolean badge |
| Approvals requested | `trace.approvals_requested` |
| Approvals denied | `trace.approvals_denied` |
| Total tokens | `trace.total_tokens` |
| Accounting mode | `trace.accounting_mode` |
| Estimated cost | `trace.estimated_cost` |
| Budget exceeded | `trace.budget_exceeded` — boolean badge |

**Content — event timeline:**

Vertical list of events in chronological order. Each event row:
- Timestamp (relative to run start)
- Event type — color-coded icon
- Key payload fields (varies by type)

Event type display:

| Event type | Icon color | Key payload shown |
|------------|-----------|-------------------|
| `run_started` | blue | session_id, turn_id |
| `generation_started` | blue | — |
| `text_chunk` | gray | chunk text (truncated) |
| `generation_completed` | green | quality_score, revision_count |
| `safety_gate_result` | green/red | eligible, blocking_reasons |
| `action_started` | blue | action_type, description |
| `action_completed` | green/red | status, error |
| `approval_requested` | yellow | action_type, description |
| `approval_resolved` | green/red | approved, reason |
| `usage_updated` | gray | total_tokens, accounting_mode |
| `budget_exceeded` | orange | reason |
| `revision_started` | blue | revision_number |
| `revision_completed` | blue | quality_score |
| `structured_validation` | green/red | success, validation_error |
| `run_completed` | green | — |
| `run_error` | red | error message |
| `run_cancelled` | yellow | reason |

**Detail view (click an event):**
- Full payload as formatted JSON
- Raw `AgentRunEvent.to_dict()` output

**Grounding:** Reads directly from `AgentRunTrace` and its `events`
list. Every field shown maps to an existing dataclass attribute.
No synthetic or derived data beyond what `_build_trace()` already
computes.

---

## D. Data / Config Model

The console reads and writes a single configuration object that
maps 1:1 to the arguments of `build_agent()` and the runtime
objects passed to `run_stream()`.

### Proposed config shape (JSON)

```json
{
  "version": "1",
  "agent": {
    "factory": "build_agent",
    "adapter": {
      "type": "MockLLMAdapter",
      "params": {
        "default_response": "Hello world."
      }
    },
    "tier": "consumer"
  },
  "tools": {
    "search": {
      "description": "Search for information",
      "risk_level": "read_only",
      "capabilities": ["research"],
      "requires_confirmation": false,
      "min_confidence": 0.3,
      "timeout_seconds": 30.0,
      "input_schema": {}
    },
    "save_report": {
      "description": "Save report to storage",
      "risk_level": "write",
      "capabilities": ["persistence"],
      "requires_confirmation": true,
      "min_confidence": 0.5,
      "timeout_seconds": 30.0,
      "input_schema": {}
    }
  },
  "action_mapping": {
    "search": "search",
    "save": "save_report"
  },
  "approval": {
    "require_all": false,
    "require_approval_for": ["save"]
  },
  "budget": {
    "max_total_tokens": 10000,
    "max_input_tokens": null,
    "max_output_tokens": null,
    "max_cost": 0.50
  },
  "structured_output": {
    "mode": "none",
    "schema_ref": null
  }
}
```

### How config maps to runtime objects

| Config section | Runtime object | Construction |
|---------------|----------------|-------------|
| `agent.factory` | — | Selects `build_agent()` vs `build_cg_mcp_agent()` |
| `agent.adapter` | LLM adapter instance | Resolved by type name + params |
| `tools.*` | `Dict[str, ToolSpec]` | Each entry → `ToolSpec(handler=..., ...)` |
| `action_mapping` | `action_type_to_tool: Dict[str, str]` | Passed to `build_agent()` |
| `approval` | `ApprovalPolicy` | `ApprovalPolicy(require_all=..., require_approval_for=frozenset(...))` |
| `budget` | `BudgetPolicy` | `BudgetPolicy(max_total_tokens=..., ...)` |
| `structured_output.schema_ref` | `SchemaTarget` | Resolved by import path at runtime |

### What the config does NOT contain

- **Tool handler functions.** Handlers are Python callables — they
  cannot be serialized to JSON. The config stores tool metadata
  only. Handler registration happens in code. The console shows
  "(handler: code-defined)" for each tool.
- **Approval callback.** The function that decides approve/deny is
  code-only. The config stores policy (which actions need approval),
  not logic (how to decide).
- **Schema type definitions.** Dataclass/Pydantic models are Python
  types. The config stores an import path reference
  (e.g. `"myapp.schemas.ResearchAnswer"`), not the type itself.

### Config file location

Convention: `agent.config.json` in the project root, or passed as
a CLI argument. The console reads this on startup and writes it on
save. The config is optional — the console works without it by
reading the agent's current in-memory state.

---

## E. User Workflow

### First-use flow

```
1. Create or load agent
   ├── "New Agent" → choose factory (build_agent / build_cg_mcp_agent)
   │                → choose adapter type
   │                → choose stub/dev or real mode
   └── "Load Config" → import agent.config.json

2. Register / inspect tools
   ├── Tools registered in code via ToolSpec (code-first)
   └── Console shows Tool Catalog (read-only inspection)

3. Map action types to tools
   ├── Console pre-fills identity mapping (action_type == tool_name)
   ├── Developer adds/overrides specific mappings
   └── Validation shows missing tools or unmapped types

4. Configure approval policy
   ├── Toggle require-all or select per-action-type
   └── Preview shows which actions will trigger approval

5. Configure budget policy
   ├── Set token caps and/or cost caps
   └── Leave blank for no limits

6. (Optional) Configure structured output
   ├── Choose schema mode (none / dataclass / dict / pydantic)
   └── Provide import path for the schema type

7. Run agent
   ├── Enter prompt
   ├── Click "Run" → live event stream
   ├── Approval prompts appear inline if policy requires them
   └── Cancel button available during execution

8. Inspect trace
   ├── Summary card: status, actions, tokens, approvals, budget
   └── Event timeline: drill into each event's payload

9. Refine configuration
   ├── Adjust approval/budget/mapping based on trace insights
   └── Re-run to verify

10. Export
    ├── "Export as JSON" → agent.config.json
    └── "Export as Python" → generates build_agent() code
```

### The "Export as Python" output

This is the key bridge between low-code and code-first. The console
generates working Python that reproduces the current configuration:

```python
# Generated by Agentic Developer Console
from agentic.agentic_framework.agent_builder import build_agent
from agentic.agentic_framework.mcp_gateway import ToolSpec, ToolRiskLevel
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.approval import ApprovalController, ApprovalPolicy
from agentic.agentic_framework.token_budget import BudgetPolicy

agent = build_agent(
    adapter=MockLLMAdapter(default_response="..."),
    tools={
        "search": ToolSpec(
            # handler must be provided in code
            handler=YOUR_SEARCH_HANDLER,
            description="Search for information",
            risk_level=ToolRiskLevel.READ_ONLY,
            capabilities=["research"],
        ),
    },
    action_type_to_tool={
        "search": "search",
    },
)
agent.new_session()

approval = ApprovalController(
    policy=ApprovalPolicy(require_approval_for=frozenset({"save"})),
    callback=YOUR_APPROVAL_CALLBACK,
)
budget = BudgetPolicy(max_total_tokens=10000, max_cost=0.50)

for event in agent.run_stream(
    "your prompt here",
    approval_controller=approval,
    budget_policy=budget,
):
    ...  # handle events
```

The generated code uses `YOUR_SEARCH_HANDLER` and
`YOUR_APPROVAL_CALLBACK` as explicit placeholders — the developer
must fill these in. The console never pretends that callable logic
can be configured without code.

---

## F. Developer Ergonomics Insights

Lessons from the onboarding work, ergonomics pass, and research
assistant pilot that should inform this interface.

### Friction points this interface should solve

**F1: Composition boilerplate (high impact)**
Before `build_agent()`, wiring a governed agent required ~25 lines
of manual composition (MockMCPClient → SafeMCPGateway →
register_tool → CGToolDispatcher → AgenticLLMWrapper). `build_agent`
reduced this to ~10 lines, but approval policy, budget policy, and
action mapping still require separate object construction. The
console should make these one-click configurations.

**F2: Trace inspection is manual (high impact)**
Today, inspecting a trace means writing a `for event in
agent.run_stream(...)` loop with `if/elif` branches for each event
type, or calling `trace.summary` and printing fields. The pilot
research assistant has 50+ lines just for event display. The trace
viewer panel eliminates this entirely.

**F3: Action mapping is invisible (medium impact)**
The relationship between goal-decomposition action types and MCP
tool names is a `Dict[str, str]` buried in constructor arguments.
Developers don't see which action types exist until they read goal
decomposition output. The action mapping panel makes this explicit
and validates it against the tool catalog.

**F4: Approval policy effect is hard to preview (medium impact)**
A developer sets `ApprovalPolicy(require_approval_for={"save"})` but
has no way to see which of their action types will actually trigger
approval without running the agent. The approval preview panel
solves this by calling `policy.requires_approval()` for each
mapped action type.

**F5: Two factory functions cause confusion (low-medium impact)**
`build_agent` vs `build_cg_mcp_agent` — developers don't know which
to use. The runtime mode selector panel explains the choice and
guides the decision (default: `build_agent` unless you need CG
signals).

**F6: Structured output feedback loop (low-medium impact)**
When structured output validation fails, the developer gets a
`validation_error` string and `raw_text` but no guidance on what
went wrong. The structured output panel shows the schema, the raw
text, the parsed attempt, and the validation error side by side.

### Friction points this interface should NOT try to solve

- **Tool handler implementation.** Writing the function that a tool
  calls is inherently a coding task. The console should not attempt
  to generate handler code.
- **LLM prompt engineering.** The quality of goal decomposition
  depends on the LLM and the prompt. The console shows what the
  LLM produced but does not try to optimize prompts.
- **CG signal tuning.** Sovereign state signals (S1-S4) and core
  pipeline signals (C1-C4) are internal governance inputs. They are
  not developer-configurable and should not be exposed in the
  console.

---

## G. Honest Risks

### R1: Hiding too much architecture
**Risk:** The console abstracts away the composition pipeline,
making developers dependent on the UI without understanding what
`SafetyGate`, `SafeMCPGateway`, or `CGToolDispatcher` do.

**Mitigation:** Every panel shows which runtime object it
configures. The "Export as Python" feature generates the full
composition code. The console is a lens on the architecture, not
a replacement for it.

### R2: Creating a second source of truth
**Risk:** Config lives in `agent.config.json` while the real
agent is built in Python code. These drift apart.

**Mitigation:** The config file is optional and explicitly
secondary. The console can read from a live agent's in-memory
state (primary) or from a config file (secondary). "Export as
Python" is the canonical way to persist — the JSON config is a
convenience, not the source of truth.

### R3: Making the interface too magical
**Risk:** Developers click buttons without understanding what
`ApprovalPolicy(require_all=True)` means, then are confused
when behavior changes in code.

**Mitigation:** Every configurable field shows its runtime type
name and constructor argument name. Tooltips show the actual
Python expression. The console is explicitly a "developer
console", not a "no-code builder".

### R4: Exposing CG/symbolic concepts too early
**Risk:** The runtime mode selector shows "CG-capable adapter"
and "sovereign state signals", confusing developers who just
want to call OpenAI.

**Mitigation:** The default path is `build_agent` with no CG
concepts. The CG path is an "Advanced" option with a clear
explanation: "Use this only if your adapter exposes
`last_cg_metadata` (e.g. MistralCGAdapter)." Most developers
never need to see this.

### R5: Trying to do no-code too early
**Risk:** Scope creep toward visual workflow editing, drag-and-drop
tool composition, or business-user dashboards before the governed
runtime has broader adoption.

**Mitigation:** The scope boundary (Section B) explicitly excludes
these. The first version is a developer inspection and
configuration console, not a platform.

### R6: Console development outpacing runtime adoption
**Risk:** Building a polished console for a runtime that has one
pilot use case and no production deployments. The console becomes
a demo artifact rather than a useful tool.

**Mitigation:** See Section H (recommendation). The console should
be built only after at least one more real adoption cycle proves
the runtime surface is stable.

---

## H. Code Escape Hatch

The low-code layer must never be a ceiling. The escape hatch story:

### When a developer must drop to code

| Situation | Why code is required |
|-----------|---------------------|
| Writing tool handler functions | Handlers are arbitrary Python callables |
| Custom approval callback logic | Approve/deny decisions require business logic |
| Defining dataclass/Pydantic schemas | Python types cannot be authored in JSON |
| Custom event processing | `run_stream()` consumers need arbitrary logic |
| Multi-turn session management | Session state and memory are code-managed |
| Adapter configuration beyond type+params | Custom adapters, API key management, retry policies |
| Integrating with external systems | Database, API, queue — all code |

### What the console should export

1. **JSON config** — `agent.config.json` for the declarative parts
   (tools metadata, action mapping, approval policy, budget policy)
2. **Python code** — a complete `build_agent()` script with
   placeholder callables. This is the primary export — a developer
   takes this, fills in handlers and callbacks, and runs it.
3. **Individual snippets** — "Copy as Python" on any panel generates
   just that panel's configuration as a Python expression.

### The invariant

**The code API is always the superset.** Everything the console can
do, code can do. The console can never configure something that code
cannot express. If a feature requires the console to work, it is
designed wrong.

---

## I. Runtime Mode Selection (Detail)

### What the developer sees

A radio-button group with two options:

**Option 1: General governed agent (default)**
- Factory: `build_agent()`
- Adapter: any (`MockLLMAdapter`, `OpenAIAdapter`, `AnthropicAdapter`, etc.)
- Governance: risk classification + confidence thresholds from `ToolSpec`
- CG signals: not used
- When to use: "Start here. Works with any LLM provider."

**Option 2: CG-enriched governed agent**
- Factory: `build_cg_mcp_agent()`
- Adapter: must expose `last_cg_metadata` (`MistralCGAdapter`, `StubCGLLMAdapter`)
- Governance: risk classification + confidence thresholds + model-internal signals (entropy, vritti, coherence)
- CG signals: used for richer per-tool gating
- When to use: "Use this when your adapter provides CG metadata. Enables signal-enriched governance."

**Sub-option (under either):**
- Stub/dev mode: uses `MockLLMAdapter` or `StubCGLLMAdapter` — no API key, no GPU
- Real mode: uses a real adapter — requires API key or local model

**What the console does NOT show:**
- Internal signal details (S1-S4 phases, entropy adapters, vritti resolution)
- Governance penalty math (confidence adjustments, escalation bias)
- Generation gate state (seal/unseal) — this is boot-time internal

### Honest labeling

The console shows:
- "Stub/dev mode — deterministic responses, no real inference"
- "CG signals — model-internal governance signals (requires CG-capable adapter)"

It does NOT show:
- "AI-powered governance" or "intelligent safety"
- Claims about production readiness beyond what FRAMEWORK_STATUS.md states

---

## J. Final Recommendation

**Should this be built next, or only after one more real adoption cycle?**

### Recommendation: Build after one more adoption cycle.

**Rationale:**

1. **The runtime surface is stable and well-tested** (1500+ tests,
   R1-R11 all proved). The governed pipeline works.

2. **But adoption is narrow.** One pilot (research assistant), three
   example scripts, and one CLI entry point. No external team has
   used the runtime in a real application.

3. **The highest-value console panel (trace viewer) can be built
   standalone** without the full console. A `trace_viewer(trace)`
   utility function that renders an `AgentRunTrace` to formatted
   output would deliver 60% of the console's value at 10% of the
   cost.

4. **The config model (Section D) is speculative.** We designed it
   from the runtime API, but we don't know if real developers want
   JSON config or prefer code-only. One more adoption cycle would
   answer this.

5. **The risk of console-before-adoption is real (Risk R6).** A
   polished console for a runtime with one pilot becomes a demo
   artifact, not a tool.

### Suggested sequencing

| Phase | What to build | Why |
|-------|--------------|-----|
| **Next** | `trace_viewer()` utility — renders `AgentRunTrace` to terminal | Highest-value, lowest-cost, immediately useful |
| **Next** | Second pilot use case with a different tool set | Validates runtime generality, surfaces new friction |
| **After second pilot** | JSON config loader for `build_agent()` | If developers ask for declarative config |
| **After config loader** | Full developer console (this spec) | Enough adoption signal to justify the investment |

### What to do with this spec now

Keep it as a design reference. When the second pilot is complete,
revisit Sections C-E to see if the panel design still matches
reality. The spec is grounded in current runtime truth — if the
runtime changes, the spec should be updated before implementation
begins.
