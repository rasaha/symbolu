# Ugence + ServiceNow: Runtime AI Decision & Execution Authority

## Partner Architecture, Product Differentiation and Package Evidence

**Version:** 3.0 (package-grounded update — current default-branch packages architecture)
**Supersedes:** v2.5 (and the v2.4 / v2.3 / v2.1 / v2.0 drafts)
**Audience:** ServiceNow architecture, product, risk & compliance, and partnership teams
**How to read this document:** Parts 0–I are the partner-facing narrative and can be read on
their own. Part II onward and the appendices carry the package-level evidence (distribution
names, public APIs, dependency graph, maturity) for technical diligence. Appendix D is the
v2.5 → v3.0 change summary; Appendix E is the package-to-document traceability table with exact
repository paths and the default-branch commit these claims were verified against.

**Evidence basis.** Every package claim in this v3.0 edition was re-verified against the live
default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` at commit
`d8dd7abc753238d1e10e5a93d14d9ab054b7ce7e` (2026-08-11). Distribution names, versions and public
API symbols are quoted from the packages at that SHA (see Appendix E).

**Central thesis**

> **ServiceNow governs the enterprise AI estate and enterprise workflow. Ugence extends that
> governance to vendor-neutral, per-decision and per-action runtime authority** — what evidence
> an AI may rely on, whether it has delegated decision authority, which model may execute the
> request, exactly what action may occur, whether it is safe *now*, and whether the observed
> effect remained within the approved boundary.

**Maturity discipline.** This edition draws a hard line between *what is implemented today* and
*where the architecture is going*, and it refuses to inflate existing code into deployment
readiness. Every module is placed on an explicit maturity ladder — the summary table (Part 0) and
Appendix B are the authoritative status references:

| Maturity level | Meaning in this document |
|---|---|
| **SHIPPED PACKAGE** | An independently distributable wheel exists under `symbolu/packages/…` on the default branch. |
| **IMPLEMENTED_AND_CI_VERIFIED** | The package's scoped GitHub Actions suite was observed green (per its own CHANGELOG/README). |
| **IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED** | Builds, installs into a clean `--no-index` venv, and passes its suite + isolated demo locally; CI not yet observed green. |
| **REFERENCE-GRADE** | Ships reference implementations behind ports / in-memory stores; explicitly *refused in production* or delegated to a vetted backend. |
| **PRODUCTION DEPLOYMENT VALIDATION PENDING** | Code exists and is verified in the senses above, but no live-enterprise validation is claimed. |
| **PROPOSED** | Design/architecture only; not a package. |

> **The ladder is cumulative in evidence, not in trust.** A SHIPPED PACKAGE that is only
> `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` and REFERENCE-GRADE is **not** production-ready.
> Existing code, reference adapters, in-memory stores, local verification, synthetic evidence and
> isolated-wheel tests are **never** presented here as live-enterprise validation. Where a package
> self-describes as reference-grade or refuses its reference stand-ins in production, this document
> repeats that boundary rather than smoothing it over.

**v2.5 changes (retained context):** fixed the runtime diagram so Model Authority verbs sat over
the shipped Model Selection kernel; disambiguated the Appendix B Model Selection / Procurement
rows; replaced overly categorical ServiceNow claims with defensible Ugence-scoped statements;
distinguished shipped TAP assertion-support from the target Evidence Admission service; added the
five-question meeting spine.

**v3.0 changes (package-state update):** re-grounded the entire document on the current
default-branch packages tree. The largest corrections: **Risk Authority is no longer "planned" —
it is a shipped, independently packaged authority spine** (`ugence-risk-authority`, RA‑1→RA‑4)
plus five shipped composition/runtime distributions (RA‑4.5 through RA‑8); **Model Authority is
shipped** as `ModelAuthorizationDecision` (ALLOW/DENY/HOLD/ESCALATE) inside `ugence-model-selection`;
the single "Runtime Assurance (composed)" section is **split into two shipped layers** — RA‑7
runtime/trajectory assurance and RA‑8 execution/effect assurance; Agent Runtime is updated to its
H22‑A→H22‑D horizon and 0.7 provider-attempt telemetry; Context Minimization is updated to its
v0.2 token-accounting contracts and the new token-accounting integration runtime; Policy Workflow
Compiler and AWC are updated to `workflow_ir.v2`; and the categorical "every package ships a
legacy-compatibility facade" claim is **removed and replaced with a per-package statement** (it is
true of some packages and explicitly false of the net-new ones). New Appendices D (change summary)
and E (traceability, with the verification SHA) were added.

---

# Part 0 — Executive Partner Summary

## Why Ugence + ServiceNow

ServiceNow has become strong at governing **both** the AI estate *and* ServiceNow-native AI
runtime interactions: AI Control Tower manages AI asset lifecycle, governance, compliance and
agent approvals; AI Risk & Compliance provides risk, regulatory and ethical governance; and Now
Assist Guardian can terminate an agentic plan when harmful content is detected. This is a
coordinated lifecycle-governance system, and it is getting stronger.

Ugence does not compete with that. Ugence differentiates through **vendor-neutral,
decision-level and exact-action authority that can span ServiceNow *and* non-ServiceNow
runtimes** — the layer that decides, per request, whether *this* AI action may execute *right
now*, and proves afterward that it stayed within bounds.

```
SYSTEM OF RECORD / WORKFLOW        →   SYSTEM OF RUNTIME AUTHORITY   →   SYSTEMS OF ACTION
ServiceNow (AICT / AIRC / Flow /       Ugence (evidence · decision ·     Agents · Models · MCP ·
Now Assist / agent platform)           model · exact action · clearance  APIs · SaaS · Databases ·
                                       · reconciliation)                 Enterprise Workflows
```

## The five strongest differentiators

1. **Delegated decision authority, not self-authorization.** An AI may issue a binding decision
   only within authority previously delegated by a human or policy principal; the shipped kernel
   structurally bars AI from authorizing itself.
2. **Exact-action authorization.** Approval is bound to the exact action *and payload digest* and
   re-checked at commit time — approving an agent or tool is not approving every payload it can
   emit.
3. **Independent operational clearance.** A separate, non-compensatory gate can block an
   authorized action when the live environment is unsafe, regardless of how valid the
   authorization is.
4. **Vendor-neutral runtime.** One governable execution contract (CER) spans ServiceNow,
   third-party and custom agents, so the same enforcement applies everywhere.
5. **Distinct, fail-closed decision vocabularies.** Evidence support, model eligibility, binding
   decision, exact-action authorization, sequence-risk advisory, operational clearance and
   execution each speak a different verb — and uncertainty is never promoted to a favorable one.

## The five-question spine for the conversation

The full portfolio is 15+ modules, but the *spoken* ServiceNow story should follow one
progression of five questions. Each question is owned by one module, with PWC + TAP supplying
policy and evidence underneath, and the Governance Story Graph explaining the lifecycle
afterward. Everything else is evidence that this authority architecture generalizes.

```
Can AI make this decision?              →  Decision Authority        (delegated, never self-auth)
        ↓
Which model is allowed to make it?      →  Model Authority           (ModelAuthorizationDecision, shipped)
        ↓
What exact action is authorized?        →  ActionGate                (exact payload digest)
        ↓
Is that action safe to execute now?     →  Action Clearance (ACP)    (independent live gate)
        ↓
Did execution remain within authority?  →  RA‑7 runtime assurance +  (trajectory & effect
                                           RA‑8 execution assurance   assessment → neutral signal)

        binding it together:  Risk Authority — RiskDecision → signed RiskAuthorizationEnvelope
        underneath:           Policy Workflow Compiler (policy) + TAP (evidence)
        afterward:            Governance Story Graph (causal lifecycle lineage, proposed)
```

## Integration architecture (vendor-neutral)

ServiceNow is **one integration adapter, not a hard dependency**. The Ugence governance core
carries neutral contracts; a per-platform adapter connects it to ServiceNow, Microsoft,
Salesforce, SAP, Workday, Oracle, or a custom stack. Where this document describes a ServiceNow
integration (policy export, decision-receipt ingestion), it describes what an adapter *can* do,
not a connector that already ships.

## Module maturity at a glance

**Status key:** **Shipped** = an independently installable wheel exists under `symbolu/packages/…`
on the default branch (see the maturity ladder above for the CI-verified / offline-verified /
reference-grade qualifiers) · **Proposed** = design/architecture, not a package. Unless a cell says
otherwise, *shipped* means the code exists and is verified in the senses above — **not** that it is
production-deployment-validated.

| Module | Shipped package(s) today | Decision surface | Proposed ServiceNow integration |
|---|---|---|---|
| **Model Authority** | `ugence-model-selection` 0.1.0 | `ModelAuthorizationDecision` → ALLOW/DENY/HOLD/ESCALATE + governed fallback, over the ExecutionGate + ModelPolicy kernel | Flow action / AICT model policy |
| **Decision Authority** | `ugence-decision-authority` 1.0.0 (frozen API) | binding `DecisionOutcome`; AI barred as principal; owns execution/reconciliation records | AICT/AIRC decision-record ingestion |
| **Risk Authority (spine)** | `ugence-risk-authority` 0.1.0 (RA‑1→RA‑4) | `RiskDecisionCase` → binding `RiskDecision` → signed `RiskAuthorizationEnvelope` (Ed25519) → ActionGate | AICT / AIRC connector |
| **Risk Authority (composition)** | `ugence-risk-authority-runtime` 0.1.0 (RA‑4.5) | fail-closed composition of RA + canonical Decision Authority + ActionGate → `GovernedExecutionDecision` | GRC decision/enforcement feed |
| **RA evidence / status / assurance** | `…-evidence-runtime` (RA‑5), `…-status-runtime` (RA‑6), `…-runtime-assurance` (RA‑7), `…-execution-assurance` (RA‑8), all 0.1.0 | trusted evidence admission; authority lifecycle (revoke/epoch); trajectory & effect assessment + neutral reassessment signals | Evidence / incident / observability |
| **TAP** | `ugence-tap-provider` 0.1.0 | `SUPPORTED/CONSTRAINED/INDETERMINATE` | Evidence/records connector |
| **ActionGate** | `ugence-actiongate-provider` 0.1.0 | exact-action `AUTHORIZED/DENIED/INDETERMINATE` | Tool/MCP + agent-action policy |
| **Action Clearance (ACP)** | `ugence-action-clearance` 0.1.0 | `CLEAR/HOLD/BLOCK/ESCALATE` | ITSM/ITOM / change-state signal |
| **Agent Runtime** | `ugence-agent-runtime` 0.7.0 (H22‑A→D) | bounded advancement, deterministic SWRR scheduling, durable recovery, bounded in-process concurrency; consumes `CLEAR/HOLD/BLOCK/ESCALATE` | Agent platform / runtime |
| **Context Minimization** | `ugence-context-minimization` 0.2.0 + `…-token-accounting-runtime` 0.1.0 | extractive reduction + CM‑TA1 token-accounting contracts | Data access / privacy controls |
| **Hiring Gov. Authority** | `ugence-ai-hiring` (dist 0.1.1 / capability 0.6.0, controlled-pilot) | human-only binding decision | HR / ATS |
| **Governed Procurement** | `ugence-procurement` 0.1.0 (reference workflow) | advisory + human approval; graduated rights are target | Procurement / approval chains |
| **StoryGraph Sequence Risk** | `ugence-storygraph` 2.0.0 | advisory `OBSERVE/ESCALATE/UNAVAILABLE` | Runtime risk signal |
| **Governance Story Graph** | *(proposed — architecture/design)* | Graph schema + service | CMDB / case lineage |

---

## Executive Brief

This document intentionally avoids the claim that ServiceNow lacks AI governance. ServiceNow is
strong in AI asset inventory, lifecycle governance, risk and compliance workflows, approval
playbooks, identity/access context, workflow automation, and an increasingly capable agentic AI
platform that governs ServiceNow-native AI runtime interactions.

The differentiation is narrower and more important: **Ugence focuses on the vendor-neutral,
execution-time decision boundary when AI is expected not merely to recommend, but to decide and
act — across ServiceNow and non-ServiceNow runtimes alike.**

> What happens when the enterprise progresses from AI *recommending* a decision to AI
> *actually making and executing* that decision, potentially outside a single vendor's runtime?

Ugence focuses on the individual decision, the exact action, the prior trajectory, live execution
conditions, and the observed real-world effect. This distinction becomes most valuable as human
approval is reduced or removed and as execution spans multiple runtimes.

What makes this edition different from earlier drafts is that **each shipped module is anchored to
a real, independently distributable package** in the `symbolu/packages/` tree, with its actual
public API, decision vocabulary, and machine-checked authority boundary — while roadmap behavior
is clearly separated and labeled. The positioning is grounded in code that exists today, with the
target architecture stated honestly as target.

**Positioning rule** — for every module, use the framing:

> *"ServiceNow has an adjacent capability; here is the deeper, vendor-neutral execution-time
> problem the Ugence package solves when AI is expected to make or execute the decision."*

---

## Architectural Philosophy

| Platform | The question it answers |
|---|---|
| **ServiceNow** | *"How should work flow?"* |
| **Ugence** | *"Should this AI decision or action be allowed to execute **right now**?"* |

Traditional enterprise platforms answer *"What policies exist?"* and *"What AI do we have?"*
The Ugence packages answer *"May this AI perform this exact action, on this exact payload, under
this exact evidence and live condition, at this moment?"* That distinction is consistent across
every package described below.

---

## The Ugence Package Architecture

The packages are organized as a strict, one-directional dependency spine. Authority is never
transferred by coordination: a lower layer defines *vocabulary and mechanics*; each capability
retains only the authority delegated to its bounded role; products merely *compose* capabilities.

```
                         Governance Products (verticals)
                    ┌───────────────────────────────────────┐
                    │  ai-hiring          procurement        │   compose kernel + providers
                    └───────────────────────────────────────┘
                                     │ composes
     ┌───────────────────────────────┼────────────────────────────────┐
     ▼                               ▼                                  ▼
 Decision & Authority Kernel   Action / Evidence Providers      Capability Leaves
 ┌───────────────────────┐     ┌───────────────────────┐   ┌──────────────────────────┐
 │ decision-authority    │     │ actiongate (author.)  │   │ model-selection          │
 │  (binding-decision    │     │ tap (assertion evid.) │   │ llm-steering-controller  │
 │   governance kernel;  │     └───────────────────────┘   │ context-minimization     │
 │   AI barred as        │              │                  │ action-clearance (ACP)   │
 │   authorizing princ.; │              │                  │ storygraph (seq-risk)    │
 │   owns exec/recon     │              │                  │ agent-workforce-composer │
 │   records)            │              │                  │ cloud-scaling-controller │
 └───────────────────────┘              │                  │ cloud-scaling-operations │
     │                                  ▼                  └──────────────────────────┘
     │                   ┌───────────────────────────┐                  │
     └──────────────────▶│ governance-provider-      │   Runtime        ▼
                         │ framework (register/       │ ┌──────────────────────────┐
                         │ resolve/invoke; NO         │ │ agent-runtime (execution │
                         │ authority)                 │ │ coordination kernel)     │
                         └───────────────────────────┘ └──────────────────────────┘
                                     │                             Tooling
                                     ▼                  ┌──────────────────────────┐
                         ┌───────────────────────────┐  │ policy-workflow-compiler │
                         │ governance-contracts      │  │ (compile-time; produces  │
                         │ (neutral vocabulary leaf; │  │  workflow_ir.v1 / .v2)   │
                         │  stdlib only)             │  └──────────────────────────┘
                         └───────────────────────────┘

  Risk Authority spine + composition/runtime layer  (independently packaged)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ ugence-risk-authority (RA‑1→RA‑4 leaf; reference impls behind ports;       │
  │   sole issuer of the signed RiskAuthorizationEnvelope)                     │
  │      ▲ composed by                                                         │
  │ risk-authority-runtime (RA‑4.5)  ── wires canonical decision-authority +   │
  │                                     actiongate as additive, subtractive    │
  │                                     governance inputs → GovernedExecution  │
  │ risk-authority-evidence-runtime (RA‑5)   trusted evidence admission        │
  │ risk-authority-status-runtime  (RA‑6)   authority lifecycle: revoke/epoch  │
  │ risk-authority-runtime-assurance (RA‑7) trajectory assessment → signal     │
  │ risk-authority-execution-assurance (RA‑8) effect reconciliation → signal   │
  └──────────────────────────────────────────────────────────────────────────┘
```

**Dependency layering (bottom → top).** `governance-contracts` (stdlib leaf) →
`governance-provider-framework` → providers (`actiongate`, `tap`) and the kernel
(`decision-authority`) → products (`ai-hiring`, `procurement`). The capability leaves
(`action-clearance`, `context-minimization`, `model-selection`, `llm-steering-controller`,
`storygraph`, `agent-runtime`) are stdlib-only or pydantic-only and depend on *no* other Ugence
package — they are individually installable and vendor-neutral. The **Risk Authority spine**
(`ugence-risk-authority`) is itself a stdlib-only leaf that ships *reference* implementations
behind ports; its five composition/runtime distributions (RA‑4.5→RA‑8) sit **above** it and are
the only layer that imports the canonical `decision-authority` / `actiongate` packages — the
direction is strictly one-way. Every distribution is prefixed `ugence-`.

> **Compatibility surfaces are per-package, not universal.** Several packages ship a *logic-free
> legacy-compatibility facade* that re-exports the same objects under a prior namespace so adoption
> is non-breaking — verified for `decision-authority` (`decision_governance`), `actiongate`
> (`actiongate_provider`), `storygraph` (`composite_threat_detector`), `model-selection`
> (`execution_gate`), `ai-hiring` (`ai_hiring`) and `procurement`
> (`domains.procurement` / `applications.procurement`). Other, net-new packages **ship none** —
> confirmed for `policy-workflow-compiler`, `agent-workforce-composer`, `agent-runtime` (its
> `compat` module is migration guidance, not identity-preserving aliases), `context-minimization`,
> the token-accounting runtime, and the entire Risk Authority spine (RA leaf + RA‑4.5→RA‑8). Do
> not read "non-breaking legacy facade" as a portfolio-wide property.

> **Build-status legend.** Every package named above is a **SHIPPED PACKAGE** — it exists under
> `symbolu/packages/`, is independently installable, and is offline-verifiable. This includes the
> **Risk Authority** spine (§D2), which in earlier editions was labeled *planned*: it is now a
> shipped leaf (`ugence-risk-authority`, RA‑1→RA‑4) plus five shipped composition/runtime
> distributions (RA‑4.5→RA‑8). *Shipped* is not *production-validated*: most of these packages
> self-describe as reference-grade and/or `PRODUCTION DEPLOYMENT VALIDATION PENDING` (Appendix B).

### Overall runtime architecture

The flow below is the runtime path realized by the shipped packages. Boxes are marked `[shipped]`
(a shipped package on the default branch), `[shipped·ref]` (shipped but reference-grade / production
validation pending), or `[proposed]` (design only, not a package — e.g. the Governance Story Graph).
Every `[shipped]` box is a SHIPPED PACKAGE; the qualifier is about deployment validation, not
existence.

```
Enterprise Platform  (ServiceNow / Microsoft / Salesforce / SAP / Workday / Oracle)
        │
        ▼
Workflow  ·  Approvals  ·  CMDB  ·  AI Inventory  ·  Human Processes
        │
        ▼
══════════════════════════════════════════════════════════════════
   UGENCE RUNTIME GOVERNANCE / AUTHORITY  (symbolu/packages)
   authority spine → Risk Authority (RA‑1→RA‑4 leaf + RA‑4.5→RA‑8 runtimes) [shipped·ref §D2]
══════════════════════════════════════════════════════════════════
   Policy Workflow Compiler   → deterministic workflow_ir.v1 / .v2           [shipped]
        ▼
   Evidence (TAP) + RA‑5 trusted admission → SUPPORTED / CONSTRAINED / INDET. [shipped]
        ▼
   Decision Authority         → binding DecisionCase (AI cannot self-auth.)  [shipped]
        ▼   Risk Authority issues the signed RiskAuthorizationEnvelope here  [shipped·ref]
   Model Authority            → ALLOW / DENY / HOLD / ESCALATE + fallback    [shipped]
        ▼   (ModelAuthorizationDecision over the ExecutionGate+ModelPolicy kernel)
   ActionGate                 → AUTHORIZED / DENIED / INDETERMINATE          [shipped]
        ▼
   StoryGraph Sequence Risk   → OBSERVE / ESCALATE (advisory)               [shipped]
        ▼
   Operational Clearance (ACP / Action Clearance) → CLEAR / HOLD / BLOCK    [shipped]
        ▼
   Authorized Execution (Agent Runtime CER; H22‑A→D)                        [shipped]
        ▼
   RA‑7 runtime/trajectory assurance → NORMAL / ESCALATED / UNKNOWN         [shipped·ref]
   RA‑8 execution/effect assurance   → effect reconciliation                [shipped·ref]
        ▼   (both emit neutral reassessment signals — never authority)
   RA‑6 authority lifecycle          → revoke / supersede / epoch propagate [shipped·ref]
        ▼
   Governance Story Graph / Calibration                                     [proposed]
```

### Governance verb vocabularies (the differentiator ServiceNow's generic approve/reject lacks)

Each layer speaks a **distinct, bounded decision vocabulary**, so authority cannot silently leak
across layers. This is a core differentiation: an "approval" in one layer is not an
authorization, a clearance, or an execution in another.

| Package / layer | Decision verbs | Authority class |
|---|---|---|
| `tap` (assertion evidence) | `SUPPORTED` / `CONSTRAINED` / `INDETERMINATE` | Advisory (assessment) |
| `storygraph` (sequence risk) | `OBSERVE` / `ESCALATE` / `UNAVAILABLE` | Advisory / evidentiary |
| `model-selection` (Model Authority) | `ModelAuthorizationDecision`: `ALLOW` / `DENY` / `HOLD` / `ESCALATE` (+ governed fallback) | Per-request model authorization |
| `llm-steering-controller` | `RECOMMENDED` (execution_status = `NOT_EXECUTED`) | Advisory routing |
| `cloud-scaling-controller` | scaling recommendation (`advisory_only = true`) | Advisory |
| `decision-authority` | binding `DecisionOutcome` (human/policy principal only) | Binding decision |
| `risk-authority` (spine) | `RiskRecommendation` (advisory) → binding `RiskOutcome` `ALLOW`/`ALLOW_WITH_CONDITIONS`/`ESCALATE`/`DENY` → signed `RiskAuthorizationEnvelope` | Signed machine-execution authority (sole issuer) |
| `actiongate` (exact action) | `ActionGateOutcome`: `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS` / `DENIED` / `INDETERMINATE` | Authorization (subtractive) |
| `action-clearance` (ACP) | `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` | Operational clearance (subtractive) |
| `agent-runtime` (execution) | consumes `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` | Execution coordination |
| `risk-authority-runtime-assurance` (RA‑7) | `TrajectoryAssessment`: `NORMAL` / `ESCALATED` / `UNKNOWN` → neutral reassessment signal | Assessment / evidence (never authority) |
| `risk-authority-execution-assurance` (RA‑8) | effect reconciliation → `AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)` | Assessment / evidence (never authority) |
| `risk-authority-status-runtime` (RA‑6) | `revoke` / `supersede` / `expire` / epoch propagation | Authority lifecycle (sole writer) |
| `cloud-scaling-operations` | gated `CONTROLLED_EXECUTION` (needs `ExecutionAuthorization`) | Controlled execution |

**Fail-closed at the AI governance boundary.** Ugence defines fail-closed semantics specifically
at AI governance boundaries: uncertainty or infrastructure failure is *never* promoted to
evidence support, action authorization, operational clearance, or execution. TAP never promotes
uncertainty to `SUPPORTED`, ActionGate never promotes it to `AUTHORIZED`, Context Minimization
fails closed when equivalence cannot be established, and the Agent Runtime fails closed to
`GOVERNANCE_NOT_CONFIGURED` if no governance boundary is wired. This is a property of the Ugence
packages; it is stated as a Ugence guarantee, not as a claim about any other platform's default
error behavior.

---

# Part I — Module-by-Module: Packages, Differentiation & Workflow Comparison

Each module below follows the same structure so executives and enterprise architects can compare
consistently:

1. **Package** — the real directory, distribution name, and decision vocabulary
2. **What the package does** — grounded in the shipped public API
3. **ServiceNow adjacency / strength** — what ServiceNow already does well here
4. **Ugence differentiation** — the deeper execution-time problem the package solves
5. **ServiceNow current pattern → Ugence runtime workflow** — side-by-side flows
6. **How it enhances ServiceNow workflow capability** — the partnership value
7. **Discovery question** — the question to ask in the evaluation meeting

---

## A. Contract & Framework Spine

### A1. Governance Contracts

| | |
|---|---|
| **Package** | `packages/governance-contracts` → `ugence-governance-contracts` (namespace `ugence_governance_contracts`) |
| **Vocabulary** | Defines the neutral request/result/outcome types the rest of the stack speaks |
| **Authority** | None — *contracts, not authority* |

**What the package does.** The stdlib-only leaf that defines *what a governance provider is
asked and what it returns*, independent of any implementation: `ActionGovernanceRequest/Result`,
`AssertionGovernanceRequest/Result`, `ExecutionDispatchRequest/Result`, the outcome enums
(`ActionGovernanceOutcome`, `AssertionCoverage`, `ExecutionBusinessOutcome`), provider protocols
(`ActionGovernanceProvider`, `AssertionGovernanceProvider`, `ExternalExecutionProvider`),
metadata (`ProviderKind`, `ProviderDescriptor`, `ProviderHealth`), and a classified error
hierarchy (`FailureClass`, `ProviderError`). Ships a machine-readable `public_api.json` asserted
equal to the installed package.

**ServiceNow adjacency / strength.** ServiceNow's data model (tables, fields, choice lists)
standardizes *records*. Governance Contracts standardizes *governance interactions*.

**Ugence differentiation.** ServiceNow standardizes what a record looks like; Governance
Contracts standardizes what a governance *decision request and verdict* look like — so that a
ServiceNow agent, a third-party agent, and a custom framework all invoke governance through one
neutral contract and receive one comparable, machine-checkable verdict shape.

**How it enhances ServiceNow workflow capability.** It gives a ServiceNow integration a single,
versioned contract to target. A Flow Designer step calling out to Ugence never has to know which
concrete provider answered — the contract guarantees the verdict shape and the fail-class
taxonomy, which is what makes the rest of the enforcement machine-consumable inside ServiceNow.

**Discovery question.** *"When a ServiceNow workflow calls an AI-governance decision, is the
verdict a free-text note, or a versioned, machine-checkable contract with a defined failure
taxonomy?"*

### A2. Governance Provider Framework

| | |
|---|---|
| **Package** | `packages/governance-provider-framework` → `ugence-governance-provider-framework` |
| **Vocabulary** | Register · resolve · invoke · observe · conform |
| **Authority** | None — *coordination transfers no authority* |

**What the package does.** The capability-neutral mechanism for **registering, resolving,
invoking, observing, and testing** governance providers: `ProviderRegistry`, deterministic
`resolve(...)`, declarative `ProvidersConfiguration`, `ProviderInvocationLog` observability,
deterministic `fingerprint`, public conformance kits, and optional kernel-bound `adapters`
(e.g. `ActionGovernanceControlPlaneAdapter`) that bind concrete providers to the Decision
Authority kernel. It is explicitly *not* a router, adjudicator, policy engine, orchestrator, or
execution authority.

**ServiceNow adjacency / strength.** ServiceNow's IntegrationHub and spoke model registers and
invokes integrations. The framework is the analogous mechanism for *governance* providers, with
deterministic resolution and machine-checked conformance.

**Ugence differentiation.** ServiceNow orchestration decides *which integration runs*; the
framework guarantees that *coordination never grants authority* — a resolved provider retains
only the authority its bounded capability was delegated, and the framework can prove this with
its conformance kits.

**How it enhances ServiceNow workflow capability.** It lets an enterprise plug TAP, ActionGate,
or a custom governance provider behind one registration surface, resolve them deterministically
at runtime, and get a reproducible invocation fingerprint for audit — all without ServiceNow
having to hard-wire any single provider.

**Discovery question.** *"Can new governance providers be registered and deterministically
resolved at runtime without any of them silently gaining authority they weren't delegated?"*

---

## B. Compile-Time Governance (Tooling)

### B1. Policy Workflow Compiler (PWC)

| | |
|---|---|
| **Package** | `packages/tooling/policy-workflow-compiler` → `ugence-policy-workflow-compiler` 0.2.0 |
| **Vocabulary** | Compiles policy pack → `workflow_ir.v1` (frozen) + additive `workflow_ir.v2` (+ assurance manifest, audit schema, digest) |
| **Authority** | None — compile-time tooling (`pilot_validated = False`, `production_certified = False`) |

**What the package does.** Deterministic tooling that compiles a reviewed, structured governance
policy pack into a governed-workflow artifact plus an assurance package. Its IR is now
two-versioned: **`workflow_ir.v1`** is byte-stable and frozen (semantic identity `0.1.0`), and the
additive **`workflow_ir.v2`** (`WORKFLOW_IR_V2 = "workflow_ir.v2"`, semantic identity `0.2.0`)
enriches a compiled v1 graph with node semantics, capability requirements, typed data contracts,
and authority/human-review classification. Also produced: an assurance manifest and test
scenarios, an audit schema, structural diffs, human-approval records, and a content-addressed
compiled package. Public API: `GovernedWorkflowCompiler`, `compile_policy_pack`,
`validate_policy_pack`, `verify_compiled_package`, plus the v2 surface `WorkflowIRv2`,
`compile_workflow_v2`, `enrich_workflow`, `upgrade_workflow_ir`, `WorkflowNodeSemantics`,
`validate_compiled_release`. It remains **deterministic planning/tooling, not runtime authority**:
it makes no binding decision, approves nothing, authorizes no action, clears nothing, and runs
nothing. (The `workflow_ir.v2` contract is consumed downstream by AWC's P2.1 compatibility adapter,
§G1 — a separate package; PWC owns the compilation, not the consumption.)

**ServiceNow adjacency / strength.** Flow Designer, policy/risk methodologies, approval
playbooks, and governance workflow configuration.

**Ugence differentiation.** Do **not** compete with Flow Designer. PWC is
policy-to-executable-constraint *compilation* for autonomous AI, so the LLM does not reinterpret
natural-language policy afresh on every decision.

```
ServiceNow current / adjacent           Ugence runtime workflow (PWC)
──────────────────────────────          ─────────────────────────────
Human policy / governance record        Regulation / corporate policy / risk standard
        │                                        │
        ▼                                        ▼
Questionnaires / static rules           PWC ingestion / AST
        │                                        │
        ▼                                        ▼
Configured process                      workflow_ir  (versioned, digest-addressed)
                                                 │
                                                 ▼
                                        Deterministic constraints consumed by
                                        Risk / Decision / Action / Composer controls
```

> Policy prose: *"Purchases above $100K require CFO approval."*
> → WorkflowIR: `IF amount > 100000 THEN REQUIRE authority = CFO ELSE procurement_authority`

**How it enhances ServiceNow workflow capability.** A **ServiceNow adapter can export** approved
policy/control definitions into PWC, which compiles them into deterministic, digest-addressed
`workflow_ir` that every downstream runtime control evaluates identically — eliminating the risk
that an LLM re-interprets the same policy differently on each invocation. (PWC compilation is the
shipped Ugence capability; the ServiceNow export adapter is a proposed integration, not a shipped
connector.) ServiceNow owns the policy record; PWC compiles its approved meaning.

**Discovery question.** *"Can policy approved in ServiceNow be exported as machine-enforceable
constraints that a runtime decision engine evaluates without reinterpreting natural-language
policy?"*

---

## C. Evidence & Assertion (Providers)

### C1. TAP — Truth Assurance / Assertion Governance

| | |
|---|---|
| **Package** | `packages/providers/tap` → `ugence-tap-provider` |
| **Vocabulary** | `SUPPORTED` / `CONSTRAINED` / `INDETERMINATE` |
| **Authority** | Advisory (assessment / recommendation only) — never authorizes or executes |

**What the package does.** An assertion-governance provider implementing the neutral
`AssertionGovernanceProvider` contract. Given a material assertion and supplied evidence
references, TAP evaluates whether the assertion is supported, constrained, or indeterminate and
returns a component-level result (`.coverage.value`, `.evidence_coverage`). **Its most important
invariant:** uncertainty, missing evidence, or infrastructure failure is *never* promoted to
`SUPPORTED` — it maps to `INDETERMINATE`, enforced as a release gate.

**ServiceNow adjacency / strength.** AI governance and guardrails, input/output safety controls,
risk/compliance records.

**Ugence differentiation.** TAP is not primarily content moderation. It governs whether an
individual assertion's *factual basis* is **supported** by the supplied evidence before the model
is allowed to rely on it.

> **TAP assertion-support vs RA‑5 trusted evidence admission — keep these distinct.** The shipped
> `ugence-tap-provider` performs **assertion support / coverage**: given an assertion and evidence
> references it returns `SUPPORTED / CONSTRAINED / INDETERMINATE`. The **evidence-admission** layer
> for the Risk Authority spine is now shipped as `ugence-risk-authority-evidence-runtime` (RA‑5):
> it supplies **trusted evidence admission + control assurance** upstream of envelope issuance, so
> that in production a caller-supplied `status="PASS"` is inert and only an evidence-derived,
> RA‑re-checked `ControlResult` satisfies a required control (it uses TAP for assertion coverage via
> `TapControlAssurance`). Do not present TAP's assertion-support verbs as RA‑5 admission semantics,
> and vice-versa. (The `ADMITTED / REJECTED / STALE / CONFLICTING` four-verdict vocabulary from the
> earlier spec was **not** independently re-verified as RA‑5's public surface at this SHA; RA‑5's
> confirmed contract is the trusted `ControlResult`.)

```
TAP assertion support (shipped)          RA‑5 trusted evidence admission (shipped, reference-grade)
─────────────────────                    ───────────────────────────────────────────────────
Assertion + evidence refs                Evidence / claim
        │                                        │
        ▼                                        ▼
Support / coverage evaluation            Trusted ingress + control assurance (TAP-backed)
        │                                        │
        ▼                                        ▼
SUPPORTED / CONSTRAINED / INDETERMINATE  Evidence-derived, RA‑re-checked ControlResult
        │                                        │
        ▼                                        ▼
(feeds assessment / recommendation)      upstream of RiskAuthorizationEnvelope issuance
```

> AI claim: *"Vendor X should win because its certification is current."* → TAP asks: do the
> supplied references *support* the claim? → `SUPPORTED` / `CONSTRAINED` / `INDETERMINATE`. The
> decision engine cannot overcome missing evidence merely because the model is confident. RA‑5
> additionally makes control satisfaction depend on *trusted, re-checked* evidence rather than a
> caller-asserted pass.

**How it enhances ServiceNow workflow capability.** A ServiceNow decision workflow can call TAP
today to gate whether the *evidence supports* an autonomous step's claim, so a
confident-but-unsupported model claim never advances the workflow; RA‑5 extends that to trusted
admission before a required control can be satisfied. ServiceNow governs the AI system; TAP governs
whether the evidence used in *this* decision supports it.

**Discovery question.** *"Can a runtime AI decision gate whether the evidence *supports* a claim
(shipped TAP), and require that evidence be *trusted and re-checked* — not merely caller-asserted —
before a control is satisfied (shipped RA‑5)?"*

---

## D. Decision & Authority Kernel

### D1. Decision Authority (AI Decision / Binding-Decision Kernel)

| | |
|---|---|
| **Package** | `packages/capabilities/decision-authority` → `ugence-decision-authority` (v1.0.0, frozen API) |
| **Vocabulary** | Binding `DecisionOutcome` on an immutable `DecisionRecord` |
| **Authority** | Binding business decision — **AI is structurally barred as an authorizing principal** |

**What the package does.** The bounded, domain-neutral governance **kernel** that governs *when
an AI recommendation may become a binding business decision*. It owns decision cases,
recommendations, decisions, action requests, context-envelope records (CER), authorization,
execution, and reconciliation — with no knowledge of any subject domain. Public surface:
`DecisionCaseService`, `DecisionRecord`, `DecisionOutcome`, `LinkedRecordPort`, `AuthorityType`.
Critically, **`AuthorityType` has no AI member** — AI cannot be the authorizing principal, in
code, not just in policy prose.

**ServiceNow adjacency / strength.** AI risk assessments, AI cases, control assessments,
regulatory classification, accountability workflows, approval playbooks, lifecycle governance.

**Ugence differentiation.** Ugence **separates AI decision-making from AI self-authorization.** An
AI may make a binding decision only *within authority previously delegated by an authorized human
or enterprise-policy principal* — it never grants itself that authority. Decision Authority
verifies the delegation, and the resulting **DecisionCase** becomes the authoritative artifact
that constrains runtime execution.

```
Correct  (delegated authority)              Prohibited  (self-authorization)
────────────────────────────────           ─────────────────────────────────
Enterprise policy / human authority         AI
        ↓                                    ↓
Delegates bounded decision authority        AI grants itself authority
        ↓                                    ↓
AI evaluates the case                       AI acts
        ↓                                   ✗ structurally impossible — AuthorityType
Decision Authority verifies delegation        has no AI member
        ↓
AI-generated DecisionRecord becomes binding
        ↓
Action authorization (ActionGate)
```

```
DecisionCase
  ├─ admitted evidence          ├─ decision
  ├─ excluded evidence          ├─ confidence boundaries
  ├─ policy / rubric version    ├─ authority basis (the delegating principal)
  ├─ model identity             ├─ conditions
  ├─ assessment / reasoning     └─ resulting authorization
```

This is **governed AI decision-making under delegation**, not AI recommendation governance and
not AI self-authorization. Decision Authority is the *shipped binding-decision kernel* (frozen at
v1.0.0) and, in the shipped Risk Authority composition (§D2), it is an **additive, subtractive-only
governance input**: the canonical `ugence-decision-authority` is the principal that
`ugence-risk-authority-runtime` (RA‑4.5) consults to confirm a binding ruling before the Risk
Authority spine mints a signed `RiskAuthorizationEnvelope`. It may **veto or tighten** the
authority that is issued; it can never widen or manufacture it. The kernel itself does not compile
GRC policy, mint signed envelopes, or manage an authority registry — those are Risk Authority
responsibilities (§D2). Two ownership facts matter for the assurance layer: **Decision Authority
remains the sole owner of execution and reconciliation records** (`execution/`,
`reconciliation` services), and the RA‑7/RA‑8 assurance layers observe and assess but never own
those records.

**How it enhances ServiceNow workflow capability.** When an enterprise removes the human
approver, Decision Authority supplies Ugence's explicit machine-consumable *authoritative decision
artifact* for that transition — an immutable record that captures which evidence was admitted,
which authority basis applied, and what downstream authorization it produced — while structurally
guaranteeing that AI never authorizes itself. ServiceNow remains the system of record; Decision
Authority
produces the machine-consumable decision object that record refers to.

**Discovery question.** *"If an enterprise removes the human approver and allows an AI to make a
consequential decision, what becomes the authoritative decision artifact in ServiceNow, and how
does that artifact constrain the downstream action?"*

### D2. Risk Authority — Packaged Executable-Authority Spine · **SHIPPED (RA‑1→RA‑8)**

| | |
|---|---|
| **Status** | ✅ **Shipped, independently packaged** — one authority-spine leaf plus five composition/runtime distributions on the default branch. Reference-grade; **production deployment validation pending**. |
| **Packages** | `packages/risk_authority` → `ugence-risk-authority` 0.1.0 (RA‑1→RA‑4); `packages/integration/risk-authority-runtime` (RA‑4.5); `…-evidence-runtime` (RA‑5); `…-status-runtime` (RA‑6); `…-runtime-assurance` (RA‑7); `…-execution-assurance` (RA‑8), all 0.1.0 |
| **Vocabulary** | `RiskDecisionCase` → advisory `RiskRecommendation` → binding `RiskOutcome` → signed, scoped, time-bound `RiskAuthorizationEnvelope` → `ActionGateDecision` |
| **Authority** | Executable authority — the sole issuer of signed machine-execution authority, between systems of record and systems of action |

> **This is no longer a design baseline.** In earlier editions Risk Authority was labeled
> *planned / not yet a package*. That is now **incorrect**: the authority spine is shipped as
> `ugence-risk-authority` (RA‑1→RA‑4), and RA‑4.5 through RA‑8 are each shipped as their own
> independently installable distribution. What is *not* claimed is production-deployment
> validation: the leaf ships **reference** implementations behind ports, several runtimes are
> **reference-grade** or delegate persistence/crypto to a vetted backend/HSM, and issuance should
> be backed by a vetted signing library in production (see maturity notes below and Appendix B).

**The corrected authority model (read this first).** The spine is built around a small number of
non-negotiable authority facts, enforced in code, not merely asserted in prose:

- **Risk Authority is the sole issuer of signed machine-execution authority.** Only an
  `ALLOW`-family `RiskDecision` (`grants_authority`) produces a `RiskAuthorizationEnvelope`.
- **`RiskAuthorizationEnvelope` is the sole signed machine-authority artifact** (Ed25519-signed,
  scoped, time-bound; its scope can never exceed the decision's scope — envelope monotonicity).
  RA‑4.5's `GovernedExecutionDecision` *wraps* the envelope with governance evidence and effective
  constraints but **carries no signature and is not a second authorization envelope**; RA‑5→RA‑8
  add **no** second machine-authority artifact and no third execution ledger.
- **Decision Authority and ActionGate are additive, subtractive-only governance inputs.** They may
  **veto or tighten** (deny, or narrow scope/conditions); they may **not widen or manufacture**
  authority. A Decision Authority refusal grants nothing; ActionGate accumulates deny reasons and
  returns `AUTHORIZED` only when none apply — it never fabricates scope.
- **The `risk_authority` leaf uses reference implementations behind ports** (`ReferenceActionGate`
  behind `ActionGatePort`, `ReferenceDecisionAuthority` behind `DecisionAuthorityPort`) so it can
  stay a stdlib-only leaf. These are *proving stand-ins* and must not be mistaken for the canonical
  kernels. **Production composition with the canonical Decision Authority and ActionGate packages
  belongs to `risk-authority-runtime` (RA‑4.5).**
- **RA‑7 and RA‑8 emit assessments/evidence and neutral reassessment signals; they never own
  authority. RA‑6 owns authority lifecycle consequences** (revocation / supersession / epoch
  propagation), and Decision Authority remains the sole owner of execution/reconciliation records.

**The packaged spine (RA‑1 → RA‑4).** `ugence-risk-authority` implements the RA‑1→RA‑4 vertical
slice as an ordered, non-compensatory pipeline (README):

```
WorkflowIR → RiskDecisionCase → ControlResult (non-compensatory)
   → Decision Authority (delegation-monotone: IssuedAuthority ⊆ DelegatedAuthority)
   → Signed RiskAuthorizationEnvelope (Ed25519, scope ⊆ decision)
   → Canonical Action (deterministic digest)
   → ActionGate (bounded, offline, no LLM)   →  AUTHORIZED / DENIED
```

RA‑4 is the ActionGate enforcement seam: an agent can physically perform *only* what the signed
envelope authorizes, checked deterministically with no LLM call and no regulatory-text
reinterpretation. Public surface (illustrative): `RiskAuthorizationEnvelope`, `RiskDecision`
(`grants_authority`), `RiskRecommendation` / `RiskOutcome` (`ALLOW` / `ALLOW_WITH_CONDITIONS` /
`ESCALATE` / `DENY`), `ActionGateDecision` (`AUTHORIZED` / `DENIED` / `RETRY_STATE_CHANGED`), and
the ports `ActionGatePort` / `DecisionAuthorityPort` / `ControlAssurancePort` /
`EvidenceAdmissionPort` with their reference implementations.

**The composition / runtime layer (RA‑4.5 → RA‑8).** Each is an independently packaged
distribution that layers on the shipped leaf:

| Package | RA level | Role | Maturity note (verbatim-grounded) |
|---|---|---|---|
| `ugence-risk-authority-runtime` | **RA‑4.5** | Fail-closed **production composition**: wires the machine-authority owner (`ugence-risk-authority`) with two additive governance inputs — the **canonical** `ugence-decision-authority` and `ugence-actiongate-provider` — into a single `GovernedExecutionDecision`. | "governance composition implemented and CI-verified; production deployment validation remains pending" |
| `ugence-risk-authority-evidence-runtime` | **RA‑5** | Trusted **evidence admission + control assurance** upstream of envelope issuance; in production a caller-supplied `status="PASS"` is inert — only an evidence-derived, RA‑re-checked `ControlResult` satisfies a required control. | Production impls behind the leaf's ports; adds no second machine-authority signature |
| `ugence-risk-authority-status-runtime` | **RA‑6** | **Owns authority lifecycle consequences** — revocation, supersession, expiry, epoch propagation. Model: observers *signal*, Risk Authority *reassesses*, a single authorized writer *mutates*, ActionGate/runtime enforce *read-only*. | Reference in-memory persistence + delegated auth seam; not globally-consistent, cryptographically-attested, multi-region, or zero-window revocation |
| `ugence-risk-authority-runtime-assurance` | **RA‑7** | **Runtime / trajectory assurance** — observes the Agent Runtime via a neutral event seam, risk-types the per-instance trajectory, and on a material deviation emits a **neutral `AuthorityReassessmentSignal`** into the RA‑6 intake. `TrajectoryAssessment` = `NORMAL` / `ESCALATED` / `UNKNOWN` (evidence, not authority). Mints nothing; not a second authority. | "Event-driven, reference-grade runtime assurance"; revocation bites at the next pre-effect recheck (bounded-latency, not instantaneous) |
| `ugence-risk-authority-execution-assurance` | **RA‑8** | **Execution / effect assurance** — post-effect reconciliation of whether actual execution/effect matched what was authorized, emitting `AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)`. Evidence + neutral signal, never authority. Decision Authority remains the sole owner of execution/reconciliation records; persistence is delegated to it. | "Reference-grade post-effect reconciliation"; integrity ≠ authenticity (a content hash is not a signature); reference reconciler refused in production |

**What the spine does not replace.** It does **not** replace GRC platforms (OneTrust, ServiceNow
GRC, Archer, Credo AI, Holistic AI). It *consumes* approved policy and risk decisions, binds them
to admissible evidence and delegated authority, and enforces the resulting compact authorization
at runtime. Product thesis: *"Your GRC system tells you what your AI policy is; Ugence makes it
executable."*

**Non-compensatory execution invariant.** Execution is permitted only when every independent gate
passes — a fail-closed conjunction (the spine's ordered pipeline plus the RA‑4.5 composition and
RA‑6 lifecycle state realize this in code):

```
P ∧ E ∧ R ∧ A ∧ O ∧ L  →  X
  P = correct policy/version binding      A = exact requested action is authorized (ActionGate)
  E = admissible & current evidence (RA‑5) O = operational environment is clear (ACP)
  R = binding risk decision permits op     L = authority still live (RA‑6: not revoked/expired)
  X = execution        Fail-closed:  ¬P ∨ ¬E ∨ ¬R ∨ ¬A ∨ ¬O ∨ ¬L  →  ¬X
```

**ServiceNow adjacency / strength.** ServiceNow GRC / AI Risk & Compliance: policy libraries,
risk registers, control assessments, AI cases, approval workflows, audit management.

**Ugence differentiation.** This is the module that ties the architecture together: ServiceNow (or
any GRC system) remains the system of record for governance; the Risk Authority spine converts an
approved governance state into **cryptographically bound, evidence-backed, state-aware machine
authority** — a signed `RiskAuthorizationEnvelope` (Ed25519, SHA-256 action digests,
tenant/subject/model/version/validity-window bindings) that ActionGate consumes on a bounded,
offline hot path whose cost scales with the compact envelope, not the size of the policy corpus.

```
ServiceNow current / adjacent           Risk Authority runtime workflow  [SHIPPED · reference-grade]
──────────────────────────────          ───────────────────────────────────────────
Compliance team                         Workflow / AI use case
        │                                        │
        ▼                                        ▼
Risk register                           RiskDecisionCase  (RA‑1→RA‑3)
        │                                        │
        ▼                                        ▼
Questionnaires / assessments            Admissible evidence (TAP / RA‑5) + control assurance
        │                                        │
        ▼                                        ▼
Approval / case                         Binding RiskDecision (Decision Authority, RA‑4.5)
                                                 │
                                                 ▼
                                        Signed RiskAuthorizationEnvelope (scoped, time-bound)
                                                 │
                                                 ▼
                                        ActionGate (RA‑4) → ACP → Authorized Execution
                                                 │
                                                 ▼
                                        RA‑7 trajectory + RA‑8 effect assessment → neutral signal
                                                 │
                                                 ▼
                                        RA‑6 owns the consequence: revoke / supersede / epoch
```

**How it enhances ServiceNow workflow capability.** It answers *"what machine-consumable runtime
artifact represents a risk/approval outcome after the human workflow is complete?"* — the shipped
answer is a signed, scoped, time-bound and revocable `RiskAuthorizationEnvelope`. ServiceNow
records and orchestrates risk governance; the Risk Authority spine turns an approved risk outcome
into executable, revocable authority and can feed decision/enforcement/assessment events back to
the GRC system for its audit dashboards. (An actual ServiceNow connector is not part of these
packages; the integration remains a proposed adapter.)

**Discovery question.** *"After the human workflow is complete, what is the closest corresponding
runtime artifact in your architecture that represents the risk/approval outcome — and can it be
cryptographically bound, scoped, time-bound and revocable, the way the Ugence
`RiskAuthorizationEnvelope` is?"*

---

## E. Action Authorization & Operational Clearance

### E1. ActionGate — Exact-Action Authorization

| | |
|---|---|
| **Package** | `packages/providers/actiongate` → `ugence-actiongate-provider` |
| **Vocabulary** | `AUTHORIZED` / authorized-with-constraints / `DENIED` / `INDETERMINATE` |
| **Authority** | Authorization only — *authorization is never execution* |

**What the package does.** An action-governance provider implementing the neutral
`ActionGovernanceProvider` contract. Given a proposed action and its authority/policy/risk/
evidence/decision context, ActionGate returns a structured authorization result
(`.outcome.value`). **Invariant:** uncertainty/failure maps to `INDETERMINATE`, never to
`AUTHORIZED`; `DENIED` and `INDETERMINATE` never dispatch. It binds approval to the exact
action/payload and rechecks at commit time. It owns *no* dispatch or execution authority and is
an independent peer of TAP (neither imports the other).

**ServiceNow adjacency / strength.** AI asset and agent governance, tool/MCP approvals, identity
and access controls, workflow and agent-action controls.

**Ugence differentiation.** ActionGate operates at the **exact-action layer**. Approval of an
agent or a tool does not imply approval of every payload that agent can generate.

```
Agent approved
      ↓
Tool approved
      ↓
AI proposes:  refund(customer=38291, amount=$4,870)
      ↓
   ACTIONGATE  — canonical payload + hash + scope/purpose/amount/destination match
      ↓
refund.prepare amount ≤ $5,000   ≠   refund.execute amount = $8,000
      ↓
AUTHORIZED / DENIED / INDETERMINATE  (commit-time recheck)
```

**How it enhances ServiceNow workflow capability.** ServiceNow can govern whether an agent and
tool *belong* in the enterprise; ActionGate governs whether *this exact action, with this exact
payload, is authorized right now* — and re-validates immediately before execution. It closes the
gap between "the agent is approved" and "this specific $8,000 refund is not."

**Discovery question.** *"At runtime, can an approval be bound to one exact payload and
revalidated immediately before execution?"*

### E2. Action Clearance — Operational Clearance (ACP)

| | |
|---|---|
| **Package** | `packages/capabilities/action-clearance` → `ugence-action-clearance` |
| **Vocabulary** | `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` (precedence `BLOCK > ESCALATE > HOLD > CLEAR`) |
| **Authority** | Operational clearance — *may narrow/hold/block, never create or broaden authority* |

**What the package does.** A deterministic, domain-neutral, **stateless** function:
`evaluate_clearance(request, policy) -> ClearanceResult`. Given an *already-authorized* exact
action plus a bundle of trusted current-state signals, it decides whether that action remains
operationally **CLEAR** in the instant immediately before execution. It reads no clock (caller
supplies `evaluation_time`), holds no persistence, and may preserve, narrow, hold, escalate, or
block an existing authorization — but may never create authority, broaden it, replace ActionGate,
or dispatch.

**ServiceNow adjacency / strength.** ITSM/ITOM/operations context, workflow execution, incident
and change-management state.

**Ugence differentiation.** A decision can be correct and an action authorized while execution
is still unsafe *right now*. Action Clearance makes operational clearance a **separate,
non-compensatory gate** — AI authority cannot override an active freeze, unavailable rollback,
instability, or blast-radius restriction.

```
AI decision        APPROVED
ActionGate         AUTHORIZED          ← authorization is valid
Database freeze    ACTIVE
Rollback ready?    NO
Blast radius       EXCEEDED
        ↓
Action Clearance   NOT CLEAR (BLOCK)
        ↓
   NO EXECUTION
```

**How it enhances ServiceNow workflow capability.** ServiceNow holds the operational
state (freezes, change windows, incident status); Action Clearance turns that state into an
independent, fail-closed veto that sits between authorization and dispatch — so an authorized AI
action still cannot execute into an unsafe live environment. Decision correctness and execution
safety are treated as independent facts.

**Discovery question.** *"If the AI decision and action authorization are valid but the live
environment is unsafe, what component independently prevents execution?"*

---

## F. Model & Context Governance

### F1. Model Authority (Model Selection kernel → binding authorization)

| | |
|---|---|
| **Package** | `packages/capabilities/model-selection` → `ugence-model-selection` 0.1.0 |
| **Vocabulary** | `ModelAuthorizationDecision` → `ModelAuthorizationDisposition` `ALLOW` / `DENY` / `HOLD` / `ESCALATE` (+ governed fallback, reason codes) |
| **Authority** | Per-request model authorization; **model invocation / execution is explicitly out of scope** |

**What the package does.** The deterministic **Model Authority** core. Its `ExecutionGate` applies
mandatory eligibility constraints fail-closed (approved-candidate membership, privacy/
jurisdiction/residency, capability/modality/tool-use, context-window sufficiency, stale-evidence
handling) and **never ranks**; `select(...)` applies policy-weighted scoring over *only* the
eligible set with deterministic tie-breaking. `ModelAuthority` then **wraps** those two audited
stages — it *"adds no new selection mathematics"* — and turns the outcome into a binding
`ModelAuthorizationDecision`. That is now **shipped**, not a target: the earlier editions marked it
"near-term," which is no longer correct.

> **Model Authority is shipped.** `ModelAuthorizationDecision` (frozen dataclass in `authority.py`)
> carries: a deterministic `decision_id` (fingerprint of request + candidates + decision content —
> no wall clock, no randomness, prefixed `mad_`); a `disposition` of `ALLOW` / `DENY` / `HOLD` /
> `ESCALATE`; `authorized_model_id` / `authorized_provider_id`; `reason_codes`
> (`AuthorityReasonCode`: `AUTHORIZED`, `FALLBACK_AUTHORIZED`, `NO_ELIGIBLE_MODEL`,
> `EXECUTION_WITHHELD`, `EVIDENCE_INDETERMINATE`, `HUMAN_REVIEW_REQUIRED`); **governed
> `fallback_model_ids`** (each already eligibility-passed); `policy_version` (policy provenance,
> `exec_gate_v1`); and `expires_at` (epoch-seconds expiry after which cited evidence is stale and
> the decision must be re-evaluated). **Model invocation / provider API calls / routing / retries /
> failover are explicitly *not owned* by this package** — authorization is the external contract,
> ranking stays an internal optimization.

```
ServiceNow workflow / AI agent
        ↓
ExecutionGate (mandatory eligibility, fail-closed, never ranks)
        ↓
Eligible model set  →  ModelPolicy ranking (policy-weighted, over eligible only)
        ↓
ModelAuthority.authorize(...)      — wraps eligibility + ranking; adds no new math
        ↓
ModelAuthorizationDecision
   ├─ disposition:  ALLOW / DENY / HOLD / ESCALATE
   ├─ authorized_model_id / provider_id (on ALLOW)   ├─ reason_codes
   ├─ fallback_model_ids (governed; each eligible)   ├─ policy_version (provenance)
   └─ decision_id (deterministic)                    └─ expires_at (freshness bound)
        ↓
(no invocation, no fallback execution — model execution is out of scope)
```

> Illustrative policy intent: general task → external lower-cost model may be eligible; restricted
> customer data → private deployment only; high-impact financial decision → model must satisfy
> evaluation/version requirements. `HOLD` withholds execution when evidence is indeterminate;
> `ESCALATE` routes to a higher authority / human / policy workflow.

**Maturity note.** Shipped and deterministic, but its demonstrated evidence is **primarily
synthetic**: this is a behavior-preserving structural migration that established no real
provider-reliability claim and added no routing or execution capability.

**ServiceNow adjacency / strength.** AI/model inventory, approved providers and connections,
AI Control Tower governance.

**Ugence differentiation.** Do not pitch model inventory. The differentiator is **per-request model
authority**: the same model may be eligible for one request and prohibited for another at the same
moment, and the platform issues a binding per-request `ModelAuthorizationDecision` — with reason
codes, governed fallback and an expiry — rather than a static configuration.

**How it enhances ServiceNow workflow capability.** ServiceNow configures *which models the
enterprise may use*; Model Authority determines *which eligible model is authorized for this
specific request*, turning static configuration into a per-request binding authorization while
leaving actual model execution to the caller.

**Discovery question.** *"Does model choice remain a configuration decision, or can the platform
issue a per-request binding authorization (ALLOW/DENY/HOLD/ESCALATE) based on policy, data,
jurisdiction, risk and runtime state — with a governed fallback and an expiry?"*

### F2. LLM Steering Controller

| | |
|---|---|
| **Package** | `packages/capabilities/llm-steering-controller` → `ugence-llm-steering-controller` |
| **Vocabulary** | `recommend(registry, request)` → `RECOMMENDED` (`execution_status = NOT_EXECUTED`) |
| **Authority** | Advisory routing — no execution, no credentials |

**What the package does.** A deterministic, provider-neutral advisory routing layer *above* the
model-selection leaf: it discovers candidates from a metadata-only registry, applies hard
policy/capability constraints fail-closed before scoring, ranks the eligible set on decomposable
dimensions, and returns a ranked, explainable routing *recommendation* — with `recommendation_only
= true`. It executes nothing and loads no credentials.

**ServiceNow adjacency / strength.** Now Assist guardrails, input/output safety and moderation,
AI configuration.

**Ugence differentiation.** Position this as **model-provider-independent semantic framing tied
to an enterprise DecisionCase**, not generic toxicity or prompt-injection protection. Steering is
anchored to the exact decision policy and evidence context, then checked for semantic consistency
and TAP evidence support.

```
DecisionCase context
        ↓
Approved semantic / policy frame
        ↓
Candidate responses (across providers)
        ↓
Semantic consistency check  +  TAP evidence/claim verification
        ↓
Approved output
```

**How it enhances ServiceNow workflow capability.** It complements — never replaces —
ServiceNow's content-safety guardrails by anchoring prompt/output steering to the *specific
enterprise decision policy and evidence*, so framing is governed by the decision at hand rather
than only by general content categories.

**Discovery question.** *"Can prompt/output steering be anchored to the exact enterprise decision
policy and evidence context rather than only general content-safety categories?"*

### F3. Context Minimization

| | |
|---|---|
| **Package** | `packages/capabilities/context-minimization` → `ugence-context-minimization` 0.2.0 (+ `ugence-context-minimization-token-accounting-runtime` 0.1.0) |
| **Vocabulary** | `minimize_context(...)` / `structural_minimize(...)` (`surviving_ids`, `equivalence_status`) + CM‑TA1 token-accounting contracts |
| **Authority** | None — deterministic **extractive** reducer, fails closed on non-equivalence |

**What the package does.** A deterministic, domain-neutral **extractive** context reducer. Given
an already-assembled context it removes units by omission while preserving a caller-defined
deterministic equivalence condition (a neutral `InvarianceOracle` the caller injects), and
**fails closed** whenever equivalence cannot be established. It never rewrites, paraphrases, or
summarizes, and creates no authority.

**New in v0.2 — token-accounting contracts (CM‑TA1).** The 0.2.0 release adds an additive
token-accounting module that keeps **three distinct measurements** rigorously separate and never
collapses them into one field:

1. **Context reduction** — `MinimizationResult.original_tokens / resulting_tokens /
   achieved_reduction` (what the reducer removed); the accounting module *copies* these, never
   re-runs minimization.
2. **Complete-request estimate** — `RequestTokenEstimate.estimated_input_tokens` for the *whole*
   serialized request (system + messages + minimized context + tool definitions + schemas +
   provider wrappers), produced by an **injected** `RequestTokenCounter`. The package ships only
   the transparent `DefaultApproximateRequestCounter` (`DEFAULT_APPROXIMATE`, word/punctuation) —
   **not** a provider tokenizer.
3. **Provider-reported usage** — `ProviderTokenUsage`, optional non-negative ints; **unknown is
   `None`, never fabricated as zero**.

Provenance is tracked by `TokenCountBasis` (`CALLER_SUPPLIED` / `INJECTED_COUNTER` /
`DEFAULT_APPROXIMATE` / `MIXED` / `PROVIDER_REPORTED` / `UNKNOWN`); the measurement APIs are
`prepare_api_call_measurement`, `reconcile_api_call_measurement` and `aggregate_logical_request_usage`.

**The token-accounting integration runtime.** Cross-package wiring lives in a separate distribution,
`ugence-context-minimization-token-accounting-runtime` (module `ugence_cm_token_accounting_runtime`,
depends on `ugence-context-minimization >= 0.2.0` and `ugence-agent-runtime >= 0.7.0`, one-way).
It **Translates** an Agent Runtime `ProviderAttempt` into a CM `ApiCallTokenRecord` via an injected
`UsageNormalizer`, **Records** every attempt (retries and failures included) through a
`TokenAccountingSink`, and **Settles** — it settles **H22‑D budgets from *measured* usage** when
that usage is authoritative, falling back to the conservative full-reservation settlement when
usage is unavailable, and surfacing `BudgetEstimateExceeded` rather than clamping or hiding an
overrun.

```
Available:       54 attributes  →  Policy permits: 7  →  Decision needs: 4
        ↓
Context Minimization  (extractive, equivalence-preserving, fail-closed)
        ↓
surviving_ids + equivalence_status        (only retained units leave the boundary)
        ↓
CM‑TA1 token accounting  (three measurements kept distinct; provenance-tagged)
        ↓
token-accounting-runtime  → measured H22‑D budget settlement (else conservative fallback)
```

> **Retained limitations (stated, not smoothed over).** No provider SDK; no real provider adapters
> (usage normalizers are injected and live outside the package); no durable accounting persistence
> (the shipped sink is in-memory / reference only); **no pricing authority** (no cost is computed);
> and **no invoice reconciliation** (provider-reported usage is authoritative only for the single
> API response reconciled). The capability's own guarantees are synthetically validated; maturity
> is `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` with no live-enterprise validation claim.

**ServiceNow adjacency / strength.** Security/privacy/governance controls, data access governance,
third-party AI configuration.

**Ugence differentiation.** Make data minimization itself *part of the authorization evidence*:
only the data required, authorized, and permitted for the specific decision crosses the AI
boundary — and make the token cost of that boundary crossing *measurable* (reduction vs
complete-request estimate vs provider-reported usage), without ever inventing a number.

**How it enhances ServiceNow workflow capability.** Instead of merely governing *whether* an
external model may be used, it governs *exactly what information* the model is allowed to see for
this decision, returns the surviving units and equivalence status, and — through the
token-accounting runtime — reconciles the measured token usage of each provider attempt against a
governed budget.

**Discovery question.** *"Can the platform reduce context to exactly what a decision needs, and
account for the token cost of that decision by keeping reduction, complete-request estimate and
provider-reported usage distinct — without fabricating a usage number or claiming a price?"*

---

## G. Workforce & Sequence Governance

### G1. Agent Workforce Composer (AWC)

| | |
|---|---|
| **Package** | `packages/capabilities/agent-workforce-composer` → `ugence-agent-workforce-composer` 0.2.1 |
| **Vocabulary** | `AgentTeamPlan`; composition result `EXACT_OPTIMUM` / `NO_FEASIBLE_TEAM` / `SEARCH_SPACE_EXCEEDED` |
| **Authority** | None — planning only; *an eligible plan is a proposal, never a grant* |

**What the package does.** A deterministic, offline *planning* capability. It adapts a compiled
`workflow_ir` into role requirements, computes hard-constraint agent eligibility
(`AgentEligibilityGate`), ranks eligible agents, composes a bounded exact multi-role team,
proposes least-privilege permission bounds (`PermissionBoundProposal`), and orders fallbacks —
producing an immutable **`AgentTeamPlan`**. It grants nothing, authorizes nothing, schedules
nothing, executes nothing.

> **New in P2.1 — the `workflow_ir.v2` compatibility adapter.** AWC now consumes the Policy
> Workflow Compiler's enriched `workflow_ir.v2` contract directly: `adapt_workflow` dispatches
> explicitly by contract version, the v1 path stays byte-frozen, and equivalent v1/v2 inputs
> produce `SEMANTICALLY_EQUIVALENT` plans. This P2.1 v2 compatibility adapter belongs to **AWC**
> (contract `awc.compiler_adapter.v2`); PWC owns the compilation, AWC owns the consumption, and the
> two never import each other. The `awc.v1` / `awc.composition.v1` planning contracts are unchanged.
> AWC remains deterministic planning/tooling, **not** runtime authority: `pilot_validated = False`,
> `production_certified = False`.

**ServiceNow adjacency / strength.** Agent orchestration and agentic AI platform, workflow
assignment, skills and capabilities.

**Ugence differentiation.** AWC focuses on **governed workforce composition before execution** —
which combination is capable, certified, policy-eligible, available, independent, and
non-conflicting — while creating **zero new authority**.

```
Candidate agents
        ↓
Capability + certification + policy + availability + independence
        ↓
AgentTeamPlan   (least-privilege permission bounds, ordered fallbacks)
        ↓
ZERO NEW AUTHORITY
        ↓
Each later action still requires its own ActionGate authorization
```

**How it enhances ServiceNow workflow capability.** When ServiceNow assembles multiple AI agents,
AWC guarantees the assembled team inherits *no more authority than each policy-approved role
already possesses* — composition chooses *who may participate*, it does not grant the team new
power.

**Discovery question.** *"When multiple AI agents are assembled, can the team inherit no more
authority than each policy-approved role actually possesses?"*

### G2. StoryGraph Sequence Risk — Sequence-Risk Analyzer

| | |
|---|---|
| **Package** | `packages/capabilities/storygraph` → `ugence-storygraph` (v2.0.0) |
| **Vocabulary** | `OBSERVE` / `ESCALATE` / `UNAVAILABLE` (advisory, `ADVISORY` effect ceiling) |
| **Authority** | Advisory / evidentiary — *never* emits `ALLOW`/`DENY`/`AUTHORIZE`/`CLEAR` (machine-checked) |

> **Three different things, deliberately named apart.** **StoryGraph Sequence Risk** (this section,
> shipped `ugence-storygraph`) *detects dangerous action sequences in real time* and emits advisory
> evidence. **RA‑7 Runtime Assurance** (§H2, shipped `ugence-risk-authority-runtime-assurance`)
> *risk-types the live per-instance trajectory and emits a neutral reassessment signal* into the
> RA‑6 authority-lifecycle owner — it is assurance/evidence, **not a second authority**. The
> **Governance Story Graph** (Part III, proposed) *records causal provenance across the entire
> lifecycle*. All three are related but distinct; do not conflate them. (The terms "RA‑7",
> "Runtime Assurance" and "Governance Story Graph" appear nowhere inside the `ugence-storygraph`
> package — its scope is purely advisory sequence-risk.)

**What the package does.** Where ActionGate governs individual actions, StoryGraph detects when
individually-acceptable actions collectively assemble a prohibited or high-risk *capability* (a
"story") and emits advisory evidence so a downstream authority can escalate. Public API:
`SequenceRiskAnalyzer`, ontologies (`DIGITAL_ONTOLOGY`), `evaluate_proposed_action(...)`, and a
policy-as-code `policypack` (`compile_pack`, deterministic `run_replay`). It holds no binding
authority — the boundary is machine-checked.

**ServiceNow adjacency / strength.** Cases, tasks, CMDB relationships, workflow history and audit
records provide rich linked operational context — evaluated largely one record at a time.

**Ugence differentiation.** Risk is evaluated across the **multi-step execution trajectory**, not
one task at a time. Individually benign actions can, in sequence, complete a harmful capability.

```
Action t
        ↓
Current trajectory state H(t)
        ↓
Accumulated data / side effects / commitments
        ↓
Trajectory / sequence-risk evaluation (encoded capability patterns)
        ↓
OBSERVE / ESCALATE  →  downstream ActionGate or policy owns the binding consequence
```

**How it enhances ServiceNow workflow capability.** It supplies a trajectory-aware advisory
signal that a ServiceNow workflow can subscribe to — so prior behavior can change the permission
posture of the next action, which per-step approval workflows cannot express.

> **Relationship to RA‑7 runtime/trajectory assurance (§H2).** StoryGraph is a *self-contained,
> advisory* sequence-risk analyzer (`OBSERVE`/`ESCALATE`/`UNAVAILABLE` only) that reasons about
> encoded capability patterns within a proposed-action stream. RA‑7 (`ugence-risk-authority-
> runtime-assurance`) is a *different, shipped* package that observes the Agent Runtime's live
> event seam, risk-types the per-workflow-instance trajectory, and emits a **neutral reassessment
> signal** into RA‑6 — which owns the authority consequence. Neither is a binding authority: the
> binding consequence is owned downstream (ActionGate for the action, RA‑6 for the authority
> lifecycle). They are complementary trajectory-aware signals, not the same component.

**Discovery question.** *"Does prior behavior change permission — can the platform flag when a
sequence of individually-approved actions assembles a prohibited capability?"*

---

## H. Runtime Execution

### H1. Agent Runtime / Canonical Execution Request (CER)

| | |
|---|---|
| **Package** | `packages/runtime/agent-runtime` → `ugence-agent-runtime` 0.7.0 |
| **Vocabulary** | Consumes governance dispositions `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE`; H22‑A→D lifecycle |
| **Authority** | Execution coordination — *creates no authority*; fails closed if governance unconfigured |

**What the package does.** A domain-neutral execution-coordination kernel: it drives task and
workflow lifecycle, invokes providers/tools, and applies retry, timeout, cancellation,
checkpointing, and durable recovery. Before any *consequential* transition it builds an immutable
proposal and asks an injected `GovernanceHook` whether that exact proposal may proceed — and
obeys the answer. The default `UnconfiguredGovernanceHook` **fails closed** with
`GOVERNANCE_NOT_CONFIGURED`; `CLEAR` continues only if the result is bound to the exact proposal
by fingerprint + reference and not expired. Public API: `create_runtime`, `WorkflowDefinition`,
`TaskDefinition`.

**The H22 horizon (shipped, 0.7.0).** The coordination kernel is built out along four bounded
increments, each of which explicitly refuses to over-reach:

- **H22‑A — bounded workflow advancement.** `advance_workflow` advances a prepared/running
  workflow by exactly one *quantum* — at most one task transition through one stable, checkpointed
  boundary — returning a frozen `WorkflowAdvanceOutcome`. The governance→exact-action→provider→
  transition→checkpoint chain runs entirely within a single quantum; an orchestrator can never
  observe or preempt a workflow between a governance `CLEAR` and the provider call it cleared.
- **H22‑B — deterministic SWRR portfolio scheduling.** A portfolio scheduler grants exactly one
  quantum at a time using **smooth weighted round-robin** fairness within a priority tier (provably
  proportional to weight, smooth, and starvation-free), plus explicit priority and bounded aging.
  It is deterministic *interleaving*, **not** simultaneous execution, and governance stays entirely
  below it — the scheduler selects a workflow, it never authorizes its task.
- **H22‑C — durable recovery, checkpointing, trace, failure/cancellation policy.** A
  `PortfolioCheckpoint` references each workflow's checkpoint by digest and never copies it;
  `recover_portfolio` is side-effect-free and requires explicit continuation (committed work never
  reruns, and the next consequential quantum still crosses *fresh* governance); an append-only
  `PortfolioTrace` records why the coordinator acted; failure propagation is bounded
  (`ISOLATE_WORKFLOW` default / `FAIL_DEPENDENTS` / `FAIL_PORTFOLIO`) and cancellation is
  cooperative and idempotent. Torn checkpoint state fails closed
  (`PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE`).
- **H22‑D — bounded in-process concurrency, resource claims, shared budgets, governed
  compensation.** Bounded, in-process concurrency over independent quanta on real OS threads capped
  at `max_concurrent_quanta`; a `ResourceClaim` is a portfolio-coordination requirement (only
  `READ + READ` is compatible; `UNKNOWN` is fail-closed; reservation is atomic all-or-none, no
  deadlock by design); a shared `PortfolioBudget` is reserved before execution so two individually
  affordable quanta cannot together exceed it (overrun fails closed with `BudgetEstimateExceeded`);
  and **compensation is a *separately-governed* workflow** — H22‑D records the intent to schedule a
  distinct, explicitly-governed compensation workflow exactly once, and never calls a compensation
  provider directly or fabricates that the original effect occurred.
- **0.7 provider-attempt telemetry.** An additive, opt-in observation seam surfaces *every* actual
  `provider.execute` invocation — success, expected failure, timeout, provider error, raw exception
  — with the runtime-authoritative attempt number; retried and failed attempts are recorded
  distinctly and never collapsed (`ProviderAttempt`, `ProviderAttemptStatus`, `AttemptObserver`).
  The runtime imports **no** provider SDK and interprets no provider token field.

> **What Agent Runtime deliberately does not claim.** In-process only: **no distributed cluster
> scheduling, no distributed locking, no exactly-once external effects, no cluster safety, and no
> production readiness.** Resource coordination is portfolio-local (not a distributed lock);
> concurrency is bounded and in-process; the synchronous backend runs quanta one at a time by
> default. Maturity is `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` at 0.7.0 (H22‑D 0.6.0 was
> `IMPLEMENTED_AND_CI_VERIFIED`); the package is explicitly *not* live-verified, pilot-validated,
> distributed-safe, or enforcement-ready.

**ServiceNow adjacency / strength.** ServiceNow agent platform and runtime, workflow execution
environment.

**Ugence differentiation.** The differentiator is **runtime neutrality**: actions from
ServiceNow *and* non-ServiceNow agents become one governable execution object.

```
OpenAI Agents ─┐
LangGraph      ├──→ Canonical Execution Request (CER)
Anthropic      │      actor · intent · tool · payload · data · purpose · side effect
ServiceNow     │
custom agent ──┘      ↓
                Ugence governance boundary (CLEAR / HOLD / BLOCK / ESCALATE)
```

**How it enhances ServiceNow workflow capability.** The same policy and exact-action enforcement
can apply to ServiceNow agents, third-party agents, and custom frameworks through *one* runtime
contract — and because the runtime fails closed when no governance is wired, an ungoverned agent
simply cannot take a consequential action. This also underpins **multi-workflow orchestration**:
ServiceNow may remain the orchestrator while Ugence supplies the CER + authorization + trajectory
state that keeps combined workflows from inferring a new permission neither possessed.

**Discovery question.** *"Can the same policy and exact-action enforcement apply to ServiceNow
agents, third-party agents and custom frameworks through one runtime contract?"*

### H2. Runtime & Execution Assurance — two shipped layers (RA‑7 + RA‑8)

| | |
|---|---|
| **Status** | ✅ **Shipped as two separate packages** (each reference-grade; production deployment validation pending). Earlier editions described a single "composed, not packaged" Runtime Assurance — that is superseded: assurance is now split into two distinct, independently installable layers. |
| **Packages** | `ugence-risk-authority-runtime-assurance` 0.1.0 (RA‑7) and `ugence-risk-authority-execution-assurance` 0.1.0 (RA‑8) |
| **Authority** | Observation & assessment only — both emit **assessments/evidence and neutral reassessment signals**; **neither authorizes.** RA‑6 owns the authority consequence; Decision Authority owns execution/reconciliation records. |

The single loop has been separated into two layers with different observation surfaces. Keeping
them apart is deliberate — one watches the *trajectory as it runs*, the other reconciles the
*effect after it lands* — and **neither is a second authority**.

**RA‑7 — runtime / trajectory assurance** (`ugence-risk-authority-runtime-assurance`). RA‑7
observes the Agent Runtime through the existing neutral event seam, risk-types the per-workflow-
instance *trajectory*, and — on a *material* deviation — emits a neutral `AuthorityReassessmentSignal`
into the RA‑6 intake. Its verdict is a `TrajectoryAssessment` of `NORMAL` / `ESCALATED` / `UNKNOWN`
— **evidence, not authority**. RA‑7 mints nothing, mutates no lifecycle state, and cannot trigger
emergency stop; it is *event-driven, reference-grade* assurance whose revocation "bites" only at
the next pre-effect recheck (bounded-latency, not instantaneous).

**RA‑8 — execution / effect assurance** (`ugence-risk-authority-execution-assurance`). RA‑8
performs **post-effect reconciliation**: did the actual execution/effect match what was authorized,
and should a discrepancy cause future authority to be reassessed? It emits
`AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)` — again evidence plus a neutral signal,
never authority. It introduces **no second authorization artifact and no third execution ledger**:
`RiskAuthorizationEnvelope` remains the sole signed machine authority, and **Decision Authority
remains the sole owner of execution/reconciliation records** (RA‑8 delegates persistence to it).
Effect-source trust is authenticated / delegated ingress plus content-hash integrity — and the
package is explicit that *integrity ≠ authenticity* (a hash is not a signature); its reference
authenticator and reconciler are refused in production.

```
    RA‑7 (runtime / trajectory)                 RA‑8 (execution / effect)
    ───────────────────────────                 ─────────────────────────
    Agent Runtime event seam                    Execution correlation + effect observation
        ↓                                            ↓
    Trajectory risk-typing                      Effect reconciliation vs authorized intent
        ↓                                            ↓
    TrajectoryAssessment                        EffectAssuranceAssessment
      NORMAL / ESCALATED / UNKNOWN                (matched? / mismatch)
        ↓                                            ↓
    neutral AuthorityReassessmentSignal ───────► RA‑6 owns the consequence:
                                                  revoke / supersede / expire / epoch
```

**Where authority actually changes.** Both RA‑7 and RA‑8 stop at *signal*. The **RA‑6**
authority-lifecycle owner (`ugence-risk-authority-status-runtime`) is the single authorized writer
that turns a reassessment into a revocation / supersession / expiry / epoch propagation, which
ActionGate and the runtime then enforce read-only. This preserves the invariant that assurance
observes and authority decides.

**ServiceNow adjacency / strength.** Workflow/agent logs, dashboards, monitoring, cases, and
observability integrations.

**Ugence differentiation.** These layers evaluate whether the *observed* trajectory and effect
matched the *authorized* boundary — closing the loop between authorization and reality — whereas
monitoring generally reports that a workflow step *completed*. And they do it without ever becoming
an authority themselves.

**How it enhances ServiceNow workflow capability.** Assessment outcomes and reassessment signals
can be emitted back to ServiceNow as governed records (incidents, cases, evidence), so the system
of record learns whether reality stayed within the approved authority — while the authority
consequence stays owned by RA‑6 and the reconciliation records by Decision Authority.

**Discovery question.** *"After execution, can the platform prove the observed trajectory and
effect stayed within the authorized boundary — and turn a deviation into a governed record and a
change to future authority, without the observer itself becoming an authority?"*

---

## I. Infrastructure Autonomy (Cloud Scaling — advisory / execution split)

The cloud-scaling pair is the clearest in-repo demonstration of the Ugence architectural
principle that **recommendation and execution are separate packages with separate authority
classes** — the same split that separates TAP/ActionGate from Agent Runtime, applied to
infrastructure.

### I1. Cloud Scaling Controller (advisory)

| | |
|---|---|
| **Package** | `packages/capabilities/cloud-scaling-controller` → `ugence-cloud-scaling-controller` |
| **Vocabulary** | `ScalingRecommendation` (`advisory_only = true`, `actuation_performed = false`) |
| **Authority** | Advisory — *no code in the wheel can apply the advice* |

**What it does.** Consumes normalized workload/infrastructure observations and emits explainable
scaling *recommendations* with a full component breakdown (`CloudScalingController.evaluate`).
Authority class ADVISORY, execution capability NONE.

**ServiceNow adjacency / strength.** ITOM, event management, and workflow-driven remediation
recommendations.

**Ugence differentiation.** The recommendation engine is *physically incapable* of acting — the
advice and the actuation live in different wheels, so a recommendation can never silently become
a mutation.

### I2. Cloud Scaling Operations (controlled execution)

| | |
|---|---|
| **Package** | `packages/capabilities/cloud-scaling-operations` → `ugence-cloud-scaling-operations` |
| **Vocabulary** | Modes `DRY_RUN` (default) / `SIMULATION` / `SHADOW` / `LIVE`; requires immutable `ExecutionAuthorization` |
| **Authority** | Controlled execution — *installation alone does not authorize execution* |

**What it does.** The fail-closed actuation layer: in `LIVE` mode, with credentials and an
explicit external `ExecutionAuthorization`, it can patch Kubernetes deployment scale and trigger
ArgoCD syncs (`ControlledScalingExecutor`, `RollbackCoordinator`). The authority chain is
explicit:
`ADVISORY_RECOMMENDATION → POLICY_AND_SAFETY_EVALUATION → HUMAN_OR_EXTERNAL_GOVERNANCE_APPROVAL →
EXECUTION_AUTHORIZATION → READINESS_CHECK → CONTROLLED_EXECUTION → OUTCOME_AND_AUDIT`. A
recommendation, an approval boolean, or a confidence score is *never* sufficient to mutate
infrastructure.

```
ServiceNow current / adjacent           Ugence runtime workflow (scaling)
──────────────────────────────          ─────────────────────────────────
Alert / event rule                      Observations → Controller (advisory recommendation)
        │                                        │
        ▼                                        ▼
Runbook / workflow                      Policy + safety evaluation
        │                                        │
        ▼                                        ▼
Execute remediation                     External ExecutionAuthorization (minted elsewhere)
                                                 │
                                                 ▼
                                        Readiness check → CONTROLLED_EXECUTION (dry_run default)
                                                 │
                                                 ▼
                                        Outcome + audit + rollback coordinator
```

**How it enhances ServiceNow workflow capability.** ServiceNow can host the remediation runbook
and the approval; the operations package guarantees the mutation is gated on an immutable,
externally-minted authorization and defaults to `dry_run` — so autonomous scaling is safe,
auditable, and reversible by construction.

**Discovery question.** *"When AI recommends an infrastructure change, is the actuation gated on
an immutable, externally-minted execution authorization — or can a confidence score alone trigger
the mutation?"*

---

## J. Governance Products (Verticals)

Products do not introduce new authority; they *compose* the kernel and providers into a bounded,
audited business workflow. Both shipped products enforce — in types, services, persistence, and
API permissions — the separation between advisory AI recommendation and binding human decision.

### J1. AI Hiring → Hiring Governance Authority (HGA)

| | |
|---|---|
| **Package** | `packages/products/ai-hiring` → `ugence-ai-hiring` (release class `PACKAGE_READY_FOR_CONTROLLED_PILOT`) |
| **Composes** | `decision-authority` + `governance-provider-framework` + optional `tap` / `actiongate` extras |
| **Authority** | Product composition — *only an authenticated authorized human can create a binding decision* |

**What the package does.** An AI-assisted hiring **governance** product on the Decision Authority
kernel: canonical data contracts, an audited workflow state machine, deterministic evidence
normalization and assessment, decision cases, and governed action-request preparation. It ships
*no* scoring/ranking/fairness model and *no* LLM inference — AI output is advisory; only an
authorized human creates a binding decision. `build_in_memory_platform()`; `version_info()` with
`.production_certified == False`.

**ServiceNow adjacency / strength.** HR workflows, recruiting/ATS integrations, AI governance and
approval.

**Ugence differentiation.** Do **not** position it as recruiting automation, and do not present
graduated AI authority as shipped. The two states must be kept distinct:

**Current package** (`ugence-ai-hiring`, controlled-pilot):

```
Resume / Assessment / Interview / Reference
        ↓
Evidence admission (TAP, optional extra)
        ↓
AI assessment (advisory only)
        ↓
HiringDecisionCase
        ↓
Authorized human binding decision   ← only an authenticated authorized human can bind
```

**Target HGA evolution** (roadmap — not shipped):

```
Enterprise hiring policy
        ↓
Delegated authority level:
   NONE  ·  ADVISORY_ONLY  ·  INTERMEDIATE_AUTONOMY  ·  HUMAN_BINDING_REQUIRED
        ↓
Hiring Governance Authority enforces the permitted level
        ↓
HiringDecisionCase → (ActionGate → ACP → ATS/HRIS) where policy & law permit
        ↓
Runtime Assurance → post-hire calibration
```

> **Current package:** human binding authority only. **Target architecture:** explicit graduated
> AI authority where policy and law permit. The value proposition is that HGA can **bound**
> autonomy — including an explicit `NONE` / human-required state — not that it maximizes it.

**How it enhances ServiceNow workflow capability.** ServiceNow automates the hiring *workflow*;
HGA governs *the level of authority AI is permitted to exercise within it*. Today that level is
"advisory, human binds"; the roadmap adds the graduated levels above, still bounded by policy and
law.

**Discovery question.** *"Can the enterprise precisely define which hiring decisions AI may make,
which it may only recommend, and which require a human authority — with a default of human-binding
today and graduated levels as policy and law permit?"*

### J2. Procurement → Governed Procurement

| | |
|---|---|
| **Package** | `packages/products/procurement` → `ugence-procurement` (maturity `REFERENCE_WORKFLOW_OFFLINE_VERIFIED`) |
| **Composes** | `decision-authority` (+ pydantic); deterministic offline supplier adapter only |
| **Authority** | Product composition — advisory recommendation + human decision gate an exactly-bound action |

**What the package does.** A bounded governance vertical for governed purchase approvals and
authorized supplier actions. It walks a purchase request through a complete audited lifecycle:
`PurchaseRequest → validation → policy assessment → advisory PurchaseRecommendation → HUMAN
PurchaseApproval → governed action request (bound to approved supplier/budget/amount) → neutral
authorization → explicit supplier dispatch → observed outcome → reconciliation → compensation`.
No AI scoring, no autonomous approval, no production connector. Public API:
`build_in_memory_platform`, `ProcurementAPI`, `PurchaseRequest`, `PurchaseApproval`.

**ServiceNow adjacency / strength.** Procurement workflows, approval chains, risk/compliance
cases.

**Ugence differentiation.** The design goal is that AI becomes the binding decision-maker *only
where policy explicitly delegates that decision class* — **graduated** AI authority, not a binary
human-versus-autonomous choice. Keep the current and future authority models distinct:

**Current package** (`ugence-procurement`, reference workflow):

```
PurchaseRequest
        ↓
Deterministic validation → policy assessment
        ↓
Advisory PurchaseRecommendation
        ↓
HUMAN PurchaseApproval          ← binding approval is human; no autonomous approval
        ↓
Governed action request (bound to approved supplier/budget/amount)
        ↓
Neutral authorization → explicit supplier dispatch → observed outcome → reconciliation
```

**Future graduated-authority policy example** (roadmap — not shipped):

```
Low risk  +  < $10K  +  approved supplier  +  no exception
        ↓
AI_BINDING_ALLOWED
High risk  /  > $100K  /  policy exception
        ↓
HUMAN_AUTHORITY_REQUIRED
```

> The `<$10K` autonomous example is a **target graduated-authority policy**, not current package
> behavior — the shipped workflow requires human approval for every binding decision.

**How it enhances ServiceNow workflow capability.** The target model lets the enterprise express,
machine-enforceably, that AI may autonomously approve a low-risk `<$10K` award while a `>$100K`
regulated exception requires a human authority — graduated decision rights ServiceNow approval
chains express only as human routing. Today the shipped package delivers the audited,
exactly-bound *human-approved* path that this graduated model would extend.

**Discovery question.** *"Can the platform express (as a target authority model) that AI may
autonomously approve a low-risk <$10K award while requiring human authority for a >$100K regulated
exception — while shipping the audited human-approved path today?"*

---

# Part II — Overall Positioning

| Enterprise question | ServiceNow strength | Ugence differentiation (package) |
|---|---|---|
| What AI do we have? | Very strong | Do not compete; consume AI inventory |
| Who owns it? | Very strong | Bind runtime decisions to ownership/authority (`decision-authority`) |
| What regulations apply? | Strong | Compile approved constraints (`policy-workflow-compiler`) |
| What is its risk classification? | Strong | Convert classification into executable authority — signed `RiskAuthorizationEnvelope` (Risk Authority spine §D2, on `decision-authority`) |
| Is the agent/model approved? | Strong | Per-request `ModelAuthorizationDecision` for *this* decision (`model-selection`) |
| Can AI make this decision? | Governance / approval workflows | AI decides only under *delegated* authority; it never self-authorizes (`decision-authority`; AI barred as principal) |
| What evidence may it rely on? | Risk/compliance records | Evidence admission at decision time (`tap`; trusted admission RA‑5) |
| What exactly may it do? | Access/tool governance | Exact-payload authorization (`actiongate`) |
| Does prior behavior change permission? | Agent lifecycle monitoring | Trajectory-aware advisory (`storygraph`) + RA‑7 runtime assurance |
| Is the action safe right now? | Operational ecosystem | Independent live clearance (`action-clearance`) |
| Did reality match approval? | Monitoring / cases | RA‑8 execution/effect reconciliation → neutral signal (`decision-authority` owns records) |
| Should the next action still be allowed? | Workflow / case response | RA‑6 authority lifecycle: revoke / supersede / expire / epoch |
| Can we explain the entire causal story? | Linked records / workflow history | Governance Story Graph (proposed, Part III) |

| ServiceNow | Ugence |
|---|---|
| Workflow platform | Runtime governance / authority platform |
| AI inventory | AI decision / execution authority |
| Provider configuration | Per-request Model Authority (`ModelAuthorizationDecision`) |
| Risk register / assessment | Executable `RiskDecision` + signed `RiskAuthorizationEnvelope` (Risk Authority spine §D2) |
| Compliance dashboard | Runtime enforcement + RA‑7/RA‑8 assurance |
| Policy / workflow configuration | Compiled `workflow_ir.v1` / `.v2` constraints |
| Workflow execution | Authorized execution (CER; Agent Runtime H22‑A→D) |
| Audit logs / cases | RA‑8 effect reconciliation → neutral signal; RA‑6 authority lifecycle |
| AI recommendations / approvals | Delegated AI decision authority |
| Linked records / process history | Governance Story Graph (proposed) |

**Core message.** *ServiceNow increasingly governs both AI assets and ServiceNow-native AI
runtime interactions. Ugence differentiates through vendor-neutral, decision-level and
exact-action authority that can span ServiceNow and non-ServiceNow runtimes.*

```
Enterprise Workflow → ServiceNow → Ugence Runtime Governance / Authority
        → Authorized AI Decision and Execution → RA‑7/RA‑8 Assurance + Governance Story Graph
```

---

# Part III — Governance Story Graph (Proposed Causal-Governance Graph)

> **Status.** The **Governance Story Graph** is included here as a *proposed* causal-governance
> module built on the architecture in this document. It is distinct from the shipped
> `ugence-storygraph` **StoryGraph Sequence Risk** analyzer (Part I §G2) and should be validated
> against any existing internal specification before implementation. Naming: *StoryGraph Sequence
> Risk* = real-time dangerous-sequence detection; *Governance Story Graph* = lifecycle causal
> provenance.

## 3.1 Why the Governance Story Graph matters

Enterprise governance often stores evidence, approvals, tasks, incidents, model records,
execution logs and outcomes as *separate* records. That is sufficient for operational
recordkeeping but makes it hard to answer causal questions about an autonomous AI decision: Which
policy applied? Which evidence was admitted? Who or what had authority? Which model was
authorized? What exact action was approved? What actually occurred? Did the outcome change future
authority?

The Governance Story Graph provides a graph-native governance *narrative* that links these
artifacts as explicit nodes and typed causal edges. It complements ServiceNow CMDB/case/workflow
relationships rather than replacing them, and it preserves causality across the AI lifecycle:

```
Prompt → Evidence → DecisionCase → Model/Agent Authority → ActionGate
       → Execution → Runtime Assurance → Outcome → Future Authority
```

## 3.2 Canonical node types

| Node type | Examples | Sourced from package |
|---|---|---|
| Policy / WorkflowIR | Policy version, compiled rule, control requirement (`workflow_ir.v1` / `.v2`) | `policy-workflow-compiler` |
| Evidence | Document, evaluation, attestation, freshness state; trusted admission | `tap`, `risk-authority-evidence-runtime` (RA‑5) |
| DecisionCase | HiringDecisionCase, ProcurementDecisionCase, `RiskDecisionCase` | `decision-authority`, `risk-authority`, products |
| Model Authority | `ModelAuthorizationDecision` (ALLOW/DENY/HOLD/ESCALATE + fallback, expiry) | `model-selection` |
| Machine Authority | `RiskDecision` → signed `RiskAuthorizationEnvelope` (sole signed artifact); `ActionGateDecision` | `risk-authority`, `actiongate` |
| Actor / Model / Agent | Human principal, AI model/version, agent/workforce | `agent-workforce-composer`, `agent-runtime` |
| Action | Canonical proposed/attempted/executed action (CER) | `agent-runtime`, `actiongate` |
| ExecutionReceipt | Attempt, execution, actual side effect | `decision-authority` execution/reconciliation (sole owner) |
| Trajectory / effect assessment | `TrajectoryAssessment` (RA‑7); effect reconciliation (RA‑8); sequence-risk trajectory state | `risk-authority-runtime-assurance`, `risk-authority-execution-assurance`, `storygraph` |
| Outcome | Business outcome, post-hire performance, payment result | products |
| Calibration / Revocation | Authority lifecycle consequence: revoke / supersede / expire / epoch | `risk-authority-status-runtime` (RA‑6), `decision-authority` |

## 3.3 Canonical edge types

| Edge | Meaning |
|---|---|
| `APPLIES_TO` | Policy/rule applies to case, actor, model or action |
| `SUPPORTED_BY` | Decision/control is supported by admitted evidence |
| `EXCLUDES` | Evidence was explicitly excluded from a decision |
| `AUTHORIZED_BY` | Decision/action was authorized by a specific authority artifact |
| `EXECUTED_AS` | Authorized action was executed as a concrete runtime event |
| `RESULTED_IN` | Execution produced an observed outcome/effect |
| `DEVIATED_FROM` | Observed action/effect differed from authorization |
| `SUPERSEDES` | New policy/decision/authority replaces a prior version |
| `REVOKES` | Event/control/decision withdraws previously active authority |
| `CALIBRATES` | Outcome contributes to future rule/threshold/authority calibration |

## 3.4 ServiceNow + Governance Story Graph integration

```
ServiceNow  CMDB / Cases / Risk / Workflow / AI Asset Records
        │
        ├── source IDs / ownership / lifecycle / approvals
        ▼
Ugence Governance Story Graph
        │  policy + evidence + authority
        │  exact runtime actions
        │  effects + reconciliation
        │  causal lineage / trajectory / calibration
        ▼
        └── summarized outcomes / incidents / evidence → ServiceNow
```

## 3.5 High-value queries

- *"Show every action executed under policy version P-17 after evidence source E became stale."*
- *"Why was model M authorized for this customer decision, and which alternatives were rejected?"*
- *"Which exact evidence supported this hiring recommendation, and which fields were excluded?"*
- *"Which prior action caused the trajectory to become ineligible for external disclosure?"*
- *"Which execution deviations resulted in authority revocation?"*
- *"Trace this post-hire calibration proposal back to the original DecisionCase and evidence."*
- *"Show all ServiceNow incidents triggered by runtime authority or reconciliation failures."*

## 3.6 Commercial value

| Value | Governance Story Graph contribution |
|---|---|
| Explainability | End-to-end provenance, not a model-generated narrative alone |
| Auditability | Reconstructs policy → evidence → authority → action → effect |
| Root-cause analysis | Identifies which decision or runtime state caused a downstream deviation |
| Regulatory evidence | Produces causal lineage for consequential AI decisions |
| Cross-case learning | Finds recurring patterns without auto-changing binding policy |
| Calibration | Connects outcomes to controlled policy/model/rubric updates |
| Vendor neutrality | Connects ServiceNow, Microsoft, Salesforce and direct-runtime records in one graph |

**Key differentiation.** ServiceNow links enterprise *records*. The Governance Story Graph links
the causal governance *story* of why an AI decision was allowed, what it did, what happened, and
how that outcome changes future authority.

---

# Part IV — Executive Meeting Playbook

## 4.1 30-second opening

> ServiceNow is strong at governing both the AI estate — what AI exists, who owns it, its risk,
> policy, compliance and lifecycle — and its own ServiceNow-native AI runtime. Ugence adds a
> vendor-neutral layer at the point where the enterprise says: *now let AI make the decision,
> possibly outside a single vendor's runtime.* We govern the evidence it can rely on, whether it
> has delegated authority, which model is authorized, the exact action and payload, whether
> execution is safe now, whether the actual effect matched approval, and how that outcome changes
> future authority. Those controls — including the Risk Authority spine that mints the signed
> authorization envelope, Model Authority, and the RA‑7/RA‑8 assurance layers — are real,
> independently installable packages today (most reference-grade, with production-deployment
> validation still pending). A few things remain on a clearly-labeled roadmap: graduated product
> autonomy, a ServiceNow connector, and the Governance Story Graph.

## 4.2 Partnership framing

```
SYSTEM OF RECORD / WORKFLOW
ServiceNow  ·  AI estate | CMDB | risk | policy | approvals | cases | workflows
        ↓
SYSTEM OF RUNTIME AUTHORITY
Ugence  ·  evidence | decisions | model authority | action authorization
        ·  trajectory | operational clearance | reconciliation | Governance Story Graph
        ↓
SYSTEMS OF ACTION
Agents | Models | MCP | APIs | SaaS | Databases | Enterprise Workflows
```

## 4.3 What not to say

- ❌ *"ServiceNow has no AI governance."* — inaccurate and weakens credibility.
- ❌ *"We replace AI Control Tower."* — unnecessary head-on competition.
- ❌ *"ServiceNow cannot enforce anything."* — too broad; focus on exact-action and
  trajectory-level authority.
- ❌ *"Our AI decides everything autonomously."* — the value is **bounded, delegated** authority,
  including explicit human-required states.
- ❌ *"Governance Story Graph replaces CMDB."* — position it as causal runtime-governance lineage that
  complements ServiceNow records.
- ❌ *"These packages are production-deployment-validated."* — most are reference-grade / offline- or
  CI-verified with **production deployment validation pending**; say *shipped and independently
  verifiable*, not *enterprise-proven*.
- ❌ *"A ServiceNow connector ships today."* — no ServiceNow connector exists in the packages; the
  integrations described are proposed adapters over the vendor-neutral contracts.

## 4.4 Best discovery questions

1. If the enterprise removes the human approver, what becomes the authoritative decision artifact,
   and how does it constrain the downstream action?
2. Can an approval be bound to one exact payload and revalidated immediately before execution?
3. If the decision and authorization are valid but the live environment is unsafe, what
   independently prevents execution?
4. Can a runtime decision distinguish admissible, stale, contradictory and unverifiable evidence
   before the model relies on it?
5. Can ServiceNow-approved policy be exported as machine-enforceable constraints evaluated without
   reinterpreting natural-language policy?
6. Can the platform prove, per invocation, which candidate fields were excluded before a request
   crossed an external-model boundary?
7. Is model choice a configuration decision, or a per-request binding authorization based on
   policy, data, jurisdiction, risk and runtime state?
8. When multiple agents are assembled, can the team inherit no more authority than each approved
   role possesses?
9. When two workflows are composed, what prevents a new permission neither workflow possessed?
10. Can the same enforcement apply to ServiceNow, third-party and custom agents through one
    runtime contract?
11. Can steering be anchored to the exact decision policy and evidence rather than only
    content-safety categories?
12. Can ServiceNow ingest runtime decision receipts, action denials, trajectory deviations and
    reconciliation outcomes as governed records?
13. Can the platform express graduated AI authority as a *target* model (autonomous `<$10K`,
    human-required `>$100K`) while shipping the audited human-approved path today?
14. Can the enterprise define which hiring decisions AI may make, recommend, or must escalate to a
    human?
15. What machine-consumable runtime artifact represents a ServiceNow risk/approval outcome after
    the human workflow completes?
16. Can an auditor traverse one graph from policy and evidence, through the AI decision and exact
    action, to actual effect and the resulting change in future authority?

## 4.5 Vendor-neutral commercial architecture

Ugence core packages remain independent products. ServiceNow is **one integration adapter, not a
required dependency**. The same authority contracts integrate with Microsoft, Salesforce, SAP,
Workday, Oracle, cloud AI platforms, or custom stacks by replacing only the integration adapter
while preserving the governance core.

```
                 Ugence Core Governance Packages
 decision-authority | model-selection | ai-hiring | tap | actiongate
 action-clearance | context-minimization (+ token-accounting-runtime) | storygraph
 policy-workflow-compiler | agent-workforce-composer | agent-runtime | procurement
 risk-authority (RA‑1→RA‑4) + risk-authority-{runtime, evidence, status,
   runtime-assurance, execution-assurance} (RA‑4.5→RA‑8) | cloud-scaling-*
                            │
                  vendor-neutral contracts (governance-contracts)
                            │
      ┌─────────────┬─────────────┬─────────────┬─────────────┐
      ▼             ▼             ▼             ▼             ▼
 ServiceNow     Microsoft     Salesforce       SAP         Custom
  Adapter        Adapter        Adapter       Adapter      Adapter
```

---

# Appendix A — Terminology Updates

| Earlier name | Updated / preferred name | Reason |
|---|---|---|
| Model Selection | **Model Authority** | Shifts the external contract from "best model" recommendation to binding per-request authorization (package remains `ugence-model-selection`) |
| AI-Assisted Hiring | **Hiring Governance Authority** | Positions the module as a decision-governance authority, not recruiting automation (package `ugence-ai-hiring`) |
| Ugence AI Control Plane / Control-Tower-like console | **Runtime Authority Console** | Avoids overlap with ServiceNow AI Control Tower; focuses on runtime decisions/execution |
| ACP (conceptual) | **Action Clearance** | Operational-clearance gate shipped as `ugence-action-clearance` (`CLEAR/HOLD/BLOCK/ESCALATE`) |
| Risk Authority (planned control plane) | **Risk Authority spine (RA‑1→RA‑8)** | No longer planned: shipped as `ugence-risk-authority` (RA‑1→RA‑4) + five composition/runtime distributions (RA‑4.5→RA‑8); sole issuer of the signed `RiskAuthorizationEnvelope` |
| Runtime Assurance (RTA, composed) | **RA‑7 runtime assurance + RA‑8 execution assurance** | Split into two shipped packages; both emit assessments/neutral signals, never authority; RA‑6 owns the authority consequence |
| Static audit narrative | **Governance Story Graph** | Adds causal governance lineage across policy, evidence, authority, execution and outcomes (proposed; distinct from the shipped StoryGraph Sequence Risk analyzer and from RA‑7 Runtime Assurance) |

---

# Appendix B — Master Map: Package ↔ Module ↔ ServiceNow Adjacency

**Status key:** ✅ SHIPPED PACKAGE (independently installable under `symbolu/packages/` on the
default branch) · 🚧 PROPOSED (design/architecture, not a package). All versions and the maturity
notes were verified at SHA `d8dd7abc75…` (Appendix E). *Maturity* names deployment-validation
evidence, not existence: **CI** = `IMPLEMENTED_AND_CI_VERIFIED`, **offline** =
`IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED`, **ref** = REFERENCE-GRADE, **PDV-pending** =
PRODUCTION DEPLOYMENT VALIDATION PENDING. No row below is claimed as live-enterprise-validated.

| Status | `symbolu/packages/…` | Distribution (version) | Conceptual module | Decision vocabulary | Maturity |
|---|---|---|---|---|---|
| ✅ | `governance-contracts` | `ugence-governance-contracts` (0.1.0) | Contract spine | request/result/outcome types | offline · PDV-pending |
| ✅ | `governance-provider-framework` | `ugence-governance-provider-framework` (0.1.0) | Provider mechanics | register/resolve/invoke | offline · PDV-pending |
| ✅ | `tooling/policy-workflow-compiler` | `ugence-policy-workflow-compiler` (0.2.0) | Policy Workflow Compiler | → `workflow_ir.v1` / `.v2` + digest | Alpha · offline · PDV-pending |
| ✅ | `providers/tap` | `ugence-tap-provider` (0.1.0) | TAP (Truth Assurance) | `SUPPORTED/CONSTRAINED/INDETERMINATE` | offline · PDV-pending |
| ✅ | `capabilities/decision-authority` | `ugence-decision-authority` (1.0.0, frozen API) | Binding-Decision Kernel; owns exec/recon records | binding `DecisionOutcome` | frozen/contractual |
| ✅ | `providers/actiongate` | `ugence-actiongate-provider` (0.1.0) | ActionGate (subtractive) | `ActionGateOutcome`: `AUTHORIZED/AUTHORIZED_WITH_CONSTRAINTS/DENIED/INDETERMINATE` | Beta · not prod-certified |
| ✅ | `capabilities/action-clearance` | `ugence-action-clearance` (0.1.0) | ACP / Operational Clearance | `CLEAR/HOLD/BLOCK/ESCALATE` | offline · PDV-pending |
| ✅ | `capabilities/model-selection` | `ugence-model-selection` (0.1.0) | Model Authority | `ModelAuthorizationDecision`: `ALLOW/DENY/HOLD/ESCALATE` + fallback/expiry | offline · synthetic evidence |
| ✅ | `capabilities/llm-steering-controller` | `ugence-llm-steering-controller` (0.1.0) | LLM Steering Controller | `RECOMMENDED` (not executed) | offline · PDV-pending |
| ✅ | `capabilities/context-minimization` | `ugence-context-minimization` (0.2.0) | Context Minimization + CM‑TA1 accounting | `minimize_context` (fail-closed); token-accounting contracts | offline · synthetic |
| ✅ | `integration/context-minimization-token-accounting-runtime` | `ugence-context-minimization-token-accounting-runtime` (0.1.0) | CM × token-accounting × runtime | translate/record/settle (measured H22‑D budget) | offline · PDV-pending |
| ✅ | `capabilities/agent-workforce-composer` | `ugence-agent-workforce-composer` (0.2.1) | Agent Workforce Composer (P2.1 v2 adapter) | `AgentTeamPlan` (zero new authority) | Alpha · not prod-certified |
| ✅ | `capabilities/storygraph` | `ugence-storygraph` (2.0.0) | StoryGraph Sequence Risk (advisory) | `OBSERVE/ESCALATE/UNAVAILABLE` | ref · synthetic |
| ✅ | `runtime/agent-runtime` | `ugence-agent-runtime` (0.7.0) | Agent Runtime / CER (H22‑A→D) | consumes `CLEAR/HOLD/BLOCK/ESCALATE`; provider-attempt telemetry | offline (0.7) / CI (0.6) · in-process only |
| ✅ | `risk_authority` | `ugence-risk-authority` (0.1.0) | Risk Authority spine (RA‑1→RA‑4) | `RiskDecisionCase` → `RiskDecision` → signed `RiskAuthorizationEnvelope` → `ActionGateDecision` | ref (impls behind ports) · PDV-pending |
| ✅ | `integration/risk-authority-runtime` | `ugence-risk-authority-runtime` (0.1.0) | RA‑4.5 governance composition | `GovernedExecutionDecision` (RA + canonical DA + ActionGate) | CI-verified · PDV-pending |
| ✅ | `integration/risk-authority-evidence-runtime` | `ugence-risk-authority-evidence-runtime` (0.1.0) | RA‑5 trusted evidence admission | evidence-derived `ControlResult` (caller `PASS` inert) | ref/production impls · PDV-pending |
| ✅ | `integration/risk-authority-status-runtime` | `ugence-risk-authority-status-runtime` (0.1.0) | RA‑6 authority lifecycle (sole writer) | revoke / supersede / expire / epoch | ref in-memory · PDV-pending |
| ✅ | `integration/risk-authority-runtime-assurance` | `ugence-risk-authority-runtime-assurance` (0.1.0) | RA‑7 runtime/trajectory assurance | `TrajectoryAssessment` `NORMAL/ESCALATED/UNKNOWN` → neutral signal | ref · PDV-pending |
| ✅ | `integration/risk-authority-execution-assurance` | `ugence-risk-authority-execution-assurance` (0.1.0) | RA‑8 execution/effect assurance | effect reconciliation → `AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)` | ref · PDV-pending |
| ✅ | `capabilities/cloud-scaling-controller` | `ugence-cloud-scaling-controller` (0.2.0) | Scaling (advisory) | recommendation (`advisory_only`) | offline · PDV-pending |
| ✅ | `capabilities/cloud-scaling-operations` | `ugence-cloud-scaling-operations` (0.1.0) | Scaling (controlled exec.) | gated `CONTROLLED_EXECUTION` | offline · PDV-pending |
| ✅ | `products/ai-hiring` | `ugence-ai-hiring` (dist 0.1.1 / capability 0.6.0) | Hiring Governance Authority | human-only binding decision | `PACKAGE_READY_FOR_CONTROLLED_PILOT`; `production_certified=False` |
| ✅ | `products/procurement` | `ugence-procurement` (0.1.0) | Governed Procurement | advisory recommendation → human `PurchaseApproval` → governed action; graduated rights are **target** | `REFERENCE_WORKFLOW_OFFLINE_VERIFIED` |
| 🚧 | *(no package)* | — | Governance Story Graph | causal-lineage node/edge schema | PROPOSED (Part III) |
| 🚧 | *(no package)* | — | ServiceNow (and other) integration adapters | policy export / receipt ingestion | PROPOSED |
| 🚧 | *(no package)* | — | Graduated product autonomy (Hiring / Procurement) | delegated AI decision rights | PROPOSED (roadmap) |

> **Note on formerly-planned services.** Several services listed as "planned" in v2.5
> (`authority-registry`, `control-assurance`, `trajectory-control`, `third-party-ai-gateway`,
> `reconciliation`, `risk-escalation`) are now realized as functionality *inside* the shipped Risk
> Authority spine and its RA‑4.5→RA‑8 runtimes (e.g. authority lifecycle in RA‑6, control assurance
> in RA‑5, reconciliation reference in RA‑8) rather than as separately named standalone wheels. A
> production Third-Party AI Gateway and a globally-consistent authority registry remain explicitly
> out of scope of the current reference-grade packages.

---

# Appendix C — Architectural Invariants (why the packages are trustworthy)

These invariants are implemented in code and, in several packages, machine-checked by tests —
they are the technical substance behind the positioning.

1. **Authority never leaks across layers.** Each layer speaks a distinct decision vocabulary
   (Appendix B). An `OBSERVE` is not a `DENY`; an `AUTHORIZED` is not an execution; a `CLEAR` is
   not an authorization; a `TrajectoryAssessment` is not a revocation. StoryGraph's boundary (never
   emits `ALLOW/DENY/AUTHORIZE/CLEAR`) is machine-checked.
2. **Fail-closed by construction.** TAP never promotes uncertainty to `SUPPORTED`; ActionGate
   never promotes it to `AUTHORIZED`; Agent Runtime fails closed to `GOVERNANCE_NOT_CONFIGURED`;
   Context Minimization fails closed when equivalence can't be established; Model Authority `HOLD`s
   on indeterminate evidence rather than authorizing; cloud-scaling defaults to `dry_run`.
3. **AI cannot authorize itself.** `decision-authority`'s `AuthorityType` has no AI member — a
   structural, not merely procedural, guarantee.
4. **One signed machine-authority artifact, additive/subtractive inputs.** The Risk Authority spine
   is the sole issuer of the signed `RiskAuthorizationEnvelope`; its scope can never exceed the
   decision's scope (envelope monotonicity); Decision Authority and ActionGate may veto or tighten
   but never widen or manufacture authority; and RA‑7/RA‑8 emit only assessments and neutral
   reassessment signals — RA‑6 alone effects the authority-lifecycle consequence.
5. **Composition grants nothing.** The provider framework, Agent Workforce Composer, RA‑4.5, and
   both products compose lower layers without creating new authority; each action still requires its
   own authorization. `GovernedExecutionDecision` wraps the envelope but is not a second envelope.
6. **Recommendation and execution are separate packages.** The cloud-scaling controller/operations
   split (and the TAP/ActionGate ↔ Agent Runtime split) physically separate advice from actuation,
   so a recommendation can never silently become a mutation.
7. **Vendor-neutral and independently distributable.** Every package ships its own wheel, prefixed
   `ugence-`, so ServiceNow is one adapter, never a hard dependency. *Compatibility facades are
   per-package, not universal:* several packages preserve a prior namespace via a logic-free
   facade (`decision-authority`, `actiongate`, `storygraph`, `model-selection`, `ai-hiring`,
   `procurement`), while the net-new packages ship none (`policy-workflow-compiler`,
   `agent-workforce-composer`, `agent-runtime`, `context-minimization`, the token-accounting
   runtime, and the entire Risk Authority spine). This claim is verified per package, not asserted
   categorically.

---

# Appendix D — Change Summary (v2.5 → v3.0)

All corrections were verified against the default branch at SHA
`d8dd7abc753238d1e10e5a93d14d9ab054b7ce7e`.

### Corrected stale claims
- **Risk Authority was labeled "planned / not yet a package."** It is now a **shipped, independently
  packaged authority spine** (`ugence-risk-authority`, RA‑1→RA‑4) plus five shipped
  composition/runtime distributions (RA‑4.5→RA‑8). Rewrote §D2, the Part 0 maturity table, the
  dependency diagram, the runtime flow, Appendix B, and the positioning tables accordingly.
- **Model Authority was labeled "near-term / target contract."** `ModelAuthorizationDecision`
  (`ALLOW/DENY/HOLD/ESCALATE`, governed fallback, `decision_id`, `policy_version`, `expires_at`) is
  **shipped** in `ugence-model-selection`. Rewrote §F1 and every "target Model Authority" reference.
- **"Runtime Assurance — composed, not packaged."** Replaced with **two shipped packages**: RA‑7
  runtime/trajectory assurance and RA‑8 execution/effect assurance (§H2).
- **"Every package ships a logic-free legacy-compatibility facade."** Removed as categorical; replaced
  with a **per-package** statement (true for 6 packages, explicitly false for the net-new ones).
- **"No standalone `runtime-assurance` wheel yet"** and the planned `authority-registry` /
  `control-assurance` / `trajectory-control` / `reconciliation` / `risk-escalation` rows — corrected:
  that functionality is realized inside the shipped RA spine and RA‑4.5→RA‑8 runtimes.
- **PWC `workflow_ir`** → clarified as `workflow_ir.v1` (frozen) + additive `workflow_ir.v2`.

### Newly documented packages
- `ugence-risk-authority` 0.1.0 (RA‑1→RA‑4 spine).
- `ugence-risk-authority-runtime` 0.1.0 (RA‑4.5 governance composition).
- `ugence-risk-authority-evidence-runtime` 0.1.0 (RA‑5).
- `ugence-risk-authority-status-runtime` 0.1.0 (RA‑6, authority lifecycle).
- `ugence-risk-authority-runtime-assurance` 0.1.0 (RA‑7).
- `ugence-risk-authority-execution-assurance` 0.1.0 (RA‑8).
- `ugence-context-minimization-token-accounting-runtime` 0.1.0 (CM‑TA1 integration).

### Newly documented package features
- **Model Authority**: `ModelAuthorizationDecision` + `ModelAuthorizationDisposition` +
  `AuthorityReasonCode`; governed fallback, deterministic `decision_id`, policy provenance, expiry;
  model invocation/execution explicitly out of scope.
- **Risk Authority spine**: signed `RiskAuthorizationEnvelope` as the sole signed machine-authority
  artifact; reference implementations behind ports in the leaf vs canonical composition in RA‑4.5;
  additive/subtractive-only Decision Authority and ActionGate; RA‑6 as sole authority-lifecycle
  writer; RA‑7/RA‑8 neutral reassessment signals.
- **Agent Runtime**: H22‑A bounded advancement; H22‑B deterministic SWRR scheduling; H22‑C durable
  recovery/checkpointing/trace/failure+cancellation; H22‑D bounded in-process concurrency, resource
  claims, shared budgets, separately-governed compensation; 0.7 provider-attempt telemetry.
- **Context Minimization**: v0.2 CM‑TA1 token-accounting contracts (reduction vs complete-request
  estimate vs provider-reported usage); token-accounting runtime with measured H22‑D budget
  settlement.
- **PWC**: `workflow_ir.v2` semantic enrichment. **AWC**: P2.1 `workflow_ir.v2` compatibility adapter.

### Maturity changes
- Introduced the six-level maturity ladder (SHIPPED PACKAGE · IMPLEMENTED_AND_CI_VERIFIED ·
  IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED · REFERENCE-GRADE · PRODUCTION DEPLOYMENT VALIDATION
  PENDING · PROPOSED).
- Risk Authority: planned → **shipped, reference-grade, PDV-pending**.
- Model Authority: near-term → **shipped (offline-verified, synthetic evidence)**.
- Runtime Assurance: composed → **two shipped reference-grade packages**.
- Agent Runtime: recorded 0.7.0 `IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` (0.6.0 CI-verified).

### Claims deliberately *not* made
- No claim that any package is production-deployment-validated or live-enterprise-proven.
- No claim that a **ServiceNow connector** ships (none exists in the packages).
- No claim of distributed scheduling, exactly-once external effects, cluster safety or production
  readiness for Agent Runtime.
- No claim that Context Minimization has a provider SDK, real provider adapters, durable accounting
  persistence, pricing authority, or invoice reconciliation.
- RA‑7 is **not** described as a second authority; RA‑7/RA‑8 emit signals, RA‑6 owns the consequence,
  Decision Authority owns execution/reconciliation records.
- StoryGraph Sequence Risk is kept distinct from RA‑7 Runtime Assurance and from the proposed
  Governance Story Graph.
- ServiceNow capability statements were preserved as written (this pass is an Ugence package-state
  update; ServiceNow claims were not independently re-verified).

---

# Appendix E — Package-to-Document Traceability

**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
**Verification SHA:** `d8dd7abc753238d1e10e5a93d14d9ab054b7ce7e` (2026-08-11)

Versions are resolved from each package's `version.py` / `__init__.py` at the SHA above.

| Repository path | Distribution | Version | Document section(s) |
|---|---|---|---|
| `packages/governance-contracts` | `ugence-governance-contracts` | 0.1.0 | §A1; App. B |
| `packages/governance-provider-framework` | `ugence-governance-provider-framework` | 0.1.0 | §A2; App. B |
| `packages/tooling/policy-workflow-compiler` | `ugence-policy-workflow-compiler` | 0.2.0 | §B1; App. B |
| `packages/providers/tap` | `ugence-tap-provider` | 0.1.0 | §C1; App. B |
| `packages/capabilities/decision-authority` | `ugence-decision-authority` | 1.0.0 | §D1; App. B/C |
| `packages/risk_authority` | `ugence-risk-authority` | 0.1.0 | §D2 (RA‑1→RA‑4); App. B/C |
| `packages/integration/risk-authority-runtime` | `ugence-risk-authority-runtime` | 0.1.0 | §D2 (RA‑4.5); App. B |
| `packages/integration/risk-authority-evidence-runtime` | `ugence-risk-authority-evidence-runtime` | 0.1.0 | §D2 (RA‑5); App. B |
| `packages/integration/risk-authority-status-runtime` | `ugence-risk-authority-status-runtime` | 0.1.0 | §D2/§H2 (RA‑6); App. B |
| `packages/integration/risk-authority-runtime-assurance` | `ugence-risk-authority-runtime-assurance` | 0.1.0 | §H2 (RA‑7); App. B |
| `packages/integration/risk-authority-execution-assurance` | `ugence-risk-authority-execution-assurance` | 0.1.0 | §H2 (RA‑8); App. B |
| `packages/providers/actiongate` | `ugence-actiongate-provider` | 0.1.0 | §E1; App. B/C |
| `packages/capabilities/action-clearance` | `ugence-action-clearance` | 0.1.0 | §E2; App. B |
| `packages/capabilities/model-selection` | `ugence-model-selection` | 0.1.0 | §F1; App. B |
| `packages/capabilities/llm-steering-controller` | `ugence-llm-steering-controller` | 0.1.0 | §F2; App. B |
| `packages/capabilities/context-minimization` | `ugence-context-minimization` | 0.2.0 | §F3; App. B |
| `packages/integration/context-minimization-token-accounting-runtime` | `ugence-context-minimization-token-accounting-runtime` | 0.1.0 | §F3; App. B |
| `packages/capabilities/agent-workforce-composer` | `ugence-agent-workforce-composer` | 0.2.1 | §G1; App. B |
| `packages/capabilities/storygraph` | `ugence-storygraph` | 2.0.0 | §G2; App. B/C |
| `packages/runtime/agent-runtime` | `ugence-agent-runtime` | 0.7.0 | §H1; App. B |
| `packages/capabilities/cloud-scaling-controller` | `ugence-cloud-scaling-controller` | 0.2.0 | §I1; App. B |
| `packages/capabilities/cloud-scaling-operations` | `ugence-cloud-scaling-operations` | 0.1.0 | §I2; App. B |
| `packages/products/ai-hiring` | `ugence-ai-hiring` | dist 0.1.1 / capability 0.6.0 | §J1; App. B |
| `packages/products/procurement` | `ugence-procurement` | 0.1.0 | §J2; App. B |

> **Evidence / maturity ambiguity noted during verification.**
> - `ugence-agent-runtime` README prose is stale at 0.5.0 while the authoritative version
>   (`version.py`) and CHANGELOG are 0.7.0; this document uses **0.7.0**.
> - `ugence-agent-workforce-composer` README header bullet is stale at 0.2.0 while `version.py` is
>   0.2.1; this document uses **0.2.1**.
> - `ugence-ai-hiring` carries two version numbers — distribution `0.1.1` and capability-maturity
>   `0.6.0` (H0–H6); both are shown.
> - The five RA integration runtimes carry no CHANGELOG and reference architecture specs
>   (`docs/architecture/…`) that live at the repo root outside the package directories; maturity was
>   taken from each README's own "Maturity (no overclaim)" section.
> - RA‑5 has no single "Status:" banner; its maturity is expressed as a reference-vs-production table
>   plus a scope-negative statement.

---

# Final Positioning Summary

ServiceNow is the **System of Record** and enterprise workflow platform, and increasingly governs
its own ServiceNow-native AI runtime. Ugence is a **vendor-neutral System of Runtime AI
Authority** — decision-level and exact-action authority that can span ServiceNow *and*
non-ServiceNow runtimes — delivered today as a set of independent, offline-verifiable packages
under `symbolu/packages/`. As of this v3.0 edition that set **includes the full Risk Authority
spine** (RA‑1→RA‑4 leaf plus the RA‑4.5→RA‑8 composition/runtime distributions that issue the
signed `RiskAuthorizationEnvelope`, admit trusted evidence, own the authority lifecycle, and run
trajectory/effect assurance), **shipped Model Authority** (`ModelAuthorizationDecision`), and the
**H22‑A→D Agent Runtime**. These packages are shipped and independently verifiable, but most are
reference-grade with **production deployment validation still pending**; graduated product
autonomy, a ServiceNow connector, and the Governance Story Graph remain on a clearly-labeled
roadmap. The integration opportunity is to convert approved governance states into enforceable
authority at the exact point an AI model, agent, or workflow is about to decide or act.

This framing preserves ServiceNow's strengths, gives Ugence a clear execution-time category, and
keeps every shipped Ugence package independently deployable with Microsoft, Salesforce, SAP,
Workday, Oracle, or a custom stack if a ServiceNow partnership is not pursued.

> **ServiceNow answers: "How should work flow?"**
> **Ugence answers: "Should this AI action be allowed to execute right now?"**
