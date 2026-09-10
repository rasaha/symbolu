"""The exchange vocabulary: states, outcomes, refusal reasons and the two records.

Three ideas here are load-bearing and worth stating before the code.

**A refusal is terminal.** When the unit declines a request it declines it once
and for all. A retriable condition is not a refusal; it is a request that is
still ``PENDING``. Collapsing the two would produce the failure this exchange
exists to avoid — a request that was refused for a reason that will never change,
retried forever.

**``OUTCOME_UNKNOWN`` is terminal too, and that is the point.** It is recorded
when a lease expired after the request may already have been dispatched. The
honest answer is that nobody knows whether the call happened. Retrying would
convert "we don't know" into "we did it twice", which is strictly worse than
never knowing: an unknown outcome can be reconciled by a human, a duplicated side
effect cannot be un-done. So the reconciler moves such a request to a terminal
state and stops, rather than returning it to the queue.

**Consumption is acknowledged, not assumed.** A result is not finished when it is
written; it is finished when the requester says it has read it. Only then may the
content be purged. Without the acknowledgement, purge would race the reader and
destroy an answer nobody ever saw.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Optional
from uuid import UUID

from .canonical import (
    EGRESS_REQUEST_DIGEST_DOMAIN,
    EGRESS_RESULT_DIGEST_DOMAIN,
    canonical_digest,
    content_digest,
)

__all__ = [
    "RequestState",
    "ResultOutcome",
    "RefusalReason",
    "TERMINAL_STATES",
    "EgressRequest",
    "EgressResult",
]


class RequestState(str, enum.Enum):
    """Where a request is in the exchange.

    ``PENDING`` and ``LEASED`` are the only non-terminal states. Everything else
    is an end: nothing transitions out of a terminal state except a purge, which
    destroys content without changing the state.
    """

    PENDING = "PENDING"
    LEASED = "LEASED"
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


#: Terminal states, named once so no caller has to re-derive the set.
TERMINAL_STATES = frozenset(
    {RequestState.COMPLETED, RequestState.REFUSED, RequestState.OUTCOME_UNKNOWN}
)


class ResultOutcome(str, enum.Enum):
    """What the unit found out.

    ``OUTCOME_UNKNOWN`` is a first-class outcome rather than an error, because
    "the call may or may not have happened" is a fact about the world that the
    ledger has to be able to state. A schema that could only record success or
    failure would force it to be recorded as one of the two, and both would be
    lies.
    """

    ANSWERED = "ANSWERED"
    REFUSED = "REFUSED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class RefusalReason(str, enum.Enum):
    """Terminal refusals. Each names a condition that re-running cannot change.

    There is deliberately no ``UNKNOWN`` or ``OTHER`` member. A refusal a caller
    cannot name is a refusal a caller cannot act on, and an escape-hatch member
    would become the one everybody uses.
    """

    #: The request names a model the unit is not configured to reach.
    MODEL_NOT_AVAILABLE = "model_not_available"
    #: The declared purpose is not one this unit serves.
    PURPOSE_NOT_PERMITTED = "purpose_not_permitted"
    #: The content exceeds the unit's declared ceiling. Retrying the same content
    #: cannot help; the caller has to send different content.
    CONTENT_EXCEEDS_CEILING = "content_exceeds_ceiling"
    #: The request was already terminal when the unit reached it.
    ALREADY_TERMINAL = "already_terminal"
    #: The requested exchange would need live vendor egress, which this
    #: distribution does not have and cannot be configured to have.
    LIVE_EGRESS_NOT_AVAILABLE = "live_egress_not_available"


@dataclass(frozen=True)
class EgressRequest:
    """One request for a model exchange, as the requester wrote it.

    ``content`` is the payload; ``content_sha256`` is its digest, computed at
    construction so that the record carries it even after ``content`` is purged.
    """

    request_id: UUID
    tenant_id: UUID
    submitted_at: datetime
    model_id: str
    purpose: str
    content: Optional[str]
    content_sha256: str
    parameters: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        request_id: UUID,
        tenant_id: UUID,
        submitted_at: datetime,
        model_id: str,
        purpose: str,
        content: str,
        parameters: Optional[Mapping[str, object]] = None,
    ) -> "EgressRequest":
        """Build a request, digesting its content once at the boundary."""

        return cls(
            request_id=request_id,
            tenant_id=tenant_id,
            submitted_at=submitted_at,
            model_id=model_id,
            purpose=purpose,
            content=content,
            content_sha256=content_digest(content),
            parameters=dict(parameters or {}),
        )

    def digest_body(self) -> dict:
        """Every field that identifies this request, with content by digest.

        ``content`` itself is absent by construction — see the module docstring
        of :mod:`.canonical`. Everything else is present unconditionally, so the
        digest is total over the request's identity.
        """

        return {
            "request_id": str(self.request_id),
            "tenant_id": str(self.tenant_id),
            "submitted_at": self.submitted_at,
            "model_id": self.model_id,
            "purpose": self.purpose,
            "content_sha256": self.content_sha256,
            "parameters": dict(self.parameters),
        }

    def digest(self) -> str:
        """The request digest. Recomputable from a purged tombstone."""

        return canonical_digest(
            EGRESS_REQUEST_DIGEST_DOMAIN, "EgressRequest", self.digest_body())


@dataclass(frozen=True)
class EgressResult:
    """What came back, or what could not be determined.

    ``content`` is ``None`` for every outcome but ``ANSWERED``, and also for an
    ``ANSWERED`` result whose content has since been purged. The two are told
    apart by ``content_sha256``: a refusal has no content digest, a purged answer
    still has one.
    """

    request_id: UUID
    tenant_id: UUID
    recorded_at: datetime
    outcome: ResultOutcome
    provider_id: str
    content: Optional[str]
    content_sha256: Optional[str]
    refusal_reason: Optional[RefusalReason] = None

    def __post_init__(self) -> None:
        if self.outcome is ResultOutcome.REFUSED and self.refusal_reason is None:
            raise ValueError(
                "a REFUSED result must name its reason: an unexplained terminal "
                "refusal cannot be acted on by the requester")
        if self.outcome is not ResultOutcome.REFUSED and self.refusal_reason is not None:
            raise ValueError(
                f"a {self.outcome.value} result must not carry a refusal reason")
        if self.outcome is not ResultOutcome.ANSWERED and self.content is not None:
            raise ValueError(
                f"a {self.outcome.value} result has no content to carry")

    @classmethod
    def answered(
        cls,
        *,
        request_id: UUID,
        tenant_id: UUID,
        recorded_at: datetime,
        provider_id: str,
        content: str,
    ) -> "EgressResult":
        return cls(
            request_id=request_id,
            tenant_id=tenant_id,
            recorded_at=recorded_at,
            outcome=ResultOutcome.ANSWERED,
            provider_id=provider_id,
            content=content,
            content_sha256=content_digest(content),
        )

    @classmethod
    def refused(
        cls,
        *,
        request_id: UUID,
        tenant_id: UUID,
        recorded_at: datetime,
        provider_id: str,
        reason: RefusalReason,
    ) -> "EgressResult":
        return cls(
            request_id=request_id,
            tenant_id=tenant_id,
            recorded_at=recorded_at,
            outcome=ResultOutcome.REFUSED,
            provider_id=provider_id,
            content=None,
            content_sha256=None,
            refusal_reason=reason,
        )

    @classmethod
    def outcome_unknown(
        cls,
        *,
        request_id: UUID,
        tenant_id: UUID,
        recorded_at: datetime,
        provider_id: str,
    ) -> "EgressResult":
        """The lease expired after the request may already have been dispatched.

        Recorded, never retried. See the module docstring.
        """

        return cls(
            request_id=request_id,
            tenant_id=tenant_id,
            recorded_at=recorded_at,
            outcome=ResultOutcome.OUTCOME_UNKNOWN,
            provider_id=provider_id,
            content=None,
            content_sha256=None,
        )

    def digest_body(self) -> dict:
        return {
            "request_id": str(self.request_id),
            "tenant_id": str(self.tenant_id),
            "recorded_at": self.recorded_at,
            "outcome": self.outcome.value,
            "provider_id": self.provider_id,
            "content_sha256": self.content_sha256,
            "refusal_reason": (
                self.refusal_reason.value if self.refusal_reason is not None else None),
        }

    def digest(self) -> str:
        """The response digest. Recomputable from a purged tombstone."""

        return canonical_digest(
            EGRESS_RESULT_DIGEST_DOMAIN, "EgressResult", self.digest_body())
