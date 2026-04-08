# Goal Decomposition and Action Mapping

How the framework turns a user prompt into governed tool calls.

---

## 1. What goal decomposition is

The model does not call tools directly. Instead, the framework asks
the model to produce a **structured decomposition** of the user's
request — a list of actions the agent should take.

```
user prompt
    ↓
LLM produces structured JSON: purpose, reasoning, actions[]
    ↓
framework parses actions, normalizes types, maps to tools
    ↓
each action goes through safety gate → approval → budget → tool execution
```

The decomposition prompt asks the model to emit actions with one of
five generic types: `search`, `compute`, `generate`, `validate`,
`execute`. Each action also has a `description` and `parameters`.

This structured output is what the governed runtime operates on — not
free-form text.

---

## 2. What an action type is

An **action type** is the label the runtime uses to decide what kind
of action the agent wants to take. Action types drive two things:

1. **Tool routing** — which registered tool handles this action
2. **Policy matching** — which approval/governance rules apply

There are two vocabularies:

| Vocabulary | Examples | Source |
|-----------|----------|--------|
| **Generic** (prompt-side) | `search`, `compute`, `generate`, `validate`, `execute` | Produced by the LLM from the decomposition prompt |
| **Domain** (developer-side) | `check_alerts`, `save_draft`, `send_update`, `escalate` | Defined by the developer when registering tools |

The framework bridges these two vocabularies through **normalization**
and **action mapping** (explained below).

---

## 3. What action mapping is

`action_type_to_tool` is a dict that maps action types to tool names.
It tells the runtime: "when the agent wants to do X, use tool Y."

### Simple case: identity mapping

When your tool names match the action types, the mapping is trivial.
`build_agent()` creates this automatically from your `tools` dict:

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, ToolSpec, ToolRiskLevel,
)

agent = build_agent(
    adapter=MockLLMAdapter(default_response="..."),
    tools={
        "search": ToolSpec(handler=search_fn, description="Search", risk_level=ToolRiskLevel.READ_ONLY),
        "save": ToolSpec(handler=save_fn, description="Save", risk_level=ToolRiskLevel.WRITE),
    },
    # No action_type_to_tool needed — defaults to {"search": "search", "save": "save"}
)
```

### When you need an explicit mapping

Real LLMs produce generic types (`search`, `execute`, `generate`),
not your domain tool names (`check_alerts`, `save_draft`). You need
to tell the framework how to route them:

```python
agent = build_agent(
    adapter=my_real_adapter,
    tools={
        "check_alerts": ToolSpec(handler=check_fn, ...),
        "save_draft": ToolSpec(handler=save_fn, ...),
        "send_update": ToolSpec(handler=send_fn, ...),
    },
    action_type_to_tool={
        # Identity mappings (domain types the LLM might also produce)
        "check_alerts": "check_alerts",
        "save_draft": "save_draft",
        "send_update": "send_update",
        # Generic → domain mappings
        "search": "check_alerts",
        "compute": "check_alerts",
        "execute": "save_draft",
    },
)
```

### What happens to unmapped types

An action whose type is not in `action_type_to_tool` does not
disappear silently. The runtime sets an explicit error on the action:

```
Unmapped action type: 'generate'. Add it to action_type_to_tool to route through MCP.
```

This appears in the trace as a failed action. This is intentional —
fail-visible, not fail-silent.

---

## 4. Why normalization exists

### The problem

The decomposition prompt tells the LLM to use five generic types:
`search`, `compute`, `generate`, `validate`, `execute`. But your
workflow might need `save_draft`, `send_update`, or `escalate`.

Static mapping (`"execute": "save_draft"`) works when there's only
one possible target. But what if `execute` should sometimes mean
`save_draft` and sometimes mean `send_update`?

### How normalization works

`normalize_action_type()` runs before action mapping. It uses a
three-step resolution:

1. **Static alias** — if the type is a key in `action_type_to_tool`,
   use the mapped value directly (e.g. `"save": "save_draft"`)

2. **Canonical match** — if the type is already a registered tool
   name, keep it (e.g. `"save_draft"` stays `"save_draft"`)

3. **Context-aware resolution** — if the type is generic (`execute`,
   `generate`) and the action's **description** contains keywords
   that signal a specific domain tool, route there:
   - Description says "send update to team" → `send_update`
   - Description says "save draft report" → `save_draft`
   - Description says "escalate to on-call" → `escalate`

   This only fires when exactly one domain tool is signalled. If the
   description is ambiguous (signals multiple tools or none), the
   generic type passes through unchanged.

### What normalization is NOT

- It is **not a hidden planner**. It uses a fixed keyword dict, not
  LLM inference.
- It is **not fuzzy matching**. Keywords are exact string lookups.
- It is **deterministic**. Same input → same output, every time.
- It is **fail-closed for ambiguity**. If the description doesn't
  clearly point to one tool, the generic type passes through and the
  developer's `action_type_to_tool` mapping handles it (or it fails
  visibly as unmapped).

### Traceability

When normalization changes an action type, the original is preserved:

```python
action.action_type          # "send_update" (after normalization)
action.original_action_type # "execute" (what the LLM produced)
```

This shows up in trace output and structured logging.

---

## 5. How this fits into governance

```
user input
    ↓
GoalDecomposition  →  ActionItems (with raw action types from LLM)
    ↓
normalize_action_type()  →  canonical action types
    ↓
action_type_to_tool  →  concrete tool names
    ↓
SafetyGate  →  turn-level coherence pre-gate
    ↓
For each action:
    ├── CancellationToken check
    ├── BudgetPolicy check
    ├── ApprovalPolicy check (callback)
    └── SafeMCPGateway → tool execution → result
    ↓
AgentRunTrace  (every step recorded)
```

**Key point:** approval policies match on the **normalized** action
type, not the raw LLM output. So if you set
`require_approval_for=frozenset({"save_draft"})`, it catches both
actions that the LLM directly labeled `save_draft` and actions that
were normalized from `execute` to `save_draft`.

---

## 6. Common failure modes

### "My tool never gets called"

**Cause:** The LLM produces a generic type (e.g. `generate`) that
isn't in your `action_type_to_tool`, and your tool is registered
under a domain name (e.g. `save_draft`).

**Fix:** Add a mapping: `"generate": "save_draft"` in
`action_type_to_tool`, or rely on context-aware normalization if
the action description contains the right keywords.

**How to spot it:** The trace shows:
```
ACTION << : error — Unmapped action type: 'generate'
```

### "Approval never triggers"

**Cause:** Your `ApprovalPolicy` gates `"save_draft"`, but the LLM
produces `"execute"` and there's no normalization or mapping that
turns it into `"save_draft"`.

**Fix:** Either add the mapping or add `"execute"` to the approval
set. Check which action types actually appear using the trace.

### "Tool runs but shouldn't have"

**Cause:** A generic type like `execute` is mapped to a write tool
(e.g. `"execute": "save_draft"`) but the LLM used `execute` for a
different intent (e.g. "execute the search"). The static mapping
routes it to the wrong tool.

**Fix:** Remove the static mapping for ambiguous types and let
context-aware normalization handle it based on the description.
Or, add more specific mappings.

### "Both approval layers block my action"

**Cause:** You set `ApprovalPolicy(require_approval_for={"save"})` 
**and** `ToolSpec(..., requires_confirmation=True)` on the same
tool. The action must pass both gates.

**Fix:** Use one layer, not both. `ApprovalPolicy` (Layer 1) is the
simple, visible choice. `requires_confirmation` (Layer 2) is for
tools that are inherently dangerous regardless of policy. See
[Quickstart § Two Approval Layers](QUICKSTART.md#two-approval-layers).

### "Mock works but real LLM doesn't"

**Cause:** `MockLLMAdapter` returns your fixed string, which may
parse as exact action types. A real LLM produces its own action
types from the decomposition prompt (usually generic ones).

**Fix:** Add generic-to-domain mappings in `action_type_to_tool`.
See [Mock → Real LLM](MOCK_TO_REAL_LLM.md) for the full transition
guide.

---

## 7. How to debug

### Check the trace

`format_trace()` shows every event in order. Look for:

```
SAFETY       eligible            ← did the safety gate pass?
APPROVE?     save_draft: ...     ← was approval requested?
APPROVE:     approved (...)      ← was it granted?
ACTION >>    save_draft: ...     ← did the action start?
ACTION <<    : completed         ← did it succeed?
ACTION <<    : error — Unmapped  ← unmapped type (fix your mapping)
```

### Check approval coverage before running

```python
from agentic.agentic_framework import (
    describe_approval_coverage, format_approval_coverage,
    ApprovalPolicy, ToolCatalog,
)

coverage = describe_approval_coverage(
    action_type_to_tool={"search": "search", "save": "save_draft"},
    approval_policy=ApprovalPolicy(require_approval_for=frozenset({"save"})),
    catalog=ToolCatalog.from_agent(agent),
)
print(format_approval_coverage(coverage))
```

This shows which action types are gated at which layer — before you
run anything.

### Check the tool catalog

```python
from agentic.agentic_framework import ToolCatalog

catalog = ToolCatalog.from_agent(agent)
for tool in catalog.list_tools():
    print(f"  {tool.name} [{tool.risk_level}] — {tool.description}")
```

### Inspect normalization in the trace

When normalization changes a type, the trace's goal state records it:

```python
for action in agent._goal_state.actions:
    if action.original_action_type:
        print(f"  {action.original_action_type} → {action.action_type}")
```

---

## 8. Practical example: alert triage

A governed alert triage assistant with three tools:

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, ToolSpec, ToolRiskLevel,
    ApprovalPolicy, ApprovalController, ApprovalResponse,
    BudgetPolicy, format_trace,
)

# Tools
TOOLS = {
    "check_alerts": ToolSpec(
        handler=lambda p: {"alerts": [{"id": "ALT-1", "severity": "critical"}]},
        description="Check monitoring alerts",
        risk_level=ToolRiskLevel.READ_ONLY,
    ),
    "acknowledge_alert": ToolSpec(
        handler=lambda p: {"acked": True, "id": p.get("alert_id")},
        description="Acknowledge an alert",
        risk_level=ToolRiskLevel.WRITE,
    ),
    "escalate_alert": ToolSpec(
        handler=lambda p: {"escalated": True, "id": p.get("alert_id")},
        description="Escalate to on-call",
        risk_level=ToolRiskLevel.WRITE,
    ),
}

# Action mapping: identity + generic-to-domain
MAPPING = {
    "check_alerts": "check_alerts",
    "acknowledge_alert": "acknowledge_alert",
    "escalate_alert": "escalate_alert",
    "search": "check_alerts",       # LLM "search" → check_alerts
    "compute": "check_alerts",      # LLM "compute" → check_alerts
    # "execute" and "generate" are NOT statically mapped here.
    # Context-aware normalization routes them via description keywords.
}

# Approval: write tools need sign-off
policy = ApprovalPolicy(
    require_approval_for=frozenset({"acknowledge_alert", "escalate_alert"}),
)

def my_callback(pending):
    if pending.action_type == "acknowledge_alert":
        return ApprovalResponse(approved=True, reason="Acks pre-approved")
    return ApprovalResponse(approved=False, reason="Needs IC approval")

ctrl = ApprovalController(policy=policy, callback=my_callback)
budget = BudgetPolicy(max_total_tokens=5000, max_cost=0.50)

# Build and run
agent = build_agent(
    adapter=MockLLMAdapter(default_response="..."),  # or a real adapter
    tools=TOOLS,
    action_type_to_tool=MAPPING,
    allow_stub=True,
)
agent.new_session()

trace = agent.run_with_trace(
    "Check current alerts and escalate any critical ones",
    approval_controller=ctrl,
    budget_policy=budget,
)
print(format_trace(trace))
```

**What happens at runtime:**
1. LLM decomposes the prompt into actions (e.g. `search` + `execute`)
2. `search` maps to `check_alerts` via `action_type_to_tool`
3. `execute` with description "escalate critical alert" normalizes to
   `escalate_alert` via description keywords
4. `check_alerts` executes freely (READ_ONLY, no approval)
5. `escalate_alert` triggers approval → denied by callback
6. Trace records everything

---

## See also

- [Quickstart](QUICKSTART.md) — first agent + API orientation
- [Mock → Real LLM](MOCK_TO_REAL_LLM.md) — adapter transition guide
- [First Governed Agent](FIRST_GOVERNED_AGENT.md) — feature-by-feature build guide
- [Examples Overview](EXAMPLES_OVERVIEW.md) — all runnable examples
