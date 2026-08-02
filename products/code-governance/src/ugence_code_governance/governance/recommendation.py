"""Product-owned advisory recommendation.

A :class:`GovernanceRecommendation` is an **automated advisory signal** produced
before any binding decision. It is deliberately a distinct product type: it can
never masquerade as a Decision Authority ``DecisionRecord`` and it carries no
authority. "All automated checks passed" is expressed here as an advisory
disposition — it can never silently mean "binding approval granted".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Tuple

from ..fingerprints import domain_hash


class RecommendationDisposition(str, Enum):
    """Advisory disposition — NOT a decision outcome and NOT an authorization."""

    RECOMMEND_PROCEED = "RECOMMEND_PROCEED"
    RECOMMEND_HOLD = "RECOMMEND_HOLD"
    RECOMMEND_ESCALATE = "RECOMMEND_ESCALATE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class GovernanceRecommendation:
    """Immutable advisory recommendation. Never a binding decision."""

    recommendation_id: str
    tenant_id: str
    repository: str
    pull_request_number: int
    change_fingerprint: str
    claim_manifest_fingerprint: str
    disposition: RecommendationDisposition
    rationale: Tuple[str, ...]
    created_at: datetime
    policy_ref: str

    #: A recommendation is, by construction, never binding. This flag exists so
    #: that any code path confusing it for a decision fails an explicit check.
    is_binding: bool = field(default=False, init=False)

    @property
    def fingerprint(self) -> str:
        return domain_hash(
            "governance_recommendation.v1",
            {
                "tenant_id": self.tenant_id,
                "repository": self.repository,
                "pull_request_number": self.pull_request_number,
                "change_fingerprint": self.change_fingerprint,
                "claim_manifest_fingerprint": self.claim_manifest_fingerprint,
                "disposition": self.disposition.value,
                "policy_ref": self.policy_ref,
            },
        )


__all__ = ["RecommendationDisposition", "GovernanceRecommendation"]
