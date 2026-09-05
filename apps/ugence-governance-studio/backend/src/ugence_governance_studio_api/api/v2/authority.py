"""Screen 3 — Authority. A reader.

Every route here is a GET. There is no issue and no revoke route, and those entry
points are permanently outside the SD-1 allowlist (SD-2).
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/authority", tags=["authority"])


@router.get("/policies", operation_id="v2_authority_list_policies")
def list_policies(request: Request):
    """Issued policy records for the identities this deployment was configured with."""
    result = studio(request).authority.policies()
    return v2_response(request, operation="authority.policies", result=result)


@router.get("/policies/{record_id}", operation_id="v2_authority_read_policy")
def read_policy(request: Request, record_id: str):
    """One issued record, with its revocations and supersessions."""
    result = studio(request).authority.policy(record_id)
    return v2_response(request, operation="authority.policy", result=result)


@router.get("/decisions/{decision_id}", operation_id="v2_authority_read_decision")
def read_decision(request: Request, decision_id: str):
    """One recorded Decision Authority decision."""
    result = studio(request).authority.decision(decision_id)
    return v2_response(request, operation="authority.decision", result=result)
