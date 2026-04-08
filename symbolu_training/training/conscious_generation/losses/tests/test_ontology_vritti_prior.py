"""
Tests for OntologyVrittiPrior — Ontology → Vritti directional regularizer.

Validates:
1. Prior construction from R[v,a] transpose and ontological state
2. No-signal / zero-alpha preserves old behavior (zero loss)
3. Prior distribution is valid (normalized, bounded)
4. Prior nudges Vritti targets in the expected direction
5. Ablatability (alpha=0 or lambda=0 restores prior behavior)
6. No inference path changed (training-only module)
7. Alpha cap enforcement
"""

import pytest
import numpy as np

torch = pytest.importorskip("torch", reason="torch required")

from symbolu_training.training.conscious_generation.losses.ontology_vritti_prior import (
    OntologyVrittiPrior,
    _R_MATRIX,
)


class TestOntologyVrittiPriorConstruction:
    """Test that the prior is correctly derived from the coupling matrix."""

    def test_r_matrix_shape(self):
        """R matrix is 5×12 (vritti × ontological layers)."""
        assert _R_MATRIX.shape == (5, 12)

    def test_r_transpose_registered_as_buffer(self):
        """R^T is registered as a non-trainable buffer."""
        module = OntologyVrittiPrior(alpha=0.1)
        assert hasattr(module, "R_T")
        assert module.R_T.shape == (12, 5)
        assert not module.R_T.requires_grad

    def test_prior_from_reasoning_dominant_bhava(self):
        """When O7_REASONING (index 6) dominates, pramana should be favored."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.zeros(1, 32)
        # Set O7_REASONING (Bhava index 6) to dominant
        state[0, 6] = 5.0  # Will softmax to ~1.0 at index 6
        prior = module.compute_prior(state)
        # Pramana (index 0) should have highest probability
        # because R[pramana, O7_REASONING] = 0.95 is the highest coupling
        assert prior[0, 0].item() > prior[0, 1].item(), "Pramana should > Viparyaya for O7"
        assert prior[0, 0].item() > prior[0, 4].item(), "Pramana should > Nidra for O7"

    def test_prior_from_potential_dominant_bhava(self):
        """When O1_POTENTIAL (index 0) dominates, nidra should be favored."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.zeros(1, 32)
        state[0, 0] = 5.0  # O1_POTENTIAL dominant
        prior = module.compute_prior(state)
        # Nidra (index 4) should have highest probability
        # because R[nidra, O1_POTENTIAL] = 0.85 is the highest coupling for O1
        assert prior[0, 4].item() > prior[0, 1].item(), "Nidra should > Viparyaya for O1"

    def test_prior_from_agency_dominant_bhava(self):
        """When O6_AGENCY (index 5) dominates, viparyaya should be favored."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.zeros(1, 32)
        state[0, 5] = 5.0  # O6_AGENCY dominant
        prior = module.compute_prior(state)
        # Viparyaya (index 1) should have highest probability
        # because R[viparyaya, O6_AGENCY] = 0.90 is the highest coupling for O6
        assert prior[0, 1].item() > prior[0, 0].item(), "Viparyaya should > Pramana for O6"
        assert prior[0, 1].item() > prior[0, 4].item(), "Viparyaya should > Nidra for O6"

    def test_prior_is_valid_distribution(self):
        """Prior sums to 1 and all values are non-negative."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.randn(4, 32)  # random batch
        prior = module.compute_prior(state)
        assert prior.shape == (4, 5)
        assert (prior >= 0).all()
        sums = prior.sum(dim=-1)
        assert torch.allclose(sums, torch.ones(4), atol=1e-5)

    def test_uniform_bhava_gives_near_uniform_prior(self):
        """When Bhava is uniform (untrained state), prior is near-uniform."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.zeros(1, 32)
        # All Bhava values equal → softmax gives uniform 1/12 each
        prior = module.compute_prior(state)
        # Should be close to uniform because R^T @ uniform ≈ column means
        max_val = prior.max().item()
        min_val = prior.min().item()
        assert max_val - min_val < 0.15, (
            f"Expected near-uniform prior for uniform Bhava, got range "
            f"[{min_val:.3f}, {max_val:.3f}]"
        )


class TestOntologyVrittiPriorLoss:
    """Test the KL loss computation."""

    def test_zero_alpha_returns_zero(self):
        """alpha=0 produces zero loss (ablatable)."""
        module = OntologyVrittiPrior(alpha=0.0)
        v_ctx = torch.softmax(torch.randn(4, 5), dim=-1)
        state = torch.randn(4, 32)
        loss = module(v_ctx, state)
        assert loss.item() == 0.0

    def test_matching_distributions_low_loss(self):
        """When v_ctx matches the prior, KL should be near zero."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.zeros(1, 32)
        state[0, 6] = 5.0  # O7_REASONING dominant
        prior = module.compute_prior(state)
        # Use the prior itself as v_ctx → KL should be ~0
        loss = module(prior, state)
        assert loss.item() < 1e-4, f"Expected near-zero KL for matching distributions, got {loss.item()}"

    def test_mismatched_distributions_positive_loss(self):
        """When v_ctx diverges from prior, KL should be positive."""
        module = OntologyVrittiPrior(alpha=0.1)
        state = torch.zeros(1, 32)
        state[0, 6] = 5.0  # O7_REASONING → pramana prior
        # v_ctx: nidra dominant (opposite of expected)
        v_ctx = torch.tensor([[0.02, 0.02, 0.02, 0.02, 0.92]])
        loss = module(v_ctx, state)
        assert loss.item() > 0.01, f"Expected positive KL for mismatched distributions, got {loss.item()}"

    def test_loss_scales_with_alpha(self):
        """Higher alpha produces larger loss."""
        state = torch.zeros(1, 32)
        state[0, 6] = 5.0
        v_ctx = torch.tensor([[0.02, 0.02, 0.02, 0.02, 0.92]])
        loss_low = OntologyVrittiPrior(alpha=0.05)(v_ctx, state)
        loss_high = OntologyVrittiPrior(alpha=0.2)(v_ctx, state)
        assert loss_high.item() > loss_low.item()

    def test_loss_is_finite(self):
        """Loss should be finite for all reasonable inputs."""
        module = OntologyVrittiPrior(alpha=0.1)
        for _ in range(10):
            v_ctx = torch.softmax(torch.randn(8, 5), dim=-1)
            state = torch.randn(8, 32)
            loss = module(v_ctx, state)
            assert torch.isfinite(loss), f"Non-finite loss: {loss.item()}"

    def test_gradient_flows_to_v_ctx(self):
        """Gradients from the KL loss should flow back to v_ctx."""
        module = OntologyVrittiPrior(alpha=0.1)
        v_ctx = torch.softmax(torch.randn(2, 5), dim=-1)
        v_ctx.requires_grad_(True)
        state = torch.randn(2, 32)
        loss = module(v_ctx, state)
        loss.backward()
        assert v_ctx.grad is not None
        assert (v_ctx.grad != 0).any()

    def test_no_gradient_to_r_matrix(self):
        """R^T buffer should not receive gradients."""
        module = OntologyVrittiPrior(alpha=0.1)
        v_ctx = torch.softmax(torch.randn(2, 5), dim=-1)
        v_ctx.requires_grad_(True)
        state = torch.randn(2, 32)
        loss = module(v_ctx, state)
        loss.backward()
        assert module.R_T.grad is None or (module.R_T.grad == 0).all()


class TestOntologyVrittiPriorSafety:
    """Test safety constraints and ablatability."""

    def test_alpha_cap_enforcement(self):
        """Alpha values above 0.4 are clamped."""
        module = OntologyVrittiPrior(alpha=0.9)
        assert module.alpha == 0.4

    def test_alpha_within_cap_preserved(self):
        """Alpha values within cap are preserved."""
        module = OntologyVrittiPrior(alpha=0.15)
        assert module.alpha == 0.15

    def test_batch_dimensions(self):
        """Prior and loss work with various batch shapes."""
        module = OntologyVrittiPrior(alpha=0.1)
        for shape in [(1, 32), (4, 32), (2, 8, 32)]:
            state = torch.randn(*shape)
            prior = module.compute_prior(state)
            assert prior.shape == (*shape[:-1], 5)
            v_ctx = torch.softmax(torch.randn(*shape[:-1], 5), dim=-1)
            loss = module(v_ctx, state)
            assert torch.isfinite(loss)

    def test_tau_sharpens_prior(self):
        """Lower tau produces a sharper (less uniform) prior distribution."""
        state = torch.zeros(1, 32)
        state[0, 6] = 3.0  # Moderate O7_REASONING dominance
        prior_warm = OntologyVrittiPrior(alpha=0.1, tau=2.0).compute_prior(state)
        prior_cold = OntologyVrittiPrior(alpha=0.1, tau=0.5).compute_prior(state)
        # Entropy of cold prior should be lower (sharper)
        entropy_warm = -(prior_warm * torch.log(prior_warm + 1e-8)).sum().item()
        entropy_cold = -(prior_cold * torch.log(prior_cold + 1e-8)).sum().item()
        assert entropy_cold < entropy_warm, "Lower tau should produce sharper prior"

    def test_r_matrix_matches_coupling_py(self):
        """Verify the embedded R matrix matches the canonical source."""
        # Primary couplings from coupling.py
        assert abs(_R_MATRIX[0, 6] - 0.95) < 1e-10, "R[pramana, O7_REASONING] should be 0.95"
        assert abs(_R_MATRIX[1, 5] - 0.90) < 1e-10, "R[viparyaya, O6_AGENCY] should be 0.90"
        assert abs(_R_MATRIX[2, 4] - 0.85) < 1e-10, "R[vikalpa, O5_COGNITION] should be 0.85"
        assert abs(_R_MATRIX[4, 0] - 0.85) < 1e-10, "R[nidra, O1_POTENTIAL] should be 0.85"
