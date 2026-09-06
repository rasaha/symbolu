"""Front-door seam 8 in the studio backend (FD-12.1 to FD-12.5): typed data-use intake.

Against a real ``SqliteDataUseDeclarations`` on a temporary file. The tenant is the
store's; the id is derived; the declarer is presented and unproven; the only write is
``declare``; the record carries an opaque ``data_ref`` and never the data; the
classification, purpose and residency labels stay uninterpreted; no egress restriction
is expressible. Every refusal is typed and never a 500.

The §13.4 failure matrix of ``ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md`` is the shape of
this file: rows 1 to 8 and 10 are asserted here, row 9 (restart) in the package's own
``tests/test_durable.py`` and again in the deployment profile.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from ugence_data_use_admission import SqliteDataUseDeclarations
from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.services.studio_v2 import (
    DECLARATION_CONFERS,
    DECLARED_BY_STATUS,
    EGRESS_RESTRICTIONS_NOTE,
    DeclarationService,
)
from ugence_governance_studio_api.settings import ApiSettings

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", ".."))

TENANT = "tenant-1"
RECORDED_BY = "governance-studio-private-hosted/0.9.0"
D = "b" * 64
PATH = "/api/v2/data-use/declarations"


def _binding(**over):
    base = {"binding_id": "bind-1", "subject_id": "subject-1", "context_id": "ctx-1",
            "context_digest": D, "system_id": "hiring-screener", "system_version": "1.0.0",
            "configuration_id": "cfg-1", "configuration_digest": D}
    base.update(over)
    return base


def _declaration(**over):
    declared = {"binding": _binding(), "data_ref": "dataset://applicants/2026",
                "classification_label": "candidate-personal-data",
                "purpose_label": "shortlisting",
                "validity": {"issued_at": "2026-09-01T00:00:00+00:00",
                             "expires_at": "2027-09-01T00:00:00+00:00"},
                "declared_by": "directory://people/declarer-1"}
    declared.update(over)
    return declared


@pytest.fixture()
def declarations(tmp_path):
    store = SqliteDataUseDeclarations(str(tmp_path / "declarations.sqlite3"), tenant_id=TENANT)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def client(declarations):
    studio = build_studio_context(data_use_declarations=declarations, recorded_by=RECORDED_BY)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _declare(client, declared):
    return client.post(PATH, json=declared)


# --------------------------------------------------------------------------- #
# §13.4 row 1 — the typed gap; and the write and the read
# --------------------------------------------------------------------------- #
def test_no_declarations_file_handed_is_the_typed_gap_on_both_routes():
    client = TestClient(create_v2_app(ApiSettings(environment="test"),
                                      studio=build_studio_context()))
    for response in (_declare(client, _declaration()), client.get(PATH)):
        result = _result(response)
        assert result["available"] is False and result["capability"] == "data_use_declarations"
        assert result["result"] is None


def test_declare_records_the_typed_input_and_confers_nothing(client, declarations):
    result = _result(_declare(client, _declaration(notes="first")))
    assert result["available"] is True and result["declared"] is True
    assert result["tenant_id"] == TENANT
    assert result["store_kind"] == "SqliteDataUseDeclarations"
    assert result["declared_by_status"] == DECLARED_BY_STATUS == "PRESENTED_UNPROVEN"
    assert result["declared_by"] == "directory://people/declarer-1"
    assert result["recorded_by"] == RECORDED_BY
    assert result["confers"] == DECLARATION_CONFERS and result["confers"].startswith("nothing")
    assert result["egress_restrictions"] == EGRESS_RESTRICTIONS_NOTE
    record = result["record"]
    assert record["declaration"]["declaration_id"].startswith("dud_")
    assert record["declaration"]["classification_label"] == "candidate-personal-data"
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
    assert listed["result"][0]["declaration"]["purpose_label"] == "shortlisting"
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
# §13.4 row 4 — what the caller cannot choose
# --------------------------------------------------------------------------- #
def test_tenant_declaration_id_and_recorded_by_are_never_caller_supplied(client):
    for extra in ({"tenant_id": "other"}, {"declaration_id": "dud_x"}, {"recorded_by": "me"},
                  {"payload": "the data itself"}):
        assert _declare(client, _declaration(**extra)).status_code == 422, extra
    assert _declare(client, _declaration(binding=_binding(tenant_id="other"))).status_code == 422
    service = client.app.state.studio.data_use
    result = service.declare(_declaration(binding=_binding(tenant_id="other")))
    assert result["refused"] is True and result["code"] == "declaration_refused"
    assert "never caller-supplied" in result["reason"]


# --------------------------------------------------------------------------- #
# §13.4 row 3 — the package's own refusals, surfaced typed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("over,code", [
    ({"data_ref": ""}, "declaration_refused"),
    ({"data_ref": "   "}, "declaration_refused"),
    ({"purpose_label": ""}, "declaration_refused"),
    ({"classification_label": ""}, "declaration_refused"),
    ({"binding": _binding(context_digest="not-a-digest")}, "declaration_refused"),
    ({"binding": _binding(system_id="")}, "declaration_refused"),
    ({"validity": {"issued_at": "2026-09-01T00:00:00"}}, "declaration_refused"),
    ({"validity": {"issued_at": "soon"}}, "declaration_refused"),
    ({"supersedes": "dud_" + "0" * 32}, "supersession_refused"),
])
def test_blank_malformed_and_unbound_inputs_refuse_typed(client, declarations, over, code):
    result = _result(_declare(client, _declaration(**over)))
    assert result["refused"] is True and result["code"] == code, result
    assert declarations.count() == 0


# --------------------------------------------------------------------------- #
# §13.4 row 5 — supersession is the package's rule, not the studio's
# --------------------------------------------------------------------------- #
def test_duplicate_and_inadmissible_supersession_refuse_and_changed_terms_supersede(
        client, declarations):
    first = _result(_declare(client, _declaration()))
    first_id = first["declaration_id"]
    dup = _result(_declare(client, _declaration()))
    assert dup["refused"] is True and dup["code"] == "declaration_duplicate"
    # different data is a new declaration, not a replacement
    elsewhere = _result(_declare(client, _declaration(data_ref="dataset://other",
                                                      supersedes=first_id)))
    assert elsewhere["code"] == "supersession_refused"
    successor = _result(_declare(client, _declaration(purpose_label="audit-sampling",
                                                      supersedes=first_id)))
    assert successor["declared"] is True
    assert successor["record"]["declaration"]["supersedes"] == first_id
    assert declarations.count() == 2


# --------------------------------------------------------------------------- #
# §13.4 rows 6, 7 and 10 — the tenant boundary, the absent data, the absent egress
# --------------------------------------------------------------------------- #
def test_a_read_for_another_tenant_is_a_typed_refusal_never_an_empty_answer(client,
                                                                            declarations):
    class _Foreign:
        tenant_id = "tenant-b"

        def __getattr__(self, name):
            return getattr(declarations, name)

    service = DeclarationService(declarations=_Foreign(), recorded_by=RECORDED_BY)
    result = service.list(as_of="2026-10-01T00:00:00+00:00")
    assert result["refused"] is True and result["code"] == "declaration_refused"
    assert result["result"] is None


def test_the_record_carries_a_reference_and_never_the_data(client):
    result = _result(_declare(client, _declaration()))
    text = json.dumps(result["record"])
    assert result["record"]["declaration"]["data_ref"] == "dataset://applicants/2026"
    for forbidden in ("payload", "content", "rows", "bytes", "blob", "sample"):
        assert forbidden not in text, forbidden


def test_the_labels_are_recorded_uninterpreted_and_no_egress_restriction_is_invented(client):
    result = _result(_declare(client, _declaration(
        classification_label="whatever-the-declarer-said",
        purpose_label="whatever-they-said-it-was-for",
        residency_label="somewhere")))
    declared = result["record"]["declaration"]
    assert declared["classification_label"] == "whatever-the-declarer-said"
    assert declared["purpose_label"] == "whatever-they-said-it-was-for"
    assert declared["residency_label"] == "somewhere"
    assert result["egress_restrictions"].startswith("not expressible")
    assert "restrict" not in json.dumps(declared)


# --------------------------------------------------------------------------- #
# §13.4 row 8 — FD-12.5: declare is the only write
# --------------------------------------------------------------------------- #
def test_declare_is_the_only_write_and_no_mutating_route_exists(client):
    for method, path in (("PUT", PATH + "/dud_x"),
                         ("PATCH", PATH + "/dud_x"),
                         ("DELETE", PATH + "/dud_x"),
                         ("POST", PATH + "/dud_x/revoke"),
                         ("POST", "/api/v2/data-use/admit"),
                         ("POST", "/api/v2/data-use/authorize"),
                         ("POST", "/api/v2/data-use/enforce")):
        assert client.request(method, path, json={}).status_code in (404, 405), (method, path)
    assert {n for n in dir(DeclarationService) if not n.startswith("_")} == {
        "CAPABILITY", "declare", "list"}


def test_the_v2_contract_carries_exactly_the_two_ruled_operations_and_the_amendment_record():
    from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes

    schema = json.loads(canonical_v2_openapi_bytes())
    ops = {op["operationId"] for methods in schema["paths"].values()
           for op in methods.values() if isinstance(op, dict) and "operationId" in op}
    ruled = {"v2_data_use_declare", "v2_data_use_list"}
    assert ruled <= ops
    assert not any(o.startswith("v2_data_use_") for o in ops - ruled)
    record = json.load(open(os.path.join(_APP, "contracts", "openapi_v2.amendments.json"),
                            encoding="utf-8"))
    latest = record["amendments"][-1]
    assert latest["amendment_id"] == "v2-A4"
    assert set(latest["operations_added"]) == ruled
    assert latest["paths_added"] == ["/api/v2/data-use/declarations"]
    previous = record["original_sha256"]
    for amendment in record["amendments"]:
        assert amendment["previous_sha256"] == previous
        previous = amendment["sha256"]
    with open(os.path.join(_APP, "contracts", "openapi_v2.json"), "rb") as fh:
        committed = fh.read()
    assert hashlib.sha256(committed).hexdigest() == previous
    assert committed == canonical_v2_openapi_bytes()
