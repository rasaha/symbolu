# Risk Authority RA-8 — Implementation Plan (Ratified, not yet implemented)

> **Status:** Ratified plan — companion to `RISK_AUTHORITY_RA8_SPEC.md`.
> **Type:** DOCUMENTATION ONLY. No code, no package, no PR. Baseline `620955fc`.
> **Verdict carried forward:** `RA8_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`.

This plan sequences the RA-8 reference milestone. It builds **only** the wiring DA
cannot own; it reuses the DA reconciliation kernel, RA-6 intake, the RA leaf signal
type, and the governance-contracts effect seam. It follows the RA-7 delivery shape.

## Package

`packages/integration/risk-authority-execution-assurance/`
(dist `ugence-risk-authority-execution-assurance`, import
`ugence_risk_authority_execution_assurance`). Deps: `ugence-decision-authority`,
`ugence-risk-authority-status-runtime`, `ugence-risk-authority`,
`ugence-governance-contracts`, `ugence-governance-provider-framework` (optional).
Observes Agent Runtime via the neutral, duck-typed event contract (no AR import
required). Stdlib + those deps only.

## Modules (mirrors the RA-7 layout)

| Module | Responsibility | Reuses |
|---|---|---|
| `contracts.py` | `ExecutionCorrelation`; neutral `EffectAssuranceAssessment`; `CONFLICTED`/`UNVERIFIABLE` terms | DA statuses, RA leaf signal |
| `correlation.py` | mint `ExecutionCorrelation` at authorize-time from `GovernedExecutionDecision`; join AR event by `correlation_id` + `proposal_fingerprint` | `risk-authority-runtime` contracts |
| `ingress.py` | trusted effect-observation ingress (reference adapter; refuse in production) | governance-contracts `ExecutionObservation`, DA `authorize_execution` |
| `intent_builder.py` | build DA `ExecutionIntent` with `authority_ref = envelope_id`, `execution_idempotency_key = AR key` | DA execution service |
| `aggregation.py` | **non-compensatory** safe aggregation over the full record set + explicit finality/version supersession (closes M-1) | DA `ExecutionRecord`/`ReconciliationResult` |
| `assurance.py` | compose DA reconciliation; produce `EffectAssuranceAssessment` | DA reconciliation service |
| `handoff.py` | map material mismatch → neutral `AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)` → RA-6 intake | RA-6 `AuthorityReassessmentSignalPort` |
| `event_adapter.py` | read AR neutral events (duck-typed `.type`/`.detail`/digests) | — |

## Sequence

1. **Leaf enum (additive):** add `SignalChangeType.EXECUTION_EFFECT_MISMATCH`
   (D-D). Additive member; fail-closed-on-unknown already present. Packaging test:
   no authority field, no grant/token.
2. **Correlation (D-B):** `ExecutionCorrelation` + authorize-time mint + event
   join. Assert no AR/DA cross-import (source-scan + clean-room import test, RA-7
   pattern).
3. **Effect ingress (D-A):** adopt `ExecutionObservation` as `EffectObservationPort`;
   reference adapter; **refuse reference adapter in production** (F-1). Authenticated
   ingress; integrity ≠ authenticity documented.
4. **Intent + binding (D-C/M-2):** build `ExecutionIntent` with
   `authority_ref = envelope_id`; enforce the intrinsic binding tuple; reject
   wrong tenant/workflow/envelope/action/attempt/stale.
5. **Safe aggregation (D-C/M-1):** non-compensatory dominance over the full record
   set; explicit finality/version supersession only; `CONFLICTED` on conflict.
6. **Reconciliation composition:** call DA reconciliation; wrap the verdict with
   the safe aggregation; produce `EffectAssuranceAssessment`.
7. **RA-6 handoff (D-D/§22):** emit the neutral signal on **material** mismatch
   only, per the §7 mapping; RA-6 decides the consequence.
8. **(Optional) AR seam (§11):** populate `execution_reference`/`result_digest`
   from `ToolResult` — additive, backward-compatible, imports nothing. Skip if the
   neutral event digests suffice.

## Tests (deny-heavy; spec §30, items 1–42)

Contracts / no-authority-field · ingress trust boundary (malformed, untrusted,
wrong tenant/workflow/envelope/action/attempt) · **M-1 favorable-cannot-mask-
unfavorable** · finality supersession only explicit · CONFLICTED on conflicting
observers · duplicate/replay · UNVERIFIABLE on absent effect source · reconciliation
fail-closed · mismatch → neutral RA-6 signal → real targeted revoke · MATCHED
cannot resurrect · RA-8 cannot revoke/mint · compensation cannot self-execute /
requires fresh authority · RA-7/RA-6/AR unchanged · DA reused (not re-implemented)
· ACP separate · no second authority artifact · no third execution ledger · RA leaf
independently installable (offline `--no-index`).

## Explicitly out of scope (FUTURE / SEPARATE)

Production Third-Party Gateway connectors · signed external receipts / attestations
· distributed effect observation · DA `_compare` hardening (additive) ·
reconciliation SLA/timing model · ACP · GRC reporting · RA-7 trajectory monitoring.

## Honesty / maturity statement

Reference-grade post-effect reconciliation that can cause previously-valid, signed
machine authority to be reassessed through the existing RA-6 lifecycle — with
delegated persistence (DA), authenticated (not cryptographically signed) effect
ingress, and provider-self-report trust bounded by the configured effect source.
**Not** production-distributed, cryptographically-attested, physical-truth, or
zero-window. `RiskAuthorizationEnvelope` remains the sole signed machine authority.
