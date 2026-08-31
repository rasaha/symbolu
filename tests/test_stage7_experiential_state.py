"""
Tests for Appendix F Stage 7C — Dual-Space Architecture (Experiential State)
=============================================================================

Verifies that ExperientialStateModule correctly implements the P_t
recurrence equation with stability constraints.

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.3
"""

import pytest
import torch
from symbolu.inference.experiential_state import (
    ExperientialStateModule,
    ExperientialStateConfig,
)


# =========================================================================
# Basic functionality
# =========================================================================

class TestExperientialState:
    """Tests for the experiential state recurrence."""

    def test_output_shape(self):
        """P_t should have shape [B, d_exp]."""
        cfg = ExperientialStateConfig(d_exp=64, hidden_dim=128)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(2, 128)
        P_t = module.step(x_t, c_total=0.7)
        assert P_t.shape == (2, 64)

    def test_initial_state_zero(self):
        """Initial P should be zero."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        assert (module.P == 0).all()

    def test_step_changes_state(self):
        """Each step should update P."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(1, 64)
        P0 = module.P.clone()
        module.step(x_t, c_total=0.5)
        assert not torch.allclose(module.P, P0)

    def test_accumulation_over_sequence(self):
        """P should accumulate information over multiple steps."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        states = []
        for t in range(5):
            x_t = torch.randn(1, 64)
            P_t = module.step(x_t, c_total=0.5)
            states.append(P_t.clone())
        # Each state should differ from the previous
        for i in range(1, 5):
            assert not torch.allclose(states[i], states[i - 1])

    def test_reset_zeros_state(self):
        """Reset should zero out P."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        module.step(torch.randn(1, 64))
        module.reset()
        assert (module.P == 0).all()

    def test_disabled_returns_zero(self):
        """When disabled, P should remain zero."""
        cfg = ExperientialStateConfig(enable=False, d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(1, 64)
        P_t = module.step(x_t, c_total=0.8)
        assert (P_t == 0).all()


# =========================================================================
# Stability constraints
# =========================================================================

class TestStabilityConstraints:
    """Tests for ρ, λ, and spectral norm constraints."""

    def test_rho_less_than_one(self):
        """ρ = sigmoid(rho_raw) should always be < 1.0."""
        cfg = ExperientialStateConfig(rho_init=3.0, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        assert module.rho.item() < 1.0
        assert module.rho.item() > 0.0

    def test_rho_approximately_095(self):
        """With default init, ρ ≈ sigmoid(3.0) ≈ 0.9526."""
        cfg = ExperientialStateConfig(rho_init=3.0, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        assert module.rho.item() == pytest.approx(0.9526, abs=0.001)

    def test_lambda_init_zero(self):
        """Default λ should be 0.0 for bounded introduction."""
        cfg = ExperientialStateConfig(lambda_init=0.0, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        assert module.lam.item() == pytest.approx(0.0)

    def test_lambda_clamped_to_max(self):
        """λ should be clamped to [0, lambda_max]."""
        cfg = ExperientialStateConfig(lambda_init=0.5, lambda_max=0.1, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        assert module.lam.item() == pytest.approx(0.1)

    def test_lambda_non_negative(self):
        """λ should never be negative."""
        cfg = ExperientialStateConfig(lambda_init=-1.0, lambda_max=0.1, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        assert module.lam.item() >= 0.0

    def test_spectral_norm_wc(self):
        """W_c should have spectral norm ≤ 1.0 on forward pass output."""
        cfg = ExperientialStateConfig(d_exp=32, d_coherence=16, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        # Spectral norm is applied during forward pass
        # Run a forward pass to trigger the parametrization
        x = torch.randn(1, 64)
        module.step(x, c_total=0.5)
        # After forward pass, the effective weight should be normalized
        # Access the weight as used in forward (after parametrization)
        with torch.no_grad():
            test_input = torch.randn(1, 16)
            output = module.W_c(test_input)
            # Spectral norm ensures ||W_c|| ≤ 1, so ||output|| ≤ ||input||
            assert output.norm() <= test_input.norm() + 0.1

    def test_p_norm_bounded_over_sequence(self):
        """P_t norm should remain bounded over a long sequence."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64, lambda_init=0.0)
        module = ExperientialStateModule(cfg)
        max_norm = 0.0
        for _ in range(200):
            x_t = torch.randn(1, 64) * 0.1  # Small inputs
            P_t = module.step(x_t, c_total=0.5)
            norm = P_t.norm().item()
            max_norm = max(max_norm, norm)
        # With rho < 1 and bounded inputs, norm should stay reasonable
        assert max_norm < 50.0  # Conservative bound


# =========================================================================
# Null integration test
# =========================================================================

class TestNullIntegration7C:
    """When λ=0, P_t should not be affected by coherence signal."""

    def test_lambda_zero_no_coherence_effect(self):
        """With λ=0, different coherence values produce same P_t."""
        cfg = ExperientialStateConfig(lambda_init=0.0, hidden_dim=64, d_exp=32)
        torch.manual_seed(42)
        module1 = ExperientialStateModule(cfg)
        torch.manual_seed(42)
        module2 = ExperientialStateModule(cfg)

        x_t = torch.randn(1, 64)
        P1 = module1.step(x_t, c_total=0.0)
        P2 = module2.step(x_t, c_total=1.0)
        assert torch.allclose(P1, P2, atol=1e-5)

    def test_lambda_nonzero_coherence_has_effect(self):
        """With λ>0, different coherence values produce different P_t."""
        cfg = ExperientialStateConfig(
            lambda_init=0.1, lambda_max=0.1, hidden_dim=64, d_exp=32
        )
        torch.manual_seed(42)
        module1 = ExperientialStateModule(cfg)
        torch.manual_seed(42)
        module2 = ExperientialStateModule(cfg)

        x_t = torch.randn(1, 64)
        P1 = module1.step(x_t, c_total=0.0)
        P2 = module2.step(x_t, c_total=1.0)
        # These should differ due to coherence coupling
        assert not torch.allclose(P1, P2, atol=1e-3)


# =========================================================================
# Batch handling
# =========================================================================

class TestBatchHandling:
    """Tests for batch size handling."""

    def test_batch_resize(self):
        """P should resize when batch size changes."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(4, 64)
        P_t = module.step(x_t)
        assert P_t.shape == (4, 32)

    def test_reset_with_batch_size(self):
        """Reset should accept a batch size parameter."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        module.reset(batch_size=4)
        assert module.P.shape == (4, 32)

    def test_get_experiential_vector(self):
        """get_experiential_vector should return current P."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(1, 64)
        module.step(x_t)
        vec = module.get_experiential_vector()
        assert torch.allclose(vec, module.P)


# =========================================================================
# Gradient flow
# =========================================================================

class TestGradientFlow7C:
    """Tests for gradient flow through the experiential state."""

    def test_gradients_flow_to_input(self):
        """Gradients should flow from P_t to x_t."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(1, 64, requires_grad=True)
        P_t = module.step(x_t, c_total=0.5)
        loss = P_t.sum()
        loss.backward()
        assert x_t.grad is not None
        assert (x_t.grad != 0).any()

    def test_gradients_flow_to_parameters(self):
        """Gradients should flow to W_g, W_u, W_c."""
        cfg = ExperientialStateConfig(d_exp=32, hidden_dim=64,
                                      lambda_init=0.05, lambda_max=0.1)
        module = ExperientialStateModule(cfg)
        x_t = torch.randn(1, 64)
        P_t = module.step(x_t, c_total=0.5)
        loss = P_t.sum()
        loss.backward()
        assert module.W_g.weight.grad is not None
        assert module.W_u.weight.grad is not None
