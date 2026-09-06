"""workflow_ir.v2 enrichment consumption of policy_pack.v2 declarations.

Declared, never inferred: a value the source policy states is carried verbatim with
EXPLICIT provenance; a value it omits stays unresolved and is never defaulted. A
v1-sourced graph declares nothing, so its fingerprint is unmoved.
"""

from __future__ import annotations

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.approval.records import build_approval_record
from ugence_policy_workflow_compiler.models.common import SCHEMA_VERSION_V2
from ugence_policy_workflow_compiler.models.declarations import (
    DeclaredContractRef,
    SemanticDeclaration,
)
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
from ugence_policy_workflow_compiler.semantics.contracts import DerivationClass

PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"


def _v1():
    pack = build_procurement_policy_pack()
    return pack, build_procurement_approval_fixture(pack)


def _v2(declaration):
    pack = build_procurement_policy_pack()
    v2_pack = pack.model_copy(
        update={"schema_version": SCHEMA_VERSION_V2, "semantic_declarations": (declaration,)}
    )
    approval = build_approval_record(
        approval_id="approval-declared",
        pack=v2_pack,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    return v2_pack, approval


def _declaration(pack, **kw):
    rule = pack.decision_rules[0]
    return SemanticDeclaration(
        object_id="decl-1",
        name="declaration",
        subject_object_id=rule.object_id,
        provenance_refs=rule.provenance_refs,
        **kw,
    )


def _full_declaration(pack):
    return _declaration(
        pack,
        data_classification_refs=("classification.customer_pii",),
        permission_intent_refs=("permission.write",),
        required_tool_refs=("tool.salesforce",),
    )


# -- v1 is unmoved -------------------------------------------------------------


def test_v1_sourced_enrichment_is_unchanged():
    pack, approval = _v1()
    v2 = compile_workflow_v2(pack, approval)
    assert v2.workflow_fingerprint == PINNED_V2_FINGERPRINT
    assert v2.declared_value_provenance == ()
    for semantics in v2.node_semantics:
        assert semantics.data_classification_refs == ()
        assert semantics.permission_intent_refs == ()
        assert semantics.required_tool_refs == ()


def test_an_empty_declaration_collection_omits_the_digest_key():
    # The key is included only when something was declared; adding it
    # unconditionally would move every existing v2 fingerprint.
    pack, approval = _v1()
    v2 = compile_workflow_v2(pack, approval)
    assert v2.logical_digest() == PINNED_V2_FINGERPRINT


# -- declared values are carried ----------------------------------------------


def test_declared_values_reach_the_declaring_node():
    base = build_procurement_policy_pack()
    pack, approval = _v2(_full_declaration(base))
    v2 = compile_workflow_v2(pack, approval)
    carrying = [s for s in v2.node_semantics if s.data_classification_refs]
    assert carrying, "the declaration must reach the nodes built from its subject"
    for semantics in carrying:
        assert semantics.data_classification_refs == ("classification.customer_pii",)
        assert semantics.permission_intent_refs == ("permission.write",)
        assert semantics.required_tool_refs == ("tool.salesforce",)


def test_declared_values_carry_explicit_provenance():
    base = build_procurement_policy_pack()
    pack, approval = _v2(_full_declaration(base))
    v2 = compile_workflow_v2(pack, approval)
    assert v2.declared_value_provenance
    for entry in v2.declared_value_provenance:
        assert entry.provenance.derivation_class is DerivationClass.EXPLICIT
        assert entry.provenance.compiler_rule == "source_declared_semantics"
        assert entry.provenance.source_refs == ("decl-1",)
        assert entry.declared_values
    fields = {entry.field_name for entry in v2.declared_value_provenance}
    assert fields == {
        "data_classification_refs",
        "permission_intent_refs",
        "required_tool_refs",
    }


def test_a_declared_contract_version_is_carried_and_marked_explicit():
    base = build_procurement_policy_pack()
    ir = api.compile_policy_pack(base, build_procurement_approval_fixture(base)).workflow_ir
    rule = base.decision_rules[0]
    contract = next(
        n.output_contract
        for n in ir.nodes
        if rule.object_id in n.input_object_ids and n.output_contract
    )
    pack, approval = _v2(
        _declaration(
            base,
            output_contract_refs=(
                DeclaredContractRef(contract_id=contract, contract_data_version="7"),
            ),
        )
    )
    v2 = compile_workflow_v2(pack, approval)
    versioned = [
        o.contract_ref
        for s in v2.node_semantics
        for o in s.produced_output_contract_refs
        if o.contract_ref.contract_data_version
    ]
    assert versioned, "a declared contract version must be carried"
    assert versioned[0].contract_id == contract
    assert versioned[0].contract_data_version == "7"
    assert versioned[0].provenance.derivation_class is DerivationClass.EXPLICIT
    assert versioned[0].provenance.compiler_rule == "source_declared_contract_version"


# -- absent is unresolved, never defaulted ------------------------------------


def test_an_undeclared_field_stays_empty_with_no_provenance_entry():
    base = build_procurement_policy_pack()
    # Declares only a classification; the other two fields are left unstated.
    pack, approval = _v2(
        _declaration(base, data_classification_refs=("classification.customer_pii",))
    )
    v2 = compile_workflow_v2(pack, approval)
    fields = {entry.field_name for entry in v2.declared_value_provenance}
    assert fields == {"data_classification_refs"}
    for semantics in v2.node_semantics:
        assert semantics.permission_intent_refs == ()
        assert semantics.required_tool_refs == ()


def test_an_undeclared_contract_version_is_never_inferred():
    base = build_procurement_policy_pack()
    pack, approval = _v2(_full_declaration(base))
    v2 = compile_workflow_v2(pack, approval)
    for semantics in v2.node_semantics:
        for output in semantics.produced_output_contract_refs:
            assert output.contract_ref.contract_data_version == ""
            assert output.contract_ref.provenance.derivation_class is (
                DerivationClass.DERIVED_FROM_CONTRACT
            )


# -- determinism ---------------------------------------------------------------


def test_enrichment_is_deterministic_and_order_free():
    base = build_procurement_policy_pack()
    pack, approval = _v2(_full_declaration(base))
    first = compile_workflow_v2(pack, approval)
    second = compile_workflow_v2(pack, approval)
    assert first.workflow_fingerprint == second.workflow_fingerprint
    assert first.model_dump(mode="python") == second.model_dump(mode="python")
    # Declaring content is new content, so a new fingerprint — not a moved one.
    assert first.workflow_fingerprint != PINNED_V2_FINGERPRINT


def test_maturity_reports_consumption():
    info = api.version_info().to_dict()
    assert info["policy_pack_v2_supported"] is True
    assert info["source_declared_semantics_implemented"] is True
    for gate in ("runtime_execution_implemented", "pilot_validated", "production_certified"):
        assert info[gate] is False, gate
