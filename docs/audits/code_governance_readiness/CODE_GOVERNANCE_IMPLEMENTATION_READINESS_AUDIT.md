# Ugence Code Governance — Implementation-Readiness Audit

**Status:** Documentation, contract-mapping, dependency, and architecture-verification phase only.
**No implementation.** No runtime, package, contract, provider, API snapshot, or frozen artifact is
changed by this audit.
**Authoritative technical source:** `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` (v0.2 — architecture
correction). Competitive documents (`UGENCE_CODE_GOVERNANCE_COMPETITIVE_POSITIONING.md`,
`UGENCE_CODE_GOVERNANCE_BATTLECARD.md`) are positioning material and do not override repository
contracts or technical evidence.
**Terminology:** follows `docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`
(Ugence Decision Governance umbrella; Decision Authority capability; Model Selection is the tenth
capability; AI Control Plane and orchestrator are optional).

**Audited commit:** `3ec11e4ecbc209eabc69d3c0d8a75ecaa10f6def` (default branch tip).
**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`.
**Audit branch:** `claude/ugence-code-governance-audit-nj6owc` (environment-mandated; the prompt's
suggested `claude/code-governance-implementation-readiness-audit` was overridden by the environment
branch directive — documented here per instruction).
**Python:** 3.11.15. **Clean tree at start:** yes.

---

## 1. Integrated starting point (verified)

| Check | Result |
|---|---|
| Actual default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Current remote default HEAD | `3ec11e4e` |
| Working-tree status | clean |
| PR #1268 (v0.2 design) merged | ✅ |
| PR #1270 + v0.2 architecture correction merged | ✅ (commit `4ea713c9` integrated) |
| PR #1269 + Model Selection audit merged | ✅ |
| PR #1271 + canonical Model Selection migration merged | ✅ |
| Competitive positioning + battlecard present on default | ✅ (PRs #1272/#1273) |
| Existing Code Governance implementation branch/PR | none found |
| Later commit modifying the design after v0.2 | none technical — only positioning-reference additions (`c75b4d1d`) |

**Three design files integrated & confirmed:** `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` (1130 lines,
v0.2), `UGENCE_CODE_GOVERNANCE_COMPETITIVE_POSITIONING.md`, `UGENCE_CODE_GOVERNANCE_BATTLECARD.md`.

**The corrected v0.2 design is integrated.** The audit proceeds (not blocked).

## 2. Baseline (reproduced, not fixed)

All relevant suites reproduced green at the default HEAD. See `TEST_AND_VALIDATION_PLAN.md` §1 for the
full table: terminology validator PASS · doc-link checker PASS (21 links) · platform freeze verifier
PASS (6 checks incl. `dependency_direction`) · dependency-direction validators 15 passed · Governance
Contracts 45 · GPF 84 · Decision Authority 79 · StoryGraph 316 · TAP provider 38 · ActionGate provider
30 · ACP-closest (robotics `acp_control_plane`) 20 · control-plane smoke 65. No canonical ACP package
tests exist (ACP is shadow-only design + robotics/K8s shadow code). Env deps installed for the run:
`pytest`, `pydantic`, `numpy` (no code fixes). No unrelated failures were fixed.

## 3. Frozen architecture audited (v0.2 authority chain)

```
GitHub Evidence Connector → (immutable evidence refs) → TAP → (assertion-governance result)
  → Code Governance Workflow Service → (prepared merge action + governance context)
    → Authorized actor + Decision Authority → (DecisionRecord)
      → CER → (minimized action-governance context)
        → ActionGate → (ActionGovernanceResult)
          → ACP → (live operational clearance)
            → GitHub Execution Provider → (dispatch / observe / reconcile)
```

Every fixed boundary in the design was verified against live code — see `PROVIDER_ROLE_MATRIX.md` and
`AUTHORITY_BOUNDARY_MATRIX.md`. **The rejected three-GitHub-provider architecture is not reopened.**
**No new `ProviderKind` is needed** (three families suffice; a fourth is a MAJOR freeze change).

## 4. Companion documents (this audit set)

| Area | Document |
|---|---|
| Live contracts (field-level) | `LIVE_CONTRACT_INVENTORY.md` · `contract_inventory.json` |
| Concept → type disposition | `CONTRACT_MAPPING_MATRIX.md` · `contract_mapping.json` |
| Authority boundaries | `AUTHORITY_BOUNDARY_MATRIX.md` |
| Provider roles / GitHub decomposition | `PROVIDER_ROLE_MATRIX.md` · `provider_role_map.json` |
| Workflow Service ownership | `WORKFLOW_SERVICE_OWNERSHIP.md` |
| Product package boundary | `PRODUCT_PACKAGE_BOUNDARY.md` |
| Evidence + TAP | `EVIDENCE_AND_TAP_MAPPING.md` |
| Decision + CER | `DECISION_AND_CER_MAPPING.md` |
| ActionGate + ACP | `ACTIONGATE_AND_ACP_MAPPING.md` |
| External execution | `EXTERNAL_EXECUTION_MAPPING.md` |
| Exact merge identity | `EXACT_MERGE_IDENTITY.md` · `merge_identity_schema.json` |
| Merge queue | `MERGE_QUEUE_ANALYSIS.md` |
| Policy ownership | `POLICY_OWNERSHIP_MATRIX.md` |
| Security & trust boundaries | `SECURITY_AND_TRUST_BOUNDARIES.md` |
| Durable audit & reconstruction | `DURABLE_AUDIT_AND_RECONSTRUCTION.md` |
| State machine | `STATE_MACHINE.md` |
| Dependency direction | `DEPENDENCY_DIRECTION.md` |
| Maturity | `MATURITY_MATRIX.md` · `maturity_matrix.json` |
| Risks | `RISK_REGISTER.md` |
| Implementation sequence | `IMPLEMENTATION_SEQUENCE.md` · `implementation_manifest.json` |
| Test & validation | `TEST_AND_VALIDATION_PLAN.md` |
| Open questions | `OPEN_QUESTIONS.md` |
| Rollback | `ROLLBACK.md` |
| Executive summary | `EXECUTIVE_SUMMARY.md` |

## 5. Central findings

1. **Authority spine exists and passes tests.** Governance Contracts, GPF, Decision Authority,
   ActionGate, and StoryGraph are IMPLEMENTED. TAP is a PARTIAL_PROTOTYPE (synthetic data).
2. **No frozen neutral contract needs to change for MVP.** Every merge-governance concept maps onto
   existing `DecisionRecord` / CER / `ActionGovernance*` / `Execution*` types + product envelopes.
   - **No `MergeDecisionRecord`** — reuse `DecisionRecord` (§4.3 confirmed).
   - **No `ExactChangeAuthorization` ActionGate contract** — it is a product envelope (§4.4 confirmed).
   - **No `cer.v2`** — `cer.v1` names permitted parameters + required controls and binds
     decision/tenant/policy/expiry/`content_hash`; exact SHA **values** ride in
     `ActionRequest.requested_parameters` + the product envelope (resolves design open question §17.3).
3. **GitHub decomposes correctly:** Evidence Connector (product, no authority) + action mapping layer
   (product, in Workflow Service) + **one `EXTERNAL_EXECUTION` GitHub Execution Provider**. The
   connector is a **normal product connector**, not a provider family.
4. **Governance-chain binding is expressible without changing the neutral execution contract** — via
   the DA `ExecutionIntent` (preferred) or reserved `parameters` keys, with the Workflow Service
   failing closed (`CHAIN_INCOMPLETE`) when the chain cannot be reconstructed (§4.7).
5. **The gaps are maturity/persistence/execution-time, not architecture:**
   - **ACP** is SHADOW_ONLY with **no GitHub domain** and no durable clearance reference.
   - **Durable audit** is PARTIAL — real hash-chained stores exist (StoryGraph, `agentic/ledger`) but
     the decision kernel persists nothing durably (audit chaining reserved/unused).
   - **Durable workflow infrastructure** is PLANNED (no engine as code).
   - **Evidence store** is absent; **validator-identity binding**, **quarantine**, **admissibility**,
     and **head-SHA invalidation** are missing.
   - **GitHub Evidence Connector**, **GitHub Execution Provider**, and **Competitive Code
     Adjudication** are MISSING (net-new by design).
6. **Enforcement is safely sequenced** shadow → recommendation → enforced; phases A–E add no
   enforcement and no GitHub writes, so most P0 prerequisites can be built in parallel with them.

## 6. Verdict

The authority and contract architecture is **sound and expressible on the live repository with no
frozen-contract changes**. However, **enforced** merge governance (MVP 1C) depends on named
prerequisites that do not yet exist: a durable workflow + audit persistence layer, product-side
governance-chain binding with fail-closed reconstruction, an ACP GitHub-domain clearance adapter with
a durable one-time clearance reference, and the GitHub connector/execution provider. Shadow (1A) and
recommendation (1B) modes are reachable earlier.

> **CODE GOVERNANCE READY WITH PREREQUISITES — named workflow, persistence, binding, or ACP gaps must
> be resolved first.**

No runtime behavior changed. Implementation has **not** begun.
