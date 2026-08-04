"""Couple + invitation routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from ...errors import not_found
from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import (
    CoupleResponse,
    InvitationCreateResponse,
    MemberModel,
)

router = APIRouter(prefix="/couples", tags=["couples"])


async def _couple_response(services: ServiceRegistry, couple_id: uuid.UUID) -> CoupleResponse:
    couple = await services.couple_repo.get(couple_id)
    assert couple is not None
    members = await services.membership_repo.for_couple(couple_id)
    return CoupleResponse(
        couple_id=couple.id,
        status=couple.status,
        members=[
            MemberModel(user_id=m.user_id, scope_slot=m.scope_slot, status=m.status)
            for m in members
        ],
    )


@router.post(
    "/invitations", response_model=InvitationCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_invitation(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> InvitationCreateResponse:
    created = await services.couples.create_invitation(principal.user_id, correlation_id)
    return InvitationCreateResponse(
        invitation_id=created.invitation.id,
        token=created.token,
        expires_at=created.invitation.expires_at,
    )


@router.post("/invitations/{token}/accept", response_model=CoupleResponse)
async def accept_invitation(
    token: str,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> CoupleResponse:
    couple = await services.couples.accept_invitation(token, principal.user_id, correlation_id)
    return await _couple_response(services, couple.id)


@router.post("/{couple_id}/unpair", status_code=status.HTTP_204_NO_CONTENT)
async def unpair(
    couple_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> None:
    await services.couples.unpair(couple_id, principal.user_id, correlation_id)


@router.get("/current", response_model=CoupleResponse)
async def current_couple(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> CoupleResponse:
    couple = await services.couples.current_couple(principal.user_id)
    if couple is None:
        raise not_found("No active couple.")
    return await _couple_response(services, couple.id)
