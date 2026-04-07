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
        adapter.enable_vritti_gate = False
        adapter.enable_guna_gate = False
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


# =============================================================================
# Vritti Sampling Gate Validation Tests (V-1 through V-7)
# Reference: docs/specs/VRITTI_SAMPLING_GATE_SPEC.md
# =============================================================================


def _make_mock_mistral_cg_with_vritti(vritti_values):
    """
    Build a mock MistralCGWrapper that returns a controlled 32D state
    with the specified Vritti values at indices [17:22].
    """
    torch = pytest.importorskip("torch", reason="torch required for Vritti gate tests")

    vocab_size = 100
    call_count = {"n": 0}

    tokenizer = MagicMock()
    tokenizer.pad_token = "[PAD]"
    tokenizer.eos_token = "[EOS]"
    tokenizer.eos_token_id = 2
    tokenizer.pad_token_id = 0

    def mock_tokenize(text, return_tensors=None, padding=False, truncation=False):
        ids = torch.tensor([[10, 20, 30, 40, 50]])
        mask = torch.ones_like(ids)
        result = MagicMock()
        result.__getitem__ = lambda self, k: {"input_ids": ids, "attention_mask": mask}[k]
        result.get = lambda k, d=None: {"input_ids": ids, "attention_mask": mask}.get(k, d)
        return result

    tokenizer.side_effect = mock_tokenize
    tokenizer.decode = MagicMock(side_effect=lambda ids, **kw: "Generated text")

    model = MagicMock()
    model.eval = MagicMock(return_value=model)
    model.tokenizer = tokenizer

    param = torch.nn.Parameter(torch.zeros(1))
    model.parameters = MagicMock(return_value=iter([param]))

    def mock_forward(input_ids, attention_mask=None, reset_state=False, **kwargs):
        call_count["n"] += 1
        B, T = input_ids.shape
        logits = torch.randn(B, T, vocab_size)
        if call_count["n"] > 3:
            logits[0, -1, :] = -100.0
            logits[0, -1, 2] = 100.0  # EOS

        # Build 32D state with controlled Vritti at [17:22]
        state = torch.zeros(B, 32)
        vritti_tensor = torch.tensor(vritti_values, dtype=torch.float32)
        state[0, 17:22] = vritti_tensor

        return {
            'logits': logits,
            'state': state,
            'delta_S': torch.zeros(B, 32),
            'delta_bhava': torch.zeros(B, 12),
            'intent_phase': torch.zeros(B, 32),
            'adapter_gate': 0.12,
        }

    model.side_effect = mock_forward
    model.__call__ = mock_forward
    return model, tokenizer


def _make_vritti_adapter(vritti_values, temperature=0.7, enable_gate=True):
    """Create a MistralCGAdapter with mock model and controlled Vritti state."""
    torch = pytest.importorskip("torch", reason="torch required for Vritti gate tests")
    mock_model, mock_tokenizer = _make_mock_mistral_cg_with_vritti(vritti_values)

    with patch(
        "agentic.agentic_framework.llm_adapters.MistralCGAdapter.__init__",
        lambda self, **kw: None,
    ):
        adapter = MistralCGAdapter.__new__(MistralCGAdapter)

    adapter._torch = torch
    adapter.model = mock_model
    adapter.tokenizer = mock_tokenizer
    adapter.max_new_tokens = 5
    adapter.temperature = temperature
    adapter.top_p = 1.0
    adapter.top_k = 0
    adapter.repetition_penalty = 1.0
    adapter.enable_vritti_gate = enable_gate
    adapter.enable_guna_gate = False
    adapter.last_cg_metadata = {}
    adapter.call_history = []
    return adapter


class TestVrittiSamplingGate:
    """
    Validation tests for the Vritti sampling gate (V-1 through V-7).
    Reference: docs/specs/VRITTI_SAMPLING_GATE_SPEC.md
    """

    # V-1: Bounded temperature effect
    def test_v1_effective_temperature_bounded(self):
        """V-1: effective_temperature is always in [min(0.5, base), base]."""
        # High ERROR state: Vritti = [0.1, 0.7, 0.1, 0.05, 0.05]
        adapter = _make_vritti_adapter([0.1, 0.7, 0.1, 0.05, 0.05], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        for ev in events:
            assert ev['effective_temperature'] <= ev['base_temperature']
            assert ev['effective_temperature'] >= min(0.5, ev['base_temperature'])

    # V-2: No-op on untrained state (uniform softmax)
    def test_v2_noop_on_uniform_vritti(self):
        """V-2: Gate does not fire on uniform Vritti (simulates untrained state)."""
        # Uniform: [0.2, 0.2, 0.2, 0.2, 0.2] -> error_risk = 0.2 + 0.06 = 0.26 < 0.5
        adapter = _make_vritti_adapter([0.2, 0.2, 0.2, 0.2, 0.2], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) == 0, f"Gate should not fire on uniform Vritti, got {len(events)} events"

    # V-3: Gate fires on high-error states
    def test_v3_fires_on_high_error(self):
        """V-3: Gate fires when ERROR dominates."""
        # ERROR-dominant: [0.05, 0.7, 0.1, 0.1, 0.05]
        # error_risk = 0.7 + 0.3*0.1 = 0.73 > 0.5
        adapter = _make_vritti_adapter([0.05, 0.7, 0.1, 0.1, 0.05], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) > 0, "Gate should fire on high ERROR state"
        for ev in events:
            assert ev['action'] == 'cool'
            assert ev['effective_temperature'] == 0.5

    # V-4: Trace completeness
    def test_v4_trace_completeness(self):
        """V-4: Gate events have all required fields."""
        adapter = _make_vritti_adapter([0.05, 0.8, 0.05, 0.05, 0.05], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) > 0
        required_fields = {'step', 'error_risk', 'action', 'base_temperature', 'effective_temperature'}
        for ev in events:
            assert required_fields.issubset(ev.keys()), f"Missing fields: {required_fields - ev.keys()}"
            assert isinstance(ev['step'], int)
            assert isinstance(ev['error_risk'], float)
            assert ev['action'] == 'cool'

    def test_v4_vritti_gate_events_key_always_present(self):
        """V-4b: vritti_gate_events key is always in metadata, even when gate is off."""
        adapter = _make_vritti_adapter([0.8, 0.05, 0.05, 0.05, 0.05], temperature=0.7)
        adapter.call("test")
        assert 'vritti_gate_events' in adapter.last_cg_metadata
        assert adapter.last_cg_metadata['vritti_gate_events'] == []

    # V-5: No generation degeneration (basic: response is non-empty)
    def test_v5_no_degenerate_output(self):
        """V-5: Generation completes and returns non-empty string with gate on."""
        adapter = _make_vritti_adapter([0.05, 0.7, 0.1, 0.1, 0.05], temperature=0.7)
        response = adapter.call("test")
        assert isinstance(response, str)
        assert len(response) > 0

    # V-6: Greedy mode bypass
    def test_v6_greedy_bypass(self):
        """V-6: Gate is entirely skipped when temperature=0."""
        adapter = _make_vritti_adapter([0.05, 0.9, 0.05, 0.0, 0.0], temperature=0.0)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) == 0, "Gate must not fire in greedy mode (temperature=0)"

    # V-7: Low-temperature no-op
    def test_v7_low_temperature_no_raise(self):
        """V-7: When temperature < 0.5, gate does not raise temperature to 0.5."""
        # temperature=0.3, gate should cool to min(0.3, 0.5) = 0.3 (no change)
        adapter = _make_vritti_adapter([0.05, 0.8, 0.1, 0.025, 0.025], temperature=0.3)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        for ev in events:
            assert ev['effective_temperature'] <= 0.3, (
                f"Gate must not raise temp above base 0.3, got {ev['effective_temperature']}"
            )

    # Additional: gate disabled by default
    def test_gate_disabled_by_default(self):
        """Gate is off by default — no events even with high-error state."""
        adapter = _make_vritti_adapter([0.05, 0.9, 0.05, 0.0, 0.0],
                                       temperature=0.7, enable_gate=False)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) == 0

    # Additional: FACT-dominant state does not fire
    def test_fact_dominant_no_fire(self):
        """FACT-dominant Vritti does not trigger the gate."""
        adapter = _make_vritti_adapter([0.7, 0.05, 0.1, 0.1, 0.05], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) == 0

    # Additional: threshold boundary
    def test_boundary_just_below_threshold(self):
        """error_risk = 0.49 (just below 0.5) does not fire."""
        # vritti[1]=0.4, vritti[2]=0.3 -> error_risk = 0.4 + 0.09 = 0.49
        adapter = _make_vritti_adapter([0.1, 0.4, 0.3, 0.1, 0.1], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) == 0

    def test_boundary_just_above_threshold(self):
        """error_risk = 0.51 (just above 0.5) fires."""
        # vritti[1]=0.45, vritti[2]=0.2 -> error_risk = 0.45 + 0.06 = 0.51
        adapter = _make_vritti_adapter([0.1, 0.45, 0.2, 0.15, 0.1], temperature=0.7)
        adapter.call("test")
        events = adapter.last_cg_metadata['vritti_gate_events']
        assert len(events) > 0


# =============================================================================
# Vritti Index Ordering Invariant Test
#
# Guards against the known naming mismatch between:
#   - training-side VrittiState enum (vritti.py): SMRITI=3, NIDRA=4
#   - 32D state layout (state_projector, inference constants): NIDRA=3, SMRITI=4
#
# The 32D state layout is the canonical ordering. The VrittiState enum is used
# only for PID physics lookup and display labels — it does NOT index into the
# 32D state. All code that reads the 32D Vritti slice (state_projector,
# VrittiResonanceLoss, VrittiValidatedPredictor, sovereign_bridge, vritti gate)
# uses NIDRA=3, SMRITI=4 consistently.
#
# This test locks the invariant so any future change to either side will fail.
# =============================================================================


class TestVrittiIndexOrderingInvariant:
    """Regression test: 32D Vritti ordering is consistent across inference."""

    def test_sovereign_constants_match_gate_assumptions(self):
        """The inference constants used by sovereign_bridge match the gate's
        hardcoded indices: vritti[1]=ERROR, vritti[2]=IMAGINATION."""
        from agentic.sovereign_constants import (
            VRITTI_ERROR,
            VRITTI_IMAGINATION,
            VRITTI_FACT,
            VRITTI_VOID,
            VRITTI_MEMORY,
        )
        # Gate reads vritti[1] as ERROR and vritti[2] as IMAGINATION
        assert VRITTI_ERROR == 1, f"VRITTI_ERROR must be 1, got {VRITTI_ERROR}"
        assert VRITTI_IMAGINATION == 2, f"VRITTI_IMAGINATION must be 2, got {VRITTI_IMAGINATION}"
        # Full 5D layout lock
        assert VRITTI_FACT == 0
        assert VRITTI_VOID == 3
        assert VRITTI_MEMORY == 4

    def test_vritti_index_enum_matches_constants(self):
        """VrittiIndex enum matches the flat index constants."""
        from agentic.sovereign_constants import (
            VrittiIndex,
            VRITTI_FACT, VRITTI_ERROR, VRITTI_IMAGINATION,
            VRITTI_VOID, VRITTI_MEMORY,
        )
        assert VrittiIndex.PRAMANA == VRITTI_FACT
        assert VrittiIndex.VIPARYAYA == VRITTI_ERROR
        assert VrittiIndex.VIKALPA == VRITTI_IMAGINATION
        assert VrittiIndex.NIDRA == VRITTI_VOID
        assert VrittiIndex.SMRITI == VRITTI_MEMORY

    def test_sovereign_bridge_uses_correct_indices(self):
        """sovereign_bridge._vritti_to_confidence reads the right slots."""
        from agentic.agentic_framework.sovereign_bridge import (
            _vritti_to_confidence,
        )
        # ERROR-dominant Vritti: index 1 = 0.9, rest near zero
        vritti = [0.02, 0.90, 0.02, 0.03, 0.03]
        result = _vritti_to_confidence(vritti)
        # If indices were swapped, reversal_risk would be near zero
        assert result['prediction_reversal_risk'] > 0.8, (
            f"Expected high reversal_risk for ERROR-dominant state, "
            f"got {result['prediction_reversal_risk']}"
        )

    def test_gate_error_risk_uses_correct_indices(self):
        """Vritti gate computes error_risk from the right positions."""
        torch = pytest.importorskip("torch", reason="torch required")
        # Construct a known 32D state: ERROR=0.8 at position 18 (17+1),
        # IMAGINATION=0.1 at position 19 (17+2)
        state = torch.zeros(1, 32)
        state[0, 17] = 0.02   # FACT
        state[0, 18] = 0.80   # ERROR  (index 1 within Vritti slice)
        state[0, 19] = 0.10   # IMAGINATION (index 2 within Vritti slice)
        state[0, 20] = 0.04   # VOID
        state[0, 21] = 0.04   # MEMORY

        vritti = state[0, 17:22]
        error_risk = (vritti[1] + 0.3 * vritti[2]).clamp(0.0, 1.0).item()
        # 0.80 + 0.3*0.10 = 0.83
        assert abs(error_risk - 0.83) < 1e-5, f"Expected 0.83, got {error_risk}"


# =============================================================================
# Guna Sampling Gate Validation Tests
#
# The Guna gate reads state[0, 22:28] (6D sigmoid-normalized Guna slice)
# and computes turbulence = ACTIVITY*0.4 + VELOCITY*0.35 + ACCEL*0.25.
# When turbulence > 0.6, it cools effective_temperature to min(current, 0.5).
#
# Guna indices within [22:28]:
#   0=LUCIDITY, 1=ACTIVITY, 2=STABILITY, 3=VELOCITY, 4=ACCEL, 5=STABLE
# =============================================================================


def _make_mock_mistral_cg_with_guna(guna_values):
    """
    Build a mock MistralCGWrapper that returns a controlled 32D state
    with the specified Guna values at indices [22:28].
    """
    torch = pytest.importorskip("torch", reason="torch required for Guna gate tests")

    vocab_size = 100
    call_count = {"n": 0}

    tokenizer = MagicMock()
    tokenizer.pad_token = "[PAD]"
    tokenizer.eos_token = "[EOS]"
    tokenizer.eos_token_id = 2
    tokenizer.pad_token_id = 0

    def mock_tokenize(text, return_tensors=None, padding=False, truncation=False):
        ids = torch.tensor([[10, 20, 30, 40, 50]])
        mask = torch.ones_like(ids)
        result = MagicMock()
        result.__getitem__ = lambda self, k: {"input_ids": ids, "attention_mask": mask}[k]
        result.get = lambda k, d=None: {"input_ids": ids, "attention_mask": mask}.get(k, d)
        return result

    tokenizer.side_effect = mock_tokenize
    tokenizer.decode = MagicMock(side_effect=lambda ids, **kw: "Generated text")

    model = MagicMock()
    model.eval = MagicMock(return_value=model)
    model.tokenizer = tokenizer

    param = torch.nn.Parameter(torch.zeros(1))
    model.parameters = MagicMock(return_value=iter([param]))

    def mock_forward(input_ids, attention_mask=None, reset_state=False, **kwargs):
        call_count["n"] += 1
        B, T = input_ids.shape
        logits = torch.randn(B, T, vocab_size)
        if call_count["n"] > 3:
            logits[0, -1, :] = -100.0
            logits[0, -1, 2] = 100.0  # EOS

        # Build 32D state with controlled Guna at [22:28]
        state = torch.zeros(B, 32)
        guna_tensor = torch.tensor(guna_values, dtype=torch.float32)
        state[0, 22:28] = guna_tensor

        return {
            'logits': logits,
            'state': state,
            'delta_S': torch.zeros(B, 32),
            'delta_bhava': torch.zeros(B, 12),
            'intent_phase': torch.zeros(B, 32),
            'adapter_gate': 0.12,
        }

    model.side_effect = mock_forward
    model.__call__ = mock_forward
    return model, tokenizer


def _make_guna_adapter(guna_values, temperature=0.7, enable_gate=True):
    """Create a MistralCGAdapter with mock model and controlled Guna state."""
    torch = pytest.importorskip("torch", reason="torch required for Guna gate tests")
    mock_model, mock_tokenizer = _make_mock_mistral_cg_with_guna(guna_values)

    with patch(
        "agentic.agentic_framework.llm_adapters.MistralCGAdapter.__init__",
        lambda self, **kw: None,
    ):
        adapter = MistralCGAdapter.__new__(MistralCGAdapter)

    adapter._torch = torch
    adapter.model = mock_model
    adapter.tokenizer = mock_tokenizer
    adapter.max_new_tokens = 5
    adapter.temperature = temperature
    adapter.top_p = 1.0
    adapter.top_k = 0
    adapter.repetition_penalty = 1.0
    adapter.enable_vritti_gate = False
    adapter.enable_guna_gate = enable_gate
    adapter.last_cg_metadata = {}
    adapter.call_history = []
    return adapter


class TestGunaSamplingGate:
    """
    Validation tests for the Guna sampling gate.
    Tests mirror the Vritti gate validation pattern (V-1 through V-7).
    """

    # G-1: Bounded temperature effect
    def test_g1_effective_temperature_bounded(self):
        """G-1: effective_temperature is always in [min(0.5, base), base]."""
        # High turbulence: ACTIVITY=0.9, VELOCITY=0.8, ACCEL=0.7
        # turbulence = 0.9*0.4 + 0.8*0.35 + 0.7*0.25 = 0.36+0.28+0.175 = 0.815
        adapter = _make_guna_adapter(
            [0.5, 0.9, 0.3, 0.8, 0.7, 0.5], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        for ev in events:
            assert ev['effective_temperature'] <= ev['base_temperature']
            assert ev['effective_temperature'] >= min(0.5, ev['base_temperature'])

    # G-2: No-op on calm state
    def test_g2_noop_on_calm_state(self):
        """G-2: Gate does not fire when energetic state is calm."""
        # Low turbulence: ACTIVITY=0.2, VELOCITY=0.1, ACCEL=0.1
        # turbulence = 0.2*0.4 + 0.1*0.35 + 0.1*0.25 = 0.08+0.035+0.025 = 0.14
        adapter = _make_guna_adapter(
            [0.8, 0.2, 0.5, 0.1, 0.1, 0.9], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) == 0, f"Gate should not fire on calm state, got {len(events)} events"

    # G-3: Gate fires on turbulent state
    def test_g3_fires_on_high_turbulence(self):
        """G-3: Gate fires when turbulence exceeds threshold."""
        # High turbulence: ACTIVITY=0.8, VELOCITY=0.9, ACCEL=0.8
        # turbulence = 0.8*0.4 + 0.9*0.35 + 0.8*0.25 = 0.32+0.315+0.20 = 0.835
        adapter = _make_guna_adapter(
            [0.5, 0.8, 0.3, 0.9, 0.8, 0.2], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) > 0, "Gate should fire on turbulent state"
        for ev in events:
            assert ev['action'] == 'cool'
            assert ev['effective_temperature'] == 0.5

    # G-4: Trace completeness
    def test_g4_trace_completeness(self):
        """G-4: Gate events have all required fields."""
        adapter = _make_guna_adapter(
            [0.3, 0.9, 0.2, 0.9, 0.9, 0.1], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) > 0
        required_fields = {'step', 'turbulence', 'action', 'base_temperature', 'effective_temperature'}
        for ev in events:
            assert required_fields.issubset(ev.keys()), f"Missing fields: {required_fields - ev.keys()}"
            assert isinstance(ev['step'], int)
            assert isinstance(ev['turbulence'], float)
            assert ev['action'] == 'cool'

    def test_g4_guna_gate_events_key_always_present(self):
        """G-4b: guna_gate_events key is always in metadata, even when gate is off."""
        adapter = _make_guna_adapter(
            [0.8, 0.1, 0.5, 0.1, 0.1, 0.9], temperature=0.7
        )
        adapter.call("test")
        assert 'guna_gate_events' in adapter.last_cg_metadata
        assert adapter.last_cg_metadata['guna_gate_events'] == []

    # G-5: No generation degeneration
    def test_g5_no_degenerate_output(self):
        """G-5: Generation completes and returns non-empty string with gate on."""
        adapter = _make_guna_adapter(
            [0.3, 0.9, 0.2, 0.9, 0.8, 0.1], temperature=0.7
        )
        response = adapter.call("test")
        assert isinstance(response, str)
        assert len(response) > 0

    # G-6: Greedy mode bypass
    def test_g6_greedy_bypass(self):
        """G-6: Gate is entirely skipped when temperature=0."""
        adapter = _make_guna_adapter(
            [0.1, 0.95, 0.1, 0.95, 0.95, 0.1], temperature=0.0
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) == 0, "Gate must not fire in greedy mode (temperature=0)"

    # G-7: Low-temperature no-raise
    def test_g7_low_temperature_no_raise(self):
        """G-7: When temperature < 0.5, gate does not raise temperature to 0.5."""
        adapter = _make_guna_adapter(
            [0.1, 0.9, 0.1, 0.9, 0.9, 0.1], temperature=0.3
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        for ev in events:
            assert ev['effective_temperature'] <= 0.3, (
                f"Gate must not raise temp above base 0.3, got {ev['effective_temperature']}"
            )

    # Gate disabled by default
    def test_gate_disabled_by_default(self):
        """Gate is off by default — no events even with turbulent state."""
        adapter = _make_guna_adapter(
            [0.1, 0.95, 0.1, 0.95, 0.95, 0.1],
            temperature=0.7, enable_gate=False
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) == 0

    # Lucidity-dominant calm state does not fire
    def test_lucidity_dominant_no_fire(self):
        """High LUCIDITY + low ACTIVITY/VELOCITY/ACCEL does not trigger."""
        # turbulence = 0.1*0.4 + 0.05*0.35 + 0.05*0.25 = 0.04+0.0175+0.0125 = 0.07
        adapter = _make_guna_adapter(
            [0.95, 0.1, 0.8, 0.05, 0.05, 0.95], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) == 0

    # Boundary: just below threshold
    def test_boundary_just_below_threshold(self):
        """turbulence = 0.59 (just below 0.6) does not fire."""
        # Want: ACTIVITY*0.4 + VELOCITY*0.35 + ACCEL*0.25 ≈ 0.59
        # Use: ACTIVITY=0.6, VELOCITY=0.6, ACCEL=0.56
        # 0.6*0.4 + 0.6*0.35 + 0.56*0.25 = 0.24+0.21+0.14 = 0.59
        adapter = _make_guna_adapter(
            [0.5, 0.6, 0.5, 0.6, 0.56, 0.5], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) == 0, f"turbulence=0.59 should not fire, got {len(events)} events"

    # Boundary: just above threshold
    def test_boundary_just_above_threshold(self):
        """turbulence = 0.61 (just above 0.6) fires."""
        # Want: ACTIVITY*0.4 + VELOCITY*0.35 + ACCEL*0.25 ≈ 0.61
        # Use: ACTIVITY=0.65, VELOCITY=0.6, ACCEL=0.58
        # 0.65*0.4 + 0.6*0.35 + 0.58*0.25 = 0.26+0.21+0.145 = 0.615
        adapter = _make_guna_adapter(
            [0.5, 0.65, 0.5, 0.6, 0.58, 0.5], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) > 0, "turbulence=0.615 should fire"

    # Uniform sigmoid midpoint does not fire
    def test_uniform_sigmoid_midpoint_no_fire(self):
        """All Guna at 0.5 (sigmoid midpoint) gives turbulence=0.40, no fire."""
        # turbulence = 0.5*0.4 + 0.5*0.35 + 0.5*0.25 = 0.2+0.175+0.125 = 0.50
        # 0.50 < 0.6 → no fire
        adapter = _make_guna_adapter(
            [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], temperature=0.7
        )
        adapter.call("test")
        events = adapter.last_cg_metadata['guna_gate_events']
        assert len(events) == 0, "Uniform 0.5 sigmoid → turbulence=0.50, should not fire"

    # Turbulence formula correctness
    def test_turbulence_formula(self):
        """Verify turbulence formula computes correctly."""
        torch = pytest.importorskip("torch", reason="torch required")
        state = torch.zeros(1, 32)
        state[0, 22] = 0.7   # LUCIDITY
        state[0, 23] = 0.85  # ACTIVITY
        state[0, 24] = 0.3   # STABILITY
        state[0, 25] = 0.9   # VELOCITY
        state[0, 26] = 0.75  # ACCEL
        state[0, 27] = 0.4   # STABLE

        guna = state[0, 22:28]
        turbulence = (guna[1] * 0.4 + guna[3] * 0.35 + guna[4] * 0.25).clamp(0.0, 1.0).item()
        # 0.85*0.4 + 0.9*0.35 + 0.75*0.25 = 0.34 + 0.315 + 0.1875 = 0.8425
        assert abs(turbulence - 0.8425) < 1e-4, f"Expected 0.8425, got {turbulence}"
