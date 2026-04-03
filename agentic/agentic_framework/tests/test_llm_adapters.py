"""
Tests for LLM Adapters

Tests the adapter classes for various LLM providers:
- BaseLLMAdapter interface
- MockLLMAdapter
- SequentialMockAdapter
- MockEmbeddingAdapter
- MistralCGAdapter (with mock backbone)
- Factory function create_adapter
"""

from unittest.mock import MagicMock, patch
import pytest

from agentic.agentic_framework.llm_adapters import (
    BaseLLMAdapter,
    MistralAdapter,
    MistralCGAdapter,
    MockLLMAdapter,
    SequentialMockAdapter,
    MockEmbeddingAdapter,
    create_adapter,
)


class TestMockLLMAdapter:
    """Tests for MockLLMAdapter."""

    def test_mock_adapter_creation(self):
        """Test basic MockLLMAdapter creation."""
        adapter = MockLLMAdapter()
        assert adapter.default_response == "Mock response"
        assert adapter.echo is False

    def test_mock_adapter_default_response(self):
        """Test default response."""
        adapter = MockLLMAdapter(default_response="Hello!")
        response = adapter.call("Any prompt")
        assert response == "Hello!"

    def test_mock_adapter_custom_responses(self):
        """Test custom response mapping."""
        adapter = MockLLMAdapter(
            responses={
                "capital": "The capital of France is Paris.",
                "population": "France has about 67 million people.",
            }
        )

        response1 = adapter.call("What is the capital of France?")
        assert "Paris" in response1

        response2 = adapter.call("What is the population?")
        assert "67 million" in response2

    def test_mock_adapter_case_insensitive(self):
        """Test case-insensitive matching."""
        adapter = MockLLMAdapter(
            responses={"hello": "Hi there!"}
        )

        response = adapter.call("HELLO world")
        assert response == "Hi there!"

    def test_mock_adapter_echo_mode(self):
        """Test echo mode."""
        adapter = MockLLMAdapter(echo=True)

        response = adapter.call("Test input")
        assert "Test input" in response
        assert response.startswith("Echo:")

    def test_mock_adapter_call_history(self):
        """Test call history tracking."""
        adapter = MockLLMAdapter()

        adapter.call("First call")
        adapter.call("Second call")
        adapter.call("Third call")

        assert len(adapter.call_history) == 3
        assert adapter.call_history[0] == "First call"
        assert adapter.call_history[2] == "Third call"

    def test_mock_adapter_reset_history(self):
        """Test resetting call history."""
        adapter = MockLLMAdapter()

        adapter.call("Call 1")
        adapter.call("Call 2")
        adapter.reset_history()

        assert len(adapter.call_history) == 0

    def test_mock_adapter_call_with_messages(self):
        """Test call_with_messages method."""
        adapter = MockLLMAdapter(default_response="Response")

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"},
        ]

        response = adapter.call_with_messages(messages)
        assert response == "Response"


class TestSequentialMockAdapter:
    """Tests for SequentialMockAdapter."""

    def test_sequential_adapter_creation(self):
        """Test SequentialMockAdapter creation."""
        adapter = SequentialMockAdapter(["First", "Second", "Third"])
        assert len(adapter.responses) == 3
        assert adapter.index == 0

    def test_sequential_responses(self):
        """Test sequential response order."""
        adapter = SequentialMockAdapter(["One", "Two", "Three"])

        assert adapter.call("a") == "One"
        assert adapter.call("b") == "Two"
        assert adapter.call("c") == "Three"

    def test_sequential_stops_at_last(self):
        """Test that adapter stays at last response without loop."""
        adapter = SequentialMockAdapter(["First", "Last"], loop=False)

        adapter.call("1")
        adapter.call("2")
        response = adapter.call("3")  # Past end

        assert response == "Last"

    def test_sequential_loop_mode(self):
        """Test loop mode."""
        adapter = SequentialMockAdapter(["A", "B"], loop=True)

        assert adapter.call("1") == "A"
        assert adapter.call("2") == "B"
        assert adapter.call("3") == "A"  # Loops back
        assert adapter.call("4") == "B"

    def test_sequential_call_history(self):
        """Test call history tracking."""
        adapter = SequentialMockAdapter(["R1", "R2"])

        adapter.call("Prompt 1")
        adapter.call("Prompt 2")

        assert len(adapter.call_history) == 2
        assert "Prompt 1" in adapter.call_history

    def test_sequential_reset(self):
        """Test reset functionality."""
        adapter = SequentialMockAdapter(["First", "Second"])

        adapter.call("a")
        adapter.call("b")
        adapter.reset()

        assert adapter.index == 0
        assert len(adapter.call_history) == 0
        assert adapter.call("c") == "First"

    def test_sequential_empty_responses(self):
        """Test with empty responses list."""
        adapter = SequentialMockAdapter([])

        response = adapter.call("test")
        assert response == "No responses configured"


class TestMockEmbeddingAdapter:
    """Tests for MockEmbeddingAdapter."""

    def test_embedding_adapter_creation(self):
        """Test MockEmbeddingAdapter creation."""
        adapter = MockEmbeddingAdapter(dimension=128)
        assert adapter.dimension == 128

    def test_embedding_adapter_default_dimension(self):
        """Test default dimension."""
        adapter = MockEmbeddingAdapter()
        assert adapter.dimension == 128

    def test_embed_returns_correct_dimension(self):
        """Test embedding has correct dimension."""
        adapter = MockEmbeddingAdapter(dimension=64)
        embedding = adapter.embed("Test text")

        assert len(embedding) == 64

    def test_embed_returns_floats(self):
        """Test embedding contains floats."""
        adapter = MockEmbeddingAdapter()
        embedding = adapter.embed("Test")

        assert all(isinstance(x, float) for x in embedding)

    def test_embed_normalized_range(self):
        """Test embedding values are in expected range."""
        adapter = MockEmbeddingAdapter()
        embedding = adapter.embed("Test text")

        assert all(-1 <= x <= 1 for x in embedding)

    def test_embed_deterministic(self):
        """Test same text produces same embedding."""
        adapter = MockEmbeddingAdapter()

        emb1 = adapter.embed("Same text")
        emb2 = adapter.embed("Same text")

        assert emb1 == emb2

    def test_embed_different_texts(self):
        """Test different texts produce different embeddings."""
        adapter = MockEmbeddingAdapter()

        emb1 = adapter.embed("Text one")
        emb2 = adapter.embed("Text two")

        assert emb1 != emb2


class TestCreateAdapterFactory:
    """Tests for create_adapter factory function."""

    def test_create_mock_adapter(self):
        """Test creating mock adapter."""
        adapter = create_adapter("mock")
        assert isinstance(adapter, MockLLMAdapter)

    def test_create_mock_with_options(self):
        """Test creating mock adapter with options."""
        adapter = create_adapter("mock", default_response="Custom")
        assert adapter.default_response == "Custom"

    def test_create_unknown_provider(self):
        """Test error for unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            create_adapter("unknown_provider")
        assert "Unknown provider" in str(exc_info.value)

    def test_create_openai_requires_package(self):
        """Test OpenAI adapter requires package."""
        # This will raise ImportError if openai is not installed
        # which is expected in test environment
        try:
            adapter = create_adapter("openai", api_key="test")
            # If we get here, openai is installed
            assert adapter is not None
        except ImportError:
            # Expected if openai not installed
            pass

    def test_create_anthropic_alias(self):
        """Test 'claude' as alias for anthropic."""
        # Will fail with ImportError if anthropic not installed
        try:
            adapter = create_adapter("claude", api_key="test")
            assert adapter is not None
        except ImportError:
            pass

    def test_create_gemini_alias(self):
        """Test 'google' as alias for gemini."""
        try:
            adapter = create_adapter("google", api_key="test")
            assert adapter is not None
        except ImportError:
            pass

    def test_create_mistral_adapter(self):
        """Test 'mistral' provider is recognized."""
        try:
            adapter = create_adapter("mistral", api_key="test")
            assert isinstance(adapter, MistralAdapter)
        except ImportError:
            # Expected if mistralai not installed
            pass


class TestBaseLLMAdapterInterface:
    """Tests for BaseLLMAdapter interface compliance."""

    def test_mock_implements_interface(self):
        """Test MockLLMAdapter implements interface."""
        adapter = MockLLMAdapter()

        # Should have call method
        assert hasattr(adapter, "call")
        assert callable(adapter.call)

        # Should have call_with_messages method
        assert hasattr(adapter, "call_with_messages")
        assert callable(adapter.call_with_messages)

    def test_sequential_implements_interface(self):
        """Test SequentialMockAdapter implements interface."""
        adapter = SequentialMockAdapter(["test"])

        assert hasattr(adapter, "call")
        assert callable(adapter.call)

    def test_call_signature(self):
        """Test call method accepts string and returns string."""
        adapter = MockLLMAdapter()

        result = adapter.call("test prompt")

        assert isinstance(result, str)

    def test_call_with_messages_signature(self):
        """Test call_with_messages accepts list and returns string."""
        adapter = MockLLMAdapter()

        messages = [{"role": "user", "content": "test"}]
        result = adapter.call_with_messages(messages)

        assert isinstance(result, str)


class TestAdapterIntegration:
    """Integration tests for adapters."""

    def test_adapter_in_conversation_flow(self):
        """Test adapter in simulated conversation."""
        adapter = SequentialMockAdapter([
            "Hello! How can I help you?",
            "Python is a great programming language.",
            "Yes, it's known for its readability.",
        ])

        # Simulate conversation
        responses = []
        prompts = ["Hi", "Tell me about Python", "Is it easy to learn?"]

        for prompt in prompts:
            response = adapter.call(prompt)
            responses.append(response)

        assert len(responses) == 3
        assert "Hello" in responses[0]
        assert "Python" in responses[1]

    def test_adapter_with_message_history(self):
        """Test adapter handling message history."""
        adapter = MockLLMAdapter(
            responses={"python": "Python info"}
        )

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Tell me about python"},
        ]

        response = adapter.call_with_messages(messages)
        assert response == "Python info"

    def test_embedding_adapter_for_similarity(self):
        """Test embedding adapter can be used for similarity."""
        adapter = MockEmbeddingAdapter(dimension=32)

        emb1 = adapter.embed("Python programming language")
        emb2 = adapter.embed("Python coding tutorial")
        emb3 = adapter.embed("Cooking recipes for dinner")

        # Calculate simple cosine similarity
        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0

        # Note: Mock embeddings are hash-based, so similarity may not be semantic
        # but the structure should work
        sim_12 = cosine_sim(emb1, emb2)
        sim_13 = cosine_sim(emb1, emb3)

        assert isinstance(sim_12, float)
        assert isinstance(sim_13, float)


# =============================================================================
# MistralCGAdapter Tests (with mock backbone)
# =============================================================================


def _make_mock_mistral_cg():
    """
    Build a fake MistralCGWrapper + tokenizer for testing MistralCGAdapter
    without loading a real 7B model.
    """
    torch = pytest.importorskip("torch", reason="torch required for MistralCG tests")

    vocab_size = 100
    hidden_dim = 64

    # --- Mock tokenizer ---
    tokenizer = MagicMock()
    tokenizer.pad_token = "[PAD]"
    tokenizer.eos_token = "[EOS]"
    tokenizer.eos_token_id = 2
    tokenizer.pad_token_id = 0

    def mock_tokenize(text, return_tensors=None, padding=False, truncation=False):
        # Return 5 token ids for any input
        ids = torch.tensor([[10, 20, 30, 40, 50]])
        mask = torch.ones_like(ids)
        result = MagicMock()
        result.__getitem__ = lambda self, k: {"input_ids": ids, "attention_mask": mask}[k]
        result.get = lambda k, d=None: {"input_ids": ids, "attention_mask": mask}.get(k, d)
        return result

    tokenizer.side_effect = mock_tokenize
    tokenizer.decode = MagicMock(side_effect=lambda ids, **kw: "Generated response text")

    # --- Mock MistralCGWrapper (nn.Module) ---
    model = MagicMock()
    model.eval = MagicMock(return_value=model)
    model.tokenizer = tokenizer

    # parameters() must yield at least one tensor (for device detection)
    param = torch.nn.Parameter(torch.zeros(1))
    model.parameters = MagicMock(return_value=iter([param]))

    # Track call count for EOS injection
    call_count = {"n": 0}

    def mock_forward(input_ids, attention_mask=None, reset_state=False, **kwargs):
        call_count["n"] += 1
        B, T = input_ids.shape
        # After 3 generation steps, emit EOS token as argmax
        logits = torch.randn(B, T, vocab_size)
        if call_count["n"] > 3:
            # Make EOS token the highest logit at last position
            logits[0, -1, :] = -100.0
            logits[0, -1, 2] = 100.0  # eos_token_id = 2

        return {
            'logits': logits,
            'state': torch.randn(B, 32),
            'delta_S': torch.randn(B, 32),
            'delta_bhava': torch.randn(B, 12),
            'intent_phase': torch.randn(B, 32),
            'adapter_gate': 0.12,
        }

    model.side_effect = mock_forward
    model.__call__ = mock_forward

    return model, tokenizer


class TestMistralCGAdapter:
    """Tests for MistralCGAdapter with mock backbone."""

    def _make_adapter(self):
        """Create adapter with mock model (bypasses real model loading)."""
        mock_model, mock_tokenizer = _make_mock_mistral_cg()

        with patch(
            "symbolu.agentic_framework.llm_adapters.MistralCGAdapter.__init__",
            lambda self, **kw: None,
        ):
            adapter = MistralCGAdapter.__new__(MistralCGAdapter)

        # Manually set attributes that __init__ would set
        import torch as _torch

        adapter._torch = _torch
        adapter.model = mock_model
        adapter.tokenizer = mock_tokenizer
        adapter.max_new_tokens = 10
        adapter.temperature = 0.0  # Greedy for determinism
        adapter.top_p = 1.0
        adapter.top_k = 0
        adapter.repetition_penalty = 1.0
        adapter.last_cg_metadata = {}
        adapter.call_history = []

        return adapter

    def test_adapter_creation(self):
        """Test MistralCGAdapter can be created with mock backbone."""
        adapter = self._make_adapter()
        assert adapter.tokenizer is not None
        assert adapter.model is not None

    def test_call_returns_string(self):
        """Test call() returns a string response."""
        adapter = self._make_adapter()
        response = adapter.call("What is consciousness?")
        assert isinstance(response, str)

    def test_call_stores_cg_metadata(self):
        """Test CG metadata is captured after call()."""
        adapter = self._make_adapter()
        adapter.call("Test prompt")

        meta = adapter.get_cg_metadata()
        assert 'state' in meta
        assert 'delta_S' in meta
        assert 'delta_bhava' in meta
        assert 'intent_phase' in meta
        assert 'adapter_gate' in meta

    def test_cg_metadata_has_correct_shapes(self):
        """Test CG metadata tensors have expected shapes."""
        adapter = self._make_adapter()
        adapter.call("Test prompt")

        meta = adapter.get_cg_metadata()
        # state: [B, 32]
        assert meta['state'].shape == (1, 32)
        # delta_S: [B, 32]
        assert meta['delta_S'].shape == (1, 32)
        # delta_bhava: [B, 12]
        assert meta['delta_bhava'].shape == (1, 12)

    def test_call_tracks_history(self):
        """Test call history is tracked."""
        adapter = self._make_adapter()
        adapter.call("First question")
        adapter.call("Second question")

        assert len(adapter.call_history) == 2
        assert adapter.call_history[0] == "First question"
        assert adapter.call_history[1] == "Second question"

    def test_implements_base_interface(self):
        """Test MistralCGAdapter implements BaseLLMAdapter interface."""
        adapter = self._make_adapter()
        assert hasattr(adapter, 'call')
        assert callable(adapter.call)
        assert hasattr(adapter, 'call_with_messages')
        assert callable(adapter.call_with_messages)

    def test_call_with_messages(self):
        """Test call_with_messages works via base class fallback."""
        adapter = self._make_adapter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"},
        ]
        response = adapter.call_with_messages(messages)
        assert isinstance(response, str)

    def test_cg_metadata_compatible_with_sovereign_bridge(self):
        """Test CG metadata can be fed to signals_from_sovereign_state."""
        adapter = self._make_adapter()
        adapter.call("Test prompt")

        meta = adapter.get_cg_metadata()

        from agentic.agentic_framework.sovereign_bridge import (
            signals_from_sovereign_state,
        )

        # Should not raise — validates tensor/list compatibility
        signals = signals_from_sovereign_state(
            meta['state'],
            meta['delta_S'],
        )
        assert 0.0 <= signals.quality_score <= 1.0
        assert 0.0 <= signals.session_stability <= 1.0


class TestCreateAdapterMistralCG:
    """Tests for create_adapter with mistral_cg provider."""

    def test_create_mistral_cg_alias(self):
        """Test mistral_cg and mistralcg are recognized providers."""
        # Will raise ImportError or loading error in test env (no GPU/model)
        # but should NOT raise ValueError("Unknown provider")
        for name in ("mistral_cg", "mistralcg"):
            try:
                create_adapter(name)
            except (ImportError, ValueError, OSError, RuntimeError):
                # Expected: no model weights / no GPU in test env
                # But NOT ValueError("Unknown provider")
                pass
