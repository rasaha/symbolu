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

1. **Defect (h) contained — no reference fallback in production.** `RiskAuthorityApplication`
   gains a `decision_authority: DecisionAuthorityPort`. In **production mode it is mandatory**:
   `decision_authority=None` and an explicit `ReferenceDecisionAuthority` both **fail closed at
   construction**, and any injected ruler must be `is_production_authoritative=True`. There is
   **no** reference decision-authority fallback in production. Reference behavior is available
   **only** when `production_mode=False`. (Consumer migration: see "Compatibility" below.)

2. **Production envelope / ActionGate containment.** Envelope issuance and action authorization
   are **Phase 5** (a separately-governed production ActionGate / provider seam) and are **not
   implemented**. In production mode, `issue_envelope` and `authorize_action` **fail closed**
   with a typed `ProductionContainmentError`; the in-package `ReferenceActionGate` /
   `EnvelopeIssuer` are conformance components and are **never** production enforcement. No
   production-mode execution-authority artifact can be minted through the facade — production
   Risk Authority integration **stops at a non-executable `RiskDecision`**. Reference /
   conformance mode retains the full flow for testing. *(Phase 5 is not implemented by this
   change.)*

3. **Neutral contracts** (`risk_authority.integrations`):
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

   Strict serialization: `from_dict` **rejects unknown fields** and a **missing
   `schema_version`**, and reads the executable flags through so a forged `executable=true` is
   **rejected**, never silently normalized (a rejected field can never disappear before the
   digest is computed).

4. **`RiskEvaluationSeam`** (`risk_authority.api`) — composes the kernel through the existing
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

## Trust-marker limitation (accepted, bounded)

`is_production_authoritative=True` is a **caller-forgeable boolean** that expresses the
*composition root's responsibility* to wire a genuine production adapter — it is **not** a
cryptographic or unforgeable trust boundary. A malicious dependency can set it. This is an
accepted limitation of this correction, bounded by two facts: (1) the seam result is **fixed
non-executable regardless** — even a lying dependency cannot make `executable` /
`authorization_performed` / `envelope_issued` true (the flags are structurally `False` and
`from_dict` rejects a forged `true`); and (2) production envelope / ActionGate paths are
contained irrespective of the marker. **Follow-up (separate PR):** replace the boolean with a
stronger production-binding mechanism (e.g. a trusted provider registry / signed provider
descriptor validated by the composition root). Not attempted here to keep the correction small.

## Compatibility & migration

`ugence-risk-authority` `0.1.0 → 0.2.0` (additive API, but **production construction semantics
intentionally become fail-closed**). Consumers pinning `>=0.1.0` (no upper bound) still resolve.
Public method *meanings* are unchanged in reference mode; in production mode the facade now
refuses a missing/reference ruler and contains envelope/authorize.

**Affected consumer:** `ugence-risk-authority-evidence-runtime` (RA-5) constructs the facade in
production mode and previously relied on the reference-ruler fallback and the production envelope
path. It is migrated in-repo to (a) inject an explicit production-authoritative
`decision_authority`, and (b) treat production envelope/authorize as Phase-5 (fail-closed) — its
end-to-end test now asserts a non-executable decision plus containment. No other of the five
`ugence-risk-authority` consumers (RA-4.5 runtime, RA-6, RA-7, RA-8) constructs the facade in
production mode, so none is affected. **Recommended follow-up:** consumers that need a real
production decision path should adopt a `ugence-decision-authority` adapter; bounded dependency
ranges (`>=0.2.0,<0.3`) can be set in a separate PR.

## Explicitly out of scope

No envelope issuance, ActionGate invocation, provider execution, readiness checking, retry,
rollback or effect verification. No RA-5 implementation. No Cloud Scaling Controller / Operations
change. No cloud-scaling-specific contract (the seam is domain-neutral; a future Phase-4
adapter binds a `CapacityActionRecommendation` digest into a `SubjectRiskEvaluationRequest`
without Risk Authority depending on the Cloud Scaling package).
