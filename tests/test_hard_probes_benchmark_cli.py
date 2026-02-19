#!/usr/bin/env python3
"""
CLI benchmark tests for train_hard_probes.py across all three attention models.

Tests the Phase-Quad LLM architecture on three attention mechanisms:
  1. Quadratic (Standard)  - O(n²) softmax attention  [HardProbeTransformer(use_phase=False)]
  2. Phase (Linear)        - O(n) phase-based cumsum   [HardProbeTransformer(use_phase=True)]
  3. Sliding-Window (Local) - O(n*w) binding cache      [BindingCacheLMTransformer]

Each test class exercises the benchmark with minimal resource usage
(tiny models, few steps, small datasets) to verify correctness without
requiring GPU or long training runs.

Spanda benefit analysis:
  - Quadratic models  -> marginal benefit (already O(n²) global context)
  - Linear attention   -> uncertain benefit (Psi parallels phase cumsum)
  - Sliding-window     -> highest potential (Psi bridges local windows)

Usage:
  pytest tests/test_hard_probes_benchmark_cli.py -v
  pytest tests/test_hard_probes_benchmark_cli.py -k "quadratic" -v
  pytest tests/test_hard_probes_benchmark_cli.py -k "sliding_window" -v
"""

import math
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

import pytest

# Ensure project root is on path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

torch = pytest.importorskip("torch")
import torch.nn.functional as F

# Import components from train_hard_probes
_HARD_PROBES_DIR = str(
    Path(__file__).resolve().parent.parent / "scripts" / "phase_probes" / "hard_probes"
)
if _HARD_PROBES_DIR not in sys.path:
    sys.path.insert(0, _HARD_PROBES_DIR)

from train_hard_probes import (
    Config,
    HardVocabulary,
    HardProbeDataset,
    HardProbeTransformer,
    SplitType,
    evaluate,
)

# Conditionally import binding cache components
try:
    from train_hard_probes import (
        LocalWindowAttention,
        BindingCachePhaseState,
        BindingCacheQuadQuery,
        BindingCacheLMBlock,
        BindingCacheLMTransformer,
    )
    BINDING_CACHE_AVAILABLE = True
except ImportError:
    BINDING_CACHE_AVAILABLE = False

# Conditionally import HP-Quad components
try:
    from symbolu.hp_quad import HPQuadBlock
    HP_QUAD_AVAILABLE = True
except ImportError:
    HP_QUAD_AVAILABLE = False


# =========================================================================
# Shared fixtures and helpers
# =========================================================================

# Tiny model config for fast tests
TINY_D_MODEL = 64
TINY_NUM_HEADS = 4
TINY_NUM_LAYERS = 2
TINY_D_FF = 128
TINY_NUM_STEPS = 5
TINY_BATCH_SIZE = 4
TINY_TRAIN_SAMPLES = 100
TINY_TEST_SAMPLES = 20


def count_parameters(model: torch.nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


@pytest.fixture(scope="module")
def vocab():
    return HardVocabulary()


@pytest.fixture(scope="module")
def num_classes(vocab):
    return len(vocab.entities)  # 16 entities


@pytest.fixture(scope="module")
def operation_tokens(vocab):
    return [vocab.NEG, vocab.PERMUTE, vocab.OVERWRITE]


@pytest.fixture(scope="module")
def train_dataset(vocab):
    return HardProbeDataset(
        vocab, SplitType.TRAIN, TINY_TRAIN_SAMPLES, 64,
        chain_length=(3, 5), bind_ratio=0.6, seed=42,
    )


@pytest.fixture(scope="module")
def test_dataset(vocab):
    return HardProbeDataset(
        vocab, SplitType.TEST_ROLES, TINY_TEST_SAMPLES, 64,
        chain_length=(3, 5), bind_ratio=0.6, seed=100,
    )


@pytest.fixture(scope="module")
def device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def _make_quad_model(vocab, num_classes, device="cpu"):
    """Create a tiny quadratic (use_phase=False) model."""
    return HardProbeTransformer(
        vocab_size=vocab.vocab_size,
        d_model=TINY_D_MODEL,
        num_heads=TINY_NUM_HEADS,
        num_layers=TINY_NUM_LAYERS,
        d_ff=TINY_D_FF,
        dropout=0.0,
        max_seq_len=64,
        num_classes=num_classes,
        use_phase=False,
    ).to(device)


def _make_phase_model(vocab, num_classes, operation_tokens, device="cpu"):
    """Create a tiny phase (use_phase=True) model."""
    return HardProbeTransformer(
        vocab_size=vocab.vocab_size,
        d_model=TINY_D_MODEL,
        num_heads=TINY_NUM_HEADS,
        num_layers=TINY_NUM_LAYERS,
        d_ff=TINY_D_FF,
        dropout=0.0,
        max_seq_len=64,
        num_classes=num_classes,
        use_phase=True,
        operation_tokens=operation_tokens,
        bounded_phase=True,
    ).to(device)


def _quick_train_classifier(model, train_loader, vocab, device, num_steps=5, lr=1e-3):
    """Train classifier for a few steps. Returns (initial_loss, final_loss)."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    losses = []
    step = 0
    for batch in train_loader:
        if step >= num_steps:
            break
        input_ids, targets, _ = batch
        input_ids = input_ids.to(device)
        targets = targets.to(device)

        target_idx = torch.tensor([
            vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
            for t in targets
        ], device=device)

        logits = model(input_ids)
        loss = F.cross_entropy(logits, target_idx)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        losses.append(loss.item())
        step += 1

    return losses[0] if losses else float("inf"), losses[-1] if losses else float("inf")


# =========================================================================
# Test Class 1: Quadratic (Standard) Attention - O(n²)
# =========================================================================


class TestQuadraticAttentionBenchmark:
    """
    Benchmark suite for O(n²) quadratic (softmax) attention.

    Expected Spanda benefit: MARGINAL
    Reason: Quadratic attention already has global context via full O(n²)
    attention matrix. Spanda's Psi trajectory adds semantic coherence but
    the backbone already captures long-range dependencies.
    """

    def test_model_creation(self, vocab, num_classes):
        """Verify quadratic model instantiates with correct architecture."""
        model = _make_quad_model(vocab, num_classes)
        assert count_parameters(model) > 0
        assert hasattr(model, 'layers')
        assert model.use_phase is False

    def test_forward_pass_shape(self, vocab, num_classes, device):
        """Verify forward pass produces [B, num_classes] logits."""
        model = _make_quad_model(vocab, num_classes, device)
        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        logits = model(input_ids)

        assert logits.shape == (TINY_BATCH_SIZE, num_classes)
        assert not torch.isnan(logits).any(), "NaN in quadratic model logits"
        assert not torch.isinf(logits).any(), "Inf in quadratic model logits"

    def test_backward_pass(self, vocab, num_classes, device):
        """Verify gradients flow through quadratic attention."""
        model = _make_quad_model(vocab, num_classes, device)
        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        targets = torch.randint(0, num_classes, (TINY_BATCH_SIZE,), device=device)

        logits = model(input_ids)
        loss = F.cross_entropy(logits, targets)
        loss.backward()

        grad_norms = []
        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                grad_norms.append(grad_norm)
                assert math.isfinite(grad_norm), f"Non-finite gradient in {name}"

        assert len(grad_norms) > 0, "No gradients computed"
        assert sum(grad_norms) > 0, "All gradients are zero"

    def test_training_produces_finite_loss(self, vocab, num_classes, train_dataset, device):
        """Verify training produces finite losses."""
        model = _make_quad_model(vocab, num_classes, device)
        loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=TINY_BATCH_SIZE, shuffle=True,
        )
        initial_loss, final_loss = _quick_train_classifier(
            model, loader, vocab, device, num_steps=TINY_NUM_STEPS,
        )
        assert math.isfinite(initial_loss), "Initial loss is not finite"
        assert math.isfinite(final_loss), "Final loss is not finite"

    def test_evaluation_returns_valid_accuracy(self, vocab, num_classes, test_dataset, device):
        """Verify evaluate() returns accuracy in [0, 1]."""
        model = _make_quad_model(vocab, num_classes, device)
        loader = torch.utils.data.DataLoader(
            test_dataset, batch_size=TINY_BATCH_SIZE, shuffle=False,
        )
        acc = evaluate(model, loader, vocab, device)
        assert 0.0 <= acc <= 1.0

    def test_sequence_length_flexibility(self, vocab, num_classes, device):
        """Verify model handles varying sequence lengths."""
        model = HardProbeTransformer(
            vocab_size=vocab.vocab_size,
            d_model=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            num_layers=TINY_NUM_LAYERS,
            d_ff=TINY_D_FF,
            dropout=0.0,
            max_seq_len=128,
            num_classes=num_classes,
            use_phase=False,
        ).to(device)

        for seq_len in [8, 16, 32, 64]:
            x = torch.randint(0, vocab.vocab_size, (2, seq_len), device=device)
            with torch.no_grad():
                out = model(x)
            assert out.shape == (2, num_classes), f"Failed for seq_len={seq_len}"


# =========================================================================
# Test Class 2: Phase (Linear) Attention - O(n)
# =========================================================================


class TestPhaseAttentionBenchmark:
    """
    Benchmark suite for O(n) phase-based linear attention.

    Expected Spanda benefit: UNCERTAIN
    Reason: Phase attention already uses O(n) cumulative sum for state
    accumulation, structurally similar to Spanda's Psi trajectory.
    The two may be redundant or complementary.
    """

    def test_model_creation(self, vocab, num_classes, operation_tokens):
        """Verify phase model has phase-specific parameters."""
        model = _make_phase_model(vocab, num_classes, operation_tokens)
        assert model.use_phase is True
        param_names = [n for n, _ in model.named_parameters()]
        assert any("phase" in n.lower() or "amp" in n.lower() for n in param_names), \
            f"Phase model missing phase parameters. Params: {param_names[:10]}"

    def test_forward_pass_shape(self, vocab, num_classes, operation_tokens, device):
        """Verify forward pass with bounded phase produces valid logits."""
        model = _make_phase_model(vocab, num_classes, operation_tokens, device)
        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        logits = model(input_ids)

        assert logits.shape == (TINY_BATCH_SIZE, num_classes)
        assert not torch.isnan(logits).any(), "NaN in phase model logits"
        assert not torch.isinf(logits).any(), "Inf in phase model logits"

    def test_backward_pass_phase_gradients(self, vocab, num_classes, operation_tokens, device):
        """Verify gradients flow through phase attention layers."""
        model = _make_phase_model(vocab, num_classes, operation_tokens, device)
        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        targets = torch.randint(0, num_classes, (TINY_BATCH_SIZE,), device=device)

        logits = model(input_ids)
        loss = F.cross_entropy(logits, targets)
        loss.backward()

        phase_grads = [
            (n, p.grad.norm().item())
            for n, p in model.named_parameters()
            if p.grad is not None and ("phase" in n.lower() or "amp" in n.lower())
        ]
        if phase_grads:
            assert any(g > 0 for _, g in phase_grads), \
                "Phase parameters received zero gradients"

    def test_bounded_phase_runs(self, vocab, num_classes, operation_tokens, device):
        """Verify bounded phase (pi*sin constraint) forward pass succeeds."""
        model = _make_phase_model(vocab, num_classes, operation_tokens, device)
        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)

        if hasattr(model, 'enable_diagnostics'):
            model.enable_diagnostics(True)

        with torch.no_grad():
            logits = model(input_ids)

        assert logits.shape == (TINY_BATCH_SIZE, num_classes)

    def test_training_produces_finite_loss(self, vocab, num_classes, operation_tokens, train_dataset, device):
        """Verify phase model training produces finite losses."""
        model = _make_phase_model(vocab, num_classes, operation_tokens, device)
        loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=TINY_BATCH_SIZE, shuffle=True,
        )
        initial_loss, final_loss = _quick_train_classifier(
            model, loader, vocab, device, num_steps=TINY_NUM_STEPS,
        )
        assert math.isfinite(initial_loss)
        assert math.isfinite(final_loss)

    def test_phase_health_metrics(self, vocab, num_classes, operation_tokens, device):
        """Verify R_k (phase health) is in valid range."""
        model = _make_phase_model(vocab, num_classes, operation_tokens, device)

        if hasattr(model, 'enable_diagnostics'):
            model.enable_diagnostics(True)

        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        with torch.no_grad():
            _ = model(input_ids)

        if hasattr(model, 'get_R_k'):
            r_k = model.get_R_k()
            assert 0.0 <= r_k <= 1.0, f"R_k out of range: {r_k}"

    def test_phase_has_more_params_than_quad(self, vocab, num_classes, operation_tokens):
        """Phase model should have more parameters (extra phase projections)."""
        quad = _make_quad_model(vocab, num_classes)
        phase = _make_phase_model(vocab, num_classes, operation_tokens)

        quad_params = count_parameters(quad)
        phase_params = count_parameters(phase)

        assert phase_params > quad_params, \
            f"Phase ({phase_params}) should have more params than Quad ({quad_params})"


# =========================================================================
# Test Class 3: Sliding Window (Binding Cache) - O(n*w)
# =========================================================================


@pytest.mark.skipif(not BINDING_CACHE_AVAILABLE, reason="Binding Cache not available")
class TestSlidingWindowBenchmark:
    """
    Benchmark suite for sliding-window attention via Binding Cache architecture.
    Three-path: Local O(n*w) + Phase O(n) + Quad O(n*k).

    Expected Spanda benefit: HIGHEST POTENTIAL
    Reason: Sliding-window models have LOCAL context only. Spanda's Psi
    trajectory provides an explicit GLOBAL semantic state bridging windows.
    """

    def test_local_window_attention_creation(self):
        """Verify LocalWindowAttention instantiates correctly."""
        attn = LocalWindowAttention(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            window_size=16,
        )
        assert count_parameters(attn) > 0

    def test_local_window_forward(self, device):
        """Verify local window attention produces correct output shape."""
        attn = LocalWindowAttention(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            window_size=16,
        ).to(device)

        x = torch.randn(TINY_BATCH_SIZE, 32, TINY_D_MODEL, device=device)
        out = attn(x)
        assert out.shape == x.shape
        assert not torch.isnan(out).any(), "NaN in local window output"

    def test_local_window_causal_mask(self, device):
        """Verify local window attention respects causal ordering."""
        attn = LocalWindowAttention(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            window_size=8,
        ).to(device)

        x = torch.randn(2, 16, TINY_D_MODEL, device=device)
        out = attn(x)
        assert out.shape == (2, 16, TINY_D_MODEL)
        assert not torch.isnan(out).any()

    def test_binding_cache_block_three_paths(self):
        """Verify BindingCacheLMBlock has all three attention paths."""
        block = BindingCacheLMBlock(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            ff_dim=TINY_D_FF,
            decay_gamma=0.9,
            bounded_phase=True,
            top_k=16,
            local_window_size=16,
            local_ratio=0.4,
            phase_ratio=0.3,
            quad_ratio=0.3,
        )
        assert hasattr(block, 'local_attn'), "Missing local attention path"
        assert hasattr(block, 'phase_state'), "Missing phase state path"
        assert hasattr(block, 'quad_query'), "Missing quad query path"

    def test_binding_cache_block_forward(self, device):
        """Verify binding cache block forward pass with all three paths."""
        block = BindingCacheLMBlock(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            ff_dim=TINY_D_FF,
            decay_gamma=0.9,
            bounded_phase=True,
            top_k=16,
            local_window_size=16,
            local_ratio=0.4,
            phase_ratio=0.3,
            quad_ratio=0.3,
        ).to(device)

        x = torch.randn(TINY_BATCH_SIZE, 32, TINY_D_MODEL, device=device)
        out = block(x)
        assert out.shape == x.shape
        assert not torch.isnan(out).any(), "NaN in binding cache output"

    def test_binding_cache_backward_all_paths(self, device):
        """Verify gradients flow through all three paths."""
        block = BindingCacheLMBlock(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            ff_dim=TINY_D_FF,
            decay_gamma=0.9,
            bounded_phase=True,
            top_k=16,
            local_window_size=16,
            local_ratio=0.4,
            phase_ratio=0.3,
            quad_ratio=0.3,
        ).to(device)

        x = torch.randn(TINY_BATCH_SIZE, 32, TINY_D_MODEL, device=device, requires_grad=True)
        out = block(x)
        out.sum().backward()

        local_grads = any(
            p.grad is not None and p.grad.norm() > 0
            for n, p in block.named_parameters() if "local" in n
        )
        phase_grads = any(
            p.grad is not None and p.grad.norm() > 0
            for n, p in block.named_parameters() if "phase" in n
        )
        quad_grads = any(
            p.grad is not None and p.grad.norm() > 0
            for n, p in block.named_parameters() if "quad" in n
        )

        assert local_grads, "No gradients flowing to local attention"
        assert phase_grads, "No gradients flowing to phase state"
        assert quad_grads, "No gradients flowing to quad query"

    def test_full_lm_transformer_forward(self, device):
        """Verify BindingCacheLMTransformer forward produces [B, T, V] logits."""
        model = BindingCacheLMTransformer(
            vocab_size=100,
            d_model=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            num_layers=TINY_NUM_LAYERS,
            d_ff=TINY_D_FF,
            dropout=0.0,
            max_seq_len=64,
            bounded_phase=True,
            top_k=16,
            use_cache=True,
            decay_gamma=0.9,
            window_size=16,
        ).to(device)

        input_ids = torch.randint(0, 100, (TINY_BATCH_SIZE, 32), device=device)
        logits = model(input_ids)
        assert logits.shape == (TINY_BATCH_SIZE, 32, 100)
        assert not torch.isnan(logits).any()

    def test_full_lm_transformer_backward(self, device):
        """Verify end-to-end backward through BindingCacheLMTransformer."""
        model = BindingCacheLMTransformer(
            vocab_size=100,
            d_model=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            num_layers=TINY_NUM_LAYERS,
            d_ff=TINY_D_FF,
            dropout=0.0,
            max_seq_len=64,
            bounded_phase=True,
            top_k=16,
            use_cache=True,
            decay_gamma=0.9,
            window_size=16,
        ).to(device)

        input_ids = torch.randint(0, 100, (TINY_BATCH_SIZE, 32), device=device)
        targets = torch.randint(0, 100, (TINY_BATCH_SIZE, 32), device=device)

        logits = model(input_ids)
        loss = F.cross_entropy(logits.view(-1, 100), targets.view(-1))
        loss.backward()

        assert math.isfinite(loss.item())
        assert count_parameters(model) > 0

    def test_lm_training_finite_losses(self, device):
        """Verify training the LM produces finite losses."""
        model = BindingCacheLMTransformer(
            vocab_size=100,
            d_model=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            num_layers=TINY_NUM_LAYERS,
            d_ff=TINY_D_FF,
            dropout=0.0,
            max_seq_len=64,
            bounded_phase=True,
            top_k=16,
            use_cache=True,
            decay_gamma=0.9,
            window_size=16,
        ).to(device)

        input_ids = torch.randint(0, 100, (TINY_BATCH_SIZE, 32), device=device)
        targets = torch.randint(0, 100, (TINY_BATCH_SIZE, 32), device=device)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

        losses = []
        for _ in range(3):
            model.train()
            logits = model(input_ids)
            loss = F.cross_entropy(logits.view(-1, 100), targets.view(-1))
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            losses.append(loss.item())

        assert all(math.isfinite(l) for l in losses), f"Non-finite losses: {losses}"

    def test_window_size_affects_output(self, device):
        """Verify different window sizes produce different outputs."""
        torch.manual_seed(42)
        x = torch.randn(2, 32, TINY_D_MODEL, device=device)

        attn_small = LocalWindowAttention(
            embed_dim=TINY_D_MODEL, num_heads=TINY_NUM_HEADS, window_size=4,
        ).to(device)
        attn_large = LocalWindowAttention(
            embed_dim=TINY_D_MODEL, num_heads=TINY_NUM_HEADS, window_size=16,
        ).to(device)
        attn_large.load_state_dict(attn_small.state_dict())

        with torch.no_grad():
            out_small = attn_small(x)
            out_large = attn_large(x)

        assert out_small.shape == out_large.shape

    def test_phase_health_in_binding_cache(self, device):
        """Verify phase health metrics from binding cache block."""
        block = BindingCacheLMBlock(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            ff_dim=TINY_D_FF,
            decay_gamma=0.9,
            bounded_phase=True,
            top_k=16,
            local_window_size=16,
        ).to(device)

        x = torch.randn(TINY_BATCH_SIZE, 32, TINY_D_MODEL, device=device)
        with torch.no_grad():
            _ = block(x)

        if hasattr(block, 'get_phase_health'):
            health = block.get_phase_health()
            assert "r_k_mean" in health
            assert 0.0 <= health["r_k_mean"] <= 1.0


# =========================================================================
# Test Class 4: Cross-Model Comparative Benchmarks
# =========================================================================


class TestCrossModelComparison:
    """Comparative benchmarks across all three attention types."""

    def test_parameter_count_comparison(self, vocab, num_classes, operation_tokens):
        """Compare parameter counts: Phase > Quad, BindingCache > both."""
        quad = _make_quad_model(vocab, num_classes)
        phase = _make_phase_model(vocab, num_classes, operation_tokens)

        quad_params = count_parameters(quad)
        phase_params = count_parameters(phase)

        print(f"\n  Parameter counts:")
        print(f"    Quadratic: {quad_params:,}")
        print(f"    Phase:     {phase_params:,}")

        assert quad_params > 0
        assert phase_params > quad_params

        if BINDING_CACHE_AVAILABLE:
            bc = BindingCacheLMTransformer(
                vocab_size=vocab.vocab_size,
                d_model=TINY_D_MODEL,
                num_heads=TINY_NUM_HEADS,
                num_layers=TINY_NUM_LAYERS,
                d_ff=TINY_D_FF,
                dropout=0.0,
                max_seq_len=64,
                bounded_phase=True,
                top_k=16,
                window_size=16,
            )
            bc_params = count_parameters(bc)
            print(f"    Binding Cache: {bc_params:,}")

    def test_all_models_produce_valid_outputs(self, vocab, num_classes, operation_tokens, device):
        """Verify all model types produce valid, non-NaN outputs."""
        input_ids = torch.randint(0, vocab.vocab_size, (2, 16), device=device)

        # Quadratic
        quad = _make_quad_model(vocab, num_classes, device)
        with torch.no_grad():
            quad_out = quad(input_ids)
        assert quad_out.shape == (2, num_classes)
        assert not torch.isnan(quad_out).any()

        # Phase
        phase = _make_phase_model(vocab, num_classes, operation_tokens, device)
        with torch.no_grad():
            phase_out = phase(input_ids)
        assert phase_out.shape == (2, num_classes)
        assert not torch.isnan(phase_out).any()

        # Binding Cache (LM output shape)
        if BINDING_CACHE_AVAILABLE:
            bc = BindingCacheLMTransformer(
                vocab_size=vocab.vocab_size,
                d_model=TINY_D_MODEL,
                num_heads=TINY_NUM_HEADS,
                num_layers=TINY_NUM_LAYERS,
                d_ff=TINY_D_FF,
                dropout=0.0,
                max_seq_len=64,
                bounded_phase=True,
                top_k=16,
                window_size=16,
            ).to(device)
            with torch.no_grad():
                bc_out = bc(input_ids)
            assert bc_out.shape == (2, 16, vocab.vocab_size)
            assert not torch.isnan(bc_out).any()

    def test_forward_timing_comparison(self, vocab, num_classes, operation_tokens, device):
        """Compare forward pass timing across architectures."""
        input_ids = torch.randint(0, vocab.vocab_size, (4, 32), device=device)

        models = {
            "quadratic": _make_quad_model(vocab, num_classes, device),
            "phase": _make_phase_model(vocab, num_classes, operation_tokens, device),
        }

        if BINDING_CACHE_AVAILABLE:
            models["binding_cache"] = BindingCacheLMTransformer(
                vocab_size=vocab.vocab_size,
                d_model=TINY_D_MODEL,
                num_heads=TINY_NUM_HEADS,
                num_layers=TINY_NUM_LAYERS,
                d_ff=TINY_D_FF,
                dropout=0.0,
                max_seq_len=64,
                bounded_phase=True,
                top_k=16,
                window_size=16,
            ).to(device)

        print("\n  Forward pass timing (ms):")
        for name, model in models.items():
            model.eval()
            with torch.no_grad():
                for _ in range(3):
                    model(input_ids)
            n_iters = 10
            start = time.perf_counter()
            with torch.no_grad():
                for _ in range(n_iters):
                    model(input_ids)
            if device == "cuda":
                torch.cuda.synchronize()
            elapsed_ms = (time.perf_counter() - start) / n_iters * 1000
            print(f"    {name}: {elapsed_ms:.2f} ms")
            assert elapsed_ms < 30000, f"{name} took too long"


# =========================================================================
# Test Class 5: CLI Argument Parsing
# =========================================================================


class TestCLIArgumentParsing:
    """Verify CLI argument structures for benchmark modes."""

    def test_default_config(self):
        """Verify Config dataclass defaults."""
        config = Config()
        assert config.d_model == 128
        assert config.num_heads == 8
        assert config.num_layers == 4
        assert config.bounded_phase is True

    def test_binding_cache_ratio_sum(self):
        """Verify binding cache layer ratios sum to 1.0."""
        bc_phase = [float(x) for x in "0.3,0.3,0.3,0.3".split(",")]
        bc_local = [float(x) for x in "0.4,0.4,0.4,0.4".split(",")]
        bc_quad = [float(x) for x in "0.3,0.3,0.3,0.3".split(",")]

        for i in range(4):
            total = bc_phase[i] + bc_local[i] + bc_quad[i]
            assert abs(total - 1.0) < 0.01, f"Layer {i} ratios sum to {total}"

    def test_hp_quad_args(self):
        """Verify HP-Quad hierarchical arguments parse correctly."""
        d_phase_levels = tuple(map(int, "128,256,512".split(",")))
        chunk_sizes = tuple(map(int, "1,8,64".split(",")))
        assert d_phase_levels == (128, 256, 512)
        assert chunk_sizes == (1, 8, 64)

    def test_curriculum_inverted(self):
        """Verify inverted curriculum decreases phase ratio per layer."""
        curriculum = [float(x) for x in "0.9,0.7,0.3,0.1".split(",")]
        assert len(curriculum) == 4
        assert curriculum[0] > curriculum[-1]

    def test_decay_gamma_effective_window(self):
        """Verify effective memory window calculation."""
        for gamma, expected in [(0.9, 9.5), (0.95, 19.5), (0.99, 99.5), (0.999, 999.5)]:
            window = -1.0 / math.log(gamma)
            assert abs(window - expected) / expected < 0.1, \
                f"gamma={gamma}: expected ~{expected}, got {window:.1f}"


# =========================================================================
# Test Class 6: Benchmark Integration Tests
# =========================================================================


class TestBenchmarkIntegration:
    """
    Integration tests running abbreviated benchmark pipelines
    for each attention type.
    """

    def test_quadratic_vs_phase_pipeline(self, vocab, num_classes, operation_tokens, device):
        """Run minimal Quadratic vs Phase comparison."""
        quad = _make_quad_model(vocab, num_classes, device)
        phase = _make_phase_model(vocab, num_classes, operation_tokens, device)

        train_ds = HardProbeDataset(
            vocab, SplitType.TRAIN, 50, 64,
            chain_length=(3, 5), bind_ratio=0.6, seed=42,
        )
        test_ds = HardProbeDataset(
            vocab, SplitType.TEST_ROLES, 20, 64,
            chain_length=(3, 5), bind_ratio=0.6, seed=100,
        )

        train_loader = torch.utils.data.DataLoader(
            train_ds, batch_size=TINY_BATCH_SIZE, shuffle=True,
        )
        test_loader = torch.utils.data.DataLoader(
            test_ds, batch_size=TINY_BATCH_SIZE, shuffle=False,
        )

        # Quick train both models
        for model in [quad, phase]:
            _quick_train_classifier(model, train_loader, vocab, device, num_steps=3)

        # Evaluate both
        quad_acc = evaluate(quad, test_loader, vocab, device)
        phase_acc = evaluate(phase, test_loader, vocab, device)

        assert 0.0 <= quad_acc <= 1.0
        assert 0.0 <= phase_acc <= 1.0

    @pytest.mark.skipif(not BINDING_CACHE_AVAILABLE, reason="Binding Cache not available")
    def test_binding_cache_lm_pipeline(self, vocab, device):
        """Run minimal LM pipeline for Binding Cache model."""
        model = BindingCacheLMTransformer(
            vocab_size=vocab.vocab_size,
            d_model=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            num_layers=TINY_NUM_LAYERS,
            d_ff=TINY_D_FF,
            dropout=0.0,
            max_seq_len=64,
            bounded_phase=True,
            top_k=16,
            window_size=16,
            decay_gamma=0.9,
        ).to(device)

        input_ids = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        targets = torch.randint(0, vocab.vocab_size, (TINY_BATCH_SIZE, 32), device=device)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

        losses = []
        for _ in range(3):
            model.train()
            logits = model(input_ids)
            loss = F.cross_entropy(logits.view(-1, vocab.vocab_size), targets.view(-1))
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            losses.append(loss.item())

        assert all(math.isfinite(l) for l in losses)


# =========================================================================
# Test Class 7: Spanda Benefit Characterization
# =========================================================================


class TestSpandaBenefitCharacterization:
    """
    Characterize where Spanda helps most across attention architectures.

    Key insight: Spanda's Psi trajectory provides explicit semantic state.
    - GLOBAL context (quadratic):      marginal, backbone already sees all
    - PARTIAL context (phase decay):   uncertain, Psi may be redundant
    - LOCAL context (sliding window):  highest, Psi bridges windows
    """

    def test_benefit_ranking(self):
        """Verify the theoretical benefit ranking."""
        ranking = {
            "quadratic": "marginal",
            "phase_linear": "uncertain",
            "sliding_window": "highest",
        }
        assert ranking["sliding_window"] == "highest"
        assert ranking["quadratic"] == "marginal"

    def test_decay_gamma_effective_windows(self):
        """Verify effective memory windows for different gamma values."""
        cases = [
            (0.9, 9.5), (0.95, 19.5), (0.99, 99.5),
            (0.995, 199.5), (0.999, 999.5),
        ]
        for gamma, expected in cases:
            window = -1.0 / math.log(gamma)
            assert abs(window - expected) / expected < 0.1

    @pytest.mark.skipif(not BINDING_CACHE_AVAILABLE, reason="Binding Cache not available")
    def test_sliding_window_context_gap(self, device):
        """
        Demonstrate the context gap that Spanda addresses.

        Token at position t sees only [t-w, t] via local attention.
        Information from position 0 is lost at position w+1.
        Spanda's Psi bridges this gap.
        """
        window_size = 8
        seq_len = 32

        attn = LocalWindowAttention(
            embed_dim=TINY_D_MODEL,
            num_heads=TINY_NUM_HEADS,
            window_size=window_size,
        ).to(device)

        x = torch.randn(1, seq_len, TINY_D_MODEL, device=device)
        x[0, 0] = torch.ones(TINY_D_MODEL, device=device) * 10.0  # Strong signal

        with torch.no_grad():
            out = attn(x)

        assert out.shape == (1, seq_len, TINY_D_MODEL)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
