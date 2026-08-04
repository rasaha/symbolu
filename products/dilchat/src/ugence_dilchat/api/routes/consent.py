"""Consent + shared-artifact routes (foundational primitives)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import (
    ConsentCreateRequest,
    ConsentResponse,
    SharedArtifactCreateRequest,
    SharedArtifactResponse,
)

router = APIRouter(tags=["consent"])


@router.post("/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def create_consent(
    body: ConsentCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> ConsentResponse:
    event = await services.consent.create_consent(
        couple_id=body.couple_id,
        granter_user_id=principal.user_id,
        artifact_type=body.artifact_type,
        bounded_summary=body.bounded_summary,
        purpose=body.purpose,
        correlation_id=correlation_id,
    )
    return ConsentResponse(
        consent_event_id=event.id,
        state=event.state,
        source_scope=event.source_scope,
        created_at=event.created_at,
    )


@router.post(
    "/shared-artifacts",
    response_model=SharedArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_shared_artifact(
    body: SharedArtifactCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> SharedArtifactResponse:
    artifact = await services.consent.create_shared_artifact(
        actor_user_id=principal.user_id,
        consent_event_id=body.consent_event_id,
        payload_snapshot=body.payload_snapshot,
        correlation_id=correlation_id,
    )
    return _artifact_response(artifact)


@router.get("/shared-artifacts/{artifact_id}", response_model=SharedArtifactResponse)
async def get_shared_artifact(
    artifact_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> SharedArtifactResponse:
    artifact = await services.consent.get_shared_artifact(artifact_id, principal.user_id)
    return _artifact_response(artifact)


def _artifact_response(artifact) -> SharedArtifactResponse:
    return SharedArtifactResponse(
        artifact_id=artifact.id,
        artifact_type=artifact.artifact_type,
        source_scope=artifact.source_scope,
        payload_snapshot=artifact.payload_snapshot,
        created_at=artifact.created_at,
        provenance=artifact.provenance,
    )
