"""Birth-profile and natal-snapshot repositories."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.orm import BirthProfile, NatalChartSnapshot


class BirthProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def latest_for_user(self, user_id: uuid.UUID) -> BirthProfile | None:
        result = await self._s.execute(
            sa.select(BirthProfile)
            .where(BirthProfile.user_id == user_id)
            .order_by(BirthProfile.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get(self, profile_id: uuid.UUID) -> BirthProfile | None:
        return await self._s.get(BirthProfile, profile_id)

    async def add(self, profile: BirthProfile) -> BirthProfile:
        self._s.add(profile)
        await self._s.flush()
        return profile

    async def delete(self, profile: BirthProfile) -> None:
        await self._s.delete(profile)
        await self._s.flush()


class NatalRepository:
    """Insert-only (immutable snapshots)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, snapshot: NatalChartSnapshot) -> NatalChartSnapshot:
        self._s.add(snapshot)
        await self._s.flush()
        return snapshot

    async def find_by_version_tuple(
        self,
        *,
        birth_profile_id: uuid.UUID,
        birth_profile_version: int,
        provider_id: str,
        provider_version: str,
        ephemeris_mode: str,
        ayanamsa: str,
    ) -> NatalChartSnapshot | None:
        result = await self._s.execute(
            sa.select(NatalChartSnapshot).where(
                NatalChartSnapshot.birth_profile_id == birth_profile_id,
                NatalChartSnapshot.birth_profile_version == birth_profile_version,
                NatalChartSnapshot.provider_id == provider_id,
                NatalChartSnapshot.provider_version == provider_version,
                NatalChartSnapshot.ephemeris_mode == ephemeris_mode,
                NatalChartSnapshot.ayanamsa == ayanamsa,
            )
        )
        return result.scalar_one_or_none()

    async def latest_for_user(self, user_id: uuid.UUID) -> NatalChartSnapshot | None:
        result = await self._s.execute(
            sa.select(NatalChartSnapshot)
            .where(NatalChartSnapshot.user_id == user_id)
            .order_by(NatalChartSnapshot.calculation_timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
