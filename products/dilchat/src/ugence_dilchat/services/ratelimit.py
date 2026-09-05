"""PostgreSQL-backed fixed-window rate limiting (Phase 3B, DILCHAT-D3B-4).

The ratified limits (Settings, env-overridable) are enforceable safety limits,
not documentation. Enforcement rules:

- **Authorization first.** A limiter is consulted only AFTER the caller's
  authorization for the attempted action has succeeded, so a 429 can never
  substitute for (or leak through) a 404/403 anti-enumeration response, and an
  unauthorized caller can never consume another user's budget.
- **Denials are generic.** The error is the canonical ``RATE_LIMITED`` (429)
  with no window arithmetic disclosed.
- **Denied requests roll back.** A raised error rolls back the request
  transaction, counter increment included; the window still bounds the number
  of *successful* actions, which is the safety property the limits state.
"""

from __future__ import annotations

import uuid

from ..config import Settings
from ..errors import DilChatError, ErrorCode
from ..repositories.safety import RateLimitRepository

_MINUTE = 60
_HOUR = 3600
_DAY = 86400


class RateLimiter:
    def __init__(self, *, settings: Settings, counters: RateLimitRepository) -> None:
        self._settings = settings
        self._counters = counters

    async def _enforce(
        self, subject: uuid.UUID, action_key: str, limits: list[tuple[int, int]]
    ) -> None:
        for window_seconds, maximum in limits:
            count = await self._counters.increment(
                subject_user_id=subject, action_key=action_key, window_seconds=window_seconds
            )
            if count > maximum:
                raise DilChatError(ErrorCode.RATE_LIMITED, "Too many requests. Try again later.")

    async def enforce_send(self, subject: uuid.UUID) -> None:
        await self._enforce(
            subject,
            "send",
            [
                (_MINUTE, self._settings.ratelimit_send_per_minute),
                (_HOUR, self._settings.ratelimit_send_per_hour),
            ],
        )

    async def enforce_report(self, subject: uuid.UUID) -> None:
        await self._enforce(subject, "report", [(_DAY, self._settings.ratelimit_report_per_day)])

    async def enforce_block_mutation(self, subject: uuid.UUID) -> None:
        await self._enforce(
            subject, "block_mut", [(_HOUR, self._settings.ratelimit_block_mutations_per_hour)]
        )
