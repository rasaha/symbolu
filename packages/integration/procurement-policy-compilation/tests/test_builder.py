"""The Procurement artifact-to-pack mapping: deterministic, and silent where the
policy is silent."""

from __future__ import annotations

import pytest
from ugence_policy_workflow_compiler.api import (
    SCHEMA_VERSION_V2,
    ObjectType,
    compile_policy_pack,
    validate_policy_pack,
)
from ugence_policy_workflow_compiler.approval.records import (
    build_approval_record,
    compute_pack_digest,
)

import _projection as proj
from ugence_procurement_policy_compilation import (
    ProcurementArtifactError,
    artifact_from_projection,
    build_procurement_pack,
    procurement_pack_builder,
)


def _pack(projection=None):
    return build_procurement_pack(
        artifact_from_projection(projection or proj.FULL)
    )


# -- the mapping ---------------------------------------------------------------


def test_the_pack_is_policy_pack_v2_and_validates():
    pack = _pack()
    assert pack.schema_version == SCHEMA_VERSION_V2
    assert validate_policy_pack(pack).ok


def test_the_pack_compiles_with_a_human_approval():
    pack = _pack()
    approval = build_approval_record(
        approval_id="approval-1",
        pack=pack,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    result = compile_policy_pack(pack, approval)
    assert result.success, [d.message for d in result.validation_report.diagnostics]


def test_the_stated_bounds_reach_the_pack_verbatim():
    artifact = artifact_from_projection(proj.FULL)
    pack = build_procurement_pack(artifact)
    rule = pack.decision_rules[0]
    assert rule.conditions[0].fact_key == artifact.amount_fact_key
    assert rule.conditions[0].value == artifact.approval_threshold
    constraint = pack.action_constraints[0]
    assert constraint.max_value == artifact.hard_limit
    assert constraint.action_type == artifact.action_type


def test_declared_roles_become_an_ordered_path_with_segregation():
    pack = _pack()
    assert [s.role_label for s in pack.approval_steps] == ["requester", "approver"]
    assert [s.order for s in pack.approval_steps] == [1, 2]
    path = pack.approval_paths[0]
    assert path.step_ids == tuple(s.object_id for s in pack.approval_steps)
    # Distinct declared roles must be satisfied by distinct identities.
    assert path.segregation_pairs == (("requester", "approver"),)


def test_declared_semantics_become_a_declaration():
    pack = _pack()
    declaration = pack.semantic_declarations[0]
    assert declaration.object_type is ObjectType.SEMANTIC_DECLARATION
    assert declaration.data_classification_refs == ("classification.supplier_pii",)
    assert declaration.permission_intent_refs == ("permission.create_purchase_order",)
    assert declaration.required_tool_refs == ("tool.erp",)
    assert declaration.subject_object_id == pack.decision_rules[0].object_id


# -- nothing is invented -------------------------------------------------------


def test_what_the_artifact_omits_the_pack_omits():
    pack = _pack(proj.MINIMAL)
    assert pack.approval_paths == ()
    assert pack.approval_steps == ()
    assert pack.required_evidence == ()
    assert pack.prohibited_conditions == ()
    assert pack.semantic_declarations == ()
    # What it does state is still there.
    assert pack.decision_rules[0].conditions[0].value == 500
    assert pack.action_constraints[0].max_value == 5_000


def test_the_builder_never_authors_an_authoritative_source():
    # Ruling X1-B: on the authoritative path the reference is derived by the
    # composition root, never authored by a builder.
    assert _pack().authoritative_source is None
    assert _pack(proj.MINIMAL).authoritative_source is None


# -- determinism ---------------------------------------------------------------


def test_identical_artifacts_produce_identical_packs():
    first, second = _pack(), _pack()
    assert first.model_dump(mode="python") == second.model_dump(mode="python")
    assert compute_pack_digest(first) == compute_pack_digest(second)


def test_key_order_in_the_projection_does_not_matter():
    reversed_projection = dict(reversed(list(proj.FULL.items())))
    assert compute_pack_digest(_pack(reversed_projection)) == compute_pack_digest(_pack())


def test_a_changed_bound_changes_the_pack():
    altered = dict(proj.FULL, approval_threshold=2_000_000)
    assert compute_pack_digest(_pack(altered)) != compute_pack_digest(_pack())


# -- the parser fails closed ---------------------------------------------------


def test_an_unknown_key_is_refused_not_ignored():
    with pytest.raises(ProcurementArtifactError, match="silently dropped"):
        artifact_from_projection(dict(proj.FULL, escalation_policy="ignore me"))


def test_a_missing_required_key_is_refused():
    incomplete = {k: v for k, v in proj.FULL.items() if k != "hard_limit"}
    with pytest.raises(ProcurementArtifactError, match="does not state"):
        artifact_from_projection(incomplete)


def test_a_hard_limit_below_the_threshold_is_refused():
    with pytest.raises(ProcurementArtifactError, match="below the approval threshold"):
        artifact_from_projection(dict(proj.FULL, hard_limit=1))


def test_a_non_mapping_projection_is_refused():
    with pytest.raises(ProcurementArtifactError):
        artifact_from_projection(["not", "a", "mapping"])


# -- the builder callable ------------------------------------------------------


def test_the_builder_callable_accepts_a_projection_or_an_artifact():
    from_projection = procurement_pack_builder(proj.FULL)
    from_artifact = procurement_pack_builder(artifact_from_projection(proj.FULL))
    assert compute_pack_digest(from_projection) == compute_pack_digest(from_artifact)


def test_maturity_states_the_non_goals():
    from ugence_procurement_policy_compilation import version_info

    info = version_info().to_dict()
    assert info["procurement_pack_builder_implemented"] is True
    for never in ("authors_authoritative_source", "depends_on_policy_authority",
                  "infers_undeclared_policy", "runtime_execution_implemented",
                  "pilot_validated", "production_certified"):
        assert info[never] is False, never
