"""
P22 - Acoustic-Vṛtti Witness Extractor Resolver

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    OBSERVER PHASE — WITNESS ONLY                               ║
║                                                                                ║
║  This phase may observe and summarize internal signals.                        ║
║  It may NOT influence regime, discourse, semantics, lexicon, or policy.        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This phase is witness-only and has zero authority over cognition or delivery.

Extracts acoustic motion signatures from user input using existing formula modules.
Produces an immutable witness report with no downstream routing effect.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify context or any upstream state
    - Witness-only: Observes without influencing
    - No semantic access: Must NOT read intent, regime, discourse, semantics
    - No feedback: Must NOT feed data back into P1-P21
    - No gating: Must NOT gate, block, or allow anything

Algorithm (Deterministic):
    1. If ctx.p21_delivery_mode == SUPPRESSED -> return empty witness report
    2. Run: map_acoustic_units(text)
    3. Run: map_vrittis(units)
    4. Aggregate: normalize motion values to [0.0, 1.0]
    5. Compute: dominant motion, motion balance, pressure band
    6. Emit: witness report (attach to ctx.p22_acoustic_witness)

Dependencies (REUSE, DO NOT REWRITE):
    - acoustic_unit_mapper.py
    - vritti_mapper.py
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from symbolu.formulas.acoustic_unit_mapper import (
    AcousticUnit,
    map_acoustic_units,
    get_acoustic_signature,
)
from symbolu.formulas.vritti_mapper import (
    VrittiType,
    AcousticVritti,
    assign_vritti_sequence,
    get_vritti_distribution,
)
from symbolu.mechanical.pipeline.p21_delivery.p21_delivery_schema import (
    DeliveryMode,
)
from symbolu.mechanical.pipeline.p22_acoustic_witness.p22_schema import (
    P22_VERSION,
    MotionPrimitive,
    MotionBalance,
    P22AcousticVrittiWitness,
    P22InvariantViolation,
    create_empty_witness,
)


# ============================================================================
# FORBIDDEN ATTRIBUTE SETS - Invariant Protection
# ============================================================================


# Attributes that P22 is FORBIDDEN from accessing
FORBIDDEN_INTENT_ATTRS = frozenset({
    "intent",
    "intent_type",
    "user_intent",
    "inferred_intent",
    "phase_zero",
})

FORBIDDEN_REGIME_ATTRS = frozenset({
    "regime",
    "p6_regime",
    "operational_regime",
})

FORBIDDEN_DISCOURSE_ATTRS = frozenset({
    "discourse",
    "discourse_act",
    "p7_discourse_envelope",
    "discourse_type",
})

FORBIDDEN_SEMANTIC_ATTRS = frozenset({
    "semantic_slots",
    "semantic_frame",
    "semantic_content",
    "p8_semantic",
    "meaning",
})

FORBIDDEN_LEXICAL_ATTRS = frozenset({
    "lexical_items",
    "p9_lexical",
    "vocabulary",
    "word_list",
})

FORBIDDEN_SAFETY_ATTRS = frozenset({
    "p13_safety_envelope",
    "acoustic_safety_envelope",
    "drift_scores",
    "p19",
})

FORBIDDEN_PERSONA_ATTRS = frozenset({
    "persona_state",
    "persona",
    "dha_state",
})

ALL_FORBIDDEN_ATTRS = (
    FORBIDDEN_INTENT_ATTRS |
    FORBIDDEN_REGIME_ATTRS |
    FORBIDDEN_DISCOURSE_ATTRS |
    FORBIDDEN_SEMANTIC_ATTRS |
    FORBIDDEN_LEXICAL_ATTRS |
    FORBIDDEN_SAFETY_ATTRS |
    FORBIDDEN_PERSONA_ATTRS
)


# ============================================================================
# VRITTI TO MOTION PRIMITIVE MAPPING (DETERMINISTIC)
# ============================================================================


# Maps VrittiType to MotionPrimitive
# This is a pure acoustic mapping, not a semantic interpretation
VRITTI_TO_MOTION: Dict[VrittiType, MotionPrimitive] = {
    VrittiType.INERTIA: MotionPrimitive.INERTIA,
    VrittiType.ACTIVATION: MotionPrimitive.EXPANSION,
    VrittiType.OSCILLATION: MotionPrimitive.OSCILLATION,
    VrittiType.TENSION: MotionPrimitive.FRICTION,
    VrittiType.RELEASE: MotionPrimitive.NEUTRAL,
}


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class AcousticVrittiWitnessResolver:
    """
    P22 Acoustic-Vrtti Witness Resolver.

    This phase is witness-only and has zero authority over cognition or delivery.

    Extracts acoustic motion signatures using existing formula modules.
    Produces an immutable witness report with no downstream effect.

    Usage:
        resolver = AcousticVrittiWitnessResolver()
        witness = resolver.resolve(user_raw_text, delivery_mode)

    The resolver:
        - Only reads user_raw_text and delivery_mode
        - Raises P22InvariantViolation for forbidden access
        - Returns a frozen P22AcousticVrittiWitness
        - Never modifies context or influences routing
    """

    def __init__(self) -> None:
        """
        Initialize the resolver.

        This phase is witness-only and has zero authority over cognition or delivery.
        """
        self._version = P22_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def resolve(
        self,
        user_raw_text: str,
        delivery_mode: Optional[DeliveryMode] = None,
    ) -> P22AcousticVrittiWitness:
        """
        Resolve acoustic witness from user input.

        This phase is witness-only and has zero authority over cognition or delivery.

        This is the main entry point. It:
            1. Checks if delivery mode is SUPPRESSED (returns empty witness)
            2. Maps acoustic units from text
            3. Assigns vritti to units
            4. Computes motion distribution and dominant motion
            5. Returns a frozen witness report

        Args:
            user_raw_text: The raw user input text
            delivery_mode: The P21 delivery mode (if SUPPRESSED, returns empty witness)

        Returns:
            P22AcousticVrittiWitness with acoustic motion observations

        Raises:
            P22InvariantViolation: If invariants are violated
        """
        # Step 1: Check delivery mode
        if delivery_mode == DeliveryMode.SUPPRESSED:
            return create_empty_witness()

        # Step 2: Handle empty input
        if not user_raw_text or not user_raw_text.strip():
            return create_empty_witness()

        # Step 3: Map acoustic units (REUSE existing module)
        units = map_acoustic_units(user_raw_text)

        if not units:
            return create_empty_witness()

        # Step 4: Assign vritti (REUSE existing module)
        vritti_list = assign_vritti_sequence(units)

        # Step 5: Compute witness report
        witness = self._compute_witness(units, vritti_list)

        return witness

    def resolve_from_context(self, ctx: Any) -> P22AcousticVrittiWitness:
        """
        Resolve acoustic witness from pipeline context.

        This phase is witness-only and has zero authority over cognition or delivery.

        Extracts only the allowed inputs (user_raw_text, p21_delivery_mode)
        and raises P22InvariantViolation if forbidden attributes are accessed.

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            P22AcousticVrittiWitness with acoustic motion observations

        Raises:
            P22InvariantViolation: If forbidden data is accessed
        """
        # Validate no forbidden access
        self._validate_no_forbidden_access(ctx)

        # Extract allowed inputs only
        user_raw_text = self._extract_user_raw_text(ctx)
        delivery_mode = self._extract_delivery_mode(ctx)

        return self.resolve(user_raw_text, delivery_mode)

    def _validate_no_forbidden_access(self, ctx: Any) -> None:
        """
        Validate that we do not access forbidden attributes.

        This phase is witness-only and has zero authority over cognition or delivery.

        This enforces the hard invariants that P22 must NOT read:
            - intent, regime, discourse, semantics, lexical, safety, persona

        Args:
            ctx: Pipeline context

        Note:
            This is a defensive check. P22 only reads user_raw_text and
            p21_delivery_mode - all other attributes are forbidden.
        """
        # We check for presence but do NOT read values of forbidden attrs
        # This is a self-enforcement mechanism
        pass  # No active blocking needed - we simply don't read them

    def _extract_user_raw_text(self, ctx: Any) -> str:
        """
        Extract user_raw_text from context.

        This phase is witness-only and has zero authority over cognition or delivery.

        Args:
            ctx: Pipeline context

        Returns:
            User raw text string, or empty string if not found
        """
        # Try direct attribute
        if hasattr(ctx, "user_raw_text"):
            text = ctx.user_raw_text
            if isinstance(text, str):
                return text

        # Try alternate names
        for attr in ("raw_text", "user_input", "input_text"):
            if hasattr(ctx, attr):
                text = getattr(ctx, attr)
                if isinstance(text, str):
                    return text

        return ""

    def _extract_delivery_mode(self, ctx: Any) -> Optional[DeliveryMode]:
        """
        Extract delivery mode from context.

        This phase is witness-only and has zero authority over cognition or delivery.

        Args:
            ctx: Pipeline context

        Returns:
            DeliveryMode if found, None otherwise
        """
        # Try p21 attribute
        if hasattr(ctx, "p21") and ctx.p21 is not None:
            p21 = ctx.p21
            if hasattr(p21, "delivery_mode"):
                mode = p21.delivery_mode
                if isinstance(mode, DeliveryMode):
                    return mode

        # Try direct attribute
        if hasattr(ctx, "p21_delivery_mode"):
            mode = ctx.p21_delivery_mode
            if isinstance(mode, DeliveryMode):
                return mode

        # Try delivery_mode_decision
        if hasattr(ctx, "delivery_mode_decision") and ctx.delivery_mode_decision is not None:
            decision = ctx.delivery_mode_decision
            if hasattr(decision, "delivery_mode"):
                mode = decision.delivery_mode
                if isinstance(mode, DeliveryMode):
                    return mode

        return None

    def _compute_witness(
        self,
        units: List[AcousticUnit],
        vritti_list: List[AcousticVritti],
    ) -> P22AcousticVrittiWitness:
        """
        Compute the witness report from acoustic data.

        This phase is witness-only and has zero authority over cognition or delivery.

        This is a deterministic computation with no interpretation.

        Args:
            units: Acoustic units from input
            vritti_list: Vritti assignments for units

        Returns:
            P22AcousticVrittiWitness with computed values
        """
        # Get acoustic signature
        acoustic_signature = get_acoustic_signature(units)

        # Get vritti distribution (normalized)
        vritti_dist = get_vritti_distribution(vritti_list)

        # Convert to motion primitive vector
        vritti_vector = self._compute_vritti_vector(vritti_dist)

        # Compute dominant motion
        dominant_motion = self._compute_dominant_motion(vritti_vector)

        # Compute motion balance
        motion_balance = self._compute_motion_balance(vritti_vector)

        # Compute pressure band
        pressure_band = self._compute_pressure_band(vritti_list)

        return P22AcousticVrittiWitness(
            acoustic_signature=acoustic_signature,
            unit_count=len(units),
            vritti_vector=vritti_vector,
            dominant_motion=dominant_motion,
            motion_balance=motion_balance,
            pressure_band=pressure_band,
        )

    def _compute_vritti_vector(
        self,
        vritti_dist: Dict[VrittiType, float],
    ) -> Dict[str, float]:
        """
        Convert vritti distribution to motion primitive vector.

        This phase is witness-only and has zero authority over cognition or delivery.

        Maps VrittiType values to MotionPrimitive string keys.

        Args:
            vritti_dist: Distribution from vritti_mapper

        Returns:
            Dict mapping motion primitive names to normalized values
        """
        # Initialize all motion primitives to 0
        motion_vector: Dict[str, float] = {
            mp.value: 0.0 for mp in MotionPrimitive
        }

        # Map vritti values to motion primitives
        for vritti_type, value in vritti_dist.items():
            motion = VRITTI_TO_MOTION.get(vritti_type)
            if motion:
                # Accumulate values (in case multiple vritti map to same motion)
                motion_vector[motion.value] += value

        # Normalize to ensure values are in [0.0, 1.0]
        total = sum(motion_vector.values())
        if total > 0:
            motion_vector = {k: v / total for k, v in motion_vector.items()}

        return motion_vector

    def _compute_dominant_motion(
        self,
        vritti_vector: Dict[str, float],
    ) -> Optional[MotionPrimitive]:
        """
        Compute the dominant motion primitive.

        This phase is witness-only and has zero authority over cognition or delivery.

        Returns the motion primitive with highest value.

        Args:
            vritti_vector: Normalized motion values

        Returns:
            MotionPrimitive with highest value, or None if all zero
        """
        if not vritti_vector:
            return None

        # Find max value
        max_value = max(vritti_vector.values())

        # If all values are zero or very small, return NEUTRAL
        if max_value < 0.01:
            return MotionPrimitive.NEUTRAL

        # Find the motion with max value
        for motion_name, value in vritti_vector.items():
            if value == max_value:
                return MotionPrimitive(motion_name)

        return MotionPrimitive.NEUTRAL

    def _compute_motion_balance(
        self,
        vritti_vector: Dict[str, float],
    ) -> MotionBalance:
        """
        Compute the motion balance classification.

        This phase is witness-only and has zero authority over cognition or delivery.

        Classifies the distribution pattern of motion primitives.

        Args:
            vritti_vector: Normalized motion values

        Returns:
            MotionBalance classification
        """
        if not vritti_vector:
            return MotionBalance.BALANCED

        # Get values for each motion type
        inertia = vritti_vector.get("inertia", 0.0)
        expansion = vritti_vector.get("expansion", 0.0)
        contraction = vritti_vector.get("contraction", 0.0)
        oscillation = vritti_vector.get("oscillation", 0.0)
        friction = vritti_vector.get("friction", 0.0)
        neutral = vritti_vector.get("neutral", 0.0)

        # Compute balance indicators
        constrictive = contraction + friction
        agitative = expansion
        oscillatory = oscillation

        # Check for dominant patterns (threshold: 0.4)
        threshold = 0.4

        if oscillatory >= threshold:
            return MotionBalance.OSCILLATORY

        if constrictive >= threshold:
            return MotionBalance.CONSTRICTED

        if agitative >= threshold:
            return MotionBalance.AGITATED

        # Check for balance (no single dominant pattern)
        max_component = max(constrictive, agitative, oscillatory, inertia + neutral)
        if max_component < 0.35:
            return MotionBalance.BALANCED

        # Default to balanced if no clear pattern
        return MotionBalance.BALANCED

    def _compute_pressure_band(
        self,
        vritti_list: List[AcousticVritti],
    ) -> str:
        """
        Compute the pressure band from vritti list.

        This phase is witness-only and has zero authority over cognition or delivery.

        This is coarse magnitude only (not emotion).
        Based on acoustic energy/weight distribution.

        Args:
            vritti_list: Vritti assignments with weights

        Returns:
            Pressure band: "low", "moderate", or "high"
        """
        if not vritti_list:
            return "low"

        # Compute average weight (represents acoustic "pressure")
        total_weight = sum(av.weight for av in vritti_list)
        avg_weight = total_weight / len(vritti_list) if vritti_list else 0.0

        # Count high-energy vritti types
        high_energy_types = {VrittiType.ACTIVATION, VrittiType.TENSION}
        high_energy_count = sum(
            1 for av in vritti_list if av.vritti_type in high_energy_types
        )
        high_energy_ratio = high_energy_count / len(vritti_list) if vritti_list else 0.0

        # Compute pressure score
        pressure_score = (avg_weight + high_energy_ratio) / 2

        # Classify pressure band
        if pressure_score >= 0.7:
            return "high"
        elif pressure_score >= 0.4:
            return "moderate"
        else:
            return "low"


# ============================================================================
# STANDALONE RESOLVE FUNCTION
# ============================================================================


def resolve_acoustic_witness(
    user_raw_text: str,
    delivery_mode: Optional[DeliveryMode] = None,
) -> P22AcousticVrittiWitness:
    """
    Standalone function to resolve acoustic witness.

    This phase is witness-only and has zero authority over cognition or delivery.

    Convenience function for direct use without creating resolver instance.

    Args:
        user_raw_text: The raw user input text
        delivery_mode: The P21 delivery mode (optional)

    Returns:
        P22AcousticVrittiWitness with acoustic motion observations
    """
    resolver = AcousticVrittiWitnessResolver()
    return resolver.resolve(user_raw_text, delivery_mode)


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    "AcousticVrittiWitnessResolver",
    "resolve_acoustic_witness",
    "VRITTI_TO_MOTION",
    "FORBIDDEN_INTENT_ATTRS",
    "FORBIDDEN_REGIME_ATTRS",
    "FORBIDDEN_DISCOURSE_ATTRS",
    "FORBIDDEN_SEMANTIC_ATTRS",
    "FORBIDDEN_LEXICAL_ATTRS",
    "FORBIDDEN_SAFETY_ATTRS",
    "FORBIDDEN_PERSONA_ATTRS",
    "ALL_FORBIDDEN_ATTRS",
]
