"""The review gate — fail-closed verification of a ledger against a requirement.

P3A-1: this gate refuses. It never downgrades a finding to a warning, never exempts
a "minor" change, and never carries an approval forward past a digest change.

The non-weakening invariant: this gate is an **additional** condition beside
:class:`~ugence_policy_workflow_compiler.approval.service.ApprovalService`, never a
substitute for it. A satisfied review cannot rescue a failed approval, and a valid
approval cannot excuse an unsatisfied review.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..approval.records import COMPILER_PRINCIPAL
from ..models.approvals import ApprovalDecision
from .models import ReviewCheck, ReviewCode, ReviewDisposition, ReviewLedger, ReviewRequirement


def _identity_for(label: str, by_step: Dict[str, ReviewDisposition]) -> Optional[str]:
    """Resolve a segregation label — a step id or a role label — to an identity.

    Labels are matched against the ledger's own dispositions only. Nothing is looked
    up outside the artifacts supplied (P3A-2).
    """
    disposition = by_step.get(label)
    if disposition is not None:
        return disposition.reviewer_id
    for candidate in by_step.values():
        if candidate.reviewer_role == label:
            return candidate.reviewer_id
    return None


def check_review(
    requirement: ReviewRequirement, ledger: Optional[ReviewLedger] = None
) -> ReviewCheck:
    """Verify that ``ledger`` satisfies ``requirement``. Refusals are typed."""
    codes: List[str] = []
    reasons: List[str] = []

    def refuse(code: ReviewCode, reason: str) -> None:
        codes.append(code.value)
        reasons.append(reason)

    # A derivation-time refusal (no covering approval path) can never be satisfied
    # by any ledger — the pack declares no route to satisfy.
    for code in requirement.unresolved_codes:
        codes.append(code)
        reasons.append(
            "the pack declares no approval path covering the changed objects; "
            "a reviewer is never defaulted"
        )

    if not requirement.is_blocking:
        # No approval-sensitive change. The approval gate still applies separately.
        return ReviewCheck(ok=not codes, codes=tuple(codes), reasons=tuple(reasons))

    if ledger is None:
        refuse(
            ReviewCode.REVIEW_REQUIREMENT_UNSATISFIED,
            "no review ledger supplied for a change that requires re-review",
        )
        return ReviewCheck(ok=False, codes=tuple(codes), reasons=tuple(reasons))

    if ledger.requirement_id != requirement.requirement_id:
        refuse(
            ReviewCode.LEDGER_REQUIREMENT_MISMATCH,
            f"ledger addresses requirement {ledger.requirement_id!r}, "
            f"not {requirement.requirement_id!r}",
        )
        return ReviewCheck(ok=False, codes=tuple(codes), reasons=tuple(reasons))

    declared = {step.step_id: step for step in requirement.required_steps}
    by_step: Dict[str, ReviewDisposition] = {}

    for disposition in ledger.dispositions:
        if disposition.step_id not in declared:
            refuse(
                ReviewCode.UNKNOWN_REVIEW_STEP,
                f"disposition {disposition.disposition_id!r} names undeclared step "
                f"{disposition.step_id!r}",
            )
            continue
        if disposition.policy_pack_digest != requirement.new_pack_digest:
            refuse(
                ReviewCode.DISPOSITION_DIGEST_MISMATCH,
                f"disposition {disposition.disposition_id!r} binds a digest other than "
                "the reviewed pack — a review must re-bind to the changed pack",
            )
        if disposition.reviewer_id == COMPILER_PRINCIPAL:
            refuse(
                ReviewCode.SELF_REVIEW,
                "a compiler process must not review its own output",
            )
        by_step.setdefault(disposition.step_id, disposition)

    # Declared order. Compare the order of the dispositions actually recorded
    # against the pack's declared step order.
    recorded = [d.step_id for d in ledger.dispositions if d.step_id in declared]
    seen: List[str] = []
    for step_id in recorded:
        if step_id not in seen:
            seen.append(step_id)
    expected = [s for s in (step.step_id for step in requirement.required_steps) if s in seen]
    if seen != expected:
        refuse(
            ReviewCode.REVIEW_STEP_OUT_OF_ORDER,
            "dispositions do not follow the approval path's declared step order",
        )

    for step in requirement.required_steps:
        disposition = by_step.get(step.step_id)
        if disposition is None:
            if not step.optional:
                refuse(
                    ReviewCode.REVIEW_REQUIREMENT_UNSATISFIED,
                    f"required step {step.step_id!r} has no disposition",
                )
            continue
        if disposition.decision is not ApprovalDecision.APPROVED:
            refuse(
                ReviewCode.REVIEW_REQUIREMENT_UNSATISFIED,
                f"step {step.step_id!r} was dispositioned "
                f"{disposition.decision.value}, not APPROVED",
            )

    for left, right in requirement.segregation_pairs:
        left_identity = _identity_for(left, by_step)
        right_identity = _identity_for(right, by_step)
        if left_identity is not None and left_identity == right_identity:
            refuse(
                ReviewCode.SEGREGATION_OF_DUTIES_VIOLATED,
                f"segregation pair ({left!r}, {right!r}) satisfied by a single "
                f"identity {left_identity!r}",
            )

    # Deterministic, de-duplicated code order.
    unique_codes: List[str] = []
    for code in codes:
        if code not in unique_codes:
            unique_codes.append(code)
    return ReviewCheck(ok=not codes, codes=tuple(unique_codes), reasons=tuple(reasons))


__all__ = ["check_review"]
