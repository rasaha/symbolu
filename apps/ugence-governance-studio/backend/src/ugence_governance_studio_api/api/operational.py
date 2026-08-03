"""Operational endpoints: /health, /ready, /version (§7).

These are unprefixed. ``/health`` performs no domain execution; ``/ready``
verifies scenario manifests, fixture hashes, AWC import and contract presence;
``/version`` returns the full version + maturity payload. No wall-clock value is
included in any logical result fingerprint.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..version import version_info
from .deps import get_context

router = APIRouter(tags=["operational"])


@router.get("/health", operation_id="get_health")
def health() -> dict:
    return {"status": "healthy"}


@router.get("/ready", operation_id="get_ready")
def ready(request: Request):
    ctx = get_context(request)
    result = ctx.catalog.readiness()
    status = 200 if result["ready"] else 503
    body = {"status": "ready" if result["ready"] else "not_ready", **result}
    return JSONResponse(status_code=status, content=body)


@router.get("/version", operation_id="get_version")
def version(request: Request) -> dict:
    ctx = get_context(request)
    return version_info(
        build_commit=ctx.settings.build_commit, build_id=ctx.settings.build_id
    )
