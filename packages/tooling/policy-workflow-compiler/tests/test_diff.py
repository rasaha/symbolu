"""Structural-diff tests: added/removed/changed classification + impact."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import (
    AuthorityRequirement,
    AuthorityType,
    ChangeType,
    ConstraintKind,
    diff_policy_packs,
)

from _builders import build_full_synthetic_pack


def test_no_change_self_diff(synthetic_pack):
    d = diff_policy_packs(synthetic_pack, synthetic_pack)
    assert not d.has_changes


def test_object_added():
    old = build_full_synthetic_pack()
    extra = AuthorityRequirement(
        object_id="auth.2", name="new", provenance_refs=("src.test",),
        decision_scope="y", authority_type=AuthorityType.COMMITTEE,
    )
    new = old.model_copy(update={"authority_requirements": old.authority_requirements + (extra,)})
    d = diff_policy_packs(old, new)
    assert any(c.object_id == "auth.2" and ChangeType.OBJECT_ADDED.value in c.change_types
               for c in d.added)


def test_object_removed():
    new = build_full_synthetic_pack()
    old = new.model_copy(
        update={"authority_requirements": new.authority_requirements + (
            AuthorityRequirement(object_id="auth.gone", name="g", provenance_refs=("src.test",),
                                 decision_scope="z"),
        )}
    )
    d = diff_policy_packs(old, new)
    assert any(c.object_id == "auth.gone" for c in d.removed)


def test_authority_changed():
    old = build_full_synthetic_pack()
    changed_auth = old.authority_requirements[0].model_copy(update={"required_role": "senior"})
    new = old.model_copy(update={"authority_requirements": (changed_auth,)})
    d = diff_policy_packs(old, new)
    changed = {c.object_id: c for c in d.changed}
    assert "auth.1" in changed
    assert ChangeType.AUTHORITY_CHANGED.value in changed["auth.1"].change_types
    assert d.impact.approval_re_review_required


def test_action_constraint_changed():
    old = build_full_synthetic_pack()
    ac = old.action_constraints[0].model_copy(update={"max_value": 999})
    new = old.model_copy(update={"action_constraints": (ac,)})
    d = diff_policy_packs(old, new)
    changed = {c.object_id: c for c in d.changed}
    assert ChangeType.ACTION_CONSTRAINT_CHANGED.value in changed["act.1"].change_types


def test_provenance_changed():
    old = build_full_synthetic_pack()
    rule = old.decision_rules[0].model_copy(update={"provenance_refs": ("src.test", "src.extra")})
    new = old.model_copy(update={"decision_rules": (rule,)})
    d = diff_policy_packs(old, new)
    changed = {c.object_id: c for c in d.changed}
    assert ChangeType.PROVENANCE_CHANGED.value in changed["rule.1"].change_types


def test_impact_summary_nodes_and_tests():
    old = build_full_synthetic_pack()
    ac = old.action_constraints[0].model_copy(update={"max_value": 42})
    new = old.model_copy(update={"action_constraints": (ac,)})
    d = diff_policy_packs(old, new)
    assert "act.1" in d.impact.workflow_nodes_affected
    assert "act.1" in d.impact.assurance_tests_affected
