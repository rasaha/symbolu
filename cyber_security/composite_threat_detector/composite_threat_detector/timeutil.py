"""Deterministic time handling — event data only, never wall-clock (§13).

Replay mode must be reproducible, so the analyzer never reads the system clock.
Time enters only as event data: an RFC-3339 ``timestamp`` (parsed to epoch
seconds) or a numeric ``at``. When neither is present the analyzer falls back to
the monotonic step position, and aging is measured in steps.
"""

from __future__ import annotations

from datetime import datetime, timezone

_FMTS = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ")


def parse_epoch(value) -> float | None:
    """Parse a supplied time value to epoch seconds, or None.

    Accepts a numeric epoch, or an RFC-3339 UTC timestamp string. Uses a fixed
    parse — no ``datetime.now``, no local timezone — so it is replay-stable.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        for fmt in _FMTS:
            try:
                dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
                return dt.timestamp()
            except ValueError:
                continue
    return None


def event_epoch(event: dict) -> float | None:
    """Preferred event time, if any: ``timestamp`` (RFC-3339) or numeric ``at``."""
    if "timestamp" in event:
        e = parse_epoch(event["timestamp"])
        if e is not None:
            return e
    if "at" in event:
        return parse_epoch(event["at"])
    return None
