"""Approval gating service.

Decides whether a pack may be compiled/released given a human-approval record.
Enforces: the pack is APPROVED, the approval decision is APPROVED, the approval
binds to the pack's structural digest, reviewer authority is present, and the
approval was not authored by the compiler process itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..models.approvals import ApprovalDecision, HumanApprovalRecord
from ..models.common import PolicyPackStatus
from ..models.policy_pack import PolicyPack
from .records import COMPILER_PRINCIPAL, compute_pack_digest


@dataclass(frozen=True)
class ApprovalCheck:
    """The result of checking an approval against a pack."""

    ok: bool
    reasons: Tuple[str, ...]

    @property
    def rejected(self) -> bool:
        return not self.ok


class ApprovalService:
    """Deterministic approval gate. Never approves; only verifies approvals."""

    def check(
        self, pack: PolicyPack, approval: Optional[HumanApprovalRecord]
    ) -> ApprovalCheck:
        reasons = []
        if approval is None:
            reasons.append("no approval record supplied")
            return ApprovalCheck(False, tuple(reasons))
        if pack.status is not PolicyPackStatus.APPROVED:
            reasons.append(
                f"pack status is {pack.status.value}; only an APPROVED pack may compile"
            )
        if approval.decision is not ApprovalDecision.APPROVED:
            reasons.append(
                f"approval decision is {approval.decision.value}, not APPROVED"
            )
        if approval.policy_pack_id != pack.pack_id:
            reasons.append("approval is for a different pack id")
        expected_digest = compute_pack_digest(pack)
        if approval.policy_pack_digest != expected_digest:
            reasons.append("approval digest does not match the pack (pack changed since approval)")
        if not approval.reviewer_id.strip() or not approval.reviewer_role.strip():
            reasons.append("approval lacks reviewer identity/role")
        if approval.reviewer_id == COMPILER_PRINCIPAL:
            reasons.append("a compiler process must not approve its own output")
        return ApprovalCheck(not reasons, tuple(reasons))
