"""The Cloudflare-facing transport boundary for the AP-3 designated issuer (owner ruling
AP3-D4, ``ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`` §20.7).

    ``Cf-Access-Jwt-Assertion`` IS A TRANSPORT HEADER, NOT A PROOF. THE ADAPTER READS IT,
    VALIDATES THE TOKEN COMPLETELY, AND EMITS THE PLANE'S NORMALIZED ``ApproverIdentity``.
    THE RAW HEADER NEVER REACHES THE WRITE GATE, IS NEVER COPIED INTO
    ``X-Ugence-Approver-Proof``, AND IS NEVER STORED, LOGGED OR ECHOED.

AW-3 stands: the plane's own proof header is ``X-Ugence-Approver-Proof``
(``authority_plane.WRITE_PROOF_HEADER``), unchanged and read first. This boundary is
the minimum AP-3 conformance seam: ``build_authority_writes`` accepts it as an
explicit, default-off argument so the conformance harness can drive the real adapter
and the real gate from the header Cloudflare injects at the origin. Production wiring
of this translation is explicitly deferred: ``composition.py`` does not construct it,
and a boundary over an adapter that is not configured with the ``cloudflare-access``
profile is refused at construction.
"""

from __future__ import annotations

from typing import Any, Mapping

from ugence_approver_identity_jwt import CLOUDFLARE_ACCESS_PROFILE
from ugence_governed_review_service.identity import ApproverIdentity

__all__ = ["CLOUDFLARE_TRANSPORT_HEADER", "CloudflareAccessProofBoundary"]

#: What Cloudflare Access injects at the origin for an authenticated request [I].
#: Transport only: it selects this boundary and nothing else.
CLOUDFLARE_TRANSPORT_HEADER = "Cf-Access-Jwt-Assertion"

RULING = "AP3-D4"


class CloudflareAccessProofBoundary:
    """Reads the transport header through one adapter configured with the Cloudflare
    Access profile, and answers only with the adapter's normalized identity."""

    header = CLOUDFLARE_TRANSPORT_HEADER
    ruling = RULING

    def __init__(self, adapter: Any) -> None:
        config = getattr(adapter, "config", None)
        if getattr(config, "issuer_profile", None) != CLOUDFLARE_ACCESS_PROFILE:
            raise ValueError(
                "CloudflareAccessProofBoundary requires an adapter configured with the "
                "cloudflare-access issuer profile (AP3-D1 to AP3-D3); it translates for the "
                "designated issuer and for no other"
            )
        if not callable(getattr(adapter, "authenticate", None)):
            raise ValueError("the adapter must implement ApproverIdentityPort.authenticate")
        self._adapter = adapter

    @property
    def issuer(self) -> str:
        return str(self._adapter.config.issuer)

    def presented(self, headers: Mapping[str, str]) -> bool:
        """Whether the transport header is present and non-empty. Reads nothing else."""
        return bool(headers.get(self.header, ""))

    def identity_from(self, headers: Mapping[str, str]) -> ApproverIdentity:
        """The adapter's answer for the assertion on the transport header: a complete
        validation (signature, issuer, audience, time, the ratified mappings) and the
        plane's normalized identity, authenticated or refused. The raw value is a local
        here and nowhere else; any failure to answer propagates for the gate to refuse."""
        assertion = headers.get(self.header, "")
        if not assertion:
            raise ValueError(f"no assertion on {self.header}")
        answer = self._adapter.authenticate(assertion)
        if not isinstance(answer, ApproverIdentity):
            raise TypeError("the adapter answered with the wrong shape")
        return answer
