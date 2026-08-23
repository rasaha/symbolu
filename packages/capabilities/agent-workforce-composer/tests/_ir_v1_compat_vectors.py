"""Compatibility vectors for the Workflow IR v1 canonicalization ratchet.

Scope (ADR ``ADR_UGENCE_CANONICALIZATION_CONTRACT.md`` §9): these vectors pin the
canonical bytes that BOTH the Policy Workflow Compiler and the Agent Workforce
Composer must derive for the same ``workflow_ir.v1`` semantic value, under the
frozen ``WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION == "0.1.0"``.

They do **not** define a shared canonicalization contract, do not apply to Risk
Authority, Policy Authority, Cloud Scaling Controller or Producer Attestation,
and are not evidence that any other canonicalizer should converge.

Three vector classes (ADR §9 `[R]`)
-----------------------------------
``NORMATIVE_V1_REACHABLE``
    Value classes structurally reachable through the ratified ``workflow_ir.v1``
    schema or one of its three documented digest preimages. **Only these define
    the frozen cross-component byte and fingerprint contract**, and only these are
    anchored in the golden fixture.

``STRUCTURAL_EXCLUSION``
    Values the v1 schema must keep *out* of a valid model. Their refusal is not a
    published v1 canonicalization guarantee, so they anchor no golden; they exist
    to demonstrate the exclusion holds.

``NON_NORMATIVE_DIAGNOSTIC``
    Values both canonicalizers happen to accept that are **not** reachable from
    v1 -- ``float``, ``-0.0``, ``set``, ``frozenset``, ``bool``, ``None``. They are
    observations, never obligations. They carry no golden and cannot fail the v1
    compatibility gate: an incidental out-of-domain behaviour change must not read
    as a v1 contract break, and test coverage must never be mistaken for contract
    scope.

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
#: v2 -- ADR §9 classification ruling: the golden gate is narrowed to
#: NORMATIVE_V1_REACHABLE vectors only. float/-0.0/set/frozenset/bool/None moved to
#: non-normative diagnostics, and ``model_nested_in_map`` dropped its unreachable
#: ``None`` so it stays normative. No retained normative digest moved.
CORPUS_VERSION = "workflow_ir_v1_compat.v2"

#: The canonicalization identity these vectors are pinned against.
PINNED_DIGEST_COMPILER_VERSION = "0.1.0"


#: The three digest preimages ``workflow_ir.v1`` actually canonicalizes, as built
#: by ``WorkflowIR.logical_digest``, ``make_node_id`` and ``make_edge_id``. They
#: introduce ``dict`` (string keys) into the reachable domain; the v1 models
#: themselves declare no mapping field.
PREIMAGE_SHAPES = ("logical_digest", "node_id", "edge_id")


def reachable_value_types():
    """The set of Python types reachable through the v1 schema + its preimages.

    Derived from the live models, never hand-listed, so a schema change moves this
    set instead of silently contradicting it.
    """
    import enum
    import typing

    from pydantic import BaseModel

    T = _ir_objects()
    found = {dict, list, tuple}          # contributed by the preimages and Tuple fields

    def _walk_annotation(annotation, seen):
        origin = typing.get_origin(annotation)
        if origin is not None:
            for arg in typing.get_args(annotation):
                if arg is not Ellipsis:
                    _walk_annotation(arg, seen)
            return
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            _walk_model(annotation, seen)
            return
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            found.add(enum.Enum)
            return
        if isinstance(annotation, type):
            found.add(annotation)

    def _walk_model(model, seen):
        if model in seen:
            return
        seen.add(model)
        found.add(BaseModel)
        for field in model.model_fields.values():
            _walk_annotation(field.annotation, seen)

    seen: set = set()
    for model in (T["WorkflowNode"], T["WorkflowEdge"], T["WorkflowIR"]):
        _walk_model(model, seen)
    return found


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


def normative_vectors():
    """``NORMATIVE_V1_REACHABLE`` -- the frozen cross-component contract.

    Values BOTH canonicalizers must accept and encode to identical bytes, and which
    the golden fixture anchors. Every one is structurally reachable through the v1
    schema or one of its three documented digest preimages.

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
        # -- scalars (bool and None are NOT v1-reachable; see diagnostic_vectors)
        "scalar_int":              {"zero": 0, "neg": -7, "big": 10 ** 20},
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
        "model_nested_in_map":     {"workflow_ir": ir, "release_label": "reference"},
        "model_list_of_nodes":     [node_full, node_defaults],
        # -- the two digest preimages workflow_ir.v1 actually canonicalizes
        "preimage_logical_digest": {"nodes": list(ir.nodes), "edges": list(ir.edges)},
        "preimage_node_id":        {"kind": NodeKind.APPROVAL_GATE.value,
                                    "capability": Cap.DECISION_AUTHORITY.value,
                                    "inputs": ["obj_a", "obj_b"]},
        "preimage_edge_id":        {"kind": EdgeKind.ON_PASS.value,
                                    "source": node_full.node_id,
                                    "target": node_defaults.node_id},
    }
    return sorted(vectors.items())


def diagnostic_vectors():
    """``NON_NORMATIVE_DIAGNOSTIC`` -- accepted by both, unreachable from v1.

    Observations, not obligations. No golden anchors these, and no v1 compatibility
    gate may fail because one of them later changes: they are outside the domain
    the ADR §9 ruling makes binding.
    """
    vectors = {
        "diagnostic_bool":      {"t": True, "f": False},
        "diagnostic_float":     {"f": 1.5},
        "diagnostic_float_neg0": {"f": -0.0},
        "diagnostic_frozenset": {"s": frozenset({"y", "x"})},
        "diagnostic_none":      {"n": None},
        "diagnostic_set":       {"s": {"b", "a", "c"}},
    }
    return sorted(vectors.items())


def structural_exclusion_vectors():
    """``STRUCTURAL_EXCLUSION`` -- values a valid ``workflow_ir.v1`` model must not
    contain, checked as bare values.

    Their refusal is **not** a published v1 canonicalization guarantee, so they
    anchor no golden and define no frozen contract. They demonstrate that the
    exclusion currently holds. Parity is asserted on the *class* of refusal, never
    the message: neither implementation publishes its exception text as contract.
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


#: Every vector id, mapped to its class. Audited against the live schema by
#: ``test_vector_classification_matches_the_live_schema``: a normative vector whose
#: runtime value tree uses a type the schema cannot reach is a failure, so this map
#: cannot silently drift from what v1 actually admits.
def vector_classes():
    return {
        **{vid: "NORMATIVE_V1_REACHABLE" for vid, _ in normative_vectors()},
        **{vid: "NON_NORMATIVE_DIAGNOSTIC" for vid, _ in diagnostic_vectors()},
        **{vid: "STRUCTURAL_EXCLUSION" for vid, _ in structural_exclusion_vectors()},
    }
