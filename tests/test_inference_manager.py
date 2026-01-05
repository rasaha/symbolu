"""
Tests for InferenceManager
==========================

Tests for the tiered inference pipeline orchestrator:
- Mode switching (Fast/Standard/Sovereign)
- Component lazy initialization
- Generation across all modes
- Metrics and status reporting
"""

import pytest
import torch
import torch.nn as nn
from typing import Dict, List, Optional


# =============================================================================
# Mock Model for Testing
# =============================================================================

class MockTransformer(nn.Module):
    """
    Mock transformer for InferenceManager testing.

    Supports all required features:
    - extract_layers for efficient hidden state extraction
    - return_last_hidden for CSR re-projection
    - lm_head access
    """

    def __init__(
        self,
        vocab_size: int = 1000,
        embed_dim: int = 256,
        num_layers: int = 12,
    ):
        super().__init__()
        self.config = type('Config', (), {
            'embed_dim': embed_dim,
            'vocab_size': vocab_size,
            'num_layers': num_layers,
            'eos_token_id': 2,
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
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@pytest.fixture
def mock_model(device):
    model = MockTransformer(vocab_size=1000, embed_dim=256, num_layers=12)
    return model.to(device)


@pytest.fixture
def input_ids(device):
    return torch.randint(0, 100, (1, 5), device=device)


# =============================================================================
# Mode Tests
# =============================================================================

class TestInferenceModes:
    """Test inference mode enumeration and switching."""

    def test_mode_enum_values(self):
        """InferenceMode has correct values."""
        from symbolu.inference import InferenceMode

        assert InferenceMode.FAST.value == "fast"
        assert InferenceMode.STANDARD.value == "standard"
        assert InferenceMode.SOVEREIGN.value == "sovereign"

    def test_manager_default_mode(self, mock_model):
        """Manager defaults to STANDARD mode."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model)
        assert manager.mode == InferenceMode.STANDARD

    def test_manager_explicit_mode(self, mock_model):
        """Manager accepts explicit mode."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)
        assert manager.mode == InferenceMode.FAST

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)
        assert manager.mode == InferenceMode.SOVEREIGN

    def test_mode_switching(self, mock_model):
        """Manager supports runtime mode switching."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)
        assert manager.mode == InferenceMode.FAST

        manager.set_mode(InferenceMode.STANDARD)
        assert manager.mode == InferenceMode.STANDARD

        manager.set_mode(InferenceMode.SOVEREIGN)
        assert manager.mode == InferenceMode.SOVEREIGN

    def test_mode_history_tracked(self, mock_model):
        """Mode history is tracked."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)
        manager.set_mode(InferenceMode.STANDARD)
        manager.set_mode(InferenceMode.SOVEREIGN)

        assert len(manager.mode_history) == 2
        assert manager.mode_history[0] == InferenceMode.FAST
        assert manager.mode_history[1] == InferenceMode.STANDARD


# =============================================================================
# Component Initialization Tests
# =============================================================================

class TestComponentInitialization:
    """Test lazy component initialization."""

    def test_fast_mode_minimal_components(self, mock_model):
        """FAST mode has no components initialized."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)

        assert manager.engine is None
        assert manager.gunas is None
        assert manager.metacognition is None
        assert manager.csr_guard is None
        assert manager.scorer is None

    def test_standard_mode_components(self, mock_model):
        """STANDARD mode has engine and gunas."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.STANDARD)

        assert manager.engine is not None
        assert manager.gunas is not None
        assert manager.metacognition is None
        assert manager.csr_guard is None
        assert manager.scorer is None

    def test_sovereign_mode_all_components(self, mock_model):
        """SOVEREIGN mode has all components."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)

        assert manager.engine is not None
        assert manager.gunas is not None
        assert manager.metacognition is not None
        assert manager.csr_guard is not None
        assert manager.scorer is not None

    def test_lazy_initialization_on_mode_switch(self, mock_model):
        """Components are lazily initialized on mode switch."""
        from symbolu.inference import InferenceManager, InferenceMode

        # Start in FAST (no components)
        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)
        assert manager.engine is None

        # Switch to STANDARD (should init engine)
        manager.set_mode(InferenceMode.STANDARD)
        assert manager.engine is not None
        assert manager.metacognition is None

        # Switch to SOVEREIGN (should init remaining)
        manager.set_mode(InferenceMode.SOVEREIGN)
        assert manager.metacognition is not None
        assert manager.csr_guard is not None


# =============================================================================
# Generation Tests
# =============================================================================

class TestGeneration:
    """Test generation across all modes."""

    def test_fast_mode_generation(self, mock_model, input_ids):
        """FAST mode generates tokens."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)

        output, metrics = manager.generate(
            input_ids,
            max_new_tokens=5,
        )

        assert output.shape[1] > input_ids.shape[1]
        assert metrics['mode'] == 'fast'
        assert 'tokens_generated' in metrics

    def test_standard_mode_generation(self, mock_model, input_ids):
        """STANDARD mode generates with karma."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.STANDARD)

        output, metrics = manager.generate(
            input_ids,
            max_new_tokens=5,
        )

        assert output.shape[1] > input_ids.shape[1]
        assert metrics['mode'] == 'standard'
        assert 'karma_stored' in metrics
        assert 'final_gunas' in metrics

    def test_sovereign_mode_generation(self, mock_model, input_ids):
        """SOVEREIGN mode generates with full pipeline."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)

        output, metrics = manager.generate(
            input_ids,
            max_new_tokens=5,
        )

        assert output.shape[1] > input_ids.shape[1]
        assert metrics['mode'] == 'sovereign'
        assert 'karma_stored' in metrics
        assert 'final_gunas' in metrics
        assert 'metacognition' in metrics
        assert 'csr_statistics' in metrics

    def test_sovereign_alignment_scoring(self, mock_model, input_ids):
        """SOVEREIGN mode computes alignment score."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)

        output, metrics = manager.generate(
            input_ids,
            max_new_tokens=5,
            compute_alignment=True,
        )

        assert 'sovereign_score' in metrics
        assert 'sovereign_info' in metrics
        assert 0 <= metrics['sovereign_score'] <= 1

    def test_karma_persistence_across_calls(self, mock_model, input_ids):
        """Karma persists across generation calls."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.STANDARD)

        # First generation - store karma
        _, metrics1 = manager.generate(
            input_ids,
            max_new_tokens=5,
            store_karma=True,
        )
        assert metrics1['karma_stored'] == True

        # Second generation - should inject karma
        _, metrics2 = manager.generate(
            input_ids,
            max_new_tokens=5,
            inject_karma=True,
        )
        assert metrics2['karma_injected'] == True


# =============================================================================
# Status and Metrics Tests
# =============================================================================

class TestStatusAndMetrics:
    """Test status reporting and detailed metrics."""

    def test_detailed_metrics(self, mock_model, input_ids):
        """Detailed metrics include component status."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)

        _, metrics = manager.generate(
            input_ids,
            max_new_tokens=3,
            return_detailed_metrics=True,
        )

        assert 'component_status' in metrics
        status = metrics['component_status']
        assert 'engine' in status
        assert 'gunas' in status
        assert 'metacognition' in status
        assert 'csr_guard' in status

    def test_status_line(self, mock_model, input_ids):
        """Status line is formatted correctly."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)
        manager.generate(input_ids, max_new_tokens=3)

        status_line = manager.get_status_line()
        assert "[SOVEREIGN]" in status_line
        assert "Karma:" in status_line

    def test_karma_status(self, mock_model, input_ids):
        """Karma status string is available."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.STANDARD)
        manager.generate(input_ids, max_new_tokens=3)

        status = manager.get_karma_status()
        assert "Karma:" in status

    def test_clear_karma(self, mock_model, input_ids):
        """Karma can be cleared."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.STANDARD)

        # Generate to create karma
        manager.generate(input_ids, max_new_tokens=3)

        # Clear karma
        manager.clear_karma()

        # Engine karma buffer should be None
        assert manager.engine.karma_buffer is None


# =============================================================================
# Repr and Configuration Tests
# =============================================================================

class TestConfiguration:
    """Test configuration and repr."""

    def test_repr(self, mock_model):
        """Repr shows mode and components."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.SOVEREIGN)
        repr_str = repr(manager)

        assert "InferenceManager" in repr_str
        assert "sovereign" in repr_str
        assert "dim=256" in repr_str

    def test_custom_configuration(self, mock_model):
        """Custom configuration is respected."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(
            mock_model,
            mode=InferenceMode.SOVEREIGN,
            resonance_alpha=0.2,
            alarm_threshold=0.5,
            entropy_threshold=3.0,
        )

        # Check engine config
        assert manager.engine.resonance_alpha == 0.2

        # Check metacognition config
        assert manager.metacognition.alarm_threshold == 0.5

        # Check CSR config
        assert manager.csr_guard.entropy_threshold == 3.0

    def test_generation_count_tracked(self, mock_model, input_ids):
        """Generation count is tracked."""
        from symbolu.inference import InferenceManager, InferenceMode

        manager = InferenceManager(mock_model, mode=InferenceMode.FAST)

        assert manager.generation_count == 0

        manager.generate(input_ids, max_new_tokens=3)
        assert manager.generation_count == 1

        manager.generate(input_ids, max_new_tokens=3)
        assert manager.generation_count == 2
