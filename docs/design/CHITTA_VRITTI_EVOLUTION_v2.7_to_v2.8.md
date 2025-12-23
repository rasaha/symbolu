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

## Part 12: Open Questions for Resolution

Before implementation, resolve:

1. **Projection dimension D** — 64? 128? Other?
2. **R[v,a] seed values** — Use illustrative values above? Different basis?
3. **B_c(h(c)) signals** — What constitutes context for bias?
4. **Smṛti algorithm** — Window? Decay? Threshold?
5. **Normalization** — Softmax or L1?
6. **Config values** — Validate Consumer/Enterprise penalties

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

*Document version: Draft 1.1*
*Prepared for: v2.7 → v2.8 evolution planning*
*Status: Pending resolution of open questions*
*Changes: Added explicit ChittaVrittiResult dataclass with fractures dict*
