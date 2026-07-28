# Ugence AI Control Plane
### Governing what enterprise AI may claim, recommend, decide and execute

*Investor First Look*

---

## 1 · The problem, and why now

**Ugence Labs is building the AI Control Plane for enterprise agents.**

AI runtimes are increasingly capable of selecting tools, recommending decisions,
and changing business systems. But the runtime proposing an action should not also
determine whether that action is authorized. Ugence provides an independent control
layer that verifies the agent's assertions and evidence, applies enterprise policy,
confirms the appropriate human or delegated authority, controls execution, and
records a reconstructable decision trail.

The core mechanisms are implemented and have been evaluated through automated tests,
controlled scenarios, cross-runtime conformance, and selected real-hardware
benchmarks. The next commercial milestone is a set of bounded enterprise
design-partner pilots that measure operational effectiveness, false-positive rates,
integration effort, and business value.

### Why now

Enterprises are moving from **AI that generates content** to **AI that recommends
decisions and performs actions**. The risk therefore shifts from *output quality*
to *enterprise consequence* — a wrong database write, an unauthorized payment, a
deleted resource, an unsupported claim presented as fact.

> Security systems determine *who may access* a system. Agent runtimes determine
> *what an AI wants to do*. **Ugence governs whether that exact proposed action may
> proceed** — under evidence, policy, human authority, and current operational
> state.

### One governed lifecycle

<div class="flow">
  <div class="flowbox"><span class="fnum">1</span><b>Propose</b><small>Agent or model proposes an action or answer</small></div>
  <div class="flowbox"><span class="fnum">2</span><b>Verify</b><small>Evidence &amp; assertions checked before reliance</small></div>
  <div class="flowbox"><span class="fnum">3</span><b>Authorize</b><small>Policy &amp; decision authority applied</small></div>
  <div class="flowbox"><span class="fnum">4</span><b>Execute</b><small>Exact action allowed, held, or blocked</small></div>
  <div class="flowbox"><span class="fnum">5</span><b>Record</b><small>Complete, reconstructable audit trail</small></div>
</div>

The runtime *proposes*; Ugence *governs*; every step is *recorded*. Monitoring tools
tell you what an agent *did*, after the fact, and hold no authority to stop it.
Ugence sits *before* commit and can allow, constrain, escalate, or deny.

---

## 2 · The product

### The commercial product being consolidated

| | |
|---|---|
| **Product** | **Ugence AI Control Plane** |
| **Current customer offer** | Governed Agent Design-Partner Pilot (assembled from the existing modules) |
| **After productization** | One repeatable enterprise platform in shadow, recommendation and enforcement modes |

Being explicit about stage — the credibility this document depends on:

| Stage | What exists |
|---|---|
| **Today** | Implemented governance kernels, runtime contracts, prototypes, and controlled evidence |
| **Available now** | A bounded design-partner shadow pilot, assembled from the existing modules |
| **What the round builds** | One repeatable, secure, enterprise-deployable Ugence AI Control Plane |

### Six customer-facing capabilities

The enterprise buys one platform. Beneath it, six capabilities cover the full
"what AI says, recommends, decides, and does" boundary:

| Capability | What it governs |
|---|---|
| **Agent Gateway** | What context and requests enter a governed decision |
| **Truth & Evidence** | Whether a claim is supported before it's relied on |
| **Policy & Decision Authority** | Who is permitted to decide, and under which policy |
| **Action Control** | Whether this exact action may execute, and is it safe now |
| **Governed Runtime** | Supervised proposal of actions as a governable request |
| **Audit & Reconstruction** | A complete, replayable record of the decision |

### Deployment model — one product, three modes

1. **Shadow** — observe proposed claims, decisions, and actions; change nothing.
2. **Recommendation** — surface governance findings and required escalations to
   humans in the loop.
3. **Enforcement** — selected controls actively allow, constrain, escalate, or
   block before commit.

Customers adopt in that order, per control — de-risking the path from observation
to enforcement.

---

## 3 · Initial buyer and first commercial pilot

### Primary buyer

**Head of AI Platform / GCC CTO / Chief Digital Officer / enterprise agent-program
owner** — one role that owns the purchase. Security, risk, and compliance are
stakeholders, not the buyer.

**Buying trigger:** the organization has an AI agent moving from proof-of-concept
toward production but lacks an independent control boundary for evidence,
authority, execution, and audit.

### Primary commercial wedge — enterprise IT / infrastructure agent action control

The first wedge is **agents that take infrastructure and IT actions** (e.g.
Kubernetes and cloud operations). It is the sharpest entry point because the action
is concrete, policy and blast radius are measurable, shadow mode is natural, and it
is where ActionGate's strongest controlled evidence already sits.

### Design-partner pilot — what the customer receives

- Integration with one agent and one workflow.
- Policy and authority mapping.
- Four to eight weeks of shadow observation.
- Unsupported-claim and unauthorized-action findings.
- Human-escalation and false-positive analysis.
- Reconstructable governance records.
- A production-enforcement readiness recommendation.

*Commercial structure:* a **paid design-partner engagement** (fixed-fee pilot,
creditable toward an annual subscription) — a stronger commercial signal than a free
proof-of-concept.

### Decision-governance reference implementation — AI-assisted hiring

The hiring workflow is the **reference implementation** for the Decision Governance
model — it is where the reusable governance kernel was extracted from. It validated
the internal decision lifecycle (recommendation → decision → authorization →
execution → reconciliation) on a deterministic synthetic cohort, preserving the
AI-advisory / human-binding separation and producing a reconstructable audit chain.
The funded productization phase will connect that lifecycle **end-to-end** with
ActionGate, operational clearance, durable enterprise identity, and execution
reconciliation. Hiring demonstrates platform breadth; it is not the initial go-to-
market.

---

## 4 · Evidence at a glance

The mechanisms are built and, in controlled conditions, do what they are specified
to do. Below: one built-evidence signal, one controlled-evidence result, and the
next pilot proof for the core capabilities. Full metrics and limitations are in the
Ugence Technical Evidence Catalogue (technical diligence).

| Capability | Built evidence | Controlled evidence | Next pilot proof |
|---|---|---|---|
| **ActionGate** | 274 dedicated tests | 27/27 red-team attacks blocked (executed, isolated) | False-block & unauthorized-action detection rates |
| **Decision Governance** | Version-frozen, reusable kernel | Deterministic decision-lifecycle replay, reconstructable | Real-workflow audit reconstruction |
| **Truth Assurance Platform** | Prototype + tests | Order-of-magnitude unsafe-delivery reduction (synthetic) | Reviewer agreement & workload reduction |
| **Agent Runtime** | 1,550+ tests | Identical action identity across 3 real runtimes | Multi-runtime customer deployment |
| **Autonomous Control Plane** | Cross-domain, runtime-independent | Byte-identical clearance contract, 0 identity ambiguities | Correct HOLDs on live operational state |

*Additional technical assets (accelerators):* **Context Minimization** (100%
decision invariance at 32–50% token reduction, cross-model) and **KVPro** (~1.8×
net KV density on real GPUs) reduce cost and broaden reach; detail in the catalogue.

> **Evidence boundary.** Unless otherwise stated, current results are based on
> internal software testing, controlled datasets, or company-run hardware
> benchmarks. No capability is yet pilot-validated or production-validated with a
> paying customer — **that is precisely what this round funds.**

---

## 5 · Market and competitive position

Ugence is not another monitoring tool. Adjacent categories each control one thing
and leave the consequential question open:

| Existing category | What it controls | What remains open |
|---|---|---|
| **IAM / RBAC** | Who may access a system | Whether this specific AI-generated action is appropriate |
| **AI observability** | What the model or agent did | Ability to stop or constrain *before* commit |
| **Model gateways** | Which model is called | Decision authority and execution control |
| **Guardrails** | Content / prompt boundaries | Enterprise action authorization and reconciliation |
| **Workflow engines** | How a process executes | Whether the proposed action is permitted |

> **Ugence governs the transition from AI proposal to enterprise consequence.**

*(Positioning to be confirmed by a formal competitive review before external
category claims.)*

---

## 6 · Funding

<p class="tbd">TO CONFIRM — the financial headline below uses placeholders. Please
supply: round stage, amount, runway, and use-of-funds split.</p>

> **Ugence is raising <span class="tbd">$[amount]</span> (<span class="tbd">[pre-seed /
> seed]</span>) to fund <span class="tbd">[N]</span> months of runway, consolidate
> five core governance capabilities into one enterprise-deployable AI Control Plane,
> complete two to three paid design-partner pilots, and convert at least one into an
> enforcement deployment.**

**The transition capital funds:** Ugence has already built and internally validated
the core technologies. The round does **not** fund eleven new research projects — it
funds consolidation of already-built governance mechanisms into one enterprise
product, across three workstreams:

**Product consolidation**
- Unified interface and administration console.
- Shared identity, tenant, policy, evidence, and audit services.
- Standard APIs and canonical contracts.
- Shadow, recommendation, and enforcement modes.

**Enterprise readiness**
- Durable persistence and tamper-evident audit.
- Security and access control.
- Observability and deployment tooling.
- Connectors to runtimes and systems of record.

**Commercial validation**
- Two to three design-partner deployments.
- Measured false-positive and false-block rates.
- Customer integration and operational evidence.
- Conversion of at least one pilot to paid enforcement.

### What the capital changes

<div class="transition">
  <div class="tcol"><h4>Today</h4><ul><li>Five core governance systems</li><li>Different interfaces</li><li>Internal &amp; synthetic validation</li><li>Founder-led deployment</li></ul></div>
  <div class="tarrow">→ funding →</div>
  <div class="tcol"><h4>Productization</h4><ul><li>Unified console</li><li>Shared platform services</li><li>Enterprise connectors</li><li>Security &amp; deployment tooling</li><li>Repeatable onboarding</li></ul></div>
  <div class="tarrow">→</div>
  <div class="tcol"><h4>Commercial outcome</h4><ul><li>One purchasable product</li><li>Two to three pilots</li><li>First paid enforcement customer</li><li>Reuse across two domains</li></ul></div>
</div>

### The milestone: enterprise-deployable v1

The round delivers one integrated, **enterprise-deployable v1** AI Control Plane —
a testable boundary, not "fully hardened for all regulated deployment." v1 means:

- Multi-tenant identity.
- Durable audit records.
- Secure APIs.
- Two runtime connectors.
- One system-of-record connector.
- Shadow deployment, with controlled enforcement for selected actions.

### Milestones within the round

1. Release the first integrated, enterprise-deployable v1 product.
2. Consolidate the core governance modules behind one interface and API.
3. Complete production-grade identity, storage, audit, security, and observability.
4. First live enterprise shadow deployment.
5. First pilot-validated use case.
6. Convert at least one pilot into a paid enforcement deployment.
7. Demonstrate reuse of the same product across two enterprise domains.
8. Establish measurable customer value — reduced governance effort, improved
   traceability, or prevented unauthorized activity.

> **Today:** a deep portfolio of implemented and internally validated governance
> technologies. **After the round:** one integrated, enterprise-deployable AI
> Control Plane enterprises can purchase, deploy, and expand across their agents.
> **Investors fund transitions, not catalogues.**

---

## 7 · Team and contact

### Why Ugence can execute

<p class="tbd">TO CONFIRM — please supply founder background, relevant enterprise/
technical experience, current team composition, and the key hires this round funds.</p>

> The founder has already developed and validated the core governance architecture
> across action authorization, assertion assurance, decision governance, runtime
> contracts, and infrastructure efficiency. The round primarily funds product
> engineering, enterprise integration, security hardening, and commercial
> deployment — not basic research discovery.

**Key hires funded by the round:** <span class="tbd">[e.g. product engineering lead,
enterprise integration engineers, security/compliance, founding GTM]</span>.

**Contact:** <span class="tbd">[name · email · company]</span>

---

*Technical diligence: detailed metrics, limitations, and per-capability evidence are
available in the accompanying **Ugence Technical Evidence Catalogue**.*

*Ugence Labs — governing what enterprise AI may claim, recommend, decide and
execute.*
