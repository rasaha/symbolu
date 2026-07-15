# Agent Runtime — VC Brief

**Ugence Labs | Agent Runtime**
*The Agent Runtime that turns AI reasoning — planning, memory, reflection, tool orchestration — into a **deterministic, governable Canonical Execution Request**.*
*Version 2.1.0 — Refined July 2026 (external / evidence-based)*

> **Product family.** The Agent Runtime is a **Specialized AI System** in the Ugence Labs
> portfolio, which spans three layers: **Specialized AI Systems** (this runtime), the
> **AI Control Plane** (Context Minimization · ActionGate · Autonomous Control Plane — its own
> product, `AI_CONTROL_PLANE_VC_BRIEF.md`), and **AI Infrastructure** (Hybrid LLM, KVPro, cloud
> infrastructure). The runtime is the **native reference producer** for the Control Plane. This
> document positions the runtime; it does **not** carry the Control Plane story, and the two
> products are **not** merged.

---

## Page 1 — The Problem

### Enterprises cannot consistently trust execution across AI runtimes

The last two years produced a wave of agent runtimes — LangGraph, CrewAI, AutoGen, AWS Bedrock
Agents, Vertex AI Agent Builder — alongside coding and desktop agents such as Claude Code and the
OpenAI Agents SDK. They made it straightforward to wire an LLM to a tool-calling loop. But **every
runtime reasons differently, and every runtime represents a chosen action differently**, and each
one enforces policy inside its own framework-specific loop.

Enterprises **increasingly run more than one runtime**: LangGraph in one team, a hosted Bedrock
agent in another, a coding agent on the desktop, a home-grown runtime in a fourth. Because each
carries **its own action representation and its own enforcement seam**, governance **fragments**.
There is no single, stable answer to the only questions a risk team actually cares about:

| The question an enterprise buyer asks | Why coupled runtimes answer it inconsistently |
|---|---|
| *"What exactly is this agent about to do — as a stable, signed object?"* | Each framework has its own internal action shape; there is no canonical, hashable request. |
| *"Who authorized this specific action, and can that authorization be replayed or transferred?"* | Authorization is entangled with the runtime loop, so it varies per framework and per integration. |
| *"Is this operationally safe against live state right now — independent of who generated it?"* | Operational safety, when present at all, is bolted into the same loop that chose the action. |
| *"Can I reconstruct and audit the decision the same way across every runtime we run?"* | The trace shape is framework-specific; there is no shared identity from proposal to execution. |

The market does not need *another* runtime with its own embedded governance. It needs **one
trustworthy execution contract** that any runtime can produce and **one** governance layer can
authorize. That is the architecture Ugence builds toward:

> **Runtime → Canonical Execution Request (CER) → AI Control Plane.**
> The runtime **proposes**; the Control Plane **governs**. One contract, one governor, many runtimes.

### The runtime's role in the decoupled architecture

The **Ugence Agent Runtime** creates structured, **evidence-rich execution requests** rather than
treating a model-selected action as authorized execution. It plans, decomposes, remembers,
reflects, and orchestrates tools — and at the moment of actuation it emits a **Canonical Execution
Request (CER)**: a runtime-independent, hashable object describing exactly what should happen.
Whether and how that request executes is decided **outside** the runtime, by the Ugence AI Control
Plane. The result returns to the runtime for observation, memory, and reflection — so the runtime
stays **stateful and iterative**, not a one-way proposal generator.

`FACT.` The CER contract at the center of this architecture is not a slideware concept. **CER V0.3
has been validated across multiple runtimes** (a native Ugence producer plus LangGraph and OpenAI
Agents adapters, all yielding identical action identity), **multiple execution profiles** (two
Kubernetes profiles and a database-mutation profile), **deterministic identity** (a content hash
that is stable from proposal to execution), and an **independent clean-room implementation** that
reproduces byte-identical canonical payloads and digests. Details are in the appendix; the headline
is that the contract already works across independent producers.

---

## Page 2 — The Architecture

### Native Execution Proposal Engine

Unlike existing runtimes — which hand the framework's internal action object straight to
execution — the Ugence Agent Runtime **converts reasoning into a Canonical Execution Request** as
its native output. The CER is the runtime's **native execution contract**: the artifact the runtime
exists to produce. Each CER carries:

| CER carries | What it is |
|---|---|
| **Intended action** | The specific operation the agent proposes (e.g. scale a deployment, mutate a table). |
| **Normalized parameters** | Canonicalized arguments, so identical intent produces an identical object. |
| **Execution target** | The concrete resource / surface the action would touch. |
| **Supporting evidence** | Structured planning, decomposition, and advisory risk/uncertainty signals. |
| **Provenance** | Which runtime and adapter produced the proposal (excluded from identity — see below). |
| **Deterministic identity** | A content hash that is stable and reproducible from proposal to execution. |

Because the CER is emitted **natively**, there is **no translation layer** between the runtime and
the governor: what the runtime proposes is exactly the object the Control Plane authorizes.

> **Not an industry standard — the runtime's native execution contract.** CER is a versioned
> interoperability contract that Ugence implements; it is not (yet) a market-adopted standard. The
> long-term vision for CER as a shared contract is on Page 4.

### The full loop (proposer → governor → execution → observation)

```
  Enterprise Goal
        │
        ▼
  Agent Runtime  (PROPOSES)
   • planning            • memory
   • decomposition       • reflection
   • tool orchestration  • advisory risk evidence
        │
        ▼
  Canonical Execution Request  (CER)   ── runtime-independent, hashable
        │
        ▼
  AI Control Plane  (GOVERNS — separate product)
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

The **return arrow is essential**. Authorization and operational safety live in the Control Plane;
the runtime remains the stateful planner that learns from the governed outcome. Exact **action
identity** is preserved from proposal to execution: the CER the runtime emits is the same object
ActionGate authorizes and ACP clears, bound by a content hash — so what was proposed is provably
what was governed and what executed.

### Runtime independence — the Control Plane does not require the Ugence Runtime

`FACT.` CER is a runtime-independent contract. The AI Control Plane governs **any** conformant
producer; it does **not** require the Ugence Runtime. Today CER can be emitted by:

| Producer | Integration | Status |
|---|---|---|
| **Ugence Agent Runtime** | Native | The **native reference producer** — emits CER as its execution seam. |
| **LangGraph** | Adapter | Real adapter; produces identical action identity in conformance testing. |
| **OpenAI Agents** | Adapter | Real adapter; produces identical action identity in conformance testing. |
| **Future runtimes** | Adapter | The contract is versioned and documented for third-party emitters. |

The Ugence Runtime is the **native reference producer**, not a gatekeeper. Other runtimes reach the
same governance layer through a thin adapter. *(This is architectural interoperability demonstrated
in the repository — it is **not** a claim of broad market adoption.)*

### Runtime advantages vs. Platform advantages — kept separate on purpose

These are two products. Their advantages are stated in two tables so the boundary stays crystal
clear — the runtime's value is **proposal quality**; the platform's value is **governance
authority**.

**Agent Runtime advantages (the proposer):**

| Advantage | What it means |
|---|---|
| **Planning** | Turns an enterprise goal into an ordered, inspectable plan. |
| **Decomposition** | Breaks goals into discrete, individually governable actions. |
| **Memory** | Carries state across turns; the runtime is stateful, not one-shot. |
| **Reflection** | Learns from governed outcomes via the observation-return loop. |
| **Tool orchestration** | Coordinates tool calls into a coherent execution proposal. |
| **Native CER generation** | Emits the canonical, hashable request directly — no translation step. |
| **Richer execution evidence** | Structured planning + advisory risk/uncertainty travel *with* the request. |

**AI Control Plane advantages (the governor — separate product):**

| Advantage | What it means |
|---|---|
| **ActionGate** | Authoritative allow / deny / approve / escalate on a specific action. |
| **ACP** | Operational-safety clearance against live state (safe-now / hold). |
| **Runtime-independent governance** | One governance layer fronts many runtimes. |
| **Operational safety** | Replay protection, execution-eligibility, commit-time validation. |
| **Deterministic authorization** | The same CER identity yields the same decision, auditable end-to-end. |
| **Runtime independence** | Governs any conformant producer, native or adapter. |

Nothing in the left/first table is enterprise authorization; nothing in the second is produced by
the runtime. A denied or unsafe CER does not execute regardless of what the runtime "decided," and
the runtime cannot mint its own authorization.

### What the runtime owns — and what it does not

| Owned by the **Agent Runtime** (safeguards & evidence) | Owned by the **AI Control Plane** (authority) |
|---|---|
| Early / structural validation of a proposed action | **Authoritative allow / deny** decisions |
| Local cancellation (async stop at checkpoints) | **Action authorization** and approval binding |
| Budget-accounting safeguards (advisory caps) | **Operational-safety** decisions (safe-now / hold) |
| User-interaction controls (human-in-the-loop UX) | **Replay protection** and execution-token creation |
| **Advisory risk evidence** (uncertainty / confidence) | **Commit-time state validation** |
| Proposal-completeness checks | **Policy enforcement as final authority** |

The runtime does **not** own authorization, operational safety, execution authority, policy
enforcement, or replay protection. Those belong **exclusively** to the AI Control Plane.

### SafetyGate and SafeMCPGateway, reframed

The runtime's legacy governance modules are **not** peers of ActionGate. Each is reclassified:

| Module | New role | Notes |
|---|---|---|
| **SafetyGate** | **Proposal validation** + **advisory evidence production** | Verifies a request is structurally complete and emits turn-level risk/coherence evidence for ActionGate. It no longer makes the authoritative turn-level allow/deny. |
| **SafeMCPGateway** | **Proposal validation** + **compatibility shim** | Structural per-tool checks and a temporary shim for existing users; its risk taxonomy becomes **advisory evidence** attached to the CER. Any duplicated final-authorization logic is **deprecated** in favor of ActionGate. |

Neither module is equivalent to ActionGate. Where they duplicated authoritative governance, that
duplication is on the deprecation path; where they produce useful signal, that signal becomes
advisory evidence in the CER.

### Model-uncertainty signals — advisory evidence, not authority

The runtime can attach **model-internal uncertainty signals** to a proposal as **advisory
evidence**. The measured, provider-agnostic one is **raw next-token predictive entropy** and a
derived **confidence-risk gap** (the model *says* safe but is internally uncertain). This evidence
**may raise scrutiny — it may never grant authorization.** Deeper research signals remain
**research-only**, off the product path, where the evidence is weak or negative (see the appendix).
**The runtime's commercial thesis does not depend on any of them.**

### Developer surface — plan, propose, govern, observe

```python
runtime = build_runtime(model=..., tools={...})

cer    = runtime.propose("Process the refund queue")   # native Canonical Execution Request
result = control_plane.govern_and_execute(cer)          # ActionGate + ACP decide (external)
runtime.observe(result)                                 # stateful loop closes; memory + reflection
```

The runtime is **compatible with commercial and local models through a common adapter interface** —
the same code evaluates against a stub model (no cost, no keys) and a live provider with no wiring
changes. Because the CER is emitted **natively**, the runtime integrates with the Control Plane with
no adapter translation step.

---

## Page 3 — Competitive Landscape

The Agent Runtime is **not** "a runtime with governance baked in" — that claim is architecturally
inaccurate, because final governance lives outside the runtime. The honest and stronger position:
**the Agent Runtime is a best-in-class proposer and the native reference producer for a
runtime-independent governance contract.** The right comparison is therefore not feature-by-feature;
it is **execution architecture**.

### Compared by execution architecture

| Runtime | Proposal mechanism | Governance location | Execution authority | Representative examples |
|---|---|---|---|---|
| **LangGraph** | Graph / state-machine of LLM + tool nodes | In-runtime (developer-coded guards, interrupts) | Runtime executes tool nodes directly | LangChain / LangGraph |
| **CrewAI** | Role-based crew agents with task delegation | In-runtime (agent-level rules) | Runtime executes | CrewAI |
| **Claude Code** | Model tool-calls in an agentic loop | In-runtime (permission prompts / policy) | Runtime executes (with user approval) | Claude Code, IDE agents |
| **OpenAI Agents** | Model tool-calls + handoffs | In-runtime (guardrails) | Runtime executes | OpenAI Agents SDK |
| **Ugence Runtime** | Plan → decompose → **emit CER** | **External** AI Control Plane (ActionGate + ACP) | **Control Plane** grants execution eligibility; runtime does not self-authorize | Ugence Agent Runtime + AI Control Plane |

*These are architectural characterizations, not feature judgments. The distinguishing axis is
**where governance lives and who holds execution authority** — in-runtime for the established
frameworks, in an external, runtime-independent control plane for Ugence. Note that those same
runtimes can also emit CER **through an adapter**; the difference is native vs. adapter production,
not exclusivity.*

### Where competitors may be stronger (stated plainly)

Established runtimes lead on **multi-agent orchestration, durability, graph tooling, hosted runtime,
ecosystem breadth, integrations, developer adoption, and observability.** We do not claim to beat
them on those in year one. Our edge is architectural: **clean proposer/governor separation and
native, evidence-rich CER production** for a control plane that can front many runtimes.

### Why use the Ugence Runtime if I already use LangGraph?

The most important commercial question, answered honestly — and **without** attacking LangGraph
(which you can keep, and front with the same Control Plane via its adapter):

| Reason | What you gain |
|---|---|
| **Native CER generation** | The execution contract is the runtime's native output — nothing to translate or reconcile. |
| **Richer execution evidence** | Structured planning, decomposition, and advisory uncertainty travel *with* the proposal. |
| **No translation layer** | The object the runtime proposes is exactly the object the governor authorizes. |
| **Better planning** | Decomposition into individually governable actions, not opaque tool calls. |
| **Better reflection** | A first-class observation-return loop folds the governed outcome back into memory. |
| **Tighter AI Control Plane integration** | Built against ActionGate + ACP as the native governance seam. |

If you already run LangGraph, the Control Plane still governs it through the LangGraph adapter. The
Ugence Runtime is the option when you want the **cleanest, most evidence-rich native producer** for
that governance layer — not a rip-and-replace mandate.

### In one sentence

Agent frameworks make it easy to call an LLM and run a tool. The Ugence Agent Runtime makes it easy
to **produce a rich, canonical request that an external control plane can deterministically
govern** — and to fold the governed result back into a stateful planning loop.

---

## Page 4 — Evidence, Roadmap, and Appendix

### What is proved today (internal evidence)

| Area | Current state |
|---|---|
| **Runtime primitives** | Planning/decomposition, memory, reflection, streaming, async cancellation, structured output, tool discovery, budget accounting, tracing — implemented and tested |
| **Test suite** | 1,550+ tests across the runtime and its primitives (internal / CI) |
| **CER production (native seam)** | The runtime emits CER as its native execution seam; **CER V0.3 is proven cross-runtime and cross-domain** (appendix) |
| **Runtime independence** | Real **LangGraph** and **OpenAI Agents** adapters emit CER with identical action identity (conformance-tested) |
| **Clean-room implementation** | An independent second implementation reproduces byte-identical canonical payloads and digests |
| **Observation-return loop** | Governed result returns to runtime memory/reflection — preserved as a first-class path |
| **Model integration** | Commercial and local models via a common adapter interface (stub model for zero-cost evaluation) |
| **Advisory evidence** | Raw next-token entropy + confidence-risk gap wired as advisory evidence (never authorization) |

All numbers are from our own repository and CI, not third-party benchmarks. An external benchmark
and a live cross-runtime demo are on the roadmap.

### Roadmap — product-centric

| Phase | Product | Focus |
|---|---|---|
| **Phase 1** | **Agent Runtime** | Productize the proposer: durable workflow state, memory, reflection, proposal quality, and the native CER seam. |
| **Phase 2** | **CER SDK** | Package the execution contract so any team or third party can emit conformant CER. |
| **Phase 3** | **Runtime adapters** | First-class LangGraph / OpenAI Agents (and future) emitters. *(LangGraph and OpenAI Agents adapters already exist in conformance testing — this phase productizes them.)* |
| **Phase 4** | **Enterprise orchestration** | Multi-runtime coordination, long-running workflow persistence, enterprise console, audit/OpenTelemetry export. |
| **Phase 5** | **Hierarchical proposal generation** | Multi-agent, hierarchical proposing and governed hand-offs under one execution contract. |

### The ask

Ugence is building **two complementary products**:

1. **Agent Runtime** — the native reference producer (this brief): workflow durability, memory,
   orchestration, proposal quality, and enterprise integrations.
2. **AI Control Plane** — the runtime-independent governor (`AI_CONTROL_PLANE_VC_BRIEF.md`):
   ActionGate, ACP, CER conformance and adapters, live pilots, and production signing/audit.

They **may be purchased independently or deployed together.** A team can adopt the Agent Runtime for
better proposals without the Control Plane, adopt the Control Plane to govern an existing runtime
(LangGraph, OpenAI Agents) without the Agent Runtime, or deploy both for the native end-to-end path.
This brief funds product (1) and **references** product (2); it does not fold the Control Plane story
into the runtime, and it does not merge the two products.

### Long-term vision — a common execution contract (architectural vision, not adoption)

`VISION.` Ugence believes AI execution will need a **common execution contract**, analogous to how
**OCI** standardized container images and **CloudEvents** standardized event envelopes — a stable,
vendor-neutral object that any producer can emit and any governor can authorize. CER is Ugence's
candidate for that contract, and the cross-runtime / clean-room evidence shows it is
*implementable* independently.

**This is the architectural vision, not a claim of present-day industry adoption.** CER today is a
versioned interoperability contract implemented by Ugence and proven across our own producers. Any
future standardization would be an outcome to earn, not a status we assert.

---

### Appendix — model-internal signal research status (evidence only)

Advisory-evidence signals are held to a measured bar. Advisory means **may raise scrutiny, may never
authorize.** Current status:

| Signal | Evidence | Status |
|---|---|---|
| **Risk taxonomy** | Strongest single feature across pilots (standalone AUROC ≈ 0.82) | **MEASURED** — advisory, default |
| **Raw next-token entropy** | Strongest measured uncertainty signal; fooled-subset AUROC 0.857 | **MEASURED** — advisory, default |
| **Confidence-risk gap** | End-to-end validated wiring (escalation + audit + negative control) | **MEASURED** (wiring) / **DIRECTIONAL** (value) — advisory |
| **CG entropy (32-D state)** | Fooled-subset AUROC 0.457 (anti-predictive); beaten by raw entropy | **RESEARCH** — off product path |
| **C×R×S semantic-frame (agentic governance)** | Real ranking signal but over-gates benign; fails pre-registered gate `AGENTIC_CRS_INCREASES_FALSE_BLOCKS` | **RESEARCH** — off product path |
| **JEPA / coherence** | Standalone AUROC ≈ 0.70 / 0.68; no value *over* raw entropy | **RESEARCH** — off by default |
| **Vritti** | Standalone AUROC 0.500 (non-discriminative) | **RESEARCH** — candidate for removal |

*Classification key: **MEASURED** = supported by repo/CI or our own experiments; **DIRECTIONAL** =
plausible, not yet at statistical power; **RESEARCH** = open question, off the product path. None of
these grants authorization; all authoritative decisions are made by ActionGate/ACP.*

### Appendix — the CER contract this runtime produces (see the AI Control Plane brief)

The runtime emits a **Canonical Execution Request** that the AI Control Plane governs. CER V0.3 has
been proven with: **three real runtimes** (native Ugence producer + LangGraph and OpenAI Agents
adapters) producing identical action identity for identical actuation; **three execution profiles**
(Kubernetes scale, Kubernetes rollout, and database mutation); an **independent clean-room second
implementation** reproducing byte-identical canonical payloads and digests; and runtime-independent
authorization with **no runtime-specific branch in the control plane**. CER is a **versioned
interoperability contract implemented by the Ugence AI Control Plane** — **not** an industry standard
already adopted by the market. Full evidence lives in the AI Control Plane brief and the CER
public-draft package.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `agentic/` (Agent Runtime) · Governance: Ugence AI Control Plane*
*Positioning: Specialized AI System · native reference producer for the AI Control Plane · proposer, not final governor*
