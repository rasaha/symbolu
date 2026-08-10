# Why Agentic Is Different

This document explains how the Agentic Framework differs from generic
agent SDKs and what its governance layer actually does at runtime.

---

## Table-stakes vs differentiated

| Capability | Table-stakes (most frameworks have this) | Agentic's differentiation |
|-----------|----------------------------------------|--------------------------|
| LLM adapter abstraction | Yes — OpenAI, Anthropic, Mistral, Gemini | Same. Multiple adapters with a common `BaseLLMAdapter` interface. |
| Tool / function calling | Yes — register tools, LLM decides when to call | Yes, but every tool call passes through per-call governance (risk classification, confidence gating, audit log). |
| Streaming | Yes — token-level streaming | Yes, plus **structured lifecycle events** (17 event types covering generation, actions, approvals, budget, errors). |
| Prompt construction | Yes — system prompts, templates | Yes, plus schema-aware prompt augmentation for structured outputs and adaptive reasoning depth. |

| Capability | Not common in generic SDKs | How Agentic does it |
|-----------|---------------------------|---------------------|
| **Turn-level safety gate** | Rare | `SafetyGate` evaluates coherence metrics (consistency, goal alignment, reversal risk, identity stability) before any action executes. If the gate blocks, the dispatcher is never called. |
| **Per-tool risk classification** | Rare | Each tool has a declared `risk_level` (read_only → write → execute → destructive → privileged), `min_confidence`, and `requires_confirmation`. The gateway enforces these at call time. |
| **Human-in-the-loop approvals** | Some frameworks | `ApprovalController` with configurable `ApprovalPolicy` — require approval for specific action types or all actions. The approval gate is wired into the action loop, not bolted on after the fact. |
| **Budget enforcement** | Rare | `BudgetPolicy` with hard caps on total/input/output tokens and cost. Budget is checked after each generation and before each action — budget exceedance is a terminal event. |
| **Signal-enriched governance** | Unique | When a CG-capable adapter is used, each tool call is enriched with entropy and coherence signals derived from the model's 32D internal state. Governance decisions use these signals, not just text output. |
| **In-memory tracing** | Some frameworks | `TraceCollector` records all events; `AgentRunTrace` provides a complete run summary with action counts, approval counts, usage stats, and budget status. No external dependency. |
| **Tool introspection** | Rare | `ToolCatalog` provides read-only discovery of registered tools with filtering by risk level, capability, and confirmation requirements. |

---

## How the governed execution path works

This is the action loop ordering, pinned by tests:

```
user_input
    │
    ▼
GoalDecomposition → ActionItems
    │
    ▼
ReflectiveGenerator → LLM response (with optional self-revision)
    │
    ▼
CoherenceEngine → coherence state
    │
    ▼
SafetyGate → eligible action types (turn-level pre-gate)
    │
    ▼
For each eligible action:
    ├── Cancellation check → stop if cancelled
    ├── Budget check → stop if exceeded (BUDGET_EXCEEDED event)
    ├── Approval gate → request human approval if required
    ├── ACTION_STARTED event
    ├── Execute via dispatcher → SafeMCPGateway (per-call governance)
    └── ACTION_COMPLETED event
    │
    ▼
RUN_COMPLETED event + AgentRunTrace
```

Key properties:
- Budget is checked **before** the approval gate — no point asking
  for approval if the budget is already blown.
- Cancellation is checked **before** budget — an already-cancelled
  run stops immediately.
- `SafetyGate` and `SafeMCPGateway` are **complementary**, not
  redundant. The gate operates at the turn level; the gateway
  operates per tool call.

---

## Signal enrichment (CG metadata path)

When a CG-capable LLM adapter (e.g., `MistralCGAdapter`) is used,
the framework enriches governance decisions with signals derived from
the model's internal state:

- **Entropy signal** — measures the model's internal uncertainty.
  High entropy can indicate the model is less confident in its
  output, triggering more conservative governance.
- **Vritti signal** — measures coherence/fluctuation in the model's
  internal state. Abnormal vritti patterns can indicate the model
  is producing less stable output.

These are not prompt-level confidence scores or self-reported
uncertainty. They are derived from the model's 32-dimensional state
tensor after inference. The governance layer uses them as additional
inputs when deciding whether a tool call should proceed.

When a non-CG adapter is used (OpenAI, Anthropic, etc.), the
governance path still works — it just uses text-level signals
(quality scores, coherence metrics) instead of model-internal
signals.

---

## Honest caveats

### What competitors still do better

| Area | Current state |
|------|--------------|
| **Multi-agent orchestration** | Frameworks like LangGraph, CrewAI, and AutoGen provide agent-to-agent handoffs, orchestration graphs, and multi-agent coordination. Agentic governs a single agent's execution path. |
| **Managed infrastructure** | Platforms like AWS Bedrock Agents, Vertex AI Agent Builder provide hosted execution, scaling, and monitoring. Agentic is a library, not a managed service. |
| **External telemetry** | Frameworks with OpenTelemetry or LangSmith integration provide cloud-based observability. Agentic's tracing is in-memory and local. |
| **Broad ecosystem / community** | LangChain, LlamaIndex, and similar frameworks have larger ecosystems of integrations, templates, and community plugins. |
| **Production adoption breadth** | Agentic's single runnable entry point is the CLI. Broader runtime adoption (web, voice, API servers) is not yet migrated. |

### What remains out of scope

- No agent-to-agent communication or delegation
- No built-in RAG / vector store integration (bring your own)
- No hosted deployment or scaling infrastructure
- No external audit log persistence (in-memory only)
- Real local model inference (`MistralCGAdapter`) is
  operator-validated, not repo-validated — it requires a torch +
  GPU environment outside the repo's test harness

---

## See also

- [README](../README.md) — entry point with quickstart code
- [What Is Agentic Framework](WHAT_IS_AGENTIC_FRAMEWORK.md) — overview
- [Quickstart](QUICKSTART.md) — setup, first code, API orientation
- [First Governed Agent](FIRST_GOVERNED_AGENT.md) — build guide
- [Framework Status](FRAMEWORK_STATUS.md) — maturity status
