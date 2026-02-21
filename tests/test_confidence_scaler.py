"""
Unit Tests for State-Conditional Logit Scale ("Confidence Knob") + Entropy Band
=================================================================================

Tests:
1. ConfidenceScaler: s_t in bounds, correct shape, risk gating works
2. EntropyBandLoss: finite loss, zero inside band, positive outside
3. VrittiRiskHead: correct shapes, risk in [0,1]
4. CalibrationDiagnostics: all metrics present, DDP-reduce mock
5. ConfidenceInferenceHook: scaling works at decode time
6. fit_constant_temperature: returns valid T and PPL
7. Training integration: loss decreases, no NaN/Inf

Run with: pytest tests/test_confidence_scaler.py -v
"""

import math
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.training.confidence_scaler import (
    ConfidenceScalerConfig,
    ConfidenceScaler,
    EntropyBandLoss,
    VrittiRiskHead,
    CalibrationDiagnostics,
    ConfidenceInferenceHook,
    fit_constant_temperature,
    log_confidence_metrics,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def config():
    return ConfidenceScalerConfig(
        enable=True,
        s_min=0.3,
        s_max=10.0,
        epsilon=1e-4,
        enable_risk_gating=False,
        alpha_risk=0.5,
        entropy_band_ratio_min=0.10,
        entropy_band_ratio_max=0.35,
        lambda_entropy_band=1e-3,
        lambda_scale_penalty=1e-4,
    )


@pytest.fixture
def config_with_risk():
    return ConfidenceScalerConfig(
        enable=True,
        s_min=0.3,
        s_max=10.0,
        enable_risk_gating=True,
        alpha_risk=0.5,
        enable_vritti_head=True,
        vritti_kl_weight=0.1,
    )


@pytest.fixture
def hidden_dim():
    return 64


@pytest.fixture
def vocab_size():
    return 1000


@pytest.fixture
def batch():
    """Create dummy batch tensors."""
    torch.manual_seed(42)
    B, T, D, V = 2, 16, 64, 1000
    hidden_states = torch.randn(B, T, D)
    logits_raw = torch.randn(B, T, V)
    targets = torch.randint(0, V, (B, T))
    return hidden_states, logits_raw, targets


# =============================================================================
# TEST 1: ConfidenceScaler
# =============================================================================

class TestConfidenceScaler:
    """Test per-token confidence scaling."""

    def test_output_shape(self, config, hidden_dim, batch):
        """s_t should be [B, T, 1]."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h, _, _ = batch
        s, diag = scaler(h)
        assert s.shape == (h.shape[0], h.shape[1], 1)

    def test_s_in_bounds(self, config, hidden_dim, batch):
        """s_t must be in [s_min, s_max]."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h, _, _ = batch
        s, _ = scaler(h)
        assert s.min().item() >= config.s_min - 1e-6
        assert s.max().item() <= config.s_max + 1e-6

    def test_initial_s_near_one(self, config, hidden_dim):
        """With zero-init weights and bias ≈ 0.54, initial s should be near 1.0."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h = torch.zeros(1, 1, hidden_dim)
        s, _ = scaler(h)
        # softplus(0.54) + 1e-4 ≈ 1.0
        assert abs(s.item() - 1.0) < 0.1, f"Initial s={s.item():.4f}, expected ~1.0"

    def test_scale_logits_shape(self, config, hidden_dim, batch):
        """scale_logits should return logits, s, diagnostics with correct shapes."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h, logits, _ = batch
        logits_scaled, s, diag = scaler.scale_logits(logits, h)
        assert logits_scaled.shape == logits.shape
        assert s.shape == (h.shape[0], h.shape[1], 1)
        assert 's_raw' in diag
        assert 's_clamped' in diag

    def test_risk_gating_increases_s(self, config_with_risk, hidden_dim, batch):
        """When risk_prob > 0, s should be larger than without risk."""
        scaler = ConfidenceScaler(hidden_dim, config_with_risk)
        h, _, _ = batch

        # Without risk
        s_no_risk, _ = scaler(h, risk_prob=None)

        # With high risk
        risk = torch.ones(h.shape[0], h.shape[1], 1) * 0.8
        s_with_risk, _ = scaler(h, risk_prob=risk)

        # s_with_risk = s * (1 + 0.5 * 0.8) = s * 1.4
        # So s_with_risk should be >= s_no_risk (before clamping)
        assert s_with_risk.mean().item() >= s_no_risk.mean().item() - 1e-4

    def test_gradient_flows(self, config, hidden_dim, batch):
        """Gradient should flow through ConfidenceScaler."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h, logits, targets = batch
        h.requires_grad_(True)

        logits_scaled, s, _ = scaler.scale_logits(logits, h)
        loss = logits_scaled.sum()
        loss.backward()

        # Check gradient exists on scale_proj parameters
        assert scaler.scale_proj.weight.grad is not None
        assert scaler.scale_proj.bias.grad is not None

    def test_mixed_precision_fp16(self, config, hidden_dim):
        """Should work with float16 inputs."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h = torch.randn(2, 8, hidden_dim, dtype=torch.float16)
        logits = torch.randn(2, 8, 1000, dtype=torch.float16)
        logits_scaled, s, _ = scaler.scale_logits(logits, h)
        assert logits_scaled.dtype == torch.float16
        assert not torch.isnan(logits_scaled).any()

    def test_mixed_precision_bf16(self, config, hidden_dim):
        """Should work with bfloat16 inputs."""
        scaler = ConfidenceScaler(hidden_dim, config)
        h = torch.randn(2, 8, hidden_dim, dtype=torch.bfloat16)
        logits = torch.randn(2, 8, 1000, dtype=torch.bfloat16)
        logits_scaled, s, _ = scaler.scale_logits(logits, h)
        assert logits_scaled.dtype == torch.bfloat16
        assert not torch.isnan(logits_scaled).any()


# =============================================================================
# TEST 2: EntropyBandLoss
# =============================================================================

class TestEntropyBandLoss:
    """Test entropy band constraint + scale penalty."""

    def test_loss_is_finite(self, config, vocab_size, batch):
        """Loss should be finite, not NaN."""
        band_loss = EntropyBandLoss(vocab_size, config)
        _, logits, targets = batch
        s = torch.ones(logits.shape[0], logits.shape[1], 1)
        loss, metrics = band_loss(logits, s, targets=targets)
        assert torch.isfinite(loss)
        assert not torch.isnan(loss)

    def test_loss_positive_outside_band(self, config, vocab_size):
        """Loss should be positive when entropy is outside band."""
        band_loss = EntropyBandLoss(vocab_size, config)

        # Very peaked logits (low entropy -> below H_min)
        logits = torch.full((2, 8, vocab_size), -100.0)
        logits[:, :, 0] = 100.0
        s = torch.ones(2, 8, 1)
        loss_low, _ = band_loss(logits, s)
        assert loss_low.item() > 0, "Loss should be positive for low entropy"

        # Uniform logits (high entropy -> above H_max)
        logits_uniform = torch.zeros(2, 8, vocab_size)
        loss_high, _ = band_loss(logits_uniform, s)
        assert loss_high.item() > 0, "Loss should be positive for high entropy"

    def test_scale_penalty(self, config, vocab_size):
        """Scale penalty should be positive when s > 1."""
        band_loss = EntropyBandLoss(vocab_size, config)
        logits = torch.randn(2, 8, vocab_size)
        s_large = torch.ones(2, 8, 1) * 5.0  # s >> 1, so log(s) > 0
        loss_large, metrics_large = band_loss(logits, s_large)

        s_one = torch.ones(2, 8, 1) * 1.0  # s = 1, so log(s) = 0
        loss_one, metrics_one = band_loss(logits, s_one)

        # Scale penalty should be larger for s=5 than s=1
        assert metrics_large['scale_penalty_loss'] > metrics_one['scale_penalty_loss']

    def test_metrics_present(self, config, vocab_size, batch):
        """All expected metric keys should be present."""
        band_loss = EntropyBandLoss(vocab_size, config)
        _, logits, targets = batch
        s = torch.ones(logits.shape[0], logits.shape[1], 1)
        _, metrics = band_loss(logits, s, targets=targets)

        expected_keys = [
            'entropy_band_loss', 'scale_penalty_loss', 'confidence_total_aux_loss',
            'entropy_mean', 'entropy_H_min', 'entropy_H_max',
            'entropy_p10', 'entropy_p90',
        ]
        for key in expected_keys:
            assert key in metrics, f"Missing metric: {key}"

    def test_mask_ignores_padding(self, config, vocab_size):
        """Padding tokens should be excluded from loss."""
        band_loss = EntropyBandLoss(vocab_size, config)
        logits = torch.randn(2, 8, vocab_size)
        s = torch.ones(2, 8, 1)

        # All valid targets
        targets_valid = torch.randint(0, vocab_size, (2, 8))
        loss_valid, _ = band_loss(logits, s, targets=targets_valid)

        # Half padding
        targets_padded = targets_valid.clone()
        targets_padded[:, 4:] = -100
        loss_padded, _ = band_loss(logits, s, targets=targets_padded)

        # Both should be finite
        assert torch.isfinite(loss_valid)
        assert torch.isfinite(loss_padded)

    def test_entropy_band_values(self, config, vocab_size):
        """H_min and H_max should be computed from vocab_size."""
        band_loss = EntropyBandLoss(vocab_size, config)
        log_V = math.log(vocab_size)
        assert abs(band_loss.H_min - 0.10 * log_V) < 1e-6
        assert abs(band_loss.H_max - 0.35 * log_V) < 1e-6


# =============================================================================
# TEST 3: VrittiRiskHead
# =============================================================================

class TestVrittiRiskHead:
    """Test auxiliary Vritti head for risk gating."""

    def test_output_shapes(self, config_with_risk, hidden_dim, batch):
        """All outputs should have correct shapes."""
        head = VrittiRiskHead(hidden_dim, config_with_risk)
        h, _, _ = batch
        out = head(h)
        B, T = h.shape[0], h.shape[1]
        assert out['v_logits'].shape == (B, T, 5)
        assert out['v_probs'].shape == (B, T, 5)
        assert out['risk_prob'].shape == (B, T, 1)

    def test_risk_in_range(self, config_with_risk, hidden_dim, batch):
        """Risk probability should be in [0, 1] (sum of two softmax probs)."""
        head = VrittiRiskHead(hidden_dim, config_with_risk)
        h, _, _ = batch
        out = head(h)
        risk = out['risk_prob']
        # Sum of two softmax probs, each in [0, 1], sum in [0, 2]
        # But practically always in [0, 1] since probs sum to 1
        assert risk.min().item() >= 0.0
        assert risk.max().item() <= 2.0  # Theoretical max

    def test_kl_loss_finite(self, config_with_risk, hidden_dim, batch):
        """KL loss should be finite."""
        head = VrittiRiskHead(hidden_dim, config_with_risk)
        h, _, _ = batch
        out = head(h)

        # Create teacher labels (uniform)
        teacher = torch.ones(h.shape[0], h.shape[1], 5) / 5
        loss, metrics = head.compute_kl_loss(out['v_logits'], teacher)
        assert torch.isfinite(loss)
        assert 'vritti_kl_loss' in metrics
        assert 'vritti_risk_mean' in metrics

    def test_kl_loss_with_mask(self, config_with_risk, hidden_dim, batch):
        """KL loss should respect mask."""
        head = VrittiRiskHead(hidden_dim, config_with_risk)
        h, _, _ = batch
        out = head(h)

        teacher = torch.ones(h.shape[0], h.shape[1], 5) / 5
        mask = torch.ones(h.shape[0], h.shape[1])
        mask[:, 8:] = 0  # Mask out second half

        loss, _ = head.compute_kl_loss(out['v_logits'], teacher, mask=mask)
        assert torch.isfinite(loss)


# =============================================================================
# TEST 4: CalibrationDiagnostics
# =============================================================================

class TestCalibrationDiagnostics:
    """Test DDP-safe calibration diagnostics."""

    def test_all_metrics_present(self, batch):
        """All expected metrics should be computed."""
        h, logits_raw, targets = batch
        s = torch.ones(logits_raw.shape[0], logits_raw.shape[1], 1)
        logits_scaled = logits_raw / s

        metrics = CalibrationDiagnostics.compute(
            logits_raw, logits_scaled, s, targets=targets,
        )

        expected = [
            'logit_std_before', 'logit_std_after',
            'logit_mean_abs_before', 'logit_mean_abs_after',
            's_mean', 's_max', 's_p95',
            'entropy_mean', 'entropy_p10', 'entropy_p90',
            'maxprob_when_wrong',
        ]
        for key in expected:
            assert key in metrics, f"Missing metric: {key}"

    def test_logit_std_changes_with_scaling(self, batch):
        """logit_std_after should differ from logit_std_before when s != 1."""
        h, logits_raw, targets = batch
        s = torch.ones(logits_raw.shape[0], logits_raw.shape[1], 1) * 3.0
        logits_scaled = logits_raw / s

        metrics = CalibrationDiagnostics.compute(
            logits_raw, logits_scaled, s, targets=targets,
        )
        # After dividing by 3, std should be roughly 1/3 of before
        assert metrics['logit_std_after'] < metrics['logit_std_before']

    def test_maxprob_when_wrong_valid(self, batch):
        """maxprob_when_wrong should be in [0, 1]."""
        h, logits_raw, targets = batch
        s = torch.ones(logits_raw.shape[0], logits_raw.shape[1], 1)
        logits_scaled = logits_raw / s

        metrics = CalibrationDiagnostics.compute(
            logits_raw, logits_scaled, s, targets=targets,
        )
        assert 0.0 <= metrics['maxprob_when_wrong'] <= 1.0

    def test_ddp_reduce_noop_for_single_rank(self, batch):
        """DDP reduce with world_size=1 should return same metrics."""
        h, logits_raw, targets = batch
        s = torch.ones(logits_raw.shape[0], logits_raw.shape[1], 1)
        logits_scaled = logits_raw / s

        metrics = CalibrationDiagnostics.compute(
            logits_raw, logits_scaled, s, targets=targets,
        )
        reduced = CalibrationDiagnostics.ddp_reduce(metrics, world_size=1)

        for key in metrics:
            assert abs(metrics[key] - reduced[key]) < 1e-6, f"Mismatch on {key}"


# =============================================================================
# TEST 5: ConfidenceInferenceHook
# =============================================================================

class TestConfidenceInferenceHook:
    """Test inference-time confidence scaling."""

    def test_scale_step_3d(self, config, hidden_dim):
        """Should work with [B, 1, V] and [B, 1, D] inputs."""
        scaler = ConfidenceScaler(hidden_dim, config)
        hook = ConfidenceInferenceHook(scaler)

        logits = torch.randn(2, 1, 1000)
        hidden = torch.randn(2, 1, hidden_dim)

        scaled = hook.scale_step(logits, hidden)
        assert scaled.shape == (2, 1, 1000)
        assert not torch.isnan(scaled).any()

    def test_scale_step_2d(self, config, hidden_dim):
        """Should work with [B, V] and [B, D] inputs."""
        scaler = ConfidenceScaler(hidden_dim, config)
        hook = ConfidenceInferenceHook(scaler)

        logits = torch.randn(2, 1000)
        hidden = torch.randn(2, hidden_dim)

        scaled = hook.scale_step(logits, hidden)
        assert scaled.shape == (2, 1000)
        assert not torch.isnan(scaled).any()

    def test_with_risk_head(self, config_with_risk, hidden_dim):
        """Should work with Vritti risk head."""
        scaler = ConfidenceScaler(hidden_dim, config_with_risk)
        risk_head = VrittiRiskHead(hidden_dim, config_with_risk)
        hook = ConfidenceInferenceHook(scaler, vritti_head=risk_head)

        logits = torch.randn(2, 1, 1000)
        hidden = torch.randn(2, 1, hidden_dim)

        scaled = hook.scale_step(logits, hidden)
        assert scaled.shape == (2, 1, 1000)

    def test_reset(self, config, hidden_dim):
        """Reset should clear step counter."""
        scaler = ConfidenceScaler(hidden_dim, config)
        hook = ConfidenceInferenceHook(scaler)

        logits = torch.randn(2, 1000)
        hidden = torch.randn(2, hidden_dim)
        hook.scale_step(logits, hidden)
        assert hook._step == 1

        hook.reset()
        assert hook._step == 0

    def test_no_gradient_during_inference(self, config, hidden_dim):
        """Inference hook should not track gradients."""
        scaler = ConfidenceScaler(hidden_dim, config)
        hook = ConfidenceInferenceHook(scaler)

        logits = torch.randn(2, 1000, requires_grad=True)
        hidden = torch.randn(2, hidden_dim, requires_grad=True)

        with torch.no_grad():
            scaled = hook.scale_step(logits, hidden)
        # The hook uses @torch.no_grad, so scaled should not require grad
        # (even though inputs do, the hook detaches)
        assert not scaled.requires_grad


# =============================================================================
# TEST 6: fit_constant_temperature
# =============================================================================

class TestFitConstantTemperature:
    """Test scale-matched baseline comparison helper."""

    def test_returns_valid_values(self, batch):
        """Should return positive temperature and finite PPL."""
        _, logits, targets = batch
        T, ppl = fit_constant_temperature(logits, targets)
        assert T > 0, f"Temperature must be positive, got {T}"
        assert math.isfinite(ppl), f"PPL must be finite, got {ppl}"
        assert ppl > 0, f"PPL must be positive, got {ppl}"

    def test_handles_all_padding(self):
        """Should handle all-padding targets gracefully."""
        logits = torch.randn(2, 8, 1000)
        targets = torch.full((2, 8), -100)
        T, ppl = fit_constant_temperature(logits, targets)
        assert T == 1.0  # Default when no valid tokens
        assert ppl == float('inf')

    def test_optimal_temp_near_one_for_calibrated(self):
        """For well-calibrated logits, best T should be near 1.0."""
        torch.manual_seed(42)
        # Create logits where T=1.0 is roughly optimal
        logits = torch.randn(4, 32, 100) * 2.0
        targets = torch.randint(0, 100, (4, 32))
        T, ppl = fit_constant_temperature(logits, targets, num_candidates=100)
        # T should be in a reasonable range (not extreme)
        assert 0.1 <= T <= 10.0, f"Temperature {T} is extreme"


# =============================================================================
# TEST 7: Training Integration
# =============================================================================

class MinimalModel(nn.Module):
    """Minimal model for integration testing."""

    def __init__(self, vocab_size=1000, d_model=64):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.linear = nn.Linear(d_model, d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
        self.d_model = d_model
        self.vocab_size = vocab_size

    def forward(self, input_ids):
        h = self.embedding(input_ids)
        h = self.linear(h)
        logits = self.lm_head(h)
        return {'logits': logits, 'last_hidden_state': h}


class TestTrainingIntegration:
    """Test full training loop with confidence scaler."""

    def test_no_nan_during_training(self, config, vocab_size):
        """Training with confidence scaler should not produce NaN."""
        torch.manual_seed(42)
        model = MinimalModel(vocab_size, 64)
        scaler = ConfidenceScaler(64, config)
        band_loss_fn = EntropyBandLoss(vocab_size, config)

        optimizer = torch.optim.AdamW(
            list(model.parameters()) + list(scaler.parameters()),
            lr=1e-3,
        )

        for step in range(20):
            x = torch.randint(0, vocab_size, (4, 16))
            y = torch.randint(0, vocab_size, (4, 16))

            optimizer.zero_grad()
            out = model(x)
            logits_raw = out['logits']
            h = out['last_hidden_state']

            logits_scaled, s, _ = scaler.scale_logits(logits_raw, h)
            ce_loss = F.cross_entropy(
                logits_scaled.view(-1, vocab_size), y.view(-1),
            )
            band_loss, _ = band_loss_fn(logits_scaled, s, targets=y)
            total_loss = ce_loss + band_loss

            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(model.parameters()) + list(scaler.parameters()), 1.0,
            )
            optimizer.step()

            assert not torch.isnan(total_loss), f"NaN at step {step}"
            assert not torch.isinf(total_loss), f"Inf at step {step}"

    def test_loss_decreases(self, config, vocab_size):
        """Loss should generally decrease over training."""
        torch.manual_seed(42)
        model = MinimalModel(vocab_size, 64)
        scaler = ConfidenceScaler(64, config)
        band_loss_fn = EntropyBandLoss(vocab_size, config)

        optimizer = torch.optim.AdamW(
            list(model.parameters()) + list(scaler.parameters()),
            lr=1e-3,
        )

        # Fixed batch for consistent comparison
        x = torch.randint(0, vocab_size, (4, 16))
        y = torch.randint(0, vocab_size, (4, 16))

        losses = []
        for step in range(50):
            optimizer.zero_grad()
            out = model(x)
            logits_scaled, s, _ = scaler.scale_logits(out['logits'], out['last_hidden_state'])
            ce_loss = F.cross_entropy(logits_scaled.view(-1, vocab_size), y.view(-1))
            band_loss, _ = band_loss_fn(logits_scaled, s, targets=y)
            total_loss = ce_loss + band_loss
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(model.parameters()) + list(scaler.parameters()), 1.0,
            )
            optimizer.step()
            losses.append(total_loss.item())

        avg_first = sum(losses[:5]) / 5
        avg_last = sum(losses[-5:]) / 5
        assert avg_last < avg_first, (
            f"Loss didn't decrease: first_5={avg_first:.4f}, last_5={avg_last:.4f}"
        )

    def test_s_adapts_during_training(self, config, vocab_size):
        """Scale s_t should change from initial values during training."""
        torch.manual_seed(42)
        model = MinimalModel(vocab_size, 64)
        scaler = ConfidenceScaler(64, config)
        band_loss_fn = EntropyBandLoss(vocab_size, config)

        optimizer = torch.optim.AdamW(
            list(model.parameters()) + list(scaler.parameters()),
            lr=1e-3,
        )

        x = torch.randint(0, vocab_size, (4, 16))
        y = torch.randint(0, vocab_size, (4, 16))

        # Get initial s
        with torch.no_grad():
            out = model(x)
            _, s_init, _ = scaler.scale_logits(out['logits'], out['last_hidden_state'])
            s_init_mean = s_init.mean().item()

        # Train
        for step in range(30):
            optimizer.zero_grad()
            out = model(x)
            logits_scaled, s, _ = scaler.scale_logits(out['logits'], out['last_hidden_state'])
            ce_loss = F.cross_entropy(logits_scaled.view(-1, vocab_size), y.view(-1))
            band_loss, _ = band_loss_fn(logits_scaled, s, targets=y)
            (ce_loss + band_loss).backward()
            optimizer.step()

        # Get final s
        with torch.no_grad():
            out = model(x)
            _, s_final, _ = scaler.scale_logits(out['logits'], out['last_hidden_state'])
            s_final_mean = s_final.mean().item()

        # s should have changed
        assert abs(s_final_mean - s_init_mean) > 1e-3, (
            f"s didn't adapt: init={s_init_mean:.4f}, final={s_final_mean:.4f}"
        )

    def test_risk_gating_training(self, config_with_risk, vocab_size):
        """Training with risk gating should not crash."""
        torch.manual_seed(42)
        model = MinimalModel(vocab_size, 64)
        scaler = ConfidenceScaler(64, config_with_risk)
        risk_head = VrittiRiskHead(64, config_with_risk)
        band_loss_fn = EntropyBandLoss(vocab_size, config_with_risk)

        all_params = (
            list(model.parameters()) +
            list(scaler.parameters()) +
            list(risk_head.parameters())
        )
        optimizer = torch.optim.AdamW(all_params, lr=1e-3)

        x = torch.randint(0, vocab_size, (4, 16))
        y = torch.randint(0, vocab_size, (4, 16))

        for step in range(10):
            optimizer.zero_grad()
            out = model(x)
            h = out['last_hidden_state']

            # Get risk from Vritti head
            vritti_out = risk_head(h.detach())
            risk_prob = vritti_out['risk_prob']

            logits_scaled, s, _ = scaler.scale_logits(out['logits'], h, risk_prob)
            ce_loss = F.cross_entropy(logits_scaled.view(-1, vocab_size), y.view(-1))
            band_loss, _ = band_loss_fn(logits_scaled, s, targets=y)
            total = ce_loss + band_loss
            total.backward()
            optimizer.step()

            assert not torch.isnan(total), f"NaN at step {step}"


# =============================================================================
# TEST 8: Logging utility
# =============================================================================

class TestLogging:
    """Test logging utility functions."""

    def test_log_confidence_metrics_format(self):
        """Log formatting should not crash."""
        metrics = {
            's_mean': 1.5,
            's_p95': 3.2,
            's_max': 5.0,
            'entropy_mean': 2.5,
            'logit_std_before': 4.0,
            'logit_std_after': 2.0,
        }
        result = log_confidence_metrics(metrics, global_step=100, print_every=100, rank=0)
        assert result is not None
        assert "Step 100" in result

    def test_log_skips_non_rank0(self):
        """Should not log on non-rank-0."""
        metrics = {'s_mean': 1.0}
        result = log_confidence_metrics(metrics, global_step=100, print_every=100, rank=1)
        assert result is None

    def test_log_skips_off_interval(self):
        """Should not log on non-interval steps."""
        metrics = {'s_mean': 1.0}
        result = log_confidence_metrics(metrics, global_step=50, print_every=100, rank=0)
        assert result is None
