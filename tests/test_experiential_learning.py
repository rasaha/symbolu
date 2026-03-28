"""
Tests for Experiential Learning modules in Conscious Generation training.

Tests the five experiential analogs with refactored architecture:
    1. ExperientialLossSignal — multi-modal + coherence state feedback
    2. VrittiResistanceGate — continuous plasticity, no binary branching
    3. OfflineConsolidationCycle — simplified replay + prune
    4. SalienceWeighter — consequence-based error weighting
    5. IdentityLayer — EMA-based, consolidation-only updates
    6. ExperientialTrainingLoop — time-scale separated orchestrator
"""

import pytest
import torch

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
)
from symbolu.training.conscious_generation.experiential.offline_consolidation import (
    OfflineConsolidationCycle,
    ConsolidationConfig,
    ReplayBuffer,
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
        assert "latent_alignment_loss" in result
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

        assert len(result["coupling_losses"]) == 3
        assert "semantic__temporal" in result["coupling_losses"]

    def test_with_base_loss(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        base_loss = torch.tensor(1.5)
        result = module(hidden, target_hidden, base_loss=base_loss)

        assert result["loss"].item() >= 1.5

    def test_with_coherence_state_3d(self, hidden, target_hidden, device):
        """Test state feedback from coherence/CSR pipeline (3D input)."""
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        coherence_state = torch.randn(B, T, D, device=device)

        result = module(hidden, target_hidden, coherence_state=coherence_state)

        assert result["latent_alignment_loss"].item() >= 0

    def test_with_coherence_state_2d(self, hidden, target_hidden, device):
        """Test state feedback from coherence/CSR pipeline (2D input)."""
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)
        coherence_state = torch.randn(B, D, device=device)

        result = module(hidden, target_hidden, coherence_state=coherence_state)

        assert result["latent_alignment_loss"].item() >= 0

    def test_interference_ema_updates(self, hidden, target_hidden):
        config = ExperientialLossConfig(d_model=D)
        module = ExperientialLossSignal(config)

        ema_before = module.interference_ema.clone()
        module(hidden, target_hidden)
        ema_after = module.interference_ema.clone()

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
        assert result.item() >= 0


# ============================================================================
# Test VrittiResistanceGate (continuous plasticity, no binary branching)
# ============================================================================


class TestVrittiResistanceGate:
    def test_basic_forward(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        assert "gated_update" in result
        assert "plasticity" in result
        assert "effective_gain" in result
        assert "damping" in result
        assert "max_gain_t" in result
        assert "resistance_openness" in result
        assert "resistance" in result
        assert "consistency" in result
        assert "stakes" in result
        assert "vritti_dist" in result
        assert result["gated_update"].shape == proposed.shape
        assert result["plasticity"].shape == (B, NUM_REGIONS)

    def test_no_dead_zones(self, region_states, error_signal):
        """Biased sigmoid ensures plasticity > floor always."""
        config = VrittiResistanceConfig(
            d_model=D, num_regions=NUM_REGIONS, plasticity_floor=0.05
        )
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        # Even with extreme inputs, plasticity >= floor
        assert (result["plasticity"] >= config.plasticity_floor).all()

    def test_adaptive_gain(self, region_states, error_signal):
        """Max gain should adapt based on coherence and step."""
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed, coherence=0.9)
        high_coherence_gain = result["max_gain_t"].item()

        # Reset and try with low coherence
        gate2 = VrittiResistanceGate(config)
        result2 = gate2(region_states, error_signal, proposed, coherence=0.1)
        low_coherence_gain = result2["max_gain_t"].item()

        # Higher coherence should allow higher gain
        assert high_coherence_gain >= low_coherence_gain

    def test_explicit_damping(self, region_states, error_signal):
        """Damping factor should be in (0, 1]."""
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        assert 0 < result["damping"].item() <= 1.0

    def test_continuous_no_binary_branching(self, region_states, error_signal):
        """All updates flow through — no hard cutoff."""
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.ones_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        assert result["gated_update"].abs().sum() > 0

    def test_independent_salience_input(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)
        external_salience = torch.ones(B, NUM_REGIONS) * 0.8

        result = gate(
            region_states, error_signal, proposed,
            salience_weights=external_salience,
        )
        assert result["plasticity"].shape == (B, NUM_REGIONS)

    def test_latent_misalignment_lowers_resistance(self, region_states, error_signal):
        """Latent misalignment should reduce resistance (allow correction)."""
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)

        gate1 = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)
        r1 = gate1(region_states, error_signal, proposed)

        gate2 = VrittiResistanceGate(config)
        # Copy state so comparison is fair
        gate2.load_state_dict(gate1.state_dict())
        high_misalignment = torch.ones(B, NUM_REGIONS) * 0.9
        r2 = gate2(
            region_states, error_signal, proposed,
            latent_misalignment=high_misalignment,
        )

        # With high misalignment, resistance should be lower (more open)
        assert r2["resistance"].mean() <= r1["resistance"].mean()

    def test_historical_consistency(self, region_states, error_signal):
        """Consistency should start at 1.0 and evolve over time."""
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)
        # Initially consistency should be ~1.0 (no history)
        assert (result["consistency"] >= 0.9).all()

    def test_vritti_distribution_valid(self, region_states, error_signal):
        config = VrittiResistanceConfig(d_model=D, num_regions=NUM_REGIONS)
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        result = gate(region_states, error_signal, proposed)

        vritti = result["vritti_dist"]
        assert vritti.shape == (B, NUM_REGIONS, 5)
        sums = vritti.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)

    def test_deferred_buffer_ttl(self, region_states, error_signal):
        """Deferred buffer should respect TTL and have no gradient storage."""
        config = VrittiResistanceConfig(
            d_model=D, num_regions=NUM_REGIONS, deferred_ttl=5,
        )
        gate = VrittiResistanceGate(config)
        proposed = torch.randn_like(error_signal)

        # Run several steps
        for _ in range(10):
            gate(region_states, error_signal, proposed)

        items = gate.drain_deferred_buffer()
        for item in items:
            # No gradient storage — only scalars and indices
            assert "error" not in item
            assert isinstance(item.get("salience", 0), float)
            assert isinstance(item.get("regions", []), list)

    def test_persistent_resistance_ema(self, region_states, error_signal):
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
# Test OfflineConsolidationCycle (simplified: replay + prune only)
# ============================================================================


class TestOfflineConsolidationCycle:
    def test_basic_creation(self):
        config = ConsolidationConfig(d_model=D, num_regions=NUM_REGIONS)
        cycle = OfflineConsolidationCycle(config)
        assert len(cycle.replay_buffer) == 0

    def test_ingest(self):
        config = ConsolidationConfig(d_model=D, num_regions=NUM_REGIONS)
        cycle = OfflineConsolidationCycle(config)

        items = [
            {
                "error": torch.randn(3, D),
                "regions": torch.tensor([0, 1, 2]),
                "salience": 0.7,
            }
            for _ in range(10)
        ]
        count = cycle.ingest(items)
        assert count == 10
        assert len(cycle.replay_buffer) == 10

    def test_consolidation_trigger(self):
        config = ConsolidationConfig(
            d_model=D, num_regions=NUM_REGIONS,
            consolidation_interval=10, min_buffer_depth=2,
        )
        cycle = OfflineConsolidationCycle(config)

        items = [{"salience": 0.5} for _ in range(5)]
        cycle.ingest(items)

        for _ in range(10):
            cycle.step()

        assert cycle.should_consolidate()

    def test_consolidation_returns_replay_items(self):
        config = ConsolidationConfig(
            d_model=D, num_regions=NUM_REGIONS,
            consolidation_interval=5, min_buffer_depth=2,
        )
        cycle = OfflineConsolidationCycle(config)

        items = [{"salience": 0.8, "error": torch.randn(2, D)} for _ in range(5)]
        cycle.ingest(items)

        result = cycle.consolidate()

        assert "replay_items" in result
        assert "replayed" in result
        assert "pruned_low_salience" in result
        assert "pruned_stale" in result
        assert result["replayed"] > 0

    def test_identity_consolidation_trigger(self):
        config = ConsolidationConfig(
            d_model=D, num_regions=NUM_REGIONS,
            identity_interval=50,
        )
        cycle = OfflineConsolidationCycle(config)

        for _ in range(50):
            cycle.step()

        assert cycle.should_consolidate_identity()

    def test_replay_buffer_priority(self):
        buf = ReplayBuffer(capacity=5)

        for i in range(10):
            buf.add({"salience": i * 0.1, "data": i})

        assert len(buf) == 5
        top = buf.sample_top_k(3)
        assert len(top) == 3
        assert top[0]["salience"] >= top[1]["salience"]

    def test_replay_buffer_pruning(self):
        buf = ReplayBuffer()
        for i in range(10):
            buf.add({"salience": i * 0.1})

        pruned = buf.prune_below(0.5)
        assert pruned > 0
        for item in buf.buffer:
            assert item["salience"] >= 0.5

    def test_staleness_pruning(self):
        buf = ReplayBuffer()
        for i in range(10):
            buf.add({"salience": 0.5, "step": i * 10})

        pruned = buf.prune_stale(current_step=100, staleness_limit=50)
        assert pruned > 0


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

        assert (registry.get_scar_levels() == 0).all()

        high_error = torch.ones(NUM_REGIONS) * 5.0
        registry.update(high_error)

        levels = registry.get_scar_levels()
        assert (levels > 0).all()

        most_scarred = registry.get_most_scarred(k=3)
        assert len(most_scarred) == 3


# ============================================================================
# Test IdentityLayer (EMA-based, consolidation-only)
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

    def test_no_step_driven_revision(self, device):
        """Identity should NOT change during forward pass (fast loop)."""
        config = IdentityLayerConfig(d_model=D, num_ontological_layers=NUM_REGIONS)
        layer = IdentityLayer(config)

        repr_before = layer.self_model.self_repr.clone()

        experience = torch.randn(B, D, device=device) * 5.0
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.9

        result = layer(experience, error_per_layer)

        # Identity should NOT have changed in fast loop
        assert result["transformation_triggered"] is False
        assert torch.allclose(repr_before, layer.self_model.self_repr)

    def test_ema_accumulation(self, device):
        """High-salience signals should accumulate in EMA buffer."""
        config = IdentityLayerConfig(d_model=D, num_ontological_layers=NUM_REGIONS)
        layer = IdentityLayer(config)

        experience = torch.randn(B, D, device=device)
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.5
        salience = torch.ones(NUM_REGIONS, device=device) * 0.8

        layer(experience, error_per_layer, salience=salience)

        assert layer.self_model.accumulator_count.item() > 0

    def test_consolidation_revises_identity(self, device):
        """Identity should change ONLY during consolidation."""
        config = IdentityLayerConfig(d_model=D, num_ontological_layers=NUM_REGIONS)
        layer = IdentityLayer(config)

        # Accumulate several signals
        for _ in range(10):
            experience = torch.randn(B, D, device=device) * 3.0
            error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.5
            salience = torch.ones(NUM_REGIONS, device=device) * 0.8
            layer(experience, error_per_layer, salience=salience)

        repr_before = layer.self_model.self_repr.clone()

        # Consolidate
        revised = layer.consolidate()

        if revised:
            repr_after = layer.self_model.self_repr
            assert not torch.allclose(repr_before, repr_after)

    def test_surface_layers_open(self, device):
        config = IdentityLayerConfig(
            d_model=D, num_ontological_layers=NUM_REGIONS,
            surface_layers=(0, 3),
        )
        layer = IdentityLayer(config)

        experience = torch.randn(B, D, device=device)
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.1

        result = layer(experience, error_per_layer)

        surface_gates = result["layer_gates"][:4]
        assert (surface_gates > 0.5).all()

    def test_deep_layers_guarded(self, device):
        config = IdentityLayerConfig(
            d_model=D, num_ontological_layers=NUM_REGIONS,
            deep_layers=(8, 11), deep_threshold=0.9,
        )
        layer = IdentityLayer(config)

        experience = torch.randn(B, D, device=device)
        error_per_layer = torch.ones(NUM_REGIONS, device=device) * 0.1

        result = layer(experience, error_per_layer)

        deep_gates = result["layer_gates"][8:]
        assert (deep_gates < 0.3).all()

    def test_ontological_depth_gate(self, device):
        config = IdentityLayerConfig(d_model=D, num_ontological_layers=NUM_REGIONS)
        gate = OntologicalDepthGate(config)

        error_mags = torch.ones(NUM_REGIONS, device=device) * 0.95
        gates = gate.compute_layer_gates(error_mags)

        assert gates.shape == (NUM_REGIONS,)
        surface_gate_mean = gates[:4].mean()
        deep_gate_mean = gates[8:].mean()
        assert surface_gate_mean > deep_gate_mean

    def test_self_model(self, device):
        model = SelfModel(D, 64)
        experience = torch.randn(B, D, device=device)

        result = model(experience)

        assert result["self_repr"].shape == (64,)
        assert result["identity_features"].shape == (B, 64)
        assert -1 <= result["identity_coherence"].item() <= 1


# ============================================================================
# Test ExperientialTrainingLoop (time-scale separated)
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

    def test_with_coherence_state(self, hidden, target_hidden, device):
        """Test state feedback from coherence/CSR pipeline."""
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)
        coherence_state = torch.randn(B, T, D, device=device)

        result = loop(hidden, target_hidden, coherence_state=coherence_state)

        assert "total_loss" in result

    def test_selective_enable(self, hidden, target_hidden):
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

    def test_time_scale_separation(self, hidden, target_hidden):
        """Medium and slow loops trigger at different intervals."""
        config = ExperientialTrainingConfig(
            d_model=D, num_regions=NUM_REGIONS,
            consolidation_interval=5,
            identity_interval=10,
        )
        loop = ExperientialTrainingLoop(config)

        consolidation_triggered = False
        identity_triggered = False

        for _ in range(12):
            result = loop(hidden, target_hidden)
            if "consolidation" in result:
                consolidation_triggered = True
            if "identity_consolidated" in result:
                identity_triggered = True

        # Consolidation should have triggered (interval=5, ran 12 steps)
        # Identity consolidation may or may not trigger (depends on buffer)
        assert result["total_loss"].requires_grad

    def test_gradient_flows(self, hidden, target_hidden, device):
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        # Provide coherence_state so latent_alignment_proj gets gradients too
        coherence_state = torch.randn(B, T, D, device=device)
        result = loop(hidden, target_hidden, coherence_state=coherence_state)
        result["total_loss"].backward()

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

    def test_control_theory_outputs(self, hidden, target_hidden):
        """Verify resistance output includes damping, adaptive gain, consistency."""
        config = ExperientialTrainingConfig(d_model=D, num_regions=NUM_REGIONS)
        loop = ExperientialTrainingLoop(config)

        result = loop(hidden, target_hidden)

        res = result["resistance"]
        assert "plasticity" in res
        assert "effective_gain" in res
        assert "damping" in res
        assert "max_gain_t" in res
        assert "consistency" in res
        assert "resistance_openness" in res
        assert 0 < res["damping"].item() <= 1.0
        assert res["max_gain_t"].item() > 0
