# Ugence + ServiceNow — Runtime AI Governance Portfolio

## Package-Grounded Differentiation & Workflow Architecture Comparison

**Version:** 2.2 (Package-Grounded Edition)
**Supersedes:** v2.1 partner-facing positioning document and the v2.0 workflow-comparison draft
**Scope:** Maps every conceptual Ugence module to the concrete distributable package that
implements it under `symbolu/packages/`, and states, module-by-module, how each package
*differentiates from and enhances* ServiceNow workflow capabilities.

> **ServiceNow can remain the system of record and enterprise workflow platform.
> Ugence becomes the system of runtime AI authority.**

Prepared as a partner-facing architecture and positioning document for evaluating how the
Ugence packages complement ServiceNow AI Control Tower, AI Risk & Compliance, Flow Designer,
agentic AI and enterprise operations capabilities — without competing head-on with them.

---

## Executive Brief

This document intentionally avoids the claim that ServiceNow lacks AI governance. ServiceNow
is already strong in AI asset inventory, lifecycle governance, risk and compliance workflows,
approval playbooks, identity/access context, workflow automation and an expanding agentic AI
platform.

The differentiation is narrower and more important: **Ugence focuses on the execution-time
decision boundary when AI is expected not merely to recommend, but to decide and act.**

> What happens when the enterprise progresses from AI *recommending* a decision to AI
> *actually making and executing* that decision?

ServiceNow has substantial governance around the AI asset and its lifecycle. Ugence focuses on
the individual decision, the exact action, the prior trajectory, live execution conditions, and
the observed real-world effect. This distinction becomes most valuable as human approval is
reduced or removed.

What makes this edition different from the earlier positioning drafts is that **each module is
now anchored to a real, independently distributable package** in the `symbolu/packages/` tree,
with its actual public API, decision vocabulary, and machine-checked authority boundary. The
positioning is therefore not aspirational marketing — it is a description of code that already
exists, is offline-verifiable, and ships with a stable public contract.

**Positioning rule** — for every module, use the framing:

> *"ServiceNow has an adjacent capability; here is the deeper execution-time problem the Ugence
> package solves when AI itself is expected to make or execute the decision."*

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
 │   authorizing princ.) │              │                  │ storygraph (seq-risk)    │
 └───────────────────────┘              │                  │ agent-workforce-composer │
     │                                  │                  │ cloud-scaling-controller │
     │                                  ▼                  │ cloud-scaling-operations │
     │                   ┌───────────────────────────┐     └──────────────────────────┘
     └──────────────────▶│ governance-provider-      │                 │
                         │ framework (register/       │   Runtime        ▼
                         │ resolve/invoke; NO         │ ┌──────────────────────────┐
                         │ authority)                 │ │ agent-runtime (execution │
                         └───────────────────────────┘ │ coordination kernel)     │
                                     │                  └──────────────────────────┘
                                     ▼                             Tooling
                         ┌───────────────────────────┐ ┌──────────────────────────┐
                         │ governance-contracts      │ │ policy-workflow-compiler │
                         │ (neutral vocabulary leaf; │ │ (compile-time; produces  │
                         │  stdlib only)             │ │  workflow_ir)            │
                         └───────────────────────────┘ └──────────────────────────┘
```

**Dependency layering (bottom → top):** `governance-contracts` (stdlib leaf) →
`governance-provider-framework` → providers (`actiongate`, `tap`) and the kernel
(`decision-authority`) → products (`ai-hiring`, `procurement`). The capability leaves
(`action-clearance`, `context-minimization`, `model-selection`, `llm-steering-controller`,
`storygraph`, `agent-runtime`) are stdlib-only or pydantic-only and depend on *no* other Ugence
package — they are individually installable and vendor-neutral. Every distribution is prefixed
`ugence-`; every module ships a logic-free legacy-compatibility facade that preserves object
identity, so adoption is non-breaking.

### Overall runtime architecture

```
Enterprise Platform  (ServiceNow / Microsoft / Salesforce / SAP / Workday / Oracle)
        │
        ▼
Workflow  ·  Approvals  ·  CMDB  ·  AI Inventory  ·  Human Processes
        │
        ▼
════════════════════════════════════════════════════════════
   UGENCE RUNTIME GOVERNANCE / AUTHORITY  (symbolu/packages)
════════════════════════════════════════════════════════════
   Policy Workflow Compiler   → deterministic WorkflowIR
        ▼
   Evidence (TAP)             → SUPPORTED / CONSTRAINED / INDETERMINATE
        ▼
   Risk / Decision Authority  → binding DecisionCase (AI cannot self-authorize)
        ▼
   Model Authority / Agent Eligibility → ALLOW / DENY / HOLD / ESCALATE
        ▼
   ActionGate                 → AUTHORIZED / DENIED / INDETERMINATE (exact payload)
        ▼
   Sequence Risk (StoryGraph) → OBSERVE / ESCALATE (advisory)
        ▼
   Operational Clearance (ACP / Action Clearance) → CLEAR / HOLD / BLOCK / ESCALATE
        ▼
   Authorized Execution (Agent Runtime CER)
        ▼
   Runtime Assurance + Reconciliation
        ▼
   Story Graph / Calibration / Revocation
```

### Governance verb vocabularies (the differentiator ServiceNow's generic approve/reject lacks)

Each layer speaks a **distinct, bounded decision vocabulary**, so authority cannot silently leak
across layers. This is a core differentiation: an "approval" in one layer is not an
authorization, a clearance, or an execution in another.

| Package / layer | Decision verbs | Authority class |
|---|---|---|
| `tap` (assertion evidence) | `SUPPORTED` / `CONSTRAINED` / `INDETERMINATE` | Advisory (assessment) |
| `storygraph` (sequence risk) | `OBSERVE` / `ESCALATE` / `UNAVAILABLE` | Advisory / evidentiary |
| `model-selection` (Model Authority) | selection **or** `NO_ELIGIBLE_MODEL` (abstain) | Eligibility + selection |
| `llm-steering-controller` | `RECOMMENDED` (execution_status = `NOT_EXECUTED`) | Advisory routing |
| `cloud-scaling-controller` | scaling recommendation (`advisory_only = true`) | Advisory |
| `decision-authority` | binding `DecisionOutcome` (human/policy principal only) | Binding decision |
| `actiongate` (exact action) | `AUTHORIZED` / `DENIED` / `INDETERMINATE` | Authorization |
| `action-clearance` (ACP) | `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` | Operational clearance |
| `agent-runtime` (execution) | consumes `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` | Execution coordination |
| `cloud-scaling-operations` | gated `CONTROLLED_EXECUTION` (needs `ExecutionAuthorization`) | Controlled execution |

**Fail-closed everywhere.** Uncertainty or infrastructure failure is *never* promoted to a
favorable verdict: TAP never promotes uncertainty to `SUPPORTED`, ActionGate never promotes it
to `AUTHORIZED`, and the Agent Runtime fails closed to `GOVERNANCE_NOT_CONFIGURED` if no
governance boundary is wired. ServiceNow workflows fail *open* by default (a step either runs or
errors); the Ugence packages fail *safe* by construction.

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
| **Package** | `packages/tooling/policy-workflow-compiler` → `ugence-policy-workflow-compiler` |
| **Vocabulary** | Compiles policy pack → `workflow_ir` (+ assurance manifest, audit schema, digest) |
| **Authority** | None — compile-time tooling |

**What the package does.** Deterministic tooling that compiles a reviewed, structured governance
policy pack into a governed-workflow artifact plus an assurance package: a `workflow_ir` (frozen
`workflow_ir.v1` + additive `workflow_ir.v2` with node semantics, capability requirements, typed
data contracts, and authority/human-review classification), an assurance manifest and test
scenarios, an audit schema, structural diffs, human-approval records, and a content-addressed
compiled package. Public API: `GovernedWorkflowCompiler.compile(pack, approval)` →
`.logical_digest` + `.compiled_package`; `validate_policy_pack`; `verify_compiled_package`.

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

**How it enhances ServiceNow workflow capability.** Policy approved *inside ServiceNow* can be
exported and compiled once into deterministic, digest-addressed constraints that every
downstream runtime control evaluates identically — eliminating the risk that an LLM
re-interprets the same policy differently on each invocation. ServiceNow owns the policy record;
PWC compiles its approved meaning.

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

**Ugence differentiation.** TAP is not primarily content moderation. It governs whether the
*factual basis* used in this individual decision is admissible and sufficient — provenance,
subject match, freshness, contradiction — before the model is allowed to rely on it.

```
ServiceNow current / adjacent           Ugence runtime workflow (TAP)
──────────────────────────────          ─────────────────────────────
AI / workflow receives available        Evidence / claim
enterprise content                              │
        │                                        ▼
        ▼                               Provenance + subject + freshness + contradiction
Platform guardrails / security                   │
        │                                        ▼
        ▼                               ADMITTED / CONSTRAINED / INDETERMINATE
AI processing                                    │
                                                 ▼
                                        Evidence snapshot → Decision Authority
```

> AI claim: *"Vendor X should win because its certification is current."* → TAP checks: source
> exists? belongs to Vendor X? still valid? authorized source? contradictory record? →
> `SUPPORTED` / `CONSTRAINED` / `INDETERMINATE`. The decision engine cannot overcome missing
> evidence merely because the model is confident.

**How it enhances ServiceNow workflow capability.** A ServiceNow decision workflow can call TAP
to gate the *evidence* an autonomous step relies on, so a confident-but-unsupported model claim
never advances the workflow. ServiceNow governs the AI system; TAP governs whether the evidence
used in *this* decision is admissible.

**Discovery question.** *"Can a runtime AI decision distinguish admissible, stale, contradictory
and unverifiable evidence before the model is allowed to rely on it?"*

---

## D. Decision & Authority Kernel

### D1. Decision Authority (AI Decision Authority / Risk Authority kernel)

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

**Ugence differentiation.** Ugence governs *whether AI itself has delegated authority* to make a
consequential decision, and creates an authoritative **DecisionCase** that subsequently
constrains runtime execution.

```
DecisionCase
  ├─ admitted evidence          ├─ decision
  ├─ excluded evidence          ├─ confidence boundaries
  ├─ policy / rubric version    ├─ authority basis
  ├─ model identity             ├─ conditions
  ├─ assessment / reasoning     └─ resulting authorization
```

This is **AI Decision Authority**, not AI recommendation governance. When Decision Authority
consumes upstream policy/risk outputs, it becomes the **Risk Authority / executable GRC** layer:
it converts an approved ServiceNow risk/approval outcome into a binding `RiskDecisionCase` and
authorization envelope that ActionGate, sequence-risk and clearance controls then enforce.

**How it enhances ServiceNow workflow capability.** When an enterprise removes the human
approver, Decision Authority supplies the *authoritative decision artifact* ServiceNow lacks at
that point — an immutable record that captures which evidence was admitted, which authority
basis applied, and what downstream authorization it produced — while structurally guaranteeing
that AI never authorizes itself. ServiceNow remains the system of record; Decision Authority
produces the machine-consumable decision object that record refers to.

**Discovery question.** *"If an enterprise removes the human approver and allows an AI to make a
consequential decision, what becomes the authoritative decision artifact in ServiceNow, and how
does that artifact constrain the downstream action?"*

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

### F1. Model Selection → Model Authority

| | |
|---|---|
| **Package** | `packages/capabilities/model-selection` → `ugence-model-selection` |
| **Vocabulary** | Two-stage `ExecutionGate` (eligibility) → `ModelPolicy` (ranking) → selection **or** `NO_ELIGIBLE_MODEL` |
| **Authority** | Per-request eligibility + selection; no invocation, no fallback execution |

**What the package does.** The deterministic Model Selection leaf. `ExecutionGate` applies
mandatory eligibility constraints fail-closed (approved-candidate membership, privacy/
jurisdiction/residency, capability/modality/tool-use, context-window sufficiency, stale-evidence
handling) and **never ranks**; `select(...)` then applies policy-weighted scoring over *only*
the eligible set, with deterministic tie-breaking, returning a `Selection` or abstaining with
`NO_ELIGIBLE_MODEL`. There is **no silent fallback** to a prohibited model.

**ServiceNow adjacency / strength.** AI/model inventory, approved providers and connections,
AI Control Tower governance.

**Ugence differentiation.** Do not pitch model inventory. The differentiator is **per-request
model authority**: the same model may be eligible for one request and prohibited for another at
the same moment.

```
ServiceNow current / adjacent           Ugence runtime workflow (Model Authority)
──────────────────────────────          ─────────────────────────────────────────
Admin / AI steward                      ServiceNow workflow / AI agent
        │                                        │
        ▼                                        ▼
Approve providers                       Model Authority: evaluate request + policy +
        │                               jurisdiction + data class + runtime health +
        ▼                               cost + security + capability
Configure default model                          │
        │                                        ▼
        ▼                               ExecutionGate → eligible set → ModelPolicy rank
Configure fallback                               │
        │                                        ▼
        ▼                               ALLOW / DENY / HOLD / ESCALATE
Now Assist / AI Agent                            │
                                                 ▼
                                        Authorized model + reason codes + governed fallback
```

> General task → external lower-cost model may be eligible. Restricted customer data → private
> deployment only. High-impact financial decision → model must satisfy evaluation/version
> requirements.

**How it enhances ServiceNow workflow capability.** ServiceNow configures *which models the
enterprise may use*; Model Authority determines *which eligible model is authorized for this
specific request*, with reason codes and a governed fallback — turning a static configuration
into a per-request binding authorization.

**Discovery question.** *"Does model choice remain a configuration decision, or can the platform
issue a per-request binding authorization based on policy, data, jurisdiction, risk and runtime
state?"*

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
| **Package** | `packages/capabilities/context-minimization` → `ugence-context-minimization` |
| **Vocabulary** | `minimize_context(...)` (oracle-verified) / `structural_minimize(...)`; exposes `surviving_ids`, `equivalence_status` |
| **Authority** | None — deterministic **extractive** reducer, fails closed on non-equivalence |

**What the package does.** A deterministic, domain-neutral **extractive** context reducer. Given
an already-assembled context it removes units by omission while preserving a caller-defined
deterministic equivalence condition (a neutral `InvarianceOracle` the caller injects), and
**fails closed** whenever equivalence cannot be established. It never rewrites, paraphrases, or
summarizes, and creates no authority.

**ServiceNow adjacency / strength.** Security/privacy/governance controls, data access
governance, third-party AI configuration.

**Ugence differentiation.** Make data minimization itself *part of the authorization evidence*:
only the data required, authorized, and permitted for the specific decision crosses the AI
boundary.

```
AI needs:        customer eligibility decision
Available:       54 attributes
Policy permits:  7 attributes
Decision needs:  4 attributes
        ↓
Context Minimization  (extractive, equivalence-preserving, fail-closed)
        ↓
Only 4 attributes leave the boundary
+ input/output hashes + removed classes + purpose + destination
```

**How it enhances ServiceNow workflow capability.** Instead of merely governing *whether* an
external model may be used, it governs *exactly what information* the model is allowed to see for
this decision — and emits a per-invocation receipt proving which candidate fields were excluded
before the request crossed the external-model boundary. Data minimization becomes a measurable
compliance control at the AI trust boundary.

**Discovery question.** *"Can the platform prove, per invocation, which candidate fields were
excluded before a request crossed an external-model boundary?"*

---

## G. Workforce & Sequence Governance

### G1. Agent Workforce Composer (AWC)

| | |
|---|---|
| **Package** | `packages/capabilities/agent-workforce-composer` → `ugence-agent-workforce-composer` |
| **Vocabulary** | `AgentTeamPlan`; composition result `EXACT_OPTIMUM` / `NO_FEASIBLE_TEAM` / `SEARCH_SPACE_EXCEEDED` |
| **Authority** | None — planning only; *an eligible plan is a proposal, never a grant* |

**What the package does.** A deterministic, offline *planning* capability. It adapts a compiled
`workflow_ir` into role requirements, computes hard-constraint agent eligibility
(`AgentEligibilityGate`), ranks eligible agents, composes a bounded exact multi-role team,
proposes least-privilege permission bounds (`PermissionBoundProposal`), and orders fallbacks —
producing an immutable **`AgentTeamPlan`**. It grants nothing, authorizes nothing, schedules
nothing, executes nothing.

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

### G2. StoryGraph — Sequence-Risk Analyzer

| | |
|---|---|
| **Package** | `packages/capabilities/storygraph` → `ugence-storygraph` (v2.0.0) |
| **Vocabulary** | `OBSERVE` / `ESCALATE` / `UNAVAILABLE` (advisory, `ADVISORY` effect ceiling) |
| **Authority** | Advisory / evidentiary — *never* emits `ALLOW`/`DENY`/`AUTHORIZE`/`CLEAR` (machine-checked) |

> **Note.** The `ugence-storygraph` package is the shipped **sequence-risk analyzer**. The
> broader "Story Graph" *causal-governance graph* described in Part III is a distinct proposed
> module; this section covers the implemented package, Part III covers the proposed graph.

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

**Discovery question.** *"Does prior behavior change permission — can the platform flag when a
sequence of individually-approved actions assembles a prohibited capability?"*

---

## H. Runtime Execution

### H1. Agent Runtime / Canonical Execution Request (CER)

| | |
|---|---|
| **Package** | `packages/runtime/agent-runtime` → `ugence-agent-runtime` |
| **Vocabulary** | Consumes governance dispositions `CLEAR` / `HOLD` / `BLOCK` / `ESCALATE` |
| **Authority** | Execution coordination — *creates no authority*; fails closed if governance unconfigured |

**What the package does.** A domain-neutral execution-coordination kernel: it drives task and
workflow lifecycle, invokes providers/tools, and applies retry, timeout, cancellation,
checkpointing, and durable recovery. Before any *consequential* transition it builds an immutable
proposal and asks an injected `GovernanceHook` whether that exact proposal may proceed — and
obeys the answer. The default `UnconfiguredGovernanceHook` **fails closed** with
`GOVERNANCE_NOT_CONFIGURED`; `CLEAR` continues only if the result is bound to the exact proposal
by fingerprint + reference and not expired. Public API: `create_runtime`, `WorkflowDefinition`,
`TaskDefinition`.

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

**Ugence differentiation.** Do **not** position it as recruiting automation. HGA is a governance
authority that can explicitly set AI decision authority to **NONE**, a limited intermediate
level, or another policy-permitted level. Final hiring remains human where required by policy or
law.

```
Resume / Assessment / Interview / Reference
        ↓
Evidence Admission (TAP)
        ↓
Hiring Governance Authority  — rubric + policy + fairness + delegated authority
        ↓
HiringDecisionCase  (+ delegated authority level)
        ↓
ActionGate → Action Clearance (ACP) → ATS / HRIS
        ↓
Runtime Assurance → Post-Hire Calibration
```

**How it enhances ServiceNow workflow capability.** ServiceNow automates the hiring *workflow*;
HGA governs *the level of authority AI is permitted to exercise within it* — demonstrating that
Ugence can **bound** autonomy rather than simply maximize it.

**Discovery question.** *"Can the enterprise precisely define which hiring decisions AI may make,
which it may only recommend, and which require a human authority?"*

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

**Ugence differentiation.** Ugence supports AI becoming the binding decision-maker *only where
policy explicitly delegates that decision class* — **graduated** AI authority, not a binary
human-versus-autonomous choice.

```
Supplier evidence
        ↓  TAP
WorkflowIR (from PWC)
        ↓
AI decision engine  →  Risk / Decision Authority
        ↓
Delegated AI decision  OR  human authority required   (by amount / risk / exception)
        ↓
ActionGate → Action Clearance (ACP) → PO / contract action
        ↓
Reconciliation
```

**How it enhances ServiceNow workflow capability.** It lets the enterprise express, machine-
enforceably, that AI may autonomously approve a low-risk `<$10K` award while a `>$100K` regulated
exception still requires a human authority — graduated decision rights ServiceNow approval chains
express only as human routing.

**Discovery question.** *"Can the platform express that AI may autonomously approve a low-risk
<$10K award while requiring human authority for a >$100K regulated exception?"*

---

# Part II — Overall Positioning

| Enterprise question | ServiceNow strength | Ugence differentiation (package) |
|---|---|---|
| What AI do we have? | Very strong | Do not compete; consume AI inventory |
| Who owns it? | Very strong | Bind runtime decisions to ownership/authority (`decision-authority`) |
| What regulations apply? | Strong | Compile approved constraints (`policy-workflow-compiler`) |
| What is its risk classification? | Strong | Convert classification into executable constraints (`decision-authority`) |
| Is the agent/model approved? | Strong | Per-request eligibility for *this* decision (`model-selection`) |
| Can AI make this decision? | Governance / approval workflows | Delegated machine authority (`decision-authority`; AI barred as principal) |
| What evidence may it rely on? | Risk/compliance records | Evidence admission at decision time (`tap`) |
| What exactly may it do? | Access/tool governance | Exact-payload authorization (`actiongate`) |
| Does prior behavior change permission? | Agent lifecycle monitoring | Trajectory-aware advisory (`storygraph`) |
| Is the action safe right now? | Operational ecosystem | Independent live clearance (`action-clearance`) |
| Did reality match approval? | Monitoring / cases | Execution receipt + reconciliation (`decision-authority` / `agent-runtime`) |
| Should the next action still be allowed? | Workflow / case response | Closed-loop revoke / constrain / continue |
| Can we explain the entire causal story? | Linked records / workflow history | Causal Story Graph (Part III) |

| ServiceNow | Ugence |
|---|---|
| Workflow platform | Runtime governance / authority platform |
| AI inventory | AI decision / execution authority |
| Provider configuration | Per-request Model Authority |
| Risk register / assessment | Executable `RiskDecision` + authorization envelope |
| Compliance dashboard | Runtime enforcement and reconciliation |
| Policy / workflow configuration | Compiled `workflow_ir` constraints |
| Workflow execution | Authorized execution (CER) |
| Audit logs / cases | Execution receipt + closed-loop reconciliation |
| AI recommendations / approvals | Delegated AI decision authority |
| Linked records / process history | Causal Story Graph |

**Core message.** *ServiceNow manages enterprise workflows. Ugence governs AI execution within
those workflows.*

```
Enterprise Workflow → ServiceNow → Ugence Runtime Governance / Authority
        → Authorized AI Decision and Execution → Runtime Assurance + Story Graph
```

---

# Part III — Story Graph (Proposed Causal-Governance Graph)

> **Status.** Story Graph is included here as a *proposed* causal-governance module built on the
> architecture in this document. It is distinct from the shipped `ugence-storygraph`
> sequence-risk analyzer (Part I §G2) and should be validated against any existing internal Story
> Graph specification before implementation.

## 3.1 Why Story Graph matters

Enterprise governance often stores evidence, approvals, tasks, incidents, model records,
execution logs and outcomes as *separate* records. That is sufficient for operational
recordkeeping but makes it hard to answer causal questions about an autonomous AI decision: Which
policy applied? Which evidence was admitted? Who or what had authority? Which model was
authorized? What exact action was approved? What actually occurred? Did the outcome change future
authority?

Story Graph provides a graph-native governance *narrative* that links these artifacts as explicit
nodes and typed causal edges. It complements ServiceNow CMDB/case/workflow relationships rather
than replacing them, and it preserves causality across the AI lifecycle:

```
Prompt → Evidence → DecisionCase → Model/Agent Authority → ActionGate
       → Execution → Runtime Assurance → Outcome → Future Authority
```

## 3.2 Canonical node types

| Node type | Examples | Sourced from package |
|---|---|---|
| Policy / WorkflowIR | Policy version, compiled rule, control requirement | `policy-workflow-compiler` |
| Evidence | Document, evaluation, attestation, freshness state | `tap` |
| DecisionCase | RiskDecisionCase, HiringDecisionCase, ProcurementDecisionCase | `decision-authority`, products |
| Authority | RiskDecision, ModelAuthorizationDecision, ActionAuthorization | `decision-authority`, `model-selection`, `actiongate` |
| Actor / Model / Agent | Human principal, AI model/version, agent/workforce | `agent-workforce-composer`, `agent-runtime` |
| Action | Canonical proposed/attempted/executed action (CER) | `agent-runtime`, `actiongate` |
| ExecutionReceipt | Attempt, execution, actual side effect | `decision-authority` execution/reconciliation |
| Trajectory state | Accumulated history, data exposure, commitments | `storygraph` |
| Outcome | Business outcome, post-hire performance, payment result | products |
| Calibration / Revocation | Authority adjustment, policy proposal, suspension | `decision-authority` |

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

## 3.4 ServiceNow + Story Graph integration

```
ServiceNow  CMDB / Cases / Risk / Workflow / AI Asset Records
        │
        ├── source IDs / ownership / lifecycle / approvals
        ▼
Ugence Story Graph
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

| Value | Story Graph contribution |
|---|---|
| Explainability | End-to-end provenance, not a model-generated narrative alone |
| Auditability | Reconstructs policy → evidence → authority → action → effect |
| Root-cause analysis | Identifies which decision or runtime state caused a downstream deviation |
| Regulatory evidence | Produces causal lineage for consequential AI decisions |
| Cross-case learning | Finds recurring patterns without auto-changing binding policy |
| Calibration | Connects outcomes to controlled policy/model/rubric updates |
| Vendor neutrality | Connects ServiceNow, Microsoft, Salesforce and direct-runtime records in one graph |

**Key differentiation.** ServiceNow links enterprise *records*. Story Graph links the causal
governance *story* of why an AI decision was allowed, what it did, what happened, and how that
outcome changes future authority — without embedding business identifiers in model weights.

---

# Part IV — Executive Meeting Playbook

## 4.1 30-second opening

> ServiceNow is extremely strong at governing the AI estate: what AI exists, who owns it, its
> risk, policy, compliance and lifecycle. Ugence begins at the point where the enterprise says:
> *now let AI make the decision.* We govern the evidence it can rely on, whether it has delegated
> authority, which model or agent is authorized, the exact action and payload, whether execution
> is safe now, whether the actual effect matched approval, and how that outcome changes future
> authority — and every one of those controls is a real, independently installable package.

## 4.2 Partnership framing

```
SYSTEM OF RECORD / WORKFLOW
ServiceNow  ·  AI estate | CMDB | risk | policy | approvals | cases | workflows
        ↓
SYSTEM OF RUNTIME AUTHORITY
Ugence  ·  evidence | decisions | model authority | action authorization
        ·  trajectory | operational clearance | reconciliation | Story Graph
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
- ❌ *"Story Graph replaces CMDB."* — position it as causal runtime-governance lineage that
  complements ServiceNow records.

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
13. Can the platform express graduated AI authority (autonomous `<$10K`, human-required `>$100K`)?
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
 action-clearance | context-minimization | storygraph | policy-workflow-compiler
 agent-workforce-composer | agent-runtime | procurement | cloud-scaling-*
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
| Static audit narrative | **Story Graph** | Adds causal governance lineage across policy, evidence, authority, execution and outcomes |

---

# Appendix B — Master Map: Package ↔ Module ↔ ServiceNow Adjacency

| `symbolu/packages/…` | Distribution | Conceptual module | Decision vocabulary | ServiceNow adjacency |
|---|---|---|---|---|
| `governance-contracts` | `ugence-governance-contracts` | Contract spine | request/result/outcome types | Data model / table schema |
| `governance-provider-framework` | `ugence-governance-provider-framework` | Provider mechanics | register/resolve/invoke | IntegrationHub / spokes |
| `tooling/policy-workflow-compiler` | `ugence-policy-workflow-compiler` | Policy Workflow Compiler | → `workflow_ir` + digest | Flow Designer / policy config |
| `providers/tap` | `ugence-tap-provider` | TAP (Truth Assurance) | `SUPPORTED/CONSTRAINED/INDETERMINATE` | AI guardrails / risk records |
| `capabilities/decision-authority` | `ugence-decision-authority` | AI Decision / Risk Authority | binding `DecisionOutcome` | AI risk assessments / cases |
| `providers/actiongate` | `ugence-actiongate-provider` | ActionGate | `AUTHORIZED/DENIED/INDETERMINATE` | Tool/MCP + access governance |
| `capabilities/action-clearance` | `ugence-action-clearance` | ACP / Operational Clearance | `CLEAR/HOLD/BLOCK/ESCALATE` | ITSM/ITOM / change state |
| `capabilities/model-selection` | `ugence-model-selection` | Model Authority | selection / `NO_ELIGIBLE_MODEL` | AI/model inventory |
| `capabilities/llm-steering-controller` | `ugence-llm-steering-controller` | LLM Steering Controller | `RECOMMENDED` (not executed) | Now Assist guardrails |
| `capabilities/context-minimization` | `ugence-context-minimization` | Context Minimization | `minimize_context` (fail-closed) | Data access / privacy controls |
| `capabilities/agent-workforce-composer` | `ugence-agent-workforce-composer` | Agent Workforce Composer | `AgentTeamPlan` (zero new authority) | Agent orchestration / skills |
| `capabilities/storygraph` | `ugence-storygraph` | Sequence-Risk / Trajectory | `OBSERVE/ESCALATE/UNAVAILABLE` | Cases / CMDB relationships |
| `runtime/agent-runtime` | `ugence-agent-runtime` | Agent Runtime / CER | consumes `CLEAR/HOLD/BLOCK/ESCALATE` | Agent platform / runtime |
| `capabilities/cloud-scaling-controller` | `ugence-cloud-scaling-controller` | Scaling (advisory) | recommendation (`advisory_only`) | ITOM event management |
| `capabilities/cloud-scaling-operations` | `ugence-cloud-scaling-operations` | Scaling (controlled exec.) | gated `CONTROLLED_EXECUTION` | Remediation runbooks |
| `products/ai-hiring` | `ugence-ai-hiring` | Hiring Governance Authority | human-only binding decision | HR / ATS workflows |
| `products/procurement` | `ugence-procurement` | Governed Procurement | graduated decision rights | Procurement / approval chains |

---

# Appendix C — Architectural Invariants (why the packages are trustworthy)

These invariants are implemented in code and, in several packages, machine-checked by tests —
they are the technical substance behind the positioning.

1. **Authority never leaks across layers.** Each layer speaks a distinct decision vocabulary
   (Appendix B). An `OBSERVE` is not a `DENY`; an `AUTHORIZED` is not an execution; a `CLEAR` is
   not an authorization. StoryGraph's boundary (never emits `ALLOW/DENY/AUTHORIZE/CLEAR`) is
   machine-checked.
2. **Fail-closed by construction.** TAP never promotes uncertainty to `SUPPORTED`; ActionGate
   never promotes it to `AUTHORIZED`; Agent Runtime fails closed to `GOVERNANCE_NOT_CONFIGURED`;
   Context Minimization fails closed when equivalence can't be established; cloud-scaling defaults
   to `dry_run`.
3. **AI cannot authorize itself.** `decision-authority`'s `AuthorityType` has no AI member — a
   structural, not merely procedural, guarantee.
4. **Composition grants nothing.** The provider framework, Agent Workforce Composer, and both
   products compose lower layers without creating new authority; each action still requires its
   own authorization.
5. **Recommendation and execution are separate packages.** The cloud-scaling controller/operations
   split (and the TAP/ActionGate ↔ Agent Runtime split) physically separate advice from actuation,
   so a recommendation can never silently become a mutation.
6. **Vendor-neutral and independently distributable.** Every package ships its own wheel, prefixed
   `ugence-`, with a legacy-compatibility facade preserving object identity — so ServiceNow is one
   adapter, never a hard dependency.

---

# Final Positioning Summary

ServiceNow is the **System of Record** and enterprise workflow platform. Ugence is the **System of
Runtime AI Authority**, delivered as a set of independent, offline-verifiable packages under
`symbolu/packages/`. The integration opportunity is to convert ServiceNow governance states into
enforceable authority at the exact point an AI model, agent, or workflow is about to decide or
act.

This framing preserves ServiceNow's strengths, gives Ugence a clear execution-time category, and
keeps every Ugence package independently deployable with Microsoft, Salesforce, SAP, Workday,
Oracle, or a custom stack if a ServiceNow partnership is not pursued.

> **ServiceNow answers: "How should work flow?"**
> **Ugence answers: "Should this AI action be allowed to execute right now?"**
