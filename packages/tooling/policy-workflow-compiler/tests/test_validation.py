"""Validation-engine tests: every rule produces the right structured diagnostic."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import (
    ActionConstraint,
    ApprovalPath,
    ApprovalStep,
    AuthorityRequirement,
    AuthorityType,
    ConstraintKind,
    ConnectorMapping,
    DecisionRule,
    ExceptionRule,
    OverrideRule,
    PolicyPack,
    PolicyPackStatus,
    Severity,
    validate_policy_pack,
)

from _builders import build_full_synthetic_pack


def _codes(report):
    return {d.code for d in report.diagnostics}


def test_valid_pack_passes(synthetic_pack):
    report = validate_policy_pack(synthetic_pack)
    assert report.ok, [d.message for d in report.blocking]


def test_duplicate_object_id():
    a1 = AuthorityRequirement(object_id="dup", name="a", decision_scope="x", provenance_refs=("s",))
    a2 = AuthorityRequirement(object_id="dup", name="b", decision_scope="y", provenance_refs=("s",))
    pack = PolicyPack(pack_id="p", name="n", authority_requirements=(a1, a2))
    report = validate_policy_pack(pack)
    assert "DUPLICATE_OBJECT_ID" in _codes(report)
    assert not report.ok


def test_dangling_reference():
    rule = DecisionRule(object_id="r", name="r", provenance_refs=("s",),
                        related_object_ids=("nonexistent",))
    pack = PolicyPack(pack_id="p", name="n", decision_rules=(rule,))
    report = validate_policy_pack(pack)
    assert "DANGLING_REFERENCE" in _codes(report)


def test_missing_provenance_is_review_required():
    rule = DecisionRule(object_id="r", name="r")  # no provenance
    pack = PolicyPack(pack_id="p", name="n", decision_rules=(rule,))
    report = validate_policy_pack(pack)
    diags = [d for d in report.diagnostics if d.code == "MISSING_PROVENANCE"]
    assert diags and diags[0].severity is Severity.REVIEW_REQUIRED
    assert not report.ok  # REVIEW_REQUIRED blocks


def test_action_constraint_without_authority():
    c = ActionConstraint(object_id="c", name="c", provenance_refs=("s",),
                         action_type="DO", parameter="amount",
                         kind=ConstraintKind.HARD_LIMIT, max_value=1)
    pack = PolicyPack(pack_id="p", name="n", action_constraints=(c,))
    report = validate_policy_pack(pack)
    assert "ACTION_CONSTRAINT_WITHOUT_AUTHORITY" in _codes(report)


def test_exception_without_decision_rule():
    exc = ExceptionRule(object_id="e", name="e", provenance_refs=("s",),
                        decision_rule_id="ghost")
    pack = PolicyPack(pack_id="p", name="n", exception_rules=(exc,))
    report = validate_policy_pack(pack)
    assert "EXCEPTION_WITHOUT_DECISION_RULE" in _codes(report)


def test_override_without_decision_rule():
    ovr = OverrideRule(object_id="o", name="o", provenance_refs=("s",),
                       decision_rule_id="ghost")
    pack = PolicyPack(pack_id="p", name="n", override_rules=(ovr,))
    report = validate_policy_pack(pack)
    assert "OVERRIDE_WITHOUT_DECISION_RULE" in _codes(report)


def test_approval_path_missing_steps():
    path = ApprovalPath(object_id="path", name="p", provenance_refs=("s",), step_ids=())
    pack = PolicyPack(pack_id="p", name="n", approval_paths=(path,))
    report = validate_policy_pack(pack)
    assert "APPROVAL_PATH_MISSING_STEPS" in _codes(report)


def test_impossible_approval_ordering():
    steps = (
        ApprovalStep(object_id="s1", name="s1", provenance_refs=("s",), order=1,
                     authority_requirement_id="a", role_label="x"),
        ApprovalStep(object_id="s2", name="s2", provenance_refs=("s",), order=1,
                     authority_requirement_id="a", role_label="y"),
    )
    path = ApprovalPath(object_id="path", name="p", provenance_refs=("s",),
                        step_ids=("s1", "s2"))
    pack = PolicyPack(pack_id="p", name="n", approval_paths=(path,), approval_steps=steps)
    report = validate_policy_pack(pack)
    assert "IMPOSSIBLE_APPROVAL_ORDERING" in _codes(report)


def test_segregation_contradiction():
    steps = (
        ApprovalStep(object_id="s1", name="s1", provenance_refs=("s",), order=1,
                     authority_requirement_id="a", role_label="x"),
    )
    path = ApprovalPath(object_id="path", name="p", provenance_refs=("s",),
                        step_ids=("s1",), segregation_pairs=(("x", "x"),))
    pack = PolicyPack(pack_id="p", name="n", approval_paths=(path,), approval_steps=steps)
    report = validate_policy_pack(pack)
    assert "SEGREGATION_OF_DUTIES_CONTRADICTION" in _codes(report)


def test_embedded_secret_rejected():
    # A secret-shaped value smuggled into a normal field is flagged.
    conn = ConnectorMapping(
        object_id="c", name="c", provenance_refs=("s",),
        policy_concept="x", target_system="SYS", target_field="f",
        credential_handle="AKIAIOSFODNN7EXAMPLE",
    )
    pack = PolicyPack(pack_id="p", name="n", connector_mappings=(conn,))
    report = validate_policy_pack(pack)
    assert "EMBEDDED_SECRET" in _codes(report)


def test_clean_handle_not_flagged():
    conn = ConnectorMapping(
        object_id="c", name="c", provenance_refs=("s",),
        policy_concept="x", target_system="SYS", target_field="f",
        credential_handle="vault://procurement/supplier-token",
    )
    pack = PolicyPack(pack_id="p", name="n", connector_mappings=(conn,))
    report = validate_policy_pack(pack)
    assert "EMBEDDED_SECRET" not in _codes(report)


def test_unsupported_schema_is_fatal():
    pack = PolicyPack(pack_id="p", name="n", schema_version="policy_pack.v999")
    report = validate_policy_pack(pack)
    assert "UNSUPPORTED_SCHEMA_VERSION" in _codes(report)
    assert any(d.severity is Severity.FATAL for d in report.diagnostics)
    assert not report.ok


def test_severity_not_reclassified():
    # A REVIEW_REQUIRED (missing provenance) stays REVIEW_REQUIRED, never becomes ERROR.
    rule = DecisionRule(object_id="r", name="r")
    pack = PolicyPack(pack_id="p", name="n", decision_rules=(rule,))
    report = validate_policy_pack(pack)
    sev = {d.code: d.severity for d in report.diagnostics}
    assert sev.get("MISSING_PROVENANCE") is Severity.REVIEW_REQUIRED
