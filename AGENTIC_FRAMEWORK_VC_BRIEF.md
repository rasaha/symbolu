# Agentic Framework — VC Brief

**Cognade Labs | Governed Runtime for Autonomous AI Agents**
*Version 1.9.0 — Prepared April 2026*

---

## Page 1 — The Problem

### Enterprises want AI agents. They cannot deploy them.

The last 18 months produced a flood of "agent frameworks" — LangChain,
LangGraph, CrewAI, AutoGen, AWS Bedrock Agents. They solved the *easy*
half of the problem: wiring an LLM to a tool-calling loop. They left the
*hard* half — the half that blocks production — untouched.

When a regulated enterprise tries to put an autonomous agent in front of
real customers, real money, or real infrastructure, four questions surface
immediately. Today's frameworks cannot answer any of them with evidence.

| The question the CISO asks | What current frameworks offer |
|---|---|
| *"Can this agent refuse to do something unsafe before it happens?"* | Post-hoc content filters. The action has already fired. |
| *"Can a human approve destructive actions without rewriting the agent?"* | Bolt-on middleware, inconsistent per-framework, untested edges. |
| *"Can I prove what the agent did, step by step, for audit?"* | External telemetry SaaS, prompt logs, no causal trace. |
| *"Can I cap spend before a runaway loop burns $40k overnight?"* | Soft warnings, after-the-fact dashboards. |

**The result:** 78% of enterprise AI pilots never reach production.
The #1 cited blocker in 2025 is not model quality — it is *governance*.
Agents are powerful enough to be useful and unsafe enough to be uninsurable.

### Why the existing stack cannot fix this

Governance in current frameworks is **retrofitted**. Safety, approvals,
budgets, and audit logs are middleware layered *around* a core loop that
was designed to "call the LLM and hope." The ordering of checks is
undocumented. The gate between "LLM decided to act" and "action executed"
is porous. A single prompt-injection or hallucinated tool name slips
through the seam.

What the market actually needs is a runtime where governance is a
*first-class property of the execution path itself* — where the action
loop is pinned by tests, every tool call passes through classification,
every action is approvable, and every run produces an in-memory trace
that a human (or auditor) can replay.

That runtime does not exist in the open market today. **We built it.**

---

## Page 2 — The Architecture

### Agentic Framework — Governance wired into the execution path

Agentic Framework is a **code-first Python library** that wraps any LLM
(OpenAI, Anthropic, Mistral, local models) and turns it into a *governed*
autonomous agent. Every action the agent takes is observable, auditable,
and interruptible — not because we bolted on middleware, but because the
runtime contract itself enforces it.

### The governed execution path (pinned by tests, not configurable)

```
  user_input
      │
      ▼
  GoalDecomposition  ──► structured ActionItems
      │
      ▼
  ReflectiveGenerator ──► LLM response (+ optional self-revision)
      │
      ▼
  CoherenceEngine    ──► turn-level coherence state
      │
      ▼
  SafetyGate         ──► eligible actions  (turn-level pre-gate)
      │
      ▼
  For each eligible action:
      ├── 1. Cancellation check      (async stop at checkpoints)
      ├── 2. Budget check            (hard token + cost caps)
      ├── 3. Approval gate           (human-in-the-loop, per action type)
      ├── 4. ACTION_STARTED event
      ├── 5. SafeMCPGateway          (per-tool risk + confidence + audit)
      └── 6. ACTION_COMPLETED event
      │
      ▼
  RUN_COMPLETED  +  AgentRunTrace   (in-memory, replayable)
```

The ordering — **cancel → budget → approve → execute** — is not a
suggestion. It is a runtime invariant verified by the test suite. A run
that is already cancelled never hits the budget. A run that blows the
budget never asks for approval. A denied approval never fires a tool.

### The two governance layers — complementary, not redundant

| Layer | Scope | Decides |
|---|---|---|
| **SafetyGate** | Turn-level | *"Given the model's current coherence state, is any action allowed to run this turn?"* |
| **SafeMCPGateway** | Per tool call | *"Given this specific tool's risk level, the model's confidence, and signal-level entropy, should this call proceed?"* |

Every tool registered with the agent declares a `risk_level`
(`read_only → write → execute → destructive → privileged`), a
`min_confidence`, and whether it `requires_confirmation`. The gateway
enforces these at call time — the LLM cannot opt out.

### Signal-enriched governance (our moat)

When the agent is backed by a **CG-capable adapter** (our
`MistralCGAdapter` or the Phase Quad LLM), governance decisions are
enriched with *model-internal* signals: entropy and vritti (coherence
fluctuation) derived from the 32-dimensional internal state tensor.
These are **not** prompt-level self-reported confidence scores. They are
ground-truth measurements of model uncertainty that prompt-level agents
physically cannot access.

This is the bridge between our full-stack research (Phase Quad LLM,
CTM+ memory, PCAM chip) and an immediately-deployable developer product.
Competitors running on black-box APIs cannot replicate this.

### Developer surface — one call, full governance

```python
from agentic.agentic_framework import build_agent, ToolSpec, ToolRiskLevel

agent = build_agent(
    adapter=AnthropicAdapter(auth_token=...),
    tools={
        "search":      ToolSpec(handler=search_fn,  risk_level=ToolRiskLevel.READ_ONLY),
        "send_email":  ToolSpec(handler=email_fn,   risk_level=ToolRiskLevel.WRITE,
                                requires_confirmation=True),
        "run_payment": ToolSpec(handler=payment_fn, risk_level=ToolRiskLevel.DESTRUCTIVE,
                                requires_confirmation=True),
    },
)
trace = agent.run_with_trace("Process the refund queue")
```

One factory call composes the full stack: adapter, safety gate, dispatcher,
gateway, tracing, budget, approvals. The same code runs against a
`MockLLMAdapter` (zero cost, zero keys) and a live Anthropic or OpenAI
endpoint with no wiring changes.

---

## Page 3 — Benchmarks & Roadmap

### What is proved today (v1.9.0)

| Metric | Result |
|---|---|
| **Test suite** | 1,550+ tests passing across core runtime + primitives |
| **Runtime primitives** | R1–R11 complete — streaming, cancel, approvals, structured output, tool discovery, budgets, tracing |
| **Test evidence per primitive** | Streaming: 28 tests · Cancel: 31 · Approvals: 33 · Structured output: 44 · Discovery: 38 · Budget: 37 · Tracing: 26 · Cross-feature: 23 |
| **Action loop ordering invariant** | Pinned by tests: cancel → budget → approve → execute |
| **Live-adapter end-to-end validation** | 3/3 phases pass against stock Anthropic API with `auth_token` + exact usage accounting |
| **Realistic-mock regression** | 60/60 checks pass across 5 LLM output-format variations |
| **Adoption pilots shipped** | 2 — Research Assistant (full governance) + Internal Copilot (approval boundary) |
| **Known fragility points resolved** | 3 of 4 (FP1 goal alignment, FP2 action vocabulary, FP4 usage accounting). FP3 low-risk, deferred |
| **Signal-enriched governance (CG path)** | Operator-validated on `MistralCGAdapter` — entropy + vritti enrichment live |
| **LLM adapters shipped** | OpenAI · Anthropic · Mistral (CG) · Mock — all behind common `BaseLLMAdapter` |

### Developer-surface benchmarks

| Measure | Before `build_agent()` (v1.7) | After (v1.9) |
|---|---|---|
| Lines to build a governed agent | ~70 | ~10 |
| Files to touch to add approvals | 3 | 0 (runtime arg) |
| Switching mock → real LLM | Rewire 4 components | Swap adapter only |
| Preview which actions are gated | Manual inspection | `describe_approval_coverage()` |
| Human-readable trace | Custom print loop | `format_trace(trace)` |

### Competitive position (honest)

| Area | Us | LangGraph / CrewAI / AutoGen | Bedrock Agents / Vertex |
|---|---|---|---|
| Governed action loop (tested ordering) | **Yes** | Middleware, not pinned | Provider-opaque |
| Per-tool risk classification | **Yes** | Partial | Partial |
| Human-in-the-loop, runtime-arg | **Yes** | Bolt-on | Console-only |
| Hard budget caps as terminal events | **Yes** | Soft/dashboard | Partial |
| Signal-enriched governance (model-internal) | **Unique** | No | No |
| Multi-agent orchestration | No — deferred | **Yes** | **Yes** |
| Managed / hosted runtime | No — library | Partial | **Yes** |
| Ecosystem breadth | Narrow | **Broad** | **Broad** |

We do not claim to win on ecosystem breadth or hosted infrastructure.
We claim to win on **the one thing enterprises cannot ship without:
provable, tested, signal-enriched runtime governance.**

### Next steps — the 12-month roadmap

**Quarter 1 — Adoption & proof**
- 3 additional enterprise pilot integrations (BFSI + healthcare beachhead)
- OpenTelemetry export adapter for `AgentRunTrace` (addresses the #1
  enterprise-evaluator gap in current framework status)
- Published third-party governance benchmark vs LangGraph / CrewAI on a
  standardized suite of safety + approval + budget scenarios

**Quarter 2 — Developer console**
- Ship the **Low-Code Developer Interface** (design spec already
  complete at `docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md`) — drag-and-drop
  tool registration, approval-policy editor, live trace replay
- Managed cloud preview — hosted runtime for teams that do not want a
  Python library

**Quarter 3 — Multi-agent + RAG**
- Agent-to-agent handoffs with **governance preserved across handoff
  boundaries** (the hard version of what CrewAI ships as the easy version)
- First-party retrieval adapter with coherence-scored provenance
- Full Phase Quad LLM integration as a first-class CG adapter, unlocking
  signal-enriched governance by default for Cognade customers

**Quarter 4 — Scale & certification**
- SOC 2 Type II on the managed runtime
- Enterprise audit-log persistence (Postgres + S3-backed)
- Production reference customer at 1M+ governed actions/day

### The ask

We are raising seed to turn a **battle-tested library** into a **managed
governed-runtime product** — the layer every enterprise AI deployment
will need once the first public agent disaster makes governance
non-optional. The technology is live, tested, and pilot-validated today.
The window is the next 12 months.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `agentic/agentic_framework/`*
*Version 1.9.0 · 1,550+ tests · 2 pilots shipped · live-adapter validated*
