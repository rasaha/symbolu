"""
Fusion Contracts - Data Structures per Specification v1.1
==========================================================

This module defines the authoritative data contracts for the Fusion stage.
These contracts enforce the normative requirements from the specification.

NORMATIVE REQUIREMENTS (from spec Section 0.2):
- MUST receive only allowed candidates as input
- MUST NOT receive or reference Stitching diagnostic data
- MUST NOT re-validate constraints (confidence, entropy, domain caps, etc.)
- MUST rank candidates using its own scoring formula only
- MUST assume all input candidates are valid by construction
- MUST NOT override or bypass Stitching decisions

CRITICAL: This module MUST NOT import from agentic.core.stitching.contracts.
It may only import from agentic.core.stitching.handoff (the boundary interface).

Reference: docs/architecture/STITCHING_FUSION_SPECIFICATION.md
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ScoredCandidate:
    """
    A candidate with fusion score and components.

    This represents a candidate after Fusion scoring, with full
    explainability of how the score was computed.

    The fusion_score is COMPARABLE across candidates and is used
    for ranking. This is different from Stitching's diagnostic_scores
    which are NOT comparable.
    """
    candidate_id: str

    # Fusion score (comparable, for ranking)
    # Formula: α×HRM + β×LCM + γ×MoE + modifiers
    fusion_score: float

    # Score components (for explainability)
    score_components: Dict[str, float] = field(default_factory=dict)
    # Expected keys:
    #   hrm_contribution: weighted HRM score
    #   lcm_contribution: weighted LCM score
    #   moe_contribution: weighted MoE score
    #   context_adjustment: modifier effects
    #   smi_penalty: semantic mismatch penalty (if applicable)

    # Rank (1 = best, assigned after sorting)
    rank: int = 0

    # Tie-break info (if applicable)
    tie_break_applied: bool = False
    tie_break_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "candidate_id": self.candidate_id,
            "fusion_score": round(self.fusion_score, 4),
            "score_components": {
                k: round(v, 4) for k, v in self.score_components.items()
            },
            "rank": self.rank,
            "tie_break_applied": self.tie_break_applied,
            "tie_break_reason": self.tie_break_reason,
        }


@dataclass
class FusionRanking:
    """
    Output from Fusion stage.

    This is the AUTHORITATIVE output contract for FusionEngine.rank().

    NORMATIVE REQUIREMENTS:
    - selected_candidate_id is the winner based on fusion_score
    - rankings contains all candidates with comparable scores
    - routing contains decisions for DHA/Renderer
    - No Stitching diagnostic data appears in this structure

    The handoff from Stitching ensures that only allowed candidates
    reach this stage, so Fusion does NOT need to re-validate.
    """

    # Primary output: selected candidate
    selected_candidate_id: str
    selected_fusion_score: float

    # Full ranking (for audit and fallback)
    # Sorted by fusion_score descending, ranks assigned
    rankings: List[ScoredCandidate] = field(default_factory=list)

    # Routing decisions for DHA/Renderer
    routing: Dict[str, Any] = field(default_factory=dict)
    # Expected keys:
    #   render_mode: "rules" | "llm" | "auto"
    #   persona_hint: Optional persona identifier
    #   dha_tone_hint: Tone guidance for DHA
    #   use_rules_renderer: bool
    #   use_llm_renderer: bool

    # Explainability
    explain: Dict[str, Any] = field(default_factory=dict)
    # Expected keys:
    #   selection_reason: Why this candidate was selected
    #   channel_weights_used: α, β, γ values
    #   top_3_summary: Brief summary of top candidates
    #   tie_resolution: Tie-break details (if applicable)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Expected keys:
    #   total_candidates_evaluated: int
    #   channel_weights: Dict
    #   context_tier: str
    #   context_intent: str
    #   stitching_audit_id: str (for traceability)

    def get_top_k(self, k: int = 3) -> List[ScoredCandidate]:
        """Get top k ranked candidates."""
        return self.rankings[:k]

    def get_score_spread(self) -> float:
        """Get difference between first and second scores."""
        if len(self.rankings) < 2:
            return 1.0  # Clear winner by default
        return self.rankings[0].fusion_score - self.rankings[1].fusion_score

    def was_tie_break(self) -> bool:
        """Check if tie-breaking was needed."""
        if not self.rankings:
            return False
        return self.rankings[0].tie_break_applied

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/storage."""
        return {
            "selected_candidate_id": self.selected_candidate_id,
            "selected_fusion_score": round(self.selected_fusion_score, 4),
            "rankings": [sc.to_dict() for sc in self.rankings],
            "routing": self.routing,
            "explain": self.explain,
            "metadata": self.metadata,
        }


# Tie-break threshold: scores within this range are considered tied
TIE_THRESHOLD = 0.02


def apply_deterministic_tie_break(
    candidates: List[ScoredCandidate],
) -> List[ScoredCandidate]:
    """
    Apply deterministic tie-breaking per spec.

    NORMATIVE REQUIREMENT:
    - Tie-breaking MUST use deterministic rule (lexicographic candidate ID)

    This ensures repeatability: same input always produces same output.

    Args:
        candidates: List of ScoredCandidate, sorted by fusion_score desc

    Returns:
        List with tie-break markers applied
    """
    if len(candidates) < 2:
        return candidates

    result = list(candidates)

    # Check if top candidates are tied (within threshold)
    top_score = result[0].fusion_score
    tied_indices = [0]

    for i in range(1, len(result)):
        if abs(result[i].fusion_score - top_score) < TIE_THRESHOLD:
            tied_indices.append(i)
        else:
            break

    if len(tied_indices) > 1:
        # Sort tied candidates by candidate_id (lexicographic)
        tied = [result[i] for i in tied_indices]
        tied.sort(key=lambda x: x.candidate_id)

        # Mark tie-break applied
        for i, sc in enumerate(tied):
            sc.tie_break_applied = True
            sc.tie_break_reason = f"lexicographic_id_rank_{i+1}_of_{len(tied)}"

        # Put sorted tied candidates back
        for i, idx in enumerate(tied_indices):
            result[idx] = tied[i]

    return result


__all__ = [
    "ScoredCandidate",
    "FusionRanking",
    "TIE_THRESHOLD",
    "apply_deterministic_tie_break",
]
