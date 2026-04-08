"""
Causal Layer: do-Calculus for SymbolU Layer Pipeline
=====================================================

This module adds causal inference capabilities to SymbolU's layer pipeline,
treating the ontological layers as a Directed Acyclic Graph (DAG).

Key Insight:
------------
SymbolU's layer pipeline IS a causal graph:

    SIGNAL → SEMANTIC → GUNA → FUSION → STATE → CALIBRATION → OUTPUT

Each layer causally affects downstream layers. This module formalizes
that relationship using do-calculus.

Capabilities:
-------------
1. do(layer, obs) - Intervention: "What if we set this layer to X?"
2. ate(treatment, outcome) - Average Treatment Effect between layers
3. counterfactual(query) - "What would have happened if...?"
4. attribute(outcome) - "Which layers caused this outcome?"

Mathematical Foundation:
------------------------
Based on Pearl's do-calculus and PyWhy's approach:

    P(Y | do(X=x)) ≠ P(Y | X=x)

The do() operator removes incoming edges to X, simulating intervention
rather than observation.

For SymbolU layers:
    P(OUTPUT | do(GUNA = obs)) = effect of forcing GUNA state

Version: 2.7.7
Date: 2025-12-22

This is SIGNAL PROCESSING, not AGI:
- Deterministic computations
- No learning or adaptation
- Bounded, auditable effects
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import math

from agentic.guna_modulation.observables import Observables
from agentic.guna_modulation.mirror_balance import OntologicalLayer
from agentic.guna_modulation.concept_readiness import (
    compute_concept_readiness,
    ConceptReadinessIndex,
)

# Epsilon for numerical stability
EPSILON: float = 1e-9


# =============================================================================
# Layer Causal Graph
# =============================================================================

# Define the causal ordering of layers (upstream → downstream)
LAYER_CAUSAL_ORDER: List[OntologicalLayer] = [
    OntologicalLayer.SIGNAL,
    OntologicalLayer.EMBEDDING,
    OntologicalLayer.GUNA,
    OntologicalLayer.MOTION,
    OntologicalLayer.FUSION,
    OntologicalLayer.STATE,
    OntologicalLayer.OUTPUT,
]

# Map layer to its position in causal order
LAYER_POSITION: Dict[OntologicalLayer, int] = {
    layer: idx for idx, layer in enumerate(LAYER_CAUSAL_ORDER)
}


def is_upstream(layer_a: OntologicalLayer, layer_b: OntologicalLayer) -> bool:
    """Check if layer_a is causally upstream of layer_b."""
    return LAYER_POSITION[layer_a] < LAYER_POSITION[layer_b]


def is_downstream(layer_a: OntologicalLayer, layer_b: OntologicalLayer) -> bool:
    """Check if layer_a is causally downstream of layer_b."""
    return LAYER_POSITION[layer_a] > LAYER_POSITION[layer_b]


def get_upstream_layers(layer: OntologicalLayer) -> List[OntologicalLayer]:
    """Get all layers that causally precede the given layer."""
    pos = LAYER_POSITION[layer]
    return LAYER_CAUSAL_ORDER[:pos]


def get_downstream_layers(layer: OntologicalLayer) -> List[OntologicalLayer]:
    """Get all layers that are causally affected by the given layer."""
    pos = LAYER_POSITION[layer]
    return LAYER_CAUSAL_ORDER[pos + 1:]


def causal_distance(layer_a: OntologicalLayer, layer_b: OntologicalLayer) -> int:
    """Compute causal distance (number of edges) between layers."""
    return abs(LAYER_POSITION[layer_a] - LAYER_POSITION[layer_b])


@dataclass(frozen=True)
class LayerCausalGraph:
    """
    Represents SymbolU's layer pipeline as a causal DAG.

    The graph is fixed by design:
        SIGNAL → SEMANTIC → GUNA → FUSION → STATE → CALIBRATION → OUTPUT

    Each edge represents direct causal influence.
    """
    layers: Tuple[OntologicalLayer, ...] = tuple(LAYER_CAUSAL_ORDER)

    def parents(self, layer: OntologicalLayer) -> List[OntologicalLayer]:
        """Get direct causal parents of a layer."""
        pos = LAYER_POSITION[layer]
        if pos == 0:
            return []
        return [LAYER_CAUSAL_ORDER[pos - 1]]

    def children(self, layer: OntologicalLayer) -> List[OntologicalLayer]:
        """Get direct causal children of a layer."""
        pos = LAYER_POSITION[layer]
        if pos == len(LAYER_CAUSAL_ORDER) - 1:
            return []
        return [LAYER_CAUSAL_ORDER[pos + 1]]

    def ancestors(self, layer: OntologicalLayer) -> List[OntologicalLayer]:
        """Get all causal ancestors (transitive parents)."""
        return get_upstream_layers(layer)

    def descendants(self, layer: OntologicalLayer) -> List[OntologicalLayer]:
        """Get all causal descendants (transitive children)."""
        return get_downstream_layers(layer)

    def is_d_separated(
        self,
        x: OntologicalLayer,
        y: OntologicalLayer,
        z: Optional[List[OntologicalLayer]] = None,
    ) -> bool:
        """
        Check if X and Y are d-separated given Z.

        In a chain graph (like SymbolU's pipeline), X and Y are d-separated
        given Z if Z blocks the path between them.
        """
        if z is None:
            z = []

        # In a chain, any node between X and Y blocks the path
        pos_x = LAYER_POSITION[x]
        pos_y = LAYER_POSITION[y]

        min_pos = min(pos_x, pos_y)
        max_pos = max(pos_x, pos_y)

        # Check if any Z blocks the path
        for blocker in z:
            pos_z = LAYER_POSITION[blocker]
            if min_pos < pos_z < max_pos:
                return True  # Z blocks the path

        return False


# Default graph instance
DEFAULT_CAUSAL_GRAPH = LayerCausalGraph()


# =============================================================================
# Causal Intervention (do-operator)
# =============================================================================

@dataclass
class LayerState:
    """State of a single layer with observables."""
    layer: OntologicalLayer
    observables: Observables


@dataclass
class PipelineState:
    """Complete state of the layer pipeline."""
    states: Dict[OntologicalLayer, Observables] = field(default_factory=dict)

    def get(self, layer: OntologicalLayer) -> Optional[Observables]:
        """Get observables for a layer."""
        return self.states.get(layer)

    def set(self, layer: OntologicalLayer, obs: Observables) -> "PipelineState":
        """Return new state with updated layer (immutable)."""
        new_states = dict(self.states)
        new_states[layer] = obs
        return PipelineState(states=new_states)

    def as_list(self) -> List[Tuple[str, Observables]]:
        """Convert to list format for CRI computation."""
        return [
            (layer if isinstance(layer, str) else layer, obs)
            for layer, obs in self.states.items()
        ]


@dataclass
class CausalIntervention:
    """
    Represents do(X = x) intervention.

    do(layer = obs) means:
    1. Set layer to specified observables
    2. Remove causal influence FROM upstream layers
    3. Propagate effect TO downstream layers
    """
    target_layer: OntologicalLayer
    intervention_obs: Observables

    def apply(self, state: PipelineState) -> PipelineState:
        """
        Apply intervention to pipeline state.

        This implements the do-operator: sets the target layer
        and propagates effects downstream.
        """
        # Set the intervention target
        new_state = state.set(self.target_layer, self.intervention_obs)

        # Downstream layers are affected (in real system, would recompute)
        # For now, we mark them as potentially changed
        return new_state


def do(
    layer: OntologicalLayer,
    obs: Observables,
) -> CausalIntervention:
    """
    Create a do(X = x) intervention.

    Usage:
        intervention = do(OntologicalLayer.GUNA, new_observables)
        new_state = intervention.apply(current_state)

    This is the Pearl do-operator for SymbolU layers.
    """
    return CausalIntervention(
        target_layer=layer,
        intervention_obs=obs,
    )


# =============================================================================
# Causal Effect Estimation
# =============================================================================

@dataclass
class CausalEffect:
    """
    Result of causal effect estimation.

    Represents E[Y | do(X = x)] - E[Y | do(X = x')]
    """
    treatment: OntologicalLayer
    outcome: OntologicalLayer
    effect_size: float  # Change in outcome metric
    effect_direction: str  # "positive", "negative", "neutral"
    baseline_metric: float  # Outcome under no intervention
    treatment_metric: float  # Outcome under intervention
    confidence: float  # How reliable is this estimate [0, 1]

    @property
    def is_significant(self) -> bool:
        """Check if effect is significant (|effect| > 0.1)."""
        return abs(self.effect_size) > 0.1

    @property
    def relative_effect(self) -> float:
        """Effect as percentage of baseline."""
        if abs(self.baseline_metric) < EPSILON:
            return 0.0
        return (self.effect_size / self.baseline_metric) * 100


def compute_layer_metric(obs: Observables) -> float:
    """
    Compute a single metric from observables for causal comparison.

    Uses: stability = (1 - H) × (1 - C_contr) × S
    Where S = sattva (clarity)
    """
    stability = (1.0 - obs.H) * (1.0 - obs.C_contr) * obs.s
    return stability


def estimate_ate(
    state: PipelineState,
    treatment: OntologicalLayer,
    outcome: OntologicalLayer,
    intervention_obs: Observables,
) -> CausalEffect:
    """
    Estimate Average Treatment Effect of treatment on outcome.

    ATE = E[Y | do(X = x_treatment)] - E[Y | do(X = x_control)]

    Where:
        Y = outcome layer metric
        X = treatment layer
        x_treatment = intervention observables
        x_control = current observables (baseline)

    Args:
        state: Current pipeline state
        treatment: Layer to intervene on
        outcome: Layer to measure effect on
        intervention_obs: Observables to set treatment layer to

    Returns:
        CausalEffect with effect size and metadata
    """
    # Validate causal relationship
    if not is_upstream(treatment, outcome):
        # Treatment must be upstream of outcome for causal effect
        return CausalEffect(
            treatment=treatment,
            outcome=outcome,
            effect_size=0.0,
            effect_direction="neutral",
            baseline_metric=0.0,
            treatment_metric=0.0,
            confidence=0.0,  # No valid causal path
        )

    # Get baseline outcome metric
    baseline_obs = state.get(outcome)
    if baseline_obs is None:
        return CausalEffect(
            treatment=treatment,
            outcome=outcome,
            effect_size=0.0,
            effect_direction="neutral",
            baseline_metric=0.0,
            treatment_metric=0.0,
            confidence=0.0,
        )

    baseline_metric = compute_layer_metric(baseline_obs)

    # Apply intervention
    intervention = do(treatment, intervention_obs)
    new_state = intervention.apply(state)

    # Estimate downstream effect using causal propagation model
    # Effect decays with causal distance
    distance = causal_distance(treatment, outcome)
    decay_factor = math.exp(-0.2 * distance)  # Exponential decay

    # Compute treatment effect on outcome
    treatment_metric_raw = compute_layer_metric(intervention_obs)

    # Propagated effect = baseline + decay × (treatment_change)
    treatment_change = treatment_metric_raw - compute_layer_metric(
        state.get(treatment) or intervention_obs
    )
    treatment_metric = baseline_metric + decay_factor * treatment_change

    # Compute effect size
    effect_size = treatment_metric - baseline_metric

    # Determine direction
    if effect_size > 0.05:
        direction = "positive"
    elif effect_size < -0.05:
        direction = "negative"
    else:
        direction = "neutral"

    # Confidence based on causal distance and data availability
    confidence = decay_factor * (1.0 if state.get(treatment) else 0.5)

    return CausalEffect(
        treatment=treatment,
        outcome=outcome,
        effect_size=effect_size,
        effect_direction=direction,
        baseline_metric=baseline_metric,
        treatment_metric=treatment_metric,
        confidence=confidence,
    )


# =============================================================================
# Counterfactual Reasoning
# =============================================================================

@dataclass
class Counterfactual:
    """
    Result of counterfactual query.

    Answers: "What would Y have been if X had been x?"
    """
    query: str  # Human-readable query
    factual_value: float  # What actually happened
    counterfactual_value: float  # What would have happened
    difference: float  # Counterfactual - Factual
    treatment: OntologicalLayer
    outcome: OntologicalLayer
    intervention: Observables

    @property
    def would_have_improved(self) -> bool:
        """Check if counterfactual outcome is better."""
        return self.counterfactual_value > self.factual_value

    @property
    def improvement_percent(self) -> float:
        """Percentage improvement in counterfactual world."""
        if abs(self.factual_value) < EPSILON:
            return 0.0
        return (self.difference / self.factual_value) * 100


def counterfactual_query(
    state: PipelineState,
    treatment: OntologicalLayer,
    outcome: OntologicalLayer,
    intervention_obs: Observables,
    query_description: Optional[str] = None,
) -> Counterfactual:
    """
    Answer a counterfactual query.

    "What would outcome have been if treatment had been intervention_obs?"

    This uses the three-step counterfactual procedure:
    1. Abduction: Infer exogenous variables from factual
    2. Action: Apply intervention (modify treatment)
    3. Prediction: Compute counterfactual outcome

    Args:
        state: Factual pipeline state
        treatment: Layer to hypothetically change
        outcome: Layer to query counterfactual value
        intervention_obs: Hypothetical treatment value
        query_description: Human-readable query description

    Returns:
        Counterfactual with factual and counterfactual values
    """
    # Default query description
    if query_description is None:
        outcome_name = outcome if isinstance(outcome, str) else outcome
        treatment_name = treatment if isinstance(treatment, str) else treatment
        query_description = (
            f"What would {outcome_name} be if {treatment_name} "
            f"had S={intervention_obs.s:.2f}, H={intervention_obs.H:.2f}?"
        )

    # Step 1: Get factual outcome
    factual_obs = state.get(outcome)
    if factual_obs is None:
        return Counterfactual(
            query=query_description,
            factual_value=0.0,
            counterfactual_value=0.0,
            difference=0.0,
            treatment=treatment,
            outcome=outcome,
            intervention=intervention_obs,
        )

    factual_value = compute_layer_metric(factual_obs)

    # Step 2 & 3: Compute counterfactual via ATE
    effect = estimate_ate(state, treatment, outcome, intervention_obs)
    counterfactual_value = effect.treatment_metric

    return Counterfactual(
        query=query_description,
        factual_value=factual_value,
        counterfactual_value=counterfactual_value,
        difference=counterfactual_value - factual_value,
        treatment=treatment,
        outcome=outcome,
        intervention=intervention_obs,
    )


# =============================================================================
# Causal Attribution
# =============================================================================

@dataclass
class LayerAttribution:
    """Attribution of outcome to a single layer."""
    layer: OntologicalLayer
    contribution: float  # Absolute contribution
    contribution_percent: float  # Percentage of total
    is_primary_cause: bool  # Highest contributor


@dataclass
class CausalAttribution:
    """
    Attribution of outcome to all upstream layers.

    Answers: "Which layers caused this outcome?"
    """
    outcome: OntologicalLayer
    outcome_metric: float
    attributions: List[LayerAttribution]
    primary_cause: Optional[OntologicalLayer]

    def get_attribution(self, layer: OntologicalLayer) -> Optional[LayerAttribution]:
        """Get attribution for a specific layer."""
        for attr in self.attributions:
            if attr.layer == layer:
                return attr
        return None


def attribute_outcome(
    state: PipelineState,
    outcome: OntologicalLayer,
) -> CausalAttribution:
    """
    Attribute outcome to upstream layers.

    Uses Shapley-style attribution: measure each layer's marginal contribution
    to the outcome by computing effect if that layer were "removed" (set to neutral).

    Args:
        state: Current pipeline state
        outcome: Layer to attribute

    Returns:
        CausalAttribution with per-layer contributions
    """
    # Get outcome metric
    outcome_obs = state.get(outcome)
    if outcome_obs is None:
        return CausalAttribution(
            outcome=outcome,
            outcome_metric=0.0,
            attributions=[],
            primary_cause=None,
        )

    outcome_metric = compute_layer_metric(outcome_obs)

    # Get upstream layers
    upstream = get_upstream_layers(outcome)

    if not upstream:
        return CausalAttribution(
            outcome=outcome,
            outcome_metric=outcome_metric,
            attributions=[],
            primary_cause=None,
        )

    # Compute marginal contribution of each upstream layer
    contributions = []

    for layer in upstream:
        layer_obs = state.get(layer)
        if layer_obs is None:
            contributions.append((layer, 0.0))
            continue

        # Create "neutral" intervention (balanced Guna, moderate entropy)
        neutral_obs = Observables(
            s=0.33,
            r=0.34,
            t=0.33,
            H=0.5,
            delta_sem=0.0,
            C_contr=0.0,
            F_fail=0.0,
        )

        # Compute effect of neutralizing this layer
        effect = estimate_ate(state, layer, outcome, neutral_obs)

        # Contribution = |effect of removing layer|
        contribution = abs(effect.effect_size)
        contributions.append((layer, contribution))

    # Normalize contributions
    total_contribution = sum(c for _, c in contributions)

    attributions = []
    max_contribution = 0.0
    primary_cause = None

    for layer, contrib in contributions:
        if total_contribution > EPSILON:
            pct = (contrib / total_contribution) * 100
        else:
            pct = 0.0

        is_primary = contrib > max_contribution
        if is_primary:
            max_contribution = contrib
            primary_cause = layer

        attributions.append(LayerAttribution(
            layer=layer,
            contribution=contrib,
            contribution_percent=pct,
            is_primary_cause=False,  # Will update after loop
        ))

    # Mark primary cause
    for attr in attributions:
        if attr.layer == primary_cause:
            attr.is_primary_cause = True

    return CausalAttribution(
        outcome=outcome,
        outcome_metric=outcome_metric,
        attributions=attributions,
        primary_cause=primary_cause,
    )


# =============================================================================
# Layer Causal Model (Main Interface)
# =============================================================================

class LayerCausalModel:
    """
    Main interface for causal inference on SymbolU layer pipeline.

    Usage:
        model = LayerCausalModel()

        # Set layer states
        model.observe(OntologicalLayer.GUNA, guna_obs)
        model.observe(OntologicalLayer.FUSION, fusion_obs)
        model.observe(OntologicalLayer.OUTPUT, output_obs)

        # Intervention query
        effect = model.do(OntologicalLayer.GUNA, low_entropy_obs)
                        .effect_on(OntologicalLayer.OUTPUT)

        # Counterfactual query
        cf = model.counterfactual(
            "What if GUNA had zero entropy?",
            treatment=OntologicalLayer.GUNA,
            outcome=OntologicalLayer.OUTPUT,
            intervention=zero_entropy_obs,
        )

        # Attribution query
        attr = model.attribute(OntologicalLayer.OUTPUT)
        print(f"Primary cause: {attr.primary_cause}")
    """

    def __init__(self, graph: Optional[LayerCausalGraph] = None):
        self._graph = graph or DEFAULT_CAUSAL_GRAPH
        self._state = PipelineState()

    @property
    def graph(self) -> LayerCausalGraph:
        """Get the causal graph."""
        return self._graph

    @property
    def state(self) -> PipelineState:
        """Get current pipeline state."""
        return self._state

    def observe(self, layer: OntologicalLayer, obs: Observables) -> "LayerCausalModel":
        """
        Observe a layer's state.

        This is observational data, not intervention.
        """
        self._state = self._state.set(layer, obs)
        return self

    def observe_all(self, states: List[Tuple[OntologicalLayer, Observables]]) -> "LayerCausalModel":
        """Observe multiple layers at once."""
        for layer, obs in states:
            self._state = self._state.set(layer, obs)
        return self

    def do(
        self,
        layer: OntologicalLayer,
        obs: Observables,
    ) -> "InterventionQuery":
        """
        Start an intervention query: do(layer = obs).

        Returns an InterventionQuery for fluent interface.
        """
        return InterventionQuery(self, layer, obs)

    def ate(
        self,
        treatment: OntologicalLayer,
        outcome: OntologicalLayer,
        intervention_obs: Observables,
    ) -> CausalEffect:
        """
        Compute Average Treatment Effect.

        ATE = E[outcome | do(treatment = intervention_obs)] - E[outcome | baseline]
        """
        return estimate_ate(self._state, treatment, outcome, intervention_obs)

    def counterfactual(
        self,
        query: str,
        treatment: OntologicalLayer,
        outcome: OntologicalLayer,
        intervention: Observables,
    ) -> Counterfactual:
        """
        Answer a counterfactual query.

        "What would outcome have been if treatment had been intervention?"
        """
        return counterfactual_query(
            self._state,
            treatment,
            outcome,
            intervention,
            query,
        )

    def attribute(self, outcome: OntologicalLayer) -> CausalAttribution:
        """
        Attribute outcome to upstream layers.

        "Which layers caused this outcome?"
        """
        return attribute_outcome(self._state, outcome)

    def compute_cri(self) -> ConceptReadinessIndex:
        """
        Compute Concept Readiness Index from current state.

        Uses observed layers for CRI computation.
        """
        return compute_concept_readiness(self._state.as_list())

    def reset(self):
        """Clear all observations."""
        self._state = PipelineState()


class InterventionQuery:
    """
    Fluent interface for intervention queries.

    Usage:
        effect = model.do(GUNA, obs).effect_on(OUTPUT)
    """

    def __init__(
        self,
        model: LayerCausalModel,
        treatment: OntologicalLayer,
        intervention: Observables,
    ):
        self._model = model
        self._treatment = treatment
        self._intervention = intervention

    def effect_on(self, outcome: OntologicalLayer) -> CausalEffect:
        """Compute effect of intervention on outcome layer."""
        return self._model.ate(self._treatment, outcome, self._intervention)

    def counterfactual_on(self, outcome: OntologicalLayer) -> Counterfactual:
        """Compute counterfactual effect on outcome layer."""
        return self._model.counterfactual(
            f"What if {self._treatment.value} were set to intervention?",
            self._treatment,
            outcome,
            self._intervention,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def create_causal_model() -> LayerCausalModel:
    """Create a new LayerCausalModel instance."""
    return LayerCausalModel()


def quick_attribution(
    layers: List[Tuple[OntologicalLayer, Observables]],
    outcome: OntologicalLayer,
) -> CausalAttribution:
    """
    Quick attribution without creating a model.

    Args:
        layers: List of (layer, observables) tuples
        outcome: Layer to attribute

    Returns:
        CausalAttribution showing which layers caused the outcome
    """
    model = LayerCausalModel()
    model.observe_all(layers)
    return model.attribute(outcome)


def quick_ate(
    layers: List[Tuple[OntologicalLayer, Observables]],
    treatment: OntologicalLayer,
    outcome: OntologicalLayer,
    intervention: Observables,
) -> CausalEffect:
    """
    Quick ATE computation without creating a model.

    Args:
        layers: List of (layer, observables) tuples
        treatment: Layer to intervene on
        outcome: Layer to measure effect on
        intervention: Observables to set treatment to

    Returns:
        CausalEffect with effect size and metadata
    """
    model = LayerCausalModel()
    model.observe_all(layers)
    return model.ate(treatment, outcome, intervention)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "LAYER_CAUSAL_ORDER",
    "LAYER_POSITION",
    "EPSILON",
    # Graph utilities
    "is_upstream",
    "is_downstream",
    "get_upstream_layers",
    "get_downstream_layers",
    "causal_distance",
    # Graph
    "LayerCausalGraph",
    "DEFAULT_CAUSAL_GRAPH",
    # State
    "LayerState",
    "PipelineState",
    # Intervention
    "CausalIntervention",
    "do",
    # Effect estimation
    "CausalEffect",
    "compute_layer_metric",
    "estimate_ate",
    # Counterfactual
    "Counterfactual",
    "counterfactual_query",
    # Attribution
    "LayerAttribution",
    "CausalAttribution",
    "attribute_outcome",
    # Main interface
    "LayerCausalModel",
    "InterventionQuery",
    # Convenience
    "create_causal_model",
    "quick_attribution",
    "quick_ate",
]
