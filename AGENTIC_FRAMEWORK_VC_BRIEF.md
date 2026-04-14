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

## Page 3 — Competitive Landscape

Agentic Framework sits in a crowded category — "agent tooling" is one
of the noisiest spaces in enterprise AI right now — but most of that
crowd is solving a different problem. Most current frameworks are
built to make it **easy to wire an LLM to a tool-calling loop**. We
are built to make the layer *between* that tool loop and a production
action **governed, auditable, and interruptible by default**. The
table below positions us against each family of competitor, stating
for every row both *how* we differ and *why* that difference is an
advantage for a regulated enterprise buyer.

| Category | Representative players | What they ship | How Agentic Framework differs — and why it is better |
|---|---|---|---|
| **Open-source agent frameworks** | LangChain / LangGraph, CrewAI, AutoGen, SmolAgents | Python (and JS) libraries that wire an LLM to a tool-calling loop, with middleware-composed safety, approvals, and logging. Multi-agent orchestration and ecosystem breadth are their strengths. | We treat governance as a **runtime contract, not middleware.** The execution ordering `cancel → budget → approve → execute` is pinned by the test suite and cannot be silently reordered; per-tool risk classification runs at the gateway; human approvals are a runtime argument, not a framework rewrite. **Better because:** a regulated buyer can point to a specific test that proves the agent cannot execute a denied or over-budget action, rather than reasoning about middleware composition order — which is exactly the property that closes enterprise diligence. |
| **Cloud-native managed agent platforms** | AWS Bedrock Agents, Vertex AI Agent Builder, Azure AI Studio Agents | Provider-hosted agent runtimes with console-driven tool registration, managed approval workflows, and observability tied to the cloud's logging stack. | We are code-first, portable across LLM providers, and emit a **replayable in-memory `AgentRunTrace`** that is not tied to a single cloud's telemetry. Approvals are per-action-type runtime arguments rather than console flows. **Better because:** customers who run multi-cloud or hybrid — which is most of BFSI and healthcare — can adopt us without provider lock-in, and the audit story is a single trace the customer owns, not a provider-specific log pipeline that evaporates the day they switch clouds. |
| **LLM-native tool / function-calling APIs** | OpenAI Assistants & Tools, Anthropic Tool Use, Mistral Function Calling | Provider-side tool-calling primitives exposed through a proprietary API. They decide *which* tool the model wants to call. | These are **substrate**, not a governance layer. They do not decide whether the call is allowed, affordable, approved, or in-scope for the current turn. **Better because:** Agentic Framework consumes these APIs through `BaseLLMAdapter` and *adds* the governance contract on top, so a customer using OpenAI Tool Use today gets SafetyGate, SafeMCPGateway, hard budget caps, and runtime approvals without migrating off their existing provider. We are additive to, not competitive with, the primitives they already pay for. |
| **Post-hoc guardrails & moderation** | NeMo Guardrails, Guardrails AI, Llama Guard, OpenAI Moderation API | Content-level filters and output classifiers applied *after* the model has produced a response. | Guardrails protect **text**, not **actions**. A hallucinated tool name, a budget breach, a denied approval, or a destructive side effect is not something a content filter is in a position to catch. **Better because:** we intervene at the action boundary — the thing that actually touches production systems — and we compose with a content-level guardrail rather than replacing it; a customer can still run NeMo Guardrails on the LLM output and use Agentic Framework for the tool-execution path. |
| **Observability & eval platforms** | LangSmith, Langfuse, Helicone, Arize Phoenix, W&B Traces | Instrumentation layers that record prompts, responses, latencies, and evals for after-the-fact debugging and scoring. | Observability tools answer *"what did the agent do?"* after the fact. We answer *"what is the agent allowed to do right now, and can we stop it?"* at execution time. **Better because:** the `AgentRunTrace` we emit is a first-class replayable object produced by the runtime contract itself — the same structure governance decisions were made against, not an out-of-band log pulled from a SaaS dashboard. Observability platforms remain useful on top; they become a *consumer* of the trace rather than a substitute for governance. |
| **Workflow / orchestration platforms** | Temporal, Airflow, Prefect, n8n, Zapier AI | Durable workflow engines (often retrofitted with LLM steps) that execute business processes with retry, state machines, and fan-out. | Workflow engines assume steps are **deterministic and pre-approved** — they are strong at durability and weak at *"the next action is chosen by an LLM and might be unsafe."* We assume steps are **LLM-chosen and must be gated**. **Better because:** we live exactly at the gap workflow engines do not cover — between *"the model decided to act"* and *"the action touched the system"* — and we can be invoked from inside a Temporal activity the same way a workflow engine calls any Python library. |

### Feature-level differentiation on governance primitives

For buyers who want the one-page side-by-side on the primitives that
come up in procurement conversations, here is the honest feature
comparison against the two most common competitor families:

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

### Why the overall bet is better, not just different

- **Governance *is* the execution path, not a wrapper around it.** The `cancel → budget → approve → execute` invariant is a tested runtime contract. No other framework in this landscape makes that a first-class, diff-testable property of the library itself — which is exactly what an enterprise risk team needs in order to sign off an autonomous agent.
- **Portable across LLM providers by construction.** `BaseLLMAdapter` lets a customer start on OpenAI or Anthropic today and move to a self-hosted or CG-enabled model later with no application rewrite. Managed platforms on the list lock the buyer into a single cloud; open-source frameworks leave portability to the user.
- **Signal enrichment from model internals is a category of one.** Because we ship our own CG-capable adapter (`MistralCGAdapter`) alongside the framework, governance can read entropy and vritti signals straight from the model's 32D state rather than trusting a text-level self-reported confidence. No wrapper on top of a closed API can reproduce this, and no closed API currently exposes it.
- **Composes with, rather than replaces, the rest of the stack.** A customer can keep LangChain for its ecosystem, Temporal for durability, LangSmith for observability, NeMo Guardrails for content filtering — and still put Agentic Framework at the tool-execution boundary. We are the missing layer, not a rival to every layer.
- **Honest scope on where we do not compete (year one).** We are not trying to win on ecosystem breadth, managed infrastructure, or multi-agent orchestration in the first twelve months. We are trying to win on the governance properties that regulated enterprises often cannot ship without: pinned action-loop ordering, per-tool risk classification, runtime approvals, hard budget caps, replayable traces, and — where customers adopt the CG path — signal enrichment from model-internal state.

### In one sentence

Agent frameworks make it easy to call an LLM and run a tool. Managed
platforms make it easy to host an agent on one cloud. Guardrails make
it easy to filter text. Agentic Framework makes it **safe for a
regulated enterprise to let an autonomous agent touch production** —
and that is a different product category than any of the incumbents
in this table are building for.

---

## Page 4 — Evidence & Roadmap

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

Governance is increasingly becoming a procurement requirement for
autonomous agents, not just a nice-to-have. We think the next 12–18 months are the right
window to establish a credible default for that layer, and we believe
the combination of a tested runtime contract, a clean developer
surface, and a path to model-internal signal enrichment gives Agentic
Framework a defensible position in it.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `agentic/agentic_framework/`*
*v1.9.0 · 1,550+ internal tests · 2 internal pilots · live-adapter validated*
