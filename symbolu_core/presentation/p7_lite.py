"""P7-Lite: Discourse Act Derivation from Presentation Layer.

This module provides a lightweight bridge from Presentation Layer outputs
to P10 Acoustic Parameterization inputs, complementing p6_lite.

P10 requires both:
1. RegimeEnvelope (from P6 or p6_lite)
2. DiscourseEnvelope (from P7 or p7_lite)

Design Rationale:
-----------------
Rather than implement full P7 (which requires PO1-P6 signals), p7_lite
derives a discourse act from the already-computed PresentationDirective.

Mapping Logic:
--------------
DeliveryMode → DiscourseAct:
    SILENT       → DEFERRAL      (cannot proceed)
    ACKNOWLEDGING → ACKNOWLEDGMENT (simple recognition)
    CLARIFYING   → QUESTION       (seeking information)
    HEDGED       → REFLECTION     (careful mirroring)
    CONFIDENT    → EXPLANATION    (providing information)

SuggestedBehaviors influence:
    offer_clarification=True → QUESTION (override to ask for clarity)
    request_repeat=True → QUESTION (override to request repeat)
    escalate_to_human=True → DEFERRAL (defer to human)

Authority Model:
---------------
- Reads PresentationDirective (downstream of CV engine)
- Produces DiscourseEnvelope for P10 consumption
- Does not override Presentation Layer decisions
- Conservative defaults (DEFERRAL) on any ambiguity

ARCHITECTURAL PRINCIPLE:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from symbolu_core.presentation.types import (
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
)
from symbolu_core.presentation.p6_lite import (
    P6LiteResolver,
    DELIVERY_MODE_TO_INTENT,
    DEFAULT_INTENT,
)
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import OperationalRegime
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)


# =============================================================================
# MAPPING CONSTANTS
# =============================================================================

# DeliveryMode → DiscourseAct
DELIVERY_MODE_TO_DISCOURSE_ACT: Dict[DeliveryMode, DiscourseAct] = {
    DeliveryMode.SILENT: DiscourseAct.DEFERRAL,
    DeliveryMode.ACKNOWLEDGING: DiscourseAct.ACKNOWLEDGMENT,
    DeliveryMode.CLARIFYING: DiscourseAct.QUESTION,
    DeliveryMode.HEDGED: DiscourseAct.REFLECTION,
    DeliveryMode.CONFIDENT: DiscourseAct.EXPLANATION,
}

# DeliveryMode → OperationalRegime (derived from p6_lite for consistency)
DELIVERY_MODE_TO_REGIME: Dict[DeliveryMode, OperationalRegime] = {
    DeliveryMode.SILENT: OperationalRegime.HOLD,
    DeliveryMode.ACKNOWLEDGING: OperationalRegime.STABILIZE,
    DeliveryMode.CLARIFYING: OperationalRegime.CLARIFY,
    DeliveryMode.HEDGED: OperationalRegime.DE_ESCALATE,
    DeliveryMode.CONFIDENT: OperationalRegime.INFORM,
}

# Safe defaults
DEFAULT_DISCOURSE_ACT = DiscourseAct.DEFERRAL
DEFAULT_REGIME = OperationalRegime.HOLD


# =============================================================================
# P7-LITE RESOLVER
# =============================================================================


class P7LiteResolver:
    """Lightweight discourse act resolver from Presentation Layer outputs.

    This resolver derives P7 DiscourseEnvelope from PresentationDirective,
    enabling the acoustic governance chain without full P7 implementation.

    Usage:
        from symbolu_core.presentation import PresentationEngine, CONSUMER_CONFIG
        from symbolu_core.presentation.p7_lite import P7LiteResolver

        # Compute presentation directive
        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)

        # Derive discourse envelope for P10
        p7_lite = P7LiteResolver()
        discourse_envelope = p7_lite.resolve(directive)

    Invariants:
    - Pure, deterministic resolution
    - Never modifies the input directive
    - Conservative defaults on missing data
    - Always produces a valid DiscourseEnvelope
    """

    def __init__(self) -> None:
        """Initialize the P7-Lite resolver."""
        pass  # Stateless resolver

    def resolve(
        self,
        directive: PresentationDirective,
        *,
        override_act: Optional[DiscourseAct] = None,
        override_intent: Optional[IntentType] = None,
        override_regime: Optional[OperationalRegime] = None,
    ) -> DiscourseEnvelope:
        """Derive DiscourseEnvelope from PresentationDirective.

        Args:
            directive: The PresentationDirective from Presentation Engine
            override_act: Optional explicit DiscourseAct
            override_intent: Optional explicit IntentType
            override_regime: Optional explicit OperationalRegime

        Returns:
            DiscourseEnvelope suitable for P10 consumption
        """
        # 1. Derive discourse act (with behavior overrides)
        act = override_act or self._derive_discourse_act(directive)

        # 2. Derive or use overridden intent
        intent = override_intent or self._derive_intent(directive.delivery_mode)

        # 3. Derive or use overridden regime
        regime = override_regime or self._derive_regime(directive.delivery_mode)

        # 4. Determine if allowed
        allowed = act != DiscourseAct.DEFERRAL

        # 5. Build reason string
        reason = self._build_reason(directive, act)

        # 6. Build supporting evidence
        evidence = self._build_evidence(directive)

        # 7. Build debug info
        debug = self._build_debug(directive)

        return DiscourseEnvelope(
            act=act,
            allowed=allowed,
            reason=reason,
            intent=intent,
            regime=regime,
            supporting_evidence=evidence,
            debug=debug,
        )

    def _derive_discourse_act(
        self,
        directive: PresentationDirective,
    ) -> DiscourseAct:
        """Derive DiscourseAct from directive with behavior overrides."""
        # Check behavior overrides first
        if directive.behaviors.escalate_to_human:
            return DiscourseAct.DEFERRAL

        if directive.behaviors.offer_clarification or directive.behaviors.request_repeat:
            return DiscourseAct.QUESTION

        # Base mapping from delivery mode
        return DELIVERY_MODE_TO_DISCOURSE_ACT.get(
            directive.delivery_mode,
            DEFAULT_DISCOURSE_ACT,
        )

    def _derive_intent(self, delivery_mode: DeliveryMode) -> IntentType:
        """Derive IntentType from DeliveryMode."""
        return DELIVERY_MODE_TO_INTENT.get(delivery_mode, DEFAULT_INTENT)

    def _derive_regime(self, delivery_mode: DeliveryMode) -> OperationalRegime:
        """Derive OperationalRegime from DeliveryMode."""
        return DELIVERY_MODE_TO_REGIME.get(delivery_mode, DEFAULT_REGIME)

    def _build_reason(
        self,
        directive: PresentationDirective,
        act: DiscourseAct,
    ) -> str:
        """Build human-readable reason string."""
        return (
            f"p7_lite derived {act.value} from "
            f"delivery_mode={directive.delivery_mode.value}, "
            f"triggered_rule={directive.triggered_rule}"
        )

    def _build_evidence(self, directive: PresentationDirective) -> Dict[str, Any]:
        """Build supporting evidence dict."""
        return {
            "source": "p7_lite",
            "delivery_mode": directive.delivery_mode.value,
            "confidence": directive.confidence.value,
            "behaviors": {
                "offer_clarification": directive.behaviors.offer_clarification,
                "request_repeat": directive.behaviors.request_repeat,
                "escalate_to_human": directive.behaviors.escalate_to_human,
            },
        }

    def _build_debug(self, directive: PresentationDirective) -> Dict[str, Any]:
        """Build debug information."""
        return {
            "source": "p7_lite",
            "source_delivery_mode": directive.delivery_mode.value,
            "source_confidence": directive.confidence.value,
            "source_triggered_rule": directive.triggered_rule,
            "is_derived": True,
        }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================


def derive_discourse_act(directive: PresentationDirective) -> DiscourseEnvelope:
    """Convenience function to derive DiscourseEnvelope from PresentationDirective.

    Args:
        directive: The PresentationDirective from Presentation Engine

    Returns:
        DiscourseEnvelope suitable for P10 consumption

    Example:
        >>> from symbolu_core.presentation.p7_lite import derive_discourse_act
        >>> envelope = derive_discourse_act(directive)
        >>> print(envelope.act)
        EXPLANATION
    """
    resolver = P7LiteResolver()
    return resolver.resolve(directive)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Resolver class
    "P7LiteResolver",
    # Convenience function
    "derive_discourse_act",
    # Mapping constants (for testing/inspection)
    "DELIVERY_MODE_TO_DISCOURSE_ACT",
    "DELIVERY_MODE_TO_REGIME",
    # Defaults
    "DEFAULT_DISCOURSE_ACT",
    "DEFAULT_REGIME",
]
