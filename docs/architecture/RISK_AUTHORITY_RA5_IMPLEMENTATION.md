# Risk Authority RA-5 — Implementation Notes

> **Status:** Implemented and locally / CI-equivalent verified; pending
> independent adversarial audit. Not called production-ready. Post-issuance
> continuous assurance and production deployment validation remain out of scope.
> **Design source of truth:** `RISK_AUTHORITY_RA5_SPEC.md` (ratified). In any
> conflict, the ratified SPEC governs; this file records how the implementation
> realizes it.
> **Baseline:** default head `143f9f3f` (merge of PR #1402) + the ratified RA-5
> docs commit. RA-1→RA-4 (#1396) and RA-4.5 (#1402) unchanged and not reopened.

## Where RA-5 sits relative to the rest of the spine

| Layer | Responsibility | Status under RA-5 |
|---|---|---|
| **RA-1→RA-4** | machine-authority spine: WorkflowIR → non-compensatory control gate → RiskEngine → Decision Authority → Ed25519 `RiskAuthorizationEnvelope` | **unchanged.** RA stays a stdlib-only leaf; the 97-test suite is untouched. |
| **RA-4.5** | downstream governance composition (`FinalAuthority ≤ RiskAuthority`, `FinalScope ⊆ RiskAuthorityScope`); wraps, never re-mints, the envelope | **unchanged.** RA-5 is upstream of the envelope; the 77-test suite is untouched; the RA-4.5 runtime package is not modified or depended upon. |
| **RA-5** | trusted evidence → trusted `ControlResult` production path *upstream* of RA authorization | **new.** Adds two production port implementations + a composition root; strengthens the RA contracts with trust bindings. |

## What changed, precisely

**Risk Authority leaf (`packages/risk_authority`, still stdlib-only):**

- `domain/evidence.py` — `ControlEvidenceRecord` extended into the canonical
  **AdmittedEvidence** contract (RA-5 §6): `schema_version`, `workflow_ir_digest`,
  `policy_digest`, `admitted_at`, `producer`/`producer_version`, `risk_case_id`,
  plus spec-name aliases and a deterministic `evidence_integrity_digest` used for
  tamper detection. Fail-closed `__post_init__` validation (unknown schema,
  impossible timestamps, negative freshness window, empty required identifiers).
- `domain/controls.py` — `ControlResult` extended (RA-5 §7) with the binding tuple
  (`tenant_id`, `risk_case_id`, `workflow_ir_digest`, `policy_digest`) and evaluator
  attribution (`assurance_engine`, `assurance_version`); `has_production_bindings()`.
  Extended, never forked — reference construction and the 97-test suite are intact.
- `domain/binding.py` — **new.** The authoritative RA-side binding re-check (§8):
  `CaseBindingContext`, `AdmittedContext`, `binding_violations`,
  `usable_control_results`. Defense-in-depth over storage-partition isolation.
- `integrations/control_assurance.py` — **new.** The `ControlAssurancePort`
  contract (§4/§5): `ControlAssuranceRequest`, `ControlAssuranceResult`,
  `ReferenceControlAssurance`, and `bind_control_result` (freshness monotonicity,
  §7.1). Provider-neutral, stdlib-only.
- `api/dependencies.py` — explicit **production path**: `evaluate_with_evidence`
  (admit → assure → RA re-check → persist trusted results → existing RiskEngine),
  strengthened state guards bound to real artifacts (§10), and a hard rejection of
  the caller-asserted reference `evaluate()` when production mode is active (§12).
  Mode is explicit; incomplete production config fails closed at construction.

**New integration package `packages/integration/risk-authority-evidence-runtime`
(`ugence-risk-authority-evidence-runtime`):**

- `admission.py` — `ProductionEvidenceAdmission` (behind RA's `EvidenceAdmissionPort`):
  provenance/integrity/freshness/schema/attribution, fail-closed.
- `tap_control_assurance.py` — `TapControlAssurance` adapts the **real**
  `ugence-tap-provider` onto `ControlAssurancePort`.
- `outcome_mapping.py` — the ratified fail-closed TAP-outcome → `ControlStatus`
  mapping (§9); `evidence_coverage` used only as the binary full-support gate.
- `runtime.py` — `RiskAuthorityEvidenceRuntime`, the explicit production
  composition root (reuses the RA engine/issuer; reimplements nothing).

## The security property this establishes

> **A caller-supplied `status="PASS"` cannot produce production authority.**

In production mode the caller-asserted control path is disabled; a required
control is satisfied only by a trusted `ControlResult` that (a) was produced by
the `ControlAssurancePort` from **admitted** evidence, (b) maps `PASS` only from
an unambiguous fully-supported outcome, and (c) passes RA's authoritative binding
re-check against the exact current tenant/case/workflow/policy/control context and
its still-fresh backing evidence. Any mismatch, staleness, tamper, outage, or
partial/ambiguous outcome fails closed (`MISSING`/`UNKNOWN`/`FAIL`) and mints no
authority. The Ed25519-signed `RiskAuthorizationEnvelope` remains the **sole**
machine-execution authority; RA-5 adds hash-binding + attribution, not signatures.

## Explicitly NOT claimed / NOT in scope

No continuous assurance; no post-issuance evidence revocation of live envelopes;
no RA-6/RA-7/RA-8; no production HSM/KMS; no second authorization artifact; no
changes to Decision Authority or ActionGate semantics; no F-D (#1397) / F2 (#1403)
/ RT-1 (#1404) work. Transport/storage trust is assumed adequate for RA-5 (§13).

## Verification (local / CI-equivalent)

| Suite | Result |
|---|---|
| RA-1→RA-4 baseline (`packages/risk_authority/tests`) | 97 passed (unchanged) |
| RA-4.5 runtime (`packages/integration/risk-authority-runtime/tests`) | 77 passed (unchanged) |
| RA-5 trusted-evidence suite (`.../risk-authority-evidence-runtime/tests`) | 63 passed |
| TAP provider | 82 passed |
| Decision Authority / ActionGate / governance framework / contracts | 79 / 62 / 84 / 48 passed |
| Offline isolated-install + boundary proof | PASS |

The RA-5 suite is deny-heavy: the caller-forged-PASS path, cross-context bindings,
stale/tampered/unadmitted evidence, partial/constrained/indeterminate outcomes,
admission/assurance outages, and duplicate (F-E) conflicts all fail closed; only a
fully-supported, in-context, fresh set proceeds.
