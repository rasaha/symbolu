"""Bring Your Workflow, phase 3A — workflow drafts (owner ruling,
ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §24). Typed intake over workflow-drafts.

Three routes: one write, ``save``, and two reads. The write keeps a document the
composer's adapter validated, as an unapproved ``DRAFT`` for this deployment's tenant,
and confers nothing; it never approves, compiles, publishes, exports, clears,
authenticates an owner or hands anything to a runtime, and there is no route for any
of those. The tenant is the deployment's, never the caller's; the draft id is derived,
never chosen; a claimed owner is recorded as presented and unproven; a revision is a
new record that supersedes its predecessor, and no record is ever edited or deleted.
The structural limits of BW-2 apply before anything is validated or kept.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import WorkflowDraftSaveRequest
from ...workflow_limits import enforce_workflow_limits
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/workflow-drafts", tags=["workflow-drafts"])


@router.post("", operation_id="v2_workflow_drafts_save")
def save_workflow_draft(request: Request, req: WorkflowDraftSaveRequest):
    """Keep one validated Workflow IR document as an unapproved draft for this
    deployment's tenant.

    The document is bounded by the BW-2 limits (a breach is the typed 422
    ``workflow_too_complex``), validated through the composer's adapter, and kept in its
    canonical encoding with its digest. A refusal is typed, never a 500.
    """
    enforce_workflow_limits(req.workflow, "workflow")
    result = studio(request).workflow_drafts.save(req.model_dump())
    return v2_response(request, operation="workflow_drafts.save", result=result)


@router.get("", operation_id="v2_workflow_drafts_list")
def list_workflow_drafts(request: Request, include_superseded: bool = False):
    """The drafts this deployment's tenant keeps: the head of every lineage, or every
    revision when ``include_superseded`` is set. Fields only; the document itself is
    read one draft at a time.
    """
    result = studio(request).workflow_drafts.list(include_superseded=include_superseded)
    return v2_response(request, operation="workflow_drafts.list", result=result)


@router.get("/{draft_id}", operation_id="v2_workflow_drafts_read")
def read_workflow_draft(request: Request, draft_id: str):
    """One draft, with its document, its lineage and the revision that supersedes it,
    if any. A draft of another tenant does not exist on this route."""
    result = studio(request).workflow_drafts.read(draft_id)
    return v2_response(request, operation="workflow_drafts.read", result=result)
