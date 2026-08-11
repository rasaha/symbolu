# ADR — Risk Authority RA-8: Execution / Effect Reconciliation

**Status:** Proposed (discovery) — **decision required**. Not Accepted; a
canonical spec must wait on decisions D-A and D-B below.
**Date:** 2026-08-11
**Discovery baseline:** default HEAD `620955fc` (RA-7 merge, PR #1413).
**Companion:** `RISK_AUTHORITY_RA8_EXECUTION_EFFECT_RECONCILIATION_PLAN.md`
(full code-grounded discovery).
**Supersedes/relates:** RA-7 SPEC §4 (D1) and §19 ratified the RA-7/RA-8
boundary; this ADR takes RA-8 forward from that boundary.

---

## Context

RA-7 (Runtime / Trajectory Assurance) observes runtime behavior *during*
execution and emits a neutral `RUNTIME_RISK_ESCALATED` signal into RA-6. The
ratified RA-7 spec assigns *post-effect* concerns to RA-8: *"did the actual
execution and resulting effect match what was authorized, expected, and
claimed?"*

Discovery against live code (baseline `620955fc`) established:

1. **Decision Authority already owns a mature reconciliation kernel** —
   `ExecutionIntent` (authorized) / `ExecutionAttempt` (transport) /
   `ExecutionRecord` (observed effect, "never inferred") / `ReconciliationResult`
   / `CompensationRequirement` — with deterministic non-compensatory semantics, an
   idempotency ledger, tenant binding, authenticated ingestion, audit, and
   persistence. It is already reused by product layers (procurement, ai-hiring).
2. **It is unwired at both ends.** It is driven by DA's own `ExternalExecutionPort`
   (only an offline adapter ships), not by Agent Runtime; and it emits **audit
   events only** — never an `AuthorityReassessmentSignal` to RA-6.
3. **Agent Runtime and DA are import-isolated parallel worlds.** Agent Runtime
   executes via providers, reserves `execution_reference`/`result_digest` fields
   that are **always `None`**, carries **no `tenant_id`/`envelope_id`**, and is
   **forbidden by test** from importing `ugence_decision_authority`.
4. **No production trusted effect source exists** (only k8s cloud-scaling reads
   real state, domain-specific + fake backend); **no second-authority artifact
   exists** anywhere; **nothing emits `EXECUTION_EFFECT_MISMATCH`** (reserved for
   RA-8, hard-excluded from RA-7).

The governing question for this ADR: **should RA-8 compose the existing DA
reconciliation, or build a new subsystem?**

---

## Decision (directional — ratification pending on D-A/D-B)

**RA-8 composes the existing DA reconciliation kernel from a new sibling
integration package** (OPTION B), mirroring RA-7's package pattern. RA-8 does
**not** re-implement reconciliation, does **not** live inside DA, Agent Runtime,
or the RA leaf, and introduces **no second authority artifact**.

Proposed package: `packages/integration/risk-authority-execution-assurance/`,
depending on `ugence-decision-authority` (reconciliation kernel),
`ugence-risk-authority-status-runtime` (RA-6 intake), `ugence-risk-authority`
(neutral signal type), and `governance-contracts` (`ExecutionObservation` effect
port); observing Agent Runtime through the neutral event stream only.

One-way dependency direction (RA-7 pattern):
```
risk_authority (leaf) ◄─ RA-6 status-runtime ◄─ RA-8 execution-assurance ─► decision-authority
                                                       │ observes ▼ neutral event contract
                                                   agent-runtime (imports neither RA nor DA)
```

RA-8's own work is the **wiring DA cannot own**: (a) admit a trusted effect
observation into DA `ExecutionRecord`; (b) bridge Agent Runtime execution
receipts + the signed envelope to DA `ExecutionIntent`; (c) map a *material*
`ReconciliationResult` mismatch to a neutral `AuthorityReassessmentSignal` → RA-6.

### Invariants (non-negotiable, inherited from RA-5/6/7)

- `RiskAuthorizationEnvelope` remains the sole signed machine authority.
- RA-8 emits **evidence only**; it never revokes, mints, or advances epoch. RA-6
  is the sole lifecycle writer.
- Compensation is an advisory proposal requiring **fresh** governed authority;
  RA-8 never executes corrective actions.
- The RA leaf stays stdlib-only; provider/effect dependencies never enter it.
- No failure resolves to MATCHED; unfavorable/unknown dominates (non-compensatory).

---

## Options considered

- **A — inside DA.** Rejected: DA must not import Risk Authority (would invert
  dependency direction) and must stay reusable by non-RA products.
- **B — sibling integration package (chosen).** Composes DA + AR receipts + effect
  source + RA-6.
- **C — inside Agent Runtime.** Rejected: importing DA from Agent Runtime is a
  hard-forbidden dependency (enforced by test); AR must not own governance
  semantics.
- **D — inside RA leaf.** Rejected: would drag provider/effect/DA deps into the
  stdlib-only leaf.
- **E — unnecessary (DA suffices).** Rejected: DA is unwired to runtime and RA-6,
  has no production effect source, and no envelope binding — the authority loop is
  open.

---

## Consequences

- **Positive:** reuses a mature, tested kernel; small blast radius; preserves all
  boundaries; makes the authorize→attempt→effect→reconcile→reassess chain
  end-to-end auditable — the enterprise differentiator.
- **Cost/risk:** larger than RA-7 (must also wire a trusted effect source and
  bridge two import-isolated execution identities), but far smaller than a
  from-scratch subsystem. Verification strength is bounded by the effect source
  (provider self-report ≠ physical truth) — must not be overclaimed.
- **Follow-ups before a canonical spec (open decisions):**
  - **D-A (blocking):** effect-source trust model & ownership (generic connector
    layer / "Third-Party Gateway" vs part of RA-8; authenticated vs signed).
  - **D-B (blocking):** the Agent Runtime receipt seam + runtime↔DA correlation,
    respecting the import boundary.
  - **D-C:** fix conflicting-receipt masking (non-compensatory aggregation) and
    wire envelope binding — in DA or in RA-8.
  - **D-D:** add `SignalChangeType.EXECUTION_EFFECT_MISMATCH` (leaf schema) vs
    reuse an existing category.
  - **D-E:** final package name/home.

---

## Verdict

`RA8_ARCHITECTURE_DECISION_REQUIRED`. The composition direction is clear and
code-supported; ratify D-A and D-B before writing an implementation-ready RA-8
spec. Discovery only — no code, no RA-8 implementation, no PR.
