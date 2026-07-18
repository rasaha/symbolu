"""Injectable clock producing the harness's RFC-3339 UTC millisecond timestamps.

The reference gate parses timestamps as ``%Y-%m-%dT%H:%M:%S.%fZ`` and the
envelope schema requires exactly three fractional digits, so every timestamp the
gateway emits must be millisecond-precision UTC with a trailing ``Z``. A
``FixedClock`` makes runtime decisions reproducible in tests and demos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def format_ts(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


class Clock:
    """Wall-clock source. Subclass to control time."""

    def now_dt(self) -> datetime:  # pragma: no cover - overridden
        raise NotImplementedError

    def now(self) -> str:
        return format_ts(self.now_dt())

    def plus(self, seconds: float) -> str:
        return format_ts(self.now_dt() + timedelta(seconds=seconds))


class RealClock(Clock):
    def now_dt(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock(Clock):
    """Deterministic clock for tests/demos; advanceable."""

    def __init__(self, start: str = "2026-07-12T14:00:00.000Z"):
        self._dt = parse_ts(start)

    def now_dt(self) -> datetime:
        return self._dt

    def advance(self, seconds: float) -> None:
        self._dt = self._dt + timedelta(seconds=seconds)

    def set(self, ts: str) -> None:
        self._dt = parse_ts(ts)
