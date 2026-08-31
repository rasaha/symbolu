# Authority-Boundary Matrix — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4, §5)
> and `Project_documentation/repository/docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`.
> Verified against live code at commit `3ec11e4e`.

Code Governance **invents no new authority**. Each component below acts strictly within a
boundary that already exists in the repository.

## Authority hierarchy (must be preserved — §5)

```
Hard policy constraints
  → Deterministic validation evidence
    → TAP evidence admission               (ASSERTION_GOVERNANCE)
      → Adjudicator recommendation          (advisory, optional)
        → Decision Authority approval       (binding — DecisionRecord)
          → ActionGate exact-action authz   (ActionGovernanceResult, bound via CER)
            → ACP live clearance
              → Execution (merge)           (EXTERNAL_EXECUTION; chain proven §4.7)
```

## Ownership matrix

| Component | Owns (authority) | Must NOT own | Binding output | Live enforcement anchor |
|---|---|---|---|---|
| **GitHub Evidence Connector** (product) | nothing | claim judgment, any decision | immutable evidence refs | net-new; no `evaluate()` |
| **TAP** (`ASSERTION_GOVERNANCE`) | evidence-admissibility of a claim | approval, authorization, execution | `AssertionGovernanceResult.coverage` | `tap_provider/provider.py:50`; fail-safe → INDETERMINATE |
| **Competitive Adjudicator** (optional) | a non-binding recommendation | approval, authorization, merge | one of `SELECT_A/B/REJECT_BOTH/REQUEST_REPAIR/ESCALATE` | structurally no path to `DecisionRecord` (§4.2) |
| **Decision Authority** | the binding decision | execution, action authorization | `DecisionRecord` (immutable) | `decisions/decision.py:25`; `AuthorityType` has no AI member; SoD in `case_validation_service.py:138` |
| **Workflow Service** (product) | coordination state, reference propagation, fail-closed chain proof | claim/approval/authorization/clearance/patch-selection/execution authority | workflow state only | net-new (§4A) |
| **ActionGate** (`ACTION_GOVERNANCE`) | exact-action authorization | the original binding decision, execution | `ActionGovernanceResult` (bound via CER) | `actiongate_provider`; adapter → `ActionControlPlanePort` |
| **ACP** | live operational clearance now | the original binding decision, authorization minting | clearance verdict (`CLEAR/HOLD`) | shadow-only; `Project_documentation/control_plane/acp/ACP_ACTIONGATE_BOUNDARY.md`; ACP `HOLD` cannot mint authz; ActionGate `DENY` never overridden |
| **StoryGraph** | advisory sequence-risk evidence | any blocking decision | `Finding` (`OBSERVE/ESCALATE/UNAVAILABLE`) | `storygraph/signals.py:28` |
| **GitHub Execution Provider** (`EXTERNAL_EXECUTION`) | dispatch/observe the merge | policy interpretation, governance judgment | `ExecutionDispatchResult`/`ExecutionObservation` | contract only; provider MISSING |
| **Governance Provider Framework** | register/resolve/adapt | authority, policy, patch selection, orchestration | `ResolutionRecord` (auditable) | `resolution.py:61`; no ALLOW/DENY logic |
| **Model Selection** | which approved model to use | governing the software change | `Selection` (advisory) | `packages/capabilities/model-selection` |

## Two distinct action-authorization layers (clarification for implementers)

The repo contains **two** action-authorization surfaces that must not be conflated:

1. **Neutral `ACTION_GOVERNANCE`** — `ActionGovernanceProvider.authorize` →
   `ActionGovernanceResult` (implemented by ActionGate). This is the family the design maps to.
2. **Decision-Authority-internal action machinery** — `ActionRequest` → CER →
   `ActionControlPlanePort.authorize` → `ActionAuthorizationResponse`
   (`OfflineDeterministicControlPlane`). ActionGate plugs into this port via the GPF adapter
   `action_to_control_plane.py:65`.

Both are authorization surfaces; neither is a decision. The binding decision is always the
`DecisionRecord`. The CER conveys the approved operation as **governance context, not an
execution command** (`actions/cer.py` docstring).

## Verdict

All authority boundaries the design asserts are **present and enforceable in live code today**
for TAP, Decision Authority, ActionGate, StoryGraph, and GPF. The only authority-bearing
gaps are **maturity** gaps (ACP is shadow-only; the execution provider and Workflow Service are
unbuilt), not **architecture** gaps. No boundary requires redesign.
