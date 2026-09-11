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
from governed_runtime_worker.authority_plane import PLANE_OPERATIONS, SERVED_WRITES
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


# --------------------------------------------------------------------------- #
# front-door seam 6 (FD-10): the start relay over the real adapter
# --------------------------------------------------------------------------- #
@requires_postgres
def test_the_sixth_route_starts_the_workers_own_shadow_run_parks_it_and_replays(worker, issuer):
    """§11.3 rows 3, 4, 5, 7 and 8 over the composed worker: the caller sends a
    correlation id and nothing else; the worker's own definition and digest bind; the
    run parks on ESCALATE in the existing queue; a retried start replays; a human
    decision through the existing relay is what resumes it."""

    from fastapi.testclient import TestClient
    from governed_runtime_worker import instance_id_for

    _grant(worker)
    client = TestClient(worker.app)
    assert worker.service.starter_configured and worker.starter is not None

    started = client.post("/review/runs", json={"correlation_id": "c-relay"})
    assert started.status_code == 200, started.text
    body = started.json()
    instance = instance_id_for(ShadowWorkload.WORKFLOW_ID, "c-relay")
    assert body["result"] == "STARTED" and body["instance_id"] == instance
    assert body["workflow_id"] == ShadowWorkload.WORKFLOW_ID
    assert body["definition_digest"] == worker.config.definition_digest
    assert body["advanced"] is True and body["awaiting_external"] is True
    assert body["mode"] == "shadow" and body["workload_maturity"] == "FIXTURE_ONLY"
    assert worker.workload.provider.calls == [], "parked before any provider ran"

    # row 5: parked in the existing queue, read through the existing reads
    (entry,) = client.get("/review/queue").json()["entries"]
    assert entry["instance_id"] == instance and entry["governance_disposition"] == "ESCALATE"
    assert client.get(f"/review/runs/{instance}").json()["instance"]["status"] == "PAUSED"
    assert client.get(f"/review/runs/{instance}").json()["engine"]["definition_digest"] == \
        worker.config.definition_digest

    # row 4: a retried start is a replay; nothing re-runs
    again = client.post("/review/runs", json={"correlation_id": "c-relay", "mode": "shadow"})
    assert again.status_code == 200 and again.json()["result"] == "REPLAYED"
    assert again.json()["instance_id"] == instance and again.json()["advanced"] is False
    assert len(client.get("/review/queue").json()["entries"]) == 1
    assert worker.workload.provider.calls == []

    # rows 3, 7, 8: nothing else can be named; a foreign digest is the adapter's refusal
    for extra in ({"workflow": {"workflow_id": "wf-mine"}}, {"definition_digest": "other"},
                  {"tenant_id": "tenant-b"}, {"execution_mode": "LIVE"}, {"provider_id": "p"}):
        assert client.post("/review/runs", json={"correlation_id": "c-relay", **extra}).status_code == 422
    assert client.post("/review/runs", json={"mode": "live"}).json()["result"] == "REFUSED_MODE"
    from governed_runtime_worker import ShadowRunStarter

    foreign = ShadowRunStarter(adapter=worker.adapter, workflow_id=ShadowWorkload.WORKFLOW_ID,
                               definition_digest="not-this-deployment", workload_maturity="FIXTURE_ONLY")
    refused = foreign.start(correlation_id="c-foreign")
    assert refused.result.value == "REFUSED_DEFINITION" and not refused.started
    assert worker.adapter.status(instance_id=refused.instance_id) == {"known": False}

    # the existing decision relay is what resumes the relayed run
    token = issuer.mint(claims_for(issuer), kid="rsa-1")
    worker.clock.advance(minutes=1)
    decided = client.post("/review/decisions", json={
        "approval_id": entry["approval_id"], "decision": "GRANT", "justification": "reviewed",
        "presented_approver": {"approver_id": subject_ref("alice"), "approver_kind": "HUMAN",
                               "role": ROLE, "authority_reference": f"directory://roles/{ROLE}"},
    }, headers={PROOF_HEADER: token})
    assert decided.status_code == 200 and decided.json()["resume_delivered"]
    outcome = worker.adapter.advance(instance_id=instance, attempt_token="a-after")
    assert outcome.progressed and len(worker.workload.provider.calls) == 1
    everything = started.text + again.text + decided.text
    for secret in (worker.config.app_database_url, worker.config.system_database_url, token):
        assert secret not in everything


# --------------------------------------------------------------------------- #
# front-door seam 7 (FD-11): the ledger read over the composed worker
# --------------------------------------------------------------------------- #
@requires_postgres
def test_the_seventh_route_reads_the_relayed_runs_receipt_from_the_workers_own_ledger(worker, issuer):
    """§12.4 rows 3, 7 and 9 over the composed worker: before any GRANT the correlation
    id is a typed not-found; after the existing decision relay and the next quantum the
    linkage the appender wrote is read back raw, chain verified, own tenant only."""

    from fastapi.testclient import TestClient
    from governed_runtime_worker import instance_id_for

    _grant(worker)
    client = TestClient(worker.app)
    assert worker.service.ledger_reader_configured

    started = client.post("/review/runs", json={"correlation_id": "c-ledger"})
    assert started.status_code == 200 and started.json()["result"] == "STARTED"
    instance = instance_id_for(ShadowWorkload.WORKFLOW_ID, "c-ledger")
    assert client.get("/review/audit/c-ledger").status_code == 404, "nothing recorded yet"

    (entry,) = client.get("/review/queue").json()["entries"]
    token = issuer.mint(claims_for(issuer), kid="rsa-1")
    worker.clock.advance(minutes=1)
    decided = client.post("/review/decisions", json={
        "approval_id": entry["approval_id"], "decision": "GRANT", "justification": "reviewed",
        "presented_approver": {"approver_id": subject_ref("alice"), "approver_kind": "HUMAN",
                               "role": ROLE, "authority_reference": f"directory://roles/{ROLE}"},
    }, headers={PROOF_HEADER: token})
    assert decided.status_code == 200
    worker.adapter.advance(instance_id=instance, attempt_token="a-ledger")
    run = client.get(f"/review/runs/{instance}").json()
    assert run["linkages"][0]["state"] == "APPENDED"

    read = client.get("/review/audit/c-ledger", headers={PROOF_HEADER: token})
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["result"] == "READ" and body["chain_verified"] is True
    assert body["tenant_id"] == TENANT and body["entry_count"] == 1
    (row,) = body["entries"]
    assert row["kind"] == "governed_review.linkage.v2" and row["correlation_id"] == "c-ledger"
    assert row["recorded_by"] == "governed-runtime-worker"
    assert row["payload"]["instance_id"] == instance and row["payload"]["approval_id"] == entry["approval_id"]
    assert row["record_digest"] == run["linkages"][0]["audit_reference"]["entry_digest"]
    assert row["entry_ref"] == run["linkages"][0]["audit_reference"]["entry_ref"]
    for secret in (worker.config.app_database_url, worker.config.system_database_url, token):
        assert secret not in read.text


# --------------------------------------------------------------------------- #
# the authority plane's four reads (AP-5) over the real composition
# --------------------------------------------------------------------------- #
@requires_postgres
def test_the_authority_reads_are_served_by_the_composed_worker_and_no_write_is(worker, issuer):
    """ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 2 over the composed worker, not a
    hand-built router: the four AP-5 reads answer from the directory this composition
    opened, at its clock, for its tenant, labelled with the decision proof a composed
    identity port gives; a proof header is neither required nor read; the grant the
    decision route consumed is the grant the reads show; no AP-3 write path answers;
    and no DSN or token appears in any answer (row 8)."""

    from fastapi.testclient import TestClient

    _grant(worker)
    scope = f"approval/{SUBJECT_KIND}"
    validity = Validity(issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30))
    bob = PrincipalRef(principal_id=subject_ref("bob"), principal_kind=PrincipalKind.HUMAN, display_ref="bob")
    bob_grant = worker.directory.put_grant(RoleGrant(
        grant_id=grant_id_for(TENANT, bob.principal_id, ROLE, scope, validity), tenant_id=TENANT,
        principal=bob, role=ROLE, scope=scope, validity=validity,
        authority_reference=f"directory://roles/{ROLE}", member_of="risk-committee",
    ), as_of=NOW - timedelta(days=1), loaded_by="e2e")
    committee = PrincipalRef(principal_id="risk-committee", principal_kind=PrincipalKind.COMMITTEE, quorum=2)
    worker.directory.put_grant(RoleGrant(
        grant_id=grant_id_for(TENANT, committee.principal_id, ROLE, scope, validity), tenant_id=TENANT,
        principal=committee, role=ROLE, scope=scope, validity=validity,
        authority_reference=f"directory://roles/{ROLE}",
    ), as_of=NOW - timedelta(days=1), loaded_by="e2e")

    client = TestClient(worker.app)
    answers: list[str] = []

    def read(path: str, expect: int = 200, **kwargs):
        r = client.get(path, **kwargs)
        answers.append(r.text)
        assert r.status_code == expect, r.text
        body = r.json()
        if expect == 200:
            assert body["result"] == "READ" and body["plane"] == "authority" and body["ruling"] == "AP-5"
            assert body["tenant_id"] == TENANT and body["as_of"] == worker.clock.now.isoformat()
            assert body["read_authenticated"] is False
            assert body["decision_identity_proof"] == IDP_AUTHENTICATED, "an identity port is composed"
            assert body["issuer_validation"] == "CLOUDFLARE_ACCESS_HUMAN_WORKSPACE_GROUP_NONPROD_VALIDATED_2026_09_11_AP3_D6"
            assert "administrator loaded" in body["provenance"]
            assert body["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY"
        return body

    # -- grants for a principal, holders of a role, a committee against its quorum ------
    alice = read("/authority/grants", params={"principal_id": subject_ref("alice")})
    assert alice["grant_count"] == 1 and alice["grants"][0]["role"] == ROLE
    assert alice["grants"][0]["scope"] == scope and alice["grants"][0]["loaded_by"] == "e2e"
    holders = read("/authority/holders", params={"role": ROLE, "scope": scope})
    assert sorted(h["principal"]["principal_id"] for h in holders["holders"]) == sorted(
        [subject_ref("alice"), subject_ref("bob"), "risk-committee"])
    report = read("/authority/committees/risk-committee", params={"role": ROLE, "scope": scope})["report"]
    assert report["committee"]["principal_kind"] == "COMMITTEE" and report["quorum"] == 2
    assert report["member_count"] == 1 and report["quorum_met_at_as_of"] is False

    # -- the grant the decision route consumes is the grant the reads show --------------
    _park(worker)
    (entry,) = client.get("/review/queue").json()["entries"]
    token = issuer.mint(claims_for(issuer), kid="rsa-1")
    worker.clock.advance(minutes=5)
    decided = client.post("/review/decisions", json={
        "approval_id": entry["approval_id"], "decision": "GRANT", "justification": "reviewed",
        "presented_approver": {"approver_id": subject_ref("alice"), "approver_kind": "HUMAN",
                               "role": ROLE, "authority_reference": f"directory://roles/{ROLE}"},
    }, headers={PROOF_HEADER: token})
    assert decided.status_code == 200 and decided.json()["identity_proof"] == IDP_AUTHENTICATED
    after = read("/authority/grants", params={"principal_id": subject_ref("alice")})
    assert after["grants"][0]["grant_id"] == alice["grants"][0]["grant_id"]
    assert after["as_of"] != alice["as_of"], "the read answers at the composition's clock"

    # -- a proof header is neither required nor read ---------------------------------
    bare = read("/authority/grants", params={"principal_id": subject_ref("bob")})
    with_proof = read("/authority/grants", params={"principal_id": subject_ref("bob")},
                      headers={PROOF_HEADER: token})
    assert bare == with_proof

    # -- a revocation shows in the event history, and the revoked holder drops out -------
    worker.directory.revoke_grant(bob_grant.grant_id, as_of=worker.clock.now, reason="left", actor="e2e")
    worker.clock.advance(minutes=1)
    events = read(f"/authority/grants/{bob_grant.grant_id}/events")
    assert [e["event_type"] for e in events["events"]] == ["GRANTED", "REVOKED"]
    assert events["grant"]["revocation_reason"] == "left"
    assert subject_ref("bob") not in {
        h["principal"]["principal_id"]
        for h in read("/authority/holders", params={"role": ROLE, "scope": scope})["holders"]}
    assert read("/authority/grants/no-such-grant/events", expect=404)["result"] == "NOT_FOUND"
    assert read("/authority/grants", params={"principal_id": "not typed"}, expect=422)["result"] == "REFUSED_UNTYPED"

    # -- no write path answers on the composed app (AP-3 controlling, section 18) --------
    writes = [op for op in PLANE_OPERATIONS if op.kind == "write"]
    assert len(writes) == 4 and SERVED_WRITES == ()
    for op in writes:
        path = op.path.format(grant_id=bob_grant.grant_id, constitution_id="c1")
        r = client.request(op.method, path, json={}, headers={PROOF_HEADER: token})
        answers.append(r.text)
        assert r.status_code in (404, 405), (op.method, path, r.status_code)

    # -- row 8: no DSN and no token anywhere -------------------------------------------
    everything = "\n".join(answers)
    for secret in (worker.config.app_database_url, worker.config.system_database_url, token):
        assert secret not in everything


# --------------------------------------------------------------------------- #
# the authority plane's two directory writes (AW-2 to AW-5), as implementation and
# conformance evidence over the real directory and the real JWT adapter; the composed
# worker itself serves neither (AP-3 controlling, section 18)
# --------------------------------------------------------------------------- #
@requires_postgres
def test_the_composed_worker_serves_no_write_while_the_implementation_conforms_over_the_real_adapter(
        worker, issuer):
    """ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md sections 16 and 18. On the composed worker a
    write path answers 405 or 404 even with a valid admin proof, and nothing is recorded.
    On a conformance harness that mounts the implementation over the worker's own
    directory, clock and JWT adapter (in-process issuer: implementation and conformance
    evidence only, never enterprise identity validation): a load with a signed admin
    proof is recorded under the admin's issuer-qualified subject; the grant it loaded is
    the grant a signed decision on the worker is then eligible by; an identical replay is
    ALREADY_LOADED; no proof and a forged proof are refused and record nothing; a revoke
    appends its event under the admin's subject and a second revoke is ALREADY_REVOKED;
    and no token or DSN appears in any answer (row 8)."""

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from governed_runtime_worker.authority_plane import IMPLEMENTED_WRITES
    from governed_runtime_worker.authority_writes import build_authority_writes

    client = TestClient(worker.app)
    answers: list[str] = []
    scope = f"approval/{SUBJECT_KIND}"
    admin_token = issuer.mint(claims_for(issuer, "root-admin"), kid="rsa-1")
    load = {
        "principal": {"principal_id": subject_ref("alice"), "principal_kind": "HUMAN", "display_ref": "alice"},
        "role": ROLE, "scope": scope,
        "issued_at": (NOW - timedelta(days=1)).isoformat(), "expires_at": (NOW + timedelta(days=30)).isoformat(),
        "authority_reference": f"directory://roles/{ROLE}",
    }

    # -- the composed worker: unserved, proof or not, nothing recorded ---------------------
    assert SERVED_WRITES == ()
    r = client.post("/authority/grants", json=load, headers={PROOF_HEADER: admin_token})
    answers.append(r.text)
    assert r.status_code == 405, r.text
    r = client.post("/authority/grants/grant_x/revoke", json={"reason": "x"}, headers={PROOF_HEADER: admin_token})
    answers.append(r.text)
    assert r.status_code == 404, r.text
    assert worker.directory.grants_for(tenant_id=TENANT, principal_id=subject_ref("alice"), as_of=NOW) == ()

    # -- the conformance harness: the implementation over the worker's real seams ---------
    harness = FastAPI()
    harness.include_router(build_authority_writes(
        worker.directory, tenant_id=TENANT, clock=worker.clock.datetime,
        identity_port=worker.identity_port, serve=IMPLEMENTED_WRITES))
    hclient = TestClient(harness)

    def post(path: str, body: dict, expect: int, **kwargs):
        r = hclient.post(path, json=body, **kwargs)
        answers.append(r.text)
        assert r.status_code == expect, r.text
        return r.json()

    # -- refused, and nothing recorded ----------------------------------------------------
    assert post("/authority/grants", load, 409)["result"] == "REFUSED_UNAUTHENTICATED"
    forged = issuer.mint(claims_for(issuer, "root-admin"), kid="rsa-1", pem=issuer.foreign_pem())
    assert post("/authority/grants", load, 409, headers={PROOF_HEADER: forged})["result"] == "REFUSED_UNAUTHENTICATED"
    assert worker.directory.grants_for(tenant_id=TENANT, principal_id=subject_ref("alice"), as_of=NOW) == ()

    # -- recorded under the admin's issuer-qualified subject ------------------------------
    recorded = post("/authority/grants", load, 200, headers={PROOF_HEADER: admin_token})
    assert recorded["result"] == "RECORDED" and recorded["recorded"] is True and recorded["event"] == "GRANTED"
    assert recorded["identity_proof"] == IDP_AUTHENTICATED and recorded["subject"] == subject_ref("root-admin")
    assert recorded["issuer_validation"] == "CLOUDFLARE_ACCESS_HUMAN_WORKSPACE_GROUP_NONPROD_VALIDATED_2026_09_11_AP3_D6" and recorded["ruling"] == "AW-1"
    admin_claims = worker.identity_port.authenticate(admin_token).claims
    assert recorded["authentication_reference"] == authentication_reference(admin_claims)
    grant_id = recorded["grant"]["grant_id"]
    assert recorded["grant"]["loaded_by"] == subject_ref("root-admin")
    assert post("/authority/grants", load, 409, headers={PROOF_HEADER: admin_token})["result"] == "ALREADY_LOADED"

    # -- the loaded grant is what a signed decision is eligible by ------------------------
    _park(worker)
    (entry,) = client.get("/review/queue").json()["entries"]
    alice_token = issuer.mint(claims_for(issuer), kid="rsa-1")
    worker.clock.advance(minutes=2)
    decided = client.post("/review/decisions", json={
        "approval_id": entry["approval_id"], "decision": "GRANT", "justification": "reviewed",
        "presented_approver": {"approver_id": subject_ref("alice"), "approver_kind": "HUMAN",
                               "role": ROLE, "authority_reference": f"directory://roles/{ROLE}"},
    }, headers={PROOF_HEADER: alice_token})
    answers.append(decided.text)
    assert decided.status_code == 200 and decided.json()["identity_proof"] == IDP_AUTHENTICATED

    # -- revoke, under the admin's subject; a second revoke is typed ------------------------
    worker.clock.advance(minutes=1)
    revoked = post(f"/authority/grants/{grant_id}/revoke", {"reason": "rotation"}, 200,
                   headers={PROOF_HEADER: admin_token})
    assert revoked["event"] == "REVOKED" and revoked["grant"]["revocation_reason"] == "rotation"
    assert post(f"/authority/grants/{grant_id}/revoke", {"reason": "again"}, 409,
                headers={PROOF_HEADER: admin_token})["result"] == "ALREADY_REVOKED"
    events = client.get(f"/authority/grants/{grant_id}/events").json()
    answers.append(json.dumps(events))
    assert [(e["event_type"], e["actor"]) for e in events["events"]] == [
        ("GRANTED", subject_ref("root-admin")), ("REVOKED", subject_ref("root-admin"))]
    assert worker.directory.grants_for(tenant_id=TENANT, principal_id=subject_ref("alice"),
                                       as_of=worker.clock.now) == ()

    # -- activate and issue answer nothing anywhere, proof or not ---------------------------
    for op in PLANE_OPERATIONS:
        if op.kind == "write" and op.operation_id not in IMPLEMENTED_WRITES:
            for c in (client, hclient):
                r = c.post(op.path.format(constitution_id="c1"), json={}, headers={PROOF_HEADER: admin_token})
                answers.append(r.text)
                assert r.status_code in (404, 405), op.operation_id

    # -- row 8 ----------------------------------------------------------------------------
    everything = "\n".join(answers)
    for secret in (worker.config.app_database_url, worker.config.system_database_url,
                   admin_token, alice_token, forged):
        assert secret not in everything
