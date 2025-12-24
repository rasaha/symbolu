"""
Provider Parity Tests
=====================

Tests that verify both enterprise and consumer modes produce
the same output STRUCTURE, even if the values differ.

These tests are critical for ensuring:
1. Governance layer receives compatible inputs regardless of mode
2. Both modes can be switched at runtime without code changes
3. Consumer mode is ready for trained model integration
"""

import pytest

from symbolu.config import SymboluConfig
from symbolu.providers import (
    get_embedding_provider,
    get_router_provider,
    get_filter_provider,
    RoutingDecision,
    FilterResult,
    ModelType,
)


class TestEmbeddingParity:
    """Tests for embedding provider parity between modes."""

    @pytest.fixture
    def enterprise_provider(self):
        """Get enterprise embedding provider."""
        return get_embedding_provider("enterprise")

    @pytest.fixture
    def consumer_provider(self):
        """Get consumer embedding provider."""
        return get_embedding_provider("consumer")

    def test_both_return_list_of_floats(
        self, enterprise_provider, consumer_provider
    ):
        """Verify both providers return List[float]."""
        text = "test query"
        e_vec = enterprise_provider.embed(text)
        c_vec = consumer_provider.embed(text)

        assert isinstance(e_vec, list)
        assert isinstance(c_vec, list)
        assert all(isinstance(v, float) for v in e_vec)
        assert all(isinstance(v, float) for v in c_vec)

    def test_dimensions_differ_as_expected(
        self, enterprise_provider, consumer_provider
    ):
        """Verify enterprise=256D, consumer=768D as documented."""
        assert enterprise_provider.get_dimension() == 256
        assert consumer_provider.get_dimension() == 768

    def test_batch_embed_returns_same_structure(
        self, enterprise_provider, consumer_provider
    ):
        """Verify batch embed returns List[List[float]]."""
        texts = ["query1", "query2"]
        e_vecs = enterprise_provider.embed_batch(texts)
        c_vecs = consumer_provider.embed_batch(texts)

        assert len(e_vecs) == len(c_vecs) == 2
        assert all(isinstance(v, list) for v in e_vecs)
        assert all(isinstance(v, list) for v in c_vecs)

    def test_similarity_returns_float(
        self, enterprise_provider, consumer_provider
    ):
        """Verify similarity returns float in both modes."""
        e_vec = enterprise_provider.embed("test")
        c_vec = consumer_provider.embed("test")

        e_sim = enterprise_provider.similarity(e_vec, e_vec)
        c_sim = consumer_provider.similarity(c_vec, c_vec)

        assert isinstance(e_sim, float)
        assert isinstance(c_sim, float)
        # Allow small floating point tolerance
        assert -0.01 <= e_sim <= 1.01
        assert -0.01 <= c_sim <= 1.01


class TestRouterParity:
    """Tests for router provider parity between modes."""

    @pytest.fixture
    def enterprise_provider(self):
        """Get enterprise router provider."""
        return get_router_provider("enterprise")

    @pytest.fixture
    def consumer_provider(self):
        """Get consumer router provider."""
        return get_router_provider("consumer")

    def test_both_return_routing_decision(
        self, enterprise_provider, consumer_provider
    ):
        """Verify both providers return RoutingDecision."""
        query = "How do atoms bond?"
        e_decision = enterprise_provider.route(query)
        c_decision = consumer_provider.route(query)

        assert isinstance(e_decision, RoutingDecision)
        assert isinstance(c_decision, RoutingDecision)

    def test_routing_decision_structure_matches(
        self, enterprise_provider, consumer_provider
    ):
        """Verify RoutingDecision has same attributes in both modes."""
        query = "Calculate the force"
        e_decision = enterprise_provider.route(query)
        c_decision = consumer_provider.route(query)

        # Same attribute names
        assert hasattr(e_decision, "model_type")
        assert hasattr(c_decision, "model_type")
        assert hasattr(e_decision, "confidence")
        assert hasattr(c_decision, "confidence")
        assert hasattr(e_decision, "dominant_layer")
        assert hasattr(c_decision, "dominant_layer")
        assert hasattr(e_decision, "layer_scores")
        assert hasattr(c_decision, "layer_scores")
        assert hasattr(e_decision, "trace")
        assert hasattr(c_decision, "trace")

    def test_model_type_is_valid_enum(
        self, enterprise_provider, consumer_provider
    ):
        """Verify model_type is valid ModelType in both modes."""
        query = "What is love?"
        e_decision = enterprise_provider.route(query)
        c_decision = consumer_provider.route(query)

        assert isinstance(e_decision.model_type, ModelType)
        assert isinstance(c_decision.model_type, ModelType)

    def test_confidence_is_float_in_range(
        self, enterprise_provider, consumer_provider
    ):
        """Verify confidence is float 0.0-1.0 in both modes."""
        query = "Run the script"
        e_decision = enterprise_provider.route(query)
        c_decision = consumer_provider.route(query)

        assert isinstance(e_decision.confidence, float)
        assert isinstance(c_decision.confidence, float)
        assert 0.0 <= e_decision.confidence <= 1.0
        assert 0.0 <= c_decision.confidence <= 1.0

    def test_batch_route_returns_list(
        self, enterprise_provider, consumer_provider
    ):
        """Verify batch route returns List[RoutingDecision]."""
        queries = ["query1", "query2"]
        e_decisions = enterprise_provider.route_batch(queries)
        c_decisions = consumer_provider.route_batch(queries)

        assert len(e_decisions) == len(c_decisions) == 2
        assert all(isinstance(d, RoutingDecision) for d in e_decisions)
        assert all(isinstance(d, RoutingDecision) for d in c_decisions)

    def test_trace_is_dict(self, enterprise_provider, consumer_provider):
        """Verify trace is dict in both modes."""
        query = "test query"
        e_decision = enterprise_provider.route(query)
        c_decision = consumer_provider.route(query)

        assert isinstance(e_decision.trace, dict)
        assert isinstance(c_decision.trace, dict)


class TestFilterParity:
    """Tests for filter provider parity between modes."""

    @pytest.fixture
    def enterprise_provider(self):
        """Get enterprise filter provider."""
        return get_filter_provider("enterprise")

    @pytest.fixture
    def consumer_provider(self):
        """Get consumer filter provider."""
        return get_filter_provider("consumer")

    def test_both_return_filter_result(
        self, enterprise_provider, consumer_provider
    ):
        """Verify both providers return FilterResult."""
        candidates = ("apple", "banana", "atom")
        query = "chemistry"
        e_result = enterprise_provider.filter(candidates, query, top_k=10)
        c_result = consumer_provider.filter(candidates, query, top_k=10)

        assert isinstance(e_result, FilterResult)
        assert isinstance(c_result, FilterResult)

    def test_filter_result_structure_matches(
        self, enterprise_provider, consumer_provider
    ):
        """Verify FilterResult has same attributes in both modes."""
        candidates = ("test1", "test2")
        query = "query"
        e_result = enterprise_provider.filter(candidates, query, top_k=10)
        c_result = consumer_provider.filter(candidates, query, top_k=10)

        # Same attribute names
        assert hasattr(e_result, "filtered_texts")
        assert hasattr(c_result, "filtered_texts")
        assert hasattr(e_result, "scores")
        assert hasattr(c_result, "scores")
        assert hasattr(e_result, "stats")
        assert hasattr(c_result, "stats")

    def test_filtered_texts_is_tuple(
        self, enterprise_provider, consumer_provider
    ):
        """Verify filtered_texts is tuple in both modes."""
        candidates = ("a", "b", "c")
        query = "query"
        e_result = enterprise_provider.filter(candidates, query, top_k=10)
        c_result = consumer_provider.filter(candidates, query, top_k=10)

        assert isinstance(e_result.filtered_texts, tuple)
        assert isinstance(c_result.filtered_texts, tuple)

    def test_scores_is_tuple_of_floats(
        self, enterprise_provider, consumer_provider
    ):
        """Verify scores is tuple of floats in both modes."""
        candidates = ("a", "b", "c")
        query = "query"
        e_result = enterprise_provider.filter(candidates, query, top_k=10)
        c_result = consumer_provider.filter(candidates, query, top_k=10)

        assert isinstance(e_result.scores, tuple)
        assert isinstance(c_result.scores, tuple)
        assert all(isinstance(s, float) for s in e_result.scores)
        assert all(isinstance(s, float) for s in c_result.scores)

    def test_stats_is_dict(self, enterprise_provider, consumer_provider):
        """Verify stats is dict in both modes."""
        candidates = ("a", "b")
        query = "query"
        e_result = enterprise_provider.filter(candidates, query, top_k=10)
        c_result = consumer_provider.filter(candidates, query, top_k=10)

        assert isinstance(e_result.stats, dict)
        assert isinstance(c_result.stats, dict)

    def test_empty_candidates_handled(
        self, enterprise_provider, consumer_provider
    ):
        """Verify empty candidates handled in both modes."""
        e_result = enterprise_provider.filter((), "query", top_k=10)
        c_result = consumer_provider.filter((), "query", top_k=10)

        assert e_result.count == 0
        assert c_result.count == 0


class TestConfigParity:
    """Tests for SymboluConfig parity."""

    def test_enterprise_config(self):
        """Verify enterprise config works."""
        config = SymboluConfig(mode="enterprise")
        assert config.is_enterprise
        assert not config.is_consumer
        assert config.audit_enabled  # Auto-enabled

    def test_consumer_config(self):
        """Verify consumer config works."""
        config = SymboluConfig(mode="consumer")
        assert config.is_consumer
        assert not config.is_enterprise
        assert not config.audit_enabled  # Not auto-enabled

    def test_invalid_mode_fails(self):
        """Verify invalid mode raises error."""
        with pytest.raises(ValueError):
            SymboluConfig(mode="invalid")

    def test_embedding_dim_differs_by_mode(self):
        """Verify get_embedding_dim differs by mode."""
        e_config = SymboluConfig(mode="enterprise")
        c_config = SymboluConfig(mode="consumer")

        assert e_config.get_embedding_dim() == 256
        assert c_config.get_embedding_dim() == 768

    def test_config_serialization(self):
        """Verify config can be serialized and deserialized."""
        config = SymboluConfig(mode="enterprise", license_key="TEST-123")
        d = config.to_dict()
        restored = SymboluConfig.from_dict(d)

        assert restored.mode == config.mode
        assert restored.license_key == config.license_key


class TestProviderFactoryParity:
    """Tests for provider factory functions."""

    def test_get_embedding_provider_enterprise(self):
        """Verify factory returns enterprise embedding provider."""
        provider = get_embedding_provider("enterprise")
        assert provider.get_dimension() == 256

    def test_get_embedding_provider_consumer(self):
        """Verify factory returns consumer embedding provider."""
        provider = get_embedding_provider("consumer")
        assert provider.get_dimension() == 768

    def test_get_router_provider_enterprise(self):
        """Verify factory returns enterprise router provider."""
        provider = get_router_provider("enterprise")
        decision = provider.route("test")
        assert decision.trace.get("provider") == "phoneme"

    def test_get_router_provider_consumer(self):
        """Verify factory returns consumer router provider."""
        provider = get_router_provider("consumer")
        decision = provider.route("test")
        assert decision.trace.get("provider") == "trained"

    def test_get_filter_provider_enterprise(self):
        """Verify factory returns enterprise filter provider."""
        provider = get_filter_provider("enterprise")
        result = provider.filter(("a",), "b", top_k=10)
        assert result.stats.get("provider") == "resonance"

    def test_get_filter_provider_consumer(self):
        """Verify factory returns consumer filter provider."""
        provider = get_filter_provider("consumer")
        result = provider.filter(("a",), "b", top_k=10)
        assert result.stats.get("provider") == "attention"

    def test_invalid_mode_raises_error(self):
        """Verify invalid mode raises error in all factories."""
        with pytest.raises(ValueError):
            get_embedding_provider("invalid")
        with pytest.raises(ValueError):
            get_router_provider("invalid")
        with pytest.raises(ValueError):
            get_filter_provider("invalid")
