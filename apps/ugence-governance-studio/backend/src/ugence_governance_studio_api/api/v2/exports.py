"""Clearance export — the one v2 read CE-5 ruled.

**Why the route is named ``exports`` and not ``clearances``.** SD-2 is enforced by
``tests/test_v2_operation_ids.py``, which scans every v2 operation id *and path* for
seven prohibited verbs, one of which is ``clear``. That guard is not weakened here
to make room for a name: the operation exports, it does not clear, so ``exports`` is
both the accurate word and the one that leaves the ratchet exactly as it was.

**One route, and it is a read.** It returns the portable artifact for a clearance
this deployment already received. There is no route here that clears, authorizes,
approves, signs or mints, and there is no route that *accepts* a clearance either:
CE-5 rules export a read, and §13.3 restates that no operation may accept a
receipt. The absence is structural rather than disciplinary — the port the service
is handed has two reads and no write.

**Exporting is not clearing.** A compile result establishes what was compiled; a
clearance establishes whether a consequential action may proceed now and until when
(CE-1). This route serializes the second and can never reach the first.

**Three ceilings travel with the answer** — ``PRESENTED_UNPROVEN``, ``UNSIGNED`` and
``SYNTHETIC_DEMONSTRATION_ONLY`` — in the artifact and again in the envelope, so a
caller that reads only one of the two still sees all three.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/exports", tags=["exports"])


@router.get("/{receipt_id}", operation_id="v2_export_read")
def read_export(request: Request, receipt_id: str):
    """The export artifact for one clearance receipt this deployment holds.

    The tenant is the deployment's, never the caller's. An id the deployment does
    not hold is refused typed, never answered as an empty success: "no such
    clearance" and "no clearances" must not look alike to an external runtime. The
    artifact is content-addressed, and the answer says in four separate ways what
    recomputing that fingerprint does not establish.
    """
    result = studio(request).clearance_export.read(receipt_id=receipt_id)
    return v2_response(request, operation="export.read", result=result)
