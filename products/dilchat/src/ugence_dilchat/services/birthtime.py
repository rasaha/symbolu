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


@dataclass(frozen=True)
class BirthInstantResult:
    utc_instant: dt.datetime | None
    is_ambiguous: bool
    is_nonexistent: bool
    fold_used: int | None
    time_assumption: str | None  # e.g. "UNKNOWN_TIME_NO_INSTANT"


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
