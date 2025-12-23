"""End-to-End Integration Test Suite.

This suite tests the complete Symbol-U pipeline from raw input signals
through all processing layers to final acoustic output.

Pipeline Under Test:
    Raw Signals → Chitta-Vṛtti → Presentation → P6/P7-Lite → P10

Test Categories:
1. Core Pipeline: Basic signal → acoustic flow
2. Multi-Turn Sessions: State tracking across conversation turns
3. Tier-Specific Behavior: Consumer vs Enterprise differences
4. V2.7 Integration: EMA and Bayesian mode signal handling
5. Edge Cases: Boundary conditions and error scenarios
6. Architectural Invariants: Verify "Sound obeys meaning" principle

Test Methodology:
- Each test creates realistic signal bundles
- Verifies outputs at each pipeline stage
- Checks invariants and contracts between layers
"""

import pytest
from dataclasses import replace

# Chitta-Vṛtti imports
from symbolu.chitta_vritti import (
    ChittaVrittiEngine,
    ChittaVrittiInputs,
)

# Presentation Layer imports
from symbolu.presentation import (
    PresentationEngine,
    SignalBundle,
    SessionContext,
    SessionStateManager,
    VrittiDistribution,
    V27ExperimentalSignals,
    PresentationDirective,
    DeliveryMode,
    ConfidenceIndicator,
    SuggestedBehaviors,
    # Configs
    CONSUMER_CONFIG,
    ENTERPRISE_SEARCH_CONFIG,
    ENTERPRISE_CHAT_CONFIG,
    DEVELOPMENT_CONFIG,
    # P6/P7-Lite bridges
    P6LiteResolver,
    P7LiteResolver,
    derive_regime,
    derive_discourse_act,
)

# Pipeline phase imports
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
    EmphasisPolicy,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def cv_engine():
    """Create a Chitta-Vṛtti engine with default config."""
    return ChittaVrittiEngine()


@pytest.fixture
def consumer_pres_engine():
    """Create a consumer-tier presentation engine."""
    return PresentationEngine(CONSUMER_CONFIG)


@pytest.fixture
def enterprise_pres_engine():
    """Create an enterprise-tier presentation engine."""
    return PresentationEngine(ENTERPRISE_CHAT_CONFIG)


@pytest.fixture
def session_manager():
    """Create a fresh session state manager."""
    return SessionStateManager()


@pytest.fixture
def p6_resolver():
    """Create a P6-Lite resolver."""
    return P6LiteResolver()


@pytest.fixture
def p7_resolver():
    """Create a P7-Lite resolver."""
    return P7LiteResolver()


@pytest.fixture
def p10_resolver():
    """Create a P10 acoustic resolver."""
    return P10AcousticResolver()


# =============================================================================
# Helper Functions
# =============================================================================


def create_high_confidence_bundle() -> SignalBundle:
    """Create a signal bundle representing high confidence state."""
    return SignalBundle.create_minimal(
        score=0.9,
        coherence=0.85,
        vritti=VrittiDistribution(
            pramana=0.8,
            viparyaya=0.05,
            vikalpa=0.05,
            smrti=0.05,
            nidra=0.05,
        ),
        dominant_vritti="pramana",
        entropy=0.15,
        motion=0.3,
        confidence=0.9,
        temporal_continuity=0.85,
    )


def create_low_confidence_bundle() -> SignalBundle:
    """Create a signal bundle representing low confidence state."""
    return SignalBundle.create_minimal(
        score=0.25,
        coherence=0.3,
        vritti=VrittiDistribution(
            pramana=0.1,
            viparyaya=0.5,
            vikalpa=0.2,
            smrti=0.1,
            nidra=0.1,
        ),
        dominant_vritti="viparyaya",
        entropy=0.8,
        motion=0.1,
        confidence=0.25,
        temporal_continuity=0.4,
    )


def create_ambiguous_bundle() -> SignalBundle:
    """Create a signal bundle representing ambiguous/clarifying state."""
    return SignalBundle.create_minimal(
        score=0.55,
        coherence=0.5,
        vritti=VrittiDistribution(
            pramana=0.1,
            viparyaya=0.1,
            vikalpa=0.6,  # Above CONSUMER threshold (0.5)
            smrti=0.1,
            nidra=0.1,
        ),
        dominant_vritti="vikalpa",
        entropy=0.75,  # Above entropy threshold (0.5)
        motion=0.2,
        confidence=0.5,
    )


def create_dormant_bundle() -> SignalBundle:
    """Create a signal bundle representing dormant/missing information state."""
    return SignalBundle.create_minimal(
        score=0.2,
        coherence=0.2,
        vritti=VrittiDistribution(
            pramana=0.05,
            viparyaya=0.05,
            vikalpa=0.1,
            smrti=0.1,
            nidra=0.7,
        ),
        dominant_vritti="nidra",
        entropy=0.3,
        motion=0.05,
        confidence=0.3,
        layers_present_count=1,
    )


def run_full_pipeline(
    bundle: SignalBundle,
    pres_engine: PresentationEngine,
    p6_resolver: P6LiteResolver,
    p7_resolver: P7LiteResolver,
    p10_resolver: P10AcousticResolver,
) -> tuple[PresentationDirective, RegimeEnvelope, DiscourseEnvelope, AcousticParameterFrame]:
    """Run the full pipeline and return all intermediate outputs."""
    # Stage 1: Presentation Layer
    directive = pres_engine.compute(bundle)

    # Stage 2: P6-Lite (Regime derivation)
    regime_envelope = p6_resolver.resolve(directive)

    # Stage 3: P7-Lite (Discourse act derivation)
    discourse_envelope = p7_resolver.resolve(directive)

    # Stage 4: P10 (Acoustic parameterization)
    acoustic_frame = p10_resolver.resolve(
        lexical_frame=None,
        discourse_envelope=discourse_envelope,
        regime_envelope=regime_envelope,
    )

    return directive, regime_envelope, discourse_envelope, acoustic_frame


# =============================================================================
# Test Class 1: Core Pipeline Integration
# =============================================================================


class TestCorePipelineIntegration:
    """Test the core pipeline flow for various signal states."""

    def test_high_confidence_produces_inform_regime(
        self,
        consumer_pres_engine,
        p6_resolver,
        p7_resolver,
        p10_resolver,
    ):
        """High confidence signals should produce INFORM regime and NEUTRAL acoustic."""
        bundle = create_high_confidence_bundle()

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Verify presentation
        assert directive.delivery_mode == DeliveryMode.CONFIDENT
        assert directive.confidence == ConfidenceIndicator.HIGH

        # Verify regime
        assert regime.regime == OperationalRegime.INFORM

        # Verify discourse
        assert discourse.act == DiscourseAct.EXPLANATION
        assert discourse.allowed is True

        # Verify acoustic
        assert acoustic.regime == AcousticRegime.NEUTRAL
        assert acoustic.emphasis_policy == EmphasisPolicy.LIMITED
        assert acoustic.suppress_emotion is True  # Always suppressed

    def test_low_confidence_produces_conservative_regime(
        self,
        consumer_pres_engine,
        p6_resolver,
        p7_resolver,
        p10_resolver,
    ):
        """Low confidence signals should produce conservative regime."""
        bundle = create_low_confidence_bundle()

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Verify presentation reflects low confidence
        assert directive.confidence in [ConfidenceIndicator.LOW, ConfidenceIndicator.MEDIUM]

        # Verify conservative regime
        assert regime.regime in [
            OperationalRegime.HOLD,
            OperationalRegime.STABILIZE,
            OperationalRegime.DE_ESCALATE,
            OperationalRegime.CLARIFY,
        ]

        # Verify acoustic is conservative
        assert acoustic.regime in [AcousticRegime.FLAT, AcousticRegime.SOFT]
        assert acoustic.suppress_emotion is True

    def test_ambiguous_signals_request_clarification(
        self,
        consumer_pres_engine,
        p6_resolver,
        p7_resolver,
        p10_resolver,
    ):
        """Ambiguous signals (high vikalpa) should request clarification."""
        bundle = create_ambiguous_bundle()

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Verify clarifying mode
        assert directive.delivery_mode == DeliveryMode.CLARIFYING

        # Verify CLARIFY regime
        assert regime.regime == OperationalRegime.CLARIFY

        # Verify QUESTION discourse act
        assert discourse.act == DiscourseAct.QUESTION

    def test_dormant_signals_produce_hold(
        self,
        consumer_pres_engine,
        p6_resolver,
        p7_resolver,
        p10_resolver,
    ):
        """Dormant signals (high nidra) should produce conservative output."""
        bundle = create_dormant_bundle()

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Should be conservative (severe_nidra triggers with layers_present_count < 2)
        # severe_nidra produces CLARIFYING mode with UNKNOWN confidence
        assert directive.confidence in [
            ConfidenceIndicator.LOW,
            ConfidenceIndicator.MEDIUM,
            ConfidenceIndicator.UNKNOWN,
        ]
        # severe_nidra triggers CLARIFYING mode which asks for more information
        assert directive.delivery_mode == DeliveryMode.CLARIFYING
        assert discourse.act == DiscourseAct.QUESTION
        # Acoustic frame should use neutral regime for clarification requests
        assert acoustic.regime == AcousticRegime.NEUTRAL

    def test_pipeline_is_deterministic(
        self,
        consumer_pres_engine,
        p6_resolver,
        p7_resolver,
        p10_resolver,
    ):
        """Same inputs should always produce same outputs."""
        bundle = create_high_confidence_bundle()

        # Run pipeline twice
        outputs1 = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )
        outputs2 = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # All outputs should match
        assert outputs1[0].delivery_mode == outputs2[0].delivery_mode
        assert outputs1[1].regime == outputs2[1].regime
        assert outputs1[2].act == outputs2[2].act
        assert outputs1[3].regime == outputs2[3].regime
        assert outputs1[3].speech_rate == outputs2[3].speech_rate


# =============================================================================
# Test Class 2: Multi-Turn Session Tests
# =============================================================================


class TestMultiTurnSessions:
    """Test session state tracking across conversation turns."""

    def test_session_tracks_turn_count(self, consumer_pres_engine, session_manager):
        """Session manager should track turn count."""
        bundle = create_high_confidence_bundle()

        # Simulate 3 turns
        for i in range(3):
            session_ctx = session_manager.get_context()
            assert session_ctx.turn_count == i

            # Update bundle with session context
            bundle_with_session = SignalBundle.create_minimal(
                score=0.8,
                session=session_ctx,
            )
            directive = consumer_pres_engine.compute(bundle_with_session)
            session_manager.update(
                bundle_with_session.score,
                bundle_with_session.motion,
                bundle_with_session.dominant_vritti,
            )

        assert session_manager.get_context().turn_count == 3

    def test_consecutive_low_scores_tracked(self, consumer_pres_engine, session_manager):
        """Session should track consecutive low scores."""
        # Simulate consecutive low confidence turns
        for _ in range(4):
            session_ctx = session_manager.get_context()
            bundle = SignalBundle.create_minimal(
                score=0.3,  # Low score
                session=session_ctx,
            )
            directive = consumer_pres_engine.compute(bundle)
            session_manager.update(
                bundle.score, bundle.motion, bundle.dominant_vritti
            )

        assert session_manager.get_context().consecutive_low_scores >= 3

    def test_high_score_resets_low_streak(self, consumer_pres_engine, session_manager):
        """High score should reset consecutive low score streak."""
        # First, accumulate low scores
        for _ in range(3):
            session_ctx = session_manager.get_context()
            bundle = SignalBundle.create_minimal(score=0.3, session=session_ctx)
            directive = consumer_pres_engine.compute(bundle)
            session_manager.update(
                bundle.score, bundle.motion, bundle.dominant_vritti
            )

        low_streak = session_manager.get_context().consecutive_low_scores

        # Now a high score
        session_ctx = session_manager.get_context()
        bundle = SignalBundle.create_minimal(score=0.9, session=session_ctx)
        directive = consumer_pres_engine.compute(bundle)
        session_manager.update(
            bundle.score, bundle.motion, bundle.dominant_vritti
        )

        # Low streak should be reset
        assert session_manager.get_context().consecutive_low_scores < low_streak

    def test_session_state_isolation(self):
        """Different session managers should not share state."""
        mgr1 = SessionStateManager()
        mgr2 = SessionStateManager()

        # Update mgr1
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = SignalBundle.create_minimal(score=0.3, session=mgr1.get_context())
        directive = engine.compute(bundle)
        mgr1.update(bundle.score, bundle.motion, bundle.dominant_vritti)

        # mgr2 should be unaffected
        assert mgr2.get_context().turn_count == 0
        assert mgr1.get_context().turn_count == 1


# =============================================================================
# Test Class 3: Tier-Specific Behavior
# =============================================================================


class TestTierSpecificBehavior:
    """Test differences between Consumer and Enterprise tiers."""

    def test_consumer_tier_disables_escalation(self, p6_resolver, p7_resolver, p10_resolver):
        """Consumer tier should not escalate to human."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = create_low_confidence_bundle()

        directive, _, _, _ = run_full_pipeline(
            bundle, engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Consumer config has escalate_to_human=False
        assert directive.behaviors.escalate_to_human is False

    def test_enterprise_tier_enables_escalation(self, p6_resolver, p7_resolver, p10_resolver):
        """Enterprise tier should enable escalation on critical issues."""
        engine = PresentationEngine(ENTERPRISE_SEARCH_CONFIG)

        # Create bundle that triggers critical viparyaya
        bundle = SignalBundle.create_minimal(
            score=0.3,
            vritti=VrittiDistribution(
                pramana=0.05,
                viparyaya=0.3,  # Above enterprise threshold of 0.2
                vikalpa=0.2,
                smrti=0.2,
                nidra=0.25,
            ),
        )

        directive, _, _, _ = run_full_pipeline(
            bundle, engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Enterprise config has escalate_to_human=True
        assert directive.behaviors.escalate_to_human is True

    def test_enterprise_chat_shows_reasoning_by_default(
        self, p6_resolver, p7_resolver, p10_resolver
    ):
        """Enterprise chat tier should show reasoning by default."""
        engine = PresentationEngine(ENTERPRISE_CHAT_CONFIG)
        bundle = create_ambiguous_bundle()

        directive, _, _, _ = run_full_pipeline(
            bundle, engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Enterprise chat has show_reasoning_by_default=True
        assert directive.behaviors.show_reasoning is True

    def test_development_tier_includes_diagnostics(
        self, p6_resolver, p7_resolver, p10_resolver
    ):
        """Development tier should include diagnostic info."""
        engine = PresentationEngine(DEVELOPMENT_CONFIG)
        bundle = SignalBundle.create_minimal(
            score=0.6,
            dominant_vritti="pramana",
        )

        directive, _, _, _ = run_full_pipeline(
            bundle, engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Development config has include_diagnostics=True
        assert directive.diagnostic is not None
        assert directive.diagnostic.dominant_vritti == "pramana"

    def test_consumer_tier_excludes_diagnostics(
        self, p6_resolver, p7_resolver, p10_resolver
    ):
        """Consumer tier should not include diagnostic info."""
        engine = PresentationEngine(CONSUMER_CONFIG)
        bundle = create_high_confidence_bundle()

        directive, _, _, _ = run_full_pipeline(
            bundle, engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Consumer config has include_diagnostics=False
        assert directive.diagnostic is None

    def test_different_thresholds_per_tier(self, p6_resolver, p7_resolver, p10_resolver):
        """Different tiers should have different sensitivity thresholds."""
        # Create bundle with borderline viparyaya
        bundle = SignalBundle.create_minimal(
            score=0.5,
            vritti=VrittiDistribution(
                pramana=0.3,
                viparyaya=0.25,  # Between consumer (0.6) and enterprise (0.2) thresholds
                vikalpa=0.2,
                smrti=0.15,
                nidra=0.1,
            ),
        )

        consumer_engine = PresentationEngine(CONSUMER_CONFIG)
        enterprise_engine = PresentationEngine(ENTERPRISE_SEARCH_CONFIG)

        consumer_directive = consumer_engine.compute(bundle)
        enterprise_directive = enterprise_engine.compute(bundle)

        # Enterprise should trigger critical_viparyaya, consumer should not
        assert enterprise_directive.triggered_rule == "critical_viparyaya"
        assert consumer_directive.triggered_rule != "critical_viparyaya"


# =============================================================================
# Test Class 4: V2.7 Signal Integration
# =============================================================================


class TestV27SignalIntegration:
    """Test integration with v2.7 experimental signals."""

    def test_v27_disabled_uses_core_rules_only(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """With v2.7 disabled, only core rules should fire."""
        bundle = SignalBundle.create_minimal(
            score=0.7,
            v27=None,  # v2.7 disabled
        )

        directive, _, _, _ = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Should not trigger v2.7 rules
        assert "_v27" not in directive.triggered_rule

    def test_v27_ema_mode_detects_regression(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """V2.7 EMA mode should detect regressing cognitive state."""
        v27_signals = V27ExperimentalSignals.ema_mode(
            cognitive_state="regressing",
        )
        bundle = SignalBundle.create_with_v27(v27_signals, score=0.7)

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Should trigger regressing_state_v27 rule
        assert directive.triggered_rule == "regressing_state_v27"
        assert directive.delivery_mode == DeliveryMode.CLARIFYING

        # Regime should be conservative
        assert regime.regime == OperationalRegime.CLARIFY

    def test_v27_bayesian_low_confidence_triggers_unreliable(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """V2.7 Bayesian mode with low confidence should trigger unreliable estimate."""
        v27_signals = V27ExperimentalSignals.bayesian_mode_signals(
            bayesian_confidence=0.3,  # Low Bayesian confidence
        )
        bundle = SignalBundle.create_with_v27(v27_signals, score=0.7)

        directive, regime, _, _ = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Should trigger unreliable_estimate_v27
        assert directive.triggered_rule == "unreliable_estimate_v27"
        assert directive.confidence == ConfidenceIndicator.LOW

    def test_v27_concept_unstable_triggers_hedged(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """V2.7 with unstable concepts should trigger hedged output."""
        v27_signals = V27ExperimentalSignals.ema_mode(
            concept_readiness=0.2,  # Low concept readiness
            concept_readiness_level="emerging",
        )
        bundle = SignalBundle.create_with_v27(v27_signals, score=0.7)

        directive, regime, _, _ = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Should trigger concept_unstable_v27
        assert directive.triggered_rule == "concept_unstable_v27"
        assert directive.delivery_mode == DeliveryMode.HEDGED

    def test_v27_signals_flow_to_acoustic(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """V2.7 signal effects should flow through to acoustic output."""
        # V2.7 regressing state
        v27_signals = V27ExperimentalSignals.ema_mode(cognitive_state="regressing")
        bundle = SignalBundle.create_with_v27(v27_signals, score=0.7)

        _, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Verify acoustic reflects the conservative regime
        assert acoustic.source_regime == regime.regime.value
        assert acoustic.source_discourse_act == discourse.act.value

    def test_core_rules_override_v27_when_higher_priority(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """Core rules with higher priority should override v2.7 rules."""
        # Both critical_viparyaya (100) and regressing_state_v27 (88) could fire
        v27_signals = V27ExperimentalSignals.ema_mode(cognitive_state="regressing")
        bundle = SignalBundle.create_with_v27(
            v27_signals,
            vritti=VrittiDistribution(
                pramana=0.05,
                viparyaya=0.8,  # High viparyaya triggers core rule
                vikalpa=0.05,
                smrti=0.05,
                nidra=0.05,
            ),
        )

        directive, _, _, _ = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # critical_viparyaya (100) should win over regressing_state_v27 (88)
        assert directive.triggered_rule == "critical_viparyaya"


# =============================================================================
# Test Class 5: Edge Cases and Boundary Conditions
# =============================================================================


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    def test_all_zero_vritti_distribution(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """System should handle all-zero vritti distribution gracefully."""
        bundle = SignalBundle.create_minimal(
            score=0.5,
            vritti=VrittiDistribution(
                pramana=0.0,
                viparyaya=0.0,
                vikalpa=0.0,
                smrti=0.0,
                nidra=0.0,
            ),
        )

        # Should not raise, should produce valid output
        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        assert directive is not None
        assert regime is not None
        assert acoustic is not None

    def test_extreme_score_values(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """System should handle extreme score values."""
        for score in [0.0, 1.0]:
            bundle = SignalBundle.create_minimal(score=score)

            directive, regime, discourse, acoustic = run_full_pipeline(
                bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
            )

            assert directive is not None
            assert 3.0 <= acoustic.speech_rate <= 5.5
            assert 0.2 <= acoustic.energy_level <= 0.6

    def test_missing_layers_handled(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """System should handle missing representation layers."""
        bundle = SignalBundle.create_minimal(
            score=0.5,
            layers_present_count=0,
            missing_layers=("phonemic", "semantic", "structural", "temporal"),
        )

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Should produce conservative output
        assert directive is not None
        assert acoustic is not None

    def test_empty_session_context(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """System should handle empty session context."""
        bundle = SignalBundle.create_minimal(
            score=0.7,
            session=SessionContext(),
        )

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        assert directive is not None
        assert acoustic is not None

    def test_boundary_confidence_thresholds(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """Test scores exactly at threshold boundaries."""
        # Score exactly at moderate_uncertainty threshold (0.4-0.6)
        for score in [0.4, 0.6]:
            bundle = SignalBundle.create_minimal(score=score)

            directive, _, _, _ = run_full_pipeline(
                bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
            )

            assert directive is not None


# =============================================================================
# Test Class 6: Architectural Invariants
# =============================================================================


class TestArchitecturalInvariants:
    """Test that architectural invariants are maintained."""

    def test_sound_obeys_meaning(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """Verify that acoustic output obeys semantic decisions."""
        # High confidence (meaning: "confident response")
        high_bundle = create_high_confidence_bundle()
        _, high_regime, _, high_acoustic = run_full_pipeline(
            high_bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Low confidence (meaning: "uncertain response")
        low_bundle = create_low_confidence_bundle()
        _, low_regime, _, low_acoustic = run_full_pipeline(
            low_bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Acoustic (sound) should reflect regime (meaning)
        assert high_acoustic.source_regime == high_regime.regime.value
        assert low_acoustic.source_regime == low_regime.regime.value

        # Conservative meaning should produce conservative sound
        if low_regime.regime in [OperationalRegime.HOLD, OperationalRegime.STABILIZE]:
            assert low_acoustic.suppress_certainty is True

    def test_regime_cannot_be_overridden_by_acoustic(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """Acoustic layer should not be able to change regime decisions."""
        bundle = create_high_confidence_bundle()

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Regime was determined by meaning (CV + Presentation)
        original_regime = regime.regime

        # Acoustic frame must reflect this regime
        assert acoustic.source_regime == original_regime.value

        # Cannot change the regime through acoustic path
        # (This is by construction - acoustic only receives, doesn't set)

    def test_all_outputs_traceable(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """All outputs should be traceable to their sources."""
        bundle = create_high_confidence_bundle()

        directive, regime, discourse, acoustic = run_full_pipeline(
            bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
        )

        # Directive traces to rule
        assert directive.triggered_rule != ""

        # Regime traces to source
        assert regime.debug["source"] == "p6_lite"
        assert regime.debug["source_delivery_mode"] == directive.delivery_mode.value

        # Discourse traces to source
        assert discourse.debug["source"] == "p7_lite"

        # Acoustic traces to regime and discourse
        assert acoustic.source_regime == regime.regime.value
        assert acoustic.source_discourse_act == discourse.act.value

    def test_pipeline_completeness(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """Every valid input should produce a complete output."""
        test_bundles = [
            create_high_confidence_bundle(),
            create_low_confidence_bundle(),
            create_ambiguous_bundle(),
            create_dormant_bundle(),
            SignalBundle.create_minimal(score=0.0),
            SignalBundle.create_minimal(score=1.0),
        ]

        for bundle in test_bundles:
            directive, regime, discourse, acoustic = run_full_pipeline(
                bundle, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
            )

            # All stages should produce output
            assert isinstance(directive, PresentationDirective)
            assert isinstance(regime, RegimeEnvelope)
            assert isinstance(discourse, DiscourseEnvelope)
            assert isinstance(acoustic, AcousticParameterFrame)

            # All outputs should be valid
            assert directive.delivery_mode in DeliveryMode
            assert regime.regime in OperationalRegime
            assert discourse.act in DiscourseAct
            assert acoustic.regime in AcousticRegime


# =============================================================================
# Test Class 7: Cross-Component Contract Tests
# =============================================================================


class TestCrossComponentContracts:
    """Test contracts between pipeline components."""

    def test_presentation_to_p6_contract(self, consumer_pres_engine, p6_resolver):
        """Presentation directive should satisfy P6-Lite input contract."""
        bundle = create_high_confidence_bundle()
        directive = consumer_pres_engine.compute(bundle)

        # P6-Lite expects valid DeliveryMode
        assert isinstance(directive.delivery_mode, DeliveryMode)

        # P6-Lite should accept any valid directive
        regime = p6_resolver.resolve(directive)
        assert isinstance(regime, RegimeEnvelope)

    def test_presentation_to_p7_contract(self, consumer_pres_engine, p7_resolver):
        """Presentation directive should satisfy P7-Lite input contract."""
        bundle = create_high_confidence_bundle()
        directive = consumer_pres_engine.compute(bundle)

        # P7-Lite expects valid DeliveryMode and behaviors
        assert isinstance(directive.delivery_mode, DeliveryMode)
        assert isinstance(directive.behaviors, SuggestedBehaviors)

        # P7-Lite should accept any valid directive
        discourse = p7_resolver.resolve(directive)
        assert isinstance(discourse, DiscourseEnvelope)

    def test_p6_p7_to_p10_contract(
        self, consumer_pres_engine, p6_resolver, p7_resolver, p10_resolver
    ):
        """P6 and P7 outputs should satisfy P10 input contract."""
        bundle = create_high_confidence_bundle()
        directive = consumer_pres_engine.compute(bundle)

        regime = p6_resolver.resolve(directive)
        discourse = p7_resolver.resolve(directive)

        # P10 expects valid RegimeEnvelope and DiscourseEnvelope
        assert isinstance(regime.regime, OperationalRegime)
        assert isinstance(discourse.act, DiscourseAct)

        # P10 should accept these
        acoustic = p10_resolver.resolve(
            lexical_frame=None,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )
        assert isinstance(acoustic, AcousticParameterFrame)

    @pytest.mark.parametrize("delivery_mode", list(DeliveryMode))
    def test_all_delivery_modes_produce_valid_pipeline_output(
        self,
        delivery_mode,
        p6_resolver,
        p7_resolver,
        p10_resolver,
    ):
        """Every DeliveryMode should produce valid output through entire pipeline."""
        directive = PresentationDirective(
            delivery_mode=delivery_mode,
            confidence=ConfidenceIndicator.MEDIUM,
            triggered_rule=f"test_{delivery_mode.value}",
        )

        regime = p6_resolver.resolve(directive)
        discourse = p7_resolver.resolve(directive)
        acoustic = p10_resolver.resolve(
            lexical_frame=None,
            discourse_envelope=discourse,
            regime_envelope=regime,
        )

        # All should be valid
        assert acoustic.regime in AcousticRegime
        assert 3.0 <= acoustic.speech_rate <= 5.5
        assert 0.2 <= acoustic.energy_level <= 0.6
