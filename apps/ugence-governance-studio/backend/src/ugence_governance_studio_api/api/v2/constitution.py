"""Screen 1 — Constitution. Validates and preflights; never issues, never activates."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import ConstitutionPreflightRequest, ConstitutionValidateRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/constitution", tags=["constitution"])


@router.post("/validate", operation_id="v2_constitution_validate")
def validate_constitution(request: Request, req: ConstitutionValidateRequest):
    """Structural validation of a constitution document. Mutation-free."""
    result = studio(request).constitution.validate(req.constitution)
    return v2_response(request, operation="constitution.validate", result=result)


@router.post("/preflight", operation_id="v2_constitution_preflight")
def preflight_constitution(request: Request, req: ConstitutionPreflightRequest):
    """Dry-run every pre-signing check.

    This is the ONLY activation entry point the studio reaches (SD-2). Issuance and
    activation are authority acts and are permanently outside the allowlist.
    """
    result = studio(request).constitution.preflight(
        constitution=req.constitution,
        record_id=req.record_id,
        approval_reference=req.approval_reference,
        expected_reference_tenant_id=req.expected_reference_tenant_id,
        as_of=datetime.now(timezone.utc),
    )
    return v2_response(request, operation="constitution.preflight", result=result)
