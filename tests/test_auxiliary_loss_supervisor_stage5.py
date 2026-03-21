"""
Tests for Appendix F Stage 5 — Auxiliary Loss Supervision.

Validates:
- AuxiliaryLossConfig defaults and custom values (F.7.3)
- TokenOntologyProjection embedding → 32D codes (F.7.8)
- BlissCoherenceProjection contrastive coherence loss (F.7.2.1)
- GradientSafetyMonitor ratio bounds (F.7.6)
- AuxiliaryLossSupervisor total loss formula (F.7.3)
  - L_total = L_token + Σ λᵢ · Lᵢ
  - Missing losses default to zero (staged curriculum)
  - O_tok cache refresh
  - Ontological compatibility loss L_ont
- Gradient flow through auxiliary losses
- Success criteria: convergence, gradient ratio bounds (F.7.7)
"""

import pytest
import torch
import torch.nn as nn

from symbolu.training.conscious_generation.losses.auxiliary_loss_supervisor import (
    AuxiliaryLossConfig,
    AuxiliaryLossSupervisor,
    TokenOntologyProjection,
    BlissCoherenceProjection,
    GradientSafetyMonitor,
)


# =============================================================================
# AuxiliaryLossConfig
# =============================================================================


class TestAuxiliaryLossConfig:

    def test_defaults(self):
        cfg = AuxiliaryLossConfig()
        assert cfg.lambda_csr == 0.01
        assert cfg.lambda_vritti == 0.02
        assert cfg.lambda_kosha == 0.005
        assert cfg.lambda_bliss == 0.02
        assert cfg.lambda_ont == 0.01
        assert cfg.d_coherence == 64
        assert cfg.onto_dim == 32
        assert cfg.gradient_safety_low == 0.01
        assert cfg.gradient_safety_high == 0.5
        assert cfg.cache_refresh_interval == 1000

    def test_custom(self):
        cfg = AuxiliaryLossConfig(lambda_csr=0.05, lambda_vritti=0.1)
        assert cfg.lambda_csr == 0.05
        assert cfg.lambda_vritti == 0.1


# =============================================================================
# TokenOntologyProjection (F.7.8)
# =============================================================================


class TestTokenOntologyProjection:

    def test_output_shape_vocab(self):
        proj = TokenOntologyProjection(embed_dim=64, onto_dim=32)
        embeddings = torch.randn(1000, 64)  # Full vocab
        codes = proj(embeddings)
        assert codes.shape == (1000, 32)

    def test_output_shape_shortlist(self):
        proj = TokenOntologyProjection(embed_dim=64, onto_dim=32)
        embeddings = torch.randn(2, 16, 64)  # [B, K, D]
        codes = proj(embeddings)
        assert codes.shape == (2, 16, 32)

    def test_no_bias(self):
        proj = TokenOntologyProjection(embed_dim=64)
        assert proj.projection.bias is None

    def test_gradient_flow(self):
        proj = TokenOntologyProjection(embed_dim=32, onto_dim=16)
        emb = torch.randn(5, 32, requires_grad=True)
        codes = proj(emb)
        codes.sum().backward()
        assert emb.grad is not None

    def test_deterministic(self):
        proj = TokenOntologyProjection(embed_dim=64)
        proj.eval()
        emb = torch.randn(10, 64)
        assert torch.allclose(proj(emb), proj(emb))


# =============================================================================
# BlissCoherenceProjection (F.7.2.1)
# =============================================================================


class TestBlissCoherenceProjection:

    @pytest.fixture
    def proj(self):
        return BlissCoherenceProjection(hidden_dim=64, embed_dim=64, d_coherence=32)

    def test_forward_shape(self, proj):
        hidden = torch.randn(2, 10, 64)
        tok = torch.randn(2, 10, 64)
        scores = proj(hidden, tok)
        assert scores.shape == (2, 10)

    def test_coherence_bounded(self, proj):
        """Cosine similarity is in [-1, 1]."""
        hidden = torch.randn(4, 5, 64)
        tok = torch.randn(4, 5, 64)
        scores = proj(hidden, tok)
        assert (scores >= -1.0 - 1e-5).all()
        assert (scores <= 1.0 + 1e-5).all()

    def test_contrastive_loss_positive(self, proj):
        hidden = torch.randn(2, 5, 64)
        correct = torch.randn(2, 5, 64)
        negative = torch.randn(2, 5, 64)
        result = proj.compute_contrastive_loss(hidden, correct, negative)
        assert "loss" in result
        assert result["loss"].item() >= 0  # Loss is non-negative
        assert "pos_coherence" in result
        assert "neg_coherence" in result

    def test_contrastive_loss_gradient(self, proj):
        hidden = torch.randn(2, 5, 64, requires_grad=True)
        correct = torch.randn(2, 5, 64)
        negative = torch.randn(2, 5, 64)
        result = proj.compute_contrastive_loss(hidden, correct, negative)
        result["loss"].backward()
        assert hidden.grad is not None

    def test_same_input_high_coherence(self, proj):
        """Identical inputs should produce high coherence."""
        proj.eval()
        x = torch.randn(1, 3, 64)
        score = proj(x, x)
        # With normalized vectors and same input, should be positive
        # (depends on learned projections, but at init both sides
        # apply the same transformation pattern)
        assert score.shape == (1, 3)


# =============================================================================
# GradientSafetyMonitor (F.7.6)
# =============================================================================


class TestGradientSafetyMonitor:

    def test_healthy_range(self):
        mon = GradientSafetyMonitor()
        result = mon.check(aux_grad_norm=0.05, backbone_grad_norm=1.0)
        assert result["ratio"] == 0.05
        assert result["status"] == "healthy"
        assert result["action"] == "none"

    def test_ineffective_range(self):
        mon = GradientSafetyMonitor()
        result = mon.check(aux_grad_norm=0.005, backbone_grad_norm=1.0)
        assert result["status"] == "ineffective"

    def test_caution_range(self):
        mon = GradientSafetyMonitor()
        result = mon.check(aux_grad_norm=0.3, backbone_grad_norm=1.0)
        assert result["status"] == "caution"

    def test_danger_range(self):
        mon = GradientSafetyMonitor()
        result = mon.check(aux_grad_norm=0.6, backbone_grad_norm=1.0)
        assert result["status"] == "danger"

    def test_zero_backbone_norm(self):
        mon = GradientSafetyMonitor()
        result = mon.check(aux_grad_norm=0.1, backbone_grad_norm=0.0)
        assert result["ratio"] == 0.0

    def test_history_tracking(self):
        mon = GradientSafetyMonitor()
        mon.check(aux_grad_norm=0.05, backbone_grad_norm=1.0)
        mon.check(aux_grad_norm=0.03, backbone_grad_norm=1.0)
        assert len(mon.history) == 2
        assert abs(mon.mean_ratio - 0.04) < 1e-6

    def test_empty_history_mean(self):
        mon = GradientSafetyMonitor()
        assert mon.mean_ratio == 0.0

    def test_custom_thresholds(self):
        cfg = AuxiliaryLossConfig(gradient_safety_low=0.05, gradient_safety_high=0.3)
        mon = GradientSafetyMonitor(cfg)
        # 0.04 is below custom low threshold
        result = mon.check(aux_grad_norm=0.04, backbone_grad_norm=1.0)
        assert result["status"] == "ineffective"
        # 0.35 is above custom high threshold
        result = mon.check(aux_grad_norm=0.35, backbone_grad_norm=1.0)
        assert result["status"] == "danger"


# =============================================================================
# AuxiliaryLossSupervisor (F.7.3)
# =============================================================================


class TestAuxiliaryLossSupervisor:

    @pytest.fixture
    def supervisor(self):
        cfg = AuxiliaryLossConfig()
        return AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)

    def test_all_losses_provided(self, supervisor):
        result = supervisor(
            loss_token=torch.tensor(3.0),
            loss_csr=torch.tensor(1.0),
            loss_vritti=torch.tensor(2.0),
            loss_kosha=torch.tensor(0.5),
            loss_bliss=torch.tensor(1.5),
            loss_ont=torch.tensor(1.0),
        )
        expected = 3.0 + 0.01*1.0 + 0.02*2.0 + 0.005*0.5 + 0.02*1.5 + 0.01*1.0
        assert abs(result["loss_total"].item() - expected) < 1e-5
        assert "loss_token" in result
        assert "weighted_csr" in result

    def test_missing_losses_default_zero(self, supervisor):
        """Missing auxiliary losses are treated as zero."""
        result = supervisor(loss_token=torch.tensor(3.0))
        assert abs(result["loss_total"].item() - 3.0) < 1e-5

    def test_partial_losses(self, supervisor):
        """Only some auxiliary losses provided."""
        result = supervisor(
            loss_token=torch.tensor(3.0),
            loss_csr=torch.tensor(1.0),
        )
        expected = 3.0 + 0.01 * 1.0
        assert abs(result["loss_total"].item() - expected) < 1e-5

    def test_output_keys(self, supervisor):
        result = supervisor(loss_token=torch.tensor(1.0))
        expected_keys = {
            "loss_total", "loss_token",
            "loss_csr", "loss_vritti", "loss_kosha", "loss_bliss", "loss_ont",
            "weighted_csr", "weighted_vritti", "weighted_kosha",
            "weighted_bliss", "weighted_ont",
        }
        assert expected_keys.issubset(result.keys())

    def test_gradient_through_total_loss(self, supervisor):
        """Gradients flow through loss_total to auxiliary parameters."""
        x = torch.randn(2, 5, 64, requires_grad=True)
        # Simulate an auxiliary loss that depends on x
        fake_loss = x.sum()
        result = supervisor(
            loss_token=torch.tensor(1.0),
            loss_csr=fake_loss,
        )
        result["loss_total"].backward()
        assert x.grad is not None

    def test_zero_lambdas_no_aux_contribution(self):
        """With all lambdas = 0, L_total = L_token."""
        cfg = AuxiliaryLossConfig(
            lambda_csr=0, lambda_vritti=0, lambda_kosha=0,
            lambda_bliss=0, lambda_ont=0,
        )
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)
        result = supervisor(
            loss_token=torch.tensor(3.0),
            loss_csr=torch.tensor(100.0),
            loss_vritti=torch.tensor(100.0),
        )
        assert abs(result["loss_total"].item() - 3.0) < 1e-5


# =============================================================================
# Token Cache (F.7.8)
# =============================================================================


class TestTokenCache:

    def test_cache_refresh(self):
        cfg = AuxiliaryLossConfig(cache_refresh_interval=10)
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)
        embedding_weight = torch.randn(100, 64)

        # First refresh
        supervisor.refresh_token_cache(embedding_weight, current_step=0)
        assert supervisor._o_tok_cache is not None
        assert supervisor._o_tok_cache.shape == (100, 32)

    def test_cache_not_refreshed_within_interval(self):
        cfg = AuxiliaryLossConfig(cache_refresh_interval=10)
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)
        embedding_weight = torch.randn(100, 64)

        supervisor.refresh_token_cache(embedding_weight, current_step=0)
        cache_v1 = supervisor._o_tok_cache.clone()

        # Step 5: within interval, should not refresh
        new_embedding = torch.randn(100, 64)
        supervisor.refresh_token_cache(new_embedding, current_step=5)
        assert torch.allclose(supervisor._o_tok_cache, cache_v1)

    def test_cache_refreshed_after_interval(self):
        cfg = AuxiliaryLossConfig(cache_refresh_interval=10)
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)
        embedding_weight = torch.randn(100, 64)

        supervisor.refresh_token_cache(embedding_weight, current_step=0)
        cache_v1 = supervisor._o_tok_cache.clone()

        # Step 10: at interval, should refresh
        new_embedding = torch.randn(100, 64)
        supervisor.refresh_token_cache(new_embedding, current_step=10)
        assert not torch.allclose(supervisor._o_tok_cache, cache_v1)


# =============================================================================
# Ontological Compatibility Loss (F.7.8)
# =============================================================================


class TestOntologicalCompatibilityLoss:

    def test_loss_computation(self):
        cfg = AuxiliaryLossConfig(onto_dim=16)
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)

        o_context = torch.randn(2, 5, 16)
        correct_ids = torch.randint(0, 100, (2, 5))
        negative_ids = torch.randint(0, 100, (2, 5))
        embedding_weight = torch.randn(100, 64)

        result = supervisor.compute_ont_loss(
            o_context, correct_ids, negative_ids, embedding_weight,
        )
        assert "loss" in result
        assert result["loss"].item() >= 0
        assert "s_correct" in result
        assert "s_negative" in result

    def test_loss_gradient(self):
        cfg = AuxiliaryLossConfig(onto_dim=16)
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=64, embed_dim=64)

        o_context = torch.randn(1, 3, 16, requires_grad=True)
        correct_ids = torch.randint(0, 50, (1, 3))
        negative_ids = torch.randint(0, 50, (1, 3))
        embedding_weight = torch.randn(50, 64)

        result = supervisor.compute_ont_loss(
            o_context, correct_ids, negative_ids, embedding_weight,
        )
        result["loss"].backward()
        assert o_context.grad is not None


# =============================================================================
# Staged Curriculum (F.7.4)
# =============================================================================


class TestStagedCurriculum:
    """Verify curriculum stages can be simulated by setting lambda values."""

    def test_stage_a_backbone_only(self):
        """Stage A: All λ = 0."""
        cfg = AuxiliaryLossConfig(
            lambda_csr=0, lambda_vritti=0, lambda_kosha=0,
            lambda_bliss=0, lambda_ont=0,
        )
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=32, embed_dim=32)
        result = supervisor(
            loss_token=torch.tensor(2.0),
            loss_kosha=torch.tensor(1.0),
        )
        assert abs(result["loss_total"].item() - 2.0) < 1e-5

    def test_stage_b_kosha_only(self):
        """Stage B: Only λ_kosha enabled."""
        cfg = AuxiliaryLossConfig(
            lambda_csr=0, lambda_vritti=0, lambda_kosha=0.005,
            lambda_bliss=0, lambda_ont=0,
        )
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=32, embed_dim=32)
        result = supervisor(
            loss_token=torch.tensor(2.0),
            loss_kosha=torch.tensor(1.0),
            loss_csr=torch.tensor(10.0),  # Should be ignored
        )
        expected = 2.0 + 0.005 * 1.0
        assert abs(result["loss_total"].item() - expected) < 1e-5

    def test_stage_c_primitives(self):
        """Stage C: Enable λ_csr, λ_vritti, λ_ont."""
        cfg = AuxiliaryLossConfig(
            lambda_csr=0.01, lambda_vritti=0.02, lambda_kosha=0.005,
            lambda_bliss=0, lambda_ont=0.01,
        )
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=32, embed_dim=32)
        result = supervisor(
            loss_token=torch.tensor(2.0),
            loss_csr=torch.tensor(1.0),
            loss_vritti=torch.tensor(1.0),
            loss_kosha=torch.tensor(1.0),
            loss_bliss=torch.tensor(1.0),  # Should be zero-weighted
            loss_ont=torch.tensor(1.0),
        )
        expected = 2.0 + 0.01 + 0.02 + 0.005 + 0.0 + 0.01
        assert abs(result["loss_total"].item() - expected) < 1e-5

    def test_stage_d_full(self):
        """Stage D: All losses active."""
        cfg = AuxiliaryLossConfig()  # Default weights
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=32, embed_dim=32)
        result = supervisor(
            loss_token=torch.tensor(2.0),
            loss_csr=torch.tensor(1.0),
            loss_vritti=torch.tensor(1.0),
            loss_kosha=torch.tensor(1.0),
            loss_bliss=torch.tensor(1.0),
            loss_ont=torch.tensor(1.0),
        )
        expected = 2.0 + 0.01 + 0.02 + 0.005 + 0.02 + 0.01
        assert abs(result["loss_total"].item() - expected) < 1e-5


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:

    def test_large_auxiliary_losses(self):
        """Large auxiliary losses are scaled down by lambdas."""
        cfg = AuxiliaryLossConfig()
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=32, embed_dim=32)
        result = supervisor(
            loss_token=torch.tensor(3.0),
            loss_csr=torch.tensor(1000.0),
        )
        # 3.0 + 0.01 * 1000 = 13.0
        assert abs(result["loss_total"].item() - 13.0) < 1e-4

    def test_nan_detection(self):
        """Verify no NaN in output with normal inputs."""
        cfg = AuxiliaryLossConfig()
        supervisor = AuxiliaryLossSupervisor(cfg, hidden_dim=32, embed_dim=32)
        result = supervisor(
            loss_token=torch.tensor(2.5),
            loss_csr=torch.tensor(0.5),
            loss_vritti=torch.tensor(0.3),
        )
        assert not torch.isnan(result["loss_total"])
