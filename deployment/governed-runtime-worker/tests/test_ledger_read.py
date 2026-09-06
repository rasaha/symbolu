"""Front-door seam 7 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md §12, ruling FD-11) at the
worker's edge, without PostgreSQL: the seventh route over the service shape the worker
composes, reading the same file-backed control-plane audit ledger the linkage appender
writes. Rows of §12.4 proven here: 3 (unknown id is a typed not-found), 4 (a chain that
does not verify is a typed refusal with the entries withheld, never a 500), 5 (another
schema version refused), 6 (an in-memory ledger refused before a read), 7 (the worker's
own tenant only), 8 (no write route), 9 (no credential or proof crosses on the read).
"""

from __future__ import annotations

import sqlite3

import pytest

from ugence_control_plane_root import AuditLedger, LedgerEntry
from ugence_governance_contracts.api import AuditReference
from ugence_governed_review_service import ROUTES, build_app

from conftest import NOW, TENANT, Clock


def _service(tmp_path, audit):
    from ugence_approval_workflow import StaticApproverEligibility
    from ugence_authority_directory import SqliteAuthorityDirectory
    from ugence_governed_review import build_review_ledger
    from ugence_governed_review_service import ReviewService, StaticRunReader, TenantMode

    from test_start_relay import _AdapterDouble, _starter

    adapter = _AdapterDouble()
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"), production_mode=False)
    ledger = build_review_ledger(str(tmp_path / "approvals.sqlite3"), directory, production_mode=False)
    service = ReviewService(
        ledger=ledger, adapter=adapter, reader=StaticRunReader(), tenant_id=TENANT,
        clock=Clock().datetime, eligibility=StaticApproverEligibility(()),
        tenant_mode=TenantMode.SINGLE_TENANT, production=False, starter=_starter(adapter),
        ledger_reader=audit,
    )
    return service, (ledger, directory)


def _append(audit, tenant, correlation, n):
    audit.append(LedgerEntry(tenant_id=tenant, kind="governed_review.linkage.v2", recorded_at=NOW,
                             recorded_by="governed-runtime-worker", payload={"n": n},
                             correlation_id=correlation), reference_factory=AuditReference)


@pytest.fixture()
def world(tmp_path):
    from fastapi.testclient import TestClient

    path = str(tmp_path / "audit-ledger.sqlite3")
    audit = AuditLedger(path)
    _append(audit, TENANT, "c-1", 1)
    _append(audit, "tenant-b", "c-1", 2)
    _append(audit, TENANT, "c-1", 3)
    service, closers = _service(tmp_path, audit)
    with TestClient(build_app(service)) as client:
        yield client, audit, path
    for c in closers:
        c.close()
    audit.close()


def test_rows_3_7_8_9_the_route_reads_the_workers_own_tenant_raw_and_writes_nothing(world):
    client, audit, _path = world
    assert ROUTES[6][1] == "/review/audit/{correlation_id}"
    r = client.get("/review/audit/c-1", headers={"X-Ugence-Approver-Proof": "never-read",
                                                  "Authorization": "Basic never-read"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"] == "READ" and body["chain_verified"] is True and body["tenant_id"] == TENANT
    assert [e["payload"]["n"] for e in body["entries"]] == [1, 3], "own tenant, chain order"
    assert body["entries"][0]["prev_digest"] != "" and len(body["entries"][1]["record_digest"]) == 64
    assert "never-read" not in r.text
    assert client.get("/review/audit/c-unknown").status_code == 404
    assert client.get("/review/audit/bad%20id").status_code == 422
    assert client.post("/review/audit/c-1", json={}).status_code == 405
    assert client.delete("/review/audit/c-1").status_code == 405
    assert client.get("/review/audit").status_code in (404, 405), "no list-all route"
    assert audit.entry_count() == 3


def test_row_4_a_chain_that_does_not_verify_is_a_typed_refusal_with_entries_withheld(world):
    client, _audit, path = world
    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER ledger_no_update")
    raw.execute("UPDATE ledger_entries SET content_digest=? WHERE tenant_seq=0 AND tenant_id=?",
                ("0" * 64, TENANT))
    raw.commit()
    raw.close()
    r = client.get("/review/audit/c-1")
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["result"] == "REFUSED_INTEGRITY" and body["entries"] == [] and body["chain_verified"] is False
    assert "withheld" in body["reason"]


def test_row_5_another_schema_version_is_refused(world):
    client, _audit, path = world
    raw = sqlite3.connect(path)
    raw.execute("UPDATE meta SET value='someone.else/9.9' WHERE key='schema_version'")
    raw.commit()
    raw.close()
    r = client.get("/review/audit/c-1")
    assert r.status_code == 409 and r.json()["result"] == "REFUSED_SCHEMA"


def test_row_6_an_in_memory_ledger_is_refused_before_any_row_is_read(tmp_path):
    from fastapi.testclient import TestClient
    from ugence_control_plane_root import ContractViolation

    audit = AuditLedger(":memory:")
    _append(audit, TENANT, "c-1", 1)
    service, closers = _service(tmp_path, audit)
    with TestClient(build_app(service), raise_server_exceptions=False) as client:
        r = client.get("/review/audit/c-1")
        assert r.status_code == 500, "the ledger's own refusal is not swallowed into a typed answer"
    with pytest.raises(ContractViolation, match="in-memory"):
        audit.read_entries(tenant_id=TENANT, correlation_id="c-1")
    for c in closers:
        c.close()
