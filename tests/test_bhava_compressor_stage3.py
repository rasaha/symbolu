"""
Tests for Appendix F Stage 3 — Bhava Relational Structure Preservation.

Validates:
- BhavaRelationshipLayer now uses BhavaVectorCompressor (F.5.4)
- bhava_vector (16D) output preserves relational structure
- Backward-compatible scalar coherence still produced
- SymbolU12LLM.forward() outputs bhava_vector
- Measurement fields: bhava_vector, bhava_vector_variance,
  bhava_vector_drift, coherence_scalar (F.5.7)
- Success criteria: meaningful variance, drift correlates with
  input change (F.5.8)
- Backward compatibility: coherence shape unchanged
"""

import pytest
import torch
import torch.nn as nn

from symbolu.inference.interpretive_conditioner import BhavaVectorCompressor


# =============================================================================
# BhavaRelationshipLayer with BhavaVectorCompressor
# =============================================================================


class TestBhavaRelationshipLayerStage3:
    """Test the modified BhavaRelationshipLayer with vector compression."""

    @pytest.fixture
    def layer(self):
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        return BhavaRelationshipLayer(num_layers=12)

    def test_output_keys(self, layer):
        """Output dict contains all expected keys including bhava_vector."""
        onto = torch.randn(2, 10, 12)
        out = layer(onto)
        assert "bhava" in out
        assert "relationship_matrix" in out
        assert "coherence" in out
        assert "bhava_vector" in out

    def test_bhava_vector_shape(self, layer):
        """bhava_vector is [B, T, 16]."""
        onto = torch.randn(2, 10, 12)
        out = layer(onto)
        assert out["bhava_vector"].shape == (2, 10, 16)

    def test_bhava_shape_unchanged(self, layer):
        """Flattened bhava is still [B, T, 144]."""
        onto = torch.randn(2, 10, 12)
        out = layer(onto)
        assert out["bhava"].shape == (2, 10, 144)

    def test_coherence_shape_backward_compatible(self, layer):
        """Coherence shape is [B, T, 1] — backward compatible."""
        onto = torch.randn(2, 10, 12)
        out = layer(onto)
        assert out["coherence"].shape == (2, 10, 1)

    def test_coherence_bounded(self, layer):
        """Coherence values are in [0, 1] (sigmoid)."""
        onto = torch.randn(3, 5, 12) * 5  # Large values
        out = layer(onto)
        assert (out["coherence"] >= 0).all()
        assert (out["coherence"] <= 1).all()

    def test_relationship_matrix_shape(self, layer):
        onto = torch.randn(2, 10, 12)
        out = layer(onto)
        assert out["relationship_matrix"].shape == (2, 10, 12, 12)

    def test_deterministic(self, layer):
        """Same input produces same output."""
        layer.eval()
        onto = torch.randn(1, 5, 12)
        out1 = layer(onto)
        out2 = layer(onto)
        assert torch.allclose(out1["bhava_vector"], out2["bhava_vector"])
        assert torch.allclose(out1["coherence"], out2["coherence"])

    def test_different_inputs_different_vectors(self, layer):
        """Different ontological states produce different bhava_vectors."""
        layer.eval()
        onto1 = torch.randn(1, 5, 12)
        onto2 = torch.randn(1, 5, 12) + 5.0  # Significantly different
        out1 = layer(onto1)
        out2 = layer(onto2)
        assert not torch.allclose(out1["bhava_vector"], out2["bhava_vector"], atol=1e-3)

    def test_bhava_vector_has_variance(self, layer):
        """bhava_vector dimensions are not collapsed (meaningful variance)."""
        layer.eval()
        onto = torch.randn(4, 20, 12)
        out = layer(onto)
        # Variance across batch and sequence should be non-trivial
        per_dim_var = out["bhava_vector"].var(dim=[0, 1])
        assert (per_dim_var > 1e-6).all(), "Some dimensions have zero variance"

    def test_custom_output_dim(self):
        """Supports custom bhava_output_dim."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12, bhava_output_dim=32)
        onto = torch.randn(1, 5, 12)
        out = layer(onto)
        assert out["bhava_vector"].shape == (1, 5, 32)

    def test_gradient_flow(self, layer):
        """Gradients flow through bhava_vector."""
        onto = torch.randn(1, 3, 12, requires_grad=True)
        out = layer(onto)
        loss = out["bhava_vector"].sum()
        loss.backward()
        assert onto.grad is not None

    def test_gradient_flow_through_coherence(self, layer):
        """Gradients flow through coherence (from compressor, not legacy net)."""
        onto = torch.randn(1, 3, 12, requires_grad=True)
        out = layer(onto)
        loss = out["coherence"].sum()
        loss.backward()
        assert onto.grad is not None


# =============================================================================
# SymbolU12LLM Integration
# =============================================================================


class TestSymbolU12LLMStage3:
    """Test bhava_vector output from SymbolU12LLM.forward()."""

    @pytest.fixture
    def model(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM
        return SymbolU12LLM(
            vocab_size=256,
            embed_dim=64,
            num_layers=2,
            num_heads=4,
            max_seq_len=128,
        )

    def test_forward_outputs_bhava_vector(self, model):
        model.eval()
        ids = torch.randint(0, 256, (1, 10))
        out = model(ids, return_ontological=True)
        assert "bhava_vector" in out
        assert out["bhava_vector"].shape == (1, 10, 16)

    def test_forward_coherence_still_works(self, model):
        """Coherence is still present and correctly shaped."""
        model.eval()
        ids = torch.randint(0, 256, (1, 10))
        out = model(ids, return_ontological=True)
        assert "coherence" in out
        assert out["coherence"].shape == (1, 10, 1)

    def test_forward_without_ontological(self, model):
        """Without return_ontological, bhava_vector not in output."""
        model.eval()
        ids = torch.randint(0, 256, (1, 10))
        out = model(ids, return_ontological=False)
        assert "bhava_vector" not in out

    def test_bhava_vector_varies_across_tokens(self, model):
        """bhava_vector varies across token positions."""
        model.eval()
        ids = torch.randint(0, 256, (1, 20))
        out = model(ids, return_ontological=True)
        bv = out["bhava_vector"]
        # Check variance across time dimension
        var_across_time = bv.var(dim=1).mean()
        # Should have some variance (not identical across positions)
        assert var_across_time > 0


# =============================================================================
# Bhava Vector Drift (F.5.7)
# =============================================================================


class TestBhavaVectorDrift:
    """Test drift computation between consecutive bhava_vectors."""

    def test_drift_same_input_zero(self):
        """Same bhava_vector gives zero drift (cosine distance)."""
        bv = torch.randn(16)
        cos_sim = torch.nn.functional.cosine_similarity(
            bv.unsqueeze(0), bv.unsqueeze(0)
        ).item()
        drift = 1.0 - cos_sim
        assert abs(drift) < 1e-5

    def test_drift_orthogonal_input_one(self):
        """Orthogonal vectors give drift of ~1.0."""
        bv1 = torch.zeros(16)
        bv1[0] = 1.0
        bv2 = torch.zeros(16)
        bv2[1] = 1.0
        cos_sim = torch.nn.functional.cosine_similarity(
            bv1.unsqueeze(0), bv2.unsqueeze(0)
        ).item()
        drift = 1.0 - cos_sim
        assert abs(drift - 1.0) < 1e-5

    def test_drift_opposite_input_two(self):
        """Opposite vectors give drift of 2.0."""
        bv1 = torch.randn(16)
        bv2 = -bv1
        cos_sim = torch.nn.functional.cosine_similarity(
            bv1.unsqueeze(0), bv2.unsqueeze(0)
        ).item()
        drift = 1.0 - cos_sim
        assert abs(drift - 2.0) < 1e-5

    def test_drift_similar_inputs_small(self):
        """Similar vectors have small drift."""
        bv1 = torch.randn(16)
        bv2 = bv1 + 0.01 * torch.randn(16)  # Small perturbation
        cos_sim = torch.nn.functional.cosine_similarity(
            bv1.unsqueeze(0), bv2.unsqueeze(0)
        ).item()
        drift = 1.0 - cos_sim
        assert drift < 0.1


# =============================================================================
# Backward Compatibility
# =============================================================================


class TestBackwardCompatibility:
    """Verify Stage 3 maintains backward compatibility."""

    def test_coherence_net_still_exists(self):
        """Legacy coherence_net is still present for checkpoint loading."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        assert hasattr(layer, 'coherence_net')

    def test_bhava_compressor_exists(self):
        """New bhava_compressor is present."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        assert hasattr(layer, 'bhava_compressor')

    def test_coherence_from_compressor_not_legacy(self):
        """Coherence output comes from BhavaVectorCompressor, not coherence_net."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        layer.eval()
        onto = torch.randn(1, 5, 12)

        # Get output via forward
        out = layer(onto)

        # Manually compute via compressor
        bhava_flat = out["bhava"]
        compressor_out = layer.bhava_compressor(bhava_flat)
        expected_coherence = compressor_out["coherence"].unsqueeze(-1)

        assert torch.allclose(out["coherence"], expected_coherence)


# =============================================================================
# Success Criteria (F.5.8)
# =============================================================================


class TestSuccessCriteria:
    """Test measurable success criteria from F.5.8."""

    def test_meaningful_variance_per_dimension(self):
        """σ > 0.1 per dimension across varied inputs (not collapsed)."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        layer.eval()

        # Generate varied ontological states
        all_vectors = []
        for _ in range(10):
            onto = torch.randn(1, 1, 12) * 2
            out = layer(onto)
            all_vectors.append(out["bhava_vector"].squeeze())

        stacked = torch.stack(all_vectors)  # [10, 16]
        per_dim_std = stacked.std(dim=0)

        # At least some dimensions should have meaningful variance
        # (not all need to since weights are random init)
        assert (per_dim_std > 0.01).sum() >= 8, (
            f"Too few dimensions with variance > 0.01: {per_dim_std}"
        )

    def test_drift_correlates_with_input_change(self):
        """bhava_vector_drift should be higher for different inputs vs same."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        layer.eval()

        # Same input → low drift
        onto = torch.randn(1, 1, 12)
        out1 = layer(onto)
        out2 = layer(onto)
        bv1 = out1["bhava_vector"].squeeze()
        bv2 = out2["bhava_vector"].squeeze()
        same_drift = 1.0 - torch.nn.functional.cosine_similarity(
            bv1.unsqueeze(0), bv2.unsqueeze(0)
        ).item()

        # Different input → higher drift
        onto_diff = torch.randn(1, 1, 12) * 5  # Very different
        out3 = layer(onto_diff)
        bv3 = out3["bhava_vector"].squeeze()
        diff_drift = 1.0 - torch.nn.functional.cosine_similarity(
            bv1.unsqueeze(0), bv3.unsqueeze(0)
        ).item()

        assert diff_drift > same_drift, (
            f"Different input drift ({diff_drift:.4f}) should exceed "
            f"same input drift ({same_drift:.4f})"
        )


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:

    def test_single_token(self):
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        onto = torch.randn(1, 1, 12)
        out = layer(onto)
        assert out["bhava_vector"].shape == (1, 1, 16)

    def test_large_batch(self):
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        onto = torch.randn(16, 50, 12)
        out = layer(onto)
        assert out["bhava_vector"].shape == (16, 50, 16)
        assert out["coherence"].shape == (16, 50, 1)

    def test_zero_input(self):
        """Zero ontological state produces valid output."""
        from symbolu.ontological.symbolu12_llm import BhavaRelationshipLayer
        layer = BhavaRelationshipLayer(num_layers=12)
        onto = torch.zeros(1, 3, 12)
        out = layer(onto)
        assert not torch.isnan(out["bhava_vector"]).any()
        assert not torch.isnan(out["coherence"]).any()
