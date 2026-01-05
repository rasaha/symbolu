"""
Unit Tests for Evolutionary Inference Engine
=============================================

Tests for Phase 1 deliverables:
- EvolutionaryBridgeInference: Seed projection, weight loading
- EvolutionaryInferenceEngine: Karma persistence, resonance injection
- extract_layers: Efficient hidden state extraction

Critical checks:
1. Karma buffer persists across generate calls
2. Resonance injection modifies hidden states correctly
3. Dynamic alpha scales with Guna state
4. Toroidal coherence computation is correct
5. State serialization/deserialization works
6. extract_layers returns correct layer mappings
"""

import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from typing import Dict, List, Optional


# =============================================================================
# Mock Model for Testing
# =============================================================================

class MockTransformer(nn.Module):
    """
    Minimal transformer mock for testing EvolutionaryInferenceEngine.

    Simulates HybridPhaseTransformer API with:
    - 12 layers
    - extract_layers support
    - return_hidden support
    """

    def __init__(self, vocab_size: int = 1000, embed_dim: int = 256, num_layers: int = 12):
        super().__init__()
        self.config = type('Config', (), {
            'embed_dim': embed_dim,
            'vocab_size': vocab_size,
            'num_layers': num_layers,
        })()

        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.layers = nn.ModuleList([
            nn.Linear(embed_dim, embed_dim) for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, torch.Tensor]:
        x = self.token_embed(input_ids)

        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        hidden_states = [] if should_extract else None

        for i, layer in enumerate(self.layers):
            x = layer(x) + x  # Residual

            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        x = self.norm(x)
        logits = self.lm_head(x)

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        return result


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def device():
    """Use CUDA if available, else CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@pytest.fixture
def model_params():
    """Standard model parameters."""
    return {
        "vocab_size": 1000,
        "embed_dim": 256,
        "num_layers": 12,
    }


@pytest.fixture
def mock_model(model_params, device):
    """Create mock transformer model."""
    model = MockTransformer(**model_params)
    return model.to(device)


@pytest.fixture
def inference_engine(mock_model):
    """Create EvolutionaryInferenceEngine with mock model."""
    from symbolu.inference import EvolutionaryInferenceEngine
    return EvolutionaryInferenceEngine(mock_model)


# =============================================================================
# EvolutionaryBridgeInference Tests
# =============================================================================

class TestEvolutionaryBridgeInference:
    """Tests for the seed projection bridge."""

    def test_bridge_initialization(self, model_params, device):
        """Bridge initializes with correct dimensions."""
        from symbolu.inference.evolutionary_inference import EvolutionaryBridgeInference

        dim = model_params['embed_dim']
        bridge = EvolutionaryBridgeInference(dim, use_gating=True).to(device)

        assert bridge.seed_gate is not None
        assert bridge.seed_proj is not None
        assert bridge.seed_norm is not None
        assert bridge.seed_gate.weight.shape == (dim, dim)

    def test_bridge_no_gating(self, model_params, device):
        """Bridge works without gating."""
        from symbolu.inference.evolutionary_inference import EvolutionaryBridgeInference

        dim = model_params['embed_dim']
        bridge = EvolutionaryBridgeInference(dim, use_gating=False).to(device)

        assert bridge.seed_gate is None
        assert bridge.seed_proj is not None

    def test_compute_seed_2d(self, model_params, device):
        """Seed computation works for [B, D] input."""
        from symbolu.inference.evolutionary_inference import EvolutionaryBridgeInference

        dim = model_params['embed_dim']
        bridge = EvolutionaryBridgeInference(dim).to(device)

        harvest = torch.randn(2, dim, device=device)
        seed = bridge.compute_seed(harvest)

        assert seed.shape == (2, dim)
        assert not torch.isnan(seed).any()

    def test_compute_seed_3d(self, model_params, device):
        """Seed computation reduces [B, N, D] to [B, D]."""
        from symbolu.inference.evolutionary_inference import EvolutionaryBridgeInference

        dim = model_params['embed_dim']
        bridge = EvolutionaryBridgeInference(dim).to(device)

        harvest = torch.randn(2, 16, dim, device=device)
        seed = bridge.compute_seed(harvest)

        assert seed.shape == (2, dim)
        assert not torch.isnan(seed).any()


# =============================================================================
# Karma Persistence Tests
# =============================================================================

class TestKarmaPersistence:
    """Tests for karma buffer persistence across sequences."""

    def test_karma_initially_none(self, inference_engine):
        """Karma buffer starts as None."""
        assert inference_engine.karma_buffer is None

    def test_karma_stored_after_generation(self, inference_engine, device):
        """Karma buffer is populated after generate_with_karma."""
        input_ids = torch.randint(0, 100, (1, 10), device=device)

        # Enable bridge for karma storage
        inference_engine.bridge_enabled = True

        output_ids, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            store_karma=True,
        )

        assert inference_engine.karma_buffer is not None
        assert metrics['karma_stored'] == True

    def test_karma_persists_across_calls(self, inference_engine, device):
        """Karma buffer persists between generation calls."""
        input_ids = torch.randint(0, 100, (1, 10), device=device)
        inference_engine.bridge_enabled = True

        # First generation
        inference_engine.generate_with_karma(input_ids, max_new_tokens=3, store_karma=True)
        karma_1 = inference_engine.karma_buffer.clone()

        # Second generation
        inference_engine.generate_with_karma(input_ids, max_new_tokens=3, store_karma=True)
        karma_2 = inference_engine.karma_buffer.clone()

        # Karma should be different (updated with new O12)
        assert not torch.allclose(karma_1, karma_2)

    def test_karma_decay(self, inference_engine, device):
        """Karma decay reduces buffer magnitude."""
        dim = inference_engine.dim
        inference_engine.karma_buffer = torch.ones(1, dim, device=device)
        initial_norm = inference_engine.karma_buffer.norm().item()

        inference_engine.apply_karma_decay()

        decayed_norm = inference_engine.karma_buffer.norm().item()
        assert decayed_norm < initial_norm
        assert decayed_norm == pytest.approx(initial_norm * inference_engine.karma_decay, rel=1e-5)

    def test_clear_karma(self, inference_engine, device):
        """clear_karma resets all state."""
        dim = inference_engine.dim
        inference_engine.karma_buffer = torch.randn(1, dim, device=device)
        inference_engine.current_o12 = torch.randn(1, 16, dim, device=device)
        inference_engine.coherence_history = [0.5, 0.6, 0.7]
        inference_engine.generation_count = 5

        inference_engine.clear_karma()

        assert inference_engine.karma_buffer is None
        assert inference_engine.current_o12 is None
        assert len(inference_engine.coherence_history) == 0
        assert inference_engine.generation_count == 0


# =============================================================================
# Resonance Injection Tests
# =============================================================================

class TestResonanceInjection:
    """Tests for delayed resonance injection."""

    def test_resonance_no_karma(self, inference_engine, device):
        """Resonance returns unchanged tensor when no karma."""
        hidden = torch.randn(2, 16, 256, device=device)

        result = inference_engine.apply_inference_resonance(hidden)

        assert torch.allclose(result, hidden)

    def test_resonance_with_karma_2d(self, inference_engine, device):
        """Resonance injects karma into [B, D] hidden state."""
        dim = inference_engine.dim
        hidden = torch.zeros(2, dim, device=device)
        inference_engine.karma_buffer = torch.ones(2, dim, device=device)

        result = inference_engine.apply_inference_resonance(hidden, alpha=0.1)

        expected = 0.1 * torch.ones(2, dim, device=device)
        assert torch.allclose(result, expected)

    def test_resonance_with_karma_3d(self, inference_engine, device):
        """Resonance broadcasts karma across sequence dimension."""
        dim = inference_engine.dim
        hidden = torch.zeros(2, 16, dim, device=device)
        inference_engine.karma_buffer = torch.ones(2, dim, device=device)

        result = inference_engine.apply_inference_resonance(hidden, alpha=0.1)

        assert result.shape == (2, 16, dim)
        assert torch.allclose(result, 0.1 * torch.ones_like(result))

    def test_dynamic_alpha_sattva_high(self, inference_engine):
        """High Sattva increases resonance alpha."""
        inference_engine.resonance_alpha = 0.1
        inference_engine.current_gunas = (0.8, 0.1, 0.1)  # High Sattva

        alpha = inference_engine._compute_dynamic_alpha()

        # With s=0.8, r=0.1: alpha = 0.1 * (1.0 + 0.8*1.5 - 0.1*0.5) = 0.1 * 2.15 = 0.215
        assert alpha > inference_engine.resonance_alpha
        assert 0.05 <= alpha <= 0.25

    def test_dynamic_alpha_rajas_high(self, inference_engine):
        """High Rajas decreases resonance alpha."""
        inference_engine.resonance_alpha = 0.1
        inference_engine.current_gunas = (0.1, 0.8, 0.1)  # High Rajas

        alpha = inference_engine._compute_dynamic_alpha()

        # With s=0.1, r=0.8: alpha = 0.1 * (1.0 + 0.1*1.5 - 0.8*0.5) = 0.1 * 0.75 = 0.075
        assert alpha < inference_engine.resonance_alpha
        assert 0.05 <= alpha <= 0.25


# =============================================================================
# Coherence Tests
# =============================================================================

class TestCoherence:
    """Tests for toroidal coherence computation."""

    def test_coherence_no_state(self, inference_engine):
        """Coherence returns 0.5 with no prior state."""
        coherence = inference_engine.compute_generation_coherence()
        assert coherence == 0.5

    def test_coherence_identical_states(self, inference_engine, device):
        """Coherence is 1.0 for identical states."""
        dim = inference_engine.dim
        state = torch.randn(1, dim, device=device)

        inference_engine.karma_buffer = state
        inference_engine.current_o12 = state.unsqueeze(1)  # [B, 1, D]

        coherence = inference_engine.compute_generation_coherence()

        assert coherence == pytest.approx(1.0, rel=1e-4)

    def test_coherence_orthogonal_states(self, inference_engine, device):
        """Coherence is 0.5 for orthogonal states."""
        dim = inference_engine.dim

        # Create orthogonal vectors
        karma = torch.zeros(1, dim, device=device)
        karma[0, 0] = 1.0

        o12 = torch.zeros(1, 1, dim, device=device)
        o12[0, 0, dim//2] = 1.0

        inference_engine.karma_buffer = karma
        inference_engine.current_o12 = o12

        coherence = inference_engine.compute_generation_coherence()

        # Cosine similarity of orthogonal = 0, mapped to [0,1] = 0.5
        assert coherence == pytest.approx(0.5, rel=1e-4)

    def test_coherence_history_tracking(self, inference_engine, device):
        """Coherence values are tracked in history."""
        dim = inference_engine.dim
        inference_engine.karma_buffer = torch.randn(1, dim, device=device)
        inference_engine.current_o12 = torch.randn(1, 16, dim, device=device)

        for _ in range(5):
            inference_engine.compute_generation_coherence()

        assert len(inference_engine.coherence_history) == 5


# =============================================================================
# State Serialization Tests
# =============================================================================

class TestStateSerialization:
    """Tests for state save/load."""

    def test_get_state_dict(self, inference_engine, device):
        """get_state_dict returns all required fields."""
        dim = inference_engine.dim
        inference_engine.karma_buffer = torch.randn(1, dim, device=device)
        inference_engine.coherence_history = [0.5, 0.6]
        inference_engine.generation_count = 3
        inference_engine.current_gunas = (0.5, 0.3, 0.2)

        state = inference_engine.get_state_dict()

        assert 'karma_buffer' in state
        assert 'coherence_history' in state
        assert 'generation_count' in state
        assert 'current_gunas' in state
        assert 'resonance_alpha' in state

    def test_load_state_dict(self, inference_engine, device):
        """load_state_dict restores state correctly."""
        dim = inference_engine.dim
        karma = torch.randn(1, dim)

        state = {
            'karma_buffer': karma,
            'coherence_history': [0.7, 0.8],
            'generation_count': 10,
            'current_gunas': (0.6, 0.2, 0.2),
            'resonance_alpha': 0.15,
        }

        inference_engine.load_state_dict(state)

        assert torch.allclose(inference_engine.karma_buffer, karma.to(device))
        assert inference_engine.coherence_history == [0.7, 0.8]
        assert inference_engine.generation_count == 10
        assert inference_engine.current_gunas == (0.6, 0.2, 0.2)
        assert inference_engine.resonance_alpha == 0.15


# =============================================================================
# Layer Extraction Tests
# =============================================================================

class TestLayerExtraction:
    """Tests for efficient layer extraction."""

    def test_extract_specific_layers(self, inference_engine, device):
        """_extract_layer_states returns only requested layers."""
        input_ids = torch.randint(0, 100, (1, 10), device=device)

        logits, layer_states = inference_engine._extract_layer_states(
            input_ids,
            extract_layers=[0, 5, 11],
        )

        assert len(layer_states) == 3
        assert 0 in layer_states
        assert 5 in layer_states
        assert 11 in layer_states

    def test_extract_default_layers(self, inference_engine, device):
        """Default extraction returns O1 and O12."""
        input_ids = torch.randint(0, 100, (1, 10), device=device)

        logits, layer_states = inference_engine._extract_layer_states(input_ids)

        assert len(layer_states) == 2
        assert 0 in layer_states
        assert 11 in layer_states

    def test_extract_layers_correct_shapes(self, inference_engine, device):
        """Extracted layers have correct tensor shapes."""
        input_ids = torch.randint(0, 100, (2, 16), device=device)
        dim = inference_engine.dim

        logits, layer_states = inference_engine._extract_layer_states(
            input_ids,
            extract_layers=[0, 11],
        )

        for layer_idx, state in layer_states.items():
            assert state.shape == (2, 16, dim)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_generation_cycle(self, inference_engine, device):
        """Full generation cycle with karma persistence."""
        input_ids = torch.randint(0, 100, (1, 10), device=device)
        inference_engine.bridge_enabled = True

        # First generation - no prior karma
        output_1, metrics_1 = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            inject_karma=True,
            store_karma=True,
            return_coherence=True,
        )

        assert metrics_1['karma_stored'] == True
        assert 'karma_coherence' in metrics_1

        # Second generation - uses karma from first
        output_2, metrics_2 = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            inject_karma=True,
            store_karma=True,
            return_coherence=True,
        )

        assert metrics_2['karma_stored'] == True
        # Coherence should be computed between sequences
        assert 'karma_coherence' in metrics_2

    def test_guna_update_affects_alpha(self, inference_engine, device):
        """Updating Gunas affects dynamic alpha calculation."""
        inference_engine.resonance_alpha = 0.1

        # Balanced state
        inference_engine.update_gunas(0.33, 0.33, 0.33)
        alpha_balanced = inference_engine._compute_dynamic_alpha()

        # High Sattva
        inference_engine.update_gunas(0.8, 0.1, 0.1)
        alpha_sattva = inference_engine._compute_dynamic_alpha()

        # High Rajas
        inference_engine.update_gunas(0.1, 0.8, 0.1)
        alpha_rajas = inference_engine._compute_dynamic_alpha()

        assert alpha_sattva > alpha_balanced > alpha_rajas
