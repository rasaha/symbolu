"""Couple service: invitation, acceptance, and unpairing.

Invitations are single-use (unique token hash + PENDING->ACCEPTED transition) and
expire. Acceptance requires an authenticated user distinct from the inviter.
Unpairing sets the couple to UNPAIRED and revokes both memberships immediately, so
authorization to shared data is withdrawn at once.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from ..audit.service import AuditService
from ..domain.enums import (
    AuditAction,
    AuthzOutcome,
    CoupleStatus,
    InvitationStatus,
    MembershipStatus,
    ScopeSlot,
)
from ..errors import DilChatError, ErrorCode
from ..infrastructure.orm import Couple, CoupleInvitation
from ..repositories.couples import (
    CoupleRepository,
    InvitationRepository,
    MembershipRepository,
)
from ..security.tokens import generate_refresh_token, hash_refresh_token

_INVITATION_TTL = dt.timedelta(days=7)


@dataclass(frozen=True)
class CreatedInvitation:
    invitation: CoupleInvitation
    token: str  # returned once to the inviter; only the hash is stored


class CoupleService:
    def __init__(
        self,
        *,
        couples: CoupleRepository,
        memberships: MembershipRepository,
        invitations: InvitationRepository,
        audit: AuditService,
    ) -> None:
        self._couples = couples
        self._memberships = memberships
        self._invitations = invitations
        self._audit = audit

    async def create_invitation(
        self, inviter_user_id: uuid.UUID, correlation_id: str | None = None
    ) -> CreatedInvitation:
        if await self._memberships.active_membership_for_user(inviter_user_id) is not None:
            raise DilChatError(ErrorCode.CONFLICT, "User is already in an active couple.")
        token = generate_refresh_token()
        invitation = CoupleInvitation(
            inviter_user_id=inviter_user_id,
            token_hash=hash_refresh_token(token),
            status=InvitationStatus.PENDING.value,
            expires_at=dt.datetime.now(dt.UTC) + _INVITATION_TTL,
        )
        await self._invitations.add(invitation)
        await self._audit.record(
            action=AuditAction.INVITATION_CREATED,
            actor_user_id=inviter_user_id,
            resource_type="couple_invitation",
            resource_id=invitation.id,
            correlation_id=correlation_id,
        )
        return CreatedInvitation(invitation=invitation, token=token)

    async def accept_invitation(
        self, token: str, accepter_user_id: uuid.UUID, correlation_id: str | None = None
    ) -> Couple:
        invitation = await self._invitations.get_by_token_hash(hash_refresh_token(token))
        if invitation is None:
            raise DilChatError(ErrorCode.INVITATION_INVALID, "Invitation not found.")
        if invitation.inviter_user_id == accepter_user_id:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR, "You cannot accept your own invitation."
            )
        now = dt.datetime.now(dt.UTC)
        if invitation.status != InvitationStatus.PENDING.value:
            code = (
                ErrorCode.INVITATION_USED
                if invitation.status == InvitationStatus.ACCEPTED.value
                else ErrorCode.INVITATION_INVALID
            )
            raise DilChatError(code, "Invitation is no longer usable.")
        if invitation.expires_at <= now:
            invitation.status = InvitationStatus.EXPIRED.value
            await self._audit.record(
                action=AuditAction.INVITATION_EXPIRED,
                actor_user_id=accepter_user_id,
                resource_type="couple_invitation",
                resource_id=invitation.id,
                outcome=AuthzOutcome.DENY,
                denial_reason_code=ErrorCode.INVITATION_EXPIRED.value,
                correlation_id=correlation_id,
            )
            raise DilChatError(ErrorCode.INVITATION_EXPIRED, "Invitation has expired.")

        # Neither party may already be in an active couple.
        for uid in (invitation.inviter_user_id, accepter_user_id):
            if await self._memberships.active_membership_for_user(uid) is not None:
                raise DilChatError(ErrorCode.CONFLICT, "A participant is already paired.")

        couple = await self._couples.create()
        await self._memberships.add(
            couple_id=couple.id, user_id=invitation.inviter_user_id, scope_slot=ScopeSlot.A.value
        )
        await self._memberships.add(
            couple_id=couple.id, user_id=accepter_user_id, scope_slot=ScopeSlot.B.value
        )
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_by_user_id = accepter_user_id
        invitation.accepted_at = now
        invitation.couple_id = couple.id

        await self._audit.record(
            action=AuditAction.INVITATION_ACCEPTED,
            actor_user_id=accepter_user_id,
            resource_type="couple",
            resource_id=couple.id,
            couple_id=couple.id,
            correlation_id=correlation_id,
        )
        return couple

    async def unpair(
        self, couple_id: uuid.UUID, actor_user_id: uuid.UUID, correlation_id: str | None = None
    ) -> None:
        # Authorization: actor must currently be an active member.
        fact = await self._memberships.membership_fact(
            couple_id=couple_id, user_id=actor_user_id
        )
        if fact.status is not MembershipStatus.ACTIVE:
            # Existence non-disclosure for a couple the actor is not part of.
            raise DilChatError(ErrorCode.NOT_FOUND)

        couple = await self._couples.get(couple_id)
        if couple is None or couple.status != CoupleStatus.ACTIVE.value:
            raise DilChatError(ErrorCode.NOT_FOUND)

        now = dt.datetime.now(dt.UTC)
        couple.status = CoupleStatus.UNPAIRED.value
        couple.unpaired_at = now
        for m in await self._memberships.for_couple(couple_id):
            if m.status == MembershipStatus.ACTIVE.value:
                m.status = MembershipStatus.REVOKED.value
                m.revoked_at = now
        await self._audit.record(
            action=AuditAction.COUPLE_UNPAIRED,
            actor_user_id=actor_user_id,
            resource_type="couple",
            resource_id=couple_id,
            couple_id=couple_id,
            correlation_id=correlation_id,
        )

    async def current_couple(self, user_id: uuid.UUID) -> Couple | None:
        membership = await self._memberships.active_membership_for_user(user_id)
        if membership is None:
            return None
        return await self._couples.get(membership.couple_id)
