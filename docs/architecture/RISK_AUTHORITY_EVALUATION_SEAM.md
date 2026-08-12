# Risk Authority — Production-Bindable, Non-Executing Evaluation Seam (PR-1)

**Status:** Implemented (design-only prerequisite for Cloud Scaling Controller Phase 4).
**Package:** `ugence-risk-authority` `0.1.0 → 0.2.0` (additive, backward-compatible).
**Scope:** A public, domain-neutral seam that lets an external integration obtain a
canonical Risk Authority outcome for a neutral subject and **stop at the risk decision** —
no envelope issuance, no ActionGate invocation, no execution. This is *not* Cloud Scaling
Phase 4; it is the Risk-Authority-side prerequisite that unblocks it.

## Why

Exact-head discovery found Phase 4 blocked: (1) Risk Authority exposed no consumable
"evaluate a proposed subject → ALLOW / DENY / typed non-decision" entry that stops at the
decision; (2) `RiskAuthorityApplication` hardcoded the **reference** Decision Authority and
**reference** ActionGate with no production injection point (audit defect (h)); (3) the only
neutral protocol (`ActionGovernanceProvider.authorize`) starts too late — it authorizes an
already-prepared action against a pre-existing signed envelope. RA-5 (Trusted Evidence &
Control Assurance) remains design-accepted but unimplemented, so caller-supplied control
statuses must never be admitted as trusted production evidence.

## What ships

1. **Injectable ruler (defect (h) repair).** `RiskAuthorityApplication` gains an optional
   `decision_authority: DecisionAuthorityPort`. Omitted, it keeps the reference ruler
   (unchanged behavior for existing RA-5 evidence-only production callers). In production
   mode, an injected ruler MUST be production-authoritative
   (`is_production_authoritative=True`) and is rejected if it is the reference ruler — fail
   closed at construction. No existing public method changes meaning.

2. **Neutral contracts** (`risk_authority.integrations`):
   - `SubjectRiskEvaluationRequest` — carries *only* canonical subject facts + correlation /
     idempotency context. It has **no** field for a policy id, control results, keys, an
     evaluator identity, a precomputed recommendation / decision, or an envelope — the trust
     boundary is structural, not documented-only.
   - `SubjectRiskDecision` — the result: a canonical outcome (`RISK_PASSED` /
     `RISK_PASSED_WITH_CONDITIONS` / `RISK_DENIED` / `RISK_ESCALATED`) or a typed
     `NOT_EVALUATED` with a `SubjectRiskNonDecisionReason`. Every executable-capability flag
     (`authorization_performed`, `envelope_issued`, `actiongate_invoked`,
     `actuation_performed`, `effect_verified`, `executable`) is fixed `False`, enforced at
     construction. A risk PASS is **not** ActionGate authorization.
   - `PolicyResolverPort`, `TrustedControlEvidenceResolverPort` — trusted, authority-owned
     injection points (the latter is the explicit seam RA-5 will implement). Reference
     implementations are shipped and are never production-authoritative.

3. **`RiskEvaluationSeam`** (`risk_authority.api`) — composes the kernel through the existing
   facade: `create_case → evaluate_with_evidence (production) / evaluate (reference) →
   issue_decision`, and **stops**. It never calls `issue_envelope` or `authorize_action`.
   - `RiskEvaluationSeam.production(...)` fails closed on any reference-grade or missing
     dependency (policy resolver, evidence resolver, evidence ports, ruler, evaluator grant).
   - `RiskEvaluationSeam.reference(...)` is a visibly-labelled conformance seam the production
     factory can never yield.

## Trust boundary

The request expresses *what* is being evaluated; it can never decide *how*. Authoritative
policy, the control catalog, trusted control results, evaluator identity, signing keys, the
clock and revocation are all supplied by the trusted composition root. Because RA-5 is not
implemented, the seam admits **no** caller control statuses: absent a trusted evidence
provider, required controls resolve to MISSING and the non-compensatory gate fails closed to
DENY / ESCALATE. This seam establishes the injection boundary RA-5 will fill; it does **not**
deliver RA-5 assurance.

## Stop-at-decision

`RISK_PASSED` means only that *risk evaluation passed*; eligibility is not authorization. A
binding `RiskDecision` is minted only for the ALLOW-family (a case reaching `AUTHORITY_REVIEW`
with satisfied controls); a denial grants nothing and carries the canonical `RiskEvaluation`
instead. An ALLOW-family evaluation that cannot be bound (e.g. the configured evaluator
principal lacks a grant) is reported as `NOT_EVALUATED(AUTHORITY_UNAVAILABLE)`, never as a
pass.

## Verified invariants

The verified kernel invariants relied on here (independently re-checked at head): authority-
owned WorkflowIR by digest; non-compensatory controls; exact tenant / scope equality
(missing ≠ named); expiry / revocation; signature / digest verification; duplicate-control
fail-closed on the risk path; single construction path (no `from_dict` divergence). The seam
adds: production rejection of reference dependencies; fail-closed typed non-decisions;
fixed non-executable result flags; envelope / ActionGate sentinels; canonical serialization +
digest round-trip parity; ±1µs decision-expiry boundary.

## Explicitly out of scope

No envelope issuance, ActionGate invocation, provider execution, readiness checking, retry,
rollback or effect verification. No RA-5 implementation. No Cloud Scaling Controller / Operations
change. No cloud-scaling-specific contract (the seam is domain-neutral; a future Phase-4
adapter binds a `CapacityActionRecommendation` digest into a `SubjectRiskEvaluationRequest`
without Risk Authority depending on the Cloud Scaling package).
