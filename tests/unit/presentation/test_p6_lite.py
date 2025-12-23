"""Tests for P6-Lite regime derivation from Presentation Layer.

Tests the p6_lite module which bridges Presentation Layer outputs
to P10 Acoustic Parameterization inputs.

Test Structure:
- TestDeliveryModeToRegimeMapping: Verify all DeliveryMode → Regime mappings
- TestConfidenceToCoherenceMapping: Verify confidence → coherence mappings
- TestConfidenceToEligibilityMapping: Verify confidence → eligibility mappings
- TestP6LiteResolver: Test resolver functionality
- TestDeriveRegimeConvenience: Test convenience function
- TestIntegrationWithP10: End-to-end integration tests
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
    SuggestedBehaviors,
)
from symbolu.presentation.p6_lite import (
    P6LiteResolver,
    derive_regime,
    DELIVERY_MODE_TO_REGIME,
    DELIVERY_MODE_TO_INTENT,
    CONFIDENCE_TO_COHERENCE,
    CONFIDENCE_TO_ELIGIBILITY,
    DEFAULT_REGIME,
    DEFAULT_INTENT,
    DEFAULT_COHERENCE,
    DEFAULT_ELIGIBILITY,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility


class TestDeliveryModeToRegimeMapping:
    """Verify DeliveryMode → OperationalRegime mappings."""

    def test_silent_maps_to_hold(self):
        """SILENT delivery mode should map to HOLD regime."""
        assert DELIVERY_MODE_TO_REGIME[DeliveryMode.SILENT] == OperationalRegime.HOLD

    def test_acknowledging_maps_to_stabilize(self):
        """ACKNOWLEDGING delivery mode should map to STABILIZE regime."""
        assert DELIVERY_MODE_TO_REGIME[DeliveryMode.ACKNOWLEDGING] == OperationalRegime.STABILIZE

    def test_clarifying_maps_to_clarify(self):
        """CLARIFYING delivery mode should map to CLARIFY regime."""
        assert DELIVERY_MODE_TO_REGIME[DeliveryMode.CLARIFYING] == OperationalRegime.CLARIFY

    def test_hedged_maps_to_de_escalate(self):
        """HEDGED delivery mode should map to DE_ESCALATE regime."""
        assert DELIVERY_MODE_TO_REGIME[DeliveryMode.HEDGED] == OperationalRegime.DE_ESCALATE

    def test_confident_maps_to_inform(self):
        """CONFIDENT delivery mode should map to INFORM regime."""
        assert DELIVERY_MODE_TO_REGIME[DeliveryMode.CONFIDENT] == OperationalRegime.INFORM

    def test_all_delivery_modes_mapped(self):
        """All DeliveryMode values should have a mapping."""
        for mode in DeliveryMode:
            assert mode in DELIVERY_MODE_TO_REGIME, f"Missing mapping for {mode}"


class TestDeliveryModeToIntentMapping:
    """Verify DeliveryMode → IntentType mappings."""

    def test_silent_maps_to_abstain(self):
        """SILENT delivery mode should map to ABSTAIN intent."""
        assert DELIVERY_MODE_TO_INTENT[DeliveryMode.SILENT] == IntentType.ABSTAIN

    def test_acknowledging_maps_to_support(self):
        """ACKNOWLEDGING delivery mode should map to SUPPORT intent."""
        assert DELIVERY_MODE_TO_INTENT[DeliveryMode.ACKNOWLEDGING] == IntentType.SUPPORT

    def test_clarifying_maps_to_clarify(self):
        """CLARIFYING delivery mode should map to CLARIFY intent."""
        assert DELIVERY_MODE_TO_INTENT[DeliveryMode.CLARIFYING] == IntentType.CLARIFY

    def test_hedged_maps_to_support(self):
        """HEDGED delivery mode should map to SUPPORT intent."""
        assert DELIVERY_MODE_TO_INTENT[DeliveryMode.HEDGED] == IntentType.SUPPORT

    def test_confident_maps_to_inform(self):
        """CONFIDENT delivery mode should map to INFORM intent."""
        assert DELIVERY_MODE_TO_INTENT[DeliveryMode.CONFIDENT] == IntentType.INFORM

    def test_all_delivery_modes_mapped(self):
        """All DeliveryMode values should have an intent mapping."""
        for mode in DeliveryMode:
            assert mode in DELIVERY_MODE_TO_INTENT, f"Missing intent mapping for {mode}"


class TestConfidenceToCoherenceMapping:
    """Verify ConfidenceIndicator → coherence_regime mappings."""

    def test_high_maps_to_coherent(self):
        """HIGH confidence should map to COHERENT."""
        assert CONFIDENCE_TO_COHERENCE[ConfidenceIndicator.HIGH] == "COHERENT"

    def test_medium_maps_to_unstable(self):
        """MEDIUM confidence should map to UNSTABLE."""
        assert CONFIDENCE_TO_COHERENCE[ConfidenceIndicator.MEDIUM] == "UNSTABLE"

    def test_low_maps_to_degraded(self):
        """LOW confidence should map to DEGRADED."""
        assert CONFIDENCE_TO_COHERENCE[ConfidenceIndicator.LOW] == "DEGRADED"

    def test_unknown_maps_to_unknown(self):
        """UNKNOWN confidence should map to UNKNOWN."""
        assert CONFIDENCE_TO_COHERENCE[ConfidenceIndicator.UNKNOWN] == "UNKNOWN"

    def test_all_confidence_levels_mapped(self):
        """All ConfidenceIndicator values should have a coherence mapping."""
        for conf in ConfidenceIndicator:
            assert conf in CONFIDENCE_TO_COHERENCE, f"Missing coherence mapping for {conf}"


class TestConfidenceToEligibilityMapping:
    """Verify ConfidenceIndicator → ExecutionEligibility mappings."""

    def test_high_maps_to_eligible(self):
        """HIGH confidence should map to ELIGIBLE."""
        assert CONFIDENCE_TO_ELIGIBILITY[ConfidenceIndicator.HIGH] == ExecutionEligibility.ELIGIBLE

    def test_medium_maps_to_deferred(self):
        """MEDIUM confidence should map to DEFERRED."""
        assert CONFIDENCE_TO_ELIGIBILITY[ConfidenceIndicator.MEDIUM] == ExecutionEligibility.DEFERRED

    def test_low_maps_to_prohibited(self):
        """LOW confidence should map to PROHIBITED."""
        assert CONFIDENCE_TO_ELIGIBILITY[ConfidenceIndicator.LOW] == ExecutionEligibility.PROHIBITED

    def test_unknown_maps_to_deferred(self):
        """UNKNOWN confidence should map to DEFERRED."""
        assert CONFIDENCE_TO_ELIGIBILITY[ConfidenceIndicator.UNKNOWN] == ExecutionEligibility.DEFERRED

    def test_all_confidence_levels_mapped(self):
        """All ConfidenceIndicator values should have an eligibility mapping."""
        for conf in ConfidenceIndicator:
            assert conf in CONFIDENCE_TO_ELIGIBILITY, f"Missing eligibility mapping for {conf}"


class TestP6LiteResolver:
    """Test P6LiteResolver functionality."""

    def test_resolver_creation(self):
        """Resolver should be created successfully."""
        resolver = P6LiteResolver()
        assert resolver is not None

    def test_resolve_confident_directive(self):
        """CONFIDENT directive should produce INFORM regime."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert isinstance(envelope, RegimeEnvelope)
        assert envelope.regime == OperationalRegime.INFORM
        assert envelope.intent == IntentType.INFORM
        assert envelope.execution_eligibility == ExecutionEligibility.ELIGIBLE
        assert envelope.coherence_regime == "COHERENT"

    def test_resolve_silent_directive(self):
        """SILENT directive should produce HOLD regime."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.SILENT,
            confidence=ConfidenceIndicator.LOW,
            triggered_rule="critical_viparyaya",
        )

        envelope = resolver.resolve(directive)

        assert envelope.regime == OperationalRegime.HOLD
        assert envelope.intent == IntentType.ABSTAIN
        assert envelope.execution_eligibility == ExecutionEligibility.PROHIBITED
        assert envelope.coherence_regime == "DEGRADED"

    def test_resolve_clarifying_directive(self):
        """CLARIFYING directive should produce CLARIFY regime."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CLARIFYING,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="high_vikalpa",
        )

        envelope = resolver.resolve(directive)

        assert envelope.regime == OperationalRegime.CLARIFY
        assert envelope.intent == IntentType.CLARIFY
        assert envelope.coherence_regime == "UNSTABLE"

    def test_resolve_hedged_directive(self):
        """HEDGED directive should produce DE_ESCALATE regime."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="moderate_uncertainty",
        )

        envelope = resolver.resolve(directive)

        assert envelope.regime == OperationalRegime.DE_ESCALATE
        assert envelope.intent == IntentType.SUPPORT

    def test_resolve_acknowledging_directive(self):
        """ACKNOWLEDGING directive should produce STABILIZE regime."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="low_confidence",
        )

        envelope = resolver.resolve(directive)

        assert envelope.regime == OperationalRegime.STABILIZE
        assert envelope.intent == IntentType.SUPPORT

    def test_reason_includes_source_info(self):
        """Reason should include source delivery mode and rule."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert "INFORM" in envelope.reason
        assert "confident" in envelope.reason
        assert "high_pramana" in envelope.reason

    def test_debug_includes_source_info(self):
        """Debug info should include source directive details."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
            explanation="Strong valid cognition",
        )

        envelope = resolver.resolve(directive)

        assert envelope.debug["source"] == "p6_lite"
        assert envelope.debug["source_delivery_mode"] == "confident"
        assert envelope.debug["source_confidence"] == "high"
        assert envelope.debug["source_triggered_rule"] == "high_pramana"
        assert envelope.debug["is_derived"] is True

    def test_override_intent(self):
        """Override intent should replace derived intent."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        # Override intent to REFLECT instead of derived INFORM
        envelope = resolver.resolve(directive, override_intent=IntentType.REFLECT)

        assert envelope.intent == IntentType.REFLECT
        # Regime still derived from delivery mode
        assert envelope.regime == OperationalRegime.INFORM

    def test_override_eligibility(self):
        """Override eligibility should replace derived eligibility."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        # Override eligibility to PROHIBITED
        envelope = resolver.resolve(
            directive,
            override_eligibility=ExecutionEligibility.PROHIBITED,
        )

        assert envelope.execution_eligibility == ExecutionEligibility.PROHIBITED

    def test_override_coherence(self):
        """Override coherence should replace derived coherence."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive, override_coherence="FORCED_COHERENT")

        assert envelope.coherence_regime == "FORCED_COHERENT"


class TestDeriveRegimeConvenience:
    """Test derive_regime convenience function."""

    def test_derive_regime_confident(self):
        """Convenience function should work for CONFIDENT directive."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = derive_regime(directive)

        assert envelope.regime == OperationalRegime.INFORM

    def test_derive_regime_silent(self):
        """Convenience function should work for SILENT directive."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.SILENT,
            confidence=ConfidenceIndicator.LOW,
            triggered_rule="critical_viparyaya",
        )

        envelope = derive_regime(directive)

        assert envelope.regime == OperationalRegime.HOLD

    def test_derive_regime_returns_valid_envelope(self):
        """Convenience function should return valid RegimeEnvelope."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CLARIFYING,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="high_vikalpa",
        )

        envelope = derive_regime(directive)

        assert isinstance(envelope, RegimeEnvelope)
        assert envelope.architectural_phase == "P6"


class TestDefaultValues:
    """Test default values are set correctly."""

    def test_default_regime_is_hold(self):
        """Default regime should be HOLD (most conservative)."""
        assert DEFAULT_REGIME == OperationalRegime.HOLD

    def test_default_intent_is_abstain(self):
        """Default intent should be ABSTAIN."""
        assert DEFAULT_INTENT == IntentType.ABSTAIN

    def test_default_coherence_is_unknown(self):
        """Default coherence should be UNKNOWN."""
        assert DEFAULT_COHERENCE == "UNKNOWN"

    def test_default_eligibility_is_deferred(self):
        """Default eligibility should be DEFERRED."""
        assert DEFAULT_ELIGIBILITY == ExecutionEligibility.DEFERRED


class TestEnvelopeInvariants:
    """Test that produced envelopes satisfy RegimeEnvelope invariants."""

    @pytest.mark.parametrize("mode", list(DeliveryMode))
    def test_all_modes_produce_valid_envelope(self, mode):
        """All delivery modes should produce valid RegimeEnvelope."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{mode.value}",
        )

        envelope = resolver.resolve(directive)

        # Envelope should be valid (no exceptions)
        assert isinstance(envelope, RegimeEnvelope)
        assert isinstance(envelope.regime, OperationalRegime)
        assert isinstance(envelope.intent, IntentType)
        assert isinstance(envelope.execution_eligibility, ExecutionEligibility)
        assert envelope.reason != ""
        assert envelope.coherence_regime != ""

    @pytest.mark.parametrize("conf", list(ConfidenceIndicator))
    def test_all_confidence_levels_produce_valid_envelope(self, conf):
        """All confidence levels should produce valid RegimeEnvelope."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=conf,
            triggered_rule=f"test_{conf.value}",
        )

        envelope = resolver.resolve(directive)

        assert isinstance(envelope, RegimeEnvelope)


class TestIntegrationWithP10:
    """Integration tests with P10 Acoustic Resolver."""

    def test_envelope_compatible_with_p10(self):
        """Produced envelope should be consumable by P10."""
        resolver = P6LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        # Check envelope has all fields P10 expects
        assert hasattr(envelope, "regime")
        assert hasattr(envelope, "reason")
        assert hasattr(envelope, "intent")
        assert hasattr(envelope, "execution_eligibility")
        assert hasattr(envelope, "coherence_regime")

        # Check regime value is valid for P10 mapping
        assert envelope.regime in [
            OperationalRegime.HOLD,
            OperationalRegime.DE_ESCALATE,
            OperationalRegime.STABILIZE,
            OperationalRegime.REFLECT,
            OperationalRegime.INFORM,
            OperationalRegime.CLARIFY,
        ]

    def test_full_pipeline_cv_to_p10_envelope(self):
        """Test full pipeline from directive to P10-compatible envelope."""
        # Simulate different presentation outputs
        test_cases = [
            (DeliveryMode.CONFIDENT, ConfidenceIndicator.HIGH, OperationalRegime.INFORM),
            (DeliveryMode.HEDGED, ConfidenceIndicator.MEDIUM, OperationalRegime.DE_ESCALATE),
            (DeliveryMode.CLARIFYING, ConfidenceIndicator.LOW, OperationalRegime.CLARIFY),
            (DeliveryMode.SILENT, ConfidenceIndicator.LOW, OperationalRegime.HOLD),
            (DeliveryMode.ACKNOWLEDGING, ConfidenceIndicator.MEDIUM, OperationalRegime.STABILIZE),
        ]

        resolver = P6LiteResolver()

        for mode, conf, expected_regime in test_cases:
            directive = PresentationDirective(
                delivery_mode=mode,
                confidence=conf,
                triggered_rule=f"test_{mode.value}",
            )

            envelope = resolver.resolve(directive)

            assert envelope.regime == expected_regime, (
                f"Expected {expected_regime} for {mode}, got {envelope.regime}"
            )
