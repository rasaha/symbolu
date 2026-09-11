"""The authority plane's two directory writes at the worker's edge, without PostgreSQL
(ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md section 16, rulings AW-2 to AW-5; section 18,
AW-1 reversed).

    IMPLEMENTATION AND CONFORMANCE EVIDENCE ONLY. Every router here is built with
    ``serve=IMPLEMENTED_WRITES`` explicitly; the contract's default serves nothing under
    AP-3, and one test proves that a default router registers no write.

Proven here: the router serves exactly the two implemented writes when told to and
nothing by default; a worker without an identity port refuses every write; the gate refuses, with a typed
reason and without recording, a missing proof, a proof that authenticates nobody, a
presented-unproven identity, a non-human actor, an expired proof, a port that cannot
answer, and a missing, ambiguous or foreign tenant claim; a load is recorded under the
proven subject with a derived grant id and an identical replay is ALREADY_LOADED; the
intake refuses unknown keys and untyped values before the directory is asked; a revoke
appends its event under the proven subject, a second revoke is ALREADY_REVOKED, and a
foreign tenant's grant reads as unknown; and no proof is echoed in any answer.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ugence_authority_directory import (
    PrincipalKind,
    PrincipalRef,
    RoleGrant,
    SqliteAuthorityDirectory,
    grant_id_for,
)
from ugence_governance_contracts.api import Validity
from ugence_governed_review_service.identity import (
    IDP_AUTHENTICATED,
    PROOF_HEADER,
    ActorKind,
    ApproverIdentity,
    StaticApproverIdentityAdapter,
    VerifiedClaims,
    authentication_reference,
    subject_reference,
)

from governed_runtime_worker.authority_plane import IMPLEMENTED_WRITES, PLANE_OPERATIONS, SERVED_WRITES
from governed_runtime_worker.authority_reads import build_authority_reads
from governed_runtime_worker.authority_writes import (
    LOAD_BODY_KEYS,
    WRITE_OPERATIONS,
    build_authority_writes,
)
from conftest import NOW, TENANT, Clock

ROLE = "risk-approver"
SCOPE = "approval/policy_pack"
ISSUER = "https://issuer.test"
AUDIENCE = "ugence-governed-review-service"

ADMIN = "proof-of-the-admin"
FOREIGN_ADMIN = "proof-of-a-foreign-admin"
NOBODY = "proof-that-authenticates-nobody"
PRESENTED = "proof-the-static-adapter-merely-presents"
SERVICE = "proof-of-a-service-account"
EXPIRED = "proof-that-has-expired"
AMBIGUOUS = "proof-with-two-tenants"
UNTENANTED = "proof-with-no-tenant"


def _claims(subject: str, *, tenants: tuple[str, ...] = (TENANT,), expires_in=timedelta(hours=1)) -> VerifiedClaims:
    return VerifiedClaims(issuer=ISSUER, subject=subject, audience=AUDIENCE,
                          authenticated_at=NOW - timedelta(minutes=1), expires_at=NOW + expires_in,
                          tenant_claims=tenants)


def _proven(claims: VerifiedClaims, kind: ActorKind = ActorKind.HUMAN) -> ApproverIdentity:
    return ApproverIdentity(subject_reference(claims), kind, True, claims, proof=IDP_AUTHENTICATED)


ADMIN_CLAIMS = _claims("root-admin")


class _ProvenPort:
    """A port that answers with what a real adapter would: identities labelled
    ``IDP_AUTHENTICATED``. The static fixture adapter relabels everything
    ``PRESENTED_UNPROVEN`` by design, which is exactly what AW-5 refuses, so it stands
    in here for one proof only, the presented-unproven case."""

    def __init__(self) -> None:
        self._static = StaticApproverIdentityAdapter()
        self._static.register_human(PRESENTED, _claims("presented-admin"))
        self._proven = {
            ADMIN: _proven(ADMIN_CLAIMS),
            FOREIGN_ADMIN: _proven(_claims("other-admin", tenants=("tenant-b",))),
            NOBODY: ApproverIdentity("", ActorKind.SYSTEM, False),
            SERVICE: _proven(_claims("svc"), ActorKind.SYSTEM),
            EXPIRED: _proven(_claims("late-admin", expires_in=timedelta(seconds=-1))),
            AMBIGUOUS: _proven(_claims("two-tenant-admin", tenants=(TENANT, "tenant-b"))),
            UNTENANTED: _proven(_claims("no-tenant-admin", tenants=())),
        }

    def authenticate(self, proof: str) -> ApproverIdentity:
        return self._proven.get(proof) or self._static.authenticate(proof)


def _adapter() -> _ProvenPort:
    return _ProvenPort()


class _BrokenPort:
    def authenticate(self, proof: str):  # noqa: ARG002
        raise RuntimeError("issuer unreachable")


def _app(directory, identity_port, clock: Clock, serve: tuple[str, ...] = IMPLEMENTED_WRITES) -> FastAPI:
    app = FastAPI()
    app.include_router(build_authority_reads(directory, tenant_id=TENANT, clock=clock.datetime,
                                             identity_port_configured=identity_port is not None))
    app.include_router(build_authority_writes(directory, tenant_id=TENANT, clock=clock.datetime,
                                              identity_port=identity_port, serve=serve))
    return app


@pytest.fixture()
def world(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    clock = Clock()
    with TestClient(_app(directory, _adapter(), clock)) as client:
        yield client, directory, clock


def _load(principal_id: str = "https%3A%2F%2Fidp.example%7Calice", **over) -> dict:
    body = {
        "principal": {"principal_id": principal_id, "principal_kind": "HUMAN", "display_ref": "alice"},
        "role": ROLE, "scope": SCOPE,
        "issued_at": (NOW - timedelta(days=1)).isoformat(),
        "expires_at": (NOW + timedelta(days=30)).isoformat(),
        "authority_reference": f"directory://roles/{ROLE}",
    }
    body.update(over)
    return body


def _post(client, path, body, *, proof=ADMIN, expect):
    r = client.post(path, json=body, headers={PROOF_HEADER: proof} if proof else {})
    assert r.status_code == expect, r.text
    answer = r.json()
    assert answer["plane"] == "authority" and "maturity" in answer
    assert answer["issuer_validation"] == "CLOUDFLARE_ACCESS_HUMAN_WORKSPACE_GROUP_NONPROD_VALIDATED_2026_09_11_AP3_D6"
    for secret in (ADMIN, FOREIGN_ADMIN, NOBODY, PRESENTED, SERVICE, EXPIRED, AMBIGUOUS, UNTENANTED):
        assert secret not in r.text, "a proof is never echoed"
    if expect == 200:
        assert answer["result"] == "RECORDED" and answer["recorded"] is True and answer["ruling"] == "AW-1"
        assert answer["identity_proof"] == IDP_AUTHENTICATED and answer["tenant_id"] == TENANT
    else:
        assert answer["recorded"] is False and answer["ruling"] in ("AW-4", "AW-5")
    return answer


# --------------------------------------------------------------------------- #
# what is served
# --------------------------------------------------------------------------- #
def test_the_router_serves_exactly_the_two_implemented_writes_when_told_to(world):
    client, _directory, _clock = world
    spec = client.get("/openapi.json").json()
    posts = {(path, op["operationId"]) for path, ops in spec["paths"].items()
             for m, op in ops.items() if m.upper() == "POST"}
    assert posts == {(op.path, op.operation_id) for op in WRITE_OPERATIONS}
    assert {op.operation_id for op in WRITE_OPERATIONS} == set(IMPLEMENTED_WRITES)
    for op in PLANE_OPERATIONS:
        if op.kind == "write" and op.operation_id not in IMPLEMENTED_WRITES:
            assert client.post(op.path.format(constitution_id="c1"), json={},
                               headers={PROOF_HEADER: ADMIN}).status_code in (404, 405)


def test_by_default_the_router_registers_nothing_because_the_contract_serves_no_write(tmp_path):
    """Section 18, AP-3 controlling: as the composition builds it, the writes router
    is empty, and a valid admin proof changes nothing."""
    assert SERVED_WRITES == ()
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    with TestClient(_app(directory, _adapter(), Clock(), serve=SERVED_WRITES)) as client:
        spec = client.get("/openapi.json").json()
        assert not any(m.upper() == "POST" for ops in spec["paths"].values() for m in ops)
        r = client.post("/authority/grants", json=_load(), headers={PROOF_HEADER: ADMIN})
        assert r.status_code == 405, r.text
        r = client.post("/authority/grants/grant_x/revoke", json={"reason": "x"}, headers={PROOF_HEADER: ADMIN})
        assert r.status_code == 404, r.text
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice", as_of=NOW) == ()
    with pytest.raises(ValueError):
        build_authority_writes(directory, tenant_id=TENANT, clock=Clock().datetime, identity_port=None,
                               serve=("authority_issue_record",))


# --------------------------------------------------------------------------- #
# AW-5: the gate
# --------------------------------------------------------------------------- #
def test_a_worker_without_an_identity_port_refuses_every_write_and_records_nothing(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    with TestClient(_app(directory, None, Clock())) as client:
        r = client.post("/authority/grants", json=_load(), headers={PROOF_HEADER: ADMIN})
        assert r.status_code == 409 and r.json()["result"] == "REFUSED_NO_IDENTITY_PORT", r.text
        r = client.post("/authority/grants/grant_x/revoke", json={"reason": "x"}, headers={PROOF_HEADER: ADMIN})
        assert r.status_code == 409 and r.json()["result"] == "REFUSED_NO_IDENTITY_PORT"
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice", as_of=NOW) == ()


@pytest.mark.parametrize("proof, result", [
    (None, "REFUSED_UNAUTHENTICATED"),
    ("unknown-proof", "REFUSED_UNAUTHENTICATED"),
    (NOBODY, "REFUSED_UNAUTHENTICATED"),
    (PRESENTED, "REFUSED_UNAUTHENTICATED"),
    (SERVICE, "REFUSED_NOT_HUMAN"),
    (EXPIRED, "REFUSED_UNAUTHENTICATED"),
    (AMBIGUOUS, "REFUSED_TENANT_UNPROVEN"),
    (UNTENANTED, "REFUSED_TENANT_UNPROVEN"),
    (FOREIGN_ADMIN, "REFUSED_TENANT_MISMATCH"),
])
def test_the_gate_refuses_with_a_typed_reason_and_records_nothing(world, proof, result):
    client, directory, _clock = world
    answer = _post(client, "/authority/grants", _load(), proof=proof, expect=409)
    assert answer["result"] == result and answer["ruling"] == "AW-5" and answer["reason"]
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice", as_of=NOW) == ()
    # the revoke path is behind the same gate, before the grant id is even looked up
    answer = _post(client, "/authority/grants/grant_nothing/revoke", {"reason": "x"}, proof=proof, expect=409)
    assert answer["result"] == result


def test_a_port_that_cannot_answer_fails_closed(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    with TestClient(_app(directory, _BrokenPort(), Clock())) as client:
        r = client.post("/authority/grants", json=_load(), headers={PROOF_HEADER: ADMIN})
        assert r.status_code == 409 and r.json()["result"] == "REFUSED_IDENTITY_UNAVAILABLE"
        assert "issuer unreachable" not in r.text, "the failure's message never crosses"


# --------------------------------------------------------------------------- #
# AW-1, AW-4: the load
# --------------------------------------------------------------------------- #
def test_a_load_is_recorded_under_the_proven_subject_with_a_derived_id_and_a_replay_is_already_loaded(world):
    client, directory, clock = world
    answer = _post(client, "/authority/grants", _load(), expect=200)
    assert answer["event"] == "GRANTED" and answer["operation"] == "authority_grant_role"
    assert answer["subject"] == subject_reference(ADMIN_CLAIMS)
    assert answer["authentication_reference"] == authentication_reference(ADMIN_CLAIMS)
    assert answer["as_of"] == clock.now.isoformat()
    grant = answer["grant"]
    expected_id = grant_id_for(TENANT, "https%3A%2F%2Fidp.example%7Calice", ROLE, SCOPE,
                               Validity(issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30)))
    assert grant["grant_id"] == expected_id and grant["tenant_id"] == TENANT
    assert grant["loaded_by"] == subject_reference(ADMIN_CLAIMS)
    assert grant["principal"]["principal_kind"] == "HUMAN" and grant["member_of"] == ""
    stored = directory.get_grant(expected_id)
    assert stored is not None and stored.loaded_by == subject_reference(ADMIN_CLAIMS)
    # the reads show it, loaded by the admin
    shown = client.get("/authority/grants", params={"principal_id": "https%3A%2F%2Fidp.example%7Calice"}).json()
    assert shown["grant_count"] == 1 and shown["grants"][0]["loaded_by"] == subject_reference(ADMIN_CLAIMS)
    # the event carries the admin as actor
    events = client.get(f"/authority/grants/{expected_id}/events").json()["events"]
    assert [(e["event_type"], e["actor"]) for e in events] == [("GRANTED", subject_reference(ADMIN_CLAIMS))]
    # an identical replay is the same grant, not a second one
    again = _post(client, "/authority/grants", _load(), expect=409)
    assert again["result"] == "ALREADY_LOADED" and again["ruling"] == "AW-4"
    assert again["grant"]["grant_id"] == expected_id
    assert len(directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice",
                                    as_of=NOW)) == 1


def test_a_committee_and_a_membership_load_as_typed(world):
    client, _directory, _clock = world
    committee = _post(client, "/authority/grants", _load(
        principal={"principal_id": "risk-committee", "principal_kind": "COMMITTEE", "quorum": 2}),
        expect=200)
    assert committee["grant"]["principal"]["quorum"] == 2
    member = _post(client, "/authority/grants", _load(
        principal={"principal_id": "https%3A%2F%2Fidp.example%7Cbob", "principal_kind": "HUMAN"},
        member_of="risk-committee"), expect=200)
    assert member["grant"]["member_of"] == "risk-committee"
    report = client.get("/authority/committees/risk-committee", params={"role": ROLE, "scope": SCOPE}).json()
    assert report["report"]["member_count"] == 1 and report["report"]["quorum_met_at_as_of"] is False


@pytest.mark.parametrize("mutate, fragment", [
    (lambda b: b.update(delegation_ref="grant_x"), "refused keys"),
    (lambda b: b.update(tenant_id="tenant-b"), "refused keys"),
    (lambda b: b.pop("role"), "role is required"),
    (lambda b: b.update(scope="approval/ policy"), "scope must be a typed token"),
    (lambda b: b.update(issued_at="yesterday"), "issued_at is not an ISO 8601 instant"),
    (lambda b: b.update(expires_at="2026-09-05T09:00:00"), "expires_at must carry a timezone"),
    (lambda b: b["principal"].update(principal_kind="ROBOT"), "principal_kind must be one of"),
    (lambda b: b["principal"].update(quorum=-1), "quorum must be a non-negative integer"),
    (lambda b: b["principal"].update(secret="x"), "refused keys"),
    (lambda b: b.update(principal="alice"), "principal must be an object"),
])
def test_the_intake_refuses_unknown_keys_and_untyped_values_before_the_directory_is_asked(world, mutate, fragment):
    client, directory, _clock = world
    body = _load()
    mutate(body)
    answer = _post(client, "/authority/grants", body, expect=422)
    assert answer["result"] == "REFUSED_UNTYPED" and answer["ruling"] == "AW-4"
    assert fragment in answer["reason"], answer["reason"]
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice", as_of=NOW) == ()


def test_a_window_that_expires_before_it_is_issued_is_refused_as_untyped(world):
    client, _directory, _clock = world
    body = _load(issued_at=(NOW + timedelta(days=2)).isoformat(), expires_at=NOW.isoformat())
    assert _post(client, "/authority/grants", body, expect=422)["result"] == "REFUSED_UNTYPED"


def test_the_load_body_keys_are_exactly_the_typed_fields_of_a_role_grant():
    assert LOAD_BODY_KEYS == {"principal", "role", "scope", "issued_at", "expires_at",
                              "authority_reference", "member_of"}


# --------------------------------------------------------------------------- #
# AW-1, AW-4: the revoke
# --------------------------------------------------------------------------- #
def test_a_revoke_appends_its_event_under_the_proven_subject_and_a_second_revoke_is_typed(world):
    client, directory, clock = world
    grant_id = _post(client, "/authority/grants", _load(), expect=200)["grant"]["grant_id"]
    clock.advance(minutes=10)
    answer = _post(client, f"/authority/grants/{grant_id}/revoke", {"reason": "left"}, expect=200)
    assert answer["event"] == "REVOKED" and answer["operation"] == "authority_revoke_grant"
    assert answer["grant"]["revocation_reason"] == "left"
    assert answer["grant"]["revoked_at"] == clock.now.isoformat(timespec="microseconds")
    events = client.get(f"/authority/grants/{grant_id}/events").json()["events"]
    assert [(e["event_type"], e["actor"]) for e in events] == [
        ("GRANTED", subject_reference(ADMIN_CLAIMS)), ("REVOKED", subject_reference(ADMIN_CLAIMS))]
    assert directory.grants_for(tenant_id=TENANT, principal_id="https%3A%2F%2Fidp.example%7Calice",
                                as_of=clock.now) == ()
    again = _post(client, f"/authority/grants/{grant_id}/revoke", {"reason": "again"}, expect=409)
    assert again["result"] == "ALREADY_REVOKED" and again["grant"]["revocation_reason"] == "left"


def test_a_revoke_of_an_unknown_untyped_or_foreign_grant_is_typed(world):
    client, directory, _clock = world
    assert _post(client, "/authority/grants/grant_nothing/revoke", {"reason": "x"}, expect=404)["result"] == "NOT_FOUND"
    assert _post(client, "/authority/grants/not%20typed/revoke", {"reason": "x"}, expect=422)["result"] == "REFUSED_UNTYPED"
    assert _post(client, "/authority/grants/grant_x/revoke", {"why": "x"}, expect=422)["reason"].startswith(
        "the revoke body carries only")
    validity = Validity(issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30))
    mallory = PrincipalRef(principal_id="mallory", principal_kind=PrincipalKind.HUMAN)
    foreign = directory.put_grant(RoleGrant(
        grant_id=grant_id_for("tenant-b", "mallory", ROLE, SCOPE, validity), tenant_id="tenant-b",
        principal=mallory, role=ROLE, scope=SCOPE, validity=validity), as_of=NOW, loaded_by="e2e")
    answer = _post(client, f"/authority/grants/{foreign.grant_id}/revoke", {"reason": "x"}, expect=404)
    assert answer["result"] == "NOT_FOUND"
    assert directory.get_grant(foreign.grant_id).revoked_at is None
