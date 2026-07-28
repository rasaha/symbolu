# Ugence AI Control Plane
### Governing what enterprise AI may claim, recommend, decide and execute

*Investor First Look — Product, Evidence and Pilot Strategy*

> **Companion document:** the detailed per-module evidence, metrics, and honest
> limitations live in **Appendix A — Ugence Technical Evidence Catalogue**
> (`MODULE_USE_CASES.md`). This first-look is the commercial layer above it.

---

## 1 · The company and the problem

**Ugence Labs is building the AI Control Plane for enterprise agents.**

AI runtimes are increasingly capable of selecting tools, recommending decisions,
and changing business systems. But the runtime proposing an action should not also
determine whether that action is authorized. Ugence provides an independent control
layer that verifies the agent's assertions and evidence, applies enterprise policy,
confirms the appropriate human or delegated authority, controls execution, and
records a reconstructable decision trail.

The core mechanisms are implemented and have been evaluated through automated tests,
controlled scenarios, cross-runtime conformance, and selected real-hardware
benchmarks. The next commercial milestone is a set of bounded enterprise shadow
pilots that will measure operational effectiveness, false-positive rates,
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

That is a new control category, not another monitoring dashboard. Monitoring tells
you what an agent *did*, after the fact, and holds no authority to stop it. Ugence
sits *before* commit and can allow, constrain, escalate, or deny.

### One governed lifecycle

```
   Agent proposes  →  Ugence verifies  →  Policy & authority applied
        │                   │                        │
   (assertion / action)  (evidence,             (who may decide,
                          support, scope)         what may execute)
        │                   │                        │
        └───────────────────┴──────────► Execution authorized or blocked
                                                 │
                                          Complete decision recorded
                                         (reconstructable audit trail)
```

The runtime *proposes*; Ugence *governs*; every step is *recorded*.

---

## 2 · The product

### What Ugence sells

| | |
|---|---|
| **One product** | **Ugence AI Control Plane** |
| **Initial deployment** | **Governed Agent Shadow Pilot** |
| **Initial customer** | A GCC or enterprise team moving an AI agent from proof-of-concept toward production |
| **Initial outcome** | Identify unsupported claims, missing evidence, unauthorized actions, policy conflicts, and required human escalations **before** the agent is allowed to affect production systems |

### Six customer-facing capabilities

The enterprise buys one platform. Beneath it, six capabilities cover the full
"what AI says, recommends, decides, and does" boundary:

| Capability | What it governs | Underlying modules |
|---|---|---|
| **Agent Gateway** | What context and requests enter a governed decision | Runtime adapters, Context Minimization |
| **Truth & Evidence** | Whether a claim is supported before it's relied on | Truth Assurance Platform, Hybrid LLM, evidence assurance |
| **Policy & Decision Authority** | Who is permitted to decide, and under which policy | Decision Governance, Model Selection policy |
| **Action Control** | Whether this exact action may execute, and is it safe now | ActionGate, Autonomous Control Plane |
| **Governed Runtime** | Supervised proposal of actions as a governable request | Agent Runtime, generation steering |
| **Audit & Reconstruction** | A complete, replayable record of the decision | Decision lineage, immutable records, reconciliation |

### Deployment model — one product, three modes

1. **Shadow** — observe proposed claims, decisions, and actions; change nothing.
2. **Recommendation** — surface governance findings and required escalations to
   humans in the loop.
3. **Enforcement** — selected controls actively allow, constrain, escalate, or
   block before commit.

Customers adopt in that order, per control — de-risking the path from observation
to enforcement.

---

## 3 · Initial use cases

Ugence governs three recurring enterprise patterns:

- **Enterprise agent action control** — an agent performs infrastructure, finance,
  or customer actions; ActionGate authorizes each exact action, and the Autonomous
  Control Plane clears it against live operational state.
- **AI-assisted human decisions** — AI recommends; a human decides; Decision
  Governance preserves that separation and records who held authority.
- **AI assertion assurance** — before a generated answer is relied upon or
  released, the Truth Assurance Platform decides deliver / qualify / abstain.

### Reference implementation — AI-assisted hiring

The hiring workflow is the reference implementation that proved the governance
model end-to-end (it is where the reusable Decision Governance kernel was
extracted from). One governed lifecycle:

1. AI reviews evidence and produces a **recommendation** (advisory only).
2. Ugence verifies which evidence is **admissible** (prohibited fields quarantined).
3. Ugence preserves the hard distinction between **AI recommendation** and **human
   decision** — an AI-authored binding decision is structurally impossible.
4. Ugence confirms **who holds authority**.
5. ActionGate determines whether the authorized action **may execute**.
6. Ugence records **recommendation → decision → authorization → execution →
   reconciliation** as an append-only, reconstructable chain.

*Current evidence:* built and internally validated — the reference application
passes its full test suite and replays a synthetic candidate cohort deterministically,
surfacing denials, evidence gaps, and reconciliation mismatches rather than hiding
them. *Pilot objective:* run this in shadow mode alongside a live hiring workflow
and measure audit-reconstruction completeness, missing-evidence rate, and time to
produce an audit package. Hiring is the **reference implementation, not the only
target market.**

---

## 4 · Evidence at a glance

The mechanisms are built and, in controlled conditions, do what they are specified
to do. The table below gives one built-evidence signal, one controlled-evidence
result, and the next pilot proof for the core capabilities. Full metrics, baselines,
and limitations are in **Appendix A**.

| Capability | Built evidence | Controlled evidence | Next pilot proof |
|---|---|---|---|
| **ActionGate** | 274 dedicated tests | 27/27 red-team attacks blocked (executed, isolated) | False-block & unauthorized-action detection rates |
| **Decision Governance** | Version-frozen, reusable kernel | Synthetic decision-lifecycle replay, reconstructable | Real-workflow audit reconstruction |
| **Truth Assurance Platform** | Prototype + tests | Order-of-magnitude unsafe-delivery reduction (synthetic) | Reviewer agreement & workload reduction |
| **Agent Runtime** | 1,550+ tests | Identical action identity across 3 real runtimes | Multi-runtime customer deployment |
| **Context Minimization** | Frozen cross-model benchmark | 100% decision invariance, 32–50% token reduction | Token cost & review reduction on real data |
| **KVPro** | Working GPU implementation | ~1.8× net KV density, quality parity on 4 models | Customer traffic, quality & throughput |

> **Evidence boundary.** Unless otherwise stated, current results are based on
> internal software testing, controlled datasets, or company-run hardware
> benchmarks. No capability is yet pilot-validated or production-validated with a
> paying customer — **that is precisely what this round funds.**

**Two questions we keep separate:** *Has the mechanism been built correctly?*
(tests, invariants, deterministic replay, benchmarks — where we are strong today.)
*Does it create customer value?* (fewer unsupported assertions, unauthorized actions
caught, faster audit reconstruction — what the pilots are designed to prove.) Ugence
has substantial **software proof** today; the round buys **business proof.**

---

## 5 · Commercial strategy

### Initial customer profile

- A GCC or enterprise with an active agentic-AI program.
- One agent approaching production deployment.
- A high-consequence workflow — HR, finance, IT operations, healthcare, claims, or
  customer-facing actions.
- An enterprise policy owner and human authority already identified.
- A concrete need for traceability, controlled execution, or auditability.

### Initial commercial motion

1. Integrate one agent in **shadow mode**.
2. Observe proposed claims, decisions, and actions.
3. Compare agent behavior against enterprise policy and authority.
4. Produce a **governance findings report**.
5. Move selected controls from shadow to **enforcement**.
6. Expand across additional agents and workflows.

### Expansion model

Land with one agent in one workflow; expand by (a) moving controls from shadow to
enforcement, (b) adding agents on the same runtime, and (c) reusing the same
governance kernel across a second enterprise domain. Each deployment sits *between*
the agents and the systems of record — a position that deepens with every workflow
added. Pricing follows the value surface — governed agents / workflows and
enforcement tier — with shadow pilots as the entry motion.

---

## 6 · Defensibility and funding

### Why this is defensible

- **Architectural** — governance is separated from the proposing runtime and cannot
  be edited by the agent it judges. A runtime that grades its own homework is not
  governed.
- **Contract** — canonical action and decision identities let the *same* governance
  logic apply across different runtimes and domains, verified by clean-room
  conformance.
- **Evidence** — every deployment generates structured data on policy conflicts,
  human escalations, authorization outcomes, and execution reconciliation that
  compounds per customer.
- **Integration** — once Ugence sits between agents and enterprise systems, it
  becomes part of the control boundary, not an optional add-on.
- **Domain packages** — a reusable governance kernel extends through domain
  policies, connectors, and evidence schemas.

*(Test counts and benchmarks are diligence signals of engineering rigor — not, by
themselves, the moat. The moat is the governed loop and the evidence it compounds.)*

### What the next round funds

Ugence has already built and internally validated the core technologies required to
govern AI assertions, recommendations, decisions, and actions. These capabilities
currently exist as modular systems with different interfaces, maturity levels, and
deployment paths. **The primary purpose of the next round is to consolidate these
capabilities into one commercially deployable product — the Ugence AI Control
Plane.**

The funded productization phase will create one enterprise-facing platform with:

- A unified product interface and administration console.
- One governed lifecycle from agent proposal through verification, authorization,
  execution, and audit.
- Shared identity, tenant, policy, workflow, evidence, and audit services.
- Standardized APIs and canonical contracts across all modules.
- Connectors for leading agent runtimes, enterprise applications, and systems of
  record.
- Production-grade security, access control, persistence, observability, and
  deployment tooling.
- Configurable shadow, recommendation, and enforcement modes.
- Domain packages for initial enterprise use cases.
- A coherent commercial SKU, implementation model, and customer onboarding
  experience.

The objective is **not to rebuild the underlying research modules** — it is to
transform proven mechanisms into one integrated enterprise product that customers
can configure, deploy, operate, and expand across multiple AI agents and workflows.

**Commercial validation funded by the round.** Once the consolidated product is
available, the round also funds two to three bounded enterprise shadow pilots to
validate: integration effort, unsupported-assertion detection, unauthorized-action
detection, false-positive and false-block rates, human-escalation requirements,
audit-reconstruction completeness, operational latency, reduction in manual
governance effort, and customer willingness to move from shadow mode to enforcement.

### Milestones

1. Release the first integrated Ugence AI Control Plane product.
2. Consolidate the core governance modules behind one product interface and API.
3. Complete production-grade identity, storage, audit, security, and observability
   layers.
4. Deploy the product in its first live enterprise shadow environment.
5. Achieve the first pilot-validated use case.
6. Convert at least one shadow pilot into a paid enforcement deployment.
7. Demonstrate reuse of the same product across two enterprise domains.
8. Establish measurable customer value — reduced governance effort, improved
   traceability, or prevented unauthorized activity.

### The funding transition

> **Today:** a deep portfolio of implemented and internally validated governance
> technologies.
> **After the round:** one integrated, production-ready AI Control Plane that
> enterprises can purchase, deploy, and use across their agents and decision
> workflows.
>
> **Investors fund transitions, not catalogues.**

---

## Appendix

**Appendix A — Ugence Technical Evidence Catalogue** (`MODULE_USE_CASES.md`):
the full per-module problem / mechanism / evidence / honest-conclusion /
next-validation-step detail for all thirteen modules across the three architectural
layers, plus the AI-Hiring flagship pilot and the complete evidence-maturity
taxonomy. Use it for technical diligence; use this first-look for the initial read.

*Ugence Labs — governing what enterprise AI may claim, recommend, decide and
execute.*
