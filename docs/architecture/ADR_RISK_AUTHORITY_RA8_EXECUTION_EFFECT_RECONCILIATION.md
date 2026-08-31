# ADR — Risk Authority RA-8: Execution / Effect Reconciliation

**Status:** **ACCEPTED (ratified).** Supersedes the discovery ADR of the same name
(verdict `RA8_ARCHITECTURE_DECISION_REQUIRED`, discovery commit `19b0dc33`).
**Date:** 2026-08-11
**Baseline:** default HEAD `620955fc` (RA-7 merge, PR #1413); re-verified live.
**Canonical spec:** `RISK_AUTHORITY_RA8_SPEC.md` (this ADR records the decision;
the spec carries the full ratified detail).
**Supporting (superseded) discovery:**
`RISK_AUTHORITY_RA8_EXECUTION_EFFECT_RECONCILIATION_PLAN.md`.

---

## Context

RA-7 (Runtime / Trajectory Assurance, merged) observes runtime behavior *during*
execution and emits `RUNTIME_RISK_ESCALATED` into RA-6. The ratified RA-7/RA-8
boundary assigns *post-effect* concerns to RA-8: *did the actual execution and
resulting effect match what was authorized and expected — and if not, should that
reassess future machine authority?*

Discovery (re-verified against live code at `620955fc` — see the spec §0 table)
established, and ratification confirmed:

1. **Decision Authority already owns a mature reconciliation kernel** —
   `ExecutionIntent` / `ExecutionAttempt` / `ExecutionRecord` (observed, never
   inferred) / `ReconciliationResult` / `CompensationRequirement` — with
   non-compensatory semantics, an idempotency ledger, tenant binding,
   authenticated ingestion, audit, and persistence; already reused by product
   layers (procurement, ai-hiring).
2. **It is unwired at both ends:** driven by DA's own `ExternalExecutionPort` (only
   offline/conformance adapters ship), not by Agent Runtime; and it emits **audit
   events only** — never an `AuthorityReassessmentSignal` into RA-6.
3. **Agent Runtime and DA are import-isolated parallel worlds.** AR reserves
   `execution_reference`/`result_digest` (always `None`), carries **no**
   `tenant_id`/`envelope_id`, and is **forbidden by test** from importing
   `ugence_decision_authority`.
4. **No production trusted effect source; no second-authority artifact; nothing
   emits `EXECUTION_EFFECT_MISMATCH`** (reserved for RA-8, hard-excluded from RA-7).
5. **M-1 (confirmed live):** DA `_compare` keys the primary-outcome verdict off
   `latest = records[-1]`; a `FAILED`-then-`SUCCEEDED` sequence on one external
   request resolves to the latest favorable → a later favorable record can mask an
   earlier material unfavorable one.

The governing question: **should RA-8 compose the existing DA reconciliation, or
build a new subsystem?**

## Decision

**RA-8 composes the existing DA reconciliation kernel from a new sibling
integration package (OPTION B).** RA-8 does **not** re-implement reconciliation,
does **not** live inside DA / Agent Runtime / the RA leaf, and introduces **no
second authority artifact**. Its own work is the wiring DA cannot own: (a) admit a
trusted effect observation into DA `ExecutionRecord`; (b) bridge Agent Runtime
execution receipts + the signed envelope to DA `ExecutionIntent`; (c) apply safe
non-compensatory aggregation; (d) map a *material* `ReconciliationResult` mismatch
to a neutral `AuthorityReassessmentSignal` → RA-6.

The five discovery decisions are now **ratified** (full rationale in the spec):

| Dec | Decision | Ratified outcome |
|---|---|---|
| **D-A** | Effect-source / Third-Party trust model | **OPTION B** — neutral `EffectObservationPort` (governance-contracts `ExecutionObservation`); provider connectors = separate Third-Party Gateway, **FUTURE**; authenticated/delegated ingress (not per-receipt crypto); reference adapter **refused in production**. Integrity ≠ authenticity. |
| **D-B** | AR → reconciliation correlation | RA-8-owned neutral **`ExecutionCorrelation`**, minted at authorize-time from `GovernedExecutionDecision` (`envelope_id`, `action_digest`, `correlation_id`), joined to AR's neutral event stream; **one optional additive AR seam** (populate reserved `execution_reference`/`result_digest`). **No AR↔DA↔RA-8 cross-import.** `authority_ref = envelope_id`. |
| **D-C** | Aggregation + envelope binding | **A (non-compensatory) + C (explicit finality/version supersession)** — a material unfavorable record is never masked by a later favorable one absent explicit supersession. **M-1 closed at the RA-8 boundary** (over the full record set), no DA change required. Envelope bound intrinsically. |
| **D-D** | RA-6 signal category | **OPTION B** — add additive neutral `SignalChangeType.EXECUTION_EFFECT_MISMATCH`; distinct audit semantics; non-authority; only material mismatch emits. |
| **D-E** | Package ownership / name | **OPTION B** — `packages/integration/risk-authority-execution-assurance/`; deps DA + RA-6 status-runtime + RA leaf + governance-contracts (+ provider-framework). |

### Invariants (non-negotiable; inherited from RA-5/6/7)

`RiskAuthorizationEnvelope` remains the sole signed machine authority · RA-8 emits
**evidence only** (never revoke/mint/epoch; RA-6 is the sole lifecycle writer) ·
compensation is an advisory proposal requiring **fresh** governed authority · the
RA leaf stays stdlib-only · no failure resolves to MATCHED (unfavorable/unknown
dominates) · `MATCHED` cannot resurrect revoked authority · no third execution
ledger.

## Options considered

- **A — inside DA.** Rejected: DA must not import Risk Authority (would invert the
  dependency direction) and must stay reusable by non-RA products.
- **B — sibling integration package (chosen).** Composes DA + AR receipts + effect
  source + RA-6, mirroring the RA-7 package pattern.
- **C — inside Agent Runtime.** Rejected: importing DA from AR is hard-forbidden
  (enforced by test); AR must not own governance/reconciliation semantics.
- **D — inside the RA leaf.** Rejected: would drag provider/effect/DA deps into the
  stdlib-only leaf.
- **E — unnecessary (DA suffices).** Rejected: DA is unwired to runtime and RA-6,
  has no production effect source, and no envelope binding — the authority loop is
  open.

## Consequences

- **Positive:** reuses a mature, tested kernel; small blast radius; preserves every
  boundary; makes the authorize→attempt→effect→reconcile→reassess chain end-to-end
  auditable (the enterprise differentiator); closes M-1 and the envelope-binding
  gap architecturally.
- **Cost/risk:** larger than RA-7 (must also wire a trusted effect source and
  bridge two import-isolated execution identities), but far smaller than a
  from-scratch subsystem. **Verification strength is bounded by the effect source**
  (provider self-report ≠ physical truth) — must not be overclaimed. The reference
  milestone ships reference-grade (authenticated ingestion + content-hash
  integrity), with signed receipts and production connectors as FUTURE.
- **Compatibility:** every change is additive (spec §33). No envelope schema change;
  no required DA change; one optional additive AR seam; one additive RA-6 enum
  member.

## Verdict

`RA8_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`. D-A–D-E are resolved, the
favorable-mask issue is architecturally closed, and no authority-critical
placeholder remains. Documentation / architecture only — no code, no RA-8
implementation, no PR.
