"""Tests for P7-Lite discourse act derivation from Presentation Layer.

Tests the p7_lite module which bridges Presentation Layer outputs
to P10 Acoustic Parameterization inputs (DiscourseEnvelope).
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
    SuggestedBehaviors,
)
from symbolu.presentation.p7_lite import (
    P7LiteResolver,
    derive_discourse_act,
    DELIVERY_MODE_TO_DISCOURSE_ACT,
    DELIVERY_MODE_TO_REGIME,
    DEFAULT_DISCOURSE_ACT,
    DEFAULT_REGIME,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import OperationalRegime
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)


class TestDeliveryModeToDiscourseActMapping:
    """Verify DeliveryMode → DiscourseAct mappings."""

    def test_silent_maps_to_deferral(self):
        """SILENT delivery mode should map to DEFERRAL."""
        assert DELIVERY_MODE_TO_DISCOURSE_ACT[DeliveryMode.SILENT] == DiscourseAct.DEFERRAL

    def test_acknowledging_maps_to_acknowledgment(self):
        """ACKNOWLEDGING delivery mode should map to ACKNOWLEDGMENT."""
        assert DELIVERY_MODE_TO_DISCOURSE_ACT[DeliveryMode.ACKNOWLEDGING] == DiscourseAct.ACKNOWLEDGMENT

    def test_clarifying_maps_to_question(self):
        """CLARIFYING delivery mode should map to QUESTION."""
        assert DELIVERY_MODE_TO_DISCOURSE_ACT[DeliveryMode.CLARIFYING] == DiscourseAct.QUESTION

    def test_hedged_maps_to_reflection(self):
        """HEDGED delivery mode should map to REFLECTION."""
        assert DELIVERY_MODE_TO_DISCOURSE_ACT[DeliveryMode.HEDGED] == DiscourseAct.REFLECTION

    def test_confident_maps_to_explanation(self):
        """CONFIDENT delivery mode should map to EXPLANATION."""
        assert DELIVERY_MODE_TO_DISCOURSE_ACT[DeliveryMode.CONFIDENT] == DiscourseAct.EXPLANATION

    def test_all_delivery_modes_mapped(self):
        """All DeliveryMode values should have a discourse act mapping."""
        for mode in DeliveryMode:
            assert mode in DELIVERY_MODE_TO_DISCOURSE_ACT, f"Missing mapping for {mode}"


class TestP7LiteResolver:
    """Test P7LiteResolver functionality."""

    def test_resolver_creation(self):
        """Resolver should be created successfully."""
        resolver = P7LiteResolver()
        assert resolver is not None

    def test_resolve_confident_directive(self):
        """CONFIDENT directive should produce EXPLANATION act."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert isinstance(envelope, DiscourseEnvelope)
        assert envelope.act == DiscourseAct.EXPLANATION
        assert envelope.allowed is True
        assert envelope.regime == OperationalRegime.INFORM

    def test_resolve_silent_directive(self):
        """SILENT directive should produce DEFERRAL act."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.SILENT,
            confidence=ConfidenceIndicator.LOW,
            triggered_rule="critical_viparyaya",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.DEFERRAL
        assert envelope.allowed is False
        assert envelope.regime == OperationalRegime.HOLD

    def test_resolve_clarifying_directive(self):
        """CLARIFYING directive should produce QUESTION act."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CLARIFYING,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="high_vikalpa",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.QUESTION
        assert envelope.allowed is True
        assert envelope.regime == OperationalRegime.CLARIFY

    def test_resolve_hedged_directive(self):
        """HEDGED directive should produce REFLECTION act."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="moderate_uncertainty",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.REFLECTION
        assert envelope.allowed is True
        assert envelope.regime == OperationalRegime.DE_ESCALATE

    def test_resolve_acknowledging_directive(self):
        """ACKNOWLEDGING directive should produce ACKNOWLEDGMENT act."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule="low_confidence",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.ACKNOWLEDGMENT
        assert envelope.allowed is True
        assert envelope.regime == OperationalRegime.STABILIZE


class TestBehaviorOverrides:
    """Test that behaviors can override discourse act."""

    def test_escalate_to_human_forces_deferral(self):
        """escalate_to_human should force DEFERRAL."""
        resolver = P7LiteResolver()
        behaviors = SuggestedBehaviors(escalate_to_human=True)
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=behaviors,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.DEFERRAL
        assert envelope.allowed is False

    def test_offer_clarification_forces_question(self):
        """offer_clarification should force QUESTION."""
        resolver = P7LiteResolver()
        behaviors = SuggestedBehaviors(offer_clarification=True)
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=behaviors,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.QUESTION

    def test_request_repeat_forces_question(self):
        """request_repeat should force QUESTION."""
        resolver = P7LiteResolver()
        behaviors = SuggestedBehaviors(request_repeat=True)
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
            behaviors=behaviors,
            triggered_rule="moderate_uncertainty",
        )

        envelope = resolver.resolve(directive)

        assert envelope.act == DiscourseAct.QUESTION

    def test_escalate_takes_priority_over_clarification(self):
        """escalate_to_human should take priority over offer_clarification."""
        resolver = P7LiteResolver()
        behaviors = SuggestedBehaviors(
            escalate_to_human=True,
            offer_clarification=True,
        )
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=behaviors,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        # Escalation (DEFERRAL) takes priority
        assert envelope.act == DiscourseAct.DEFERRAL


class TestEnvelopeContents:
    """Test envelope contains expected information."""

    def test_reason_includes_source_info(self):
        """Reason should include source delivery mode and rule."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert "EXPLANATION" in envelope.reason
        assert "confident" in envelope.reason
        assert "high_pramana" in envelope.reason

    def test_supporting_evidence_includes_behaviors(self):
        """Supporting evidence should include behavior flags."""
        resolver = P7LiteResolver()
        behaviors = SuggestedBehaviors(offer_clarification=True)
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=behaviors,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert envelope.supporting_evidence["behaviors"]["offer_clarification"] is True

    def test_debug_includes_source_info(self):
        """Debug info should include source directive details."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        assert envelope.debug["source"] == "p7_lite"
        assert envelope.debug["source_delivery_mode"] == "confident"
        assert envelope.debug["is_derived"] is True


class TestOverrides:
    """Test override functionality."""

    def test_override_act(self):
        """Override act should replace derived act."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive, override_act=DiscourseAct.INSTRUCTION)

        assert envelope.act == DiscourseAct.INSTRUCTION

    def test_override_regime(self):
        """Override regime should replace derived regime."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive, override_regime=OperationalRegime.HOLD)

        assert envelope.regime == OperationalRegime.HOLD


class TestDeriveDiscourseActConvenience:
    """Test derive_discourse_act convenience function."""

    def test_derive_discourse_act_confident(self):
        """Convenience function should work for CONFIDENT directive."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = derive_discourse_act(directive)

        assert envelope.act == DiscourseAct.EXPLANATION

    def test_derive_discourse_act_silent(self):
        """Convenience function should work for SILENT directive."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.SILENT,
            confidence=ConfidenceIndicator.LOW,
            triggered_rule="critical_viparyaya",
        )

        envelope = derive_discourse_act(directive)

        assert envelope.act == DiscourseAct.DEFERRAL


class TestDefaultValues:
    """Test default values are set correctly."""

    def test_default_discourse_act_is_deferral(self):
        """Default discourse act should be DEFERRAL (most conservative)."""
        assert DEFAULT_DISCOURSE_ACT == DiscourseAct.DEFERRAL

    def test_default_regime_is_hold(self):
        """Default regime should be HOLD."""
        assert DEFAULT_REGIME == OperationalRegime.HOLD


class TestEnvelopeInvariants:
    """Test that produced envelopes satisfy DiscourseEnvelope invariants."""

    @pytest.mark.parametrize("mode", list(DeliveryMode))
    def test_all_modes_produce_valid_envelope(self, mode):
        """All delivery modes should produce valid DiscourseEnvelope."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{mode.value}",
        )

        envelope = resolver.resolve(directive)

        assert isinstance(envelope, DiscourseEnvelope)
        assert isinstance(envelope.act, DiscourseAct)
        assert isinstance(envelope.regime, OperationalRegime)
        assert envelope.reason != ""

    @pytest.mark.parametrize("conf", list(ConfidenceIndicator))
    def test_all_confidence_levels_produce_valid_envelope(self, conf):
        """All confidence levels should produce valid DiscourseEnvelope."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=conf,
            triggered_rule=f"test_{conf.value}",
        )

        envelope = resolver.resolve(directive)

        assert isinstance(envelope, DiscourseEnvelope)


class TestIntegrationWithP10:
    """Integration tests with P10 Acoustic Resolver."""

    def test_envelope_compatible_with_p10(self):
        """Produced envelope should be consumable by P10."""
        resolver = P7LiteResolver()
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            triggered_rule="high_pramana",
        )

        envelope = resolver.resolve(directive)

        # Check envelope has all fields P10 expects
        assert hasattr(envelope, "act")
        assert hasattr(envelope, "allowed")
        assert hasattr(envelope, "reason")
        assert hasattr(envelope, "intent")
        assert hasattr(envelope, "regime")

        # Check act value is valid for P10 mapping
        assert envelope.act in [
            DiscourseAct.QUESTION,
            DiscourseAct.REFLECTION,
            DiscourseAct.ACKNOWLEDGMENT,
            DiscourseAct.EXPLANATION,
            DiscourseAct.INSTRUCTION,
            DiscourseAct.DEFERRAL,
        ]
