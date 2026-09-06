"""Screen 5 — Data-use declarations (front-door seam 8, FD-12). Typed intake over
data-use-admission.

Two routes: one write, ``declare``, and one read. The write records what a declarer
asserted and confers nothing (DE-1, FD-12.5); it never inspects, classifies, admits,
authorizes, verifies, scores, enforces, edits or deletes, and there is no route for any
of those. The tenant is the deployment's, never the caller's; the declaration id is
derived, never chosen; the declarer is recorded as presented and unproven (FD-12.3);
the classification, purpose and residency labels are recorded uninterpreted. No egress
restriction is expressible here, and none is invented for the absent egress package.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import DataUseDeclareRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/data-use", tags=["data-use"])


@router.post("/declarations", operation_id="v2_data_use_declare")
def declare_data_use(request: Request, req: DataUseDeclareRequest):
    """Record one typed data-use declaration for this deployment's tenant.

    Every field is validated by data-use-admission's own refusal reasons; a superseding
    declaration is admitted only by ``supersession_refusals``. ``data_ref`` is an opaque
    handle and the record carries no data. A refusal is typed, never a 500.
    """
    result = studio(request).data_use.declare(req.model_dump())
    return v2_response(request, operation="data_use.declare", result=result)


@router.get("/declarations", operation_id="v2_data_use_list")
def list_data_use_declarations(request: Request, as_of: Optional[str] = None):
    """The declarations in force for this deployment's tenant at ``as_of``.

    ``as_of`` is an ISO-8601 instant with a timezone; absent, the request's own instant
    is used and reported back. A declaration outside its window is absent from the
    answer, never flagged.
    """
    result = studio(request).data_use.list(as_of=as_of)
    return v2_response(request, operation="data_use.list", result=result)
