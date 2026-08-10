# Ontological Layer Projection Design Specification

**Document Version:** 1.0
**Document Status:** DESIGN-ONLY (Pre-Implementation)
**Effective Date:** 2025-12-15
**Enforcement:** None (design phase)

---

## Executive Summary

Ontological layers in this system are **projection lenses**, not containers or abstraction levels. The same invariant structural configuration, when projected through different layers, produces different influence patterns—affecting reachability, constraint propagation, and stabilization behavior—without any semantic transformation occurring internally. This document specifies the architectural design for the layer projection system, ensuring it preserves the core invariants: no semantics, no probability, full determinism, complete auditability.

**Core Principle:** The system computes invariant structure and lawful influence under projection; meaning is an observer-side phenomenon, not an internal operation.

---

## 1. Foundational Concepts

### 1.1 What Ontological Layers Are

| Layers ARE | Layers ARE NOT |
|------------|----------------|
| Projection functions over structure | Containers where structures live |
| Constraint activation masks | Abstraction levels |
| Deterministic lenses | Semantic contexts |
| First-class compositional objects | Implicit environmental state |
| Binary selectors (active/inactive) | Weighted influence modulators |

### 1.2 The Invariant/Variant Separation

**Invariant across ALL projections:**
- Node identity (`node_id`, `structural_hash`)
- Edge existence (the edge either exists or doesn't)
- Graph topology (connectivity structure)
- Node types and flags (the data itself)

**Variant BY projection:**
- Which edges are *active* for influence propagation
- Computed reachability (under active edges)
- Constraint satisfaction verdicts
- Influence footprint pattern

### 1.3 No Privileged Base Layer

There is no "default" or "ground truth" layer. All layers are equally valid projections of the same underlying structure. The system never operates on structure without an explicit layer context. This prevents semantic assumptions from hiding in an implicit "real" layer.

---

## 2. Core Data Structures

### 2.1 Ontological Layer

```
OntologicalLayer:
    layer_id: str (hex, 16-32 chars)
    layer_hash: str (hex, 16-32 chars, deterministic from content)

    # Activation masks (binary only)
    active_edge_types: FrozenSet[int]      # Which edge types propagate
    active_node_flags: FrozenSet[int]      # Which flag indices participate
    active_constraint_rules: FrozenSet[int] # Which rules fire

    # Structural metadata
    layer_depth: int                        # Position in lattice (0 = most constrained)
    composable: bool                        # Can this layer be composed with others
```

### 2.2 Projection Result

```
ProjectionResult:
    source_graph_hash: str
    layer_id: str

    # Computed under this projection
    active_edges: Tuple[EdgeID, ...]
    suppressed_edges: Tuple[EdgeID, ...]
    reachability_matrix: Tuple[Tuple[int, ...], ...]  # Binary 0/1
    constraint_verdicts: Tuple[Tuple[ConstraintID, bool], ...]

    # Influence pattern
    influence_footprint: InfluencePattern

    # Audit trail
    projection_trace: ProjectionTrace
    result_hash: str
```

### 2.3 Influence Pattern

```
InfluencePattern:
    origin_node_ids: Tuple[str, ...]        # Where influence originates
    reach_set: FrozenSet[str]               # Node IDs reachable under projection
    propagation_depth: int                  # Maximum propagation distance
    boundary_nodes: FrozenSet[str]          # Nodes at propagation boundary
    pattern_hash: str                       # Deterministic hash of pattern
```

### 2.4 Projection Trace

```
ProjectionTrace:
    layer_id: str
    steps: Tuple[ProjectionStep, ...]

ProjectionStep:
    step_type: StepType (EDGE_ACTIVATION | NODE_FILTER | CONSTRAINT_CHECK)
    input_state_hash: str
    output_state_hash: str
    elements_affected: Tuple[str, ...]      # IDs of affected elements
```

---

## 3. Layer Algebra

### 3.1 Composition Operations

Layers form a **Boolean algebra** under these operations:

| Operation | Notation | Semantics |
|-----------|----------|-----------|
| **Sequential** | `L1 >> L2` | Project through L1, then L2 on result |
| **Intersection** | `L1 & L2` | Only constraints active in BOTH layers |
| **Union** | `L1 \| L2` | Constraints active in EITHER layer |
| **Complement** | `~L1` | Invert all activation masks |
| **Identity** | `I` | All constraints active (universal projection) |
| **Null** | `O` | No constraints active (null projection) |

### 3.2 Algebraic Laws

The algebra must satisfy:

```
Associativity:    (L1 & L2) & L3 = L1 & (L2 & L3)
Commutativity:    L1 & L2 = L2 & L1
Identity:         L & I = L
Annihilation:     L & O = O
Idempotence:      L & L = L
Complement:       L & ~L = O
                  L | ~L = I
De Morgan:        ~(L1 & L2) = ~L1 | ~L2
                  ~(L1 | L2) = ~L1 & ~L2
```

### 3.3 Sequential Composition Properties

Sequential composition (`>>`) is NOT commutative but IS associative:

```
(L1 >> L2) >> L3 = L1 >> (L2 >> L3)
L1 >> L2 ≠ L2 >> L1  (in general)
```

Sequential composition represents "view through L1, then further constrain by L2."

### 3.4 Layer Lattice

Layers form a lattice ordered by constraint activation:

```
       I (identity - all active)
      /|\
     / | \
   L1  L2  L3 ...
     \ | /
      \|/
       O (null - none active)
```

**Lattice properties:**
- Meet: `L1 ∧ L2 = L1 & L2`
- Join: `L1 ∨ L2 = L1 | L2`
- Top: `I` (identity layer)
- Bottom: `O` (null layer)

---

## 4. Projection Operations

### 4.1 Core Projection Function

```
project(graph: Phase9Graph, layer: OntologicalLayer) -> ProjectionResult
```

**Invariants:**
- Same graph + same layer = same result (deterministic)
- Projection does not modify the input graph
- All activation decisions are binary (no scoring)
- Result includes complete trace for auditability

### 4.2 Projection Algorithm

```
1. VALIDATE inputs
   - Graph must be canonicalized (Phase-9 output)
   - Layer must have valid structure

2. COMPUTE active edge set
   active_edges = { e ∈ graph.edges | e.edge_type ∈ layer.active_edge_types }
   suppressed_edges = graph.edges - active_edges

3. COMPUTE active node set
   active_nodes = { n ∈ graph.nodes |
                    any(n.flags[i] for i in layer.active_node_flags) }

4. COMPUTE reachability under active edges
   reachability = transitive_closure(active_edges, active_nodes)

5. EVALUATE constraints under projection
   for rule_id in layer.active_constraint_rules:
       verdict = evaluate_rule(rule_id, active_nodes, active_edges)
       record(rule_id, verdict)

6. COMPUTE influence pattern
   influence = compute_influence_footprint(reachability, constraint_verdicts)

7. EMIT projection result with trace
```

### 4.3 Influence Computation

Influence propagation under a projection:

```
compute_influence(origin_nodes, layer, graph) -> InfluencePattern:

1. Initialize frontier = origin_nodes
2. Initialize reached = origin_nodes
3. Initialize depth = 0

4. While frontier is not empty AND depth < MAX_DEPTH:
   next_frontier = {}
   for node in frontier:
       for edge in active_edges_from(node, layer):
           target = edge.target_id
           if target not in reached:
               next_frontier.add(target)
               reached.add(target)
   frontier = next_frontier
   depth += 1

5. boundary = { n ∈ reached | no active outgoing edges }

6. Return InfluencePattern(
       origin_node_ids = origin_nodes,
       reach_set = reached,
       propagation_depth = depth,
       boundary_nodes = boundary
   )
```

---

## 5. Cross-Layer Independence

### 5.1 No Cross-Layer Leakage

Projection through layer L1 must NOT depend on what would happen under L2:

**Forbidden patterns:**
```python
# VIOLATION: cross-layer dependency
def project(graph, layer):
    if would_be_active_under(graph, OTHER_LAYER):  # NO
        ...

# VIOLATION: implicit layer state
def project(graph, layer):
    if self.last_layer == SOME_LAYER:  # NO
        ...

# VIOLATION: layer comparison in logic
def project(graph, layer):
    if layer.is_more_constrained_than(OTHER_LAYER):  # NO
        ...
```

**Required pattern:**
```python
# CORRECT: layer-isolated projection
def project(graph, layer):
    active = apply_mask(graph.edges, layer.active_edge_types)
    # ... all decisions based only on (graph, layer) pair
```

### 5.2 Independence Verification

Every projection function must pass this test:

```
For all graphs G, layers L1, L2:
    result1 = project(G, L1)
    result2 = project(G, L1)  # Same inputs

    # Must be identical regardless of what other projections occurred
    assert result1 == result2

    # Interleaving with other projections must not affect result
    _ = project(G, L2)
    result3 = project(G, L1)
    assert result1 == result3
```

---

## 6. Fail-Closed Rules

### 6.1 Mandatory Rejection Conditions

The projection system must BLOCK and return `PROJECTION_BLOCKED` if:

| Condition | Reason |
|-----------|--------|
| Graph not canonicalized | Non-deterministic input |
| Layer has invalid structure | Undefined behavior risk |
| Activation mask references unknown type | Structural inconsistency |
| Cross-layer dependency detected | Independence violation |
| Non-binary activation value | Probability violation |
| Trace cannot be constructed | Auditability violation |

### 6.2 Blocked Result Structure

```
ProjectionBlockedResult:
    blocked: bool = True
    reason: BlockReason (enum)
    location: str (where in algorithm)
    input_graph_hash: str
    input_layer_id: str
    partial_trace: Optional[ProjectionTrace]
```

---

## 7. System/Observer Boundary

### 7.1 What the System Provides

The projection system provides to the observer:

| Output | Type | Description |
|--------|------|-------------|
| `projection_result` | ProjectionResult | Complete projection outcome |
| `influence_pattern` | InfluencePattern | Structural influence footprint |
| `constraint_verdicts` | Dict[RuleID, bool] | Which constraints satisfied |
| `reachability_matrix` | Binary matrix | What reaches what |
| `projection_trace` | ProjectionTrace | Full audit trail |

### 7.2 What the Observer Provides

The observer provides to the system:

| Input | Type | Description |
|-------|------|-------------|
| `graph` | Phase9Graph | Structure to project |
| `layer` | OntologicalLayer | Lens to project through |
| `origin_nodes` | Set[NodeID] | Where to compute influence from |

### 7.3 What the System Does NOT Provide

The system explicitly does NOT provide:

- Interpretation of what influence patterns "mean"
- Selection of which layer is "appropriate"
- Ranking of projection results by "relevance"
- Semantic labels for structural configurations
- Recommendations based on pattern analysis

**These are observer-side operations.** The system is a structural constraint engine, not a meaning generator.

---

## 8. Canonical Layers

### 8.1 Predefined Layer Types

The system defines these canonical layers (not semantically named):

| Layer ID | Active Edge Types | Active Node Flags | Purpose |
|----------|------------------|-------------------|---------|
| `L_FULL` | ALL | ALL | Identity projection |
| `L_NULL` | NONE | NONE | Null projection |
| `L_STRUCT` | {0, 1} | {0} | Structural adjacency only |
| `L_PROP` | {0, 1, 2} | {0, 1} | Propagation-relevant |
| `L_FOLD` | {0} | {0} | Fold-graph only |

### 8.2 Layer Construction

New layers are constructed structurally:

```python
def construct_layer(
    active_edge_types: FrozenSet[int],
    active_node_flags: FrozenSet[int],
    active_rules: FrozenSet[int]
) -> OntologicalLayer:

    layer_content = (active_edge_types, active_node_flags, active_rules)
    layer_hash = sha256(str(layer_content)).hexdigest()[:16]
    layer_id = sha256(f"layer_{layer_hash}").hexdigest()[:16]

    return OntologicalLayer(
        layer_id=layer_id,
        layer_hash=layer_hash,
        active_edge_types=active_edge_types,
        active_node_flags=active_node_flags,
        active_constraint_rules=active_rules,
        layer_depth=compute_lattice_depth(active_edge_types, active_node_flags),
        composable=True
    )
```

---

## 9. Integration with Phase-9

### 9.1 Input Requirements

The projection system operates on **canonicalized Phase-9 graphs**:

```
Phase9Graph (canonicalized)
    ↓
project(graph, layer)
    ↓
ProjectionResult
```

### 9.2 Structural Hash Preservation

Projection does not change structural hashes:

```
graph.graph_hash == result.source_graph_hash  # Always true
```

The structure is invariant; only the *view* of it changes.

### 9.3 Quotient Compatibility

If Phase-9 applied exact quotient:
- Projection operates on the merged graph
- Expansion map is preserved separately
- Observer can expand before or after projection

---

## 10. Implementation Constraints

### 10.1 Forbidden Patterns

| Pattern | Reason |
|---------|--------|
| Floating-point values in activation | Probability analog |
| String matching on node content | Semantic operation |
| "Soft" or partial activation | Violates binary constraint |
| Layer selection heuristics | Implicit scoring |
| Caching based on "similar" inputs | Similarity is semantic |
| Any use of randomness | Non-determinism |

### 10.2 Required Properties

| Property | Verification Method |
|----------|-------------------|
| Determinism | Same inputs → same outputs |
| Independence | Interleaved projections don't affect each other |
| Trace completeness | Every step recorded |
| Algebraic laws | Composition tests |
| Fail-closed | All error paths return blocked result |

---

## 11. Expressive Richness

### 11.1 Source of Richness

Expressive richness comes from the **lattice of possible layer configurations**, not from semantic vocabulary:

```
ExpressivePotential(S) = { project(S, L) | L ∈ LayerLattice }
```

A structure's expressive capacity is the set of all distinct influence patterns it can produce under different projections.

### 11.2 Structural Multiplicity

The same structure can produce lawfully different influence patterns:

```
project(S, L1) → InfluencePattern_1
project(S, L2) → InfluencePattern_2
project(S, L3) → InfluencePattern_3
```

This is **lawful plurality**, not ambiguity:
- Ambiguity: "We don't know which interpretation is correct"
- Plurality: "Different projections lawfully yield different patterns"

### 11.3 Emergent Expression

Expression emerges at the system/observer boundary:

```
System:   Structure × Layer → InfluencePattern
Observer: InfluencePattern → Meaning (external operation)
```

The system provides the structural conditions under which meaning can arise. It does not generate meaning itself.

---

## Appendix A: Invariant Checklist

| Invariant | Enforced By |
|-----------|-------------|
| `NO_PROBABILITY` | Binary activation only |
| `NO_SEMANTICS` | No string/meaning operations |
| `NO_LEARNING` | No parameter updates |
| `DETERMINISTIC` | Pure functions, no randomness |
| `REVERSIBLE` | Trace enables replay |
| `FAIL_CLOSED` | All errors → blocked result |
| `INDEPENDENT` | No cross-layer leakage |
| `AUDITABLE` | Complete projection trace |

---

## Appendix B: Relation to Phase-9

| Phase-9 Concept | Layer Projection Analog |
|-----------------|------------------------|
| Canonicalization | Layer application produces canonical result |
| Exact quotient | Operates identically on merged graphs |
| Structural hash | Preserved through projection |
| Rewrite trace | Projection trace |
| Expansion map | Available for post-projection expansion |

---

**END OF DOCUMENT**
