"""Front-door seam 5 in the studio backend (FD-9.1 to FD-9.5): typed registration intake.

Against a real ``SqliteSystemRegistry`` on a temporary file. The tenant is the
registry's; the id is derived; the registrant is presented and unproven; the only
write is ``register``; every refusal is typed and never a 500.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ugence_ai_system_registry import SqliteSystemRegistry
from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.services.studio_v2 import OWNER_REF_STATUS, RegistryService
from ugence_governance_studio_api.settings import ApiSettings

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", ".."))

TENANT = "tenant-1"
REGISTERED_BY = "governance-studio-private-hosted/0.6.0"
D = "a" * 64


def _binding(**over):
    base = {"binding_id": "bind-1", "subject_id": "subject-1", "context_id": "ctx-1",
            "context_digest": D, "system_id": "hiring-screener", "system_version": "1.0.0",
            "configuration_id": "cfg-1", "configuration_digest": D}
    base.update(over)
    return base


def _body(**over):
    body = {"binding": _binding(), "owner_ref": "directory://people/owner-1",
            "classification_label": "high-risk",
            "validity": {"issued_at": "2026-09-01T00:00:00+00:00", "expires_at": "2027-09-01T00:00:00+00:00"}}
    body.update(over)
    return body


@pytest.fixture()
def registry(tmp_path):
    store = SqliteSystemRegistry(str(tmp_path / "registry.sqlite3"), tenant_id=TENANT)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def client(registry):
    studio = build_studio_context(system_registry=registry, registered_by=REGISTERED_BY)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _register(client, body):
    return client.post("/api/v2/registry/registrations", json=body)


# --------------------------------------------------------------------------- #
# the gap, the write, the read
# --------------------------------------------------------------------------- #
def test_no_registry_handed_is_the_typed_gap_on_both_routes():
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=build_studio_context()))
    for response in (_register(client, _body()), client.get("/api/v2/registry/registrations")):
        result = _result(response)
        assert result["available"] is False and result["capability"] == "system_registry"
        assert result["result"] is None


def test_register_records_the_typed_input_and_confers_nothing(client, registry):
    result = _result(_register(client, _body(notes="first")))
    assert result["available"] is True and result["registered"] is True
    assert result["tenant_id"] == TENANT and result["registry_kind"] == "SqliteSystemRegistry"
    assert result["owner_ref_status"] == OWNER_REF_STATUS == "PRESENTED_UNPROVEN"
    assert result["registered_by"] == REGISTERED_BY
    assert result["confers"].startswith("nothing")
    record = result["record"]
    assert record["registration"]["registration_id"].startswith("reg_")
    assert record["registration"]["classification_label"] == "high-risk"
    assert record["registration"]["registered_by"] == REGISTERED_BY
    assert record["binding"]["tenant_id"] == TENANT
    assert registry.count() == 1
    stored = registry.get_registration(record["registration"]["registration_id"])
    assert stored is not None and stored.record_digest() == result["record_digest"]


def test_list_answers_the_tenant_at_the_caller_instant_or_the_request_instant(client):
    _result(_register(client, _body()))
    listed = _result(client.get("/api/v2/registry/registrations",
                                params={"as_of": "2026-10-01T00:00:00+00:00"}))
    assert listed["available"] is True and listed["count"] == 1 and listed["as_of_source"] == "caller"
    assert listed["tenant_id"] == TENANT and listed["owner_ref_status"] == "PRESENTED_UNPROVEN"
    assert listed["result"][0]["registration"]["classification_label"] == "high-risk"
    # outside the window: absent, never flagged
    lapsed = _result(client.get("/api/v2/registry/registrations",
                                params={"as_of": "2030-01-01T00:00:00+00:00"}))
    assert lapsed["count"] == 0 and lapsed["result"] == []
    now = _result(client.get("/api/v2/registry/registrations"))
    assert now["as_of_source"] == "request"
    assert datetime.fromisoformat(now["as_of"]).tzinfo is not None
    for bad in ("2026-10-01T00:00:00", "yesterday"):
        r = _result(client.get("/api/v2/registry/registrations", params={"as_of": bad}))
        assert r["refused"] is True and r["code"] == "as_of_untyped"


# --------------------------------------------------------------------------- #
# what the caller cannot choose
# --------------------------------------------------------------------------- #
def test_tenant_registration_id_and_registered_by_are_never_caller_supplied(client):
    for extra in ({"tenant_id": "other"}, {"registration_id": "reg_x"}, {"registered_by": "me"}):
        response = _register(client, _body(**extra))
        assert response.status_code == 422, response.text  # StrictModel: unknown field
    # a tenant inside the binding is the contract's own 422 (unknown field) over HTTP,
    # and the service refuses it typed for any caller that bypasses the contract
    assert _register(client, _body(binding=_binding(tenant_id="other"))).status_code == 422
    service = client.app.state.studio.registry
    result = service.register(_body(binding=_binding(tenant_id="other")))
    assert result["refused"] is True and result["code"] == "registration_refused"
    assert "never caller-supplied" in result["reason"]


# --------------------------------------------------------------------------- #
# the package's own refusals, surfaced typed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("over,code", [
    ({"owner_ref": ""}, "registration_refused"),
    ({"owner_ref": "   "}, "registration_refused"),
    ({"classification_label": ""}, "registration_refused"),
    ({"binding": _binding(context_digest="not-a-digest")}, "registration_refused"),
    ({"binding": _binding(system_id="")}, "registration_refused"),
    ({"validity": {"issued_at": "2026-09-01T00:00:00"}}, "registration_refused"),
    ({"validity": {"issued_at": "soon"}}, "registration_refused"),
    ({"supersedes": "reg_" + "0" * 32}, "supersession_refused"),
])
def test_blank_malformed_and_unbound_inputs_refuse_typed(client, registry, over, code):
    result = _result(_register(client, _body(**over)))
    assert result["refused"] is True and result["code"] == code, result
    assert registry.count() == 0


def test_duplicate_and_inadmissible_supersession_refuse_and_a_new_version_supersedes(client, registry):
    first = _result(_register(client, _body()))
    first_id = first["registration_id"]
    dup = _result(_register(client, _body()))
    assert dup["refused"] is True and dup["code"] == "registration_duplicate"
    same_identity = _result(_register(client, _body(owner_ref="directory://people/owner-2",
                                                    supersedes=first_id)))
    assert same_identity["code"] == "supersession_refused"
    successor = _result(_register(client, _body(binding=_binding(system_version="2.0.0",
                                                                 binding_id="bind-2"),
                                                supersedes=first_id)))
    assert successor["registered"] is True
    assert successor["record"]["registration"]["supersedes"] == first_id
    assert registry.count() == 2


def test_the_classification_label_is_recorded_uninterpreted(client):
    result = _result(_register(client, _body(classification_label="whatever-the-admin-said")))
    assert result["record"]["registration"]["classification_label"] == "whatever-the-admin-said"
    assert "classification" not in {k for k in result if k.endswith("_status")}


# --------------------------------------------------------------------------- #
# FD-9.5: register is the only write
# --------------------------------------------------------------------------- #
def test_register_is_the_only_write_and_no_mutating_route_exists(client):
    for method, path in (("PUT", "/api/v2/registry/registrations/reg_x"),
                         ("PATCH", "/api/v2/registry/registrations/reg_x"),
                         ("DELETE", "/api/v2/registry/registrations/reg_x"),
                         ("POST", "/api/v2/registry/registrations/reg_x/revoke"),
                         ("POST", "/api/v2/registry/admit"),
                         ("POST", "/api/v2/registry/approve")):
        assert client.request(method, path, json={}).status_code in (404, 405), (method, path)
    service_public = {n for n in dir(RegistryService) if not n.startswith("_")}
    assert service_public == {"CAPABILITY", "register", "list"}


def test_the_v2_contract_carries_exactly_the_two_ruled_operations_and_the_amendment_record():
    from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes

    schema = json.loads(canonical_v2_openapi_bytes())
    ops = {op["operationId"] for methods in schema["paths"].values()
           for op in methods.values() if isinstance(op, dict) and "operationId" in op}
    assert {"v2_registry_register", "v2_registry_list"} <= ops
    assert not any(o.startswith("v2_registry_") for o in ops - {"v2_registry_register", "v2_registry_list"})
    # FD-9.4: the amendment record chains from the original freeze to the committed bytes
    record = json.load(open(os.path.join(_APP, "contracts", "openapi_v2.amendments.json"), encoding="utf-8"))
    assert record["contract"] == "governance_studio.api.v2"
    assert record["original_sha256"] == "dd63180dc91ba7842dc1dc2b6efb3dbc155ea3bd47200f40de7bac85d373f39a"
    previous = record["original_sha256"]
    for amendment in record["amendments"]:
        assert amendment["previous_sha256"] == previous
        assert set(amendment["operations_added"]) <= ops
        previous = amendment["sha256"]
    with open(os.path.join(_APP, "contracts", "openapi_v2.json"), "rb") as fh:
        committed = fh.read()
    assert hashlib.sha256(committed).hexdigest() == previous
    assert committed == canonical_v2_openapi_bytes()
