"""The HTTP presentation of the service: five routes, named as the screen/API audit
proposed them, carrying none of the SD-2 verbs in any path or operation id.

FastAPI is a presentation dependency and an optional extra; it is imported inside
``build_app`` so the service core, and every test of it, runs without it. The routes
serialise the service's typed answers to plain JSON and add nothing: no identity is
read from a session (none exists), no result other than the service's typed answer is
returned, and the body's ``decision`` is the human's word, forwarded verbatim.

The presented approver arrives in the body as a non-secret reference and is recorded
as exactly that (``identity_proof: PRESENTED_UNPROVEN``). A deployment that fronts
this app with an identity provider replaces the body field with the session's
principal in its own composition root; this package does not do it and says so.
"""


from typing import Any, Mapping

from ugence_approval_workflow import ApproverKind, ApproverRef, ReviewDecision

from .linkage import linkage_view
from .service import DecisionOutcome, QueueEntry, ReviewService
from .version import CONTRACT_VERSION, IDENTITY_PROOF, MATURITY, __version__

__all__ = ["ROUTES", "build_app", "queue_entry_view", "decision_view"]

#: (method, path, operation id). The prohibition scan in the boundary tests runs
#: over this table, so a route cannot be added without passing it.
ROUTES = (
    ("GET", "/review/queue", "review_list_queue"),
    ("GET", "/review/runs/{instance_id}", "review_read_run"),
    ("GET", "/review/runs/{instance_id}/events", "review_read_run_events"),
    ("GET", "/review/approvals/{approval_id}", "review_read_approval"),
    ("POST", "/review/decisions", "review_submit_decision"),
)


def queue_entry_view(entry: QueueEntry) -> dict:
    return {
        "approval_id": entry.approval_id,
        "approval_state": entry.approval_state.value,
        "instance_id": entry.instance_id,
        "task_id": entry.task_id,
        "fingerprint": entry.fingerprint,
        "required_role": entry.required_role,
        "requested_by": entry.requested_by,
        "requested_at": entry.requested_at.isoformat(),
        "expires_at": entry.expires_at.isoformat(),
        "justification": entry.justification,
        "workflow_id": entry.workflow_id,
        "workflow_status": entry.workflow_status,
        "task_status": entry.task_status,
        "provider_id": entry.provider_id,
        "operation": entry.operation,
        "governance_disposition": entry.governance_disposition,
        "eligible_approvers": [a.to_dict() for a in entry.eligible_approvers],
        "instance_known": entry.instance_known,
    }


def decision_view(outcome: DecisionOutcome) -> dict:
    return {
        "result": outcome.result.value,
        "recorded": outcome.recorded,
        "approval_id": outcome.approval_id,
        "approval": None if outcome.approval is None else outcome.approval.to_dict(),
        "instance_id": outcome.instance_id,
        "task_id": outcome.task_id,
        "signal_delivered": outcome.signal_delivered,
        "resume_delivered": outcome.resume_delivered,
        "resume_skipped_reason": outcome.resume_skipped_reason,
        "reason": outcome.reason,
        "identity_proof": outcome.identity_proof,
        "linkage": linkage_view(outcome.linkage),
    }


def _approver_from(body: Mapping[str, Any]) -> ApproverRef:
    presented = body.get("presented_approver")
    if not isinstance(presented, Mapping):
        raise ValueError("presented_approver is required and must be an object")
    return ApproverRef(
        approver_id=str(presented.get("approver_id", "")),
        approver_kind=ApproverKind(str(presented.get("approver_kind", "HUMAN"))),
        role=str(presented.get("role", "")),
        authority_reference=str(presented.get("authority_reference", "")),
    )


def build_app(service: ReviewService) -> Any:
    """A FastAPI application over one service. Requires the ``http`` extra."""

    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(
        title="Ugence Governed Review Service",
        version=__version__,
        description=(
            f"{MATURITY}. Records a human decision a presented approver made "
            f"({IDENTITY_PROOF}); never approves, authenticates, clears or executes."
        ),
    )
    app.state.contract_version = CONTRACT_VERSION

    @app.get(ROUTES[0][1], operation_id=ROUTES[0][2])
    def review_list_queue(required_role: str = "") -> Any:
        entries = service.list_queue(required_role=required_role)
        return {"entries": [queue_entry_view(e) for e in entries],
                "maturity": MATURITY, "identity_proof": IDENTITY_PROOF}

    @app.get(ROUTES[1][1], operation_id=ROUTES[1][2])
    def review_read_run(instance_id: str) -> Any:
        run = service.read_run(instance_id)
        if run is None:
            raise HTTPException(status_code=404, detail="unknown instance")
        return run

    @app.get(ROUTES[2][1], operation_id=ROUTES[2][2])
    def review_read_run_events(instance_id: str) -> Any:
        events = service.read_run_events(instance_id)
        if events is None:
            raise HTTPException(status_code=404, detail="unknown instance")
        return {"instance_id": instance_id, "events": list(events)}

    @app.get(ROUTES[3][1], operation_id=ROUTES[3][2])
    def review_read_approval(approval_id: str) -> Any:
        view = service.read_approval(approval_id)
        if view is None:
            raise HTTPException(status_code=404, detail="unknown approval")
        return view

    @app.post(ROUTES[4][1], operation_id=ROUTES[4][2])
    async def review_submit_decision(request: Request) -> Any:
        body = await request.json()
        if not isinstance(body, Mapping):
            raise HTTPException(status_code=422, detail="the body must be an object")
        try:
            decision = ReviewDecision(str(body.get("decision", "")))
            approver = _approver_from(body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        outcome = service.submit_decision(
            approval_id=str(body.get("approval_id", "")), decision=decision,
            presented_approver=approver, justification=str(body.get("justification", "")),
        )
        status = 200 if outcome.recorded else 409
        return JSONResponse(status_code=status, content=decision_view(outcome))

    return app
