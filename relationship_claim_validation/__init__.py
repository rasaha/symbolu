"""
Relationship Claim Validation Experiment v0.1 — "Claim Truth Layer".

A NEW, self-contained research track. It is additive and imports nothing from any
other track in this repository. It does NOT modify or depend on any resolver,
governance, packet, corpus, benchmark, or experiment.

IMPORTANT HONESTY NOTE (see docs/relationship_claim_validation/FINAL_VERDICT.md):
The frozen substrate referenced by the experiment brief (SEEB, a resolver series
v0.1-v0.5, a hidden relationship corpus, a frozen proposal-validation/governance/
packet pipeline, and prior experiment locks) does NOT exist in this repository.
This package therefore does not "insert a stage before frozen governance"; it is a
stand-alone demonstration of a relationship-claim-validation *mechanism* over a
self-authored SYNTHETIC corpus, using DETERMINISTIC span-grounded judges (not LLMs)
so results are reproducible. Any measured effect is construction/mechanism
validation on synthetic data only — it is NOT evidence of real-world error
reduction, and NOT evidence for production deployment.
"""

from relationship_claim_validation.model import (
    ClaimStatus, RecommendedAction, PredicateName, PredicateVerdict,
    ConfidenceVector, EvidenceRecord, RelationshipClaim, Document, Span,
    GoldLabel,
)
from relationship_claim_validation.validator import (
    ClaimValidationLayer, AblationConfig, ABLATIONS,
)

__all__ = [
    "ClaimStatus", "RecommendedAction", "PredicateName", "PredicateVerdict",
    "ConfidenceVector", "EvidenceRecord", "RelationshipClaim", "Document", "Span",
    "GoldLabel", "ClaimValidationLayer", "AblationConfig", "ABLATIONS",
]

__version__ = "0.1.0"
