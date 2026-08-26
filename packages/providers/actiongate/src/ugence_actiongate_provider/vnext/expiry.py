"""The inclusive-expiry boundary.

One rule, stated once, so that every layer agrees on the boundary instant:

    an authorization is expired when ``now >= expires_at``

The instant an authorization expires, it is expired — not still valid for that
tick. This matches ``ugence_action_clearance``, which applies the same rule in
two places and labels it in both (``evaluation/__init__.py:102`` for
authorization validity, ``:251`` for signal validity). Before this module the
two layers disagreed by one instant: the control-plane adapter computed
``cer.expires_at < now``, which treats the boundary instant as still valid,
while Action Clearance treated it as expired. A one-instant disagreement about
whether an authorization is live is not a rounding detail — it is a window in
which one layer will authorize what the other has already retired.

This function reads no clock. ``now`` is always supplied by the caller, so
expiry stays a pure comparison and callers keep their injected-clock
determinism.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def is_expired(now: datetime, expires_at: Optional[datetime]) -> bool:
    """Return whether ``expires_at`` has been reached at ``now`` (inclusive).

    An authorization with no expiry never expires, so ``expires_at=None`` is
    ``False``. Comparing an aware to a naive datetime raises ``TypeError`` from
    the standard library rather than being silently coerced — a timezone
    mismatch is a caller bug, and guessing which side is UTC would be a way to
    authorize past an expiry by an unknown offset.
    """
    if expires_at is None:
        return False
    return now >= expires_at


__all__ = ["is_expired"]
