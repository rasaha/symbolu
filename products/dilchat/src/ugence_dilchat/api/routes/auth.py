"""Authentication routes: register, login, refresh, logout, logout-all."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> RegisterResponse:
    user = await services.identity.register(body.email, body.password, correlation_id)
    return RegisterResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> TokenResponse:
    tokens = await services.identity.login(
        body.email,
        body.password,
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.access_expires_in,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> TokenResponse:
    tokens = await services.identity.refresh(
        body.refresh_token,
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id,
    )
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.access_expires_in,
        refresh_token=tokens.refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> None:
    await services.identity.logout(principal.session_id, correlation_id)
    # Logout of THIS device also revokes the push registrations this session
    # created (device model, D3C ratification); other devices stay registered.
    await services.devices.revoke_for_session(principal.user_id, principal.session_id)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> None:
    await services.identity.logout_all(principal.user_id, correlation_id)
    # Logout-all revokes every push registration the user holds.
    await services.devices.revoke_all_for_user(principal.user_id)
