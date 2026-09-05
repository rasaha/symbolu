"""Screens 7 and 8 — Review Queue and Run Detail (GAS-7, HR-D).

Read plus verbatim relay, under owner ruling HR-1. The studio renders what the review
service holds and transmits a human's decision to it. The decision route is named for
the act of submitting, not for its outcome: no path or operation id here names an
authority act, and the studio's review client cannot reach a resume, release, continue
or signal route because the review service exposes none.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

from ...contracts.v2 import ReviewDecisionRequest
from .deps import studio, v2_response

router = APIRouter(prefix="/api/v2/review", tags=["review"])


@router.get("/queue", operation_id="v2_review_list_queue")
def list_queue(request: Request, required_role: str = ""):
    """Parked ESCALATE instances awaiting a human decision, as the review service lists them.

    A HOLD is never presented as awaiting a human (HR-5); the studio counts any it
    filtered so the guard is visible.
    """
    result = studio(request).review.queue(required_role)
    return v2_response(request, operation="review.list_queue", result=result)


@router.get("/runs/{instance_id}", operation_id="v2_review_read_run")
def read_run(request: Request, instance_id: str):
    """One instance: checkpoint view, engine status and its open approvals.

    Fingerprints and ``valid_until`` values are history — what was evaluated and when
    that evaluation lapsed — never a live permission.
    """
    result = studio(request).review.run(instance_id)
    return v2_response(request, operation="review.read_run", result=result)


@router.get("/runs/{instance_id}/events", operation_id="v2_review_read_run_events")
def read_run_events(request: Request, instance_id: str):
    """The full runtime event log for one instance, including signal rows."""
    result = studio(request).review.run_events(instance_id)
    return v2_response(request, operation="review.read_run_events", result=result)


@router.get("/approvals/{approval_id}", operation_id="v2_review_read_approval")
def read_approval(request: Request, approval_id: str):
    """One approval record and its hash-linked event chain."""
    result = studio(request).review.approval(approval_id)
    return v2_response(request, operation="review.read_approval", result=result)


@router.post("/decisions", operation_id="v2_review_submit_decision")
def submit_decision(request: Request, req: ReviewDecisionRequest):
    """Relay a human's decision to the review service, verbatim.

    The body is forwarded as received. The studio adds no identity, computes no
    eligibility and reads nothing but the review service's typed answer, which it
    returns whether the decision was recorded, replayed or refused.
    """
    result = studio(request).review.submit_decision(req.model_dump())
    return v2_response(request, operation="review.submit_decision", result=result)
