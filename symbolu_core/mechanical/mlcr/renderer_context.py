"""
Renderer Context Builder
=========================

Builds context for downstream renderer based on domain, intent, and tier.

Renderer Modes:
- standard: Normal rendering
- regulated: Compliance-safe (medical/legal)
- symbolic: Abstract/philosophical language
- minimal: Concise, direct answers

Version: v3.1
Status: Production
"""

from typing import Dict, Optional, List
from .activation_plan import TierType, IntentType


# Regulated domains (require compliance-safe rendering)
REGULATED_DOMAINS = [
    "medical",
    "legal",
    "financial_advice",
    "healthcare",
    "legal_advice"
]

# Symbolic intents (require abstract/philosophical language)
SYMBOLIC_INTENTS = [
    IntentType.REFLECTION,
    IntentType.WHY,  # When in UPPER tier
    IntentType.META
]

# Minimal intents (require concise answers)
MINIMAL_INTENTS = [
    IntentType.WHAT,  # When in LOWER tier
    IntentType.COMMAND
]


class RendererContextBuilder:
    """
    Builds renderer context based on routing decisions.
    
    Determines:
    - Renderer mode (standard/regulated/symbolic/minimal)
    - Tone preferences
    - Formatting hints
    - Compliance flags
    """
    
    def __init__(self):
        self.regulated_domains = REGULATED_DOMAINS
        self.symbolic_intents = SYMBOLIC_INTENTS
        self.minimal_intents = MINIMAL_INTENTS
    
    def build_context(
        self,
        tier: TierType,
        intent: IntentType,
        domain: Optional[str] = None,
        user_state: Optional[str] = None,
        activation: Optional[Dict[str, bool]] = None
    ) -> Dict:
        """
        Build renderer context.
        
        Args:
            tier: Selected tier
            intent: Query intent
            domain: Optional domain
            user_state: Optional user state
            activation: Expert activation flags
            
        Returns:
            {
                "mode": str,
                "tone": str,
                "formatting": dict,
                "compliance": dict
            }
        """
        # Determine renderer mode
        mode = self._select_mode(tier, intent, domain)
        
        # Determine tone
        tone = self._select_tone(tier, intent, user_state)
        
        # Build formatting hints
        formatting = self._build_formatting_hints(mode, tier, intent)
        
        # Build compliance context
        compliance = self._build_compliance_context(domain, mode)
        
        return {
            "mode": mode,
            "tone": tone,
            "formatting": formatting,
            "compliance": compliance,
            "metadata": {
                "tier": tier.value,
                "intent": intent.value,
                "domain": domain,
                "user_state": user_state
            }
        }
    
    def _select_mode(
        self,
        tier: TierType,
        intent: IntentType,
        domain: Optional[str]
    ) -> str:
        """Select renderer mode."""
        # Regulated domains override everything
        if domain in self.regulated_domains:
            return "regulated"
        
        # Symbolic mode for reflection/abstract queries
        if intent in self.symbolic_intents:
            if tier == TierType.UPPER or tier == TierType.HYBRID:
                return "symbolic"
        
        # Minimal mode for simple factual queries
        if intent in self.minimal_intents and tier == TierType.LOWER:
            return "minimal"
        
        # Default to standard
        return "standard"
    
    def _select_tone(
        self,
        tier: TierType,
        intent: IntentType,
        user_state: Optional[str]
    ) -> str:
        """Select output tone."""
        # Empathetic tone for emotional queries
        if intent in [IntentType.REFLECTION, IntentType.FEELING]:
            return "empathetic"
        
        # Analytical tone for reasoning queries
        if intent == IntentType.WHY and tier in [TierType.UPPER, TierType.HYBRID]:
            return "analytical"
        
        # Direct tone for commands and factual queries
        if intent in [IntentType.COMMAND, IntentType.WHAT]:
            return "direct"
        
        # Balanced tone for planning
        if intent == IntentType.PLAN:
            return "balanced"
        
        # Careful tone for decision support
        if intent == IntentType.SHOULD:
            return "careful"
        
        # Default to conversational
        return "conversational"
    
    def _build_formatting_hints(
        self,
        mode: str,
        tier: TierType,
        intent: IntentType
    ) -> Dict:
        """Build formatting hints for renderer."""
        formatting = {
            "use_bullets": False,
            "use_headers": False,
            "max_length": None,
            "structure": "prose"
        }
        
        # Minimal mode: concise, no formatting
        if mode == "minimal":
            formatting["max_length"] = 200
            formatting["structure"] = "direct"
        
        # Regulated mode: structured, clear
        elif mode == "regulated":
            formatting["use_bullets"] = True
            formatting["use_headers"] = True
            formatting["structure"] = "structured"
        
        # Symbolic mode: flowing prose
        elif mode == "symbolic":
            formatting["structure"] = "flowing"
        
        # Standard mode: balanced
        else:
            if intent == IntentType.PLAN:
                formatting["use_bullets"] = True
                formatting["structure"] = "organized"
        
        return formatting
    
    def _build_compliance_context(
        self,
        domain: Optional[str],
        mode: str
    ) -> Dict:
        """Build compliance context."""
        compliance = {
            "is_regulated": mode == "regulated",
            "domain": domain,
            "disclaimers_required": False,
            "fact_checking_required": False
        }
        
        if mode == "regulated":
            compliance["disclaimers_required"] = True
            compliance["fact_checking_required"] = True
            
            if domain == "medical":
                compliance["disclaimer_text"] = (
                    "This information is for educational purposes only. "
                    "Consult a healthcare professional for medical advice."
                )
            elif domain == "legal":
                compliance["disclaimer_text"] = (
                    "This information is for general guidance only. "
                    "Consult a qualified attorney for legal advice."
                )
        
        return compliance
    
    def explain_context(self, context: Dict) -> List[str]:
        """Generate human-readable explanation of renderer context."""
        explanations = []
        
        explanations.append(f"Renderer Context:")
        explanations.append(f"  Mode: {context['mode']}")
        explanations.append(f"  Tone: {context['tone']}")
        explanations.append("")
        
        # Explain mode choice
        mode_explanations = {
            "standard": "Normal rendering with balanced formatting",
            "regulated": "Compliance-safe rendering with disclaimers",
            "symbolic": "Abstract/philosophical language for reflection",
            "minimal": "Concise, direct answers without elaboration"
        }
        explanations.append(
            f"Mode Description: {mode_explanations.get(context['mode'], 'Unknown')}"
        )
        
        # Show formatting hints
        fmt = context['formatting']
        explanations.append("")
        explanations.append("Formatting Hints:")
        explanations.append(f"  Structure: {fmt['structure']}")
        if fmt['max_length']:
            explanations.append(f"  Max Length: {fmt['max_length']} chars")
        if fmt['use_bullets']:
            explanations.append("  Use Bullets: Yes")
        if fmt['use_headers']:
            explanations.append("  Use Headers: Yes")
        
        # Show compliance info
        comp = context['compliance']
        if comp['is_regulated']:
            explanations.append("")
            explanations.append("Compliance:")
            explanations.append(f"  Regulated Domain: {comp['domain']}")
            if comp['disclaimers_required']:
                explanations.append("  Disclaimers Required: Yes")
            if comp['fact_checking_required']:
                explanations.append("  Fact Checking Required: Yes")
        
        return explanations
    
    def get_mode_description(self, mode: str) -> str:
        """Get description of renderer mode."""
        descriptions = {
            "standard": (
                "Standard mode: Normal rendering with balanced tone and formatting. "
                "Suitable for most queries."
            ),
            "regulated": (
                "Regulated mode: Compliance-safe rendering for medical/legal domains. "
                "Includes disclaimers and conservative language."
            ),
            "symbolic": (
                "Symbolic mode: Abstract, philosophical language for reflection and "
                "deep reasoning queries."
            ),
            "minimal": (
                "Minimal mode: Concise, direct answers without elaboration. "
                "For simple factual queries."
            )
        }
        return descriptions.get(mode, "Unknown mode")


# Singleton instance
_renderer_context_builder = None

def get_renderer_context_builder() -> RendererContextBuilder:
    """Get singleton renderer context builder."""
    global _renderer_context_builder
    if _renderer_context_builder is None:
        _renderer_context_builder = RendererContextBuilder()
    return _renderer_context_builder
