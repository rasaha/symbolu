"""The seven routes, through Starlette's test client, over the service core."""

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


# --------------------------------------------------------------------------- #
# the sixth route (front-door seam 6, FD-10)
# --------------------------------------------------------------------------- #
def test_the_start_route_without_a_composed_starter_is_the_typed_unconfigured_refusal(client):
    c, _aid, adapter = client
    r = c.post("/review/runs", json={})
    assert r.status_code == 409
    body = r.json()
    assert body["result"] == "REFUSED_UNCONFIGURED" and body["started"] is False
    assert body["mode"] == "shadow" and body["instance_id"] == ""
    assert body["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"
    assert adapter.signals == [] and adapter.resumes == []


def test_the_start_route_refuses_any_mode_but_shadow_before_the_starter(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    starter = S.RecordingStarter()
    svc = S.service(ledger, clock, starter=starter)
    with TestClient(build_app(svc)) as c:
        for mode in ("live", "LIVE", "dry_run", "simulation", ""):
            r = c.post("/review/runs", json={"mode": mode})
            assert r.status_code == 409 and r.json()["result"] == "REFUSED_MODE", mode
        assert starter.calls == [], "nothing reached the starter"
        ok = c.post("/review/runs", json={"mode": "shadow", "correlation_id": "c-1"})
        assert ok.status_code == 200 and ok.json()["result"] == "STARTED"
        same = c.post("/review/runs", json={"correlation_id": "c-1"})
        assert same.json()["result"] == "REPLAYED" and same.json()["instance_id"] == ok.json()["instance_id"]
        assert starter.calls == ["c-1", "c-1"]


def test_the_start_route_takes_no_definition_provider_mode_word_or_digest(tmp_path):
    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    starter = S.RecordingStarter()
    svc = S.service(ledger, clock, starter=starter)
    with TestClient(build_app(svc)) as c:
        for extra in ({"workflow": {}}, {"workflow_id": "wf"}, {"tasks": []}, {"provider_id": "p"},
                      {"definition_digest": "d"}, {"execution_mode": "LIVE"}, {"inputs": {}},
                      {"instance_id": "chosen"}, {"tenant_id": "other"}):
            r = c.post("/review/runs", json={"correlation_id": "c", **extra})
            assert r.status_code == 422, extra
            assert "FD-10.3" in r.json()["detail"]
        assert c.post("/review/runs", json={"correlation_id": "has space"}).status_code == 422
        assert c.post("/review/runs", json={"correlation_id": 7}).status_code == 422
        assert c.post("/review/runs", json=[1]).status_code == 422
        assert c.post("/review/runs", content=b"not json",
                      headers={"Content-Type": "application/json"}).status_code == 422
        assert starter.calls == []


# --------------------------------------------------------------------------- #
# the seventh route (front-door seam 7, FD-11)
# --------------------------------------------------------------------------- #
def _entry(correlation: str, step: int, at):
    return dict(tenant_id=F.TENANT, kind="governed_review.linkage.v2", recorded_at=at,
                recorded_by="governed-review-service", payload={"step": step},
                correlation_id=correlation)


def test_the_audit_route_without_a_composed_reader_is_the_typed_unconfigured_refusal(client):
    c, _aid, _adapter = client
    r = c.get("/review/audit/corr-1")
    assert r.status_code == 409
    body = r.json()
    assert body["result"] == "REFUSED_UNCONFIGURED" and body["read"] is False
    assert body["entries"] == [] and body["chain_verified"] is False
    assert body["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"


def test_the_audit_route_reads_the_tenants_rows_in_chain_order_with_the_verification(tmp_path):
    from datetime import timedelta

    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    t0 = clock.datetime()
    _path, audit = S.file_audit_ledger(
        tmp_path,
        _entry("corr-1", 1, t0), _entry("corr-2", 9, t0 + timedelta(minutes=1)),
        _entry("corr-1", 2, t0 + timedelta(minutes=2)),
        dict(tenant_id="tenant-other", kind="k", recorded_at=t0, recorded_by="x",
             payload={"step": 7}, correlation_id="corr-1"))
    svc = S.service(ledger, clock, ledger_reader=audit)
    with TestClient(build_app(svc)) as c:
        r = c.get("/review/audit/corr-1")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["result"] == "READ" and body["read"] is True and body["chain_verified"] is True
        assert body["tenant_id"] == F.TENANT and body["correlation_id"] == "corr-1"
        assert [e["payload"]["step"] for e in body["entries"]] == [1, 2], "own tenant, chain order"
        assert body["entry_count"] == 2
        first = body["entries"][0]
        assert set(first) == {"seq", "entry_ref", "kind", "recorded_at", "recorded_by",
                              "correlation_id", "payload", "prev_digest", "record_digest"}
        assert first["entry_ref"] == f"{F.TENANT}/{first['seq']}"
        assert first["kind"] == "governed_review.linkage.v2" and len(first["record_digest"]) == 64
        assert "raw and uninterpreted" in body["record_type"]
        assert c.get("/review/audit/corr-nope").status_code == 404
        assert c.get("/review/audit/has%20space").status_code == 422
        # no list-all and no write
        assert c.get("/review/audit").status_code in (404, 405)
        assert c.post("/review/audit/corr-1", json={}).status_code == 405
        assert c.delete("/review/audit/corr-1").status_code == 405
    audit.close()


def test_a_chain_that_does_not_verify_is_a_typed_refusal_with_the_entries_withheld(tmp_path):
    import sqlite3

    clock, ledger = F.Clock(), F.sqlite_ledger(tmp_path)
    t0 = clock.datetime()
    path, audit = S.file_audit_ledger(tmp_path, _entry("corr-1", 1, t0), _entry("corr-1", 2, t0))
    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER ledger_no_update")
    raw.execute("UPDATE ledger_entries SET content_digest=? WHERE tenant_seq=0", ("0" * 64,))
    raw.commit()
    raw.close()
    svc = S.service(ledger, clock, ledger_reader=audit)
    with TestClient(build_app(svc)) as c:
        r = c.get("/review/audit/corr-1")
        assert r.status_code == 409, r.text
        body = r.json()
        assert body["result"] == "REFUSED_INTEGRITY" and body["read"] is False
        assert body["entries"] == [] and body["chain_verified"] is False
        assert "does not verify" in body["reason"] and "withheld" in body["reason"]
    audit.close()
