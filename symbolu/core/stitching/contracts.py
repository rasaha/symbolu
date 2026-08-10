"""
Stitching Contracts - Data Structures per Specification v1.1
=============================================================

This module defines the authoritative data contracts for the Stitching stage.
These contracts enforce the normative requirements from the specification.

NORMATIVE REQUIREMENTS (from spec Section 0):
- MUST return boolean eligibility (allowed: true/false) per candidate
- MUST NOT produce comparable or optimization scores
- Diagnostic values MAY exist only for audit/debug
- MUST NOT select, rank, or prioritize candidates
- MUST expose rejection reasons only via audit metadata

Reference: Project_documentation/repository/docs/architecture/STITCHING_FUSION_SPECIFICATION.md
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class RejectionReason(Enum):
    """Enumerated reasons for candidate rejection.

    These are the ONLY valid rejection reasons. Each maps to a specific
    constraint violation that Stitching enforces.
    """
    LOW_CONFIDENCE = "confidence_below_threshold"
    HIGH_ENTROPY = "entropy_above_threshold"
    DOMAIN_JUMP_CAP = "max_domain_jumps_exceeded"
    LOW_SCORE = "score_below_minimum"
    TOO_REDUNDANT = "redundancy_threshold_exceeded"
    CONSTRAINT_VIOLATION = "hard_constraint_violated"


@dataclass
class CandidateDecision:
    """
    Decision for a single candidate.

    This is the per-candidate output of Stitching's evaluate() method.

    IMPORTANT: diagnostic_scores are for AUDIT ONLY. They MUST NOT
    be passed to Fusion or used for ranking decisions.
    """
    candidate_id: str
    allowed: bool

    # Diagnostic scores (NOT for ranking - audit/debug only)
    # These scores explain WHY a decision was made, not HOW to rank
    diagnostic_scores: Dict[str, float] = field(default_factory=dict)
    # Expected keys: relevance, redundancy_penalty, domain_jump_penalty, total

    # Rejection info (populated only if allowed=False)
    rejection_reason: Optional[RejectionReason] = None
    rejection_detail: Optional[str] = None

    # Audit notes for explainability
    audit_notes: List[str] = field(default_factory=list)

    # Constraint status (which constraints passed/failed)
    constraint_status: Dict[str, bool] = field(default_factory=dict)
    # Expected keys: confidence_ok, entropy_ok, domain_cap_ok, score_ok, redundancy_ok

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "candidate_id": self.candidate_id,
            "allowed": self.allowed,
            "diagnostic_scores": self.diagnostic_scores,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "rejection_detail": self.rejection_detail,
            "audit_notes": self.audit_notes,
            "constraint_status": self.constraint_status,
        }


@dataclass
class StitchingDecision:
    """
    Output from Stitching stage.

    This is the AUTHORITATIVE output contract for StitchingEngine.evaluate().

    NORMATIVE REQUIREMENTS:
    - allowed_candidate_ids contains ONLY candidates that passed ALL constraints
    - decisions dict contains audit trail for ALL evaluated candidates
    - diagnostics contains aggregate stats for observability
    - This object MUST NOT be passed directly to Fusion

    The handoff to Fusion uses StitchingToFusionHandoff which strips
    diagnostic information to enforce the boundary.
    """

    # Primary output: IDs of allowed candidates
    # These are the ONLY candidates that may proceed to Fusion
    allowed_candidate_ids: List[str]

    # Per-candidate decisions (for audit trail)
    # Contains decisions for ALL candidates, including rejected ones
    decisions: Dict[str, CandidateDecision] = field(default_factory=dict)

    # Aggregate diagnostics for observability
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: total_evaluated, total_allowed, total_rejected,
    #                cross_domain_count, rejection_summary

    # Audit metadata
    audit: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: timestamp, config_snapshot, constraint_thresholds, audit_id

    def get_allowed_decisions(self) -> List[CandidateDecision]:
        """Get decisions for allowed candidates only."""
        return [d for d in self.decisions.values() if d.allowed]

    def get_rejected_decisions(self) -> List[CandidateDecision]:
        """Get decisions for rejected candidates only."""
        return [d for d in self.decisions.values() if not d.allowed]

    def get_rejection_summary(self) -> Dict[str, int]:
        """Count rejections by reason."""
        summary: Dict[str, int] = {}
        for d in self.decisions.values():
            if not d.allowed and d.rejection_reason:
                key = d.rejection_reason.value
                summary[key] = summary.get(key, 0) + 1
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "allowed_candidate_ids": self.allowed_candidate_ids,
            "total_evaluated": len(self.decisions),
            "total_allowed": len(self.allowed_candidate_ids),
            "total_rejected": len(self.decisions) - len(self.allowed_candidate_ids),
            "decisions": {
                cid: d.to_dict() for cid, d in self.decisions.items()
            },
            "diagnostics": self.diagnostics,
            "audit": self.audit,
        }


__all__ = [
    "RejectionReason",
    "CandidateDecision",
    "StitchingDecision",
]
