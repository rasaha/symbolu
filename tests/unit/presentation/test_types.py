"""Tests for presentation types.

Part 3: Presentation Directives
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    DiagnosticInfo,
    PresentationDirective,
)


class TestDeliveryMode:
    """Tests for DeliveryMode enum."""

    def test_all_modes_defined(self):
        """All 5 delivery modes should be defined."""
        assert DeliveryMode.CONFIDENT.value == "confident"
        assert DeliveryMode.HEDGED.value == "hedged"
        assert DeliveryMode.CLARIFYING.value == "clarifying"
        assert DeliveryMode.ACKNOWLEDGING.value == "acknowledging"
        assert DeliveryMode.SILENT.value == "silent"

    def test_mode_count(self):
        """Exactly 5 modes should exist."""
        assert len(DeliveryMode) == 5


class TestConfidenceIndicator:
    """Tests for ConfidenceIndicator enum."""

    def test_all_indicators_defined(self):
        """All 4 confidence indicators should be defined."""
        assert ConfidenceIndicator.HIGH.value == "high"
        assert ConfidenceIndicator.MEDIUM.value == "medium"
        assert ConfidenceIndicator.LOW.value == "low"
        assert ConfidenceIndicator.UNKNOWN.value == "unknown"

    def test_indicator_count(self):
        """Exactly 4 indicators should exist."""
        assert len(ConfidenceIndicator) == 4


class TestSuggestedBehaviors:
    """Tests for SuggestedBehaviors dataclass."""

    def test_default_all_false(self):
        """Default behaviors should all be False."""
        behaviors = SuggestedBehaviors()
        assert behaviors.show_alternatives is False
        assert behaviors.request_repeat is False
        assert behaviors.offer_clarification is False
        assert behaviors.show_reasoning is False
        assert behaviors.delay_response is False
        assert behaviors.escalate_to_human is False

    def test_custom_behaviors(self):
        """Custom behaviors should be set correctly."""
        behaviors = SuggestedBehaviors(
            show_alternatives=True,
            escalate_to_human=True,
        )
        assert behaviors.show_alternatives is True
        assert behaviors.escalate_to_human is True
        assert behaviors.request_repeat is False


class TestDiagnosticInfo:
    """Tests for DiagnosticInfo dataclass."""

    def test_minimal_diagnostic(self):
        """Minimal diagnostic should work."""
        diag = DiagnosticInfo(
            dominant_vritti="pramana",
            primary_fracture=None,
        )
        assert diag.dominant_vritti == "pramana"
        assert diag.primary_fracture is None
        assert diag.active_penalties == []
        assert diag.signal_summary == ""

    def test_full_diagnostic(self):
        """Full diagnostic should capture all fields."""
        diag = DiagnosticInfo(
            dominant_vritti="viparyaya",
            primary_fracture=("semantic", "structural"),
            active_penalties=["viparyaya_penalty"],
            signal_summary="score=0.45 coherence=0.30",
        )
        assert diag.dominant_vritti == "viparyaya"
        assert diag.primary_fracture == ("semantic", "structural")
        assert "viparyaya_penalty" in diag.active_penalties


class TestPresentationDirective:
    """Tests for PresentationDirective dataclass."""

    def test_frozen_directive(self):
        """Directive should be immutable."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            directive.delivery_mode = DeliveryMode.HEDGED

    def test_directive_defaults(self):
        """Directive should have sensible defaults."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
        )
        assert directive.diagnostic is None
        assert directive.explanation == ""
        assert directive.triggered_rule == ""

    def test_with_behaviors(self):
        """with_behaviors should create modified copy."""
        original = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=SuggestedBehaviors(),
        )
        modified = original.with_behaviors(show_alternatives=True)

        assert original.behaviors.show_alternatives is False
        assert modified.behaviors.show_alternatives is True
        assert modified.delivery_mode == DeliveryMode.CONFIDENT

    def test_with_diagnostic(self):
        """with_diagnostic should attach diagnostic info."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.HEDGED,
            confidence=ConfidenceIndicator.MEDIUM,
        )
        diag = DiagnosticInfo(
            dominant_vritti="pramana",
            primary_fracture=None,
        )
        with_diag = directive.with_diagnostic(diag)

        assert directive.diagnostic is None
        assert with_diag.diagnostic is not None
        assert with_diag.diagnostic.dominant_vritti == "pramana"

    def test_complete_directive(self):
        """Complete directive with all fields should work."""
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.ACKNOWLEDGING,
            confidence=ConfidenceIndicator.LOW,
            behaviors=SuggestedBehaviors(
                show_alternatives=True,
                escalate_to_human=True,
            ),
            diagnostic=DiagnosticInfo(
                dominant_vritti="viparyaya",
                primary_fracture=("semantic", "phonemic"),
                active_penalties=["viparyaya_penalty"],
                signal_summary="test",
            ),
            explanation="Potential misinterpretation",
            triggered_rule="critical_viparyaya",
        )

        assert directive.delivery_mode == DeliveryMode.ACKNOWLEDGING
        assert directive.confidence == ConfidenceIndicator.LOW
        assert directive.behaviors.show_alternatives is True
        assert directive.diagnostic.dominant_vritti == "viparyaya"
        assert directive.triggered_rule == "critical_viparyaya"
