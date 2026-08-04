"""Natal-Moon service: deterministic interval evaluation into immutable snapshots.

Given a user's latest birth profile and its UTC uncertainty interval (Area B), the
service evaluates the Moon's classification across the interval (single instant for
EXACT inputs) and persists an immutable snapshot keyed by the (birth-profile
version, provider) tuple.

Provider safety (Area A): a synthetic (fake) result is never persisted as an
authoritative snapshot — it is tagged ``synthetic``/``test_only`` and
``authoritative=False``. A real provider yields an authoritative snapshot.
"""

from __future__ import annotations

import datetime as dt
import uuid

from ..astrology.interval import evaluate_interval
from ..astrology.provider import AstrologyProvider, EphemerisUnavailableError
from ..audit.service import AuditService
from ..domain.enums import AuditAction, BirthTimePrecision, ProviderKind
from ..errors import DilChatError, ErrorCode
from ..infrastructure.orm import BirthProfile, NatalChartSnapshot
from ..repositories.birth_profiles import BirthProfileRepository, NatalRepository


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

        start, end = self._interval(profile)

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

        exact = profile.birth_time_precision == BirthTimePrecision.EXACT.value and start == end
        try:
            result = evaluate_interval(
                self._provider,
                start,
                end,
                input_confidence=profile.input_confidence,
                exact=exact,
                time_assumption=(
                    None if profile.utc_birth_instant is not None else "INTERVAL_INPUT"
                ),
            )
        except EphemerisUnavailableError as exc:
            raise DilChatError(ErrorCode.EPHEMERIS_UNAVAILABLE, str(exc)) from exc

        p = result.provenance
        synthetic = result.synthetic
        rashi = result.moon_rashi
        nak = result.moon_nakshatra
        pada = result.moon_pada

        snapshot = NatalChartSnapshot(
            birth_profile_id=profile.id,
            birth_profile_version=profile.version,
            user_id=user_id,
            provider_id=p.provider_id,
            provider_version=p.provider_version,
            ephemeris_mode=p.ephemeris_mode,
            ayanamsa=p.ayanamsa,
            julian_day=self._provider.julian_day(start),
            moon_longitude=result.longitude_start,
            longitude_end=result.longitude_end,
            # Definitive single values only when the field is EXACT/STABLE.
            rashi_index=rashi.value,
            rashi_name=rashi.name,
            nakshatra_index=nak.value,
            nakshatra_name=nak.name,
            pada=pada.value,
            utc_interval_start=start,
            utc_interval_end=end,
            rashi_status=rashi.status.value,
            nakshatra_status=nak.status.value,
            pada_status=pada.status.value,
            rashi_possible=rashi.possible_values,
            nakshatra_possible=nak.possible_values,
            pada_possible=pada.possible_values,
            guna_eligibility=result.guna_eligibility.value,
            provider_kind=ProviderKind.SYNTHETIC.value if synthetic else ProviderKind.REAL.value,
            synthetic=synthetic,
            test_only=synthetic,          # fake output is test-only
            authoritative=not synthetic,  # never persist synthetic as authoritative
            requires_recalculation=False,
            numerical_precision_class=p.numerical_precision_class,
            fallback_used=p.fallback_used,
            fallback_reason=p.fallback_reason,
            input_confidence=p.input_confidence,
            time_assumption=p.time_assumption,
            calculation_timestamp=p.calculation_timestamp,
            trace=result.trace,
        )
        self._assert_persist_allowed(snapshot)
        await self._natal.add(snapshot)
        await self._audit.record(
            action=AuditAction.NATAL_MOON_COMPUTED,
            actor_user_id=user_id,
            resource_type="natal_chart_snapshot",
            resource_id=snapshot.id,
            correlation_id=correlation_id,
            provenance={**p.to_dict(), "guna_eligibility": result.guna_eligibility.value},
        )
        return snapshot

    async def latest_for_user(self, user_id: uuid.UUID) -> NatalChartSnapshot | None:
        return await self._natal.latest_for_user(user_id)

    @staticmethod
    def _assert_persist_allowed(snapshot: NatalChartSnapshot) -> None:
        # No synthetic result may be persisted as an authoritative snapshot (Area A).
        if snapshot.synthetic and snapshot.authoritative:
            raise DilChatError(
                ErrorCode.SYNTHETIC_PERSIST_FORBIDDEN,
                "A synthetic (fake) result cannot be persisted as an authoritative snapshot.",
            )
        if snapshot.synthetic and not snapshot.test_only:
            raise DilChatError(
                ErrorCode.SYNTHETIC_PERSIST_FORBIDDEN,
                "A synthetic result must be tagged test_only to be persisted.",
            )

    @staticmethod
    def _interval(profile: BirthProfile) -> tuple[dt.datetime, dt.datetime]:
        start = profile.utc_interval_start
        end = profile.utc_interval_end
        if start is None or end is None:
            # Legacy/edge: fall back to the single instant when present.
            if profile.utc_birth_instant is not None:
                inst = _aware(profile.utc_birth_instant)
                return inst, inst
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR,
                "Birth profile has no resolvable UTC interval.",
            )
        return _aware(start), _aware(end)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)
