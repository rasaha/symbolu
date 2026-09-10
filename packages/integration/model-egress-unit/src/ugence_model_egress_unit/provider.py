"""The provider seam, the reference adapters, and the deterministic fake clearance.

There is no vendor provider here and no configuration that produces one. The seam
exists so a live provider — if one is ever commissioned — has a shape to implement
and a boundary to land on.

Why the fake cannot pass for production
---------------------------------------
Four independent mechanisms, because a label alone is a comment:

1. ``maturity = "FIXTURE_ONLY"`` and ``NON_PRODUCTION = True``, the repository's
   convention, machine-readable and asserted by tests.
2. Every answer begins with a fixed marker and names its adapter inside its own
   body, so a response that reached a log, a screen or an audit record still says
   what produced it.
3. Every provenance record it writes carries ``genuine_call: False`` — and the
   database refuses any other value, so the claim cannot be made even by a caller
   writing rows directly.
4. :meth:`DeterministicFakeProvider.execute` refuses outright when handed a
   production posture.

The fourth is the one that matters. The first three describe the adapter; only the
fourth makes the description binding. A fake that returns plausible model output is
a demo; one that returns labelled output is a test fixture, and the provenance
record is the only thing standing between a governed loop and a governed-looking
one.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from .canonical import canonical_digest, EGRESS_REQUEST_DIGEST_DOMAIN
from .records import AuthorizationBinding, EgressRequest, EgressResult, RefusalReason

__all__ = [
    "EgressProvider",
    "ProviderRefusedInProduction",
    "REFERENCE_RESPONSE_MARKER",
    "REFERENCE_CLEARANCE_DOMAIN",
    "reference_clearance",
    "DeterministicFakeProvider",
    "LiveEgressUnavailableProvider",
]

#: Prefixed to every answer the reference provider produces. Deliberately loud and
#: deliberately not configurable: a marker a deployment can turn off is a marker
#: that will be off in the deployment that most needed it.
REFERENCE_RESPONSE_MARKER = "[UGENCE-REFERENCE-FAKE — NOT A MODEL RESPONSE]"

#: Domain for the deterministic fake clearance below. Separate from every real
#: clearance domain so a fixture receipt can never validate as a genuine one.
REFERENCE_CLEARANCE_DOMAIN = "ugence.model-egress-unit/reference-clearance/v1"


class ProviderRefusedInProduction(RuntimeError):
    """A reference adapter was asked to serve a production posture."""


def reference_clearance(
    *,
    tenant_id: UUID,
    vendor: str,
    model: str,
    policy_id: str = "reference-policy",
    reservation_id: Optional[str] = None,
    clearance_ref: Optional[str] = None,
) -> AuthorizationBinding:
    """A deterministic fake clearance, for tests and the reference deployment.

    **This mints no authority.** It fabricates the *shape* of a binding that a
    real Model Authority would have produced, so the exchange can be exercised
    end to end without one. The ``cer-ref-`` prefix and the fixture digest domain
    are what keep it from being mistaken for a genuine receipt: nothing here is
    signed, and no verifier of real clearances would accept it.

    Deterministic in its digest so a test can assert an exact request digest.
    """

    ref = clearance_ref or f"cer-ref-{tenant_id}"
    reservation = reservation_id or f"rsv-ref-{tenant_id}"
    digest = canonical_digest(
        REFERENCE_CLEARANCE_DOMAIN,
        "ReferenceClearance",
        {
            "clearance_ref": ref,
            "tenant_id": str(tenant_id),
            "vendor": vendor,
            "model": model,
            "policy_id": policy_id,
            "reservation_id": reservation,
        },
    )
    return AuthorizationBinding(
        clearance_ref=ref,
        clearance_digest=digest,
        tenant_id=tenant_id,
        authorized_vendor=vendor,
        authorized_model=model,
        policy_id=policy_id,
        reservation_id=reservation,
    )


class EgressProvider(Protocol):
    """What the unit calls once it holds a lease and has verified the binding.

    Returning an :class:`EgressResult` rather than raw text keeps the refusal path
    first-class: an adapter that can only return content has no way to say "this
    request is one I will never serve" except by raising, and an exception is not
    a record.
    """

    adapter_id: str
    vendor: str

    def execute(self, request: EgressRequest, *, now: datetime,
                production: bool = False) -> EgressResult:
        ...


class DeterministicFakeProvider:
    """Answers as a pure function of the request digest. No network, no vendor.

    Determinism is the feature: the same request produces the same answer in every
    process and on every machine, so a test can assert an exact response digest
    rather than merely that *something* came back — which is what lets the purge
    tests prove a tombstone's digest is the digest of the content destroyed.
    """

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(self, *, adapter_id: str = "ugence-reference-fake",
                 vendor: str = "reference-vendor",
                 available_models: Optional[frozenset] = None,
                 content_ceiling: int = 65_536) -> None:
        self.adapter_id = adapter_id
        self.vendor = vendor
        self._models = available_models
        self._ceiling = content_ceiling

    def _refusal(self, request: EgressRequest, now: datetime) -> Optional[RefusalReason]:
        """The first terminal reason this request cannot be served, if any.

        Order matters. The authorization check comes before anything about the
        content, because a target nobody authorized must be refused whether or not
        its prompt would also have been acceptable.
        """

        if not request.authorization.authorizes(
                vendor=self.vendor, model=request.authorization.authorized_model,
                tenant_id=request.tenant_id):
            return RefusalReason.TARGET_NOT_AUTHORIZED
        if now >= request.not_valid_after:
            return RefusalReason.REQUEST_NOT_VALID
        if not request.content_matches_digest():
            return RefusalReason.CONTENT_DIGEST_MISMATCH
        if (self._models is not None
                and request.authorization.authorized_model not in self._models):
            return RefusalReason.MODEL_NOT_AVAILABLE
        if request.minimized_context is not None:
            size = sum(len(u.text) for u in request.minimized_context)
            if size > self._ceiling:
                return RefusalReason.CONTENT_EXCEEDS_CEILING
        return None

    def answer_for(self, request: EgressRequest) -> str:
        """The deterministic body for a request. Pure, and depends on no clock."""

        seed = hashlib.sha256(
            b"ugence.model-egress-unit/reference-answer/v1\x00"
            + request.digest().encode("ascii")
        ).hexdigest()
        return (
            f"{REFERENCE_RESPONSE_MARKER} adapter={self.adapter_id} "
            f"model={request.authorization.authorized_model} seed={seed}"
        )

    def execute(self, request: EgressRequest, *, now: datetime,
                production: bool = False) -> EgressResult:
        if production:
            raise ProviderRefusedInProduction(
                f"{self.adapter_id} is a reference fixture and refuses to serve a "
                f"production posture. It has no vendor egress and its answers are "
                f"computed from a hash; returning one here would present a "
                f"fabrication as a model response."
            )

        reason = self._refusal(request, now)
        if reason is not None:
            return EgressResult.refused(
                request_id=request.request_id, tenant_id=request.tenant_id,
                correlation_id=request.correlation_id, recorded_at=now,
                adapter_id=self.adapter_id, reason=reason,
                model_ref=request.authorization.authorized_model)
        tokens = sum(u.token_count for u in (request.minimized_context or ()))
        return EgressResult.answered(
            request_id=request.request_id, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, recorded_at=now,
            adapter_id=self.adapter_id, payload=self.answer_for(request),
            model_ref=request.authorization.authorized_model, token_count=tokens)


class LiveEgressUnavailableProvider:
    """Refuses everything, terminally, naming the missing custody.

    What a deployment gets when no provider credential has been commissioned. It
    is not a stub that fails obscurely, and it does not treat a credential as
    required configuration and fail to start: the unit composes, claims work,
    validates it, and refuses the call with a typed reason — never a generic
    error, never a silent skip, never a fabricated answer.
    """

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(self, *, adapter_id: str = "ugence-live-egress-unavailable",
                 vendor: str = "reference-vendor") -> None:
        self.adapter_id = adapter_id
        self.vendor = vendor

    def execute(self, request: EgressRequest, *, now: datetime,
                production: bool = False) -> EgressResult:
        return EgressResult.refused(
            request_id=request.request_id, tenant_id=request.tenant_id,
            correlation_id=request.correlation_id, recorded_at=now,
            adapter_id=self.adapter_id,
            reason=RefusalReason.CREDENTIAL_NOT_COMMISSIONED,
            model_ref=request.authorization.authorized_model)
