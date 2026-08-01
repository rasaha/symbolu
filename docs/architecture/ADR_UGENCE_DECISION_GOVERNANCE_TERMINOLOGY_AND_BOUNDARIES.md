# ADR — Ugence Decision Governance: Canonical Terminology and Boundaries

**Status:** Accepted (documentation-only)
**Date:** 2026-08-01
**Owners:** Ugence platform architecture
**Related:**
- [`ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`](../../ADR_MODEL_SELECTION_POLICY_PLACEMENT.md) — Model Selection placement (complementary; not superseded)
- [`UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md`](../../UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md) — the evidence audit behind this decision
- [`UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md`](../../UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md), [`UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md`](../../UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md), [`UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md`](../../UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md)

> *This ADR changes **no** production code, package, wheel, API, schema, frozen identifier,
> serialization, digest, authority boundary, or historical record. It fixes vocabulary and
> boundaries in documentation only. Code/package renames it implies are explicitly deferred
> to later, compatibility-controlled migrations.*

---

## Central decision

> **"Ugence Decision Governance"** is the canonical umbrella name for the platform and
> product family. **"Decision Authority"** is the bounded capability currently implemented
> under the `decision_governance` package. The **AI Control Plane** is an optional
> administration and coordination layer, not the umbrella and not a universal authority.

---

## Context

The logical architecture is settled — federated capabilities with distributed,
function-specific authority. The **naming** is not. As verified in the companion audit, the
phrase "Decision Governance" is used at three incompatible altitudes at once: the whole
platform (umbrella), a single bounded capability (the binding-decision engine), and a frozen
technical bundle ("Decision Governance Platform v1.0.0"). The same overload lives in code as
the `decision_governance` package. Separately, **Model Selection** is inconsistently folded
under Hybrid LLM despite being a distinct capability. Without a canonical vocabulary, every
downstream migration, product description, and investor document re-litigates the same
ambiguity.

## Naming problem

1. **Umbrella vs. capability collision.** "Decision Governance" names both the platform and
   one capability inside it — so "we sell Decision Governance" is ambiguous about whether the
   customer gets the platform or one engine.
2. **Legacy bundle collision.** "Decision Governance Platform" is a *frozen technical bundle*
   label, distinct from both the umbrella and the capability, but reads as either.
3. **Authority inflation risk.** The AI Control Plane and its orchestrator, being the visible
   "top" of the stack, are easily mistaken for the umbrella or for a universal adjudicator.
4. **Model Selection misplacement.** Treating Model Selection as a Hybrid LLM submodule hides
   a distinct, customer-governed policy capability and understates the capability inventory
   (nine where there are ten).

## Decision

### Canonical terminology

| Canonical name | Meaning |
|---|---|
| **Ugence Decision Governance** | The umbrella: the complete platform and product family. Positioning: *"Ugence Decision Governance controls what enterprise AI may claim, recommend, decide, and execute."* |
| **Decision Authority** | The bounded capability governing when an AI recommendation may become a **binding** business decision. Implemented today under the `decision_governance` package (name unchanged this phase). |
| **AI Control Plane** | An **optional**, bypassable shared platform component beneath the umbrella: administration, policy distribution, capability registry, connector config, observability, audit correlation, workflow composition, optional orchestration. |
| **Optional Orchestrator** | A service **inside** the optional AI Control Plane that coordinates configured workflows and **does not acquire authority** from the capabilities it invokes. |
| **Decision Governance Platform** *(legacy)* | An existing frozen technical bundle label. **Not** used for new architecture or product naming; preserved verbatim in frozen/historical text. |
| **Model Selection** | A distinct cross-cutting policy capability (the tenth), separate from Hybrid LLM. |

### Umbrella-versus-capability distinction

*Ugence Decision Governance* (umbrella) is a **family name**; it maps to no single package.
*Decision Authority* (capability) is one engine in that family, implemented by the frozen
`decision_governance` kernel. "Decision Governance," unqualified, is **retired** from new
architecture text: use the umbrella name or the capability name explicitly.

### Authority boundaries

Coordination does not transfer authority. Each component owns exactly one function:

| Component | Authority / role |
|---|---|
| TAP | Assertion evidence & admissibility result |
| **Decision Authority** | Binding business-decision governance |
| StoryGraph | Advisory sequence-risk evidence |
| ActionGate | Exact-action authorization |
| ACP | Commit-time operational clearance |
| Agent Runtime | Coordination & execution; never self-authorization |
| Context Minimization | Context transformation |
| Model Selection | Policy-bounded model/provider selection |
| Hybrid LLM | Local/frontier handover (research or runtime) |
| LLM Steering | Behavior shaping |
| AI Control Plane | Optional administration & coordination |
| Orchestrator | Optional workflow composition |

**Decision Authority may own:** decision-authority validation, segregation of duties,
evidence completeness, human/policy approval, overrides, immutable decision records, decision
reconstruction. **It must not own:** assertion admissibility, exact-action authorization,
operational clearance, model routing, sequence-risk analysis, workflow execution, or
universal orchestration.

### Product-versus-capability distinction

**Capabilities** are internal, reusable engines (implemented once, used through public
contracts). **Products** are customer-facing compositions over those contracts — never new
copies of the engines. Proposed products (compositions, not packages this phase): **Assert**
(what AI may claim), **Decide** (how recommendations become binding), **Act** (what agents
may execute), **Sequence** (risk across linked events).

### Optional AI Control Plane

The AI Control Plane is **optional and bypassable**. A single-capability customer deploys
none of it. It is neither the umbrella nor a universal governance authority.

### Optional orchestrator

The orchestrator is **optional**. It composes workflows and does not become an adjudicator
over the capabilities' findings; authority remains federated by function.

### Model Selection correction

Model Selection is the **tenth capability**, distinct from Hybrid LLM. Its platform placement
is a **cross-cutting policy service at research/pilot maturity**
(`CROSS_CUTTING_POLICY_SERVICE — RESEARCH/PILOT MATURITY`), consistent with
[`ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`](../../ADR_MODEL_SELECTION_POLICY_PLACEMENT.md).
It may govern approved-model/provider eligibility, privacy/data-egress restrictions, required
capabilities, cost/latency constraints, availability policy, and fallback order. It must
**not** determine assertion admissibility, binding business decisions, exact-action
authorization, operational safety, or execution permission. It is **not** merged into Hybrid
LLM.

> **Two complementary axes, not a contradiction.** The *capability-engine inventory*
> (restructuring / packaging) counts ten reusable engines and now lists Model Selection among
> them. The *platform-component taxonomy* in `UGENCE_PLATFORM_OVERVIEW.md` (three layers, ten
> components) is a different axis and is **unchanged**; there Model Selection remains a
> cross-cutting policy service, not one of the ten numbered components.

### Legacy terminology

"Decision Governance Platform" is legacy. New architecture and product naming must not use
it. Where historical/frozen materials use it, preserve the original text and point readers to
this ADR.

## Compatibility implications

- The `decision_governance` package, the `decision-governance` wheel, its frozen v1.0.0 API
  snapshot, and all `platform_freeze` identifiers keep their names **unchanged** this phase.
- The architectural name "Decision Authority" is an **alias over** the existing package name;
  no import path, symbol, or serialized field is renamed.
- A future "Decision Authority capability migration" (see the roadmap) may rename directories
  and packages, but only as an explicit, reviewed, freeze-re-baselined change — never
  silently, and never in this phase.

## Consequences

- Current architecture documents adopt the umbrella/capability/optional-control-plane
  vocabulary via **concise terminology notes**, not rewrites.
- The capability inventory moves from nine to ten across the restructuring and packaging
  audits; Model Selection is separated from Hybrid LLM.
- A terminology validation check guards new architecture documents against the retired/legacy
  usages.
- No runtime behavior, test result, freeze snapshot, or historical record changes.

## Migration guidance

The next capability migration in the roadmap concerns the **bounded Decision Authority
engine** (`decision_governance` kernel), **not** the umbrella Ugence Decision Governance
product family. Package/directory renames implied by "Decision Authority" are deferred to that
migration and gated on freeze re-baselining and parity tests.

## Explicit non-goals

This ADR does **not**: rename any Python package, wheel, module, API, or schema; alter any
frozen identifier, manifest, api-snapshot, or digest; change any authority boundary or runtime
behavior; rewrite historical validation reports, frozen evidence, prior verdicts, or investor
documents; create any product or capability package; or re-count the ten-component
platform-overview taxonomy (a separate axis, left unchanged).

## Canonical hierarchy

```text
Ugence Decision Governance
│
├── Customer-facing products
│   ├── Assert
│   ├── Decide
│   ├── Act
│   └── Sequence
│
├── Reusable capabilities
│   ├── TAP
│   ├── Decision Authority
│   ├── ActionGate
│   ├── ACP
│   ├── StoryGraph
│   ├── Agent Runtime
│   ├── Context Minimization
│   ├── Model Selection
│   ├── Hybrid LLM
│   └── LLM Steering
│
├── Shared foundation
│   ├── Governance Contracts
│   ├── Identity and tenancy
│   ├── Policy and evidence references
│   ├── Audit and reconstruction
│   ├── Connector framework
│   └── Observability
│
└── Optional AI Control Plane
    ├── Administration
    ├── Policy distribution
    ├── Capability registry
    ├── Cross-product monitoring
    ├── Workflow composition
    └── Optional orchestrator
```

- Products may be purchased and deployed separately.
- Capabilities may be used independently through public APIs.
- The AI Control Plane is optional.
- The orchestrator is optional.
- Neither the Control Plane nor the orchestrator becomes a universal adjudicator.
- Authority remains federated by function.
