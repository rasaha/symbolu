"""Natal-Moon service: deterministic derivation into immutable snapshots.

Given a user's latest birth profile, derive the sidereal Moon (longitude, rashi,
nakshatra, pada) via the configured :class:`AstrologyProvider` and persist an
immutable snapshot keyed by the (birth-profile version, provider) tuple. Recomputing
the same tuple returns the existing snapshot (determinism + immutability).

Unknown birth time is never treated as exact: an explicit noon-UTC assumption is
recorded in provenance/``time_assumption`` and the (already lowered) birth-time
confidence propagates to the snapshot.
"""

from __future__ import annotations

import datetime as dt
import uuid

from ..astrology.provider import AstrologyProvider, EphemerisUnavailableError
from ..audit.service import AuditService
from ..domain.enums import AuditAction
from ..errors import DilChatError, ErrorCode
from ..infrastructure.orm import BirthProfile, NatalChartSnapshot
from ..repositories.birth_profiles import BirthProfileRepository, NatalRepository

_ASSUMED_NOON = "ASSUMED_NOON_UTC_UNKNOWN_PRECISION"


class NatalService:
    def __init__(
        self,
        *,
        provider: AstrologyProvider,
        profiles: BirthProfileRepository,
        natal: NatalRepository,
        audit: AuditService,
    ) -> None:
        self._provider = provider
        self._profiles = profiles
        self._natal = natal
        self._audit = audit

    async def compute_for_user(
        self, user_id: uuid.UUID, correlation_id: str | None = None
    ) -> NatalChartSnapshot:
        profile = await self._profiles.latest_for_user(user_id)
        if profile is None:
            raise DilChatError(ErrorCode.NOT_FOUND, "No birth profile found for user.")

        instant, time_assumption = self._resolve_instant(profile)

        existing = await self._natal.find_by_version_tuple(
            birth_profile_id=profile.id,
            birth_profile_version=profile.version,
            provider_id=self._provider.provider_id,
            provider_version=self._provider.provider_version,
            ephemeris_mode=self._provider.ephemeris_mode,
            ayanamsa=self._provider.ayanamsa,
        )
        if existing is not None:
            return existing  # immutable; identical inputs+versions => identical result

        try:
            result = self._provider.compute_moon(
                instant,
                input_confidence=profile.input_confidence,
                time_assumption=time_assumption,
            )
        except EphemerisUnavailableError as exc:
            raise DilChatError(ErrorCode.EPHEMERIS_UNAVAILABLE, str(exc)) from exc

        d = result.derivation
        p = result.provenance
        snapshot = NatalChartSnapshot(
            birth_profile_id=profile.id,
            birth_profile_version=profile.version,
            user_id=user_id,
            provider_id=p.provider_id,
            provider_version=p.provider_version,
            ephemeris_mode=p.ephemeris_mode,
            ayanamsa=p.ayanamsa,
            julian_day=result.julian_day,
            moon_longitude=d.longitude,
            rashi_index=d.rashi_index,
            rashi_name=d.rashi_name,
            nakshatra_index=d.nakshatra_index,
            nakshatra_name=d.nakshatra_name,
            pada=d.pada,
            numerical_precision_class=p.numerical_precision_class,
            fallback_used=p.fallback_used,
            fallback_reason=p.fallback_reason,
            input_confidence=p.input_confidence,
            time_assumption=time_assumption,
            calculation_timestamp=p.calculation_timestamp,
            trace=result.trace,
        )
        await self._natal.add(snapshot)
        await self._audit.record(
            action=AuditAction.NATAL_MOON_COMPUTED,
            actor_user_id=user_id,
            resource_type="natal_chart_snapshot",
            resource_id=snapshot.id,
            correlation_id=correlation_id,
            provenance=p.to_dict(),
        )
        return snapshot

    async def latest_for_user(self, user_id: uuid.UUID) -> NatalChartSnapshot | None:
        return await self._natal.latest_for_user(user_id)

    def _resolve_instant(self, profile: BirthProfile) -> tuple[dt.datetime, str | None]:
        if profile.utc_birth_instant is not None:
            instant = profile.utc_birth_instant
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=dt.UTC)
            return instant, None
        # UNKNOWN birth time: explicit, flagged noon-UTC assumption (never silent).
        assumed = dt.datetime.combine(
            profile.birth_date, dt.time(12, 0), tzinfo=dt.UTC
        )
        return assumed, _ASSUMED_NOON
