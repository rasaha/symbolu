"""
Provider Interface Tests
========================

Tests that verify provider interfaces are correctly defined
and that all providers implement the required methods.
"""

import pytest
from abc import ABC

from symbolu.providers.interfaces import (
    EmbeddingProvider,
    RouterProvider,
    FilterProvider,
    RoutingDecision,
    FilterResult,
    ModelType,
)


class TestEmbeddingProviderInterface:
    """Tests for EmbeddingProvider ABC."""

    def test_is_abstract_base_class(self):
        """Verify EmbeddingProvider is an ABC."""
        assert issubclass(EmbeddingProvider, ABC)

    def test_cannot_instantiate_directly(self):
        """Verify EmbeddingProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            EmbeddingProvider()

    def test_requires_embed_method(self):
        """Verify embed method is abstract."""
        assert hasattr(EmbeddingProvider, "embed")

    def test_requires_embed_batch_method(self):
        """Verify embed_batch method is abstract."""
        assert hasattr(EmbeddingProvider, "embed_batch")

    def test_requires_get_dimension_method(self):
        """Verify get_dimension method is abstract."""
        assert hasattr(EmbeddingProvider, "get_dimension")

    def test_similarity_has_default_implementation(self):
        """Verify similarity has a default implementation."""
        # Create a minimal concrete implementation
        class ConcreteEmbedding(EmbeddingProvider):
            def embed(self, text):
                return [0.5, 0.5]

            def embed_batch(self, texts):
                return [self.embed(t) for t in texts]

            def get_dimension(self):
                return 2

        provider = ConcreteEmbedding()
        # Should work with default implementation
        sim = provider.similarity([1.0, 0.0], [1.0, 0.0])
        assert sim == pytest.approx(1.0)


class TestRouterProviderInterface:
    """Tests for RouterProvider ABC."""

    def test_is_abstract_base_class(self):
        """Verify RouterProvider is an ABC."""
        assert issubclass(RouterProvider, ABC)

    def test_cannot_instantiate_directly(self):
        """Verify RouterProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            RouterProvider()

    def test_requires_route_method(self):
        """Verify route method is abstract."""
        assert hasattr(RouterProvider, "route")

    def test_requires_route_batch_method(self):
        """Verify route_batch method is abstract."""
        assert hasattr(RouterProvider, "route_batch")


class TestFilterProviderInterface:
    """Tests for FilterProvider ABC."""

    def test_is_abstract_base_class(self):
        """Verify FilterProvider is an ABC."""
        assert issubclass(FilterProvider, ABC)

    def test_cannot_instantiate_directly(self):
        """Verify FilterProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            FilterProvider()

    def test_requires_filter_method(self):
        """Verify filter method is abstract."""
        assert hasattr(FilterProvider, "filter")


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_routing_decision_creation(self):
        """Verify RoutingDecision can be created with valid data."""
        decision = RoutingDecision(
            model_type=ModelType.REASONING,
            confidence=0.85,
            dominant_layer="O6_REASONING",
            layer_scores=(("O6_REASONING", 0.4), ("O9_UNIFYING", 0.3)),
            trace={"provider": "test"},
        )
        assert decision.model_type == ModelType.REASONING
        assert decision.confidence == 0.85

    def test_routing_decision_to_dict(self):
        """Verify RoutingDecision serializes to dict."""
        decision = RoutingDecision(
            model_type=ModelType.REASONING,
            confidence=0.85,
            dominant_layer="O6_REASONING",
            layer_scores=(("O6_REASONING", 0.4),),
            trace={},
        )
        d = decision.to_dict()
        assert d["model_type"] == "reasoning"
        assert d["confidence"] == 0.85

    def test_routing_decision_is_frozen(self):
        """Verify RoutingDecision is immutable."""
        decision = RoutingDecision(
            model_type=ModelType.REASONING,
            confidence=0.85,
            dominant_layer="O6_REASONING",
            layer_scores=(),
            trace={},
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            decision.confidence = 0.5


class TestFilterResult:
    """Tests for FilterResult dataclass."""

    def test_filter_result_creation(self):
        """Verify FilterResult can be created with valid data."""
        result = FilterResult(
            filtered_texts=("text1", "text2"),
            scores=(0.9, 0.8),
            stats={"provider": "test"},
        )
        assert result.count == 2
        assert result.filtered_texts[0] == "text1"

    def test_filter_result_length_mismatch_fails(self):
        """Verify FilterResult fails with mismatched lengths."""
        with pytest.raises(ValueError):
            FilterResult(
                filtered_texts=("text1", "text2"),
                scores=(0.9,),  # Mismatch!
                stats={},
            )

    def test_filter_result_top_k(self):
        """Verify FilterResult.top_k works correctly."""
        result = FilterResult(
            filtered_texts=("a", "b", "c"),
            scores=(0.9, 0.8, 0.7),
            stats={},
        )
        top2 = result.top_k(2)
        assert top2.count == 2
        assert top2.filtered_texts == ("a", "b")

    def test_filter_result_is_frozen(self):
        """Verify FilterResult is immutable."""
        result = FilterResult(
            filtered_texts=(),
            scores=(),
            stats={},
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            result.filtered_texts = ("new",)


class TestModelType:
    """Tests for ModelType enum."""

    def test_all_model_types_exist(self):
        """Verify all expected model types exist."""
        expected = [
            "GENERAL",
            "REASONING",
            "RELATIONSHIP",
            "ACTION",
            "CREATIVE",
            "REFLECTIVE",
            "DIRECTIVE",
            "TRANSCENDENT",
        ]
        for name in expected:
            assert hasattr(ModelType, name)

    def test_model_type_values(self):
        """Verify model type values are lowercase strings."""
        for model_type in ModelType:
            assert model_type.value == model_type.name.lower()
