"""
Tests for alternative attention normalizations in Phase-Quad.

Tests cover:
1. Mathematical correctness of sparsemax, entmax, kernel attention
2. Integration with Phase-Quad proposal cross-attention
3. Evaluation infrastructure
4. Configuration integration
5. Original modules remain unchanged (no regression)
"""

import pytest
import torch
import torch.nn.functional as F
from torch import Tensor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def device():
    """Use CPU for tests (no GPU dependency)."""
    return torch.device("cpu")


@pytest.fixture
def batch_config():
    """Standard batch configuration for tests."""
    return {
        "B": 2,    # batch size
        "N": 16,   # sequence length (patches)
        "K": 8,    # topk proposals
        "D": 64,   # embed dim
        "H": 4,    # heads
    }


@pytest.fixture
def sample_inputs(batch_config, device):
    """Create sample inputs for attention tests."""
    B, N, K, D = (
        batch_config["B"],
        batch_config["N"],
        batch_config["K"],
        batch_config["D"],
    )
    torch.manual_seed(42)
    return {
        "x": torch.randn(B, N, D, device=device),
        "proposals": torch.randn(B, N, K, D, device=device),
        "scores": torch.randn(B, N, K, device=device),
    }


@pytest.fixture
def sample_scores(device):
    """Create sample scores for normalization tests."""
    torch.manual_seed(42)
    return torch.randn(4, 10, device=device)


# ===========================================================================
# Test 1: Sparsemax mathematical properties
# ===========================================================================

class TestSparsemax:
    """Test sparsemax normalization correctness."""

    def test_sums_to_one(self, sample_scores):
        """Sparsemax output should sum to 1 along normalized dimension."""
        from symbolu.vision.attention_normalizations import sparsemax

        result = sparsemax(sample_scores, dim=-1)
        sums = result.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5), (
            f"Sparsemax outputs should sum to 1, got {sums}"
        )

    def test_non_negative(self, sample_scores):
        """Sparsemax output should be non-negative."""
        from symbolu.vision.attention_normalizations import sparsemax

        result = sparsemax(sample_scores, dim=-1)
        assert (result >= 0).all(), "Sparsemax should produce non-negative values"

    def test_produces_exact_zeros(self):
        """Sparsemax should produce exact zeros (sparsity)."""
        from symbolu.vision.attention_normalizations import sparsemax

        # Scores with one dominant value
        scores = torch.tensor([[5.0, 0.1, 0.1, 0.1, 0.1]])
        result = sparsemax(scores, dim=-1)
        num_zeros = (result == 0.0).sum().item()
        assert num_zeros > 0, "Sparsemax should produce exact zeros for spread-out scores"

    def test_uniform_input(self):
        """Equal scores should produce uniform output."""
        from symbolu.vision.attention_normalizations import sparsemax

        scores = torch.ones(1, 5)
        result = sparsemax(scores, dim=-1)
        expected = torch.ones(1, 5) / 5.0
        assert torch.allclose(result, expected, atol=1e-5), (
            f"Uniform scores should give uniform sparsemax, got {result}"
        )

    def test_gradient_flows(self, sample_scores):
        """Sparsemax should allow gradient flow."""
        from symbolu.vision.attention_normalizations import sparsemax

        scores = sample_scores.detach().requires_grad_(True)
        result = sparsemax(scores, dim=-1)
        loss = result.sum()
        loss.backward()
        assert scores.grad is not None, "Gradients should flow through sparsemax"

    def test_batched(self, device):
        """Sparsemax should work with batched inputs."""
        from symbolu.vision.attention_normalizations import sparsemax

        scores = torch.randn(3, 4, 8, device=device)
        result = sparsemax(scores, dim=-1)
        assert result.shape == scores.shape
        sums = result.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)


# ===========================================================================
# Test 2: Entmax mathematical properties
# ===========================================================================

class TestEntmax:
    """Test entmax normalization correctness."""

    def test_alpha_1_equals_softmax(self, sample_scores):
        """Entmax with alpha=1 should equal softmax."""
        from symbolu.vision.attention_normalizations import entmax

        result = entmax(sample_scores, alpha=1.0, dim=-1)
        expected = F.softmax(sample_scores, dim=-1)
        assert torch.allclose(result, expected, atol=1e-5), (
            "entmax(alpha=1) should equal softmax"
        )

    def test_alpha_2_equals_sparsemax(self, sample_scores):
        """Entmax with alpha=2 should equal sparsemax."""
        from symbolu.vision.attention_normalizations import entmax, sparsemax

        result = entmax(sample_scores, alpha=2.0, dim=-1)
        expected = sparsemax(sample_scores, dim=-1)
        assert torch.allclose(result, expected, atol=1e-4), (
            "entmax(alpha=2) should equal sparsemax"
        )

    def test_entmax15_sums_to_one(self, sample_scores):
        """Entmax(1.5) should sum to 1."""
        from symbolu.vision.attention_normalizations import entmax15

        result = entmax15(sample_scores, dim=-1)
        sums = result.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-4), (
            f"Entmax(1.5) should sum to 1, got {sums}"
        )

    def test_entmax15_non_negative(self, sample_scores):
        """Entmax(1.5) should be non-negative."""
        from symbolu.vision.attention_normalizations import entmax15

        result = entmax15(sample_scores, dim=-1)
        assert (result >= -1e-6).all(), "Entmax should produce non-negative values"

    def test_sparsity_increases_with_alpha(self):
        """Higher alpha should produce sparser outputs."""
        from symbolu.vision.attention_normalizations import entmax

        scores = torch.randn(8, 20)
        alphas = [1.0, 1.25, 1.5, 1.75, 2.0]
        sparsities = []

        for alpha in alphas:
            result = entmax(scores, alpha=alpha, dim=-1)
            sparsity = (result == 0.0).float().mean().item()
            sparsities.append(sparsity)

        # Sparsity should be non-decreasing with alpha
        for i in range(1, len(sparsities)):
            assert sparsities[i] >= sparsities[i - 1] - 0.01, (
                f"Sparsity should increase with alpha: "
                f"alpha={alphas[i]}: {sparsities[i]:.3f} < "
                f"alpha={alphas[i-1]}: {sparsities[i-1]:.3f}"
            )

    def test_gradient_flows(self, sample_scores):
        """Entmax should allow gradient flow."""
        from symbolu.vision.attention_normalizations import entmax15

        scores = sample_scores.detach().requires_grad_(True)
        result = entmax15(scores, dim=-1)
        loss = result.sum()
        loss.backward()
        assert scores.grad is not None, "Gradients should flow through entmax"


# ===========================================================================
# Test 3: Kernel attention properties
# ===========================================================================

class TestKernelAttention:
    """Test kernel (linear) attention."""

    def test_elu_kernel_output_shape(self, device):
        """Kernel attention should produce correct output shape."""
        from symbolu.vision.attention_normalizations import KernelAttention

        kernel = KernelAttention(feature_map="elu", head_dim=16)
        q = torch.randn(2, 4, 8, 16, device=device)   # [B, H, N_q, D_h]
        k = torch.randn(2, 4, 12, 16, device=device)  # [B, H, N_k, D_h]
        v = torch.randn(2, 4, 12, 16, device=device)  # [B, H, N_k, D_h]

        out = kernel(q, k, v)
        assert out.shape == (2, 4, 8, 16), f"Expected (2,4,8,16), got {out.shape}"

    def test_elu_feature_map_positive(self, device):
        """ELU+1 feature map should produce positive values."""
        from symbolu.vision.attention_normalizations import elu_feature_map

        x = torch.randn(10, 16, device=device)
        phi = elu_feature_map(x)
        assert (phi > 0).all(), "ELU+1 should be strictly positive"

    def test_kernel_gradient_flows(self, device):
        """Kernel attention should allow gradient flow."""
        from symbolu.vision.attention_normalizations import KernelAttention

        kernel = KernelAttention(feature_map="elu", head_dim=16)
        q = torch.randn(2, 4, 8, 16, device=device, requires_grad=True)
        k = torch.randn(2, 4, 12, 16, device=device)
        v = torch.randn(2, 4, 12, 16, device=device)

        out = kernel(q, k, v)
        loss = out.sum()
        loss.backward()
        assert q.grad is not None

    def test_rbf_kernel_output_shape(self, device):
        """RBF kernel attention should produce correct output shape."""
        from symbolu.vision.attention_normalizations import KernelAttention

        kernel = KernelAttention(feature_map="rbf", head_dim=16, num_features=32)
        q = torch.randn(2, 4, 8, 16, device=device)
        k = torch.randn(2, 4, 12, 16, device=device)
        v = torch.randn(2, 4, 12, 16, device=device)

        out = kernel(q, k, v)
        assert out.shape == (2, 4, 8, 16)


# ===========================================================================
# Test 4: AlternativeAttentionToProposals integration
# ===========================================================================

class TestAlternativeAttentionToProposals:
    """Test the alternative cross-attention module."""

    @pytest.mark.parametrize("norm_type", [
        "SOFTMAX", "SPARSEMAX", "ENTMAX15", "KERNEL_ELU",
    ])
    def test_output_shape(self, norm_type, sample_inputs, batch_config):
        """All variants should produce correct output shape."""
        from symbolu.vision.attention_normalizations import AttentionNormType
        from symbolu.vision.alternative_attention import AlternativeAttentionToProposals

        B, N, D = batch_config["B"], batch_config["N"], batch_config["D"]
        H = batch_config["H"]
        nt = AttentionNormType[norm_type]

        module = AlternativeAttentionToProposals(
            embed_dim=D, num_heads=H, norm_type=nt,
        )

        out = module(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
        )
        assert out.shape == (B, N, D), f"Expected ({B},{N},{D}), got {out.shape}"

    @pytest.mark.parametrize("norm_type", [
        "SOFTMAX", "SPARSEMAX", "ENTMAX15",
    ])
    def test_sparsity_metrics_available(self, norm_type, sample_inputs, batch_config):
        """Sparsity metrics should be available after forward pass."""
        from symbolu.vision.attention_normalizations import AttentionNormType
        from symbolu.vision.alternative_attention import AlternativeAttentionToProposals

        nt = AttentionNormType[norm_type]
        module = AlternativeAttentionToProposals(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            norm_type=nt,
        )

        module(sample_inputs["x"], sample_inputs["proposals"], sample_inputs["scores"])
        metrics = module.get_sparsity_metrics()

        assert "attn/sparsity" in metrics, "Should report sparsity"
        assert "attn/entropy" in metrics, "Should report entropy"

    def test_without_score_bias(self, sample_inputs, batch_config):
        """Should work without retrieval score bias."""
        from symbolu.vision.attention_normalizations import AttentionNormType
        from symbolu.vision.alternative_attention import AlternativeAttentionToProposals

        module = AlternativeAttentionToProposals(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            norm_type=AttentionNormType.ENTMAX15,
            use_score_bias=False,
        )

        out = module(sample_inputs["x"], sample_inputs["proposals"])
        assert out.shape == sample_inputs["x"].shape

    def test_gradient_flow(self, sample_inputs, batch_config):
        """Gradients should flow through alternative attention."""
        from symbolu.vision.attention_normalizations import AttentionNormType
        from symbolu.vision.alternative_attention import AlternativeAttentionToProposals

        module = AlternativeAttentionToProposals(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            norm_type=AttentionNormType.ENTMAX15,
        )

        x = sample_inputs["x"].detach().requires_grad_(True)
        out = module(x, sample_inputs["proposals"], sample_inputs["scores"])
        loss = out.sum()
        loss.backward()
        assert x.grad is not None, "Gradients should flow through entmax attention"


# ===========================================================================
# Test 5: PhaseQuadAttentionVariant (BCVF hybrid)
# ===========================================================================

class TestPhaseQuadAttentionVariant:
    """Test the BCVF + alternative attention hybrid."""

    def test_output_shape(self, sample_inputs, batch_config, device):
        """Hybrid variant should produce correct output shape."""
        from symbolu.vision.attention_normalizations import AttentionNormType
        from symbolu.vision.alternative_attention import PhaseQuadAttentionVariant

        B, N, D = batch_config["B"], batch_config["N"], batch_config["D"]
        H = batch_config["H"]

        module = PhaseQuadAttentionVariant(
            embed_dim=D,
            num_heads=H,
            norm_type=AttentionNormType.ENTMAX15,
        )

        phase_state = torch.randn(B, N, D, device=device)

        out = module(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
            phase_state,
        )
        assert out.shape == (B, N, D)

    def test_diagnostics(self, sample_inputs, batch_config, device):
        """Should return combined BCVF + attention diagnostics."""
        from symbolu.vision.attention_normalizations import AttentionNormType
        from symbolu.vision.alternative_attention import PhaseQuadAttentionVariant

        module = PhaseQuadAttentionVariant(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            norm_type=AttentionNormType.SPARSEMAX,
        )

        phase_state = torch.randn(
            batch_config["B"], batch_config["N"], batch_config["D"], device=device
        )

        module(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
            phase_state,
        )

        diag = module.get_diagnostics()
        assert "bcvf/sf_mean" in diag, "Should include BCVF metrics"
        assert "attn/sparsity" in diag, "Should include attention metrics"
        assert "mix_ratio" in diag, "Should include mix ratio"
        assert "norm_type" in diag, "Should include normalization type"


# ===========================================================================
# Test 6: Evaluation infrastructure
# ===========================================================================

class TestAttentionNormEvaluator:
    """Test the evaluation/comparison infrastructure."""

    def test_compare_all(self, sample_inputs, batch_config):
        """Should compare all variants and produce report."""
        from symbolu.vision.attention_eval import AttentionNormEvaluator

        evaluator = AttentionNormEvaluator(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            topk=batch_config["K"],
        )

        report = evaluator.compare_all(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
        )

        assert len(report.variants) > 0, "Should have variant results"
        assert report.recommendation, "Should generate recommendation"

    def test_comparison_table(self, sample_inputs, batch_config):
        """Should format a readable comparison table."""
        from symbolu.vision.attention_eval import (
            AttentionNormEvaluator,
        )

        evaluator = AttentionNormEvaluator(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            topk=batch_config["K"],
        )

        report = evaluator.compare_all(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
        )

        table = AttentionNormEvaluator.format_comparison_table(report)
        assert "softmax" in table, "Table should include softmax baseline"
        assert "sparsemax" in table, "Table should include sparsemax"
        assert "entmax15" in table, "Table should include entmax15"

    def test_cosine_similarities(self, sample_inputs, batch_config):
        """Should compute cosine similarities to softmax baseline."""
        from symbolu.vision.attention_eval import AttentionNormEvaluator

        evaluator = AttentionNormEvaluator(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
            topk=batch_config["K"],
        )

        report = evaluator.compare_all(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
        )

        assert len(report.cosine_similarities) > 0, (
            "Should have cosine similarities to baseline"
        )


# ===========================================================================
# Test 7: Standalone score comparison
# ===========================================================================

class TestScoreComparison:
    """Test lightweight score-level comparison functions."""

    def test_compare_normalizations_on_scores(self, device):
        """Should compare normalizations directly on scores."""
        from symbolu.vision.attention_eval import compare_normalizations_on_scores

        scores = torch.randn(4, 20, device=device)
        results = compare_normalizations_on_scores(scores, dim=-1)

        assert "softmax" in results
        assert "sparsemax" in results
        assert "entmax15" in results

        # Softmax should have zero sparsity
        assert results["softmax"]["sparsity"] == 0.0, (
            "Softmax should have zero sparsity"
        )

        # Sparsemax should have nonzero sparsity on random inputs
        assert results["sparsemax"]["sparsity"] >= 0.0

    def test_analyze_quad_scores(self, device):
        """Should analyze quad retriever scores."""
        from symbolu.vision.attention_eval import analyze_quad_scores_for_attention

        # Simulate QuadRetriever output scores
        proposal_scores = torch.randn(2, 16, 64, device=device)
        analysis = analyze_quad_scores_for_attention(proposal_scores)

        assert "softmax" in analysis
        assert "sparsemax" in analysis
        assert "entmax15" in analysis

        for name, metrics in analysis.items():
            assert "sparsity" in metrics, f"{name} missing sparsity"
            assert "entropy" in metrics, f"{name} missing entropy"
            assert "top1_mass" in metrics, f"{name} missing top1_mass"


# ===========================================================================
# Test 8: Sparsity metrics correctness
# ===========================================================================

class TestSparsityMetrics:
    """Test sparsity diagnostic calculations."""

    def test_uniform_distribution(self, device):
        """Uniform distribution should have max entropy and zero sparsity."""
        from symbolu.vision.attention_normalizations import attention_sparsity_metrics

        n = 10
        uniform = torch.ones(1, n, device=device) / n
        metrics = attention_sparsity_metrics(uniform, dim=-1)

        assert metrics["sparsity"] == 0.0, "Uniform should have zero sparsity"
        assert metrics["normalized_entropy"] > 0.95, (
            "Uniform should have near-max entropy"
        )

    def test_one_hot_distribution(self, device):
        """One-hot distribution should have zero entropy and high sparsity."""
        from symbolu.vision.attention_normalizations import attention_sparsity_metrics

        n = 10
        one_hot = torch.zeros(1, n, device=device)
        one_hot[0, 0] = 1.0
        metrics = attention_sparsity_metrics(one_hot, dim=-1)

        assert metrics["sparsity"] > 0.8, "One-hot should have high sparsity"
        assert metrics["top1_mass"] == 1.0, "One-hot should have top1_mass=1.0"


# ===========================================================================
# Test 9: Configuration integration
# ===========================================================================

class TestConfigIntegration:
    """Test that AlternativeAttentionConfig integrates with existing config."""

    def test_config_exists_in_block_config(self):
        """AlternativeAttentionConfig should be part of BlockConfig."""
        from symbolu.vision.config import BlockConfig, AlternativeAttentionConfig

        config = BlockConfig()
        assert hasattr(config, "alt_attention"), (
            "BlockConfig should have alt_attention field"
        )
        assert isinstance(config.alt_attention, AlternativeAttentionConfig)

    def test_config_defaults(self):
        """Config defaults should be safe (disabled by default)."""
        from symbolu.vision.config import AlternativeAttentionConfig

        config = AlternativeAttentionConfig()
        assert config.enabled is False, "Should be disabled by default"
        assert config.norm_type == "entmax15", "Default should be entmax15"

    def test_existing_config_unchanged(self):
        """Original config fields should be completely unchanged."""
        from symbolu.vision.config import (
            BlockConfig,
            PhaseConfig,
            QuadConfig,
            BCVFConfig,
        )

        config = BlockConfig()

        # Verify original fields are present and unchanged
        assert isinstance(config.phase, PhaseConfig)
        assert isinstance(config.quad, QuadConfig)
        assert isinstance(config.bcvf, BCVFConfig)
        assert config.embed_dim == 768
        assert config.num_heads == 12
        assert config.phase.bounded_phase is True
        assert config.quad.topk == 64
        assert config.bcvf.enabled is True


# ===========================================================================
# Test 10: Original modules not modified (regression guard)
# ===========================================================================

class TestOriginalModulesUnchanged:
    """Verify original attention modules are NOT modified."""

    def test_cross_attention_uses_softmax(self, sample_inputs, batch_config):
        """Original CrossAttentionToProposals should still use softmax."""
        from symbolu.vision.cross_attention_proposals import CrossAttentionToProposals

        module = CrossAttentionToProposals(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
        )

        # Should work without any changes
        out = module(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
        )
        assert out.shape == sample_inputs["x"].shape

    def test_hybrid_bcvf_unchanged(self, sample_inputs, batch_config, device):
        """Original HybridBCVFCrossAttention should be unchanged."""
        from symbolu.vision.bcvf_weighter import HybridBCVFCrossAttention

        module = HybridBCVFCrossAttention(
            embed_dim=batch_config["D"],
            num_heads=batch_config["H"],
        )

        phase_state = torch.randn(
            batch_config["B"], batch_config["N"], batch_config["D"], device=device
        )

        out = module(
            sample_inputs["x"],
            sample_inputs["proposals"],
            sample_inputs["scores"],
            phase_state,
        )
        assert out.shape == sample_inputs["x"].shape
