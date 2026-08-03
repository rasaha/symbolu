"""Compiler-adaptation tests (§24 — Compiler adaptation + total node accounting)."""
from __future__ import annotations

import copy

from ugence_agent_workforce_composer.adapter import adapt_compiled_workflow, classify_node
from ugence_agent_workforce_composer.contracts import (
    AuthorityDisposition,
    CapabilityOwner,
    NodeDisposition,
    NodeKind,
)
from ugence_agent_workforce_composer import fixtures


def test_valid_package_adapts_deterministically():
    pkg = fixtures.procurement_workflow()
    a = adapt_compiled_workflow(pkg, role_overlay=fixtures.role_overlay())
    b = adapt_compiled_workflow(pkg, role_overlay=fixtures.role_overlay())
    assert a.ok and b.ok
    assert a.adaptation_fingerprint == b.adaptation_fingerprint


def test_all_nodes_accounted_exactly_once():
    for wf in (fixtures.procurement_workflow, fixtures.support_workflow, fixtures.security_workflow):
        a = adapt_compiled_workflow(wf(), role_overlay=fixtures.role_overlay())
        assert a.accounting_holds()
        # union == all, disjoint
        assert a.role_node_ids().isdisjoint(a.non_agent_node_ids())
        allids = set(a.all_node_ids())
        assert (a.role_node_ids() | a.non_agent_node_ids()) == allids
        assert len(allids) == len(a.node_dispositions)


def test_authoritative_nodes_never_become_agent_roles():
    a = adapt_compiled_workflow(fixtures.procurement_workflow())
    role_nodes = a.role_node_ids()
    # governance / approval / clearance nodes must not be agent roles
    for nid in ("proc_binding_approval", "proc_purchase_auth", "proc_commit_clearance"):
        assert nid not in role_nodes
    # and every AI_AGENT_ELIGIBLE node is advisory + compiler-owned
    for r in a.role_requirements:
        assert r.authority_context.authority_disposition is AuthorityDisposition.ADVISORY
        assert r.authority_context.owning_capability is CapabilityOwner.COMPILER


def test_unknown_ir_version_fails_closed():
    pkg = fixtures.support_workflow()
    pkg["workflow_ir"]["ir_version"] = "workflow_ir.v999"
    a = adapt_compiled_workflow(pkg)
    assert a.ok is False
    assert any(d.code == "UNSUPPORTED_IR_VERSION" for d in a.diagnostics)


def test_missing_source_digest_fails_closed():
    pkg = fixtures.support_workflow()
    pkg.pop("structural_digest", None)
    pkg.get("manifest", {}).pop("structural_digest", None)
    a = adapt_compiled_workflow(pkg["workflow_ir"])  # bare IR, no digest anywhere
    assert a.ok is False
    assert any(d.code == "MISSING_SOURCE_DIGEST" for d in a.diagnostics)


def test_unknown_node_kind_is_typed_unsupported():
    pkg = fixtures.support_workflow()
    pkg["workflow_ir"]["nodes"][0]["kind"] = "NOT_A_REAL_KIND"
    a = adapt_compiled_workflow(pkg)
    dispo = {nd.node_id: nd.disposition for nd in a.node_dispositions}
    assert dispo["sup_classification"] is NodeDisposition.UNSUPPORTED_NODE


def test_missing_authority_metadata_is_invalid_node_not_agent():
    pkg = fixtures.support_workflow()
    pkg["workflow_ir"]["nodes"][0]["owning_capability"] = "???"
    a = adapt_compiled_workflow(pkg)
    dispo = {nd.node_id: nd.disposition for nd in a.node_dispositions}
    assert dispo["sup_classification"] is NodeDisposition.INVALID_NODE
    assert "sup_classification" not in a.role_node_ids()


def test_duplicate_node_id_is_fatal():
    pkg = fixtures.support_workflow()
    dup = copy.deepcopy(pkg["workflow_ir"]["nodes"][0])
    pkg["workflow_ir"]["nodes"].append(dup)
    a = adapt_compiled_workflow(pkg)
    assert a.ok is False
    assert any(d.code == "DUPLICATE_NODE_ID" for d in a.diagnostics)


def test_invalid_graph_reference_is_fatal():
    pkg = fixtures.support_workflow()
    pkg["workflow_ir"]["edges"].append(
        {"edge_id": "bad", "kind": "NEXT", "source_id": "sup_classification",
         "target_id": "does_not_exist", "order": 99})
    a = adapt_compiled_workflow(pkg)
    assert a.ok is False
    assert any(d.code == "INVALID_GRAPH_REFERENCE" for d in a.diagnostics)


def test_source_digest_and_provenance_preserved():
    pkg = fixtures.procurement_workflow()
    a = adapt_compiled_workflow(pkg)
    assert a.source_package_digest == pkg["structural_digest"]
    for r in a.role_requirements:
        assert r.source_package_digest == pkg["structural_digest"]
        assert r.provenance.synthetic is True


def test_undeclared_overlay_field_rejected():
    pkg = fixtures.procurement_workflow()
    a = adapt_compiled_workflow(pkg, role_overlay={"proc_supplier_evidence": {"not_a_field": 1}})
    assert a.ok is False
    assert any(d.code == "INVALID_OVERLAY_FIELD" for d in a.diagnostics)


def test_classify_authoritative_actiongate_is_governance_owned():
    d, _ = classify_node(NodeKind.ACTION_CONSTRAINT, CapabilityOwner.ACTION_GATE,
                         AuthorityDisposition.AUTHORITATIVE, "")
    assert d is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP


def test_classify_approval_gate_is_human_authority():
    d, _ = classify_node(NodeKind.APPROVAL_GATE, CapabilityOwner.DECISION_AUTHORITY,
                         AuthorityDisposition.AUTHORITATIVE, "HUMAN_APPROVER")
    assert d is NodeDisposition.HUMAN_AUTHORITY_REQUIRED


def test_classify_evidence_requirement_advisory_compiler_is_agent():
    d, _ = classify_node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityOwner.COMPILER,
                         AuthorityDisposition.ADVISORY, "")
    assert d is NodeDisposition.AI_AGENT_ELIGIBLE


def test_classify_storygraph_advisory_is_governance_owned():
    d, _ = classify_node(NodeKind.SEQUENCE_RISK_CHECK, CapabilityOwner.STORYGRAPH,
                         AuthorityDisposition.ADVISORY, "")
    assert d is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP
