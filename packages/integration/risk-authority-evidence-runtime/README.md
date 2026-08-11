# ugence-risk-authority-evidence-runtime (RA-5)

**Trusted evidence admission + control assurance for Risk Authority.**

RA-5 closes a specific production trust gap: in the RA-1→RA-4 reference path a
caller supplies a control *status* (`ControlResultInput{control_id, status:"PASS",
evidence_ids}`) that Risk Authority stamps into a `ControlResult` and trusts. That
is correct for conformance/reference use, but in production it means a caller can
mint machine authority simply by asserting `PASS`.

This integration package supplies the production implementations behind Risk
Authority's two ports and an explicit composition root that makes the trusted
path the only way to satisfy a mandatory control in production:

```
raw evidence
   │
   ▼  Evidence Admission        (ProductionEvidenceAdmission → EvidenceAdmissionPort)
AdmittedEvidence                (provenance ∧ integrity(digest) ∧ fresh(now) ∧ schema)
   │
   ▼  Control Assurance         (TapControlAssurance → ControlAssurancePort)
trusted ControlResult           (intrinsically bound to tenant/case/workflow/policy/control)
   │
   ▼  Risk Authority            (its EXISTING non-compensatory gate — unchanged)
RiskDecision
   │
   ▼  Ed25519-signed RiskAuthorizationEnvelope   ← the SOLE machine authority
```

> **The central security property:** in production mode a caller-supplied
> `status="PASS"` is inert. Only an evidence-derived, RA-re-checked, trusted
> `ControlResult` may satisfy a required control. See
> `docs/architecture/RISK_AUTHORITY_RA5_SPEC.md` (ratified).

## Ownership fences (never blurred)

| Concern | Owner | Answers |
|---|---|---|
| **Evidence Admission** | `ProductionEvidenceAdmission` (behind RA's `EvidenceAdmissionPort`) | "May this evidence enter the assurance process?" (provenance / integrity / freshness / schema) |
| **Control Assurance** | `TapControlAssurance` (behind RA's new `ControlAssurancePort`) | "Does the admitted evidence satisfy control C?" → a trusted, bound `ControlResult` |
| **Risk Authority** | `ugence-risk-authority` (unchanged leaf) | "Given trusted results for required controls, what machine authority may be issued?" |

RA-5 is strictly **upstream** of envelope issuance and adds **no** second machine
authority artifact. Evidence admission never decides whether a control passes;
control assurance never issues authority; Risk Authority keeps its
non-compensatory aggregation rule.

## Ratified outcome mapping (fail-closed, non-compensatory)

Only an unambiguous, fully-supported outcome may satisfy a mandatory control:

| TAP outcome | → `ControlStatus` |
|---|---|
| `SUPPORTED` ∧ `evidence_coverage >= 1.0` | `PASS` |
| `SUPPORTED` ∧ coverage `< 1.0` / `None` | `UNKNOWN` (not PASS) |
| `CONSTRAINED` | `UNKNOWN` (not PASS) |
| `UNSUPPORTED` | `FAIL` |
| `INDETERMINATE` / unknown / malformed | `UNKNOWN` (fail closed) |

`evidence_coverage` is used **only** as the binary full-support gate — never as a
weight or score, and high coverage on one control never compensates a failed
mandatory control (that remains RA's unchanged gate).

## Reference vs production mode

| | Reference / conformance | Production |
|---|---|---|
| Control result origin | caller-supplied `ControlResultInput` (synthetic) | trusted `ControlResult` from `ControlAssurancePort`; caller status inert |
| Admission | none / injected records | required through `EvidenceAdmissionPort` |
| Binding fields | may be unset | **must** be populated and RA-re-checked (§8) |
| Caller-asserted `PASS` | permitted (isolated tests) | **cannot produce authority** |

Production mode is **explicit**: constructing `RiskAuthorityEvidenceRuntime`
(or a production `RiskAuthorityApplication`) requires both ports; an incomplete
configuration fails closed. Production never silently falls back to the reference
path — the reference `evaluate()` is disabled when production mode is active.

## Usage

```python
from ugence_risk_authority_evidence_runtime import (
    ProductionEvidenceAdmission, TapControlAssurance, RiskAuthorityEvidenceRuntime,
)
from ugence_tap_provider.api import TapEngine, build_tap_provider

runtime = RiskAuthorityEvidenceRuntime(
    workflow_source=source, key_record=key, clock=clock,
    evidence_admission=ProductionEvidenceAdmission(),
    control_assurance=TapControlAssurance(build_tap_provider(TapEngine())),
)
runtime.create_case(create_req)
evaluation = runtime.submit_evidence_and_evaluate(
    tenant_id, case_id, raw_evidence, control_evidence={"C1": ("ev1",)},
)
decision = runtime.issue_decision(tenant_id, case_id, evaluation, decision_req)
envelope = runtime.issue_envelope(tenant_id, case_id, envelope_req)  # sole authority
```

## Dependency direction (one-way; no cycle)

```
risk_authority (stdlib-only leaf)   defines EvidenceAdmissionPort + ControlAssurancePort
        ▲  import (integration → RA), never the reverse
        │
ugence-risk-authority-evidence-runtime (this package)
        ▼
ugence-tap-provider (Control-Assurance evaluator candidate) + governance framework/contracts
```

`ugence-risk-authority` stays a stdlib-only leaf; no provider dependency enters
it. The RA-4.5 runtime package is **not** modified or depended upon (RA-5 is
upstream of the envelope it consumes).

## Scope (explicitly NOT in this milestone)

No continuous assurance, no post-issuance evidence revocation, no RA-6/7/8, no
HSM/KMS, no second authorization artifact, no changes to RA-1→RA-4 or RA-4.5
semantics. RA-5 adds hash-binding + attribution, **not** new signatures — the
Ed25519 envelope remains the sole machine-authority signature.

## Build & verify

```
python -m build packages/integration/risk-authority-evidence-runtime
python packages/integration/risk-authority-evidence-runtime/scripts/verify_isolated_install.py
python -m pytest packages/integration/risk-authority-evidence-runtime/tests -q
```
