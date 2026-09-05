"""Screen 2 — Policy. Validate and preview while authoring; compile only with approval."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import PolicyCompileRequest, PolicyPackRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/policy", tags=["policy"])


@router.post("/validate", operation_id="v2_policy_validate")
def validate_policy(request: Request, req: PolicyPackRequest):
    """Validate a policy pack. No approval required; produces no release."""
    result = studio(request).policy.validate(req.pack)
    return v2_response(request, operation="policy.validate", result=result)


@router.post("/synthesize", operation_id="v2_policy_synthesize")
def synthesize_policy(request: Request, req: PolicyPackRequest):
    """Preview the Workflow IR the canvas would produce. No approval; no release."""
    result = studio(request).policy.synthesize(req.pack)
    return v2_response(request, operation="policy.synthesize", result=result)


@router.post("/compile", operation_id="v2_policy_compile")
def compile_policy(request: Request, req: PolicyCompileRequest):
    """Compile a reviewed pack into a release.

    ``approval`` is required by the request model and ``require_approval`` is left at
    the compiler's default of True. The studio has no path that compiles without one.
    """
    result = studio(request).policy.compile(req.pack, req.approval)
    return v2_response(request, operation="policy.compile", result=result)
