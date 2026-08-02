"""Persistence boundary — narrow protocols + in-memory reference stores.

Persistence lives only in the product boundary. No production database is
introduced in MVP 1A.
"""
from __future__ import annotations

from .memory import (
    InMemoryClaimManifestRepository,
    InMemoryEvidenceRepository,
    InMemoryGovernanceChainRepository,
    InMemoryPreparedActionRepository,
    InMemoryRecommendationRepository,
    InMemoryWorkflowRepository,
)
from .protocols import (
    ClaimManifestRepository,
    EvidenceRepository,
    GovernanceChainRepository,
    PreparedActionRepository,
    RecommendationRepository,
    WorkflowRepository,
)

__all__ = [
    "EvidenceRepository",
    "ClaimManifestRepository",
    "RecommendationRepository",
    "PreparedActionRepository",
    "WorkflowRepository",
    "GovernanceChainRepository",
    "InMemoryEvidenceRepository",
    "InMemoryClaimManifestRepository",
    "InMemoryRecommendationRepository",
    "InMemoryPreparedActionRepository",
    "InMemoryWorkflowRepository",
    "InMemoryGovernanceChainRepository",
]
