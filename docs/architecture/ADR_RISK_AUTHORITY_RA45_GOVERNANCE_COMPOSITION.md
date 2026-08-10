# ADR — Risk Authority RA-4.5: Additive Fail-Closed Governance Composition

**Status:** Accepted (documentation-only; supersedes the RA-4.5 substitution-adapter plan)
**Date:** 2026-08-10
**Owners:** Ugence platform architecture
**Related:**
- [`RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md`](./RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md) — the corrected design this ADR ratifies
- [`RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md`](./RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md) — the semantic parity audit that forced the correction
- [`RISK_AUTHORITY_RA45_ADAPTER_PLAN.md`](./RISK_AUTHORITY_RA45_ADAPTER_PLAN.md) — **SUPERSEDED** substitution plan (rejected alternative)
- PR #1396 — merged RA-1→RA-4 authority spine (merge commit `59bb4f27`)
- Issue #1397 (F-D), #1398 (F-G), #1399 (F-H) — tracked, separate follow-ups

> *This ADR changes **no** production code, package, wheel, API, schema, frozen
> identifier, serialization, digest, authority boundary, or historical record. It
> records an architecture decision in documentation only. No adapters are
> implemented, no RA-5 work is started, and no PR is opened by this decision.*

---

## Central decision

> **RA-4.5 integrates the production kernels `ugence-decision-authority` and
> `ugence-actiongate-provider` as *additive, fail-closed governance
> collaborators* — not as replacements for the Risk Authority reference
> components.** Risk Authority remains the platform's sole issuer and enforcer of
> machine execution authority (scope, delegation monotonicity, signed envelope,
> expiry, revocation, authority epoch, exact-action match). Decision Authority
> and ActionGate may **veto or restrict**; they may **never manufacture, refresh,
> or widen** authority Risk Authority has not issued.

Formally: `FinalAuthority ≤ RiskAuthority` and `FinalScope ⊆ RiskAuthorityScope`.

---

## Context

The original RA-4.5 plan
([`RISK_AUTHORITY_RA45_ADAPTER_PLAN.md`](./RISK_AUTHORITY_RA45_ADAPTER_PLAN.md))
proposed a **substitution** model: swap the in-package `ReferenceDecisionAuthority`
and `ReferenceActionGate` for adapters onto the shipped kernels, behind the
existing `DecisionAuthorityPort` / `ActionGatePort`, so the kernels would own the
binding ruling and the enforcement decision (§8, §9, §15 of that plan).

That plan **mandated a Phase 1 semantic parity audit before any adapter code**.
The audit
([`RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md`](./RISK_AUTHORITY_RA45_PHASE1_PARITY_AUDIT.md))
ran that gate and returned **RA45_BLOCKED** for the substitution model. Its
findings, re-verified here against current code:

- **`ugence-decision-authority`** is a human/committee/policy *decision-of-record*
  kernel (outcomes `ADVANCE/HOLD/REJECT/DEFER`; AI explicitly cannot bind). It has
  **no** authority `Scope`, **no** `Scope_issued ⊆ Scope_delegated` relation,
  **no** amount ceiling, **no** model-identity binding, **no** decision expiry,
  **no** revocation, and **no** authority epoch. Its binding outcome is
  caller-asserted, not control-derived.
- **`ugence-actiongate-provider`** decides on `action_type` **alone**. It verifies
  **no** signature, tenant (hard-coded `""`), actor, model, scope, time/expiry,
  revocation, epoch, amount, tools, data, or destination. Its typed
  `maximum_amount` / `allowed_region` / `required_approval` values are emitted
  *outputs*, not enforced *inputs*.
- Neither kernel signs or verifies an Ed25519 envelope; the RA
  `RiskAuthorizationEnvelope` and the unsigned production CER cannot be translated
  without re-authorizing.

Routing RA authority *through* these kernels would therefore make the system
enforce **strictly less** than the audited RA-1→RA-4 reference — silently
weakening F-A, F-B, F-E, monotonicity, expiry, revocation, epoch, and
signature/exact-action binding.

---

## Decision

1. **Risk Authority retains machine-authority ownership** end-to-end: control-
   derived authority, scope + monotonicity, envelope signing/verification, expiry,
   revocation, authority epoch, tenant/actor/model binding, and exact-action match
   stay RA-owned and RA-computed.
2. **Decision Authority contributes an organizational governance veto**
   (`ADVANCE` = no veto; `HOLD`/`DEFER` = non-executable hold; `REJECT` = deny),
   including its genuine strengths (SoD, required human approvals, non-AI binding).
   It never supplies a scope or an ALLOW.
3. **ActionGate contributes a supplementary `action_type` policy veto** behind a
   full RA envelope verification + scope match (`DENY`/`UNKNOWN` = veto;
   `ALLOW_WITH_CONSTRAINTS` = tightening obligations only).
4. **A new integration package owns the fail-closed composition engine** and the
   two governance adapters. `risk_authority` stays a stdlib-only leaf and imports
   neither kernel.
5. **Composition is monotone-restrictive:** `EffectiveAuthority = RA ∩
   GovernanceRestrictions ⊆ RA`. No dimension may be widened; permissions are
   never unioned.
6. **Failure is never ALLOW:** every unavailable/malformed/ambiguous state
   classifies to `DENY` or a non-executable disposition.
7. **F-D (#1397) stays separate** and is not closed by composition; unsupported
   dimensions (jurisdiction, autonomy, resource/target) are **not** silently
   mapped through the kernels or claimed as enforced.
8. **The signed `RiskAuthorizationEnvelope` remains the machine-execution
   authority;** no second authorization artifact is minted.

---

## Consequences

- **Cleaner separation of authority** — human/organizational governance is
  explicitly distinct from machine execution authority.
- **No weakening of RA guarantees** — F-A/F-B/F-E and all monotonicity/validity/
  crypto invariants are preserved by construction.
- **A more explicit composition layer** — vetoes, holds, and restrictions are
  first-class and fail-closed.
- **Production kernels remain reusable** — they are consulted for their genuine
  competencies (organizational governance; action-type policy) without being
  overloaded into a machine-authority role they cannot fulfill.
- **An additional integration package is required** (tentatively
  `packages/integration/risk-authority-runtime/`), owning composition one-way over
  all three packages, with no dependency cycle and the leaf untouched.
- **F-D remains separate** — jurisdiction/autonomy/resource enforcement is
  tracked in #1397 and is out of RA-4.5 scope.
- **Maturity language is unchanged** — RA-1→RA-4 remains a conformance/reference
  implementation; production maturity still requires the RA-4.5 composition to be
  built and verified.

---

## Rejected alternative — direct substitution adapters

**Rejected:** the original plan's `KernelDecisionAuthorityAdapter` /
`KernelActionGateAdapter` as *substitutes* that place the kernels behind the ports
as the owners of the binding ruling and enforcement.

**Why rejected:** the parity audit proved the kernels **cannot represent or
enforce** the RA authority-critical semantics (authority scope + `⊆`
monotonicity, amount ceiling, model-on-binding, decision expiry, revocation,
authority epoch, offline signature verification, and exact-action scope matching).
Substitution would make production enforce **less** than the audited reference —
the precise failure the audit gate exists to prevent. The binding outcome
vocabularies are also a category mismatch (`ADVANCE/HOLD/REJECT/DEFER` vs
`ALLOW` + `Scope`), and the DA kernel's binding outcome is caller-asserted rather
than control-derived, reopening the F-A trap. Substitution is therefore
architecturally invalid; additive fail-closed composition is adopted instead.

---

## Status of implementation

**None.** This ADR and the corrected plan are documentation only. Implementation
is gated behind the readiness criteria in
[`RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md §17`](./RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md).
No adapters are written, no RA-5 work is begun, and no PR is opened.
