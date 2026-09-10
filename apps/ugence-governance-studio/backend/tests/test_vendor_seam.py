"""Front-door seam 9 in the studio backend (FD-13.1 to FD-13.4): typed vendor intake.

Against a real ``SqliteVendorDeclarations`` on a temporary file. The tenant is the
store's; the id is derived; the declarer is presented and unproven; the only write is
``declare``; the record carries an opaque ``vendor_ref`` and never a way to reach the
vendor; the risk posture is uninterpreted and never ranked; no vendor approval or
onboarding status is expressible. Every refusal is typed and never a 500.

The §14.4 failure matrix of ``ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md`` is the shape
of this file, with restart covered in the package's own ``tests/test_durable.py`` and
again in the deployment profile.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from ugence_vendor_dependency import SqliteVendorDeclarations, VocabularyBinding
from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.services.studio_v2 import (
    DECLARED_BY_STATUS,
    VENDOR_DECLARATION_CONFERS,
    VENDOR_RISK_POSTURE_NOTE,
    VendorDeclarationService,
)
from ugence_governance_studio_api.settings import ApiSettings

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", ".."))

TENANT = "tenant-1"
RECORDED_BY = "governance-studio-private-hosted/0.10.0"
D = "e" * 64
PATH = "/api/v2/vendor/declarations"

#: The published vocabulary this test deployment records against. A real deployment
#: configures its own; what matters here is that one is configured at all, because a
#: seam handed none refuses to record rather than stamping a vocabulary nobody chose.
POSTURE_VOCABULARY = VocabularyBinding(
    vocabulary="vendor-dependency-assessment-state", version="1.0.0",
    specification_digest="sha256:" + "1a" * 32)


def _binding(**over):
    base = {"binding_id": "bind-1", "subject_id": "subject-1", "context_id": "ctx-1",
            "context_digest": D, "system_id": "hiring-screener", "system_version": "1.0.0",
            "configuration_id": "cfg-1", "configuration_digest": D}
    base.update(over)
    return base


def _declaration(**over):
    declared = {"binding": _binding(), "vendor_ref": "vendor://acme-llm",
                "risk_posture_label": "elevated",
                "policy_ref": "policy://vendor-standard/v3",
                "validity": {"issued_at": "2026-09-01T00:00:00+00:00",
                             "expires_at": "2027-09-01T00:00:00+00:00"},
                "declared_by": "directory://people/declarer-1"}
    declared.update(over)
    return declared


@pytest.fixture()
def declarations(tmp_path):
    store = SqliteVendorDeclarations(str(tmp_path / "vendor.sqlite3"), tenant_id=TENANT)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def client(declarations):
    studio = build_studio_context(vendor_declarations=declarations, recorded_by=RECORDED_BY,
                                  vendor_posture_vocabulary=POSTURE_VOCABULARY)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _declare(client, declared):
    return client.post(PATH, json=declared)


# --------------------------------------------------------------------------- #
# the typed gap; the write and the read
# --------------------------------------------------------------------------- #
def test_no_vendor_file_handed_is_the_typed_gap_on_both_routes():
    client = TestClient(create_v2_app(ApiSettings(environment="test"),
                                      studio=build_studio_context()))
    for response in (_declare(client, _declaration()), client.get(PATH)):
        result = _result(response)
        assert result["available"] is False and result["capability"] == "vendor_declarations"
        assert result["result"] is None


def test_declare_records_the_typed_input_and_confers_nothing(client, declarations):
    result = _result(_declare(client, _declaration(notes="first")))
    assert result["available"] is True and result["declared"] is True
    assert result["tenant_id"] == TENANT
    assert result["store_kind"] == "SqliteVendorDeclarations"
    assert result["declared_by_status"] == DECLARED_BY_STATUS == "PRESENTED_UNPROVEN"
    assert result["recorded_by"] == RECORDED_BY
    assert result["confers"] == VENDOR_DECLARATION_CONFERS
    assert result["confers"].startswith("nothing")
    assert result["risk_posture"] == VENDOR_RISK_POSTURE_NOTE
    record = result["record"]
    assert record["declaration"]["declaration_id"].startswith("vdd_")
    assert record["declaration"]["risk_posture_label"] == "elevated"
    assert record["declaration"]["policy_ref"] == "policy://vendor-standard/v3"
    assert record["binding"]["tenant_id"] == TENANT
    assert declarations.count() == 1
    stored = declarations.get_declaration(record["declaration"]["declaration_id"])
    assert stored is not None and stored.record_digest() == result["record_digest"]


def test_list_answers_the_tenant_at_the_caller_instant_or_the_request_instant(client):
    _result(_declare(client, _declaration()))
    listed = _result(client.get(PATH, params={"as_of": "2026-10-01T00:00:00+00:00"}))
    assert listed["available"] is True and listed["count"] == 1
    assert listed["as_of_source"] == "caller" and listed["tenant_id"] == TENANT
    assert listed["declared_by_status"] == "PRESENTED_UNPROVEN"
    assert listed["result"][0]["declaration"]["vendor_ref"] == "vendor://acme-llm"
    # outside the window: absent, never flagged
    lapsed = _result(client.get(PATH, params={"as_of": "2030-01-01T00:00:00+00:00"}))
    assert lapsed["count"] == 0 and lapsed["result"] == []
    now = _result(client.get(PATH))
    assert now["as_of_source"] == "request"
    assert datetime.fromisoformat(now["as_of"]).tzinfo is not None
    for bad in ("2026-10-01T00:00:00", "yesterday"):
        refused = _result(client.get(PATH, params={"as_of": bad}))
        assert refused["refused"] is True and refused["code"] == "as_of_untyped"


# --------------------------------------------------------------------------- #
# what the caller cannot choose, and what no field could carry
# --------------------------------------------------------------------------- #
def test_tenant_id_and_recorded_by_are_never_caller_supplied(client):
    for extra in ({"tenant_id": "other"}, {"declaration_id": "vdd_x"}, {"recorded_by": "me"},
                  {"approved": True}, {"onboarding_status": "complete"},
                  {"risk_score": 7}, {"tier": "critical"},
                  {"vendor_endpoint": "https://acme.example"},
                  {"contract_terms": "net-30"}):
        assert _declare(client, _declaration(**extra)).status_code == 422, extra
    assert _declare(client, _declaration(binding=_binding(tenant_id="other"))).status_code == 422
    service = client.app.state.studio.vendor
    result = service.declare(_declaration(binding=_binding(tenant_id="other")))
    assert result["refused"] is True and result["code"] == "vendor_declaration_refused"
    assert "never caller-supplied" in result["reason"]


# --------------------------------------------------------------------------- #
# the package's own refusals, surfaced typed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("over,code", [
    ({"vendor_ref": ""}, "vendor_declaration_refused"),
    ({"vendor_ref": "   "}, "vendor_declaration_refused"),
    ({"risk_posture_label": ""}, "vendor_declaration_refused"),
    ({"policy_ref": ""}, "vendor_declaration_refused"),
    ({"binding": _binding(context_digest="not-a-digest")}, "vendor_declaration_refused"),
    ({"binding": _binding(system_id="")}, "vendor_declaration_refused"),
    ({"validity": {"issued_at": "2026-09-01T00:00:00"}}, "vendor_declaration_refused"),
    ({"validity": {"issued_at": "soon"}}, "vendor_declaration_refused"),
    ({"supersedes": "vdd_" + "0" * 32}, "supersession_refused"),
])
def test_blank_malformed_and_unbound_inputs_refuse_typed(client, declarations, over, code):
    result = _result(_declare(client, _declaration(**over)))
    assert result["refused"] is True and result["code"] == code, result
    assert declarations.count() == 0


def test_duplicate_and_inadmissible_supersession_refuse_and_changed_terms_supersede(
        client, declarations):
    first = _result(_declare(client, _declaration()))
    first_id = first["declaration_id"]
    dup = _result(_declare(client, _declaration()))
    assert dup["refused"] is True and dup["code"] == "vendor_declaration_duplicate"
    # a different vendor is a new declaration, not a replacement
    elsewhere = _result(_declare(client, _declaration(vendor_ref="vendor://beta",
                                                      supersedes=first_id)))
    assert elsewhere["code"] == "supersession_refused"
    successor = _result(_declare(client, _declaration(
        policy_ref="policy://vendor-standard/v4", supersedes=first_id)))
    assert successor["declared"] is True
    assert successor["record"]["declaration"]["supersedes"] == first_id
    assert declarations.count() == 2


# --------------------------------------------------------------------------- #
# the tenant boundary, and the vendor that cannot be reached
# --------------------------------------------------------------------------- #
def test_a_read_for_another_tenant_is_a_typed_refusal_never_an_empty_answer(client,
                                                                            declarations):
    class _Foreign:
        tenant_id = "tenant-b"

        def __getattr__(self, name):
            return getattr(declarations, name)

    service = VendorDeclarationService(declarations=_Foreign(), recorded_by=RECORDED_BY)
    result = service.list(as_of="2026-10-01T00:00:00+00:00")
    assert result["refused"] is True and result["code"] == "vendor_declaration_refused"
    assert result["result"] is None


def test_the_record_carries_a_reference_and_never_a_way_to_reach_the_vendor(client):
    result = _result(_declare(client, _declaration()))
    text = json.dumps(result["record"])
    assert result["record"]["declaration"]["vendor_ref"] == "vendor://acme-llm"
    for forbidden in ("address", "endpoint", "credential", "secret", "token", "password",
                      "phone", "pricing", "invoice", "contract_terms"):
        assert forbidden not in text, forbidden


# --------------------------------------------------------------------------- #
# FD-13.4: the posture is recorded, never ordered, ranked, scored or approved
# --------------------------------------------------------------------------- #
def test_the_risk_posture_is_recorded_verbatim_and_nothing_ranks_it(client):
    result = _result(_declare(client, _declaration(
        risk_posture_label="whatever-the-declarer-called-it")))
    declared = result["record"]["declaration"]
    assert declared["risk_posture_label"] == "whatever-the-declarer-called-it"
    assert result["risk_posture"].startswith("uninterpreted")
    for forbidden in ("severity", "tier", "rank", "score", "approved", "onboard",
                      "certification"):
        assert forbidden not in json.dumps(declared), forbidden


def test_the_listed_order_is_not_a_posture_ordering(client):
    """Two postures, listed. The answer's order is the package's stable key order, and
    no field in it says which posture is worse — nothing computes that."""

    _result(_declare(client, _declaration(risk_posture_label="zebra")))
    _result(_declare(client, _declaration(risk_posture_label="alpha",
                                          policy_ref="policy://vendor-standard/v4")))
    listed = _result(client.get(PATH, params={"as_of": "2026-10-01T00:00:00+00:00"}))
    assert listed["count"] == 2
    postures = [r["declaration"]["risk_posture_label"] for r in listed["result"]]
    assert sorted(postures) == ["alpha", "zebra"]
    assert listed["risk_posture"].startswith("uninterpreted")
    for record in listed["result"]:
        assert "severity" not in record["declaration"]
        assert "rank" not in record["declaration"]


def test_the_policy_reference_is_recorded_and_never_resolved(client):
    result = _result(_declare(client, _declaration(policy_ref="policy://does-not-exist")))
    declared = result["record"]["declaration"]
    # a reference that names nothing records exactly as one that names something:
    # only Policy Authority could tell, and it is never asked (VR-4)
    assert declared["policy_ref"] == "policy://does-not-exist"
    assert "policy_resolved" not in declared and "policy_status" not in declared


# --------------------------------------------------------------------------- #
# FD-13.4: declare is the only write
# --------------------------------------------------------------------------- #
def test_declare_is_the_only_write_and_no_mutating_route_exists(client):
    for method, path in (("PUT", PATH + "/vdd_x"),
                         ("PATCH", PATH + "/vdd_x"),
                         ("DELETE", PATH + "/vdd_x"),
                         ("POST", PATH + "/vdd_x/revoke"),
                         ("POST", "/api/v2/vendor/approve"),
                         ("POST", "/api/v2/vendor/onboard"),
                         ("POST", "/api/v2/vendor/score"),
                         ("POST", "/api/v2/vendor/verify")):
        assert client.request(method, path, json={}).status_code in (404, 405), (method, path)
    assert {n for n in dir(VendorDeclarationService) if not n.startswith("_")} == {
        "CAPABILITY", "declare", "list"}


def test_the_v2_contract_carries_exactly_the_two_ruled_operations_and_the_amendment():
    from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes

    schema = json.loads(canonical_v2_openapi_bytes())
    ops = {op["operationId"] for methods in schema["paths"].values()
           for op in methods.values() if isinstance(op, dict) and "operationId" in op}
    ruled = {"v2_vendor_declare", "v2_vendor_list"}
    assert ruled <= ops
    assert not any(o.startswith("v2_vendor_") for o in ops - ruled)
    record = json.load(open(os.path.join(_APP, "contracts", "openapi_v2.amendments.json"),
                            encoding="utf-8"))
    # Found by id, not by position: a later seam appends its own amendment, and this
    # test is about seam 9's, which never moves once written.
    (mine,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A5"]
    assert set(mine["operations_added"]) == ruled
    assert mine["paths_added"] == ["/api/v2/vendor/declarations"]
    previous = record["original_sha256"]
    for amendment in record["amendments"]:
        assert amendment["previous_sha256"] == previous
        previous = amendment["sha256"]
    with open(os.path.join(_APP, "contracts", "openapi_v2.json"), "rb") as fh:
        committed = fh.read()
    assert hashlib.sha256(committed).hexdigest() == previous
    assert committed == canonical_v2_openapi_bytes()


def test_a_file_without_a_vocabulary_refuses_to_record_rather_than_stamping_one(declarations):
    """VV-E and PUB-2: an absent vocabulary reference is never defaulted.

    The store is real and writable; what is missing is the deployment's statement of
    which published taxonomy its administrators record against. Recording anyway would
    put a vocabulary nobody chose into a field whose whole purpose is provenance, so the
    seam reports the gap — the same rule this app already applies to every other
    dependency it is handed nothing for.
    """

    studio = build_studio_context(vendor_declarations=declarations, recorded_by=RECORDED_BY)
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
    result = _result(_declare(client, _declaration()))
    assert result["available"] is False and result["result"] is None
    assert "vocabulary" in result["reason"]
    # and nothing reached the file
    assert declarations.count() == 0
