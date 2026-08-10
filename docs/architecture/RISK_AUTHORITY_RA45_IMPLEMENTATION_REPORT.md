# Risk Authority RA-4.5 — Governance Composition Implementation Report

**Status: RA-4.5 governance composition implemented and CI-verified; production
deployment validation remains pending.**

This document records the implementation of the corrected RA-4.5 architecture
([`RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md`](./RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md),
[`ADR_RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION.md`](./ADR_RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION.md)).
It supersedes the substitution-adapter approach
([`RISK_AUTHORITY_RA45_ADAPTER_PLAN.md`](./RISK_AUTHORITY_RA45_ADAPTER_PLAN.md),
**SUPERSEDED**), which the Phase 1 parity audit
([`RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md`](./RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md))
disproved.

## Terminology (RA-1→RA-4 vs RA-4.5)

| Layer | Meaning |
|---|---|
| **RA-1→RA-4** | Machine-authority **reference / conformance** layer (`ugence-risk-authority`, a stdlib-only leaf). The independently audited baseline (PR #1396). |
| **RA-4.5** | Additive **production governance composition** (`ugence-risk-authority-runtime`). Composes RA with two governance kernels, fail-closed. |
| **Decision Authority** | Human / organizational governance veto (`ugence-decision-authority`). Outcomes `ADVANCE/HOLD/REJECT/DEFER`; binding authority is never an AI model. |
| **ActionGate provider** | Supplementary action-policy veto / restriction (`ugence-actiongate-provider`). Decides on `action_type` alone. |
| **Risk Authorization Envelope** | The signed (Ed25519), scoped, time-bound **machine execution authority artifact**. RA-owned. The sole authority for execution. |

Two facts are stated explicitly and enforced in code:

```
production kernel ALLOW ≠ machine execution authority
FinalAuthority ≤ RiskAuthority
```

## What was built

A new integration package `packages/integration/risk-authority-runtime/`
(import `ugence_risk_authority_runtime`) depending on the three composed
packages one-way (no cycle; RA remains a stdlib-only leaf, unmodified):

```
risk_authority  ◄──  risk_authority_runtime  ──►  decision-authority
                                          └────►  actiongate-provider
```

| Module | Responsibility |
|---|---|
| `contracts.py` | Fail-closed value objects: `GovernanceVetoResult` (no ALLOW, no scope), `RiskAuthorityMachineResult`, `EffectiveConstraints`, `GovernedExecutionDecision`. |
| `risk_authority_enforcer.py` | Reuses the canonical RA enforcement path (`ReferenceActionGate` = envelope verify + exact-action match). Never reimplements the matcher. |
| `decision_authority_adapter.py` | `DecisionOutcome` → governance veto (ADVANCE=no-veto, HOLD/DEFER=hold, REJECT=deny, unknown=deny, missing=error). |
| `actiongate_adapter.py` | `ActionGateOutcome` → policy veto + tightening restrictions (ALLOW/…=no-veto, DENY/UNKNOWN=deny, missing=error). |
| `restrictions.py` | Monotone restriction algebra: `Effective = RA ∩ governance`, `⊆ RA` on every dimension. |
| `composition.py` | The single fail-closed composition engine implementing the §2 rule and §3 precedence. |

**Risk Authority was not modified.** The corrected additive model does not route
RA authority *through* the kernels, so no DI seam into the RA leaf was required
(plan §7 — "prefer that … use the narrowest valid design"). RA's own
`DecisionAuthorityPort` / `ActionGatePort` (ruler + cryptographic enforcer) stay
RA-owned; the two *production* kernels are composed additively, outside the leaf.

## Failure semantics (fail-closed — §4, §10)

Authority-critical failures never become `ALLOW`:

- **DENY** (authoritative negative about this request): RA off-scope / identity
  mismatch / bad signature; DA `REJECT`; DA unknown outcome; AG `DENY`; AG
  `UNKNOWN`; empty effective scope; RA `DENY` (absorbing).
- **HOLD_NON_EXECUTABLE**: DA `HOLD` / `DEFER`.
- **ERROR_NON_EXECUTABLE**: RA enforcement unavailable; DA/AG unavailable or
  malformed. A missing/failed authority input → do-not-execute, never proceed.

## F-A / F-B / F-E preservation

- **F-A** (failed mandatory control cannot become ALLOW): RA derives the binding
  outcome from persisted `ControlResult`s and refuses to mint an envelope for a
  non-granting decision; the composition engine only ever subtracts. Regression:
  `test_f_a_failed_control_cannot_be_overridden` (RA issues **no** envelope →
  composed DENY).
- **F-B** (expired decision cannot mint/refresh authority): effective expiry is
  `earliest(RA, governance)`, never extended; DA `ADVANCE` / AG `ALLOW` cannot
  refresh. Regressions: `test_f_b_…`, `test_expiry_only_shortens_never_extends`.
- **F-E** (duplicate control cannot mask failure): RA groups per control id;
  `FAIL` wins. Regressions: `test_f_e_duplicate_fail_then_pass…`,
  `test_f_e_pass_then_duplicate_fail…`.

## F-D — explicit non-goal (#1397)

RA-4.5 preserves current enforcement coverage and **does not close F-D**
(jurisdiction / autonomy / resource-target enforcement). `CanonicalAction` has no
`jurisdiction`/`autonomy` field; the ActionGate provider matches neither. An AG
`allowed_region` is recorded as a governance obligation only — **never** mapped
onto RA jurisdiction enforcement (`test_f_d_allowed_region_recorded_as_obligation
_not_jurisdiction_enforcement`). Closing F-D is separate work under #1397.

## Verification (exact counts)

| Suite | Result |
|---|---|
| Risk Authority baseline (`packages/risk_authority/tests`) | **97 passed** (unchanged) |
| RA isolated single-wheel verifier | **PASS** (unchanged) |
| RA-4.5 composition suite (`packages/integration/risk-authority-runtime/tests`) | **60 passed** |
| RA-4.5 wheel build + isolated-install verifier | **PASS** |
| Decision Authority suite (`packages/capabilities/decision-authority/tests`) | **79 passed** |
| ActionGate provider suite (`packages/providers/actiongate/tests`) | **57 passed, 1 skipped** |

The composition suite proves the corrected property: **composition may preserve
or reduce authority; it may never enlarge it** — every production DENY is
RA/adapter-enforced.

## Maturity

RA-4.5 governance composition is **implemented and CI-verified**. This is not a
claim of production readiness: production deployment validation (real Decision
Authority / ActionGate deployments, live revocation stores, trusted clocks,
HSM/KMS key custody) remains pending and is out of scope for RA-4.5.
