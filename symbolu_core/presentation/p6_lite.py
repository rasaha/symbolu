"""P6-Lite: Regime Derivation from Presentation Layer.

This module provides a lightweight bridge from Presentation Layer outputs
to P10 Acoustic Parameterization inputs, enabling activation of the
acoustic governance chain (P10/P11/P12) without requiring full P6 implementation.

Design Rationale:
-----------------
P10 requires a RegimeEnvelope from P6 to determine acoustic parameters.
Rather than implement full P6 (which requires PO1-PO5 signals), p6_lite
derives a regime from the already-computed PresentationDirective.

This approach:
1. Leverages the existing CV → Presentation pipeline
2. Enables meaningful P12 auditing (not "meaningless theater")
3. Creates minimal technical debt (straightforward mapping)
4. Can be superseded by full P6 implementation later

Mapping Logic:
--------------
DeliveryMode → OperationalRegime:
    SILENT       → HOLD         (most conservative, no output)
    ACKNOWLEDGING → STABILIZE   (minimal acknowledgment)
    CLARIFYING   → CLARIFY      (seeking clarification)
    HEDGED       → DE_ESCALATE  (careful/hedged response)
    CONFIDENT    → INFORM       (direct information delivery)

ConfidenceIndicator → coherence_regime:
    HIGH    → "COHERENT"
    MEDIUM  → "UNSTABLE"
    LOW     → "DEGRADED"
    UNKNOWN → "UNKNOWN"

Authority Model:
---------------
- Reads PresentationDirective (downstream of CV engine)
- Produces RegimeEnvelope for P10 consumption
- Does not override Presentation Layer decisions
- Conservative defaults on any ambiguity

ARCHITECTURAL PRINCIPLE:
    Sound must obey meaning.
    Meaning must never obey sound.

    p6_lite preserves this by deriving regime from semantic decisions
    (Presentation Layer), not acoustic preferences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from symbolu_core.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
)
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu_core.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility


# =============================================================================
# MAPPING CONSTANTS
# =============================================================================

# DeliveryMode → OperationalRegime
DELIVERY_MODE_TO_REGIME: Dict[DeliveryMode, OperationalRegime] = {
    DeliveryMode.SILENT: OperationalRegime.HOLD,
    DeliveryMode.ACKNOWLEDGING: OperationalRegime.STABILIZE,
    DeliveryMode.CLARIFYING: OperationalRegime.CLARIFY,
    DeliveryMode.HEDGED: OperationalRegime.DE_ESCALATE,
    DeliveryMode.CONFIDENT: OperationalRegime.INFORM,
}

# DeliveryMode → IntentType (derived)
DELIVERY_MODE_TO_INTENT: Dict[DeliveryMode, IntentType] = {
    DeliveryMode.SILENT: IntentType.ABSTAIN,
    DeliveryMode.ACKNOWLEDGING: IntentType.SUPPORT,
    DeliveryMode.CLARIFYING: IntentType.CLARIFY,
    DeliveryMode.HEDGED: IntentType.SUPPORT,
    DeliveryMode.CONFIDENT: IntentType.INFORM,
}

# ConfidenceIndicator → coherence_regime string
CONFIDENCE_TO_COHERENCE: Dict[ConfidenceIndicator, str] = {
    ConfidenceIndicator.HIGH: "COHERENT",
    ConfidenceIndicator.MEDIUM: "UNSTABLE",
    ConfidenceIndicator.LOW: "DEGRADED",
    ConfidenceIndicator.UNKNOWN: "UNKNOWN",
}

# ConfidenceIndicator → ExecutionEligibility
CONFIDENCE_TO_ELIGIBILITY: Dict[ConfidenceIndicator, ExecutionEligibility] = {
    ConfidenceIndicator.HIGH: ExecutionEligibility.ELIGIBLE,
    ConfidenceIndicator.MEDIUM: ExecutionEligibility.DEFERRED,
    ConfidenceIndicator.LOW: ExecutionEligibility.PROHIBITED,
    ConfidenceIndicator.UNKNOWN: ExecutionEligibility.DEFERRED,
}

# Safe defaults
DEFAULT_REGIME = OperationalRegime.HOLD
DEFAULT_INTENT = IntentType.ABSTAIN
DEFAULT_COHERENCE = "UNKNOWN"
DEFAULT_ELIGIBILITY = ExecutionEligibility.DEFERRED


# =============================================================================
# P6-LITE RESOLVER
# =============================================================================


class P6LiteResolver:
    """Lightweight regime resolver from Presentation Layer outputs.

    This resolver derives P6 RegimeEnvelope from PresentationDirective,
    enabling the acoustic governance chain without full P6 implementation.

    Usage:
        from symbolu_core.presentation import PresentationEngine, CONSUMER_CONFIG
        from symbolu_core.presentation.p6_lite import P6LiteResolver

        # Compute presentation directive
        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)

        # Derive regime for P10
        p6_lite = P6LiteResolver()
        regime_envelope = p6_lite.resolve(directive)

        # Now P10 can consume regime_envelope
        p10_resolver = P10AcousticResolver()
        acoustic_frame = p10_resolver.resolve(
            regime_envelope=regime_envelope,
            discourse_envelope=discourse_envelope,  # from P7 or p7_lite
            lexical_frame=lexical_frame,  # from P9 or None
        )

    Invariants:
    - Pure, deterministic resolution
    - Never modifies the input directive
    - Conservative defaults on missing data
    - Always produces a valid RegimeEnvelope
    """

    def __init__(self) -> None:
        """Initialize the P6-Lite resolver."""
        pass  # Stateless resolver

    def resolve(
        self,
        directive: PresentationDirective,
        *,
        override_intent: Optional[IntentType] = None,
        override_eligibility: Optional[ExecutionEligibility] = None,
        override_coherence: Optional[str] = None,
    ) -> RegimeEnvelope:
        """Derive RegimeEnvelope from PresentationDirective.

        Args:
            directive: The PresentationDirective from Presentation Engine
            override_intent: Optional explicit IntentType (for integration with PO2)
            override_eligibility: Optional explicit ExecutionEligibility (for PO5)
            override_coherence: Optional explicit coherence regime string

        Returns:
            RegimeEnvelope suitable for P10 consumption
        """
        # 1. Derive regime from delivery mode
        regime = self._derive_regime(directive.delivery_mode)

        # 2. Derive or use overridden intent
        intent = override_intent or self._derive_intent(directive.delivery_mode)

        # 3. Derive or use overridden eligibility
        eligibility = override_eligibility or self._derive_eligibility(directive.confidence)

        # 4. Derive or use overridden coherence regime
        coherence = override_coherence or self._derive_coherence(directive.confidence)

        # 5. Build reason string
        reason = self._build_reason(directive, regime)

        # 6. Build debug info
        debug = self._build_debug(directive)

        return RegimeEnvelope(
            regime=regime,
            reason=reason,
            intent=intent,
            execution_eligibility=eligibility,
            coherence_regime=coherence,
            debug=debug,
        )

    def _derive_regime(self, delivery_mode: DeliveryMode) -> OperationalRegime:
        """Derive OperationalRegime from DeliveryMode."""
        return DELIVERY_MODE_TO_REGIME.get(delivery_mode, DEFAULT_REGIME)

    def _derive_intent(self, delivery_mode: DeliveryMode) -> IntentType:
        """Derive IntentType from DeliveryMode."""
        return DELIVERY_MODE_TO_INTENT.get(delivery_mode, DEFAULT_INTENT)

    def _derive_eligibility(
        self,
        confidence: ConfidenceIndicator,
    ) -> ExecutionEligibility:
        """Derive ExecutionEligibility from ConfidenceIndicator."""
        return CONFIDENCE_TO_ELIGIBILITY.get(confidence, DEFAULT_ELIGIBILITY)

    def _derive_coherence(self, confidence: ConfidenceIndicator) -> str:
        """Derive coherence regime string from ConfidenceIndicator."""
        return CONFIDENCE_TO_COHERENCE.get(confidence, DEFAULT_COHERENCE)

    def _build_reason(
        self,
        directive: PresentationDirective,
        regime: OperationalRegime,
    ) -> str:
        """Build human-readable reason string."""
        return (
            f"p6_lite derived {regime.value} from "
            f"delivery_mode={directive.delivery_mode.value}, "
            f"triggered_rule={directive.triggered_rule}"
        )

    def _build_debug(self, directive: PresentationDirective) -> Dict[str, Any]:
        """Build debug information."""
        return {
            "source": "p6_lite",
            "source_delivery_mode": directive.delivery_mode.value,
            "source_confidence": directive.confidence.value,
            "source_triggered_rule": directive.triggered_rule,
            "source_explanation": directive.explanation,
            "is_derived": True,
        }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================


def derive_regime(directive: PresentationDirective) -> RegimeEnvelope:
    """Convenience function to derive RegimeEnvelope from PresentationDirective.

    This is a shorthand for creating a P6LiteResolver and calling resolve().

    Args:
        directive: The PresentationDirective from Presentation Engine

    Returns:
        RegimeEnvelope suitable for P10 consumption

    Example:
        >>> from symbolu_core.presentation.p6_lite import derive_regime
        >>> envelope = derive_regime(directive)
        >>> print(envelope.regime)
        INFORM
    """
    resolver = P6LiteResolver()
    return resolver.resolve(directive)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Resolver class
    "P6LiteResolver",
    # Convenience function
    "derive_regime",
    # Mapping constants (for testing/inspection)
    "DELIVERY_MODE_TO_REGIME",
    "DELIVERY_MODE_TO_INTENT",
    "CONFIDENCE_TO_COHERENCE",
    "CONFIDENCE_TO_ELIGIBILITY",
    # Defaults
    "DEFAULT_REGIME",
    "DEFAULT_INTENT",
    "DEFAULT_COHERENCE",
    "DEFAULT_ELIGIBILITY",
]
