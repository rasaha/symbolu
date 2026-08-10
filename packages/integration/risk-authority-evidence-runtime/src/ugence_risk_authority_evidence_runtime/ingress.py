"""Trusted evidence-ingress implementations (RA-5 spec §13; audit H-2).

Risk Authority owns the neutral ``TrustedEvidenceIngressPort`` contract; this
module supplies implementations behind it. RA-5 deliberately does **not** ship a
cryptographic producer-authentication system (attestation/signatures remain
FUTURE, §13). What it ships is the honest architectural boundary: production
evidence must be presented over an *authenticated producer channel*, and that
decision is made by the deployment — never derived from the (self-computable)
integrity digest.

* :class:`StaticTrustedIngress` is a **conformance/reference** seam that records a
  single trust posture for the channel. A real deployment injects a verifier
  backed by its authenticated ingress (mTLS / workload identity / signed
  producer-channel token) instead. It is intentionally NOT an authenticator — it
  exists so the trusted-evidence *flow* can be exercised deterministically and so
  the fail-closed requirement (no ingress ⇒ production refuses to construct) is
  testable.

  Because it is a stand-in and not a real authenticator, **production mode
  refuses it**: it is flagged ``is_reference_ingress = True`` and the production
  ``RiskAuthorityApplication`` fails closed on any ingress carrying that marker
  (RA-5 audit F-1), symmetric with the ``is_production_authoritative`` guardrail
  on the Control-Assurance port. Wiring this stand-in into production would
  silently reopen the H-2 evidence-authenticity gap, so it is rejected at
  construction. Use it only in reference/conformance and adversarial tests.

This module is stdlib-only apart from the RA contract types it implements.
"""

from __future__ import annotations

from datetime import datetime

from risk_authority.domain.evidence import ControlEvidenceRecord

__all__ = ["StaticTrustedIngress"]


class StaticTrustedIngress:
    """A conformance ``TrustedEvidenceIngressPort`` with a fixed channel posture.

    ``trusted=True`` represents *"this composition's evidence arrives over an
    authenticated producer channel"*; ``trusted=False`` represents an
    unauthenticated caller. It is a stand-in for the deployment's real channel
    decision, not an implementation of authentication — a fabricated record with a
    self-computed digest gains nothing here, because ingress is decided by this
    injected posture, not by anything in the evidence artifact.
    """

    #: Marks this port as a reference/conformance seam (documentation signal).
    is_reference_ingress = True

    def __init__(self, *, trusted: bool = False) -> None:
        self._trusted = bool(trusted)

    def is_trusted(self, evidence: ControlEvidenceRecord, *, now: datetime) -> bool:
        return self._trusted
