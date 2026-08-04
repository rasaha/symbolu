"""Local birth datetime -> UTC conversion (pure, testable).

Uses the historical IANA timezone database via ``zoneinfo`` (never a fixed UTC
offset). Handles the two DST edge cases explicitly:

- **Ambiguous** local time (fall-back overlap): requires an explicit resolution
  (EARLIER/LATER). Without one, raises ``AMBIGUOUS_LOCAL_TIME``.
- **Nonexistent** local time (spring-forward gap): raises
  ``NONEXISTENT_LOCAL_TIME``; the value is never silently shifted.

UNKNOWN birth time is never converted to a fabricated noon/midnight instant: the
result carries ``utc_instant = None`` and a lowered confidence.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..domain.enums import AmbiguityResolution, BirthTimePrecision
from ..errors import DilChatError, ErrorCode

# APPROXIMATE uncertainty must be explicit and bounded. Beyond this width the input
# should be modeled as UNKNOWN (a full civil day) instead.
MAX_APPROX_UNCERTAINTY_MINUTES = 720  # +/- 12 hours

_UNKNOWN_DAY_ASSUMPTION = "UNKNOWN_CIVIL_DAY_INTERVAL"


@dataclass(frozen=True)
class BirthInstantResult:
    utc_instant: dt.datetime | None
    is_ambiguous: bool
    is_nonexistent: bool
    fold_used: int | None
    time_assumption: str | None  # e.g. "UNKNOWN_TIME_NO_INSTANT"


@dataclass(frozen=True)
class BirthIntervalResult:
    """A UTC interval representing birth-time uncertainty (Area B)."""

    utc_start: dt.datetime
    utc_end: dt.datetime
    is_exact: bool                     # True only for EXACT precision (start == end)
    uncertainty_minutes: int | None    # set for APPROXIMATE
    is_ambiguous: bool                 # EXACT ambiguous-local (resolved) flag
    time_assumption: str | None


def _zone(iana_timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(iana_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DilChatError(
            ErrorCode.VALIDATION_ERROR, f"Unknown IANA timezone: {iana_timezone!r}"
        ) from exc


def is_nonexistent(naive_local: dt.datetime, tz: ZoneInfo) -> bool:
    """A wall-clock time that does not exist (spring-forward gap)."""
    aware = naive_local.replace(tzinfo=tz)
    utc = aware.astimezone(dt.UTC)
    round_trip = utc.astimezone(tz).replace(tzinfo=None)
    return round_trip != naive_local


def is_ambiguous(naive_local: dt.datetime, tz: ZoneInfo) -> bool:
    """A wall-clock time that occurs twice (fall-back overlap)."""
    off0 = naive_local.replace(tzinfo=tz, fold=0).utcoffset()
    off1 = naive_local.replace(tzinfo=tz, fold=1).utcoffset()
    return off0 != off1


def compute_birth_instant(
    *,
    birth_date: dt.date,
    birth_time_local: dt.time | None,
    precision: BirthTimePrecision,
    iana_timezone: str,
    ambiguity_resolution: AmbiguityResolution | None,
) -> BirthInstantResult:
    tz = _zone(iana_timezone)

    if precision is BirthTimePrecision.UNKNOWN or birth_time_local is None:
        # Never fabricate an instant from an unknown time.
        return BirthInstantResult(
            utc_instant=None,
            is_ambiguous=False,
            is_nonexistent=False,
            fold_used=None,
            time_assumption="UNKNOWN_TIME_NO_INSTANT",
        )

    naive_local = dt.datetime.combine(birth_date, birth_time_local)

    if is_nonexistent(naive_local, tz):
        raise DilChatError(
            ErrorCode.NONEXISTENT_LOCAL_TIME,
            "The provided local birth time does not exist in this timezone "
            "(daylight-saving spring-forward gap). Please correct the time.",
        )

    ambiguous = is_ambiguous(naive_local, tz)
    fold_used: int | None = None
    if ambiguous:
        if ambiguity_resolution is None:
            raise DilChatError(
                ErrorCode.AMBIGUOUS_LOCAL_TIME,
                "The provided local birth time occurs twice (daylight-saving "
                "fall-back). Specify ambiguity_resolution = EARLIER or LATER.",
            )
        fold_used = 0 if ambiguity_resolution is AmbiguityResolution.EARLIER else 1

    aware = naive_local.replace(tzinfo=tz, fold=fold_used or 0)
    utc_instant = aware.astimezone(dt.UTC)
    return BirthInstantResult(
        utc_instant=utc_instant,
        is_ambiguous=ambiguous,
        is_nonexistent=False,
        fold_used=fold_used,
        time_assumption=None,
    )


def _localize_to_utc(naive_local: dt.datetime, tz: ZoneInfo, *, fold: int = 0) -> dt.datetime:
    """Localize a naive local wall-time to UTC (no raising; for interval bounds)."""
    return naive_local.replace(tzinfo=tz, fold=fold).astimezone(dt.UTC)


def compute_birth_interval(
    *,
    birth_date: dt.date,
    birth_time_local: dt.time | None,
    precision: BirthTimePrecision,
    iana_timezone: str,
    ambiguity_resolution: AmbiguityResolution | None,
    uncertainty_minutes: int | None,
) -> BirthIntervalResult:
    """Resolve a birth input into a UTC uncertainty interval by precision (Area B)."""
    tz = _zone(iana_timezone)

    if precision is BirthTimePrecision.EXACT:
        instant = compute_birth_instant(
            birth_date=birth_date,
            birth_time_local=birth_time_local,
            precision=precision,
            iana_timezone=iana_timezone,
            ambiguity_resolution=ambiguity_resolution,
        )
        assert instant.utc_instant is not None  # EXACT always yields an instant
        return BirthIntervalResult(
            utc_start=instant.utc_instant,
            utc_end=instant.utc_instant,
            is_exact=True,
            uncertainty_minutes=None,
            is_ambiguous=instant.is_ambiguous,
            time_assumption=None,
        )

    if precision is BirthTimePrecision.APPROXIMATE:
        if birth_time_local is None:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR,
                "APPROXIMATE precision requires a stated local time.",
            )
        if uncertainty_minutes is None:
            raise DilChatError(
                ErrorCode.MISSING_APPROXIMATION_INTERVAL,
                "APPROXIMATE precision requires an explicit uncertainty_minutes.",
            )
        if uncertainty_minutes <= 0 or uncertainty_minutes > MAX_APPROX_UNCERTAINTY_MINUTES:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR,
                f"uncertainty_minutes must be in 1..{MAX_APPROX_UNCERTAINTY_MINUTES}; "
                "use UNKNOWN for broader uncertainty.",
            )
        center = dt.datetime.combine(birth_date, birth_time_local)
        start_local = center - dt.timedelta(minutes=uncertainty_minutes)
        end_local = center + dt.timedelta(minutes=uncertainty_minutes)
        return BirthIntervalResult(
            utc_start=_localize_to_utc(start_local, tz),
            utc_end=_localize_to_utc(end_local, tz),
            is_exact=False,
            uncertainty_minutes=uncertainty_minutes,
            is_ambiguous=False,
            time_assumption=None,
        )

    # UNKNOWN: the entire local civil day [day start, next day start).
    day_start = dt.datetime.combine(birth_date, dt.time(0, 0))
    next_day_start = dt.datetime.combine(birth_date + dt.timedelta(days=1), dt.time(0, 0))
    utc_start = _localize_to_utc(day_start, tz)
    utc_end = _localize_to_utc(next_day_start, tz)
    # Short/long civil days (DST transitions) are handled naturally: the two ends
    # localize with their own offsets, so the UTC span is 23/24/25 h as appropriate.
    return BirthIntervalResult(
        utc_start=utc_start,
        utc_end=utc_end,
        is_exact=False,
        uncertainty_minutes=None,
        is_ambiguous=False,
        time_assumption=_UNKNOWN_DAY_ASSUMPTION,
    )
