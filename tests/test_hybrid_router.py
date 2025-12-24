"""
Tests for Semantic Router (symbolu/hybrid/router.py)

These tests validate the semantic routing to specialized models:
- Model type selection based on phoneme signatures
- Routing decisions and confidence levels
- Layer-to-model mapping
- Edge cases and determinism
"""

import pytest
from unittest.mock import MagicMock, patch

from symbolu.hybrid.router import (
    ModelType,
    RoutingDecision,
    SemanticRouter,
    LAYER_TO_MODEL,
    ModelRegistry,
    create_demo_registry,
)


# =============================================================================
# Tests for ModelType Enum
# =============================================================================


class TestModelType:
    """Tests for ModelType enum."""

    def test_all_types_exist(self):
        """All expected model types should exist."""
        assert ModelType.GENERAL is not None
        assert ModelType.RELATIONSHIP is not None
        assert ModelType.REASONING is not None
        assert ModelType.ACTION is not None
        assert ModelType.CREATIVE is not None
        assert ModelType.REFLECTIVE is not None
        assert ModelType.DIRECTIVE is not None
        assert ModelType.TRANSCENDENT is not None

    def test_type_values_unique(self):
        """All model type values should be unique."""
        values = [mt.value for mt in ModelType]
        assert len(values) == len(set(values))

    def test_type_is_string_enum(self):
        """Model type should be string enum for JSON serialization."""
        assert isinstance(ModelType.GENERAL.value, str)


# =============================================================================
# Tests for RoutingDecision
# =============================================================================


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_creation(self):
        """Should create RoutingDecision with required fields."""
        # Create a mock PhraseAnalysis
        mock_analysis = MagicMock()
        mock_analysis.words = []

        decision = RoutingDecision(
            model_type=ModelType.REASONING,
            confidence=0.85,
            dominant_layer="O7_REASONING",
            layer_scores=(("O7_REASONING", 0.85), ("O1_POTENTIAL", 0.10)),
            query_analysis=mock_analysis,
        )

        assert decision.model_type == ModelType.REASONING
        assert decision.confidence == 0.85
        assert decision.dominant_layer == "O7_REASONING"

    def test_frozen(self):
        """RoutingDecision should be frozen (immutable)."""
        mock_analysis = MagicMock()

        decision = RoutingDecision(
            model_type=ModelType.GENERAL,
            confidence=0.5,
            dominant_layer="O2_IDENTITY",
            layer_scores=(),
            query_analysis=mock_analysis,
        )

        with pytest.raises(AttributeError):
            decision.confidence = 0.9


# =============================================================================
# Tests for LAYER_TO_MODEL Mapping
# =============================================================================


class TestLayerToModel:
    """Tests for LAYER_TO_MODEL constant."""

    def test_has_all_layers(self):
        """Should have mappings for all 12 layers."""
        expected_layers = [
            "O1_POTENTIAL",
            "O2_IDENTITY",
            "O3_EXECUTION",
            "O4_STRUCTURE",
            "O5_COGNITION",
            "O6_AGENCY",
            "O7_REASONING",
            "O8_PURPOSE",
            "O9_WITNESSES",
            "O10_UNIFYING",
            "O11_INTEGRATION",
            "O12_ABSOLVING",
        ]
        for layer in expected_layers:
            assert layer in LAYER_TO_MODEL

    def test_all_map_to_model_type(self):
        """All mappings should be to ModelType values."""
        for layer, model in LAYER_TO_MODEL.items():
            assert isinstance(model, ModelType)


# =============================================================================
# Tests for SemanticRouter
# =============================================================================


class TestSemanticRouter:
    """Tests for SemanticRouter class."""

    def test_initialization_with_defaults(self):
        """Should initialize with default values."""
        router = SemanticRouter()
        assert router.confidence_threshold == 0.3
        assert router.fallback_model == ModelType.GENERAL

    def test_initialization_with_custom_values(self):
        """Should accept custom configuration."""
        router = SemanticRouter(
            confidence_threshold=0.5,
            fallback_model=ModelType.REASONING,
        )
        assert router.confidence_threshold == 0.5
        assert router.fallback_model == ModelType.REASONING

    def test_route_returns_routing_decision(self):
        """route() should return a RoutingDecision."""
        router = SemanticRouter()
        decision = router.route("What is the meaning of love?")

        assert isinstance(decision, RoutingDecision)
        assert isinstance(decision.model_type, ModelType)
        assert 0.0 <= decision.confidence <= 1.0

    def test_route_empty_query(self):
        """Empty query should use fallback model."""
        router = SemanticRouter(fallback_model=ModelType.GENERAL)
        decision = router.route("")

        assert decision.model_type == ModelType.GENERAL
        assert decision.confidence == 0.0

    def test_route_deterministic(self):
        """Same query should produce same routing."""
        router = SemanticRouter()
        query = "How do I solve this problem?"

        decision1 = router.route(query)
        decision2 = router.route(query)

        assert decision1.model_type == decision2.model_type
        assert decision1.dominant_layer == decision2.dominant_layer

    def test_route_includes_layer_scores(self):
        """Decision should include top layer scores."""
        router = SemanticRouter()
        decision = router.route("Think deeply about this matter")

        assert isinstance(decision.layer_scores, tuple)
        # Should have layer scores
        for layer_name, score in decision.layer_scores:
            assert isinstance(layer_name, str)
            assert isinstance(score, float)

    def test_route_includes_query_analysis(self):
        """Decision should include query analysis."""
        router = SemanticRouter()
        decision = router.route("Love conquers all")

        assert decision.query_analysis is not None


# =============================================================================
# Tests for ModelRegistry
# =============================================================================


class TestModelRegistry:
    """Tests for ModelRegistry class."""

    def test_initialization(self):
        """Should initialize empty registry."""
        registry = ModelRegistry()
        assert registry is not None

    def test_register_handler(self):
        """Should register model handlers."""
        registry = ModelRegistry()

        def mock_handler(query: str) -> str:
            return f"Processed: {query}"

        registry.register(ModelType.REASONING, mock_handler)
        # Should not raise

    def test_invoke_dispatches_to_handler(self):
        """invoke() should dispatch to registered handler."""
        registry = ModelRegistry()

        # Handlers take (query, decision) as per the API
        def reasoning_handler(query: str, decision: RoutingDecision) -> str:
            return "Reasoning response"

        def general_handler(query: str, decision: RoutingDecision) -> str:
            return "General response"

        registry.register(ModelType.REASONING, reasoning_handler)
        registry.register(ModelType.GENERAL, general_handler)

        # Test invoke (this uses internal router)
        result = registry.invoke("test query")
        assert result is not None


# =============================================================================
# Tests for create_demo_registry
# =============================================================================


class TestCreateDemoRegistry:
    """Tests for create_demo_registry function."""

    def test_returns_registry(self):
        """Should return a ModelRegistry instance."""
        registry = create_demo_registry()
        assert isinstance(registry, ModelRegistry)

    def test_registry_can_invoke(self):
        """Created registry should be able to invoke queries."""
        registry = create_demo_registry()
        result = registry.invoke("Hello world")
        assert result is not None


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


class TestEdgeCases:
    """Edge cases and boundary tests."""

    def test_very_long_query(self):
        """Should handle very long queries."""
        router = SemanticRouter()
        long_query = "word " * 1000  # 1000 words
        decision = router.route(long_query)
        assert isinstance(decision, RoutingDecision)

    def test_special_characters(self):
        """Should handle special characters."""
        router = SemanticRouter()
        decision = router.route("What's the @#$% meaning of !@#$?")
        assert isinstance(decision, RoutingDecision)

    def test_unicode_query(self):
        """Should handle unicode characters."""
        router = SemanticRouter()
        decision = router.route("Что такое любовь? 爱是什么？")
        assert isinstance(decision, RoutingDecision)

    def test_numeric_query(self):
        """Should handle numeric queries."""
        router = SemanticRouter()
        decision = router.route("123 456 789")
        assert isinstance(decision, RoutingDecision)

    def test_whitespace_only(self):
        """Should handle whitespace-only queries."""
        router = SemanticRouter()
        decision = router.route("   \n\t   ")
        assert decision.model_type == router.fallback_model


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for routing flow."""

    def test_full_routing_flow(self):
        """Test complete routing from query to decision."""
        router = SemanticRouter()

        # Test various query types
        queries = [
            "How do I calculate the sum?",
            "I love you",
            "Think about this carefully",
            "Create a beautiful painting",
            "Execute the command now",
        ]

        for query in queries:
            decision = router.route(query)
            assert isinstance(decision, RoutingDecision)
            assert decision.model_type in list(ModelType)
            assert 0.0 <= decision.confidence <= 1.0

    def test_registry_with_router(self):
        """Test registry integration with router."""
        registry = create_demo_registry()

        # Invoke multiple queries
        queries = ["Hello", "Calculate this", "I love you"]
        for query in queries:
            result = registry.invoke(query)
            assert result is not None
            assert isinstance(result, str)
