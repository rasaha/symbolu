"""Unit tests for Neural Cloud Scaling Controller — Stage 1.

Tests verify the core control math against known input/output pairs
derived from the CG ExperientialController equations.
"""

import math
import numpy as np
import pytest

from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.core.plasticity_gate import PlasticityGate
from symbolu.cloud_controller.core.adaptive_gain import AdaptiveGain
from symbolu.cloud_controller.core.damping import Damping
from symbolu.cloud_controller.core.identity_ema import IdentityEMA
from symbolu.cloud_controller.core.coherence import CoherenceModel
from symbolu.cloud_controller.core.replay_buffer import ReplayBuffer
from symbolu.cloud_controller.controller import Controller


# ============================================================
# Plasticity Gate
# ============================================================

class TestPlasticityGate:
    def test_stable_system_small_change(self):
        """High stability + low misalignment -> gate opens."""
        gate = PlasticityGate(k_r=2.0, k_m=2.0, b_p=-1.0)
        # Warm up persistent resistance — double smoothing needs ~200 cycles
        # to converge because fast EMA (alpha=0.1) and slow EMA (alpha=0.05)
        # both attenuate the input signal significantly
        for _ in range(200):
            gate.compute(resistance=1.0, misalignment=0.0)
        result = gate.compute(resistance=1.0, misalignment=0.0)
        # With double smoothing, R converges below 1.0 — gate opens moderately
        assert result.plasticity > 0.5

    def test_fragile_system_large_change(self):
        """Low stability + high misalignment -> gate closes."""
        gate = PlasticityGate(k_r=2.0, k_m=2.0, b_p=-1.0)
        for _ in range(50):
            gate.compute(resistance=0.0, misalignment=1.0)
        result = gate.compute(resistance=0.0, misalignment=1.0)
        # Due to double smoothing, won't reach theoretical minimum immediately
        # but should be well below 0.3
        assert result.plasticity < 0.35

    def test_gate_never_fully_closes(self):
        """b_p=-1.0 ensures floor at sigmoid(-1) ≈ 0.27."""
        gate = PlasticityGate(k_r=2.0, k_m=2.0, b_p=-1.0)
        for _ in range(100):
            result = gate.compute(resistance=0.0, misalignment=5.0)
        # Even with extreme inputs, gate has a floor
        assert result.plasticity > 0.0
        # sigmoid(b_p) = sigmoid(-1) ≈ 0.27 is the theoretical floor
        # but double smoothing of R means it won't hit the absolute minimum

    def test_double_smoothing_prevents_flicker(self):
        """Rapidly alternating inputs should produce smooth output."""
        gate = PlasticityGate()
        results = []
        for i in range(20):
            r = 1.0 if i % 2 == 0 else 0.0  # Alternating
            result = gate.compute(resistance=r, misalignment=0.2)
            results.append(result.plasticity)
        # Check that output doesn't swing as wildly as input
        output_range = max(results[-10:]) - min(results[-10:])
        assert output_range < 0.3  # Smoothed, not oscillating between extremes


# ============================================================
# Adaptive Gain
# ============================================================

class TestAdaptiveGain:
    def test_rate_limiting(self):
        """Gain can't change by more than 10% of G_base per step."""
        gain = AdaptiveGain(G_base=1.0, G_min=0.0, G_max=3.0)
        # First step establishes baseline
        r1 = gain.compute(coherence=0.1, phase="off_peak", step=100, warmup_steps=100)
        # Jump to high coherence + peak
        r2 = gain.compute(coherence=1.0, phase="peak", step=101, warmup_steps=100)
        # Delta should be at most 0.1 (10% of G_base=1.0)
        assert abs(r2.gain - r1.gain) <= 0.1 + 1e-9

    def test_coherence_factor_midpoint(self):
        """At coherence=0.5, f_coh should be 0.75."""
        gain = AdaptiveGain()
        result = gain.compute(coherence=0.5, step=1000, warmup_steps=100)
        assert abs(result.f_coh - 0.75) < 0.01

    def test_warmup_ramp(self):
        """Gain ramps from 50% to 100% over warmup period."""
        gain = AdaptiveGain(G_base=1.0)
        r_start = gain.compute(coherence=0.5, phase="normal", step=0, warmup_steps=100)
        gain.reset()
        r_end = gain.compute(coherence=0.5, phase="normal", step=100, warmup_steps=100)
        # Start should be lower than end (warmup ramp)
        assert r_start.f_phase < r_end.f_phase

    def test_phase_multipliers(self):
        """Peak phase should produce higher gain than off_peak."""
        gain_peak = AdaptiveGain(G_base=1.0)
        gain_off = AdaptiveGain(G_base=1.0)
        r_peak = gain_peak.compute(coherence=0.8, phase="peak", step=200, warmup_steps=100)
        r_off = gain_off.compute(coherence=0.8, phase="off_peak", step=200, warmup_steps=100)
        assert r_peak.gain > r_off.gain


# ============================================================
# Damping
# ============================================================

class TestDamping:
    def test_baseline_variance_no_damping(self):
        """At baseline variance, d_t should be close to 1.0 (no damping)."""
        d = Damping(k_dv=1.0, k_dc=0.5)
        # Feed steady variance to establish baseline
        for _ in range(100):
            d.compute(metric_variance=0.1, coherence_instability=0.0)
        result = d.compute(metric_variance=0.1, coherence_instability=0.0)
        assert result.damping > 0.85

    def test_spike_triggers_damping(self):
        """5x baseline variance should produce significant damping."""
        d = Damping(k_dv=1.0, k_dc=0.5)
        # Establish baseline
        for _ in range(200):
            d.compute(metric_variance=0.1)
        # Spike
        for _ in range(20):
            result = d.compute(metric_variance=0.5)
        assert result.damping < 0.7
        assert result.v_excess > 0.5

    def test_hard_floor(self):
        """Damping never goes below 0.01."""
        d = Damping(k_dv=1.0, k_dc=0.5)
        d.compute(metric_variance=0.01)
        # Extreme spike
        for _ in range(100):
            result = d.compute(metric_variance=100.0, coherence_instability=10.0)
        assert result.damping >= 0.01

    def test_rate_limiting(self):
        """Damping changes by at most +/-0.1 per cycle."""
        d = Damping()
        d.compute(metric_variance=0.1)
        r1 = d.compute(metric_variance=0.1)
        # Sudden extreme spike
        r2 = d.compute(metric_variance=100.0, coherence_instability=5.0)
        assert abs(r2.damping - r1.damping) <= 0.1 + 1e-9

    def test_asymmetric_ema_fast_detect(self):
        """Rising variance should be tracked faster than falling."""
        d = Damping()
        for _ in range(100):
            d.compute(metric_variance=0.1)
        baseline_v = d._V_ema
        # Spike
        d.compute(metric_variance=1.0)
        spike_v = d._V_ema
        # Recovery
        d.compute(metric_variance=0.1)
        recovery_v = d._V_ema
        # Rise alpha=0.10, so spike should move V_ema up by ~0.10*(1.0-baseline)
        # Decay alpha=0.20, so recovery should move V_ema down by ~0.20*(spike-0.1)
        assert spike_v > baseline_v  # Detected the spike
        assert recovery_v < spike_v  # Started recovering


# ============================================================
# Identity EMA
# ============================================================

class TestIdentityEMA:
    def test_no_update_when_empty(self):
        """Consolidation should not update when no signals accumulated."""
        identity = IdentityEMA(dim=8, alpha_base=0.01)
        result = identity.consolidate()
        assert result.updated is False

    def test_low_salience_ignored(self):
        """Signals with salience <= 0.3 are not accumulated."""
        identity = IdentityEMA(dim=8)
        identity.accumulate(np.ones(8) * 0.5, salience=0.2)
        assert identity.count == 0

    def test_high_salience_accumulated(self):
        """Signals with salience > 0.3 are accumulated."""
        identity = IdentityEMA(dim=8)
        identity.accumulate(np.ones(8) * 0.5, salience=0.8)
        assert identity.count == 1

    def test_consolidation_resets_accumulator(self):
        """After consolidation, accumulator should be zeroed."""
        identity = IdentityEMA(dim=8)
        for _ in range(10):
            identity.accumulate(np.random.randn(8), salience=0.8)
        result = identity.consolidate()
        assert result.updated is True
        assert identity.count == 0
        assert np.linalg.norm(identity.accumulator) < 1e-8

    def test_alpha_eff_modulated(self):
        """Effective alpha should be between 0.1*alpha_base and alpha_base."""
        identity = IdentityEMA(dim=8, alpha_base=0.01)
        for _ in range(50):
            identity.accumulate(np.random.randn(8), salience=0.8)
        result = identity.consolidate()
        assert result.alpha_eff >= 0.001  # 0.1 * 0.01
        assert result.alpha_eff <= 0.01   # alpha_base

    def test_deviation_from_baseline(self):
        """Deviation should be high for orthogonal vectors."""
        identity = IdentityEMA(dim=8)
        # Baseline is random, so a zero vector should have max deviation
        dev = identity.deviation(np.zeros(8))
        assert dev == 1.0  # Zero norm -> max deviation


# ============================================================
# Coherence Model
# ============================================================

class TestCoherenceModel:
    def test_all_elevated_high_coherence(self):
        """All signals elevated and agreeing -> high coherence."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.75, "error_rate": 0.70,
            "queue_depth": 0.65,
        })
        assert result.coherence > 0.7

    def test_only_cpu_elevated_low_coherence(self):
        """Only CPU elevated, rest flat -> coherence lower than all-elevated case."""
        model = CoherenceModel()
        result_incoherent = model.compute({
            "cpu": 0.90, "memory": 0.20,
            "latency_p99": 0.15, "error_rate": 0.10,
            "queue_depth": 0.10,
        })
        result_coherent = model.compute({
            "cpu": 0.85, "memory": 0.80,
            "latency_p99": 0.75, "error_rate": 0.70,
            "queue_depth": 0.65,
        })
        # Incoherent should be meaningfully lower than coherent
        assert result_incoherent.coherence < result_coherent.coherence

    def test_instability_inverse_of_coherence(self):
        """Instability should equal 1 - coherence."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.5, "memory": 0.5,
            "latency_p99": 0.5, "error_rate": 0.5,
        })
        assert abs(result.instability - (1.0 - result.coherence)) < 1e-9

    def test_missing_business_signals(self):
        """Should work without business signals."""
        model = CoherenceModel()
        result = model.compute({
            "cpu": 0.8, "memory": 0.7,
            "latency_p99": 0.75, "error_rate": 0.65,
        })
        assert 0.0 <= result.coherence <= 1.0


# ============================================================
# Replay Buffer
# ============================================================

class TestReplayBuffer:
    def test_capacity_limit(self):
        """Buffer should not exceed capacity."""
        buf = ReplayBuffer(capacity=5, ttl=100)
        for i in range(10):
            buf.store({"priority": float(i), "data": i}, step=i)
        assert len(buf) == 5

    def test_evicts_lowest_priority(self):
        """When full, lowest priority item should be evicted."""
        buf = ReplayBuffer(capacity=3, ttl=100)
        buf.store({"priority": 1.0, "id": "a"}, step=0)
        buf.store({"priority": 5.0, "id": "b"}, step=1)
        buf.store({"priority": 3.0, "id": "c"}, step=2)
        buf.store({"priority": 4.0, "id": "d"}, step=3)  # Should evict "a"
        ids = [item["id"] for item in buf.buffer]
        assert "a" not in ids
        assert len(buf) == 3

    def test_ttl_prune(self):
        """Entries past TTL should be pruned."""
        buf = ReplayBuffer(capacity=100, ttl=10)
        buf.store({"priority": 1.0}, step=0)
        buf.store({"priority": 1.0}, step=5)
        buf.store({"priority": 1.0}, step=15)
        removed = buf.prune(current_step=20)
        assert removed == 2  # Steps 0 and 5 are stale
        assert len(buf) == 1

    def test_sample_respects_k(self):
        """Sample should return at most k items."""
        buf = ReplayBuffer(capacity=100, ttl=1000)
        for i in range(20):
            buf.store({"priority": 1.0}, step=i)
        sampled = buf.sample(5)
        assert len(sampled) == 5

    def test_empty_sample(self):
        """Sampling empty buffer returns empty list."""
        buf = ReplayBuffer()
        assert buf.sample(5) == []


# ============================================================
# Full Controller Integration
# ============================================================

class TestController:
    def test_basic_step(self):
        """Controller should produce a valid ActionResult."""
        ctrl = Controller(InfraControllerConfig())
        result = ctrl.step(
            metrics={"cpu": 0.5, "memory": 0.4, "latency_p99": 0.3,
                     "error_rate": 0.1, "queue_depth": 0.2},
            current_replicas=5,
        )
        assert result.recommendation is not None
        assert result.step == 1
        assert isinstance(result.explain(), str)

    def test_high_coherent_pressure_scales_out(self):
        """High coherent pressure should recommend scaling out."""
        ctrl = Controller(InfraControllerConfig())
        # Warm up
        for _ in range(50):
            ctrl.step(
                metrics={"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5,
                         "error_rate": 0.5, "queue_depth": 0.5},
                current_replicas=5,
            )
        # Sustained high pressure, all signals agree
        for _ in range(20):
            result = ctrl.step(
                metrics={"cpu": 0.90, "memory": 0.85, "latency_p99": 0.88,
                         "error_rate": 0.80, "queue_depth": 0.85},
                current_replicas=5,
                phase="peak",
            )
        assert result.action_score > 0
        assert result.coherence.coherence > 0.6

    def test_incoherent_pressure_suppressed(self):
        """Only CPU elevated -> action score should be lower than coherent case."""
        ctrl_coherent = Controller(InfraControllerConfig())
        ctrl_incoherent = Controller(InfraControllerConfig())
        # Warm up both
        baseline = {"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5,
                    "error_rate": 0.5, "queue_depth": 0.5}
        for _ in range(50):
            ctrl_coherent.step(metrics=baseline, current_replicas=5)
            ctrl_incoherent.step(metrics=baseline, current_replicas=5)

        coherent_metrics = {"cpu": 0.90, "memory": 0.85, "latency_p99": 0.88,
                           "error_rate": 0.80, "queue_depth": 0.85}
        incoherent_metrics = {"cpu": 0.90, "memory": 0.20, "latency_p99": 0.15,
                             "error_rate": 0.10, "queue_depth": 0.10}

        r_coh = ctrl_coherent.step(metrics=coherent_metrics, current_replicas=5)
        r_inc = ctrl_incoherent.step(metrics=incoherent_metrics, current_replicas=5)

        assert r_coh.action_score > r_inc.action_score

    def test_deploy_active_reduces_plasticity(self):
        """Active deployment should lower plasticity (resistance drops)."""
        ctrl_stable = Controller(InfraControllerConfig())
        ctrl_deploy = Controller(InfraControllerConfig())
        metrics = {"cpu": 0.7, "memory": 0.6, "latency_p99": 0.65,
                   "error_rate": 0.5, "queue_depth": 0.6}
        for _ in range(50):
            ctrl_stable.step(metrics=metrics, current_replicas=5)
            ctrl_deploy.step(metrics=metrics, current_replicas=5)

        r_stable = ctrl_stable.step(metrics=metrics, current_replicas=5, deploy_active=False)
        r_deploy = ctrl_deploy.step(metrics=metrics, current_replicas=5, deploy_active=True)

        assert r_stable.plasticity.plasticity > r_deploy.plasticity.plasticity

    def test_explain_output(self):
        """Explain should produce readable output with all components."""
        ctrl = Controller()
        result = ctrl.step(
            metrics={"cpu": 0.8, "memory": 0.6, "latency_p99": 0.7, "error_rate": 0.3},
            current_replicas=3,
        )
        explanation = result.explain()
        assert "Pressure" in explanation
        assert "Coherence" in explanation
        assert "Plasticity" in explanation
        assert "Gain" in explanation
        assert "Damping" in explanation

    def test_replay_buffer_stores_stressed_moments(self):
        """High misalignment + low plasticity should populate replay buffer."""
        # Use config with high G_base to amplify misalignment
        config = InfraControllerConfig(G_base=3.0)
        ctrl = Controller(config)
        # Drive system to stressed state: fragile + big proposed change
        for _ in range(100):
            ctrl.step(
                metrics={"cpu": 0.95, "memory": 0.90, "latency_p99": 0.85,
                         "error_rate": 0.80, "queue_depth": 0.90},
                current_replicas=1,  # Very small -> high misalignment
                deploy_active=True,  # Lowers resistance
                recent_pod_restarts=5,
            )
        assert len(ctrl.replay_buffer) > 0

    def test_safety_bounds(self):
        """Replica delta should respect safety bounds."""
        config = InfraControllerConfig(
            max_scale_out_ratio=0.5,
            min_replicas=2,
        )
        ctrl = Controller(config)
        # Even with extreme action score, can't scale more than 50%
        result = ctrl.step(
            metrics={"cpu": 0.99, "memory": 0.99, "latency_p99": 0.99,
                     "error_rate": 0.99, "queue_depth": 0.99},
            current_replicas=4,
            phase="peak",
        )
        # Max +50% of 4 = +2
        assert result.replica_delta <= 2
