"""Screen 1 — Registration (front-door seam 5, FD-9). Typed intake over ai-system-registry.

Two routes: one write, ``register``, and one read. The write records what an
administrator asserted and confers nothing (registry ADR D-5); it never admits, gates,
promotes, attests, edits or deletes, and there is no route for any of those. The
tenant is the deployment's, never the caller's; the registration id is derived, never
chosen; the registrant is recorded as presented and unproven (FD-9.3).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import RegistryRegisterRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/registry", tags=["registry"])


@router.post("/registrations", operation_id="v2_registry_register")
def register_system(request: Request, req: RegistryRegisterRequest):
    """Record one typed system registration for this deployment's tenant.

    Every field is validated by ai-system-registry's own refusal reasons; the
    classification label is recorded uninterpreted; a superseding registration is
    admitted only by the package's supersession rule. A refusal is typed, never a 500.
    """
    result = studio(request).registry.register(req.model_dump())
    return v2_response(request, operation="registry.register", result=result)


@router.get("/registrations", operation_id="v2_registry_list")
def list_registrations(request: Request, as_of: Optional[str] = None):
    """The registrations in force for this deployment's tenant at ``as_of``.

    ``as_of`` is an ISO-8601 instant with a timezone; absent, the request's own instant
    is used and reported back. A registration outside its window is absent from the
    answer, never flagged.
    """
    result = studio(request).registry.list(as_of=as_of)
    return v2_response(request, operation="registry.list", result=result)
