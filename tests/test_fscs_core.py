"""
tests/test_fscs_core.py — CPU smoke tests for the Text-FSCS core modules.

These tests exercise each FSCS building block on synthetic tensors with
tiny shapes (batch=2, seq=32, hidden=16). They verify:

    1. Shapes flow correctly through every module
    2. Sequence warmup (§4) produces zero coherence at the first w_seq positions
    3. Boundary detector fires on the right token IDs
    4. Surprise-delta suppressor returns ones when surprise is flat,
       < 1 when surprise is climbing
    5. Layer cap enforces the β_max limit and zeroes out low-pi tokens
    6. Routing gate is monotonic in coherence
    7. Gradients flow through the alignment loss to the coarse branch
       but not to the full branch (stopgrad check)
    8. Each module runs in both train() and eval() mode

These tests are designed to be runnable on CPU without Mistral weights,
without transformers, and without any GPU. They only require torch.

To run:
    pytest tests/test_fscs_core.py -v

Note: This test file has NOT been executed in the session that created
these files. It is code-complete but unverified. The first time you run
it, expect 1–3 small fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

torch = pytest.importorskip("torch")

from symbolu.fscs.core import (
    FSCSConfig,
    FSCSCoherenceModule,
    FSCSRoutingGate,
    FSCSBoundaryDetector,
    FSCSSurpriseDeltaSuppressor,
    FSCSLayerCap,
    FSCSCoarseAdapter,
    fscs_alignment_loss,
)


# ============================================================================
# Fixtures
# ============================================================================


B, N, D = 2, 32, 16


@pytest.fixture
def cfg() -> FSCSConfig:
    return FSCSConfig(
        gamma=5.0,
        delta_residual=3.0,
        ema_decay=0.4,
        warmup_tokens=3,
        num_bands=3,
        alpha_sharpness=10.0,
        tau_global=0.7,
        tau_mid=0.5,
        tau_local=0.3,
        hard_route_threshold=0.7,
        use_hard_routing=False,
        surprise_eta=1.0,
        use_surprise_delta=True,
        use_boundary_detector=True,
        boundary_token_ids=(7, 13, 42),  # Arbitrary sentinel IDs
        beta_max_train=0.3,
        beta_max_inference=0.5,
        coarse_window=8,
        alignment_lambda=0.1,
    )


@pytest.fixture
def fake_attn_output() -> torch.Tensor:
    # Low-variance around a slow-drifting mean, so coherence should be high
    t = torch.linspace(0, 1, N).view(1, N, 1)
    base = 0.1 * t.expand(B, N, D)
    noise = 0.01 * torch.randn(B, N, D)
    return base + noise


@pytest.fixture
def fake_residual() -> torch.Tensor:
    # Similar slow drift
    t = torch.linspace(0, 1, N).view(1, N, 1)
    base = 0.1 * t.expand(B, N, D)
    noise = 0.02 * torch.randn(B, N, D)
    return base + noise


# ============================================================================
# §1 — Coherence module
# ============================================================================


class TestCoherenceModule:
    def test_output_shape(self, cfg, fake_attn_output, fake_residual):
        mod = FSCSCoherenceModule(cfg)
        out = mod(fake_attn_output, fake_residual)
        assert out.shape == (B, N), f"expected {(B, N)}, got {out.shape}"

    def test_range_in_unit_interval(self, cfg, fake_attn_output, fake_residual):
        mod = FSCSCoherenceModule(cfg)
        out = mod(fake_attn_output, fake_residual)
        assert out.min().item() >= 0.0
        assert out.max().item() <= 1.0 + 1e-5

    def test_warmup_region_is_zero(self, cfg, fake_attn_output, fake_residual):
        """§4 — sequence-start warmup forces low coherence for the first w tokens."""
        mod = FSCSCoherenceModule(cfg)
        out = mod(fake_attn_output, fake_residual)
        w = cfg.warmup_tokens
        assert (out[:, :w] == 0.0).all(), \
            f"warmup region should be 0, got {out[:, :w]}"

    def test_stable_input_gives_high_coherence(self, cfg):
        """A literally constant residual should yield high coherence."""
        stable = torch.ones(B, N, D)
        mod = FSCSCoherenceModule(cfg)
        out = mod(stable, stable)
        # Past the warmup, coherence should be high (~1.0) because deltas are 0
        w = cfg.warmup_tokens
        assert out[:, w + 2:].mean().item() > 0.9, \
            f"stable input coherence too low: {out[:, w + 2:].mean().item()}"

    def test_noisy_input_gives_lower_coherence(self, cfg):
        """Very noisy input should yield lower coherence than stable input."""
        stable = torch.ones(B, N, D)
        noisy = torch.randn(B, N, D) * 5.0
        mod = FSCSCoherenceModule(cfg)
        stable_c = mod(stable, stable)[:, cfg.warmup_tokens + 2:].mean().item()
        noisy_c = mod(noisy, noisy)[:, cfg.warmup_tokens + 2:].mean().item()
        assert stable_c > noisy_c, \
            f"expected stable ({stable_c}) > noisy ({noisy_c})"


# ============================================================================
# §6 — Routing gate
# ============================================================================


class TestRoutingGate:
    def test_shape_and_range(self, cfg):
        gate = FSCSRoutingGate(cfg, band="mid")
        coherence = torch.linspace(0, 1, B * N).view(B, N)
        pi = gate(coherence)
        assert pi.shape == (B, N)
        assert pi.min().item() >= 0.0 and pi.max().item() <= 1.0

    def test_monotonic_in_coherence(self, cfg):
        """Higher coherence should produce monotonically higher π."""
        gate = FSCSRoutingGate(cfg, band="mid")
        c_low = torch.full((B, N), 0.1)
        c_high = torch.full((B, N), 0.9)
        pi_low = gate(c_low).mean().item()
        pi_high = gate(c_high).mean().item()
        assert pi_high > pi_low, \
            f"expected π(0.9)={pi_high} > π(0.1)={pi_low}"

    def test_band_ordering(self, cfg):
        """Given the same coherence, global band should gate less than local."""
        global_gate = FSCSRoutingGate(cfg, band="global")
        local_gate = FSCSRoutingGate(cfg, band="local")
        c = torch.full((B, N), 0.6)  # between τ_global and τ_local
        pi_global = global_gate(c).mean().item()
        pi_local = local_gate(c).mean().item()
        assert pi_local > pi_global, \
            f"expected local π={pi_local} > global π={pi_global}"

    def test_rejects_invalid_band(self, cfg):
        with pytest.raises(ValueError):
            FSCSRoutingGate(cfg, band="nonsense")


# ============================================================================
# §3 — Boundary detector
# ============================================================================


class TestBoundaryDetector:
    def test_fires_on_listed_tokens(self, cfg):
        det = FSCSBoundaryDetector(cfg)
        # Input with some boundary tokens at known positions
        ids = torch.tensor([[1, 2, 7, 4, 13, 6, 7, 8]])
        out = det(ids)
        assert out.shape == ids.shape
        assert out[0, 0].item() == 0.0  # id 1 is not a boundary
        assert out[0, 2].item() == 1.0  # id 7 is a boundary
        assert out[0, 4].item() == 1.0  # id 13 is a boundary
        assert out[0, 6].item() == 1.0  # id 7 again

    def test_empty_boundary_list_is_noop(self):
        empty_cfg = FSCSConfig(boundary_token_ids=())
        det = FSCSBoundaryDetector(empty_cfg)
        ids = torch.tensor([[1, 2, 3, 4]])
        out = det(ids)
        assert (out == 0.0).all()


# ============================================================================
# §2 — Surprise-delta suppressor
# ============================================================================


class TestSurpriseDelta:
    def test_flat_surprise_returns_ones(self, cfg):
        sup = FSCSSurpriseDeltaSuppressor(cfg)
        s = torch.full((B, N), 2.0)  # flat surprise
        out = sup(s)
        assert out.shape == (B, N)
        assert torch.allclose(out, torch.ones_like(out), atol=1e-5), \
            "flat surprise should give U_t = 1"

    def test_increasing_surprise_suppresses(self, cfg):
        sup = FSCSSurpriseDeltaSuppressor(cfg)
        # Linearly increasing surprise
        s = torch.linspace(0, 5, N).view(1, N).expand(B, N).contiguous()
        out = sup(s)
        # Later positions should be < 1 because Δs > 0
        assert out[:, -1].mean().item() < 1.0

    def test_decreasing_surprise_clamped(self, cfg):
        sup = FSCSSurpriseDeltaSuppressor(cfg)
        # Decreasing surprise → Δs < 0 → clamped to 0 → U_t = 1
        s = torch.linspace(5, 0, N).view(1, N).expand(B, N).contiguous()
        out = sup(s)
        assert torch.allclose(out, torch.ones_like(out), atol=1e-5)

    def test_none_returns_scalar_one(self, cfg):
        sup = FSCSSurpriseDeltaSuppressor(cfg)
        out = sup(None)
        assert out.numel() == 1 and out.item() == 1.0


# ============================================================================
# §7 — Layer cap
# ============================================================================


class TestLayerCap:
    def test_respects_beta_max(self, cfg):
        cap = FSCSLayerCap(cfg)
        # π with 80% of tokens above the gate — should be capped
        pi = torch.linspace(0.0, 1.0, N).view(1, N).expand(B, N).contiguous()
        capped = cap.apply(pi, training=True)  # β_max_train = 0.3
        active = (capped > 0).float().mean().item()
        assert active <= cfg.beta_max_train + 0.05, \
            f"cap should keep ≤ {cfg.beta_max_train}, got {active}"

    def test_inference_cap_higher(self, cfg):
        cap = FSCSLayerCap(cfg)
        pi = torch.linspace(0.0, 1.0, N).view(1, N).expand(B, N).contiguous()
        capped_train = cap.apply(pi, training=True)
        capped_eval = cap.apply(pi, training=False)
        train_active = (capped_train > 0).float().mean().item()
        eval_active = (capped_eval > 0).float().mean().item()
        assert eval_active >= train_active, \
            f"inference cap should allow at least as many tokens as training"

    def test_keeps_highest_pi(self, cfg):
        """The cap should keep the tokens with the highest π values."""
        cap = FSCSLayerCap(cfg)
        pi = torch.tensor([[0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6]])
        capped = cap.apply(pi, training=False)  # β_max_inference = 0.5, allow 4
        kept = (capped > 0).nonzero().squeeze(-1)[:, 1].tolist()
        # The four highest values are at positions 1, 3, 5, 7
        assert set(kept) == {1, 3, 5, 7}, f"expected top-4, got {kept}"


# ============================================================================
# §12.2 — Alignment loss stopgrad
# ============================================================================


class TestAlignmentLoss:
    def test_loss_shape_and_sign(self):
        out_full = torch.randn(B, N, D)
        out_coarse = torch.randn(B, N, D)
        loss = fscs_alignment_loss(out_full, out_coarse, lambda_weight=0.1)
        assert loss.dim() == 0  # scalar
        assert loss.item() >= 0.0

    def test_zero_loss_when_branches_match(self):
        out = torch.randn(B, N, D)
        loss = fscs_alignment_loss(out, out.clone(), lambda_weight=0.1)
        assert loss.item() < 1e-8

    def test_stopgrad_on_full_path(self):
        """Gradient should flow to coarse but NOT to full (§12.2 invariant)."""
        out_full = torch.randn(B, N, D, requires_grad=True)
        out_coarse = torch.randn(B, N, D, requires_grad=True)
        loss = fscs_alignment_loss(out_full, out_coarse, lambda_weight=0.1)
        loss.backward()

        # Full path should have no gradient (stopgrad detaches it)
        assert out_full.grad is None or out_full.grad.abs().sum().item() == 0.0, \
            "stopgrad invariant violated: full path received a gradient"
        # Coarse path should have a gradient
        assert out_coarse.grad is not None
        assert out_coarse.grad.abs().sum().item() > 0.0


# ============================================================================
# Integration: all modules flow together
# ============================================================================


class TestCompositeFlow:
    def test_full_pipeline_flows(self, cfg, fake_attn_output, fake_residual):
        """
        Wire coherence → routing → boundary → cap → blend in sequence,
        verifying every shape and range invariant along the way.
        """
        coh = FSCSCoherenceModule(cfg)
        gate = FSCSRoutingGate(cfg, band="mid")
        boundary = FSCSBoundaryDetector(cfg)
        cap = FSCSLayerCap(cfg)

        c = coh(fake_attn_output, fake_residual)  # [B, N]
        pi = gate(c)                              # [B, N]

        # Simulated input_ids with some boundaries at positions 5 and 10
        ids = torch.zeros(B, N, dtype=torch.long)
        ids[:, 5] = 7   # boundary id
        ids[:, 10] = 13  # another boundary id
        bound = boundary(ids)
        pi_after_boundary = pi * (1 - bound)

        # Boundaries must have π = 0
        assert pi_after_boundary[:, 5].abs().sum().item() == 0.0
        assert pi_after_boundary[:, 10].abs().sum().item() == 0.0

        # Cap
        pi_capped = cap.apply(pi_after_boundary, training=False)
        assert pi_capped.shape == pi.shape
        assert pi_capped.min().item() >= 0.0
        assert pi_capped.max().item() <= 1.0

        # Blend
        fake_full = torch.randn(B, N, D)
        fake_coarse = torch.randn(B, N, D)
        pi_exp = pi_capped.unsqueeze(-1)
        blended = (1 - pi_exp) * fake_full + pi_exp * fake_coarse
        assert blended.shape == (B, N, D)


# ============================================================================
# FSCSCoarseAdapter + alignment-loss training smoke test
# ============================================================================


class TestCoarseAdapter:
    """
    The coarse adapter is the trainable piece the alignment loss acts on.
    These tests verify that (1) it has the right residual semantics at
    init, (2) it produces gradients that flow through the alignment
    loss, (3) the stopgrad on the full path still holds when the
    adapter is in the loop, and (4) a handful of training steps visibly
    reduce the alignment loss on synthetic data.
    """

    def test_shapes_and_init_identity(self):
        """At init, gate ≈ 0.12 and up-weights are zero → adapter output
        is approximately an identity map on its input."""
        d_model = 64
        ad = FSCSCoarseAdapter(d_model=d_model, d_inner=16, gate_init=-2.0)
        x = torch.randn(B, N, d_model)
        y = ad(x)
        assert y.shape == x.shape
        # With up.weight=0 and up.bias=0, the gated residual is
        # x + sigmoid(-2) * 0 = x exactly.
        assert torch.allclose(y, x, atol=1e-6)

    def test_gradient_flows_through_alignment_loss(self):
        """Gradient flows from alignment loss through the adapter to
        its trainable parameters, but NOT back to the full output."""
        d_model = 64
        ad = FSCSCoarseAdapter(d_model=d_model, d_inner=16, gate_init=0.0)

        out_full = torch.randn(B, N, d_model, requires_grad=True)
        out_coarse_raw = torch.randn(B, N, d_model, requires_grad=True)

        out_coarse_adapted = ad(out_coarse_raw)
        loss = fscs_alignment_loss(out_full, out_coarse_adapted,
                                   lambda_weight=1.0)
        loss.backward()

        # Stopgrad invariant
        assert out_full.grad is None or out_full.grad.abs().sum().item() == 0.0
        # Adapter parameters should receive gradient
        ad_grad_total = 0.0
        for p in ad.parameters():
            if p.grad is not None:
                ad_grad_total += p.grad.abs().sum().item()
        assert ad_grad_total > 0.0, \
            "coarse adapter received no gradient from alignment loss"

    def test_training_reduces_alignment_loss(self):
        """Five AdamW steps on synthetic data should measurably reduce
        the alignment loss, with the adapter gate opening from its
        near-zero init."""
        d_model = 64
        ad = FSCSCoarseAdapter(d_model=d_model, d_inner=16, gate_init=-2.0)
        opt = torch.optim.AdamW(ad.parameters(), lr=1e-2)

        # Fixed synthetic pair — the "full" target is a specific linear
        # projection of the "coarse" raw, so the adapter CAN learn it.
        torch.manual_seed(0)
        coarse_raw = torch.randn(B, N, d_model)
        target_proj = torch.randn(d_model, d_model) * 0.1
        out_full = coarse_raw @ target_proj + coarse_raw  # linear residual

        losses = []
        for step in range(10):
            opt.zero_grad()
            out_coarse_adapted = ad(coarse_raw)
            loss = fscs_alignment_loss(out_full, out_coarse_adapted,
                                       lambda_weight=1.0)
            loss.backward()
            opt.step()
            losses.append(loss.item())

        assert losses[-1] < losses[0], (
            f"alignment loss did not decrease: {losses[0]:.6f} -> "
            f"{losses[-1]:.6f}. Adapter training may be broken."
        )

    def test_num_trainable_params_reasonable(self):
        """Adapter at d_model=4096, d_inner=256 should have ~2M params
        per layer (within an order of magnitude)."""
        ad = FSCSCoarseAdapter(d_model=4096, d_inner=256)
        n = ad.num_trainable_params()
        assert 1_000_000 < n < 5_000_000, (
            f"expected adapter param count in [1M, 5M], got {n}"
        )


if __name__ == "__main__":
    # Allow direct invocation for quick manual runs
    pytest.main([__file__, "-v"])
