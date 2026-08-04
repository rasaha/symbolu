"""Birth-profile service: create/version a profile and convert local time to UTC."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from ..audit.service import AuditService
from ..config import Settings
from ..domain.enums import AmbiguityResolution, AuditAction, BirthTimePrecision
from ..infrastructure.orm import BirthProfile
from ..repositories.birth_profiles import BirthProfileRepository
from .birthtime import compute_birth_instant


@dataclass(frozen=True)
class BirthProfileInput:
    preferred_name: str
    birth_date: dt.date
    birth_time_local: dt.time | None
    birth_time_precision: BirthTimePrecision
    birthplace_label: str
    latitude: float
    longitude: float
    iana_timezone: str
    ambiguity_resolution: AmbiguityResolution | None = None


class BirthProfileService:
    def __init__(
        self,
        *,
        settings: Settings,
        profiles: BirthProfileRepository,
        audit: AuditService,
    ) -> None:
        self._settings = settings
        self._profiles = profiles
        self._audit = audit

    async def create_or_version(
        self, user_id: uuid.UUID, data: BirthProfileInput, correlation_id: str | None = None
    ) -> BirthProfile:
        instant = compute_birth_instant(
            birth_date=data.birth_date,
            birth_time_local=data.birth_time_local,
            precision=data.birth_time_precision,
            iana_timezone=data.iana_timezone,
            ambiguity_resolution=data.ambiguity_resolution,
        )
        confidence = self._settings.confidence_for_precision(data.birth_time_precision.value)

        current = await self._profiles.latest_for_user(user_id)
        version = 1 if current is None else current.version + 1

        profile = BirthProfile(
            user_id=user_id,
            version=version,
            supersedes_id=current.id if current else None,
            preferred_name=data.preferred_name,
            birth_date=data.birth_date,
            birth_time_local=data.birth_time_local,
            birth_time_precision=data.birth_time_precision.value,
            ambiguity_resolution=(
                data.ambiguity_resolution.value if data.ambiguity_resolution else None
            ),
            birthplace_label=data.birthplace_label,
            latitude=data.latitude,
            longitude=data.longitude,
            iana_timezone=data.iana_timezone,
            utc_birth_instant=instant.utc_instant,
            input_confidence=confidence,
        )
        await self._profiles.add(profile)
        await self._audit.record(
            action=(
                AuditAction.BIRTH_PROFILE_CREATED
                if current is None
                else AuditAction.BIRTH_PROFILE_UPDATED
            ),
            actor_user_id=user_id,
            resource_type="birth_profile",
            resource_id=profile.id,
            correlation_id=correlation_id,
            # provenance carries only non-sensitive confidence/precision metadata.
            provenance={"input_confidence": confidence},
        )
        return profile

    async def get_latest(self, user_id: uuid.UUID) -> BirthProfile | None:
        return await self._profiles.latest_for_user(user_id)
