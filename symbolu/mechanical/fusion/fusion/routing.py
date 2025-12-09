"""
FusionEngine Routing Decider
Determines which renderer to use and with what parameters

Routing decisions:
1. Rules vs LLM renderer
2. Persona selection
3. DHA tone selection  
4. Safety mode switches
"""

from typing import Dict, Optional
from ..schemas.candidate import Candidate
from ..schemas.fusion_result import FusionContext


class RoutingDecider:
    """
    Decides rendering strategy based on fusion results
    
    Determines:
    - Render mode (rules, llm, hybrid)
    - Persona hint for voice
    - DHA tone for delivery
    """
    
    def __init__(self):
        """Initialize routing decider with thresholds"""
        # Confidence thresholds for rule-based rendering
        self.rules_confidence_threshold = 0.9
        self.rules_smi_threshold = 0.3
        
        # Entropy thresholds for delivery mode
        self.high_entropy_threshold = 0.6
        self.very_high_entropy_threshold = 0.8
    
    def decide_render_mode(
        self,
        candidate: Candidate,
        context: FusionContext,
        fusion_score: float
    ) -> str:
        """
        Decide rendering mode
        
        Options:
        - "rules": Deterministic rule-based renderer (fast, safe)
        - "llm": LLM-based renderer (flexible, expressive)
        - "hybrid": Combination approach
        
        Rules mode used when:
        - High confidence + low SMI (clear, unambiguous)
        - Regulated mode (safety critical)
        - Tight latency budget
        """
        # Force rules mode in regulated contexts
        if context.is_regulated():
            # Only use rules if candidate is high quality
            if candidate.confidence >= self.rules_confidence_threshold:
                return "rules"
            else:
                # Fall back to hybrid for safety
                return "hybrid"
        
        # Use rules mode for high-confidence, low-SMI cases
        if (
            candidate.confidence >= self.rules_confidence_threshold and
            (candidate.smi is None or candidate.smi <= self.rules_smi_threshold) and
            fusion_score >= 0.8
        ):
            return "rules"
        
        # Use rules mode under tight latency
        if context.has_tight_latency():
            return "rules"
        
        # Use LLM for complex/nuanced cases
        if context.is_high_entropy() or fusion_score < 0.6:
            return "llm"
        
        # Default to hybrid
        return "hybrid"
    
    def decide_persona(
        self,
        candidate: Candidate,
        context: FusionContext
    ) -> Optional[str]:
        """
        Select persona for rendering
        
        Personas:
        - "professional": Formal, domain-expert voice
        - "empathetic": Warm, understanding voice
        - "direct": Straightforward, clear voice
        - "exploratory": Questioning, philosophical voice
        """
        # Domain-based persona selection
        if context.domain in ["medical", "legal", "financial"]:
            return "professional"
        
        # Intent-based persona selection
        if context.intent == "WHY":
            return "exploratory"
        elif context.intent == "HOW":
            return "professional"
        elif context.intent == "WHAT":
            return "direct"
        
        # SMI-based persona selection
        if candidate.smi is not None:
            if candidate.smi > 0.6:
                # High mismatch: use empathetic voice
                return "empathetic"
            elif candidate.smi < 0.3:
                # Low mismatch: use direct voice
                return "direct"
        
        # Default to professional
        return "professional"
    
    def decide_dha_tone(
        self,
        candidate: Candidate,
        context: FusionContext
    ) -> Optional[str]:
        """
        Select DHA (Delivery Harmonization Algorithm) tone
        
        Tones:
        - "sweet_resonance": Direct truth when ready
        - "inverse_jolt": Challenging when stuck
        - "symbolic_metaphor": Indirect when defensive
        """
        # Get total entropy
        total_entropy = context.entropy.get("total_entropy", 0.0)
        
        # High entropy + high SMI = symbolic approach
        if total_entropy > self.very_high_entropy_threshold:
            if candidate.smi and candidate.smi > 0.6:
                return "symbolic_metaphor"
            else:
                return "inverse_jolt"
        
        # Medium entropy = direct but gentle
        if total_entropy > self.high_entropy_threshold:
            return "sweet_resonance"
        
        # Low entropy + low SMI = direct truth
        if total_entropy < self.high_entropy_threshold:
            if candidate.smi is None or candidate.smi < 0.4:
                return "sweet_resonance"
        
        # Default to sweet resonance
        return "sweet_resonance"
    
    def should_use_rules_renderer(
        self,
        render_mode: str,
        candidate: Candidate,
        context: FusionContext
    ) -> bool:
        """
        Determine if rules renderer should be used
        
        Returns: True if rules renderer is appropriate
        """
        if render_mode == "rules":
            return True
        
        if render_mode == "hybrid":
            # Use rules as primary in hybrid for high-confidence cases
            return candidate.confidence >= 0.8
        
        return False
    
    def should_use_llm_renderer(
        self,
        render_mode: str,
        candidate: Candidate,
        context: FusionContext
    ) -> bool:
        """
        Determine if LLM renderer should be used
        
        Returns: True if LLM renderer is appropriate
        """
        if render_mode == "llm":
            return True
        
        if render_mode == "hybrid":
            # Use LLM for polishing in hybrid mode
            return True
        
        # Even in rules mode, might need LLM for edge cases
        if render_mode == "rules":
            # Use LLM fallback if rules might be insufficient
            if context.is_high_entropy():
                return True
        
        return False
    
    def make_routing_decision(
        self,
        candidate: Candidate,
        context: FusionContext,
        fusion_score: float
    ) -> Dict[str, any]:
        """
        Make complete routing decision
        
        Returns: Dict with all routing parameters
        """
        render_mode = self.decide_render_mode(candidate, context, fusion_score)
        persona = self.decide_persona(candidate, context)
        dha_tone = self.decide_dha_tone(candidate, context)
        
        use_rules = self.should_use_rules_renderer(render_mode, candidate, context)
        use_llm = self.should_use_llm_renderer(render_mode, candidate, context)
        
        return {
            "render_mode": render_mode,
            "use_rules_renderer": use_rules,
            "use_llm_renderer": use_llm,
            "persona_hint": persona,
            "dha_tone_hint": dha_tone,
            "reasoning": {
                "mode_reason": self._explain_render_mode(render_mode, candidate, context),
                "persona_reason": self._explain_persona(persona, context),
                "tone_reason": self._explain_dha_tone(dha_tone, context),
            }
        }
    
    def _explain_render_mode(
        self,
        mode: str,
        candidate: Candidate,
        context: FusionContext
    ) -> str:
        """Explain why this render mode was chosen"""
        if mode == "rules":
            if context.is_regulated():
                return "Regulated mode requires deterministic rendering"
            elif context.has_tight_latency():
                return "Tight latency budget favors rule-based rendering"
            else:
                return "High confidence and low SMI enable deterministic rendering"
        
        elif mode == "llm":
            if context.is_high_entropy():
                return "High entropy requires flexible LLM rendering"
            else:
                return "Complex case requires LLM expressiveness"
        
        else:  # hybrid
            return "Balanced approach: rules for structure, LLM for polish"
    
    def _explain_persona(self, persona: Optional[str], context: FusionContext) -> str:
        """Explain persona selection"""
        if persona == "professional":
            return f"Domain '{context.domain}' requires professional tone"
        elif persona == "empathetic":
            return "High semantic mismatch requires empathetic approach"
        elif persona == "direct":
            return "Clear communication context favors direct voice"
        elif persona == "exploratory":
            return "WHY questions benefit from exploratory dialogue"
        else:
            return "Default professional voice"
    
    def _explain_dha_tone(self, tone: Optional[str], context: FusionContext) -> str:
        """Explain DHA tone selection"""
        total_entropy = context.entropy.get("total_entropy", 0.0)
        
        if tone == "sweet_resonance":
            return f"Low entropy ({total_entropy:.2f}) indicates readiness for direct truth"
        elif tone == "inverse_jolt":
            return f"High entropy ({total_entropy:.2f}) suggests need for challenge"
        elif tone == "symbolic_metaphor":
            return f"Very high entropy ({total_entropy:.2f}) requires indirect approach"
        else:
            return "Default delivery tone"
