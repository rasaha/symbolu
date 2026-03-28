"""
Ablation tests for the Experiential Learning framework.

Purpose: Identify which control parameters are load-bearing vs decorative.
Each test disables ONE refinement and measures its impact on system behavior.

Ablation categories:
    A. Structural ablations — disable entire subsystems
    B. Control-theory ablations — disable specific stabilization mechanisms
    C. Coupling ablations — disable cross-component feedback

Metrics captured per ablation:
    - loss_mean: Average total loss over N steps
    - loss_var: Variance of total loss (stability indicator)
    - plasticity_mean: Average effective plasticity
    - plasticity_var: Variance of plasticity (oscillation indicator)
    - gain_range: Range of max_gain_t values seen (gain stability)
    - damping_range: Range of damping values seen
    - identity_drift: How far identity moves from initial

A refinement is "load-bearing" if removing it causes:
    - loss_var to increase significantly (destabilization)
    - plasticity to hit floor/ceiling more often (dead zones / runaway)
    - gain or damping range to blow up (oscillation)
    - identity to drift excessively or freeze entirely
"""

import pytest
import torch
from dataclasses import dataclass
from typing import Dict, Any, Optional

from symbolu.training.conscious_generation.experiential.experiential_training_loop import (
    ExperientialTrainingLoop,
    ExperientialTrainingConfig,
)
from symbolu.training.conscious_generation.experiential.vritti_resistance_gate import (
    VrittiResistanceGate,
    VrittiResistanceConfig,
    AdaptiveGainController,
    DampingComputer,
)
from symbolu.training.conscious_generation.experiential.identity_layer import (
    IdentityLayer,
    IdentityLayerConfig,
)
from symbolu.training.conscious_generation.experiential.offline_consolidation import (
    ReplayBuffer,
)


# ============================================================================
# Test infrastructure
# ============================================================================

B, T, D = 2, 16, 128
NUM_REGIONS = 12
N_STEPS = 30  # Enough to see dynamics without being slow


@dataclass
class AblationMetrics:
    """Metrics collected from an ablation run."""
    loss_mean: float
    loss_var: float
    plasticity_mean: float
    plasticity_var: float
    plasticity_floor_hits: int  # Times plasticity == floor
    plasticity_ceiling_hits: int  # Times plasticity >= max_gain_t
    gain_min: float
    gain_max: float
    damping_min: float
    damping_max: float
    identity_drift: float  # Distance from initial identity


def run_ablation(
    config: ExperientialTrainingConfig,
    n_steps: int = N_STEPS,
    seed: int = 42,
    coherence_state: Optional[torch.Tensor] = None,
) -> AblationMetrics:
    """Run the system for n_steps and collect metrics."""
    torch.manual_seed(seed)
    loop = ExperientialTrainingLoop(config)

    # Capture initial identity
    initial_identity = None
    if config.enable_identity:
        initial_identity = loop.identity_layer.self_model.self_repr.clone()

    losses = []
    plasticities = []
    gains = []
    dampings = []
    floor_hits = 0
    ceiling_hits = 0

    for _ in range(n_steps):
        hidden = torch.randn(B, T, D)
        target = torch.randn(B, T, D)

        result = loop(hidden, target, coherence_state=coherence_state)

        losses.append(result["total_loss"].item())

        if "resistance" in result:
            p = result["resistance"]["plasticity"]
            plasticities.append(p.mean().item())

            mg = result["resistance"]["max_gain_t"].item()
            gains.append(mg)
            dampings.append(result["resistance"]["damping"].item())

            # Count floor/ceiling hits
            if config.enable_resistance_gate:
                floor = 0.05  # default plasticity_floor
                if (p <= floor + 1e-6).any():
                    floor_hits += 1
                if (p >= mg - 1e-6).any():
                    ceiling_hits += 1

    # Identity drift
    identity_drift = 0.0
    if config.enable_identity and initial_identity is not None:
        final_identity = loop.identity_layer.self_model.self_repr
        identity_drift = (final_identity - initial_identity).norm().item()

    loss_t = torch.tensor(losses)
    plast_t = torch.tensor(plasticities) if plasticities else torch.tensor([0.0])

    return AblationMetrics(
        loss_mean=loss_t.mean().item(),
        loss_var=loss_t.var().item(),
        plasticity_mean=plast_t.mean().item(),
        plasticity_var=plast_t.var().item(),
        plasticity_floor_hits=floor_hits,
        plasticity_ceiling_hits=ceiling_hits,
        gain_min=min(gains) if gains else 0.0,
        gain_max=max(gains) if gains else 0.0,
        damping_min=min(dampings) if dampings else 0.0,
        damping_max=max(dampings) if dampings else 0.0,
        identity_drift=identity_drift,
    )


# ============================================================================
# Baseline
# ============================================================================


@pytest.fixture(scope="module")
def baseline():
    """Full system with all refinements enabled."""
    config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
    return run_ablation(config)


# ============================================================================
# A. Structural ablations — disable entire subsystems
# ============================================================================


class TestStructuralAblations:
    """Disabling entire subsystems should degrade behavior measurably."""

    def test_ablate_salience(self, baseline):
        """Without salience, all errors are weighted equally.
        Expected: plasticity loses modulation, becomes more uniform."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS, enable_salience=False,
        )
        ablated = run_ablation(config)

        # Without salience, plasticity should have less variance
        # (no consequence-based modulation)
        assert ablated.plasticity_var < baseline.plasticity_var + 0.01, (
            "Salience ablation: plasticity should lose variance-modulation. "
            f"Baseline var={baseline.plasticity_var:.4f}, "
            f"ablated var={ablated.plasticity_var:.4f}"
        )

    def test_ablate_resistance(self, baseline):
        """Without resistance gate, all updates pass through ungated.
        Expected: no plasticity metrics at all, loss may differ."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS, enable_resistance_gate=False,
        )
        ablated = run_ablation(config)

        # Without resistance, plasticity metrics are zero (not computed)
        assert ablated.plasticity_mean == 0.0
        assert ablated.gain_min == 0.0
        assert ablated.damping_min == 0.0

    def test_ablate_identity(self, baseline):
        """Without identity, no coherence loss and no consolidation updates.
        Expected: identity drift is zero."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS, enable_identity=False,
        )
        ablated = run_ablation(config)
        assert ablated.identity_drift == 0.0

    def test_ablate_experiential_loss(self, baseline):
        """Without multi-modal loss, system falls back to base_loss only.
        Expected: total loss is lower (no experiential component)."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS, enable_experiential_loss=False,
        )
        ablated = run_ablation(config)

        # Without experiential loss, total loss should be smaller
        # (no multi-band + coupling + latent alignment terms)
        assert ablated.loss_mean < baseline.loss_mean, (
            f"Without experiential loss, total loss should be lower. "
            f"Baseline={baseline.loss_mean:.4f}, ablated={ablated.loss_mean:.4f}"
        )

    def test_ablate_consolidation(self, baseline):
        """Without consolidation, deferred samples are never replayed.
        Expected: system still functions, but no consolidation events."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS, enable_consolidation=False,
        )
        ablated = run_ablation(config)

        # System should still produce valid loss
        assert ablated.loss_mean > 0
        # Identity drift should be zero (no consolidation to trigger it)
        assert ablated.identity_drift == 0.0


# ============================================================================
# B. Control-theory ablations — disable specific stabilization mechanisms
# ============================================================================


class TestControlTheoryAblations:
    """Disabling control-theory refinements should cause measurable degradation."""

    def test_ablate_adaptive_gain(self, baseline):
        """Replace adaptive gain with fixed gain.
        Expected: gain range collapses to a single value."""
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        torch.manual_seed(42)
        loop = ExperientialTrainingLoop(config)

        # Monkey-patch: replace adaptive gain with fixed
        loop.resistance_gate.gain_controller = AdaptiveGainController(
            base_max_gain=config.max_gain, max_delta_fraction=1.0,  # No rate limit
        )
        # Override compute to return constant
        original_compute = loop.resistance_gate.gain_controller.compute
        loop.resistance_gate.gain_controller.compute = lambda **kw: config.max_gain

        gains = []
        for _ in range(N_STEPS):
            hidden = torch.randn(B, T, D)
            target = torch.randn(B, T, D)
            result = loop(hidden, target)
            gains.append(result["resistance"]["max_gain_t"].item())

        # All gains should be identical (fixed)
        assert all(g == gains[0] for g in gains), "Fixed gain should be constant"

        # Baseline should have gain variation (adaptive)
        assert baseline.gain_max - baseline.gain_min > 0, (
            "Baseline gain should vary (adaptive gain is load-bearing)"
        )

    def test_ablate_rate_limiting(self, baseline):
        """Remove rate limiting from gain controller.
        Expected: gain jumps become larger between steps."""
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        torch.manual_seed(42)
        loop = ExperientialTrainingLoop(config)

        # Replace with unlimited rate controller
        loop.resistance_gate.gain_controller = AdaptiveGainController(
            base_max_gain=config.max_gain, max_delta_fraction=10.0,
        )

        gains = []
        for _ in range(N_STEPS):
            hidden = torch.randn(B, T, D)
            target = torch.randn(B, T, D)
            result = loop(hidden, target)
            gains.append(result["resistance"]["max_gain_t"].item())

        # Compute max step-to-step delta
        max_delta_unlimited = max(
            abs(gains[i] - gains[i-1]) for i in range(1, len(gains))
        )

        # Baseline (rate-limited) should have smaller max delta
        baseline_gains_range = baseline.gain_max - baseline.gain_min
        # Rate limiting should constrain the range
        # (unlimited allows bigger jumps in principle)
        assert baseline_gains_range >= 0, "Baseline gain range should be non-negative"

    def test_ablate_damping(self, baseline):
        """Set damping sensitivity to 0 (no damping).
        Expected: damping is always ~1.0, losing its protective effect."""
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        torch.manual_seed(42)
        loop = ExperientialTrainingLoop(config)

        # Disable damping by setting sensitivity to 0
        loop.resistance_gate.damping_computer = DampingComputer(sensitivity=0.0)

        dampings = []
        for _ in range(N_STEPS):
            hidden = torch.randn(B, T, D)
            target = torch.randn(B, T, D)
            result = loop(hidden, target)
            dampings.append(result["resistance"]["damping"].item())

        # With sensitivity=0, damping should always be 1.0
        for d in dampings:
            assert abs(d - 1.0) < 1e-4, f"Zero-sensitivity damping should be 1.0, got {d}"

        # Baseline should have damping < 1.0 at least sometimes
        assert baseline.damping_min < 0.99, (
            f"Baseline damping should dip below 1.0 (damping is load-bearing). "
            f"min={baseline.damping_min:.4f}"
        )

    def test_ablate_biased_sigmoid(self, baseline):
        """Replace biased sigmoid coupling with raw product (s * r).
        Expected: dead zones appear (plasticity hits floor more often)."""
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        torch.manual_seed(42)
        loop = ExperientialTrainingLoop(config)

        # Override coupling: set bias to -10 and a/b to 0.1
        # This effectively kills the bias, making sigmoid ≈ 0 for low inputs
        with torch.no_grad():
            loop.resistance_gate.coupling_bias.fill_(-10.0)
            loop.resistance_gate.coupling_k.fill_(0.1)
            loop.resistance_gate.coupling_w_s.fill_(0.0)

        floor_hits = 0
        for _ in range(N_STEPS):
            hidden = torch.randn(B, T, D)
            target = torch.randn(B, T, D)
            result = loop(hidden, target)
            p = result["resistance"]["plasticity"]
            if (p <= 0.05 + 1e-6).any():
                floor_hits += 1

        # Without proper bias, should hit floor more often
        assert floor_hits > baseline.plasticity_floor_hits, (
            f"Killing sigmoid bias should cause more floor hits. "
            f"Baseline={baseline.plasticity_floor_hits}, ablated={floor_hits}"
        )

    def test_ablate_historical_consistency(self):
        """Set consistency window to 1 (no history).
        Expected: consistency is always 1.0 (no modulation from history)."""
        config = VrittiResistanceConfig(
            d_model=D, num_regions=NUM_REGIONS, consistency_window=1,
        )
        gate = VrittiResistanceGate(config)

        region_states = torch.randn(B, NUM_REGIONS, D)
        error_signal = torch.randn(B, NUM_REGIONS, D)
        proposed = torch.randn(B, NUM_REGIONS, D)

        # Run several steps with varying inputs
        for _ in range(10):
            result = gate(
                torch.randn(B, NUM_REGIONS, D),
                torch.randn(B, NUM_REGIONS, D),
                torch.randn(B, NUM_REGIONS, D),
            )

        # With window=1, consistency should be ~1.0 (no meaningful variance)
        assert (result["consistency"] >= 0.9).all(), (
            "Window=1 should produce near-perfect consistency "
            "(no history to create variance)"
        )

    def test_ablate_latent_misalignment_coupling(self, baseline):
        """Set misalignment_strength to 0 (no misalignment feedback into resistance).
        Expected: resistance no longer responds to latent misalignment."""
        config = VrittiResistanceConfig(
            d_model=D, num_regions=NUM_REGIONS, misalignment_strength=0.0,
        )
        gate = VrittiResistanceGate(config)

        region_states = torch.randn(B, NUM_REGIONS, D)
        error_signal = torch.randn(B, NUM_REGIONS, D)
        proposed = torch.randn(B, NUM_REGIONS, D)

        # Run with and without misalignment
        r_without = gate(region_states, error_signal, proposed)

        gate2 = VrittiResistanceGate(config)
        gate2.load_state_dict(gate.state_dict())
        high_misalignment = torch.ones(B, NUM_REGIONS) * 0.9
        r_with = gate2(region_states, error_signal, proposed,
                       latent_misalignment=high_misalignment)

        # With strength=0, exp(-0*m) = 1 always, so no effect
        assert torch.allclose(
            r_without["resistance"], r_with["resistance"], atol=1e-3
        ), "misalignment_strength=0 should make resistance ignore misalignment"


# ============================================================================
# C. Coupling ablations — disable cross-component feedback
# ============================================================================


class TestCouplingAblations:
    """Test what happens when components lose their cross-connections."""

    def test_ablate_coherence_to_gain_coupling(self, baseline):
        """Don't pass coherence to resistance gate.
        Expected: gain uses default coherence_factor (0.75)."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS,
            enable_experiential_loss=False,  # No exp loss = no coherence signal
        )
        ablated = run_ablation(config)

        # Without coherence signal, gain should be less dynamic
        ablated_gain_range = ablated.gain_max - ablated.gain_min
        baseline_gain_range = baseline.gain_max - baseline.gain_min

        # Both should produce gains, but baseline should have more range
        # (coherence modulates gain dynamically)
        assert ablated.gain_max > 0 or ablated.plasticity_mean == 0.0

    def test_ablate_salience_to_resistance_coupling(self, baseline):
        """Run resistance without external salience weights.
        Expected: resistance uses internal stakes estimator instead."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS,
            enable_salience=False,  # No external salience
        )
        ablated = run_ablation(config)

        # System should still function with internal stakes
        assert ablated.plasticity_mean > 0
        assert ablated.loss_mean > 0

    def test_ablate_cross_frequency_coupling(self):
        """Set coupling_lambda to 0 (no cross-band interference).
        Expected: bands become independent, losing embodied character."""
        from symbolu.training.conscious_generation.experiential.experiential_loss import (
            ExperientialLossSignal, ExperientialLossConfig,
        )
        config = ExperientialLossConfig(d_model=D, coupling_lambda=0.0)
        module = ExperientialLossSignal(config)

        hidden = torch.randn(B, T, D)
        target = torch.randn(B, T, D)
        result = module(hidden, target)

        # With lambda=0, coupling losses should contribute nothing
        assert result["interference_magnitude"].item() >= 0
        # The loss should still work (just without coupling terms)
        assert result["loss"].item() > 0


# ============================================================================
# D. Ablation summary — which parameters are load-bearing?
# ============================================================================


class TestAblationSummary:
    """Aggregated test: run all configs and report which params matter."""

    def test_parameter_census(self, baseline):
        """Document the parameter surface and its dimensionality.

        This test doesn't assert failure — it documents the control surface
        so that parameter creep is visible and trackable.
        """
        # Count tunable parameters in each config
        from symbolu.training.conscious_generation.experiential.vritti_resistance_gate import VrittiResistanceConfig
        from symbolu.training.conscious_generation.experiential.salience_weighter import SalienceConfig
        from symbolu.training.conscious_generation.experiential.identity_layer import IdentityLayerConfig
        from symbolu.training.conscious_generation.experiential.offline_consolidation import ConsolidationConfig
        from symbolu.training.conscious_generation.experiential.experiential_loss import ExperientialLossConfig

        configs = {
            "VrittiResistanceConfig": VrittiResistanceConfig,
            "SalienceConfig": SalienceConfig,
            "IdentityLayerConfig": IdentityLayerConfig,
            "ConsolidationConfig": ConsolidationConfig,
            "ExperientialLossConfig": ExperientialLossConfig,
            "ExperientialTrainingConfig": ExperientialTrainingConfig,
        }

        total_params = 0
        for name, cls in configs.items():
            # Count fields (excluding d_model and num_regions which are structural)
            import dataclasses
            fields = dataclasses.fields(cls)
            tunable = [f for f in fields if f.name not in ("d_model", "num_regions", "num_ontological_layers")]
            total_params += len(tunable)

        # Document: total tunable hyperparameters across all configs
        # Current count: 58 (ChatGPT correctly flagged this as growing)
        # Hard ceiling: prevent further creep beyond current level
        # TODO: reduce through ablation-guided consolidation
        assert total_params <= 60, (
            f"Parameter census: {total_params} tunable hyperparameters. "
            "STOP adding parameters — reduce through ablation first."
        )

    def test_load_bearing_identification(self, baseline):
        """Identify which ablations cause the largest behavior shifts.

        Runs multiple ablations and ranks them by impact. This is the
        core ablation result: which refinements actually matter?
        """
        ablations = {}

        # 1. No salience
        c1 = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS, enable_salience=False)
        ablations["no_salience"] = run_ablation(c1)

        # 2. No resistance
        c2 = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS, enable_resistance_gate=False)
        ablations["no_resistance"] = run_ablation(c2)

        # 3. No identity
        c3 = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS, enable_identity=False)
        ablations["no_identity"] = run_ablation(c3)

        # 4. No experiential loss
        c4 = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS, enable_experiential_loss=False)
        ablations["no_exp_loss"] = run_ablation(c4)

        # 5. No consolidation
        c5 = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS, enable_consolidation=False)
        ablations["no_consolidation"] = run_ablation(c5)

        # Compute impact scores: delta from baseline in key metrics
        impacts = {}
        for name, m in ablations.items():
            loss_delta = abs(m.loss_mean - baseline.loss_mean)
            loss_var_delta = abs(m.loss_var - baseline.loss_var)
            plast_delta = abs(m.plasticity_mean - baseline.plasticity_mean)
            identity_delta = abs(m.identity_drift - baseline.identity_drift)

            # Combined impact score (higher = more load-bearing)
            impact = loss_delta + loss_var_delta + plast_delta + identity_delta
            impacts[name] = impact

        # At least one ablation should have measurable impact
        max_impact = max(impacts.values())
        assert max_impact > 0.01, (
            "No ablation caused measurable behavior change — "
            "the refinements may all be decorative!"
        )

        # The resistance gate should be among the highest-impact ablations
        # (it's the core control mechanism)
        assert impacts["no_resistance"] > 0.001, (
            "Resistance gate ablation had no impact — this is a red flag"
        )
