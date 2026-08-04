"""User and session repositories."""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.orm import User, UserSession


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._s.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._s.execute(sa.select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(self, email: str, credential_hash: str) -> User:
        user = User(email=email.lower(), credential_hash=credential_hash)
        self._s.add(user)
        await self._s.flush()
        return user


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        expires_at: dt.datetime,
        rotated_from_id: uuid.UUID | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        row = UserSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            rotated_from_id=rotated_from_id,
            user_agent=user_agent,
        )
        self._s.add(row)
        await self._s.flush()
        return row

    async def get(self, session_id: uuid.UUID) -> UserSession | None:
        return await self._s.get(UserSession, session_id)

    async def get_by_refresh_hash(self, token_hash: str) -> UserSession | None:
        result = await self._s.execute(
            sa.select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def mark_rotated(self, row: UserSession) -> None:
        row.rotated_at = dt.datetime.now(dt.UTC)

    async def revoke(self, row: UserSession) -> None:
        if row.revoked_at is None:
            row.revoked_at = dt.datetime.now(dt.UTC)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        now = dt.datetime.now(dt.UTC)
        result = await self._s.execute(
            sa.update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return getattr(result, "rowcount", 0) or 0

    async def revoke_chain_from(self, root_id: uuid.UUID) -> int:
        """Revoke every live session that descends from a rotated ancestor.

        Used on refresh-token reuse detection: the whole rotation chain is killed.
        """
        # Collect the chain by walking rotated_from links forward.
        revoked = 0
        frontier = {root_id}
        seen: set[uuid.UUID] = set()
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            row = await self._s.get(UserSession, current)
            if row is not None:
                await self.revoke(row)
                revoked += 1
            children = await self._s.execute(
                sa.select(UserSession.id).where(UserSession.rotated_from_id == current)
            )
            frontier.update(children.scalars().all())
        return revoked
