"""Birth-profile routes (owner-scoped)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ...domain.enums import BirthTimePrecision
from ...errors import not_found
from ...infrastructure.orm import BirthProfile
from ...services.birth_profiles import BirthProfileInput
from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import BirthProfileCreateRequest, BirthProfileResponse, UtcIntervalModel

router = APIRouter(prefix="/birth-profiles", tags=["birth-profiles"])


def _to_response(profile: BirthProfile) -> BirthProfileResponse:
    interval = None
    if profile.utc_interval_start is not None and profile.utc_interval_end is not None:
        interval = UtcIntervalModel(
            start=profile.utc_interval_start, end=profile.utc_interval_end
        )
    return BirthProfileResponse(
        id=profile.id,
        version=profile.version,
        preferred_name=profile.preferred_name,
        birth_date=profile.birth_date,
        birth_time_precision=BirthTimePrecision(profile.birth_time_precision),
        has_birth_time=profile.birth_time_local is not None,
        birthplace_label=profile.birthplace_label,
        iana_timezone=profile.iana_timezone,
        utc_birth_instant=profile.utc_birth_instant,
        utc_interval=interval,
        uncertainty_minutes=profile.uncertainty_minutes,
        input_confidence=profile.input_confidence,
    )


async def _create(
    body: BirthProfileCreateRequest,
    principal: AuthPrincipal,
    services: ServiceRegistry,
    correlation_id: str | None,
) -> BirthProfileResponse:
    data = BirthProfileInput(
        preferred_name=body.preferred_name,
        birth_date=body.birth_date,
        birth_time_local=body.birth_time_local,
        birth_time_precision=body.birth_time_precision,
        birthplace_label=body.birthplace_label,
        latitude=body.latitude,
        longitude=body.longitude,
        iana_timezone=body.iana_timezone,
        ambiguity_resolution=body.ambiguity_resolution,
        uncertainty_minutes=body.uncertainty_minutes,
    )
    profile = await services.birth_profiles.create_or_version(
        principal.user_id, data, correlation_id
    )
    return _to_response(profile)


@router.post("", response_model=BirthProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_birth_profile(
    body: BirthProfileCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> BirthProfileResponse:
    return await _create(body, principal, services, correlation_id)


@router.get("/me", response_model=BirthProfileResponse)
async def get_my_birth_profile(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> BirthProfileResponse:
    profile = await services.birth_profiles.get_latest(principal.user_id)
    if profile is None:
        raise not_found("No birth profile.")
    return _to_response(profile)


@router.patch("/me", response_model=BirthProfileResponse, status_code=status.HTTP_201_CREATED)
async def update_my_birth_profile(
    body: BirthProfileCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> BirthProfileResponse:
    # PATCH creates a new immutable version (design DILCHAT_DATA_MODEL.md).
    return await _create(body, principal, services, correlation_id)
