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
| RA-5 trusted-evidence suite (`.../risk-authority-evidence-runtime/tests`) | 86 passed (63 pre-audit + hardening/boundary coverage) |
| TAP provider | 82 passed |
| Decision Authority / ActionGate / governance framework / contracts | 79 / 62 / 84 / 48 passed |
| Offline isolated-install + boundary proof | PASS |

The RA-5 suite is deny-heavy: the caller-forged-PASS path, cross-context bindings,
stale/tampered/unadmitted evidence, partial/constrained/indeterminate outcomes,
admission/assurance outages, and duplicate (F-E) conflicts all fail closed; only a
fully-supported, in-context, fresh set proceeds.

## Post-audit hardening (independent adversarial audit remediation)

> **Provenance:** audited implementation HEAD `a40995a8`; the ratified RA-5 spec
> was ratified in this branch by commit **`ede6f454`** (*"docs(risk-authority):
> ratify canonical RA-5 spec"*). (An earlier external reference to a SHA
> `4e6089a3` was a provenance-label error; that commit does not exist in this
> ancestry.)

An independent adversarial audit reproduced a path in which fabricated caller
evidence (a self-computed integrity digest) plus the rule-less reference TAP
evaluator yielded `PASS → ALLOW → signed envelope`. The following narrow
hardening closes it without redesigning RA-1→RA-4, RA-4.5, or the ratified RA-5
architecture; the baselines above remain green and unchanged.

- **H-1 — no fail-open control assurance.** The reference TAP engine now marks
  support *presumed from mere evidence presence* (no per-assertion rule / explicit
  stance) with a `presumptive_support` reason code; its native outcome is
  unchanged, so existing TAP consumers are unaffected. The production
  `TapControlAssurance` (default `require_explicit_determination=True`) downgrades
  presumptive support to `UNKNOWN` — a `PASS` now requires an *explicit affirmative
  determination*. Production composition additionally **rejects a non-authoritative
  Control-Assurance port** (`is_production_authoritative` must be `True`), so a
  permissive/reference evaluator cannot silently satisfy control assurance.
- **H-2 — authenticated producer-channel seam.** A new stdlib-only
  `TrustedEvidenceIngressPort` (RA leaf) makes the previously-implicit §13
  transport/producer-trust assumption **explicit and fail-closed**: production mode
  requires it, and each record is gated through the injected channel verifier
  *before* admission. RA adds no cryptography here — producer attestation /
  signatures remain FUTURE (§13); the integrity digest is content tamper-detection,
  **not** producer authenticity. No canonical authenticated-ingress facility exists
  in-repo to compose with, so this ships the neutral seam plus a conformance
  `StaticTrustedIngress` stand-in for the deployment's real channel decision.
- **M-1** — the two directly-imported governance distributions
  (`ugence-governance-contracts`, `ugence-governance-provider-framework`) are now
  declared dependencies (no longer only transitive via the TAP provider); a
  package-boundary test fails on any undeclared direct import.
- **M-2** — RA's authoritative binding re-check now independently enforces
  freshness monotonicity (§7.1: `result.valid_until ≤ min(backing evidence
  valid_until)`), rather than trusting the evaluator's clamp.
- **L-1** — RA-5 state transitions are gated on real artifacts: a case with
  missing/stale/untrusted required evidence is never represented as
  evidence-complete and cannot reach `AUTHORITY_REVIEW`.
- **L-2** — an out-of-range coverage (`<0` or `>1`) is treated as malformed
  (`UNKNOWN`), never clamped up to `PASS`.
- **L-3** — a separate **admission-record binding digest** binds the admission-time
  attribution (`producer` / `producer_version` / `admitted_at` / status) to the
  content digest; post-hoc mutation of attribution now fails admission. It is kept
  distinct from the content integrity digest because those fields are decided *at
  admission*, not present in the pre-admission evidence a producer stamps — folding
  them into the content digest would be lifecycle-invalid. Neither digest is a
  signature.

Post-hardening the RA-5 suite is **86 passed**; the reproduced exploit now fails
closed (`DENY`, no envelope) via three independent layers (admission-record
binding, presumptive-support downgrade, and trusted-ingress gating).
