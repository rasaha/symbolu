"""Ugence Risk Authority Evidence Runtime — RA-5 trusted-evidence integration.

This integration package closes the RA-5 trust gap: in production, Risk Authority
must no longer trust an arbitrary caller-asserted control ``PASS``. It supplies
the production implementations behind Risk Authority's two ports and an explicit
composition root that orchestrates the trusted path:

    raw evidence
        → Evidence Admission        (ProductionEvidenceAdmission → EvidenceAdmissionPort)
        → AdmittedEvidence
        → Control Assurance         (TapControlAssurance → ControlAssurancePort)
        → trusted ControlResult (intrinsically bound to the case context)
        → Risk Authority's EXISTING non-compensatory gate
        → RiskDecision
        → Ed25519-signed RiskAuthorizationEnvelope   (the sole machine authority)

**Ownership fences (RA-5 spec §4), never blurred here:**

* Evidence Admission owns admissibility (provenance / integrity / freshness /
  schema). It does not decide whether a control passes.
* Control Assurance owns "does admitted evidence satisfy control C?" — it produces
  a trusted, bound ``ControlResult`` and *nothing else*. It issues no authority.
* Risk Authority owns aggregation + authority issuance (unchanged, in its leaf).

This package is **upstream** of envelope issuance and adds **no** second machine
authority artifact. It does not implement RA-6/7/8, continuous assurance,
post-issuance revocation, or HSM/KMS.

Dependency direction (one-way; ``ugence-risk-authority`` stays a stdlib-only leaf):

    risk_authority  ◄──  risk_authority_evidence_runtime  ──►  ugence-tap-provider
        (ports)                                          └──►  governance framework/contracts

See ``docs/architecture/RISK_AUTHORITY_RA5_SPEC.md`` (ratified).
"""

from __future__ import annotations

from .admission import ProductionEvidenceAdmission, stamp_admitted_evidence
from .ingress import StaticTrustedIngress
from .outcome_mapping import FULL_COVERAGE, map_assertion_outcome
from .runtime import RiskAuthorityEvidenceRuntime
from .tap_control_assurance import TapControlAssurance
from .version import __version__

__all__ = [
    "__version__",
    "ProductionEvidenceAdmission",
    "stamp_admitted_evidence",
    "StaticTrustedIngress",
    "TapControlAssurance",
    "map_assertion_outcome",
    "FULL_COVERAGE",
    "RiskAuthorityEvidenceRuntime",
]
