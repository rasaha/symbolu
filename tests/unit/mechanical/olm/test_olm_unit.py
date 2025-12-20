"""
OLM Unit Tests

Tests for the Ontological Layer Mapper engine validating:
1. Normalization of layer_weights and anchor_scores
2. Dominant/suppressed layer separation
3. Execution vs governance profile computation
4. Entropy regime classification
5. Tension zone detection
6. Resolution constraint generation
7. Legacy aspect name conversion

5+5 Ontological Layer Architecture (Patent-Aligned):
- Lower 5 (O1-O5): Execution / Manifestation Layers
- Upper 5 (O6-O10): Governance / Coherence Layers
"""

import pytest
from symbolu.mechanical.olm.olm_engine import OLMEngine, get_olm_engine
from symbolu.mechanical.olm.models import (
    OLMInput,
    OntologicalLayerMap,
    LOWER_ONTOLOGICAL_LAYERS,
    UPPER_ONTOLOGICAL_LAYERS,
    LEGACY_ASPECT_TO_LAYER,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def engine() -> OLMEngine:
    """Create a fresh OLM engine for each test."""
    return OLMEngine(layer_threshold=0.10, tension_threshold=0.25)


@pytest.fixture
def basic_input() -> OLMInput:
    """Create a basic OLM input for testing using O1-O10 layer names."""
    return OLMInput(
        layer_weights={
            "O1_action": 0.20,
            "O2_tagging": 0.15,
            "O3_forming": 0.10,
            "O4_thinking": 0.10,
            "O5_directing": 0.05,
            "O6_reasoning": 0.10,
            "O7_purposing": 0.10,
            "O8_meta_observing": 0.08,
            "O9_unifying": 0.07,
            "O10_absolving": 0.05,
        },
        anchor_scores={
            "Needs": 0.4,
            "Exchange": 0.3,
            "Challenge": 0.1,
            "Belonging": 0.05,
            "Relation": 0.05,
            "Change": 0.03,
            "Meaning": 0.04,
            "Role": 0.02,
            "Collective": 0.01,
        },
        H_D=1.0,
        H_G=0.5,
        H_K=0.8,
        domain="generic",
        tier="lower",
        flow_mode="outer_only",
    )


@pytest.fixture
def legacy_input() -> OLMInput:
    """Create an OLM input using legacy aspect names for conversion testing."""
    return OLMInput(
        layer_weights={
            "Execution": 0.30,
            "Identity": 0.20,
            "Form": 0.10,
            "Cognition": 0.10,
            "Agency": 0.05,
            "Reasoning": 0.10,
            "Purpose": 0.05,
            "Observation": 0.05,
            "Core": 0.03,
            "Universal": 0.02,
        },
        anchor_scores={
            "Needs": 0.5,
            "Exchange": 0.3,
            "Challenge": 0.2,
        },
        H_D=1.0,
        H_G=0.5,
        H_K=0.8,
        domain="task",
        tier="lower",
        flow_mode="outer_only",
    )


# =============================================================================
# NORMALIZATION TESTS
# =============================================================================


class TestNormalization:
    """Tests for layer weight normalization."""

    def test_layer_weights_normalized_to_sum_one(self, engine: OLMEngine) -> None:
        """Layer weights should be normalized to sum to 1.0."""
        probs = {"O1_action": 0.3, "O2_tagging": 0.5, "O3_forming": 0.2}
        normalized = engine._normalize_probs(probs)

        assert abs(sum(normalized.values()) - 1.0) < 1e-10
        assert normalized["O1_action"] == pytest.approx(0.3, abs=1e-10)
        assert normalized["O2_tagging"] == pytest.approx(0.5, abs=1e-10)
        assert normalized["O3_forming"] == pytest.approx(0.2, abs=1e-10)

    def test_unnormalized_weights_get_normalized(self, engine: OLMEngine) -> None:
        """Weights that don't sum to 1 should be normalized."""
        probs = {"O1_action": 2.0, "O2_tagging": 3.0, "O3_forming": 5.0}  # Sum = 10
        normalized = engine._normalize_probs(probs)

        assert abs(sum(normalized.values()) - 1.0) < 1e-10
        assert normalized["O1_action"] == pytest.approx(0.2, abs=1e-10)
        assert normalized["O2_tagging"] == pytest.approx(0.3, abs=1e-10)
        assert normalized["O3_forming"] == pytest.approx(0.5, abs=1e-10)

    def test_empty_weights_returns_empty(self, engine: OLMEngine) -> None:
        """Empty weight dict should return empty dict."""
        normalized = engine._normalize_probs({})
        assert normalized == {}

    def test_all_zero_weights_uniform_distribution(self, engine: OLMEngine) -> None:
        """All-zero weights should become uniform distribution."""
        probs = {"O1_action": 0.0, "O2_tagging": 0.0, "O3_forming": 0.0}
        normalized = engine._normalize_probs(probs)

        assert abs(sum(normalized.values()) - 1.0) < 1e-10
        assert all(v == pytest.approx(1.0 / 3, abs=1e-10) for v in normalized.values())

    def test_negative_values_clamped_to_zero(self, engine: OLMEngine) -> None:
        """Negative weight values should be clamped to 0."""
        probs = {"O1_action": -0.5, "O2_tagging": 0.5, "O3_forming": 0.5}
        normalized = engine._normalize_probs(probs)

        assert normalized["O1_action"] == 0.0
        assert abs(sum(normalized.values()) - 1.0) < 1e-10


# =============================================================================
# LEGACY ASPECT CONVERSION TESTS
# =============================================================================


class TestLegacyAspectConversion:
    """Tests for legacy aspect name to O1-O10 layer conversion."""

    def test_legacy_aspects_converted_correctly(self, engine: OLMEngine, legacy_input: OLMInput) -> None:
        """Legacy aspect names should be converted to O1-O10 layer names."""
        olm_map = engine.build_map(legacy_input)

        # Should have ontological layer names in output
        assert olm_map.tier == "lower"
        assert olm_map.domain == "task"
        # Dominant layers should use O1-O10 nomenclature
        for layer in olm_map.dominant_layers:
            assert layer.startswith("O") or layer in LEGACY_ASPECT_TO_LAYER.values()

    def test_all_legacy_aspects_map_correctly(self, engine: OLMEngine) -> None:
        """All legacy aspect names should map to correct O1-O10 layers."""
        expected_mappings = {
            "Execution": "O1_action",
            "Identity": "O2_tagging",
            "Form": "O3_forming",
            "Cognition": "O4_thinking",
            "Agency": "O5_directing",
            "Reasoning": "O6_reasoning",
            "Purpose": "O7_purposing",
            "Observation": "O8_meta_observing",
            "Core": "O9_unifying",
            "Universal": "O10_absolving",
        }

        legacy_weights = {k: 0.1 for k in expected_mappings.keys()}
        converted = engine._convert_legacy_aspects(legacy_weights)

        for legacy, ontological in expected_mappings.items():
            assert ontological in converted
            assert converted[ontological] == 0.1


# =============================================================================
# LAYER CLASSIFICATION TESTS
# =============================================================================


class TestLayerClassification:
    """Tests for dominant/suppressed layer classification."""

    def test_dominant_layer_appears_first(self, engine: OLMEngine) -> None:
        """Layer with highest weight should appear first in dominant list."""
        olm_input = OLMInput(
            layer_weights={
                "O1_action": 0.6,
                "O2_tagging": 0.05,
                "O3_forming": 0.05,
                "O7_purposing": 0.3,
            },
            anchor_scores={"Needs": 0.5, "Exchange": 0.3, "Challenge": 0.2},
            H_D=1.0,
            H_G=0.5,
            H_K=0.5,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        olm_map = engine.build_map(olm_input)

        assert olm_map.dominant_layers[0] == "O1_action"
        assert "O1_action" not in olm_map.suppressed_layers

    def test_low_weight_layers_are_suppressed(self, engine: OLMEngine) -> None:
        """Layers below threshold should be classified as suppressed."""
        olm_input = OLMInput(
            layer_weights={
                "O1_action": 0.8,
                "O2_tagging": 0.1,
                "O3_forming": 0.02,
                "O7_purposing": 0.02,
                "O10_absolving": 0.06,
            },
            anchor_scores={"Needs": 0.5},
            H_D=0.5,
            H_G=0.3,
            H_K=0.2,
            domain="code",
            tier="lower",
            flow_mode="outer_only",
        )

        olm_map = engine.build_map(olm_input)

        assert "O1_action" in olm_map.dominant_layers
        # Low weight layers should be suppressed
        low_weight_layers = ["O3_forming", "O7_purposing"]
        for layer in low_weight_layers:
            assert layer in olm_map.suppressed_layers


# =============================================================================
# LAYER BALANCE TESTS
# =============================================================================


class TestLayerBalance:
    """Tests for execution vs governance layer balance computation."""

    def test_execution_dominant_balance(self, engine: OLMEngine) -> None:
        """Execution-dominant profile should have balance > 0.5."""
        olm_input = OLMInput(
            layer_weights={
                "O1_action": 0.3,
                "O2_tagging": 0.2,
                "O3_forming": 0.2,
                "O4_thinking": 0.15,
                "O5_directing": 0.1,
                "O6_reasoning": 0.02,
                "O7_purposing": 0.02,
                "O10_absolving": 0.01,
            },
            anchor_scores={"Needs": 0.5, "Exchange": 0.5},
            H_D=0.5,
            H_G=0.3,
            H_K=0.3,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        olm_map = engine.build_map(olm_input)

        assert olm_map.layer_balance > 0.7
        assert "execution_layer_dominant" in olm_map.resolution_constraints

    def test_governance_dominant_balance(self, engine: OLMEngine) -> None:
        """Governance-dominant profile should have balance < 0.3."""
        olm_input = OLMInput(
            layer_weights={
                "O1_action": 0.02,
                "O2_tagging": 0.03,
                "O6_reasoning": 0.2,
                "O7_purposing": 0.3,
                "O8_meta_observing": 0.2,
                "O9_unifying": 0.15,
                "O10_absolving": 0.1,
            },
            anchor_scores={"Meaning": 0.5, "Collective": 0.5},
            H_D=1.5,
            H_G=0.7,
            H_K=0.9,
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        olm_map = engine.build_map(olm_input)

        assert olm_map.layer_balance < 0.3
        assert "governance_layer_dominant" in olm_map.resolution_constraints


# =============================================================================
# ENTROPY REGIME TESTS
# =============================================================================


class TestEntropyRegime:
    """Tests for entropy regime classification."""

    def test_low_entropy_regime(self, engine: OLMEngine) -> None:
        """Low entropy values should result in 'low' regime."""
        olm_input = OLMInput(
            layer_weights={"O1_action": 0.9, "O3_forming": 0.1},
            anchor_scores={"Needs": 0.7, "Exchange": 0.3},
            H_D=0.3,
            H_G=0.2,
            H_K=0.2,
            domain="code",
            tier="lower",
            flow_mode="outer_only",
        )

        olm_map = engine.build_map(olm_input)

        assert olm_map.entropy_profile["regime"] == "low"
        assert olm_map.entropy_profile["entropy_mix"] < 0.33

    def test_high_entropy_regime(self, engine: OLMEngine) -> None:
        """High entropy values should result in 'high' regime."""
        olm_input = OLMInput(
            layer_weights={"O7_purposing": 0.5, "O10_absolving": 0.5},
            anchor_scores={"Meaning": 0.5, "Collective": 0.5},
            H_D=2.0,
            H_G=0.95,
            H_K=1.4,
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        olm_map = engine.build_map(olm_input)

        assert olm_map.entropy_profile["regime"] == "high"
        assert olm_map.entropy_profile["entropy_mix"] >= 0.66


# =============================================================================
# TENSION ZONE TESTS
# =============================================================================


class TestTensionZones:
    """Tests for ontological tension zone detection."""

    def test_execution_governance_gap_detected(self, engine: OLMEngine) -> None:
        """High execution without governance should trigger gap."""
        olm_input = OLMInput(
            layer_weights={
                "O1_action": 0.4,
                "O2_tagging": 0.3,
                "O3_forming": 0.25,
                "O6_reasoning": 0.02,
                "O7_purposing": 0.02,
                "O10_absolving": 0.01,
            },
            anchor_scores={"Needs": 0.7, "Exchange": 0.3},
            H_D=0.5,
            H_G=0.3,
            H_K=0.3,
            domain="task",
            tier="lower",
            flow_mode="outer_only",
        )

        olm_map = engine.build_map(olm_input)

        assert "execution_governance_gap" in olm_map.tension_zones

    def test_grounding_deficit_detected(self, engine: OLMEngine) -> None:
        """High governance without grounding should trigger deficit."""
        olm_input = OLMInput(
            layer_weights={
                "O1_action": 0.02,
                "O3_forming": 0.02,
                "O7_purposing": 0.4,
                "O8_meta_observing": 0.3,
                "O9_unifying": 0.2,
                "O10_absolving": 0.06,
            },
            anchor_scores={"Meaning": 0.5, "Collective": 0.5},
            H_D=1.8,
            H_G=0.85,
            H_K=1.1,
            domain="spiritual",
            tier="upper",
            flow_mode="inner_priority",
        )

        olm_map = engine.build_map(olm_input)

        assert "grounding_deficit" in olm_map.tension_zones
        assert "add_concrete_grounding" in olm_map.resolution_constraints


# =============================================================================
# RESOLUTION CONSTRAINT TESTS
# =============================================================================


class TestResolutionConstraints:
    """Tests for resolution constraint generation."""

    def test_upper_tier_constraints(self, engine: OLMEngine) -> None:
        """Upper tier should generate appropriate constraints."""
        olm_input = OLMInput(
            layer_weights={"O7_purposing": 0.7, "O10_absolving": 0.3},
            anchor_scores={"Meaning": 0.6, "Collective": 0.4},
            H_D=1.5,
            H_G=0.7,
            H_K=0.8,
            domain="philosophy",
            tier="upper",
            flow_mode="inner_priority",
        )

        olm_map = engine.build_map(olm_input)

        assert "upper_tier_processing" in olm_map.resolution_constraints
        assert "meaning_constraint_active" in olm_map.resolution_constraints

    def test_lower_tier_constraints(self, engine: OLMEngine) -> None:
        """Lower tier should generate appropriate constraints."""
        olm_input = OLMInput(
            layer_weights={"O1_action": 0.7, "O3_forming": 0.3},
            anchor_scores={"Needs": 0.6, "Exchange": 0.4},
            H_D=0.5,
            H_G=0.3,
            H_K=0.3,
            domain="code",
            tier="lower",
            flow_mode="outer_only",
        )

        olm_map = engine.build_map(olm_input)

        assert "lower_tier_processing" in olm_map.resolution_constraints
        assert "execution_constraint_active" in olm_map.resolution_constraints

    def test_no_duplicate_constraints(self, engine: OLMEngine) -> None:
        """Resolution constraints should not have duplicates."""
        olm_input = OLMInput(
            layer_weights={"O7_purposing": 0.7, "O10_absolving": 0.3},
            anchor_scores={"Meaning": 0.6, "Collective": 0.4},
            H_D=2.0,
            H_G=0.9,
            H_K=1.2,
            domain="spiritual",
            tier="upper",
            flow_mode="inner_priority",
        )

        olm_map = engine.build_map(olm_input)

        assert len(olm_map.resolution_constraints) == len(set(olm_map.resolution_constraints))


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_olm_engine_returns_singleton(self) -> None:
        """get_olm_engine should return the same instance."""
        engine1 = get_olm_engine()
        engine2 = get_olm_engine()

        assert engine1 is engine2

    def test_singleton_is_olm_engine_instance(self) -> None:
        """Singleton should be an OLMEngine instance."""
        engine = get_olm_engine()
        assert isinstance(engine, OLMEngine)


# =============================================================================
# MODEL TESTS
# =============================================================================


class TestOntologicalLayerMap:
    """Tests for OntologicalLayerMap model."""

    def test_to_dict(self, engine: OLMEngine, basic_input: OLMInput) -> None:
        """to_dict should serialize all fields."""
        olm_map = engine.build_map(basic_input)
        result = olm_map.to_dict()

        assert "dominant_layers" in result
        assert "suppressed_layers" in result
        assert "execution_profile" in result
        assert "governance_profile" in result
        assert "anchor_profile" in result
        assert "entropy_profile" in result
        assert "tension_zones" in result
        assert "resolution_constraints" in result
        assert "tier" in result
        assert "domain" in result
        assert "layer_balance" in result

    def test_repr(self, engine: OLMEngine, basic_input: OLMInput) -> None:
        """__repr__ should provide concise summary."""
        olm_map = engine.build_map(basic_input)
        repr_str = repr(olm_map)

        assert "OntologicalLayerMap" in repr_str
        assert olm_map.tier in repr_str
        assert olm_map.domain in repr_str


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests for deterministic output."""

    def test_identical_input_identical_output(self, engine: OLMEngine, basic_input: OLMInput) -> None:
        """Same input should produce identical output."""
        results = [engine.build_map(basic_input) for _ in range(5)]

        first = results[0].to_dict()
        for result in results[1:]:
            assert result.to_dict() == first
