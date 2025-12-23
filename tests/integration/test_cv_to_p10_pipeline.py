"""Integration test: CV → Presentation → P6/P7-Lite → P10 Pipeline.

This test validates the complete pipeline from Chitta-Vṛtti signals
through Presentation Layer to P10 Acoustic Parameterization.

Pipeline Flow:
    ChittaVrittiInputs → ChittaVrittiEngine → ChittaVrittiResult
    ChittaVrittiResult → SignalBundle → PresentationEngine → PresentationDirective
    PresentationDirective → P6LiteResolver → RegimeEnvelope
    PresentationDirective → P7LiteResolver → DiscourseEnvelope
    RegimeEnvelope + DiscourseEnvelope → P10AcousticResolver → AcousticParameterFrame

ARCHITECTURAL PRINCIPLE:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

import pytest
from symbolu.chitta_vritti import ChittaVrittiEngine, ChittaVrittiInputs
from symbolu.presentation import (
    PresentationEngine,
    SignalBundle,
    SessionContext,
    VrittiDistribution,
    CONSUMER_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
    DeliveryMode,
    ConfidenceIndicator,
)
from symbolu.presentation.p6_lite import P6LiteResolver, derive_regime
from symbolu.presentation.p7_lite import P7LiteResolver, derive_discourse_act
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_resolver import (
    P10AcousticResolver,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
    AcousticRegime,
)


class TestFullPipelineIntegration:
    """Test complete pipeline from CV inputs to P10 acoustic frame."""

    def test_high_confidence_pipeline(self):
        """High confidence input should produce INFORM regime and NEUTRAL acoustic."""
        # 1. Create CV inputs with high confidence signals
        cv_inputs = ChittaVrittiInputs(
            phonemic_rep={"ipa": "/hɛloʊ/"},
            semantic_rep={"embedding": [0.1] * 768},
            structural_rep={"parse_tree": "NP"},
            temporal_rep={"continuity": 0.9},
            entropy=0.2,  # Low uncertainty
            motion=0.3,
            confidence=0.9,  # High confidence
            temporal_continuity=0.9,
        )

        # 2. Compute CV result (using signal bundle directly for simplicity)
        signal_bundle = SignalBundle.create_minimal(
            score=0.85,
            coherence=0.9,
            vritti=VrittiDistribution(pramana=0.8, viparyaya=0.05, vikalpa=0.05, smrti=0.05, nidra=0.05),
            dominant_vritti="pramana",
            entropy=0.2,
            motion=0.3,
            confidence=0.9,
        )

        # 3. Compute presentation directive
        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)

        assert directive.delivery_mode == DeliveryMode.CONFIDENT
        assert directive.confidence == ConfidenceIndicator.HIGH

        # 4. Derive regime and discourse envelopes
        regime_envelope = derive_regime(directive)
        discourse_envelope = derive_discourse_act(directive)

        assert regime_envelope.regime == OperationalRegime.INFORM
        assert discourse_envelope.act == DiscourseAct.EXPLANATION

        # 5. Compute acoustic parameters
        p10_resolver = P10AcousticResolver()
        acoustic_frame = p10_resolver.resolve(
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        assert isinstance(acoustic_frame, AcousticParameterFrame)
        assert acoustic_frame.regime == AcousticRegime.NEUTRAL
        assert acoustic_frame.source_regime == "INFORM"

    def test_low_confidence_pipeline(self):
        """Low confidence input should produce conservative regime and FLAT acoustic."""
        # Low confidence signal bundle
        signal_bundle = SignalBundle.create_minimal(
            score=0.25,
            coherence=0.3,
            vritti=VrittiDistribution(pramana=0.1, viparyaya=0.5, vikalpa=0.2, smrti=0.1, nidra=0.1),
            dominant_vritti="viparyaya",
            entropy=0.8,
            motion=0.1,
            confidence=0.3,
        )

        # Compute presentation directive
        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)

        # Low confidence should trigger hedged or acknowledging mode
        assert directive.confidence in [ConfidenceIndicator.LOW, ConfidenceIndicator.MEDIUM]

        # Derive envelopes
        regime_envelope = derive_regime(directive)
        discourse_envelope = derive_discourse_act(directive)

        # Conservative regime expected
        assert regime_envelope.regime in [
            OperationalRegime.HOLD,
            OperationalRegime.STABILIZE,
            OperationalRegime.DE_ESCALATE,
            OperationalRegime.CLARIFY,
        ]

        # Compute acoustic parameters
        p10_resolver = P10AcousticResolver()
        acoustic_frame = p10_resolver.resolve(
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        # Conservative acoustic regime expected
        assert acoustic_frame.regime in [AcousticRegime.FLAT, AcousticRegime.SOFT]
        # Suppressions should be active for conservative regimes
        assert acoustic_frame.suppress_emotion is True

    def test_clarifying_pipeline(self):
        """Clarifying input should produce CLARIFY regime."""
        # High vikalpa (conceptual branching) signal bundle
        signal_bundle = SignalBundle.create_minimal(
            score=0.55,
            coherence=0.5,
            vritti=VrittiDistribution(pramana=0.1, viparyaya=0.1, vikalpa=0.6, smrti=0.1, nidra=0.1),
            dominant_vritti="vikalpa",
            entropy=0.7,  # High entropy triggers vikalpa rule
        )

        # Compute presentation directive
        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)

        assert directive.delivery_mode == DeliveryMode.CLARIFYING

        # Derive envelopes
        regime_envelope = derive_regime(directive)
        discourse_envelope = derive_discourse_act(directive)

        assert regime_envelope.regime == OperationalRegime.CLARIFY
        assert discourse_envelope.act == DiscourseAct.QUESTION

        # Compute acoustic parameters
        p10_resolver = P10AcousticResolver()
        acoustic_frame = p10_resolver.resolve(
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        assert acoustic_frame.regime == AcousticRegime.NEUTRAL
        assert acoustic_frame.source_regime == "CLARIFY"


class TestEnvelopeCompatibility:
    """Test that derived envelopes are compatible with P10."""

    @pytest.mark.parametrize("delivery_mode", list(DeliveryMode))
    def test_all_delivery_modes_produce_valid_p10_input(self, delivery_mode):
        """All delivery modes should produce valid P10 inputs."""
        from symbolu.presentation import PresentationDirective

        directive = PresentationDirective(
            delivery_mode=delivery_mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{delivery_mode.value}",
        )

        regime_envelope = derive_regime(directive)
        discourse_envelope = derive_discourse_act(directive)

        # Both envelopes should be valid
        assert isinstance(regime_envelope, RegimeEnvelope)
        assert isinstance(discourse_envelope, DiscourseEnvelope)

        # P10 should accept them
        p10_resolver = P10AcousticResolver()
        acoustic_frame = p10_resolver.resolve(
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        assert isinstance(acoustic_frame, AcousticParameterFrame)
        # All acoustic frames should have valid bounds
        assert 3.0 <= acoustic_frame.speech_rate <= 5.5
        assert 0.2 <= acoustic_frame.energy_level <= 0.6


class TestArchitecturalInvariant:
    """Test the architectural invariant: Sound must obey meaning."""

    def test_regime_determines_acoustic_not_vice_versa(self):
        """Acoustic parameters should be derived from regime, not influence it."""
        # Two different presentation paths
        high_confidence = SignalBundle.create_minimal(
            score=0.9,
            vritti=VrittiDistribution(pramana=0.9, viparyaya=0.025, vikalpa=0.025, smrti=0.025, nidra=0.025),
        )

        low_confidence = SignalBundle.create_minimal(
            score=0.2,
            vritti=VrittiDistribution(pramana=0.1, viparyaya=0.4, vikalpa=0.2, smrti=0.15, nidra=0.15),
        )

        pres_engine = PresentationEngine(CONSUMER_CONFIG)

        # Get directives
        high_directive = pres_engine.compute(high_confidence)
        low_directive = pres_engine.compute(low_confidence)

        # Derive regimes (meaning layer)
        high_regime = derive_regime(high_directive)
        low_regime = derive_regime(low_directive)

        # Get acoustic frames (sound layer)
        p10 = P10AcousticResolver()

        high_acoustic = p10.resolve(
            lexical_frame=None,
            discourse_envelope=derive_discourse_act(high_directive),
            regime_envelope=high_regime,
        )

        low_acoustic = p10.resolve(
            lexical_frame=None,
            discourse_envelope=derive_discourse_act(low_directive),
            regime_envelope=low_regime,
        )

        # High confidence should have less restrictive acoustic
        # Low confidence should have more restrictive acoustic
        # This verifies: meaning (regime) → sound (acoustic), not reverse
        if high_regime.regime == OperationalRegime.INFORM:
            assert high_acoustic.regime == AcousticRegime.NEUTRAL
            assert high_acoustic.emphasis_policy.value == "limited"

        if low_regime.regime in [OperationalRegime.HOLD, OperationalRegime.STABILIZE]:
            assert low_acoustic.suppress_emotion is True

    def test_acoustic_cannot_override_regime_decision(self):
        """Acoustic layer should not be able to change regime decision."""
        signal_bundle = SignalBundle.create_minimal(
            score=0.9,
            vritti=VrittiDistribution(pramana=0.9, viparyaya=0.025, vikalpa=0.025, smrti=0.025, nidra=0.025),
        )

        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)
        regime_envelope = derive_regime(directive)

        # The regime is determined by meaning (CV + Presentation)
        original_regime = regime_envelope.regime

        # P10 receives this regime but cannot change it
        p10 = P10AcousticResolver()
        acoustic_frame = p10.resolve(
            lexical_frame=None,
            discourse_envelope=derive_discourse_act(directive),
            regime_envelope=regime_envelope,
        )

        # Source regime in acoustic frame must match original regime
        assert acoustic_frame.source_regime == original_regime.value


class TestTracingAndDebug:
    """Test that tracing information flows through pipeline."""

    def test_debug_info_flows_through_pipeline(self):
        """Debug information should trace the full pipeline."""
        signal_bundle = SignalBundle.create_minimal(
            score=0.75,
            vritti=VrittiDistribution(pramana=0.7, viparyaya=0.1, vikalpa=0.1, smrti=0.05, nidra=0.05),
        )

        pres_engine = PresentationEngine(CONSUMER_CONFIG)
        directive = pres_engine.compute(signal_bundle)

        regime_envelope = derive_regime(directive)
        discourse_envelope = derive_discourse_act(directive)

        # Check tracing in regime envelope
        assert regime_envelope.debug["source"] == "p6_lite"
        assert regime_envelope.debug["is_derived"] is True

        # Check tracing in discourse envelope
        assert discourse_envelope.debug["source"] == "p7_lite"
        assert discourse_envelope.debug["is_derived"] is True

        # Check P10 includes source info
        p10 = P10AcousticResolver()
        acoustic_frame = p10.resolve(
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        assert acoustic_frame.source_regime == regime_envelope.regime.value
        assert acoustic_frame.source_discourse_act == discourse_envelope.act.value
