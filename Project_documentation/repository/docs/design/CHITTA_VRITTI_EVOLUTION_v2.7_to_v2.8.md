# Chitta-Vṛtti Integration: Evolution from v2.7 to v2.8

## Document Purpose

This document establishes the conceptual bridge between the existing v2.7 architecture and the proposed Chitta-Vṛtti layer for v2.8. It identifies what exists, what's missing, and how the pieces connect to form a coherent reasoning system.

---

## Part 1: The Core Formula (Target State)

The central equation that drives aspect distribution:

```
p_w[a] = normalize( E(w,c) · Φ(a) · Σ_{v} p_v[v] · R[v,a] + B_c(h(c)) )
```

Where:
- **p_w[a]** — Probability that word w in context c belongs to aspect a
- **E(w,c)** — Evidence score from syllable/vṛtti preprocessing
- **Φ(a)** — Aspect prior (fixed or slowly modulated)
- **p_v[v]** — Vṛtti probability distribution (5-dimensional control vector)
- **R[v,a]** — Vṛtti-Aspect coupling matrix (5×10)
- **B_c(h(c))** — Context adaptor bias
- **normalize** — Softmax across 10 aspects

This formula is:
- Symbolic (no neural weights)
- Context-sensitive (dynamic p_v, context bias)
- Explainable (traceable from syllables → vṛtti → aspect)
- Efficient (matrix-vector multiply)

---

## Part 2: Current v2.7 Implementation Status

### What Exists

| Component | Location | Status |
|-----------|----------|--------|
| 10 Dimensions | `ontology/backbone/encoder.py` | ✓ Implemented |
| Dimension enum | `Dimension.ACTION` through `Dimension.ABSOLUTE` | ✓ Complete |
| 5 Acoustic Vṛtti | `formulas/vritti_mapper.py` | ✓ Implemented |
| Vṛtti distribution | `get_vritti_distribution()` | ✓ Implemented |
| Aspect patterns | `*_PATTERNS` in encoder | ✓ Implemented |
| Evidence scoring | `core/stitching/penalties.py` | ✓ Implemented |
| Cross-domain reasoning | `core/stitching/stitching_engine.py` | ✓ Implemented |

### What's Missing or Stub

| Component | Location | Status |
|-----------|----------|--------|
| R[v,a] coupling matrix | None | ✗ Not implemented |
| p_v[v] as control vector | None | ✗ Not formalized |
| B_c(h(c)) context bias | None | ✗ Not implemented |
| p_w[a] distribution | None | ✗ Not normalized |
| Aspect mapping | `core/smi/aspect_mapping.py` | ✗ Stub only |
| SMI engine | `core/smi/smi_engine.py` | ✗ Stub only |

### The Naming Disconnect

**v2.7 uses two different vṛtti concepts:**

| Concept | Current Name | Patañjali Name | Nature |
|---------|--------------|----------------|--------|
| Acoustic motion | `VrittiType.INERTIA` | — | Articulatory quality |
| Acoustic motion | `VrittiType.ACTIVATION` | — | Articulatory quality |
| Acoustic motion | `VrittiType.OSCILLATION` | — | Articulatory quality |
| Acoustic motion | `VrittiType.TENSION` | — | Articulatory quality |
| Acoustic motion | `VrittiType.RELEASE` | — | Articulatory quality |
| Cognitive mode | (not implemented) | Pramāṇa | Valid cognition |
| Cognitive mode | (not implemented) | Viparyaya | Misperception |
| Cognitive mode | (not implemented) | Vikalpa | Conceptual branching |
| Cognitive mode | (not implemented) | Smṛti | Memory persistence |
| Cognitive mode | (not implemented) | Nidrā | Dormancy/absence |

**These are orthogonal concepts.** Acoustic vṛtti describes motion quality of sounds. Cognitive vṛtti (citta-vṛtti) describes mental fluctuation modes.

---

## Part 3: The 10 Dimensions / Aspects

### Mapping Between Naming Conventions

| Dimension (v2.7 code) | Aspect (formula docs) | Index |
|-----------------------|-----------------------|-------|
| `Dimension.ACTION` | Karma | 1 |
| `Dimension.IDENTIFICATION` | Identification | 2 |
| `Dimension.BODY` | Body | 3 |
| `Dimension.MIND` | Mind | 4 |
| `Dimension.EGO` | Ego | 5 |
| `Dimension.INTELLECT` | Intellect | 6 |
| `Dimension.SOUL` | Soul | 7 |
| `Dimension.WITNESS` | Witness | 8 |
| `Dimension.SINGULARITY` | Atman | 9 |
| `Dimension.ABSOLUTE` | Brahman | 10 |

These are the 10 aspects that p_w[a] distributes probability over.

---

## Part 4: Where Chitta-Vṛtti Fits

### The Gap

The core formula requires **p_v[v]** — a 5-dimensional probability distribution over cognitive modes. Currently:

1. No computation produces this distribution
2. No mechanism updates it dynamically
3. The R[v,a] coupling matrix doesn't exist

### What Chitta-Vṛtti Provides

The Chitta-Vṛtti module computes **p_v[v]** from cross-layer coherence:

```
┌─────────────────────────────────────────────────────────────┐
│                    REPRESENTATION LAYERS                     │
├─────────────────────────────────────────────────────────────┤
│  Phonemic    Semantic    Structural    Temporal              │
│  (acoustic)  (embedding) (ontology)    (state Δ)            │
└──────┬────────────┬───────────┬────────────┬────────────────┘
       │            │           │            │
       └────────────┴─────┬─────┴────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   PROJECT TO COMMON   │
              │   SPACE (dim D, L2)   │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  PAIRWISE COHERENCE   │
              │  sim(a,b) = a · b     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   COMPUTE p_v[v]      │
              │   (5 cognitive modes) │
              └───────────┬───────────┘
                          │
    ┌─────────┬─────────┬─┴─────────┬─────────┐
    ▼         ▼         ▼           ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│Pramāṇa│ │Vipary.│ │Vikalpa│ │ Smṛti │ │ Nidrā │
└───────┘ └───────┘ └───────┘ └───────┘ └───────┘
```

### Computation Logic for Each Mode

| Mode | Computation | Intuition |
|------|-------------|-----------|
| **Pramāṇa** | High when: coherence↑, entropy↓, motion stable | All layers agree, low uncertainty |
| **Viparyaya** | High when: confident opposition detected | Layers actively contradict |
| **Vikalpa** | High when: entropy↑, agreement variance↑ | Multiple valid interpretations |
| **Smṛti** | High when: state unchanged despite input | Frozen / stale representations |
| **Nidrā** | High when: representations missing/weak | Insufficient information |

### Output Types

The module produces a complete diagnostic result:

```python
@dataclass(frozen=True)
class ChittaVrittiResult:
    """Complete output from Chitta-Vṛtti computation."""

    # Cross-Representation Coherence
    coherence: float                              # Aggregate coherence [0,1]
    fractures: dict[tuple[str, str], float]       # Per-pair fracture (1 - similarity)

    # Vṛtti Distribution (THE CONTROL VECTOR for core formula)
    vritti: dict[str, float]                      # 5 modes: pramana, viparyaya, vikalpa, smrti, nidra
                                                  # Sums to 1.0 (probability distribution)

    # Diagnostic Score
    score: float                                  # Overall readiness [0,1]

    # Explainability Fields
    dominant_vritti: str                          # Mode with highest activation
    primary_fracture: tuple[str, str] | None      # Layer pair with largest disagreement
    explanation: str                              # Human-readable summary
```

### Fracture Profile

The **fractures** dictionary preserves pairwise disagreement for debugging and explainability:

```python
# Example fracture profile
fractures = {
    ("phonemic", "semantic"): 0.15,      # Low fracture = good agreement
    ("phonemic", "structural"): 0.42,    # Moderate fracture
    ("phonemic", "temporal"): 0.08,      # Low fracture
    ("semantic", "structural"): 0.67,    # HIGH FRACTURE = primary disagreement
    ("semantic", "temporal"): 0.23,      # Moderate
    ("structural", "temporal"): 0.31,    # Moderate
}
# primary_fracture = ("semantic", "structural")
# explanation = "Semantic and structural layers disagree (fracture=0.67)"
```

**Fracture computation:**
```
fracture(layer_i, layer_j) = 1 - similarity(project(layer_i), project(layer_j))
```

**Use cases:**
- **Debugging:** "Why is coherence low?" → Check highest fracture
- **Monitoring:** Track fracture trends across sessions
- **Explainability:** Human-readable: "Phonemic and semantic layers conflict"

### The Complete Flow

```
         UPSTREAM (existing v2.7)
                  │
    ┌─────────────┴─────────────┐
    │  Syllable preprocessing   │
    │  Acoustic vṛtti mapping   │
    │  Semantic embedding       │
    │  Structural encoding      │
    │  Temporal state           │
    └─────────────┬─────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │      CHITTA-VṚTTI MODULE    │  ◄── NEW
    │                             │
    │  Input: 4 representation    │
    │         layers + signals    │
    │                             │
    │  Output: p_v[v] distribution│
    │          (5-dim vector)     │
    └─────────────┬───────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │    R[v,a] COUPLING MATRIX   │  ◄── NEW (5×10)
    │                             │
    │  Couples cognitive modes    │
    │  to ontological aspects     │
    └─────────────┬───────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │    ASPECT DISTRIBUTION      │
    │    p_w[a] via core formula  │
    └─────────────┬───────────────┘
                  │
                  ▼
         DOWNSTREAM (existing v2.7)
              Stitching
              Fusion
              Rendering
```

---

## Part 5: The R[v,a] Coupling Matrix

### Semantic Basis

The coupling encodes: "When in cognitive mode v, which aspects become more prominent?"

| | Karma | Ident. | Body | Mind | Ego | Intellect | Soul | Witness | Atman | Brahman |
|---|---|---|---|---|---|---|---|---|---|---|
| **Pramāṇa** | 0.7 | 0.8 | 0.6 | 0.7 | 0.5 | **0.95** | 0.6 | 0.8 | 0.7 | 0.6 |
| **Viparyaya** | 0.5 | 0.7 | 0.4 | 0.6 | **0.90** | 0.4 | 0.3 | 0.5 | 0.3 | 0.2 |
| **Vikalpa** | 0.6 | 0.5 | 0.5 | **0.85** | 0.6 | 0.7 | 0.5 | 0.6 | 0.4 | 0.3 |
| **Smṛti** | 0.8 | 0.6 | 0.7 | 0.7 | 0.5 | 0.6 | **0.80** | 0.5 | 0.6 | 0.4 |
| **Nidrā** | 0.3 | 0.3 | **0.70** | 0.4 | 0.3 | 0.2 | 0.4 | 0.6 | 0.5 | **0.75** |

### Interpretation

- **Pramāṇa → Intellect**: Valid cognition activates discriminative wisdom
- **Viparyaya → Ego**: Misperception activates self-referential conflict
- **Vikalpa → Mind**: Conceptual branching activates mental proliferation
- **Smṛti → Soul**: Memory persistence activates continuity of being
- **Nidrā → Body/Brahman**: Dormancy activates either physical inertia or transcendent stillness

### Configuration

These values should be:
- Explicitly defined in configuration
- Auditable (no hidden weights)
- Tier-specific if needed (Consumer vs Enterprise)

---

## Part 6: Integration with Existing Signals

### Signal Sources (from v2.7)

| Signal | Source Module | Used For |
|--------|---------------|----------|
| Entropy (H) | `entropy/cross_domain_entropy.py` | Vikalpa, Pramāṇa |
| Motion (M) | Observables.delta_sem | Pramāṇa stability |
| Confidence | Fusion audit metadata | Viparyaya confidence |
| Temporal Δ | Temporal tracker / CoherenceState | Smṛti detection |
| Layer presence | CandidateEntry fields | Nidrā detection |

### Wiring Contract

```python
@dataclass(frozen=True)
class ChittaVrittiInputs:
    """Inputs required for Chitta-Vṛtti computation."""

    # Representations (project to common space)
    phonemic_rep: Optional[np.ndarray]      # From acoustic pipeline
    semantic_rep: Optional[np.ndarray]      # From embedding layer
    structural_rep: Optional[np.ndarray]    # From ontology encoder
    temporal_rep: Optional[np.ndarray]      # From state differencing

    # Signals
    entropy: float                          # Combined normalized H
    motion: float                           # M from Observables
    confidence: float                       # From fusion audit
    temporal_continuity: float              # From temporal tracker

    # Previous state (for Smṛti)
    previous_state: Optional["ChittaVrittiInputs"] = None
```

---

## Part 7: Pipeline Placement

### Incorrect (Original Spec)

```
Fusion (ranking/selection)
   ↓
▶ Chitta-Vṛtti  ← Post-fusion = observation only = overhead
   ↓
Renderer
```

### Correct (With Formula Integration)

```
Syllable preprocessing
   ↓
Acoustic vṛtti (existing)
   ↓
Semantic embedding
   ↓
▶ Chitta-Vṛtti (computes p_v[v])  ← HERE
   ↓
Aspect distribution (p_w[a] via R[v,a])
   ↓
Stitching (uses aspect weights)
   ↓
Fusion
   ↓
Renderer
```

**Chitta-Vṛtti must run BEFORE aspect distribution to feed p_v[v] into the formula.**

---

## Part 8: Remaining Gaps

### Gap 1: Projection Dimension D

**Issue:** All representations must project to dimension D for coherence computation.

**Current state:** Representations have varying native dimensions:
- Guna: 3
- Kosha: 5
- Domain: 12
- Semantic: 768 (typical)

**Required:** Explicit projection adapters for each representation type.

**Decision needed:** What is D? Suggest D=64 or D=128.

### Gap 2: R[v,a] Matrix Values

**Issue:** The coupling matrix values shown above are illustrative, not validated.

**Required:**
- Empirical or theoretical basis for values
- Or: configuration-based with sensible defaults
- Or: seed values that can be adjusted per deployment

### Gap 3: Context Adaptor Bias B_c(h(c))

**Issue:** Not implemented in v2.7.

**Definition from formula:**
> Encodes current dialog state / observer context c via function h(c)

**Possible implementation:**
```python
def context_bias(context: Context) -> np.ndarray:
    """Compute bias vector for 10 aspects based on context."""
    h = np.zeros(10)
    h += context.entropy * ENTROPY_ASPECT_BIAS
    h += context.tone * TONE_ASPECT_BIAS
    h += context.coherence_score * COHERENCE_ASPECT_BIAS
    return h
```

**Decision needed:** What signals constitute h(c)?

### Gap 4: Smṛti Temporal Window

**Issue:** How many turns of unchanged state triggers Smṛti escalation?

**Options:**
- Fixed window (e.g., 3 turns)
- Decay-based (exponential memory)
- Threshold-based (Δ < ε for N turns)

**Decision needed:** Smṛti detection algorithm.

### Gap 5: Normalization Strategy

**Issue:** The formula uses normalize() but doesn't specify softmax vs L1.

**Options:**
- Softmax: `p[a] = exp(x[a]) / Σexp(x)`
- L1: `p[a] = x[a] / Σx`

**Difference:** Softmax sharpens distribution; L1 preserves proportions.

**Decision needed:** Which normalization?

### Gap 6: Consumer vs Enterprise Divergence

**Issue:** Spec mentions different tolerances but doesn't specify values.

**Required:**

```python
@dataclass
class ChittaVrittiConfig:
    # Projection
    projection_dim: int

    # Vṛtti penalties (for Score computation)
    viparyaya_penalty: float
    vikalpa_penalty: float
    smrti_penalty: float
    nidra_penalty: float

    # Thresholds
    coherence_threshold: float
    smrti_decay_rate: float

CONSUMER_CONFIG = ChittaVrittiConfig(
    projection_dim=64,
    viparyaya_penalty=0.3,
    vikalpa_penalty=0.2,  # More tolerant
    smrti_penalty=0.2,
    nidra_penalty=0.2,
    coherence_threshold=0.6,
    smrti_decay_rate=0.3,  # Faster decay
)

ENTERPRISE_CONFIG = ChittaVrittiConfig(
    projection_dim=64,
    viparyaya_penalty=0.5,  # Higher penalty
    vikalpa_penalty=0.3,
    smrti_penalty=0.2,
    nidra_penalty=0.4,     # Higher penalty
    coherence_threshold=0.8,  # Stricter
    smrti_decay_rate=0.1,  # Slower decay
)
```

---

## Part 9: Invariants

### Required Invariants

| ID | Invariant | Test |
|----|-----------|------|
| INV-CV-1 | Order independence | `coherence(A,B,C) == coherence(C,A,B)` |
| INV-CV-2 | Scale invariance | Pre-L2-norm scaling doesn't affect sim |
| INV-CV-3 | Identity | Identical projections → coherence=1 |
| INV-CV-4 | Null handling | Missing rep → only nidrā increases |
| INV-CV-5 | Bounded output | All values ∈ [0,1] |
| INV-CV-6 | Determinism | Same inputs → identical outputs |
| INV-CV-7 | Sum constraint | Σ p_v[v] = 1.0 (probability) |

---

## Part 10: File Structure

### Proposed Layout

```
symbolu/
└── chitta_vritti/
    ├── __init__.py
    ├── types.py              # ChittaVrittiResult, ChittaVrittiInputs
    ├── projector.py          # RepresentationProjector protocol + adapters
    ├── coherence.py          # Pairwise similarity, aggregate coherence
    ├── vritti.py             # 5 mode computations
    ├── coupling.py           # R[v,a] matrix definition
    ├── score.py              # Final score composition
    ├── config.py             # Consumer/Enterprise presets
    ├── explain.py            # Human-readable logging
    └── integration.py        # Pipeline wiring

tests/
└── unit/
    └── chitta_vritti/
        ├── test_projector.py
        ├── test_coherence.py
        ├── test_vritti_pramana.py
        ├── test_vritti_viparyaya.py
        ├── test_vritti_vikalpa.py
        ├── test_vritti_smrti.py
        ├── test_vritti_nidra.py
        ├── test_coupling.py
        ├── test_score.py
        ├── test_invariants.py
        └── test_determinism.py
```

---

## Part 11: Summary

### What This Enables

1. **Grounded p_v[v]** — Cognitive mode distribution computed from representational agreement, not heuristics
2. **Complete formula** — All components of `p_w[a] = normalize(E·Φ·Σp_v·R + B)` have implementations
3. **Diagnostic insight** — Know WHY interpretation is unstable (contradiction vs ambiguity vs staleness)
4. **Configurable behavior** — Consumer/Enterprise presets tune system personality
5. **Explainability** — Trace from input representations through coherence to aspect activation

### What It Does NOT Enable

- Learning (still zero-adaptation)
- Goal formation (still no autonomous objectives)
- Truth override (still non-authoritative over STL)
- Policy modification (still observer-only for safety)

### The Intelligence Contribution

The system gains the ability to:
- Assess its own interpretive confidence
- Distinguish types of uncertainty
- Modulate aspect weighting based on representational agreement
- Produce explanations for its confidence state

This is **metacognitive measurement** — a component of reasoning, not full reasoning itself.

---

## Part 12: Real-Time Optimization Guidelines

### Computational Profile

| Operation | Complexity | Expected Runtime |
|-----------|------------|------------------|
| Project 4 layers to dim D | O(4 × native_dim × D) | ~10-50μs |
| Pairwise similarity (6 pairs) | O(6 × D) | <1μs |
| 5 vṛtti formulas | O(1) each | <1μs |
| R[v,a] matrix multiply (5×10) | O(50) | <1μs |
| Normalize (softmax over 10) | O(10) | <1μs |

**Target:** <100μs per invocation

### Memory Footprint

| Component | Size | Lifecycle |
|-----------|------|-----------|
| R[v,a] matrix | 400 bytes (50 floats) | Static — cache at startup |
| Projection adapters | ~D × native_dim per layer | Static — precompute |
| ChittaVrittiResult | ~200 bytes | Per invocation |
| Fractures dict | ~100 bytes (6 pairs) | Per invocation |

**Total runtime allocation:** <1KB per invocation

### Fast-Path Optimization

Skip detailed computation when conditions are clearly stable.

**IMPORTANT (Refinement from Review):** Fast path must also verify no viparyaya signal,
because a coherent inversion (high coherence + semantic opposition) is dangerous.

```python
def compute_chitta_vritti(inputs: ChittaVrittiInputs, config: OptimizedConfig) -> ChittaVrittiResult:
    # Quick viparyaya estimate for fast-path safety
    estimated_viparyaya = quick_opposition_check(inputs)

    # FAST PATH 1: Low entropy + all layers present + no opposition → pramāṇa
    if (all_layers_present(inputs) and
        inputs.entropy < config.fast_path_entropy_threshold and
        estimated_viparyaya < config.fast_path_viparyaya_ceiling):  # SAFETY GATE
        return fast_path_pramana(inputs)

    # FAST PATH 2: Most layers missing → nidrā dominant
    missing = count_missing(inputs)
    if missing >= 3:
        return fast_path_nidra(inputs, missing)

    # FULL PATH: Detailed computation required
    return compute_full(inputs, config)

def quick_opposition_check(inputs: ChittaVrittiInputs) -> float:
    """Lightweight check for semantic inversion without full fracture analysis.

    Returns estimated viparyaya signal [0,1].
    Uses only the two most semantically relevant layers for speed.
    """
    if inputs.semantic_rep is None or inputs.structural_rep is None:
        return 0.0  # Can't detect opposition without both layers

    # Quick cosine similarity between semantic and structural
    sim = cosine_similarity(inputs.semantic_rep, inputs.structural_rep)

    if sim < -0.3:  # Early warning threshold
        return abs(sim)  # Higher opposition → higher viparyaya estimate
    return 0.0

def fast_path_pramana(inputs: ChittaVrittiInputs) -> ChittaVrittiResult:
    """Optimized path for stable, coherent state."""
    return ChittaVrittiResult(
        coherence=0.95,
        fractures={},  # Skip detailed fracture analysis
        vritti={"pramana": 0.85, "viparyaya": 0.03, "vikalpa": 0.04,
                "smrti": 0.04, "nidra": 0.04},
        score=0.90,
        dominant_vritti="pramana",
        primary_fracture=None,
        explanation="Fast path: low entropy, all layers present, no opposition"
    )
```

### Recommended Thresholds

```python
@dataclass(frozen=True)
class OptimizedConfig:
    """Production-ready threshold configuration."""

    # Projection dimension (smaller = faster)
    projection_dim: int = 32              # Start here, increase if quality degrades

    # Fast-path gates
    fast_path_entropy_threshold: float = 0.1
    fast_path_coherence_threshold: float = 0.9
    fast_path_viparyaya_ceiling: float = 0.1  # SAFETY: block fast-path if opposition detected

    # Vṛtti computation thresholds
    pramana_entropy_ceiling: float = 0.3       # Above this → pramāṇa decreases
    viparyaya_opposition_floor: float = -0.5   # Similarity below this → opposition
    vikalpa_variance_floor: float = 0.2        # Fracture variance above this → branching
    smrti_staleness_threshold: float = 0.05    # State Δ below this → unchanged
    nidra_presence_floor: float = 0.1          # Confidence below this → absent

    # Smṛti temporal parameters
    smrti_window_turns: int = 3
    smrti_decay_rate: float = 0.4              # Per-turn decay

    # Score penalties (applied as step functions, not proportionally)
    penalty_viparyaya: float = 0.25
    penalty_vikalpa: float = 0.15
    penalty_smrti: float = 0.15
    penalty_nidra: float = 0.20

    # Activation thresholds (penalty applies only above these)
    viparyaya_activation_threshold: float = 0.1
    vikalpa_activation_threshold: float = 0.15
    smrti_activation_threshold: float = 0.2
    nidra_activation_threshold: float = 0.25
```

### Vṛtti Computation Formulas

**Pramāṇa (Valid Cognition):**
```python
def compute_pramana(coherence: float, entropy: float, motion: float,
                    config: OptimizedConfig) -> float:
    """High when layers agree, entropy low, motion stable."""
    entropy_factor = max(0, 1 - entropy / config.pramana_entropy_ceiling)
    motion_stability = 1 - min(1, motion)  # Lower motion = more stable
    raw = coherence * entropy_factor * motion_stability
    return clamp(raw, 0, 1)
```

**Viparyaya (Misperception):**
```python
def compute_viparyaya(fractures: dict, confidence: float,
                      config: OptimizedConfig) -> float:
    """High when layers confidently oppose each other."""
    if not fractures:
        return 0.0

    # Find maximum opposition (fracture approaching 1.0 = anti-correlation)
    max_fracture = max(fractures.values())

    if max_fracture > 0.7:  # Strong disagreement
        opposition_strength = (max_fracture - 0.7) / 0.3  # Scale 0.7-1.0 → 0-1
        return clamp(opposition_strength * confidence, 0, 1)
    return 0.0
```

**Vikalpa (Conceptual Branching):**
```python
def compute_vikalpa(fractures: dict, entropy: float,
                    config: OptimizedConfig) -> float:
    """High when agreement is uneven AND entropy is high."""
    if not fractures or len(fractures) < 2:
        return 0.0

    fracture_values = list(fractures.values())
    fracture_variance = variance(fracture_values)

    if fracture_variance > config.vikalpa_variance_floor and entropy > 0.3:
        return clamp(entropy * (fracture_variance / 0.5), 0, 1)
    return 0.0
```

**Smṛti (Memory Persistence):**
```python
def compute_smrti(current: ChittaVrittiInputs,
                  previous: Optional[ChittaVrittiInputs],
                  accumulated_smrti: float,
                  config: OptimizedConfig) -> float:
    """High when state unchanged despite new input."""
    if previous is None:
        return 0.0

    # Compute state delta
    delta = compute_representation_delta(current, previous)

    if delta < config.smrti_staleness_threshold:
        # State unchanged → accumulate smṛti
        new_smrti = min(1.0, accumulated_smrti + 0.2)
    else:
        # State changed → decay smṛti
        new_smrti = accumulated_smrti * config.smrti_decay_rate

    return clamp(new_smrti, 0, 1)
```

**Nidrā (Dormancy):**
```python
def compute_nidra(inputs: ChittaVrittiInputs) -> float:
    """High when representations are missing or weak."""
    layers = [inputs.phonemic_rep, inputs.semantic_rep,
              inputs.structural_rep, inputs.temporal_rep]
    missing_count = sum(1 for layer in layers if layer is None)
    return missing_count / 4.0
```

**Normalization to Probability Distribution:**
```python
def normalize_vritti(raw_scores: dict[str, float]) -> dict[str, float]:
    """Convert raw scores to probability distribution."""
    # Add small epsilon to prevent division by zero
    total = sum(raw_scores.values()) + 1e-8
    return {k: v / total for k, v in raw_scores.items()}
```

### Aggregate Coherence Computation

```python
def compute_coherence(fractures: dict[tuple[str, str], float]) -> float:
    """Aggregate coherence from pairwise fractures."""
    if not fractures:
        return 1.0  # No pairs to compare = vacuously coherent

    # Coherence = 1 - mean(fractures)
    mean_fracture = sum(fractures.values()) / len(fractures)
    return clamp(1 - mean_fracture, 0, 1)
```

### Score Composition

**IMPORTANT (Refinement from Review):** Use threshold-driven penalties (step functions),
not proportional penalties. This keeps the system interpretable and resistant to drift.

```python
def compute_score(coherence: float, vritti: dict[str, float],
                  config: OptimizedConfig) -> float:
    """Compute overall readiness score using threshold-driven penalties.

    Penalties apply only when vṛtti values exceed their activation thresholds,
    not proportionally across the whole range. This prevents drift and maintains
    interpretability.
    """
    score = coherence

    # Threshold-driven penalties (step functions)
    # Penalty applies in FULL when threshold crossed, not proportionally
    if vritti["viparyaya"] > config.viparyaya_activation_threshold:
        score -= config.penalty_viparyaya

    if vritti["vikalpa"] > config.vikalpa_activation_threshold:
        score -= config.penalty_vikalpa

    if vritti["smrti"] > config.smrti_activation_threshold:
        score -= config.penalty_smrti

    if vritti["nidra"] > config.nidra_activation_threshold:
        score -= config.penalty_nidra

    return clamp(score, 0, 1)
```

**Rationale:** Proportional penalties (`score -= vritti * penalty`) create continuous
degradation that's hard to interpret. Threshold-driven penalties create clear
decision boundaries: either the vṛtti is "activated" and penalized, or it's not.

### Caching Strategy

```python
# At startup — compute once, reuse
CACHED_R_MATRIX = load_coupling_matrix()  # 5×10 floats
CACHED_PROJECTORS = {
    "phonemic": PhonemeProjector(dim=32),
    "semantic": SemanticProjector(dim=32),
    "structural": StructuralProjector(dim=32),
    "temporal": TemporalProjector(dim=32),
}

# Per-session — maintain smṛti state
class SessionState:
    previous_inputs: Optional[ChittaVrittiInputs] = None
    accumulated_smrti: float = 0.0
```

### Tier-Specific Configurations

```python
# Consumer: More tolerant, faster decay, wider thresholds
CONSUMER_OPTIMIZED = OptimizedConfig(
    projection_dim=32,
    fast_path_entropy_threshold=0.15,     # Wider fast-path
    fast_path_viparyaya_ceiling=0.15,     # More tolerant of minor opposition
    penalty_viparyaya=0.20,               # Lower penalties
    penalty_vikalpa=0.10,
    penalty_smrti=0.10,
    penalty_nidra=0.15,
    viparyaya_activation_threshold=0.15,  # Higher threshold to activate
    vikalpa_activation_threshold=0.20,
    smrti_activation_threshold=0.25,
    nidra_activation_threshold=0.30,
    smrti_decay_rate=0.5,                 # Faster forgetting
)

# Enterprise: Stricter, slower decay, tighter thresholds
ENTERPRISE_OPTIMIZED = OptimizedConfig(
    projection_dim=32,
    fast_path_entropy_threshold=0.08,     # Narrower fast-path
    fast_path_viparyaya_ceiling=0.05,     # Very sensitive to opposition
    penalty_viparyaya=0.35,               # Higher penalties
    penalty_vikalpa=0.20,
    penalty_smrti=0.15,
    penalty_nidra=0.30,
    viparyaya_activation_threshold=0.05,  # Lower threshold = more sensitive
    vikalpa_activation_threshold=0.10,
    smrti_activation_threshold=0.15,
    nidra_activation_threshold=0.20,
    smrti_decay_rate=0.2,                 # Slower forgetting
)
```

### Enterprise Variant Derivation

Per external review, the enterprise variant can be derived by tightening **three key numbers**:

| Parameter | Consumer | Enterprise | Rationale |
|-----------|----------|------------|-----------|
| `fast_path_viparyaya_ceiling` | 0.15 | 0.05 | Enterprise must detect inversions earlier |
| `viparyaya_activation_threshold` | 0.15 | 0.05 | Lower threshold = faster penalty activation |
| `penalty_viparyaya` | 0.20 | 0.35 | Truth inversion costs more in enterprise |

**Why these three?**

1. **Viparyaya is the critical differentiator.** Enterprise cannot tolerate semantic inversion
   because it may feed into downstream decisions (contracts, compliance, audit trails).

2. **Other vṛttis are less critical.** Vikalpa (branching) and Smṛti (staleness) are
   acceptable in both tiers; Nidrā (missing data) is handled by input validation.

3. **Multiplicative effect.** Lowering `fast_path_viparyaya_ceiling` catches inversions
   before fast-path; lowering `activation_threshold` catches them in full-path;
   raising `penalty` ensures they hurt the score.

**Derivation formula:**

```python
def derive_enterprise_from_consumer(consumer: OptimizedConfig) -> OptimizedConfig:
    """Derive enterprise config by tightening viparyaya parameters."""
    return OptimizedConfig(
        # Keep structural parameters
        projection_dim=consumer.projection_dim,
        fast_path_entropy_threshold=consumer.fast_path_entropy_threshold * 0.5,

        # Tighten viparyaya (THE KEY CHANGES)
        fast_path_viparyaya_ceiling=consumer.fast_path_viparyaya_ceiling / 3,
        penalty_viparyaya=consumer.penalty_viparyaya * 1.75,
        viparyaya_activation_threshold=consumer.viparyaya_activation_threshold / 3,

        # Moderate tightening for others
        penalty_vikalpa=consumer.penalty_vikalpa * 1.5,
        penalty_smrti=consumer.penalty_smrti * 1.25,
        penalty_nidra=consumer.penalty_nidra * 1.5,
        vikalpa_activation_threshold=consumer.vikalpa_activation_threshold * 0.75,
        smrti_activation_threshold=consumer.smrti_activation_threshold * 0.75,
        nidra_activation_threshold=consumer.nidra_activation_threshold * 0.75,

        # Slower decay (enterprise needs longer memory)
        smrti_decay_rate=consumer.smrti_decay_rate * 0.4,
        smrti_window_turns=consumer.smrti_window_turns + 2,
    )
```

### Performance Validation

Add instrumentation to validate <100μs target:

```python
import time

def compute_chitta_vritti_instrumented(inputs, config):
    start = time.perf_counter_ns()
    result = compute_chitta_vritti(inputs, config)
    elapsed_us = (time.perf_counter_ns() - start) / 1000

    if elapsed_us > 100:
        log.warning(f"Chitta-Vṛtti exceeded 100μs: {elapsed_us:.1f}μs")

    return result
```

---

## Part 13: Open Questions Status

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| 1 | Projection dimension D | ✅ RESOLVED | D=32 (validated by review) |
| 2 | R[v,a] seed values | ⚠️ OPEN | Use illustrative values; tune empirically |
| 3 | B_c(h(c)) signals | ⚠️ OPEN | Deferred to implementation phase |
| 4 | Smṛti algorithm | ✅ RESOLVED | Window=3 turns, decay=0.4/turn, threshold=0.05 |
| 5 | Normalization | ✅ RESOLVED | L1 (simple sum normalization) |
| 6 | Config values | ✅ RESOLVED | Validated by external review; threshold-driven |

### Remaining Open Items

1. **R[v,a] matrix values** — Current values are illustrative. Options:
   - Use as-is for MVP
   - Derive from philosophical sources (Yoga Sutras commentary)
   - Tune empirically against test cases

2. **B_c(h(c)) context bias** — Not implemented in v2.7; can defer:
   - MVP: Set B_c = 0 (no context bias)
   - v2.9: Add context bias based on session coherence, tone, entropy history

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **Chitta** | Mind-stuff; the field of consciousness |
| **Vṛtti** | Fluctuation; modification of the mind |
| **Pramāṇa** | Valid cognition; correct knowledge |
| **Viparyaya** | Misperception; erroneous knowledge |
| **Vikalpa** | Conceptualization; verbal/imaginative construction |
| **Smṛti** | Memory; retention of past experience |
| **Nidrā** | Sleep; absence of mental content |
| **p_v[v]** | Probability distribution over 5 vṛtti modes |
| **p_w[a]** | Probability distribution over 10 aspects for word w |
| **R[v,a]** | Coupling matrix relating vṛtti modes to aspects |
| **Φ(a)** | Prior weight for aspect a |
| **E(w,c)** | Evidence score for word w in context c |
| **B_c(h(c))** | Context-dependent bias function |

---

*Document version: Draft 1.3*
*Prepared for: v2.7 → v2.8 evolution planning*
*Status: Reviewed and refined; ready for implementation*

**Changelog:**
- Draft 1.3: Incorporated external review refinements:
  - Added viparyaya safety gate to fast-path (prevents coherent inversions)
  - Changed to threshold-driven penalties (step functions, not proportional)
  - Added activation thresholds to OptimizedConfig
  - Added Enterprise Variant Derivation section with three-number tightening
- Draft 1.2: Added Part 12 (Real-Time Optimization Guidelines) with formulas, thresholds, caching, tier configs
- Draft 1.1: Added explicit ChittaVrittiResult dataclass with fractures dict
