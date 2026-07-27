"""
outcome_contract.py — bounded enterprise outcome vocabulary + exact semantic contracts.

Outcomes are NON-executing decision states. The mapping from typed structured reasoning fields to an
outcome is a transparent, auditable rule (`decide`). Hard gates (§7) are encoded here and a learned
head must never override them.
"""
from __future__ import annotations

from dataclasses import dataclass

# canonical outcome states
APPROVE, REJECT, REVIEW_REQUIRED, ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT = range(5)
OUTCOMES = ("APPROVE", "REJECT", "REVIEW_REQUIRED",
            "ABSTAIN_INCOMPLETE_EVIDENCE", "ABSTAIN_MATERIAL_CONFLICT")
N_OUTCOME = 5
INVALID_RUN = -1                        # unauthorized evidence present → blocked, not an outcome

# typed structured-reasoning field vocabularies
BUDGET_SUFFICIENT, BUDGET_INSUFFICIENT, BUDGET_MISSING = 0, 1, 2
POLICY_IDENTIFIED, POLICY_MISSING, POLICY_CONFLICTED = 0, 1, 2
APPROVAL_PRESENT, APPROVAL_MISSING = 0, 1


@dataclass
class StructuredFinding:
    budget_status: int            # SUFFICIENT / INSUFFICIENT / MISSING
    policy_status: int            # IDENTIFIED / MISSING / CONFLICTED
    approval_status: int          # PRESENT / MISSING
    material_conflict: bool
    evidence_complete: bool
    unauthorized_present: bool = False


def decide(f: StructuredFinding) -> int:
    """Deterministic outcome contract (§5/§7). Hard gates first, in priority order."""
    if f.unauthorized_present:
        return INVALID_RUN                                    # blocked before any mapping
    if f.material_conflict or f.policy_status == POLICY_CONFLICTED:
        return ABSTAIN_MATERIAL_CONFLICT                      # unresolved authoritative conflict
    if (not f.evidence_complete or f.budget_status == BUDGET_MISSING
            or f.policy_status == POLICY_MISSING):
        return ABSTAIN_INCOMPLETE_EVIDENCE                    # mandatory evidence unavailable
    if f.budget_status == BUDGET_INSUFFICIENT:
        return REJECT                                         # constraint fails on complete evidence
    if f.approval_status == APPROVAL_MISSING:
        return REVIEW_REQUIRED                                # required human authority not evidenced
    return APPROVE                                            # all constraints satisfied + evidenced


CONTRACT_DOC = {
    "APPROVE": "evidence complete; active policy identified; budget sufficient; required approval "
               "evidenced; no unresolved material conflict",
    "REJECT": "evidence complete; active policy identified; but budget insufficient for the request",
    "REVIEW_REQUIRED": "evidence complete enough for review, but the required approval/human "
                       "authority is not yet evidenced",
    "ABSTAIN_INCOMPLETE_EVIDENCE": "one or more mandatory evidence fields (budget / active policy) "
                                   "are unavailable",
    "ABSTAIN_MATERIAL_CONFLICT": "an unresolved authoritative evidence conflict prevents a reliable "
                                 "outcome",
}
