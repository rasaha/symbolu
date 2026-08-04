"""User self routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...repositories.users import UserRepository
from ..deps import AuthPrincipal, ServiceRegistry, get_current_principal, get_services
from ..schemas import UserMeResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> UserMeResponse:
    user = await UserRepository(services.session).get(principal.user_id)
    assert user is not None  # principal was validated against a live session
    return UserMeResponse(
        id=user.id, email=user.email, status=user.status, created_at=user.created_at
    )
