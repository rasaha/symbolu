"""
Tests for Causal Layer Module
==============================

Tests for do-calculus style causal inference on SymbolU layer pipeline.

This module tests:
- Layer causal graph structure
- do() intervention operator
- Average Treatment Effect (ATE) estimation
- Counterfactual reasoning
- Causal attribution
"""

import math
import pytest

from symbolu.guna_modulation.observables import Observables
from symbolu.guna_modulation.mirror_balance import OntologicalLayer
from symbolu.guna_modulation.causal_layer import (
    # Constants
    LAYER_CAUSAL_ORDER,
    LAYER_POSITION,
    EPSILON,
    # Graph utilities
    is_upstream,
    is_downstream,
    get_upstream_layers,
    get_downstream_layers,
    causal_distance,
    # Graph
    LayerCausalGraph,
    DEFAULT_CAUSAL_GRAPH,
    # State
    LayerState,
    PipelineState,
    # Intervention
    CausalIntervention,
    do,
    # Effect estimation
    CausalEffect,
    compute_layer_metric,
    estimate_ate,
    # Counterfactual
    Counterfactual,
    counterfactual_query,
    # Attribution
    LayerAttribution,
    CausalAttribution,
    attribute_outcome,
    # Main interface
    LayerCausalModel,
    InterventionQuery,
    # Convenience
    create_causal_model,
    quick_attribution,
    quick_ate,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def high_clarity_obs():
    """Observables with high Sattva (clarity)."""
    return Observables(
        s=0.8, r=0.1, t=0.1,
        H=0.2,
        delta_sem=0.1,
        C_contr=0.1, F_fail=0.0,
    )


@pytest.fixture
def low_clarity_obs():
    """Observables with low Sattva (poor clarity)."""
    return Observables(
        s=0.2, r=0.3, t=0.5,
        H=0.7,
        delta_sem=0.3,
        C_contr=0.4, F_fail=0.2,
    )


@pytest.fixture
def neutral_obs():
    """Neutral/balanced observables."""
    return Observables(
        s=0.33, r=0.34, t=0.33,
        H=0.5,
        delta_sem=0.0,
        C_contr=0.0, F_fail=0.0,
    )


@pytest.fixture
def sample_pipeline_state(high_clarity_obs, low_clarity_obs, neutral_obs):
    """Sample pipeline state with multiple layers."""
    state = PipelineState()
    state = state.set(OntologicalLayer.GUNA, high_clarity_obs)
    state = state.set(OntologicalLayer.FUSION, neutral_obs)
    state = state.set(OntologicalLayer.STATE, neutral_obs)
    state = state.set(OntologicalLayer.OUTPUT, low_clarity_obs)
    return state


# =============================================================================
# Test Layer Causal Order
# =============================================================================

class TestLayerCausalOrder:
    """Tests for causal ordering of layers."""

    def test_layer_order_length(self):
        """Should have 7 layers in order."""
        assert len(LAYER_CAUSAL_ORDER) == 7

    def test_layer_order_starts_with_signal(self):
        """First layer should be SIGNAL."""
        assert LAYER_CAUSAL_ORDER[0] == OntologicalLayer.SIGNAL

    def test_layer_order_ends_with_output(self):
        """Last layer should be OUTPUT."""
        assert LAYER_CAUSAL_ORDER[-1] == OntologicalLayer.OUTPUT

    def test_layer_positions_match_order(self):
        """Position map should match order list."""
        for idx, layer in enumerate(LAYER_CAUSAL_ORDER):
            assert LAYER_POSITION[layer] == idx

    def test_is_upstream(self):
        """Test upstream relationship."""
        assert is_upstream(OntologicalLayer.GUNA, OntologicalLayer.OUTPUT)
        assert is_upstream(OntologicalLayer.SIGNAL, OntologicalLayer.EMBEDDING)
        assert not is_upstream(OntologicalLayer.OUTPUT, OntologicalLayer.GUNA)
        assert not is_upstream(OntologicalLayer.GUNA, OntologicalLayer.GUNA)

    def test_is_downstream(self):
        """Test downstream relationship."""
        assert is_downstream(OntologicalLayer.OUTPUT, OntologicalLayer.GUNA)
        assert is_downstream(OntologicalLayer.FUSION, OntologicalLayer.GUNA)
        assert not is_downstream(OntologicalLayer.GUNA, OntologicalLayer.OUTPUT)

    def test_get_upstream_layers(self):
        """Test getting upstream layers."""
        upstream = get_upstream_layers(OntologicalLayer.FUSION)
        assert OntologicalLayer.GUNA in upstream
        assert OntologicalLayer.EMBEDDING in upstream
        assert OntologicalLayer.SIGNAL in upstream
        assert OntologicalLayer.FUSION not in upstream
        assert OntologicalLayer.OUTPUT not in upstream

    def test_get_downstream_layers(self):
        """Test getting downstream layers."""
        downstream = get_downstream_layers(OntologicalLayer.GUNA)
        assert OntologicalLayer.FUSION in downstream
        assert OntologicalLayer.STATE in downstream
        assert OntologicalLayer.OUTPUT in downstream
        assert OntologicalLayer.GUNA not in downstream
        assert OntologicalLayer.SIGNAL not in downstream

    def test_causal_distance(self):
        """Test causal distance computation."""
        # SIGNAL(0) → EMBEDDING(1) → GUNA(2) → MOTION(3) → FUSION(4) → STATE(5) → OUTPUT(6)
        assert causal_distance(OntologicalLayer.GUNA, OntologicalLayer.MOTION) == 1  # Adjacent
        assert causal_distance(OntologicalLayer.GUNA, OntologicalLayer.FUSION) == 2  # GUNA → MOTION → FUSION
        assert causal_distance(OntologicalLayer.GUNA, OntologicalLayer.OUTPUT) == 4  # GUNA → ... → OUTPUT
        assert causal_distance(OntologicalLayer.SIGNAL, OntologicalLayer.OUTPUT) == 6  # Full chain
        # Distance is symmetric
        assert causal_distance(OntologicalLayer.OUTPUT, OntologicalLayer.GUNA) == 4


# =============================================================================
# Test Layer Causal Graph
# =============================================================================

class TestLayerCausalGraph:
    """Tests for LayerCausalGraph class."""

    def test_default_graph(self):
        """Default graph should have all layers."""
        graph = DEFAULT_CAUSAL_GRAPH
        assert len(graph.layers) == 7

    def test_parents(self):
        """Test parent computation."""
        graph = LayerCausalGraph()

        # SIGNAL has no parents
        assert graph.parents(OntologicalLayer.SIGNAL) == []

        # GUNA's parent is EMBEDDING
        parents = graph.parents(OntologicalLayer.GUNA)
        assert len(parents) == 1
        assert parents[0] == OntologicalLayer.EMBEDDING

    def test_children(self):
        """Test children computation."""
        graph = LayerCausalGraph()

        # OUTPUT has no children
        assert graph.children(OntologicalLayer.OUTPUT) == []

        # GUNA's child is MOTION (not FUSION - there's MOTION between them)
        children = graph.children(OntologicalLayer.GUNA)
        assert len(children) == 1
        assert children[0] == OntologicalLayer.MOTION

    def test_ancestors(self):
        """Test ancestor computation."""
        graph = LayerCausalGraph()

        ancestors = graph.ancestors(OntologicalLayer.FUSION)
        assert OntologicalLayer.GUNA in ancestors
        assert OntologicalLayer.EMBEDDING in ancestors
        assert OntologicalLayer.SIGNAL in ancestors

    def test_descendants(self):
        """Test descendant computation."""
        graph = LayerCausalGraph()

        descendants = graph.descendants(OntologicalLayer.GUNA)
        assert OntologicalLayer.FUSION in descendants
        assert OntologicalLayer.OUTPUT in descendants

    def test_d_separation_blocked(self):
        """Test d-separation when path is blocked."""
        graph = LayerCausalGraph()

        # GUNA blocks path between EMBEDDING and FUSION
        is_sep = graph.is_d_separated(
            OntologicalLayer.EMBEDDING,
            OntologicalLayer.FUSION,
            [OntologicalLayer.GUNA],
        )
        assert is_sep

    def test_d_separation_unblocked(self):
        """Test d-separation when path is not blocked."""
        graph = LayerCausalGraph()

        # No blocker between EMBEDDING and FUSION
        is_sep = graph.is_d_separated(
            OntologicalLayer.EMBEDDING,
            OntologicalLayer.FUSION,
            [],
        )
        assert not is_sep


# =============================================================================
# Test Pipeline State
# =============================================================================

class TestPipelineState:
    """Tests for PipelineState class."""

    def test_empty_state(self):
        """Empty state should return None for all layers."""
        state = PipelineState()
        assert state.get(OntologicalLayer.GUNA) is None

    def test_set_and_get(self, high_clarity_obs):
        """Test setting and getting layer state."""
        state = PipelineState()
        new_state = state.set(OntologicalLayer.GUNA, high_clarity_obs)

        assert new_state.get(OntologicalLayer.GUNA) == high_clarity_obs
        # Original unchanged (immutable)
        assert state.get(OntologicalLayer.GUNA) is None

    def test_as_list(self, high_clarity_obs, neutral_obs):
        """Test converting to list format."""
        state = PipelineState()
        state = state.set(OntologicalLayer.GUNA, high_clarity_obs)
        state = state.set(OntologicalLayer.FUSION, neutral_obs)

        layer_list = state.as_list()

        assert len(layer_list) == 2
        layer_names = [name for name, _ in layer_list]
        assert "guna" in layer_names
        assert "fusion" in layer_names


# =============================================================================
# Test do() Intervention
# =============================================================================

class TestDoIntervention:
    """Tests for do() operator."""

    def test_create_intervention(self, high_clarity_obs):
        """Test creating an intervention."""
        intervention = do(OntologicalLayer.GUNA, high_clarity_obs)

        assert intervention.target_layer == OntologicalLayer.GUNA
        assert intervention.intervention_obs == high_clarity_obs

    def test_apply_intervention(self, high_clarity_obs, neutral_obs):
        """Test applying intervention to state."""
        state = PipelineState()
        state = state.set(OntologicalLayer.GUNA, neutral_obs)

        intervention = do(OntologicalLayer.GUNA, high_clarity_obs)
        new_state = intervention.apply(state)

        # Intervention should change the target layer
        assert new_state.get(OntologicalLayer.GUNA) == high_clarity_obs


# =============================================================================
# Test Causal Effect Estimation
# =============================================================================

class TestCausalEffect:
    """Tests for CausalEffect and ATE estimation."""

    def test_compute_layer_metric(self, high_clarity_obs, low_clarity_obs):
        """Test layer metric computation."""
        high_metric = compute_layer_metric(high_clarity_obs)
        low_metric = compute_layer_metric(low_clarity_obs)

        # High clarity should have higher metric
        assert high_metric > low_metric

    def test_ate_upstream_to_downstream(self, sample_pipeline_state, high_clarity_obs):
        """Test ATE computation for valid causal direction."""
        effect = estimate_ate(
            sample_pipeline_state,
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            intervention_obs=high_clarity_obs,
        )

        # Should have valid effect
        assert effect.confidence > 0
        assert effect.treatment == OntologicalLayer.GUNA
        assert effect.outcome == OntologicalLayer.OUTPUT

    def test_ate_downstream_to_upstream_invalid(self, sample_pipeline_state, high_clarity_obs):
        """Test ATE returns zero for invalid causal direction."""
        effect = estimate_ate(
            sample_pipeline_state,
            treatment=OntologicalLayer.OUTPUT,  # Downstream
            outcome=OntologicalLayer.GUNA,  # Upstream
            intervention_obs=high_clarity_obs,
        )

        # Should have zero confidence (no valid causal path)
        assert effect.confidence == 0.0
        assert effect.effect_size == 0.0

    def test_effect_is_significant(self):
        """Test significance threshold."""
        significant = CausalEffect(
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            effect_size=0.15,
            effect_direction="positive",
            baseline_metric=0.5,
            treatment_metric=0.65,
            confidence=0.8,
        )

        not_significant = CausalEffect(
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            effect_size=0.05,
            effect_direction="neutral",
            baseline_metric=0.5,
            treatment_metric=0.55,
            confidence=0.8,
        )

        assert significant.is_significant
        assert not not_significant.is_significant

    def test_relative_effect(self):
        """Test relative effect computation."""
        effect = CausalEffect(
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            effect_size=0.1,
            effect_direction="positive",
            baseline_metric=0.5,
            treatment_metric=0.6,
            confidence=0.8,
        )

        # 0.1 / 0.5 = 20%
        assert abs(effect.relative_effect - 20.0) < 0.1


# =============================================================================
# Test Counterfactual Reasoning
# =============================================================================

class TestCounterfactual:
    """Tests for counterfactual queries."""

    def test_counterfactual_query(self, sample_pipeline_state, high_clarity_obs):
        """Test basic counterfactual query."""
        cf = counterfactual_query(
            sample_pipeline_state,
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            intervention_obs=high_clarity_obs,
            query_description="What if GUNA had high clarity?",
        )

        assert cf.query == "What if GUNA had high clarity?"
        assert cf.treatment == OntologicalLayer.GUNA
        assert cf.outcome == OntologicalLayer.OUTPUT

    def test_counterfactual_difference(self, sample_pipeline_state, high_clarity_obs):
        """Test counterfactual difference computation."""
        cf = counterfactual_query(
            sample_pipeline_state,
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            intervention_obs=high_clarity_obs,
        )

        # Difference should equal counterfactual - factual
        expected_diff = cf.counterfactual_value - cf.factual_value
        assert abs(cf.difference - expected_diff) < EPSILON

    def test_would_have_improved(self):
        """Test improvement detection."""
        improved = Counterfactual(
            query="Test",
            factual_value=0.5,
            counterfactual_value=0.7,
            difference=0.2,
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            intervention=Observables(s=0.8, r=0.1, t=0.1, H=0.2, delta_sem=0.1, C_contr=0.1, F_fail=0.0),
        )

        worsened = Counterfactual(
            query="Test",
            factual_value=0.7,
            counterfactual_value=0.5,
            difference=-0.2,
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            intervention=Observables(s=0.2, r=0.4, t=0.4, H=0.7, delta_sem=0.3, C_contr=0.3, F_fail=0.1),
        )

        assert improved.would_have_improved
        assert not worsened.would_have_improved


# =============================================================================
# Test Causal Attribution
# =============================================================================

class TestCausalAttribution:
    """Tests for causal attribution."""

    def test_attribute_outcome(self, sample_pipeline_state):
        """Test attributing outcome to upstream layers."""
        attribution = attribute_outcome(
            sample_pipeline_state,
            OntologicalLayer.OUTPUT,
        )

        assert attribution.outcome == OntologicalLayer.OUTPUT
        assert len(attribution.attributions) > 0

    def test_attribution_has_primary_cause(self, sample_pipeline_state):
        """Test that attribution identifies primary cause."""
        attribution = attribute_outcome(
            sample_pipeline_state,
            OntologicalLayer.OUTPUT,
        )

        # Should have a primary cause if attributions exist
        if attribution.attributions:
            assert attribution.primary_cause is not None

    def test_attribution_percentages_reasonable(self, sample_pipeline_state):
        """Test that attribution percentages are reasonable."""
        attribution = attribute_outcome(
            sample_pipeline_state,
            OntologicalLayer.OUTPUT,
        )

        total_pct = sum(a.contribution_percent for a in attribution.attributions)

        # Total should be close to 100% if there are contributions
        if attribution.attributions and any(a.contribution > 0 for a in attribution.attributions):
            assert abs(total_pct - 100.0) < 1.0

    def test_get_attribution_for_layer(self, sample_pipeline_state):
        """Test getting attribution for specific layer."""
        attribution = attribute_outcome(
            sample_pipeline_state,
            OntologicalLayer.OUTPUT,
        )

        guna_attr = attribution.get_attribution(OntologicalLayer.GUNA)

        # GUNA should have an attribution since it's in the state
        assert guna_attr is not None
        assert guna_attr.layer == OntologicalLayer.GUNA


# =============================================================================
# Test LayerCausalModel
# =============================================================================

class TestLayerCausalModel:
    """Tests for main LayerCausalModel interface."""

    def test_create_model(self):
        """Test creating a causal model."""
        model = LayerCausalModel()
        assert model.graph is not None
        assert model.state is not None

    def test_observe(self, high_clarity_obs):
        """Test observing layer state."""
        model = LayerCausalModel()
        model.observe(OntologicalLayer.GUNA, high_clarity_obs)

        assert model.state.get(OntologicalLayer.GUNA) == high_clarity_obs

    def test_observe_fluent(self, high_clarity_obs, neutral_obs):
        """Test fluent interface for observing."""
        model = (
            LayerCausalModel()
            .observe(OntologicalLayer.GUNA, high_clarity_obs)
            .observe(OntologicalLayer.FUSION, neutral_obs)
        )

        assert model.state.get(OntologicalLayer.GUNA) == high_clarity_obs
        assert model.state.get(OntologicalLayer.FUSION) == neutral_obs

    def test_observe_all(self, high_clarity_obs, neutral_obs):
        """Test observing multiple layers at once."""
        model = LayerCausalModel()
        model.observe_all([
            (OntologicalLayer.GUNA, high_clarity_obs),
            (OntologicalLayer.FUSION, neutral_obs),
        ])

        assert model.state.get(OntologicalLayer.GUNA) == high_clarity_obs
        assert model.state.get(OntologicalLayer.FUSION) == neutral_obs

    def test_do_fluent(self, high_clarity_obs, neutral_obs, low_clarity_obs):
        """Test fluent do() interface."""
        model = (
            LayerCausalModel()
            .observe(OntologicalLayer.GUNA, neutral_obs)
            .observe(OntologicalLayer.OUTPUT, low_clarity_obs)
        )

        effect = model.do(OntologicalLayer.GUNA, high_clarity_obs).effect_on(OntologicalLayer.OUTPUT)

        assert effect.treatment == OntologicalLayer.GUNA
        assert effect.outcome == OntologicalLayer.OUTPUT

    def test_ate_method(self, high_clarity_obs, neutral_obs, low_clarity_obs):
        """Test ATE method."""
        model = (
            LayerCausalModel()
            .observe(OntologicalLayer.GUNA, neutral_obs)
            .observe(OntologicalLayer.OUTPUT, low_clarity_obs)
        )

        effect = model.ate(
            OntologicalLayer.GUNA,
            OntologicalLayer.OUTPUT,
            high_clarity_obs,
        )

        assert effect is not None

    def test_counterfactual_method(self, high_clarity_obs, neutral_obs, low_clarity_obs):
        """Test counterfactual method."""
        model = (
            LayerCausalModel()
            .observe(OntologicalLayer.GUNA, neutral_obs)
            .observe(OntologicalLayer.OUTPUT, low_clarity_obs)
        )

        cf = model.counterfactual(
            "What if GUNA had high clarity?",
            OntologicalLayer.GUNA,
            OntologicalLayer.OUTPUT,
            high_clarity_obs,
        )

        assert cf.query == "What if GUNA had high clarity?"

    def test_attribute_method(self, high_clarity_obs, neutral_obs, low_clarity_obs):
        """Test attribute method."""
        model = (
            LayerCausalModel()
            .observe(OntologicalLayer.GUNA, high_clarity_obs)
            .observe(OntologicalLayer.FUSION, neutral_obs)
            .observe(OntologicalLayer.OUTPUT, low_clarity_obs)
        )

        attribution = model.attribute(OntologicalLayer.OUTPUT)

        assert attribution.outcome == OntologicalLayer.OUTPUT

    def test_compute_cri(self, high_clarity_obs, neutral_obs):
        """Test CRI computation from model state."""
        model = (
            LayerCausalModel()
            .observe(OntologicalLayer.GUNA, high_clarity_obs)
            .observe(OntologicalLayer.FUSION, neutral_obs)
        )

        cri = model.compute_cri()

        assert cri is not None
        assert hasattr(cri, 'index')

    def test_reset(self, high_clarity_obs):
        """Test resetting model state."""
        model = LayerCausalModel()
        model.observe(OntologicalLayer.GUNA, high_clarity_obs)

        assert model.state.get(OntologicalLayer.GUNA) is not None

        model.reset()

        assert model.state.get(OntologicalLayer.GUNA) is None


# =============================================================================
# Test Convenience Functions
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_causal_model(self):
        """Test create_causal_model function."""
        model = create_causal_model()
        assert isinstance(model, LayerCausalModel)

    def test_quick_attribution(self, high_clarity_obs, neutral_obs, low_clarity_obs):
        """Test quick_attribution function."""
        layers = [
            (OntologicalLayer.GUNA, high_clarity_obs),
            (OntologicalLayer.FUSION, neutral_obs),
            (OntologicalLayer.OUTPUT, low_clarity_obs),
        ]

        attribution = quick_attribution(layers, OntologicalLayer.OUTPUT)

        assert attribution.outcome == OntologicalLayer.OUTPUT

    def test_quick_ate(self, high_clarity_obs, neutral_obs, low_clarity_obs):
        """Test quick_ate function."""
        layers = [
            (OntologicalLayer.GUNA, neutral_obs),
            (OntologicalLayer.OUTPUT, low_clarity_obs),
        ]

        effect = quick_ate(
            layers,
            OntologicalLayer.GUNA,
            OntologicalLayer.OUTPUT,
            high_clarity_obs,
        )

        assert effect.treatment == OntologicalLayer.GUNA
        assert effect.outcome == OntologicalLayer.OUTPUT


# =============================================================================
# Integration Tests
# =============================================================================

class TestCausalLayerIntegration:
    """Integration tests for causal layer functionality."""

    def test_full_causal_workflow(self):
        """Test complete causal analysis workflow."""
        # Create observables
        high_clarity = Observables(
            s=0.8, r=0.1, t=0.1,
            H=0.2, delta_sem=0.1,
            C_contr=0.1, F_fail=0.0,
        )
        moderate = Observables(
            s=0.5, r=0.3, t=0.2,
            H=0.4, delta_sem=0.2,
            C_contr=0.2, F_fail=0.0,
        )
        poor = Observables(
            s=0.2, r=0.3, t=0.5,
            H=0.7, delta_sem=0.3,
            C_contr=0.4, F_fail=0.1,
        )

        # Create model and observe
        model = (
            create_causal_model()
            .observe(OntologicalLayer.GUNA, moderate)
            .observe(OntologicalLayer.FUSION, moderate)
            .observe(OntologicalLayer.STATE, moderate)
            .observe(OntologicalLayer.OUTPUT, poor)
        )

        # 1. Attribute: Which layer caused poor output?
        attribution = model.attribute(OntologicalLayer.OUTPUT)
        assert attribution.primary_cause is not None

        # 2. Counterfactual: What if GUNA had high clarity?
        cf = model.counterfactual(
            "What if GUNA had high clarity?",
            OntologicalLayer.GUNA,
            OntologicalLayer.OUTPUT,
            high_clarity,
        )
        # Should show improvement potential
        assert cf is not None

        # 3. ATE: What's the effect of improving GUNA?
        effect = model.do(OntologicalLayer.GUNA, high_clarity).effect_on(OntologicalLayer.OUTPUT)
        assert effect.treatment == OntologicalLayer.GUNA

        # 4. CRI: What's the concept readiness?
        cri = model.compute_cri()
        assert cri.index >= 0.0

    def test_causal_chain_effect_decay(self):
        """Test that causal effects decay with distance."""
        obs = Observables(
            s=0.8, r=0.1, t=0.1,
            H=0.2, delta_sem=0.1,
            C_contr=0.1, F_fail=0.0,
        )
        baseline = Observables(
            s=0.5, r=0.3, t=0.2,
            H=0.5, delta_sem=0.2,
            C_contr=0.2, F_fail=0.0,
        )

        model = (
            create_causal_model()
            .observe(OntologicalLayer.GUNA, baseline)
            .observe(OntologicalLayer.FUSION, baseline)
            .observe(OntologicalLayer.STATE, baseline)
            .observe(OntologicalLayer.MOTION, baseline)
            .observe(OntologicalLayer.OUTPUT, baseline)
        )

        # Effect on nearby layer
        near_effect = model.ate(
            OntologicalLayer.GUNA,
            OntologicalLayer.FUSION,
            obs,
        )

        # Effect on distant layer
        far_effect = model.ate(
            OntologicalLayer.GUNA,
            OntologicalLayer.OUTPUT,
            obs,
        )

        # Near effect should have higher confidence (less decay)
        assert near_effect.confidence >= far_effect.confidence
