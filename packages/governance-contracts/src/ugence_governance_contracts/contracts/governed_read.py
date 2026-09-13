"""The governed-read port — a neutral contract, declared and never implemented.

Stage 1 item 3.5 under ``docs/architecture/STAGE1_CHANGE_EFFECT_CLASSIFIER_CONTRACTS_SCOPING.md``.

Every consumer of governed recalibration state reads it through this port, never by
direct store access. The port lives here, in the neutral contracts package, and
deliberately knows nothing about the classifier: it names no record type, imports
nothing from ``ugence_change_effect_records``, and would be a coherent contract if that
package did not exist. A read port that depended on the producer of the state it guards
would make every reader a dependent of the classifier.

Two properties are load-bearing and are held by the shapes rather than by discipline:

* **The answer is never a bare boolean.** ``ReadEligibility`` is a typed determination
  with a reason, so "not eligible" carries why, and so a caller cannot coerce the answer
  into a truthy value and cache it as permission. A boolean would be indistinguishable
  from a stale ``True``.
* **The answer carries the authorization digest it was computed under.** An eligibility
  computed under an authorization that has since been revoked is identifiable as such by
  a reader holding the determination, which is what makes revocation reach a cache that
  should never have existed.

    THIS MODULE DECLARES A PORT. IT COMPUTES NO ELIGIBILITY, HOLDS NO STATE,
    CACHES NOTHING, READS NO STORE AND IMPLEMENTS NOTHING.

There is no implementation here and none anywhere: a ``Protocol`` with no
implementation cannot serve a read. The determination is made by governed memory in
Stage 3, which does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from ..errors import ProviderProtocolError


class ReadPurpose(str, Enum):
    """Why a consumer is asking. The purpose is part of the question, not a hint.

    A determination is made for one purpose and is not transferable to another: state a
    consumer may read to explain a past decision is not thereby state it may read to make
    a new one.
    """

    DECISION_INPUT = "DECISION_INPUT"
    EXPLANATION = "EXPLANATION"
    AUDIT = "AUDIT"


class ReadEligibilityStatus(str, Enum):
    """The determination itself. ``INDETERMINATE`` is fail-safe and never permission."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INDETERMINATE = "INDETERMINATE"


class ReadIneligibilityReason(str, Enum):
    """Why a read was refused. Required whenever the status is not ``ELIGIBLE``."""

    NO_AUTHORIZATION = "NO_AUTHORIZATION"
    AUTHORIZATION_REVOKED = "AUTHORIZATION_REVOKED"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    NOT_APPLIED = "NOT_APPLIED"
    TARGET_VERSION_MISMATCH = "TARGET_VERSION_MISMATCH"
    PURPOSE_NOT_PERMITTED = "PURPOSE_NOT_PERMITTED"
    CONSUMER_NOT_PERMITTED = "CONSUMER_NOT_PERMITTED"
    DETERMINATION_UNAVAILABLE = "DETERMINATION_UNAVAILABLE"


@dataclass(frozen=True)
class GovernedReadRequest:
    """What a consumer asks. Every field is part of the question."""

    tenant_id: str
    consumer_id: str
    purpose: ReadPurpose
    target_id: str
    target_version: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "consumer_id", "target_id", "target_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ProviderProtocolError(f"{name} must be a non-empty string")
        if not isinstance(self.purpose, ReadPurpose):
            raise ProviderProtocolError("purpose must be a ReadPurpose")


@dataclass(frozen=True)
class ReadEligibility:
    """A typed determination. Never a boolean, and never valid for another question.

    It restates the request's coordinates so a determination cannot be detached from
    what it was an answer to, and carries ``authorization_digest`` so a holder can tell
    which authorization it rests on.
    """

    status: ReadEligibilityStatus
    tenant_id: str
    consumer_id: str
    purpose: ReadPurpose
    target_id: str
    target_version: str
    authorization_digest: str
    reason: ReadIneligibilityReason | None = None

    def __post_init__(self) -> None:
        for name in ("tenant_id", "consumer_id", "target_id", "target_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ProviderProtocolError(f"{name} must be a non-empty string")
        if self.status is ReadEligibilityStatus.ELIGIBLE:
            if self.reason is not None:
                raise ProviderProtocolError("an eligible determination carries no reason")
            if not isinstance(self.authorization_digest, str) or not self.authorization_digest.strip():
                raise ProviderProtocolError(
                    "an eligible determination names the authorization it was computed under"
                )
        elif self.reason is None:
            raise ProviderProtocolError(
                "a determination that is not ELIGIBLE must carry its reason"
            )

    def __bool__(self) -> bool:
        """Refuse truthiness. A determination is read, never coerced.

        ``if eligibility:`` is the mistake this port exists to prevent: it would treat
        ``INDETERMINATE`` as permission and would keep working after a revocation.
        """

        raise ProviderProtocolError(
            "ReadEligibility has no truth value: compare its status explicitly"
        )

    def answers(self, request: GovernedReadRequest) -> bool:
        """Whether this determination is an answer to exactly this question.

        A pure comparison of the coordinates both already carry. It reads no state,
        consults no authorization and decides no eligibility.
        """

        return (
            self.tenant_id == request.tenant_id
            and self.consumer_id == request.consumer_id
            and self.purpose is request.purpose
            and self.target_id == request.target_id
            and self.target_version == request.target_version
        )


@runtime_checkable
class GovernedReadPort(Protocol):
    """The port. One method, one typed answer, no implementation anywhere.

    An implementation belongs to governed memory in Stage 3 and does not exist. It must
    determine eligibility per request rather than serve a cached boolean: a revoked
    entry cannot stay readable through a cache.
    """

    def determine(self, request: GovernedReadRequest) -> ReadEligibility: ...
