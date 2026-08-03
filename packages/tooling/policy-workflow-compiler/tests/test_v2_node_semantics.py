"""Semantic node enrichment, capability extraction and typed contracts."""

from __future__ import annotations

import pytest

from ugence_policy_workflow_compiler.compiler.workflow_ir import NodeKind
from ugence_policy_workflow_compiler.models.common import (
    AuthorityDisposition,
    CapabilityId,
)
from ugence_policy_workflow_compiler.semantics import (
    CapabilityRequirementSource,
    RoleRelevance,
    classify_role_relevance,
    enrich_workflow,
)
import _v2_helpers as H


def _semantics(ir):
    v2 = enrich_workflow(ir, compiler_version="test")
    return {s.node_id: s for s in v2.node_semantics}, v2


def test_every_node_has_semantics_and_a_purpose():
    ir = H.procurement_ir()
    by_id, v2 = _semantics(ir)
    assert len(v2.node_semantics) == len(ir.nodes)
    for s in v2.node_semantics:
        assert s.semantic_purpose
        assert s.node_kind
        assert s.authority_disposition in ("ADVISORY", "AUTHORITATIVE")


def test_advisory_evidence_node_is_agent_eligible():
    n = H.node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, H.ADV,
               output_contract="x")
    assert classify_role_relevance(n) is RoleRelevance.ADVISORY_AGENT_ELIGIBLE


@pytest.mark.parametrize("kind", [NodeKind.APPROVAL_GATE, NodeKind.OVERRIDE_GATE,
                                  NodeKind.AUTHORITY_CHECK])
def test_human_authority_nodes(kind):
    n = H.node(kind, CapabilityId.DECISION_AUTHORITY, H.AUTH, authority_type="HUMAN_APPROVER")
    assert classify_role_relevance(n) is RoleRelevance.HUMAN_AUTHORITY


def test_segregation_is_human_review():
    n = H.node(NodeKind.SEGREGATION_OF_DUTIES_GATE, CapabilityId.DECISION_AUTHORITY, H.AUTH)
    assert classify_role_relevance(n) is RoleRelevance.HUMAN_REVIEW


def test_authoritative_governance_node_is_governance_owned():
    n = H.node(NodeKind.ACTION_CONSTRAINT, CapabilityId.ACTION_GATE, H.AUTH)
    assert classify_role_relevance(n) is RoleRelevance.GOVERNANCE_OWNED


def test_authoritative_node_is_never_agent_eligible():
    for kind, owner in [(NodeKind.DECISION_RULE, CapabilityId.DECISION_AUTHORITY),
                        (NodeKind.ACTION_CONSTRAINT, CapabilityId.ACTION_GATE),
                        (NodeKind.ACTION_CLEARANCE_REQUIREMENT, CapabilityId.ACTION_CLEARANCE)]:
        n = H.node(kind, owner, H.AUTH)
        assert classify_role_relevance(n) is not RoleRelevance.ADVISORY_AGENT_ELIGIBLE


def test_evidence_node_requires_evidence_extraction_from_node_kind_mapping():
    ir = H.procurement_ir()
    by_id, v2 = _semantics(ir)
    agent_nodes = [s for s in v2.node_semantics
                   if s.role_relevance is RoleRelevance.ADVISORY_AGENT_ELIGIBLE]
    assert agent_nodes
    for s in agent_nodes:
        caps = {c.capability_id: c for c in s.required_capability_refs}
        assert "evidence_extraction" in caps
        assert caps["evidence_extraction"].source is CapabilityRequirementSource.NODE_KIND_MAPPING


def test_capability_extraction_is_deterministic_and_provenanced():
    ir = H.procurement_ir()
    _, a = _semantics(ir)
    _, b = _semantics(ir)
    assert a.workflow_fingerprint == b.workflow_fingerprint
    for s in a.node_semantics:
        for c in s.required_capability_refs:
            assert c.provenance.compiler_rule
            assert c.provenance.derivation_class


def test_no_duplicate_capability_requirements():
    ir = H.cybersecurity_success_ir()
    _, v2 = _semantics(ir)
    for s in v2.node_semantics:
        ids = [c.capability_id for c in s.required_capability_refs]
        assert len(ids) == len(set(ids))


def test_typed_contracts_have_producer_and_consumer_links():
    ir = H.procurement_ir()
    by_id, v2 = _semantics(ir)
    # the risk-analysis node consumes supplier_evidence and produces supplier_risk_report
    risk = next(s for s in v2.node_semantics
                if any(o.contract_ref.contract_id == "supplier_risk_report"
                       for o in s.produced_output_contract_refs))
    inputs = {i.contract_ref.contract_id: i for i in risk.required_input_contract_refs}
    assert "supplier_evidence" in inputs
    assert inputs["supplier_evidence"].producer_node_id  # resolved producer


def test_contract_refs_are_versioned_fields_present():
    ir = H.procurement_ir()
    _, v2 = _semantics(ir)
    for s in v2.node_semantics:
        for o in s.produced_output_contract_refs:
            assert o.contract_ref.contract_version == "workflow_ir.v2"
            assert hasattr(o.contract_ref, "contract_data_version")


def test_semantic_purpose_is_not_derived_from_free_text_label():
    # purpose comes from the node-kind mapping, not the (possibly arbitrary) label.
    n1 = H.node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, H.ADV, label="anything at all")
    ir = H.linear_ir("p", [n1, H.node(NodeKind.TERMINAL_OUTCOME, CapabilityId.COMPILER, H.ADV)])
    _, v2 = _semantics(ir)
    sem = next(s for s in v2.node_semantics if s.node_id == n1.node_id)
    assert sem.semantic_purpose == "collect and extract evidence for a governed decision"
    assert sem.semantic_description == "anything at all"  # label kept separately, verbatim
