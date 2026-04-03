"""
Stitching Engine - Cross-Domain Reasoning via Constrained Optimization
=======================================================================

This module implements the Stitching Encoder for Symbol-U, which performs
cross-domain reasoning through constrained optimization:

    maximize   Σ Relevance(c)
    minimize   Redundancy(c) + DomainJumpPenalty(c)

    subject to:
        confidence(c) ≥ θ_conf
        entropy(c) ≤ θ_entropy
        count(cross_domain) ≤ N_max

Patent Reference:
    Claim [2]  - Relevance scoring with resonance coupling
    Claim [12] - Resonance modulation coefficient λres
    Claim [13] - Governance gates including cross-domain entropy gate

Key Design Principles:
    1. Claude is NOT "thinking" - it optimizes a constrained symbolic objective
    2. Domain jumps are PRICED, not blocked - allows controlled cross-domain reasoning
    3. All decisions are AUDITABLE via explicit penalty breakdowns
    4. Aspects are domain-AGNOSTIC - enables structural pattern matching

Architecture Position:
    TTOR Router → Mappers (HRM/LCM/LAM) → [STITCHING ENCODER] → Fusion → DHA → Renderer
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
import logging

from agentic.core.stitching.penalties import (
    PenaltyCalculator,
    PenaltyConfig,
    ScoredCandidate,
    StitchingConstraints,
)
from agentic.core.stitching.domain_distance import (
    get_domain_distance,
    get_aspect_overlap,
    is_cross_domain,
    UNIVERSAL_ASPECTS,
)
from agentic.core.stitching.contracts import (
    RejectionReason,
    CandidateDecision,
    StitchingDecision,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Stitching Result (Output Format per Specification)
# =============================================================================

@dataclass
class StitchingResult:
    """
    Output of the Stitching Encoder (per prompt specification).

    Includes:
    - selected_candidates: List of selected CandidateEntry objects
    - scores: Dict mapping candidate_id to final score
    - diagnostics: Breakdown of relevance, redundancy, domain_jump
    """
    selected_candidates: List[Any]
    scores: Dict[str, float]
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "selected_candidates": [
                getattr(c, "id", str(i)) for i, c in enumerate(self.selected_candidates)
            ],
            "scores": self.scores,
            "diagnostics": self.diagnostics,
        }


# =============================================================================
# Query Context
# =============================================================================

@dataclass
class QueryContext:
    """
    Context from the analyzed query for stitching.

    Contains domain information and aspect vectors extracted from
    the query for cross-domain relevance matching.
    """
    text: str
    domain: str = "generic"
    aspect_vector: Dict[str, float] = field(default_factory=dict)
    entropy: float = 0.0
    confidence: float = 1.0
    intent: Optional[str] = None  # WHY, WHAT, HOW

    # Channel preferences from TTOR
    prefer_hrm: bool = False
    prefer_lcm: bool = False
    prefer_moe: bool = False


# =============================================================================
# Stitching Engine Configuration
# =============================================================================

@dataclass
class StitchingConfig:
    """Configuration for the Stitching Engine."""

    # Beam search
    beam_size: int = 10
    max_candidates: int = 50

    # Relevance weights
    aspect_weight: float = 0.60      # Weight for aspect-based relevance
    channel_weight: float = 0.40     # Weight for channel scores (HRM/LCM/MoE)

    # Channel weights (α, β, γ from patent)
    hrm_weight: float = 0.40   # High-Reasoning Module
    lcm_weight: float = 0.30   # Linguistic Coherence Module
    moe_weight: float = 0.30   # Mixture of Experts

    # Penalty configuration
    penalty_config: PenaltyConfig = field(default_factory=PenaltyConfig)

    # Constraints
    constraints: StitchingConstraints = field(default_factory=StitchingConstraints)

    # Logging
    enable_audit_log: bool = True


# Default configuration
DEFAULT_STITCHING_CONFIG = StitchingConfig()


# =============================================================================
# Stitching Engine
# =============================================================================

class StitchingEngine:
    """
    Scores and selects best candidates using Symbol-U stitching algorithm.

    This engine implements cross-domain reasoning via constrained optimization:
    - Relevance is computed using domain-agnostic aspects
    - Penalties are applied for redundancy and domain jumps
    - Constraints enforce quality and limit cross-domain sprawl

    The engine does NOT "reason" - it optimizes a well-defined objective.
    """

    def __init__(self, config: Optional[StitchingConfig] = None):
        """Initialize with optional custom configuration."""
        self.config = config or DEFAULT_STITCHING_CONFIG
        self.penalty_calculator = PenaltyCalculator(self.config.penalty_config)
        self._audit_log: List[Dict[str, Any]] = []

    def score_candidates(
        self,
        candidates: List[Any],
        context: QueryContext,
    ) -> List[ScoredCandidate]:
        """
        Score all candidates using the stitching objective.

        Implements:
            Score(c) = Relevance(c) - Redundancy(c) - DomainJumpPenalty(c)

        Subject to constraint enforcement.

        Args:
            candidates: List of candidates to score
            context: Query context with domain and aspect information

        Returns:
            List of ScoredCandidate objects, sorted by score descending
        """
        if not candidates:
            return []

        scored = []
        selected = []  # For redundancy calculation
        domain_jump_count = 0

        # Sort candidates by initial relevance for greedy selection
        candidates_with_relevance = [
            (c, self._compute_relevance(c, context))
            for c in candidates
        ]
        candidates_with_relevance.sort(key=lambda x: x[1], reverse=True)

        for candidate, relevance in candidates_with_relevance:
            # Check if this is a cross-domain candidate
            candidate_domain = getattr(candidate, "domain", "generic") or "generic"
            is_cross = is_cross_domain(context.domain, candidate_domain)

            # Check constraints
            passes, reason = self.config.constraints.passes(
                candidate,
                domain_jump_count if is_cross else 0,
            )

            if not passes:
                if self.config.enable_audit_log:
                    self._log_rejection(candidate, reason)
                continue

            # Compute penalties
            penalties = self.penalty_calculator.compute_all_penalties(
                candidate,
                selected,
                context.domain,
                context.aspect_vector,
            )

            # Compute final score
            final_score = relevance - penalties["total"]

            # Check minimum score threshold
            if final_score < self.config.constraints.min_score:
                if self.config.enable_audit_log:
                    self._log_rejection(candidate, f"score {final_score:.3f} < min")
                continue

            # Check redundancy threshold
            if self.penalty_calculator.is_too_redundant(candidate, selected):
                if self.config.enable_audit_log:
                    self._log_rejection(candidate, "too redundant")
                continue

            # Accept candidate
            scored_candidate = ScoredCandidate(
                candidate=candidate,
                relevance=relevance,
                penalties=penalties,
                final_score=final_score,
            )
            scored.append(scored_candidate)
            selected.append(candidate)

            # Track domain jumps
            if is_cross:
                domain_jump_count += 1

            # Check if we have enough candidates
            if len(scored) >= self.config.beam_size:
                break

        # Sort by final score and assign ranks
        scored.sort(key=lambda x: x.final_score, reverse=True)
        for i, sc in enumerate(scored):
            sc.rank = i + 1

        if self.config.enable_audit_log:
            self._log_selection(scored, context)

        return scored

    def select_best(
        self,
        candidates: List[Any],
        context: QueryContext,
        beam_size: Optional[int] = None,
    ) -> List[Any]:
        """
        Select top candidates using stitching algorithm.

        Convenience method that returns just the candidate objects,
        not the full ScoredCandidate wrappers.

        Args:
            candidates: List of candidates to select from
            context: Query context
            beam_size: Override default beam size

        Returns:
            List of selected candidate objects
        """
        beam = beam_size or self.config.beam_size
        scored = self.score_candidates(candidates, context)
        return [sc.candidate for sc in scored[:beam]]

    def stitch(
        self,
        candidates: List[Any],
        context: QueryContext,
    ) -> StitchingResult:
        """
        Execute stitching and return StitchingResult (per prompt specification).

        This is the main entry point that returns the output format:
        - selected_candidates: List[CandidateEntry]
        - scores: Dict[candidate_id, float]
        - diagnostics: { "relevance": float, "redundancy": float, "domain_jump": float }

        Args:
            candidates: List of candidates to select from
            context: Query context

        Returns:
            StitchingResult with selected candidates, scores, and diagnostics
        """
        scored = self.score_candidates(candidates, context)

        # Build output per specification
        selected_candidates = [sc.candidate for sc in scored]

        scores = {
            getattr(sc.candidate, "id", f"c_{i}"): sc.final_score
            for i, sc in enumerate(scored)
        }

        # Aggregate diagnostics
        total_relevance = sum(sc.relevance for sc in scored)
        total_redundancy = sum(sc.redundancy_penalty for sc in scored)
        total_domain_jump = sum(sc.domain_jump_penalty for sc in scored)

        diagnostics = {
            "relevance": total_relevance,
            "redundancy": total_redundancy,
            "domain_jump": total_domain_jump,
            "selected_count": len(scored),
            "cross_domain_count": sum(1 for sc in scored if sc.is_cross_domain),
            "per_candidate": [sc.to_dict() for sc in scored],
        }

        return StitchingResult(
            selected_candidates=selected_candidates,
            scores=scores,
            diagnostics=diagnostics,
        )

    def evaluate(
        self,
        candidates: List[Any],
        context: QueryContext,
    ) -> StitchingDecision:
        """
        Evaluate candidates and return StitchingDecision (per spec v1.1).

        This is the NORMATIVE entry point per STITCHING_FUSION_SPECIFICATION.md.

        NORMATIVE REQUIREMENTS:
        - MUST return boolean eligibility per candidate
        - MUST NOT produce comparable or optimization scores
        - Diagnostic values are for audit/debug only
        - MUST NOT select, rank, or prioritize candidates

        Args:
            candidates: List of candidates to evaluate
            context: Query context with domain and aspect information

        Returns:
            StitchingDecision with allowed_candidate_ids and audit trail
        """
        import uuid
        from datetime import datetime

        if not candidates:
            return StitchingDecision(
                allowed_candidate_ids=[],
                decisions={},
                diagnostics={"total_evaluated": 0, "total_allowed": 0},
                audit={"audit_id": str(uuid.uuid4())[:8], "timestamp": datetime.utcnow().isoformat()},
            )

        decisions: Dict[str, CandidateDecision] = {}
        allowed_ids: List[str] = []
        selected_for_redundancy: List[Any] = []  # Track for redundancy calculation
        domain_jump_count = 0
        cross_domain_count = 0
        domains_involved: List[str] = [context.domain]

        # Sort by relevance for greedy processing (affects redundancy calculation)
        candidates_with_relevance = [
            (c, self._compute_relevance(c, context))
            for c in candidates
        ]
        candidates_with_relevance.sort(key=lambda x: x[1], reverse=True)

        for candidate, relevance in candidates_with_relevance:
            candidate_id = getattr(candidate, "id", f"unknown_{id(candidate)}")
            candidate_domain = getattr(candidate, "domain", "generic") or "generic"
            is_cross = is_cross_domain(context.domain, candidate_domain)

            # Track domains
            if candidate_domain not in domains_involved:
                domains_involved.append(candidate_domain)

            # Initialize constraint status
            constraint_status = {}
            audit_notes: List[str] = []
            rejection_reason: Optional[RejectionReason] = None
            rejection_detail: Optional[str] = None

            # Check confidence constraint
            confidence = getattr(candidate, "confidence", 1.0)
            constraint_status["confidence_ok"] = confidence >= self.config.constraints.min_confidence
            if not constraint_status["confidence_ok"]:
                rejection_reason = RejectionReason.LOW_CONFIDENCE
                rejection_detail = f"confidence {confidence:.3f} < threshold {self.config.constraints.min_confidence}"
                audit_notes.append(rejection_detail)

            # Check entropy constraint
            entropy = getattr(candidate, "entropy", 0.0)
            constraint_status["entropy_ok"] = entropy <= self.config.constraints.max_entropy
            if rejection_reason is None and not constraint_status["entropy_ok"]:
                rejection_reason = RejectionReason.HIGH_ENTROPY
                rejection_detail = f"entropy {entropy:.3f} > threshold {self.config.constraints.max_entropy}"
                audit_notes.append(rejection_detail)

            # Check domain jump cap
            would_exceed_cap = is_cross and domain_jump_count >= self.config.constraints.max_domain_jumps
            constraint_status["domain_cap_ok"] = not would_exceed_cap
            if rejection_reason is None and not constraint_status["domain_cap_ok"]:
                rejection_reason = RejectionReason.DOMAIN_JUMP_CAP
                rejection_detail = f"domain jump cap reached ({self.config.constraints.max_domain_jumps})"
                audit_notes.append(rejection_detail)

            # Compute penalties for diagnostic purposes ONLY
            penalties = self.penalty_calculator.compute_all_penalties(
                candidate,
                selected_for_redundancy,
                context.domain,
                context.aspect_vector,
            )

            # Diagnostic score (NOT for ranking - audit only)
            diagnostic_score = relevance - penalties["total"]

            # Check minimum score
            constraint_status["score_ok"] = diagnostic_score >= self.config.constraints.min_score
            if rejection_reason is None and not constraint_status["score_ok"]:
                rejection_reason = RejectionReason.LOW_SCORE
                rejection_detail = f"diagnostic_score {diagnostic_score:.3f} < threshold {self.config.constraints.min_score}"
                audit_notes.append(rejection_detail)

            # Check redundancy
            is_redundant = self.penalty_calculator.is_too_redundant(candidate, selected_for_redundancy)
            constraint_status["redundancy_ok"] = not is_redundant
            if rejection_reason is None and not constraint_status["redundancy_ok"]:
                rejection_reason = RejectionReason.TOO_REDUNDANT
                rejection_detail = f"redundancy {penalties['redundancy']:.3f} >= threshold"
                audit_notes.append(rejection_detail)

            # Determine if allowed
            allowed = rejection_reason is None

            # Build diagnostic scores (for audit only)
            diagnostic_scores = {
                "relevance": relevance,
                "redundancy_penalty": penalties["redundancy"],
                "domain_jump_penalty": penalties["domain_jump"],
                "total_diagnostic": diagnostic_score,
                # Note: These are NOT comparable across candidates
            }

            # Record decision
            decisions[candidate_id] = CandidateDecision(
                candidate_id=candidate_id,
                allowed=allowed,
                diagnostic_scores=diagnostic_scores,
                rejection_reason=rejection_reason,
                rejection_detail=rejection_detail,
                audit_notes=audit_notes,
                constraint_status=constraint_status,
            )

            if allowed:
                allowed_ids.append(candidate_id)
                selected_for_redundancy.append(candidate)
                if is_cross:
                    domain_jump_count += 1
                    cross_domain_count += 1

                # Check beam size limit
                if len(allowed_ids) >= self.config.beam_size:
                    break

        # Build aggregate diagnostics
        diagnostics = {
            "total_evaluated": len(decisions),
            "total_allowed": len(allowed_ids),
            "total_rejected": len(decisions) - len(allowed_ids),
            "cross_domain_count": cross_domain_count,
            "domains_involved": domains_involved,
            "rejection_summary": self._build_rejection_summary(decisions),
        }

        # Build audit metadata
        audit = {
            "audit_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.utcnow().isoformat(),
            "config_snapshot": {
                "beam_size": self.config.beam_size,
                "min_confidence": self.config.constraints.min_confidence,
                "max_entropy": self.config.constraints.max_entropy,
                "max_domain_jumps": self.config.constraints.max_domain_jumps,
                "min_score": self.config.constraints.min_score,
            },
            "query_domain": context.domain,
        }

        return StitchingDecision(
            allowed_candidate_ids=allowed_ids,
            decisions=decisions,
            diagnostics=diagnostics,
            audit=audit,
        )

    def _build_rejection_summary(
        self,
        decisions: Dict[str, CandidateDecision],
    ) -> Dict[str, int]:
        """Build summary of rejection reasons."""
        summary: Dict[str, int] = {}
        for d in decisions.values():
            if not d.allowed and d.rejection_reason:
                key = d.rejection_reason.value
                summary[key] = summary.get(key, 0) + 1
        return summary

    def apply_penalties(
        self,
        candidates: List[Any],
        context: QueryContext,
    ) -> List[Tuple[Any, Dict[str, float]]]:
        """
        Apply penalties to candidates and return penalty breakdowns.

        Useful for debugging and audit without full selection.

        Args:
            candidates: List of candidates
            context: Query context

        Returns:
            List of (candidate, penalty_dict) tuples
        """
        results = []
        selected = []

        for candidate in candidates:
            penalties = self.penalty_calculator.compute_all_penalties(
                candidate,
                selected,
                context.domain,
                context.aspect_vector,
            )
            results.append((candidate, penalties))
            selected.append(candidate)

        return results

    def _compute_relevance(
        self,
        candidate: Any,
        context: QueryContext,
    ) -> float:
        """
        Compute relevance score for a candidate.

        Formula:
            Relevance = w_asp × AspectScore + w_ch × ChannelScore

        Where:
            AspectScore = Σ_k query_aspect[k] × candidate_aspect[k]
            ChannelScore = α×HRM + β×LCM + γ×MoE

        Args:
            candidate: The candidate to score
            context: Query context with aspect vector

        Returns:
            Relevance score in range [0, 1]
        """
        # 1. Aspect-based relevance (domain-agnostic structural matching)
        aspect_score = self._compute_aspect_relevance(candidate, context)

        # 2. Channel-based relevance (HRM/LCM/MoE scores)
        channel_score = self._compute_channel_relevance(candidate, context)

        # Combine with weights
        relevance = (
            self.config.aspect_weight * aspect_score +
            self.config.channel_weight * channel_score
        )

        return min(max(relevance, 0.0), 1.0)

    def _compute_aspect_relevance(
        self,
        candidate: Any,
        context: QueryContext,
    ) -> float:
        """
        Compute aspect-based relevance using domain-agnostic structural patterns.

        This enables cross-domain matching via shared aspects like:
        - ENTROPY (disorder/chaos)
        - CAUSALITY (cause-effect chains)
        - AGENCY (actor capability)
        - BALANCE (equilibrium)

        Formula (from prompt specification):
            relevance = Σ (aspect_weight[k] * min(query.aspect[k], candidate.aspect[k]))

        This uses min-based overlap, NOT cosine similarity.
        """
        query_aspects = context.aspect_vector
        candidate_aspects = getattr(candidate, "aspect_vector", {})

        if not query_aspects or not candidate_aspects:
            # Fall back to ontology/kosha signature if available
            return self._compute_signature_relevance(candidate)

        # Compute min-based aspect overlap (per prompt specification)
        # relevance = Σ (aspect_weight[k] * min(query.aspect[k], candidate.aspect[k]))
        overlap_sum = 0.0
        for aspect_key in query_aspects:
            if aspect_key in candidate_aspects:
                q_val = query_aspects[aspect_key]
                c_val = candidate_aspects[aspect_key]
                # aspect_weight defaults to 1.0 if not specified
                overlap_sum += min(q_val, c_val)

        # Normalize to [0, 1] range
        if query_aspects:
            max_possible = sum(query_aspects.values())
            return overlap_sum / max_possible if max_possible > 0 else 0.0
        return 0.0

    def _compute_signature_relevance(
        self,
        candidate: Any,
    ) -> float:
        """
        Fallback relevance from ontology/kosha signatures.

        Used when aspect vectors are not available.
        """
        ontology = getattr(candidate, "ontology_signature", None)
        kosha = getattr(candidate, "kosha_signature", None)

        if ontology and isinstance(ontology, list):
            # Use mean of ontology signature as proxy
            return sum(ontology) / len(ontology) if ontology else 0.5

        return 0.5  # Default neutral relevance

    def _compute_channel_relevance(
        self,
        candidate: Any,
        context: QueryContext,
    ) -> float:
        """
        Compute channel-based relevance from HRM/LCM/MoE scores.

        Formula:
            ChannelScore = α×HRM + β×LCM + γ×MoE

        Where α, β, γ are configurable weights (default 0.4, 0.3, 0.3).
        """
        channel_scores = getattr(candidate, "channel_scores", {})

        if not channel_scores:
            return getattr(candidate, "relevance_score", 0.5)

        # Normalize channel names
        hrm = channel_scores.get("hrm", channel_scores.get("HRM", 0.0))
        lcm = channel_scores.get("lcm", channel_scores.get("LCM", 0.0))
        moe = channel_scores.get("moe", channel_scores.get("MoE", 0.0))

        # Adjust weights based on context preferences
        hrm_w = self.config.hrm_weight
        lcm_w = self.config.lcm_weight
        moe_w = self.config.moe_weight

        if context.prefer_hrm:
            hrm_w *= 1.5
        if context.prefer_lcm:
            lcm_w *= 1.5
        if context.prefer_moe:
            moe_w *= 1.5

        # Normalize weights
        total_w = hrm_w + lcm_w + moe_w
        if total_w > 0:
            hrm_w /= total_w
            lcm_w /= total_w
            moe_w /= total_w

        return hrm_w * hrm + lcm_w * lcm + moe_w * moe

    def _log_rejection(self, candidate: Any, reason: str):
        """Log a candidate rejection for audit."""
        self._audit_log.append({
            "action": "rejected",
            "candidate_id": getattr(candidate, "id", "unknown"),
            "domain": getattr(candidate, "domain", "generic"),
            "reason": reason,
        })

    def _log_selection(
        self,
        scored: List[ScoredCandidate],
        context: QueryContext,
    ):
        """Log selection results for audit."""
        self._audit_log.append({
            "action": "selection_complete",
            "query_domain": context.domain,
            "selected_count": len(scored),
            "cross_domain_count": sum(1 for sc in scored if sc.is_cross_domain),
            "candidates": [sc.to_dict() for sc in scored],
        })

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get the audit log for explainability."""
        return self._audit_log.copy()

    def clear_audit_log(self):
        """Clear the audit log."""
        self._audit_log.clear()

    def explain_selection(
        self,
        scored: List[ScoredCandidate],
        context: QueryContext,
    ) -> str:
        """
        Generate human-readable explanation of selection.

        For debugging and transparency.
        """
        lines = [
            f"Stitching Selection for domain '{context.domain}'",
            f"Selected {len(scored)} candidates:",
            "",
        ]

        for sc in scored:
            domain = getattr(sc.candidate, "domain", "generic")
            cross = " [CROSS-DOMAIN]" if sc.is_cross_domain else ""
            lines.append(
                f"  #{sc.rank}: {domain}{cross}"
            )
            lines.append(
                f"       Relevance: {sc.relevance:.3f}"
            )
            lines.append(
                f"       Penalties: redundancy={sc.redundancy_penalty:.3f}, "
                f"domain_jump={sc.domain_jump_penalty:.3f}"
            )
            lines.append(
                f"       Final Score: {sc.final_score:.3f}"
            )
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# Factory Functions
# =============================================================================

def create_stitching_engine(
    beam_size: int = 10,
    max_domain_jumps: int = 3,
    domain_jump_lambda: float = 0.30,
) -> StitchingEngine:
    """
    Create a configured Stitching Engine.

    Convenience factory for common configurations.

    Args:
        beam_size: Number of candidates to select
        max_domain_jumps: Maximum cross-domain candidates
        domain_jump_lambda: Weight for domain jump penalty

    Returns:
        Configured StitchingEngine instance
    """
    penalty_config = PenaltyConfig(
        domain_jump_lambda=domain_jump_lambda,
        max_domain_jumps=max_domain_jumps,
    )

    constraints = StitchingConstraints(
        max_domain_jumps=max_domain_jumps,
        max_candidates=beam_size,
    )

    config = StitchingConfig(
        beam_size=beam_size,
        penalty_config=penalty_config,
        constraints=constraints,
    )

    return StitchingEngine(config)


def create_query_context(
    text: str,
    domain: str = "generic",
    aspect_vector: Optional[Dict[str, float]] = None,
) -> QueryContext:
    """
    Create a QueryContext for stitching.

    Args:
        text: Query text
        domain: Query domain
        aspect_vector: Optional pre-computed aspect vector

    Returns:
        QueryContext instance
    """
    return QueryContext(
        text=text,
        domain=domain,
        aspect_vector=aspect_vector or {},
    )


__all__ = [
    "StitchingEngine",
    "StitchingConfig",
    "StitchingResult",
    "QueryContext",
    "create_stitching_engine",
    "create_query_context",
    "DEFAULT_STITCHING_CONFIG",
]
