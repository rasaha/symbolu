"""
FusionEngine Conflict Resolver
Deterministic rules for resolving conflicts between candidates

Hierarchy of resolution rules:
1. Safety constraints (regulated mode)
2. Intent alignment (WHY/HOW/WHAT)
3. Domain expertise
4. Consciousness alignment (SMI)
5. Confidence thresholds
"""

from typing import List, Optional, Tuple
from ..schemas.candidate import Candidate, CandidateSource
from ..schemas.fusion_result import FusionContext


class ConflictResolver:
    """
    Resolves conflicts between competing candidates
    
    Uses deterministic rules (no randomness, no LLM)
    """
    
    def __init__(self):
        """Initialize conflict resolver with default thresholds"""
        self.min_confidence = 0.5
        self.min_relevance = 0.3
        self.max_smi = 0.8  # Maximum acceptable semantic mismatch
        
        # Regulated mode has stricter thresholds
        self.regulated_min_confidence = 0.8
        self.regulated_max_smi = 0.5
    
    def apply_safety_filters(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> List[Candidate]:
        """
        Apply safety filters (first priority)
        
        Filters out candidates that violate safety constraints
        """
        filtered = []
        
        for candidate in candidates:
            # Check confidence threshold
            min_conf = (
                self.regulated_min_confidence if context.is_regulated()
                else self.min_confidence
            )
            
            if candidate.confidence < min_conf:
                continue
            
            # Check SMI (semantic mismatch)
            max_smi = (
                self.regulated_max_smi if context.is_regulated()
                else self.max_smi
            )
            
            if candidate.smi is not None and candidate.smi > max_smi:
                continue
            
            # Check relevance
            if candidate.relevance_score < self.min_relevance:
                continue
            
            # Passed all safety filters
            filtered.append(candidate)
        
        return filtered
    
    def resolve_by_intent(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> Optional[Candidate]:
        """
        Resolve by intent alignment (second priority)
        
        Selects candidate based on intent matching:
        - WHY → HRM channel preference
        - WHAT → LCM channel preference
        - HOW → MoE channel preference
        """
        if not candidates:
            return None
        
        intent = context.intent
        
        # Find best match for intent
        best_candidate = None
        best_score = -1.0
        
        for candidate in candidates:
            score = 0.0
            
            if intent == "WHY":
                score = candidate.channel_scores.get("hrm", 0.0)
            elif intent == "WHAT":
                score = candidate.channel_scores.get("lcm", 0.0)
            elif intent == "HOW":
                score = candidate.channel_scores.get("moe", 0.0)
            else:  # ACTION or unknown
                # Use average of all channels
                score = sum(candidate.channel_scores.values()) / len(candidate.channel_scores)
            
            if score > best_score:
                best_score = score
                best_candidate = candidate
        
        return best_candidate
    
    def resolve_by_domain(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> Optional[Candidate]:
        """
        Resolve by domain expertise (third priority)
        
        Prefers candidates from domain-matched sources
        """
        if not candidates:
            return None
        
        domain = context.domain
        
        # Filter by domain match
        domain_matched = [
            c for c in candidates 
            if c.domain == domain
        ]
        
        if domain_matched:
            # Return highest scoring domain-matched candidate
            return max(domain_matched, key=lambda c: c.relevance_score)
        
        # No domain match, return highest scoring overall
        return max(candidates, key=lambda c: c.relevance_score)
    
    def resolve_by_consciousness(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> Optional[Candidate]:
        """
        Resolve by consciousness alignment (fourth priority)
        
        Prefers candidates with:
        - Lower SMI (less semantic mismatch)
        - Better ontology/kosha alignment
        """
        if not candidates:
            return None
        
        # Score by consciousness alignment
        def consciousness_score(candidate: Candidate) -> float:
            score = 0.0
            
            # Lower SMI is better
            if candidate.smi is not None:
                score += (1.0 - candidate.smi) * 0.4
            
            # Ontology alignment
            if candidate.ontology_signature:
                upper_mass = context.ontology_mass.get("upper_mass", 0.5)
                lower_mass = context.ontology_mass.get("lower_mass", 0.5)
                
                # Simple alignment check (could be more sophisticated)
                if context.tier == "UPPER":
                    score += upper_mass * 0.3
                elif context.tier == "LOWER":
                    score += lower_mass * 0.3
                else:  # HYBRID
                    score += (upper_mass + lower_mass) / 2 * 0.3
            
            # Confidence boost
            score += candidate.confidence * 0.3
            
            return score
        
        return max(candidates, key=consciousness_score)
    
    def resolve_tie(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> Candidate:
        """
        Final tiebreaker (fifth priority)
        
        Uses simple heuristics when all else is equal
        """
        if len(candidates) == 1:
            return candidates[0]
        
        # Prefer by source priority: MoE > LCM > HRM > RAG > TEMPLATE
        source_priority = {
            CandidateSource.MOE: 5,
            CandidateSource.LCM: 4,
            CandidateSource.HRM: 3,
            CandidateSource.RAG: 2,
            CandidateSource.TEMPLATE: 1,
        }
        
        # Sort by source priority, then confidence
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                source_priority.get(c.source, 0),
                c.confidence,
                c.relevance_score
            ),
            reverse=True
        )
        
        return sorted_candidates[0]
    
    def resolve_conflict(
        self,
        candidates: List[Candidate],
        context: FusionContext
    ) -> Tuple[Optional[Candidate], str]:
        """
        Main conflict resolution method
        
        Applies resolution rules in priority order
        
        Returns:
            (selected_candidate, resolution_reason)
        """
        if not candidates:
            return None, "no_candidates"
        
        # Apply safety filters first
        safe_candidates = self.apply_safety_filters(candidates, context)
        
        if not safe_candidates:
            return None, "all_filtered_by_safety"
        
        if len(safe_candidates) == 1:
            return safe_candidates[0], "only_safe_candidate"
        
        # Try intent-based resolution
        intent_winner = self.resolve_by_intent(safe_candidates, context)
        
        # Check if intent resolution is clear winner (significantly better)
        if intent_winner:
            intent_score = intent_winner.channel_scores.get(
                {"WHY": "hrm", "WHAT": "lcm", "HOW": "moe"}.get(context.intent, "hrm"),
                0.0
            )
            
            if intent_score > 0.7:  # Strong intent match
                return intent_winner, "intent_match"
        
        # Try domain-based resolution
        domain_winner = self.resolve_by_domain(safe_candidates, context)
        
        if domain_winner and domain_winner.domain == context.domain:
            return domain_winner, "domain_expertise"
        
        # Try consciousness-based resolution
        consciousness_winner = self.resolve_by_consciousness(safe_candidates, context)
        
        if consciousness_winner:
            return consciousness_winner, "consciousness_alignment"
        
        # Final tiebreaker
        final_winner = self.resolve_tie(safe_candidates, context)
        return final_winner, "tiebreaker"
    
    def explain_resolution(
        self,
        candidates: List[Candidate],
        winner: Optional[Candidate],
        reason: str,
        context: FusionContext
    ) -> dict:
        """
        Generate explanation for conflict resolution
        
        Returns: Dict with resolution details
        """
        return {
            "total_candidates": len(candidates),
            "winner": winner.id if winner else None,
            "resolution_reason": reason,
            "filters_applied": {
                "safety": True,
                "confidence_threshold": (
                    self.regulated_min_confidence if context.is_regulated()
                    else self.min_confidence
                ),
                "smi_threshold": (
                    self.regulated_max_smi if context.is_regulated()
                    else self.max_smi
                ),
            },
            "resolution_hierarchy": [
                "safety_filters",
                "intent_alignment",
                "domain_expertise",
                "consciousness_alignment",
                "tiebreaker"
            ]
        }
