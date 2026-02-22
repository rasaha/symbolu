# Part 7: Ontology Alignment — Discovery & Validation

**Status**: Discovery phase
**Date**: 2026-02-22
**Depends on**: Parts 1–6 of causal subspace pipeline (validated)

---

## 0. Discovery Framing

We do not yet know how — or whether — an ontological layer should exist. Parts 1–6 proved that the model encodes grammatical structure in a causally load-bearing subspace. Part 7 is a **discovery process** that answers two questions:

1. **Do the model's internal structural directions correspond to nameable ontological axes?** (The "naming ceremony" question)
2. **If yes, which architecture should the ontological layer use?** (Two candidates)

### The Naming Ceremony Problem

We propose 12 ontological axes (abstraction level, semantic density, concreteness, agency, temporal anchoring, etc.). PCA gives us k structural directions. Just because we *label* PCA axis 3 "concreteness" doesn't make it true. The label is only valid if MI(axis_3, concreteness_rating) is high.

Phase 1 measures per-axis MI to determine which of the 12 proposed labels survive contact with the data. Maybe 4 of 12 survive. Maybe 11. Maybe 0. The number N of validated axes determines everything downstream.

### Four Scenarios

```
Scenario A: Isomorphic (MI >> 0.3, CKA > 0.6, N ≥ 8 axes validated)
  The model already encodes something that maps onto our proposed
  ontological categories.  Both architectures are viable.
  → Phase 2: Build both, benchmark.

Scenario B: Partial Overlap (MI 0.15–0.5, CKA 0.3–0.6, N = 3–7 axes)
  Some axes correspond, others don't.  There's a bridge, but it's
  partial.  The surviving axes define the ontological space.
  → Phase 2: Meta-controller (Option 1) on surviving axes.
    Q/K gating (Option 2) is risky with few axes.

Scenario C: Orthogonal (MI < 0.05, N ≤ 2 axes)
  The model encodes structure in a way that has no correspondence
  to our proposed categories.  Its encoding is alien but valid.
  → Phase 2: STOP.  Report findings.
  → Fall back to whatever PCA gives us (unlabeled but real).

Scenario D: Complementary (MI low, but ont + H >> H for classification)
  The ontology captures aspects the model DOESN'T have.
  → Phase 2: Content injection (the ontology adds info, not policy).
```

**The discovery process determines which scenario we're in. The architecture follows from the evidence, not the other way around.**

---

## 1. Motivation

Parts 1–6 established that:
- Transformer hidden states encode grammatical role information in a low-dimensional subspace (MDL compression > 1.5x)
- This subspace is causally load-bearing (12.5% causal success, 28.98x specificity over random)
- Information crystallizes at middle layers and is consumed downstream

**Part 7 asks**: Do the model's structural PCA directions correspond to human-nameable ontological properties? If so, which architecture should exploit that correspondence?

---

## 1b. Two Candidate Architectures

Discovery (Phase 1) determines the scenario. If the scenario supports an ontological layer, two architectures compete:

### Option 1: Parallel Latent State (Meta-Controller)

The ontology lives **outside** the transformer. At each reasoning step, an encoder reads hidden states and emits an N-dimensional ontological state vector. This vector governs system-level decisions.

```
  ┌──────────────────────────────────────────────────────────┐
  │  Hidden states H[layer]  ──→  Ontology Encoder  ──→  z_ont ∈ R^N  │
  │                                  (frozen H,                        │
  │                                   trained encoder)                 │
  │                                                                    │
  │  z_ont governs:                                                    │
  │    • decoding temperature                                          │
  │    • critique loop triggering                                      │
  │    • tool use routing                                              │
  │    • recursion depth                                               │
  │    • confidence calibration                                        │
  │                                                                    │
  │  The transformer remains untouched.                                │
  │  Ontology is a meta-controller, not a structural constraint.       │
  └──────────────────────────────────────────────────────────┘

  Pros:                              Cons:
  • Does not destabilize training    • Labels may be aspirational
  • No gradient flow interference    • Controller may learn useful
  • No attention math rewriting        features that don't correspond
  • Compatible with orchestration      to the named axes
    patterns (OpenAI policy layers,  • Technically "orchestration",
    Anthropic constitutional layer)    not "ontological"
  • Safest, cleanest direction       • Naming ceremony risk: 12-D
                                       controller with fake labels
```

### Option 2: Q/K Dimension Gating (Structural Constraint)

The ontology lives **inside** attention. Each token activates a subset of Q/K dimensions based on its ontological type. This is a type-system constraint on attention.

```
  ┌──────────────────────────────────────────────────────────┐
  │  For each token i with ontological type o_i:             │
  │                                                          │
  │    gate = σ(W_gate @ o_i)    ∈ [0,1]^d_head             │
  │    q'_i = q_i ⊙ gate                                    │
  │    k'_i = k_i ⊙ gate                                    │
  │                                                          │
  │  Effect: tokens of different ontological types attend     │
  │  through different dimension subsets. Like a type system  │
  │  for attention — agents attend via "agency dimensions",   │
  │  locations via "spatial dimensions", etc.                 │
  │                                                          │
  │  Key invariant: gate → 1 recovers original model.        │
  └──────────────────────────────────────────────────────────┘

  Pros:                              Cons:
  • Elegant, principled              • Hard to validate
  • No n² mask                       • Hard to prove benefit
  • Structural constraint is real    • Risk of capacity suppression
  • Type-system-like                   (gating out dimensions loses
  • Publishable if it works            expressivity in small models)
                                     • Needs large model
```

### Which option for which scenario

| Scenario | N axes | Option 1 (Meta-controller) | Option 2 (Q/K Gating) |
|----------|--------|---------------------------|----------------------|
| A: Isomorphic | ≥ 8 | Yes (full 12-D controller) | Yes (rich type system) |
| B: Partial | 3–7 | Yes (N-D controller) | Risky (too few axes) |
| C: Orthogonal | ≤ 2 | No | No |
| D: Complementary | — | No (needs injection) | No (needs injection) |

### The L0/L2 Dissociation: READ vs ACT layers

Empirical finding from Parts 4–5: structure can peak at one layer (crystallization, high MDL compression) while causal effect peaks at a different layer (high intervention success rate). In our results:

```
L0: MDL compression = 1.53x (peak)     ← structure is ENCODED here
L2: Causal success  = 25%   (peak)     ← structure is CONSUMED here
```

This means the ontological layer cannot simply "operate at the crystallization layer." It must **read** from where structure is richest and **act** where structure is causally load-bearing.

```
Option 1 (Meta-controller):
  READ from L0 (where ontological alignment is strongest)
  │
  ├─→ z_ont ∈ R^N  (ontological state vector)
  │
  ACT at L2 (where causal effect peaks)
  └─→ governs temperature, routing, confidence at L2 decisions

Option 2 (Q/K Gating):
  OPERATE at L2 (where attention routing matters)
  │
  └─→ gate(o) modulates Q/K at the layer where the model
      actually uses structural information for attention
```

The 4.40x swap/ablation ratio confirms that *direction* in the subspace encodes role identity — different roles use different directions. This is exactly what Q/K gating would exploit: ontological type determines which dimensions of Q and K participate in attention.

The 28.98x specificity gives the naming ceremony high-SNR signal to work with. If any of the 12 axes correspond to real model directions, the MI should be detectable.

**Implementation**: `run_multi_layer_discovery()` runs Phase 1 at both layers, identifies the dissociation, and routes each architecture to the appropriate layer(s).

---

## 2. Two-Phase Structure

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: DISCOVERY  (always runs, ~2 min)                   │
│                                                               │
│  7a. Define 12 proposed ontological axes                      │
│  7b. Build per-axis feature vectors from annotations          │
│  7c. Naming ceremony: MI(each axis, each PCA direction)       │
│  7d. Global alignment (MI, CKA, subspace overlap)             │
│  7e. Discriminability (ont vs H vs concat)                    │
│  7f. Scenario classification (A / B / C / D)                  │
│                                                               │
│  Output: N validated axes, scenario, recommended Phase 2      │
└────────────────────────┬──────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┬──────────────┐
          ▼              ▼              ▼              ▼
      Scenario A     Scenario B     Scenario C     Scenario D
      N ≥ 8 axes     N = 3–7        N ≤ 2          ont adds info
          │              │              │              │
          ▼              ▼              ▼              ▼
      Phase 2:       Phase 2:       STOP.          Phase 2:
      Build both     Option 1       Report          Content
      Option 1 +     (meta-ctrl     findings.       injection
      Option 2       on surviving                   test
                     axes)
```

### Phase 1 inputs (from existing pipeline)

```
Existing pipeline outputs
    │
    ├── annotations.hidden_states[layer]  # [N_w, d]   word-level states
    ├── annotations.labels_role           # [N_w]      grammatical roles
    ├── annotations.words                 # List[WordAnnotation]
    ├── best_pca_basis                    # [d, k]     MDL-validated basis
    ├── trajectory.crystallization_layer  # int
    └── store.attention_entropy[layer]    # [N_tok, H] per-head entropy
```

---

## 3. The 12 Proposed Ontological Axes

Each axis is a scalar property computable from word annotations, dependency parse, or hidden states. The naming ceremony validates which ones correspond to real model directions.

| # | Axis | Source | Computation |
|---|------|--------|-------------|
| 0 | **Abstraction level** | WordNet hypernym depth | depth(synset) / max_depth; 0=entity, 1=most specific |
| 1 | **Concreteness** | Brysbaert norms or POS heuristic | 1–5 rating, normalized to [0,1] |
| 2 | **Animacy** | WordNet hypernym chain | 1 if chain includes "organism", else 0 |
| 3 | **Agency** | dep_relation + animacy | 1 if nsubj AND animate, graded otherwise |
| 4 | **Temporal anchoring** | Verb tense / dep type | 1 for past, 0.5 for present, 0 for non-verb |
| 5 | **Structural depth** | dep_depth from Part 2 | depth / max_depth, normalized |
| 6 | **Information density** | Token surprisal proxy | 1/freq(word) normalized; rare = dense |
| 7 | **Relational role** | Grammatical role from Part 2 | One-hot → softmax distance to role centroids |
| 8 | **Modificational load** | Count of modifiers | n_dependents / max_dependents |
| 9 | **Semantic specificity** | WordNet synset count | 1/n_synsets; fewer senses = more specific |
| 10 | **Positional salience** | Position in sentence | (position / sent_length), captures SVO order |
| 11 | **Categorical type** | POS tag | Compressed: noun=0, verb=0.33, adj=0.67, other=1.0 |

**Total**: 12 axes → `ont_features ∈ R^{N_w × 12}`

**Key difference from old design**: The old design used a 51-dimensional kitchen-sink vector (WordNet lex files, one-hot POS, etc.). The new design uses 12 **named, individually measurable** axes. Each axis is a single scalar with a clear semantic interpretation. This makes the naming ceremony possible — we can check each axis individually.

---

## 4. Phase 1 Implementation

### 4a. Config and Result Dataclasses

```python
@dataclass
class OntologyConfig:
    mi_n_bins: int = 20
    cka_kernel: str = "linear"
    n_bootstrap: int = 200
    bootstrap_ci: float = 0.95
    naming_mi_threshold: float = 0.1    # axis survives if MI > this
    device: str = "cpu"
    seed: int = 42

AXIS_NAMES = [
    "abstraction_level", "concreteness", "animacy", "agency",
    "temporal_anchoring", "structural_depth", "information_density",
    "relational_role", "modificational_load", "semantic_specificity",
    "positional_salience", "categorical_type",
]

@dataclass
class DiscoveryResult:
    layer_idx: int

    # 7b: Per-axis features
    ontology_dim: int = 12
    n_words_with_ontology: int = 0
    coverage_ratio: float = 0.0

    # 7c: Naming ceremony (per-axis MI with each PCA direction)
    per_axis_mi: Dict[str, float]         # axis_name → max MI with any PCA dir
    per_axis_best_pca: Dict[str, int]     # axis_name → which PCA dir it maps to
    n_validated_axes: int = 0             # how many axes pass MI threshold
    validated_axes: List[str]             # names of surviving axes

    # 7d: Global alignment
    alignment_mi: float = 0.0
    alignment_mi_normalized: float = 0.0
    subspace_overlap: float = 0.0
    cka_similarity: float = 0.0

    # 7e: Discriminability
    ontology_role_accuracy: float = 0.0
    embedding_role_accuracy: float = 0.0
    concat_role_accuracy: float = 0.0
    discriminability_gap: float = 0.0
    accuracy_ci_low: float = 0.0
    accuracy_ci_high: float = 0.0

    # 7f: Scenario classification
    scenario: str = ""
    scenario_confidence: float = 0.0
    scenario_evidence: List[str]
    recommended_phase2: str = ""
```

### 4b. Build 12-Axis Ontology Vectors

```python
def build_ontology_vectors(
    annotations: StructuralAnnotations,
    H: np.ndarray,           # [N_w, d]
    labels: np.ndarray,       # [N_w]
) -> Tuple[np.ndarray, np.ndarray]:
    """Build 12-axis ontology feature vectors.

    Returns
    -------
    ont_features : np.ndarray [N_w, 12]
    valid_mask : np.ndarray [N_w] bool
    """
```

Each axis is computed independently. Words missing WordNet coverage get NaN for axes 0, 1, 2, 9. All other axes are always computable from parse/position info. A word is valid if ≥ 8 of 12 axes have values.

### 4c. Naming Ceremony

```python
def run_naming_ceremony(
    ont_features: np.ndarray,    # [N, 12]
    H_proj: np.ndarray,          # [N, k]  (H @ U_k)
    threshold: float = 0.1,
) -> Tuple[Dict[str, float], Dict[str, int], List[str]]:
    """For each of the 12 axes, compute MI with each PCA direction.

    Returns (per_axis_mi, per_axis_best_pca, validated_axes).

    per_axis_mi[axis_name] = max over PCA dirs of MI(axis, pca_dir)
    per_axis_best_pca[axis_name] = argmax PCA dir
    validated_axes = [name for name in AXIS_NAMES if per_axis_mi[name] > threshold]
    """
```

This is the critical step. If MI("concreteness", pca_dir_3) = 0.45 but MI("concreteness", pca_dir_j) < 0.05 for all j ≠ 3, then PCA direction 3 IS "concreteness" (validated). If MI("agency", pca_dir_j) < 0.05 for ALL j, then "agency" is not a real axis in this model (rejected).

### 4d. Global Alignment Metrics

Same as before: MI, CKA, subspace overlap. But now computed on the N validated axes only (not the rejected ones).

### 4e. Discriminability

Same three-way comparison (ont vs H vs concat), but using only validated axes.

### 4f. Scenario Classification

```python
def classify_scenario(result: DiscoveryResult) -> DiscoveryResult:
    N = result.n_validated_axes
    mi = result.alignment_mi
    cka = result.cka_similarity
    gap = result.discriminability_gap

    if result.coverage_ratio < 0.1:
        result.scenario = "C"
        result.recommended_phase2 = "stop"
    elif N >= 8 and mi > 0.5 and cka > 0.6:
        result.scenario = "A"
        result.recommended_phase2 = "build_both"
    elif mi < 0.05 or N <= 2:
        result.scenario = "C"
        result.recommended_phase2 = "stop"
    elif mi < 0.2 and gap > 0.05:
        result.scenario = "D"
        result.recommended_phase2 = "injection_test"
    else:
        result.scenario = "B"
        result.recommended_phase2 = "meta_controller"
    return result
```

---

## 5. Phase 2 Architecture Stubs

Phase 2 is NOT implemented in this PR. It's stubbed to show the interface.

### Phase 2, Option 1: Meta-Controller

```python
class OntologyMetaController:
    """Parallel latent state that governs system-level decisions.

    H[layer] → encoder → z_ont ∈ R^N → control signals

    Trained on validated axes only. N = number of axes that
    survived the naming ceremony.
    """

    def __init__(self, d_model: int, n_axes: int):
        self.encoder = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Linear(64, n_axes),
            nn.Sigmoid(),        # each axis ∈ [0, 1]
        )

    def forward(self, H: torch.Tensor) -> torch.Tensor:
        # H: [batch, seq, d] → pool → [batch, d]
        h_pool = H.mean(dim=1)
        return self.encoder(h_pool)  # [batch, N]
```

### Phase 2, Option 2: Q/K Dimension Gating

```python
class QKDimensionGating:
    """Type-system constraint on attention dimensions.

    Each token's ontological type determines which Q/K
    dimensions participate in attention.

    gate = σ(W_gate @ ont_per_token)
    q' = q ⊙ gate
    k' = k ⊙ gate
    """

    def __init__(self, n_axes: int, d_head: int):
        self.W_gate = nn.Linear(n_axes, d_head)

    def forward(
        self,
        Q: torch.Tensor,          # [batch, seq, d_head]
        K: torch.Tensor,          # [batch, seq, d_head]
        ont: torch.Tensor,        # [batch, seq, n_axes]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        gate = torch.sigmoid(self.W_gate(ont))
        return Q * gate, K * gate
```

---

## 6. Integration

```python
# In run_pipeline.py, after Part 6:

# PART 7: Ontology Discovery
from scripts.causal_subspace.ontology_alignment import (
    OntologyConfig, run_ontology_discovery,
)

ont_cfg = OntologyConfig(device=device, seed=seed)
discovery = run_ontology_discovery(
    annotations=annotations,
    H=annotations.hidden_states[trajectory.crystallization_layer],
    labels=annotations.labels_role,
    U_k=best_pca_basis,
    cfg=ont_cfg,
)
results["ontology_discovery"] = asdict(discovery)
```

---

## 7. Testing Strategy

### Unit tests

```python
class TestOntologyDiscovery:
    def test_build_12_axis_vectors_shape()
    def test_naming_ceremony_aligned_data()     # synthetic: axis=PCA dir → MI high
    def test_naming_ceremony_random_data()       # random axes → MI ≈ 0
    def test_cka_identity()                      # CKA(X, X) = 1.0
    def test_cka_random()                        # CKA(X, random) ≈ 0
    def test_discriminability_bootstrap_ci()
    def test_scenario_classification_A()         # high MI, high CKA, N=12
    def test_scenario_classification_C()         # MI ≈ 0, N=0
    def test_scenario_classification_D()         # low MI but concat >> emb
```

---

## 8. Dependencies

| Package | Purpose | Already in project? |
|---------|---------|---------------------|
| `nltk` (wordnet) | Axes 0, 2, 9 (abstraction, animacy, specificity) | No — optional, graceful fallback |
| `scikit-learn` | Logistic regression, MI estimation | Yes |
| `scipy` | CCA, bootstrap | Yes |

WordNet is **optional**. Without it, axes 0/1/2/9 fall back to heuristics (POS-based concreteness proxy, dep-relation-based animacy proxy). The naming ceremony still runs on all 12 axes — it just measures whether the heuristic-based axes correspond to model directions.

---

## 9. Computational Cost

| Step | Operations | Time |
|------|-----------|------|
| 7a–7b. Build 12-axis vectors | Loop over words, lookups | ~5–10s |
| 7c. Naming ceremony | 12 axes × k PCA dirs × MI | ~10–30s |
| 7d. Global alignment | MI + CKA + overlap | ~5–15s |
| 7e. Discriminability | 3 probes × 200 bootstraps | ~30–60s |
| **Total Phase 1** | | **~1–2 min** |

Phase 2 (if any) adds ~1–3 min depending on architecture.

---

## 10. Open Questions (Resolved by Phase 1 Data)

1. **How many of the 12 axes survive?** → The naming ceremony answers this.
2. **Which architecture to use?** → Scenario classification answers this.
3. **Is governance the right paradigm?** → Scenario D honestly admits it might not be.
4. **Should we name axes before or after PCA?** → Before (hypothesis-driven), validated after (data-driven). The naming ceremony bridges these.
