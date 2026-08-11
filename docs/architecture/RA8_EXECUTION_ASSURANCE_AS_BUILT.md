# RA-8 Execution / Effect Reconciliation — As-Built

> **Status:** Implemented (reference-grade). Companion to the ratified
> `RISK_AUTHORITY_RA8_SPEC.md`, the ADR, and `RISK_AUTHORITY_RA8_IMPLEMENTATION_PLAN.md`.
> **Package:** `packages/integration/risk-authority-execution-assurance/`
> (dist `ugence-risk-authority-execution-assurance`, import
> `ugence_risk_authority_execution_assurance`, version `0.1.0`).
> **Baseline:** ratification commit `d495bb51` (default HEAD `620955fc` + RA-8 docs).

RA-8 closes the loop from an **observed external effect** back to **machine
authority**: it correlates a governed authority context, the Agent Runtime
execution attempt, and a trusted external effect observation; composes the existing
Decision Authority reconciliation kernel under a safe, non-compensatory
aggregation; and — on a *material* post-effect mismatch — emits a neutral
`AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)` into the RA-6 intake.

**RA-8 OBSERVES, CORRELATES, AGGREGATES, AND ASSESSES POST-EFFECT. RA-6 OWNS
AUTHORITY CONSEQUENCES.** `RiskAuthorizationEnvelope` remains the sole signed
machine authority; Decision Authority remains the sole owner of
execution/reconciliation records.

## Modules

| Module | Responsibility |
|---|---|
| `contracts.py` | `ExecutionCorrelation`, `EffectObservation`, `EffectFinality` (PENDING/PARTIAL/FINAL), `EffectReconciliationOutcome` (+ `CONFLICTED`/`UNVERIFIABLE`), `EffectReasonCode`, `EffectAssuranceAssessment`. Reuses DA `BusinessOutcome`/`Finality`/`ReconciliationStatus`. |
| `correlation.py` | `GovernedAuthorityContext`, `ExecutionCorrelator` — mint the correlation, enforce the intrinsic binding tuple (wrong tenant/workflow/envelope/action/attempt fail closed). |
| `event_adapter.py` | Duck-typed neutral Agent Runtime event → `RuntimeAttemptEvidence`; join by `correlation_id` + `proposal_fingerprint`. No AR import. |
| `ingress.py` | `TrustedEffectIngress` + `ReferenceEffectSourceAuthenticator` (F-1: refused in production); `normalize_execution_observation` reuses the governance-contracts seam; malformed-truthy hardening. |
| `aggregation.py` | `safe_aggregate` — non-compensatory dominance over the full record set + explicit finality/version supersession. **Closes M-1.** |
| `reconciler.py` | `DecisionAuthorityReconciler` seam + `ReferenceDecisionAuthorityReconciler` (composes a real DA `ReconciliationService` over DA's in-memory repo; F-1). `ExpectedEffect`, `ReconciliationEvidence`. |
| `assurance.py` | `EffectAssuranceService` composition owner + `.reference()` factory. |
| `handoff.py` | Map a material assessment → `EXECUTION_EFFECT_MISMATCH` signal → RA-6 intake. |

## Ratified-decision realization

- **D-A** — neutral `EffectObservationPort`: RA-8 reuses governance-contracts
  `ExecutionObservation` via `normalize_execution_observation`; authenticated/
  delegated ingress; the reference authenticator is **refused in production**;
  concrete connectors (Third-Party Gateway) remain FUTURE. Integrity ≠ authenticity.
- **D-B** — RA-8-owned `ExecutionCorrelation`, minted at authorize-time from the
  governed context, joined to the AR event stream; `authority_ref = envelope_id`;
  **no AR↔DA↔RA-8 cross-import**. The optional additive AR seam
  (`execution_reference`/`result_digest`) was **not** required — RA-8 derives attempt
  evidence from the neutral event contract (spec §5 Q4, §11: seam is optional).
- **D-C** — non-compensatory aggregation (A) + explicit finality/version
  supersession (C). **M-1 closed at the RA-8 boundary**, no DA change. Envelope
  bound intrinsically.
- **D-D** — additive leaf enum member `SignalChangeType.EXECUTION_EFFECT_MISMATCH`
  (the single ratified leaf change), wired into the RA-6 `ReferenceReassessmentDecider`
  revoke-envelope branch exactly as the RA-7 `RUNTIME_RISK_ESCALATED` category is
  (restrictive-only; RA-6 owns the consequence).
- **D-E** — sibling integration package `risk-authority-execution-assurance`.

## The M-1 closure

DA's internal `_compare` keys the primary-outcome verdict off `records[-1]`
(latest-wins, confirmed live). RA-8's `safe_aggregate` runs over the **full** record
set before trusting any single-record verdict:

- a material unfavorable **final** effect is never masked by a later favorable
  record of a *different* effect identity (`FAILED`-then-`SUCCEEDED` → `CONFLICTED`,
  not `MATCHED`);
- supersession is explicit/narrow — same effect identity, `PARTIAL → FINAL` only;
- conflicting trusted observers → `CONFLICTED`; duplicate distinct real effects →
  `MANUAL_REVIEW`; not-yet-final → `PARTIAL`/`UNKNOWN`, never a premature `MATCHED`.

No failure, malformed input, wrong binding, replay, or conflict becomes `MATCHED`.
A false RA-8 mismatch can cost availability but can never widen authority.

## Test coverage

| Suite | Result |
|---|---|
| RA-8 execution-assurance (this package) | **163 passed** |
| — includes the ratified deny-heavy 42-case adversarial matrix (`test_adversarial.py`), the M-1 aggregation suite, the real DA + real RA-6 end-to-end, and packaging/boundary tests | |
| RA leaf (`risk_authority`) | 113 passed (carries the additive category) |
| RA-6 status-runtime | 72 passed |
| RA-7 runtime-assurance | 100 passed (leaf-enum boundary updated for D-D) |
| Decision Authority | 79 passed (reused, not re-implemented) |
| governance-contracts | 48 passed |
| RA-4.5 / RA-5 runtime | 77 passed |
| Agent Runtime | 340 passed, 2 skipped (decoupled; no RA/DA import) |
| Isolated-install verifier | PASS (first-party wheels; index only for pydantic) |

## Implemented · Reference-only · Delegated · Future

**Implemented:** `ExecutionCorrelation` + intrinsic binding; trusted effect ingress
(reference authenticator, F-1); governance-contracts observation normalization;
`authority_ref = envelope_id` binding; safe non-compensatory aggregation + finality
supersession (M-1 closed); DA reconciliation composition; neutral RA-6 handoff
(`EXECUTION_EFFECT_MISMATCH`); the additive leaf enum member.

**Reference-only (refused in production):** the reference effect-source
authenticator; the reference DA reconciler (in-memory DA persistence).

**Delegated:** durable persistence of execution/reconciliation records (Decision
Authority); the authenticated lifecycle write + reassessment consequence (RA-6);
compensation execution (a fresh governed action through Risk Authority → RA-4.5 →
ActionGate → Agent Runtime).

**Future / separate:** production Third-Party Gateway connectors; signed external
receipts / attestations; globally-distributed effect observation; a DA `_compare`
non-compensatory hardening (additive); a reconciliation SLA/timing model; ACP; GRC.

## Maturity statement (conservative)

RA-8 provides **reference-grade execution/effect reconciliation** that correlates
governed machine authority, execution attempts, trusted effect observations,
Decision Authority reconciliation, and RA-6 reassessment. It is explicitly **not**:

- cryptographically-attested external truth (integrity ≠ authenticity; hash ≠ signature),
- a production Third-Party Gateway,
- globally distributed or zero-window,
- ACP or GRC,
- another authority subsystem.

Verification strength is bounded by the configured effect source: where the only
effect source is a provider self-report, RA-8 verifies the *reported* effect, not
physical-world truth.
