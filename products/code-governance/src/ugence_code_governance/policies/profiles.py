"""Risk-scoped repository policy profiles (orchestration layer only).

This is the profile + orchestration layer described by the merged Change
Intelligence design — **not** analyzers. It maps a risk tier to the claims a
policy requires, distinguishing mandatory (hard, non-compensatory) from advisory
(optional) families. Advisory evidence is never converted into a hard denial
unless a policy explicitly marks a claim mandatory.

Only claim families named in the merged documentation appear here. Detection
engines (mutation, fuzz, taint, complexity, performance analysis) are NOT
implemented in MVP 1A; the product governs evidence produced by external
validators.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from ..claims.requirements import ClaimRequirement
from ..models.enums import ClaimType, RiskTier

# Mandatory claim families per risk tier (higher tiers include lower-tier ones).
# Derived from change_intelligence_evidence_profiles.json (LOW/MEDIUM/HIGH).
_LOW_MANDATORY: Tuple[ClaimType, ...] = (
    ClaimType.BUILD,
    ClaimType.UNIT_TEST,
    ClaimType.STATIC_ANALYSIS,
)
_MEDIUM_MANDATORY: Tuple[ClaimType, ...] = _LOW_MANDATORY + (
    ClaimType.DIFFERENTIAL_TEST,
    ClaimType.DEPENDENCY_DELTA,
    ClaimType.PUBLIC_API_DELTA,
    ClaimType.PERFORMANCE_BUDGET,
)
_HIGH_MANDATORY: Tuple[ClaimType, ...] = _MEDIUM_MANDATORY + (
    ClaimType.SECURITY,
    ClaimType.MUTATION_ADEQUACY,
    ClaimType.INDEPENDENT_REVIEW,
)

# Advisory (optional) families — descriptive, never a hard gate on their own.
_ADVISORY: Tuple[ClaimType, ...] = (
    ClaimType.ARTIFACT_SIZE_DELTA,
    ClaimType.COMPLEXITY_DELTA,
    ClaimType.ARCHITECTURE_DELTA,
    ClaimType.PROPERTY_TEST,
)

_MANDATORY_BY_TIER: Mapping[RiskTier, Tuple[ClaimType, ...]] = {
    RiskTier.LOW: _LOW_MANDATORY,
    RiskTier.MEDIUM: _MEDIUM_MANDATORY,
    RiskTier.HIGH: _HIGH_MANDATORY,
}


@dataclass(frozen=True)
class RepositoryPolicy:
    """A named, versioned repository policy that selects required claims by tier."""

    policy_id: str
    version: str

    @property
    def policy_ref(self) -> str:
        return f"{self.policy_id}:{self.version}"

    def requirements_for(self, tier: RiskTier) -> Tuple[ClaimRequirement, ...]:
        """Return the (mandatory + advisory) claim requirements for ``tier``."""
        mandatory = _MANDATORY_BY_TIER[tier]
        reqs = [ClaimRequirement(claim_type=ct, mandatory=True) for ct in mandatory]
        for ct in _ADVISORY:
            reqs.append(ClaimRequirement(claim_type=ct, mandatory=False))
        return tuple(reqs)

    def mandatory_claim_types(self, tier: RiskTier) -> Tuple[ClaimType, ...]:
        return _MANDATORY_BY_TIER[tier]


#: A conservative default policy used by demos/tests.
DEFAULT_POLICY = RepositoryPolicy(policy_id="repo-policy", version="v1")


__all__ = ["RepositoryPolicy", "DEFAULT_POLICY"]
