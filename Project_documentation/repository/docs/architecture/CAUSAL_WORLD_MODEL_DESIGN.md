# Causal World Model Architecture for Phase-Quad

## Status: DESIGN DOCUMENT

**Author**: Claude (Architecture Design)
**Date**: February 2026
**Version**: 1.0
**Depends On**: Phase-Quad, HP-Quad, Reflective Phase-Quad

---

## Executive Summary

This document specifies a **Causal World Model** extension for Phase-Quad that enables:
1. **Explicit Causal Graphs** - Learned/maintained cause-effect structure
2. **Intervention Modeling** - do-calculus for causal inference
3. **World State Simulation** - Predicting outcomes of actions
4. **Counterfactual Reasoning** - "What if X had been different?"

### The Gap We're Filling

```
Current LLMs:                    Causal World Model:
┌─────────────────┐              ┌─────────────────────────────────┐
│ P(B|A) = high   │              │ A ──causes──> B                 │
│ (correlation)   │              │ P(B|do(A)) ≠ P(B|A)            │
│                 │              │ Counterfactual: A'→B'?          │
│ No mechanism    │              │ Explicit mechanism graph        │
│ No intervention │              │ Intervention & simulation       │
└─────────────────┘              └─────────────────────────────────┘
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CAUSAL WORLD MODEL PHASE-QUAD                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  INPUT PROCESSING                                                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │   Tokens     │→ │  Embeddings  │→ │Entity/Relation│              │   │
│  │  │              │  │              │  │  Extraction   │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CAUSAL GRAPH LAYER                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │   Variable   │  │    Edge      │  │   Structure  │              │   │
│  │  │   Encoder    │  │  Predictor   │  │   Learner    │              │   │
│  │  │  (nodes)     │  │  (A→B?)      │  │  (DAG)       │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                           ↓                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │  CAUSAL GRAPH:  Weather → Rain → WetGround                     │ │   │
│  │  │                    ↓                    ↑                       │ │   │
│  │  │                 Umbrella            Sprinkler                   │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  WORLD STATE MODULE                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  State       │  │   State      │  │   State      │              │   │
│  │  │  Encoder     │  │   Memory     │  │   Decoder    │              │   │
│  │  │  (observe)   │  │   (persist)  │  │   (query)    │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  World State: {rain: 0.8, wet_ground: 0.9, umbrella: 0.7, ...}     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  INTERVENTION MODULE (do-calculus)                                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  do(X=x)     │  │   Graph      │  │   Effect     │              │   │
│  │  │  Operator    │  │   Surgery    │  │   Propagator │              │   │
│  │  │              │  │  (cut edges) │  │              │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  P(Y|do(X=1)) = Σ P(Y|X=1,Pa) P(Pa)  [backdoor adjustment]        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  COUNTERFACTUAL REASONER                                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │   Abduction  │→ │   Action     │→ │  Prediction  │              │   │
│  │  │  (infer U)   │  │  (modify X)  │  │  (compute Y')│              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  "If rain hadn't happened, would ground be wet?"                    │   │
│  │  → Abduct: U (sprinkler was on)                                     │   │
│  │  → Action: do(rain=0)                                               │   │
│  │  → Predict: P(wet|do(rain=0), sprinkler=1) = 0.9                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  WORLD SIMULATOR                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │   Action     │  │    State     │  │   Outcome    │              │   │
│  │  │   Encoder    │  │  Transition  │  │   Predictor  │              │   │
│  │  │              │  │   Model      │  │              │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                      │   │
│  │  Simulate: Action A at State S → State S' (multi-step rollout)     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE-QUAD INTEGRATION                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Causal      │  │   Phase      │  │  Reflective  │              │   │
│  │  │  Attention   │  │   Memory     │  │  Validation  │              │   │
│  │  │  (graph-     │  │  (world      │  │  (causal     │              │   │
│  │  │   guided)    │  │   state)     │  │   coherence) │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│                               OUTPUT                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Causal Graph Layer

The foundation of causal reasoning - learns and maintains explicit causal structure.

```python
class CausalGraphLayer(nn.Module):
    """
    Learns causal graph structure from data.

    Key innovations:
    1. Differentiable DAG learning (NOTEARS-style)
    2. Variable-level abstraction from token embeddings
    3. Edge prediction with causal direction
    4. Integration with Phase memory for persistent graphs
    """

    def __init__(
        self,
        d_model: int,
        max_variables: int = 128,
        num_edge_types: int = 4,  # causes, prevents, enables, neutral
    ):
        # Variable encoder: token embeddings → variable embeddings
        self.variable_encoder = VariableEncoder(d_model)

        # Edge predictor: P(A→B | emb_A, emb_B)
        self.edge_predictor = EdgePredictor(d_model, num_edge_types)

        # DAG constraint: ensures acyclicity
        self.dag_constraint = DAGConstraint()

        # Graph memory: persistent causal knowledge
        self.graph_memory = CausalGraphMemory(max_variables)

    def forward(self, x, entities, relations):
        """
        Extract/update causal graph from input.

        Returns:
            adjacency: [V, V] weighted adjacency matrix
            edge_types: [V, V, E] edge type probabilities
            variables: [V, D] variable embeddings
        """
        pass
```

#### DAG Learning (NOTEARS-style)

```python
class DAGConstraint(nn.Module):
    """
    Differentiable acyclicity constraint.

    From NOTEARS: h(W) = tr(e^(W∘W)) - d = 0 iff W is DAG

    This allows gradient-based learning of DAG structure.
    """

    def compute_dag_loss(self, adjacency: Tensor) -> Tensor:
        """
        Compute DAG constraint violation.

        Args:
            adjacency: [V, V] weighted adjacency matrix

        Returns:
            dag_loss: scalar, 0 iff adjacency is DAG
        """
        d = adjacency.shape[0]
        # Matrix exponential of element-wise square
        M = torch.matrix_exp(adjacency * adjacency)
        # Trace minus dimension
        h = torch.trace(M) - d
        return h
```

### 2. World State Module

Maintains a differentiable representation of world state.

```python
class WorldStateModule(nn.Module):
    """
    Encodes, stores, and queries world state.

    State is represented as:
    - Variable values: {var_name: value} continuous [0,1]
    - Uncertainty: {var_name: confidence}
    - Temporal: state history for dynamics
    """

    def __init__(
        self,
        d_model: int,
        max_variables: int = 128,
        history_len: int = 16,
    ):
        # Encode observations into state
        self.state_encoder = StateEncoder(d_model)

        # Persistent state memory (integrates with Phase)
        self.state_memory = StateMemory(max_variables, history_len)

        # Query interface
        self.state_decoder = StateDecoder(d_model)

        # Uncertainty estimator
        self.uncertainty = UncertaintyEstimator(d_model)

    def observe(self, x: Tensor, entities: List[str]) -> WorldState:
        """Update world state from observation."""
        pass

    def query(self, variable: str) -> Tuple[Tensor, Tensor]:
        """Query variable value and confidence."""
        pass

    def get_state_vector(self) -> Tensor:
        """Get full state as vector for simulation."""
        pass
```

### 3. Intervention Module (do-calculus)

Implements Pearl's do-calculus for causal inference.

```python
class InterventionModule(nn.Module):
    """
    Implements do-calculus operations.

    Key operations:
    1. do(X=x): Intervene on variable X
    2. Graph surgery: Remove incoming edges to X
    3. Effect propagation: Compute downstream effects
    4. Backdoor/frontdoor adjustment
    """

    def __init__(self, d_model: int):
        self.intervention_encoder = InterventionEncoder(d_model)
        self.graph_surgeon = GraphSurgeon()
        self.effect_propagator = EffectPropagator(d_model)
        self.adjustment_computer = AdjustmentComputer()

    def do(
        self,
        variable: str,
        value: Tensor,
        causal_graph: CausalGraph,
        world_state: WorldState,
    ) -> WorldState:
        """
        Perform intervention do(variable=value).

        Steps:
        1. Graph surgery: remove edges INTO variable
        2. Set variable to value
        3. Propagate effects through graph
        4. Return modified world state
        """
        # Surgery: cut incoming edges
        modified_graph = self.graph_surgeon.cut_incoming(
            causal_graph, variable
        )

        # Set intervention
        modified_state = world_state.clone()
        modified_state.set(variable, value, confidence=1.0)

        # Propagate effects
        final_state = self.effect_propagator(
            modified_state, modified_graph
        )

        return final_state

    def compute_causal_effect(
        self,
        treatment: str,
        outcome: str,
        causal_graph: CausalGraph,
        world_state: WorldState,
    ) -> Tensor:
        """
        Compute P(outcome | do(treatment=1)) - P(outcome | do(treatment=0))

        Uses backdoor adjustment if valid adjustment set exists.
        """
        # Find adjustment set (backdoor criterion)
        adjustment_set = self.adjustment_computer.find_backdoor(
            causal_graph, treatment, outcome
        )

        if adjustment_set is not None:
            # Backdoor adjustment formula
            effect = self.backdoor_adjustment(
                treatment, outcome, adjustment_set, world_state
            )
        else:
            # Try frontdoor or other methods
            effect = self.frontdoor_adjustment(
                treatment, outcome, causal_graph, world_state
            )

        return effect
```

#### Backdoor Adjustment

```python
def backdoor_adjustment(
    self,
    treatment: str,
    outcome: str,
    adjustment_set: List[str],
    world_state: WorldState,
) -> Tensor:
    """
    P(Y|do(X)) = Σ_z P(Y|X,Z=z) P(Z=z)

    Where Z is the adjustment set satisfying backdoor criterion.
    """
    # Get distribution over adjustment variables
    z_probs = world_state.get_marginal(adjustment_set)

    # For each configuration of Z
    effect = 0.0
    for z_config, z_prob in z_probs:
        # P(Y|X=1, Z=z) - P(Y|X=0, Z=z)
        p_y_x1_z = self.conditional_prob(outcome, treatment, 1, z_config)
        p_y_x0_z = self.conditional_prob(outcome, treatment, 0, z_config)
        effect += (p_y_x1_z - p_y_x0_z) * z_prob

    return effect
```

### 4. Counterfactual Reasoner

Three-step counterfactual reasoning: Abduction → Action → Prediction.

```python
class CounterfactualReasoner(nn.Module):
    """
    Implements counterfactual reasoning via three steps:

    1. Abduction: Given evidence, infer latent variables U
    2. Action: Modify the model (intervention)
    3. Prediction: Compute outcome under modified model

    Example: "If the sprinkler hadn't been on, would the grass be wet?"
    - Abduction: Infer rain status from evidence
    - Action: do(sprinkler=0)
    - Prediction: P(wet_grass | do(sprinkler=0), rain_inferred)
    """

    def __init__(self, d_model: int):
        self.abductor = Abductor(d_model)
        self.action_encoder = ActionEncoder(d_model)
        self.predictor = OutcomePredictor(d_model)

    def counterfactual(
        self,
        factual_evidence: Dict[str, Tensor],  # What we observed
        counterfactual_action: Tuple[str, Tensor],  # What if X had been x'?
        query_variable: str,  # What would Y have been?
        causal_graph: CausalGraph,
        world_state: WorldState,
    ) -> Tuple[Tensor, Tensor]:
        """
        Compute counterfactual: P(Y_x' | evidence)

        Returns:
            value: predicted counterfactual value
            confidence: confidence in prediction
        """
        # Step 1: Abduction - infer latent variables
        latents = self.abductor(
            factual_evidence, causal_graph, world_state
        )

        # Step 2: Action - apply intervention
        var, val = counterfactual_action
        modified_state = self.intervention_module.do(
            var, val, causal_graph, world_state
        )

        # Merge inferred latents with modified state
        modified_state.update_latents(latents)

        # Step 3: Prediction - compute counterfactual outcome
        cf_value, confidence = self.predictor(
            query_variable, modified_state, causal_graph
        )

        return cf_value, confidence
```

### 5. World Simulator

Simulates world dynamics given actions.

```python
class WorldSimulator(nn.Module):
    """
    Simulates world state evolution.

    Given:
    - Current state S
    - Action A
    - Causal graph G

    Predicts:
    - Next state S'
    - Can do multi-step rollouts
    """

    def __init__(
        self,
        d_model: int,
        num_actions: int,
        rollout_steps: int = 10,
    ):
        self.action_encoder = ActionEncoder(d_model, num_actions)
        self.transition_model = TransitionModel(d_model)
        self.reward_predictor = RewardPredictor(d_model)
        self.rollout_steps = rollout_steps

    def step(
        self,
        state: WorldState,
        action: Tensor,
        causal_graph: CausalGraph,
    ) -> Tuple[WorldState, Tensor]:
        """
        Single simulation step.

        Returns:
            next_state: WorldState after action
            reward: immediate reward signal
        """
        # Encode action
        action_embed = self.action_encoder(action)

        # Predict state change using causal graph
        state_delta = self.transition_model(
            state.get_state_vector(),
            action_embed,
            causal_graph.adjacency,
        )

        # Apply delta respecting causal structure
        next_state = state.apply_delta(state_delta, causal_graph)

        # Predict reward
        reward = self.reward_predictor(state, action, next_state)

        return next_state, reward

    def rollout(
        self,
        initial_state: WorldState,
        action_sequence: List[Tensor],
        causal_graph: CausalGraph,
    ) -> List[WorldState]:
        """
        Multi-step rollout for planning.
        """
        states = [initial_state]
        state = initial_state

        for action in action_sequence:
            state, _ = self.step(state, action, causal_graph)
            states.append(state)

        return states

    def imagine(
        self,
        initial_state: WorldState,
        goal_state: WorldState,
        causal_graph: CausalGraph,
        max_steps: int = 10,
    ) -> List[Tensor]:
        """
        Plan action sequence to reach goal state.

        Uses causal graph to identify which variables to intervene on.
        """
        # Find causal path from controllable variables to goal variables
        controllable = self.get_controllable_variables(causal_graph)
        goal_vars = goal_state.get_changed_variables(initial_state)

        # Plan interventions
        plan = self.plan_interventions(
            initial_state, goal_vars, controllable, causal_graph
        )

        return plan
```

### 6. Integration with Phase-Quad

```python
class CausalPhaseQuadBlock(nn.Module):
    """
    Phase-Quad block augmented with causal reasoning.

    Integrations:
    1. Causal graph stored in Phase memory
    2. Attention guided by causal structure
    3. World state persists across tokens
    4. Reflective loop validates causal coherence
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        max_variables: int = 128,
    ):
        # Core Phase-Quad
        self.phase_attention = PhaseAttention(d_model, num_heads)
        self.phase_integrator = PhaseIntegrator(d_model)

        # Causal components
        self.causal_graph_layer = CausalGraphLayer(d_model, max_variables)
        self.world_state = WorldStateModule(d_model, max_variables)
        self.intervention = InterventionModule(d_model)
        self.counterfactual = CounterfactualReasoner(d_model)
        self.simulator = WorldSimulator(d_model)

        # Causal attention: bias attention by causal structure
        self.causal_attention_bias = CausalAttentionBias(d_model, num_heads)

        # Reflective validation with causal coherence
        self.causal_critic = CausalCoherenceCritic(d_model)

    def forward(
        self,
        x: Tensor,
        phase_state: PhaseState,
        causal_state: Optional[CausalState] = None,
    ) -> Tuple[Tensor, PhaseState, CausalState]:
        """
        Forward with causal reasoning.
        """
        B, N, D = x.shape

        # Initialize causal state if needed
        if causal_state is None:
            causal_state = CausalState.create(B, self.max_variables)

        # 1. Extract/update causal graph from input
        entities, relations = self.extract_entities_relations(x)
        causal_graph = self.causal_graph_layer(x, entities, relations)

        # 2. Update world state from observations
        world_state = self.world_state.observe(x, entities)

        # 3. Compute causal attention bias
        # Tokens mentioning causally-related entities attend more
        causal_bias = self.causal_attention_bias(
            x, causal_graph, entities
        )

        # 4. Phase attention with causal bias
        attended = self.phase_attention(
            x, phase_state.content_memory,
            attention_bias=causal_bias,
        )

        # 5. Update phase state
        new_phase_state = self.phase_integrator(attended, phase_state)

        # 6. Store causal knowledge in phase memory
        new_phase_state.causal_graph = causal_graph
        new_phase_state.world_state = world_state

        # 7. Validate causal coherence (for reflective loop)
        coherence = self.causal_critic(x, attended, causal_graph)

        causal_state.graph = causal_graph
        causal_state.world_state = world_state
        causal_state.coherence = coherence

        return attended, new_phase_state, causal_state
```

---

## Training Strategy

### Phase 1: Causal Graph Learning

Train on datasets with known causal structure.

```python
# Datasets:
# 1. Synthetic causal graphs with observations
# 2. Knowledge graphs with causal annotations
# 3. Scientific papers with extracted causal claims

def causal_graph_loss(predicted_graph, true_graph):
    # Edge prediction loss
    edge_loss = F.binary_cross_entropy(
        predicted_graph.adjacency,
        true_graph.adjacency,
    )

    # DAG constraint
    dag_loss = dag_constraint(predicted_graph.adjacency)

    # Edge type loss
    type_loss = F.cross_entropy(
        predicted_graph.edge_types,
        true_graph.edge_types,
    )

    return edge_loss + 0.1 * dag_loss + type_loss
```

### Phase 2: Intervention Training

Train on intervention-outcome pairs.

```python
# Data: (context, intervention, outcome) triples
# Sources:
# 1. Randomized controlled trials (medical, A/B tests)
# 2. Simulated environments with known dynamics
# 3. Counterfactual datasets (what-if scenarios)

def intervention_loss(model, context, intervention, true_outcome):
    # Extract causal graph
    graph = model.causal_graph_layer(context)
    state = model.world_state.observe(context)

    # Perform intervention
    var, val = intervention
    predicted_state = model.intervention.do(var, val, graph, state)

    # Compare with true outcome
    return F.mse_loss(predicted_state[outcome_var], true_outcome)
```

### Phase 3: Counterfactual Training

```python
def counterfactual_loss(model, factual, counterfactual_query, true_cf):
    """
    Train on counterfactual examples.

    factual: What actually happened
    counterfactual_query: (what_if_var, what_if_value, query_var)
    true_cf: True counterfactual outcome
    """
    graph = model.causal_graph_layer(factual["context"])
    state = model.world_state.observe(factual["context"])

    cf_var, cf_val, query_var = counterfactual_query

    predicted_cf, confidence = model.counterfactual.counterfactual(
        factual["evidence"],
        (cf_var, cf_val),
        query_var,
        graph,
        state,
    )

    return F.mse_loss(predicted_cf, true_cf)
```

### Phase 4: End-to-End with Language Modeling

```python
def causal_lm_loss(model, tokens, causal_annotations=None):
    """
    Combined language modeling + causal reasoning loss.
    """
    # Standard LM loss
    logits = model(tokens)
    lm_loss = F.cross_entropy(logits, tokens[:, 1:])

    # Causal coherence loss (if annotations available)
    if causal_annotations is not None:
        graph = model.get_causal_graph()
        coherence_loss = causal_graph_loss(graph, causal_annotations)
    else:
        # Self-supervised: DAG constraint + consistency
        graph = model.get_causal_graph()
        coherence_loss = dag_constraint(graph.adjacency)

    return lm_loss + 0.1 * coherence_loss
```

---

## Inference Modes

### Mode 1: Causal Explanation

```python
def explain_causally(model, observation):
    """
    Generate causal explanation for observation.

    "Why is the ground wet?"
    → Extract: ground=wet
    → Query graph: causes(ground=wet) = {rain, sprinkler}
    → Check state: rain=0.9, sprinkler=0.2
    → Explain: "The ground is wet because it rained (P=0.9)"
    """
    graph = model.get_causal_graph()
    state = model.get_world_state()

    target_var = extract_target(observation)
    causes = graph.get_causes(target_var)

    explanations = []
    for cause in causes:
        strength = state.query(cause)[0]
        effect = model.intervention.compute_causal_effect(
            cause, target_var, graph, state
        )
        explanations.append((cause, strength, effect))

    return sorted(explanations, key=lambda x: -x[1] * x[2])
```

### Mode 2: What-If Reasoning

```python
def what_if(model, context, intervention_query):
    """
    Answer what-if questions.

    "What would happen if we turned off the sprinkler?"
    → Intervention: do(sprinkler=0)
    → Propagate through graph
    → Report affected variables
    """
    graph = model.get_causal_graph()
    state = model.get_world_state()

    var, val = parse_intervention(intervention_query)

    new_state = model.intervention.do(var, val, graph, state)

    changes = state.diff(new_state)
    return changes
```

### Mode 3: Planning with Causal Model

```python
def plan_actions(model, current_state, goal):
    """
    Plan actions to achieve goal using causal model.

    "How can I make the grass wet without wasting water?"
    → Goal: grass=wet
    → Constraint: water_usage < threshold
    → Find: minimal intervention set
    """
    graph = model.get_causal_graph()

    goal_vars = parse_goal(goal)
    constraints = parse_constraints(goal)

    plan = model.simulator.imagine(
        current_state,
        goal_vars,
        graph,
        constraints=constraints,
    )

    return plan
```

---

## Benchmarks

### 1. Causal Discovery Accuracy

```python
def benchmark_causal_discovery(model, test_graphs):
    """
    Test ability to recover causal structure.

    Metrics:
    - SHD (Structural Hamming Distance)
    - F1 for edge prediction
    - DAG validity
    """
    results = []
    for true_graph, observations in test_graphs:
        predicted_graph = model.causal_graph_layer(observations)

        shd = structural_hamming_distance(predicted_graph, true_graph)
        f1 = edge_f1(predicted_graph, true_graph)
        is_dag = is_valid_dag(predicted_graph)

        results.append({"shd": shd, "f1": f1, "is_dag": is_dag})

    return aggregate(results)
```

### 2. Intervention Prediction

```python
def benchmark_interventions(model, intervention_data):
    """
    Test ability to predict intervention outcomes.

    Metrics:
    - MSE on outcome prediction
    - Calibration of confidence
    """
    errors = []
    for context, intervention, true_outcome in intervention_data:
        graph = model.causal_graph_layer(context)
        state = model.world_state.observe(context)

        var, val = intervention
        predicted_state = model.intervention.do(var, val, graph, state)

        error = (predicted_state[outcome_var] - true_outcome) ** 2
        errors.append(error)

    return {"mse": mean(errors), "rmse": sqrt(mean(errors))}
```

### 3. Counterfactual Accuracy

```python
def benchmark_counterfactuals(model, cf_data):
    """
    Test counterfactual reasoning.

    Uses datasets with known counterfactual outcomes.
    """
    results = []
    for factual, cf_query, true_cf in cf_data:
        predicted_cf, confidence = model.counterfactual.counterfactual(
            factual["evidence"],
            cf_query[:2],
            cf_query[2],
            model.get_causal_graph(),
            model.get_world_state(),
        )

        error = abs(predicted_cf - true_cf)
        results.append({"error": error, "confidence": confidence})

    return aggregate(results)
```

---

## CLI Flags

```bash
# Enable causal world model
python train_hard_probes.py --enable-causal-world-model

# Causal graph settings
--cwm-max-variables 128
--cwm-dag-penalty 0.1
--cwm-edge-threshold 0.5

# Intervention settings
--cwm-intervention-training
--cwm-intervention-data PATH

# Counterfactual settings
--cwm-counterfactual-training
--cwm-cf-data PATH

# Simulation settings
--cwm-enable-simulator
--cwm-rollout-steps 10

# Benchmarks
--test-causal-world-model
--cwm-benchmark-discovery
--cwm-benchmark-intervention
--cwm-benchmark-counterfactual
```

---

## Expected Capabilities

After training, the model should be able to:

| Capability | Example |
|------------|---------|
| **Causal Explanation** | "Why is X happening?" → "Because A caused B which caused X" |
| **Intervention Prediction** | "What if I do X?" → "Then Y will change by Z" |
| **Counterfactual Reasoning** | "Would Y have happened if not X?" → "No, because..." |
| **Causal Planning** | "How to achieve X?" → "Do A, then B" |
| **Confounding Detection** | "Is A→B causal or confounded?" → "Confounded by C" |

---

## Comparison with Existing Approaches

| Aspect | Standard LLM | Causal LLM (Ours) | True Causal Model |
|--------|--------------|-------------------|-------------------|
| Correlation | ✓ Captures | ✓ Captures | ✓ Captures |
| Causal Direction | ✗ Often wrong | ✓ Learned graph | ✓ Given/learned |
| Intervention | ✗ Confuses with conditioning | ✓ do-calculus | ✓ Exact |
| Counterfactual | ✗ Superficial | ✓ Three-step | ✓ Exact |
| Generalization | ✗ In-distribution only | ✓ Causal transfer | ✓ Perfect |

---

## Research Directions

1. **Causal Abstraction**: Learning hierarchical causal graphs at multiple levels
2. **Causal Transfer**: Using causal knowledge from one domain in another
3. **Active Causal Learning**: Choosing interventions to learn causal structure
4. **Causal Language Grounding**: Grounding language in causal world models
5. **Multi-Agent Causal Modeling**: Modeling other agents' causal beliefs

---

## References

1. Pearl, J. (2009). Causality: Models, Reasoning, and Inference
2. Peters, J., Janzing, D., & Schölkopf, B. (2017). Elements of Causal Inference
3. Zheng, X., et al. (2018). DAGs with NO TEARS
4. Ke, N. R., et al. (2019). Learning Neural Causal Models from Unknown Interventions
5. Schölkopf, B., et al. (2021). Toward Causal Representation Learning
