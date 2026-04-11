# Agentic Framework — VC Brief

**Cognade Labs | Governed Runtime for Autonomous AI Agents**
*Version 1.9.0 — Prepared April 2026*

---

## Page 1 — The Problem

### Enterprises want autonomous agents. Governance is blocking deployment.

The last 18 months produced a wave of agent frameworks — LangChain,
LangGraph, CrewAI, AutoGen, AWS Bedrock Agents, Vertex AI Agent Builder.
They have made it straightforward to wire an LLM to a tool-calling loop.
What remains genuinely hard is the layer between *"the model decided to
act"* and *"the action executed against a production system"* — the
governance, approval, budget, and audit layer that regulated buyers
require before an autonomous agent can be put in front of customers,
money, or infrastructure.

In enterprise pilots we and our design partners have observed, four
questions consistently come up early — and most current frameworks
answer them only partially:

| The question an enterprise buyer asks | What most current frameworks offer |
|---|---|
| *"Can this agent be stopped before it does something unsafe, not after?"* | Primarily post-hoc content filters and output moderation. |
| *"Can a human approve destructive actions without a custom rewrite?"* | Middleware patterns that vary per framework and per integration. |
| *"Can I reconstruct what the agent did, step by step, for audit?"* | External telemetry or prompt logs — rarely a structured causal trace. |
| *"Can I cap token and dollar spend as a hard stop, not a warning?"* | Usage dashboards and soft alerts, not terminal budget events. |

In practice, a large share of enterprise AI pilots stall before
production, and the blockers our design partners cite most often are not
model quality — they are trust, auditability, approval workflow, and
spend control. Agents are now capable enough to be genuinely useful and
unpredictable enough to be difficult to insure and certify.

### Why retrofitting governance onto existing loops is hard

In most current frameworks, governance is layered *around* a core loop
that was designed primarily to "call the LLM and dispatch tools." Safety,
approvals, budgets, and audit logs tend to be composed as middleware.
The ordering in which these checks run — and how they interact with
cancellation and streaming — is often framework-specific and not always
pinned by tests. The result is that the seam between *"the model asked
to act"* and *"the action executed"* can be porous under edge cases:
prompt injection, hallucinated tool names, partial failures, concurrent
approvals.

Our view is that the market needs a runtime where governance is a
**first-class property of the execution path itself** — where the
action loop ordering is pinned by tests, every tool call passes through
explicit risk classification, every action can be gated for human
approval as a runtime argument, and every run produces a replayable
in-memory trace. That is the category we are building for.

---

## Page 2 — The Architecture

### Agentic Framework — governance wired into the execution path

Agentic Framework is a **code-first Python library** that wraps any LLM
adapter (OpenAI, Anthropic, Mistral, local models via a common
`BaseLLMAdapter`) and turns it into a governed autonomous agent. Every
action is observable, auditable, and interruptible because those
properties are enforced by the runtime contract, not by optional
middleware.

### The governed execution path (pinned by the test suite)

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

The ordering — **cancel → budget → approve → execute** — is a runtime
invariant verified by the test suite, not a configurable option. A run
that is already cancelled does not reach the budget check. A run that
exceeds the budget does not reach the approval gate. A denied approval
does not reach tool execution. This is a deliberately narrow, tested
contract — one of the things we think enterprise buyers will care about
most during diligence.

### Two complementary governance layers

| Layer | Scope | What it decides |
|---|---|---|
| **SafetyGate** | Turn-level | *"Given the current coherence state, is any action allowed to run this turn?"* |
| **SafeMCPGateway** | Per tool call | *"Given this tool's declared risk level, the model's confidence, and enriched signals, should this specific call proceed?"* |

Every tool registered with the agent declares a `risk_level`
(`read_only → write → execute → destructive → privileged`), a
`min_confidence`, and whether it `requires_confirmation`. The gateway
enforces these at call time; the LLM cannot route around them. Turn-level
and per-call governance are complementary — one protects the turn, the
other protects the specific action.

### Signal-enriched governance (our differentiation)

When the agent is backed by a **CG-capable adapter** (our
`MistralCGAdapter`, or the Phase Quad LLM from our broader stack),
governance decisions can be enriched with *model-internal runtime
signals* — entropy and vritti (coherence-fluctuation) values derived
from the model's internal state after inference. These are
state-derived uncertainty and coherence signals, not prompt-level
self-reported confidence scores, and they are not available to
frameworks that only see the text output of a closed API. Our approach
is differentiated here because we control both the adapter interface
and, in the CG path, the model internals.

When a non-CG adapter is used (OpenAI, Anthropic, etc.), the same
governance path still runs — it falls back to text-level signals
(quality scores and coherence metrics). Customers can therefore start
on commercial APIs today and move to the CG path later without rewiring.

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

One factory call composes the full stack: adapter, safety gate,
dispatcher, gateway, tracing, budget, and approvals. The same code runs
against a `MockLLMAdapter` (no cost, no API keys) and a live Anthropic
or OpenAI endpoint with no wiring changes — which makes the library
easy to evaluate before any procurement conversation.

---

## Page 3 — Evidence & Roadmap

### What is proved today (v1.9.0, internal evidence)

| Area | Current state |
|---|---|
| **Test suite** | 1,550+ tests passing across core runtime and R1–R11 runtime primitives |
| **Runtime primitives** | Streaming, async cancellation, approvals, structured output, tool discovery, budgets, tracing — all implemented and tested |
| **Test evidence per primitive** | Streaming: 28 · Cancel: 31 · Approvals: 33 · Structured output: 44 · Discovery: 38 · Budget: 37 · Tracing: 26 · Cross-feature: 23 |
| **Action loop ordering invariant** | Pinned by tests: cancel → budget → approve → execute |
| **Live-adapter end-to-end validation** | 3/3 phases pass against stock Anthropic API with exact usage accounting |
| **Realistic-mock regression** | 60/60 checks across 5 LLM output-format variations |
| **Adoption pilots shipped** | 2 internal pilots — Research Assistant (tool composition + governance) and Internal Copilot (per-action-type approval boundary) |
| **Known fragility points** | 3 of 4 surfaced in real-LLM pilots resolved (goal-alignment gate, action vocabulary normalization, usage accounting). The 4th is low-risk and tracked. |
| **Signal-enriched governance (CG path)** | Operator-validated on `MistralCGAdapter` in a torch/GPU environment; not yet repo-validated end-to-end. |
| **LLM adapters shipped** | OpenAI · Anthropic · Mistral (CG) · Mock — all behind a common `BaseLLMAdapter` |

All numbers above are from our own repository and CI — not third-party
benchmarks. An external benchmark is planned (see roadmap).

### Developer-surface improvements (v1.7 → v1.9)

| Measure | Before `build_agent()` (v1.7) | After (v1.9) |
|---|---|---|
| Lines to build a governed agent | ~70 | ~10 |
| Files to touch to add approvals | 3 | 0 (runtime arg) |
| Switching mock → real LLM | Rewire several components | Swap adapter only |
| Preview which actions are gated | Manual inspection | `describe_approval_coverage()` |
| Human-readable trace | Custom print loop | `format_trace(trace)` |

### Competitive position (honest)

| Area | Agentic Framework | LangGraph / CrewAI / AutoGen | Bedrock / Vertex Agents |
|---|---|---|---|
| Action loop ordering pinned by tests | **Yes** | Varies; typically middleware-composed | Provider-opaque |
| Per-tool risk classification at the gateway | **Yes** | Partial / per-integration | Partial |
| Human-in-the-loop as a runtime argument | **Yes** | Bolt-on patterns | Console-driven |
| Hard budget caps as terminal events | **Yes** | Typically soft / dashboard | Partial |
| Signal enrichment from model-internal state | **Differentiated** (requires CG adapter) | Not available without model-internal access | Not exposed |
| Multi-agent orchestration | Not yet — on roadmap | **Mature** | **Mature** |
| Managed / hosted runtime | Not yet — on roadmap | Partial | **Mature** |
| Ecosystem breadth (integrations, templates) | Narrow, focused | **Broad** | **Broad** |

We are not trying to win on ecosystem breadth or hosted infrastructure
in year one. We are trying to win on the governance properties that
regulated enterprises cannot ship without: pinned action-loop ordering,
per-tool risk classification, runtime approvals, hard budget caps,
replayable traces, and — where customers adopt the CG path — signal
enrichment from model-internal state.

### 12-month roadmap

**Quarter 1 — Adoption and external proof**
- Add 3 external design-partner pilots (target sectors: BFSI and healthcare)
- OpenTelemetry export adapter for `AgentRunTrace` (the most common
  gap raised by enterprise evaluators)
- Publish an external governance benchmark vs LangGraph / CrewAI across
  a standardized safety + approval + budget scenario suite

**Quarter 2 — Developer console and managed preview**
- Ship the Low-Code Developer Interface (design spec complete at
  `docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md`) — tool registration,
  approval-policy editor, trace replay
- Launch a managed cloud preview for teams that prefer a hosted runtime

**Quarter 3 — Multi-agent and retrieval**
- Agent-to-agent handoffs that preserve governance across the handoff
  boundary
- First-party retrieval adapter with coherence-scored provenance
- Phase Quad LLM integration as a first-class CG adapter, enabling
  signal-enriched governance by default for Cognade customers

**Quarter 4 — Scale and certification**
- Begin SOC 2 Type II process on the managed runtime
- Enterprise audit-log persistence (Postgres + S3-backed)
- Target a production reference customer on the managed runtime

### The ask

We are raising seed to evolve Agentic Framework from a tested
code-first library into a managed governed-runtime product. The
technology is live, internally tested, and validated in two pilots and
on live commercial LLM APIs today. The capital is earmarked for:
external design-partner pilots, the managed runtime and low-code
console, multi-agent and retrieval support, and the compliance and
audit-persistence work required for regulated enterprise deployment.

Governance is becoming a procurement requirement for autonomous agents,
not a nice-to-have. We think the next 12–18 months are the right
window to establish a credible default for that layer, and we believe
the combination of a tested runtime contract, a clean developer
surface, and a path to model-internal signal enrichment gives Agentic
Framework a defensible position in it.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `agentic/agentic_framework/`*
*v1.9.0 · 1,550+ internal tests · 2 internal pilots · live-adapter validated*
