"""
tap_validator.py — TAP assertion governance (§11/§13).

Given a drafted explanation decomposed into typed claims, TAP classifies each claim against the
structured finding, the evidence IDs, and hard authority/certainty ceilings, then assigns a
disposition. Authority-exceeding and unsupported/contradicted claims are blocked or forced to
qualify/escalate — enforcement that a system prompt cannot guarantee.

Classifications: SUPPORTED / QUALIFIED / UNSUPPORTED / CONTRADICTED / UNTRACEABLE / EXCEEDS_AUTHORITY.
Dispositions:    PASS / REVISE / QUALIFY / ABSTAIN / ESCALATE.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from experiments.enterprise_output_mapping.outcome_contract import (StructuredFinding, APPROVAL_PRESENT,
    POLICY_IDENTIFIED)
from .claim_decomposer import Claim

SUPPORTED, QUALIFIED, UNSUPPORTED, CONTRADICTED, UNTRACEABLE, EXCEEDS_AUTHORITY = (
    "SUPPORTED", "QUALIFIED", "UNSUPPORTED", "CONTRADICTED", "UNTRACEABLE", "EXCEEDS_AUTHORITY")
PASS, REVISE, QUALIFY, ABSTAIN, ESCALATE = "PASS", "REVISE", "QUALIFY", "ABSTAIN", "ESCALATE"

# claim kinds that assert authority/execution/compliance the system may never grant
AUTHORITY_KINDS = {"compliance_guaranteed", "recommendation_as_binding", "execution_authorized",
                   "review_optional", "inferred_authority_as_explicit"}


@dataclass
class TAPResult:
    claim: Claim
    classification: str
    disposition: str
    required_qualifier: str = ""


def classify(claim: Claim, finding: StructuredFinding, authority_ceiling=True, certainty_ceiling=True) -> TAPResult:
    k = claim.kind
    # hard authority/certainty ceilings (T3) — cannot be overridden
    if k in AUTHORITY_KINDS:
        return TAPResult(claim, EXCEEDS_AUTHORITY, ESCALATE if authority_ceiling else PASS)
    # grounded claims: check against the finding + evidence
    if k == "outcome_recommendation":
        return TAPResult(claim, SUPPORTED, PASS, required_qualifier="based on available evidence")
    if k == "evidence_complete":
        return TAPResult(claim, SUPPORTED if finding.evidence_complete else CONTRADICTED,
                         PASS if finding.evidence_complete else REVISE)
    if k == "policy_identified":
        return TAPResult(claim, SUPPORTED if finding.policy_status == POLICY_IDENTIFIED else CONTRADICTED,
                         PASS if finding.policy_status == POLICY_IDENTIFIED else REVISE)
    if k == "approval_granted_when_requested":
        # claim asserts granted; supported only if the finding actually has approval present
        ok = finding.approval_status == APPROVAL_PRESENT
        return TAPResult(claim, SUPPORTED if ok else CONTRADICTED, PASS if ok else REVISE)
    if k in ("policy_active_when_unresolved", "conflict_settled", "missing_as_negative",
             "ambiguous_exception_applies"):
        return TAPResult(claim, CONTRADICTED if k in ("conflict_settled",) else UNSUPPORTED, REVISE)
    # untraceable: a factual claim with no evidence IDs
    if not claim.evidence_ids and claim.kind in ("policy_identified", "evidence_complete"):
        return TAPResult(claim, UNTRACEABLE, ESCALATE)
    return TAPResult(claim, UNSUPPORTED, REVISE)


def govern(claims: List[Claim], finding: StructuredFinding, arm="T3") -> List[TAPResult]:
    """arm: T2 = decomposition+matching (no ceilings); T3 = + authority/certainty ceilings."""
    ceilings = arm in ("T3", "T4")
    return [classify(c, finding, authority_ceiling=ceilings, certainty_ceiling=ceilings) for c in claims]


def admissible(results: List[TAPResult]) -> List[TAPResult]:
    """Final admissible claim set: only PASS/QUALIFY claims reach the user; others blocked/escalated."""
    return [r for r in results if r.disposition in (PASS, QUALIFY)]
