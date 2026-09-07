"""The authority plane's reads at the worker's edge, without PostgreSQL
(ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 2, ruling AP-5 READS_FIRST).

Proven here: the four reads answer from the directory for this worker's own tenant at
the injected clock; a foreign tenant's grants are not expressible and its grant ids read
as unknown; an untyped identifier is refused before the directory is asked; a missing
committee or grant is a typed not-found, never an empty success; every answer says a
read is not authenticated and carries the decision proof the deployment can give and
the adapter's issuer-validation label; no proof or credential header is read or
echoed; and no write is reachable on any read path.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ugence_authority_directory import (
    GrantEventType,
    PrincipalKind,
    PrincipalRef,
    RoleGrant,
    SqliteAuthorityDirectory,
    grant_id_for,
)
from ugence_governance_contracts.api import Validity

from governed_runtime_worker.authority_reads import (
    IDP_AUTHENTICATED,
    PRESENTED_UNPROVEN,
    READ_OPERATIONS,
    build_authority_reads,
)
from conftest import NOW, TENANT, Clock

ROLE = "risk-approver"
SCOPE = "approval/policy_pack"
PROOF = "opaque.proof.value-that-must-never-be-read-on-a-read"


def _human(pid: str) -> PrincipalRef:
    return PrincipalRef(principal_id=pid, principal_kind=PrincipalKind.HUMAN,
                        display_ref=f"directory://people/{pid}")


def _grant(principal: PrincipalRef, *, tenant: str = TENANT, role: str = ROLE, scope: str = SCOPE,
           member_of: str = "") -> RoleGrant:
    validity = Validity(issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30))
    return RoleGrant(grant_id=grant_id_for(tenant, principal.principal_id, role, scope, validity),
                     tenant_id=tenant, principal=principal, role=role, scope=scope, validity=validity,
                     authority_reference=f"directory://roles/{role}", member_of=member_of)


@pytest.fixture()
def world(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    alice = directory.put_grant(_grant(_human("https%3A%2F%2Fidp.example%7Calice")),
                                as_of=NOW - timedelta(days=1), loaded_by="e2e")
    bob = directory.put_grant(_grant(_human("bob"), member_of="risk-committee"),
                              as_of=NOW - timedelta(days=1), loaded_by="e2e")
    carol = directory.put_grant(_grant(_human("carol"), member_of="risk-committee"),
                                as_of=NOW - timedelta(days=1), loaded_by="e2e")
    committee = PrincipalRef(principal_id="risk-committee", principal_kind=PrincipalKind.COMMITTEE, quorum=2)
    directory.put_grant(_grant(committee), as_of=NOW - timedelta(days=1), loaded_by="e2e")
    foreign = directory.put_grant(_grant(_human("mallory"), tenant="tenant-b"),
                                  as_of=NOW - timedelta(days=1), loaded_by="e2e")
    directory.revoke_grant(carol.grant_id, as_of=NOW - timedelta(hours=1), reason="left", actor="e2e")
    app = FastAPI()
    app.include_router(build_authority_reads(directory, tenant_id=TENANT, clock=Clock().datetime,
                                             identity_port_configured=False))
    with TestClient(app) as client:
        yield client, {"alice": alice, "bob": bob, "carol": carol, "foreign": foreign}


def _ok(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"] == "READ" and body["plane"] == "authority" and body["ruling"] == "AP-5"
    assert body["tenant_id"] == TENANT and body["as_of"] == NOW.isoformat()
    assert body["read_authenticated"] is False
    assert body["decision_identity_proof"] == PRESENTED_UNPROVEN
    assert body["issuer_validation"] == "IN_PROCESS_ISSUER_ONLY"
    assert "administrator loaded" in body["provenance"]
    return body


def test_the_router_serves_exactly_the_four_contract_reads(world):
    client, _ = world
    spec = client.get("/openapi.json").json()
    seen = {(m.upper(), p, op["operationId"]) for p, ops in spec["paths"].items() for m, op in ops.items()}
    assert seen == {("GET", op.path, op.operation_id) for op in READ_OPERATIONS}


def test_grants_for_a_principal_are_this_tenants_and_active_at_the_clock(world):
    client, g = world
    body = _ok(client.get("/authority/grants", params={"principal_id": "https%3A%2F%2Fidp.example%7Calice"}))
    assert body["grant_count"] == 1 and body["grants"][0]["grant_id"] == g["alice"].grant_id
    assert body["grants"][0]["loaded_by"] == "e2e"
    # carol's grant was revoked an hour ago: not active at the clock
    assert _ok(client.get("/authority/grants", params={"principal_id": "carol"}))["grant_count"] == 0
    # a foreign tenant's principal reads as holding nothing here
    assert _ok(client.get("/authority/grants", params={"principal_id": "mallory"}))["grant_count"] == 0


def test_holders_of_a_role_in_a_scope(world):
    client, _ = world
    body = _ok(client.get("/authority/holders", params={"role": ROLE, "scope": SCOPE}))
    ids = sorted(h["principal"]["principal_id"] for h in body["holders"])
    assert ids == sorted(["https%3A%2F%2Fidp.example%7Calice", "bob", "risk-committee"])
    assert body["holder_count"] == 3
    assert _ok(client.get("/authority/holders", params={"role": "nobody-has-this", "scope": SCOPE}))["holder_count"] == 0


def test_a_committee_report_counts_members_against_its_quorum(world):
    client, _ = world
    body = _ok(client.get("/authority/committees/risk-committee", params={"role": ROLE, "scope": SCOPE}))
    report = body["report"]
    assert report["committee"]["principal_kind"] == "COMMITTEE" and report["quorum"] == 2
    assert [m["principal"]["principal_id"] for m in report["members"]] == ["bob"], "carol's grant is revoked"
    assert report["member_count"] == 1 and report["quorum_met_at_as_of"] is False


def test_a_missing_committee_is_a_typed_not_found_never_an_empty_report(world):
    client, _ = world
    r = client.get("/authority/committees/no-such-committee", params={"role": ROLE, "scope": SCOPE})
    assert r.status_code == 404
    assert r.json()["result"] == "NOT_FOUND" and "no committee" in r.json()["reason"]


def test_a_grants_event_history_is_append_only_and_shows_the_revocation(world):
    client, g = world
    body = _ok(client.get(f"/authority/grants/{g['carol'].grant_id}/events"))
    assert [e["event_type"] for e in body["events"]] == [GrantEventType.GRANTED.value, GrantEventType.REVOKED.value]
    assert body["events"][1]["actor"] == "e2e" and body["event_count"] == 2
    assert body["grant"]["revocation_reason"] == "left"


def test_a_foreign_tenants_grant_id_reads_as_unknown_never_as_someone_elses(world):
    client, g = world
    r = client.get(f"/authority/grants/{g['foreign'].grant_id}/events")
    assert r.status_code == 404 and r.json()["result"] == "NOT_FOUND"
    assert "mallory" not in r.text and "tenant-b" not in r.text
    assert client.get("/authority/grants/grant_no-such/events").status_code == 404


def test_an_untyped_identifier_is_refused_before_the_directory_is_asked(world):
    client, _ = world
    for path, params in (
        ("/authority/grants", {"principal_id": "has space"}),
        ("/authority/holders", {"role": " padded", "scope": SCOPE}),
        ("/authority/holders", {"role": ROLE, "scope": "x" * 300}),
        ("/authority/committees/risk-committee", {"role": ROLE, "scope": "tab\there"}),
    ):
        r = client.get(path, params=params)
        assert r.status_code == 422, (path, params, r.text)
        assert r.json()["result"] == "REFUSED_UNTYPED"
    assert client.get("/authority/grants").status_code == 422, "principal_id is required"


def test_no_proof_or_credential_is_read_or_echoed_and_no_write_is_reachable(world):
    client, g = world
    headers = {"X-Ugence-Approver-Proof": PROOF, "Authorization": "Basic never-read"}
    r = client.get("/authority/grants", params={"principal_id": "bob"}, headers=headers)
    assert r.status_code == 200 and PROOF not in r.text and "never-read" not in r.text
    for path in ("/authority/grants", "/authority/holders",
                 "/authority/committees/risk-committee", f"/authority/grants/{g['bob'].grant_id}/events"):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert client.request(method, path, json={}).status_code == 405, (method, path)
    # the write paths of the contract do not exist on this app at all
    assert client.post("/authority/grants/x/revoke", json={}).status_code == 404
    assert client.post("/authority/issuances", json={}).status_code == 404


def test_the_decision_proof_label_follows_whether_an_identity_port_is_composed(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    app = FastAPI()
    app.include_router(build_authority_reads(directory, tenant_id=TENANT, clock=Clock().datetime,
                                             identity_port_configured=True))
    with TestClient(app) as client:
        body = client.get("/authority/grants", params={"principal_id": "bob"}).json()
    assert body["decision_identity_proof"] == IDP_AUTHENTICATED
    assert body["read_authenticated"] is False, "a composed port authenticates decisions, not reads"
    assert body["issuer_validation"] == "IN_PROCESS_ISSUER_ONLY"


def test_a_foreign_or_untyped_tenant_cannot_be_composed(tmp_path):
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    with pytest.raises(ValueError):
        build_authority_reads(directory, tenant_id="has space", clock=Clock().datetime,
                              identity_port_configured=False)
