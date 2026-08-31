"""Relay liveness probe: ``python -m ugence_dilchat.scripts_relay_health``.

The relay serves no HTTP surface (DEC-3C-4), so its health signal is the
freshness of the heartbeat file it rewrites each loop. Exit 0 = fresh, 1 = stale
or missing/unreadable, 2 = no heartbeat configured (cannot judge — fail closed
rather than report a health the deployment never asked for).

Content-free: reads a timestamp, prints a machine-style status line, never any
event, token, or message.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys

from .base import utcnow
from .config import Settings


def check(settings: Settings | None = None, *, now: dt.datetime | None = None) -> tuple[int, str]:
    settings = settings or Settings()
    now = now or utcnow()
    if not settings.relay_heartbeat_path:
        return 2, "RELAY_HEARTBEAT_NOT_CONFIGURED"
    try:
        raw = pathlib.Path(settings.relay_heartbeat_path).read_text().strip()
    except OSError:
        return 1, "RELAY_HEARTBEAT_MISSING"
    try:
        stamp = dt.datetime.fromisoformat(raw)
    except ValueError:
        return 1, "RELAY_HEARTBEAT_UNREADABLE"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.UTC)
    age = (now - stamp).total_seconds()
    if age > settings.relay_heartbeat_max_age_seconds:
        return 1, f"RELAY_HEARTBEAT_STALE age_seconds={int(age)}"
    return 0, f"RELAY_HEARTBEAT_OK age_seconds={int(max(age, 0))}"


def main() -> None:
    code, message = check()
    print(message)
    sys.exit(code)


if __name__ == "__main__":
    main()
