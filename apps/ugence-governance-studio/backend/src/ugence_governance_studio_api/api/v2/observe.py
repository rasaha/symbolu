"""Screen 6 — Observe. Renders the console's audit chain and, since front-door seam 7
(FD-11), the worker's own audit-ledger rows; never re-derives either."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/observe", tags=["observe"])


@router.get("/audit", operation_id="v2_observe_audit_ids")
def audit_ids(request: Request):
    """Known correlation ids, as the console reports them."""
    result = studio(request).observe.correlation_ids()
    return v2_response(request, operation="observe.audit_ids", result=result)


@router.get("/audit/{correlation_id}", operation_id="v2_observe_audit_chain")
def audit_chain(request: Request, correlation_id: str):
    """One reconstructed decision chain, rendered exactly as returned.

    The studio does not re-derive, re-order or re-hash it: the console's audit store is
    the record, and a studio-side reconstruction would be a second unverified account.
    """
    result = studio(request).observe.chain(correlation_id)
    return v2_response(request, operation="observe.audit_chain", result=result)


@router.get("/ledger/{correlation_id}", operation_id="v2_observe_ledger_chain")
def ledger_chain(request: Request, correlation_id: str):
    """The worker's own tenant's audit-ledger rows for one correlation id, as the
    worker read them, with the worker's chain verification (FD-11.3, FD-11.4).

    The studio names no tenant and re-derives, re-orders and re-hashes nothing: what
    is returned is the worker's answer, including its typed refusal when the chain
    does not verify.
    """
    result = studio(request).ledger_observe.chain(correlation_id)
    return v2_response(request, operation="observe.ledger_chain", result=result)
