"""The five routes, through Starlette's test client, over the service core."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ugence_approval_workflow import ReviewDecision, StaticApproverEligibility  # noqa: E402

from ugence_governed_review_service import ROUTES, StaticRunReader, build_app  # noqa: E402

import _service_fixtures as S  # noqa: E402

F = S.F
FP = "c" * 64


@pytest.fixture()
def client(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    adapter = S.RecordingAdapter(known=("i1",))
    svc = S.service(ledger, clock, adapter=adapter,
                    reader=StaticRunReader({"i1": S.parked_checkpoint("i1", "t1", FP)}),
                    eligibility=StaticApproverEligibility((F.APPROVER,)))
    aid = S.request_for(ledger, clock, "i1", fingerprint=FP).approval_id
    with TestClient(build_app(svc)) as c:
        yield c, aid, adapter


def _presented(approver=F.APPROVER) -> dict:
    return approver.to_dict()


def test_the_openapi_surface_is_exactly_the_audited_routes(client):
    c, _aid, _ = client
    spec = c.get("/openapi.json").json()
    seen = {(m.upper(), path, op["operationId"])
            for path, ops in spec["paths"].items() for m, op in ops.items()}
    assert seen == set(ROUTES)


def test_queue_run_events_and_approval_reads(client):
    c, aid, _ = client
    q = c.get("/review/queue").json()
    assert q["identity_proof"] == "PRESENTED_UNPROVEN" and q["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"
    (entry,) = q["entries"]
    assert entry["approval_id"] == aid and entry["fingerprint"] == FP
    assert entry["eligible_approvers"][0]["approver_id"] == F.APPROVER.approver_id
    assert c.get("/review/queue", params={"required_role": "auditor"}).json()["entries"] == []
    run = c.get("/review/runs/i1").json()
    assert run["instance"]["status"] == "PAUSED" and run["open_approvals"][0]["approval_id"] == aid
    assert c.get("/review/runs/nope").status_code == 404
    assert c.get("/review/runs/i1/events").json() == {"instance_id": "i1", "events": []}
    assert c.get("/review/runs/nope/events").status_code == 404
    assert c.get(f"/review/approvals/{aid}").json()["state_at"] == "PENDING"
    assert c.get("/review/approvals/nope").status_code == 404


def test_a_decision_is_relayed_verbatim_and_answered_with_the_typed_outcome(client):
    c, aid, adapter = client
    r = c.post("/review/decisions", json={"approval_id": aid, "decision": "GRANT",
                                          "presented_approver": _presented(),
                                          "justification": "looked fine"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"] == "RECORDED" and body["recorded"]
    assert body["signal_delivered"] and body["resume_delivered"]
    assert body["identity_proof"] == "PRESENTED_UNPROVEN"
    assert body["approval"]["justification"] == "looked fine"
    assert adapter.resumes == ["i1"]
    assert c.get("/review/queue").json()["entries"] == []


def test_a_refusal_is_a_409_with_the_reason_and_the_standing_record(client):
    c, aid, adapter = client
    r = c.post("/review/decisions", json={"approval_id": aid, "decision": "GRANT",
                                          "presented_approver": _presented(F.OTHER_ROLE_APPROVER)})
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_INELIGIBLE"
    assert r.json()["approval"]["state"] == "PENDING" and adapter.signals == []
    r = c.post("/review/decisions", json={"approval_id": "nope", "decision": "REJECT",
                                          "presented_approver": _presented()})
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_UNKNOWN_APPROVAL"


@pytest.mark.parametrize("body", [
    {"approval_id": "x", "decision": "APPROVE", "presented_approver": F.APPROVER.to_dict()},
    {"approval_id": "x", "decision": "GRANT"},
    {"approval_id": "x", "decision": "GRANT", "presented_approver": "me"},
    {"approval_id": "x", "decision": "GRANT", "presented_approver": {"approver_kind": "ROBOT",
                                                                     "approver_id": "a", "role": "r"}},
    [],
])
def test_a_malformed_submission_is_422_and_nothing_is_recorded(client, body):
    c, _aid, adapter = client
    assert c.post("/review/decisions", json=body).status_code == 422
    assert adapter.signals == []


def test_request_changes_is_refused_not_mapped(client):
    c, aid, _ = client
    r = c.post("/review/decisions", json={"approval_id": aid, "decision": ReviewDecision.REQUEST_CHANGES.value,
                                          "presented_approver": _presented()})
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_INVALID_DECISION"


def test_the_queue_view_renders_a_directory_projection_that_is_not_an_approver_ref():
    """A composition root whose eligibility comes from the authority directory lists
    ``DirectoryApproverRef`` projections: structurally an ``ApproverRef`` without its
    ``to_dict``. The view reads the structure, never the method."""

    from dataclasses import replace

    from ugence_approval_workflow import ApprovalState
    from enum import Enum

    from ugence_governed_review_service.http import queue_entry_view
    from ugence_governed_review_service.service import QueueEntry

    class Kind(str, Enum):
        HUMAN = "HUMAN"

    class Projection:
        approver_id = "https%3A%2F%2Fissuer.test|alice"
        approver_kind = Kind.HUMAN
        role = S.F.ROLE
        authority_reference = "directory://roles/risk-approver"

    entry = QueueEntry(
        approval_id="ap-1", approval_state=ApprovalState.PENDING, instance_id="i1",
        task_id="t1", fingerprint="f" * 64, required_role=S.F.ROLE, requested_by="r",
        requested_at=S.F.T0, expires_at=S.F.T0, eligible_approvers=(Projection(),),
    )
    view = queue_entry_view(entry)
    assert view["eligible_approvers"] == [{
        "approver_id": Projection.approver_id, "approver_kind": "HUMAN",
        "role": S.F.ROLE, "authority_reference": Projection.authority_reference}]
    assert queue_entry_view(replace(entry, eligible_approvers=()))["eligible_approvers"] == []
