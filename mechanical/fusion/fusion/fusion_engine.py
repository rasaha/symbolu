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

from typing import List, Dict, Optional, Tuple
import logging

from ..schemas.candidate import Candidate
from ..schemas.fusion_result import FusionResult, FusionContext
from .scorer import FusionScorer
from .conflict_resolver import ConflictResolver
from .routing import RoutingDecider
from .explanation import ExplanationGenerator


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
        
        # If only one candidate, select it
        if len(ranked_candidates) == 1:
            return ranked_candidates[0], "only_candidate"
        
        # Check if top candidate is clear winner
        top_score = scores[ranked_candidates[0].id]
        second_score = scores[ranked_candidates[1].id]
        
        # Clear winner threshold
        if top_score - second_score > 0.2:
            return ranked_candidates[0], "clear_winner"
        
        # Close competition: use conflict resolver
        logger.debug("Close competition detected, using conflict resolver")
        
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
