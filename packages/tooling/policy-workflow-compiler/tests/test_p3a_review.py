"""PWC-P3A — governed diff-driven review: routing, the fail-closed gate, and the
boundary guarantees that keep every existing digest byte-identical.

Rulings under test:
* P3A-1 REVIEW_ENFORCEMENT = BLOCKING — unsatisfied requirements refuse.
* P3A-2 REVIEWER_IDENTITY = OPAQUE_REFERENCE — no directory import or resolution.
* The non-weakening invariant — the review gate never rescues a failed approval.
"""

from __future__ import annotations

import pytest

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.approval.records import (
    COMPILER_PRINCIPAL,
    compute_pack_digest,
)
from ugence_policy_workflow_compiler.models.approvals import ApprovalDecision
from ugence_policy_workflow_compiler.models.authority import ApprovalPath, ApprovalStep
from ugence_policy_workflow_compiler.models.common import ObjectType
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.review import (
    REVIEW_ENFORCEMENT,
    REVIEWER_IDENTITY,
    ReviewCode,
    ReviewDisposition,
    ReviewLedger,
    check_review,
    derive_review_requirement,
)

PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V1_IR_DIGEST = "sha256:169ad24c09e45ac7176a75a2708ff4687085f2f8f878990862542df0c20ca1e1"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"
PINNED_PACK_DIGEST = "sha256:28eedf60892bc1b3e9f8c15c56d43b0aa353659c8158a793f94168a81de98b14"


def _pack():
    pack = build_procurement_policy_pack()
    return pack, build_procurement_approval_fixture(pack)


def _mutate_decision_rule(pack):
    """Change one approval-sensitive object — a decision rule's threshold."""
    rules = list(pack.decision_rules)
    assert rules, "the reference pack must declare a decision rule"
    changed = rules[0].model_copy(update={"description": "threshold revised"})
    return pack.model_copy(update={"decision_rules": (changed,) + tuple(rules[1:])})


def _without_paths(pack):
    """The same pack with its declared approval routing removed."""
    return pack.model_copy(update={"approval_paths": (), "approval_steps": ()})


def _with_two_unrelated_paths(pack):
    """Two declared paths, neither referencing the changed object."""
    first = pack.approval_paths[0]
    second = first.model_copy(
        update={"object_id": "path.second", "name": "second path", "related_object_ids": ()}
    )
    first_unlinked = first.model_copy(update={"related_object_ids": ()})
    return pack.model_copy(update={"approval_paths": (first_unlinked, second)})


def _disposition(requirement, step_id, reviewer, *, digest=None, decision=None):
    return ReviewDisposition(
        disposition_id=f"disp-{step_id}-{reviewer}",
        requirement_id=requirement.requirement_id,
        step_id=step_id,
        reviewer_id=reviewer,
        reviewer_role=step_id.split(".")[-1],
        reviewer_authority_reference="directory://opaque/handle",
        decision=decision or ApprovalDecision.APPROVED,
        policy_pack_digest=digest or requirement.new_pack_digest,
    )


def _satisfied_ledger(requirement):
    return ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=tuple(
            _disposition(requirement, step.step_id, f"reviewer-{i}")
            for i, step in enumerate(requirement.required_steps, start=1)
        ),
    )


# -- ratified postures ---------------------------------------------------------


def test_ratified_postures_are_declared():
    assert REVIEW_ENFORCEMENT == "BLOCKING"
    assert REVIEWER_IDENTITY == "OPAQUE_REFERENCE"


def test_p3a_never_imports_an_authority_directory():
    # P3A-2: the reference is opaque. Resolving it would need a dependency this
    # package does not have and a separate ruling to acquire.
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "ugence_policy_workflow_compiler"
    banned = re.compile(r"authority_directory|ugence_authority_directory|authority-directory")
    for module in (root / "review").glob("*.py"):
        assert not banned.search(module.read_text()), module


# -- routing -------------------------------------------------------------------


def test_no_sensitive_change_requires_no_review():
    pack, _ = _pack()
    requirement = derive_review_requirement(pack, pack)
    assert requirement.review_required is False
    assert requirement.is_blocking is False
    assert check_review(requirement, None).ok


def test_sensitive_change_without_declared_path_refuses():
    # Never default a reviewer: the pack declares no covering path.
    pack, _ = _pack()
    stripped = _without_paths(pack)
    requirement = derive_review_requirement(stripped, _mutate_decision_rule(stripped))
    assert requirement.review_required is True
    assert requirement.unresolved_codes == (ReviewCode.NO_APPROVAL_PATH_FOR_CHANGE.value,)
    # No ledger can satisfy it — there is no declared route to satisfy.
    check = check_review(requirement, _satisfied_ledger(requirement))
    assert check.rejected
    assert ReviewCode.NO_APPROVAL_PATH_FOR_CHANGE.value in check.codes


def test_ambiguous_routing_refuses_rather_than_choosing():
    # Two declared paths, neither referencing the change: there is no determinate
    # route, so the requirement refuses instead of picking one arbitrarily.
    pack, _ = _pack()
    old = _with_two_unrelated_paths(pack)
    new = _with_two_unrelated_paths(_mutate_decision_rule(pack))
    requirement = derive_review_requirement(old, new)
    assert requirement.review_required is True
    assert requirement.unresolved_codes == (ReviewCode.NO_APPROVAL_PATH_FOR_CHANGE.value,)
    assert requirement.required_approval_path_id == ""


def test_declared_path_is_routed_in_declared_order():
    pack, _ = _pack()
    new = _mutate_decision_rule(pack)
    requirement = derive_review_requirement(pack, new)
    assert requirement.review_required is True
    assert requirement.unresolved_codes == ()
    assert requirement.required_approval_path_id == "path.purchase_approval"
    assert [s.step_id for s in requirement.required_steps] == ["step.requester", "step.approver"]
    assert [s.order for s in requirement.required_steps] == [1, 2]
    assert requirement.segregation_pairs == (("requester", "approver"),)
    assert requirement.new_pack_digest == compute_pack_digest(new)


def test_derivation_is_deterministic_including_the_id():
    pack, _ = _pack()
    old, new = pack, _mutate_decision_rule(pack)
    a = derive_review_requirement(old, new)
    b = derive_review_requirement(old, new)
    assert a.model_dump(mode="python") == b.model_dump(mode="python")
    assert a.requirement_id == b.requirement_id


# -- the gate ------------------------------------------------------------------


def test_satisfied_ledger_passes():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    assert check_review(requirement, _satisfied_ledger(requirement)).ok


def test_missing_ledger_refuses():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    check = check_review(requirement, None)
    assert check.rejected
    assert ReviewCode.REVIEW_REQUIREMENT_UNSATISFIED.value in check.codes


def test_unsatisfied_step_refuses():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    partial = ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=(_disposition(requirement, "step.requester", "reviewer-1"),),
    )
    check = check_review(requirement, partial)
    assert check.rejected
    assert ReviewCode.REVIEW_REQUIREMENT_UNSATISFIED.value in check.codes


def test_stale_digest_refuses():
    # The point of re-review: a disposition must bind the CHANGED pack.
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    ledger = ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=(
            _disposition(requirement, "step.requester", "reviewer-1", digest=requirement.old_pack_digest),
            _disposition(requirement, "step.approver", "reviewer-2"),
        ),
    )
    check = check_review(requirement, ledger)
    assert check.rejected
    assert ReviewCode.DISPOSITION_DIGEST_MISMATCH.value in check.codes


def test_out_of_order_refuses():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    ledger = ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=(
            _disposition(requirement, "step.approver", "reviewer-2"),
            _disposition(requirement, "step.requester", "reviewer-1"),
        ),
    )
    check = check_review(requirement, ledger)
    assert check.rejected
    assert ReviewCode.REVIEW_STEP_OUT_OF_ORDER.value in check.codes


def test_segregation_of_duties_refuses_one_identity():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    ledger = ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=tuple(
            _disposition(requirement, step.step_id, "same-person")
            for step in requirement.required_steps
        ),
    )
    check = check_review(requirement, ledger)
    assert check.rejected
    assert ReviewCode.SEGREGATION_OF_DUTIES_VIOLATED.value in check.codes


def test_self_review_refuses():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    ledger = ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=(
            _disposition(requirement, "step.requester", COMPILER_PRINCIPAL),
            _disposition(requirement, "step.approver", "reviewer-2"),
        ),
    )
    check = check_review(requirement, ledger)
    assert check.rejected
    assert ReviewCode.SELF_REVIEW.value in check.codes


def test_rejected_decision_refuses():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    ledger = ReviewLedger(
        ledger_id="ledger-1",
        requirement_id=requirement.requirement_id,
        dispositions=(
            _disposition(requirement, "step.requester", "reviewer-1", decision=ApprovalDecision.REJECTED),
            _disposition(requirement, "step.approver", "reviewer-2"),
        ),
    )
    assert check_review(requirement, ledger).rejected


def test_ledger_for_another_requirement_refuses():
    pack, _ = _pack()
    requirement = derive_review_requirement(
        pack, _mutate_decision_rule(pack)
    )
    ledger = _satisfied_ledger(requirement).model_copy(update={"requirement_id": "other"})
    check = check_review(requirement, ledger)
    assert check.rejected
    assert ReviewCode.LEDGER_REQUIREMENT_MISMATCH.value in check.codes


# -- P3A-1 blocking at compile time --------------------------------------------


def test_compilation_refuses_an_unsatisfied_requirement():
    pack, approval = _pack()
    requirement = derive_review_requirement(pack, pack).model_copy(
        update={"review_required": True, "required_approval_path_id": "path.purchase_approval"}
    )
    result = api.compile_policy_pack(
        pack, approval, review_requirement=requirement, review_ledger=None
    )
    assert result.success is False
    codes = {d.code for d in result.validation_report.diagnostics}
    assert ReviewCode.REVIEW_REQUIREMENT_UNSATISFIED.value in codes


def test_compilation_refuses_a_requirement_for_another_pack():
    pack, approval = _pack()
    requirement = derive_review_requirement(pack, pack).model_copy(
        update={"new_pack_digest": "sha256:" + "0" * 64}
    )
    result = api.compile_policy_pack(pack, approval, review_requirement=requirement)
    assert result.success is False
    codes = {d.code for d in result.validation_report.diagnostics}
    assert ReviewCode.REQUIREMENT_PACK_MISMATCH.value in codes


def test_review_never_rescues_a_failed_approval():
    # The non-weakening invariant: gates compose as AND in both directions.
    pack, _ = _pack()
    requirement = derive_review_requirement(pack, pack)
    result = api.compile_policy_pack(
        pack, None, review_requirement=requirement, review_ledger=None
    )
    assert result.success is False
    codes = {d.code for d in result.validation_report.diagnostics}
    assert "APPROVAL_REQUIRED" in codes


# -- boundary and digest invariance --------------------------------------------


def test_review_artifacts_are_not_stored_in_the_pack():
    # A review artifact inside the pack would change the digest it binds to.
    pack, _ = _pack()
    dumped = pack.model_dump(mode="python")
    for key in dumped:
        assert "review" not in key, key


def test_every_pinned_digest_is_unchanged_by_p3a():
    pack, approval = _pack()
    assert compute_pack_digest(pack) == PINNED_PACK_DIGEST
    result = api.compile_policy_pack(pack, approval)
    assert result.logical_digest == PINNED_V1_RELEASE_DIGEST
    assert result.workflow_ir.logical_digest() == PINNED_V1_IR_DIGEST
    from ugence_policy_workflow_compiler.semantics import compile_workflow_v2

    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_a_satisfied_review_does_not_move_the_release_digest():
    pack, approval = _pack()
    requirement = derive_review_requirement(pack, pack)
    with_review = api.compile_policy_pack(
        pack, approval, review_requirement=requirement, review_ledger=None
    )
    without = api.compile_policy_pack(pack, approval)
    assert with_review.success and without.success
    assert with_review.logical_digest == without.logical_digest == PINNED_V1_RELEASE_DIGEST


def test_maturity_reports_p3a_honestly():
    info = api.version_info().to_dict()
    assert info["diff_driven_review_implemented"] is True
    for gate in (
        "runtime_deployment_implemented",
        "runtime_execution_implemented",
        "action_authorization_implemented",
        "pilot_validated",
        "production_certified",
    ):
        assert info[gate] is False, gate
