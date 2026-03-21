"""
Tests for Appendix F Stage 7E — State Projector Component Normalization
========================================================================

Integration tests validating that the 12D ontological state projector
maintains proper normalization, orthogonality, and that individual
components don't dominate.

These tests use mock projector weights to verify the test logic itself,
and can be run with a real SovereignStateProjector when available.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.5
"""

import pytest
import torch
import torch.nn as nn


# =========================================================================
# Mock state projector for testing
# =========================================================================

class MockStateProjector(nn.Module):
    """A mock projector that maps hidden → 12D ontological state."""

    def __init__(self, hidden_dim: int = 768, onto_dim: int = 12):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(onto_dim, hidden_dim))
        nn.init.orthogonal_(self.weight)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return hidden @ self.weight.T


class DegenerateStateProjector(nn.Module):
    """A projector with known issues for negative testing."""

    def __init__(self, hidden_dim: int = 768, onto_dim: int = 12):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(onto_dim, hidden_dim))
        # Make first dimension dominate
        with torch.no_grad():
            self.weight[0] *= 100.0
            # Kill last dimension
            self.weight[-1] *= 0.0001

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return hidden @ self.weight.T


# =========================================================================
# Test 1: Component variance
# =========================================================================

class TestComponentVariance:
    """Each of the 12 dimensions should contribute meaningfully."""

    def test_healthy_projector_all_dims_active(self):
        """All 12 dimensions should have variance > 0.01."""
        projector = MockStateProjector()
        # Generate a diverse corpus
        torch.manual_seed(42)
        test_corpus = torch.randn(100, 768)
        onto_states = projector(test_corpus)  # [100, 12]

        per_dim_var = onto_states.var(dim=0)  # [12]
        assert (per_dim_var > 0.01).all(), (
            f"Dead ontological dimension detected: {per_dim_var.tolist()}"
        )

    def test_healthy_projector_no_dominance(self):
        """Max/min variance ratio should be < 100."""
        projector = MockStateProjector()
        torch.manual_seed(42)
        test_corpus = torch.randn(100, 768)
        onto_states = projector(test_corpus)

        per_dim_var = onto_states.var(dim=0)
        ratio = per_dim_var.max() / per_dim_var.min()
        assert ratio < 100, f"Dimension dominance detected: ratio={ratio:.1f}"

    def test_degenerate_projector_detects_dominance(self):
        """Degenerate projector should fail the dominance test."""
        projector = DegenerateStateProjector()
        torch.manual_seed(42)
        test_corpus = torch.randn(100, 768)
        onto_states = projector(test_corpus)

        per_dim_var = onto_states.var(dim=0)
        ratio = per_dim_var.max() / (per_dim_var.min() + 1e-10)
        # Degenerate should have extreme ratio
        assert ratio > 100, "Expected dominance not detected in degenerate projector"


# =========================================================================
# Test 2: Component orthogonality
# =========================================================================

class TestComponentOrthogonality:
    """Projector components should be sufficiently independent."""

    def test_healthy_projector_off_diagonal_low(self):
        """Off-diagonal cosine similarity should be < 0.5."""
        projector = MockStateProjector()
        W = projector.weight  # [12, 768]
        # Compute cosine similarity matrix
        norms = W.norm(dim=1, keepdim=True)  # [12, 1]
        cosine_sim = (W @ W.T) / (norms @ norms.T + 1e-8)
        off_diagonal = cosine_sim - torch.eye(12)
        assert off_diagonal.abs().max() < 0.5, (
            f"Projector components not sufficiently independent: "
            f"max off-diagonal={off_diagonal.abs().max():.3f}"
        )

    def test_diagonal_is_one(self):
        """Diagonal of cosine similarity should be ~1.0."""
        projector = MockStateProjector()
        W = projector.weight
        norms = W.norm(dim=1, keepdim=True)
        cosine_sim = (W @ W.T) / (norms @ norms.T + 1e-8)
        diagonal = cosine_sim.diag()
        assert torch.allclose(diagonal, torch.ones(12), atol=0.01)


# =========================================================================
# Test 3: Gradient flow
# =========================================================================

class TestGradientFlow7E:
    """All dimensions should receive gradient flow."""

    def test_all_dims_receive_gradient(self):
        """Gradient should flow to all 12 projector dimensions."""
        projector = MockStateProjector()
        test_input = torch.randn(4, 768, requires_grad=True)
        output = projector(test_input)
        loss = output.sum()
        loss.backward()

        grad_norms = projector.weight.grad.norm(dim=1)  # [12]
        assert (grad_norms > 0).all(), (
            f"Dead gradient in state projector: {(grad_norms == 0).nonzero().tolist()}"
        )

    def test_gradient_magnitudes_reasonable(self):
        """No dimension should have gradient orders of magnitude larger."""
        projector = MockStateProjector()
        test_input = torch.randn(4, 768)
        output = projector(test_input)
        loss = output.sum()
        loss.backward()

        grad_norms = projector.weight.grad.norm(dim=1)
        ratio = grad_norms.max() / (grad_norms.min() + 1e-10)
        assert ratio < 100, f"Gradient magnitude ratio too high: {ratio:.1f}"


# =========================================================================
# Test 4: Projection stability
# =========================================================================

class TestProjectionStability:
    """State projector should be stable to small input perturbations."""

    def test_small_perturbation_small_drift(self):
        """Perturbing input by ε=0.01 should produce drift < 0.5."""
        projector = MockStateProjector()
        torch.manual_seed(42)
        hidden_states = torch.randn(10, 768)

        onto_1 = projector(hidden_states)
        onto_2 = projector(hidden_states + 0.01 * torch.randn_like(hidden_states))

        drift = (onto_1 - onto_2).norm(dim=1).mean()
        assert drift < 0.5, (
            f"State projector too sensitive to input perturbation: drift={drift:.4f}"
        )

    def test_zero_perturbation_zero_drift(self):
        """No perturbation should produce zero drift."""
        projector = MockStateProjector()
        torch.manual_seed(42)
        hidden_states = torch.randn(10, 768)

        onto_1 = projector(hidden_states)
        onto_2 = projector(hidden_states)

        drift = (onto_1 - onto_2).norm(dim=1).mean()
        assert drift < 1e-6

    def test_large_perturbation_bounded_drift(self):
        """Even large perturbation should produce bounded drift."""
        projector = MockStateProjector()
        torch.manual_seed(42)
        hidden_states = torch.randn(10, 768)

        onto_1 = projector(hidden_states)
        onto_2 = projector(hidden_states + 1.0 * torch.randn_like(hidden_states))

        drift = (onto_1 - onto_2).norm(dim=1).mean()
        # Should still be finite and bounded
        assert drift < 50.0


# =========================================================================
# Integration with SovereignStateProjector (optional)
# =========================================================================

class TestSovereignProjectorIntegration:
    """Tests using the actual SovereignStateProjector if available."""

    def test_import_succeeds(self):
        """SovereignStateProjector should be importable."""
        try:
            from symbolu.jepa.state_projector import SovereignStateProjector
        except ImportError:
            pytest.skip("SovereignStateProjector not available")

    def test_32d_state_has_12d_bhava_component(self):
        """The 32D state should have Bhavas at [0:12]."""
        try:
            from symbolu.jepa.state_projector import SovereignStateProjector
        except ImportError:
            pytest.skip("SovereignStateProjector not available")

        projector = SovereignStateProjector(hidden_dim=768)
        hidden = torch.randn(4, 768)
        state = projector(hidden)
        assert state.shape[-1] == 32
        # Bhavas at [0:12] should be normalized (softmax)
        bhava = state[..., :12]
        # Softmax output should sum to ~1
        assert torch.allclose(bhava.sum(dim=-1), torch.ones(4), atol=0.1)
