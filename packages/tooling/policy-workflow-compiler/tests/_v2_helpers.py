"""Helpers for the workflow_ir.v2 (P2) test suite.

Builds v1 ``WorkflowIR`` graphs directly (via the frozen v1 models) mirroring the
four merged Governance Studio P3A scenario shapes, so P2 enrichment can be tested
against compiler-owned semantics without depending on the AWC package or the
Studio app. Nothing here re-implements enrichment — it only assembles v1 inputs.
"""

from __future__ import annotations

from typing import List, Tuple

from ugence_policy_workflow_compiler.compiler.workflow_ir import (
    EdgeKind,
    NodeKind,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
    make_edge_id,
    make_node_id,
)
from ugence_policy_workflow_compiler.models.common import (
    AuthorityDisposition,
    CapabilityId,
)


def node(kind: NodeKind, owner: CapabilityId, disposition: AuthorityDisposition, *,
         authority_type: str = "", output_contract: str = "",
         inputs: Tuple[str, ...] = (), label: str = "",
         public_contract_target: str = "") -> WorkflowNode:
    return WorkflowNode(
        node_id=make_node_id(kind, owner, inputs),
        kind=kind, owning_capability=owner, disposition=disposition,
        authority_type=authority_type, output_contract=output_contract,
        input_object_ids=inputs, label=label,
        public_contract_target=public_contract_target,
    )


def linear_ir(pack_id: str, nodes: List[WorkflowNode]) -> WorkflowIR:
    edges = []
    for i in range(len(nodes) - 1):
        src, tgt = nodes[i].node_id, nodes[i + 1].node_id
        edges.append(WorkflowEdge(edge_id=make_edge_id(EdgeKind.ON_PASS, src, tgt),
                                  kind=EdgeKind.ON_PASS, source_id=src, target_id=tgt, order=i))
    refs = tuple(sorted({n.owning_capability.value for n in nodes}))
    return WorkflowIR(policy_pack_id=pack_id, policy_pack_version=1,
                      nodes=tuple(nodes), edges=tuple(edges), referenced_capabilities=refs)


ADV = AuthorityDisposition.ADVISORY
AUTH = AuthorityDisposition.AUTHORITATIVE


def procurement_ir() -> WorkflowIR:
    return linear_ir("gs_procurement", [
        node(NodeKind.DECISION_RULE, CapabilityId.DECISION_AUTHORITY, AUTH,
             output_contract="validated_request", label="request validation"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="supplier_evidence", inputs=("validated_request",),
             label="supplier evidence collection"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="supplier_risk_report", inputs=("supplier_evidence",),
             label="supplier-risk analysis"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="recommendation_draft", inputs=("supplier_risk_report",),
             label="procurement recommendation"),
        node(NodeKind.APPROVAL_GATE, CapabilityId.DECISION_AUTHORITY, AUTH,
             authority_type="HUMAN_APPROVER", label="binding approval",
             public_contract_target="ugence_decision_authority.api"),
        node(NodeKind.ACTION_CONSTRAINT, CapabilityId.ACTION_GATE, AUTH,
             label="purchase authorization",
             public_contract_target="ugence_actiongate_provider.api"),
        node(NodeKind.AUDIT_EMISSION, CapabilityId.COMPILER, ADV, label="audit emission"),
        node(NodeKind.TERMINAL_OUTCOME, CapabilityId.COMPILER, ADV, label="terminal"),
    ])


def customer_support_ir() -> WorkflowIR:
    return linear_ir("gs_support", [
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="ticket_class", label="ticket triage"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="retrieved_context", inputs=("ticket_class",),
             label="knowledge retrieval"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="draft_response", inputs=("retrieved_context",),
             label="response drafting"),
        node(NodeKind.AUTHORITY_CHECK, CapabilityId.DECISION_AUTHORITY, AUTH,
             authority_type="HUMAN_REVIEWER", label="escalation decision"),
        node(NodeKind.APPROVAL_GATE, CapabilityId.DECISION_AUTHORITY, AUTH,
             authority_type="HUMAN_APPROVER", label="human approval"),
        node(NodeKind.TERMINAL_OUTCOME, CapabilityId.COMPILER, ADV, label="terminal"),
    ])


def cybersecurity_success_ir() -> WorkflowIR:
    return linear_ir("gs_security", [
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="incident_evidence", label="security evidence collection"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="threat_assessment", inputs=("incident_evidence",),
             label="threat analysis"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="correlated_incident", inputs=("threat_assessment",),
             label="incident correlation"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="security_recommendation", inputs=("correlated_incident",),
             label="security recommendation"),
        node(NodeKind.SEQUENCE_RISK_CHECK, CapabilityId.STORYGRAPH, ADV,
             output_contract="sequence_risk_signal", label="sequence-risk advisory"),
        node(NodeKind.OVERRIDE_GATE, CapabilityId.DECISION_AUTHORITY, AUTH,
             authority_type="HUMAN_APPROVER", label="human escalation"),
        node(NodeKind.ACTION_CONSTRAINT, CapabilityId.ACTION_GATE, AUTH,
             label="action boundary"),
        node(NodeKind.AUDIT_EMISSION, CapabilityId.COMPILER, ADV, label="audit emission"),
        node(NodeKind.TERMINAL_OUTCOME, CapabilityId.COMPILER, ADV, label="terminal"),
    ])


def cybersecurity_no_feasible_team_ir() -> WorkflowIR:
    return linear_ir("gs_security_infeasible", [
        node(NodeKind.DECISION_RULE, CapabilityId.DECISION_AUTHORITY, AUTH,
             output_contract="incident_evidence", label="incident intake"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="threat_assessment", inputs=("incident_evidence",),
             label="threat analysis"),
        node(NodeKind.EVIDENCE_REQUIREMENT, CapabilityId.COMPILER, ADV,
             output_contract="correlated_incident", inputs=("threat_assessment",),
             label="incident correlation"),
        node(NodeKind.OVERRIDE_GATE, CapabilityId.DECISION_AUTHORITY, AUTH,
             authority_type="HUMAN_APPROVER", label="human escalation"),
        node(NodeKind.ACTION_CONSTRAINT, CapabilityId.ACTION_GATE, AUTH,
             label="action boundary"),
        node(NodeKind.AUDIT_EMISSION, CapabilityId.COMPILER, ADV, label="audit emission"),
        node(NodeKind.TERMINAL_OUTCOME, CapabilityId.COMPILER, ADV, label="terminal"),
    ])


P3A_SCENARIOS = {
    "procurement": procurement_ir,
    "customer_support": customer_support_ir,
    "cybersecurity_success": cybersecurity_success_ir,
    "cybersecurity_no_feasible_team": cybersecurity_no_feasible_team_ir,
}


def reference_v2():
    """Enrich the shipped procurement reference pack to v2."""
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )
    from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
    pack = build_procurement_policy_pack()
    appr = build_procurement_approval_fixture(pack)
    return compile_workflow_v2(pack, appr, require_approval=True)
