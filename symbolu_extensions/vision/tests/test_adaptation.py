"""
Tests for Phase-Aware Adaptation: IA³ gates + surgical LoRA.

Run with: pytest symbolu/vision/tests/test_adaptation.py -v
"""

import pytest
import torch
import torch.nn as nn

from symbolu_extensions.vision.adaptation import (
    IA3Gate,
    IA3BlockGates,
    IA3Config,
    LoRALinear,
    LoRAConfig,
    AdaptationConfig,
    PhaseQuadAdaptationManager,
)
from symbolu_extensions.vision.controls import PatchMeta, BlockControl
from symbolu_extensions.vision.phase_quad_dit_block import PhaseQuadDiTBlockStack


# Test constants
BATCH_SIZE = 2
EMBED_DIM = 256
NUM_HEADS = 8
TOPK = 16
WINDOW_SIZE = 4
FFN_RATIO = 4.0
NUM_BLOCKS = 3
PATCH_SIZE = 2
H_P = 8
W_P = 8
N_PATCHES = H_P * W_P
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def _make_meta(device: str = DEVICE) -> PatchMeta:
    """Create test PatchMeta."""
    coords = torch.stack(
        torch.meshgrid(
            torch.arange(H_P), torch.arange(W_P), indexing="ij"
        ),
        dim=-1,
    ).reshape(-1, 2).to(device)
    return PatchMeta(H_p=H_P, W_p=W_P, coords=coords, patch_size=PATCH_SIZE)


def _make_block_stack(device: str = DEVICE) -> PhaseQuadDiTBlockStack:
    """Create test block stack."""
    stack = PhaseQuadDiTBlockStack(
        num_blocks=NUM_BLOCKS,
        embed_dim=EMBED_DIM,
        num_heads=NUM_HEADS,
        topk=TOPK,
        window_size=WINDOW_SIZE,
        ffn_ratio=FFN_RATIO,
        use_cross_attn=False,
        use_bcvf=False,
    ).to(device)
    return stack


# ===========================================================================
# IA³ Gate Tests
# ===========================================================================


class TestIA3Gate:
    """Tests for the basic IA³ gate vector."""

    def test_identity_init(self):
        """Gate initialized to 1.0 should act as identity."""
        gate = IA3Gate(dim=64, init_value=1.0)
        x = torch.randn(2, 10, 64)
        y = gate(x)
        torch.testing.assert_close(y, x)

    def test_scaling(self):
        """Gate should scale activations element-wise."""
        gate = IA3Gate(dim=4, init_value=1.0)
        gate.gate.data = torch.tensor([2.0, 0.5, 1.0, 0.0])
        x = torch.ones(1, 1, 4)
        y = gate(x)
        expected = torch.tensor([[[2.0, 0.5, 1.0, 0.0]]])
        torch.testing.assert_close(y, expected)

    def test_gradient_flow(self):
        """Gate parameters should receive gradients."""
        gate = IA3Gate(dim=32, init_value=1.0)
        x = torch.randn(2, 5, 32, requires_grad=True)
        y = gate(x)
        loss = y.sum()
        loss.backward()
        assert gate.gate.grad is not None
        assert gate.gate.grad.shape == (32,)

    def test_shape_preservation(self):
        """Gate should preserve input shape."""
        gate = IA3Gate(dim=64)
        for shape in [(2, 10, 64), (1, 100, 64), (4, 1, 64)]:
            x = torch.randn(*shape)
            y = gate(x)
            assert y.shape == x.shape


class TestIA3BlockGates:
    """Tests for per-block IA³ gates."""

    def test_all_gates_enabled(self):
        """All three gates should be created."""
        config = IA3Config(gate_attention=True, gate_mlp=True, gate_quad=True)
        gates = IA3BlockGates(embed_dim=64, ffn_dim=256, config=config)
        assert gates.gate_local_attn is not None
        assert gates.gate_quad_attn is not None
        assert gates.gate_ffn is not None

    def test_selective_gates(self):
        """Only enabled gates should be created."""
        config = IA3Config(gate_attention=True, gate_mlp=False, gate_quad=False)
        gates = IA3BlockGates(embed_dim=64, ffn_dim=256, config=config)
        assert gates.gate_local_attn is not None
        assert gates.gate_quad_attn is None
        assert gates.gate_ffn is None

    def test_identity_at_init(self):
        """All gates should be identity (1.0) at initialization."""
        config = IA3Config(init_value=1.0)
        gates = IA3BlockGates(embed_dim=32, ffn_dim=128, config=config)

        x_attn = torch.randn(2, 10, 32)
        x_ffn = torch.randn(2, 10, 128)

        torch.testing.assert_close(gates.scale_local_attn(x_attn), x_attn)
        torch.testing.assert_close(gates.scale_quad_attn(x_attn), x_attn)
        torch.testing.assert_close(gates.scale_ffn_hidden(x_ffn), x_ffn)

    def test_regularization_loss(self):
        """Regularization should be zero at init (gates = 1.0)."""
        config = IA3Config(init_value=1.0)
        gates = IA3BlockGates(embed_dim=32, ffn_dim=128, config=config)
        loss = gates.regularization_loss()
        assert loss.item() == pytest.approx(0.0, abs=1e-6)

    def test_regularization_nonzero_after_update(self):
        """Regularization should be nonzero after gates move away from 1.0."""
        config = IA3Config(init_value=1.0)
        gates = IA3BlockGates(embed_dim=32, ffn_dim=128, config=config)

        # Manually shift a gate away from 1.0
        gates.gate_local_attn.gate.data.fill_(2.0)
        loss = gates.regularization_loss()
        assert loss.item() > 0.0

    def test_parameter_count(self):
        """Parameter count should match expected dimensions."""
        config = IA3Config(gate_attention=True, gate_mlp=True, gate_quad=True)
        gates = IA3BlockGates(embed_dim=64, ffn_dim=256, config=config)
        total = sum(p.numel() for p in gates.parameters())
        # local_attn(64) + quad_attn(64) + ffn(256)
        assert total == 64 + 64 + 256


# ===========================================================================
# LoRA Tests
# ===========================================================================


class TestLoRALinear:
    """Tests for LoRA-adapted linear layer."""

    def test_zero_init_output(self):
        """LoRA should produce zero delta at initialization (B=0)."""
        base = nn.Linear(64, 128)
        lora = LoRALinear(base, rank=8, alpha=16.0)

        x = torch.randn(2, 10, 64)
        base_out = base(x)
        lora_out = lora(x)

        # Should be identical since B is zero-initialized
        torch.testing.assert_close(lora_out, base_out, atol=1e-5, rtol=1e-5)

    def test_base_frozen(self):
        """Base weights should be frozen after LoRA wrapping."""
        base = nn.Linear(64, 128)
        lora = LoRALinear(base, rank=8)

        assert not lora.base_linear.weight.requires_grad
        if lora.base_linear.bias is not None:
            assert not lora.base_linear.bias.requires_grad

    def test_lora_trainable(self):
        """LoRA A and B should be trainable."""
        base = nn.Linear(64, 128)
        lora = LoRALinear(base, rank=8)

        assert lora.lora_A.requires_grad
        assert lora.lora_B.requires_grad

    def test_gradient_flow(self):
        """Gradients should flow through LoRA path."""
        base = nn.Linear(32, 64)
        lora = LoRALinear(base, rank=4)

        x = torch.randn(2, 5, 32)
        y = lora(x)
        loss = y.sum()
        loss.backward()

        assert lora.lora_A.grad is not None
        assert lora.lora_B.grad is not None

    def test_merge_unmerge(self):
        """Merge and unmerge should be reversible."""
        base = nn.Linear(32, 64, bias=False)
        lora = LoRALinear(base, rank=4, alpha=8.0)

        # Set some non-zero LoRA weights
        nn.init.normal_(lora.lora_B, std=0.1)

        x = torch.randn(2, 5, 32)
        out_before = lora(x).detach().clone()

        # Save original base weights
        original_weight = base.weight.data.clone()

        # Merge
        lora.merge_weights()
        assert lora._merged is True

        # After merge, calling lora(x) should give same result (skips LoRA path)
        out_merged_via_lora = lora(x).detach().clone()
        torch.testing.assert_close(out_merged_via_lora, out_before, atol=1e-4, rtol=1e-4)

        # Also verify base(x) directly matches
        out_merged = base(x)
        torch.testing.assert_close(out_merged, out_before, atol=1e-4, rtol=1e-4)

        # Double merge should be idempotent
        lora.merge_weights()
        out_double = lora(x).detach().clone()
        torch.testing.assert_close(out_double, out_before, atol=1e-4, rtol=1e-4)

        # Unmerge
        lora.unmerge_weights()
        assert lora._merged is False
        torch.testing.assert_close(
            base.weight.data, original_weight, atol=1e-5, rtol=1e-5
        )

        # After unmerge, lora(x) should still give same result
        out_unmerged = lora(x).detach().clone()
        torch.testing.assert_close(out_unmerged, out_before, atol=1e-4, rtol=1e-4)

    def test_param_count(self):
        """LoRA parameter count should be rank * (in + out)."""
        base = nn.Linear(64, 128)
        lora = LoRALinear(base, rank=8)
        assert lora.num_trainable_params == 8 * (64 + 128)

    def test_output_shape(self):
        """Output shape should match base linear."""
        base = nn.Linear(64, 128)
        lora = LoRALinear(base, rank=8)

        x = torch.randn(2, 10, 64)
        y = lora(x)
        assert y.shape == (2, 10, 128)


# ===========================================================================
# Adaptation Manager Tests
# ===========================================================================


class TestPhaseQuadAdaptationManager:
    """Tests for the full adaptation manager."""

    def test_ia3_only(self):
        """IA³-only adaptation should work end-to-end."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=False),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        meta = _make_meta("cpu")
        x = torch.randn(BATCH_SIZE, N_PATCHES, EMBED_DIM)
        t_emb = torch.randn(BATCH_SIZE, EMBED_DIM)
        timestep = torch.randint(0, 1000, (BATCH_SIZE,))

        out = adapter(x, meta, t_emb, timestep=timestep)
        assert out.shape == (BATCH_SIZE, N_PATCHES, EMBED_DIM)

    def test_ia3_plus_lora(self):
        """Combined IA³ + LoRA should work end-to-end."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=True, rank=4, alpha=8.0),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        meta = _make_meta("cpu")
        x = torch.randn(BATCH_SIZE, N_PATCHES, EMBED_DIM)
        t_emb = torch.randn(BATCH_SIZE, EMBED_DIM)
        timestep = torch.randint(0, 1000, (BATCH_SIZE,))

        out = adapter(x, meta, t_emb, timestep=timestep)
        assert out.shape == (BATCH_SIZE, N_PATCHES, EMBED_DIM)

    def test_base_frozen(self):
        """Base model parameters should be frozen."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        # All base params should be frozen
        for name, param in stack.named_parameters():
            if not param.requires_grad:
                continue
            # Only IA³ gate params should still have grad
            assert "gate" in name or "lora" in name, (
                f"Base param {name} should be frozen"
            )

    def test_trainable_param_count(self):
        """Trainable params should be much smaller than base."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        summary = adapter.get_adaptation_summary()
        assert summary["ia3_params"] > 0
        assert summary["adaptation_ratio"] < 0.01  # Less than 1%

    def test_regularization_loss_zero_at_init(self):
        """Regularization loss should be ~0 at initialization."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(ia3=IA3Config(enable=True))
        adapter = PhaseQuadAdaptationManager(stack, config)

        reg_loss = adapter.regularization_loss()
        assert reg_loss.item() == pytest.approx(0.0, abs=1e-5)

    def test_save_load_adapter(self, tmp_path):
        """Adapter save/load should preserve weights."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(ia3=IA3Config(enable=True))
        adapter = PhaseQuadAdaptationManager(stack, config)

        # Modify gates
        for gates in adapter.ia3_gates:
            if gates is not None and gates.gate_local_attn is not None:
                gates.gate_local_attn.gate.data.fill_(0.5)

        # Save
        save_path = str(tmp_path / "adapter.pt")
        adapter.save_adapter(save_path)

        # Create fresh adapter and load
        stack2 = _make_block_stack("cpu")
        adapter2 = PhaseQuadAdaptationManager(stack2, config)
        adapter2.load_adapter(save_path)

        # Check weights match
        for g1, g2 in zip(adapter.ia3_gates, adapter2.ia3_gates):
            if g1 is not None and g2 is not None:
                if g1.gate_local_attn is not None:
                    torch.testing.assert_close(
                        g1.gate_local_attn.gate.data,
                        g2.gate_local_attn.gate.data,
                    )

    def test_output_matches_base_at_init(self):
        """Adapted model should produce same output as base at init.

        Since IA³ gates start at 1.0 and LoRA starts at 0, the adapted
        forward should be identical to the original forward.
        """
        torch.manual_seed(42)
        stack = _make_block_stack("cpu")

        meta = _make_meta("cpu")
        x = torch.randn(BATCH_SIZE, N_PATCHES, EMBED_DIM)
        t_emb = torch.randn(BATCH_SIZE, EMBED_DIM)
        timestep = torch.randint(0, 1000, (BATCH_SIZE,))

        # Base output
        with torch.no_grad():
            base_out = stack(x, meta, t_emb, timestep=timestep)

        # Adapted output (should be identical at init)
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=False),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        with torch.no_grad():
            adapted_out = adapter(x, meta, t_emb, timestep=timestep)

        torch.testing.assert_close(adapted_out, base_out, atol=1e-4, rtol=1e-4)

    def test_lora_module_placement(self):
        """LoRA should only be applied to QuadRetriever projections."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(
            ia3=IA3Config(enable=False),
            lora=LoRAConfig(enable=True, rank=4, target_modules=["W_q", "W_k", "W_v"]),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        # Check that LoRA was applied to quad retrievers
        for block in stack.blocks:
            assert isinstance(block.quad.W_q, LoRALinear)
            assert isinstance(block.quad.W_k, LoRALinear)
            assert isinstance(block.quad.W_v, LoRALinear)

        # Total LoRA modules = 3 projections * NUM_BLOCKS
        assert len(adapter._lora_modules) == 3 * NUM_BLOCKS

    def test_adaptation_summary(self):
        """Summary should report correct counts."""
        stack = _make_block_stack("cpu")
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=True, rank=4),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config)

        summary = adapter.get_adaptation_summary()
        assert summary["num_blocks"] == NUM_BLOCKS
        assert summary["num_lora_modules"] == 3 * NUM_BLOCKS
        assert summary["ia3_params"] > 0
        assert summary["lora_params"] > 0
        assert summary["total_trainable"] == summary["ia3_params"] + summary["lora_params"]

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_gpu_forward(self):
        """Adaptation should work on GPU."""
        stack = _make_block_stack("cuda")
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=True, rank=4),
            freeze_base=True,
        )
        adapter = PhaseQuadAdaptationManager(stack, config).cuda()

        meta = _make_meta("cuda")
        x = torch.randn(BATCH_SIZE, N_PATCHES, EMBED_DIM, device="cuda")
        t_emb = torch.randn(BATCH_SIZE, EMBED_DIM, device="cuda")
        timestep = torch.randint(0, 1000, (BATCH_SIZE,), device="cuda")

        out = adapter(x, meta, t_emb, timestep=timestep)
        assert out.shape == (BATCH_SIZE, N_PATCHES, EMBED_DIM)
        assert out.device.type == "cuda"
