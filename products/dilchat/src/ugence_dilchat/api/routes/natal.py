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
from ..schemas import (
    FieldResultModel,
    NatalMoonResponse,
    ProvenanceModel,
    UtcIntervalModel,
)

router = APIRouter(prefix="/natal", tags=["natal"])


def _to_response(s: NatalChartSnapshot) -> NatalMoonResponse:
    # Every snapshot written by NatalService carries its evaluation interval.
    assert s.utc_interval_start is not None and s.utc_interval_end is not None
    return NatalMoonResponse(
        snapshot_id=s.id,
        birth_profile_version=s.birth_profile_version,
        birth_time_precision="",  # not stored on snapshot; interval conveys uncertainty
        utc_interval=UtcIntervalModel(start=s.utc_interval_start, end=s.utc_interval_end),
        moon_longitude_start=s.moon_longitude,
        moon_longitude_end=s.longitude_end,
        moon_rashi=FieldResultModel(
            status=s.rashi_status, value=s.rashi_index, name=s.rashi_name,
            possible_values=s.rashi_possible,
        ),
        moon_nakshatra=FieldResultModel(
            status=s.nakshatra_status, value=s.nakshatra_index, name=s.nakshatra_name,
            possible_values=s.nakshatra_possible,
        ),
        moon_pada=FieldResultModel(
            status=s.pada_status, value=s.pada, possible_values=s.pada_possible,
        ),
        guna_eligibility=s.guna_eligibility,
        synthetic_calculation=s.synthetic,
        authoritative=s.authoritative,
        test_only=s.test_only,
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
            provider_kind=s.provider_kind,
            synthetic_calculation=s.synthetic,
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
