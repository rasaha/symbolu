"""Consent-event and shared-artifact repositories (shared artifacts are insert-only)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.orm import ConsentEvent, SharedArtifact


class ConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, event: ConsentEvent) -> ConsentEvent:
        self._s.add(event)
        await self._s.flush()
        return event

    async def get(self, event_id: uuid.UUID) -> ConsentEvent | None:
        return await self._s.get(ConsentEvent, event_id)


class SharedArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, artifact: SharedArtifact) -> SharedArtifact:
        self._s.add(artifact)
        await self._s.flush()
        return artifact

    async def get(self, artifact_id: uuid.UUID) -> SharedArtifact | None:
        return await self._s.get(SharedArtifact, artifact_id)
