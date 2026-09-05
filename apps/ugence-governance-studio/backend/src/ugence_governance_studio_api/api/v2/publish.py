"""Screen 5 — Publish. Reaches the console's SHADOW governed loop and nothing else."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import PublishShadowRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/publish", tags=["publish"])


@router.post("/shadow", operation_id="v2_publish_shadow")
def publish_shadow(request: Request, req: PublishShadowRequest):
    """Hand a compiled release package to the console's SHADOW governed loop.

    There is no non-shadow variant. The console also exposes action-authorization and
    clearance routes; the studio's console client cannot reach them (SD-2).
    """
    result = studio(request).publish.shadow(
        compiled_package=req.compiled_package, scenario_id=req.scenario_id
    )
    return v2_response(request, operation="publish.shadow", result=result)
