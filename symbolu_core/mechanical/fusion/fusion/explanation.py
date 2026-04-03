"""
FusionEngine Explanation Generator
Generates human-readable explanations for fusion decisions

Provides:
- Score breakdowns
- Ranking explanations
- Conflict resolution details
- Routing rationale
"""

from typing import Dict, List, Any
from ..schemas.candidate import Candidate
from ..schemas.fusion_result import FusionContext


class ExplanationGenerator:
    """
    Generates explanations for fusion decisions
    
    Outputs are designed for:
    - Debugging/development
    - Audit trails (compliance)
    - User transparency (when requested)
    """
    
    def __init__(self):
        """Initialize explanation generator"""
        pass
    
    def explain_candidate_scores(
        self,
        candidates: List[Candidate],
        scores: Dict[str, float],
        context: FusionContext
    ) -> Dict[str, Any]:
        """
        Explain individual candidate scores
        
        Returns: Dict with score breakdowns for each candidate
        """
        explanations = {}
        
        for candidate in candidates:
            fusion_score = scores.get(candidate.id, 0.0)
            
            explanations[candidate.id] = {
                "fusion_score": round(fusion_score, 4),
                "channel_scores": {
                    k: round(v, 4) 
                    for k, v in candidate.channel_scores.items()
                },
                "relevance": round(candidate.relevance_score, 4),
                "confidence": round(candidate.confidence, 4),
                "smi": round(candidate.smi, 4) if candidate.smi else None,
                "source": candidate.source.value,
                "domain": candidate.domain,
                "modifiers": self._explain_modifiers(candidate, context)
            }
        
        return explanations
    
    def _explain_modifiers(
        self,
        candidate: Candidate,
        context: FusionContext
    ) -> Dict[str, str]:
        """Explain score modifiers applied"""
        modifiers = {}
        
        # Relevance boost
        if candidate.relevance_score > 0.5:
            modifiers["relevance_boost"] = f"+{int(candidate.relevance_score * 20)}% from high relevance"
        
        # Confidence adjustment
        if candidate.confidence < 1.0:
            modifiers["confidence_adjustment"] = f"{int((candidate.confidence - 1.0) * 100)}% from confidence {candidate.confidence:.2f}"
        
        # SMI penalty
        if candidate.smi and candidate.smi > 0.3:
            penalty_pct = int(0.3 * min(candidate.smi, 1.0) * 100)
            modifiers["smi_penalty"] = f"-{penalty_pct}% from semantic mismatch {candidate.smi:.2f}"
        
        # Regulated mode
        if context.is_regulated():
            modifiers["regulated_mode"] = "Strict safety thresholds applied"
        
        return modifiers
    
    def explain_ranking(
        self,
        ranked_candidates: List[Candidate],
        scores: Dict[str, float],
        context: FusionContext
    ) -> Dict[str, Any]:
        """
        Explain candidate ranking
        
        Returns: Dict with ranking details
        """
        ranking_info = {
            "total_candidates": len(ranked_candidates),
            "top_3": [],
            "score_distribution": self._compute_score_distribution(ranked_candidates, scores),
        }
        
        # Top 3 details
        for i, candidate in enumerate(ranked_candidates[:3], 1):
            score = scores[candidate.id]
            ranking_info["top_3"].append({
                "rank": i,
                "id": candidate.id,
                "score": round(score, 4),
                "source": candidate.source.value,
                "domain": candidate.domain,
                "why_ranked_here": self._explain_rank_position(
                    candidate, score, ranked_candidates, scores, i
                )
            })
        
        return ranking_info
    
    def _compute_score_distribution(
        self,
        candidates: List[Candidate],
        scores: Dict[str, float]
    ) -> Dict[str, float]:
        """Compute statistics about score distribution"""
        if not candidates:
            return {}
        
        score_values = [scores[c.id] for c in candidates]
        
        return {
            "highest": round(max(score_values), 4),
            "lowest": round(min(score_values), 4),
            "average": round(sum(score_values) / len(score_values), 4),
            "spread": round(max(score_values) - min(score_values), 4),
        }
    
    def _explain_rank_position(
        self,
        candidate: Candidate,
        score: float,
        all_candidates: List[Candidate],
        scores: Dict[str, float],
        rank: int
    ) -> str:
        """Explain why candidate is at this rank"""
        if rank == 1:
            # Winner explanation
            reasons = []
            
            if score > 0.8:
                reasons.append("high fusion score")
            
            if candidate.confidence > 0.8:
                reasons.append("high confidence")
            
            if candidate.relevance_score > 0.7:
                reasons.append("strong relevance")
            
            if candidate.smi and candidate.smi < 0.3:
                reasons.append("low semantic mismatch")
            
            return f"Top ranked due to: {', '.join(reasons) if reasons else 'overall best scores'}"
        
        else:
            # Runner-up explanation
            top_score = scores[all_candidates[0].id]
            gap = top_score - score
            
            if gap < 0.1:
                return f"Very close to winner (gap: {gap:.3f})"
            elif gap < 0.2:
                return f"Close runner-up (gap: {gap:.3f})"
            else:
                return f"Ranked #{rank} with score {score:.3f}"
    
    def explain_selection(
        self,
        selected: Candidate,
        fusion_score: float,
        all_candidates: List[Candidate],
        resolution_reason: str,
        context: FusionContext
    ) -> Dict[str, Any]:
        """
        Explain why this candidate was selected
        
        Returns: Dict with selection rationale
        """
        return {
            "selected_id": selected.id,
            "fusion_score": round(fusion_score, 4),
            "selection_reason": resolution_reason,
            "key_factors": self._identify_key_factors(selected, fusion_score, context),
            "alternatives_considered": len(all_candidates) - 1,
            "confidence_in_selection": self._compute_selection_confidence(
                selected, fusion_score, all_candidates
            )
        }
    
    def _identify_key_factors(
        self,
        candidate: Candidate,
        fusion_score: float,
        context: FusionContext
    ) -> List[str]:
        """Identify key factors in selection"""
        factors = []
        
        # Score-based factors
        if fusion_score > 0.8:
            factors.append("Very high fusion score")
        
        # Channel-based factors
        dominant_channel = max(
            candidate.channel_scores.items(),
            key=lambda x: x[1]
        )
        if dominant_channel[1] > 0.7:
            factors.append(f"Strong {dominant_channel[0].upper()} channel score")
        
        # Intent alignment
        intent_channel_map = {
            "WHY": "hrm",
            "WHAT": "lcm",
            "HOW": "moe"
        }
        expected_channel = intent_channel_map.get(context.intent)
        if expected_channel and candidate.channel_scores.get(expected_channel, 0) > 0.6:
            factors.append(f"Intent alignment ({context.intent})")
        
        # Domain match
        if candidate.domain == context.domain:
            factors.append(f"Domain expertise match ({context.domain})")
        
        # Low SMI
        if candidate.smi and candidate.smi < 0.3:
            factors.append("Low semantic mismatch")
        
        # High confidence
        if candidate.confidence > 0.8:
            factors.append("High confidence")
        
        return factors if factors else ["Balanced overall performance"]
    
    def _compute_selection_confidence(
        self,
        selected: Candidate,
        selected_score: float,
        all_candidates: List[Candidate]
    ) -> str:
        """Compute confidence level in selection"""
        if len(all_candidates) == 1:
            return "certain (only candidate)"
        
        # Find second-best score
        other_scores = [
            c.channel_scores.get("hrm", 0) + 
            c.channel_scores.get("lcm", 0) + 
            c.channel_scores.get("moe", 0)
            for c in all_candidates if c.id != selected.id
        ]
        
        if not other_scores:
            return "certain"
        
        second_best = max(other_scores) if other_scores else 0
        gap = selected_score - second_best
        
        if gap > 0.3:
            return "very high"
        elif gap > 0.2:
            return "high"
        elif gap > 0.1:
            return "moderate"
        else:
            return "low (close competition)"
    
    def generate_debug_report(
        self,
        selected: Candidate,
        fusion_score: float,
        all_candidates: List[Candidate],
        scores: Dict[str, float],
        routing: Dict[str, Any],
        context: FusionContext
    ) -> str:
        """
        Generate comprehensive debug report
        
        Returns: Multi-line string for logging/debugging
        """
        lines = []
        lines.append("=" * 70)
        lines.append("FUSION ENGINE DEBUG REPORT")
        lines.append("=" * 70)
        
        # Context
        lines.append("\n[CONTEXT]")
        lines.append(f"  Tier: {context.tier}")
        lines.append(f"  Intent: {context.intent}")
        lines.append(f"  Domain: {context.domain}")
        lines.append(f"  Entropy: {context.entropy.get('total_entropy', 0):.3f}")
        lines.append(f"  Regulated: {context.is_regulated()}")
        
        # Selection
        lines.append("\n[SELECTION]")
        lines.append(f"  Selected: {selected.id}")
        lines.append(f"  Score: {fusion_score:.4f}")
        lines.append(f"  Source: {selected.source.value}")
        lines.append(f"  Confidence: {selected.confidence:.3f}")
        
        # Routing
        lines.append("\n[ROUTING]")
        lines.append(f"  Render Mode: {routing['render_mode']}")
        lines.append(f"  Use Rules: {routing['use_rules_renderer']}")
        lines.append(f"  Use LLM: {routing['use_llm_renderer']}")
        lines.append(f"  Persona: {routing['persona_hint']}")
        lines.append(f"  DHA Tone: {routing['dha_tone_hint']}")
        
        # Ranking
        lines.append("\n[TOP 5 CANDIDATES]")
        for i, cand in enumerate(all_candidates[:5], 1):
            score = scores[cand.id]
            lines.append(
                f"  {i}. {cand.id} ({score:.4f}) - "
                f"Source: {cand.source.value}, "
                f"Domain: {cand.domain or 'N/A'}"
            )
        
        # Score distribution
        if all_candidates:
            score_values = [scores[c.id] for c in all_candidates]
            lines.append("\n[SCORE DISTRIBUTION]")
            lines.append(f"  Highest: {max(score_values):.4f}")
            lines.append(f"  Lowest: {min(score_values):.4f}")
            lines.append(f"  Average: {sum(score_values)/len(score_values):.4f}")
            lines.append(f"  Spread: {max(score_values) - min(score_values):.4f}")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def generate_complete_explanation(
        self,
        selected: Candidate,
        fusion_score: float,
        ranked_candidates: List[Candidate],
        scores: Dict[str, float],
        resolution_reason: str,
        routing: Dict[str, Any],
        context: FusionContext
    ) -> Dict[str, Any]:
        """
        Generate complete explanation package
        
        Returns: Dict with all explanation data
        """
        return {
            "scores": self.explain_candidate_scores(ranked_candidates, scores, context),
            "ranking": self.explain_ranking(ranked_candidates, scores, context),
            "selection": self.explain_selection(
                selected, fusion_score, ranked_candidates, resolution_reason, context
            ),
            "routing": routing.get("reasoning", {}),
            "context": {
                "tier": context.tier,
                "intent": context.intent,
                "domain": context.domain,
                "entropy": context.entropy,
                "regulated": context.is_regulated(),
            }
        }
