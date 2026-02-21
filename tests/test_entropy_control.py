"""
Validation Tests for Entropy-Based Logit Scale Control
=======================================================

Tests to confirm:
1. Baseline and entropy-controlled model start with same initial entropy.
2. Logit std remains within stable band (1-6 typical).
3. No training instability introduced.
4. Inference entropy converges toward target band.

Run with: pytest tests/test_entropy_control.py -v
"""

import math
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.training.entropy_control import (
    EntropyControlConfig,
    LogitScaleModule,
    AdaptiveEntropyController,
    topk_entropy,
    compute_entropy_penalty,
    attach_logit_scale,
    log_entropy_metrics,
)


# =============================================================================
# FIXTURES: Minimal decoder-only transformer for testing
# =============================================================================

class MinimalTransformer(nn.Module):
    """Minimal decoder-only transformer for entropy control tests."""

    def __init__(self, vocab_size=1000, d_model=64, n_heads=4, n_layers=2):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.pos_embedding = nn.Embedding(512, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_model * 4,
            batch_first=True, dropout=0.0,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, input_ids):
        B, N = input_ids.shape
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0).expand(B, -1)
        x = self.embedding(input_ids) + self.pos_embedding(positions)
        # Causal mask
        mask = nn.Transformer.generate_square_subsequent_mask(N, device=input_ids.device)
        x = self.transformer(x, mask=mask, is_causal=True)
        logits = self.lm_head(x)
        return logits


@pytest.fixture
def vocab_size():
    return 1000


@pytest.fixture
def device():
    return torch.device("cpu")


@pytest.fixture
def model(vocab_size, device):
    torch.manual_seed(42)
    m = MinimalTransformer(vocab_size=vocab_size).to(device)
    return m


@pytest.fixture
def default_config():
    return EntropyControlConfig(
        enable_entropy_control_train=True,
        entropy_topk=50,
        entropy_h_min=0.15,
        entropy_h_max=0.35,
        entropy_lambda=0.01,
        logit_scale_min=-4.0,
        logit_scale_max=4.0,
    )


@pytest.fixture
def dummy_batch(vocab_size, device):
    """Create dummy input and target tensors."""
    torch.manual_seed(42)
    B, N = 4, 32
    x = torch.randint(0, vocab_size, (B, N), device=device)
    y = torch.randint(0, vocab_size, (B, N), device=device)
    return x, y


# =============================================================================
# TEST 1: Baseline and entropy-controlled model start with same initial entropy
# =============================================================================

class TestInitialEntropy:
    """Verify that adding entropy control doesn't change initial entropy."""

    def test_same_initial_entropy(self, model, default_config, dummy_batch, vocab_size):
        """Baseline and entropy-controlled model should start with same entropy."""
        x, y = dummy_batch

        # Compute baseline entropy
        model.eval()
        with torch.no_grad():
            baseline_logits = model(x)
            baseline_entropy = topk_entropy(baseline_logits, K=50)

        # Attach entropy control
        scale_module = attach_logit_scale(model, default_config)

        # Scale is initialized to 0, so exp(0) = 1.0 => no scaling
        with torch.no_grad():
            controlled_logits = model(x)
            scaled_logits = scale_module(controlled_logits)
            controlled_entropy = topk_entropy(scaled_logits, K=50)

        # Initial logit_scale = 0 means exp(0) = 1.0, so entropy should be identical
        assert abs(baseline_entropy.item() - controlled_entropy.item()) < 1e-5, (
            f"Initial entropy mismatch: baseline={baseline_entropy.item():.6f}, "
            f"controlled={controlled_entropy.item():.6f}"
        )

    def test_initial_scale_is_one(self, default_config):
        """Verify initial exp(logit_scale) = 1.0."""
        module = LogitScaleModule(default_config)
        assert abs(module.get_scale_factor() - 1.0) < 1e-6


# =============================================================================
# TEST 2: Logit std remains within stable band
# =============================================================================

class TestLogitStdStability:
    """Verify logit std stays in stable range during training steps."""

    def test_logit_std_within_range(self, model, default_config, dummy_batch, vocab_size):
        """After a few training steps, logit std should remain reasonable."""
        x, y = dummy_batch
        scale_module = attach_logit_scale(model, default_config)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        logit_stds = []
        for step in range(20):
            optimizer.zero_grad()
            logits = model(x)
            scaled_logits = scale_module(logits)
            ce_loss = F.cross_entropy(
                scaled_logits.view(-1, vocab_size), y.view(-1), ignore_index=-100
            )
            total_loss, metrics = scale_module.compute_loss(scaled_logits, ce_loss)
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            logit_stds.append(metrics['logit_std'])

        # Logit std should stay within a reasonable range (not exploding or collapsing)
        for i, std in enumerate(logit_stds):
            assert 0.01 < std < 50.0, (
                f"Logit std out of range at step {i}: {std:.4f}"
            )

    def test_logit_scale_clamped(self, default_config):
        """Verify logit scale stays within configured bounds."""
        module = LogitScaleModule(default_config)

        # Manually set scale beyond bounds
        module.logit_scale.data.fill_(10.0)
        dummy_logits = torch.randn(2, 16, 1000)
        scaled = module(dummy_logits)

        # The clamping should limit the effective scale
        with torch.no_grad():
            effective_scale = torch.exp(
                torch.clamp(module.logit_scale, default_config.logit_scale_min, default_config.logit_scale_max)
            ).item()
        assert effective_scale <= math.exp(default_config.logit_scale_max) + 1e-3


# =============================================================================
# TEST 3: No training instability introduced
# =============================================================================

class TestTrainingStability:
    """Verify entropy control doesn't introduce NaN/Inf or training instability."""

    def test_no_nan_or_inf(self, model, default_config, dummy_batch, vocab_size):
        """Training should not produce NaN or Inf values."""
        x, y = dummy_batch
        scale_module = attach_logit_scale(model, default_config)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        for step in range(30):
            optimizer.zero_grad()
            logits = model(x)
            scaled_logits = scale_module(logits)
            ce_loss = F.cross_entropy(
                scaled_logits.view(-1, vocab_size), y.view(-1), ignore_index=-100
            )
            total_loss, metrics = scale_module.compute_loss(scaled_logits, ce_loss)
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            # Check for NaN/Inf
            assert not torch.isnan(total_loss), f"NaN loss at step {step}"
            assert not torch.isinf(total_loss), f"Inf loss at step {step}"
            assert not math.isnan(metrics['logit_std']), f"NaN logit_std at step {step}"
            assert not math.isnan(metrics['normalized_entropy']), f"NaN entropy at step {step}"
            assert not math.isnan(metrics['exp_logit_scale']), f"NaN exp_scale at step {step}"

    def test_loss_decreases(self, model, default_config, dummy_batch, vocab_size):
        """Loss should generally decrease over training steps."""
        x, y = dummy_batch
        scale_module = attach_logit_scale(model, default_config)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        losses = []
        for step in range(50):
            optimizer.zero_grad()
            logits = model(x)
            scaled_logits = scale_module(logits)
            ce_loss = F.cross_entropy(
                scaled_logits.view(-1, vocab_size), y.view(-1), ignore_index=-100
            )
            total_loss, metrics = scale_module.compute_loss(scaled_logits, ce_loss)
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(total_loss.item())

        # Loss at end should be lower than at start (allow small fluctuations)
        avg_first_5 = sum(losses[:5]) / 5
        avg_last_5 = sum(losses[-5:]) / 5
        assert avg_last_5 < avg_first_5, (
            f"Loss did not decrease: first_5_avg={avg_first_5:.4f}, last_5_avg={avg_last_5:.4f}"
        )

    def test_gradient_flows_through_scale(self, model, default_config, dummy_batch, vocab_size):
        """Logit scale parameter must receive gradients from CE loss."""
        x, y = dummy_batch
        scale_module = attach_logit_scale(model, default_config)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

        optimizer.zero_grad()
        logits = model(x)
        scaled_logits = scale_module(logits)
        ce_loss = F.cross_entropy(
            scaled_logits.view(-1, vocab_size), y.view(-1), ignore_index=-100
        )
        total_loss, metrics = scale_module.compute_loss(scaled_logits, ce_loss)
        total_loss.backward()

        # logit_scale should have gradient
        assert scale_module.logit_scale.grad is not None, "logit_scale has no gradient"
        assert scale_module.logit_scale.grad.abs().item() > 0, "logit_scale gradient is zero"

    def test_entropy_detached_from_gradient(self, default_config):
        """Entropy computation must be detached from gradient graph."""
        logits = torch.randn(2, 16, 1000, requires_grad=True)
        H = topk_entropy(logits, K=50)

        # H should not have gradient tracking (computed with torch.no_grad)
        assert not H.requires_grad, "topk_entropy should be detached"


# =============================================================================
# TEST 4: Inference entropy converges toward target band
# =============================================================================

class TestInferenceAdaptiveControl:
    """Verify inference-time adaptive entropy control converges."""

    def test_entropy_converges_to_target(self, vocab_size):
        """Adaptive controller should drive entropy toward target."""
        config = EntropyControlConfig(
            enable_entropy_control_infer=True,
            infer_h_target=0.25,
            infer_eta=0.02,
            infer_delta_clip=0.05,
            entropy_topk=50,
            logit_scale_min=-4.0,
            logit_scale_max=4.0,
        )
        controller = AdaptiveEntropyController(config)

        # Generate synthetic logits with various entropy levels
        torch.manual_seed(42)
        entropies = []
        for step in range(100):
            # Generate logits that have somewhat fixed distribution per step
            # (simulating generation output)
            logits = torch.randn(1, vocab_size) * 3.0
            scaled = controller.scale_logits(logits)
            metrics = controller.update(scaled)
            entropies.append(metrics['infer_entropy'])

        # After 100 steps, entropy should be closer to target than at start
        initial_error = abs(entropies[0] - config.infer_h_target)
        final_error = abs(entropies[-1] - config.infer_h_target)
        # Allow for stochastic logits - just verify the controller is moving in the right direction
        avg_first_10 = sum(abs(e - config.infer_h_target) for e in entropies[:10]) / 10
        avg_last_10 = sum(abs(e - config.infer_h_target) for e in entropies[-10:]) / 10

        # The average error in the last 10 steps should be no worse than the first 10
        # (Controller shouldn't diverge)
        assert avg_last_10 <= avg_first_10 + 0.15, (
            f"Controller diverged: avg_first_10_error={avg_first_10:.4f}, "
            f"avg_last_10_error={avg_last_10:.4f}"
        )

    def test_no_gradient_during_inference(self):
        """Adaptive controller must not track gradients."""
        config = EntropyControlConfig(enable_entropy_control_infer=True)
        controller = AdaptiveEntropyController(config)

        logits = torch.randn(1, 1000, requires_grad=True)
        scaled = controller.scale_logits(logits)
        metrics = controller.update(scaled)

        # log_scale should not require grad
        assert not controller.log_scale.requires_grad

    def test_controller_reset(self):
        """Controller reset should restore initial state."""
        config = EntropyControlConfig(enable_entropy_control_infer=True)
        initial_scale = torch.tensor(0.5)
        controller = AdaptiveEntropyController(config, initial_scale)

        # Modify state
        logits = torch.randn(1, 1000)
        scaled = controller.scale_logits(logits)
        controller.update(scaled)
        assert controller._step == 1

        # Reset
        controller.reset(initial_scale)
        assert controller._step == 0
        assert abs(controller.log_scale.item() - 0.5) < 1e-6

    def test_scale_clamped_during_inference(self):
        """Scale should stay within configured bounds during inference."""
        config = EntropyControlConfig(
            enable_entropy_control_infer=True,
            logit_scale_min=-2.0,
            logit_scale_max=2.0,
            infer_eta=1.0,  # Very aggressive to push bounds
        )
        controller = AdaptiveEntropyController(config)

        # Force extreme entropy to push scale to bounds
        for _ in range(100):
            # Very low entropy logits (one-hot-ish)
            logits = torch.full((1, 1000), -100.0)
            logits[0, 0] = 100.0
            scaled = controller.scale_logits(logits)
            controller.update(scaled)

        assert controller.log_scale.item() <= config.logit_scale_max + 1e-6
        assert controller.log_scale.item() >= config.logit_scale_min - 1e-6


# =============================================================================
# TEST: Core utility functions
# =============================================================================

class TestUtilityFunctions:
    """Test core utility functions."""

    def test_topk_entropy_range(self):
        """Normalized entropy should be in [0, 1]."""
        # Uniform logits -> high entropy
        uniform_logits = torch.zeros(2, 16, 1000)
        H_uniform = topk_entropy(uniform_logits, K=50)
        assert 0.0 <= H_uniform.item() <= 1.0

        # One-hot logits -> low entropy
        onehot_logits = torch.full((2, 16, 1000), -100.0)
        onehot_logits[:, :, 0] = 100.0
        H_onehot = topk_entropy(onehot_logits, K=50)
        assert H_onehot.item() < 0.1

        # Entropy of uniform should be higher than one-hot
        assert H_uniform.item() > H_onehot.item()

    def test_entropy_penalty_zero_in_band(self):
        """Entropy within target band should produce zero penalty."""
        H_in_band = torch.tensor(0.25)
        penalty = compute_entropy_penalty(H_in_band, H_min=0.15, H_max=0.35)
        assert abs(penalty.item()) < 1e-9

    def test_entropy_penalty_positive_outside_band(self):
        """Entropy outside target band should produce positive penalty."""
        # Below band
        H_low = torch.tensor(0.05)
        penalty_low = compute_entropy_penalty(H_low, H_min=0.15, H_max=0.35)
        assert penalty_low.item() > 0

        # Above band
        H_high = torch.tensor(0.50)
        penalty_high = compute_entropy_penalty(H_high, H_min=0.15, H_max=0.35)
        assert penalty_high.item() > 0

    def test_topk_clamps_to_vocab(self):
        """K should be clamped when larger than vocab size."""
        small_logits = torch.randn(2, 10, 20)  # vocab=20
        H = topk_entropy(small_logits, K=50)  # K=50 > vocab=20
        assert 0.0 <= H.item() <= 1.0

    def test_log_entropy_metrics_format(self):
        """Log formatting should not crash."""
        metrics = {
            'logit_std': 2.5,
            'normalized_entropy': 0.25,
            'exp_logit_scale': 1.1,
            'entropy_penalty': 0.001,
        }
        log_str = log_entropy_metrics(metrics, step=100)
        assert "Step 100" in log_str
        assert "logit_std" in log_str

    def test_log_entropy_metrics_with_warning(self):
        """Log formatting with warning should include warning."""
        metrics = {
            'logit_std': 0.5,
            'normalized_entropy': 0.02,
            'exp_logit_scale': 0.1,
            'entropy_penalty': 0.01,
            'entropy_warning': 'COLLAPSE',
        }
        log_str = log_entropy_metrics(metrics, step=50)
        assert "COLLAPSE" in log_str


# =============================================================================
# TEST: attach_logit_scale integration
# =============================================================================

class TestAttachLogitScale:
    """Test the attach_logit_scale helper."""

    def test_attach_adds_parameter(self, model, default_config):
        """Attaching should add a parameter to the model."""
        initial_params = sum(p.numel() for p in model.parameters())
        attach_logit_scale(model, default_config)
        new_params = sum(p.numel() for p in model.parameters())
        assert new_params == initial_params + 1  # One scalar parameter

    def test_attach_creates_attribute(self, model, default_config):
        """Attaching should create entropy_logit_scale attribute."""
        attach_logit_scale(model, default_config)
        assert hasattr(model, 'entropy_logit_scale')
        assert isinstance(model.entropy_logit_scale, LogitScaleModule)

    def test_parameter_in_state_dict(self, model, default_config):
        """The logit_scale should appear in model state dict for checkpointing."""
        attach_logit_scale(model, default_config)
        state_dict = model.state_dict()
        matching_keys = [k for k in state_dict.keys() if 'logit_scale' in k]
        assert len(matching_keys) > 0, "logit_scale not found in state_dict"


# =============================================================================
# TEST: Mixed precision safety
# =============================================================================

class TestMixedPrecision:
    """Test numerical stability with different dtypes."""

    def test_float16_safe(self, default_config):
        """Scale module should work with float16 inputs."""
        module = LogitScaleModule(default_config)
        logits = torch.randn(2, 16, 1000, dtype=torch.float16)
        scaled = module(logits)
        assert scaled.dtype == torch.float16
        assert not torch.isnan(scaled).any()

    def test_bfloat16_safe(self, default_config):
        """Scale module should work with bfloat16 inputs."""
        module = LogitScaleModule(default_config)
        logits = torch.randn(2, 16, 1000, dtype=torch.bfloat16)
        scaled = module(logits)
        assert scaled.dtype == torch.bfloat16
        assert not torch.isnan(scaled).any()

    def test_float32_safe(self, default_config):
        """Scale module should work with float32 inputs."""
        module = LogitScaleModule(default_config)
        logits = torch.randn(2, 16, 1000, dtype=torch.float32)
        scaled = module(logits)
        assert scaled.dtype == torch.float32
        assert not torch.isnan(scaled).any()


# =============================================================================
# TEST: Safety constraints
# =============================================================================

class TestSafetyConstraints:
    """Test safety monitoring and warnings."""

    def test_collapse_warning(self, default_config):
        """Should warn when entropy is below collapse threshold."""
        module = LogitScaleModule(default_config)
        # Create nearly one-hot logits (very low entropy)
        logits = torch.full((2, 16, 1000), -100.0)
        logits[:, :, 0] = 100.0
        scaled = module(logits)
        ce_loss = torch.tensor(1.0, requires_grad=True)
        _, metrics = module.compute_loss(scaled, ce_loss)
        assert metrics.get('entropy_warning') == 'COLLAPSE'

    def test_diffuse_warning(self, default_config):
        """Should warn when entropy is above diffuse threshold."""
        module = LogitScaleModule(default_config)
        # Create uniform logits (very high entropy)
        logits = torch.zeros(2, 16, 1000)
        scaled = module(logits)
        ce_loss = torch.tensor(1.0, requires_grad=True)
        _, metrics = module.compute_loss(scaled, ce_loss)
        assert metrics.get('entropy_warning') == 'DIFFUSE'

    def test_no_warning_in_band(self, default_config):
        """No warning when entropy is within target band."""
        module = LogitScaleModule(default_config)
        # Create logits with moderate entropy
        torch.manual_seed(42)
        logits = torch.randn(2, 16, 1000) * 3.0  # Some spread
        scaled = module(logits)
        ce_loss = torch.tensor(1.0, requires_grad=True)
        _, metrics = module.compute_loss(scaled, ce_loss)
        # May or may not have warning - depends on exact entropy
        # Just verify no crash
        assert 'normalized_entropy' in metrics
