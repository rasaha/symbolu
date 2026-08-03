"""Approval-gate tests: unapproved/rejected packs cannot compile; no self-approval."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import (
    GovernedWorkflowCompiler,
    PolicyPackStatus,
    build_approval_record,
    compute_pack_digest,
)
from ugence_policy_workflow_compiler.approval import COMPILER_PRINCIPAL, ApprovalService
from ugence_policy_workflow_compiler.models.approvals import ApprovalDecision

from _builders import build_full_synthetic_pack


def _approval(pack, **kw):
    defaults = dict(
        approval_id="a1", pack=pack, reviewer_id="rev", reviewer_role="role",
        decision=ApprovalDecision.APPROVED,
    )
    defaults.update(kw)
    return build_approval_record(**defaults)


def test_unapproved_pack_cannot_compile():
    pack = build_full_synthetic_pack(status=PolicyPackStatus.DRAFT)
    appr = _approval(pack)  # status is DRAFT, not APPROVED
    result = GovernedWorkflowCompiler().compile(pack, appr)
    assert not result.success
    assert any("APPROVED pack" in d.message for d in result.diagnostics)


def test_no_approval_record_cannot_compile():
    pack = build_full_synthetic_pack()
    result = GovernedWorkflowCompiler().compile(pack, approval=None)
    assert not result.success
    assert any(d.code == "APPROVAL_REQUIRED" for d in result.diagnostics)


def test_rejected_approval_cannot_compile():
    pack = build_full_synthetic_pack()
    appr = _approval(pack, decision=ApprovalDecision.REJECTED)
    result = GovernedWorkflowCompiler().compile(pack, appr)
    assert not result.success


def test_reviewer_authority_required():
    # The model itself refuses an approval with no reviewer identity/role.
    import pytest

    pack = build_full_synthetic_pack()
    with pytest.raises(Exception):
        _approval(pack, reviewer_id="", reviewer_role="")
    # And the service also rejects a whitespace-only reviewer via model_construct.
    from ugence_policy_workflow_compiler.models.approvals import HumanApprovalRecord

    blank = HumanApprovalRecord.model_construct(
        object_id="a", name="a", approval_id="a", policy_pack_id=pack.pack_id,
        policy_pack_digest=compute_pack_digest(pack), reviewer_id="  ",
        reviewer_role="  ", decision=ApprovalDecision.APPROVED,
    )
    assert ApprovalService().check(pack, blank).rejected


def test_compiler_cannot_self_approve():
    pack = build_full_synthetic_pack()
    appr = _approval(pack, reviewer_id=COMPILER_PRINCIPAL)
    result = GovernedWorkflowCompiler().compile(pack, appr)
    assert not result.success
    assert any("must not approve its own output" in d.message for d in result.diagnostics)


def test_approval_digest_binding():
    pack = build_full_synthetic_pack()
    appr = _approval(pack)
    # mutate the pack after approval -> digest mismatch
    changed = pack.model_copy(update={"description": "changed after approval"})
    check = ApprovalService().check(changed, appr)
    assert check.rejected
    assert any("digest" in r for r in check.reasons)


def test_reviewed_gaps_recorded():
    pack = build_full_synthetic_pack()
    appr = _approval(pack, reviewed_gap_ids=("gap.1",), accepted_warning_ids=("w.1",))
    assert appr.reviewed_gap_ids == ("gap.1",)
    assert appr.accepted_warning_ids == ("w.1",)


def test_valid_approval_compiles():
    pack = build_full_synthetic_pack()
    appr = _approval(pack)
    result = GovernedWorkflowCompiler().compile(pack, appr)
    assert result.success
