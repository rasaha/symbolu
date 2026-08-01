# Ugence Decision Governance — Terminology Update Report

**Date:** 2026-08-01
**Phase:** documentation-only terminology & boundary canonicalization
**Decision record:** [`ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md)
**Evidence audit:** [`../../UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md`](../../UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md)

> *No runtime package, API, import path, serialization, digest, authority boundary, frozen
> artifact, or historical record was renamed or changed in this phase.*

---

## 0. State verification & a required deviation (Step 1)

Before any work, repository state was verified directly (local refs, all remote branches,
reflog, object store):

- The referenced terminology-audit commit **`4cb3f1e` does not exist** anywhere
  (`git cat-file -t 4cb3f1e` → *"Not a valid object name"*), and the file
  `UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md` was **absent** from the working
  tree and from every commit tree.
- The `…-m25c2i` branch is **already merged** (PR #1260) into the default branch; it carries
  **zero** commits ahead of it.

**Consequence for Step 1 ("push commit `4cb3f1e`"):** *not executable and not fabricated.*
There was no such commit to push. Rather than invent one, the missing terminology audit was
**authored fresh in this phase** from live repository evidence and committed normally. All
work landed on the designated development branch `claude/storygraph-canonical-package-migration-j5u0iv`
(restarted from the current default-branch tip), not on the merged `…-m25c2i` branch — a
merged pull request cannot track new work.

---

## 1. Canonical umbrella name

**Ugence Decision Governance** — the umbrella for the complete platform and product family.
Positioning: *"Ugence Decision Governance controls what enterprise AI may claim, recommend,
decide, and execute."*

## 2. Decision Authority definition

**Decision Authority** — the bounded capability governing when an AI recommendation may become
a **binding** business decision. It may own decision-authority validation, segregation of
duties, evidence completeness, human/policy approval, overrides, immutable decision records,
and decision reconstruction. It must **not** own assertion admissibility, exact-action
authorization, operational clearance, model routing, sequence-risk analysis, workflow
execution, or universal orchestration.

## 3. Current implementation / package alias

Decision Authority is implemented today by the frozen **`decision_governance`** kernel
(`decision-governance` wheel, frozen v1.0.0). The package name is an **alias** carried
unchanged this phase; any rename is deferred to the future Decision Authority capability
migration under explicit freeze re-baselining.

## 4. AI Control Plane classification

**Optional, bypassable** administration & coordination layer beneath the umbrella
(administration, policy distribution, capability registry, connector config, observability,
audit correlation, workflow composition, optional orchestration). It is **not** the umbrella
and **not** a universal authority. A single-capability customer deploys none of it.
*(Single canonical meaning: "AI Control Plane" denotes only this optional component. The
governance layer formerly labeled "AI Control Plane" in `UGENCE_PLATFORM_OVERVIEW.md` is renamed
the **Governance Services Layer**; that overview's ten-component taxonomy is unchanged.)*

## 5. Orchestrator classification

**Optional Orchestrator** — a service inside the optional AI Control Plane that coordinates
configured workflows and **acquires no authority** from the capabilities it invokes.
Coordination does not transfer authority; authority remains federated by function.

## 6. Product composition definitions

Proposed customer-facing products (compositions over capability public contracts; **no product
packages created this phase**):

| Product | Governs | Likely capabilities |
|---|---|---|
| **Assert** | what AI may claim / communicate | TAP, Context Minimization, LLM Steering, evidence/release audit |
| **Decide** | how recommendations become binding | Decision Authority, TAP evidence, human review, override controls |
| **Act** | what AI agents may execute | ActionGate, ACP, Agent Runtime, credential enforcement, reconciliation |
| **Sequence** | risk across linked events | StoryGraph, trusted-context verification, historical replay, case/ActionGate integration |

## 7. Capability inventory — before and after

**Before (nine; Model Selection folded under Hybrid LLM):** TAP, Decision Governance,
ActionGate, ACP, StoryGraph, Agent Runtime, Context Minimization, Hybrid LLM, LLM Steering.

**After (ten):**

| # | Capability | Package alias |
|---:|---|---|
| 1 | TAP | `tap_provider` |
| 2 | **Decision Authority** | `decision_governance` (unchanged) |
| 3 | ActionGate | `actiongate_provider` / `cyber_security/action_gateway*` |
| 4 | ACP | `symbolu_robotics/autonomous_control_plane` |
| 5 | StoryGraph | `cyber_security/composite_threat_detector` |
| 6 | Agent Runtime | `agent_runtime_migration` |
| 7 | Context Minimization | `experiments/actiongate_context_ablation` |
| 8 | **Model Selection** | `model_selection_pilot` |
| 9 | Hybrid LLM | `agentic/hybrid_handover` |
| 10 | LLM Steering | `scripts/cg_wrapper_ablation/csr_match_filter` |

Governance Contracts remain **shared foundation**, not a capability.

## 8. Model Selection classification

`CROSS_CUTTING_POLICY_SERVICE — RESEARCH/PILOT MATURITY`, distinct from Hybrid LLM and
**not** merged into it. It may govern approved-model/provider eligibility, privacy/data-egress
restrictions, required capabilities, cost/latency constraints, availability policy, and
fallback order. It must **not** determine assertion admissibility, binding business decisions,
exact-action authorization, operational safety, or execution permission. Consistent with
[`../../ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`](../../ADR_MODEL_SELECTION_POLICY_PLACEMENT.md)
(complementary axis: capability-engine inventory vs. platform placement).

## 9. Documents amended

Concise terminology notes (not rewrites) linking the ADR were added to:

- `UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md` (also: §4 inventory nine→ten with Decision
  Authority + Model Selection; conceptual Model-C target; conceptual migration roadmap)
- `UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md`
- `UGENCE_INTERMODULE_IO_AND_AUTHORITY_AUDIT.md`
- `UGENCE_PLATFORM_OVERVIEW.md` (governance-layer usage of "AI Control Plane" renamed to
  **Governance Services Layer**; "AI Control Plane" reserved for the optional component;
  ten-component taxonomy unchanged)
- `UGENCE_PRODUCTIZATION_ROADMAP.md`

New documents: this report, the ADR, the terminology audit, and the terminology validator
(`scripts/validate_terminology.py` + `tests/test_terminology_validation.py`).

## 10. Legacy terms preserved

**"Decision Governance Platform"** (frozen technical bundle) is marked legacy and preserved
verbatim in frozen/historical materials; readers are pointed to the ADR. No frozen manifest,
API snapshot, historical validation report, or investor document was edited.

## 11. Validation results

- **Terminology validation** (`python scripts/validate_terminology.py`): **PASS** — all three
  governed documents satisfy the canonical-vocabulary rules; all five amended documents carry
  the ADR-linked terminology note.
- **Terminology test** (`tests/test_terminology_validation.py`): both checks pass. `pytest`
  is not installed in this environment, so the two test functions were executed directly via
  `importlib`; both returned green. The test is pytest-collectable where pytest is available.
- **Documentation links:** relative links in the new documents resolve within the tree.
- **StoryGraph tests** (`cyber_security/composite_threat_detector/tests`): unaffected by this
  documentation-only change (no source touched).
- **Git diff review:** changes are confined to Markdown docs plus one new validation
  script/test; no source module, package manifest, API snapshot, or freeze artifact appears in
  the diff.

## 12. Runtime & freeze confirmation

No change to runtime behavior, Python imports, package names, wheel names, public APIs,
serialization, digests, authority semantics, freeze snapshots, or historical evidence. The
phase is documentation-only.

## 13. Future code / package renames (deferred)

- Renaming the `decision_governance` package/directory to a Decision Authority name — deferred
  to the **Decision Authority capability migration** (roadmap step 5), gated on freeze
  re-baseline and parity tests.
- Physical `packages/` Model-C layout (including `capabilities/decision-authority/`,
  `capabilities/model-selection/`, `platform/optional-ai-control-plane/`, `products/`) — a
  conceptual target only; no directories created or renamed.

## 14. Remaining ambiguities

- **`decision_governance` name overload persists in code** until the deferred capability
  migration; the alias note is the interim mitigation.
- **"AI Control Plane" now has a single canonical current meaning** — the optional, bypassable
  administration & coordination component. The governance-layer sense was renamed **Governance
  Services Layer** in the current architecture documents (platform overview). Residual
  governance-layer uses of "AI Control Plane" may remain in *accepted ADRs and
  historical/frozen/investor materials*, which are preserved and pointed to the terminology
  ADR rather than rewritten (e.g. `ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`, which references
  the Governance Services Layer as Model Selection's provisional owner).
- **Original audit commit `4cb3f1e` never existed;** the audit here is a fresh, evidence-based
  reconstruction, not a recovery of prior content.

---

## Verdict

**CONTINUE — Ugence Decision Governance terminology and boundaries established.**

"Ugence Decision Governance" is now the canonical umbrella name for the platform and product
family. "Decision Authority" is the bounded capability currently implemented under the legacy
decision_governance package name. The AI Control Plane is an optional, bypassable
administration and coordination layer containing an optional orchestrator; it is neither the
umbrella nor a universal governance authority. Model Selection is formally recognized as the
tenth capability and remains distinct from Hybrid LLM. No runtime package, API, import path,
serialization, digest, authority boundary, frozen artifact, or historical record is renamed or
changed in this phase.
