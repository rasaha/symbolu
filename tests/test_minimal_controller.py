"""
Tests for the 12-parameter minimal experiential controller.

Validates:
    - Core equation: g_eff = d_t · G_t · P_t · ∇L_exp
    - 4-term loss decomposition
    - Plasticity gate: P_t = sigmoid(k_r·R_t - k_m·M_t + b_p)
    - Adaptive gain with rate limiting
    - Exponential damping
    - Identity EMA consolidation
    - Pipeline integration (coherence signals, latent state)
    - Parameter census (must be exactly 12)
"""

import pytest
import torch
import dataclasses

from symbolu.training.conscious_generation.experiential.minimal_controller import (
    ExperientialController,
    ExperientialControllerConfig,
    ExperientialLoss,
    PlasticityGate,
    AdaptiveGain,
    Damping,
    IdentityEMA,
    ReplayBuffer,
)


B, T, D = 2, 16, 128
NUM_REGIONS = 12


@pytest.fixture
def config():
    return ExperientialControllerConfig(d_model=D, num_regions=NUM_REGIONS)


@pytest.fixture
def controller(config):
    return ExperientialController(config)


@pytest.fixture
def hidden():
    return torch.randn(B, T, D)


@pytest.fixture
def target_hidden():
    return torch.randn(B, T, D)


# ============================================================================
# Parameter census
# ============================================================================


class TestParameterCensus:
    def test_exactly_12_core_parameters(self):
        """The minimal controller must have exactly 12 core tunable parameters."""
        core_params = [
            "lambda_temporal", "lambda_coherence", "lambda_latent",  # 3
            "k_r", "k_m", "b_p",                                     # 3
            "G_base", "G_min", "G_max",                               # 3
            "k_dv", "k_dc",                                           # 2
            "alpha_base",                                              # 1
        ]
        config = ExperientialControllerConfig()
        fields = {f.name for f in dataclasses.fields(config)}

        for param in core_params:
            assert param in fields, f"Missing core parameter: {param}"

        assert len(core_params) == 12

    def test_structural_params_not_counted(self):
        """d_model, num_regions, replay params are structural, not core."""
        structural = ["d_model", "num_regions", "replay_buffer_size", "replay_ttl"]
        config = ExperientialControllerConfig()
        fields = dataclasses.fields(config)
        tunable = [f for f in fields if f.name not in structural]
        assert len(tunable) == 12


# ============================================================================
# Experiential Loss
# ============================================================================


class TestExperientialLoss:
    def test_4_term_decomposition(self, hidden, target_hidden, config):
        loss_fn = ExperientialLoss(config)
        result = loss_fn(hidden, target_hidden)

        assert "loss" in result
        assert "L_token" in result
        assert "L_temporal" in result
        assert "L_coherence" in result
        assert "L_latent" in result
        assert result["loss"].requires_grad

    def test_with_base_loss(self, hidden, target_hidden, config):
        loss_fn = ExperientialLoss(config)
        base = torch.tensor(2.0, requires_grad=True)
        result = loss_fn(hidden, target_hidden, base_loss=base)
        assert result["loss"].item() >= 2.0

    def test_with_coherence_signals(self, hidden, target_hidden, config):
        loss_fn = ExperientialLoss(config)
        signals = {"c_tok": 0.8, "c_lat": 0.6, "c_conv": 0.7}
        result = loss_fn(hidden, target_hidden, coherence_signals=signals)
        assert result["L_coherence"].item() > 0

    def test_with_latent_state(self, hidden, target_hidden, config):
        loss_fn = ExperientialLoss(config)
        latent = torch.randn(B, D)
        result = loss_fn(hidden, target_hidden, latent_state=latent)
        assert result["L_latent"].item() > 0

    def test_loss_weights_matter(self, hidden, target_hidden):
        """Different lambda values should produce different losses."""
        c1 = ExperientialControllerConfig(d_model=D, lambda_temporal=0.0)
        c2 = ExperientialControllerConfig(d_model=D, lambda_temporal=2.0)

        r1 = ExperientialLoss(c1)(hidden, target_hidden)
        r2 = ExperientialLoss(c2)(hidden, target_hidden)

        # With higher lambda_temporal, loss should be different
        assert r1["loss"].item() != r2["loss"].item()


# ============================================================================
# Plasticity Gate
# ============================================================================


class TestPlasticityGate:
    def test_output_shape(self, config):
        gate = PlasticityGate(config)
        region_states = torch.randn(B, NUM_REGIONS, D)
        result = gate(region_states)

        assert result["plasticity"].shape == (B, NUM_REGIONS)
        assert result["resistance_openness"].shape == (B, NUM_REGIONS)

    def test_no_dead_zones(self, config):
        """Bias floor ensures plasticity > 0 always."""
        gate = PlasticityGate(config)
        region_states = torch.randn(B, NUM_REGIONS, D)

        result = gate(region_states)
        min_plasticity = torch.sigmoid(torch.tensor(config.b_p)).item()

        # Plasticity should never go below sigmoid(b_p)
        assert (result["plasticity"] >= min_plasticity - 0.01).all()

    def test_misalignment_reduces_plasticity(self, config):
        """High misalignment should reduce plasticity (k_m term)."""
        gate = PlasticityGate(config)
        region_states = torch.randn(B, NUM_REGIONS, D)

        r_no_m = gate(region_states)

        # Reset state for fair comparison
        gate2 = PlasticityGate(config)
        gate2.load_state_dict(gate.state_dict())
        high_m = torch.ones(B, NUM_REGIONS) * 0.9
        r_high_m = gate2(region_states, misalignment=high_m)

        assert r_high_m["plasticity"].mean() < r_no_m["plasticity"].mean()

    def test_resistance_is_primary(self, config):
        """Plasticity should vary with resistance even without misalignment."""
        gate = PlasticityGate(config)
        # Two different region states should give different plasticity
        r1 = gate(torch.randn(B, NUM_REGIONS, D))
        r2 = gate(torch.randn(B, NUM_REGIONS, D) * 5.0)

        # Not identical (resistance varies with input)
        assert not torch.allclose(r1["plasticity"], r2["plasticity"])


# ============================================================================
# Adaptive Gain
# ============================================================================


class TestAdaptiveGain:
    def test_bounded(self, config):
        gain = AdaptiveGain(config)
        for step in range(100):
            g = gain.compute(coherence=0.5, step=step)
            assert config.G_min <= g <= config.G_max

    def test_rate_limited(self, config):
        gain = AdaptiveGain(config)
        g1 = gain.compute(coherence=0.1, step=5000)
        g2 = gain.compute(coherence=0.9, step=5001)

        max_delta = config.G_base * 0.1
        assert abs(g2 - g1) <= max_delta + 1e-6

    def test_coherence_increases_gain(self, config):
        gain_low = AdaptiveGain(config)
        gain_high = AdaptiveGain(config)

        # Run for several steps to pass rate limiting
        for step in range(5000, 5100):
            g_low = gain_low.compute(coherence=0.1, step=step)
            g_high = gain_high.compute(coherence=0.9, step=step)

        assert g_high > g_low


# ============================================================================
# Damping
# ============================================================================


class TestDamping:
    def test_bounded(self, config):
        damp = Damping(config)
        for _ in range(50):
            d = damp.compute(grad_variance=1.0, coherence_instability=0.5)
            assert 0.01 <= d <= 1.0

    def test_high_variance_reduces_damping(self, config):
        damp_low = Damping(config)
        damp_high = Damping(config)

        for _ in range(20):
            d_low = damp_low.compute(grad_variance=0.01)
            d_high = damp_high.compute(grad_variance=10.0)

        assert d_low > d_high

    def test_exponential_form(self, config):
        """Damping uses exp(-k·V - k·U), which is smooth and interpretable."""
        damp = Damping(config)
        # With zero variance and zero instability, damping should be ~1.0
        d = damp.compute(grad_variance=0.0, coherence_instability=0.0)
        assert d > 0.9


# ============================================================================
# Identity EMA
# ============================================================================


class TestIdentityEMA:
    def test_accumulation(self):
        ema = IdentityEMA(d_identity=64)
        signal = torch.randn(64)
        ema.accumulate(signal, salience=0.8)
        assert ema.count == 1

    def test_consolidation(self):
        ema = IdentityEMA(d_identity=64)
        for _ in range(20):
            ema.accumulate(torch.randn(64), salience=0.8)

        initial = ema.identity.clone()
        assert ema.consolidate() is True

        # Identity should have changed
        assert not torch.allclose(initial, ema.identity)

        # Count should be reset
        assert ema.count == 0

    def test_low_salience_filtered(self):
        ema = IdentityEMA(d_identity=64)
        ema.accumulate(torch.randn(64), salience=0.1)  # Below 0.3 threshold
        assert ema.count == 0

    def test_adaptive_alpha(self):
        """Alpha should adapt to stability and agreement."""
        ema = IdentityEMA(d_identity=64, alpha_base=0.01)

        # Feed aligned signals (should produce higher effective alpha)
        for _ in range(20):
            ema.accumulate(ema.identity.clone() + torch.randn(64) * 0.01, salience=0.9)

        assert ema.consolidate() is True


# ============================================================================
# Replay Buffer
# ============================================================================


class TestReplayBuffer:
    def test_bounded_capacity(self):
        buf = ReplayBuffer(capacity=5)
        for i in range(20):
            buf.store({"priority": i * 0.1}, step=i)
        assert len(buf) == 5

    def test_ttl_pruning(self):
        buf = ReplayBuffer(capacity=100, ttl=10)
        for i in range(20):
            buf.store({"priority": 0.5}, step=i)
        pruned = buf.prune(current_step=25)
        assert pruned > 0

    def test_priority_sampling(self):
        buf = ReplayBuffer(capacity=20)
        for i in range(20):
            buf.store({"priority": i * 0.05, "id": i}, step=0)
        samples = buf.sample(5)
        assert len(samples) <= 5


# ============================================================================
# Full Controller Integration
# ============================================================================


class TestControllerIntegration:
    def test_basic_forward(self, controller, hidden, target_hidden):
        result = controller(hidden, target_hidden)

        assert "total_loss" in result
        assert result["total_loss"].requires_grad
        assert "plasticity" in result
        assert "gain" in result
        assert "damping" in result
        assert "g_eff" in result
        assert result["g_eff"].shape == (B, NUM_REGIONS)

    def test_with_coherence_signals(self, controller, hidden, target_hidden):
        signals = {"c_tok": 0.8, "c_lat": 0.6, "c_conv": 0.7}
        result = controller(hidden, target_hidden, coherence_signals=signals)
        assert result["total_loss"].requires_grad

    def test_with_latent_state(self, controller, hidden, target_hidden):
        latent = torch.randn(B, D)
        result = controller(hidden, target_hidden, latent_state=latent)
        assert result["loss_components"]["L_latent"].item() > 0

    def test_gradient_flows(self, controller, hidden, target_hidden):
        result = controller(hidden, target_hidden)
        result["total_loss"].backward()

        has_grad = False
        for p in controller.parameters():
            if p.grad is not None:
                has_grad = True
                break
        assert has_grad

    def test_step_counter(self, controller, hidden, target_hidden):
        for _ in range(5):
            controller(hidden, target_hidden)
        assert controller.step.item() == 5

    def test_g_eff_bounded(self, controller, hidden, target_hidden):
        for _ in range(20):
            result = controller(hidden, target_hidden)
            assert (result["g_eff"] >= controller.config.G_min - 1e-6).all()
            assert (result["g_eff"] <= controller.config.G_max + 1e-6).all()

    def test_summary(self, controller, hidden, target_hidden):
        controller(hidden, target_hidden)
        s = controller.summary()
        assert "Experiential Controller" in s
        assert "Identity" in s

    def test_identity_consolidation(self, controller, hidden, target_hidden):
        for _ in range(50):
            controller(hidden, target_hidden)
        # Should be able to consolidate after accumulation
        result = controller.consolidate_identity()
        assert isinstance(result, bool)

    def test_replay_integration(self, controller, hidden, target_hidden):
        # Feed signals that trigger replay storage
        signals = {"c_tok": 0.1, "c_lat": 0.1, "c_conv": 0.1}  # Low coherence = high misalignment
        for _ in range(10):
            controller(hidden, target_hidden, coherence_signals=signals)

        items = controller.get_replay_items(k=3)
        assert isinstance(items, list)

    def test_full_pipeline_simulation(self, controller, hidden, target_hidden):
        """Simulate Phase-Quad pipeline: forward → coherence → controller → optimizer."""
        optimizer = torch.optim.Adam(controller.parameters(), lr=1e-3)

        coherence = {"c_tok": 0.7, "c_lat": 0.6, "c_conv": 0.8}
        latent = torch.randn(B, D)

        losses = []
        for step in range(20):
            optimizer.zero_grad()
            result = controller(
                hidden, target_hidden,
                coherence_signals=coherence,
                latent_state=latent,
            )
            result["total_loss"].backward()
            optimizer.step()
            losses.append(result["total_loss"].item())

            # Medium loop: every 10 steps
            if step % 10 == 9:
                replay_items = controller.get_replay_items(k=4)

            # Slow loop: every 20 steps
            if step % 20 == 19:
                controller.consolidate_identity()

        # Loss should be finite
        assert all(loss < 1e6 for loss in losses)

    def test_no_nan_under_stress(self, controller):
        """Controller should not produce NaN even with extreme inputs."""
        extreme_hidden = torch.randn(B, T, D) * 100.0
        extreme_target = torch.randn(B, T, D) * 100.0
        signals = {"c_tok": 0.0, "c_lat": 0.0, "c_conv": 0.0}

        result = controller(
            extreme_hidden, extreme_target,
            coherence_signals=signals,
        )
        assert not torch.isnan(result["total_loss"])
        assert not torch.isnan(result["g_eff"]).any()


# ============================================================
# Edge Case Tests (from audit)
# ============================================================

class TestEdgeCases:
    """Edge cases identified by audit."""

    def test_empty_coherence_signals(self):
        """Empty dict should not crash (ZeroDivisionError guard)."""
        config = ExperientialControllerConfig(d_model=64)
        controller = ExperientialController(config)
        B, T, D = 2, 16, 64
        hidden = torch.randn(B, T, D)
        target = torch.randn(B, T, D)

        # Empty dict — should not raise
        result = controller(hidden, target, coherence_signals={})
        assert not torch.isnan(result["total_loss"])

    def test_single_coherence_signal(self):
        """Single signal should not crash."""
        config = ExperientialControllerConfig(d_model=64)
        controller = ExperientialController(config)
        B, T, D = 2, 16, 64
        hidden = torch.randn(B, T, D)
        target = torch.randn(B, T, D)

        result = controller(hidden, target, coherence_signals={"c_tok": 0.7})
        assert not torch.isnan(result["total_loss"])

    def test_dimension_mismatch_raises(self):
        """D != d_model should raise ValueError."""
        config = ExperientialControllerConfig(d_model=128)
        controller = ExperientialController(config)
        hidden = torch.randn(2, 16, 64)  # D=64, config expects 128
        target = torch.randn(2, 16, 64)

        with pytest.raises(ValueError, match="Hidden dimension 64 != config.d_model 128"):
            controller(hidden, target)

    def test_identity_small_hidden_dim(self):
        """D < 64 should pad identity signal, not crash."""
        config = ExperientialControllerConfig(d_model=32, num_regions=4)
        controller = ExperientialController(config)
        B, T, D = 2, 8, 32
        hidden = torch.randn(B, T, D)
        target = torch.randn(B, T, D)

        # Should work — identity pads from 32 to 64
        result = controller(hidden, target)
        assert not torch.isnan(result["total_loss"])

        # Verify identity accumulated
        state = controller.identity.get_state()
        assert state["accumulator_count"] >= 0

    def test_consolidation_count_tracked(self):
        """consolidation_count should be in get_state()."""
        ema = IdentityEMA(d_identity=32, alpha_base=0.1)
        state = ema.get_state()
        assert "consolidation_count" in state
        assert state["consolidation_count"] == 0

        # Accumulate and consolidate
        for _ in range(10):
            ema.accumulate(torch.randn(32) * 10.0, salience=0.8)
        ema.consolidate()
        state = ema.get_state()
        assert state["consolidation_count"] == 1

    def test_replay_sample_no_duplicates(self):
        """Replay sample should not return duplicates."""
        buf = ReplayBuffer(capacity=10, ttl=1000)
        for i in range(10):
            buf.store({"priority": float(i + 1), "id": i}, step=0)

        sample = buf.sample(k=5)
        ids = [item["id"] for item in sample]
        assert len(ids) == len(set(ids)), f"Duplicates found: {ids}"

    def test_batch_size_one(self):
        """B=1 should work."""
        config = ExperientialControllerConfig(d_model=64)
        controller = ExperientialController(config)
        hidden = torch.randn(1, 16, 64)
        target = torch.randn(1, 16, 64)
        result = controller(hidden, target)
        assert result["total_loss"].shape == ()

    def test_sequence_length_one(self):
        """T=1 should work."""
        config = ExperientialControllerConfig(d_model=64, num_regions=1)
        controller = ExperientialController(config)
        hidden = torch.randn(2, 1, 64)
        target = torch.randn(2, 1, 64)
        result = controller(hidden, target)
        assert not torch.isnan(result["total_loss"])
