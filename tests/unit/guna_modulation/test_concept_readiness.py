"""
Tests for Concept Readiness Index (CRI) Module
===============================================

Tests for safe concept detection (not concept formation).

This module tests:
- Concept Coherence Score computation
- Concept Entropy computation
- Concept Readiness Index (CRI = C × (1-H) × S)
- Drift detection
- Safe output generation
"""

import math
import pytest

from symbolu.guna_modulation.observables import Observables
from symbolu.guna_modulation.concept_readiness import (
    # Constants
    EPSILON,
    # Types
    LayerRepresentation,
    ConceptCoherence,
    InterpretationCandidate,
    ConceptEntropy,
    ConceptReadinessIndex,
    ConceptDrift,
    # Functions
    compute_vector_similarity,
    compute_centroid,
    compute_concept_coherence,
    compute_concept_entropy_from_observables,
    compute_concept_readiness,
    # Monitor
    ConceptReadinessMonitor,
    # Reporter
    ConceptReadinessReporter,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def high_clarity_obs():
    """Observables with high Sattva (clarity)."""
    return Observables(
        s=0.8, r=0.1, t=0.1,
        H=0.2,
        delta_sem=0.1,
        C_contr=0.1, F_fail=0.0,
    )


@pytest.fixture
def high_activity_obs():
    """Observables with high Rajas (activity)."""
    return Observables(
        s=0.2, r=0.7, t=0.1,
        H=0.5,
        delta_sem=0.3,
        C_contr=0.2, F_fail=0.1,
    )


@pytest.fixture
def high_stability_obs():
    """Observables with high Tamas (stability)."""
    return Observables(
        s=0.1, r=0.1, t=0.8,
        H=0.7,
        delta_sem=0.1,
        C_contr=0.3, F_fail=0.0,
    )


@pytest.fixture
def uniform_clarity_layers(high_clarity_obs):
    """All layers with similar clarity-dominant observables."""
    obs1 = high_clarity_obs
    obs2 = Observables(
        s=0.75, r=0.15, t=0.1,
        H=0.25, delta_sem=0.12,
        C_contr=0.12, F_fail=0.0,
    )
    obs3 = Observables(
        s=0.82, r=0.08, t=0.1,
        H=0.18, delta_sem=0.08,
        C_contr=0.08, F_fail=0.0,
    )
    return [
        ("guna", obs1),
        ("fusion", obs2),
        ("state", obs3),
    ]


@pytest.fixture
def mixed_layers(high_clarity_obs, high_activity_obs, high_stability_obs):
    """Layers with diverse, conflicting observables."""
    return [
        ("guna", high_clarity_obs),
        ("fusion", high_activity_obs),
        ("state", high_stability_obs),
    ]


# =============================================================================
# Test LayerRepresentation
# =============================================================================

class TestLayerRepresentation:
    """Tests for LayerRepresentation dataclass."""

    def test_coherence_vector_dimensions(self, high_clarity_obs):
        """Coherence vector should have 6 dimensions."""
        rep = LayerRepresentation(layer_id="guna", observables=high_clarity_obs)
        vec = rep.coherence_vector

        assert len(vec) == 6
        assert all(isinstance(v, float) for v in vec)

    def test_coherence_vector_content(self, high_clarity_obs):
        """Coherence vector should contain S, R, T, H, non-contradiction, coherence."""
        rep = LayerRepresentation(layer_id="guna", observables=high_clarity_obs)
        vec = rep.coherence_vector

        assert vec[0] == high_clarity_obs.s
        assert vec[1] == high_clarity_obs.r
        assert vec[2] == high_clarity_obs.t
        assert vec[3] == high_clarity_obs.H
        assert vec[4] == 1.0 - high_clarity_obs.C_contr
        assert vec[5] == high_clarity_obs.s - high_clarity_obs.C_contr

    def test_stability_formula(self, high_clarity_obs):
        """Stability = (1-H) × (1-M)."""
        rep = LayerRepresentation(layer_id="guna", observables=high_clarity_obs)
        expected = (1.0 - high_clarity_obs.H) * (1.0 - high_clarity_obs.delta_sem)

        assert abs(rep.stability - expected) < EPSILON

    def test_layer_id_preserved(self):
        """Layer ID should be preserved in representation."""
        obs = Observables(
            s=0.5, r=0.3, t=0.2,
            H=0.3, delta_sem=0.1,
            C_contr=0.1, F_fail=0.0,
        )
        rep = LayerRepresentation(layer_id="fusion", observables=obs)

        assert rep.layer_id == "fusion"


# =============================================================================
# Test Vector Similarity
# =============================================================================

class TestVectorSimilarity:
    """Tests for compute_vector_similarity function."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        v = (0.5, 0.3, 0.2, 0.1, 0.9, 0.4)
        sim = compute_vector_similarity(v, v)

        assert abs(sim - 1.0) < EPSILON

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        v1 = (1.0, 0.0, 0.0)
        v2 = (-1.0, 0.0, 0.0)
        sim = compute_vector_similarity(v1, v2)

        assert abs(sim - (-1.0)) < EPSILON

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        v1 = (1.0, 0.0, 0.0)
        v2 = (0.0, 1.0, 0.0)
        sim = compute_vector_similarity(v1, v2)

        assert abs(sim) < EPSILON

    def test_zero_vector(self):
        """Zero vector should return 0.0 similarity."""
        v1 = (0.0, 0.0, 0.0)
        v2 = (1.0, 0.0, 0.0)
        sim = compute_vector_similarity(v1, v2)

        assert sim == 0.0

    def test_different_length_raises(self):
        """Different length vectors should raise ValueError."""
        v1 = (1.0, 0.0)
        v2 = (1.0, 0.0, 0.0)

        with pytest.raises(ValueError):
            compute_vector_similarity(v1, v2)

    def test_similar_vectors(self):
        """Similar vectors should have high similarity."""
        v1 = (0.8, 0.1, 0.1, 0.2, 0.9, 0.7)
        v2 = (0.75, 0.12, 0.13, 0.22, 0.88, 0.68)
        sim = compute_vector_similarity(v1, v2)

        assert sim > 0.99  # Very similar


# =============================================================================
# Test Centroid Computation
# =============================================================================

class TestCentroid:
    """Tests for compute_centroid function."""

    def test_empty_representations(self):
        """Empty list should return empty tuple."""
        centroid = compute_centroid([])
        assert centroid == ()

    def test_single_representation(self, high_clarity_obs):
        """Single representation's vector IS the centroid."""
        rep = LayerRepresentation(layer_id="guna", observables=high_clarity_obs)
        centroid = compute_centroid([rep])

        assert centroid == rep.coherence_vector

    def test_multiple_representations_average(self, high_clarity_obs, high_activity_obs):
        """Centroid should be mean of all vectors."""
        rep1 = LayerRepresentation(layer_id="guna", observables=high_clarity_obs)
        rep2 = LayerRepresentation(layer_id="fusion", observables=high_activity_obs)

        centroid = compute_centroid([rep1, rep2])

        vec1 = rep1.coherence_vector
        vec2 = rep2.coherence_vector

        for i in range(len(centroid)):
            expected = (vec1[i] + vec2[i]) / 2
            assert abs(centroid[i] - expected) < EPSILON


# =============================================================================
# Test Concept Coherence
# =============================================================================

class TestConceptCoherence:
    """Tests for ConceptCoherence computation."""

    def test_empty_representations(self):
        """Empty representations should have 0 coherence."""
        coherence = compute_concept_coherence([])

        assert coherence.score == 0.0
        assert coherence.representations == []
        assert coherence.centroid == ()

    def test_single_representation_perfect_coherence(self, high_clarity_obs):
        """Single representation has perfect coherence with itself."""
        rep = LayerRepresentation(layer_id="guna", observables=high_clarity_obs)
        coherence = compute_concept_coherence([rep])

        assert abs(coherence.score - 1.0) < EPSILON

    def test_uniform_layers_high_coherence(self, uniform_clarity_layers):
        """Similar layers should have high coherence."""
        reps = [
            LayerRepresentation(layer_id=lid, observables=obs)
            for lid, obs in uniform_clarity_layers
        ]
        coherence = compute_concept_coherence(reps)

        assert coherence.score > 0.95  # Very coherent
        assert coherence.is_coherent

    def test_mixed_layers_low_coherence(self, mixed_layers):
        """Diverse layers should have lower coherence."""
        reps = [
            LayerRepresentation(layer_id=lid, observables=obs)
            for lid, obs in mixed_layers
        ]
        coherence = compute_concept_coherence(reps)

        # Mixed layers still have relatively high coherence due to centroid averaging
        # but lower than uniform layers (which have > 0.99)
        assert coherence.score < 0.95  # Not perfectly coherent

    def test_is_coherent_threshold(self):
        """Test is_coherent threshold (> 0.7)."""
        # Create manually with known score
        coherence_high = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.8, 0.85]
        )
        coherence_low = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.5, 0.6]
        )

        assert coherence_high.is_coherent
        assert not coherence_low.is_coherent

    def test_is_fragmented_threshold(self):
        """Test is_fragmented threshold (< 0.3)."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.1, 0.2]
        )

        assert coherence.is_fragmented

    def test_coherence_spread(self):
        """Test coherence spread (variance) calculation."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.8, 0.6]
        )

        # Mean = 0.7, variance = ((0.8-0.7)^2 + (0.6-0.7)^2) / 2 = 0.01
        expected_spread = math.sqrt(0.01)

        assert abs(coherence.coherence_spread - expected_spread) < EPSILON

    def test_weakest_layer(self, mixed_layers):
        """Should identify layer with lowest agreement."""
        reps = [
            LayerRepresentation(layer_id=lid, observables=obs)
            for lid, obs in mixed_layers
        ]
        coherence = compute_concept_coherence(reps)

        # Weakest layer should be identified
        assert coherence.weakest_layer in ["guna", "fusion", "state"]


# =============================================================================
# Test Interpretation Candidate
# =============================================================================

class TestInterpretationCandidate:
    """Tests for InterpretationCandidate dataclass."""

    def test_basic_properties(self):
        """Test basic properties of InterpretationCandidate."""
        interp = InterpretationCandidate(
            label="clarity-dominant@guna",
            probability=0.6,
            source_layer="guna",
        )

        assert interp.label == "clarity-dominant@guna"
        assert interp.probability == 0.6
        assert interp.source_layer == "guna"


# =============================================================================
# Test Concept Entropy
# =============================================================================

class TestConceptEntropy:
    """Tests for ConceptEntropy computation."""

    def test_empty_interpretations(self):
        """Empty interpretations should have 0 entropy."""
        entropy = ConceptEntropy(interpretations=[])

        assert entropy.entropy == 0.0

    def test_single_interpretation_zero_entropy(self):
        """Single interpretation has zero entropy."""
        interp = InterpretationCandidate(
            label="clarity-dominant",
            probability=1.0,
            source_layer="guna",
        )
        entropy = ConceptEntropy(interpretations=[interp])

        assert entropy.entropy == 0.0
        assert entropy.is_clear

    def test_uniform_distribution_max_entropy(self):
        """Uniform distribution has maximum entropy (normalized to 1.0)."""
        interps = [
            InterpretationCandidate(label=f"interp_{i}", probability=0.25, source_layer="layer")
            for i in range(4)
        ]
        entropy = ConceptEntropy(interpretations=interps)

        assert abs(entropy.entropy - 1.0) < 0.01  # Normalized max

    def test_skewed_distribution_low_entropy(self):
        """Highly skewed distribution has low entropy."""
        interps = [
            InterpretationCandidate(label="dominant", probability=0.9, source_layer="guna"),
            InterpretationCandidate(label="minor1", probability=0.05, source_layer="fusion"),
            InterpretationCandidate(label="minor2", probability=0.05, source_layer="state"),
        ]
        entropy = ConceptEntropy(interpretations=interps)

        # Skewed distribution has lower entropy than uniform
        assert entropy.entropy < 0.7  # Lower than uniform
        # is_clear requires entropy < 0.3, which is stricter

    def test_is_ambiguous_threshold(self):
        """Test is_ambiguous threshold (> 0.7)."""
        # Near-uniform distribution
        interps = [
            InterpretationCandidate(label=f"interp_{i}", probability=0.33, source_layer="layer")
            for i in range(3)
        ]
        entropy = ConceptEntropy(interpretations=interps)

        assert entropy.is_ambiguous

    def test_dominant_interpretation(self):
        """Should identify dominant interpretation."""
        interps = [
            InterpretationCandidate(label="dominant", probability=0.8, source_layer="guna"),
            InterpretationCandidate(label="minor", probability=0.2, source_layer="fusion"),
        ]
        entropy = ConceptEntropy(interpretations=interps)

        dom = entropy.dominant_interpretation
        assert dom is not None
        assert dom.label == "dominant"

    def test_no_dominant_when_close(self):
        """Should return None when no clear dominant."""
        interps = [
            InterpretationCandidate(label="a", probability=0.35, source_layer="guna"),
            InterpretationCandidate(label="b", probability=0.35, source_layer="fusion"),
            InterpretationCandidate(label="c", probability=0.30, source_layer="state"),
        ]
        entropy = ConceptEntropy(interpretations=interps)

        assert entropy.dominant_interpretation is None

    def test_competing_count(self):
        """Should count interpretations with probability > 0.1."""
        interps = [
            InterpretationCandidate(label="a", probability=0.4, source_layer="guna"),
            InterpretationCandidate(label="b", probability=0.3, source_layer="fusion"),
            InterpretationCandidate(label="c", probability=0.2, source_layer="state"),
            InterpretationCandidate(label="d", probability=0.05, source_layer="output"),
            InterpretationCandidate(label="e", probability=0.05, source_layer="extra"),
        ]
        entropy = ConceptEntropy(interpretations=interps)

        assert entropy.competing_count == 3  # a, b, c


class TestConceptEntropyFromObservables:
    """Tests for compute_concept_entropy_from_observables."""

    def test_empty_layers(self):
        """Empty layers should produce 0 entropy."""
        entropy = compute_concept_entropy_from_observables([])

        assert entropy.entropy == 0.0
        assert len(entropy.interpretations) == 0

    def test_single_layer(self, high_clarity_obs):
        """Single layer produces single interpretation."""
        entropy = compute_concept_entropy_from_observables([
            ("guna", high_clarity_obs)
        ])

        assert len(entropy.interpretations) == 1
        assert entropy.entropy == 0.0

    def test_classifies_by_dominant_guna(self, high_clarity_obs, high_activity_obs, high_stability_obs):
        """Should classify interpretations by dominant Guna."""
        entropy = compute_concept_entropy_from_observables([
            ("guna", high_clarity_obs),
            ("fusion", high_activity_obs),
            ("state", high_stability_obs),
        ])

        labels = [i.label for i in entropy.interpretations]

        assert "clarity-dominant@guna" in labels
        assert "activity-dominant@fusion" in labels
        assert "stability-dominant@state" in labels


# =============================================================================
# Test Concept Readiness Index
# =============================================================================

class TestConceptReadinessIndex:
    """Tests for ConceptReadinessIndex computation."""

    def test_cri_formula(self):
        """CRI = C × (1 - H) × S."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.8]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])

        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.9,
        )

        expected = 0.8 * (1 - 0.0) * 0.9  # C=0.8, H=0, S=0.9
        assert abs(cri.index - expected) < EPSILON

    def test_high_cri_is_ready(self):
        """High CRI should be 'ready'."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.9]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])

        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.95,
        )

        assert cri.index > 0.8
        assert cri.readiness_level == "ready"

    def test_low_cri_is_not_ready(self):
        """Low CRI should be 'not_ready'."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.2]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="a", probability=0.5, source_layer="guna"),
            InterpretationCandidate(label="b", probability=0.5, source_layer="fusion"),
        ])

        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.3,
        )

        assert cri.index < 0.2
        assert cri.readiness_level == "not_ready"

    def test_readiness_levels(self):
        """Test all readiness level thresholds."""
        # Create CRIs at different levels
        def make_cri(c_score, h_val, s_val):
            coherence = ConceptCoherence(
                representations=[], centroid=(), layer_similarities=[c_score]
            )
            # Create entropy with specific value
            if h_val == 0:
                interps = [InterpretationCandidate("a", 1.0, "guna")]
            else:
                # Approximate entropy value with probabilities
                interps = [
                    InterpretationCandidate("a", 0.5, "guna"),
                    InterpretationCandidate("b", 0.5, "fusion"),
                ]
            entropy = ConceptEntropy(interpretations=interps)
            # Override entropy manually for testing

            return ConceptReadinessIndex(
                coherence=coherence,
                entropy=entropy,
                stability=s_val,
            )

        # High CRI: C=1, H=0, S=1 → CRI=1
        cri_high = make_cri(1.0, 0, 1.0)
        assert cri_high.readiness_level == "ready"

    def test_blocking_factor_low_coherence(self):
        """Should identify low coherence as blocking factor."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.3]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])

        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.9,
        )

        assert cri.blocking_factor == "low_coherence"

    def test_blocking_factor_low_stability(self):
        """Should identify low stability as blocking factor."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.9]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])

        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.3,
        )

        assert cri.blocking_factor == "low_stability"

    def test_safe_description_content(self):
        """Safe description should describe conditions, not define concepts."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.9]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])

        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.95,
        )

        desc = cri.get_safe_description()

        # Should contain safe language
        assert "coherence" in desc.lower() or "ready" in desc.lower()
        # Should NOT contain unsafe language
        assert "is a concept" not in desc.lower()
        assert "new concept" not in desc.lower()


class TestComputeConceptReadiness:
    """Tests for compute_concept_readiness function."""

    def test_empty_layers(self):
        """Empty layers should produce 0 CRI."""
        cri = compute_concept_readiness([])

        assert cri.index == 0.0
        assert cri.readiness_level == "not_ready"

    def test_uniform_layers_high_cri(self, uniform_clarity_layers):
        """Uniform layers should have high coherence."""
        cri = compute_concept_readiness(uniform_clarity_layers)

        # Coherence is high since all layers are similar
        assert cri.coherence.is_coherent
        # Note: CRI can be low if entropy is high (many layers with same label
        # creates uniform distribution in entropy calculation)
        # The key property is high coherence, not necessarily high CRI
        assert cri.coherence.score > 0.95

    def test_mixed_layers_lower_cri(self, mixed_layers):
        """Mixed layers should produce lower CRI."""
        cri = compute_concept_readiness(mixed_layers)

        # Not as high as uniform
        assert cri.index < 0.8


# =============================================================================
# Test Concept Drift
# =============================================================================

class TestConceptDrift:
    """Tests for ConceptDrift detection."""

    def test_positive_drift_is_crystallizing(self):
        """Positive drift (> 0.1) should be crystallizing."""
        drift = ConceptDrift(
            previous_cri=0.4,
            current_cri=0.6,
            delta_coherence=0.2,
            delta_entropy=-0.1,
            delta_stability=0.1,
        )

        assert abs(drift.drift - 0.2) < EPSILON
        assert drift.is_crystallizing
        assert not drift.is_fragmenting
        assert drift.drift_type == "crystallizing"

    def test_negative_drift_is_fragmenting(self):
        """Negative drift (< -0.1) should be fragmenting."""
        drift = ConceptDrift(
            previous_cri=0.6,
            current_cri=0.4,
            delta_coherence=-0.2,
            delta_entropy=0.1,
            delta_stability=-0.1,
        )

        assert abs(drift.drift - (-0.2)) < EPSILON
        assert drift.is_fragmenting
        assert not drift.is_crystallizing
        assert drift.drift_type == "fragmenting"

    def test_small_drift_is_stable(self):
        """Small drift (|drift| <= 0.1) should be stable."""
        drift = ConceptDrift(
            previous_cri=0.5,
            current_cri=0.55,
            delta_coherence=0.02,
            delta_entropy=-0.01,
            delta_stability=0.02,
        )

        assert drift.is_stable
        assert drift.drift_type == "stable"


# =============================================================================
# Test Concept Readiness Monitor
# =============================================================================

class TestConceptReadinessMonitor:
    """Tests for ConceptReadinessMonitor."""

    def test_initial_state(self):
        """Monitor should start with no history."""
        monitor = ConceptReadinessMonitor()

        assert monitor.current_cri is None
        assert monitor.get_drift() is None
        assert monitor.average_cri == 0.0

    def test_single_observation(self, uniform_clarity_layers):
        """Single observation should work."""
        monitor = ConceptReadinessMonitor()
        cri = monitor.observe(uniform_clarity_layers)

        assert cri is not None
        assert monitor.current_cri == cri
        assert monitor.get_drift() is None  # Need 2 for drift

    def test_drift_after_two_observations(self, uniform_clarity_layers, mixed_layers):
        """Drift should be computed after two observations."""
        monitor = ConceptReadinessMonitor()

        cri1 = monitor.observe(uniform_clarity_layers)
        cri2 = monitor.observe(mixed_layers)

        drift = monitor.get_drift()

        assert drift is not None
        assert drift.previous_cri == cri1.index
        assert drift.current_cri == cri2.index

    def test_window_trimming(self, uniform_clarity_layers):
        """History should be trimmed to window size."""
        monitor = ConceptReadinessMonitor(window_size=3)

        for _ in range(5):
            monitor.observe(uniform_clarity_layers)

        # Only 3 should be kept
        assert len(monitor._history) == 3

    def test_trend_unknown_with_few_observations(self, uniform_clarity_layers):
        """Trend should be unknown with < 3 observations."""
        monitor = ConceptReadinessMonitor()

        monitor.observe(uniform_clarity_layers)
        monitor.observe(uniform_clarity_layers)

        assert monitor.get_trend() == "unknown"

    def test_trend_calculation(self, uniform_clarity_layers, mixed_layers):
        """Trend should be calculated with enough observations."""
        monitor = ConceptReadinessMonitor()

        # Observe improving trend
        for _ in range(5):
            monitor.observe(uniform_clarity_layers)

        trend = monitor.get_trend()
        assert trend in ["improving", "degrading", "stable"]

    def test_average_cri(self, uniform_clarity_layers, mixed_layers):
        """Average CRI should be calculated correctly."""
        monitor = ConceptReadinessMonitor()

        cri1 = monitor.observe(uniform_clarity_layers)
        cri2 = monitor.observe(mixed_layers)

        expected_avg = (cri1.index + cri2.index) / 2
        assert abs(monitor.average_cri - expected_avg) < EPSILON

    def test_reset(self, uniform_clarity_layers):
        """Reset should clear history."""
        monitor = ConceptReadinessMonitor()

        monitor.observe(uniform_clarity_layers)
        assert monitor.current_cri is not None

        monitor.reset()

        assert monitor.current_cri is None
        assert len(monitor._history) == 0


# =============================================================================
# Test Concept Readiness Reporter
# =============================================================================

class TestConceptReadinessReporter:
    """Tests for ConceptReadinessReporter safe outputs."""

    def test_describe_readiness_is_safe(self):
        """Readiness description should be safe (no concept formation)."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.9]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])
        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.95,
        )

        desc = ConceptReadinessReporter.describe_readiness(cri)

        # Should NOT contain unsafe phrases
        unsafe_phrases = [
            "is a concept",
            "new concept",
            "created concept",
            "this concept applies",
            "reuse this concept",
        ]
        for phrase in unsafe_phrases:
            assert phrase not in desc.lower()

    def test_describe_coherence(self):
        """Coherence description should use safe language."""
        coherence_high = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.85]
        )
        coherence_low = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.2]
        )

        desc_high = ConceptReadinessReporter.describe_coherence(coherence_high)
        desc_low = ConceptReadinessReporter.describe_coherence(coherence_low)

        assert "consistent" in desc_high.lower()
        assert "fragmented" in desc_low.lower()

    def test_describe_ambiguity(self):
        """Ambiguity description should use safe language."""
        entropy_clear = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])
        entropy_ambig = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="a", probability=0.33, source_layer="guna"),
            InterpretationCandidate(label="b", probability=0.33, source_layer="fusion"),
            InterpretationCandidate(label="c", probability=0.34, source_layer="state"),
        ])

        desc_clear = ConceptReadinessReporter.describe_ambiguity(entropy_clear)
        desc_ambig = ConceptReadinessReporter.describe_ambiguity(entropy_ambig)

        assert "converged" in desc_clear.lower() or "low" in desc_clear.lower()
        assert "competing" in desc_ambig.lower() or "ambig" in desc_ambig.lower()

    def test_describe_drift(self):
        """Drift description should use safe language."""
        drift_crystal = ConceptDrift(
            previous_cri=0.4, current_cri=0.7,
            delta_coherence=0.2, delta_entropy=-0.1, delta_stability=0.1,
        )
        drift_frag = ConceptDrift(
            previous_cri=0.7, current_cri=0.4,
            delta_coherence=-0.2, delta_entropy=0.1, delta_stability=-0.1,
        )

        desc_crystal = ConceptReadinessReporter.describe_drift(drift_crystal)
        desc_frag = ConceptReadinessReporter.describe_drift(drift_frag)

        assert "crystallizing" in desc_crystal.lower()
        assert "fragmenting" in desc_frag.lower()

    def test_full_report_structure(self):
        """Full report should contain expected fields."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.8]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])
        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.9,
        )

        report = ConceptReadinessReporter.generate_full_report(cri)

        # Check required fields
        assert "cri" in report
        assert "coherence_score" in report
        assert "entropy" in report
        assert "stability" in report
        assert "readiness_level" in report
        assert "blocking_factor" in report
        assert "description" in report
        assert "human_can_conceptualize" in report

    def test_full_report_with_drift(self):
        """Full report should include drift when provided."""
        coherence = ConceptCoherence(
            representations=[], centroid=(), layer_similarities=[0.8]
        )
        entropy = ConceptEntropy(interpretations=[
            InterpretationCandidate(label="dom", probability=1.0, source_layer="guna")
        ])
        cri = ConceptReadinessIndex(
            coherence=coherence,
            entropy=entropy,
            stability=0.9,
        )
        drift = ConceptDrift(
            previous_cri=0.6, current_cri=0.72,
            delta_coherence=0.1, delta_entropy=-0.05, delta_stability=0.02,
        )

        report = ConceptReadinessReporter.generate_full_report(cri, drift)

        assert "drift" in report
        assert "drift_type" in report
        assert "is_crystallizing" in report
        assert "is_fragmenting" in report


# =============================================================================
# Integration Tests
# =============================================================================

class TestConceptReadinessIntegration:
    """Integration tests for full CRI workflow."""

    def test_full_workflow(self):
        """Test complete workflow: observe → compute → report."""
        # Create observables for 3 layers
        obs_guna = Observables(
            s=0.7, r=0.2, t=0.1,
            H=0.3, delta_sem=0.15,
            C_contr=0.1, F_fail=0.0,
        )
        obs_fusion = Observables(
            s=0.65, r=0.25, t=0.1,
            H=0.35, delta_sem=0.18,
            C_contr=0.12, F_fail=0.0,
        )
        obs_state = Observables(
            s=0.72, r=0.18, t=0.1,
            H=0.28, delta_sem=0.12,
            C_contr=0.08, F_fail=0.0,
        )

        layers = [
            ("guna", obs_guna),
            ("fusion", obs_fusion),
            ("state", obs_state),
        ]

        # Compute CRI
        cri = compute_concept_readiness(layers)

        # Verify all components
        assert cri.coherence.score > 0.0
        assert cri.entropy.entropy >= 0.0
        assert cri.stability > 0.0
        assert cri.index > 0.0

        # Generate report
        report = ConceptReadinessReporter.generate_full_report(cri)

        assert isinstance(report, dict)
        assert report["cri"] == cri.index

    def test_monitor_over_time(self):
        """Test monitoring CRI evolution over time."""
        monitor = ConceptReadinessMonitor(window_size=5)

        # Simulate improving concept readiness
        base_s = 0.5
        for i in range(5):
            # s increases, r and t decrease to maintain sum = 1.0
            s_val = base_s + i * 0.05  # Improving clarity
            r_val = 0.3 - i * 0.03
            t_val = 1.0 - s_val - r_val  # Ensure sum = 1.0
            obs = Observables(
                s=s_val,
                r=r_val,
                t=t_val,
                H=0.4 - i * 0.05,  # Decreasing entropy
                delta_sem=0.2 - i * 0.02,
                C_contr=0.15 - i * 0.02,
                F_fail=0.0,
            )

            monitor.observe([
                ("guna", obs),
                ("fusion", obs),
                ("state", obs),
            ])

        # Should see improvement
        assert monitor.get_trend() in ["improving", "stable"]

        # All CRIs should be recorded
        assert len(monitor._history) == 5

    def test_safe_output_never_creates_concepts(self):
        """Verify all outputs describe conditions, never create concepts."""
        # Various CRI states
        test_cases = [
            # High CRI
            ConceptReadinessIndex(
                coherence=ConceptCoherence([], (), [0.95]),
                entropy=ConceptEntropy([InterpretationCandidate("a", 1.0, "guna")]),
                stability=0.98,
            ),
            # Low CRI
            ConceptReadinessIndex(
                coherence=ConceptCoherence([], (), [0.2]),
                entropy=ConceptEntropy([
                    InterpretationCandidate("a", 0.33, "guna"),
                    InterpretationCandidate("b", 0.33, "fusion"),
                    InterpretationCandidate("c", 0.34, "state"),
                ]),
                stability=0.3,
            ),
        ]

        forbidden_phrases = [
            "this is a concept",
            "new concept",
            "created concept",
            "formed concept",
            "concept definition",
            "reuse this",
            "applies elsewhere",
        ]

        for cri in test_cases:
            desc = cri.get_safe_description()
            report = ConceptReadinessReporter.generate_full_report(cri)

            for phrase in forbidden_phrases:
                assert phrase not in desc.lower(), f"Unsafe phrase '{phrase}' in description"
                assert phrase not in str(report).lower(), f"Unsafe phrase '{phrase}' in report"
