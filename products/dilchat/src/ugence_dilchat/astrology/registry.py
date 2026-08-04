"""Astrology provider selection enforcing the environment policy (Area A).

This is a defence-in-depth check on top of ``Settings`` validation: even if a
config somehow reaches here, the registry refuses a provider not permitted for the
environment, and refuses the Swiss adapter in production-like environments without
a recorded licensing decision. There is no silent fallback to ``fake``.
"""

from __future__ import annotations

from ..config import Settings
from ..errors import DilChatError, ErrorCode
from .fake import FakeAstrologyProvider
from .provider import AstrologyProvider


def build_provider(settings: Settings) -> AstrologyProvider:
    provider = settings.astrology_provider
    permitted = settings.permitted_providers()
    if provider not in permitted:
        raise DilChatError(
            ErrorCode.PROVIDER_NOT_PERMITTED,
            f"Provider {provider!r} is not permitted in environment "
            f"{settings.environment.value!r} (permitted: {sorted(permitted) or 'none'}).",
        )

    if provider == "fake":
        # Never reachable in qa (without opt-in) / staging / production due to the
        # permitted-set check above.
        return FakeAstrologyProvider()

    if provider == "swiss":
        if settings.environment.is_production_like and not settings.swiss_production_licensed:
            raise DilChatError(
                ErrorCode.PROVIDER_NOT_PERMITTED,
                "Swiss Ephemeris requires a recorded production-licensing decision "
                "(swiss_production_licensed) in staging/production.",
            )
        if not settings.environment.is_production_like and not settings.enable_swiss_ephemeris:
            raise DilChatError(
                ErrorCode.PROVIDER_DISABLED,
                "Swiss Ephemeris is not enabled (set DILCHAT_ENABLE_SWISS_EPHEMERIS).",
            )
        from .swiss import SwissEphemerisProvider

        return SwissEphemerisProvider(
            mode=settings.swiss_ephemeris_mode,
            ephemeris_path=settings.swiss_ephemeris_path,
        )

    raise DilChatError(ErrorCode.PROVIDER_NOT_PERMITTED, f"Unknown provider: {provider!r}")


def is_real_provider(provider: AstrologyProvider) -> bool:
    return getattr(provider, "provider_id", None) != "fake"
