"""Tests for Acoustic Governance Chain.

Tests the complete P10 → P12 acoustic governance pipeline
integrated with the Presentation Layer via P6-Lite and P7-Lite bridges.

Test Categories:
1. Chain Initialization: Verify chain components are created
2. Execute Method: Test end-to-end execution
3. Result Structure: Verify AcousticChainResult fields
4. Audit Validation: Test P12 validation integration
5. Convenience Functions: Test helper functions
6. Edge Cases: Boundary conditions and error handling
"""

import pytest
from symbolu.presentation import (
    DeliveryMode,
    ConfidenceIndicator,
    PresentationDirective,
    SuggestedBehaviors,
    AcousticGovernanceChain,
    AcousticChainResult,
    run_acoustic_chain,
    is_acoustically_consistent,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import OperationalRegime
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import DiscourseAct
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import AcousticRegime


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def chain():
    """Create a fresh AcousticGovernanceChain instance."""
    return AcousticGovernanceChain()


@pytest.fixture
def confident_directive():
    """Create a CONFIDENT delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.CONFIDENT,
        confidence=ConfidenceIndicator.HIGH,
        triggered_rule="high_pramana",
        explanation="Strong valid cognition detected",
    )


@pytest.fixture
def silent_directive():
    """Create a SILENT delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.SILENT,
        confidence=ConfidenceIndicator.LOW,
        triggered_rule="critical_viparyaya",
        explanation="Critical misperception detected",
    )


@pytest.fixture
def hedged_directive():
    """Create a HEDGED delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.HEDGED,
        confidence=ConfidenceIndicator.MEDIUM,
        triggered_rule="moderate_uncertainty",
        explanation="Moderate uncertainty in assessment",
    )


@pytest.fixture
def clarifying_directive():
    """Create a CLARIFYING delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.CLARIFYING,
        confidence=ConfidenceIndicator.MEDIUM,
        triggered_rule="high_vikalpa",
        explanation="High conceptual confusion",
    )


@pytest.fixture
def acknowledging_directive():
    """Create an ACKNOWLEDGING delivery mode directive."""
    return PresentationDirective(
        delivery_mode=DeliveryMode.ACKNOWLEDGING,
        confidence=ConfidenceIndicator.MEDIUM,
        triggered_rule="low_confidence",
        explanation="Low confidence requires acknowledgment only",
    )


# =============================================================================
# Test Class 1: Chain Initialization
# =============================================================================


class TestChainInitialization:
    """Test AcousticGovernanceChain initialization."""

    def test_chain_created_successfully(self, chain):
        """Chain should be created without errors."""
        assert chain is not None
        assert isinstance(chain, AcousticGovernanceChain)

    def test_chain_has_resolvers(self, chain):
        """Chain should have all required resolvers."""
        assert chain._p6_resolver is not None
        assert chain._p7_resolver is not None
        assert chain._p10_resolver is not None
        assert chain._p12_validator is not None


# =============================================================================
# Test Class 2: Execute Method
# =============================================================================


class TestExecuteMethod:
    """Test chain.execute() method."""

    def test_execute_confident_directive(self, chain, confident_directive):
        """Execute should process CONFIDENT directive correctly."""
        result = chain.execute(confident_directive)

        assert isinstance(result, AcousticChainResult)
        assert result.directive == confident_directive
        assert result.regime_envelope.regime == OperationalRegime.INFORM
        assert result.discourse_envelope.act == DiscourseAct.EXPLANATION

    def test_execute_silent_directive(self, chain, silent_directive):
        """Execute should process SILENT directive correctly."""
        result = chain.execute(silent_directive)

        assert result.directive == silent_directive
        assert result.regime_envelope.regime == OperationalRegime.HOLD
        assert result.discourse_envelope.act == DiscourseAct.DEFERRAL

    def test_execute_hedged_directive(self, chain, hedged_directive):
        """Execute should process HEDGED directive correctly."""
        result = chain.execute(hedged_directive)

        assert result.regime_envelope.regime == OperationalRegime.DE_ESCALATE
        assert result.discourse_envelope.act == DiscourseAct.REFLECTION

    def test_execute_clarifying_directive(self, chain, clarifying_directive):
        """Execute should process CLARIFYING directive correctly."""
        result = chain.execute(clarifying_directive)

        assert result.regime_envelope.regime == OperationalRegime.CLARIFY
        assert result.discourse_envelope.act == DiscourseAct.QUESTION

    def test_execute_acknowledging_directive(self, chain, acknowledging_directive):
        """Execute should process ACKNOWLEDGING directive correctly."""
        result = chain.execute(acknowledging_directive)

        assert result.regime_envelope.regime == OperationalRegime.STABILIZE
        assert result.discourse_envelope.act == DiscourseAct.ACKNOWLEDGMENT

    def test_execute_raises_on_none(self, chain):
        """Execute should raise ValueError on None directive."""
        with pytest.raises(ValueError, match="directive cannot be None"):
            chain.execute(None)


# =============================================================================
# Test Class 3: Result Structure
# =============================================================================


class TestResultStructure:
    """Test AcousticChainResult structure."""

    def test_result_has_all_fields(self, chain, confident_directive):
        """Result should have all expected fields."""
        result = chain.execute(confident_directive)

        # Input
        assert result.directive is not None

        # Intermediate outputs
        assert result.regime_envelope is not None
        assert result.discourse_envelope is not None
        assert result.acoustic_frame is not None

        # Audit report
        assert result.audit_report is not None

        # Convenience flags
        assert isinstance(result.is_consistent, bool)
        assert isinstance(result.has_critical_violation, bool)
        assert isinstance(result.has_major_violation, bool)

        # Debug
        assert result.debug is not None

    def test_result_debug_info(self, chain, confident_directive):
        """Result debug info should contain source information."""
        result = chain.execute(confident_directive)

        assert result.debug["source"] == "acoustic_chain"
        assert result.debug["delivery_mode"] == "confident"
        assert result.debug["regime"] == "INFORM"
        assert result.debug["discourse_act"] == "EXPLANATION"

    def test_result_is_frozen(self, chain, confident_directive):
        """Result should be immutable (frozen dataclass)."""
        result = chain.execute(confident_directive)

        with pytest.raises(Exception):  # FrozenInstanceError
            result.is_consistent = False

    def test_violation_count_property(self, chain, confident_directive):
        """violation_count property should work correctly."""
        result = chain.execute(confident_directive)

        assert result.violation_count >= 0
        assert result.violation_count == len(result.audit_report.violations)

    def test_warning_count_property(self, chain, confident_directive):
        """warning_count property should work correctly."""
        result = chain.execute(confident_directive)

        assert result.warning_count >= 0
        assert result.warning_count == len(result.audit_report.warnings)


# =============================================================================
# Test Class 4: Acoustic Parameter Mapping
# =============================================================================


class TestAcousticParameterMapping:
    """Test that regimes map to correct acoustic parameters."""

    def test_hold_produces_flat_acoustic(self, chain, silent_directive):
        """HOLD regime should produce FLAT acoustic regime."""
        result = chain.execute(silent_directive)

        assert result.acoustic_frame.regime == AcousticRegime.FLAT

    def test_inform_produces_neutral_acoustic(self, chain, confident_directive):
        """INFORM regime should produce NEUTRAL acoustic regime."""
        result = chain.execute(confident_directive)

        assert result.acoustic_frame.regime == AcousticRegime.NEUTRAL

    def test_de_escalate_produces_soft_acoustic(self, chain, hedged_directive):
        """DE_ESCALATE regime should produce SOFT acoustic regime."""
        result = chain.execute(hedged_directive)

        assert result.acoustic_frame.regime == AcousticRegime.SOFT

    def test_clarify_produces_neutral_acoustic(self, chain, clarifying_directive):
        """CLARIFY regime should produce NEUTRAL acoustic regime."""
        result = chain.execute(clarifying_directive)

        assert result.acoustic_frame.regime == AcousticRegime.NEUTRAL

    def test_stabilize_produces_soft_acoustic(self, chain, acknowledging_directive):
        """STABILIZE regime should produce SOFT acoustic regime."""
        result = chain.execute(acknowledging_directive)

        assert result.acoustic_frame.regime == AcousticRegime.SOFT


# =============================================================================
# Test Class 5: Suppression Behavior
# =============================================================================


class TestSuppressionBehavior:
    """Test that suppressions are correctly applied."""

    def test_hold_applies_all_suppressions(self, chain, silent_directive):
        """HOLD regime should apply all suppressions."""
        result = chain.execute(silent_directive)

        assert result.acoustic_frame.suppress_emotion is True
        assert result.acoustic_frame.suppress_emphasis is True
        assert result.acoustic_frame.suppress_certainty is True

    def test_de_escalate_applies_all_suppressions(self, chain, hedged_directive):
        """DE_ESCALATE regime should apply all suppressions."""
        result = chain.execute(hedged_directive)

        assert result.acoustic_frame.suppress_emotion is True
        assert result.acoustic_frame.suppress_emphasis is True
        assert result.acoustic_frame.suppress_certainty is True

    def test_inform_suppresses_emotion_only(self, chain, confident_directive):
        """INFORM regime should suppress emotion but allow emphasis/certainty."""
        result = chain.execute(confident_directive)

        assert result.acoustic_frame.suppress_emotion is True
        assert result.acoustic_frame.suppress_emphasis is False
        assert result.acoustic_frame.suppress_certainty is False


# =============================================================================
# Test Class 6: P12 Audit Integration
# =============================================================================


class TestP12AuditIntegration:
    """Test P12 consistency validation integration."""

    def test_audit_report_present(self, chain, confident_directive):
        """Audit report should always be present."""
        result = chain.execute(confident_directive)

        assert result.audit_report is not None
        assert hasattr(result.audit_report, "is_consistent")
        assert hasattr(result.audit_report, "violations")
        assert hasattr(result.audit_report, "warnings")

    def test_well_formed_directive_is_consistent(self, chain, confident_directive):
        """Well-formed directive should produce consistent output."""
        result = chain.execute(confident_directive)

        # CONFIDENT → INFORM → NEUTRAL should be consistent
        assert result.is_consistent is True
        assert result.has_critical_violation is False

    def test_audit_checks_invariants(self, chain, confident_directive):
        """Audit should check invariants."""
        result = chain.execute(confident_directive)

        # Check that invariants were verified
        assert len(result.audit_report.checked_invariants) > 0

    def test_should_block_property(self, chain, confident_directive):
        """should_block should reflect critical violations."""
        result = chain.execute(confident_directive)

        # No critical violations for well-formed input
        assert result.should_block is False


# =============================================================================
# Test Class 7: Convenience Functions
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_run_acoustic_chain(self, confident_directive):
        """run_acoustic_chain should work like chain.execute()."""
        result = run_acoustic_chain(confident_directive)

        assert isinstance(result, AcousticChainResult)
        assert result.regime_envelope.regime == OperationalRegime.INFORM

    def test_is_acoustically_consistent(self, confident_directive):
        """is_acoustically_consistent should return boolean."""
        is_consistent = is_acoustically_consistent(confident_directive)

        assert isinstance(is_consistent, bool)
        assert is_consistent is True


# =============================================================================
# Test Class 8: All Delivery Modes
# =============================================================================


class TestAllDeliveryModes:
    """Test all delivery modes produce valid output."""

    @pytest.mark.parametrize("mode", list(DeliveryMode))
    def test_all_modes_produce_valid_result(self, chain, mode):
        """All delivery modes should produce valid AcousticChainResult."""
        directive = PresentationDirective(
            delivery_mode=mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{mode.value}",
        )

        result = chain.execute(directive)

        assert isinstance(result, AcousticChainResult)
        assert result.acoustic_frame is not None
        assert result.audit_report is not None

    @pytest.mark.parametrize("mode", list(DeliveryMode))
    def test_all_modes_produce_consistent_output(self, chain, mode):
        """All delivery modes should produce consistent (no violations) output."""
        directive = PresentationDirective(
            delivery_mode=mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{mode.value}",
        )

        result = chain.execute(directive)

        # All well-formed directives should be consistent
        assert result.is_consistent is True
        assert result.has_critical_violation is False


# =============================================================================
# Test Class 9: Determinism
# =============================================================================


class TestDeterminism:
    """Test that chain is deterministic."""

    def test_same_input_same_output(self, chain, confident_directive):
        """Same input should produce identical output."""
        result1 = chain.execute(confident_directive)
        result2 = chain.execute(confident_directive)

        assert result1.regime_envelope.regime == result2.regime_envelope.regime
        assert result1.discourse_envelope.act == result2.discourse_envelope.act
        assert result1.acoustic_frame.regime == result2.acoustic_frame.regime
        assert result1.acoustic_frame.speech_rate == result2.acoustic_frame.speech_rate
        assert result1.is_consistent == result2.is_consistent

    def test_different_chains_same_result(self, confident_directive):
        """Different chain instances should produce same result."""
        chain1 = AcousticGovernanceChain()
        chain2 = AcousticGovernanceChain()

        result1 = chain1.execute(confident_directive)
        result2 = chain2.execute(confident_directive)

        assert result1.acoustic_frame.regime == result2.acoustic_frame.regime
        assert result1.is_consistent == result2.is_consistent


# =============================================================================
# Test Class 10: Behavior Overrides
# =============================================================================


class TestBehaviorOverrides:
    """Test that behavior flags affect acoustic output."""

    def test_escalate_to_human_produces_deferral(self, chain):
        """escalate_to_human should force DEFERRAL discourse act."""
        behaviors = SuggestedBehaviors(escalate_to_human=True)
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=behaviors,
            triggered_rule="high_pramana",
        )

        result = chain.execute(directive)

        # escalate_to_human overrides to DEFERRAL
        assert result.discourse_envelope.act == DiscourseAct.DEFERRAL
        assert result.discourse_envelope.allowed is False

    def test_offer_clarification_produces_question(self, chain):
        """offer_clarification should force QUESTION discourse act."""
        behaviors = SuggestedBehaviors(offer_clarification=True)
        directive = PresentationDirective(
            delivery_mode=DeliveryMode.CONFIDENT,
            confidence=ConfidenceIndicator.HIGH,
            behaviors=behaviors,
            triggered_rule="high_pramana",
        )

        result = chain.execute(directive)

        # offer_clarification overrides to QUESTION
        assert result.discourse_envelope.act == DiscourseAct.QUESTION


# =============================================================================
# Test Class 11: Traceability
# =============================================================================


class TestTraceability:
    """Test that outputs are traceable to inputs."""

    def test_source_tracing_in_acoustic_frame(self, chain, confident_directive):
        """Acoustic frame should include source tracing."""
        result = chain.execute(confident_directive)

        assert result.acoustic_frame.source_regime == "INFORM"
        assert result.acoustic_frame.source_discourse_act == "EXPLANATION"
        assert result.acoustic_frame.architectural_phase == "P10"

    def test_audit_report_includes_sources(self, chain, confident_directive):
        """Audit report should include source information."""
        result = chain.execute(confident_directive)

        assert result.audit_report.source_regime is not None
        assert result.audit_report.source_discourse_act is not None

    def test_debug_info_is_complete(self, chain, confident_directive):
        """Debug info should have all tracing fields."""
        result = chain.execute(confident_directive)

        required_fields = [
            "source",
            "delivery_mode",
            "confidence",
            "triggered_rule",
            "regime",
            "discourse_act",
            "acoustic_regime",
            "violation_count",
            "warning_count",
        ]

        for field in required_fields:
            assert field in result.debug, f"Missing debug field: {field}"
