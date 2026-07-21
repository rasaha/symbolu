"""
Authority hierarchy for TAP-E4 (never collapsed).

Governance authority tiers, ordered, with a deterministic ranking. Each governing
candidate's tier is derived from the TAP-E2 evidence unit that states it (document type +
authority level) — the authority of a governing statement is the authority of the source
that states it. This mapping is documented and frozen; it is the only place upstream
authority metadata is interpreted.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping

AUTHORITY_MODEL_VERSION = "tap-e4-authority/1.0.0"


class AuthorityTier(str, Enum):
    LAW = "law"
    REGULATION = "regulation"
    CORPORATE_POLICY = "corporate_policy"
    DEPARTMENT_POLICY = "department_policy"
    SOP = "sop"
    WORK_INSTRUCTION = "work_instruction"
    DRAFT = "draft"
    RECOMMENDATION = "recommendation"
    UNKNOWN = "unknown"


# Higher rank = more authoritative. Never collapse tiers.
TIER_RANK: Mapping[AuthorityTier, int] = {
    AuthorityTier.LAW: 8,
    AuthorityTier.REGULATION: 7,
    AuthorityTier.CORPORATE_POLICY: 6,
    AuthorityTier.DEPARTMENT_POLICY: 5,
    AuthorityTier.SOP: 4,
    AuthorityTier.WORK_INSTRUCTION: 3,
    AuthorityTier.RECOMMENDATION: 2,
    AuthorityTier.DRAFT: 1,
    AuthorityTier.UNKNOWN: 0,
}

# Tiers that a customer contract / corporate policy may NEVER override.
IMMUTABLE_TIERS = frozenset({AuthorityTier.LAW, AuthorityTier.REGULATION})

# A draft is never a valid governing selection.
NON_SELECTABLE_TIERS = frozenset({AuthorityTier.DRAFT})


def tier_from_evidence(authority_level: str, doc_type: str,
                       explicit_tier: str = "") -> AuthorityTier:
    """Map an upstream (TAP-E2) authority level + document type to a governance tier.

    ``explicit_tier`` (from a governing statement's own scope, e.g. "law"/"regulation"/
    "department_policy") wins when present, so the corpus can state a finer tier than the
    coarse upstream document type."""
    if explicit_tier:
        try:
            return AuthorityTier(explicit_tier)
        except ValueError:
            pass
    if authority_level == "regulatory":
        return AuthorityTier.REGULATION
    if authority_level == "draft":
        return AuthorityTier.DRAFT
    if authority_level == "official":
        if doc_type == "contract":
            return AuthorityTier.CORPORATE_POLICY   # a contract is an official obligation
        if doc_type == "sop":
            return AuthorityTier.SOP
        return AuthorityTier.CORPORATE_POLICY
    if authority_level == "reference":
        return AuthorityTier.WORK_INSTRUCTION
    if authority_level == "deprecated":
        return AuthorityTier.DRAFT
    return AuthorityTier.UNKNOWN


def rank(tier: AuthorityTier) -> int:
    return TIER_RANK[tier]


def is_immutable(tier: AuthorityTier) -> bool:
    return tier in IMMUTABLE_TIERS


def is_selectable(tier: AuthorityTier) -> bool:
    return tier not in NON_SELECTABLE_TIERS
