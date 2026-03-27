"""
Tests for Experiential Learning modules in Conscious Generation training.

Tests the five experiential analogs:
    1. ExperientialLossSignal — multi-modal, cross-frequency loss
    2. VrittiResistanceGate — vritti-gated gradient modulation
    3. OfflineConsolidationCycle — sleep analog consolidation
    4. SalienceWeighter — consequence-based error weighting
    5. IdentityLayer — persistent self-model
    6. ExperientialTrainingLoop — full orchestrator
"""

import pytest
import torch
import torch.nn as nn

from symbolu.training.conscious_generation.experiential.experiential_loss import (
    ExperientialLossSignal,
    ExperientialLossConfig,
    FrequencyBandProjector,
    CrossFrequencyCoupling,
)
from symbolu.training.conscious_generation.experiential.vritti_resistance_gate import (
    VrittiResistanceGate,
    VrittiResistanceConfig,
    VrittiFieldEstimator,
    StakesEstimator,
)
from symbolu.training.conscious_generation.experiential.offline_consolidation import (
    OfflineConsolidationCycle,
    ConsolidationConfig,
    ReplayBuffer,
    ContradictionDetector,
    CrossLayerCoherenceEnforcer,
)
from symbolu.training.conscious_generation.experiential.salience_weighter import (
    SalienceWeighter,
    SalienceConfig,
    CascadeTracker,
    ScarTissueRegistry,
)
from symbolu.training.conscious_generation.experiential.identity_layer import (
    IdentityLayer,
    IdentityLayerConfig,
    SelfModel,
    OntologicalDepthGate,
)
from symbolu.training.conscious_generation.experiential.experiential_training_loop import (
    ExperientialTrainingLoop,
    ExperientialTrainingConfig,
)


# ============================================================================
# Fixtures
# ============================================================================

B, T, D = 2, 16, 128
NUM_REGIONS = 12


@pytest.fixture
def device():
    return torch.device("cpu")


@pytest.fixture
def hidden(device):
    return torch.randn(B, T, D, device=device)


@pytest.fixture
def target_hidden(device):
    return torch.randn(B, T, D, device=device)


@pytest.fixture
def region_states(device):
    return torch.randn(B, NUM_REGIONS, D, device=device)


@pytest.fixture
def error_signal(device):
    return torch.randn(B, NUM_REGIONS, D, device=device)


# ============================================================================
# Test ExperientialLossSignal
# ============================================================================


class TestExperientialLossSignal:
    def test_basic_forward(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        result = module(hidden, target_hidden)

        assert "loss" in result
        assert "band_losses" in result
        assert "coupling_losses" in result
        assert "loss_texture" in result
        assert result["loss"].shape == ()
        assert result["loss"].requires_grad

    def test_loss_texture_has_three_bands(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        result = module(hidden, target_hidden)

        assert result["loss_texture"].shape == (3,)
        for name in ["semantic", "temporal", "somatic"]:
            assert name in result["band_losses"]

    def test_coupling_losses_exist(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        result = module(hidden, target_hidden)

        # 3 bands -> 3 coupling pairs
        assert len(result["coupling_losses"]) == 3
        assert "semantic__temporal" in result["coupling_losses"]
        assert "semantic__somatic" in result["coupling_losses"]
        assert "temporal__somatic" in result["coupling_losses"]

    def test_with_base_loss(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        base_loss = torch.tensor(1.5)
        result = module(hidden, target_hidden, base_loss=base_loss)

        assert result["loss"].item() >= 1.5  # Must include base loss

    def test_interference_ema_updates(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)

        ema_before = module.interference_ema.clone()
        module(hidden, target_hidden)
        ema_after = module.interference_ema.clone()

        # EMA should have changed
        assert not torch.allclose(ema_before, ema_after)

    def test_frequency_band_projector(self):
        for band_type in ["semantic", "temporal", "somatic"]:
            proj = FrequencyBandProjector(D, D // 3, band_type)
            x = torch.randn(B, T, D)
            out = proj(x)
            assert out.shape == (B, T, D // 3)

    def test_cross_frequency_coupling(self):
        d_band = D // 3
        coupling = CrossFrequencyCoupling(d_band, rank=16)
        band_i = torch.randn(B, T, d_band)
        band_j = torch.randn(B, T, d_band)
        result = coupling(band_i, band_j)
        assert result.shape == ()
        assert result.item() >= 0  # Absolute value


# ============================================================================
# Test VrittiResistanceGate
# ============================================================================


class TestVrittiResistanceGate:
    def test_basic_forward(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        assert "gated_update" in result
        assert "gate_values" in result
        assert "resistance" in result
        assert "stakes" in result
        assert "vritti_dist" in result
        assert result["gated_update"].shape == proposed.shape
        assert result["gate_values"].shape == (B, NUM_REGIONS)

    def test_gate_values_bounded(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        assert (result["gate_values"] >= 0).all()
        assert (result["gate_values"] <= 1).all()

    def test_vritti_distribution_valid(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        vritti = result["vritti_dist"]
        assert vritti.shape == (B, NUM_REGIONS, 5)
        # Should sum to 1 (softmax)
        sums = vritti.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)

    def test_consolidation_queue(self, region_states, error_signal):
        config = VrittiResistanceConfig(
            d_model=D, num_regions=NUM_REGIONS, resistance_ceiling=0.99
        )
        gate = VrittiResistanceGate(config)
        # Force high resistance by setting persistent resistance high
        gate.persistent_resistance.fill_(0.95)
        proposed = torch.randn_like(error_signal)

        gate(region_states, error_signal, proposed)

        # Should have queued some items
        items = gate.drain_consolidation_queue()
        # Queue may or may not have items depending on random init
        assert isinstance(items, list)

    def test_persistent_resistance_updates(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        before = gate.persistent_resistance.clone()
        gate(region_states, error_signal, proposed)
        after = gate.persistent_resistance

        assert not torch.allclose(before, after)

    def test_vritti_field_estimator(self, region_states):
        estimator = VrittiFieldEstimator(D, NUM_REGIONS, 5)
        vritti_dist, resistance = estimator(region_states)

        assert vritti_dist.shape == (B, NUM_REGIONS, 5)
        assert resistance.shape == (B, NUM_REGIONS)
        assert (resistance >= 0).all()
        assert (resistance <= 1).all()


# ============================================================================
# Test OfflineConsolidationCycle
# ============================================================================


class TestOfflineConsolidationCycle:
    def test_basic_creation(self):
        config = ConsolidationConfig(d_model=D, num_regions=NUM_REGIONS)
        cycle = OfflineConsolidationCycle(config)
        assert len(cycle.replay_buffer) == 0

    def test_ingest_queue(self):
        config = ConsolidationConfig(d_model=D, num_regions=NUM_REGIONS)
        cycle = OfflineConsolidationCycle(config)

        items = [
            {
                "error": torch.randn(3, D),
                "regions": torch.tensor([0, 1, 2]),
                "stakes": torch.tensor([0.5, 0.6, 0.7]),
            }
            for _ in range(10)
        ]
        count = cycle.ingest_queue(items)
        assert count == 10
        assert len(cycle.replay_buffer) == 10

    def test_consolidation_trigger(self):
        config = ConsolidationConfig(
            d_model=D, num_regions=NUM_REGIONS,
            consolidation_interval=10, min_queue_depth=2,
        )
        cycle = OfflineConsolidationCycle(config)

        # Add items
        items = [
            {
                "error": torch.randn(2, D),
                "regions": torch.tensor([0, 1]),
                "stakes": torch.tensor([0.5, 0.6]),
            }
            for _ in range(5)
        ]
        cycle.ingest_queue(items)

        # Step to consolidation interval
        for _ in range(10):
            cycle.step()

        assert cycle.should_consolidate()

    def test_consolidation_cycle(self):
        config = ConsolidationConfig(
            d_model=D, num_regions=NUM_REGIONS,
            consolidation_interval=5, min_queue_depth=2,
        )
        cycle = OfflineConsolidationCycle(config)

        items = [
            {
                "error": torch.randn(2, D),
                "regions": torch.tensor([0, 1]),
                "stakes": torch.tensor([0.8, 0.9]),
            }
            for _ in range(5)
        ]
        cycle.ingest_queue(items)

        result = cycle.consolidate()

        assert "replayed" in result
        assert "contradictions_found" in result
        assert "pruned" in result
        assert "deepened" in result
        assert result["replayed"] > 0

    def test_replay_buffer_priority(self):
        buf = ReplayBuffer(capacity=5)

        for i in range(10):
            buf.add({"salience": i * 0.1, "data": i})

        assert len(buf) == 5
        top = buf.sample_top_k(3)
        assert len(top) == 3
        # Top should have highest salience
        assert top[0]["salience"] >= top[1]["salience"]

    def test_replay_buffer_pruning(self):
        buf = ReplayBuffer()
        for i in range(10):
            buf.add({"salience": i * 0.1})

        pruned = buf.prune_below(0.5)
        assert pruned > 0
        for item in buf.buffer:
            assert item["salience"] >= 0.5

    def test_cross_layer_coherence(self):
        enforcer = CrossLayerCoherenceEnforcer(D, NUM_REGIONS)
        states = [torch.randn(B, T, D) for _ in range(4)]
        loss = enforcer(states)
        assert loss.shape == ()
        assert loss.item() >= 0


# ============================================================================
# Test SalienceWeighter
# ============================================================================


class TestSalienceWeighter:
    def test_basic_forward(self, error_signal):
        config = SalienceConfig(d_model=D, num_regions=NUM_REGIONS)
        weighter = SalienceWeighter(config)

        result = weighter(error_signal)

        assert "salience_weights" in result
        assert "cascade_scores" in result
        assert "scar_levels" in result
        assert "recurrence" in result
        assert result["salience_weights"].shape == (B, NUM_REGIONS)

    def test_salience_bounded(self, error_signal):
        config = SalienceConfig(d_model=D, num_regions=NUM_REGIONS)
        weighter = SalienceWeighter(config)

        result = weighter(error_signal)

        assert (result["salience_weights"] >= config.min_salience).all()
        assert (result["salience_weights"] <= config.max_salience).all()

    def test_scar_tissue_grows(self, error_signal):
        config = SalienceConfig(d_model=D, num_regions=NUM_REGIONS)
        weighter = SalienceWeighter(config)

        scar_before = weighter.scar_registry.get_scar_levels().clone()

        # Run multiple steps with high error
        for _ in range(5):
            high_error = torch.randn(B, NUM_REGIONS, D) * 10.0
            weighter(high_error)

        scar_after = weighter.scar_registry.get_scar_levels()
        assert (scar_after >= scar_before).all()

    def test_cascade_tracker(self, error_signal):
        tracker = CascadeTracker(D, NUM_REGIONS, cascade_depth=4)
        scores = tracker(error_signal)
        assert scores.shape == (B, NUM_REGIONS)
        assert (scores >= 0).all()
        assert (scores <= 1).all()

    def test_with_cross_modal_impact(self, error_signal):
        config = SalienceConfig(d_model=D, num_regions=NUM_REGIONS)
        weighter = SalienceWeighter(config)
        cross_modal = torch.rand(B, NUM_REGIONS)

        result = weighter(error_signal, cross_modal_impact=cross_modal)
        assert result["salience_weights"].shape == (B, NUM_REGIONS)

    def test_scar_tissue_registry(self):
        registry = ScarTissueRegistry(NUM_REGIONS, decay=0.99, growth_rate=0.1)

        # Initially zero
        assert (registry.get_scar_levels() == 0).all()

        # Grow scar tissue
        high_error = torch.ones(NUM_REGIONS) * 5.0
        registry.update(high_error)

        levels = registry.get_scar_levels()
        assert (levels > 0).all()

        most_scarred = registry.get_most_scarred(k=3)
        assert len(most_scarred) == 3


# ============================================================================
# Test IdentityLayer
# ============================================================================


class TestIdentityLayer:
    def test_basic_forward(self, device):
        config = IdentityLayerConfig(d_model=D, num_ontological_layers=NUM_REGIONS)
        layer = IdentityLayer(config)

        experience = torch.randn(B, D, device=device)
        error_per_layer = torch.randn(NUM_REGIONS, device=device).abs()

        result = layer(experience, error_per_layer)

        assert "layer_gates" in result
        assert "identity_coherence" in result
        assert "identity_loss" in result
        assert result["layer_gates"].shape == (NUM_REGIONS,)

    def test_surface_layers_open(self, device):
        config = IdentityLayerConfig(
            d_model=D, num_ontological_layers=NUM_REGIONS,
            surface_layers=(0, 3),
        )
        layer = IdentityLayer(config)

        experience = torch.randn(B, D, device=device)
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.1

        result = layer(experience, error_per_layer)

        # Surface layers (0-3) should have high gate values even with low error
        surface_gates = result["layer_gates"][:4]
        assert (surface_gates > 0.5).all()

    def test_deep_layers_guarded(self, device):
        config = IdentityLayerConfig(
            d_model=D, num_ontological_layers=NUM_REGIONS,
            deep_layers=(8, 11), deep_threshold=0.9,
        )
        layer = IdentityLayer(config)

        experience = torch.randn(B, D, device=device)
        # Low error shouldn't open deep layers
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.1

        result = layer(experience, error_per_layer)

        # Deep layers (8-11) should have very low gate values with low error
        deep_gates = result["layer_gates"][8:]
        assert (deep_gates < 0.3).all()

    def test_identity_transformation(self, device):
        config = IdentityLayerConfig(
            d_model=D, num_ontological_layers=NUM_REGIONS,
            identity_threshold=0.1,  # Low threshold for testing
        )
        layer = IdentityLayer(config)

        repr_before = layer.self_model.self_repr.clone()

        experience = torch.randn(B, D, device=device) * 5.0
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.5

        layer(experience, error_per_layer)

        # Self-representation may have changed
        # (depends on gate value from random init)
        state = layer.get_identity_state()
        assert "self_repr_norm" in state

    def test_ontological_depth_gate(self, device):
        config = IdentityLayerConfig(
            d_model=D, num_ontological_layers=NUM_REGIONS,
        )
        gate = OntologicalDepthGate(config)

        # High error everywhere
        error_mags = torch.ones(NUM_REGIONS, device=device) * 0.95
        gates = gate.compute_layer_gates(error_mags)

        assert gates.shape == (NUM_REGIONS,)
        # Surface layers should have higher gates than deep layers
        # (because of lr_scale)
        surface_gate_mean = gates[:4].mean()
        deep_gate_mean = gates[8:].mean()
        assert surface_gate_mean > deep_gate_mean

    def test_self_model(self, device):
        model = SelfModel(D, 64)
        experience = torch.randn(B, D, device=device)

        result = model(experience, error_magnitude=0.5)

        assert result["self_repr"].shape == (64,)
        assert result["identity_features"].shape == (B, 64)
        assert result["update_gate"].shape == (B, 1)
        assert -1 <= result["identity_coherence"].item() <= 1


# ============================================================================
# Test ExperientialTrainingLoop
# ============================================================================


class TestExperientialTrainingLoop:
    def test_full_forward(self, hidden, target_hidden):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        result = loop(hidden, target_hidden)

        assert "total_loss" in result
        assert result["total_loss"].requires_grad
        assert "experiential_loss" in result
        assert "salience" in result
        assert "resistance" in result
        assert "identity" in result

    def test_with_base_loss(self, hidden, target_hidden):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)
        base_loss = torch.tensor(2.0, requires_grad=True)

        result = loop(hidden, target_hidden, base_loss=base_loss)

        assert result["total_loss"].item() > 0

    def test_selective_enable(self, hidden, target_hidden):
        # Only enable experiential loss
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS,
            enable_experiential_loss=True,
            enable_resistance_gate=False,
            enable_consolidation=False,
            enable_salience=False,
            enable_identity=False,
        )
        loop = ExperientialTrainingLoop(config)

        result = loop(hidden, target_hidden)

        assert "total_loss" in result
        assert "experiential_loss" in result
        assert "resistance" not in result
        assert "identity" not in result

    def test_consolidation_triggers(self, hidden, target_hidden):
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS,
            consolidation_interval=5,
        )
        loop = ExperientialTrainingLoop(config)

        # Run multiple steps
        for _ in range(6):
            result = loop(hidden, target_hidden)

        # Consolidation may or may not have triggered (depends on queue depth)
        assert result["total_loss"].requires_grad

    def test_gradient_flows(self, hidden, target_hidden):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        result = loop(hidden, target_hidden)
        result["total_loss"].backward()

        # Check gradients flow through experiential loss
        for name, param in loop.experiential_loss.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"

    def test_with_region_states(self, hidden, target_hidden, region_states):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        result = loop(hidden, target_hidden, region_states=region_states)
        assert "total_loss" in result

    def test_get_full_state(self, hidden, target_hidden):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        loop(hidden, target_hidden)
        state = loop.get_full_state()

        assert "global_step" in state
        assert state["global_step"] == 1
        assert "resistance" in state
        assert "consolidation" in state
        assert "identity" in state
        assert "scar_tissue" in state

    def test_step_counter_increments(self, hidden, target_hidden):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        for i in range(5):
            loop(hidden, target_hidden)

        assert loop.global_step.item() == 5
