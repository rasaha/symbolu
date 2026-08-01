# Ugence Terminology, Product & Capability-Boundary Audit

**Status:** Authored in the Ugence Decision Governance terminology phase.
**Scope:** documentation and naming only — no code, package, API, schema, freeze
artifact, or historical record is renamed or changed.
**Companion decision record:**
[`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md)

> **Provenance note (read this first).** An earlier hand-off referenced this audit as
> pre-existing commit `4cb3f1e`. Direct verification against the repository (local refs,
> all remote branches, reflog, and object store) found **no such commit and no such
> file** — `git cat-file -t 4cb3f1e` returns *"Not a valid object name."* This document
> was therefore **authored fresh in this phase** from live repository evidence, not
> recovered from a prior commit. Every count and claim below is traceable to the current
> tree; nothing is carried over on trust.

---

## 1. Why this audit exists

The repository's logical architecture is settled — federated capabilities with
distributed, function-specific authority (see
[`UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md`](UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md)
and
[`UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md`](UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md)).
The **naming** is not settled. One phrase — "Decision Governance" — is used at three
incompatible altitudes at once:

1. the **whole platform / product family** (umbrella),
2. a **single bounded capability** (the binding-decision engine), and
3. a **frozen technical bundle** ("Decision Governance Platform v1.0.0").

The same overload appears in code as the `decision_governance` package, which is the
frozen kernel for altitude (2) but shares a name with altitudes (1) and (3). Meanwhile
**Model Selection** is variously folded under Hybrid LLM, called an "accelerator," and
(correctly) classified elsewhere as a cross-cutting policy service — three placements
for one thing. This audit fixes the vocabulary before any physical migration touches it.

---

## 2. Verified current terminology usage

Counts are `*.md` files containing each term, measured against the working tree at the
current branch tip. They establish the size of the reconciliation, not a rename order.

| Term as used today | Files | Altitude(s) it is used at | Problem |
|---|---:|---|---|
| `AI Control Plane` | 82 | governance layer; sometimes implied umbrella | must be pinned as **optional**, not the umbrella |
| `decision_governance` (package) | 45 | bounded capability (frozen kernel) | correct target of altitude (2); **do not rename this phase** |
| `Hybrid LLM` | 43 | reasoning substrate | sometimes wrongly absorbs Model Selection |
| `Orchestrator` / `orchestrat*` | 39 | optional composition service | must be pinned as **optional / bypassable** |
| `Decision Governance` | 37 | umbrella **and** capability **and** bundle | the core overload |
| `Model Selection` | 31 | capability / accelerator / policy service | must be a **distinct capability**, not a Hybrid LLM submodule |
| `Decision Governance Platform` | 13 | frozen technical bundle (legacy) | **legacy term**; preserve in frozen/historical text only |
| `Decision Authority` | 3 | (emerging) bounded-capability name | the name to **adopt** for altitude (2) |
| `Digital Governance` | 0 | — | must **never** become the canonical umbrella |

The `decision_governance/` package exists as a real frozen kernel (`api/`, `identity/`,
`audit/`, `actions/cer.py`, `decisions/authority`; 29 package tests) and is distributed
as the `decision-governance` wheel under `packaging/`. Its name is **frozen** and out of
scope for renaming here.

---

## 3. The three altitudes, separated

| Altitude | Canonical name (adopted) | What it is | Current code/artifact |
|---|---|---|---|
| Platform & product family (umbrella) | **Ugence Decision Governance** | the complete platform and the family of products/capabilities under it | *no single package — a family name* |
| Bounded capability | **Decision Authority** | governs when an AI recommendation may become a **binding** business decision | `decision_governance/` (frozen kernel; name unchanged this phase) |
| Legacy frozen bundle | **Decision Governance Platform** *(legacy)* | an existing frozen technical bundle / freeze label | `platform/PLATFORM_FREEZE_V1.json`, api-snapshots — **preserved** |

Positioning sentence for the umbrella:

> **Ugence Decision Governance controls what enterprise AI may claim, recommend, decide,
> and execute.**

Its scope is broader than business approvals. It governs the chain of consequential AI
decisions: what context may be exposed · which model or provider may be used · what AI
may claim or communicate · whether a recommendation may become binding · whether an exact
action may execute · whether the action is operationally safe now · whether linked events
collectively create unacceptable risk.

---

## 4. Product-versus-capability boundary

**Capabilities** are internal, reusable engines. **Products** are customer-facing
compositions over capability *public contracts* — never new copies of the engines.

### Capability inventory correction: nine → ten

The current audits enumerate **nine** reusable capabilities
([`UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md`](UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md) §4;
[`UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md`](UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md)),
with model selection folded under Hybrid LLM. The canonical inventory is **ten**:

| # | Capability | Current implementation / package alias |
|---:|---|---|
| 1 | TAP | `tap_provider/` (adapter over mock engine) |
| 2 | **Decision Authority** | `decision_governance/` (frozen kernel — name unchanged) |
| 3 | ActionGate | `actiongate_provider/` + `cyber_security/action_gateway*` |
| 4 | ACP | `symbolu_robotics/autonomous_control_plane/` (shadow-only) |
| 5 | StoryGraph | `cyber_security/composite_threat_detector/` |
| 6 | Agent Runtime | `agent_runtime_migration/` |
| 7 | Context Minimization | `experiments/actiongate_context_ablation/` (research) |
| 8 | **Model Selection** | `model_selection_pilot/` (+ `_experiment/`, `_reconciliation/`) |
| 9 | Hybrid LLM | `agentic/hybrid_handover/` (scaffold) |
| 10 | LLM Steering | `scripts/cg_wrapper_ablation/csr_match_filter/` |

Model Selection (#8) is a **distinct capability**, separate from Hybrid LLM (#9). It is
simultaneously classified as a *cross-cutting policy service* at research/pilot maturity
(see [`ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`](ADR_MODEL_SELECTION_POLICY_PLACEMENT.md));
the two framings are complementary — capability-engine inventory vs. platform placement.

Governance Contracts are **shared foundation**, not a capability. The AI Control Plane and
the orchestrator are **platform services**, not governance authorities.

### Proposed products (compositions, not yet packages)

| Product | Governs | Likely capabilities |
|---|---|---|
| **Assert** | what AI may claim or communicate | TAP, Context Minimization, LLM Steering, evidence/release audit |
| **Decide** | how recommendations become binding decisions | Decision Authority, TAP evidence, human review, override controls |
| **Act** | what AI agents may execute | ActionGate, ACP, Agent Runtime, credential enforcement, reconciliation |
| **Sequence** | risk emerging across linked events | StoryGraph, trusted-context verification, historical replay, case/ActionGate integration |

These are **proposed compositions** unless canonical product packages already exist in
code. No product packages are created in this phase.

---

## 5. Authority boundaries (must be preserved)

Coordination does not transfer authority. Each component owns exactly one function.

| Component | Authority or role |
|---|---|
| TAP | Assertion evidence and admissibility result |
| **Decision Authority** | Binding business-decision governance |
| StoryGraph | Advisory sequence-risk evidence |
| ActionGate | Exact-action authorization |
| ACP | Commit-time operational clearance |
| Agent Runtime | Coordination and execution; never self-authorization |
| Context Minimization | Context transformation |
| Model Selection | Policy-bounded model/provider selection |
| Hybrid LLM | Local/frontier handover (research or runtime) |
| LLM Steering | Behavior shaping |
| AI Control Plane | Optional administration and coordination |
| Orchestrator | Optional workflow composition |

**Decision Authority may own:** decision-authority validation, segregation of duties,
evidence completeness, human/policy approval, overrides, immutable decision records,
decision reconstruction.

**Decision Authority must NOT own:** assertion admissibility (TAP), exact-action
authorization (ActionGate), operational clearance (ACP), model routing (Model Selection /
Hybrid LLM), sequence-risk analysis (StoryGraph), workflow execution (Agent Runtime), or
universal orchestration (the optional orchestrator).

---

## 6. The optional AI Control Plane

The AI Control Plane is an **optional** shared platform component beneath Ugence Decision
Governance. It may provide central administration, policy distribution, a capability
registry, connector configuration, cross-module observability, audit correlation, workflow
composition, and optional orchestration.

**It must remain bypassable.** Customers must be able to deploy and invoke individual
products or capabilities without requiring the AI Control Plane. The **Optional
Orchestrator** inside it coordinates configured workflows but **does not acquire authority
from the capabilities it invokes**. This matches the code today: the governed-loop
orchestrator (`ugence_console_api/orchestrator.py`) and `cer_v0_3.run_control_plane` are
*optional* composers, and every audit records that a single-capability customer deploys
none of them.

---

## 7. Legacy terminology handling

"**Decision Governance Platform**" is a legacy overloaded term bound to an existing frozen
technical bundle. It is **not** used for new architecture or product naming. Frozen
artifacts that carry it (freeze manifest, API snapshots, historical validation reports,
investor documents) are **preserved verbatim**; readers are pointed to the new ADR for
current terminology. Renaming any frozen artifact is a later, compatibility-controlled
migration — explicitly out of scope here.

---

## 8. Findings & required actions

| # | Finding | Action (this phase) |
|---:|---|---|
| F1 | "Decision Governance" overloaded across three altitudes | Adopt **Ugence Decision Governance** (umbrella), **Decision Authority** (capability), keep **Decision Governance Platform** as legacy-only |
| F2 | Capability inventory lists nine; Model Selection folded under Hybrid LLM | Correct to **ten**; Model Selection is capability #8, distinct from Hybrid LLM |
| F3 | AI Control Plane sometimes misread as the umbrella or as a universal authority | Pin as **optional, bypassable**; it is **not** a universal authority |
| F4 | Orchestrator not consistently marked optional | Pin orchestrator as **optional / bypassable**; coordination ≠ authority |
| F5 | `decision_governance` package name == capability name == bundle name | Document the alias; **defer** any code/package rename to a later compatibility-controlled migration |
| F6 | No canonical decision record for any of the above | Create the naming **ADR** and this audit; add a terminology validation check |

**Verdict:** the terminology is ambiguous today and the fixes above are documentation-only
and non-breaking. Proceed with the ADR, the concise amendments to current architecture
documents, and the terminology validation. No runtime, package, API, serialization,
digest, authority boundary, or frozen artifact is changed by acting on this audit.
