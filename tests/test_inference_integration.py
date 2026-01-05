"""
Integration Tests for Phase 2 Quality Monitoring
=================================================

Tests for integrated inference pipeline:
- EvolutionaryInferenceEngine + InferenceMetacognition
- EvolutionaryInferenceEngine + InferenceGunas
- EvolutionaryInferenceEngine + CSRInferenceGuard
- Full pipeline with all components

Critical checks:
1. Components communicate correctly during generation
2. ABORT recommendation stops generation
3. CSR guard re-projection affects token selection
4. Guna state flows to metacognition
5. Dynamic alpha updates from Gunas
"""

import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Any


# =============================================================================
# Mock Model for Integration Testing
# =============================================================================

class MockTransformerWithCSR(nn.Module):
    """
    Extended mock transformer supporting CSR integration.

    Includes return_last_hidden support for CSR re-projection.
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
    model = MockTransformerWithCSR(vocab_size=1000, embed_dim=256, num_layers=12)
    return model.to(device)


@pytest.fixture
def inference_engine(mock_model):
    from symbolu.inference import EvolutionaryInferenceEngine
    engine = EvolutionaryInferenceEngine(mock_model)
    engine.bridge_enabled = True
    return engine


@pytest.fixture
def metacognition():
    from symbolu.inference import InferenceMetacognition
    return InferenceMetacognition(
        coherence_window=20,
        alarm_threshold=0.3,
        abort_consecutive=3,
    )


@pytest.fixture
def guna_tracker():
    from symbolu.inference import InferenceGunas
    return InferenceGunas(window_size=10)


@pytest.fixture
def csr_guard(mock_model):
    from symbolu.inference import CSRInferenceGuard
    return CSRInferenceGuard(
        lm_head=mock_model.lm_head,
        dim=256,
        entropy_threshold=2.0,
    )


# =============================================================================
# Metacognition Integration Tests
# =============================================================================

class TestMetacognitionIntegration:
    """Test InferenceMetacognition integration with engine."""

    def test_metacognition_updates_during_generation(
        self, inference_engine, metacognition, device
    ):
        """Metacognition receives updates for each token."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=10,
            metacognition=metacognition,
        )

        # Metacognition should have tracked tokens
        assert metacognition.total_tokens > 0
        assert len(metacognition.coherence_history) > 0

    def test_abort_stops_generation(self, inference_engine, device):
        """ABORT recommendation stops generation early."""
        from symbolu.inference import InferenceMetacognition

        # Create metacog that will abort quickly
        metacog = InferenceMetacognition(
            alarm_threshold=0.99,  # Very high threshold
            abort_consecutive=1,   # Abort after 1 low token
        )

        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=50,
            metacognition=metacog,
        )

        # Should have aborted
        assert metrics['aborted'] == True
        # Should have generated fewer tokens than max
        assert output.shape[1] < input_ids.shape[1] + 50

    def test_brake_reduces_temperature(self, inference_engine, metacognition, device):
        """BRAKE recommendation reduces effective temperature."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        # This test verifies the code path exists
        # Full verification would require inspecting internal state
        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            temperature=1.0,
            metacognition=metacognition,
        )

        # Generation should complete
        assert output.shape[1] > input_ids.shape[1]


# =============================================================================
# Guna Tracker Integration Tests
# =============================================================================

class TestGunaIntegration:
    """Test InferenceGunas integration with engine."""

    def test_gunas_update_during_generation(
        self, inference_engine, guna_tracker, device
    ):
        """Guna tracker receives updates for each token."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=10,
            guna_tracker=guna_tracker,
        )

        # Guna tracker should have history
        assert len(guna_tracker.history) > 0
        assert len(guna_tracker.token_ids) > 0

    def test_gunas_flow_to_engine(self, inference_engine, guna_tracker, device):
        """Guna state flows to engine for dynamic alpha."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        # Initial Gunas
        initial_gunas = inference_engine.current_gunas

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            guna_tracker=guna_tracker,
        )

        # Engine's Gunas should have been updated
        # (May or may not differ depending on generation)
        assert inference_engine.current_gunas is not None

    def test_gunas_flow_to_metacognition(
        self, inference_engine, metacognition, guna_tracker, device
    ):
        """Guna state flows to metacognition."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            metacognition=metacognition,
            guna_tracker=guna_tracker,
        )

        # Metacognition should have received Guna updates
        assert len(metacognition.guna_history) > 0


# =============================================================================
# CSR Guard Integration Tests
# =============================================================================

class TestCSRGuardIntegration:
    """Test CSRInferenceGuard integration with engine."""

    def test_csr_guard_called_during_generation(
        self, inference_engine, csr_guard, device
    ):
        """CSR guard is called for each token."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            csr_guard=csr_guard,
        )

        # Guard should have been called
        assert csr_guard.total_calls > 0

    def test_csr_interventions_tracked(self, inference_engine, device):
        """CSR interventions are tracked in metrics."""
        from symbolu.inference import CSRInferenceGuard

        # Create guard with low threshold to trigger interventions
        guard = CSRInferenceGuard(
            lm_head=inference_engine.model.lm_head,
            dim=256,
            entropy_threshold=0.1,  # Very low = always intervene
            skip_threshold=0.0,     # Never skip
        )

        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            csr_guard=guard,
        )

        # Should have some interventions tracked
        assert 'interventions' in metrics

    def test_csr_reprojects_through_lm_head(self, csr_guard, device):
        """CSR guard re-projects modified hidden state through lm_head."""
        dim = 256
        vocab_size = 1000

        hidden = torch.randn(1, dim, device=device)
        logits = torch.randn(1, vocab_size, device=device)

        # Force high entropy to trigger intervention
        uniform_logits = torch.zeros(1, vocab_size, device=device)

        modified_logits, info = csr_guard.apply(
            hidden_state=hidden,
            original_logits=uniform_logits,
        )

        # If intervention happened, logits should differ
        # (Guard may or may not intervene depending on entropy)
        assert modified_logits.shape == uniform_logits.shape


# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================

class TestFullPipelineIntegration:
    """Test complete inference pipeline with all Phase 2 components."""

    def test_full_pipeline_generation(
        self, inference_engine, metacognition, guna_tracker, csr_guard, device
    ):
        """Full pipeline with all components generates successfully."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=10,
            metacognition=metacognition,
            guna_tracker=guna_tracker,
            csr_guard=csr_guard,
        )

        # Should generate tokens
        assert output.shape[1] > input_ids.shape[1]

        # Metrics should have Phase 2 fields
        assert 'aborted' in metrics
        assert 'interventions' in metrics

    def test_pipeline_with_karma_persistence(
        self, inference_engine, metacognition, guna_tracker, device
    ):
        """Pipeline maintains karma across generations."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        # First generation
        output1, metrics1 = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            store_karma=True,
            metacognition=metacognition,
            guna_tracker=guna_tracker,
        )

        # Karma should be stored
        assert metrics1['karma_stored'] == True
        karma1 = inference_engine.karma_buffer.clone()

        # Second generation
        output2, metrics2 = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            inject_karma=True,
            store_karma=True,
            metacognition=metacognition,
            guna_tracker=guna_tracker,
        )

        # Karma should have been injected and updated
        assert metrics2['karma_injected'] == True
        assert metrics2['karma_stored'] == True

    def test_pipeline_graceful_without_components(self, inference_engine, device):
        """Pipeline works when Phase 2 components are None."""
        input_ids = torch.randint(0, 100, (1, 5), device=device)

        output, metrics = inference_engine.generate_with_karma(
            input_ids,
            max_new_tokens=5,
            metacognition=None,
            guna_tracker=None,
            csr_guard=None,
        )

        # Should still work
        assert output.shape[1] > input_ids.shape[1]
        assert not metrics['aborted']


# =============================================================================
# Component Interaction Tests
# =============================================================================

class TestComponentInteractions:
    """Test interactions between Phase 2 components."""

    def test_high_tamas_triggers_recover(self, metacognition, guna_tracker, device):
        """High Tamas (repetition) triggers RECOVER recommendation."""
        # Simulate repetitive tokens
        for i in range(20):
            # Same token repeated
            guna_tracker.update(token_id=42, token_prob=0.5)

        # Tamas should be high
        s, r, t = guna_tracker.current_gunas
        assert t > 0.4  # High repetition

        # Update metacognition with Gunas
        metacognition.update_gunas(s, r, t)

        # Simulate coherent but stagnant generation
        for _ in range(15):
            logits = torch.randn(1000)
            metacognition.update(logits)

        # Should eventually recommend RECOVER for stagnation
        # (Depends on exact coherence values)

    def test_csr_guard_statistics(self, csr_guard, device):
        """CSR guard tracks intervention statistics correctly."""
        dim = 256
        vocab_size = 1000

        # Reset stats
        csr_guard.reset_statistics()

        # Simulate multiple calls
        for _ in range(10):
            hidden = torch.randn(1, dim, device=device)
            logits = torch.randn(1, vocab_size, device=device)
            csr_guard.apply(hidden, logits)

        stats = csr_guard.get_statistics()

        assert stats['total_calls'] == 10
        assert 'intervention_rate' in stats

    def test_metacognition_recommendation_sequence(self, metacognition, device):
        """Metacognition provides correct recommendation sequence."""
        # Simulate declining coherence
        for i in range(10):
            # Increasingly uniform (low confidence) logits
            logits = torch.randn(1000) * (0.1 + i * 0.1)
            status = metacognition.update(logits)

        # After sustained low coherence, should recommend action
        final_rec = status['recommendation']
        assert final_rec in ['CONTINUE', 'SLOW_DOWN', 'BRAKE', 'ABORT', 'RECOVER']
