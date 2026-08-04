"""Couple, membership, and invitation repositories."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import MembershipStatus
from ..infrastructure.orm import Couple, CoupleInvitation, CoupleMembership
from ..security.scope import MembershipFact


class CoupleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self) -> Couple:
        couple = Couple()
        self._s.add(couple)
        await self._s.flush()
        return couple

    async def get(self, couple_id: uuid.UUID) -> Couple | None:
        return await self._s.get(Couple, couple_id)


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(
        self, *, couple_id: uuid.UUID, user_id: uuid.UUID, scope_slot: str
    ) -> CoupleMembership:
        row = CoupleMembership(couple_id=couple_id, user_id=user_id, scope_slot=scope_slot)
        self._s.add(row)
        await self._s.flush()
        return row

    async def for_couple(self, couple_id: uuid.UUID) -> list[CoupleMembership]:
        result = await self._s.execute(
            sa.select(CoupleMembership).where(CoupleMembership.couple_id == couple_id)
        )
        return list(result.scalars().all())

    async def get_membership(
        self, *, couple_id: uuid.UUID, user_id: uuid.UUID
    ) -> CoupleMembership | None:
        result = await self._s.execute(
            sa.select(CoupleMembership).where(
                CoupleMembership.couple_id == couple_id,
                CoupleMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def active_membership_for_user(self, user_id: uuid.UUID) -> CoupleMembership | None:
        result = await self._s.execute(
            sa.select(CoupleMembership).where(
                CoupleMembership.user_id == user_id,
                CoupleMembership.status == MembershipStatus.ACTIVE.value,
            )
        )
        return result.scalar_one_or_none()

    async def membership_fact(
        self, *, couple_id: uuid.UUID, user_id: uuid.UUID
    ) -> MembershipFact:
        """Read the current membership fact for an authorization decision."""
        row = await self.get_membership(couple_id=couple_id, user_id=user_id)
        status = MembershipStatus(row.status) if row is not None else None
        return MembershipFact(couple_id=couple_id, status=status)


class InvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, invitation: CoupleInvitation) -> CoupleInvitation:
        self._s.add(invitation)
        await self._s.flush()
        return invitation

    async def get_by_token_hash(self, token_hash: str) -> CoupleInvitation | None:
        result = await self._s.execute(
            sa.select(CoupleInvitation).where(CoupleInvitation.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get(self, invitation_id: uuid.UUID) -> CoupleInvitation | None:
        return await self._s.get(CoupleInvitation, invitation_id)
