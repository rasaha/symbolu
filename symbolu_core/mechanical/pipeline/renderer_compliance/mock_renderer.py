"""
Mock Renderer Implementations

This module provides mock renderers for testing P13 compliance enforcement.
These renderers do NOT generate audio - they output AcousticRenderIntent
objects describing what they would do.

The mock renderers include:
1. CompliantRenderer - Always complies with P13
2. AmplifyingRenderer - Exceeds pitch/energy bounds
3. AuthorityRenderer - Introduces authority/certainty signals
4. EmotiveRenderer - Adds emotional expression despite prohibition
5. IgnoreSafetyRenderer - Ignores P13 envelope entirely
6. BoundaryPusherRenderer - Stays just outside allowed ranges

CRITICAL: These renderers exist to TEST compliance checking.
They demonstrate that unsafe behavior is DETECTED and BLOCKED.

None of these renderers produce sound. They are compliance testing fixtures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_contract import (
    AcousticRenderIntent,
    RenderIntentCategory,
    RendererInputContract,
)


# ============================================================================
# CONSTANTS
# ============================================================================


# Epsilon for boundary testing (just beyond limit)
BOUNDARY_EPSILON_PITCH = 1  # 1 Hz above limit
BOUNDARY_EPSILON_ENERGY = 0.01  # 0.01 above limit
BOUNDARY_EPSILON_VARIANCE = 1  # 1 Hz above limit


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================


class MockRenderer(ABC):
    """
    Abstract base class for mock renderers.

    All mock renderers:
    - Receive a RendererInputContract
    - Output an AcousticRenderIntent (NOT audio)
    - Have a unique renderer_id
    """

    def __init__(self, renderer_id: Optional[str] = None) -> None:
        """Initialize mock renderer with optional custom ID."""
        self._renderer_id = renderer_id or self.__class__.__name__

    @property
    def renderer_id(self) -> str:
        """Get the renderer identifier."""
        return self._renderer_id

    @abstractmethod
    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """
        Process the contract and produce a render intent.

        Args:
            contract: The RendererInputContract from Symbol-U

        Returns:
            An AcousticRenderIntent describing intended acoustic output
        """
        pass

    def _get_debug_info(self, contract: RendererInputContract) -> Dict[str, Any]:
        """Get debug info for render intent."""
        return {
            "renderer_class": self.__class__.__name__,
            "renderer_id": self.renderer_id,
            "contract_regime": contract.source_regime,
            "contract_blocked": contract.is_blocked(),
        }


# ============================================================================
# COMPLIANT RENDERER
# ============================================================================


class CompliantRenderer(MockRenderer):
    """
    A renderer that always complies with P13 constraints.

    This renderer:
    - Reads P13 envelope bounds verbatim
    - Uses parameters strictly within bounds
    - Respects all expression flags
    - Never exceeds any limit
    - Produces COMPLIANT intent category

    This is the ONLY safe renderer. All tests should show this
    renderer passing compliance checks.
    """

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce a fully compliant render intent."""
        envelope = contract.p13_envelope

        # Use allowed bounds exactly (or conservatively within)
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range
        variance_range = envelope.allowed_variance_range

        # Respect expression flags exactly
        allow_emphasis = envelope.allow_emphasis
        allow_pitch_contours = envelope.allow_pitch_contours
        allow_rhythm_variation = envelope.allow_rhythm_variation
        allow_intonation_shift = envelope.allow_intonation_shift

        # Check if envelope is fully restricted
        is_fully_restricted = (
            not allow_emphasis and
            not allow_pitch_contours and
            not allow_rhythm_variation and
            not allow_intonation_shift
        )

        # Compute conservative pitch variance (within allowed)
        max_variance = variance_range[1]

        # Under fully restricted envelope, use VERY conservative variance (25% of max)
        # to ensure we pass the semantic excessive variance check
        if is_fully_restricted:
            target_variance = max(0, max_variance // 4)
        else:
            # Use half variance under normal conditions
            target_variance = max_variance // 2

        # Use pitch range that produces variance within limit
        pitch_mid = (pitch_range[0] + pitch_range[1]) // 2
        half_variance = min(target_variance // 2, (pitch_range[1] - pitch_range[0]) // 2)

        intended_pitch_min = max(pitch_range[0], pitch_mid - half_variance)
        intended_pitch_max = min(pitch_range[1], pitch_mid + half_variance)
        intended_variance = intended_pitch_max - intended_pitch_min

        # Use energy conservatively within bounds
        intended_energy_min = energy_range[0]
        # Under fully restricted, use 50% of allowed range for energy
        if is_fully_restricted:
            intended_energy_max = energy_range[0] + (energy_range[1] - energy_range[0]) * 0.5
        else:
            intended_energy_max = min(energy_range[1], (energy_range[0] + energy_range[1]) / 2)

        # Stressed tokens: 0 if emphasis not allowed
        intended_stressed = 1 if allow_emphasis else 0

        return AcousticRenderIntent(
            intended_pitch_min=intended_pitch_min,
            intended_pitch_max=intended_pitch_max,
            intended_pitch_variance=intended_variance,
            intended_energy_min=intended_energy_min,
            intended_energy_max=intended_energy_max,
            will_use_emphasis=allow_emphasis,
            will_use_pitch_contours=allow_pitch_contours,
            will_use_rhythm_variation=allow_rhythm_variation,
            will_use_intonation_shift=allow_intonation_shift,
            intended_stressed_tokens=intended_stressed,
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.COMPLIANT,
            debug=self._get_debug_info(contract),
        )


# ============================================================================
# AMPLIFYING RENDERER
# ============================================================================


class AmplifyingRenderer(MockRenderer):
    """
    A renderer that amplifies acoustic parameters beyond P13 limits.

    This renderer:
    - Exceeds pitch bounds by a significant margin
    - Exceeds energy bounds by a significant margin
    - Exceeds variance bounds
    - Produces AMPLIFIED intent category

    This renderer should ALWAYS fail compliance checks.
    It demonstrates that acoustic amplification is detected.
    """

    def __init__(
        self,
        renderer_id: Optional[str] = None,
        pitch_amplification: int = 20,  # Hz beyond limit
        energy_amplification: float = 0.15,  # Beyond limit
        variance_amplification: int = 15,  # Hz beyond limit
    ) -> None:
        """Initialize with configurable amplification amounts."""
        super().__init__(renderer_id)
        self._pitch_amp = pitch_amplification
        self._energy_amp = energy_amplification
        self._variance_amp = variance_amplification

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce an amplified (non-compliant) render intent."""
        envelope = contract.p13_envelope

        # AMPLIFY: Exceed bounds deliberately
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range
        variance_range = envelope.allowed_variance_range

        # Exceed pitch bounds
        intended_pitch_min = pitch_range[0] - self._pitch_amp
        intended_pitch_max = pitch_range[1] + self._pitch_amp

        # Exceed energy bounds
        intended_energy_min = energy_range[0]
        intended_energy_max = energy_range[1] + self._energy_amp

        # Exceed variance bounds
        intended_variance = variance_range[1] + self._variance_amp

        return AcousticRenderIntent(
            intended_pitch_min=intended_pitch_min,
            intended_pitch_max=intended_pitch_max,
            intended_pitch_variance=intended_variance,
            intended_energy_min=intended_energy_min,
            intended_energy_max=intended_energy_max,
            will_use_emphasis=True,  # Force emphasis
            will_use_pitch_contours=True,  # Force contours
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=5,  # Many stressed tokens
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.AMPLIFIED,
            debug={
                **self._get_debug_info(contract),
                "pitch_amplification": self._pitch_amp,
                "energy_amplification": self._energy_amp,
                "variance_amplification": self._variance_amp,
            },
        )


# ============================================================================
# AUTHORITY RENDERER
# ============================================================================


class AuthorityRenderer(MockRenderer):
    """
    A renderer that introduces authority/certainty signals.

    This renderer:
    - Uses high energy to signal confidence
    - Uses emphatic stress patterns
    - Introduces assertive prosodic contours
    - Produces AUTHORITATIVE intent category

    This renderer should ALWAYS fail compliance checks under
    REFLEXIVE/RELATIONAL grounding or HOLD/DE_ESCALATE regimes.
    It demonstrates that authority signaling is detected.
    """

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce an authoritative (non-compliant) render intent."""
        envelope = contract.p13_envelope

        # Get bounds but ignore expression flags
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range

        # Use maximum energy for authority signaling
        intended_energy_max = energy_range[1]

        # Use wide pitch range for assertive contours
        pitch_variance = pitch_range[1] - pitch_range[0]

        return AcousticRenderIntent(
            intended_pitch_min=pitch_range[0],
            intended_pitch_max=pitch_range[1],
            intended_pitch_variance=pitch_variance,
            intended_energy_min=energy_range[0],
            intended_energy_max=intended_energy_max,
            will_use_emphasis=True,  # Force emphasis for authority
            will_use_pitch_contours=True,  # Force contours for assertiveness
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=3,  # Multiple stressed for authority
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.AUTHORITATIVE,
            debug={
                **self._get_debug_info(contract),
                "authority_signal": "high_energy_emphasis",
            },
        )


# ============================================================================
# EMOTIVE RENDERER
# ============================================================================


class EmotiveRenderer(MockRenderer):
    """
    A renderer that adds emotional expression despite prohibition.

    This renderer:
    - Adds emphasis even when allow_emphasis=False
    - Adds pitch contours even when allow_pitch_contours=False
    - Uses emotional intonation patterns
    - Produces EMOTIVE intent category

    This renderer should ALWAYS fail compliance checks when
    expressive flags are False in P13.
    It demonstrates that emotion amplification is detected.
    """

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce an emotive (non-compliant) render intent."""
        envelope = contract.p13_envelope

        # Get bounds
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range
        variance_range = envelope.allowed_variance_range

        # Stay within numeric bounds but IGNORE expression flags
        # This tests that expression flags are checked, not just bounds

        return AcousticRenderIntent(
            intended_pitch_min=pitch_range[0],
            intended_pitch_max=pitch_range[1],
            intended_pitch_variance=variance_range[1],
            intended_energy_min=energy_range[0],
            intended_energy_max=energy_range[1],
            # IGNORE P13 expression flags - always use expression
            will_use_emphasis=True,  # Ignore allow_emphasis
            will_use_pitch_contours=True,  # Ignore allow_pitch_contours
            will_use_rhythm_variation=True,  # Ignore allow_rhythm_variation
            will_use_intonation_shift=True,  # Ignore allow_intonation_shift
            intended_stressed_tokens=2,  # Emotional stress
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.EMOTIVE,
            debug={
                **self._get_debug_info(contract),
                "emotion_injection": "forced_expression",
                "ignored_flags": {
                    "allow_emphasis": envelope.allow_emphasis,
                    "allow_pitch_contours": envelope.allow_pitch_contours,
                    "allow_rhythm_variation": envelope.allow_rhythm_variation,
                    "allow_intonation_shift": envelope.allow_intonation_shift,
                },
            },
        )


# ============================================================================
# IGNORE SAFETY RENDERER
# ============================================================================


class IgnoreSafetyRenderer(MockRenderer):
    """
    A renderer that completely ignores the P13 safety envelope.

    This renderer:
    - Ignores P13 entirely
    - Uses arbitrary acoustic parameters
    - Renders even when BLOCKED
    - Produces IGNORED intent category

    This renderer should ALWAYS fail compliance checks.
    It demonstrates that complete safety bypass is detected.
    """

    def __init__(
        self,
        renderer_id: Optional[str] = None,
        force_pitch_min: int = 50,   # Way below safe
        force_pitch_max: int = 200,  # Way above safe
        force_energy: float = 0.9,   # Way above safe
        force_variance: int = 100,   # Way above safe
    ) -> None:
        """Initialize with configurable forced parameters."""
        super().__init__(renderer_id)
        self._force_pitch_min = force_pitch_min
        self._force_pitch_max = force_pitch_max
        self._force_energy = force_energy
        self._force_variance = force_variance

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce a safety-ignoring (non-compliant) render intent."""
        # COMPLETELY IGNORE the contract's P13 envelope
        # Use arbitrary unsafe parameters

        return AcousticRenderIntent(
            intended_pitch_min=self._force_pitch_min,
            intended_pitch_max=self._force_pitch_max,
            intended_pitch_variance=self._force_variance,
            intended_energy_min=0.1,
            intended_energy_max=self._force_energy,
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=10,
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.IGNORED,
            debug={
                **self._get_debug_info(contract),
                "safety_ignored": True,
                "forced_parameters": {
                    "pitch_min": self._force_pitch_min,
                    "pitch_max": self._force_pitch_max,
                    "energy": self._force_energy,
                    "variance": self._force_variance,
                },
            },
        )


# ============================================================================
# BOUNDARY PUSHER RENDERER
# ============================================================================


class BoundaryPusherRenderer(MockRenderer):
    """
    A renderer that stays JUST outside allowed ranges.

    This renderer:
    - Uses pitch exactly 1 Hz above max allowed
    - Uses energy exactly 0.01 above max allowed
    - Uses variance exactly 1 Hz above max allowed
    - Produces BOUNDARY intent category

    This renderer tests that boundary checking is precise.
    Even epsilon above limit must be detected and blocked.
    """

    def __init__(
        self,
        renderer_id: Optional[str] = None,
        epsilon_pitch: int = BOUNDARY_EPSILON_PITCH,
        epsilon_energy: float = BOUNDARY_EPSILON_ENERGY,
        epsilon_variance: int = BOUNDARY_EPSILON_VARIANCE,
    ) -> None:
        """Initialize with configurable epsilon values."""
        super().__init__(renderer_id)
        self._epsilon_pitch = epsilon_pitch
        self._epsilon_energy = epsilon_energy
        self._epsilon_variance = epsilon_variance

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce a boundary-pushing (non-compliant) render intent."""
        envelope = contract.p13_envelope

        # Get exact bounds
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range
        variance_range = envelope.allowed_variance_range

        # Stay JUST outside bounds (epsilon above max)
        intended_pitch_max = pitch_range[1] + self._epsilon_pitch
        intended_energy_max = energy_range[1] + self._epsilon_energy
        intended_variance = variance_range[1] + self._epsilon_variance

        return AcousticRenderIntent(
            intended_pitch_min=pitch_range[0],
            intended_pitch_max=intended_pitch_max,
            intended_pitch_variance=intended_variance,
            intended_energy_min=energy_range[0],
            intended_energy_max=intended_energy_max,
            # Respect expression flags (testing bounds, not flags)
            will_use_emphasis=envelope.allow_emphasis,
            will_use_pitch_contours=envelope.allow_pitch_contours,
            will_use_rhythm_variation=envelope.allow_rhythm_variation,
            will_use_intonation_shift=envelope.allow_intonation_shift,
            intended_stressed_tokens=1 if envelope.allow_emphasis else 0,
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.BOUNDARY,
            debug={
                **self._get_debug_info(contract),
                "epsilon_pitch": self._epsilon_pitch,
                "epsilon_energy": self._epsilon_energy,
                "epsilon_variance": self._epsilon_variance,
                "boundary_violations": {
                    "pitch_over": self._epsilon_pitch,
                    "energy_over": self._epsilon_energy,
                    "variance_over": self._epsilon_variance,
                },
            },
        )


# ============================================================================
# EXACT BOUNDARY RENDERER (Compliant at exact limit)
# ============================================================================


class ExactBoundaryRenderer(MockRenderer):
    """
    A renderer that stays EXACTLY at allowed limits.

    This renderer:
    - Uses pitch exactly at max allowed
    - Uses energy exactly at max allowed
    - Uses variance exactly at max allowed
    - Produces COMPLIANT intent category

    This renderer tests that exact boundary values are ALLOWED.
    Exactly at limit should PASS (not FAIL).
    """

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce an exact-boundary (compliant) render intent."""
        envelope = contract.p13_envelope

        # Use EXACTLY the allowed bounds
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range
        variance_range = envelope.allowed_variance_range

        return AcousticRenderIntent(
            intended_pitch_min=pitch_range[0],
            intended_pitch_max=pitch_range[1],  # Exact max
            intended_pitch_variance=variance_range[1],  # Exact max
            intended_energy_min=energy_range[0],
            intended_energy_max=energy_range[1],  # Exact max
            will_use_emphasis=envelope.allow_emphasis,
            will_use_pitch_contours=envelope.allow_pitch_contours,
            will_use_rhythm_variation=envelope.allow_rhythm_variation,
            will_use_intonation_shift=envelope.allow_intonation_shift,
            intended_stressed_tokens=1 if envelope.allow_emphasis else 0,
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.COMPLIANT,
            debug={
                **self._get_debug_info(contract),
                "boundary_behavior": "exact_at_limit",
            },
        )


# ============================================================================
# BLOCKED OVERRIDE RENDERER
# ============================================================================


class BlockedOverrideRenderer(MockRenderer):
    """
    A renderer that attempts to render when envelope is BLOCKED.

    This renderer:
    - Produces output even when P13 risk_level is BLOCKED
    - Uses minimal but non-zero expression
    - Produces IGNORED intent category

    This renderer should ALWAYS fail when envelope is BLOCKED.
    It demonstrates that BLOCKED envelopes cannot be bypassed.
    """

    def render(self, contract: RendererInputContract) -> AcousticRenderIntent:
        """Produce a render intent that ignores BLOCKED status."""
        envelope = contract.p13_envelope

        # Use envelope bounds but ignore BLOCKED status
        pitch_range = envelope.allowed_pitch_range
        energy_range = envelope.allowed_energy_range

        return AcousticRenderIntent(
            intended_pitch_min=pitch_range[0],
            intended_pitch_max=pitch_range[1],
            intended_pitch_variance=10,  # Minimal variance
            intended_energy_min=energy_range[0],
            intended_energy_max=energy_range[1],
            # Use ANY expression (should be none under BLOCKED)
            will_use_emphasis=True,
            will_use_pitch_contours=True,
            will_use_rhythm_variation=True,
            will_use_intonation_shift=True,
            intended_stressed_tokens=1,
            renderer_id=self.renderer_id,
            intent_category=RenderIntentCategory.IGNORED,
            debug={
                **self._get_debug_info(contract),
                "ignored_blocked": True,
                "envelope_blocked": envelope.is_blocked() if hasattr(envelope, 'is_blocked') else False,
            },
        )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Constants
    "BOUNDARY_EPSILON_PITCH",
    "BOUNDARY_EPSILON_ENERGY",
    "BOUNDARY_EPSILON_VARIANCE",
    # Base class
    "MockRenderer",
    # Implementations
    "CompliantRenderer",
    "AmplifyingRenderer",
    "AuthorityRenderer",
    "EmotiveRenderer",
    "IgnoreSafetyRenderer",
    "BoundaryPusherRenderer",
    "ExactBoundaryRenderer",
    "BlockedOverrideRenderer",
]
