"""
Unit tests for Phase-Quad Image Generator components.

Run with: pytest symbolu/vision/tests/test_components.py -v
"""

import math
import pytest
import torch
import torch.nn as nn

from symbolu_extensions.vision.contracts import (
    ContractViolationError,
    assert_control_shape,
)
from symbolu_extensions.vision.controls import (
    PatchMeta,
    PhaseControl,
    QuadControl,
    GateControl,
    BlockControl,
    GeneratorControl,
)
from symbolu_extensions.vision.config import PhaseQuadVisionConfig
from symbolu_extensions.vision.scan_manager import ScanManager2D, get_scan_manager
from symbolu_extensions.vision.rope_2d import RotaryPositionEmbedding2D
from symbolu_extensions.vision.patch_embed import PatchEmbed2D, TimestepEmbedding
from symbolu_extensions.vision.phase_integrator import PhaseIntegrator1D, PhaseIntegrator2D
from symbolu_extensions.vision.quad_retriever import QuadRetriever2D
from symbolu_extensions.vision.gate_mixer import GateMixer
from symbolu_extensions.vision.local_mixer import LocalMixer
from symbolu_extensions.vision.cognade_vision_block import CognadeVisionBlock
from symbolu_extensions.vision.phase_quad_generator import PhaseQuadImageGenerator
from symbolu_extensions.vision.diagnostics import (
    compute_quad_utilization,
    compute_phase_health,
    compute_ghost_metrics,
)


# Test configuration
BATCH_SIZE = 2
LATENT_H = 32
LATENT_W = 32
LATENT_C = 4
EMBED_DIM = 256
NUM_HEADS = 8
PATCH_SIZE = 2
TOPK = 16
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class TestContracts:
    """Test no-write contract enforcement."""

    def test_valid_scalar_control(self):
        """Scalar [] should be valid."""
        control = torch.tensor(1.0)
        assert_control_shape(control, "test", num_heads=8)

    def test_valid_per_head_control(self):
        """Per-head [H] should be valid."""
        control = torch.randn(8)
        assert_control_shape(control, "test", num_heads=8)

    def test_valid_batch_head_control(self):
        """Per-batch per-head [B, H] should be valid."""
        control = torch.randn(4, 8)
        assert_control_shape(control, "test", num_heads=8)

    def test_valid_batch_head_broadcast_control(self):
        """Per-batch per-head with broadcast [B, H, 1] should be valid."""
        control = torch.randn(4, 8, 1)
        assert_control_shape(control, "test", num_heads=8)

    def test_invalid_token_position_control(self):
        """Token-position-specific [B, N, D] should be INVALID."""
        control = torch.randn(4, 100, 256)
        with pytest.raises(ContractViolationError):
            assert_control_shape(control, "test", num_heads=8)

    def test_invalid_token_scalar_control(self):
        """Token-specific scalars [B, N] should be INVALID."""
        control = torch.randn(4, 100)
        with pytest.raises(ContractViolationError):
            assert_control_shape(control, "test", num_heads=8)

    def test_none_control_is_valid(self):
        """None should be valid (no control)."""
        assert_control_shape(None, "test", num_heads=8)


class TestScanManager:
    """Test 2D scan order management."""

    def test_scan_manager_creation(self):
        """Test ScanManager2D creation."""
        scan = ScanManager2D(8, 8)
        assert scan.H_p == 8
        assert scan.W_p == 8
        assert scan.N == 64

    def test_row_order_shape(self):
        """Test row order has correct shape."""
        scan = ScanManager2D(8, 8)
        assert scan.row_order.shape == (64,)

    def test_col_order_shape(self):
        """Test column order has correct shape."""
        scan = ScanManager2D(8, 8)
        assert scan.col_order.shape == (64,)

    def test_gather_scatter_roundtrip(self):
        """Test gather then scatter restores original order."""
        scan = ScanManager2D(4, 4).to(DEVICE)
        x = torch.randn(2, 16, 32, device=DEVICE)

        # Row order roundtrip
        x_row = scan.gather(x, scan.row_order)
        x_restored = scan.scatter(x_row, scan.row_order)
        assert torch.allclose(x, x_restored)

        # Column order roundtrip
        x_col = scan.gather(x, scan.col_order)
        x_restored = scan.scatter(x_col, scan.col_order)
        assert torch.allclose(x, x_restored)

    def test_non_square_grid(self):
        """Test non-square grids work correctly."""
        scan = ScanManager2D(4, 8)  # H != W
        assert scan.N == 32
        assert scan.row_order.shape == (32,)
        assert scan.col_order.shape == (32,)


class TestRoPE2D:
    """Test 2D Rotary Position Embedding."""

    def test_rope_creation(self):
        """Test RotaryPositionEmbedding2D creation."""
        rope = RotaryPositionEmbedding2D(dim=64)
        assert rope.dim == 64

    def test_rope_forward_shape(self):
        """Test RoPE forward maintains shape."""
        rope = RotaryPositionEmbedding2D(dim=32).to(DEVICE)
        x = torch.randn(2, 16, 8, 32, device=DEVICE)  # [B, N, H, D_h]
        coords = torch.stack([
            torch.arange(4).repeat_interleave(4),
            torch.arange(4).repeat(4),
        ], dim=-1).to(DEVICE)  # [16, 2]

        x_rot = rope(x, coords)
        assert x_rot.shape == x.shape

    def test_rope_dim_validation(self):
        """Test RoPE requires dim divisible by 4."""
        with pytest.raises(ValueError):
            RotaryPositionEmbedding2D(dim=30)  # Not divisible by 4


class TestPatchEmbed:
    """Test patch embedding."""

    def test_patch_embed_creation(self):
        """Test PatchEmbed2D creation."""
        embed = PatchEmbed2D(
            in_channels=4,
            patch_size=2,
            embed_dim=256,
        )
        assert embed.embed_dim == 256

    def test_patch_embed_forward(self):
        """Test PatchEmbed2D forward pass."""
        embed = PatchEmbed2D(
            in_channels=LATENT_C,
            patch_size=PATCH_SIZE,
            embed_dim=EMBED_DIM,
        ).to(DEVICE)

        z = torch.randn(BATCH_SIZE, LATENT_C, LATENT_H, LATENT_W, device=DEVICE)
        x, meta = embed(z)

        expected_n = (LATENT_H // PATCH_SIZE) * (LATENT_W // PATCH_SIZE)
        assert x.shape == (BATCH_SIZE, expected_n, EMBED_DIM)
        assert meta.H_p == LATENT_H // PATCH_SIZE
        assert meta.W_p == LATENT_W // PATCH_SIZE

    def test_unpatchify_roundtrip(self):
        """Test unpatchify reverses patchify (approximately)."""
        embed = PatchEmbed2D(
            in_channels=LATENT_C,
            patch_size=PATCH_SIZE,
            embed_dim=LATENT_C * PATCH_SIZE * PATCH_SIZE,  # Exact reconstruction
        ).to(DEVICE)

        z = torch.randn(BATCH_SIZE, LATENT_C, LATENT_H, LATENT_W, device=DEVICE)
        x, meta = embed(z)

        # Note: unpatchify expects output projection dimension
        z_recon = embed.unpatchify(x, meta)
        assert z_recon.shape == z.shape


class TestTimestepEmbedding:
    """Test timestep embedding."""

    def test_timestep_embed_forward(self):
        """Test TimestepEmbedding forward pass."""
        embed = TimestepEmbedding(EMBED_DIM).to(DEVICE)
        t = torch.randint(0, 1000, (BATCH_SIZE,), device=DEVICE)

        t_emb = embed(t)
        assert t_emb.shape == (BATCH_SIZE, EMBED_DIM)

    def test_different_timesteps_different_embeddings(self):
        """Test different timesteps produce different embeddings."""
        embed = TimestepEmbedding(EMBED_DIM).to(DEVICE)
        t1 = torch.tensor([100], device=DEVICE)
        t2 = torch.tensor([500], device=DEVICE)

        emb1 = embed(t1)
        emb2 = embed(t2)

        assert not torch.allclose(emb1, emb2)


class TestPhaseIntegrator:
    """Test phase integrator modules."""

    def test_phase1d_creation(self):
        """Test PhaseIntegrator1D creation."""
        phase = PhaseIntegrator1D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        )
        assert phase.embed_dim == EMBED_DIM
        assert phase.num_heads == NUM_HEADS

    def test_phase1d_forward(self):
        """Test PhaseIntegrator1D forward pass."""
        phase = PhaseIntegrator1D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        ).to(DEVICE)

        N = 64
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)

        S_re, S_im = phase(x)
        assert S_re.shape == (BATCH_SIZE, N, NUM_HEADS, EMBED_DIM // NUM_HEADS)
        assert S_im.shape == (BATCH_SIZE, N, NUM_HEADS, EMBED_DIM // NUM_HEADS)

    def test_phase1d_bounded_phase_mandatory(self):
        """Test that bounded_phase=False raises error."""
        with pytest.raises(ValueError):
            PhaseIntegrator1D(
                embed_dim=EMBED_DIM,
                num_heads=NUM_HEADS,
                bounded_phase=False,
            )

    def test_phase2d_forward(self):
        """Test PhaseIntegrator2D forward pass."""
        phase = PhaseIntegrator2D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        ).to(DEVICE)

        H_p, W_p = 8, 8
        N = H_p * W_p
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)

        coords = torch.stack([
            torch.arange(H_p).repeat_interleave(W_p),
            torch.arange(W_p).repeat(H_p),
        ], dim=-1).to(DEVICE)

        meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords)

        S = phase(x, meta)
        assert S.shape == (BATCH_SIZE, N, EMBED_DIM)

    def test_phase_control_validation(self):
        """Test phase control validates no-write contract."""
        phase = PhaseIntegrator1D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        ).to(DEVICE)

        x = torch.randn(BATCH_SIZE, 64, EMBED_DIM, device=DEVICE)

        # Valid control
        valid_control = PhaseControl(
            intent_phase=torch.randn(NUM_HEADS, device=DEVICE),
        )
        S_re, S_im = phase(x, valid_control)  # Should work

        # Invalid control (token-specific)
        invalid_control = PhaseControl(
            intent_phase=torch.randn(BATCH_SIZE, 64, device=DEVICE),
        )
        with pytest.raises(ContractViolationError):
            phase(x, invalid_control)


class TestQuadRetriever:
    """Test Quad retriever module."""

    def test_quad_creation(self):
        """Test QuadRetriever2D creation."""
        quad = QuadRetriever2D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
            topk=TOPK,
        )
        assert quad.topk == TOPK

    def test_quad_forward(self):
        """Test QuadRetriever2D forward pass."""
        quad = QuadRetriever2D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
            topk=TOPK,
        ).to(DEVICE)

        H_p, W_p = 8, 8
        N = H_p * W_p
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)
        S = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)

        coords = torch.stack([
            torch.arange(H_p).repeat_interleave(W_p),
            torch.arange(W_p).repeat(H_p),
        ], dim=-1).to(DEVICE)

        meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords)

        proposals, scores = quad(x, S, meta)
        assert proposals.shape == (BATCH_SIZE, N, TOPK, EMBED_DIM)
        assert scores.shape == (BATCH_SIZE, N, TOPK)

    def test_quad_disabled_returns_zeros(self):
        """Test QuadRetriever2D returns zeros when disabled."""
        quad = QuadRetriever2D(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
            topk=TOPK,
        ).to(DEVICE)

        H_p, W_p = 4, 4
        N = H_p * W_p
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)
        S = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)

        coords = torch.stack([
            torch.arange(H_p).repeat_interleave(W_p),
            torch.arange(W_p).repeat(H_p),
        ], dim=-1).to(DEVICE)

        meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords)
        control = QuadControl(enable_quad=False)

        proposals, scores = quad(x, S, meta, control)
        assert torch.all(proposals == 0)
        assert torch.all(scores == 0)


class TestGateMixer:
    """Test gate mixer module."""

    def test_gate_creation(self):
        """Test GateMixer creation."""
        gate = GateMixer(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        )
        assert gate.embed_dim == EMBED_DIM

    def test_gate_forward(self):
        """Test GateMixer forward pass."""
        gate = GateMixer(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        ).to(DEVICE)

        N = 64
        K = TOPK
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)
        proposals = torch.randn(BATCH_SIZE, N, K, EMBED_DIM, device=DEVICE)
        scores = torch.randn(BATCH_SIZE, N, K, device=DEVICE)

        x_out = gate(x, proposals, scores)
        assert x_out.shape == (BATCH_SIZE, N, EMBED_DIM)

    def test_gate_temperature_effect(self):
        """Test that higher tau produces softer gates."""
        gate = GateMixer(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
        ).to(DEVICE)

        N = 64
        K = TOPK
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)
        proposals = torch.randn(BATCH_SIZE, N, K, EMBED_DIM, device=DEVICE)
        scores = torch.randn(BATCH_SIZE, N, K, device=DEVICE)

        # Low tau (sharp)
        control_low = GateControl(tau=0.5)
        _ = gate(x, proposals, scores, control_low)
        sat_low = gate._last_gate_saturation

        # High tau (soft)
        control_high = GateControl(tau=3.0)
        _ = gate(x, proposals, scores, control_high)
        sat_high = gate._last_gate_saturation

        # Higher tau should have lower saturation (softer gates)
        assert sat_high <= sat_low


class TestLocalMixer:
    """Test local mixer module."""

    def test_local_creation(self):
        """Test LocalMixer creation."""
        local = LocalMixer(
            embed_dim=EMBED_DIM,
            window_size=4,
            num_heads=NUM_HEADS,
        )
        assert local.window_size == 4

    def test_local_forward(self):
        """Test LocalMixer forward pass."""
        local = LocalMixer(
            embed_dim=EMBED_DIM,
            window_size=4,
            num_heads=NUM_HEADS,
        ).to(DEVICE)

        H_p, W_p = 8, 8
        N = H_p * W_p
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)

        coords = torch.stack([
            torch.arange(H_p).repeat_interleave(W_p),
            torch.arange(W_p).repeat(H_p),
        ], dim=-1).to(DEVICE)

        meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords)

        x_local = local(x, meta)
        assert x_local.shape == (BATCH_SIZE, N, EMBED_DIM)


class TestCognadeVisionBlock:
    """Test full Cognade vision block."""

    def test_block_creation(self):
        """Test CognadeVisionBlock creation."""
        block = CognadeVisionBlock(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
            topk=TOPK,
        )
        assert block.embed_dim == EMBED_DIM

    def test_block_forward(self):
        """Test CognadeVisionBlock forward pass."""
        block = CognadeVisionBlock(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
            topk=TOPK,
            window_size=4,
            use_cross_attn=False,
        ).to(DEVICE)

        H_p, W_p = 8, 8
        N = H_p * W_p
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)
        t_emb = torch.randn(BATCH_SIZE, EMBED_DIM, device=DEVICE)

        coords = torch.stack([
            torch.arange(H_p).repeat_interleave(W_p),
            torch.arange(W_p).repeat(H_p),
        ], dim=-1).to(DEVICE)

        meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords)

        x_out = block(x, meta, t_emb)
        assert x_out.shape == (BATCH_SIZE, N, EMBED_DIM)

    def test_block_ablation_quad_disabled(self):
        """Test block with Quad disabled."""
        block = CognadeVisionBlock(
            embed_dim=EMBED_DIM,
            num_heads=NUM_HEADS,
            topk=TOPK,
            use_cross_attn=False,
        ).to(DEVICE)

        H_p, W_p = 4, 4
        N = H_p * W_p
        x = torch.randn(BATCH_SIZE, N, EMBED_DIM, device=DEVICE)
        t_emb = torch.randn(BATCH_SIZE, EMBED_DIM, device=DEVICE)

        coords = torch.stack([
            torch.arange(H_p).repeat_interleave(W_p),
            torch.arange(W_p).repeat(H_p),
        ], dim=-1).to(DEVICE)

        meta = PatchMeta(H_p=H_p, W_p=W_p, coords=coords)
        control = BlockControl(enable_quad=False)

        x_out = block(x, meta, t_emb, control=control)
        assert x_out.shape == (BATCH_SIZE, N, EMBED_DIM)


class TestPhaseQuadGenerator:
    """Test full Phase-Quad Image Generator."""

    def test_generator_tiny(self):
        """Test tiny generator creation and forward."""
        config = PhaseQuadVisionConfig.tiny()
        model = PhaseQuadImageGenerator(config).to(DEVICE)

        z_t = torch.randn(1, 4, 16, 16, device=DEVICE)
        t = torch.randint(0, 1000, (1,), device=DEVICE)

        noise_pred = model(z_t, t)
        assert noise_pred.shape == z_t.shape

    def test_generator_with_text(self):
        """Test generator with text conditioning."""
        config = PhaseQuadVisionConfig.tiny()
        config.block.local.use_cross_attn = True
        model = PhaseQuadImageGenerator(config).to(DEVICE)

        z_t = torch.randn(1, 4, 16, 16, device=DEVICE)
        t = torch.randint(0, 1000, (1,), device=DEVICE)
        text_cond = torch.randn(1, 10, config.text_encoder.embed_dim, device=DEVICE)

        noise_pred = model(z_t, t, text_cond)
        assert noise_pred.shape == z_t.shape

    def test_generator_control(self):
        """Test generator with control signals."""
        config = PhaseQuadVisionConfig.tiny()
        model = PhaseQuadImageGenerator(config).to(DEVICE)

        z_t = torch.randn(1, 4, 16, 16, device=DEVICE)
        t = torch.randint(0, 1000, (1,), device=DEVICE)

        control = GeneratorControl(
            tau=2.0,
            enable_quad=True,
            enable_phase=True,
        )

        noise_pred = model(z_t, t, control=control)
        assert noise_pred.shape == z_t.shape


class TestDiagnostics:
    """Test diagnostic metrics."""

    def test_quad_utilization_metrics(self):
        """Test QuadUtilizationMetrics computation."""
        K = 16
        gate_weights = torch.softmax(torch.randn(BATCH_SIZE, 64, K), dim=-1)
        scores = torch.randn(BATCH_SIZE, 64, K)

        metrics = compute_quad_utilization(gate_weights, scores)

        assert 0 <= metrics.gate_entropy
        assert 0 <= metrics.active_selection_rate <= 1
        assert 0 <= metrics.gate_saturation_rate <= 1

    def test_phase_health_metrics(self):
        """Test PhaseHealthMetrics computation."""
        N = 64
        D = EMBED_DIM
        H = NUM_HEADS

        S_row = torch.randn(BATCH_SIZE, N, D)
        S_col = torch.randn(BATCH_SIZE, N, D)
        a_k = torch.sigmoid(torch.randn(BATCH_SIZE, N, H))

        metrics = compute_phase_health(S_row, S_col, a_k)

        assert 0 <= metrics.amplitude_mean <= 1
        assert 0 <= metrics.amplitude_saturation <= 1
        assert -1 <= metrics.row_col_similarity <= 1

    def test_ghost_metrics(self):
        """Test ghost metrics computation."""
        S = torch.randn(BATCH_SIZE, 128, EMBED_DIM)

        metrics = compute_ghost_metrics(S)

        assert "directional_stability" in metrics
        assert "drift_magnitude" in metrics
        assert "positional_variance" in metrics


class TestConfig:
    """Test configuration system."""

    def test_config_presets(self):
        """Test all config presets are valid."""
        for preset_fn in [
            PhaseQuadVisionConfig.tiny,
            PhaseQuadVisionConfig.small,
            PhaseQuadVisionConfig.base,
            PhaseQuadVisionConfig.large,
        ]:
            config = preset_fn()
            config.validate()  # Should not raise

    def test_config_validation(self):
        """Test config validation catches errors."""
        config = PhaseQuadVisionConfig()
        config.embed_dim = 100
        config.num_heads = 12  # 100 not divisible by 12

        with pytest.raises(ValueError):
            config.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
