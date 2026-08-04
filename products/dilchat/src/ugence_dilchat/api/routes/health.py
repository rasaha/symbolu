"""Liveness and readiness probes."""

from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ... import __version__
from ...db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/readiness")
async def readiness(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    checks: dict[str, str] = {}
    ready = True
    try:
        await session.execute(sa.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        ready = False
    provider = getattr(request.app.state, "astrology_provider", None)
    provider_id = getattr(provider, "provider_id", "none")
    checks["astrology_provider"] = provider_id
    settings = request.app.state.settings
    checks["environment"] = settings.environment.value
    # Readiness must fail if a production-like environment has no permitted real
    # provider configured (Area A) — never serve real astrology from a fake stub.
    if settings.environment.is_production_like and (provider is None or provider_id == "fake"):
        checks["astrology_provider"] = "invalid_for_production"
        ready = False
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
