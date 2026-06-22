# Agentic Framework — VC Brief

**Cognade Labs | Governed Runtime for Autonomous AI Agents**
*Version 1.10.0 — Updated June 2026 (external / evidence-based)*

> **Product family.** This product is part of a broader SymbolU / Conscious Generation portfolio. The
> products share elements of the same symbolic-control patent architecture, but each brief describes a
> distinct product boundary, validation state, and commercialization path.

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

### Signal-enriched governance (model-uncertainty signals in the execution path)

The governance runtime can ingest **model-internal uncertainty signals** at the
decision point — not just a prompt-level, self-reported confidence score. The
first-class signal is **raw next-token predictive entropy**: it is provider-agnostic
(computed from any model that exposes logits or logprobs) and the gateway combines it
with the risk taxonomy, approval workflows, budget enforcement, and the audit trail in
a single execution path. A concrete primitive built on it is the **confidence-risk
gap**: when the model *says* an action is safe but its raw next-token entropy is high
(internally uncertain) on a non-trivial tool, the gateway escalates to a human — catching
the confident-but-wrong case that a text-level confidence score misses, with a structured
audit record explaining why.

We make **no proprietary claim** on raw entropy — it is a standard, provider-exposed
quantity. The differentiation is the **combination**: risk taxonomy + approvals + audit +
budget + model-uncertainty signals enforced together, model-agnostically, in the execution
path. That is the product customers buy.

A richer, **experimental/research-only** path reads a 32-D "sovereign state" from a
CG-capable adapter (`MistralCGWrapper`) to derive entropy/vritti/JEPA signals. It is **off
by default**. Three internal experiments (see *Internal Signal Research Status*, Page 4) found
that on confident-but-unsafe fabrication, raw next-token entropy out-performed the 32-D
CG-state projection (which was anti-predictive there); CG is promoted to a default signal
only if and when it beats cheap uncertainty signals on held-out benchmarks. We are
deliberately not betting the company on it.

When a non-CG adapter is used (OpenAI, Anthropic, etc.), the same governance path runs and
uses raw entropy where logits/logprobs are available, plus the text-level signals; it
degrades gracefully (to verbalized confidence + the risk taxonomy) when they are not.
Customers start on commercial APIs today with no rewiring.

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
| Model-uncertainty signals in the execution path | **Yes** — raw next-token entropy + confidence-risk gap (provider-agnostic) | Not in the execution path | Not exposed |
| Multi-agent orchestration | Not yet — on roadmap | **Mature** | **Mature** |
| Managed / hosted runtime | Not yet — on roadmap | Partial | **Mature** |
| Ecosystem breadth (integrations, templates) | Narrow, focused | **Broad** | **Broad** |

### Where the moat is — and is not

**Primary moat — what the company rests on (all MEASURED in repo/CI):**
- **Governance *is* the execution path, not a wrapper around it.** The `cancel → budget → approve → execute` invariant is a tested runtime contract. No other framework in this landscape makes that a first-class, diff-testable property of the library itself — exactly what an enterprise risk team needs to sign off an autonomous agent.
- **Audit & compliance system-of-record.** Every run emits a replayable in-memory `AgentRunTrace` the customer owns — the same structure governance decisions were made against, not an out-of-band SaaS log. This is the compliance buy-reason and the durable lock-in.
- **Provider-agnostic enforcement layer.** `BaseLLMAdapter` lets a customer start on OpenAI or Anthropic today and move providers later with no application rewrite. Managed platforms lock the buyer into one cloud; open-source frameworks leave portability to the user.
- **Composes with, rather than replaces, the rest of the stack.** Keep LangChain, Temporal, LangSmith, NeMo Guardrails — and still put Agentic Framework at the tool-execution boundary. We are the missing layer, not a rival to every layer.

**Secondary optionality — upside, not the foundation:**
- **Model-internal uncertainty signals.** Today the runtime ingests **raw next-token entropy** (provider-agnostic; **no proprietary claim** — it is a standard quantity) via the confidence-risk gap, escalating confident-but-uncertain actions that a text-level confidence score misses. A real feature, not a moat.
- **Advanced uncertainty estimation / sovereign-state research.** The deeper 32-D CG sovereign-state model is **experimental research, off by default.** It returns to product positioning only if it beats risk taxonomy + verbalized confidence + raw entropy on held-out benchmarks — which on our own experiments it has not yet done (see *Internal Signal Research Status*). **The company does not depend on this succeeding.**

**Honest scope on where we do not compete (year one).** We are not trying to win on ecosystem breadth, managed infrastructure, or multi-agent orchestration in the first twelve months. We win on the governance properties regulated enterprises cannot ship without: pinned action-loop ordering, per-tool risk classification, runtime approvals, hard budget caps, and replayable traces.

### In one sentence

Agent frameworks make it easy to call an LLM and run a tool. Managed
platforms make it easy to host an agent on one cloud. Guardrails make
it easy to filter text. Agentic Framework makes it **safe for a
regulated enterprise to let an autonomous agent touch production** —
and that is a different product category than any of the incumbents
in this table are building for.

---

## Page 4 — Evidence & Roadmap

### What is proved today (v1.10.0, internal evidence)

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
| **Raw-entropy escalation (confidence-risk gap)** | Wired into the gateway + the provider-agnostic adapter path; end-to-end validated in repo (gateway escalation + structured audit, with a negative control). First-class, on by default. |
| **CG sovereign-state signals (experimental)** | Real CG checkpoint trained + three internal experiments completed. Raw entropy out-performed the 32-D CG-state projection; CG is **OFF by default**. See *Internal Signal Research Status*. |
| **LLM adapters shipped** | OpenAI · Anthropic · Mistral (CG) · Mock — all behind a common `BaseLLMAdapter` |

All numbers above are from our own repository and CI — not third-party
benchmarks. An external benchmark is planned (see roadmap).

### Internal Signal Research Status

We ran a disciplined program to test whether model-internal signals improve governance
beyond cheap baselines. Three experiments are complete:

- **Real CG checkpoint pilot — completed.** A real CG head (Mistral-7B backbone + a trained
  sovereign-state head) was trained and run through the signal harness. The 32-D state's
  vritti component was non-discriminative (standalone AUROC 0.500).
- **Fair-baseline pilot — completed.** With a *real* verbalized-confidence baseline (not a
  placeholder), the full internal-signal config did **not** significantly beat verbalized
  confidence (ΔAUROC ≈ +0.02, p ≈ 0.18, N=30). The model's own verbalized safety judgment
  captured most of the available signal.
- **Fastest-falsification — completed.** On a confident-but-unsafe fabrication probe, scored
  on the subset where verbalized confidence is fooled, **raw next-token entropy was the
  strongest signal (AUROC 0.857)**, while the 32-D CG-state entropy was anti-predictive
  (0.457). Verdict: deprioritize the CG projection.

**Net:** raw next-token entropy currently emerges as the strongest *measured* model-internal
uncertainty signal. The CG sovereign-state projection remains experimental research, off the
product path, until it beats the cheap baseline on a held-out benchmark.

| Signal | Evidence | Status |
|---|---|---|
| **Risk taxonomy** | Strongest single feature across pilots (standalone AUROC ≈ 0.82) | **MEASURED** — shipped, default |
| **Raw next-token entropy** | Strongest measured uncertainty signal; fooled-subset AUROC 0.857 | **MEASURED** — shipped, first-class default |
| **Confidence-risk gap** | End-to-end validated wiring (escalation + audit + negative control) | **MEASURED** (wiring) / **DIRECTIONAL** (governance value, not yet powered) — shipped |
| **CG entropy (32-D state)** | Fooled-subset AUROC 0.457 (anti-predictive); beaten by raw entropy | **RESEARCH** — off by default |
| **JEPA / coherence** | Pilot standalone AUROC ≈ 0.70 / 0.68; no demonstrated value *over* raw entropy | **RESEARCH** — off by default |
| **Vritti** | Standalone AUROC 0.500 (non-discriminative in every run) | **RESEARCH** — candidate for removal |

*Classification key: **MEASURED** = supported by repo/CI or our own experiments;
**DIRECTIONAL** = plausible but not yet established at statistical power; **RESEARCH** = open
question, off the product path.*

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
- First-party retrieval adapter with relevance-scored provenance
- Harden the raw-entropy uncertainty signal across providers (logits/logprobs
  ingestion for OpenAI/Anthropic where exposed)

**Parallel research track (separate from the product roadmap)**
- CG sovereign-state "fix-or-falsify": run the signal-survival diagnostics and the
  held-out promotion gate. CG returns to product positioning **only** if it beats
  risk taxonomy + verbalized confidence + raw entropy on a held-out benchmark. The
  product roadmap above does not depend on this outcome.

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
surface, and the ability to enforce risk taxonomy, approvals, audit, budget, and
model-uncertainty signals together in the execution path gives Agentic Framework a
defensible position in it. Model-internal signals are an enhancement on that foundation
(raw next-token entropy today; the deeper CG-state path is research-only until it earns
its place on held-out benchmarks) — not the thing the company rests on.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `agentic/agentic_framework/`*
*v1.10.0 · 1,550+ internal tests · 2 internal pilots · live-adapter validated · raw-entropy escalation validated end-to-end*
