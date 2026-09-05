"""The whole composition root over a real PostgreSQL 16, the real SQLite stores and the
AI-C adapter's in-process issuer: start, park on ESCALATE, list over HTTP, decide over
HTTP with a signed proof, re-arm, consume, run the fixture provider once, link into
the audit ledger, and never let a DSN or a token into any answer or any output (row 8).

Test mode is used because the issuer serves its JWKS over loopback HTTP; the posture
rows in ``test_preflight.py`` are the production evidence. Nothing here reads a wall
clock: one settable clock is injected everywhere.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import pytest

from _issuer import InProcessIssuer
from governed_runtime_worker import ShadowWorkload, compose
from ugence_approval_workflow import ApprovalState, ApproverKind
from ugence_authority_directory import PrincipalKind, PrincipalRef, RoleGrant, grant_id_for
from ugence_governance_contracts.api import Validity
from ugence_governed_review import SUBJECT_KIND
from ugence_governed_review_service import (
    IDP_AUTHENTICATED,
    PROOF_HEADER,
    VerifiedClaims,
    authentication_reference,
    subject_reference,
    verify_authentication_reference,
)

from conftest import (
    ACTOR_CLAIM,
    AUDIENCE,
    HUMAN_VALUE,
    ISSUER,
    NOW,
    ROLE,
    TENANT,
    TENANT_CLAIM,
    Clock,
    config_for,
    requires_postgres,
)

INSTANCE = "i-shadow-1"


def claims_for(issuer: InProcessIssuer, subject: str = "alice") -> dict:
    return {
        "iss": issuer.issuer, "sub": subject, "aud": issuer.audience,
        "iat": int((NOW - timedelta(seconds=60)).timestamp()),
        "exp": int((NOW + timedelta(hours=1)).timestamp()),
        "auth_time": int((NOW - timedelta(minutes=2)).timestamp()),
        "jti": "jti-e2e-0001", "amr": ["pwd", "otp"], "acr": "urn:example:loa2",
        TENANT_CLAIM: TENANT, ACTOR_CLAIM: HUMAN_VALUE,
    }


def subject_ref(subject: str) -> str:
    probe = VerifiedClaims(issuer=ISSUER, subject=subject, audience=AUDIENCE,
                           authenticated_at=NOW, expires_at=NOW)
    return subject_reference(probe)


@pytest.fixture()
def issuer():
    iss = InProcessIssuer(issuer=ISSUER, audience=AUDIENCE)
    iss.add_key("RS256", kid="rsa-1")
    iss.start()
    try:
        yield iss
    finally:
        iss.stop()


@pytest.fixture()
def worker(pg_databases, tmp_path, issuer):
    app_url, sys_url = pg_databases
    data_dir = tmp_path / "volume"
    data_dir.mkdir()
    cfg = config_for(
        tmp_path, "test", app_database_url=app_url, system_database_url=sys_url,
        data_dir=str(data_dir), identity_issuer=ISSUER, identity_audience=AUDIENCE,
        identity_jwks_url=issuer.jwks_url, identity_tenant_claim=TENANT_CLAIM,
        identity_actor_type_claim=ACTOR_CLAIM, identity_human_actor_value=HUMAN_VALUE,
    )
    clock = Clock()
    w = compose(cfg, clock=clock, workload=ShadowWorkload(required_role=ROLE))
    w.clock = clock  # type: ignore[attr-defined]
    try:
        yield w
    finally:
        w.close()


def _grant(worker, subject: str = "alice") -> None:
    """Alice's role grant in the authority directory, keyed by the issuer-qualified
    subject the adapter will present, over every proposal of the review subject kind."""

    validity = Validity(issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30))
    scope = f"approval/{SUBJECT_KIND}"
    principal = PrincipalRef(principal_id=subject_ref(subject), principal_kind=PrincipalKind.HUMAN,
                             display_ref=subject)
    worker.directory.put_grant(RoleGrant(
        grant_id=grant_id_for(TENANT, principal.principal_id, ROLE, scope, validity),
        tenant_id=TENANT, principal=principal, role=ROLE, scope=scope, validity=validity,
        authority_reference=f"directory://roles/{ROLE}",
    ), as_of=NOW - timedelta(days=1), loaded_by="e2e")


def _park(worker) -> None:
    worker.adapter.start(workflow_id=ShadowWorkload.WORKFLOW_ID,
                         definition_digest=worker.config.definition_digest,
                         instance_id=INSTANCE, correlation_id="c-e2e", inputs={})
    outcome = worker.adapter.advance(instance_id=INSTANCE, attempt_token="a1")
    assert outcome.awaiting_external and not outcome.terminal
    assert worker.workload.provider.calls == []


@requires_postgres
def test_the_composed_worker_parks_lists_decides_over_http_re_arms_consumes_and_links(
        worker, issuer, capsys):
    from fastapi.testclient import TestClient

    _grant(worker)
    _park(worker)
    client = TestClient(worker.app)
    answers: list[str] = []

    def get(path: str, expect: int = 200):
        r = client.get(path)
        answers.append(r.text)
        assert r.status_code == expect, r.text
        return r.json()

    # -- list ---------------------------------------------------------------------
    queue = get("/review/queue")
    assert queue["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"
    (entry,) = queue["entries"]
    assert entry["instance_id"] == INSTANCE and entry["task_id"] == "t1"
    assert entry["governance_disposition"] == "ESCALATE" and entry["workflow_status"] == "PAUSED"
    approval_id = entry["approval_id"]
    assert get(f"/review/approvals/{approval_id}")["state"] == "PENDING"

    # -- decide with a signed proof --------------------------------------------------
    token = issuer.mint(claims_for(issuer), kid="rsa-1")
    body = {
        "approval_id": approval_id, "decision": "GRANT", "justification": "reviewed",
        "presented_approver": {
            "approver_id": subject_ref("alice"), "approver_kind": "HUMAN", "role": ROLE,
            "authority_reference": f"directory://roles/{ROLE}",
        },
    }
    worker.clock.advance(minutes=5)
    r = client.post("/review/decisions", json=body, headers={PROOF_HEADER: token})
    answers.append(r.text)
    assert r.status_code == 200, r.text
    decided = r.json()
    assert decided["result"] == "RECORDED" and decided["recorded"] is True
    assert decided["identity_proof"] == IDP_AUTHENTICATED
    assert decided["tenant_source"] == "PROOF"
    assert decided["signal_delivered"] and decided["resume_delivered"]
    assert decided["approval"]["decided_by"] == subject_ref("alice")
    reference = decided["authentication_reference"]
    expected = worker.identity_port.authenticate(token).claims
    assert reference == authentication_reference(expected)
    assert verify_authentication_reference(expected, reference)
    assert decided["approval"]["authentication_reference"] == reference
    assert decided["linkage"]["state"] == "NOT_YET"
    assert worker.workload.provider.calls == [], "recording and re-arming run nothing"
    assert get("/review/queue")["entries"] == []
    assert get(f"/review/runs/{INSTANCE}")["instance"]["status"] == "RUNNING"

    # -- the next quantum consumes the grant and runs the fixture once -------------------
    outcome = worker.adapter.advance(instance_id=INSTANCE, attempt_token="a2")
    assert outcome.progressed and not outcome.awaiting_external
    assert len(worker.workload.provider.calls) == 1
    assert worker.workload.provider.calls[0][1] == "do"
    record = worker.ledger.get_approval(approval_id)
    assert record.state is ApprovalState.CONSUMED
    assert record.authentication_reference == reference
    assert record.decided_by == subject_ref("alice")

    # -- linkage into the control-plane audit ledger (HE-1, HE-5, AI-D) ----------------
    run = get(f"/review/runs/{INSTANCE}")
    (link,) = run["linkages"]
    assert link["state"] == "APPENDED"
    assert link["linkage"]["authentication_reference"] == reference
    assert link["linkage"]["proposal_fingerprint"] == record.subject_digest
    assert get(f"/review/runs/{INSTANCE}")["linkages"][0]["state"] == "ALREADY_APPENDED"
    assert worker.audit.entry_count() == 1 and worker.audit.verify_chain(tenant_id=TENANT)
    events = get(f"/review/runs/{INSTANCE}/events")["events"]
    assert any(e["event_type"].startswith("EXTERNAL_SIGNAL") for e in events)

    # -- row 8: no DSN and no token anywhere -------------------------------------------
    captured = capsys.readouterr()
    everything = "\n".join(answers) + captured.out + captured.err + json.dumps(run)
    for secret in (worker.config.app_database_url, worker.config.system_database_url, token):
        assert secret not in everything
    for event in worker.ledger.approval_events(approval_id):
        assert token not in json.dumps(event.to_dict())
    assert "postgresql" not in captured.out + captured.err

    # -- the three stores are files on the volume -------------------------------------
    names = sorted(os.listdir(worker.config.data_dir))
    assert {"authority-directory.sqlite3", "approvals.sqlite3", "audit-ledger.sqlite3"} <= set(names)


@requires_postgres
def test_without_a_proof_or_with_a_stranger_nothing_is_recorded_and_the_run_stays_parked(
        worker, issuer):
    from fastapi.testclient import TestClient

    _grant(worker)
    _park(worker)
    client = TestClient(worker.app)
    (entry,) = client.get("/review/queue").json()["entries"]
    body = {
        "approval_id": entry["approval_id"], "decision": "GRANT", "justification": "x",
        "presented_approver": {"approver_id": subject_ref("alice"), "approver_kind": "HUMAN",
                               "role": ROLE, "authority_reference": f"directory://roles/{ROLE}"},
    }
    # row 3 of the composition ADR (AI-A row 1): no proof at all
    r = client.post("/review/decisions", json=body)
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_UNAUTHENTICATED"
    # a forged proof
    forged = issuer.mint(claims_for(issuer), kid="rsa-1", pem=issuer.foreign_pem())
    r = client.post("/review/decisions", json=body, headers={PROOF_HEADER: forged})
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_UNAUTHENTICATED"
    # a proven subject who holds no grant in the directory
    carol = issuer.mint(claims_for(issuer, "carol"), kid="rsa-1")
    body_carol = dict(body, presented_approver=dict(body["presented_approver"],
                                                   approver_id=subject_ref("carol")))
    r = client.post("/review/decisions", json=body_carol, headers={PROOF_HEADER: carol})
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_INELIGIBLE"

    assert worker.ledger.get_approval(entry["approval_id"]).state is ApprovalState.PENDING
    outcome = worker.adapter.advance(instance_id=INSTANCE, attempt_token="a2")
    assert outcome.awaiting_external and worker.workload.provider.calls == []
    assert worker.audit.entry_count() == 0
