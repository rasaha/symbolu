"""Compiler-contract fidelity (§28 P1-A3): the adapter consumes the LIVE
``ugence_policy_workflow_compiler`` ``WorkflowIR`` (workflow_ir.v1) without
inventing a parallel workflow representation.

Skips cleanly when the optional ``compiler-reference`` extra is not installed —
the core adapter/eligibility engine never depend on the compiler at runtime.
"""
from __future__ import annotations

import pytest

pytest.importorskip("ugence_policy_workflow_compiler")

from ugence_agent_workforce_composer.adapter import adapt_compiled_workflow  # noqa: E402
from ugence_agent_workforce_composer.canonical import digest, to_canonical_obj  # noqa: E402
from ugence_agent_workforce_composer.contracts import NodeDisposition  # noqa: E402


def _real_ir_document():
    from ugence_policy_workflow_compiler.compiler.workflow_ir import (
        NodeKind, WorkflowIR, WorkflowNode,
    )
    from ugence_policy_workflow_compiler.models.common import (
        AuthorityDisposition, CapabilityId,
    )

    nodes = (
        WorkflowNode(node_id="n_evidence", kind=NodeKind.EVIDENCE_REQUIREMENT,
                     owning_capability=CapabilityId.COMPILER,
                     disposition=AuthorityDisposition.ADVISORY, label="collect evidence"),
        WorkflowNode(node_id="n_approve", kind=NodeKind.APPROVAL_GATE,
                     owning_capability=CapabilityId.DECISION_AUTHORITY,
                     disposition=AuthorityDisposition.AUTHORITATIVE, authority_type="HUMAN_APPROVER"),
        WorkflowNode(node_id="n_action", kind=NodeKind.ACTION_CONSTRAINT,
                     owning_capability=CapabilityId.ACTION_GATE,
                     disposition=AuthorityDisposition.AUTHORITATIVE),
        WorkflowNode(node_id="n_terminal", kind=NodeKind.TERMINAL_OUTCOME,
                     owning_capability=CapabilityId.COMPILER,
                     disposition=AuthorityDisposition.ADVISORY),
    )
    ir = WorkflowIR(policy_pack_id="ref_pack", policy_pack_version=1, nodes=nodes)
    ir_dict = ir.model_dump(mode="json")
    return {"workflow_ir": ir_dict, "structural_digest": digest(to_canonical_obj(ir_dict)),
            "release_metadata": {"synthetic": True}}


def test_adapter_consumes_live_compiler_ir():
    result = adapt_compiled_workflow(_real_ir_document())
    assert result.ok
    assert result.source_contract_version == "workflow_ir.v1"
    assert result.accounting_holds()
    d = {nd.node_id: nd.disposition for nd in result.node_dispositions}
    # advisory compiler evidence -> agent role
    assert d["n_evidence"] is NodeDisposition.AI_AGENT_ELIGIBLE
    # authoritative governance nodes never become agent work
    assert d["n_approve"] is NodeDisposition.HUMAN_AUTHORITY_REQUIRED
    assert d["n_action"] is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP
    assert d["n_terminal"] is NodeDisposition.NO_AI_AGENT_REQUIRED


def test_awc_node_kind_values_match_compiler():
    from ugence_policy_workflow_compiler.compiler.workflow_ir import NodeKind as CNodeKind
    from ugence_agent_workforce_composer.contracts import NodeKind as ANodeKind
    assert {k.value for k in CNodeKind} == {k.value for k in ANodeKind}
