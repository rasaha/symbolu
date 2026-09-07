"""The BPMN 2.0 converter over the synthetic fixtures (CV-2, CV-3, CV-4), to the
same standard as the n8n suite."""
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
from ugence_workflow_converters.bpmn.convert import translate_condition, _Ctx

NS = 'xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def _bytes(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def purchase():
    return convert("bpmn-2.0", _bytes("purchase_approval.bpmn"))


def _rows(outcome):
    return {r.source_name: r for r in outcome.report.mapping_table}


def test_every_construct_has_exactly_one_row_and_the_state_is_partial(purchase):
    rows = purchase.report.mapping_table
    assert len(rows) == 18  # 2 pools, 2 lanes, 14 flow nodes
    assert len({r.source_construct_id for r in rows}) == 18
    assert purchase.report.source.construct_count == 14
    assert purchase.report.conversion_state is ConversionState.PARTIAL
    assert [r.source_name for r in purchase.report.unsupported_constructs] == ["Compute total"]


def test_a_gateway_becomes_one_rule_per_conditioned_flow_with_the_predicates_that_translate(purchase):
    row = _rows(purchase)["Over threshold?"]
    assert row.outcome is RowOutcome.MAPPED
    assert row.reason_code == "GATEWAY_TO_DECISION_RULES"
    assert len(row.target_object_ids) == 1  # the default flow's condition is not a rule
    rule = next(r for r in purchase.pack.decision_rules if r.object_id == row.target_object_ids[0])
    assert rule.name == "Over threshold? → Task_approve_purchase"
    assert [(p.fact_key, p.comparator.value, p.value) for p in rule.conditions] == [
        ("amount", "GT", 1000), ("status", "EQ", "OPEN")]
    assert "DEFAULT_FLOW_CONDITION_IGNORED" in row.semantic_loss


def test_a_business_rule_task_becomes_a_rule_with_no_predicate_and_a_dmn_loss(purchase):
    row = _rows(purchase)["Risk score"]
    assert row.reason_code == "BUSINESS_RULE_TO_DECISION_RULE"
    assert row.note == "risk_scoring"
    rule = next(r for r in purchase.pack.decision_rules if r.object_id == row.target_object_ids[0])
    assert rule.conditions == ()
    assert "DMN_NOT_TRANSLATED" in row.semantic_loss
    gaps = {(g.source_construct_id, g.gap_code) for g in purchase.report.governance_gaps}
    assert ("Task_risk_score", "BRANCH_PREDICATE_NOT_TRANSLATED") in gaps


def test_receive_send_service_and_throw_map_to_connectors_with_the_right_derivations(purchase):
    rows = _rows(purchase)
    assert rows["Receive confirmation"].target_object_types == ("CONNECTOR_MAPPING", "REQUIRED_EVIDENCE")
    ev = next(e for e in purchase.pack.required_evidence if e.name == "Receive confirmation")
    assert ev.fact_key == "receive_confirmation"
    assert rows["Notify supplier"].target_object_types == ("CONNECTOR_MAPPING",)
    assert rows["Fetch order"].target_object_types == ("CONNECTOR_MAPPING",)
    assert rows["Signal done"].reason_code == "EXTERNAL_THROW_TO_CONNECTOR_MAPPING"
    fetch = next(c for c in purchase.pack.connector_mappings if c.name == "Fetch order")
    assert fetch.target_system == "bpmn:serviceTask"
    assert "taskDefinition.type=fetch-order" in fetch.target_field
    assert fetch.credential_handle == ""
    gaps = {(g.source_construct_id, g.gap_code) for g in purchase.report.governance_gaps}
    assert ("Task_notify_supplier", "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY") in gaps
    assert ("Event_signal_done", "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY") in gaps
    assert ("Task_fetch_order", "SERVICE_EFFECT_UNDECLARED") in gaps
    assert purchase.pack.action_constraints == () and purchase.pack.authority_requirements == ()


def test_human_start_end_wait_parallel_boundary_abstract_lane_and_pool_rows(purchase):
    rows = _rows(purchase)
    assert rows["Approve purchase"].reason_code == "HUMAN_STEP"
    assert rows["Approve purchase"].note == "lane: Finance"
    assert rows["Purchase requested"].reason_code == "ENTRY_POINT"
    assert rows["Done"].reason_code == "TERMINAL"
    assert rows["Wait one day"].reason_code == "EVENT_WAIT" and rows["Wait one day"].note == "timer"
    assert rows["Fork"].reason_code == "PARALLEL_SPLIT"
    assert rows["Fetch failed"].reason_code == "EXCEPTION_PATH" and rows["Fetch failed"].note == "error"
    assert rows["File record"].reason_code == "ABSTRACT_TASK"
    assert rows["Finance"].reason_code == "LANE_PERFORMER_NOT_AUTHORITY"
    assert rows["Supplier"].reason_code == "POOL_CONTEXT"
    gaps = {(g.source_construct_id, g.gap_code) for g in purchase.report.governance_gaps}
    assert ("Task_approve_purchase", "HUMAN_STEP_WITHOUT_AUTHORITY") in gaps
    assert ("StartEvent_request", "ENTRY_POINT_NOT_GOVERNED") in gaps
    assert ("Task_file_record", "TASK_EFFECT_UNDECLARED") in gaps
    human_gap = next(g for g in purchase.report.governance_gaps if g.source_construct_id == "Task_approve_purchase")
    assert "Finance" in human_gap.detail


def test_scripts_are_unsupported_and_never_inspected(purchase):
    row = _rows(purchase)["Compute total"]
    assert row.outcome is RowOutcome.UNSUPPORTED and row.reason_code == "EXECUTABLE_NOT_TRANSLATED"
    dumped = json.dumps(purchase.pack_document) + json.dumps(purchase.report.as_document()) + json.dumps(purchase.preview)
    assert "setVariable" not in dumped


def test_workflow_level_losses_name_control_flow_and_data_objects(purchase):
    codes = {(w.source_construct_id, w.code) for w in purchase.report.semantic_loss_warnings}
    assert ("$", "CONTROL_FLOW_ORDER_NOT_CARRIED") in codes
    assert ("$", "DATA_OBJECTS_NOT_CARRIED") in codes
    assert purchase.report.source.connection_count == 14
    assert len(purchase.connections) == 14
    assert ("StartEvent_request", "Task_fetch_order") in purchase.connections
    assert purchase.report.credential_requirements == ()  # BPMN names no credentials
    assert {t.tool for t in purchase.report.tool_requirements} == {"bpmn:serviceTask", "bpmn:sendTask", "bpmn:receiveTask", "bpmn:intermediateThrowEvent"}


def test_the_pack_cites_the_export_as_the_provenance_of_every_object(purchase):
    src = purchase.pack.source_documents[0]
    assert src.content_digest == purchase.report.source.input_digest
    assert src.title == "Purchase Approval"
    assert src.document_version == "Definitions_purchase"
    for obj in purchase.pack.all_objects():
        if obj.object_type.value == "SOURCE_DOCUMENT":
            continue
        assert obj.provenance_refs == (src.object_id,), obj.object_id
    assert purchase.pack.status.value == "DRAFT"
    assert purchase.report.validation.ok is True
    assert purchase.report.source.format_detail == "BPMN 2.0 XML export; exporter Synthetic Modeler 1.0"


def test_the_minimal_process_translates_with_a_predicate_free_gateway():
    outcome = convert("bpmn-2.0", _bytes("minimal.bpmn"))
    rows = {r.source_name: r for r in outcome.report.mapping_table}
    assert rows["Decide"].reason_code == "GATEWAY_TO_DECISION_RULES"
    rule = outcome.pack.decision_rules[0]
    assert rule.conditions == ()
    assert rows["Receive request"].target_object_types == ("CONNECTOR_MAPPING", "REQUIRED_EVIDENCE")
    assert outcome.report.conversion_state is ConversionState.PARTIAL  # control flow is never carried
    assert outcome.preview is not None and outcome.report.validation.ok


def test_an_unknown_bpmn_element_is_unsupported_and_the_conversion_partial():
    outcome = convert("bpmn-2.0", _bytes("unknown_element.bpmn"))
    row = {r.source_name: r for r in outcome.report.mapping_table}["Quantum step"]
    assert row.outcome is RowOutcome.UNSUPPORTED and row.reason_code == "UNKNOWN_ELEMENT"
    assert outcome.report.conversion_state is ConversionState.PARTIAL


@pytest.mark.parametrize("name, code", [
    ("embedded_secret.bpmn", RefusalCode.EMBEDDED_SECRET),
    ("doctype.bpmn", RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT),
])
def test_refusals_over_fixtures(name, code):
    with pytest.raises(ConversionRefused) as excinfo:
        convert("bpmn-2.0", _bytes(name))
    assert excinfo.value.code is code


@pytest.mark.parametrize("data, code", [
    (b"name: x\nnodes: []\n", RefusalCode.NOT_XML),
    (b'{"nodes": [], "connections": {}}', RefusalCode.NOT_XML),
    (b"<html><body>hi</body></html>", RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT),
    (f'<definitions {NS}></definitions>'.encode(), RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT),
    (b'<?xml version="1.0"?><!ENTITY x "y"><a/>', RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT),
    (f'<definitions {NS}><process id="p"><serviceTask id="t" name="t" apiKey="abc"/></process></definitions>'.encode(), RefusalCode.EMBEDDED_SECRET),
    (f'<definitions {NS}><process id="p"><serviceTask id="t" name="t"><documentation>token: sk-abcdefghijklmnopqrstuvwxyz</documentation></serviceTask></process></definitions>'.encode(), RefusalCode.EMBEDDED_SECRET),
])
def test_refusals_by_typed_code(data, code):
    with pytest.raises(ConversionRefused) as excinfo:
        convert("bpmn-2.0", data)
    assert excinfo.value.code is code


def test_limits_refuse_before_any_construct_is_read():
    many = "".join(f'<task id="t{i}" name="T{i}"/>' for i in range(201))
    with pytest.raises(ConversionRefused) as excinfo:
        convert("bpmn-2.0", f'<definitions {NS}><process id="p">{many}</process></definitions>'.encode())
    assert excinfo.value.code is RefusalCode.TOO_MANY_NODES
    deep = "<a>" * 40 + "</a>" * 40
    with pytest.raises(ConversionRefused) as excinfo:
        convert("bpmn-2.0", f'<definitions {NS}><process id="p"><extensionElements>{deep}</extensionElements></process></definitions>'.encode())
    assert excinfo.value.code is RefusalCode.TOO_DEEP
    big = f'<definitions {NS}><process id="p"><documentation>'.encode() + b"x" * (1024 * 1024) + b"</documentation></process></definitions>"
    with pytest.raises(ConversionRefused) as excinfo:
        convert("bpmn-2.0", big)
    assert excinfo.value.code is RefusalCode.TOO_LARGE


@pytest.mark.parametrize("text, expected, losses", [
    ("${amount > 1000}", [("amount", "GT", 1000)], []),
    ("#{order.total >= 250 && approved}", [("total", "GTE", 250), ("approved", "IS_TRUE", None)], []),
    ("=status = \"OPEN\" and !flagged", [("status", "EQ", "OPEN"), ("flagged", "IS_FALSE", None)], []),
    ("${approved == true}", [("approved", "IS_TRUE", None)], []),
    ("${amount > 1000 || vip}", [], ["OR_COMBINATOR_NOT_TRANSLATED"]),
    ("${amount > threshold}", [], ["EXPRESSION_NOT_TRANSLATED"]),
    ("${ratio > 0.5}", [], ["NON_INTEGER_LITERAL"]),
    ("${compute(amount) > 3}", [], ["EXPRESSION_NOT_TRANSLATED"]),
    ("", [], ["BRANCH_PREDICATE_NOT_TRANSLATED"]),
])
def test_condition_translation_table(text, expected, losses):
    ctx = _Ctx("src")
    predicates, got = translate_condition(text, "g", ctx)
    assert [(p.fact_key, p.comparator.value, p.value) for p in predicates] == expected
    assert got == sorted(losses)


def test_conversion_is_deterministic_and_the_report_is_content_addressed():
    a = convert("bpmn-2.0", _bytes("purchase_approval.bpmn"))
    b = convert("bpmn-2.0", _bytes("purchase_approval.bpmn"))
    assert a.report.as_document() == b.report.as_document()
    assert a.pack_document == b.pack_document
    assert a.preview == b.preview
    assert a.report.report_digest.startswith("sha256:")
