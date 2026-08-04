"""Astrology provider selection with a hard production guard.

The Swiss provider (AGPL, dev/test only) can be selected only when BOTH the
environment allows it and it is explicitly enabled. In any production-like
environment the registry refuses to build it (raising ``PROVIDER_DISABLED``),
regardless of configuration.
"""

from __future__ import annotations

from ..config import Settings
from ..errors import DilChatError, ErrorCode
from .fake import FakeAstrologyProvider
from .provider import AstrologyProvider


def build_provider(settings: Settings) -> AstrologyProvider:
    provider = settings.astrology_provider
    if provider == "fake":
        return FakeAstrologyProvider()
    if provider == "swiss":
        if not settings.environment.allows_dev_ephemeris:
            raise DilChatError(
                ErrorCode.PROVIDER_DISABLED,
                "Swiss Ephemeris is available only in development/test environments "
                "in this phase (DEC-007 licensing boundary).",
            )
        if not settings.enable_swiss_ephemeris:
            raise DilChatError(
                ErrorCode.PROVIDER_DISABLED,
                "Swiss Ephemeris is not enabled (set DILCHAT_ENABLE_SWISS_EPHEMERIS).",
            )
        from .swiss import SwissEphemerisProvider

        return SwissEphemerisProvider(
            mode=settings.swiss_ephemeris_mode,
            ephemeris_path=settings.swiss_ephemeris_path,
        )
    raise DilChatError(ErrorCode.PROVIDER_DISABLED, f"Unknown astrology provider: {provider!r}")
