"""Authority-boundary tests: illegal authority compositions fail compilation."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import (
    AuthorityDisposition,
    CapabilityId,
    DecisionRule,
    GovernedWorkflowCompiler,
    PolicyPack,
    PolicyPackStatus,
    Predicate,
    Comparator,
)
from ugence_policy_workflow_compiler.compiler.workflow_ir import (
    NodeKind,
    WorkflowIR,
    WorkflowNode,
)
from ugence_policy_workflow_compiler.validation import authority_boundaries as B

from _builders import build_full_synthetic_pack


def _node(kind, capability, disposition):
    return WorkflowNode(
        node_id="n1", kind=kind, owning_capability=capability, disposition=disposition
    )


def test_tap_cannot_decide():
    node = _node(NodeKind.DECISION_RULE, CapabilityId.TAP, AuthorityDisposition.ADVISORY)
    assert B.check_node(node)


def test_storygraph_cannot_decide():
    node = _node(NodeKind.DECISION_RULE, CapabilityId.STORYGRAPH, AuthorityDisposition.ADVISORY)
    assert B.check_node(node)


def test_decision_authority_cannot_authorize_exact_action():
    node = _node(NodeKind.ACTION_CONSTRAINT, CapabilityId.DECISION_AUTHORITY,
                 AuthorityDisposition.AUTHORITATIVE)
    assert B.check_node(node)


def test_actiongate_cannot_make_business_decision():
    node = _node(NodeKind.DECISION_RULE, CapabilityId.ACTION_GATE,
                 AuthorityDisposition.AUTHORITATIVE)
    assert B.check_node(node)


def test_action_clearance_cannot_make_business_decision():
    node = _node(NodeKind.DECISION_RULE, CapabilityId.ACTION_CLEARANCE,
                 AuthorityDisposition.AUTHORITATIVE)
    assert B.check_node(node)


def test_orchestrator_cannot_grant_authority():
    node = _node(NodeKind.AUTHORITY_CHECK, CapabilityId.OPTIONAL_ORCHESTRATOR,
                 AuthorityDisposition.ADVISORY)
    assert B.check_node(node)


def test_advisory_node_cannot_be_authoritative():
    node = _node(NodeKind.SEQUENCE_RISK_CHECK, CapabilityId.STORYGRAPH,
                 AuthorityDisposition.AUTHORITATIVE)
    assert B.check_node(node)


def test_well_formed_nodes_pass():
    good = [
        _node(NodeKind.DECISION_RULE, CapabilityId.DECISION_AUTHORITY, AuthorityDisposition.AUTHORITATIVE),
        _node(NodeKind.ACTION_CONSTRAINT, CapabilityId.ACTION_GATE, AuthorityDisposition.AUTHORITATIVE),
        _node(NodeKind.EVIDENCE_ADMISSIBILITY, CapabilityId.TAP, AuthorityDisposition.ADVISORY),
        _node(NodeKind.SEQUENCE_RISK_CHECK, CapabilityId.STORYGRAPH, AuthorityDisposition.ADVISORY),
    ]
    for n in good:
        assert not B.check_node(n)


def test_misconfigured_pack_fails_compilation():
    """A decision rule declared as owned by TAP synthesizes a boundary-violating
    IR and fails compilation with a FATAL diagnostic."""
    pack = build_full_synthetic_pack()
    bad_rule = DecisionRule(
        object_id="rule.bad", name="bad", provenance_refs=("src.test",),
        conditions=(Predicate(fact_key="ok", comparator=Comparator.IS_TRUE),),
        owning_capability=CapabilityId.TAP,  # illegal: TAP cannot decide
    )
    pack = pack.model_copy(update={"decision_rules": pack.decision_rules + (bad_rule,)})
    result = GovernedWorkflowCompiler().compile(pack, approval=None, require_approval=False)
    assert not result.success
    assert any(d.code == "AUTHORITY_BOUNDARY_VIOLATION" for d in result.diagnostics)


def test_procurement_ir_has_no_boundary_violations(procurement_pack):
    ir = GovernedWorkflowCompiler().synthesize(procurement_pack)
    assert not B.check_ir(ir)
