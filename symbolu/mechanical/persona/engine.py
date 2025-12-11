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
from .schema_adaptive_routing import SchemaAdaptiveRoutingSnapshot, compute_schema_adaptive_map


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
        if coherence_observation is not None:
            # Compute cross-layer resonance map
            cl_map = compute_cross_layer_persona_map(coherence_observation)
            # Apply tone-only modulation (observation only in v1.0)
            self._apply_cross_layer_resonance(persona_response, cl_map)
            # Attach cl_map to response for observability
            persona_response.cross_layer_resonance_map = cl_map

        # Phase 33 Step 9: Compute persona schema adaptive routing (observation-only)
        # Extract coherence observation from explain_log (same as Phase 30)
        if coherence_observation is not None:
            # Compute schema adaptive map (experimental, diagnostic-only)
            schema_map = self._compute_schema_adaptive_snapshot(
                coherence_observation,
                explain_log
            )
            # Attach schema_map to response for observability (NEVER affects routing)
            persona_response.schema_adaptive_map = schema_map

        # Phase 34 Step 10: Extract identity harmonics and apply tone adjustments
        # Extract identity harmonics snapshot from coherence state
        ihl_snapshot = self._extract_identity_harmonics(explain_log)
        if ihl_snapshot is not None:
            # Compute identity harmonics profile (tone-level adjustments only, ±0.02 max)
            identity_harmonics_profile = self._apply_identity_harmonics_to_tone(
                persona,
                ihl_snapshot
            )
            # Attach profile to response for observability (NEVER affects routing)
            persona_response.identity_harmonics_profile = identity_harmonics_profile

        # Phase 35 Step 11: Extract predictive persona drift and apply tone adjustments
        # Extract predictive drift snapshot from coherence state
        ppdm_snapshot = self._extract_predictive_drift_from_coherence(explain_log)
        if ppdm_snapshot is not None:
            # Compute predictive drift profile (tone-level adjustments only, ±0.02 max)
            predictive_drift_profile = self._apply_predictive_drift_to_tone(
                persona,
                ppdm_snapshot
            )
            # Attach profile to response for observability (NEVER affects routing)
            persona_response.predictive_drift_profile = predictive_drift_profile

        # Phase 36 Step 12: Extract identity resonance memory and apply tone adjustments
        # Extract IRM snapshot from coherence state
        irm_snapshot = self._extract_irm_from_coherence(explain_log)
        if irm_snapshot is not None:
            # Compute identity resonance memory profile (tone-level adjustments only, ±0.02 max)
            irm_profile = self._apply_identity_resonance_memory(
                persona,
                irm_snapshot
            )
            # Attach profile to response for observability (NEVER affects routing)
            persona_response.identity_resonance_memory_profile = irm_profile

        # Phase 37 Step 13: Extract adaptive continuity engine and apply tone adjustments
        # Extract ACE snapshot from coherence state
        ace_snapshot = self._extract_continuity_snapshot(explain_log)
        if ace_snapshot is not None:
            # Compute continuity profile (tone-level adjustments only, ±0.015 max)
            continuity_profile = self._apply_continuity_tone_modulation(
                persona,
                ace_snapshot
            )
            # Attach profile to response for observability (NEVER affects routing)
            persona_response.continuity_profile = continuity_profile

        # Phase 40 Step 14: Extract cross-horizon resonance and apply tone adjustments
        # Extract CHRA snapshot from coherence state
        chra_snapshot = self._extract_cross_horizon_resonance(explain_log)
        if chra_snapshot is not None:
            # Compute CHRA profile (tone-level adjustments only, ±0.015 max)
            chra_profile = self._apply_cross_horizon_resonance_to_tone(
                persona,
                chra_snapshot
            )
            # Attach profile to response for observability (NEVER affects routing)
            persona_response.cross_horizon_resonance_profile = chra_profile

        # Phase 42 Step 15: Extract scenario fusion metadata (metadata-only, no tone changes)
        # Extract scenario fusion snapshot from coherence state
        scenario_fusion_snapshot = self._extract_scenario_fusion(explain_log)
        if scenario_fusion_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            scenario_fusion_metadata = self._build_scenario_fusion_metadata(scenario_fusion_snapshot)
            persona_response.persona_scenario_fusion = scenario_fusion_metadata

        # Phase 44 Step 16: Extract coherence-scenario alignment metadata (metadata-only, no tone changes)
        # Extract coherence-scenario alignment snapshot from coherence state
        scenario_alignment_snapshot = self._extract_scenario_alignment(explain_log)
        if scenario_alignment_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            scenario_alignment_metadata = self._build_scenario_alignment_metadata(scenario_alignment_snapshot)
            persona_response.persona_scenario_alignment = scenario_alignment_metadata

        # Phase 45 Step 17: Extract MTSF metadata (metadata-only, no tone changes)
        # Extract MTSF snapshot from coherence state
        mtsf_snapshot = self._extract_mtsf(explain_log)
        if mtsf_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            mtsf_metadata = self._build_mtsf_metadata(mtsf_snapshot)
            persona_response.persona_mtsf = mtsf_metadata

        # Phase 46 Step 18: Extract TFCE metadata (metadata-only, no tone changes)
        # Extract TFCE snapshot from coherence state
        tfce_snapshot = self._extract_trajectory_convergence(explain_log)
        if tfce_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            tfce_metadata = self._build_trajectory_convergence_metadata(tfce_snapshot)
            persona_response.persona_trajectory_convergence = tfce_metadata

        # Phase 47 Step 19: Extract UTSSE metadata (metadata-only, no tone changes)
        # Extract UTSSE snapshot from coherence state
        utsse_snapshot = self._extract_unified_synthesis(explain_log)
        if utsse_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            utsse_metadata = self._build_unified_synthesis_metadata(utsse_snapshot)
            persona_response.persona_unified_synthesis_profile = utsse_metadata

        # Phase 48 Step 19.5: Extract MSR metadata (metadata-only, no tone changes)
        # Extract MSR snapshot from coherence state
        msr_snapshot = self._extract_macro_stability_snapshot(explain_log)
        if msr_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            msr_metadata = self._build_macro_stability_metadata(msr_snapshot)
            persona_response.persona_macro_stability_profile = msr_metadata

        # Phase 49 Step 19.6: Extract UCTSE metadata (metadata-only, no tone changes)
        # Extract UCTSE snapshot from coherence state
        uctse_snapshot = self._extract_temporal_stability_snapshot(explain_log)
        if uctse_snapshot is not None:
            # Attach metadata to response for observability (METADATA-ONLY, NO tone changes)
            uctse_metadata = self._build_temporal_stability_metadata(uctse_snapshot)
            persona_response.persona_temporal_stability_profile = uctse_metadata

        # Step 20: Return complete response
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

    def _compute_schema_adaptive_snapshot(
        self,
        coherence_observation: Any,
        explain_log: Dict[str, Any]
    ) -> Optional[SchemaAdaptiveRoutingSnapshot]:
        """
        Phase 33: Compute persona schema adaptive routing snapshot.

        This method computes experimental schema alignment signals that map
        the user's coherence patterns to different persona schemas.

        CRITICAL: This is OBSERVATION-ONLY. The computed schema alignment
        scores are NEVER used to change persona selection or routing.
        They are purely for research and diagnostic purposes.

        Args:
            coherence_observation: CoherenceObservation with all signals
            explain_log: MLCR explain log with metadata

        Returns:
            SchemaAdaptiveRoutingSnapshot or None if computation fails

        Invariants:
            • Zero-LLM: pure mathematical computation
            • Deterministic: same inputs → same outputs
            • Observation-only: NEVER affects routing
            • Graceful degradation: missing signals → None
        """
        # Graceful degradation: if coherence observation missing, return None
        if coherence_observation is None:
            return None

        try:
            # Extract previous schema snapshot from explain_log if available
            # (for drift computation across turns)
            previous_snapshot = None
            if explain_log:
                coherence_state = explain_log.get('coherence_state')
                if coherence_state is not None:
                    previous_snapshot = getattr(
                        coherence_state,
                        'previous_schema_adaptive_snapshot',
                        None
                    )

            # Compute schema adaptive map
            schema_map = compute_schema_adaptive_map(
                coherence_observation,
                previous_snapshot=previous_snapshot
            )

            return schema_map

        except Exception:
            # Graceful degradation: any error → return None
            # This ensures schema adaptive routing NEVER breaks the pipeline
            return None

    def _extract_identity_harmonics(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 34: Extract identity harmonics snapshot from coherence state.

        This method safely extracts the identity harmonics snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            IdentityHarmonicsSnapshot or None if not available

        Graceful Degradation:
            Returns None if identity harmonics not available in coherence state.
        """
        # Try to extract from coherence_state or coherence_observation
        if not explain_log:
            return None

        # Try coherence_state path
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            ihl_snapshot = getattr(coherence_state, 'identity_harmonics_snapshot', None)
            if ihl_snapshot is not None:
                return ihl_snapshot

        # Try coherence_observation path (if it has IHL data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            ihl_snapshot = getattr(coherence_observation, 'identity_harmonics_snapshot', None)
            if ihl_snapshot is not None:
                return ihl_snapshot

        return None

    def _apply_identity_harmonics_to_tone(
        self,
        persona: PersonaProfile,
        ihl_snapshot: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 34: Apply identity harmonics to persona tone.

        This method maps IHL outputs into micro-adjustments of persona tone
        parameters. It is tone-level only and never affects semantic content.

        Mapping Rules:
            • High CIH (≥0.75) → more confident tone (+0.02 confidence boost)
            • High AIH (≥0.70) → more flexible/adaptive tone (+0.02 flexibility)
            • High RIH (≥0.70) → more relational warmth (+0.02 warmth)

        Tone Adjustments (all ≤ ±0.02):
            • confidence_adjustment: [-0.02, +0.02]
            • flexibility_adjustment: [-0.02, +0.02]
            • warmth_adjustment: [-0.02, +0.02]

        Args:
            persona: Selected PersonaProfile
            ihl_snapshot: IdentityHarmonicsSnapshot (or None)

        Returns:
            Dict with identity harmonics profile or None if IHL not available

        Invariants:
            • All adjustments are ≤ ±0.02 (2% max deviation)
            • Deterministic: same inputs → same outputs
            • Safe default: if IHL missing → no modulation (returns None)
        """
        # Graceful degradation: if IHL not available, return None
        if ihl_snapshot is None:
            return None

        # Extract harmonics from snapshot
        cih = getattr(ihl_snapshot, 'core_identity_harmonic', None)
        aih = getattr(ihl_snapshot, 'adaptive_identity_harmonic', None)
        rih = getattr(ihl_snapshot, 'relational_identity_harmonic', None)
        ihi = getattr(ihl_snapshot, 'identity_harmonics_index', None)
        notes = getattr(ihl_snapshot, 'notes', [])

        # If any harmonic is missing, return None
        if cih is None or aih is None or rih is None:
            return None

        # ========================================================================
        # STEP 1: Compute confidence adjustment based on CIH
        # ========================================================================
        if cih >= 0.75:
            # High core identity → more confident tone
            confidence_adjustment = 0.02
        elif cih >= 0.50:
            # Medium core identity → neutral
            confidence_adjustment = 0.0
        else:
            # Low core identity → less confident tone
            confidence_adjustment = -0.02

        # ========================================================================
        # STEP 2: Compute flexibility adjustment based on AIH
        # ========================================================================
        if aih >= 0.70:
            # High adaptive identity → more flexible tone
            flexibility_adjustment = 0.02
        elif aih >= 0.40:
            # Medium adaptive identity → neutral
            flexibility_adjustment = 0.0
        else:
            # Low adaptive identity → more rigid tone
            flexibility_adjustment = -0.02

        # ========================================================================
        # STEP 3: Compute warmth adjustment based on RIH
        # ========================================================================
        if rih >= 0.70:
            # High relational identity → more warmth
            warmth_adjustment = 0.02
        elif rih >= 0.40:
            # Medium relational identity → neutral
            warmth_adjustment = 0.0
        else:
            # Low relational identity → less warmth
            warmth_adjustment = -0.02

        # ========================================================================
        # STEP 4: Build identity harmonics profile
        # ========================================================================
        identity_harmonics_profile = {
            "cih": round(cih, 4),
            "aih": round(aih, 4),
            "rih": round(rih, 4),
            "ihi": round(ihi, 4) if ihi is not None else None,
            "confidence_adjustment": round(confidence_adjustment, 4),
            "flexibility_adjustment": round(flexibility_adjustment, 4),
            "warmth_adjustment": round(warmth_adjustment, 4),
            "identity_harmonics_tags": notes,
        }

        return identity_harmonics_profile

    def _extract_predictive_drift_from_coherence(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 35: Extract predictive persona drift snapshot from coherence state.

        This method safely extracts the predictive drift snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            PredictivePersonaDriftSnapshot or None if not available

        Graceful Degradation:
            Returns None if predictive drift not available in coherence state.
        """
        # Try to extract from coherence_state or coherence_observation
        if not explain_log:
            return None

        # Try coherence_state path
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            ppdm_snapshot = getattr(coherence_state, 'predictive_drift_snapshot', None)
            if ppdm_snapshot is not None:
                return ppdm_snapshot

        # Try coherence_observation path (if it has PPDM data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            ppdm_snapshot = getattr(coherence_observation, 'predictive_drift_snapshot', None)
            if ppdm_snapshot is not None:
                return ppdm_snapshot

        return None

    def _apply_predictive_drift_to_tone(
        self,
        persona: PersonaProfile,
        ppdm_snapshot: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 35: Apply predictive persona drift to tone.

        This method maps PPDM outputs into micro-adjustments of persona tone
        parameters. It is tone-level only and never affects semantic content.

        Mapping Rules (based on predicted drift):
            • High drift magnitude (≥0.65) → stabilize tone (↑ structure, ↓ metaphor)
            • Low drift magnitude (<0.35) → no stabilization
            • Drift direction toward_structure → +structure
            • Drift direction toward_warmth → +warmth
            • Drift direction toward_grounding → +structure (grounding emphasis)

        Tone Adjustments (all ≤ ±0.02, max total ±0.02):
            • structure_adjustment: [-0.02, +0.02]
            • warmth_adjustment: [-0.02, +0.02]
            • clarity_adjustment: [-0.02, +0.02]

        Args:
            persona: Selected PersonaProfile
            ppdm_snapshot: PredictivePersonaDriftSnapshot (or None)

        Returns:
            Dict with predictive drift profile or None if PPDM not available

        Invariants:
            • All adjustments are ≤ ±0.02 (2% max deviation)
            • Total combined adjustment ≤ ±0.02
            • Deterministic: same inputs → same outputs
            • Safe default: if PPDM missing → no modulation (returns None)
        """
        # Graceful degradation: if PPDM not available, return None
        if ppdm_snapshot is None:
            return None

        # Extract metrics from snapshot
        drift_magnitude = getattr(ppdm_snapshot, 'drift_magnitude_prediction', None)
        drift_stability = getattr(ppdm_snapshot, 'drift_stability_score', None)
        drift_band = getattr(ppdm_snapshot, 'drift_likelihood_band', None)
        drift_directions = getattr(ppdm_snapshot, 'drift_direction_scores', None)
        notes = getattr(ppdm_snapshot, 'notes', [])

        # If core metrics missing, return None
        if drift_magnitude is None or drift_directions is None:
            return None

        # ========================================================================
        # STEP 1: Initialize adjustments
        # ========================================================================
        structure_adjustment = 0.0
        warmth_adjustment = 0.0
        clarity_adjustment = 0.0

        # ========================================================================
        # STEP 2: Apply drift magnitude stabilization
        # ========================================================================
        # High predicted drift → stabilize tone (more structure, less metaphor)
        if drift_magnitude >= 0.65:
            # High drift risk → increase structure for stability
            structure_adjustment += 0.01
        elif drift_magnitude <= 0.35:
            # Low drift risk → no stabilization needed
            pass  # No adjustment

        # ========================================================================
        # STEP 3: Apply directional drift adjustments
        # ========================================================================
        # Extract direction scores
        toward_structure = drift_directions.get('toward_structure', 0.5)
        toward_warmth = drift_directions.get('toward_warmth', 0.5)
        toward_grounding = drift_directions.get('toward_grounding', 0.5)

        # Find dominant direction (highest score ≥ 0.60)
        if toward_structure >= 0.60 and toward_structure >= toward_warmth and toward_structure >= toward_grounding:
            # Drift toward structure → increase clarity
            clarity_adjustment += 0.01
        elif toward_warmth >= 0.60 and toward_warmth >= toward_structure and toward_warmth >= toward_grounding:
            # Drift toward warmth → increase warmth
            warmth_adjustment += 0.01
        elif toward_grounding >= 0.60 and toward_grounding >= toward_structure and toward_grounding >= toward_warmth:
            # Drift toward grounding → increase structure (grounding emphasis)
            structure_adjustment += 0.01

        # ========================================================================
        # STEP 4: Apply stability dampening
        # ========================================================================
        # High stability → confidence in prediction → apply adjustments fully
        # Low stability → less confidence → dampen adjustments
        if drift_stability is not None:
            if drift_stability < 0.40:
                # Low stability → reduce adjustment magnitude by 50%
                structure_adjustment *= 0.5
                warmth_adjustment *= 0.5
                clarity_adjustment *= 0.5

        # ========================================================================
        # STEP 5: Enforce total adjustment bound (±0.02 max total)
        # ========================================================================
        total_adjustment = abs(structure_adjustment) + abs(warmth_adjustment) + abs(clarity_adjustment)
        if total_adjustment > 0.02:
            # Scale down proportionally to enforce ±0.02 max total
            scale_factor = 0.02 / total_adjustment
            structure_adjustment *= scale_factor
            warmth_adjustment *= scale_factor
            clarity_adjustment *= scale_factor

        # ========================================================================
        # STEP 6: Build predictive drift profile
        # ========================================================================
        predictive_drift_profile = {
            "drift_magnitude_prediction": round(drift_magnitude, 4),
            "drift_stability_score": round(drift_stability, 4) if drift_stability is not None else None,
            "drift_likelihood_band": drift_band,
            "drift_direction_scores": {
                "toward_structure": round(toward_structure, 4),
                "toward_warmth": round(toward_warmth, 4),
                "toward_grounding": round(toward_grounding, 4),
            },
            "structure_adjustment": round(structure_adjustment, 4),
            "warmth_adjustment": round(warmth_adjustment, 4),
            "clarity_adjustment": round(clarity_adjustment, 4),
            "predictive_drift_tags": notes,
        }

        return predictive_drift_profile

    def _extract_irm_from_coherence(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 36: Extract identity resonance memory snapshot from coherence state.

        This method safely extracts the IRM snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            IdentityResonanceMemorySnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if IRM computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            irm_snapshot = getattr(coherence_state, 'identity_resonance_memory_snapshot', None)
            if irm_snapshot is not None:
                return irm_snapshot

        # Try coherence_observation path (if it has IRM data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            irm_snapshot = getattr(coherence_observation, 'identity_resonance_memory_snapshot', None)
            if irm_snapshot is not None:
                return irm_snapshot

        return None

    def _apply_identity_resonance_memory(
        self,
        persona: PersonaProfile,
        irm_snapshot: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 36: Apply identity resonance memory to persona tone.

        This method maps IRM outputs into micro-adjustments of persona tone
        parameters. It is tone-level only and never affects semantic content.

        Mapping Rules:
            • High IMS (≥0.70) → increase warmth + continuity tone (≤ +0.015)
            • High IEP (≥0.70) → increase metaphor richness (≤ +0.01)
            • Low IDA (<0.35) → increase structure, reduce expressiveness (≤ +0.02)

        Tone Adjustments (all ≤ ±0.02):
            • warmth_adjustment: Applied to warmth parameter [-0.02, +0.02]
            • metaphor_adjustment: Applied to metaphor_level parameter [-0.02, +0.02]
            • structure_adjustment: Applied to structure_level parameter [-0.02, +0.02]

        Total adjustment limit: ±0.02 max (enforced by scaling)

        Args:
            persona: PersonaProfile being applied
            irm_snapshot: IdentityResonanceMemorySnapshot from Phase 36

        Returns:
            Identity resonance memory profile dict or None if snapshot invalid

        Invariants:
            • Tone-level only (NEVER affects routing, mappers, or semantics)
            • Bounded adjustments (≤ ±0.02 total)
            • Deterministic (same inputs → same outputs)
            • Non-invasive (observation-only)
        """
        if irm_snapshot is None:
            return None

        # ========================================================================
        # STEP 1: Extract IRM metrics
        # ========================================================================
        ims = getattr(irm_snapshot, 'identity_memory_strength', None)
        iep = getattr(irm_snapshot, 'identity_echo_persistence', None)
        ida = getattr(irm_snapshot, 'identity_drift_anchoring', None)
        memory_band = getattr(irm_snapshot, 'memory_band', None)
        tags = getattr(irm_snapshot, 'diagnostic_tags', [])

        # If any core metric is missing, return None
        if ims is None or iep is None or ida is None:
            return None

        # ========================================================================
        # STEP 2: Compute warmth adjustment based on IMS
        # ========================================================================
        # High IMS → increase warmth + continuity
        if ims >= 0.70:
            warmth_adjustment = +0.015  # Max +0.015
        elif ims >= 0.50:
            warmth_adjustment = +0.007  # Moderate warmth
        else:
            warmth_adjustment = 0.0  # No adjustment

        # ========================================================================
        # STEP 3: Compute metaphor adjustment based on IEP
        # ========================================================================
        # High IEP → increase metaphor richness
        if iep >= 0.70:
            metaphor_adjustment = +0.010  # Max +0.01
        elif iep >= 0.50:
            metaphor_adjustment = +0.005  # Moderate metaphor
        else:
            metaphor_adjustment = 0.0  # No adjustment

        # ========================================================================
        # STEP 4: Compute structure adjustment based on IDA
        # ========================================================================
        # Low IDA → increase structure, reduce expressiveness
        # High IDA → maintain or slightly reduce structure
        if ida <= 0.35:
            structure_adjustment = +0.020  # Max +0.02 (need more grounding)
        elif ida <= 0.50:
            structure_adjustment = +0.010  # Moderate structure
        elif ida >= 0.70:
            structure_adjustment = -0.005  # Slightly reduce structure (allow flow)
        else:
            structure_adjustment = 0.0  # No adjustment

        # ========================================================================
        # STEP 5: Enforce total adjustment limit (±0.02 max)
        # ========================================================================
        # Compute total absolute adjustment
        total_adjustment = abs(warmth_adjustment) + abs(metaphor_adjustment) + abs(structure_adjustment)

        # If total exceeds 0.02, scale down proportionally
        if total_adjustment > 0.02:
            scale_factor = 0.02 / total_adjustment
            warmth_adjustment *= scale_factor
            metaphor_adjustment *= scale_factor
            structure_adjustment *= scale_factor

        # ========================================================================
        # STEP 6: Build identity resonance memory profile
        # ========================================================================
        irm_profile = {
            "ims": round(ims, 4),
            "iep": round(iep, 4),
            "ida": round(ida, 4),
            "memory_band": memory_band,
            "warmth_adjustment": round(warmth_adjustment, 4),
            "metaphor_adjustment": round(metaphor_adjustment, 4),
            "structure_adjustment": round(structure_adjustment, 4),
            "irm_tags": tags,
        }

        return irm_profile

    def _extract_continuity_snapshot(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 37: Extract adaptive continuity engine snapshot from coherence state.

        This method safely extracts the ACE snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            AdaptiveContinuitySnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if ACE computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            ace_snapshot = getattr(coherence_state, 'adaptive_continuity_snapshot', None)
            if ace_snapshot is not None:
                return ace_snapshot

        # Try coherence_observation path (if it has ACE data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            ace_snapshot = getattr(coherence_observation, 'adaptive_continuity_snapshot', None)
            if ace_snapshot is not None:
                return ace_snapshot

        return None

    def _apply_continuity_tone_modulation(
        self,
        persona: PersonaProfile,
        ace_snapshot: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 37: Apply adaptive continuity engine to persona tone.

        This method maps ACE outputs into micro-adjustments of persona tone
        parameters. It is tone-level only and never affects semantic content.

        Mapping Rules:
            • High NCC (≥0.70) → increase narrative flow tone (≤ +0.010)
            • High ICC (≥0.70) → increase warmth + solidarity tone (≤ +0.010)
            • Low CSS (<0.40) → increase structure + grounding (≤ +0.015)

        Tone Adjustments (all ≤ ±0.015):
            • narrative_flow_adjustment: Applied to flow parameter [-0.015, +0.015]
            • warmth_adjustment: Applied to warmth parameter [-0.015, +0.015]
            • structure_adjustment: Applied to structure parameter [-0.015, +0.015]

        Total adjustment limit: ±0.015 max (enforced by scaling)

        Args:
            persona: PersonaProfile being applied
            ace_snapshot: AdaptiveContinuitySnapshot from Phase 37

        Returns:
            Continuity profile dict or None if snapshot invalid

        Invariants:
            • Tone-level only (NEVER affects routing, mappers, or semantics)
            • Bounded adjustments (≤ ±0.015 total)
            • Deterministic (same inputs → same outputs)
            • Non-invasive (observation-only)
        """
        if ace_snapshot is None:
            return None

        # ========================================================================
        # STEP 1: Extract ACE metrics
        # ========================================================================
        ncc = getattr(ace_snapshot, 'ncc', None)
        icc = getattr(ace_snapshot, 'icc', None)
        css = getattr(ace_snapshot, 'css', None)
        continuity_band = getattr(ace_snapshot, 'continuity_band', None)
        tags = getattr(ace_snapshot, 'continuity_tags', [])

        # If any core metric is missing, return None
        if ncc is None or icc is None or css is None:
            return None

        # ========================================================================
        # STEP 2: Compute narrative flow adjustment based on NCC
        # ========================================================================
        # High NCC → increase narrative flow tone (smoother transitions)
        if ncc >= 0.70:
            narrative_flow_adjustment = +0.010  # Max +0.010
        elif ncc >= 0.50:
            narrative_flow_adjustment = +0.005  # Moderate flow
        else:
            narrative_flow_adjustment = 0.0  # No adjustment

        # ========================================================================
        # STEP 3: Compute warmth adjustment based on ICC
        # ========================================================================
        # High ICC → increase warmth + solidarity (identity reinforcement)
        if icc >= 0.70:
            warmth_adjustment = +0.010  # Max +0.010
        elif icc >= 0.50:
            warmth_adjustment = +0.005  # Moderate warmth
        else:
            warmth_adjustment = 0.0  # No adjustment

        # ========================================================================
        # STEP 4: Compute structure adjustment based on CSS
        # ========================================================================
        # Low CSS → increase structure + grounding (stability needed)
        # High CSS → maintain or slightly reduce structure (allow flow)
        if css < 0.40:
            structure_adjustment = +0.015  # Max +0.015 (need stability)
        elif css < 0.55:
            structure_adjustment = +0.008  # Moderate structure
        elif css >= 0.70:
            structure_adjustment = -0.005  # Slightly reduce structure (stable)
        else:
            structure_adjustment = 0.0  # No adjustment

        # ========================================================================
        # STEP 5: Enforce total adjustment limit (±0.015 max)
        # ========================================================================
        # Compute total absolute adjustment
        total_adjustment = (
            abs(narrative_flow_adjustment) +
            abs(warmth_adjustment) +
            abs(structure_adjustment)
        )

        # If total exceeds 0.015, scale down proportionally
        if total_adjustment > 0.015:
            scale_factor = 0.015 / total_adjustment
            narrative_flow_adjustment *= scale_factor
            warmth_adjustment *= scale_factor
            structure_adjustment *= scale_factor

        # ========================================================================
        # STEP 6: Build adaptive continuity profile
        # ========================================================================
        continuity_profile = {
            "ncc": round(ncc, 4),
            "icc": round(icc, 4),
            "css": round(css, 4),
            "continuity_band": continuity_band,
            "narrative_flow_adjustment": round(narrative_flow_adjustment, 4),
            "warmth_adjustment": round(warmth_adjustment, 4),
            "structure_adjustment": round(structure_adjustment, 4),
            "continuity_tags": tags,
        }

        return continuity_profile

    def _extract_cross_horizon_resonance(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 40: Extract cross-horizon resonance alignment snapshot from coherence state.

        This method safely extracts the CHRA snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            CrossHorizonResonanceSnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if CHRA computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            chra_snapshot = getattr(coherence_state, 'cross_horizon_resonance_snapshot', None)
            if chra_snapshot is not None:
                return chra_snapshot

        # Try coherence_observation path (if it has CHRA data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            chra_snapshot = getattr(coherence_observation, 'cross_horizon_resonance_snapshot', None)
            if chra_snapshot is not None:
                return chra_snapshot

        return None

    def _extract_scenario_fusion(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 42: Extract scenario fusion snapshot from coherence state.

        This method safely extracts the scenario fusion snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            ScenarioFusionSnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if scenario fusion computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            scenario_fusion_snapshot = getattr(coherence_state, 'scenario_fusion_snapshot', None)
            if scenario_fusion_snapshot is not None:
                return scenario_fusion_snapshot

        # Try coherence_observation path (if it has scenario fusion data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            # Check if observation has scenario fusion fields
            if hasattr(coherence_observation, 'scenario_fusion_alignment'):
                # Build a minimal snapshot from observation fields
                scenario_fusion_alignment = getattr(coherence_observation, 'scenario_fusion_alignment', None)
                scenario_fusion_divergence = getattr(coherence_observation, 'scenario_fusion_divergence', None)
                scenario_fusion_uncertainty_band = getattr(coherence_observation, 'scenario_fusion_uncertainty_band', None)
                scenario_fusion_dominant_path = getattr(coherence_observation, 'scenario_fusion_dominant_path', None)
                scenario_fusion_tags = getattr(coherence_observation, 'scenario_fusion_tags', [])

                # If we have meaningful data, create a minimal dict
                if scenario_fusion_alignment is not None or scenario_fusion_divergence is not None:
                    return {
                        'scenario_alignment_score': scenario_fusion_alignment,
                        'scenario_divergence_index': scenario_fusion_divergence,
                        'future_uncertainty_band': scenario_fusion_uncertainty_band,
                        'dominant_future_path': scenario_fusion_dominant_path,
                        'diagnostic_tags': scenario_fusion_tags,
                    }

        return None

    def _extract_scenario_alignment(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 44: Extract coherence-scenario alignment snapshot from coherence state.

        This method safely extracts the coherence-scenario alignment snapshot from the
        coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            CoherenceScenarioAlignmentSnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if coherence-scenario alignment computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            scenario_alignment_snapshot = getattr(coherence_state, 'scenario_alignment_snapshot', None)
            if scenario_alignment_snapshot is not None:
                return scenario_alignment_snapshot

        # Try coherence_observation path (if it has CSAE data)
        coherence_observation = explain_log.get('coherence_observation')
        if coherence_observation is not None:
            # Check if observation has CSAE fields
            if hasattr(coherence_observation, 'csae_alignment_score'):
                # Build a minimal snapshot from observation fields
                csae_alignment_score = getattr(coherence_observation, 'csae_alignment_score', None)
                csae_conflict_index = getattr(coherence_observation, 'csae_conflict_index', None)
                csae_stability_agreement = getattr(coherence_observation, 'csae_stability_agreement', None)
                csae_alignment_band = getattr(coherence_observation, 'csae_alignment_band', None)
                csae_diagnostic_tags = getattr(coherence_observation, 'csae_diagnostic_tags', [])

                # If we have meaningful data, create a minimal dict
                if csae_alignment_score is not None or csae_conflict_index is not None:
                    return {
                        'alignment_score': csae_alignment_score,
                        'conflict_index': csae_conflict_index,
                        'stability_agreement': csae_stability_agreement,
                        'overall_alignment_band': csae_alignment_band,
                        'diagnostic_tags': csae_diagnostic_tags,
                    }

        return None

    def _build_scenario_alignment_metadata(
        self,
        scenario_alignment_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 44: Build coherence-scenario alignment metadata from snapshot.

        This method extracts metadata from the CSAE snapshot for observability.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            scenario_alignment_snapshot: CoherenceScenarioAlignmentSnapshot or dict

        Returns:
            dict: Metadata dictionary for observability

        Behavior:
            • Extracts alignment_score, conflict_index, stability_agreement
            • Extracts overall_alignment_band
            • Extracts diagnostic_tags
            • NEVER modifies tone or persona behavior
        """
        if scenario_alignment_snapshot is None:
            return {}

        # Handle both snapshot objects and dicts
        if isinstance(scenario_alignment_snapshot, dict):
            return {
                "alignment_score": scenario_alignment_snapshot.get('alignment_score'),
                "conflict_index": scenario_alignment_snapshot.get('conflict_index'),
                "stability_agreement": scenario_alignment_snapshot.get('stability_agreement'),
                "alignment_band": scenario_alignment_snapshot.get('overall_alignment_band'),
                "tags": scenario_alignment_snapshot.get('diagnostic_tags', []),
            }
        else:
            # Snapshot object
            return {
                "alignment_score": getattr(scenario_alignment_snapshot, 'alignment_score', None),
                "conflict_index": getattr(scenario_alignment_snapshot, 'conflict_index', None),
                "stability_agreement": getattr(scenario_alignment_snapshot, 'stability_agreement', None),
                "alignment_band": getattr(scenario_alignment_snapshot, 'overall_alignment_band', None),
                "tags": getattr(scenario_alignment_snapshot, 'diagnostic_tags', []),
            }

    def _extract_mtsf(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 45: Extract MTSF snapshot from coherence state.

        This method safely extracts the MTSF snapshot from the coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            MultiTrajectoryStabilityFieldSnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if MTSF computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            mtsf_snapshot = getattr(coherence_state, 'mtsf_snapshot', None)
            if mtsf_snapshot is not None:
                return mtsf_snapshot

        return None

    def _build_mtsf_metadata(
        self,
        mtsf_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 45: Build MTSF metadata from snapshot.

        This method extracts metadata from the MTSF snapshot for observability.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            mtsf_snapshot: MultiTrajectoryStabilityFieldSnapshot or dict

        Returns:
            dict: Metadata dictionary for observability

        Behavior:
            • Extracts tsi, tvi, chf, scc
            • Extracts band and tags
            • NEVER modifies tone or persona behavior
        """
        if mtsf_snapshot is None:
            return {}

        # Handle both snapshot objects and dicts
        if isinstance(mtsf_snapshot, dict):
            return {
                "tsi": mtsf_snapshot.get('tsi', 0.0),
                "tvi": mtsf_snapshot.get('tvi', 0.0),
                "chf": mtsf_snapshot.get('chf', 0.0),
                "scc": mtsf_snapshot.get('scc', 0.0),
                "band": mtsf_snapshot.get('band'),
                "tags": mtsf_snapshot.get('tags', []),
            }
        else:
            # Snapshot object
            return {
                "tsi": getattr(mtsf_snapshot, 'tsi', 0.0),
                "tvi": getattr(mtsf_snapshot, 'tvi', 0.0),
                "chf": getattr(mtsf_snapshot, 'chf', 0.0),
                "scc": getattr(mtsf_snapshot, 'scc', 0.0),
                "band": getattr(mtsf_snapshot, 'band', None),
                "tags": getattr(mtsf_snapshot, 'tags', []),
            }

    def _extract_trajectory_convergence(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 46: Extract TFCE snapshot from coherence state.

        This method safely extracts the TFCE snapshot from the coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            TrajectoryFieldConvergenceSnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if TFCE computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            tfce_snapshot = getattr(coherence_state, 'trajectory_convergence_snapshot', None)
            if tfce_snapshot is not None:
                return tfce_snapshot

        return None

    def _build_trajectory_convergence_metadata(
        self,
        tfce_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 46: Build TFCE metadata from snapshot.

        This method extracts metadata from the TFCE snapshot for observability.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            tfce_snapshot: TrajectoryFieldConvergenceSnapshot or dict

        Returns:
            dict: Metadata dictionary for observability

        Behavior:
            • Extracts convergence_index, divergence_index, stability_index
            • Extracts convergence_band and dominant_convergence_signal
            • Extracts diagnostic_tags
            • NEVER modifies tone or persona behavior
        """
        if tfce_snapshot is None:
            return {}

        # Handle both snapshot objects and dicts
        if isinstance(tfce_snapshot, dict):
            return {
                "convergence_index": tfce_snapshot.get('convergence_index', 0.0),
                "divergence_index": tfce_snapshot.get('divergence_index', 0.0),
                "stability_index": tfce_snapshot.get('stability_index', 0.0),
                "convergence_band": tfce_snapshot.get('convergence_band'),
                "dominant_convergence_signal": tfce_snapshot.get('dominant_convergence_signal'),
                "diagnostic_tags": tfce_snapshot.get('diagnostic_tags', []),
            }
        else:
            # Snapshot object
            return {
                "convergence_index": getattr(tfce_snapshot, 'convergence_index', 0.0),
                "divergence_index": getattr(tfce_snapshot, 'divergence_index', 0.0),
                "stability_index": getattr(tfce_snapshot, 'stability_index', 0.0),
                "convergence_band": getattr(tfce_snapshot, 'convergence_band', None),
                "dominant_convergence_signal": getattr(tfce_snapshot, 'dominant_convergence_signal', None),
                "diagnostic_tags": getattr(tfce_snapshot, 'diagnostic_tags', []),
            }

    def _extract_unified_synthesis(
        self,
        explain_log: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Phase 47: Extract UTSSE snapshot from coherence state.

        This method safely extracts the UTSSE snapshot from the coherence state if available.

        Args:
            explain_log: MLCR explain log with coherence state

        Returns:
            UnifiedTrajectoryScenarioSnapshot or None if not available

        Behavior:
            • Returns None if no coherence state present
            • Returns None if UTSSE computation was not run
            • Returns snapshot if successfully computed
        """
        # Try coherence_state path first (most common)
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is not None:
            utsse_snapshot = getattr(coherence_state, 'trajectory_scenario_synthesis_snapshot', None)
            if utsse_snapshot is not None:
                return utsse_snapshot

        return None

    def _build_unified_synthesis_metadata(
        self,
        utsse_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 47: Build UTSSE metadata from snapshot.

        This method extracts metadata from the UTSSE snapshot for observability.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            utsse_snapshot: UnifiedTrajectoryScenarioSnapshot or dict

        Returns:
            dict: Metadata dictionary for observability

        Behavior:
            • Extracts synthesis_integrity_score, future_state_alignment_score, etc.
            • Extracts synthesis_band and dominant_future_path
            • Extracts diagnostic_tags
            • NEVER modifies tone or persona behavior
        """
        if utsse_snapshot is None:
            return {}

        # Handle both snapshot objects and dicts
        if isinstance(utsse_snapshot, dict):
            return {
                "synthesis_integrity_score": utsse_snapshot.get('synthesis_integrity_score', 0.0),
                "future_state_alignment_score": utsse_snapshot.get('future_state_alignment_score', 0.0),
                "future_state_coherence_score": utsse_snapshot.get('future_state_coherence_score', 0.0),
                "cross_horizon_consistency_score": utsse_snapshot.get('cross_horizon_consistency_score', 0.0),
                "future_divergence_risk": utsse_snapshot.get('future_divergence_risk', 0.0),
                "convergence_signal_strength": utsse_snapshot.get('convergence_signal_strength', 0.0),
                "dominant_future_path": utsse_snapshot.get('dominant_future_path'),
                "synthesis_band": utsse_snapshot.get('synthesis_band'),
                "diagnostic_tags": utsse_snapshot.get('diagnostic_tags', []),
            }
        else:
            # Snapshot object
            return {
                "synthesis_integrity_score": getattr(utsse_snapshot, 'synthesis_integrity_score', 0.0),
                "future_state_alignment_score": getattr(utsse_snapshot, 'future_state_alignment_score', 0.0),
                "future_state_coherence_score": getattr(utsse_snapshot, 'future_state_coherence_score', 0.0),
                "cross_horizon_consistency_score": getattr(utsse_snapshot, 'cross_horizon_consistency_score', 0.0),
                "future_divergence_risk": getattr(utsse_snapshot, 'future_divergence_risk', 0.0),
                "convergence_signal_strength": getattr(utsse_snapshot, 'convergence_signal_strength', 0.0),
                "dominant_future_path": getattr(utsse_snapshot, 'dominant_future_path', None),
                "synthesis_band": getattr(utsse_snapshot, 'synthesis_band', None),
                "diagnostic_tags": getattr(utsse_snapshot, 'diagnostic_tags', []),
            }

    def _extract_macro_stability_snapshot(
        self,
        explain_log: Optional[Any]
    ) -> Optional[Any]:
        """
        Phase 48: Extract Macro-Stability Regulator snapshot from coherence state.

        This method extracts the MSR snapshot for metadata observation.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            explain_log: Explain log dict (may contain coherence_state)

        Returns:
            MacroStabilitySnapshot or None

        Behavior:
            • Extracts macro_stability_snapshot from coherence state
            • Returns None if not available
            • NEVER modifies tone or persona behavior
        """
        if explain_log is None:
            return None

        # Try to get coherence state
        coherence_state = explain_log.get('coherence_state')
        if coherence_state is None:
            return None

        # Extract MSR snapshot from coherence state
        if isinstance(coherence_state, dict):
            msr_snapshot = coherence_state.get('macro_stability_snapshot')
        else:
            msr_snapshot = getattr(coherence_state, 'macro_stability_snapshot', None)

        return msr_snapshot

    def _build_macro_stability_metadata(
        self,
        msr_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 48: Build MSR metadata from snapshot.

        This method extracts metadata from the MSR snapshot for observability.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            msr_snapshot: MacroStabilitySnapshot or dict

        Returns:
            dict: Metadata dictionary for observability

        Behavior:
            • Extracts macro_stability_index, macro_divergence_index, etc.
            • Extracts stability_band and diagnostic_tags
            • NEVER modifies tone or persona behavior
        """
        if msr_snapshot is None:
            return {}

        # Handle both snapshot objects and dicts
        if isinstance(msr_snapshot, dict):
            return {
                "macro_stability_index": msr_snapshot.get('macro_stability_index', 0.0),
                "macro_divergence_index": msr_snapshot.get('macro_divergence_index', 0.0),
                "macro_predictive_confidence": msr_snapshot.get('macro_predictive_confidence', 0.0),
                "macro_identity_resilience": msr_snapshot.get('macro_identity_resilience', 0.0),
                "stability_band": msr_snapshot.get('stability_band'),
                "diagnostic_tags": msr_snapshot.get('diagnostic_tags', []),
            }
        else:
            # Snapshot object
            return {
                "macro_stability_index": getattr(msr_snapshot, 'macro_stability_index', 0.0),
                "macro_divergence_index": getattr(msr_snapshot, 'macro_divergence_index', 0.0),
                "macro_predictive_confidence": getattr(msr_snapshot, 'macro_predictive_confidence', 0.0),
                "macro_identity_resilience": getattr(msr_snapshot, 'macro_identity_resilience', 0.0),
                "stability_band": getattr(msr_snapshot, 'stability_band', None),
                "diagnostic_tags": getattr(msr_snapshot, 'diagnostic_tags', []),
            }

    def _extract_temporal_stability_snapshot(
        self,
        explain_log: Optional[Any]
    ) -> Optional[Any]:
        """
        Phase 49: Extract Unified Cross-Phase Temporal Stability Engine (UCTSE) snapshot.

        This method extracts the UCTSE snapshot from coherence state for metadata extraction.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            explain_log: ExplanationLog (contains coherence_state)

        Returns:
            UnifiedTemporalStabilitySnapshot or None

        Behavior:
            • Extracts temporal_stability_snapshot from coherence state
            • NEVER modifies tone or persona behavior
        """
        if explain_log is None:
            return None

        coherence_state = getattr(explain_log, 'coherence_state', None)
        if coherence_state is None:
            return None

        # Extract UCTSE snapshot from coherence state
        if isinstance(coherence_state, dict):
            uctse_snapshot = coherence_state.get('temporal_stability_snapshot')
        else:
            uctse_snapshot = getattr(coherence_state, 'temporal_stability_snapshot', None)

        return uctse_snapshot

    def _build_temporal_stability_metadata(
        self,
        uctse_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 49: Build UCTSE metadata from snapshot.

        This method extracts metadata from the UCTSE snapshot for observability.
        This is METADATA-ONLY and does NOT affect tone or any other behavior.

        Args:
            uctse_snapshot: UnifiedTemporalStabilitySnapshot or dict

        Returns:
            dict: Metadata dictionary for observability

        Behavior:
            • Extracts temporal_stability_index, drift_risk, predictive_entropy, etc.
            • Extracts stability_band, dominant_regime, and diagnostic_tags
            • NEVER modifies tone or persona behavior
        """
        if uctse_snapshot is None:
            return {}

        # Handle both snapshot objects and dicts
        if isinstance(uctse_snapshot, dict):
            return {
                "temporal_stability_index": uctse_snapshot.get('temporal_stability_index', 0.0),
                "drift_risk": uctse_snapshot.get('drift_risk', 0.0),
                "predictive_entropy": uctse_snapshot.get('predictive_entropy', 0.0),
                "future_consistency": uctse_snapshot.get('future_consistency', 0.0),
                "dominant_regime": uctse_snapshot.get('dominant_regime'),
                "stability_band": uctse_snapshot.get('stability_band'),
                "diagnostic_tags": uctse_snapshot.get('diagnostic_tags', []),
            }
        else:
            # Snapshot object
            return {
                "temporal_stability_index": getattr(uctse_snapshot, 'temporal_stability_index', 0.0),
                "drift_risk": getattr(uctse_snapshot, 'drift_risk', 0.0),
                "predictive_entropy": getattr(uctse_snapshot, 'predictive_entropy', 0.0),
                "future_consistency": getattr(uctse_snapshot, 'future_consistency', 0.0),
                "dominant_regime": getattr(uctse_snapshot, 'dominant_regime', None),
                "stability_band": getattr(uctse_snapshot, 'stability_band', None),
                "diagnostic_tags": getattr(uctse_snapshot, 'diagnostic_tags', []),
            }

    def _build_scenario_fusion_metadata(
        self,
        scenario_fusion_snapshot: Any
    ) -> Dict[str, Any]:
        """
        Phase 42: Build scenario fusion metadata dict for persona response.

        This method builds a JSON-safe metadata dict from the scenario fusion snapshot.
        This is METADATA-ONLY and does NOT affect tone parameters.

        Args:
            scenario_fusion_snapshot: ScenarioFusionSnapshot or dict

        Returns:
            dict: JSON-safe metadata dict

        Behavior:
            • Extracts key metrics from snapshot
            • Returns JSON-serializable dict
            • Safe for null/missing fields
        """
        if scenario_fusion_snapshot is None:
            return {}

        # If it's a dict (from observation path), use directly
        if isinstance(scenario_fusion_snapshot, dict):
            return {
                "alignment": scenario_fusion_snapshot.get('scenario_alignment_score'),
                "divergence": scenario_fusion_snapshot.get('scenario_divergence_index'),
                "uncertainty_band": scenario_fusion_snapshot.get('future_uncertainty_band'),
                "dominant_future_path": scenario_fusion_snapshot.get('dominant_future_path'),
                "tags": scenario_fusion_snapshot.get('diagnostic_tags', []),
            }

        # Otherwise, it's a dataclass snapshot
        return {
            "alignment": getattr(scenario_fusion_snapshot, 'scenario_alignment_score', None),
            "divergence": getattr(scenario_fusion_snapshot, 'scenario_divergence_index', None),
            "consensus": getattr(scenario_fusion_snapshot, 'multi_regime_consensus', None),
            "uncertainty_band": getattr(scenario_fusion_snapshot, 'future_uncertainty_band', None),
            "dominant_future_path": getattr(scenario_fusion_snapshot, 'dominant_future_path', None),
            "tags": getattr(scenario_fusion_snapshot, 'diagnostic_tags', []),
        }

    def _apply_cross_horizon_resonance_to_tone(
        self,
        persona: PersonaProfile,
        chra_snapshot: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 40: Apply cross-horizon resonance alignment to persona tone.

        This method maps CHRA outputs into micro-adjustments of persona tone
        parameters. It is tone-level only and never affects semantic content.

        Mapping Rules:
            • HIGH_ALIGNMENT + low DFT → slight ↑ warmth and flow (≤ +0.010)
            • MIXED_ALIGNMENT → no change or very mild adjustments (≤ ±0.005)
            • LOW_ALIGNMENT or high DFT → slight ↑ structure and grounding, ↓ metaphor (≤ +0.010)

        Tone Adjustments (all ≤ ±0.015):
            • warmth_adjustment: Applied to warmth parameter [-0.015, +0.015]
            • flow_adjustment: Applied to flow parameter [-0.015, +0.015]
            • structure_adjustment: Applied to structure parameter [-0.015, +0.015]
            • metaphor_adjustment: Applied to metaphor parameter [-0.015, +0.015]

        Total adjustment limit: ±0.015 max (enforced by scaling)

        Args:
            persona: PersonaProfile being applied
            chra_snapshot: CrossHorizonResonanceSnapshot from Phase 40

        Returns:
            CHRA profile dict or None if snapshot invalid

        Invariants:
            • Tone-level only (NEVER affects routing, mappers, or semantics)
            • Bounded adjustments (≤ ±0.015 total)
            • Deterministic (same inputs → same outputs)
            • Non-invasive (observation-only)
        """
        if chra_snapshot is None:
            return None

        # ========================================================================
        # STEP 1: Extract CHRA metrics
        # ========================================================================
        rai = getattr(chra_snapshot, 'rai', None)
        dft = getattr(chra_snapshot, 'dft', None)
        ifa = getattr(chra_snapshot, 'ifa', None)
        alignment_band = getattr(chra_snapshot, 'alignment_band', None)
        tags = getattr(chra_snapshot, 'diagnostic_tags', [])

        # If any core metric is missing, return None
        if rai is None or dft is None or alignment_band is None:
            return None

        # ========================================================================
        # STEP 2: Compute warmth adjustment based on alignment + DFT
        # ========================================================================
        # HIGH_ALIGNMENT + low DFT → increase warmth (supportive tone)
        # LOW_ALIGNMENT or high DFT → no warmth increase
        warmth_adjustment = 0.0
        if alignment_band == "HIGH_ALIGNMENT" and dft <= 0.35:
            warmth_adjustment = +0.010  # Max +0.010 (aligned, low tension)
        elif alignment_band == "HIGH_ALIGNMENT" and dft <= 0.50:
            warmth_adjustment = +0.005  # Moderate warmth
        elif alignment_band == "MIXED_ALIGNMENT" and dft <= 0.40:
            warmth_adjustment = +0.003  # Slight warmth

        # ========================================================================
        # STEP 3: Compute flow adjustment based on RAI
        # ========================================================================
        # High RAI → increase flow (smooth narrative)
        # Low RAI → maintain or reduce flow
        flow_adjustment = 0.0
        if rai >= 0.70:
            flow_adjustment = +0.010  # Max +0.010 (strong alignment)
        elif rai >= 0.55:
            flow_adjustment = +0.005  # Moderate flow
        elif rai < 0.40:
            flow_adjustment = -0.005  # Reduce flow (misaligned)

        # ========================================================================
        # STEP 4: Compute structure adjustment based on DFT and alignment
        # ========================================================================
        # High DFT → increase structure + grounding (stabilize)
        # LOW_ALIGNMENT → increase structure
        structure_adjustment = 0.0
        if dft >= 0.65:
            structure_adjustment = +0.010  # Max +0.010 (high tension)
        elif dft >= 0.50:
            structure_adjustment = +0.005  # Moderate structure
        elif alignment_band == "LOW_ALIGNMENT":
            structure_adjustment = +0.008  # Need structure

        # ========================================================================
        # STEP 5: Compute metaphor adjustment based on alignment
        # ========================================================================
        # LOW_ALIGNMENT or high DFT → reduce metaphor (be more direct)
        # HIGH_ALIGNMENT → maintain or slightly increase metaphor
        metaphor_adjustment = 0.0
        if alignment_band == "LOW_ALIGNMENT" or dft >= 0.60:
            metaphor_adjustment = -0.008  # Reduce metaphor (be direct)
        elif alignment_band == "HIGH_ALIGNMENT" and dft <= 0.35:
            metaphor_adjustment = +0.005  # Slight increase (safe to be poetic)

        # ========================================================================
        # STEP 6: Enforce total adjustment limit (±0.015 max)
        # ========================================================================
        # Compute total absolute adjustment
        total_adjustment = (
            abs(warmth_adjustment) +
            abs(flow_adjustment) +
            abs(structure_adjustment) +
            abs(metaphor_adjustment)
        )

        # If total exceeds 0.015, scale down proportionally
        if total_adjustment > 0.015:
            scale_factor = 0.015 / total_adjustment
            warmth_adjustment *= scale_factor
            flow_adjustment *= scale_factor
            structure_adjustment *= scale_factor
            metaphor_adjustment *= scale_factor

        # ========================================================================
        # STEP 7: Build cross-horizon resonance profile
        # ========================================================================
        chra_profile = {
            "rai": round(rai, 4),
            "ifa": round(ifa, 4) if ifa is not None else None,
            "dft": round(dft, 4),
            "alignment_band": alignment_band,
            "warmth_adjustment": round(warmth_adjustment, 4),
            "flow_adjustment": round(flow_adjustment, 4),
            "structure_adjustment": round(structure_adjustment, 4),
            "metaphor_adjustment": round(metaphor_adjustment, 4),
            "chra_tags": tags,
        }

        return chra_profile

    def get_persona_summary(self) -> str:
        """
        Get a summary of all available personas.

        Returns:
            Formatted summary string
        """
        return self.registry.summary()
