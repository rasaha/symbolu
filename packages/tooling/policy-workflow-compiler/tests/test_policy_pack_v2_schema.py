"""policy_pack.v2 step two — the schema gate and the sidecar carriage.

The whole point is asymmetry: a v2 pack carries source-declared semantics in its
digest, while every v1 pack, digest and approval is byte-identical to what it was
before v2 existed.
"""

from __future__ import annotations

import pytest

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.approval.records import (
    build_approval_record,
    compute_pack_digest,
)
from ugence_policy_workflow_compiler.diff.change_impact import (
    APPROVAL_SENSITIVE_OBJECT_TYPES,
)
from ugence_policy_workflow_compiler.diff.structural_diff import diff_policy_packs
from ugence_policy_workflow_compiler.models.common import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V2,
    SUPPORTED_SCHEMA_VERSIONS,
    ObjectType,
)
from ugence_policy_workflow_compiler.validation.errors import Severity
from ugence_policy_workflow_compiler.models.declarations import (
    AuthoritativeSourceRef,
    DeclaredContractRef,
    SemanticDeclaration,
)
from ugence_policy_workflow_compiler.models.pack_view import (
    V2_ONLY_PACK_FIELDS,
    canonical_pack_view,
)
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
from ugence_policy_workflow_compiler.validation.provenance import (
    check_schema_declarations,
)

PINNED_PACK_DIGEST = "sha256:28eedf60892bc1b3e9f8c15c56d43b0aa353659c8158a793f94168a81de98b14"
PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V1_IR_DIGEST = "sha256:169ad24c09e45ac7176a75a2708ff4687085f2f8f878990862542df0c20ca1e1"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"


def _pack():
    pack = build_procurement_policy_pack()
    return pack, build_procurement_approval_fixture(pack)


def _declaration(pack, object_id=None, decl_id="decl-1", **kw):
    subject = object_id or pack.decision_rules[0].object_id
    return SemanticDeclaration(
        object_id=decl_id,
        name=f"declaration {decl_id}",
        subject_object_id=subject,
        provenance_refs=pack.decision_rules[0].provenance_refs,
        **kw,
    )


def _v2_pack(pack, declarations=None, source=None):
    return pack.model_copy(
        update={
            "schema_version": SCHEMA_VERSION_V2,
            "semantic_declarations": declarations
            if declarations is not None
            else (
                _declaration(
                    pack,
                    data_classification_refs=("classification.customer_pii",),
                    permission_intent_refs=("permission.write",),
                    required_tool_refs=("tool.salesforce",),
                    input_contract_refs=(
                        DeclaredContractRef(contract_id="contract.purchase", contract_data_version="3"),
                    ),
                ),
            ),
            "authoritative_source": source,
        }
    )


def _source_ref():
    return AuthoritativeSourceRef(
        policy_family="procurement",
        policy_id="policy.purchase_approval",
        policy_version="4",
        content_digest="sha256:" + "a" * 64,
        scope="global",
        record_id="rec-1",
        policy_body_digest="sha256:" + "b" * 64,
        issuing_authority_id="authority.policy",
        resolved_as_of="2026-09-06T00:00:00Z",
    )


# -- the schema itself ---------------------------------------------------------


def test_both_schema_versions_are_supported():
    assert SUPPORTED_SCHEMA_VERSIONS == (SCHEMA_VERSION, SCHEMA_VERSION_V2)


def test_the_v2_only_field_list_is_explicit():
    # Pruning by emptiness would silently drop a declared-but-empty value.
    assert V2_ONLY_PACK_FIELDS == {"semantic_declarations", "authoritative_source"}


# -- v1 is untouched -----------------------------------------------------------


def test_v1_canonical_view_carries_no_v2_key():
    pack, _ = _pack()
    view = canonical_pack_view(pack)
    for field in V2_ONLY_PACK_FIELDS:
        assert field not in view


def test_every_v1_digest_is_byte_identical():
    pack, approval = _pack()
    assert compute_pack_digest(pack) == PINNED_PACK_DIGEST
    result = api.compile_policy_pack(pack, approval)
    assert result.success
    assert result.logical_digest == PINNED_V1_RELEASE_DIGEST
    assert result.workflow_ir.logical_digest() == PINNED_V1_IR_DIGEST
    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_the_existing_approval_still_binds_and_compiles():
    pack, approval = _pack()
    assert approval.policy_pack_digest == compute_pack_digest(pack)
    assert api.compile_policy_pack(pack, approval).success


# -- v2 carries its declarations ----------------------------------------------


def test_v2_pack_carries_declarations_in_its_canonical_view():
    pack, _ = _pack()
    v2 = _v2_pack(pack, source=_source_ref())
    view = canonical_pack_view(v2)
    assert view["semantic_declarations"], "declared semantics must be in the digest"
    assert view["authoritative_source"] is not None
    assert compute_pack_digest(v2) != PINNED_PACK_DIGEST


def test_v2_pack_round_trips_through_canonical_json():
    from ugence_policy_workflow_compiler.models.policy_pack import PolicyPack
    from ugence_policy_workflow_compiler.serialization import canonical_json

    pack, _ = _pack()
    v2 = _v2_pack(pack, source=_source_ref())
    restored = PolicyPack.model_validate(
        canonical_json.loads(canonical_json.dumps_pretty(v2.model_dump(mode="python")))
    )
    assert restored.schema_version == SCHEMA_VERSION_V2
    assert restored.semantic_declarations == v2.semantic_declarations
    assert restored.authoritative_source == v2.authoritative_source
    assert compute_pack_digest(restored) == compute_pack_digest(v2)


def test_v2_pack_validates_and_compiles():
    pack, _ = _pack()
    v2 = _v2_pack(pack, source=_source_ref())
    approval = build_approval_record(
        approval_id="approval-v2",
        pack=v2,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    result = api.compile_policy_pack(v2, approval)
    assert result.success, [d.message for d in result.validation_report.diagnostics]
    # New content, so a new digest — not a moved one.
    assert result.logical_digest != PINNED_V1_RELEASE_DIGEST


def test_declarations_are_addressable_objects():
    pack, _ = _pack()
    v2 = _v2_pack(pack)
    index = v2.object_index()
    assert "decl-1" in index
    assert index["decl-1"].object_type is ObjectType.SEMANTIC_DECLARATION


# -- fail closed ---------------------------------------------------------------


def test_v2_content_in_a_v1_pack_is_refused_not_pruned():
    pack, approval = _pack()
    smuggled = pack.model_copy(update={"semantic_declarations": (_declaration(pack),)})
    assert smuggled.schema_version == SCHEMA_VERSION
    diags = check_schema_declarations(smuggled)
    assert [d.code for d in diags] == ["V2_FIELD_IN_V1_PACK"]
    assert diags[0].severity is Severity.FATAL
    assert api.compile_policy_pack(smuggled, approval).success is False


def test_dangling_declaration_subject_is_refused():
    pack, _ = _pack()
    v2 = _v2_pack(pack, declarations=(_declaration(pack, object_id="does.not.exist"),))
    assert "DANGLING_DECLARATION_SUBJECT" in {d.code for d in check_schema_declarations(v2)}


def test_duplicate_declaration_subject_is_refused():
    pack, _ = _pack()
    v2 = _v2_pack(
        pack,
        declarations=(_declaration(pack, decl_id="d1"), _declaration(pack, decl_id="d2")),
    )
    assert "DUPLICATE_DECLARATION_SUBJECT" in {d.code for d in check_schema_declarations(v2)}


def test_malformed_contract_reference_is_refused():
    pack, _ = _pack()
    with pytest.raises(Exception):
        # An empty contract id cannot even be constructed; the model refuses first.
        DeclaredContractRef(contract_id="")


def test_unsupported_schema_still_fails_closed():
    pack, approval = _pack()
    bogus = pack.model_copy(update={"schema_version": "policy_pack.v9"})
    result = api.compile_policy_pack(bogus, approval)
    assert result.success is False
    assert "UNSUPPORTED_SCHEMA_VERSION" in {
        d.code for d in result.validation_report.diagnostics
    }


# -- ruling V2-B ---------------------------------------------------------------


def test_a_changed_declaration_routes_to_review():
    pack, _ = _pack()
    old = _v2_pack(pack)
    new = _v2_pack(
        pack,
        declarations=(
            _declaration(pack, data_classification_refs=("classification.customer_pii",)),
        ),
    )
    assert ObjectType.SEMANTIC_DECLARATION in APPROVAL_SENSITIVE_OBJECT_TYPES
    diff = diff_policy_packs(old, new)
    assert diff.has_changes
    assert diff.impact.approval_re_review_required is True


def test_maturity_reports_v2_honestly():
    info = api.version_info().to_dict()
    assert info["policy_pack_v2_supported"] is True
    # Enrichment does not read declarations yet; the gate says so.
    assert info["source_declared_semantics_implemented"] is False
    for gate in ("runtime_execution_implemented", "pilot_validated", "production_certified"):
        assert info[gate] is False, gate
