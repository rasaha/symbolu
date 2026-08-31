"""Repository for push-device registrations (Phase 3C)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import utcnow
from ..domain import enums
from ..infrastructure.devices_orm import ChatDevice


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, device_id: uuid.UUID) -> ChatDevice | None:
        return await self._s.get(ChatDevice, device_id)

    async def get_own_by_token(self, user_id: uuid.UUID, push_token: str) -> ChatDevice | None:
        res = await self._s.execute(
            sa.select(ChatDevice).where(
                ChatDevice.user_id == user_id, ChatDevice.push_token == push_token
            )
        )
        return res.scalars().first()

    async def list_for_user(self, user_id: uuid.UUID) -> list[ChatDevice]:
        res = await self._s.execute(
            sa.select(ChatDevice)
            .where(ChatDevice.user_id == user_id)
            .order_by(ChatDevice.created_at)
        )
        return list(res.scalars().all())

    async def active_tokens_for_user(self, user_id: uuid.UUID) -> list[ChatDevice]:
        res = await self._s.execute(
            sa.select(ChatDevice).where(
                ChatDevice.user_id == user_id,
                ChatDevice.status == enums.DeviceStatus.ACTIVE.value,
            )
        )
        return list(res.scalars().all())

    async def add(self, row: ChatDevice) -> ChatDevice:
        self._s.add(row)
        await self._s.flush()
        return row

    async def release_token(self, push_token: str) -> int:
        """Revoke any ACTIVE registration holding this token, whoever owns it.

        On PostgreSQL this MUST use the ``app_release_push_token`` SECURITY
        DEFINER helper: owner-only RLS hides another user's registration from
        the caller, yet a device handed to a new user must displace the previous
        owner's registration (the partial unique index would otherwise reject
        the new one). On SQLite (no RLS) a direct update is equivalent.
        """
        if self._s.bind is not None and self._s.bind.dialect.name == "postgresql":
            res = await self._s.execute(
                sa.text("SELECT app_release_push_token(:tok)"), {"tok": push_token}
            )
            return int(res.scalar_one())
        res = await self._s.execute(
            sa.update(ChatDevice)
            .where(
                ChatDevice.push_token == push_token,
                ChatDevice.status == enums.DeviceStatus.ACTIVE.value,
            )
            .values(status=enums.DeviceStatus.REVOKED.value, revoked_at=utcnow())
        )
        return int(getattr(res, "rowcount", 0) or 0)

    async def revoke_where(self, *conditions) -> int:
        res = await self._s.execute(
            sa.update(ChatDevice)
            .where(ChatDevice.status == enums.DeviceStatus.ACTIVE.value, *conditions)
            .values(status=enums.DeviceStatus.REVOKED.value, revoked_at=utcnow())
        )
        return int(getattr(res, "rowcount", 0) or 0)
