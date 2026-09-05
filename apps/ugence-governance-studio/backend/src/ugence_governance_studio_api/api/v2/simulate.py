"""Screen 4 — Simulate. Runs against fixtures; nothing consequential is reachable."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import SimulateRunRequest
from ...errors import ApiException
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/simulate", tags=["simulate"])


@router.post("/run", operation_id="v2_simulate_run")
def run_simulation(request: Request, req: SimulateRunRequest):
    """Drive a workflow a bounded number of quanta and report every outcome.

    ``execution_mode`` accepts only the non-mutating modes; ``LIVE`` is refused with a
    typed 422 rather than being silently downgraded, so a caller that asked for live
    execution learns that the studio does not do that.
    """
    try:
        result = studio(request).simulate.run(
            workflow=req.workflow,
            execution_mode=req.execution_mode,
            max_quanta=req.max_quanta,
            correlation_id=req.correlation_id,
        )
    except ValueError as exc:
        raise ApiException(422, "invalid_execution_mode", str(exc))
    return v2_response(request, operation="simulate.run", result=result)
