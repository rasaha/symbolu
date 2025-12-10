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
from .models import RendererOutputV3, DHAResult, PersonaResponse, PersonaMetadata, PersonaProfile, PersonaResonanceProfile
from .registry import PersonaRegistry
from .selector import PersonaSelector
from .persona_resonance_mapping import CrossLayerResonanceMap, compute_cross_layer_persona_map
from .persona_echo_layer import AdaptivePersonaEchoProfile, compute_adaptive_persona_echo_profile


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
        # Safeguard: Handle None explain_log
        if explain_log is None:
            explain_log = {}

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

        # Phase 29 Step 6: Extract SHF and apply persona resonance
        shf_snapshot = self._extract_symbolic_harmony(explain_log)
        persona_resonance = self._apply_resonance_to_persona_tone(persona, shf_snapshot)

        # Step 7: Build PersonaResponse (with optional persona_resonance from Phase 29)
        persona_response = PersonaResponse(
            persona_id=persona.id,
            text=text,
            layers={
                "symbolic_layer": symbolic,
                "practical_layer": practical,
                "mirror_truth_layer": mirror
            },
            metadata=metadata,
            persona_resonance=persona_resonance  # Phase 29: Optional resonance profile
        )

        # Phase 30 Step 8: Apply cross-layer resonance modulation
        # Extract coherence observation from explain_log
        coherence_observation = self._extract_coherence_observation(explain_log)
        cl_map = None
        if coherence_observation is not None:
            # Compute cross-layer resonance map
            cl_map = compute_cross_layer_persona_map(coherence_observation)
            # Apply tone-only modulation (observation only in v1.0)
            self._apply_cross_layer_resonance(persona_response, cl_map)
            # Attach cl_map to response for observability
            persona_response.cross_layer_resonance_map = cl_map

        # Phase 31 Step 9: Apply adaptive persona echo layer
        # Extract inputs from explain_log
        session_summary = explain_log.get("session_summary")
        identity_signature = explain_log.get("identity_signature")
        intent_arc = explain_log.get("intent_arc")
        motivation_profile = explain_log.get("motivation_profile")
        interaction_mode = explain_log.get("interaction_mode", "SMART_INSIGHT")
        domain = metadata.domain

        # Compute adaptive persona echo profile
        echo_profile = compute_adaptive_persona_echo_profile(
            session_summary=session_summary,
            resonance_map=cl_map,
            identity_signature=identity_signature,
            intent_arc=intent_arc,
            motivation_profile=motivation_profile,
            interaction_mode=interaction_mode,
            domain=domain,
        )

        # Apply echo profile to response (metadata only)
        self._apply_adaptive_persona_echo(persona_response, echo_profile)

        # Step 10: Return complete response
        return persona_response
    
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
    
    def _extract_symbolic_harmony(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 29: Extract Symbolic Harmonization snapshot from pipeline context.

        Args:
            explain_log: MLCR explain log with metadata

        Returns:
            SymbolicHarmonizationSnapshot or None if not available

        Graceful Degradation:
            Returns None if SHF data is not present in context.
        """
        # Try to extract SHF snapshot from explain_log
        # Expected path: explain_log -> coherence_state -> symbolic_harmonization_snapshot
        if not explain_log:
            return None

        # Check if coherence_state exists
        coherence_state = explain_log.get('coherence_state')
        if not coherence_state:
            return None

        # Extract symbolic harmonization snapshot
        shf_snapshot = getattr(coherence_state, 'symbolic_harmonization_snapshot', None)

        return shf_snapshot

    def _extract_coherence_observation(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 30: Extract CoherenceObservation from pipeline context.

        Args:
            explain_log: MLCR explain log with metadata

        Returns:
            CoherenceObservation or None if not available

        Graceful Degradation:
            Returns None if coherence observation is not present in context.
        """
        # Try to extract coherence observation from explain_log
        # Expected path: explain_log -> coherence_observation
        if not explain_log:
            return None

        # Direct access to coherence_observation
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            return coherence_observation

        # Alternative path: explain_log -> coherence_state (might be the observation itself)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            # Check if coherence_state has coherence observation attributes
            if hasattr(coherence_state, 'coherence_score'):
                return coherence_state

        return None

    def _apply_resonance_to_persona_tone(
        self,
        persona: PersonaProfile,
        shf_snapshot: Optional[Any]
    ) -> Optional[PersonaResonanceProfile]:
        """
        Phase 29: Apply symbolic harmonization resonance to persona tone.

        This method maps SHF outputs into micro-adjustments of persona tone
        parameters. It is UI-layer only and never affects semantic content.

        Mapping Rules:
            • SHI >= 0.75 → +bias (+0.02 to +0.05)
            • SHI 0.50-0.75 → neutral bias (±0.01)
            • SHI < 0.50 → -bias (-0.05 to -0.02)

        Tone Adjustments:
            • +bias → slightly softer, more expressive (↑metaphor, ↑warmth, ↓structure)
            • -bias → slightly simpler, grounded (↓metaphor, ↓warmth, ↑structure)

        Args:
            persona: Selected PersonaProfile
            shf_snapshot: SymbolicHarmonizationSnapshot (or None)

        Returns:
            PersonaResonanceProfile or None if SHF not available

        Invariants:
            • All adjustments are ≤ ±0.05 (5% max deviation)
            • Deterministic: same inputs → same outputs
            • Safe default: if SHF missing → no modulation (returns None)
        """
        # Graceful degradation: if SHF not available, return None
        if shf_snapshot is None:
            return None

        # Extract SHI and notes from snapshot
        shi = getattr(shf_snapshot, 'symbolic_harmonization_index', None)
        notes = getattr(shf_snapshot, 'notes', [])

        # If SHI is missing, return None
        if shi is None:
            return None

        # ========================================================================
        # STEP 1: Compute symbolic_harmony_bias based on SHI thresholds
        # ========================================================================
        if shi >= 0.75:
            # High harmonization → +bias (softer, more expressive)
            symbolic_harmony_bias = 0.03
        elif shi >= 0.50:
            # Medium harmonization → neutral bias
            symbolic_harmony_bias = 0.0
        else:
            # Low harmonization → -bias (simpler, grounded)
            symbolic_harmony_bias = -0.03

        # ========================================================================
        # STEP 2: Compute granular tone adjustments
        # ========================================================================
        # Positive bias → increase metaphor/warmth, decrease structure
        # Negative bias → decrease metaphor/warmth, increase structure

        metaphor_adjustment = symbolic_harmony_bias * 0.67  # Max ±0.02
        warmth_adjustment = symbolic_harmony_bias * 0.33  # Max ±0.01
        structure_adjustment = -symbolic_harmony_bias * 0.33  # Max ±0.01 (inverted)

        # Clamp all adjustments to [-0.05, +0.05]
        metaphor_adjustment = max(-0.05, min(0.05, metaphor_adjustment))
        warmth_adjustment = max(-0.05, min(0.05, warmth_adjustment))
        structure_adjustment = max(-0.05, min(0.05, structure_adjustment))

        # ========================================================================
        # STEP 3: Build persona_resonance_tone dict
        # ========================================================================
        persona_resonance_tone = {
            "metaphor_adjustment": round(metaphor_adjustment, 4),
            "warmth_adjustment": round(warmth_adjustment, 4),
            "structure_adjustment": round(structure_adjustment, 4),
        }

        # ========================================================================
        # STEP 4: Extract symbolic_resonance_tags from SHF notes
        # ========================================================================
        # Filter notes to only include SHF-specific tags
        symbolic_resonance_tags = []
        if notes:
            # Only include notes related to symbolic harmonization
            # (e.g., "high_symbolic_harmonization", "symbolic_mirror_resonant", etc.)
            for note in notes:
                if any(kw in note for kw in [
                    'symbolic', 'harmonization', 'mirror', 'guna', 'kosha',
                    'semantic_integrity', 'focused', 'diffuse', 'converging', 'diverging'
                ]):
                    symbolic_resonance_tags.append(note)

        # ========================================================================
        # STEP 5: Return PersonaResonanceProfile
        # ========================================================================
        return PersonaResonanceProfile(
            symbolic_harmony_bias=round(symbolic_harmony_bias, 4),
            symbolic_resonance_tags=symbolic_resonance_tags,
            persona_resonance_tone=persona_resonance_tone,
        )

    def _apply_cross_layer_resonance(
        self,
        persona_response: PersonaResponse,
        cl_map: CrossLayerResonanceMap
    ) -> None:
        """
        Phase 30: Apply cross-layer resonance modulation to persona tone.

        This method performs tone-only modulation based on cross-layer
        resonance signals. It does NOT change semantics.

        Deterministic Adjustments:
            • metaphor_weight: Affects metaphor expansion/richness
            • warmth_weight: Affects softening tone/empathy
            • structure_weight: Controls clarity/organization
            • grounding_bias: Increases concreteness/practicality
            • expressiveness_bias: Adds expressive nuance

        Args:
            persona_response: PersonaResponse to modulate (in-place)
            cl_map: CrossLayerResonanceMap with tone parameters

        Returns:
            None (modulates persona_response in-place)

        Invariants:
            • All modulations are tone-only (no semantic changes)
            • Deterministic: same inputs → same outputs
            • Safe: no exceptions for missing signals
            • Zero-LLM: pure rule-based transforms

        NOTE: In Phase 30 v1.0, this method stores the cl_map for observability
        but does NOT yet apply live tone transformations to the text.
        Future versions may implement live text modulation based on weights.
        """
        # Phase 30 v1.0: Store cl_map for observability
        # Future: Apply tone transformations based on weights
        # (e.g., adjust metaphor richness, warmth phrasing, structure clarity)

        # For now, we simply attach the resonance map to the response
        # This allows downstream consumers (e.g., UI, analytics) to observe
        # the computed tone parameters without modifying the text.

        # No-op for now: future versions will implement live tone modulation
        pass

    def _apply_adaptive_persona_echo(
        self,
        response: PersonaResponse,
        echo_profile: AdaptivePersonaEchoProfile,
    ) -> None:
        """
        Phase 31: Apply adaptive persona echo metadata to PersonaResponse.

        This method applies echo metadata & echo segment placeholders to PersonaResponse.

        IMPORTANT:
        - Does NOT alter the core semantic explanation.
        - Echo is represented as a separate, optional field.
        - Tone-only and structure-only guidance (no LLM, no generation here).

        Args:
            response: PersonaResponse to modulate (in-place)
            echo_profile: AdaptivePersonaEchoProfile with echo parameters

        Returns:
            None (modulates response in-place)

        Invariants:
            • No semantic changes (core text unchanged)
            • No LLM calls (pure metadata attachment)
            • Deterministic: same inputs → same outputs
            • Safe: no exceptions for disabled echo
        """
        # If echo is disabled, do nothing
        if not echo_profile.echo_enabled:
            return

        # Attach echo_profile to response for observability
        response.echo_profile = echo_profile

    def get_persona_summary(self) -> str:
        """
        Get a summary of all available personas.

        Returns:
            Formatted summary string
        """
        return self.registry.summary()
