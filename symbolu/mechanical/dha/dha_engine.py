"""
DHA Engine v3.0 - Delivery Harmonization & Adaptation Engine
=============================================================

Main orchestrator for determining HOW the system should deliver responses.

Pipeline Position:
    FusionEngine → PersonaEngine → FusionRenderer → DHAEngine → Output

The DHA Engine:
    1. Analyzes user readiness and resistance
    2. Selects appropriate delivery profile
    3. Modulates the message for optimal reception
    4. Applies safety filters
    5. Returns adapted message with diagnostics

Inputs:
    - fusion_output: From symbolu.mechanical.fusion.fusion_engine
    - persona_output: From symbolu.mechanical.persona.engine
    - renderer_output: From symbolu.mechanical.renderer.fusion_renderer
    - metadata: readiness_score, resistance_score, emotional_entropy, ego_state, folded_truths

Outputs:
    - delivery_profile: SWEET_RESONANCE | INVERSE_JOLT | SYMBOLIC_METAPHOR
    - adapted_message: Modified renderer output
    - diagnostics: Optional metadata about the process

Version: 3.0
Author: Symbol-U AGI
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import MapperProfile

from .adaptation_rules import DeliveryProfile, get_delivery_profile_metadata
from .readiness_analyzer import ReadinessAnalyzer
from .resistance_detector import ResistanceDetector
from .tone_selector import ToneSelector
from .delivery_modulator import DeliveryModulator
from .safety_filters import SafetyFilters


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class DHAInput:
    """
    Input structure for DHA Engine.

    Contains all data needed for delivery harmonization.
    """
    fusion_output: Optional[Dict[str, Any]] = None
    persona_output: Optional[Dict[str, Any]] = None
    renderer_output: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def text_to_adapt(self) -> str:
        """Extract text to adapt from renderer output."""
        if self.renderer_output:
            # Try common text fields
            if isinstance(self.renderer_output, dict):
                return (
                    self.renderer_output.get("text", "") or
                    self.renderer_output.get("rendered_text", "") or
                    self.renderer_output.get("output", "") or
                    str(self.renderer_output)
                )
            return str(self.renderer_output)
        return ""


@dataclass
class DHAOutput:
    """
    Output structure from DHA Engine.

    Contains the adapted message and all diagnostic information.
    """
    delivery_profile: str
    adapted_message: str
    original_message: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "delivery_profile": self.delivery_profile,
            "adapted_message": self.adapted_message,
            "original_message": self.original_message,
            "diagnostics": self.diagnostics,
            "timestamp": self.timestamp
        }


# ============================================================================
# DHA ENGINE CORE
# ============================================================================

class DHAEngine:
    """
    Delivery Harmonization & Adaptation Engine v3.0.

    Main orchestrator that determines how to deliver system responses
    for optimal user reception.

    Pipeline:
        1. ReadinessAnalyzer → Assess user's readiness to receive
        2. ResistanceDetector → Detect resistance patterns
        3. ToneSelector → Choose delivery profile
        4. DeliveryModulator → Transform message
        5. SafetyFilters → Ensure safe delivery

    Usage:
        engine = DHAEngine()
        result = engine.run(
            fusion_output={...},
            persona_output={...},
            renderer_output={...},
            metadata={
                "readiness_score": 0.7,
                "resistance_score": 0.3,
                "emotional_entropy": 0.4,
                "ego_state": "open",
                "folded_truths": []
            }
        )
    """

    def __init__(
        self,
        readiness_analyzer: Optional[ReadinessAnalyzer] = None,
        resistance_detector: Optional[ResistanceDetector] = None,
        tone_selector: Optional[ToneSelector] = None,
        delivery_modulator: Optional[DeliveryModulator] = None,
        safety_filters: Optional[SafetyFilters] = None,
        strict_safety: bool = False
    ):
        """
        Initialize DHA Engine.

        Args:
            readiness_analyzer: Custom ReadinessAnalyzer (uses default if None)
            resistance_detector: Custom ResistanceDetector (uses default if None)
            tone_selector: Custom ToneSelector (uses default if None)
            delivery_modulator: Custom DeliveryModulator (uses default if None)
            safety_filters: Custom SafetyFilters (uses default if None)
            strict_safety: Enable strict safety filtering
        """
        self.readiness_analyzer = readiness_analyzer or ReadinessAnalyzer()
        self.resistance_detector = resistance_detector or ResistanceDetector()
        self.tone_selector = tone_selector or ToneSelector(
            readiness_analyzer=self.readiness_analyzer,
            resistance_detector=self.resistance_detector
        )
        self.delivery_modulator = delivery_modulator or DeliveryModulator()
        self.safety_filters = safety_filters or SafetyFilters(strict_mode=strict_safety)

        # Statistics tracking
        self.stats = {
            "total_runs": 0,
            "profile_counts": {p.value: 0 for p in DeliveryProfile},
            "avg_process_time_ms": 0.0,
            "safety_blocks": 0
        }

    def run(
        self,
        fusion_output: Optional[Dict[str, Any]] = None,
        persona_output: Optional[Dict[str, Any]] = None,
        renderer_output: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DHAOutput:
        """
        Run the DHA Engine pipeline.

        This is the main entry point for the engine.

        Args:
            fusion_output: Output from FusionEngine
            persona_output: Output from PersonaEngine
            renderer_output: Output from FusionRenderer (contains text to adapt)
            metadata: Dictionary containing:
                - readiness_score (0-1): User's readiness to receive
                - resistance_score (0-1): User's resistance level
                - emotional_entropy (0-1): Emotional chaos indicator
                - ego_state: User's ego state (open, defensive, etc.)
                - folded_truths: Previously integrated truths

        Returns:
            DHAOutput with adapted message and diagnostics
        """
        start_time = datetime.now().timestamp()
        metadata = metadata or {}

        # Create input structure
        dha_input = DHAInput(
            fusion_output=fusion_output,
            persona_output=persona_output,
            renderer_output=renderer_output,
            metadata=metadata
        )

        # Extract text to adapt
        original_text = dha_input.text_to_adapt

        # Handle empty text
        if not original_text.strip():
            return DHAOutput(
                delivery_profile=DeliveryProfile.SWEET_RESONANCE.value,
                adapted_message="",
                original_message="",
                diagnostics={"error": "No text provided for adaptation"}
            )

        # Step 1 & 2: Analyze readiness and resistance (done by ToneSelector)
        # Step 3: Select delivery profile
        tone_result = self.tone_selector.select(metadata)
        delivery_profile = tone_result["delivery_profile"]

        # Step 4: Modulate delivery
        modulation_context = self._build_modulation_context(
            fusion_output, persona_output, metadata
        )
        modulation_result = self.delivery_modulator.modulate(
            original_text,
            delivery_profile,
            modulation_context
        )
        adapted_message = modulation_result["adapted_message"]

        # Step 5: Apply safety filters
        safety_result = self.safety_filters.filter(adapted_message)

        if safety_result["blocked"]:
            # Text failed validation - return safe fallback
            self.stats["safety_blocks"] += 1
            adapted_message = "[Content could not be delivered safely]"
        else:
            adapted_message = safety_result["filtered_text"]

        # Build diagnostics
        diagnostics = self._build_diagnostics(
            tone_result=tone_result,
            modulation_result=modulation_result,
            safety_result=safety_result,
            process_time_ms=(datetime.now().timestamp() - start_time) * 1000
        )

        # Update statistics
        self._update_stats(delivery_profile, diagnostics["process_time_ms"])

        return DHAOutput(
            delivery_profile=delivery_profile.value,
            adapted_message=adapted_message,
            original_message=original_text,
            diagnostics=diagnostics
        )

    def analyze_only(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user state without modulating any text.

        Useful for pre-flight checks or state inspection.

        Args:
            metadata: User state metadata

        Returns:
            Analysis result with readiness, resistance, and recommended profile
        """
        readiness = self.readiness_analyzer.analyze(metadata)
        resistance = self.resistance_detector.detect(metadata)
        tone = self.tone_selector.select(metadata)

        return {
            "readiness": readiness,
            "resistance": resistance,
            "recommended_profile": tone["profile_name"],
            "confidence": tone["confidence"],
            "reasoning": tone["reasoning"]
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset engine statistics."""
        self.stats = {
            "total_runs": 0,
            "profile_counts": {p.value: 0 for p in DeliveryProfile},
            "avg_process_time_ms": 0.0,
            "safety_blocks": 0
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _build_modulation_context(
        self,
        fusion_output: Optional[Dict[str, Any]],
        persona_output: Optional[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build context for delivery modulation.

        Args:
            fusion_output: FusionEngine output
            persona_output: PersonaEngine output
            metadata: User state metadata

        Returns:
            Context dictionary for modulator
        """
        context = {}

        # Extract hints from fusion output
        if fusion_output:
            context["domain"] = fusion_output.get("domain", "general")
            context["complexity"] = fusion_output.get("complexity", 0.5)

        # Extract hints from persona output
        if persona_output:
            context["persona"] = persona_output.get("persona_id", "neutral")
            context["tone"] = persona_output.get("tone", "neutral")

        # Add metadata hints
        context["readiness"] = metadata.get("readiness_score", 0.5)
        context["resistance"] = metadata.get("resistance_score", 0.3)

        # Deterministic frame selection based on metadata
        context["frame_hint"] = int(
            (metadata.get("readiness_score", 0.5) * 100) % 4
        )
        context["closing_hint"] = int(
            (metadata.get("resistance_score", 0.3) * 100) % 4
        )

        return context

    def _build_diagnostics(
        self,
        tone_result: Dict[str, Any],
        modulation_result: Dict[str, Any],
        safety_result: Dict[str, Any],
        process_time_ms: float
    ) -> Dict[str, Any]:
        """
        Build diagnostics dictionary.

        Args:
            tone_result: Result from tone selector
            modulation_result: Result from modulator
            safety_result: Result from safety filters
            process_time_ms: Processing time

        Returns:
            Comprehensive diagnostics dictionary
        """
        return {
            "process_time_ms": process_time_ms,
            "tone_selection": {
                "profile": tone_result["profile_name"],
                "confidence": tone_result["confidence"],
                "reasoning": tone_result["reasoning"]
            },
            "readiness_analysis": {
                "level": tone_result["readiness_analysis"]["readiness_level"],
                "adjusted_score": tone_result["readiness_analysis"]["adjusted_score"]
            },
            "resistance_analysis": {
                "level": tone_result["resistance_analysis"]["resistance_level"],
                "composite_score": tone_result["resistance_analysis"]["composite_score"],
                "patterns": tone_result["resistance_analysis"]["detected_patterns"]
            },
            "modulation": {
                "transformations": modulation_result["transformations"]
            },
            "safety": {
                "is_safe": safety_result["is_safe"],
                "modifications": safety_result["modifications"],
                "warnings": safety_result["warnings"]
            },
            "profile_metadata": tone_result["profile_metadata"]
        }

    def _update_stats(
        self,
        profile: DeliveryProfile,
        process_time_ms: float
    ) -> None:
        """Update engine statistics."""
        self.stats["total_runs"] += 1
        self.stats["profile_counts"][profile.value] += 1

        # Update average process time
        n = self.stats["total_runs"]
        old_avg = self.stats["avg_process_time_ms"]
        self.stats["avg_process_time_ms"] = (old_avg * (n - 1) + process_time_ms) / n

    def modulate_dha_depth(
        self,
        insight: Dict[str, Any],
        mapper_profile: Optional["MapperProfile"]
    ) -> Dict[str, Any]:
        """
        Modulate DHA depth based on mapper profile.

        Adjusts introspection level, metaphor usage, and framing
        based on mapper signals WITHOUT changing semantic truth.

        Rules:
        ------
        LCM Active (practical_bias high, resolution_level low):
            - Minimal introspection
            - No metaphor
            - Surface-truth only
            - No long-range implications

        HRM Active (detail_bias high, resolution_level high):
            - Deeper introspection
            - Contrastive phrasing allowed
            - Symbolic mirrors emphasized

        LAM Active (reflective_bias high, arc_mode set):
            - Long-arc identity reflection
            - "trajectory", "momentum", "directionality" allowed
            - Emphasize coherence across turns
            - If tension > 0.7 → add stabilization framing

        Args:
            insight: DHA insight dictionary (readiness, tone, etc.)
            mapper_profile: Mapper profile from MLCR/TTOR

        Returns:
            Modulated insight dictionary
        """
        if mapper_profile is None:
            return insight

        modulated = insight.copy()

        # LCM: Shallow insight
        if mapper_profile.practical_bias > 0.6 and mapper_profile.resolution_level == "low":
            modulated["introspection_level"] = "minimal"
            modulated["metaphor_allowed"] = False
            modulated["reflection_depth"] = "surface"
            modulated["long_range_implications"] = False
            modulated["framing_note"] = "Focused on immediate practical delivery"

        # HRM: Rich framing
        elif mapper_profile.detail_bias > 0.6 and mapper_profile.resolution_level == "high":
            modulated["introspection_level"] = "deep"
            modulated["metaphor_allowed"] = True
            modulated["reflection_depth"] = "detailed"
            modulated["contrastive_phrasing"] = True
            modulated["symbolic_mirrors"] = "emphasized"
            modulated["framing_note"] = "High-resolution analysis with nuanced framing"

        # LAM: Long-arc identity-level framing
        elif mapper_profile.reflective_bias > 0.6 and mapper_profile.arc_mode != "none":
            modulated["introspection_level"] = "arc-aware"
            modulated["metaphor_allowed"] = True
            modulated["reflection_depth"] = "identity"
            modulated["arc_keywords"] = ["trajectory", "momentum", "directionality", "coherence"]
            modulated["emphasize_coherence"] = True

            # Add arc-specific framing
            if mapper_profile.arc_mode == "temporal":
                modulated["arc_framing"] = "This shift seems part of a broader movement across sessions."
            elif mapper_profile.arc_mode == "identity":
                modulated["arc_framing"] = "This reflects ongoing identity development and self-concept evolution."
            elif mapper_profile.arc_mode == "deep_context":
                modulated["arc_framing"] = "This emerges from deep contextual patterns showing trajectory alignment."

            # Add stabilization framing if high tension
            if "long_arc_tension" in insight and insight.get("long_arc_tension", 0) > 0.7:
                modulated["stabilization_framing"] = "Pattern suggests need for integration and stabilization."

        return modulated


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def run_dha(
    renderer_output: Dict[str, Any],
    metadata: Dict[str, Any],
    fusion_output: Optional[Dict[str, Any]] = None,
    persona_output: Optional[Dict[str, Any]] = None
) -> DHAOutput:
    """
    Convenience function to run DHA Engine.

    Args:
        renderer_output: Output from FusionRenderer
        metadata: User state metadata
        fusion_output: Optional FusionEngine output
        persona_output: Optional PersonaEngine output

    Returns:
        DHAOutput with adapted message
    """
    engine = DHAEngine()
    return engine.run(
        fusion_output=fusion_output,
        persona_output=persona_output,
        renderer_output=renderer_output,
        metadata=metadata
    )


def adapt_message(
    text: str,
    readiness_score: float = 0.5,
    resistance_score: float = 0.3,
    emotional_entropy: float = 0.3
) -> str:
    """
    Quick message adaptation with minimal parameters.

    Args:
        text: Text to adapt
        readiness_score: User readiness (0-1)
        resistance_score: User resistance (0-1)
        emotional_entropy: Emotional chaos (0-1)

    Returns:
        Adapted message string
    """
    engine = DHAEngine()
    result = engine.run(
        renderer_output={"text": text},
        metadata={
            "readiness_score": readiness_score,
            "resistance_score": resistance_score,
            "emotional_entropy": emotional_entropy
        }
    )
    return result.adapted_message


if __name__ == "__main__":
    print("DHA Engine v3.0 - Delivery Harmonization & Adaptation")
    print("=" * 60)
    print("Determines HOW to deliver system responses")
    print("\nDelivery Profiles:")
    for profile in DeliveryProfile:
        meta = get_delivery_profile_metadata(profile)
        print(f"  - {profile.value}: {meta.get('description', 'N/A')}")
    print("\nUse examples.py for usage examples")
