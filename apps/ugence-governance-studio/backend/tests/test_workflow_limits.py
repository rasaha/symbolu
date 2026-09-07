"""Structural limits on caller-supplied workflow documents (BW-2, BW-3; ADR §22).

The three workflow routes refuse, with a typed 422 ``workflow_too_complex``, any
document over the owner's figures, before any adapter runs; a document at the limit
is handled as before. The guard adds nothing to the frozen contract: the OpenAPI
freeze test elsewhere in this suite keeps proving that.
"""
from __future__ import annotations

import json

import pytest

from ugence_governance_studio_api import workflow_limits as wl
from ugence_governance_studio_api.scenarios.catalog import ScenarioCatalog


@pytest.fixture()
def cat() -> ScenarioCatalog:
    return ScenarioCatalog()


def _error(response):
    assert response.status_code == 422, response.text
    body = response.json()["error"]
    assert body["code"] == "workflow_too_complex"
    return body


def _v1_with_nodes(cat, count):
    wf = cat.raw_workflow("procurement")
    wf = json.loads(json.dumps(wf))
    node = wf["workflow_ir"]["nodes"][0]
    wf["workflow_ir"]["nodes"] = [dict(node, node_id=f"n{i}") for i in range(count)]
    return wf


def _nested(depth):
    doc = {"ir_version": "workflow_ir.v2"}
    cursor = doc
    for _ in range(depth - 1):
        cursor["child"] = {}
        cursor = cursor["child"]
    return doc


def test_the_owner_figures_are_the_ones_recorded():
    assert wl.LIMITS == {"document_bytes": 1024 * 1024, "depth": 32, "nodes": 200,
                         "edges": 400, "elements": 50_000}


def test_measure_reports_depth_elements_and_the_longest_node_and_edge_lists(cat):
    wf = cat.raw_workflow("procurement")
    m = wl.measure_document(wf)
    assert m["nodes"] == len(wf["workflow_ir"]["nodes"])
    assert m["edges"] == len(wf["workflow_ir"]["edges"])
    assert m["depth"] >= 3
    assert m["elements"] > m["nodes"] + m["edges"]
    assert wl.measure_document(_nested(5))["depth"] == 5


def test_validate_refuses_too_many_nodes_and_says_which_measure(client, cat):
    body = _error(client.post("/api/v1/workflows/validate",
                              json={"contract_version": "workflow_ir.v1",
                                    "workflow": _v1_with_nodes(cat, wl.MAX_NODES + 1)}))
    details = body.get("safe_details") or body.get("details") or {}
    assert details.get("measure") == "nodes"
    assert details.get("observed") == wl.MAX_NODES + 1
    assert details.get("limit") == wl.MAX_NODES


def test_validate_accepts_a_document_at_the_node_limit(client, cat):
    response = client.post("/api/v1/workflows/validate",
                           json={"contract_version": "workflow_ir.v1",
                                 "workflow": _v1_with_nodes(cat, wl.MAX_NODES)})
    assert response.status_code == 200, response.text
    assert response.json()["result"]["declared_contract_version"] == "workflow_ir.v1"


def test_adapt_refuses_before_the_adapter_runs(client, cat):
    body = _error(client.post("/api/v1/workflows/adapt",
                              json={"workflow": _nested(wl.MAX_DEPTH + 1)}))
    assert "depth" in body["message"]


def test_adapt_checks_the_overlay_too(client, cat):
    wf = cat.raw_workflow("procurement")
    _error(client.post("/api/v1/workflows/adapt",
                       json={"workflow": wf, "overlay": _nested(wl.MAX_DEPTH + 1)}))


def test_compare_checks_both_documents(client, cat):
    v2s = cat.v2_inputs("procurement")
    payload = {"v1_workflow": v2s["v1_workflow"], "v2_workflow": v2s["v2_workflow"],
               "v1_overlay": v2s["v1_overlay"], "v2_overlay": v2s["v2_overlay"]}
    big = json.loads(json.dumps(v2s["v2_workflow"]))
    big["base_ir"]["edges"] = [dict(big["base_ir"]["edges"][0], edge_id=f"e{i}")
                               for i in range(wl.MAX_EDGES + 1)]
    body = _error(client.post("/api/v1/workflows/compare-adaptations",
                              json=dict(payload, v2_workflow=big)))
    assert body["field_path"] == "v2_workflow"


def test_the_byte_cap_is_enforced_below_the_body_middleware(client):
    # 1 MiB of payload inside the 2 MiB body cap: the structural guard, not the
    # middleware, must be the one that answers, and with the typed code.
    padding = "x" * (wl.MAX_DOCUMENT_BYTES + 16)
    body = _error(client.post("/api/v1/workflows/validate",
                              json={"contract_version": "workflow_ir.v1",
                                    "workflow": {"ir_version": "workflow_ir.v1", "pad": padding}}))
    assert "document_bytes" in body["message"]


def test_the_element_cap_stops_the_walk_without_recursion():
    wide = {"ir_version": "workflow_ir.v2", "items": [0] * (wl.MAX_ELEMENTS + 10)}
    with pytest.raises(Exception) as excinfo:
        wl.enforce_workflow_limits(wide)
    assert getattr(excinfo.value, "code", "") == "workflow_too_complex"
