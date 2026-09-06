"""Screen 5b — Vendor dependencies (front-door seam 9, FD-13). Typed intake over
vendor-dependency.

Two routes: one write, ``declare``, and one read. The write records what a declarer
asserted and confers nothing (VR-1, FD-13.4); it never resolves, verifies, scores,
grades, ranks, approves, onboards, contacts, edits or deletes, and there is no route
for any of those. The tenant is the deployment's, never the caller's; the declaration
id is derived, never chosen; the declarer is recorded as presented and unproven; the
risk posture is recorded uninterpreted and the ``policy_ref`` recorded and never
resolved.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import VendorDeclareRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/vendor", tags=["vendor"])


@router.post("/declarations", operation_id="v2_vendor_declare")
def declare_vendor_dependency(request: Request, req: VendorDeclareRequest):
    """Record one typed vendor-dependency declaration for this deployment's tenant.

    Every field is validated by vendor-dependency's own refusal reasons; a superseding
    declaration is admitted only by ``supersession_refusals``. ``vendor_ref`` is an
    opaque handle and the record carries no way to reach the vendor. A refusal is
    typed, never a 500.
    """
    result = studio(request).vendor.declare(req.model_dump())
    return v2_response(request, operation="vendor.declare", result=result)


@router.get("/declarations", operation_id="v2_vendor_list")
def list_vendor_declarations(request: Request, as_of: Optional[str] = None):
    """The vendor declarations in force for this deployment's tenant at ``as_of``.

    ``as_of`` is an ISO-8601 instant with a timezone; absent, the request's own instant
    is used and reported back. A declaration outside its window is absent from the
    answer, never flagged. The answer is never ordered by posture: nothing ranks one.
    """
    result = studio(request).vendor.list(as_of=as_of)
    return v2_response(request, operation="vendor.list", result=result)
