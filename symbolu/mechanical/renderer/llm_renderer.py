"""
LLM-Enhanced Renderer
======================

Uses LLM for polishing while preserving core intelligence.
Implements "stylist not thinker" principle.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from symbolu.mechanical.renderer.prompts import PromptTemplates
from symbolu.mechanical.renderer.style_modifiers import StyleModifiers
from symbolu.mechanical.renderer.safety_guardrails import SafetyGuardrails

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import MapperProfile


class LLMRenderer:
    """
    LLM renderer that polishes output without modifying core intelligence.
    
    Key principle: LLM is a STYLIST, not a THINKER.
    Core analysis is preserved; only presentation is enhanced.
    """
    
    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.prompts = PromptTemplates()
        self.style = StyleModifiers()
        self.safety = SafetyGuardrails()
    
    def render(
        self,
        analysis: Dict[str, Any],
        tone: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Render analysis with LLM enhancement.
        
        Args:
            analysis: Core analysis result (PRESERVED)
            tone: DHA tone for delivery
            **kwargs: Additional parameters
            
        Returns:
            Polished output string
        """
        # Build prompt preserving core intelligence
        prompt = self.prompts.build_enhancement_prompt(analysis, tone)
        
        # Apply style modifiers
        prompt = self.style.apply(prompt, tone)
        
        # Safety check
        if not self.safety.check_prompt(prompt):
            raise ValueError("Prompt failed safety check")
        
        # LLM call would go here - placeholder
        # In production, this calls the actual LLM API
        enhanced = self._call_llm(prompt)
        
        # Verify output preserves core
        if not self.safety.verify_output(analysis, enhanced):
            raise ValueError("Output diverged from core analysis")
        
        return enhanced
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM API - placeholder."""
        # Placeholder - actual implementation would call LLM
        raise NotImplementedError("LLM integration pending.")

    def apply_mapper_tone(
        self,
        text: str,
        mapper_profile: Optional["MapperProfile"]
    ) -> str:
        """
        Apply mapper tone modulation to text.

        Modulates TONE and CADENCE only, not semantic content.
        LLM renderer must remain optional and non-semantic.

        Tones:
        ------
        LCM: Short, clipped, actionable
            - Sentence length: 8-12 words
            - Structure: Direct, imperative
            - Avoid: subordinate clauses, complex transitions

        HRM: Clearer transitions, deeper detail, parallel structures
            - Sentence length: 15-25 words
            - Structure: Compound-complex, contrastive
            - Use: transitional phrases, parallel constructions

        LAM: Reflective, slow cadence, stabilizing tone
            - Sentence length: 18-30 words
            - Structure: Flowing, contemplative
            - Use: cohesive devices, temporal markers
            - Avoid: therapy language (unless domain=therapy)

        Phase 9 Resonance Modulation:
            - Positive resonance bias → smoother transitions
            - Negative resonance bias → tighter, more compressed tone

        Args:
            text: Original text
            mapper_profile: Mapper profile from MLCR/TTOR

        Returns:
            Tone-modulated text
        """
        if mapper_profile is None:
            return text

        # Check if mapper-specific tone should be applied
        has_mapper_tone = False

        # LCM: Short, clipped, actionable
        if mapper_profile.practical_bias > 0.6 and mapper_profile.resolution_level == "low":
            text = self._apply_lcm_tone(text)
            has_mapper_tone = True

        # HRM: Clearer transitions, deeper detail
        elif mapper_profile.detail_bias > 0.6 and mapper_profile.resolution_level == "high":
            text = self._apply_hrm_tone(text)
            has_mapper_tone = True

        # LAM: Reflective, slow cadence
        elif mapper_profile.reflective_bias > 0.6 and mapper_profile.arc_mode != "none":
            text = self._apply_lam_tone(text, mapper_profile.arc_mode)
            has_mapper_tone = True

        # Phase 9: Apply resonance tone shaping only if no mapper-specific tone applied
        if not has_mapper_tone and hasattr(mapper_profile, 'guna_resonance_bias') and hasattr(mapper_profile, 'kosha_resonance_bias'):
            # Check for positive resonance (smoother)
            if mapper_profile.guna_resonance_bias > 0 or mapper_profile.kosha_resonance_bias > 0:
                text = self._apply_smooth_tone(text)
            # Check for negative resonance (tighter)
            elif mapper_profile.guna_resonance_bias < 0 or mapper_profile.kosha_resonance_bias < 0:
                text = self._apply_compressed_tone(text)

        return text

    def _apply_lcm_tone(self, text: str) -> str:
        """Apply LCM tone: short, clipped, actionable."""
        # Split into sentences and keep them short
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        # Shorten each sentence - keep only main clause
        shortened = []
        for sent in sentences:
            # Remove subordinate clauses (basic heuristic)
            if ',' in sent:
                parts = sent.split(',')
                # Keep first part (usually main clause)
                shortened.append(parts[0].strip())
            else:
                shortened.append(sent)

        # Join with periods, limit to 3 sentences max
        result = '. '.join(shortened[:3]) + '.'
        return result

    def _apply_hrm_tone(self, text: str) -> str:
        """Apply HRM tone: clearer transitions, deeper detail, parallel structures."""
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        # Add transitional phrases between sentences
        transitions = ["Furthermore", "Moreover", "In addition", "Specifically"]
        enhanced = []

        for i, sent in enumerate(sentences):
            if i > 0 and i < len(transitions):
                # Add transition to second+ sentences
                enhanced.append(f"{transitions[i-1].lower()}, {sent.lower()}")
            else:
                enhanced.append(sent)

        result = '. '.join(enhanced) + '.'
        return result

    def _apply_lam_tone(self, text: str, arc_mode: str) -> str:
        """Apply LAM tone: reflective, slow cadence, stabilizing."""
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        # Add cohesive devices and temporal markers
        arc_markers = {
            "temporal": ["Over time", "As patterns emerge", "Through this progression"],
            "identity": ["In this evolution", "Through self-development", "Within this growth"],
            "deep_context": ["In this broader context", "Through these patterns", "Within this framework"]
        }

        markers = arc_markers.get(arc_mode, ["In this context"])

        # Add marker to first sentence
        if sentences:
            first = sentences[0]
            sentences[0] = f"{markers[0]}, {first.lower()}"

        # Join with more flowing connectors
        result = '. '.join(sentences) + '.'
        return result

    def _apply_smooth_tone(self, text: str) -> str:
        """
        Apply Phase 9 smooth tone (positive resonance bias).

        Makes transitions smoother and more flowing.
        """
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        # Add smooth connectors between sentences
        if len(sentences) > 1:
            smooth_connectors = ["Additionally", "Furthermore", "Also"]
            enhanced = [sentences[0]]

            for i, sent in enumerate(sentences[1:], 1):
                if i <= len(smooth_connectors):
                    enhanced.append(f"{smooth_connectors[i-1].lower()}, {sent.lower()}")
                else:
                    enhanced.append(sent)

            return '. '.join(enhanced) + '.'

        return text

    def _apply_compressed_tone(self, text: str) -> str:
        """
        Apply Phase 9 compressed tone (negative resonance bias).

        Makes text tighter and more compressed.
        """
        sentences = [s.strip() for s in text.split('.') if s.strip()]

        # Remove connectors and make more direct
        compressed = []
        for sent in sentences:
            # Remove transition words at start (with or without comma)
            words = sent.split()
            if words:
                first_word = words[0].rstrip(',').lower()
                if first_word in ['additionally', 'furthermore', 'moreover', 'also', 'however']:
                    # Remove first word (and potential comma)
                    sent = ' '.join(words[1:])
                    # Remove leading comma if present
                    sent = sent.lstrip(', ')
                    # Capitalize first letter
                    if sent:
                        sent = sent[0].upper() + sent[1:] if len(sent) > 1 else sent.upper()
            compressed.append(sent)

        # Keep maximum 3 sentences for compression
        return '. '.join(compressed[:3]) + '.'
