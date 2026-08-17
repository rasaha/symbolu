# ADR — RA-5: Trusted Evidence & Control Assurance for Risk Authority

- **Status:** **Accepted (ratified).** The preconditions that gated this ADR are
  resolved in the canonical spec `RISK_AUTHORITY_RA5_SPEC.md` (its §1 ledger); the
  companion plan `RISK_AUTHORITY_RA5_TAP_CONTROL_ASSURANCE_PLAN.md` holds the
  long-form rationale. Acceptance is of the *design*; RA-5 *implementation*
  remains a separate, future, reviewed milestone.
- **Date:** 2026-08-10 (ratified same day)
- **Baseline:** default head `143f9f3f` (merge of PR #1402). RA-1→RA-4 (#1396) and
  RA-4.5 (#1402) merged and stable.
- **Verdict:** `RA5_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`
  (was `RA5_READY_WITH_PRECONDITIONS` at discovery).

## Context

Risk Authority's non-compensatory control gate today consumes **caller-asserted**
control statuses: `ControlResultInput{control_id, status:str, evidence_ids}` is
supplied to `evaluate()`, stamped into a `ControlResult`, and trusted
(`api/dependencies.py:206-273`, `api/schemas.py:47-56`). The evidence-admission
seam (`EvidenceAdmissionPort`, `ControlEvidenceRecord`) exists but is **invoked
nowhere**; the `EVIDENCE_PENDING → EVIDENCE_COMPLETE → CONTROL_EVALUATED`
transitions are stamped with no admission or evaluation behind them. This is correct
for RA-1→RA-4 reference/conformance mode, but in production it means a caller can
mint machine authority by asserting `PASS`.

RA-5 ("TAP + Control Assurance", roadmap `README.md:31-36`) is the milestone that
closes this. Discovery surfaced two facts that shape the decision:

1. The consolidated **RA Architecture Specification v1.1 is cited but absent** from
   the repo.
2. The productized component named **"TAP" (`ugence-tap-provider`) is an
   assertion-support scorer** (a peer of ActionGate: SUPPORTED / UNSUPPORTED /
   CONSTRAINED / INDETERMINATE), **not** the evidence-**admission** pipeline that
   RA-5's "TAP" (spec §9: provenance/integrity/freshness) requires. The
   evidence-admission role has no productized owner; the `truth_assurance_pipeline`
   tree is synthetic research.

## Decision

1. **RA-5 attaches upstream of envelope issuance, inside `ugence-risk-authority`,
   behind ports — never as an RA-4.5 governance veto.** RA-4.5's additive-composition
   invariants (`FinalAuthority ≤ RiskAuthority`, `FinalScope ⊆ RiskAuthorityScope`)
   remain true by construction because RA-5 changes only *whether/what scope RA
   issues*.

2. **Two distinct trust questions, two ports.** Evidence *admission* ("is this
   evidence trustworthy?" — provenance/integrity/freshness) stays behind the existing
   `EvidenceAdmissionPort`. Control *assurance* ("does admitted evidence satisfy
   control C?") gets a **new `ControlAssurancePort`**. These never blur.

3. **Risk Authority keeps the non-compensatory aggregation rule; RA-5 supplies only
   a *trusted producer* of `ControlResult`.** RA-5 does not move the control-
   satisfaction rule out of RA and introduces **no new authorization artifact** —
   the Ed25519-signed `RiskAuthorizationEnvelope` remains the sole machine-execution
   authority.

4. **Production integration lives in a new leaf integration package**
   (proposed `ugence-risk-authority-evidence-runtime`), mirroring the RA-4.5
   runtime package. Dependency direction is one-way (integration → providers → RA
   ports); `ugence-risk-authority` stays a stdlib-only leaf. TAP/provider
   dependencies never enter the RA leaf.

5. **Trusted results and admitted evidence are intrinsically bound** to
   `tenant / risk_case / policy_digest / workflow_ir_digest / control_id`, plus
   evaluator attribution — storage-partition isolation is insufficient. Any mismatch
   fails closed (treated as `MISSING`).

## Rejected alternatives

- **Wire the caller-asserted `ControlResult` as production-trusted** — rejected:
  reintroduces the F-A class of bug (permissive caller input minting authority).
- **Adopt `ugence-tap-provider` as the *admission* pipeline** — rejected: it scores
  assertion support, does not admit evidence, has no freshness/revocation model, and
  binds neither tenant nor workflow first-class. It is a candidate *Control-Assurance
  evaluator*, not the admission owner.
- **Build a new evidence/authority component inside Risk Authority** — rejected:
  duplicates existing responsibilities and would make RA the evidence authority,
  violating the ownership matrix.
- **Attach RA-5 as an additive governance veto in RA-4.5** — rejected: violates "no
  upstream permissive result upgrades RA" and the RA-4.5 non-goal fence
  (`RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md:648-653`).

## Consequences

- RA-5 **reinforces** F-A (removes caller-asserted control status from the production
  authority path) and preserves F-E (duplicate-control fail-closed grouping).
- No new state is added — the RA state machine already models
  `EVIDENCE_PENDING/EVIDENCE_COMPLETE/CONTROL_EVALUATED`; RA-5 only adds real guards.
- Adopting `ugence-tap-provider` as the evaluator requires a ratified
  coverage→binary **fail-closed** mapping (a `CONSTRAINED`/partial result is **not**
  `PASS`), so no coverage score can compensate a failed mandatory control.
- The preconditions are now **resolved** (`RISK_AUTHORITY_RA5_SPEC.md` §1): the
  in-repo RA-5 spec is ratified, the evidence-admission owner/naming is settled
  (Outcome C — neutral admission seam; `ugence-tap-provider` = evaluator
  candidate, not admission owner), the Control-Assurance boundary is fixed (new
  `ControlAssurancePort`; aggregation rule stays in RA), the trust-binding
  contracts are defined, and reference-mode conformance is preserved.
  Implementation of RA-5 remains a distinct, future, separately-reviewed
  milestone — this ADR accepts the *design*, not any code.

## Amendment (2026-08-17) — cross-reference only; no RA-5 decision changed

[`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
ratifies a **platform-wide** trusted evidence admission/verification authority under the
"TAP" umbrella that `RISK_AUTHORITY_RA5_SPEC.md` §3.2 deliberately retained without naming
an owner. Recorded here so the two are not read as competing evidence authorities:

- **RA-5's `EvidenceAdmissionPort` remains the RA-scoped instance** — admission of *control
  evidence* backing a `ControlResult`, bound to
  `tenant / risk_case / policy_digest / workflow_ir_digest / control_id`, inside
  `ugence-risk-authority`. Its scope, contracts and ports are **unchanged**.
- **Extending that port platform-wide was considered and rejected** by the new ADR (§25.3):
  it would force `governance-contracts` and Readiness to import Risk Authority, which is
  prohibited, or silently widen a ratified RA-scoped contract without review.
- **The non-collapse rule is preserved and extended** — assertion-support scoring
  (`ugence-tap-provider`) and evidence admission/verification remain **different trust
  questions, never merged**. `ugence-tap-provider` stays a Control-Assurance evaluator
  *candidate*, **not** the admission or verification owner.
- **A TAP evidence-verification receipt is not an authorization artifact.** Decision 3
  stands: the Ed25519-signed `RiskAuthorizationEnvelope` remains the sole machine-execution
  authority, and RA keeps the non-compensatory aggregation rule.
- **Alignment** of RA-5's seam with the platform receipt is a separate, later,
  separately-reviewed decision (DD-6 in that ADR).

**No RA-5 decision, precondition resolution, port, contract, verdict or scope statement is
changed by this amendment.**

## Scope statement

Documentation/design only. No production code changed, no RA-5 package or adapters
created, no RA-4.5 code changed, no #1397/#1403/#1404 work folded in, no PR opened.
