# Agent Runtime — VC Brief

**Ugence Labs | Agent Runtime**
*A stateful autonomous runtime that plans work, coordinates tools, and emits Canonical Execution Requests for deterministic governance.*
*Version 2.0.0 — Repositioned July 2026 (external / evidence-based)*

> **Product family.** The Agent Runtime is a **Specialized AI System** in the Ugence Labs
> portfolio. It is the **native reference producer** for the **Ugence AI Control Plane**
> (Context Minimization · ActionGate · Autonomous Control Plane), which is described in its
> own brief (`AI_CONTROL_PLANE_VC_BRIEF.md`). This document positions the runtime; it does
> **not** carry the entire Control Plane story.

---

## Page 1 — The Problem

### Generation and governance are improperly coupled

The last two years produced a wave of agent runtimes — LangChain / LangGraph, CrewAI,
AutoGen, AWS Bedrock Agents, Vertex AI Agent Builder. They made it straightforward to wire
an LLM to a tool-calling loop. But each of them combines **planning, tool selection, policy
checks, and execution** inside one framework-specific loop. That coupling is the problem.

Because every framework exposes a **different action representation and a different
enforcement seam**, an enterprise cannot govern actions **consistently across multiple
runtimes**. A bank running LangGraph in one team, a hosted Bedrock agent in another, and a
home-grown runtime in a third has three incompatible answers to the only questions a risk
team actually cares about:

| The question an enterprise buyer asks | Why coupled runtimes answer it inconsistently |
|---|---|
| *"What exactly is this agent about to do — as a stable, signed object?"* | Each framework has its own internal action shape; there is no canonical, hashable request. |
| *"Who authorized this specific action, and can that authorization be replayed or transferred?"* | Authorization is entangled with the runtime loop, so it varies per framework and per integration. |
| *"Is this operationally safe against live state right now — independent of who generated it?"* | Operational safety, when present at all, is bolted into the same loop that chose the action. |
| *"Can I reconstruct and audit the decision the same way across every runtime we run?"* | The trace shape is framework-specific; there is no shared identity from proposal to execution. |

The market does not need *another* runtime that embeds its own governance. It needs a clean
separation: a runtime that **proposes and orchestrates**, and an external control plane that
**authorizes and operationally clears**. When generation and governance are decoupled, one
governance layer can sit in front of *many* runtimes — and the enterprise gets one consistent
answer.

### The runtime's role in the decoupled architecture

The **Ugence Agent Runtime** creates structured, **evidence-rich execution requests** rather
than treating a model-selected action as authorized execution. It plans, decomposes,
remembers, reflects, and orchestrates tools — and at the moment of actuation it emits a
**Canonical Execution Request (CER)**: a runtime-independent, hashable object describing
exactly what should happen. Whether and how that request executes is decided **outside** the
runtime, by the Ugence AI Control Plane. The result returns to the runtime for observation,
memory, and reflection — so the runtime stays **stateful and iterative**, not a one-way
proposal generator.

---

## Page 2 — The Architecture

### Agent Runtime — a proposer in a governed loop

The Agent Runtime is a **code-first Python runtime** that wraps any LLM adapter (OpenAI,
Anthropic, Mistral, local models via a common `BaseLLMAdapter`) into a stateful autonomous
agent. Its job is to turn an enterprise goal into a **well-formed, evidence-rich CER**, hand
it to the Control Plane, and metabolize the governed result back into memory and reflection.

### The full loop (proposer → governor → execution → observation)

```
  Enterprise Goal
        │
        ▼
  Agent Runtime
   • planning            • memory
   • decomposition       • reflection
   • tool orchestration  • advisory risk evidence
        │
        ▼
  Canonical Execution Request  (CER)   ── runtime-independent, hashable
        │
        ▼
  AI Control Plane
   • Context Minimization (where applicable)
   • ActionGate authorization      (allow / deny / approve / escalate)
   • ACP operational safety        (safe-now / hold)
        │
        ▼
  Governed execution result
        │
        ▼
  Tool / API / cloud / database / robot
        │
        ▼
  Observation & outcome
        └────────────────────────► Agent Runtime  (memory & reflection)
```

The **return arrow is essential**. Authorization and operational safety live in the Control
Plane; the runtime remains the stateful planner that learns from the governed outcome. Exact
**action identity** is preserved from proposal to execution: the CER the runtime emits is the
same object ActionGate authorizes and ACP clears, bound by a content hash — so what was
proposed is provably what was governed and what executed.

### What the runtime owns — and what it does not

| Owned by the **Agent Runtime** (safeguards & evidence) | Owned by the **AI Control Plane** (authority) |
|---|---|
| Early / structural validation of a proposed action | **Authoritative allow / deny** decisions |
| Local cancellation (async stop at checkpoints) | **Action authorization** and approval binding |
| Budget-accounting safeguards (advisory caps) | **Operational-safety** decisions (safe-now / hold) |
| User-interaction controls (human-in-the-loop UX) | **Replay protection** and execution-token creation |
| **Advisory risk evidence** (uncertainty / confidence) | **Commit-time state validation** |
| Proposal-completeness checks | **Policy enforcement as final authority** |

Everything in the left column is a **runtime safeguard or a piece of evidence** — useful, but
**not** enterprise authorization. Everything in the right column now resides in ActionGate and
ACP. A denied or unsafe CER does not execute regardless of what the runtime "decided," and the
runtime cannot mint its own authorization.

### SafetyGate and SafeMCPGateway, reframed

The runtime's legacy governance modules are **not** peers of ActionGate. Each is reclassified:

| Module | New role | Notes |
|---|---|---|
| **SafetyGate** | **Proposal validation** + **advisory evidence production** | Verifies a request is structurally complete and emits turn-level risk/coherence evidence for ActionGate. It no longer makes the authoritative turn-level allow/deny. |
| **SafeMCPGateway** | **Proposal validation** + **compatibility shim** | Structural per-tool checks and a temporary shim for existing users; its risk taxonomy becomes **advisory evidence** attached to the CER. Any duplicated final-authorization logic is **deprecated** in favor of ActionGate. |

Neither module is equivalent to ActionGate. Where they duplicated authoritative governance,
that duplication is on the deprecation path; where they produce useful signal, that signal
becomes advisory evidence in the CER.

### Model-uncertainty signals — advisory evidence, not authority

The runtime can attach **model-internal uncertainty signals** to a proposal as **advisory
evidence**. The measured, provider-agnostic one is **raw next-token predictive entropy** and a
derived **confidence-risk gap** (the model *says* safe but is internally uncertain). This
evidence **may raise scrutiny — it may never grant authorization.** Deeper research signals
(CG "sovereign state", JEPA, vritti, C×R×S) remain **research-only**, off the product path,
where the evidence is weak or negative (see the evidence appendix, Page 4). **The runtime's
commercial thesis does not depend on any of them.**

### Developer surface — plan, propose, govern, observe

```python
from agentic.agent_runtime import build_runtime

runtime = build_runtime(adapter=AnthropicAdapter(auth_token=...), tools={...})

# The runtime plans and emits a CER instead of executing directly.
cer = runtime.propose("Process the refund queue")           # Canonical Execution Request

# Governance is external: the AI Control Plane decides whether/how it executes.
result = control_plane.govern_and_execute(cer)              # ActionGate + ACP

# The governed result returns to the runtime for memory and reflection.
runtime.observe(result)                                     # stateful loop closes
```

The same code runs against a `MockLLMAdapter` (no cost, no keys) and a live provider with no
wiring changes — easy to evaluate before procurement. Because the CER is emitted **natively**,
the runtime integrates with the Control Plane without an adapter translation step.

---

## Page 3 — Competitive Landscape

The Agent Runtime is **not** positioned as "a runtime with governance baked in." That claim is
now architecturally inaccurate: final governance lives outside the runtime. The honest position
is narrower and stronger — the Agent Runtime is a **best-in-class proposer** and the **native
reference producer** for a runtime-independent governance contract (CER).

### Where competitors may be stronger (stated plainly)

Established runtimes lead on **multi-agent orchestration, durability, graph tooling, hosted
runtime, ecosystem breadth, integrations, developer adoption, and observability.** We do not
claim to beat them on those in year one.

### Where the Ugence Agent Runtime differentiates

- **Native CER output.** The runtime emits the canonical, hashable request directly — not via
  an after-the-fact adapter — so identity is exact from proposal to execution.
- **Evidence-rich proposals.** Structured planning/decomposition plus advisory risk/uncertainty
  evidence travel *with* the request, giving the governor more to reason about.
- **Clean proposer/governor separation.** No runtime-owned final authorization; one governance
  layer can front many runtimes.
- **Seamless ActionGate + ACP integration.** Native compatibility with the Ugence AI Control
  Plane, including the governed **observation-return** loop.
- **Exact identity continuity** from proposal → authorization → operational clearance → execution.
- **Memory and post-execution reflection** — the runtime is stateful and learns from governed outcomes.

### The strongest platform-level comparison

> **Other runtimes can also integrate through CER adapters. The Ugence Agent Runtime is the
> native reference producer.** Competing runtimes become CER *emitters via an adapter*; ours
> emits CER as its native execution seam. The broader moat — runtime-independent authorization
> and operational-safety composition — belongs to the **AI Control Plane**, not the runtime
> alone. The runtime's edge is being the cleanest, most evidence-rich, natively-conformant
> producer for that control plane.

### In one sentence

Agent frameworks make it easy to call an LLM and run a tool. The Ugence Agent Runtime makes it
easy to **produce a rich, canonical request that an external control plane can deterministically
govern** — and to fold the governed result back into a stateful planning loop.

---

## Page 4 — Evidence, Roadmap, and Appendix

### What is proved today (internal evidence)

| Area | Current state |
|---|---|
| **Runtime primitives** | Planning/decomposition, memory, reflection, streaming, async cancellation, structured output, tool discovery, budget accounting, tracing — implemented and tested |
| **Test suite** | 1,550+ tests across the runtime and its primitives (internal / CI) |
| **CER production (native seam)** | The runtime's execution seam is being finalized to emit CER natively; CER V0.3 is proven cross-runtime and cross-domain (see appendix) |
| **Observation-return loop** | Governed result returns to runtime memory/reflection — preserved as a first-class path |
| **Live-adapter validation** | End-to-end against a stock commercial API with exact usage accounting |
| **LLM adapters** | OpenAI · Anthropic · Mistral · Mock — behind a common `BaseLLMAdapter` |
| **Advisory evidence** | Raw next-token entropy + confidence-risk gap wired as advisory evidence (never authorization) |

All numbers are from our own repository and CI, not third-party benchmarks. An external
benchmark and a cross-runtime demo are on the roadmap.

### Roadmap

**Near term**
- **CER-native Agent Runtime path** (emit CER as the governed execution seam)
- **Observation / result-return loop** hardened as a first-class contract
- **Legacy governance deprecation** (SafetyGate/SafeMCPGateway → validation + advisory evidence)
- Durable workflow state; **OpenTelemetry** + audit export
- Better tool and runtime adapters; compatibility with the AI Control Plane

**Medium term**
- Long-running workflow persistence
- Hierarchical / multi-agent **proposal** generation; governed hand-offs
- **CER adapter SDK** (so third-party runtimes can emit CER)
- Human collaboration / intervention; runtime recovery and resumption

**Later**
- Managed Agent Runtime; enterprise console; runtime observability; deeper infrastructure integration

### The ask

We are raising to fund **two linked but separately positioned assets**:

1. **Agent Runtime productization** — workflow durability, memory, orchestration, proposal
   quality, and enterprise integrations.
2. **AI Control Plane commercialization** — ActionGate, ACP, CER conformance and adapters, live
   pilots, and production signing/audit infrastructure (detailed in `AI_CONTROL_PLANE_VC_BRIEF.md`).

This brief funds asset (1) and **references** asset (2) as a complementary product family; it
does not fold the entire Control Plane story into the runtime. The near-term thesis: a clean
proposer/governor split lets one control plane govern many runtimes, and the Ugence Agent
Runtime is the native reference producer for that split.

---

### Appendix — model-internal signal research status (evidence only)

Advisory-evidence signals are held to a measured bar. Advisory means **may raise scrutiny, may
never authorize.** Current status:

| Signal | Evidence | Status |
|---|---|---|
| **Risk taxonomy** | Strongest single feature across pilots (standalone AUROC ≈ 0.82) | **MEASURED** — advisory, default |
| **Raw next-token entropy** | Strongest measured uncertainty signal; fooled-subset AUROC 0.857 | **MEASURED** — advisory, default |
| **Confidence-risk gap** | End-to-end validated wiring (escalation + audit + negative control) | **MEASURED** (wiring) / **DIRECTIONAL** (value) — advisory |
| **CG entropy (32-D state)** | Fooled-subset AUROC 0.457 (anti-predictive); beaten by raw entropy | **RESEARCH** — off product path |
| **C×R×S semantic-frame (agentic governance)** | Real ranking signal but over-gates benign; fails pre-registered gate `AGENTIC_CRS_INCREASES_FALSE_BLOCKS` | **RESEARCH** — off product path |
| **JEPA / coherence** | Standalone AUROC ≈ 0.70 / 0.68; no value *over* raw entropy | **RESEARCH** — off by default |
| **Vritti** | Standalone AUROC 0.500 (non-discriminative) | **RESEARCH** — candidate for removal |

*Classification key: **MEASURED** = supported by repo/CI or our own experiments; **DIRECTIONAL**
= plausible, not yet at statistical power; **RESEARCH** = open question, off the product path.
None of these grants authorization; all authoritative decisions are made by ActionGate/ACP.*

### Appendix — the CER contract this runtime produces (see the AI Control Plane brief)

The runtime emits a **Canonical Execution Request** that the AI Control Plane governs. CER V0.3
has been proven with: three real runtimes producing identical action identity for identical
actuation; two Kubernetes profiles (scale, rollout) and a database-mutation profile; a
clean-room second implementation reproducing byte-identical canonical payloads and digests; and
runtime-independent authorization with no runtime-specific branch in the control plane. CER is a
**versioned interoperability contract implemented by the Ugence AI Control Plane** — not an
industry standard already adopted by the market. Full evidence lives in the AI Control Plane
brief and the CER public-draft package.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `agentic/` (Agent Runtime) · Governance: Ugence AI Control Plane*
*Positioning: Specialized AI System · native reference producer for the AI Control Plane · proposer, not final governor*
