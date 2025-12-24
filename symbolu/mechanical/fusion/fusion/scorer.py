"""
FusionEngine Scorer
Calculates weighted fusion scores for candidates

Implements deterministic scoring across three channels:
- HRM (symbolic/abstract reasoning)
- LCM (linguistic coherence)
- MoE (domain expertise)
"""

from typing import Dict, List
import math
from ..schemas.candidate import Candidate
from ..schemas.fusion_result import FusionContext


class ChannelScorer:
    """
    Scores individual channels for candidates
    
    Each channel represents a different reasoning aspect:
    - HRM: Abstract/symbolic reasoning (WHY questions)
    - LCM: Semantic clarity and linguistic coherence (WHAT questions)
    - MoE: Domain-specific expertise (HOW questions)
    """
    
    def __init__(self, channel_weights: Dict[str, float] = None):
        """
        Initialize channel scorer
        
        Args:
            channel_weights: Weights for each channel (α, β, γ)
                Default: {"hrm": 0.4, "lcm": 0.3, "moe": 0.3}
        """
        self.channel_weights = channel_weights or {
            "hrm": 0.4,  # α - High-Reasoning weight
            "lcm": 0.3,  # β - Linguistic Coherence weight  
            "moe": 0.3,  # γ - Mixture of Experts weight
        }
        
        # Validate weights sum to 1.0
        total = sum(self.channel_weights.values())
        if not math.isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(f"Channel weights must sum to 1.0, got {total}")
    
    def score_hrm_channel(self, candidate: Candidate, context: FusionContext) -> float:
        """
        Score HRM (High-Reasoning Module) channel
        
        Evaluates:
        - Abstract reasoning quality
        - Symbolic depth
        - Ontology alignment with UPPER mass
        """
        base_score = candidate.channel_scores.get("hrm", 0.0)

        # Boost for WHY intent - strong preference for abstract reasoning
        if context.intent == "WHY":
            base_score *= 2.0

        # Boost for UPPER tier
        if context.tier == "UPPER":
            base_score *= 1.2
        
        # Boost if ontology signature aligns with upper mass
        if candidate.ontology_signature:
            upper_mass = context.ontology_mass.get("upper_mass", 0.5)
            if upper_mass > 0.5:
                base_score *= (1 + 0.2 * (upper_mass - 0.5))

        # No cap here - let the score reflect full boost effect
        return base_score
    
    def score_lcm_channel(self, candidate: Candidate, context: FusionContext) -> float:
        """
        Score LCM (Linguistic Coherence Module) channel
        
        Evaluates:
        - Semantic clarity
        - Linguistic coherence
        - Communication effectiveness
        """
        base_score = candidate.channel_scores.get("lcm", 0.0)

        # Boost for WHAT intent - strong preference for semantic clarity
        if context.intent == "WHAT":
            base_score *= 2.0

        # Boost for HYBRID tier
        if context.tier == "HYBRID":
            base_score *= 1.15
        
        # Penalty for high entropy (unclear communication)
        if context.is_high_entropy():
            base_score *= 0.9

        # No cap here - let the score reflect full boost effect
        return base_score
    
    def score_moe_channel(self, candidate: Candidate, context: FusionContext) -> float:
        """
        Score MoE (Mixture of Experts) channel
        
        Evaluates:
        - Domain-specific accuracy
        - Factual precision
        - Expert knowledge
        """
        base_score = candidate.channel_scores.get("moe", 0.0)

        # Boost for HOW intent - strong preference for domain expertise
        if context.intent == "HOW":
            base_score *= 2.0

        # Boost for LOWER tier (concrete/factual)
        if context.tier == "LOWER":
            base_score *= 1.2
        
        # Boost for domain match
        if candidate.domain == context.domain:
            base_score *= 1.1
        
        # Boost if kosha signature aligns with lower mass
        if candidate.kosha_signature:
            lower_mass = context.ontology_mass.get("lower_mass", 0.5)
            if lower_mass > 0.5:
                base_score *= (1 + 0.2 * (lower_mass - 0.5))

        # No cap here - let the score reflect full boost effect
        return base_score
    
    def score_all_channels(
        self, 
        candidate: Candidate, 
        context: FusionContext
    ) -> Dict[str, float]:
        """Score all three channels"""
        return {
            "hrm": self.score_hrm_channel(candidate, context),
            "lcm": self.score_lcm_channel(candidate, context),
            "moe": self.score_moe_channel(candidate, context),
        }


class FusionScorer:
    """
    Calculates final fusion scores
    
    Combines channel scores with weights and applies modifiers
    """
    
    def __init__(self, channel_weights: Dict[str, float] = None):
        """Initialize fusion scorer"""
        self.channel_scorer = ChannelScorer(channel_weights)
        self.channel_weights = self.channel_scorer.channel_weights
    
    def calculate_base_fusion_score(
        self,
        candidate: Candidate,
        context: FusionContext
    ) -> float:
        """
        Calculate base fusion score
        
        Formula: score = α*HRM + β*LCM + γ*MoE
        """
        channel_scores = self.channel_scorer.score_all_channels(candidate, context)
        
        fusion_score = (
            self.channel_weights["hrm"] * channel_scores["hrm"] +
            self.channel_weights["lcm"] * channel_scores["lcm"] +
            self.channel_weights["moe"] * channel_scores["moe"]
        )
        
        return fusion_score
    
    def apply_modifiers(
        self,
        base_score: float,
        candidate: Candidate,
        context: FusionContext
    ) -> float:
        """
        Apply modifiers to base score

        Modifiers:
        - Relevance boost (minor)
        - Confidence adjustment (moderate)
        - SMI penalty (semantic mismatch)
        - Safety penalties for regulated mode
        """
        score = base_score

        # Relevance boost (minor impact)
        score *= (1 + 0.1 * candidate.relevance_score)

        # Confidence adjustment (moderate impact, less aggressive)
        # Use square root to reduce the penalty for small differences
        score *= (0.7 + 0.3 * candidate.confidence)

        # SMI penalty (high mismatch = lower score)
        if candidate.smi is not None:
            smi_penalty = 1.0 - (0.4 * min(candidate.smi, 1.0))
            score *= smi_penalty

        # Regulated mode: strict safety penalties
        if context.is_regulated():
            # Require high confidence
            if candidate.confidence < 0.8:
                score *= 0.7

            # Require low SMI
            if candidate.smi and candidate.smi > 0.5:
                score *= 0.5

        return min(score, 1.0)
    
    def score_candidate(
        self,
        candidate: Candidate,
        context: FusionContext
    ) -> float:
        """
        Calculate final fusion score for candidate
        
        Returns: float in [0, 1]
        """
        base_score = self.calculate_base_fusion_score(candidate, context)
        final_score = self.apply_modifiers(base_score, candidate, context)
        
        return round(final_score, 4)
    
    def score_all_candidates(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> Dict[str, float]:
        """
        Score all candidates
        
        Returns: Dict mapping candidate.id -> fusion_score
        """
        scores = {}
        for candidate in candidates:
            scores[candidate.id] = self.score_candidate(candidate, context)
        
        return scores
    
    def rank_candidates(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> List[Candidate]:
        """
        Rank candidates by fusion score (descending)
        
        Returns: Sorted list of candidates
        """
        scores = self.score_all_candidates(candidates, context)
        
        # Sort by score descending
        ranked = sorted(
            candidates,
            key=lambda c: scores[c.id],
            reverse=True
        )
        
        return ranked
