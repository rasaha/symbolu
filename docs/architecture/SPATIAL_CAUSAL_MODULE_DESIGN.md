# Spatial-Causal Module Design (V10.11)

## Overview

The Spatial-Causal Module extends the Causal World Model (V10.10) with spatial reasoning capabilities, enabling the Phase-Quad LLM to understand how spatial configurations cause effects in the physical world.

**Key Insight**: Spatial relationships are often causal mechanisms. A ball falls because it's positioned at the edge of a table. Fire spreads because rooms are adjacent. Understanding causality requires understanding space.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SPATIAL-CAUSAL MODULE (V10.11)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SPATIAL STATE TRACKING                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │ SpatialObj  │  │ SpatialWorld│  │  SpatialRelationGraph       │  │   │
│  │  │ - position  │  │ - objects   │  │  - nodes: objects           │  │   │
│  │  │ - orient    │→ │ - relations │→ │  - edges: spatial relations │  │   │
│  │  │ - scale     │  │ - bounds    │  │  - transitive inference     │  │   │
│  │  │ - bbox      │  │ - physics   │  │  - relation types           │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   PHYSICS-GROUNDED CAUSAL EDGES                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐     │   │
│  │  │ ContactEdge  │  │ GravityEdge  │  │ PropagationEdge        │     │   │
│  │  │ A touches B  │  │ unsupported  │  │ spreads through space  │     │   │
│  │  │ → force      │  │ → falls      │  │ → affects neighbors    │     │   │
│  │  └──────────────┘  └──────────────┘  └────────────────────────┘     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐     │   │
│  │  │ CollisionEdge│  │ ContainEdge  │  │ OcclusionEdge          │     │   │
│  │  │ paths cross  │  │ A inside B   │  │ A blocks B from C      │     │   │
│  │  │ → impact     │  │ → constrained│  │ → visibility/access    │     │   │
│  │  └──────────────┘  └──────────────┘  └────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  SPATIAL INTERVENTION OPERATORS                      │   │
│  │                                                                       │   │
│  │   do(move(X, Δpos))      - translate object X by Δpos               │   │
│  │   do(rotate(X, Δθ))      - rotate object X by angle Δθ              │   │
│  │   do(place(X, Y, rel))   - place X relative to Y with relation      │   │
│  │   do(remove(X))          - remove object X from world               │   │
│  │   do(resize(X, scale))   - change scale of object X                 │   │
│  │   do(connect(X, Y))      - create physical connection               │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 SPATIAL COUNTERFACTUAL REASONING                     │   │
│  │                                                                       │   │
│  │  1. ABDUCTION: Infer spatial configuration from observations        │   │
│  │     "The vase broke" → infer it was near edge, got pushed           │   │
│  │                                                                       │   │
│  │  2. ACTION: Apply spatial intervention in latent space              │   │
│  │     do(position(vase) = center_of_table)                            │   │
│  │                                                                       │   │
│  │  3. PREDICTION: Simulate with modified spatial state                │   │
│  │     vase at center → push doesn't reach edge → vase intact          │   │
│  │                                                                       │   │
│  │  Result: "If the vase had been in the center, it wouldn't have      │   │
│  │           broken when pushed"                                        │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              INTEGRATION WITH CAUSAL WORLD MODEL                     │   │
│  │                                                                       │   │
│  │  CausalGraph ──extend──→ SpatialCausalGraph                         │   │
│  │      │                        │                                      │   │
│  │      │ variables              │ spatial variables (pos, orient)     │   │
│  │      │ edges                  │ physics-grounded edges              │   │
│  │      │ interventions          │ spatial interventions               │   │
│  │      ↓                        ↓                                      │   │
│  │  WorldState ──extend──→ SpatialWorldState                           │   │
│  │      │                        │                                      │   │
│  │      │ entities               │ spatial objects                     │   │
│  │      │ relations              │ spatial relations                   │   │
│  │      │ simulation             │ physics simulation                  │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Spatial State Tracking

#### SpatialObject
Represents an object in 3D space with full geometric state.

```python
@dataclass
class SpatialObject:
    id: str
    position: torch.Tensor      # [x, y, z]
    orientation: torch.Tensor   # [qw, qx, qy, qz] quaternion
    scale: torch.Tensor         # [sx, sy, sz]
    velocity: torch.Tensor      # [vx, vy, vz]
    angular_velocity: torch.Tensor  # [wx, wy, wz]
    mass: float
    is_static: bool
    bbox: torch.Tensor          # [min_x, min_y, min_z, max_x, max_y, max_z]
    properties: Dict[str, Any]  # custom properties (color, material, etc.)
```

#### SpatialWorld
Container for all spatial objects and their relationships.

```python
class SpatialWorld:
    objects: Dict[str, SpatialObject]
    relation_graph: SpatialRelationGraph
    bounds: torch.Tensor  # world boundaries
    gravity: torch.Tensor  # gravity vector
    time: float
```

#### SpatialRelationGraph
Graph encoding spatial relationships between objects.

**Relation Types**:
- **Topological**: inside, outside, touching, overlapping
- **Directional**: above, below, left, right, front, behind
- **Distance**: near, far, adjacent
- **Support**: on, under, supported_by
- **Containment**: contains, contained_by
- **Alignment**: aligned, perpendicular, parallel

```python
class SpatialRelation(Enum):
    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    IN_FRONT_OF = "in_front_of"
    BEHIND = "behind"
    INSIDE = "inside"
    OUTSIDE = "outside"
    ON = "on"
    UNDER = "under"
    NEAR = "near"
    FAR = "far"
    TOUCHING = "touching"
    CONTAINS = "contains"
    SUPPORTED_BY = "supported_by"
    ALIGNED_WITH = "aligned_with"
    BLOCKS = "blocks"
```

### 2. Physics-Grounded Causal Edges

#### PhysicsCausalType
Categories of physics-based causation.

```python
class PhysicsCausalType(Enum):
    CONTACT = "contact"         # A touches B → force transfer
    GRAVITY = "gravity"         # unsupported object → falls
    COLLISION = "collision"     # paths intersect → impact
    PROPAGATION = "propagation" # effect spreads through space
    CONTAINMENT = "containment" # A inside B → constrained by B
    OCCLUSION = "occlusion"     # A blocks B from C
    SUPPORT = "support"         # A supports B → B doesn't fall
    FRICTION = "friction"       # surface contact → resistance
    ELASTICITY = "elasticity"   # collision → bounce
```

#### PhysicsCausalEdge
Causal edge grounded in physics.

```python
@dataclass
class PhysicsCausalEdge:
    source: str              # source object id
    target: str              # target object id
    physics_type: PhysicsCausalType
    strength: float          # causal strength [0, 1]
    spatial_condition: Callable  # when does this edge activate?
    effect: Callable         # what effect does it produce?
```

#### Example Physics-Causal Rules

```python
# Gravity rule: unsupported objects fall
GravityRule = PhysicsCausalEdge(
    source="*",
    target="*",
    physics_type=PhysicsCausalType.GRAVITY,
    spatial_condition=lambda obj, world: not is_supported(obj, world),
    effect=lambda obj: obj.velocity += world.gravity * dt
)

# Contact propagation: fire spreads to adjacent objects
FireSpreadRule = PhysicsCausalEdge(
    source="fire",
    target="*",
    physics_type=PhysicsCausalType.PROPAGATION,
    spatial_condition=lambda src, tgt: distance(src, tgt) < spread_radius,
    effect=lambda tgt: tgt.properties["on_fire"] = True
)

# Support rule: object on surface is supported
SupportRule = PhysicsCausalEdge(
    source="surface",
    target="*",
    physics_type=PhysicsCausalType.SUPPORT,
    spatial_condition=lambda surf, obj: is_on(obj, surf),
    effect=lambda obj: obj.is_supported = True
)
```

### 3. Spatial Intervention Operators

Extend do-calculus with spatial operations.

#### MoveIntervention
```python
def do_move(world: SpatialWorld, obj_id: str, new_position: torch.Tensor):
    """
    do(position(X) = new_position)

    Surgically set object position, breaking all incoming causal edges
    related to position, then propagate effects.
    """
    obj = world.objects[obj_id]
    old_position = obj.position.clone()

    # Graph surgery: cut incoming position edges
    world.relation_graph.cut_incoming_edges(obj_id, edge_type="position")

    # Set new position
    obj.position = new_position

    # Update spatial relations
    world.relation_graph.recompute_relations(obj_id)

    # Propagate causal effects
    return propagate_spatial_effects(world, obj_id, old_position)
```

#### RotateIntervention
```python
def do_rotate(world: SpatialWorld, obj_id: str, rotation: torch.Tensor):
    """
    do(orientation(X) = rotation)

    Rotate object and propagate orientation-dependent effects.
    """
    obj = world.objects[obj_id]
    obj.orientation = quaternion_multiply(obj.orientation, rotation)

    # Recompute directional relations (front, behind, etc.)
    world.relation_graph.recompute_directional_relations(obj_id)

    return propagate_orientation_effects(world, obj_id)
```

#### PlaceIntervention
```python
def do_place(world: SpatialWorld, obj_id: str,
             reference_id: str, relation: SpatialRelation):
    """
    do(place(X, relative_to=Y, relation=ON))

    Place object X in specified spatial relation to Y.
    """
    obj = world.objects[obj_id]
    reference = world.objects[reference_id]

    # Compute target position based on relation
    target_position = compute_relation_position(obj, reference, relation)

    # Apply move intervention
    return do_move(world, obj_id, target_position)
```

### 4. Spatial Counterfactual Reasoning

Three-step counterfactual process with spatial grounding.

#### Step 1: Spatial Abduction
Infer spatial configuration from observations.

```python
def spatial_abduction(observation: str, world: SpatialWorld) -> SpatialWorld:
    """
    Given observation, infer most likely spatial configuration.

    Example:
        observation: "The vase broke"
        inferred: vase was at edge, got pushed, fell
    """
    # Encode observation
    obs_embedding = encode_observation(observation)

    # Infer spatial state that explains observation
    inferred_positions = position_inference_network(obs_embedding, world)
    inferred_relations = relation_inference_network(obs_embedding, world)

    # Construct abduced world state
    abduced_world = world.clone()
    for obj_id, position in inferred_positions.items():
        abduced_world.objects[obj_id].position = position

    return abduced_world
```

#### Step 2: Spatial Intervention
Apply counterfactual spatial change.

```python
def spatial_intervention(world: SpatialWorld,
                         intervention: SpatialIntervention) -> SpatialWorld:
    """
    Apply spatial intervention to create counterfactual world.

    Example:
        intervention: do(position(vase) = center_of_table)
    """
    counterfactual_world = world.clone()

    if intervention.type == "move":
        do_move(counterfactual_world, intervention.obj_id, intervention.value)
    elif intervention.type == "rotate":
        do_rotate(counterfactual_world, intervention.obj_id, intervention.value)
    elif intervention.type == "place":
        do_place(counterfactual_world, intervention.obj_id,
                intervention.reference_id, intervention.relation)

    return counterfactual_world
```

#### Step 3: Spatial Prediction
Simulate counterfactual world forward.

```python
def spatial_prediction(world: SpatialWorld,
                       steps: int = 10) -> List[SpatialWorld]:
    """
    Simulate world forward with physics to predict outcomes.

    Example:
        vase at center + push → vase moves but stays on table → intact
    """
    trajectory = [world]
    current_world = world.clone()

    for step in range(steps):
        # Apply physics rules
        current_world = physics_step(current_world)

        # Check for causal events (collisions, falls, etc.)
        events = detect_causal_events(current_world)

        # Apply event effects
        for event in events:
            apply_causal_effect(current_world, event)

        trajectory.append(current_world.clone())

    return trajectory
```

## Integration with Phase-Quad

### SpatialCausalPhaseQuadBlock

```python
class SpatialCausalPhaseQuadBlock(nn.Module):
    """
    Phase-Quad block with spatial-causal reasoning.

    Extends CausalPhaseQuadBlock with:
    - Spatial state encoder
    - Physics-grounded causal edges
    - Spatial intervention module
    - Spatial counterfactual reasoning
    """

    def __init__(self, config):
        super().__init__()

        # Base Phase-Quad components
        self.phase_quad = PhaseQuadBlock(config)

        # Causal World Model (V10.10)
        self.causal_graph_layer = CausalGraphLayer(config)
        self.intervention_module = InterventionModule(config)
        self.counterfactual_reasoner = CounterfactualReasoner(config)

        # Spatial extensions (V10.11)
        self.spatial_encoder = SpatialStateEncoder(config)
        self.spatial_relation_predictor = SpatialRelationPredictor(config)
        self.physics_causal_layer = PhysicsCausalLayer(config)
        self.spatial_intervention_module = SpatialInterventionModule(config)
        self.spatial_counterfactual = SpatialCounterfactualReasoner(config)
        self.physics_simulator = PhysicsSimulator(config)

    def forward(self, x, phase_state, spatial_world=None):
        # 1. Encode spatial state if provided
        if spatial_world is not None:
            spatial_embedding = self.spatial_encoder(spatial_world)
            x = x + spatial_embedding

        # 2. Run Phase-Quad attention
        x, phase_state = self.phase_quad(x, phase_state)

        # 3. Extract spatial objects from hidden states
        spatial_objects = self.spatial_encoder.extract_objects(x)

        # 4. Predict spatial relations
        spatial_relations = self.spatial_relation_predictor(spatial_objects)

        # 5. Build physics-grounded causal graph
        causal_graph = self.physics_causal_layer(spatial_objects, spatial_relations)

        # 6. Update world state
        world_state = self.update_spatial_world(spatial_objects, spatial_relations)

        return x, phase_state, SpatialCausalState(
            causal_graph=causal_graph,
            spatial_world=world_state,
            spatial_relations=spatial_relations
        )
```

## Training Strategy

### Spatial-Causal Pre-training Tasks

1. **Spatial Relation Prediction**: Given object descriptions, predict spatial relations
2. **Physics Outcome Prediction**: Given initial state + action, predict outcome
3. **Spatial Counterfactual QA**: "What would happen if X was at position Y?"
4. **Causal Chain Tracing**: Trace spatial-causal chains through events

### Datasets

1. **CLEVR**: Spatial reasoning with simple 3D objects
2. **PHYRE**: Physical reasoning benchmark
3. **IntPhys**: Intuitive physics dataset
4. **Physion**: Physical prediction benchmark
5. **PTR**: Physical reasoning in text

### Loss Functions

```python
# Spatial relation prediction loss
L_spatial = CrossEntropy(predicted_relations, true_relations)

# Physics prediction loss
L_physics = MSE(predicted_trajectory, true_trajectory)

# Counterfactual consistency loss
L_counterfactual = MSE(
    predict(do(move(X, pos))),
    simulate(world_with_X_at_pos)
)

# Total spatial-causal loss
L_total = L_spatial + λ_physics * L_physics + λ_cf * L_counterfactual
```

## Inference Modes

### 1. Spatial Query Mode
Answer questions about spatial configurations.

```
Input: "Is the cup on the table?"
Process: Extract objects → Compute relations → Query relation graph
Output: "Yes, the cup is on the table"
```

### 2. Physics Prediction Mode
Predict physical outcomes.

```
Input: "What happens if I push the ball?"
Process: Identify ball → Apply force → Simulate trajectory
Output: "The ball rolls across the table and falls off the edge"
```

### 3. Spatial Counterfactual Mode
Reason about alternative spatial configurations.

```
Input: "Would the vase have broken if it was in the center of the table?"
Process:
  1. Abduct: Infer vase was at edge when pushed
  2. Intervene: do(position(vase) = center)
  3. Predict: Simulate push → vase moves but stays on table
Output: "No, if the vase had been in the center, it would not have broken"
```

### 4. Spatial Planning Mode
Plan actions to achieve spatial goals.

```
Input: "How do I get the book that's behind the box?"
Process:
  1. Identify obstacle (box blocks book)
  2. Plan intervention: do(move(box, aside))
  3. Verify: book now reachable
Output: "Move the box to the left, then reach for the book"
```

## Benchmarks

### Spatial Reasoning Benchmarks
- Spatial relation accuracy
- Multi-hop spatial inference
- Viewpoint transformation

### Physics Reasoning Benchmarks
- Trajectory prediction accuracy
- Collision detection
- Support/stability prediction

### Counterfactual Benchmarks
- Spatial counterfactual accuracy
- Physical counterfactual consistency
- Intervention effect prediction

## Version History

- V10.10: Causal World Model (DAG learning, do-calculus, counterfactuals)
- **V10.11**: Spatial-Causal Module (spatial state, physics causation, spatial interventions)

## References

1. Pearl, J. (2009). Causality: Models, Reasoning, and Inference
2. Battaglia, P. et al. (2013). Simulation as an engine of physical scene understanding
3. Ullman, T. et al. (2017). Mind Games: Game Engines as an Architecture for Intuitive Physics
4. Yi, K. et al. (2020). CLEVRER: Collision Events for Video Representation and Reasoning
