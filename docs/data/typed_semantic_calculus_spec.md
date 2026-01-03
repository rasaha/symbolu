# Typed Semantic Calculus for Generative Model

## Core Architecture

The generative model is **not** a phoneme-level statistical model. It is a **type-directed constraint satisfaction system** where meaning emerges from typed composition.

## The Type System

```
Type := (OntologicalLayer, SemanticSlot, DiscourseAct, OperationalRegime)
Value := (LexicalFrame, AcousticRealization)

semantic_effect : Type × Value → Meaning
```

### Type Components

| Component | Cardinality | Source |
|-----------|-------------|--------|
| OntologicalLayer | 10 | `ontology_layer.py` |
| SemanticSlot | 9 | `p8_semantic_schema.py` |
| DiscourseAct | 6 | `p7_discourse_schema.py` |
| OperationalRegime | 6 | `p6_schema.py` |

**Theoretical Type Space**: 10 × 9 × 6 × 6 = **3,240 types**

In practice, constrained by:
- `DISCOURSE_ACT_ALLOWED_SLOTS` (slot allowlist per discourse act)
- `PHASE_ALLOWED_HINTS` (layer allowlist per phase)
- Regime compatibility rules

**Effective Type Space**: ~200-400 valid type combinations

## Semantic Differentiation

The same acoustic form under different types yields different meaning:

| Type | Value | Semantic Effect |
|------|-------|-----------------|
| `(ACTING, STATE, EXPLANATION, INFORM)` | `/si:/` | "perceive visually" |
| `(FORMING, TARGET, QUESTION, CLARIFY)` | `/si:/` | "large body of water" |
| `(ACTING, AGENT, INSTRUCTION, INFORM)` | `/kæt/` | "feline actor" |
| `(TAGGING, TARGET, REFLECTION, REFLECT)` | `/kæt/` | "feline referent" |

## Generation Algorithm

### Forward Direction (Existing Pipeline)
```
Intent → Type Selection → Value Realization → Acoustic Output
     PO1-PO5      P6-P8           P9-P10           P21+
```

### Generative Direction (New)
```
Target Semantic Effect
        ↓
Valid Type Enumeration (constraint satisfaction)
        ↓
Value Lookup (knowledge store query)
        ↓
Vṛtti Coherence Scoring
        ↓
Output Selection
```

## Knowledge Store Schema

The knowledge store maps Types to valid Values:

```python
@dataclass(frozen=True)
class TypedSemanticEntry:
    """Single entry in the typed semantic knowledge store."""

    # Type signature
    layer: OntologicalLayer
    slot: SemanticSlot
    discourse_act: DiscourseAct
    regime: OperationalRegime

    # Value realization
    lexical_form: str  # e.g., "see", "sea"
    phoneme_sequence: Tuple[str, ...]  # e.g., ("S", "IY1")

    # Vṛtti profile for coherence scoring
    vrtti_inertia: float
    vrtti_activation: float
    vrtti_oscillation: float
    vrtti_tension: float
    vrtti_release: float


class TypedSemanticStore:
    """Knowledge store for type → value mappings."""

    def lookup_by_type(
        self,
        layer: OntologicalLayer,
        slot: SemanticSlot,
        discourse_act: DiscourseAct,
        regime: OperationalRegime,
    ) -> List[TypedSemanticEntry]:
        """Return all valid values for given type."""
        ...

    def lookup_by_semantic_target(
        self,
        target_concept: str,
    ) -> List[TypedSemanticEntry]:
        """Return all type/value pairs that realize target concept."""
        ...
```

## Type Transition Graph

Nodes are Type tuples. Edges encode valid transitions:

```python
@dataclass(frozen=True)
class TypeTransition:
    """Valid transition between type states."""

    from_type: Tuple[OntologicalLayer, SemanticSlot, DiscourseAct, OperationalRegime]
    to_type: Tuple[OntologicalLayer, SemanticSlot, DiscourseAct, OperationalRegime]

    # Transition constraints
    vrtti_momentum_range: Tuple[float, float]  # valid momentum for this transition
    regime_escalation_allowed: bool


class TypeTransitionGraph:
    """Graph of valid type transitions."""

    def get_valid_successors(
        self,
        current_type: Tuple[OntologicalLayer, SemanticSlot, DiscourseAct, OperationalRegime],
        current_vrtti_momentum: float,
    ) -> List[TypeTransition]:
        """Return valid next types given current state."""
        ...
```

## Generation Process

```python
def generate_utterance(
    target_effects: List[str],
    store: TypedSemanticStore,
    graph: TypeTransitionGraph,
    initial_regime: OperationalRegime = OperationalRegime.INFORM,
) -> List[TypedSemanticEntry]:
    """
    Generate utterance as sequence of typed values.

    1. For each target effect, find candidate type/value pairs
    2. Build valid path through type transition graph
    3. Score by Vṛtti coherence
    4. Return highest-scoring sequence
    """

    result = []
    current_type = None
    current_momentum = 0.0

    for target in target_effects:
        # Find all type/value pairs for this target
        candidates = store.lookup_by_semantic_target(target)

        if current_type is None:
            # First element: filter by initial regime
            valid = [c for c in candidates if c.regime == initial_regime]
        else:
            # Subsequent: filter by valid transitions
            valid_transitions = graph.get_valid_successors(current_type, current_momentum)
            valid_next_types = {t.to_type for t in valid_transitions}
            valid = [c for c in candidates if _entry_to_type(c) in valid_next_types]

        if not valid:
            raise GenerationBlockedError(f"No valid realization for {target}")

        # Score by Vṛtti coherence and select best
        best = max(valid, key=lambda c: _vrtti_coherence_score(c, current_momentum))

        result.append(best)
        current_type = _entry_to_type(best)
        current_momentum = _update_momentum(current_momentum, best)

    return result
```

## What This Is NOT

1. **Not statistical language modeling** - no probability distributions over tokens
2. **Not neural network inference** - no learned weights
3. **Not phoneme-level semantics** - phonemes are terminal values, not semantic carriers
4. **Not unconstrained generation** - bounded by type lattice and transition graph

## What This IS

1. **Type-theoretic semantics** - meaning from typed composition
2. **Constraint satisfaction** - generation as search over valid type paths
3. **Symbolic-connectionist hybrid** - symbolic types, continuous Vṛtti scoring
4. **Deterministic core** - same input constraints → same output (modulo tie-breaking)

## Implementation Priority

### Phase 1: Type System Infrastructure
- [ ] Formalize valid type combinations from existing phase schemas
- [ ] Build type validation functions
- [ ] Define type equality and hashing

### Phase 2: Knowledge Store
- [ ] Design storage format (SQLite or flat file)
- [ ] Populate with CMU dict entries tagged by type
- [ ] Build lookup indices

### Phase 3: Transition Graph
- [ ] Extract transition rules from phase progression
- [ ] Encode Vṛtti momentum constraints
- [ ] Build graph traversal functions

### Phase 4: Generation Algorithm
- [ ] Implement constraint satisfaction search
- [ ] Add Vṛtti coherence scoring
- [ ] Wire to acoustic output (P10+)

## Resource Requirements

| Component | Storage | Computation |
|-----------|---------|-------------|
| Type System | ~10 KB (code) | O(1) validation |
| Knowledge Store | ~50-100 MB | O(log n) lookup |
| Transition Graph | ~1-5 MB | O(degree) traversal |
| Generation | - | O(targets × candidates) |

**No GPU required. No training required. Pure constraint satisfaction.**
