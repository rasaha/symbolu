"""The n8n converter over the synthetic fixtures (CV-2, CV-3, CV-4)."""
from __future__ import annotations

import json
import os

import pytest

from conftest import FIXTURES
from ugence_workflow_converters.api import (
    ConversionRefused,
    ConversionState,
    RefusalCode,
    RowOutcome,
    convert,
)


def _bytes(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def order():
    return convert("n8n", _bytes("order_review.n8n.json"))


def _rows(outcome):
    return {r.source_name: r for r in outcome.report.mapping_table}


def test_every_node_has_exactly_one_row_and_the_state_is_partial(order):
    rows = order.report.mapping_table
    assert len(rows) == 10
    assert len({r.source_construct_id for r in rows}) == 10
    assert order.report.conversion_state is ConversionState.PARTIAL
    assert [r.source_name for r in order.report.unsupported_constructs] == ["Score Risk"]


def test_the_branch_becomes_a_decision_rule_with_only_the_predicates_that_translate(order):
    rule = order.pack.decision_rules[0]
    assert rule.object_id.startswith("rule_amount_over_threshold_")
    assert [(p.fact_key, p.comparator.value, p.value) for p in rule.conditions] == [
        ("amount", "GT", 1000), ("status", "EQ", "OPEN")]
    row = _rows(order)["Amount Over Threshold"]
    assert row.outcome is RowOutcome.MAPPED
    assert row.target_object_ids == (rule.object_id,)
    assert "EXPRESSION_NOT_TRANSLATED" in row.semantic_loss
    assert any(g.gap_code == "BRANCH_PREDICATE_PARTIAL" and g.source_construct_id == "n3" for g in order.report.governance_gaps)


def test_a_system_read_becomes_a_connector_mapping_and_required_evidence(order):
    row = _rows(order)["Get Orders"]
    assert row.reason_code == "SYSTEM_READ_TO_CONNECTOR_AND_EVIDENCE"
    assert row.target_object_types == ("CONNECTOR_MAPPING", "REQUIRED_EVIDENCE")
    cm = next(c for c in order.pack.connector_mappings if c.name == "Get Orders")
    assert cm.target_system == "n8n-nodes-base.httpRequest"
    assert cm.target_field == "GET api.example.invalid/orders"
    assert cm.credential_handle == "httpHeaderAuth:orders_api"
    ev = next(e for e in order.pack.required_evidence if e.name == "Get Orders")
    assert ev.connector_mapping_id == cm.object_id
    assert ev.fact_key == "get_orders"


def test_a_system_write_gets_a_connector_mapping_and_a_gap_but_never_an_action_constraint(order):
    for name in ("Create Purchase Order", "Notify Finance"):
        row = _rows(order)[name]
        assert row.reason_code == "SYSTEM_WRITE_TO_CONNECTOR_MAPPING"
        assert row.target_object_types == ("CONNECTOR_MAPPING",)
    assert order.pack.action_constraints == ()
    assert order.pack.authority_requirements == ()
    gaps = {(g.source_construct_id, g.gap_code) for g in order.report.governance_gaps}
    assert ("n7", "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY") in gaps
    assert ("n4", "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY") in gaps


def test_model_steps_triggers_human_steps_and_data_shaping_are_unmapped_with_their_reasons(order):
    rows = _rows(order)
    assert rows["When clicking Test workflow"].reason_code == "ENTRY_POINT"
    assert rows["Summarize"].reason_code == "MODEL_STEP"
    assert rows["OpenAI Chat Model"].reason_code == "MODEL_STEP"
    assert rows["Normalize"].reason_code == "DATA_SHAPING"
    assert rows["Archive Old Draft"].semantic_loss == ("DISABLED_IN_SOURCE",)
    gaps = {(g.source_construct_id, g.gap_code) for g in order.report.governance_gaps}
    assert ("n1", "ENTRY_POINT_NOT_GOVERNED") in gaps
    assert ("n8", "MODEL_STEP_WITHOUT_GOVERNANCE") in gaps


def test_code_is_unsupported_and_never_inspected(order):
    row = _rows(order)["Score Risk"]
    assert row.outcome is RowOutcome.UNSUPPORTED
    assert row.reason_code == "EXECUTABLE_NOT_TRANSLATED"
    dumped = json.dumps(order.pack_document) + json.dumps(order.report.as_document())
    assert "return items.map" not in dumped


def test_credentials_are_handles_only_and_tools_are_listed(order):
    handles = {c.credential_handle for c in order.report.credential_requirements}
    assert handles == {"httpHeaderAuth:orders_api", "slackApi:finance_slack", "httpBasicAuth:erp_service_account", "openAiApi:openai_account"}
    assert all(":" in h and "cred-" not in h for h in handles)
    tools = {(t.tool, t.target) for t in order.report.tool_requirements}
    assert ("@n8n/n8n-nodes-langchain.lmChatOpenAi", "gpt-4o-mini") in tools
    assert ("n8n-nodes-base.httpRequest", "POST erp.example.invalid/purchase-orders") in tools


def test_workflow_level_losses_name_control_flow_and_pinned_data(order):
    codes = {(w.source_construct_id, w.code) for w in order.report.semantic_loss_warnings}
    assert ("$", "CONTROL_FLOW_ORDER_NOT_CARRIED") in codes
    assert ("$", "PINNED_DATA_IGNORED") in codes
    assert order.report.source.connection_count == 8  # seven main lanes and one ai_languageModel lane
    assert len(order.connections) == 8


def test_the_pack_cites_the_export_as_the_provenance_of_every_object(order):
    src = order.pack.source_documents[0]
    assert src.content_digest == order.report.source.input_digest
    assert src.title == "Order Review"
    for obj in order.pack.all_objects():
        if obj.object_type.value == "SOURCE_DOCUMENT":
            continue
        assert obj.provenance_refs == (src.object_id,), obj.object_id
    assert order.pack.status.value == "DRAFT"
    assert order.report.validation.ok is True
    assert order.report.validation.blocking == ()


def test_the_legacy_if_shape_translates_too():
    outcome = convert("n8n", _bytes("legacy_if.n8n.json"))
    rule = outcome.pack.decision_rules[0]
    assert [(p.fact_key, p.comparator.value, p.value) for p in rule.conditions] == [
        ("total", "GTE", 250), ("approved", "IS_TRUE", None)]
    row = {r.source_name: r for r in outcome.report.mapping_table}["Send Mail"]
    assert row.reason_code == "SYSTEM_WRITE_TO_CONNECTOR_MAPPING"
    assert outcome.report.conversion_state is ConversionState.PARTIAL  # control flow is never carried


def test_an_unknown_node_type_is_unsupported_and_the_conversion_partial():
    outcome = convert("n8n", _bytes("unknown_node.n8n.json"))
    row = {r.source_name: r for r in outcome.report.mapping_table}["Mystery Step"]
    assert row.outcome is RowOutcome.UNSUPPORTED
    assert row.reason_code == "UNKNOWN_NODE_TYPE"
    assert outcome.report.conversion_state is ConversionState.PARTIAL


@pytest.mark.parametrize("name, code", [
    ("embedded_secret.n8n.json", RefusalCode.EMBEDDED_SECRET),
])
def test_an_export_carrying_a_secret_is_refused_whole(name, code):
    with pytest.raises(ConversionRefused) as excinfo:
        convert("n8n", _bytes(name))
    assert excinfo.value.code is code


@pytest.mark.parametrize("data, code", [
    (b"name: x\nnodes: []\n", RefusalCode.NOT_JSON),
    (b"[1, 2]", RefusalCode.NOT_AN_OBJECT),
    (b'{"name": "x"}', RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT),
    (b'{"nodes": [], "connections": {}, "x": {"password": "hunter2"}}', RefusalCode.EMBEDDED_SECRET),
    (b'{"nodes": [], "connections": {}, "x": "sk-abcdefghijklmnopqrstuvwxyz"}', RefusalCode.EMBEDDED_SECRET),
])
def test_refusals_by_typed_code(data, code):
    with pytest.raises(ConversionRefused) as excinfo:
        convert("n8n", data)
    assert excinfo.value.code is code


def test_limits_refuse_before_any_construct_is_read():
    too_many = {"nodes": [{"id": f"n{i}", "name": f"N{i}", "type": "n8n-nodes-base.noOp", "parameters": {}} for i in range(201)], "connections": {}}
    with pytest.raises(ConversionRefused) as excinfo:
        convert("n8n", json.dumps(too_many).encode())
    assert excinfo.value.code is RefusalCode.TOO_MANY_NODES
    deep: dict = {"nodes": [], "connections": {}}
    cursor = deep
    for _ in range(40):
        cursor["child"] = {}
        cursor = cursor["child"]
    with pytest.raises(ConversionRefused) as excinfo:
        convert("n8n", json.dumps(deep).encode())
    assert excinfo.value.code is RefusalCode.TOO_DEEP
    big = b'{"nodes": [], "connections": {}, "pad": "' + b"x" * (1024 * 1024) + b'"}'
    with pytest.raises(ConversionRefused) as excinfo:
        convert("n8n", big)
    assert excinfo.value.code is RefusalCode.TOO_LARGE


def test_deferred_and_unknown_formats_are_refused_by_code():
    for name in ("langgraph", "crewai", "autogen"):
        with pytest.raises(ConversionRefused) as excinfo:
            convert(name, b"{}")
        assert excinfo.value.code is RefusalCode.DEFERRED_FORMAT
    with pytest.raises(ConversionRefused) as excinfo:
        convert("zapier", b"{}")
    assert excinfo.value.code is RefusalCode.UNSUPPORTED_FORMAT


def test_conversion_is_deterministic_and_the_report_is_content_addressed():
    a = convert("n8n", _bytes("order_review.n8n.json"))
    b = convert("n8n", _bytes("order_review.n8n.json"))
    assert a.report.as_document() == b.report.as_document()
    assert a.pack_document == b.pack_document
    assert a.preview == b.preview
    assert a.report.report_digest.startswith("sha256:")
    changed = a.report.model_copy(update={"conversion_state": ConversionState.STRUCTURALLY_TRANSLATED}).sealed()
    assert changed.report_digest != a.report.report_digest
