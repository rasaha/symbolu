"""The provider seam, and the only provider this distribution ships.

There is no vendor provider here, and there is no configuration that produces
one. The seam exists so that a live provider — if one is ever ratified — has a
shape to implement and a boundary to land on. Until then the only implementation
computes its answer from a hash.

Why the fake cannot pass for production
---------------------------------------
Three independent mechanisms, because a label alone is a comment:

1. ``maturity = "FIXTURE_ONLY"`` and ``NON_PRODUCTION = True``, the repository's
   existing convention, machine-readable and asserted by tests.
2. Every answer it produces **begins with a fixed marker string** and names the
   provider inside its own body. A response that reached a log, a screen or an
   audit record still says what produced it; there is no rendering of it that
   looks like a model's answer.
3. :meth:`DeterministicFakeProvider.execute` refuses outright when it is handed
   a production posture. A deployment that tried to run this in production gets
   a refusal at the call, not a plausible answer.

The third is the one that matters. The first two describe the provider; only the
third makes the description binding.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from .records import EgressRequest, EgressResult, RefusalReason

__all__ = [
    "EgressProvider",
    "ProviderRefusedInProduction",
    "REFERENCE_RESPONSE_MARKER",
    "DeterministicFakeProvider",
]

#: Prefixed to every answer the reference provider produces. Deliberately loud
#: and deliberately not configurable: a marker a deployment can turn off is a
#: marker that will be off in the deployment that most needed it.
REFERENCE_RESPONSE_MARKER = "[UGENCE-REFERENCE-FAKE — NOT A MODEL RESPONSE]"


class ProviderRefusedInProduction(RuntimeError):
    """A reference provider was asked to serve a production posture."""


class EgressProvider(Protocol):
    """What the unit calls once it holds a lease.

    Returning an :class:`EgressResult` rather than raw text keeps the refusal
    path first-class: a provider that can only return content has no way to say
    "this request is one I will never serve" except by raising, and an exception
    is not a record.
    """

    provider_id: str

    def execute(
        self,
        request: EgressRequest,
        *,
        now: datetime,
        production: bool = False,
    ) -> EgressResult:
        ...


class DeterministicFakeProvider:
    """Answers as a pure function of the request digest. No network, no vendor.

    Determinism is the feature: the same request produces the same answer in
    every process and on every machine, so an exchange test can assert an exact
    response digest rather than merely that *something* came back. That is what
    lets the purge tests prove a tombstone's digest is the digest of the content
    that was destroyed.
    """

    #: Repository convention for a non-production implementation.
    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(
        self,
        *,
        provider_id: str = "ugence-reference-fake",
        available_models: Optional[frozenset] = None,
        permitted_purposes: Optional[frozenset] = None,
        content_ceiling: int = 65_536,
    ) -> None:
        self.provider_id = provider_id
        self._models = available_models
        self._purposes = permitted_purposes
        self._ceiling = content_ceiling

    def _refusal(self, request: EgressRequest) -> Optional[RefusalReason]:
        """The first terminal reason this request cannot be served, if any.

        Every reason here names a condition that re-running cannot change, which
        is what makes the refusal terminal rather than a retry in disguise.
        """

        if self._models is not None and request.model_id not in self._models:
            return RefusalReason.MODEL_NOT_AVAILABLE
        if self._purposes is not None and request.purpose not in self._purposes:
            return RefusalReason.PURPOSE_NOT_PERMITTED
        if request.content is not None and len(request.content) > self._ceiling:
            return RefusalReason.CONTENT_EXCEEDS_CEILING
        return None

    def answer_for(self, request: EgressRequest) -> str:
        """The deterministic body for a request. Pure, and depends on no clock."""

        seed = hashlib.sha256(
            b"ugence.model-egress-unit/reference-answer/v1\x00"
            + request.digest().encode("ascii")
        ).hexdigest()
        return (
            f"{REFERENCE_RESPONSE_MARKER} provider={self.provider_id} "
            f"model={request.model_id} seed={seed}"
        )

    def execute(
        self,
        request: EgressRequest,
        *,
        now: datetime,
        production: bool = False,
    ) -> EgressResult:
        if production:
            raise ProviderRefusedInProduction(
                f"{self.provider_id} is a reference fixture and refuses to serve a "
                f"production posture. It has no vendor egress and its answers are "
                f"computed from a hash; returning one here would be presenting a "
                f"fabrication as a model response."
            )

        reason = self._refusal(request)
        if reason is not None:
            return EgressResult.refused(
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                recorded_at=now,
                provider_id=self.provider_id,
                reason=reason,
            )
        return EgressResult.answered(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            recorded_at=now,
            provider_id=self.provider_id,
            content=self.answer_for(request),
        )


class LiveEgressUnavailableProvider:
    """Refuses everything, terminally, naming why.

    What a deployment gets if it configures the unit without a provider. It is
    not a stub that fails obscurely — it produces a proper terminal refusal with
    :attr:`RefusalReason.LIVE_EGRESS_NOT_AVAILABLE`, so the requester learns that
    live egress does not exist here rather than watching a request sit pending
    forever.
    """

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(self, *, provider_id: str = "ugence-live-egress-unavailable") -> None:
        self.provider_id = provider_id

    def execute(
        self,
        request: EgressRequest,
        *,
        now: datetime,
        production: bool = False,
    ) -> EgressResult:
        return EgressResult.refused(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            recorded_at=now,
            provider_id=self.provider_id,
            reason=RefusalReason.LIVE_EGRESS_NOT_AVAILABLE,
        )
