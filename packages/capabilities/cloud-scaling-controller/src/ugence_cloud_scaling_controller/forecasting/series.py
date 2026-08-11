"""``CanonicalCapacitySeries`` — an immutable, versioned, provider-neutral ordered history
of :class:`~..canonical.state.CanonicalCapacityState` observations for ONE subject.

A series is the input to shadow forecasting. It binds a single :class:`CapacitySubject`
(tenant and scope identity included), the ordered observations, the event-time range, the
observation count, a schema version, an explicit :class:`SeriesConstructionPolicy`, and a
deterministic content digest.

Event time is the observation's ``observed_at`` — never a collection or production time.
The series enforces, and fails closed on:

* subject / tenant / scope inconsistency (cross-subject or cross-tenant contamination),
* naive timestamps (unless the policy explicitly permits them),
* invalid event-time ordering,
* conflicting duplicate observations (same timestamp, different content) — ALWAYS rejected.

Every transformation that is not identity-preserving — sorting out-of-order input,
collapsing identical duplicates — requires an explicit policy opt-in and is disclosed
(``applied_sort`` / ``collapsed_duplicate_count``) so evidence never hides it. Missing
capacity signals are never imputed here; a state that lacks a measurement simply lacks it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..canonical.identity import CapacitySubject
from ..canonical.serialization import content_digest
from ..canonical.state import CanonicalCapacityState

CANONICAL_SERIES_SCHEMA_VERSION = "capacity-series-1"


class SeriesErrorReason(str, Enum):
    """Typed classification of a series-construction failure.

    Lets a controlled admission/service boundary map a *data-quality* construction failure
    to a typed forecasting abstention, while programming/type errors stay hard failures."""

    EMPTY = "empty"
    TYPE = "type"
    CROSS_SUBJECT = "cross_subject"
    CROSS_TENANT = "cross_tenant"
    NAIVE_TIMESTAMP = "naive_timestamp"
    INVALID_TIME_ORDER = "invalid_time_order"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"


class SeriesError(ValueError):
    """Raised when a series cannot be constructed safely (fail closed).

    Carries an optional typed :class:`SeriesErrorReason` so a service boundary can map
    expected data-quality failures to typed abstentions (and re-raise everything else)."""

    def __init__(self, message: str, *, reason: Optional["SeriesErrorReason"] = None):
        super().__init__(message)
        self.reason = reason


class OrderingPolicy(str, Enum):
    """How to treat input whose event times are not already ascending."""

    REQUIRE_SORTED = "require_sorted"   # default: reject non-ascending input (fail closed)
    SORT = "sort"                       # explicitly permit a stable sort (disclosed)


class DuplicateTimestampPolicy(str, Enum):
    """How to treat multiple observations sharing an event time.

    Conflicting duplicates (same timestamp, DIFFERENT content) are ALWAYS rejected,
    regardless of this policy — that is a fail-closed invariant, not a knob.
    """

    REJECT = "reject"                       # default: any duplicate timestamp fails closed
    COLLAPSE_IDENTICAL = "collapse_identical"  # identical duplicates collapse to one


@dataclass(frozen=True)
class SeriesConstructionPolicy:
    """Explicit, deterministic policy governing series construction.

    Safe defaults reject: ``REQUIRE_SORTED`` ordering, ``REJECT`` duplicates, and
    timezone-aware timestamps required. Every non-identity transformation must be
    turned on here and is then disclosed in the series and its evidence.
    """

    policy_id: str = "series-strict-default"
    ordering: OrderingPolicy = OrderingPolicy.REQUIRE_SORTED
    duplicate_timestamp: DuplicateTimestampPolicy = DuplicateTimestampPolicy.REJECT
    require_timezone_aware: bool = True
    description: str = ""
    schema_version: str = CANONICAL_SERIES_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or self.policy_id == "":
            raise SeriesError("policy_id must be a non-empty string")
        if not isinstance(self.ordering, OrderingPolicy):
            raise SeriesError("ordering must be an OrderingPolicy")
        if not isinstance(self.duplicate_timestamp, DuplicateTimestampPolicy):
            raise SeriesError("duplicate_timestamp must be a DuplicateTimestampPolicy")
        if not isinstance(self.require_timezone_aware, bool):
            raise SeriesError("require_timezone_aware must be a bool")

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "ordering": self.ordering.value,
            "duplicate_timestamp": self.duplicate_timestamp.value,
            "require_timezone_aware": self.require_timezone_aware,
            "description": self.description,
        }

    def digest(self) -> str:
        return content_digest(
            "series_construction_policy", self.schema_version, self.to_canonical_dict()
        )


def _as_utc(value: datetime) -> datetime:
    """Total ordering helper: naive datetimes are treated as UTC (only reached when the
    policy explicitly permits naive timestamps)."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass(frozen=True)
class CanonicalCapacitySeries:
    """Immutable, versioned ordered history of canonical states for one subject."""

    schema_version: str
    subject: CapacitySubject
    states: Tuple[CanonicalCapacityState, ...]
    construction_policy: SeriesConstructionPolicy
    applied_sort: bool
    collapsed_duplicate_count: int

    # ---- construction -------------------------------------------------------------
    @classmethod
    def build(
        cls,
        states: Iterable[CanonicalCapacityState],
        policy: Optional[SeriesConstructionPolicy] = None,
    ) -> "CanonicalCapacitySeries":
        """Construct a validated series from ``states`` under ``policy`` (fail-closed)."""
        policy = policy or SeriesConstructionPolicy()
        if not isinstance(policy, SeriesConstructionPolicy):
            raise SeriesError("policy must be a SeriesConstructionPolicy",
                              reason=SeriesErrorReason.TYPE)

        materialized: List[CanonicalCapacityState] = list(states)
        if not materialized:
            raise SeriesError("a series requires at least one observation",
                              reason=SeriesErrorReason.EMPTY)
        for s in materialized:
            if not isinstance(s, CanonicalCapacityState):
                raise SeriesError("every series item must be a CanonicalCapacityState",
                                  reason=SeriesErrorReason.TYPE)

        subject = materialized[0].subject
        for s in materialized:
            if s.subject != subject:
                if s.subject.workload_id != subject.workload_id:
                    raise SeriesError(
                        "cross-subject contamination: all observations must share one "
                        f"subject; got workload_id {s.subject.workload_id!r} != "
                        f"{subject.workload_id!r}",
                        reason=SeriesErrorReason.CROSS_SUBJECT,
                    )
                raise SeriesError(
                    "cross-tenant/scope contamination: subject/tenant/scope identity "
                    "differs across observations",
                    reason=SeriesErrorReason.CROSS_TENANT,
                )

        if policy.require_timezone_aware:
            for s in materialized:
                if s.observed_at.tzinfo is None:
                    raise SeriesError(
                        "timezone-aware observed_at required by policy; got a naive "
                        "datetime (enable require_timezone_aware=False to allow naive)",
                        reason=SeriesErrorReason.NAIVE_TIMESTAMP,
                    )

        # Ordering.
        applied_sort = False
        if policy.ordering is OrderingPolicy.SORT:
            before = [id(s) for s in materialized]
            materialized.sort(key=lambda s: _as_utc(s.observed_at))
            applied_sort = [id(s) for s in materialized] != before
        else:  # REQUIRE_SORTED
            for a, b in zip(materialized, materialized[1:]):
                if _as_utc(a.observed_at) > _as_utc(b.observed_at):
                    raise SeriesError(
                        "invalid event-time order: observations are not ascending and "
                        "ordering policy is REQUIRE_SORTED (enable ordering=SORT to permit "
                        "an explicit, disclosed sort)",
                        reason=SeriesErrorReason.INVALID_TIME_ORDER,
                    )

        # Duplicate timestamps (now that equal timestamps are adjacent).
        collapsed = 0
        deduped: List[CanonicalCapacityState] = []
        i = 0
        n = len(materialized)
        while i < n:
            j = i + 1
            while j < n and _as_utc(materialized[j].observed_at) == _as_utc(materialized[i].observed_at):
                j += 1
            group = materialized[i:j]
            if len(group) == 1:
                deduped.append(group[0])
            else:
                digests = {g.digest() for g in group}
                if len(digests) > 1:
                    raise SeriesError(
                        "conflicting duplicate: multiple observations share event time "
                        f"{group[0].observed_at.isoformat()} but differ in content "
                        "(always rejected, fail closed)",
                        reason=SeriesErrorReason.CONFLICTING_DUPLICATE,
                    )
                # Identical duplicates.
                if policy.duplicate_timestamp is DuplicateTimestampPolicy.COLLAPSE_IDENTICAL:
                    deduped.append(group[0])
                    collapsed += len(group) - 1
                else:  # REJECT
                    raise SeriesError(
                        "duplicate timestamp: multiple identical observations share event "
                        f"time {group[0].observed_at.isoformat()} and duplicate policy is "
                        "REJECT (enable COLLAPSE_IDENTICAL to collapse identical duplicates)",
                        reason=SeriesErrorReason.DUPLICATE_TIMESTAMP,
                    )
            i = j

        return cls(
            schema_version=policy.schema_version,
            subject=subject,
            states=tuple(deduped),
            construction_policy=policy,
            applied_sort=applied_sort,
            collapsed_duplicate_count=collapsed,
        )

    # ---- accessors ----------------------------------------------------------------
    @property
    def observation_count(self) -> int:
        return len(self.states)

    @property
    def start_event_time(self) -> datetime:
        return self.states[0].observed_at

    @property
    def end_event_time(self) -> datetime:
        return self.states[-1].observed_at

    @property
    def tenant_id(self) -> Optional[str]:
        return self.subject.tenant_id

    def state_digests(self) -> Tuple[str, ...]:
        return tuple(s.digest() for s in self.states)

    def observations_at_or_before(self, cutoff: datetime) -> Tuple[CanonicalCapacityState, ...]:
        """Return the observations whose EVENT time is ``<= cutoff``.

        This is the sole leakage-safe accessor a forecast input window is built from:
        no observation with an event time strictly after the cutoff can be returned.
        """
        c = _as_utc(cutoff)
        return tuple(s for s in self.states if _as_utc(s.observed_at) <= c)

    # ---- identity -----------------------------------------------------------------
    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject": self.subject.to_canonical_dict(),
            "observation_count": self.observation_count,
            "start_event_time": self.start_event_time,
            "end_event_time": self.end_event_time,
            "state_digests": list(self.state_digests()),
            "construction_policy": self.construction_policy.to_canonical_dict(),
            "applied_sort": self.applied_sort,
            "collapsed_duplicate_count": self.collapsed_duplicate_count,
        }

    def digest(self) -> str:
        """Stable ``sha256:`` content identity of this series."""
        return content_digest("capacity_series", self.schema_version, self.to_canonical_dict())


__all__ = [
    "CANONICAL_SERIES_SCHEMA_VERSION",
    "SeriesError",
    "SeriesErrorReason",
    "OrderingPolicy",
    "DuplicateTimestampPolicy",
    "SeriesConstructionPolicy",
    "CanonicalCapacitySeries",
]
