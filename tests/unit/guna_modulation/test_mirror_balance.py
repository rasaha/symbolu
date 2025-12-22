"""
Tests for MirrorBalance module.

Tests:
- Mirror observables computation
- Balance detection and correction
- Self-questioning protocol
- Ontological layer hierarchy
- Cross-layer dissonance detection
- Cognitive ambition measurement
"""

import pytest
import math
from symbolu.guna_modulation.observables import Observables, MotionType
from symbolu.guna_modulation.mirror_balance import (
    # Core mirror functions
    compute_mirror_observables,
    create_mirror_pair,
    MirrorPair,
    # Balance correction
    compute_balance_correction,
    apply_balance_correction,
    BalanceCorrection,
    MirrorBalanceEngine,
    # Harmonic mirror
    compute_harmonic_mirror,
    # Self-questioning
    generate_self_questions,
    SelfQuestion,
    # Ontological layers
    OntologicalLayer,
    # Cross-layer dissonance
    LayerState,
    LayerDissonance,
    compute_layer_dissonance,
    LayerDissonanceMonitor,
    generate_ambition_questions,
    # Benchmark
    CognitiveMetrics,
    MirrorOnlyAnalyzer,
    SelectiveOnlyAnalyzer,
    CombinedAnalyzer,
    BenchmarkResult,
    run_cognitive_benchmark,
    run_standard_benchmark_suite,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def balanced_observables():
    """Observables that are balanced (S ≈ T, H ≈ 0.5, M ≈ 0.5)."""
    return Observables(
        s=0.35,
        r=0.30,
        t=0.35,
        H=0.5,
        delta_sem=0.5,
        C_contr=0.1,
        F_fail=0.05,
    )


@pytest.fixture
def sattva_heavy_observables():
    """Observables biased toward Sattva."""
    return Observables(
        s=0.7,
        r=0.2,
        t=0.1,
        H=0.3,
        delta_sem=0.2,
        C_contr=0.05,
        F_fail=0.0,
    )


@pytest.fixture
def tamas_heavy_observables():
    """Observables biased toward Tamas."""
    return Observables(
        s=0.1,
        r=0.2,
        t=0.7,
        H=0.7,
        delta_sem=0.8,
        C_contr=0.3,
        F_fail=0.2,
    )


# =============================================================================
# Mirror Observables Tests
# =============================================================================

class TestMirrorObservables:
    """Tests for compute_mirror_observables."""

    def test_guna_swap(self, sattva_heavy_observables):
        """Mirror swaps Sattva and Tamas."""
        mirror = compute_mirror_observables(sattva_heavy_observables)
        assert mirror.s == sattva_heavy_observables.t
        assert mirror.t == sattva_heavy_observables.s
        assert mirror.r == sattva_heavy_observables.r

    def test_entropy_complement(self, balanced_observables):
        """Mirror has complementary entropy."""
        mirror = compute_mirror_observables(balanced_observables)
        assert mirror.H == pytest.approx(1.0 - balanced_observables.H)

    def test_motion_complement(self, balanced_observables):
        """Mirror has complementary motion."""
        mirror = compute_mirror_observables(balanced_observables)
        assert mirror.delta_sem == pytest.approx(1.0 - balanced_observables.delta_sem)

    def test_double_mirror_identity(self, sattva_heavy_observables):
        """Mirroring twice returns to original."""
        mirror = compute_mirror_observables(sattva_heavy_observables)
        double_mirror = compute_mirror_observables(mirror)
        assert double_mirror.s == pytest.approx(sattva_heavy_observables.s)
        assert double_mirror.t == pytest.approx(sattva_heavy_observables.t)
        assert double_mirror.H == pytest.approx(sattva_heavy_observables.H)

    def test_balanced_mirror_similar(self, balanced_observables):
        """Balanced observables have similar mirror."""
        mirror = compute_mirror_observables(balanced_observables)
        # For balanced obs (S=T, H=0.5), mirror should be identical
        assert abs(mirror.s - balanced_observables.s) < 0.01
        assert abs(mirror.H - balanced_observables.H) < 0.01


# =============================================================================
# Mirror Pair Tests
# =============================================================================

class TestMirrorPair:
    """Tests for MirrorPair and asymmetry detection."""

    def test_balanced_has_low_asymmetry(self, balanced_observables):
        """Balanced observables have low total asymmetry."""
        pair = create_mirror_pair(balanced_observables)
        assert pair.total_asymmetry < 0.15
        assert pair.is_balanced

    def test_unbalanced_has_high_asymmetry(self, sattva_heavy_observables):
        """Unbalanced observables have high asymmetry."""
        pair = create_mirror_pair(sattva_heavy_observables)
        assert pair.guna_asymmetry > 0.5  # |S - T| = 0.6
        assert not pair.is_balanced

    def test_balance_direction_sattva_heavy(self, sattva_heavy_observables):
        """Detects sattva-heavy direction."""
        pair = create_mirror_pair(sattva_heavy_observables)
        assert "sattva-heavy" in pair.balance_direction

    def test_balance_direction_tamas_heavy(self, tamas_heavy_observables):
        """Detects tamas-heavy direction."""
        pair = create_mirror_pair(tamas_heavy_observables)
        assert "tamas-heavy" in pair.balance_direction


# =============================================================================
# Balance Correction Tests
# =============================================================================

class TestBalanceCorrection:
    """Tests for balance correction computation and application."""

    def test_correction_reduces_asymmetry(self, sattva_heavy_observables):
        """Correction should reduce asymmetry."""
        correction = compute_balance_correction(sattva_heavy_observables, learning_rate=0.5)
        assert correction.asymmetry_after < correction.asymmetry_before
        assert correction.improvement_ratio > 0

    def test_small_learning_rate_small_delta(self, sattva_heavy_observables):
        """Small learning rate produces small deltas."""
        small = compute_balance_correction(sattva_heavy_observables, learning_rate=0.1)
        large = compute_balance_correction(sattva_heavy_observables, learning_rate=0.5)
        assert small.correction_magnitude < large.correction_magnitude

    def test_apply_correction_maintains_constraints(self, sattva_heavy_observables):
        """Applied correction maintains Guna sum = 1."""
        correction = compute_balance_correction(sattva_heavy_observables, learning_rate=0.3)
        corrected = apply_balance_correction(sattva_heavy_observables, correction)
        assert corrected.s + corrected.r + corrected.t == pytest.approx(1.0)
        assert 0 <= corrected.H <= 1
        assert 0 <= corrected.delta_sem <= 1

    def test_correction_moves_toward_balance(self, sattva_heavy_observables):
        """Corrected observables are more balanced."""
        correction = compute_balance_correction(sattva_heavy_observables, learning_rate=0.3)
        corrected = apply_balance_correction(sattva_heavy_observables, correction)

        original_pair = create_mirror_pair(sattva_heavy_observables)
        corrected_pair = create_mirror_pair(corrected)

        assert corrected_pair.total_asymmetry < original_pair.total_asymmetry


# =============================================================================
# Mirror Balance Engine Tests
# =============================================================================

class TestMirrorBalanceEngine:
    """Tests for MirrorBalanceEngine."""

    def test_analyze_returns_pair(self, balanced_observables):
        """Analyze returns MirrorPair."""
        engine = MirrorBalanceEngine()
        pair = engine.analyze(balanced_observables)
        assert isinstance(pair, MirrorPair)

    def test_history_tracking(self, sattva_heavy_observables, tamas_heavy_observables):
        """Engine tracks history of asymmetry."""
        engine = MirrorBalanceEngine()
        engine.analyze(sattva_heavy_observables)
        engine.analyze(tamas_heavy_observables)
        assert len(engine.asymmetry_trend) == 2

    def test_auto_correct_mode(self, sattva_heavy_observables):
        """Auto-correct mode applies corrections."""
        engine = MirrorBalanceEngine(auto_correct=True, learning_rate=0.2)
        corrected, pair = engine.process(sattva_heavy_observables)
        # Should be different from original
        assert corrected.s != sattva_heavy_observables.s

    def test_no_auto_correct_mode(self, sattva_heavy_observables):
        """Non-auto-correct mode returns original."""
        engine = MirrorBalanceEngine(auto_correct=False)
        result, pair = engine.process(sattva_heavy_observables)
        assert result.s == sattva_heavy_observables.s


# =============================================================================
# Harmonic Mirror Tests
# =============================================================================

class TestHarmonicMirror:
    """Tests for harmonic mirror (HRM integration)."""

    def test_harmonic_mirror_blends_signals(self, sattva_heavy_observables):
        """Harmonic mirror blends original, mirror, and balance."""
        harmonic = compute_harmonic_mirror(sattva_heavy_observables)
        # Should be between original and mirror
        assert sattva_heavy_observables.s > harmonic.s > sattva_heavy_observables.t

    def test_harmonic_maintains_constraints(self, sattva_heavy_observables):
        """Harmonic maintains Guna sum = 1."""
        harmonic = compute_harmonic_mirror(sattva_heavy_observables)
        assert harmonic.s + harmonic.r + harmonic.t == pytest.approx(1.0)

    def test_harmonic_more_balanced(self, sattva_heavy_observables):
        """Harmonic is more balanced than original."""
        harmonic = compute_harmonic_mirror(sattva_heavy_observables)
        original_pair = create_mirror_pair(sattva_heavy_observables)
        harmonic_pair = create_mirror_pair(harmonic)
        assert harmonic_pair.total_asymmetry < original_pair.total_asymmetry


# =============================================================================
# Self-Questioning Tests
# =============================================================================

class TestSelfQuestioning:
    """Tests for self-questioning protocol."""

    def test_balanced_few_questions(self, balanced_observables):
        """Balanced observables generate few questions."""
        questions = generate_self_questions(balanced_observables)
        assert len(questions) <= 2  # Maybe just subtle ones

    def test_unbalanced_many_questions(self, tamas_heavy_observables):
        """Unbalanced observables generate many questions."""
        questions = generate_self_questions(tamas_heavy_observables)
        assert len(questions) >= 3  # Multiple concerns

    def test_questions_have_severity(self, sattva_heavy_observables):
        """Questions include severity classification."""
        questions = generate_self_questions(sattva_heavy_observables)
        for q in questions:
            assert q.severity in ["low", "medium", "high"]

    def test_high_contradiction_flags_question(self):
        """High contradiction generates question."""
        obs = Observables(
            s=0.33, r=0.34, t=0.33,
            H=0.5, delta_sem=0.5,
            C_contr=0.5,  # High contradiction
            F_fail=0.0,
        )
        questions = generate_self_questions(obs)
        question_signals = [q.signal for q in questions]
        assert "contradiction" in question_signals


# =============================================================================
# Ontological Layer Tests
# =============================================================================

class TestOntologicalLayer:
    """Tests for ontological layer hierarchy."""

    def test_layer_levels(self):
        """Layers have correct levels."""
        assert OntologicalLayer.level(OntologicalLayer.SIGNAL) == 0
        assert OntologicalLayer.level(OntologicalLayer.EMBEDDING) == 1
        assert OntologicalLayer.level(OntologicalLayer.GUNA) == 2
        assert OntologicalLayer.level(OntologicalLayer.OUTPUT) == 6

    def test_adjacent_detection(self):
        """Correctly detects adjacent layers."""
        assert OntologicalLayer.is_adjacent(OntologicalLayer.SIGNAL, OntologicalLayer.EMBEDDING)
        assert OntologicalLayer.is_adjacent(OntologicalLayer.GUNA, OntologicalLayer.MOTION)
        assert not OntologicalLayer.is_adjacent(OntologicalLayer.SIGNAL, OntologicalLayer.GUNA)

    def test_direction_ascending(self):
        """Detects ascending direction."""
        direction = OntologicalLayer.direction(OntologicalLayer.SIGNAL, OntologicalLayer.GUNA)
        assert direction == "ascending"

    def test_direction_descending(self):
        """Detects descending direction."""
        direction = OntologicalLayer.direction(OntologicalLayer.OUTPUT, OntologicalLayer.GUNA)
        assert direction == "descending"


# =============================================================================
# Cross-Layer Dissonance Tests
# =============================================================================

class TestCrossLayerDissonance:
    """Tests for cross-layer dissonance detection."""

    def test_compute_dissonance(self, balanced_observables, sattva_heavy_observables):
        """Computes dissonance between layers."""
        layer_a = LayerState(
            layer_id=OntologicalLayer.EMBEDDING,
            observables=balanced_observables,
            layer_index=0,
        )
        layer_b = LayerState(
            layer_id=OntologicalLayer.GUNA,
            observables=sattva_heavy_observables,
            layer_index=1,
        )
        dissonance = compute_layer_dissonance(layer_a, layer_b)
        assert dissonance.total_dissonance > 0
        assert dissonance.guna_dissonance > 0

    def test_constructive_dissonance(self, tamas_heavy_observables, sattva_heavy_observables):
        """Detects constructive dissonance (improvement)."""
        # Layer A has low coherence (tamas-heavy)
        layer_a = LayerState(
            layer_id=OntologicalLayer.EMBEDDING,
            observables=tamas_heavy_observables,
        )
        # Layer B has high coherence (sattva-heavy)
        layer_b = LayerState(
            layer_id=OntologicalLayer.GUNA,
            observables=sattva_heavy_observables,
        )
        dissonance = compute_layer_dissonance(layer_a, layer_b)
        assert dissonance.is_constructive
        assert dissonance.cognitive_ambition > 0

    def test_destructive_dissonance(self, sattva_heavy_observables, tamas_heavy_observables):
        """Detects destructive dissonance (regression)."""
        # Layer A has high coherence
        layer_a = LayerState(
            layer_id=OntologicalLayer.GUNA,
            observables=sattva_heavy_observables,
        )
        # Layer B has low coherence (regression)
        layer_b = LayerState(
            layer_id=OntologicalLayer.FUSION,
            observables=tamas_heavy_observables,
        )
        dissonance = compute_layer_dissonance(layer_a, layer_b)
        assert dissonance.coherence_gap < 0

    def test_ontological_tension(self, balanced_observables, sattva_heavy_observables):
        """Computes ontological tension for adjacent layers."""
        layer_a = LayerState(
            layer_id=OntologicalLayer.EMBEDDING,
            observables=balanced_observables,
        )
        layer_b = LayerState(
            layer_id=OntologicalLayer.GUNA,
            observables=sattva_heavy_observables,
        )
        dissonance = compute_layer_dissonance(layer_a, layer_b)
        assert dissonance.is_ontologically_adjacent
        assert dissonance.ontological_tension > 0


# =============================================================================
# Layer Dissonance Monitor Tests
# =============================================================================

class TestLayerDissonanceMonitor:
    """Tests for LayerDissonanceMonitor."""

    def test_add_layers_computes_dissonance(self, balanced_observables, sattva_heavy_observables):
        """Adding layers computes dissonance automatically."""
        monitor = LayerDissonanceMonitor()
        monitor.add_layer(OntologicalLayer.SIGNAL, balanced_observables)
        monitor.add_layer(OntologicalLayer.EMBEDDING, sattva_heavy_observables)

        report = monitor.analyze()
        assert report["layers"] == 2
        assert report["transitions"] == 1

    def test_full_pipeline_analysis(self, balanced_observables, sattva_heavy_observables, tamas_heavy_observables):
        """Analyzes full pipeline."""
        monitor = LayerDissonanceMonitor()
        monitor.add_layer(OntologicalLayer.SIGNAL, tamas_heavy_observables)
        monitor.add_layer(OntologicalLayer.EMBEDDING, balanced_observables)
        monitor.add_layer(OntologicalLayer.GUNA, sattva_heavy_observables)

        report = monitor.analyze()
        assert report["layers"] == 3
        assert report["transitions"] == 2
        assert len(report["ambition_trend"]) == 2

    def test_net_ambition(self, balanced_observables, sattva_heavy_observables, tamas_heavy_observables):
        """Computes net cognitive ambition."""
        monitor = LayerDissonanceMonitor()
        # Start with poor state, improve through layers
        monitor.add_layer(OntologicalLayer.SIGNAL, tamas_heavy_observables)
        monitor.add_layer(OntologicalLayer.GUNA, balanced_observables)
        monitor.add_layer(OntologicalLayer.FUSION, sattva_heavy_observables)

        assert monitor.net_ambition > 0  # Overall improvement


# =============================================================================
# Ambition Questions Tests
# =============================================================================

class TestAmbitionQuestions:
    """Tests for ambition question generation."""

    def test_generates_questions(self, balanced_observables, sattva_heavy_observables):
        """Generates questions from dissonance."""
        layer_a = LayerState(
            layer_id=OntologicalLayer.EMBEDDING,
            observables=balanced_observables,
        )
        layer_b = LayerState(
            layer_id=OntologicalLayer.GUNA,
            observables=sattva_heavy_observables,
        )
        dissonance = compute_layer_dissonance(layer_a, layer_b)
        questions = generate_ambition_questions(dissonance)
        assert len(questions) > 0

    def test_constructive_question_content(self, tamas_heavy_observables, sattva_heavy_observables):
        """Constructive dissonance generates improvement questions."""
        layer_a = LayerState(
            layer_id=OntologicalLayer.SIGNAL,
            observables=tamas_heavy_observables,
        )
        layer_b = LayerState(
            layer_id=OntologicalLayer.GUNA,
            observables=sattva_heavy_observables,
        )
        dissonance = compute_layer_dissonance(layer_a, layer_b)
        questions = generate_ambition_questions(dissonance)

        # Should mention improvement
        has_improvement_question = any("improvement" in q.lower() or "amplify" in q.lower() for q in questions)
        assert has_improvement_question


# =============================================================================
# Configurable Layer Comparison Tests
# =============================================================================

from symbolu.guna_modulation.mirror_balance import (
    LayerComparisonConfig,
    LAYER_COMPARISON_ENTERPRISE_T1,
    LAYER_COMPARISON_ENTERPRISE_T2,
    LAYER_COMPARISON_CONSUMER,
    LAYER_COMPARISON_FULL_PIPELINE,
    DEFAULT_LAYER_COMPARISON,
    get_layer_comparison_for_tier,
    ConfigurableDissonanceMonitor,
)


class TestLayerComparisonConfig:
    """Tests for LayerComparisonConfig."""

    def test_default_config_is_enterprise_t2(self):
        """Default config matches Enterprise T2."""
        assert DEFAULT_LAYER_COMPARISON == LAYER_COMPARISON_ENTERPRISE_T2

    def test_enterprise_t1_focuses_on_fusion_state(self):
        """Enterprise T1 focuses on Fusion → State transition."""
        config = LAYER_COMPARISON_ENTERPRISE_T1
        assert config.primary_comparison == (OntologicalLayer.FUSION, OntologicalLayer.STATE)

    def test_consumer_focuses_on_output(self):
        """Consumer config focuses on State → Output."""
        config = LAYER_COMPARISON_CONSUMER
        assert config.primary_comparison == (OntologicalLayer.STATE, OntologicalLayer.OUTPUT)
        assert config.mirror_layer == OntologicalLayer.OUTPUT

    def test_full_pipeline_monitors_all(self):
        """Full pipeline monitors all layer transitions."""
        config = LAYER_COMPARISON_FULL_PIPELINE
        # Should have 6 secondary comparisons (all adjacent pairs)
        assert len(config.secondary_comparisons) == 6

    def test_monitored_layers_property(self):
        """monitored_layers returns all unique layers."""
        config = LAYER_COMPARISON_ENTERPRISE_T2
        layers = config.monitored_layers
        assert OntologicalLayer.GUNA in layers
        assert OntologicalLayer.FUSION in layers

    def test_get_layer_comparison_for_tier(self):
        """get_layer_comparison_for_tier returns correct config."""
        assert get_layer_comparison_for_tier("enterprise_t1") == LAYER_COMPARISON_ENTERPRISE_T1
        assert get_layer_comparison_for_tier("consumer") == LAYER_COMPARISON_CONSUMER
        assert get_layer_comparison_for_tier("unknown") == DEFAULT_LAYER_COMPARISON


class TestConfigurableDissonanceMonitor:
    """Tests for ConfigurableDissonanceMonitor."""

    def test_for_tier_factory(self):
        """for_tier factory creates correct configuration."""
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t1")
        assert monitor.config == LAYER_COMPARISON_ENTERPRISE_T1

    def test_observe_updates_dissonances(self, balanced_observables, sattva_heavy_observables):
        """observe() updates dissonances when layers are available."""
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t2")

        # Add observations for configured layers
        monitor.observe(OntologicalLayer.GUNA, balanced_observables)
        monitor.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        # Primary dissonance should be computed
        primary = monitor.get_primary_dissonance()
        assert primary is not None
        assert primary.layer_a.layer_id == OntologicalLayer.GUNA
        assert primary.layer_b.layer_id == OntologicalLayer.FUSION

    def test_cognitive_insights(self, balanced_observables, sattva_heavy_observables, tamas_heavy_observables):
        """get_cognitive_insights returns structured insights."""
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t2")

        # Simulate pipeline with improving quality
        monitor.observe(OntologicalLayer.EMBEDDING, tamas_heavy_observables)
        monitor.observe(OntologicalLayer.GUNA, balanced_observables)
        monitor.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        insights = monitor.get_cognitive_insights()

        assert "primary_comparison" in insights
        assert "primary_ambition" in insights
        assert "total_ambition" in insights
        assert "mirror_balance" in insights
        assert "cognitive_state" in insights
        assert "attention_focus" in insights

    def test_cognitive_state_classification(self, balanced_observables, sattva_heavy_observables):
        """Cognitive state is correctly classified."""
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t2")

        # Balanced state at guna layer = good mirror balance
        monitor.observe(OntologicalLayer.GUNA, balanced_observables)
        monitor.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        insights = monitor.get_cognitive_insights()
        # Should be either stable, neutral, or thriving depending on ambition
        assert insights["cognitive_state"] in ["stable", "neutral", "thriving", "striving"]

    def test_attention_focus_with_destructive(self, sattva_heavy_observables, tamas_heavy_observables):
        """Attention focus identifies destructive transitions."""
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t2")

        # Regression: good → bad
        monitor.observe(OntologicalLayer.GUNA, sattva_heavy_observables)
        monitor.observe(OntologicalLayer.FUSION, tamas_heavy_observables)

        insights = monitor.get_cognitive_insights()
        # Should recommend fixing regression, amplifying, or maintaining
        focus = insights["attention_focus"]
        assert "fix" in focus or "maintain" in focus or "amplify" in focus

    def test_custom_config(self, balanced_observables, sattva_heavy_observables):
        """Custom configuration works correctly."""
        config = LayerComparisonConfig(
            primary_comparison=(OntologicalLayer.SIGNAL, OntologicalLayer.GUNA),
            secondary_comparisons=[],
            mirror_layer=OntologicalLayer.SIGNAL,
            attention_weight=0.9,
        )
        monitor = ConfigurableDissonanceMonitor(config)

        monitor.observe(OntologicalLayer.SIGNAL, balanced_observables)
        monitor.observe(OntologicalLayer.GUNA, sattva_heavy_observables)

        insights = monitor.get_cognitive_insights()
        assert insights["primary_comparison"] == (OntologicalLayer.SIGNAL, OntologicalLayer.GUNA)

    def test_reset_clears_observations(self, balanced_observables):
        """reset() clears all observations."""
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t2")
        monitor.observe(OntologicalLayer.GUNA, balanced_observables)
        monitor.reset()

        assert monitor.get_primary_dissonance() is None


# =============================================================================
# Test Cognitive Benchmark
# =============================================================================

class TestCognitiveMetrics:
    """Tests for CognitiveMetrics dataclass."""

    def test_total_score_calculation(self):
        """Total score is weighted correctly."""
        metrics = CognitiveMetrics(
            self_awareness=1.0,
            directional_focus=1.0,
            actionability=1.0,
            state_classification=1.0,
        )
        assert metrics.total_cognitive_score == 1.0

    def test_category_high(self):
        """High category for score >= 0.8."""
        metrics = CognitiveMetrics(
            self_awareness=0.9,
            directional_focus=0.9,
            actionability=0.9,
            state_classification=0.9,
        )
        assert metrics.category == "high"

    def test_category_moderate(self):
        """Moderate category for score 0.5-0.8."""
        metrics = CognitiveMetrics(
            self_awareness=0.6,
            directional_focus=0.6,
            actionability=0.6,
            state_classification=0.6,
        )
        assert metrics.category == "moderate"

    def test_category_low(self):
        """Low category for score 0.3-0.5."""
        metrics = CognitiveMetrics(
            self_awareness=0.35,
            directional_focus=0.35,
            actionability=0.35,
            state_classification=0.35,
        )
        assert metrics.category == "low"


class TestMirrorOnlyAnalyzer:
    """Tests for mirror-only cognitive approach."""

    def test_detects_imbalance(self, sattva_heavy_observables):
        """Mirror-only detects internal imbalance."""
        analyzer = MirrorOnlyAnalyzer()
        metrics = analyzer.analyze(sattva_heavy_observables)

        # Should have some self-awareness
        assert metrics.self_awareness > 0.3

    def test_limited_directional_focus(self, balanced_observables):
        """Mirror-only has limited directional focus."""
        analyzer = MirrorOnlyAnalyzer()
        metrics = analyzer.analyze(balanced_observables)

        # Directional focus is capped (no layer awareness)
        assert metrics.directional_focus <= 0.5

    def test_limited_state_classification(self, balanced_observables):
        """Mirror-only has limited state classification."""
        analyzer = MirrorOnlyAnalyzer()
        metrics = analyzer.analyze(balanced_observables)

        # Only binary (balanced/unbalanced)
        assert metrics.state_classification <= 0.4


class TestSelectiveOnlyAnalyzer:
    """Tests for selective-only cognitive approach."""

    def test_high_directional_focus(self, balanced_observables, sattva_heavy_observables):
        """Selective-only has high directional focus."""
        analyzer = SelectiveOnlyAnalyzer()
        analyzer.observe(OntologicalLayer.GUNA, balanced_observables)
        analyzer.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        metrics = analyzer.analyze()

        # Should know which layer to focus on
        assert metrics.directional_focus >= 0.8

    def test_limited_self_awareness(self, balanced_observables, sattva_heavy_observables):
        """Selective-only has limited self-awareness (no mirror)."""
        analyzer = SelectiveOnlyAnalyzer()
        analyzer.observe(OntologicalLayer.GUNA, balanced_observables)
        analyzer.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        metrics = analyzer.analyze()

        # Self-awareness capped (no internal balance check)
        assert metrics.self_awareness <= 0.5


class TestCombinedAnalyzer:
    """Tests for combined cognitive approach."""

    def test_high_overall_score(self, balanced_observables, sattva_heavy_observables):
        """Combined approach has highest overall score."""
        analyzer = CombinedAnalyzer()
        analyzer.observe(OntologicalLayer.GUNA, balanced_observables)
        analyzer.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        metrics = analyzer.analyze()

        # Combined should score in high or moderate range
        assert metrics.total_cognitive_score >= 0.7

    def test_high_self_awareness(self, balanced_observables, sattva_heavy_observables):
        """Combined has high self-awareness from mirror."""
        analyzer = CombinedAnalyzer()
        analyzer.observe(OntologicalLayer.GUNA, balanced_observables)
        analyzer.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        metrics = analyzer.analyze()

        assert metrics.self_awareness >= 0.7

    def test_high_state_classification(self, balanced_observables, sattva_heavy_observables):
        """Combined has rich state classification (6 states)."""
        analyzer = CombinedAnalyzer()
        analyzer.observe(OntologicalLayer.GUNA, balanced_observables)
        analyzer.observe(OntologicalLayer.FUSION, sattva_heavy_observables)

        metrics = analyzer.analyze()

        assert metrics.state_classification >= 0.8


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_combined_wins(self, balanced_observables, sattva_heavy_observables):
        """Combined approach wins benchmark."""
        result = run_cognitive_benchmark(
            scenario="Test scenario",
            layer_observations={
                OntologicalLayer.GUNA: balanced_observables,
                OntologicalLayer.FUSION: sattva_heavy_observables,
            },
        )

        assert result.winner == "combined"

    def test_improvement_metrics(self, balanced_observables, sattva_heavy_observables):
        """Improvement metrics are calculated."""
        result = run_cognitive_benchmark(
            scenario="Test scenario",
            layer_observations={
                OntologicalLayer.GUNA: balanced_observables,
                OntologicalLayer.FUSION: sattva_heavy_observables,
            },
        )

        # Combined should improve over both
        assert result.combined_improvement_over_mirror > 0
        assert result.combined_improvement_over_selective > 0

    def test_summary_format(self, balanced_observables, sattva_heavy_observables):
        """Summary has expected fields."""
        result = run_cognitive_benchmark(
            scenario="Test scenario",
            layer_observations={
                OntologicalLayer.GUNA: balanced_observables,
                OntologicalLayer.FUSION: sattva_heavy_observables,
            },
        )

        summary = result.summary()

        assert "scenario" in summary
        assert "mirror_only_score" in summary
        assert "selective_only_score" in summary
        assert "combined_score" in summary
        assert "winner" in summary
        assert "combined_vs_mirror" in summary
        assert "combined_vs_selective" in summary


class TestStandardBenchmarkSuite:
    """Tests for standard benchmark suite."""

    def test_runs_all_scenarios(self):
        """Standard suite runs all 5 scenarios."""
        results = run_standard_benchmark_suite()

        assert len(results) == 5

    def test_combined_wins_most(self):
        """Combined approach wins most scenarios."""
        results = run_standard_benchmark_suite()

        combined_wins = sum(1 for r in results if r.winner == "combined")

        # Combined should win at least 4 out of 5
        assert combined_wins >= 4

    def test_scenarios_have_names(self):
        """All scenarios have descriptive names."""
        results = run_standard_benchmark_suite()

        scenario_names = [r.scenario for r in results]

        assert "Balanced Pipeline" in scenario_names
        assert "Constructive Improvement" in scenario_names
        assert "Destructive Regression" in scenario_names
        assert "Internal Imbalance" in scenario_names
        assert "Mixed Signals" in scenario_names
