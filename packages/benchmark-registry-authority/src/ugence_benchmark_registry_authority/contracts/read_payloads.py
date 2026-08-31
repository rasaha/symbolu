"""Two read payloads, two exact types, and neither can stand in for the other.

D-09 as ratified keeps trusted resolution and historical inspection apart by
**type**, not by documentation:

* :class:`BenchmarkResolutionRecordPayload` — the structural shape a
  trusted-resolution answer takes at BR-2A.
* :class:`BenchmarkHistoricalRecordPayload` — the structural shape a historical
  answer takes. It **discloses its ``as_of`` and its historical nature**, and it
  is a **different exact type** that cannot satisfy an API expecting a
  resolution payload, nor the reverse.

Why type separation and not a flag
-----------------------------------
"Type separation, not documentation, is what stops a historical answer from
being consumed as a current one." A single payload with an
``is_historical=True`` flag would be one forgotten branch away from a caller
acting on a revoked benchmark's last good state; two types make the mistake a
:class:`TypeError` at the boundary instead of a silent authorization. The two
also occupy **different canonical byte spaces**, so they cannot be confused at
the digest level either.

:func:`require_exact_resolution_record_payload` and
:func:`require_exact_historical_record_payload` are the pure type guards that
make the separation testable. They are validators, not resolvers: they check the
exact type of an object a caller already holds and return it. Neither performs a
lookup, consults a store, reads a clock or establishes anything.

Neither payload authorizes anything
-----------------------------------
Both carry §09's five permanent ``False`` derivations, and both add
:attr:`authorizes_execution` and :attr:`active_eligibility_established`,
permanently ``False``. B-9: possession is not validity, retrieval is not
resolution. Holding either object — or any digest of it — authorizes no
execution and establishes no active eligibility.

**The authoritative result type does not exist here.** It belongs to BR-2D,
after real verification exists, and its name (``BenchmarkResolution``) is
reserved and undefined at BR-2A. A caller can construct a
:class:`BenchmarkResolutionRecordPayload` all day and never construct a
resolution, because there is no resolution type to construct.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ugence_benchmark_registry import BenchmarkCoordinate

from ._authority import permanently_unverified_authority
from ._validation import (
    require_aware_datetime,
    require_digest,
    require_enum_member,
    require_exact_type,
    require_identifier,
)
from .canonical import (
    BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    _register_contract_type,
)
from .enums import BenchmarkRegistrationState

__all__ = [
    "BenchmarkResolutionRecordPayload",
    "BenchmarkHistoricalRecordPayload",
    "require_exact_resolution_record_payload",
    "require_exact_historical_record_payload",
]


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkResolutionRecordPayload:
    """The structural shape of a trusted-resolution answer at BR-2A.

    It carries **no** ``as_of``: trusted resolution is a present-tense question,
    and an instant on the answer would invite a caller to reason about when it
    was true.

    :attr:`declared_registration_state` is a *declaration*. A payload saying
    ``REGISTERED`` was registered by nobody; a payload saying ``REVOKED`` revoked
    nothing. Under D-09's ``DENY_ALWAYS`` a revoked artifact never resolves as
    admissible — but nothing here enforces that, because nothing here resolves.
    """

    #: The exact BR-1 locator this answer is about.
    coordinate: BenchmarkCoordinate

    #: The registry state this answer declares. Declared, never established.
    declared_registration_state: BenchmarkRegistrationState

    #: The immutable admitted digest declared for the locator — the content
    #: address D-05 pins by requiring the embedded lifecycle state to be exactly
    #: ``APPROVED`` at admission.
    declared_admitted_digest: str

    #: The registry authority this answer declares it came from. Unverified.
    declared_registry_authority_identity: str

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")
        require_enum_member(
            self.declared_registration_state,
            BenchmarkRegistrationState,
            "declared_registration_state",
        )
        require_digest(self.declared_admitted_digest, "declared_admitted_digest")
        require_identifier(
            self.declared_registry_authority_identity,
            "declared_registry_authority_identity",
        )

    @property
    def is_historical_disclosure(self) -> bool:
        """Permanently ``False``. This shape carries no ``as_of`` to disclose."""

        return False

    @property
    def authorizes_execution(self) -> bool:
        """Permanently ``False``. B-9: retrieval is not resolution."""

        return False

    @property
    def active_eligibility_established(self) -> bool:
        """Permanently ``False``. Nothing here establishes current eligibility."""

        return False


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkHistoricalRecordPayload:
    """The structural shape of a historical-inspection answer. A **different** type.

    Discloses its :attr:`as_of` and its historical nature
    (:attr:`is_historical_disclosure` is permanently ``True``), so a consumer
    cannot mistake it for a current answer even if it ignores the type.

    It cannot satisfy an API expecting a
    :class:`BenchmarkResolutionRecordPayload`, and that payload cannot satisfy
    one expecting this — proved by
    :func:`require_exact_resolution_record_payload` and
    :func:`require_exact_historical_record_payload`, which use exact-type checks
    rather than ``isinstance``, so not even a subclass slips through.

    A historical answer is **never admissible**. It says what the registry held
    at an instant; it never says a caller may rely on it now.
    """

    #: The exact BR-1 locator this answer is about.
    coordinate: BenchmarkCoordinate

    #: The registry state declared **as of** :attr:`as_of`. Declared, never
    #: established.
    declared_registration_state: BenchmarkRegistrationState

    #: The immutable admitted digest declared for the locator.
    declared_admitted_digest: str

    #: The registry authority this answer declares it came from. Unverified.
    declared_registry_authority_identity: str

    #: The instant this answer is about — mandatory, caller-supplied, disclosed,
    #: and digest-participating. It never relaxes authorization and never
    #: bypasses ``DENY_ALWAYS``.
    as_of: datetime

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")
        require_enum_member(
            self.declared_registration_state,
            BenchmarkRegistrationState,
            "declared_registration_state",
        )
        require_digest(self.declared_admitted_digest, "declared_admitted_digest")
        require_identifier(
            self.declared_registry_authority_identity,
            "declared_registry_authority_identity",
        )
        require_aware_datetime(self.as_of, "as_of")

    @property
    def is_historical_disclosure(self) -> bool:
        """Permanently ``True``. This shape is historical and says so."""

        return True

    @property
    def authorizes_execution(self) -> bool:
        """Permanently ``False``. A historical answer is never admissible."""

        return False

    @property
    def active_eligibility_established(self) -> bool:
        """Permanently ``False``. History establishes no current eligibility."""

        return False


def require_exact_resolution_record_payload(
    value: object,
) -> BenchmarkResolutionRecordPayload:
    """Pure type guard: accept **only** a :class:`BenchmarkResolutionRecordPayload`.

    Exact-type, so a :class:`BenchmarkHistoricalRecordPayload` is refused, and so
    is any subclass of either. This is the boundary that makes "a historical
    answer cannot be consumed as a current one" a mechanical fact.

    Performs no lookup, consults no store, reads no clock, and establishes
    nothing. It checks the exact type of an object the caller already holds.
    """

    require_exact_type(
        value,
        BenchmarkResolutionRecordPayload,
        "exact resolution record payload",
    )
    return value  # type: ignore[return-value]


def require_exact_historical_record_payload(
    value: object,
) -> BenchmarkHistoricalRecordPayload:
    """Pure type guard: accept **only** a :class:`BenchmarkHistoricalRecordPayload`.

    The mirror of :func:`require_exact_resolution_record_payload`, and equally
    strict in the other direction: a resolution payload is refused here.
    """

    require_exact_type(
        value,
        BenchmarkHistoricalRecordPayload,
        "historical record payload",
    )
    return value  # type: ignore[return-value]


for _cls, _domain in (
    (
        BenchmarkResolutionRecordPayload,
        BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    ),
    (
        BenchmarkHistoricalRecordPayload,
        BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN,
    ),
):
    _register_contract_type(_cls, _domain, root_canonicalizable=True)
del _cls, _domain
