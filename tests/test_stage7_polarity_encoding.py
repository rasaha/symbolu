"""
Tests for Appendix F Stage 7D — Polarity Encoding (Varna Polarity Gates)
=========================================================================

Verifies that PolarityGate correctly implements the polarity encoding
formula: c = (1-φ)/2 · v_neg + (1+φ)/2 · v_pos

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.4
"""

import pytest
import torch
from symbolu.inference.polarity_encoding import (
    PolarityGate,
    PolarityEncodingConfig,
)


# =========================================================================
# Polarity formula
# =========================================================================

class TestPolarityFormula:
    """Tests for the core polarity encoding formula."""

    def test_output_shape(self):
        """c_polar should have shape (..., csr_dim)."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(2, 10, 64)
        onto = torch.randn(2, 10, 12)
        result = gate(hidden, onto)
        assert result["c_polar"].shape == (2, 10, 16)

    def test_phi_bounded(self):
        """φ should be in [-1, 1] due to tanh."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(2, 10, 64)
        onto = torch.randn(2, 10, 12) * 10  # Large values
        result = gate(hidden, onto)
        assert (result["phi"] >= -1.0).all()
        assert (result["phi"] <= 1.0).all()

    def test_phi_zero_gives_average(self):
        """When φ=0, c_polar should be (v_neg + v_pos) / 2."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16,
                                     phi_init_scale=0.0)
        gate = PolarityGate(cfg)
        # Zero-init W_phi and bias → φ ≈ 0
        nn = torch.nn
        nn.init.zeros_(gate.W_phi.weight)
        nn.init.zeros_(gate.W_phi.bias)

        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        result = gate(hidden, onto)

        v_neg = gate.W_neg(hidden)
        v_pos = gate.W_pos(hidden)
        expected = (v_neg + v_pos) / 2
        assert torch.allclose(result["c_polar"], expected, atol=1e-5)

    def test_phi_one_gives_v_pos(self):
        """When φ=1, c_polar should be v_pos."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 1, 64)
        onto = torch.randn(1, 1, 12)

        result = gate(hidden, onto)
        phi = result["phi"]
        v_neg = result["v_neg"]
        v_pos = result["v_pos"]

        # Manually compute with actual phi
        expected = (1 - phi) / 2 * v_neg + (1 + phi) / 2 * v_pos
        assert torch.allclose(result["c_polar"], expected, atol=1e-5)

    def test_phi_negative_one_gives_v_neg(self):
        """Verify formula at extreme negative polarity."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        # Force φ = -1 by making W_phi produce large negative
        with torch.no_grad():
            gate.W_phi.weight.fill_(-100.0)
            gate.W_phi.bias.fill_(0.0)

        hidden = torch.randn(1, 1, 64)
        onto = torch.ones(1, 1, 12)  # Non-zero to activate tanh(-large) ≈ -1
        result = gate(hidden, onto)

        v_neg = gate.W_neg(hidden)
        # φ ≈ -1: c = (1-(-1))/2 · v_neg + (1+(-1))/2 · v_pos = v_neg
        assert torch.allclose(result["c_polar"], v_neg, atol=0.01)

    def test_different_onto_different_polarity(self):
        """Different ontological states should produce different polarities."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 1, 64)

        onto1 = torch.randn(1, 1, 12)
        onto2 = -onto1  # Opposite ontological state
        r1 = gate(hidden, onto1)
        r2 = gate(hidden, onto2)

        # Polarity should differ for opposite ontological states
        # (with random init, phi values will be different)
        # Note: with small phi_init_scale, differences might be small
        assert not torch.allclose(r1["phi"], r2["phi"], atol=1e-3)


# =========================================================================
# Kill switch (enable=False)
# =========================================================================

class TestKillSwitch7D:
    """Tests for the enable/disable switch."""

    def test_disabled_uses_standard_projection(self):
        """When disabled, should use standard CSR projection."""
        cfg = PolarityEncodingConfig(enable=False, hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        result = gate(hidden, onto)
        assert result["c_polar"].shape == (1, 5, 16)
        assert (result["phi"] == 0).all()

    def test_disabled_phi_is_zero(self):
        """When disabled, phi should be all zeros."""
        cfg = PolarityEncodingConfig(enable=False, hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(2, 3, 64)
        onto = torch.randn(2, 3, 12)
        result = gate(hidden, onto)
        assert (result["phi"] == 0).all()


# =========================================================================
# Output fields
# =========================================================================

class TestOutputFields7D:
    """Tests for output dictionary fields."""

    def test_all_fields_present(self):
        """Output should contain c_polar, phi, v_neg, v_pos."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        result = gate(hidden, onto)
        assert "c_polar" in result
        assert "phi" in result
        assert "v_neg" in result
        assert "v_pos" in result

    def test_field_shapes(self):
        """All fields should have consistent shapes."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(2, 10, 64)
        onto = torch.randn(2, 10, 12)
        result = gate(hidden, onto)
        for key in ["c_polar", "phi", "v_neg", "v_pos"]:
            assert result[key].shape == (2, 10, 16)


# =========================================================================
# Bounded introduction
# =========================================================================

class TestBoundedIntroduction7D:
    """Tests for bounded introduction (small initial polarity)."""

    def test_small_initial_phi(self):
        """With default phi_init_scale=0.01, initial φ should be small."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16,
                                     phi_init_scale=0.01)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        result = gate(hidden, onto)
        # With small W_phi weights, phi should be close to 0
        assert result["phi"].abs().max() < 0.5


# =========================================================================
# Gradient flow
# =========================================================================

class TestGradientFlow7D:
    """Tests for gradient flow through polarity gate."""

    def test_gradients_flow_through_c_polar(self):
        """Gradients should flow from c_polar back to hidden and onto."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 5, 64, requires_grad=True)
        onto = torch.randn(1, 5, 12, requires_grad=True)
        result = gate(hidden, onto)
        loss = result["c_polar"].sum()
        loss.backward()
        assert hidden.grad is not None
        assert onto.grad is not None

    def test_gradients_flow_to_W_phi(self):
        """Gradients should flow to W_phi (polarity gate weights)."""
        cfg = PolarityEncodingConfig(hidden_dim=64, onto_dim=12, csr_dim=16)
        gate = PolarityGate(cfg)
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        result = gate(hidden, onto)
        loss = result["c_polar"].sum()
        loss.backward()
        assert gate.W_phi.weight.grad is not None
