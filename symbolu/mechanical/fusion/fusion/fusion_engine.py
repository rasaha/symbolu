"""
SOULPI FusionEngine v3.1 - Main Orchestrator
Deterministic reasoning fusion for HYBRID tier

Coordinates:
- Channel scoring (HRM, LCM, MoE)
- Conflict resolution
- Routing decisions
- Explainability generation

Part of mechanical layer - NO Symbol-U dependencies
Deterministic, explainable, patent-safe
"""

from typing import List, Dict, Optional, Tuple, Any, TYPE_CHECKING
import logging

from ..schemas.candidate import Candidate
from ..schemas.fusion_result import FusionResult, FusionContext
from .scorer import FusionScorer
from .conflict_resolver import ConflictResolver
from .routing import RoutingDecider
from .explanation import ExplanationGenerator
from .contracts import (
    ScoredCandidate as FusionScoredCandidate,
    FusionRanking,
    TIE_THRESHOLD,
    apply_deterministic_tie_break,
)

if TYPE_CHECKING:
    # IMPORTANT: Only import handoff for type checking
    # This enforces the boundary: Fusion cannot access Stitching internals
    from symbolu.core.stitching.handoff import StitchingToFusionHandoff


logger = logging.getLogger(__name__)


class FusionEngine:
    """
    Main FusionEngine orchestrator
    
    Blends three reasoning channels:
    - HRM (High-Reasoning Module): symbolic/abstract "WHY"
    - LCM (Linguistic Coherence Module): semantic clarity "WHAT"
    - MoE (Mixture of Experts): domain-specific facts "HOW"
    
    Process:
    1. Score all candidates across channels
    2. Resolve conflicts deterministically
    3. Make routing decisions
    4. Generate explanations
    """
    
    def __init__(
        self,
        channel_weights: Optional[Dict[str, float]] = None,
        enable_explanations: bool = True,
        debug_mode: bool = False
    ):
        """
        Initialize FusionEngine
        
        Args:
            channel_weights: Weights for HRM, LCM, MoE channels
                Default: {"hrm": 0.4, "lcm": 0.3, "moe": 0.3}
            enable_explanations: Generate detailed explanations
            debug_mode: Enable debug logging
        """
        self.channel_weights = channel_weights or {
            "hrm": 0.4,  # α - High-Reasoning weight
            "lcm": 0.3,  # β - Linguistic Coherence weight
            "moe": 0.3,  # γ - Mixture of Experts weight
        }
        
        # Initialize components
        self.scorer = FusionScorer(self.channel_weights)
        self.conflict_resolver = ConflictResolver()
        self.routing_decider = RoutingDecider()
        self.explainer = ExplanationGenerator()
        
        # Configuration
        self.enable_explanations = enable_explanations
        self.debug_mode = debug_mode
        
        if debug_mode:
            logger.setLevel(logging.DEBUG)
        
        logger.info(f"FusionEngine v3.1 initialized with weights: {self.channel_weights}")
    
    def fuse(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> FusionResult:
        """
        Main fusion method
        
        Args:
            candidates: List of candidate responses
            context: MLCR decision and operational context
            
        Returns:
            FusionResult with selected candidate and routing
        """
        if not candidates:
            raise ValueError("No candidates provided for fusion")
        
        logger.info(f"Fusing {len(candidates)} candidates for tier={context.tier}, intent={context.intent}")
        
        # Step 1: Score all candidates
        scores = self.scorer.score_all_candidates(candidates, context)
        logger.debug(f"Scored {len(scores)} candidates")
        
        # Step 2: Rank candidates by score
        ranked_candidates = self.scorer.rank_candidates(candidates, context)
        logger.debug(f"Ranked candidates: {[c.id for c in ranked_candidates[:3]]}")
        
        # Step 3: Resolve conflicts (if needed)
        selected_candidate, resolution_reason = self._select_candidate(
            ranked_candidates, context, scores
        )
        
        if selected_candidate is None:
            raise RuntimeError("No suitable candidate found after conflict resolution")
        
        fusion_score = scores[selected_candidate.id]
        logger.info(
            f"Selected candidate: {selected_candidate.id} "
            f"(score={fusion_score:.4f}, reason={resolution_reason})"
        )
        
        # Step 4: Make routing decisions
        routing = self.routing_decider.make_routing_decision(
            selected_candidate, context, fusion_score
        )
        logger.debug(f"Routing: {routing['render_mode']} mode")
        
        # Step 5: Generate explanations
        explain = {}
        if self.enable_explanations:
            explain = self.explainer.generate_complete_explanation(
                selected_candidate,
                fusion_score,
                ranked_candidates,
                scores,
                resolution_reason,
                routing,
                context
            )
        
        # Step 6: Create FusionResult
        result = FusionResult(
            selected_candidate=selected_candidate,
            fusion_score=fusion_score,
            ranked_candidates=ranked_candidates,
            routing=routing,
            explain=explain,
            metadata={
                "resolution_reason": resolution_reason,
                "total_candidates": len(candidates),
                "channel_weights": self.channel_weights,
            }
        )
        
        # Step 7: Debug report (if enabled)
        if self.debug_mode:
            debug_report = self.explainer.generate_debug_report(
                selected_candidate,
                fusion_score,
                ranked_candidates,
                scores,
                routing,
                context
            )
            logger.debug(f"\n{debug_report}")
        
        return result

    def rank(
        self,
        handoff: "StitchingToFusionHandoff",
    ) -> FusionRanking:
        """
        Rank candidates from Stitching handoff (per spec v1.1).

        This is the NORMATIVE entry point per STITCHING_FUSION_SPECIFICATION.md.

        NORMATIVE REQUIREMENTS:
        - MUST receive only allowed candidates as input (via handoff)
        - MUST NOT receive or reference Stitching diagnostic data
        - MUST NOT re-validate constraints
        - MUST rank candidates using its own scoring formula only
        - MUST assume all input candidates are valid by construction
        - MUST NOT override or bypass Stitching decisions

        Args:
            handoff: StitchingToFusionHandoff containing allowed candidates and context

        Returns:
            FusionRanking with selected candidate and rankings
        """
        # BOUNDARY ASSERTION: Verify handoff is the correct type
        # This prevents accidentally passing raw candidates or StitchingDecision
        from symbolu.core.stitching.handoff import StitchingToFusionHandoff
        if not isinstance(handoff, StitchingToFusionHandoff):
            raise TypeError(
                f"rank() requires StitchingToFusionHandoff, got {type(handoff).__name__}. "
                "Use StitchingToFusionHandoff.from_decision() to create handoff."
            )

        candidates = handoff.allowed_candidates
        context = handoff.context

        if not candidates:
            raise ValueError("No candidates in handoff. Cannot rank empty candidate set.")

        logger.info(
            f"Ranking {len(candidates)} candidates from handoff "
            f"(audit_id={handoff.stitching_audit_id})"
        )

        # Step 1: Score all candidates using Fusion's formula
        # IMPORTANT: We use ONLY channel scores (HRM/LCM/MoE), NOT Stitching diagnostics
        scored_candidates: List[FusionScoredCandidate] = []

        for candidate in candidates:
            # Compute channel scores
            channel_scores = self.scorer.channel_scorer.score_all_channels(candidate, context)

            # Compute weighted fusion score
            hrm_contribution = self.channel_weights["hrm"] * channel_scores["hrm"]
            lcm_contribution = self.channel_weights["lcm"] * channel_scores["lcm"]
            moe_contribution = self.channel_weights["moe"] * channel_scores["moe"]

            base_score = hrm_contribution + lcm_contribution + moe_contribution

            # Apply modifiers
            final_score = self.scorer.apply_modifiers(base_score, candidate, context)

            scored_candidates.append(FusionScoredCandidate(
                candidate_id=candidate.id,
                fusion_score=final_score,
                score_components={
                    "hrm_contribution": round(hrm_contribution, 4),
                    "lcm_contribution": round(lcm_contribution, 4),
                    "moe_contribution": round(moe_contribution, 4),
                    "base_score": round(base_score, 4),
                    "modifiers_applied": round(final_score - base_score, 4),
                },
            ))

        # Step 2: Sort by fusion_score descending
        scored_candidates.sort(key=lambda x: x.fusion_score, reverse=True)

        # Step 3: Apply deterministic tie-breaking (per spec: lexicographic ID)
        scored_candidates = apply_deterministic_tie_break(scored_candidates)

        # Step 4: Assign ranks
        for i, sc in enumerate(scored_candidates):
            sc.rank = i + 1

        # Step 5: Select winner (always rank 1 after tie-break)
        winner = scored_candidates[0]
        selected_candidate = next(
            c for c in candidates if c.id == winner.candidate_id
        )

        # Step 6: Determine routing
        routing = self.routing_decider.make_routing_decision(
            selected_candidate, context, winner.fusion_score
        )

        # Step 7: Build explainability
        explain = {
            "selection_reason": self._build_selection_reason(winner, scored_candidates),
            "channel_weights_used": self.channel_weights,
            "top_3_summary": [
                {"id": sc.candidate_id, "score": round(sc.fusion_score, 4)}
                for sc in scored_candidates[:3]
            ],
        }
        if winner.tie_break_applied:
            explain["tie_resolution"] = winner.tie_break_reason

        # Step 8: Build metadata
        metadata = {
            "total_candidates_evaluated": len(scored_candidates),
            "channel_weights": self.channel_weights,
            "context_tier": context.tier,
            "context_intent": context.intent,
            "stitching_audit_id": handoff.stitching_audit_id,
            "cross_domain_count": handoff.cross_domain_info.get("cross_domain_count", 0),
        }

        return FusionRanking(
            selected_candidate_id=winner.candidate_id,
            selected_fusion_score=winner.fusion_score,
            rankings=scored_candidates,
            routing=routing,
            explain=explain,
            metadata=metadata,
        )

    def _build_selection_reason(
        self,
        winner: FusionScoredCandidate,
        all_ranked: List[FusionScoredCandidate],
    ) -> str:
        """Build human-readable selection reason."""
        if len(all_ranked) == 1:
            return "only_candidate"

        spread = winner.fusion_score - all_ranked[1].fusion_score
        if spread > TIE_THRESHOLD:
            return f"clear_winner_by_{spread:.3f}"
        elif winner.tie_break_applied:
            return f"tie_break_applied_{winner.tie_break_reason}"
        else:
            return "highest_score"

    def _select_candidate(
        self,
        ranked_candidates: List[Candidate],
        context: FusionContext,
        scores: Dict[str, float]
    ) -> Tuple[Optional[Candidate], str]:
        """
        Select candidate using conflict resolution if needed

        Returns: (selected_candidate, resolution_reason)
        """
        if not ranked_candidates:
            return None, "no_candidates"

        # Apply safety filters first for regulated mode (even for single candidates)
        if context.is_regulated():
            safe_candidates = self.conflict_resolver.apply_safety_filters(
                ranked_candidates, context
            )
            if not safe_candidates:
                return None, "all_filtered_by_safety"
            ranked_candidates = [c for c in ranked_candidates if c in safe_candidates]
            if not ranked_candidates:
                return None, "all_filtered_by_safety"

        # If only one candidate remains, select it
        if len(ranked_candidates) == 1:
            return ranked_candidates[0], "only_candidate"

        # Check if top candidate is clear winner
        top_score = scores[ranked_candidates[0].id]
        second_score = scores[ranked_candidates[1].id]

        # Winner threshold: respect the ranking from scorer which includes SMI penalty
        # Use conflict resolver for close scores (< 0.02 difference)
        if top_score - second_score > 0.02:
            return ranked_candidates[0], "clear_winner"

        # True tie: use conflict resolver
        logger.debug("True tie detected, using conflict resolver")

        selected, reason = self.conflict_resolver.resolve_conflict(
            ranked_candidates[:5],  # Consider top 5 for conflict resolution
            context
        )

        return selected, f"conflict_resolved_{reason}"
    
    def fuse_with_fallback(
        self,
        candidates: List[Candidate],
        context: FusionContext,
        fallback_candidate: Optional[Candidate] = None
    ) -> FusionResult:
        """
        Fuse with fallback handling
        
        If fusion fails or all candidates filtered out,
        returns fallback candidate with appropriate routing
        
        Args:
            candidates: List of candidates
            context: Fusion context
            fallback_candidate: Fallback if fusion fails
            
        Returns:
            FusionResult (with fallback if needed)
        """
        try:
            return self.fuse(candidates, context)
        
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Fusion failed: {e}. Using fallback.")
            
            if fallback_candidate is None:
                # Create generic fallback
                fallback_candidate = Candidate(
                    id="fallback_generic",
                    text="I understand your query. Let me help you with that.",
                    source="TEMPLATE",
                    channel_scores={"hrm": 0.5, "lcm": 0.5, "moe": 0.5},
                    confidence=0.6
                )
            
            # Use conservative routing for fallback
            routing = {
                "render_mode": "rules",
                "use_rules_renderer": True,
                "use_llm_renderer": False,
                "persona_hint": "professional",
                "dha_tone_hint": "sweet_resonance",
                "reasoning": {
                    "mode_reason": "Fallback due to fusion failure",
                    "persona_reason": "Conservative default",
                    "tone_reason": "Safe delivery mode"
                }
            }
            
            return FusionResult(
                selected_candidate=fallback_candidate,
                fusion_score=0.5,
                ranked_candidates=[fallback_candidate],
                routing=routing,
                explain={"fallback_used": True, "reason": str(e)},
                metadata={"fallback": True}
            )
    
    def update_channel_weights(self, new_weights: Dict[str, float]):
        """
        Update channel weights (for adaptation/personalization)
        
        Args:
            new_weights: New weights for channels
        """
        # Validate
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        
        self.channel_weights = new_weights
        self.scorer = FusionScorer(new_weights)
        
        logger.info(f"Updated channel weights: {new_weights}")
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get engine statistics
        
        Returns: Dict with configuration and state
        """
        return {
            "version": "3.1.0",
            "channel_weights": self.channel_weights,
            "enable_explanations": self.enable_explanations,
            "debug_mode": self.debug_mode,
            "components": {
                "scorer": "FusionScorer",
                "conflict_resolver": "ConflictResolver",
                "routing_decider": "RoutingDecider",
                "explainer": "ExplanationGenerator"
            }
        }


# Convenience function for simple fusion
def fuse_candidates(
    candidates: List[Candidate],
    context: FusionContext,
    **engine_kwargs
) -> FusionResult:
    """
    Convenience function for one-off fusion
    
    Creates engine and fuses candidates
    
    Args:
        candidates: List of candidates
        context: Fusion context
        **engine_kwargs: Arguments for FusionEngine
        
    Returns:
        FusionResult
    """
    engine = FusionEngine(**engine_kwargs)
    return engine.fuse(candidates, context)
