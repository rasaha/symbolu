"""Natal-Moon routes (owner-scoped). No Guna Milan is exposed here or anywhere."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ...errors import not_found
from ...infrastructure.orm import NatalChartSnapshot
from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import NatalMoonResponse, ProvenanceModel

router = APIRouter(prefix="/natal", tags=["natal"])


def _to_response(s: NatalChartSnapshot) -> NatalMoonResponse:
    return NatalMoonResponse(
        snapshot_id=s.id,
        birth_profile_version=s.birth_profile_version,
        moon_longitude=s.moon_longitude,
        rashi_index=s.rashi_index,
        rashi_name=s.rashi_name,
        nakshatra_index=s.nakshatra_index,
        nakshatra_name=s.nakshatra_name,
        pada=s.pada,
        provenance=ProvenanceModel(
            provider_id=s.provider_id,
            provider_version=s.provider_version,
            ephemeris_mode=s.ephemeris_mode,
            ayanamsa=s.ayanamsa,
            calculation_timestamp=s.calculation_timestamp,
            numerical_precision_class=s.numerical_precision_class,
            fallback_used=s.fallback_used,
            fallback_reason=s.fallback_reason,
            input_confidence=s.input_confidence,
            time_assumption=s.time_assumption,
        ),
    )


@router.post("/moon", response_model=NatalMoonResponse, status_code=status.HTTP_201_CREATED)
async def compute_natal_moon(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> NatalMoonResponse:
    snapshot = await services.natal.compute_for_user(principal.user_id, correlation_id)
    return _to_response(snapshot)


@router.get("/moon/latest", response_model=NatalMoonResponse)
async def latest_natal_moon(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> NatalMoonResponse:
    snapshot = await services.natal.latest_for_user(principal.user_id)
    if snapshot is None:
        raise not_found("No natal snapshot.")
    return _to_response(snapshot)
