"""Speech Pipeline - Unified End-to-End Speech Generation.

This module provides the complete speech generation pipeline from
PresentationDirective through SSML output with GOVERNED mode enforcement.

Complete Pipeline:
-----------------
    PresentationDirective
            ↓
    AcousticGovernanceChain (P6-Lite → P7-Lite → P10 → P12)
            ↓
    GovernedGate (GOVERNED/OPEN/AUDIT decision)
            ↓
    ProsodicRenderer (SSML generation)
            ↓
    SpeechOutput (final result)

Design Principles:
-----------------
1. Sound must obey meaning (acoustic constraints are authoritative)
2. Fail-closed in GOVERNED mode (block on critical violations)
3. Deterministic output (same input → identical SSML)
4. Full traceability from directive to speech
5. No semantic interpretation in prosodic rendering

Usage:
    from symbolu.presentation import PresentationEngine, CONSUMER_CONFIG
    from symbolu.presentation.speech_pipeline import SpeechPipeline, PipelineMode

    # Create presentation directive
    engine = PresentationEngine(CONSUMER_CONFIG)
    directive = engine.compute(signal_bundle)

    # Run complete speech pipeline
    pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
    result = pipeline.execute(
        directive=directive,
        text="I'm not entirely certain about that.",
    )

    if result.is_blocked:
        print(f"Blocked: {result.fallback_response}")
    else:
        print(result.ssml)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Dict, List, Optional

from symbolu.presentation.types import PresentationDirective
from symbolu.presentation.acoustic_chain import (
    AcousticGovernanceChain,
    AcousticChainResult,
)
from symbolu.presentation.prosodic_renderer import (
    ProsodicRenderer,
    SSMLOutput,
    render_minimal_ssml,
)
from symbolu.presentation.governed_gate import (
    GovernedGate,
    GateMode,
    GateDecision,
    GateAction,
)


# =============================================================================
# PIPELINE MODE ENUM
# =============================================================================


@unique
class PipelineMode(str, Enum):
    """Speech pipeline operation mode.

    GOVERNED: Production - strict enforcement, blocks on critical violations
    OPEN: Development - permissive, allows with warnings
    BYPASS: Testing - skip gate entirely, always render
    """
    GOVERNED = "governed"
    OPEN = "open"
    BYPASS = "bypass"


# =============================================================================
# SPEECH OUTPUT
# =============================================================================


@dataclass(frozen=True)
class SpeechOutput:
    """Complete speech pipeline output.

    Attributes:
        ssml: The final SSML string (or fallback)
        plain_text: The original plain text input
        is_blocked: True if output was blocked by gate
        is_fallback: True if using fallback response
        fallback_response: Fallback text if blocked
        gate_decision: The GovernedGate decision
        chain_result: The AcousticChainResult
        ssml_output: The SSMLOutput (None if blocked)
        mode: The pipeline mode used
        debug: Additional debug information
    """
    ssml: str
    plain_text: str
    is_blocked: bool
    is_fallback: bool
    fallback_response: Optional[str]
    gate_decision: GateDecision
    chain_result: AcousticChainResult
    ssml_output: Optional[SSMLOutput]
    mode: PipelineMode
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_consistent(self) -> bool:
        """Check if P12 audit passed with no violations."""
        return self.chain_result.is_consistent

    @property
    def acoustic_regime(self) -> str:
        """Get the acoustic regime used."""
        return self.chain_result.acoustic_frame.regime.value

    @property
    def delivery_mode(self) -> str:
        """Get the source delivery mode."""
        return self.chain_result.directive.delivery_mode.value

    @property
    def violation_count(self) -> int:
        """Get total violation count."""
        return self.gate_decision.total_violations


# =============================================================================
# SPEECH PIPELINE
# =============================================================================


class SpeechPipeline:
    """Unified end-to-end speech generation pipeline.

    This pipeline orchestrates the complete flow from PresentationDirective
    to SSML output, including:
    1. Acoustic governance (P6-Lite → P7-Lite → P10 → P12)
    2. GOVERNED mode gate enforcement
    3. Prosodic SSML rendering

    Example:
        pipeline = SpeechPipeline(mode=PipelineMode.GOVERNED)
        result = pipeline.execute(directive, "Hello world")

        if not result.is_blocked:
            synthesize(result.ssml)
        else:
            synthesize(render_minimal_ssml(result.fallback_response))
    """

    def __init__(self, mode: PipelineMode = PipelineMode.GOVERNED) -> None:
        """Initialize the speech pipeline.

        Args:
            mode: Pipeline operation mode (default: GOVERNED)
        """
        self._mode = mode
        self._acoustic_chain = AcousticGovernanceChain()
        self._renderer = ProsodicRenderer()

        # Map pipeline mode to gate mode
        gate_mode_map = {
            PipelineMode.GOVERNED: GateMode.GOVERNED,
            PipelineMode.OPEN: GateMode.OPEN,
            PipelineMode.BYPASS: GateMode.AUDIT_ONLY,
        }
        self._gate = GovernedGate(mode=gate_mode_map[mode])

    @property
    def mode(self) -> PipelineMode:
        """Get the current pipeline mode."""
        return self._mode

    def execute(
        self,
        directive: PresentationDirective,
        text: str,
        *,
        emphasis_tokens: Optional[List[str]] = None,
    ) -> SpeechOutput:
        """Execute the complete speech pipeline.

        Args:
            directive: The PresentationDirective from Presentation Engine
            text: The plain text to render as speech
            emphasis_tokens: Optional tokens to emphasize

        Returns:
            SpeechOutput with SSML or fallback response

        Raises:
            ValueError: If directive is None or text is empty
        """
        if directive is None:
            raise ValueError("directive cannot be None")
        if not text or not text.strip():
            raise ValueError("text cannot be empty")

        # Stage 1: Run acoustic governance chain
        chain_result = self._acoustic_chain.execute(directive)

        # Stage 2: Evaluate gate decision
        gate_decision = self._gate.evaluate(chain_result)

        # Stage 3: Render or use fallback based on gate decision
        if gate_decision.should_block:
            # Use fallback response
            fallback = gate_decision.fallback_response or "I need to reconsider."
            ssml = render_minimal_ssml(fallback)

            return SpeechOutput(
                ssml=ssml,
                plain_text=text,
                is_blocked=True,
                is_fallback=True,
                fallback_response=fallback,
                gate_decision=gate_decision,
                chain_result=chain_result,
                ssml_output=None,
                mode=self._mode,
                debug=self._build_debug(chain_result, gate_decision, blocked=True),
            )

        # Stage 4: Render SSML from acoustic frame
        ssml_output = self._renderer.render(
            frame=chain_result.acoustic_frame,
            text=text,
            emphasis_tokens=emphasis_tokens,
        )

        return SpeechOutput(
            ssml=ssml_output.ssml,
            plain_text=text,
            is_blocked=False,
            is_fallback=False,
            fallback_response=None,
            gate_decision=gate_decision,
            chain_result=chain_result,
            ssml_output=ssml_output,
            mode=self._mode,
            debug=self._build_debug(chain_result, gate_decision, blocked=False),
        )

    def _build_debug(
        self,
        chain_result: AcousticChainResult,
        gate_decision: GateDecision,
        blocked: bool,
    ) -> Dict[str, Any]:
        """Build debug information."""
        return {
            "pipeline_mode": self._mode.value,
            "gate_action": gate_decision.action.value,
            "blocked": blocked,
            "delivery_mode": chain_result.directive.delivery_mode.value,
            "confidence": chain_result.directive.confidence.value,
            "regime": chain_result.regime_envelope.regime.value,
            "discourse_act": chain_result.discourse_envelope.act.value,
            "acoustic_regime": chain_result.acoustic_frame.regime.value,
            "is_consistent": chain_result.is_consistent,
            "violation_count": gate_decision.total_violations,
            "critical_count": gate_decision.critical_count,
            "major_count": gate_decision.major_count,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def generate_speech(
    directive: PresentationDirective,
    text: str,
    mode: PipelineMode = PipelineMode.GOVERNED,
) -> SpeechOutput:
    """Convenience function to generate speech from directive.

    Args:
        directive: The PresentationDirective from Presentation Engine
        text: The plain text to render
        mode: Pipeline mode (default: GOVERNED)

    Returns:
        SpeechOutput with complete result

    Example:
        >>> output = generate_speech(directive, "Hello world")
        >>> if not output.is_blocked:
        ...     print(output.ssml)
    """
    pipeline = SpeechPipeline(mode=mode)
    return pipeline.execute(directive, text)


def generate_ssml(
    directive: PresentationDirective,
    text: str,
) -> str:
    """Generate SSML string directly (GOVERNED mode).

    Returns fallback SSML if blocked.

    Args:
        directive: The PresentationDirective
        text: The plain text

    Returns:
        SSML string (either rendered or fallback)
    """
    output = generate_speech(directive, text)
    return output.ssml


def is_speech_allowed(directive: PresentationDirective) -> bool:
    """Check if speech would be allowed in GOVERNED mode.

    Args:
        directive: The PresentationDirective to check

    Returns:
        True if speech would be allowed
    """
    chain = AcousticGovernanceChain()
    result = chain.execute(directive)
    gate = GovernedGate(mode=GateMode.GOVERNED)
    decision = gate.evaluate(result)
    return not decision.should_block


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main classes
    "SpeechPipeline",
    "SpeechOutput",
    # Enums
    "PipelineMode",
    # Convenience functions
    "generate_speech",
    "generate_ssml",
    "is_speech_allowed",
]
