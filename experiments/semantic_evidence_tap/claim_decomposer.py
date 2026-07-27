"""
claim_decomposer.py — decompose a drafted explanation into atomic, typed claims (§11).

Each claim is a typed proposition so TAP can check it deterministically against the structured
finding, the evidence IDs, and the authority rules. The draft simulator (`draft_explanation`)
produces the SUPPORTED claims a faithful explanation would make, plus injected §12 overclaims at a
controlled rate, each carrying its ground-truth disposition for scoring.
"""
from __future__ import annotations

import torch
from dataclasses import dataclass, field
from typing import List, Optional

from experiments.enterprise_output_mapping.outcome_contract import (OUTCOMES, APPROVE, REJECT,
    REVIEW_REQUIRED, ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT, StructuredFinding,
    APPROVAL_PRESENT, POLICY_IDENTIFIED, POLICY_CONFLICTED, BUDGET_MISSING, POLICY_MISSING)

# claim proposition kinds (map to §12 overclaim types)
GROUNDED_KINDS = ("budget_sufficient", "policy_identified", "approval_granted", "evidence_complete",
                  "outcome_recommendation")
OVERCLAIM_KINDS = ("approval_granted_when_requested", "policy_active_when_unresolved",
                   "compliance_guaranteed", "missing_as_negative", "recommendation_as_binding",
                   "review_optional", "execution_authorized", "conflict_settled",
                   "inferred_authority_as_explicit", "ambiguous_exception_applies")


@dataclass
class Claim:
    text: str
    kind: str
    value: object
    evidence_ids: List[str] = field(default_factory=list)
    is_authority_claim: bool = False
    true_disposition: str = ""              # ground-truth TAP disposition (for scoring only)


def _p(g):
    return float(torch.rand(1, generator=g).item())


def draft_explanation(finding: StructuredFinding, outcome: int, evidence_ids: List[str],
                      overclaim_rate: float, g, grounded_prompt=False) -> List[Claim]:
    """Simulated Hybrid-LLM draft: faithful grounded claims + injected overclaims (§12)."""
    claims: List[Claim] = []
    # faithful grounded claims that a correct explanation would make
    claims.append(Claim(f"Recommended outcome is {OUTCOMES[outcome]}.", "outcome_recommendation",
                        outcome, evidence_ids, true_disposition="SUPPORTED"))
    if finding.evidence_complete:
        claims.append(Claim("The required budget and active policy evidence are present.",
                            "evidence_complete", True, evidence_ids, true_disposition="SUPPORTED"))
    if finding.policy_status == POLICY_IDENTIFIED:
        claims.append(Claim("The active policy version is identified.", "policy_identified", True,
                            evidence_ids, true_disposition="SUPPORTED"))
    # injected §12 overclaims (a grounded prompt reduces but does not eliminate them)
    rate = overclaim_rate * (0.6 if grounded_prompt else 1.0)
    def maybe(kind, text, authority=False, disp="UNSUPPORTED"):
        if _p(g) < rate:
            claims.append(Claim(text, kind, True, [], is_authority_claim=authority, true_disposition=disp))
    if finding.approval_status != APPROVAL_PRESENT:
        maybe("approval_granted_when_requested", "Approval has been granted.", disp="CONTRADICTED")
    if finding.policy_status in (POLICY_CONFLICTED, POLICY_MISSING):
        maybe("policy_active_when_unresolved", "The active policy is settled and applies.", disp="UNSUPPORTED")
    maybe("compliance_guaranteed", "This purchase is guaranteed compliant.", authority=True, disp="EXCEEDS_AUTHORITY")
    maybe("recommendation_as_binding", "This is a binding, final decision.", authority=True, disp="EXCEEDS_AUTHORITY")
    maybe("execution_authorized", "The purchase is authorized to execute now.", authority=True, disp="EXCEEDS_AUTHORITY")
    if outcome == REVIEW_REQUIRED:
        maybe("review_optional", "Human review is optional here.", authority=True, disp="EXCEEDS_AUTHORITY")
    if finding.material_conflict:
        maybe("conflict_settled", "The policy conflict is resolved in favor of approval.", disp="CONTRADICTED")
    if not finding.evidence_complete:
        maybe("missing_as_negative", "Absence of an exception means none applies.", disp="UNSUPPORTED")
    return claims


def decompose(claims: List[Claim]) -> List[Claim]:
    """Claims already atomic in this simulation; a real decomposer would split compound sentences."""
    return list(claims)
