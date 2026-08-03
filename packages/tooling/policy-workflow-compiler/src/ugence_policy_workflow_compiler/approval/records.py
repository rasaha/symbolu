"""Human-approval record helpers and the pack structural digest.

The pack **structural digest** is a status-independent content digest of a pack:
it excludes the lifecycle ``status`` field so a pack keeps the same digest across
the ``APPROVED -> COMPILED`` transition. A :class:`HumanApprovalRecord` binds to
this digest; recompiling a materially different pack invalidates the approval.
"""

from __future__ import annotations

from ..models.approvals import ApprovalDecision, HumanApprovalRecord
from ..models.policy_pack import PolicyPack
from ..serialization import hashing

#: The principal identity the compiler process would use. An approval authored by
#: this identity is rejected — a compiler must not approve its own output.
COMPILER_PRINCIPAL = "ugence_policy_workflow_compiler:process"


def compute_pack_digest(pack: PolicyPack) -> str:
    """Status-independent structural digest of a policy pack."""
    data = pack.model_dump(mode="python")
    data.pop("status", None)
    return hashing.digest(data)


def build_approval_record(
    *,
    approval_id: str,
    pack: PolicyPack,
    reviewer_id: str,
    reviewer_role: str,
    decision: ApprovalDecision = ApprovalDecision.APPROVED,
    reviewer_authority_reference: str = "",
    approved_at: str = "",
    reviewed_gap_ids=(),
    accepted_warning_ids=(),
    justification: str = "",
    signature_reference: str = "",
    is_fixture: bool = False,
    name: str = "",
) -> HumanApprovalRecord:
    """Build a :class:`HumanApprovalRecord` bound to ``pack``'s structural digest."""
    return HumanApprovalRecord(
        object_id=approval_id,
        name=name or f"approval:{approval_id}",
        approval_id=approval_id,
        policy_pack_id=pack.pack_id,
        policy_pack_digest=compute_pack_digest(pack),
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        reviewer_authority_reference=reviewer_authority_reference,
        decision=decision,
        approved_at=approved_at,
        reviewed_gap_ids=tuple(reviewed_gap_ids),
        accepted_warning_ids=tuple(accepted_warning_ids),
        justification=justification,
        signature_reference=signature_reference,
        is_fixture=is_fixture,
    )
