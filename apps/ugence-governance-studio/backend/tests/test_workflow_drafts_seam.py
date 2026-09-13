"""Bring Your Workflow phase 3A in the studio backend (owner ruling,
ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §24): typed draft intake over workflow-drafts.

Against a real ``SqliteWorkflowDrafts`` on a temporary file. The tenant is the
store's; the id is derived; what is kept is the validated canonical document and its
digest, never the text brought; a claimed owner is presented and unproven; a
registration link is a reference plus a digest matched against the tenant's own
registry; the only write is ``save``; every refusal is typed and never a 500; and
nothing here approves, compiles, publishes, exports or executes.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest
from fastapi.testclient import TestClient

from ugence_ai_system_registry import SqliteSystemRegistry, VocabularyBinding
from ugence_workflow_drafts import SqliteWorkflowDrafts, workflow_digest
from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog
from ugence_governance_studio_api.serialization.canonical import canonical_digest
from ugence_governance_studio_api.services.studio_v2 import (
    CLAIMED_OWNER_STATUS,
    DRAFT_CONFERS,
    DRAFT_LIFECYCLE_NOTE,
    WorkflowDraftService,
)
from ugence_governance_studio_api.settings import ApiSettings

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.abspath(os.path.join(_HERE, "..", ".."))

TENANT = "tenant-1"
RECORDED_BY = "governance-studio-private-hosted/0.13.0"
PATH = "/api/v2/workflow-drafts"
D = "a" * 64
VOCABULARY = VocabularyBinding(vocabulary="eu-ai-act-system-classification", version="1.0.0",
                               specification_digest="sha256:" + "1a" * 32)


@pytest.fixture(scope="module")
def catalog():
    return ScenarioCatalog()


@pytest.fixture(scope="module")
def v1_workflow(catalog):
    return catalog.raw_workflow("procurement")


@pytest.fixture(scope="module")
def v2_workflow(catalog):
    return catalog.v2_inputs("procurement")["v2_workflow"]


@pytest.fixture()
def drafts(tmp_path):
    store = SqliteWorkflowDrafts(str(tmp_path / "drafts.sqlite3"), tenant_id=TENANT)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def registry(tmp_path):
    store = SqliteSystemRegistry(str(tmp_path / "registry.sqlite3"), tenant_id=TENANT)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def client(drafts):
    studio = build_studio_context(workflow_drafts=drafts, recorded_by=RECORDED_BY)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


@pytest.fixture()
def client_with_registry(drafts, registry):
    studio = build_studio_context(workflow_drafts=drafts, recorded_by=RECORDED_BY,
                                  system_registry=registry, registered_by=RECORDED_BY,
                                  system_classification_vocabulary=VOCABULARY)
    return TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _body(workflow, **over):
    body = {"workflow": workflow, "contract_version": "workflow_ir.v1", "title": "Procurement intake"}
    body.update(over)
    return body


def _save(client, body):
    return client.post(PATH, json=body)


# --------------------------------------------------------------------------- #
# the gap, the write, the reads
# --------------------------------------------------------------------------- #
def test_no_drafts_file_handed_is_the_typed_gap_on_every_route(v1_workflow):
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=build_studio_context()))
    for response in (_save(client, _body(v1_workflow)), client.get(PATH),
                     client.get(PATH + "/wfd_" + "0" * 32)):
        result = _result(response)
        assert result["available"] is False and result["capability"] == "workflow_drafts"
        assert result["result"] is None


def test_save_keeps_the_validated_canonical_document_and_confers_nothing(client, drafts, v1_workflow):
    digest = canonical_digest(v1_workflow)
    result = _result(_save(client, _body(v1_workflow, claimed_owner_ref="directory://people/owner-1",
                                         notes="first", source_digest=digest)))
    assert result["available"] is True and result["saved"] is True
    assert result["tenant_id"] == TENANT and result["store_kind"] == "SqliteWorkflowDrafts"
    assert result["draft_id"].startswith("wfd_")
    assert result["lifecycle"] == "DRAFT" and result["lifecycle_note"] == DRAFT_LIFECYCLE_NOTE
    assert result["claimed_owner_status"] == CLAIMED_OWNER_STATUS == "PRESENTED_UNPROVEN"
    assert result["claimed_owner_ref"] == "directory://people/owner-1"
    assert result["recorded_by"] == RECORDED_BY
    assert result["validated_by"].startswith("ugence-agent-workforce-composer/")
    assert result["confers"] == DRAFT_CONFERS and result["confers"].startswith("nothing")
    # one digest of record, three computations: the studio's canonical, the package's,
    # and the one the client sent
    assert result["workflow_digest"] == digest == workflow_digest(v1_workflow)
    assert result["integrity"] == {"checked": True, "source_digest": digest,
                                   "computed_digest": digest, "match": True}
    record = result["record"]
    assert record["draft"]["lifecycle"] == "DRAFT"
    assert record["draft"]["claimed_owner_assurance"] == "PRESENTED_UNPROVEN"
    assert record["draft"]["tenant_id"] == TENANT and record["draft"]["recorded_by"] == RECORDED_BY
    assert record["workflow"] == v1_workflow
    assert drafts.count() == 1
    kept = drafts.get_draft(result["draft_id"])
    assert kept is not None and kept.record_digest() == result["record_digest"]


def test_read_and_list_answer_the_tenants_drafts_and_their_lineage(client, v1_workflow, v2_workflow):
    first = _result(_save(client, _body(v1_workflow)))
    second = _result(_save(client, _body(v1_workflow, title="Procurement intake, revised",
                                         supersedes=first["draft_id"])))
    other = _result(_save(client, _body(v2_workflow, contract_version="workflow_ir.v2", title="Another")))
    listed = _result(client.get(PATH))
    assert listed["available"] is True and listed["count"] == 2
    assert [row["draft_id"] for row in listed["result"]] == [second["draft_id"], other["draft_id"]]
    assert all("workflow" not in row for row in listed["result"])
    assert listed["result"][0]["supersedes"] == first["draft_id"]
    assert listed["lifecycle"] == "DRAFT" and listed["claimed_owner_status"] == "PRESENTED_UNPROVEN"
    everything = _result(client.get(PATH, params={"include_superseded": "true"}))
    assert everything["count"] == 3
    assert [row["superseded_by"] for row in everything["result"]] == [second["draft_id"], "", ""]
    read = _result(client.get(f"{PATH}/{first['draft_id']}"))
    assert read["found"] is True and read["superseded_by"] == second["draft_id"]
    assert read["lineage"] == [first["draft_id"]]
    assert read["record"]["workflow"] == v1_workflow
    head = _result(client.get(f"{PATH}/{second['draft_id']}"))
    assert head["lineage"] == [first["draft_id"], second["draft_id"]] and head["superseded_by"] == ""
    missing = _result(client.get(PATH + "/wfd_" + "0" * 32))
    assert missing["found"] is False and missing["result"] is None


def test_the_document_kept_is_canonical_not_the_text_brought(client, drafts, v1_workflow):
    reordered = dict(reversed(list(v1_workflow.items())))
    result = _result(_save(client, _body(reordered)))
    kept = drafts.get_draft(result["draft_id"])
    assert kept is not None
    assert kept.workflow_text == json.dumps(v1_workflow, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert result["workflow_digest"] == canonical_digest(v1_workflow)


# --------------------------------------------------------------------------- #
# what the caller cannot choose, and what is refused typed
# --------------------------------------------------------------------------- #
def test_tenant_draft_id_lifecycle_and_recorder_are_never_caller_supplied(client, v1_workflow):
    for extra in ({"tenant_id": "other"}, {"draft_id": "wfd_x"}, {"recorded_by": "me"},
                  {"lifecycle": "APPROVED"}, {"claimed_owner_assurance": "IDP_AUTHENTICATED"},
                  {"approved": True}, {"status": "COMPILED"}, {"owner_id": "u1"}):
        response = _save(client, _body(v1_workflow, **extra))
        assert response.status_code == 422, (extra, response.text)


def test_an_invalid_or_mismatched_document_is_a_typed_refusal(client, drafts, v1_workflow, v2_workflow):
    invalid = _result(_save(client, _body({"ir_version": "workflow_ir.v2", "nodes": [], "edges": []},
                                          contract_version="workflow_ir.v2")))
    assert invalid["refused"] is True and invalid["code"] == "draft_refused"
    assert "does not validate" in invalid["reason"] and isinstance(invalid["diagnostics"], list)
    unknown = _result(_save(client, _body(v1_workflow, contract_version="workflow_ir.v9")))
    assert unknown["code"] == "draft_refused" and "never guessed" in unknown["reason"]
    mismatched = _result(_save(client, _body(v2_workflow, contract_version="workflow_ir.v1")))
    assert mismatched["code"] == "draft_refused" and "declares" in mismatched["reason"]
    assert _save(client, _body(v1_workflow, title="")).status_code == 422
    assert _save(client, _body(v1_workflow, title="x" * 201)).status_code == 422
    assert drafts.count() == 0


def test_the_bw2_limits_apply_before_anything_is_validated_or_kept(client, drafts):
    too_many = {"ir_version": "workflow_ir.v2", "nodes": [{"node_id": f"n{i}"} for i in range(201)], "edges": []}
    response = _save(client, _body(too_many, contract_version="workflow_ir.v2"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "workflow_too_complex"
    assert drafts.count() == 0


def test_duplicates_and_inadmissible_supersessions_refuse_typed(client, drafts, v1_workflow):
    first = _result(_save(client, _body(v1_workflow)))
    dup = _result(_save(client, _body(v1_workflow)))
    assert dup["refused"] is True and dup["code"] == "draft_duplicate"
    unchanged = _result(_save(client, _body(v1_workflow, supersedes=first["draft_id"])))
    assert unchanged["code"] == "supersession_refused" and "changes nothing" in unchanged["reason"]
    unknown = _result(_save(client, _body(v1_workflow, title="x", supersedes="wfd_" + "0" * 32)))
    assert unknown["code"] == "supersession_refused" and "not recorded" in unknown["reason"]
    second = _result(_save(client, _body(v1_workflow, title="Second", supersedes=first["draft_id"])))
    assert second["saved"] is True
    third = _result(_save(client, _body(v1_workflow, title="Third", supersedes=first["draft_id"])))
    assert third["code"] == "supersession_refused" and "already superseded" in third["reason"]
    assert drafts.count() == 2


# --------------------------------------------------------------------------- #
# the registration link: a reference plus a digest, matched against the tenant's registry
# --------------------------------------------------------------------------- #
def _registration_body():
    return {"binding": {"binding_id": "bind-1", "subject_id": "subject-1", "context_id": "ctx-1",
                        "context_digest": D, "system_id": "procurement-agent", "system_version": "1.0.0",
                        "configuration_id": "cfg-1", "configuration_digest": D},
            "owner_ref": "directory://people/owner-1", "classification_label": "limited-risk",
            "validity": {"issued_at": "2026-09-01T00:00:00+00:00", "expires_at": "2027-09-01T00:00:00+00:00"}}


def test_a_link_needs_a_matching_registration_in_this_tenants_registry(client_with_registry, drafts, v1_workflow):
    client = client_with_registry
    registered = _result(client.post("/api/v2/registry/registrations", json=_registration_body()))
    ref, digest = registered["registration_id"], registered["record_digest"]
    linked = _result(_save(client, _body(v1_workflow, registration_ref=ref, registration_digest=digest)))
    assert linked["saved"] is True
    assert linked["record"]["draft"]["registration_ref"] == ref
    assert linked["record"]["draft"]["registration_digest"] == digest
    alone = _result(_save(client, _body(v1_workflow, title="alone", registration_ref=ref)))
    assert alone["code"] == "registration_link_refused" and "travel together" in alone["reason"]
    unknown = _result(_save(client, _body(v1_workflow, title="unknown", registration_ref="reg_" + "0" * 32,
                                          registration_digest=digest)))
    assert unknown["code"] == "registration_link_refused" and "names no registration" in unknown["reason"]
    wrong = _result(_save(client, _body(v1_workflow, title="wrong", registration_ref=ref,
                                        registration_digest="f" * 64)))
    assert wrong["code"] == "registration_link_refused" and "not the digest" in wrong["reason"]
    assert drafts.count() == 1


def test_a_link_without_a_registry_is_refused_not_guessed(client, drafts, v1_workflow):
    result = _result(_save(client, _body(v1_workflow, registration_ref="reg_" + "0" * 32,
                                         registration_digest=D)))
    assert result["code"] == "registration_link_refused" and "no system registry" in result["reason"]
    assert drafts.count() == 0


# --------------------------------------------------------------------------- #
# save is the only write; nothing approves, compiles, publishes or exports
# --------------------------------------------------------------------------- #
def test_save_is_the_only_write_and_no_advancing_route_exists(client):
    for method, path in (("PUT", PATH + "/wfd_x"), ("PATCH", PATH + "/wfd_x"), ("DELETE", PATH + "/wfd_x"),
                         ("POST", PATH + "/wfd_x/approve"), ("POST", PATH + "/wfd_x/compile"),
                         ("POST", PATH + "/wfd_x/publish"), ("POST", PATH + "/wfd_x/export"),
                         ("POST", PATH + "/wfd_x/submit"), ("POST", PATH + "/wfd_x/supersede")):
        assert client.request(method, path, json={}).status_code in (404, 405), (method, path)
    service_public = {n for n in dir(WorkflowDraftService) if not n.startswith("_")}
    assert service_public == {"CAPABILITY", "save", "read", "list"}


def test_the_v2_contract_carries_exactly_the_three_ruled_operations_and_the_amendment_record():
    from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes

    schema = json.loads(canonical_v2_openapi_bytes())
    ops = {op["operationId"] for methods in schema["paths"].values()
           for op in methods.values() if isinstance(op, dict) and "operationId" in op}
    mine = {"v2_workflow_drafts_save", "v2_workflow_drafts_list", "v2_workflow_drafts_read"}
    assert mine <= ops
    assert not any(o.startswith("v2_workflow_drafts_") for o in ops - mine)
    record = json.load(open(os.path.join(_APP, "contracts", "openapi_v2.amendments.json"), encoding="utf-8"))
    (amendment,) = [a for a in record["amendments"] if a["amendment_id"] == "v2-A8"]
    assert set(amendment["operations_added"]) == mine
    previous = record["original_sha256"]
    for entry in record["amendments"]:
        assert entry["previous_sha256"] == previous
        previous = entry["sha256"]
    with open(os.path.join(_APP, "contracts", "openapi_v2.json"), "rb") as fh:
        committed = fh.read()
    assert hashlib.sha256(committed).hexdigest() == previous
    assert committed == canonical_v2_openapi_bytes()


def test_the_v1_workflow_operations_are_unchanged_by_the_seam(client, v1_workflow):
    """The frozen v1 surface stays byte-identical: validate still answers, and this
    seam added nothing to it."""
    from ugence_governance_studio_api.openapi import canonical_openapi_bytes

    with open(os.path.join(_APP, "contracts", "openapi.json"), "rb") as fh:
        assert fh.read() == canonical_openapi_bytes()
    assert client.post("/api/v1/workflows/validate", json={"workflow": v1_workflow}).status_code == 404
