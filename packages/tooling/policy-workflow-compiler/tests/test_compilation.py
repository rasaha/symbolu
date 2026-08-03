"""Compilation tests: determinism of ids, edges, manifests, digest."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import (
    GovernedWorkflowCompiler,
    compile_policy_pack,
    verify_compiled_package,
)
from ugence_policy_workflow_compiler.compiler.workflow_ir import NodeKind


def test_deterministic_node_ids(procurement_pack):
    c = GovernedWorkflowCompiler()
    ir1 = c.synthesize(procurement_pack)
    ir2 = c.synthesize(procurement_pack)
    assert [n.node_id for n in ir1.nodes] == [n.node_id for n in ir2.nodes]


def test_deterministic_edge_order(procurement_pack):
    c = GovernedWorkflowCompiler()
    ir1 = c.synthesize(procurement_pack)
    ir2 = c.synthesize(procurement_pack)
    assert [(e.source_id, e.target_id, e.kind.value, e.order) for e in ir1.edges] == [
        (e.source_id, e.target_id, e.kind.value, e.order) for e in ir2.edges
    ]
    # edge orders are contiguous and sorted
    assert [e.order for e in ir1.edges] == list(range(len(ir1.edges)))


def test_identical_input_same_digest(procurement_pack, synthetic_pack):
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
    )

    appr = build_procurement_approval_fixture(procurement_pack)
    a = compile_policy_pack(procurement_pack, appr)
    b = compile_policy_pack(procurement_pack, appr)
    assert a.success and b.success
    assert a.logical_digest == b.logical_digest


def test_capability_manifest_deterministic(procurement_pack):
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
    )

    appr = build_procurement_approval_fixture(procurement_pack)
    a = compile_policy_pack(procurement_pack, appr)
    caps = a.compiled_package.capability_manifest.referenced_capabilities
    # Procurement requires exactly these (no clearance/storygraph/model-selection).
    assert set(caps) == {"ACTION_GATE", "COMPILER", "DECISION_AUTHORITY", "TAP"}


def test_only_required_capabilities_included(procurement_pack):
    ir = GovernedWorkflowCompiler().synthesize(procurement_pack)
    assert "ACTION_CLEARANCE" not in ir.referenced_capabilities
    assert "STORYGRAPH" not in ir.referenced_capabilities
    assert "MODEL_SELECTION" not in ir.referenced_capabilities


def test_all_expected_node_kinds_present(procurement_pack):
    ir = GovernedWorkflowCompiler().synthesize(procurement_pack)
    kinds = set(ir.node_kinds)
    for expected in (
        NodeKind.EVIDENCE_REQUIREMENT.value,
        NodeKind.DECISION_RULE.value,
        NodeKind.AUTHORITY_CHECK.value,
        NodeKind.APPROVAL_GATE.value,
        NodeKind.SEGREGATION_OF_DUTIES_GATE.value,
        NodeKind.PROHIBITED_CONDITION.value,
        NodeKind.ACTION_CONSTRAINT.value,
        NodeKind.AUDIT_EMISSION.value,
        NodeKind.TERMINAL_OUTCOME.value,
    ):
        assert expected in kinds


def test_verify_compiled_package(procurement_pack):
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
    )

    appr = build_procurement_approval_fixture(procurement_pack)
    result = compile_policy_pack(procurement_pack, appr)
    report = verify_compiled_package(result.compiled_package)
    assert report.passed, report.failed_checks()


def test_synthetic_pack_compiles(synthetic_pack):
    from ugence_policy_workflow_compiler.approval import build_approval_record
    from ugence_policy_workflow_compiler.models.approvals import ApprovalDecision

    appr = build_approval_record(
        approval_id="a1", pack=synthetic_pack, reviewer_id="rev",
        reviewer_role="role", decision=ApprovalDecision.APPROVED,
    )
    result = compile_policy_pack(synthetic_pack, appr)
    assert result.success, [d.message for d in result.diagnostics]
    assert result.assurance_manifest.coverage_matrix.complete
