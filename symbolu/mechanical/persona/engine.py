"""
Persona Engine (v2.8.2)
========================

Main engine for applying persona styling to SOULPI responses.

Core Functionality:
    1. Select appropriate persona (via PersonaSelector)
    2. Determine layer ordering (based on tone and persona)
    3. Compose persona-styled text (intro + layers + outro)
    4. Preserve all analytical layers unchanged
    5. Track complete metadata for auditability

CRITICAL CONSTRAINT: PersonaEngine NEVER modifies layer contents.
It only controls ordering, framing, and presentation style.
"""

from typing import Dict, Any, Optional, List, Tuple
from .models import RendererOutputV3, DHAResult, PersonaResponse, PersonaMetadata, PersonaProfile
from .registry import PersonaRegistry
from .selector import PersonaSelector


class PersonaEngine:
    """
    Main Persona Engine for SOULPI v2.8.2.
    
    Pipeline Position:
        MLCR → Hybrid Fusion → FusionRenderer v3.0 → DHA v2.8.1 → 
        PersonaEngine v2.8.2 → LLM Enhancement (optional) → Output
    
    Responsibilities:
        - Persona selection (deterministic, no ML)
        - Layer ordering (based on tone + persona)
        - Text composition (intro + headers + content + outro)
        - Metadata preservation (complete audit trail)
    
    Non-Responsibilities:
        - Layer content modification (FORBIDDEN)
        - Meaning transformation (FORBIDDEN)
        - NLP/LLM operations (FORBIDDEN)
    """
    
    def __init__(
        self,
        registry: Optional[PersonaRegistry] = None,
        selector: Optional[PersonaSelector] = None
    ):
        """
        Initialize Persona Engine.
        
        Args:
            registry: PersonaRegistry instance (uses default if None)
            selector: PersonaSelector instance (creates new if None)
        """
        from .registry import get_default_registry
        
        self.registry = registry if registry is not None else get_default_registry()
        self.selector = selector if selector is not None else PersonaSelector()
    
    def apply(
        self,
        renderer_output: RendererOutputV3,
        dha_result: DHAResult,
        explain_log: Dict[str, Any],
        user_persona_override: Optional[str] = None
    ) -> PersonaResponse:
        """
        Apply persona styling to renderer output.
        
        This is the main entry point for the Persona Engine.
        
        Args:
            renderer_output: Output from FusionRenderer v3.0
            dha_result: Result from DHA Tone Engine v2.8.1
            explain_log: MLCR explain log with metadata
            user_persona_override: Optional user-requested persona
            
        Returns:
            PersonaResponse with styled text and preserved layers
        """
        # Step 1: Choose persona
        persona_id = self.selector.auto_select(explain_log, user_persona_override)
        persona = self.registry.get_safe(persona_id, default="neutral")
        
        # Step 2: Extract layers (no modification allowed)
        symbolic = renderer_output.symbolic_layer
        practical = renderer_output.practical_layer
        mirror = renderer_output.mirror_truth_layer
        
        # Step 3: Determine layer ordering
        ordered_layers = self._order_layers(
            persona=persona,
            tone=dha_result.tone,
            symbolic=symbolic,
            practical=practical,
            mirror=mirror
        )
        
        # Step 4: Compose textual response
        text = self._compose_text(
            persona=persona,
            tone=dha_result.tone,
            ordered_layers=ordered_layers
        )
        
        # Step 5: Build metadata
        metadata = PersonaMetadata(
            tier=renderer_output.metadata.get("tier", "UNKNOWN"),
            domain=renderer_output.metadata.get("domain", "unknown"),
            intent=renderer_output.metadata.get("intent", "unknown"),
            persona_id=persona.id,
            persona_name=persona.display_name,
            persona_description=persona.description,
            dha_tone=dha_result.tone,
            dha_confidence=dha_result.confidence,
            confidence=renderer_output.metadata.get("confidence")
        )
        
        # Step 6: Return complete response
        return PersonaResponse(
            persona_id=persona.id,
            text=text,
            layers={
                "symbolic_layer": symbolic,
                "practical_layer": practical,
                "mirror_truth_layer": mirror
            },
            metadata=metadata
        )
    
    def _order_layers(
        self,
        persona: PersonaProfile,
        tone: str,
        symbolic: Dict[str, Any],
        practical: Dict[str, Any],
        mirror: Dict[str, Any]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Determine the ordering of layers based on tone and persona.
        
        Priority Rules:
            1. Tone overrides (inverse_jolt → mirror first, symbolic → symbolic first)
            2. Persona preferences (sage → symbolic first, analyst → practical first)
            3. Default ordering (practical, symbolic, mirror)
        
        Args:
            persona: Selected PersonaProfile
            tone: DHA tone (resonance, inverse_jolt, symbolic)
            symbolic: Symbolic layer content
            practical: Practical layer content
            mirror: Mirror truth layer content
            
        Returns:
            List of (layer_name, layer_content) tuples in display order
        """
        # Tone overrides always take priority
        if tone == "inverse_jolt":
            # Mirror truth first for direct confrontation
            return [
                ("mirror", mirror),
                ("practical", practical),
                ("symbolic", symbolic)
            ]
        
        if tone == "symbolic":
            # Symbolic first for metaphorical delivery
            return [
                ("symbolic", symbolic),
                ("practical", practical),
                ("mirror", mirror)
            ]
        
        # Persona-specific ordering (when tone is "resonance")
        if persona.id == "sage":
            # Sage prefers symbolic → practical → mirror
            return [
                ("symbolic", symbolic),
                ("practical", practical),
                ("mirror", mirror)
            ]
        
        if persona.id == "analyst":
            # Analyst prefers practical → symbolic → mirror
            return [
                ("practical", practical),
                ("symbolic", symbolic),
                ("mirror", mirror)
            ]
        
        if persona.id == "coach":
            # Coach prefers mirror → practical → symbolic (action focus)
            return [
                ("mirror", mirror),
                ("practical", practical),
                ("symbolic", symbolic)
            ]
        
        if persona.id == "friendly":
            # Friendly prefers mirror → symbolic → practical (empathy first)
            return [
                ("mirror", mirror),
                ("symbolic", symbolic),
                ("practical", practical)
            ]
        
        # Default ordering for regulator, neutral, and unknown personas
        return [
            ("practical", practical),
            ("symbolic", symbolic),
            ("mirror", mirror)
        ]
    
    def _compose_text(
        self,
        persona: PersonaProfile,
        tone: str,
        ordered_layers: List[Tuple[str, Dict[str, Any]]]
    ) -> str:
        """
        Compose the final text response with persona styling.
        
        Composition Structure:
            1. Intro template (from persona)
            2. Layer sections with headers
            3. Outro template (from persona)
        
        Args:
            persona: Selected PersonaProfile
            tone: DHA tone
            ordered_layers: Ordered list of (layer_name, layer_content)
            
        Returns:
            Complete formatted response text
        """
        lines = []
        
        # Add intro template
        if persona.intro_template:
            lines.append(persona.intro_template)
        
        # Process each layer
        for layer_name, layer_content in ordered_layers:
            # Skip empty layers
            if not layer_content:
                continue
            
            # Determine header based on layer and tone
            header = self._get_layer_header(layer_name, tone)
            lines.append(header)
            
            # Add layer content (convert dict to readable string)
            content_str = self._format_layer_content(layer_content)
            lines.append(content_str)
            lines.append("")  # Blank line between sections
        
        # Add outro template
        if persona.outro_template:
            lines.append(persona.outro_template)
        
        return "\n".join(lines).strip()
    
    def _get_layer_header(self, layer_name: str, tone: str) -> str:
        """
        Get the appropriate header for a layer based on its type and tone.
        
        Args:
            layer_name: Name of the layer (symbolic, practical, mirror)
            tone: DHA tone
            
        Returns:
            Formatted header string
        """
        if layer_name == "symbolic":
            return "● Deeper symbolic insight:"
        
        elif layer_name == "practical":
            return "● Practical explanation:"
        
        elif layer_name == "mirror":
            # Mirror header varies by tone
            if tone == "resonance":
                return "● Reflection:"
            elif tone == "inverse_jolt":
                return "● Direct truth:"
            elif tone == "symbolic":
                return "● Symbolic mirror:"
            else:
                return "● Mirror truth:"
        
        else:
            return f"● {layer_name.title()}:"
    
    def _format_layer_content(self, content: Dict[str, Any]) -> str:
        """
        Format layer content dictionary into readable text.
        
        Args:
            content: Layer content dictionary
            
        Returns:
            Formatted string representation
        """
        if not content:
            return "(No content)"
        
        # Handle different content structures
        parts = []
        
        for key, value in content.items():
            if isinstance(value, (list, tuple)):
                # Format lists with bullets
                value_str = "\n  " + "\n  ".join(f"• {item}" for item in value)
                parts.append(f"{key.title()}: {value_str}")
            elif isinstance(value, dict):
                # Format nested dicts
                value_str = "\n  " + "\n  ".join(f"{k}: {v}" for k, v in value.items())
                parts.append(f"{key.title()}: {value_str}")
            else:
                # Simple key-value pairs
                parts.append(f"{key.title()}: {value}")
        
        return "\n".join(parts) if parts else str(content)
    
    def get_persona_summary(self) -> str:
        """
        Get a summary of all available personas.
        
        Returns:
            Formatted summary string
        """
        return self.registry.summary()
