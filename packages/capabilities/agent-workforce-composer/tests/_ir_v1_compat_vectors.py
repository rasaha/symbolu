"""Compatibility vectors for the Workflow IR v1 canonicalization ratchet.

Scope (ADR ``ADR_UGENCE_CANONICALIZATION_CONTRACT.md`` §9): these vectors pin the
canonical bytes that BOTH the Policy Workflow Compiler and the Agent Workforce
Composer must derive for the same ``workflow_ir.v1`` semantic value, under the
frozen ``WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION == "0.1.0"``.

They do **not** define a shared canonicalization contract, do not apply to Risk
Authority, Policy Authority, Cloud Scaling Controller or Producer Attestation,
and are not evidence that any other canonicalizer should converge.

Vector discipline
-----------------
* Every vector is built here, in reviewable Python — never loaded from a blob.
* ``VECTORS`` is returned in sorted-by-id order, so the corpus and the golden
  file are diffable and stable across runs and processes.
* ``CORPUS_VERSION`` labels the corpus. Bump it in the same commit as any vector
  change, and say in the ADR why the corpus moved.
* Vectors carry no wall-clock time, no filesystem path and no machine state.
"""
from __future__ import annotations

#: Label for this corpus. Bump on any vector addition, removal or edit.
CORPUS_VERSION = "workflow_ir_v1_compat.v1"

#: The canonicalization identity these vectors are pinned against.
PINNED_DIGEST_COMPILER_VERSION = "0.1.0"


def _ir_objects():
    """The live compiler ``workflow_ir.v1`` types. Imported lazily: this module
    is only ever loaded by tests, never by either distribution's source."""
    from ugence_policy_workflow_compiler.compiler.workflow_ir import (
        EdgeKind, NodeKind, WorkflowEdge, WorkflowIR, WorkflowNode,
    )
    from ugence_policy_workflow_compiler.models.common import (
        AuthorityDisposition, BlockBehavior, CapabilityId,
    )
    return dict(EdgeKind=EdgeKind, NodeKind=NodeKind, WorkflowEdge=WorkflowEdge,
                WorkflowIR=WorkflowIR, WorkflowNode=WorkflowNode,
                AuthorityDisposition=AuthorityDisposition,
                BlockBehavior=BlockBehavior, CapabilityId=CapabilityId)


def _reference_procurement_ir():
    """The ``workflow_ir.v1`` from the compiler's own reference procurement pack.

    Deterministic and clock-free: the IR carries no timestamp, and its node and
    edge ids are content-derived. This is the same artifact whose fingerprints the
    ADR §2 measurement covered, so the corpus is anchored to a real compile rather
    than to hand-built nodes alone.
    """
    from ugence_policy_workflow_compiler.compiler.compiler import compile_policy_pack
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture, build_procurement_policy_pack,
    )
    pack = build_procurement_policy_pack()
    result = compile_policy_pack(pack, approval=build_procurement_approval_fixture(pack))
    if not result.success or result.workflow_ir is None:
        raise RuntimeError(f"reference compile failed: {result.diagnostics}")
    return result.workflow_ir


def accepted_vectors():
    """Values BOTH canonicalizers must accept and encode to identical bytes.

    Returns ``[(vector_id, value), ...]`` sorted by ``vector_id``.
    """
    T = _ir_objects()
    NodeKind, EdgeKind = T["NodeKind"], T["EdgeKind"]
    WorkflowNode, WorkflowEdge, WorkflowIR = T["WorkflowNode"], T["WorkflowEdge"], T["WorkflowIR"]
    Disp, Block, Cap = T["AuthorityDisposition"], T["BlockBehavior"], T["CapabilityId"]

    node_full = WorkflowNode(
        node_id="node_approval_gate_000000000001", kind=NodeKind.APPROVAL_GATE,
        owning_capability=Cap.DECISION_AUTHORITY, authority_type="HUMAN_APPROVER",
        disposition=Disp.AUTHORITATIVE, public_contract_target="decision_authority.contract",
        input_object_ids=("obj_b", "obj_a"), output_contract="ApprovalOutcome",
        failure_behavior=Block.BLOCK, audit_requirements=("actor", "decided_at"),
        label="approve the requisition")
    node_defaults = WorkflowNode(
        node_id="node_terminal_outcome_000000000002", kind=NodeKind.TERMINAL_OUTCOME,
        owning_capability=Cap.COMPILER, disposition=Disp.ADVISORY)
    edge = WorkflowEdge(edge_id="edge_000000000003", kind=EdgeKind.ON_PASS,
                        source_id=node_full.node_id, target_id=node_defaults.node_id, order=0)
    ir = WorkflowIR(policy_pack_id="pack_reference", policy_pack_version=1,
                    nodes=(node_full, node_defaults), edges=(edge,),
                    referenced_capabilities=("compiler", "decision_authority"))
    ir_empty = WorkflowIR(policy_pack_id="pack_empty", policy_pack_version=0)
    ir_reference = _reference_procurement_ir()

    vectors = {
        # -- mapping semantics
        "map_key_ordering":        {"b": 1, "a": 2, "C": 3, "0": 4},
        "map_nested":              {"outer": {"z": {"y": 1}, "a": {"b": 2}}},
        "map_empty":               {},
        "map_unicode_keys":        {"Café": 1, "Café": 2},
        # -- sequence semantics
        "seq_list":                [1, 2, 3],
        "seq_tuple":               ("a", "b"),
        "seq_empty_list":          [],
        "seq_empty_tuple":         (),
        "seq_nested":              [[1, [2, [3]]], []],
        # -- scalars
        "scalar_bool":             {"t": True, "f": False},
        "scalar_int":              {"zero": 0, "neg": -7, "big": 10 ** 20},
        "scalar_none":             {"n": None},
        "scalar_str":              {"s": "approve"},
        "scalar_str_empty":        {"s": ""},
        # -- unicode: normalization-sensitive pairs must NOT be folded together
        "unicode_nfc":             {"s": "Café"},
        "unicode_nfd":             {"s": "Café"},
        "unicode_non_bmp":         {"s": "\U0001F512"},
        "unicode_control":         {"s": "a\tb\nc"},
        # -- enumerations (every enum reachable from workflow_ir.v1)
        "enum_node_kind":          NodeKind.APPROVAL_GATE,
        "enum_edge_kind":          EdgeKind.ON_FAIL,
        "enum_capability_id":      Cap.COMPILER,
        "enum_disposition":        Disp.ADVISORY,
        "enum_block_behavior":     Block.BLOCK,
        # -- pydantic projection through the documented normative mode
        "model_node_full":         node_full,
        "model_node_defaults":     node_defaults,
        "model_edge":              edge,
        "model_ir":                ir,
        "model_ir_empty":          ir_empty,
        # The REAL compiled reference IR -- the artifact whose fingerprints the
        # ADR §2 measurement covered. Synthetic nodes cannot stand in for the
        # node/edge shapes an actual compile produces.
        "model_ir_reference":      ir_reference,
        "preimage_reference_digest": {"nodes": list(ir_reference.nodes),
                                      "edges": list(ir_reference.edges)},
        "model_nested_in_map":     {"workflow_ir": ir, "release_metadata": None},
        "model_list_of_nodes":     [node_full, node_defaults],
        # -- the two digest preimages workflow_ir.v1 actually canonicalizes
        "preimage_logical_digest": {"nodes": list(ir.nodes), "edges": list(ir.edges)},
        "preimage_node_id":        {"kind": NodeKind.APPROVAL_GATE.value,
                                    "capability": Cap.DECISION_AUTHORITY.value,
                                    "inputs": ["obj_a", "obj_b"]},
        "preimage_edge_id":        {"kind": EdgeKind.ON_PASS.value,
                                    "source": node_full.node_id,
                                    "target": node_defaults.node_id},
        # -- accepted by BOTH canonicalizers though not reachable from a v1 field.
        #    Pinned so a change to either implementation's handling is visible.
        "outside_v1_float":        {"f": 1.5},
        "outside_v1_float_neg0":   {"f": -0.0},
        "outside_v1_set":          {"s": {"b", "a", "c"}},
        "outside_v1_frozenset":    {"s": frozenset({"y", "x"})},
    }
    return sorted(vectors.items())


def rejected_vectors():
    """Bare values BOTH canonicalizers must refuse.

    Rejection parity is asserted on the *class* of refusal, not the message:
    neither implementation publishes its exception text as contract.
    """
    from datetime import date, datetime, timezone
    from decimal import Decimal
    from uuid import UUID

    vectors = {
        "reject_bare_bytes":    b"\x01\x02",
        "reject_bare_complex":  1 + 2j,
        "reject_bare_date":     date(2026, 1, 2),
        "reject_bare_datetime": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "reject_bare_decimal":  Decimal("10.25"),
        "reject_bare_object":   object(),
        "reject_bare_uuid":     UUID(int=1),
    }
    return sorted(vectors.items())
