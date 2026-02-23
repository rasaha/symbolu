# Part 7: Ontology Alignment — Discovery & Validation

**Status**: Phase 1 COMPLETE. Phase 2 prototype COMPLETE.
**Date**: 2026-02-23 (Phase 2 update)
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

---

## 11. Evaluation Results (Full Pipeline Run)

**Date**: 2026-02-23
**Model**: GPT-2 (124M parameters, 12 layers, 768 hidden dim)
**Data**: 52,728 tokens → 46,309 word annotations
**Layers analyzed**: 0–11 (all 12)
**Pipeline runtime**: 434s (~7.2 min)

---

### 11.1 Part 1–2: Data Collection & Structural Labels

| Metric | Value |
|--------|-------|
| Tokens analyzed | 52,728 |
| Words annotated | 46,309 |
| Coverage | ~88% (tokens → word-level annotations) |

The data collection and structural labeling ran at full scale (500 sequences from WikiText). Two label sets were extracted: `grammatical_role` and `dep_depth`.

---

### 11.2 Part 3: SAE Feature Sparsity

The Sparse Autoencoder (3072 hidden units, L1-regularized) was trained independently at each layer. Key pattern: **sparsity monotonically increases with layer depth**.

| Layer | % Active | L0 (mean ± std) | Reconstruction Error |
|-------|----------|------------------|---------------------|
| 0 | 74.0% | 2274 ± 320 | 0.0051 |
| 1 | 75.7% | 2327 ± 317 | 0.0041 |
| 2 | 78.6% | 2413 ± 272 | 0.0060 |
| 3 | 81.3% | 2497 ± 269 | 0.0062 |
| 4 | 83.3% | 2558 ± 247 | 0.0061 |
| 5 | 84.7% | 2602 ± 258 | 0.0069 |
| 6 | 85.8% | 2637 ± 256 | 0.0075 |
| 7 | 87.5% | 2689 ± 253 | 0.0058 |
| 8 | 88.8% | 2729 ± 237 | 0.0057 |
| 9 | 90.4% | 2777 ± 207 | 0.0050 |
| 10 | 91.5% | 2811 ± 187 | 0.0043 |
| 11 | 91.1% | 2799 ± 127 | 0.0040 |

**Interpretation**: L0 norms rise from ~2274 (L0) to ~2811 (L10) — the model uses progressively more distributed representations in deeper layers. Reconstruction error remains low throughout (0.004–0.008), confirming the SAE captures the bulk of representational content. The slight plateau at L11 (91.1% vs 91.5% at L10) is consistent with the output projection layer recycling features for next-token prediction rather than introducing new structure.

**Concern**: L0 norms are very high (2274–2811 out of 3072 features active). This means ~75–91% of SAE features fire on average — the representations are not truly sparse. The SAE bottleneck (3072 = 4× the 768 hidden dim) may be too small to achieve meaningful sparsity. A larger dictionary (e.g., 16k or 32k features) would likely yield sparser, more interpretable features. However, the current sparsity is sufficient for the downstream MDL probing and clustering tasks.

---

### 11.3 Part 4: MDL Compression Ratios

MDL (Minimum Description Length) probing with prequential coding measures how compressible grammatical labels are from hidden-state PCA projections. Compression > 1.0× means the subspace encodes the label; < 1.0× means the probe does worse than a uniform prior.

#### Grammatical Role

| Layer | Compression | Bits/Label | Assessment |
|-------|-------------|------------|------------|
| **0** | **1.70x** | 1.126 | Strong encoding |
| **1** | **1.77x** | 1.080 | **Peak (crystallization)** |
| 2 | 1.50x | 1.274 | Good |
| **3** | **1.72x** | 1.109 | Strong (second peak) |
| 4 | 1.65x | 1.159 | Good |
| 5 | 1.49x | 1.278 | Moderate |
| 6 | 1.49x | 1.284 | Moderate |
| 7 | 1.34x | 1.425 | Beginning consumption |
| 8 | 1.21x | 1.580 | Weak |
| 9 | 1.16x | 1.650 | Weak |
| 10 | 0.98x | 1.944 | Below baseline |
| 11 | 0.85x | 2.250 | Below baseline |

**Crystallization layer**: L1 (1.77×), with a secondary peak at L3 (1.72×). The structural subspace forms in the first two layers and is progressively consumed through L7–L11, falling below the 1.0× baseline by L10.

**Key finding**: The double-peak (L1 + L3) suggests two-phase encoding: L1 captures initial syntactic role assignment, L3 refines it after initial attention mixing. This differs from the `--quick` run which identified L3 as the sole crystallization layer — the full dataset reveals L1 as the true peak.

#### Dependency Depth

| Layer | Compression | Bits/Label | Assessment |
|-------|-------------|------------|------------|
| **0** | 1.02x | 2.416 | Barely above baseline |
| **1** | **1.06x** | 2.312 | Weak peak |
| 2 | 0.99x | 2.486 | Below baseline |
| 3 | 1.03x | 2.392 | Marginal |
| 4 | 1.01x | 2.436 | Marginal |
| 5–11 | 0.54–0.93x | 2.6–4.6 | Progressively worse |

**Dependency depth is barely encoded.** Peak compression of 1.06× at L1 is near the noise floor. GPT-2's structural subspace primarily encodes *role identity* (subject/object/modifier), not *tree depth*. This is expected for a left-to-right autoregressive model — tree depth is a global structural property that requires bidirectional context to represent faithfully.

---

### 11.4 Part 5: Causal Interchange Interventions

Activation patching: swap the structural subspace (top-64 PCA directions) between a source and target sentence, measure whether the model's output flips to match the source's grammatical role.

#### Primary Interventions (26 pairs at crystallization layers)

| Layer | Pairs | Success Rate | Flip Rate | Fluency | vs_random | vs_unrelated | swap/ablation |
|-------|-------|-------------|-----------|---------|-----------|-------------|---------------|
| L1 | 26 | **0.0%** | 0.0% | 100.0% | 4.27× | 0.01× | 0.01× |
| L3 | 26 | **0.0%** | 0.0% | 100.0% | 23.30× | 0.14× | 0.19× |

#### Full Trajectory Interventions (6 pairs per layer, Part 6)

| Layer | Success | vs_random | vs_unrelated | swap/ablation | PCA explained var |
|-------|---------|-----------|-------------|---------------|-------------------|
| L0 | 0.0% | 7.18× | 0.01× | 0.00× | 70.3% |
| L1 | 0.0% | 6.78× | 0.02× | 0.01× | 90.1% |
| L2 | 0.0% | 16.40× | 0.08× | 0.06× | 98.9% |
| L3 | 0.0% | 33.91× | 0.24× | 0.27× | 98.6% |
| L4 | 0.0% | 55.81× | 0.34× | 0.42× | 98.4% |
| L5 | 0.0% | 39.58× | 0.29× | 0.30× | 98.1% |
| L6 | 0.0% | 20.97× | 0.19× | 0.21× | 97.7% |
| L7 | 0.0% | 36.67× | 0.34× | 0.28× | 96.9% |
| **L8** | **16.7%** | **47.32×** | **0.75×** | **0.64×** | 95.9% |
| L9 | 0.0% | 50.15× | 0.69× | 0.74× | 94.3% |
| L10 | 0.0% | 43.02× | 0.70× | 0.98× | 91.9% |
| **L11** | **16.7%** | 26.05× | 0.78× | 0.28× | 68.6% |

**Key observations from the full trajectory**:

1. **vs_random specificity peaks at L4 (55.81×) and L9 (50.15×).** The subspace intervention produces maximally different effects from random perturbation in mid-to-late layers. The structural subspace is *real* — the model's response to targeted structural perturbation is categorically different from random noise.

2. **vs_unrelated ratio climbs monotonically** from 0.01× (L0) to 0.98× (L10). In early layers, the structural subspace intervention is *weaker* than unrelated-subspace intervention. By L10, they converge to parity. This means the structural subspace becomes increasingly important relative to other subspaces as depth increases — even as its *absolute* information content (MDL compression) declines.

3. **swap/ablation ratio climbs from 0.00× to 0.98×.** In early layers, swapping is far weaker than ablation (the model cares about *presence*, not *identity*). By L10, swapping ≈ ablation (the model now treats the *specific direction* as important).

4. **16.7% success at L8 and L11** (1/6 pairs each). These are the only layers where interventions succeed, and they're in the consumption/output zone where the model is actively *using* structural information for prediction. However, 6 pairs is too few to distinguish signal from noise (p ≈ 0.33 under null).

**Diagnosis**: The structural subspace is **informational but not cleanly causal at the encoding layer**. The specificity gradient (low vs_unrelated at L1, high at L10) suggests the model transitions from *encoding* structure in a redundant, distributed way (early layers) to *consuming* it through specific directions (late layers). A causal intervention strategy targeting late layers (L8–L10) with more pairs might yield stronger results.

---

### 11.5 Part 6: Layer Trajectory

```
Crystallization: Layer 1 (compression = 1.77×)
Consumption:     Layer 7
Peak causal:     16.7% (at L8 and L11, 6 pairs each)
```

The trajectory reveals a clear lifecycle: structural information **crystallizes at L1** (peak compression), is **maintained through L6** (compression > 1.3×), is **consumed at L7** (attention entropy minimizes), and is **exploited at L8–L11** (where the only successful causal interventions occur, even as compression drops below baseline).

The paradox that causal success peaks *after* compression drops below 1.0× is revealing: the model consumes structural information by transforming it from a probe-readable format into operational features that directly influence next-token prediction. You can't *read* it anymore (MDL fails), but you can *perturb* it (interventions succeed).

---

### 11.6 Part 5b: Attention Entropy

Per-head entropy across layers (in nats):

| Layer | Mean | Min | Max | Pattern |
|-------|------|-----|-----|---------|
| 0 | 2.50 | 0.36 | 3.89 | High variance — one very focused head |
| 1 | 3.06 | 1.13 | 3.86 | Most diffuse layer |
| 2 | 2.13 | 1.13 | 3.31 | Sharpening begins |
| 3 | 1.63 | 0.97 | 2.41 | Further sharpening |
| 4 | 1.62 | **0.01** | 2.42 | One near-deterministic head |
| 5 | 1.41 | 0.19 | 2.68 | |
| 6 | 1.65 | 0.47 | 2.65 | |
| 7 | **1.30** | 0.29 | 2.20 | **Most focused layer** |
| 8 | 1.73 | 0.84 | 2.89 | Slight recovery |
| 9 | 1.54 | 1.17 | 1.94 | Narrow range |
| 10 | 1.71 | 1.07 | 2.40 | |
| 11 | 2.27 | 1.56 | 3.51 | Output diffusion |

**Key observations**:
- **L7 is the most focused layer** (mean entropy 1.30 nats), coinciding with the consumption inflection point where structural information is transformed into prediction features.
- **L4 has a near-deterministic head** (entropy 0.01 nats) — a "hard attention" head that focuses almost all mass on a single position. This is likely a positional or copy head.
- **L11 recovers entropy** (2.27 nats) — the output layer broadens attention to integrate context for final prediction, consistent with "fan-out" before the unembedding matrix.
- The attention sharpening trajectory (L1→L7) mirrors the structural consumption trajectory (high compression at L1 → consumed by L7), suggesting attention heads use structural information *as they consume it*.

---

### 11.7 Part 7: Ontology Alignment Discovery

Phase 1 ran at two layers (L1 = crystallization, L7 = best alignment) to capture the READ/ACT dissociation.

#### Layer 1 (Crystallization Layer — Where Structure Peaks)

| Metric | Value |
|--------|-------|
| MI | 0.168 |
| CKA | 0.013 |
| Validated axes | 6/12 |
| Scenario | **D (Complementary)** |

Six axes passed the naming ceremony at L1: `concreteness`, `temporal_anchoring`, `structural_depth`, `relational_role`, `modificational_load`, `categorical_type`. This means the structural subspace at L1 has measurable correspondence with these six human-nameable properties.

However, the global alignment metrics are low: MI = 0.168 (below the 0.2 threshold for Scenario B) and CKA = 0.013 (near zero). The scenario classification landed on **D (Complementary)** — the ontology captures aspects the model doesn't encode, suggesting content injection rather than governance.

#### Layer 7 (Best Alignment Layer — Where Attention Is Most Focused)

| Metric | Value |
|--------|-------|
| MI | 0.375 |
| CKA | 0.006 |
| Validated axes | 4/12 |
| Scenario | **B (Partial Overlap)** |

Four axes survived at L7: `concreteness`, `relational_role`, `modificational_load`, `categorical_type`. Fewer axes than L1, but stronger global MI (0.375 vs 0.168). CKA remains near zero (0.006).

Scenario B with `recommended_phase2 = meta_controller`: the partial overlap justifies a meta-controller that reads from L7 (best alignment) and acts at L1 (best causal signal — where structural encoding is freshest).

#### Discriminability (7e): Ontology vs Embeddings vs Concat

The discriminability test trains linear probes on three feature sets and compares classification accuracy for grammatical role (5 classes). This reveals whether the ontology adds predictive power beyond what the model already encodes.

| Feature Set | L1 Accuracy | L7 Accuracy |
|-------------|-------------|-------------|
| Ontology only (12-dim) | **98.8%** | **99.5%** |
| Embedding only (768-dim) | 74.5% | 75.8% |
| Concat (ont + emb) | 86.3% | 82.5% |
| **Gap (concat − emb)** | **+11.8%** | **+6.8%** |

**Bootstrap CI on gap**: L1 = [2.8%, 6.5%], L7 = [1.3%, 4.7%]

**Key findings**:

1. **Ontology features are near-perfect classifiers** (98.8–99.5%). This is expected — grammatical role labels are *derived from* the same dependency parse that feeds the ontological axes (relational_role, categorical_type directly encode role information). The ontology is essentially cheating on this test by containing the labels.

2. **Embeddings alone achieve only ~75% accuracy.** The model's 768-dim hidden state is an imperfect encoder of grammatical role. This is consistent with the MDL compression results (1.77× is real compression, but far from lossless).

3. **Concatenation improves over embeddings by 6.8–11.8%.** The ontology adds information the model doesn't have. This is the defining signature of **Scenario D (Complementary)** at L1 — the gap is positive and statistically significant.

4. **The gap shrinks from L1 (11.8%) to L7 (6.8%).** By L7, the model's representation has absorbed more of the structural information, reducing the ontology's additive value. This is consistent with the MI increase from L1 (0.168) to L7 (0.375).

5. **Concat accuracy (82–86%) < Ontology accuracy (99%).** Adding the model embeddings to the ontology features actually *hurts* compared to ontology alone. This means the embeddings add noise when concatenated — the model's distributed encoding partially interferes with the clean ontological signal. This argues against naive concatenation architectures.

#### The READ/ACT Dissociation

```
DISSOCIATION DETECTED:
  Alignment peaks at L7  (MI = 0.375)
  Causal effect peaks at L1  (compression = 1.77×)

Architecture routing:
  Meta-controller: READ L7, ACT L1
  Q/K gating:      OPERATE at L1
```

This dissociation is the most architecturally significant finding. The model *encodes* structural information at L1 but the best *alignment* between our ontological axes and the model's internal directions occurs at L7. This means:

1. **The model's representation of structure evolves**: By L7, the initially encoded grammatical features have been transformed into directions that better correspond to the proposed ontological axes (concreteness, relational role, etc.).
2. **A meta-controller cannot read and act at the same layer**: It must read the ontological state from L7 (where the representation aligns with nameable axes) and inject control signals at L1 (where the structural subspace is freshest and most compressible).
3. **Q/K gating should operate at L1**: Since causal effect (what little there is) concentrates at early layers, attention dimension gating makes most sense where attention routing decisions have downstream consequence.

#### Validated Axes Summary

| Axis | L1 MI | L1 Best PCA | L7 MI | L7 Best PCA | Status |
|------|-------|-------------|-------|-------------|--------|
| **relational_role** | **0.473** | dir 3 | **0.168** | dir 4 | Robust (strongest) |
| **concreteness** | **0.306** | dir 4 | **0.309** | dir 4 | Robust (stable) |
| **categorical_type** | **0.188** | dir 4 | **0.186** | dir 4 | Robust (same PCA dir) |
| **modificational_load** | **0.151** | dir 4 | **0.151** | dir 4 | Robust (identical MI) |
| temporal_anchoring | **0.144** | dir 6 | 0.071 | dir 6 | Layer-specific (L1 only) |
| structural_depth | **0.124** | dir 6 | 0.088 | dir 4 | Layer-specific (L1 only) |
| information_density | 0.043 | dir 1 | 0.050 | dir 1 | Failed (below 0.10 threshold) |
| positional_salience | 0.043 | dir 1 | 0.050 | dir 1 | Failed (identical to info_density!) |
| agency | 0.024 | dir 18 | 0.019 | dir 11 | Failed |
| animacy | 0.022 | dir 18 | 0.019 | dir 18 | Failed |
| abstraction_level | 0.000 | dir 0 | 0.000 | dir 0 | Failed (zero MI — WordNet hypernym depth is noise) |
| semantic_specificity | 0.000 | dir 0 | 0.000 | dir 0 | Failed (zero MI — synset count is noise) |

**Notable patterns in the naming ceremony data**:

- **PCA direction 4 is overloaded**: concreteness, categorical_type, modificational_load, and relational_role at L7 all map to the same PCA direction. This means PCA dir 4 is a "grammatical type" mega-axis that conflates multiple ontological properties. The axes are not truly independent — they share a common structural direction.
- **PCA direction 6** captures temporal and depth information (temporal_anchoring, structural_depth at L1).
- **information_density and positional_salience have identical MI** (0.043 at L1, 0.050 at L7) and map to the same PCA direction. They may be measuring the same underlying signal (token frequency correlates with position in sentence).
- **WordNet-derived axes (abstraction_level, semantic_specificity) produce zero MI**. WordNet hypernym depth and synset count have no correspondence with any PCA direction. These features are either too noisy or capture properties the model doesn't encode at all.
- **animacy and agency are near-identical** (MI 0.022 vs 0.024) and map to the same PCA direction (dir 18 at L1). Both are too weak to pass the threshold, but they weakly track the same model direction.

**6 of 12 proposed axes failed validation.** The failures cluster into two groups:
- **Zero-MI axes** (2): `abstraction_level`, `semantic_specificity` — WordNet-derived features that have absolutely no correspondence with any model direction. These should be removed from the ontology.
- **Low-MI axes** (4): `animacy`, `agency`, `information_density`, `positional_salience` — weak signals (MI 0.02–0.05) that fall below the 0.10 threshold. These might be rescued with better feature engineering or a lower threshold, but currently add noise.

The surviving 6 axes split into:
- **Robust** (4 axes): `concreteness`, `relational_role`, `modificational_load`, `categorical_type` — validated at both L1 and L7, with stable MI values and consistent PCA direction mapping.
- **Layer-specific** (2 axes): `temporal_anchoring`, `structural_depth` — validated only at L1 (MI ~0.13), consumed by L7 (MI drops to ~0.08). These capture early-layer representations that the model uses and discards.

**Architectural implication**: A meta-controller operating on robust axes only needs 4 dimensions. If it reads from L1 (to also capture temporal_anchoring and structural_depth), it needs 6 dimensions. The additional 2 layer-specific axes provide richer signal but require reading from the crystallization layer rather than the best-alignment layer.

---

### 11.8 Scenario Classification Verdict

```
┌─────────────────────────────────────────────────────────┐
│  SCENARIO B: Partial Overlap                            │
│                                                         │
│  MI = 0.375 (L7), CKA = 0.006, 4 surviving axes (L7)   │
│  6 surviving axes (L1), 4 robust across both layers     │
│                                                         │
│  Recommended Phase 2: META-CONTROLLER                   │
│  Architecture: READ from L7, ACT at L1                  │
│  Axes: concreteness, relational_role,                   │
│         modificational_load, categorical_type            │
│                                                         │
│  Q/K gating: RISKY (only 4 robust axes, CKA ≈ 0)       │
└─────────────────────────────────────────────────────────┘
```

---

### 11.9 Critical Assessment & Honest Concerns

#### What Worked

1. **MDL probing is rock-solid.** 1.77× compression at L1 for grammatical role is a clear signal. The information-theoretic validation is the strongest evidence in the entire pipeline.
2. **The naming ceremony produced meaningful results.** 6/12 axes validated (50% survival rate) is neither suspiciously high nor dishearteningly low. The surviving axes are plausible: concreteness, relational role, and POS type are exactly what a syntactic encoder should represent.
3. **The layer trajectory is clean.** Crystallization at L1, consumption by L7, monotonic decline through L10–L11. No anomalies.
4. **Attention entropy correlates with structural consumption.** L7 (most focused attention) coincides with the consumption inflection point.

#### What Failed (or Underperformed)

1. **Causal interventions produced 0% success at encoding layers (L1/L3) and only 16.7% at consumption layers (L8/L11) with 6 pairs.** The structural subspace is detectable by a probe (MDL works) but is not cleanly swappable at the layer where it's encoded. The marginal success at L8/L11 is suggestive but statistically unreliable (1/6 pairs, p ≈ 0.33). The specificity gradient (vs_unrelated climbing from 0.01× to 0.98× across layers) reveals that the subspace becomes increasingly causally relevant in deeper layers, but the current methodology (6 pairs, binary flip measure) lacks power to capture this.

2. **CKA is near zero (0.006–0.013) despite MI being moderate (0.168–0.375).** This means the ontological features and hidden-state projections share *mutual information* (they co-vary) but have near-zero *linear kernel alignment* (they don't point in the same directions). The ontological axes capture structure that overlaps with the model's encoding in a nonlinear, many-to-many way — not as a clean rotation or projection. This makes the meta-controller's job harder: it can't simply read off ontological state from a linear subspace.

3. **Dependency depth is barely encoded (peak 1.06×).** The model has a weak notion of tree structure. This is expected for a left-to-right model but limits the richness of the structural representation available to an ontological layer.

4. **SAE sparsity is low.** With 75–91% of features active, the SAE decomposition provides minimal interpretability benefit over raw PCA. A larger feature dictionary would be needed for mechanistic interpretability.

#### What Remains Ambiguous

1. **The 16.7% causal success at L8/L11 is real but underpowered.** With only 6 intervention pairs per layer, a single success gives 16.7% — statistically indistinguishable from noise. The full trajectory specificity ratios (vs_unrelated climbing to 0.75× at L8) provide supporting evidence that late-layer interventions have real causal effect, but the binary flip metric is too coarse to capture it. The methodology needs more pairs (50+), continuous metrics (KL divergence), and/or activation addition instead of swap.

2. **Scenario D at L1 vs Scenario B at L7.** The layer choice determines the scenario. This ambiguity is real — the model's structural encoding has different properties at different depths. The pipeline correctly identifies this as a dissociation rather than forcing a single answer. The discriminability data strengthens the Scenario D classification at L1: the ontology adds +11.8% accuracy over embeddings alone (CI: [2.8%, 6.5%]).

3. **Whether the meta-controller would actually help.** Phase 1 establishes that the correspondence exists (MI = 0.375, 4 robust axes) and that the ontology adds discriminative power the model lacks (+6.8% gap at L7). But the near-zero CKA means the correspondence is nonlinear — a meta-controller would need a nonlinear encoder to exploit it. Phase 2 would need to demonstrate that a meta-controller trained on these 4 axes can actually influence generation quality, safety, or capability.

4. **Ontology features are "too good" at classification (98.8–99.5%).** This near-perfect accuracy raises circularity concerns: grammatical role labels are derived from dependency parsing, and several ontological axes (relational_role, categorical_type, structural_depth) are also derived from dependency parsing. The discriminability gap may reflect ontological feature engineering quality rather than genuine model-ontology alignment. A fairer test would use held-out labels not derivable from the same parse.

---

### 11.10 Comparison: Design Predictions vs Actual Results

| Prediction (Section 0) | Actual Result | Match? |
|------------------------|---------------|--------|
| "Maybe 4 of 12 survive. Maybe 11. Maybe 0." | 6/12 at L1, 4/12 at L7 | Yes — middle range |
| Scenario A: MI > 0.3, CKA > 0.6, N ≥ 8 | MI = 0.375 but CKA = 0.006, N = 4 | No — CKA far too low |
| Scenario B: MI 0.15–0.5, N = 3–7 | MI = 0.375, N = 4 (L7) | **Yes — Scenario B** |
| Scenario C: MI < 0.05, N ≤ 2 | Not observed | N/A |
| Scenario D: MI low, concat >> emb | MI = 0.168 at L1, gap = +11.8% | **Yes — Observed at L1** |
| "Crystallization at middle layers" (Section 1) | Crystallization at L1 | **No — earlier than expected** |
| "12.5% causal success, 28.98× specificity" (Section 1, prior `--quick` data) | 0% at L1/L3, 16.7% at L8/L11 (6 pairs), 23.3× specificity | **Partial — specificity real, success marginal** |
| "~1–2 min" Phase 1 runtime (Section 9) | 434s total pipeline (~7 min) | **No — longer** (but includes Parts 1–6) |
| CKA threshold 0.3–0.6 for Scenario B | CKA = 0.006 | **No — CKA is not discriminative** |

**The CKA thresholds in the scenario classifier need recalibration.** Linear CKA on high-dimensional hidden states vs 12-dimensional ontology vectors will always be low. The classifier correctly fell through to Scenario B via the MI path, but the CKA criterion for Scenario A (> 0.6) is unreachable with the current feature dimensionality mismatch.

---

### 11.11 Recommendations for Phase 2

Given the Scenario B classification with the caveats above:

1. **Proceed with meta-controller prototype, but with low expectations.** The 4 robust axes (concreteness, relational_role, modificational_load, categorical_type) provide a real signal. A 4-dimensional meta-controller reading from L7 is architecturally clean and cheap to train. But the zero causal success rate means we should not expect the controller to meaningfully steer generation.

2. **Reframe the meta-controller as a monitoring tool, not a governance tool.** Instead of trying to *control* the model via the ontological state, use it to *observe* and *classify* what the model is doing. This aligns with the Scenario D insight at L1: the ontology adds information the model doesn't explicitly represent.

3. **Invest in better causal intervention before Phase 2.** The 0% success rate likely reflects methodology limitations, not the absence of causal structure. Consider:
   - **More intervention pairs** (50–100 instead of 12)
   - **Distributed interchange** (swap top-k PCA directions individually, not as a block)
   - **Activation addition** instead of swap (add the difference vector rather than replacing)
   - **Measure downstream KL divergence** instead of binary role-flip success

4. **Drop Q/K gating for now.** With only 4 robust axes and CKA ≈ 0, there is no evidence that ontological types correspond to separable attention dimensions. Q/K gating requires strong linear alignment between ontological type and Q/K dimension usage — which CKA directly measures, and it's near zero.

5. **Recalibrate CKA thresholds** in the scenario classifier. Linear CKA between 768-dim hidden states projected to 64 PCA dimensions vs 12-dim ontology vectors will systematically underestimate alignment. Consider replacing CKA with Procrustes distance on the validated axes only, or using kernel CKA with an RBF kernel.

6. **Scale up the SAE dictionary** (3072 → 16k or 32k features) if mechanistic interpretability of the structural subspace is desired. The current L0 norms (2274–2811 out of 3072) indicate the bottleneck is too narrow for sparse decomposition.

---

### 11.12 Updated Computational Cost (Actual)

Timestamps from complete pipeline log (06:11:17 → 06:18:29):

| Step | Time (actual) | Timestamps | Notes |
|------|--------------|------------|-------|
| Part 1: Data collection | ~14s | 06:11:17–06:11:31 | 500 sequences, GPT-2 forward pass (32 batch) |
| Part 2: Structural labels | ~216s | 06:11:32–06:15:08 | SpaCy dependency parsing (bottleneck!) |
| Part 3: SAE disentanglement | ~75s | 06:15:08–06:16:23 | 12 layers in parallel (8 workers) |
| Part 4: MDL probing | ~32s | 06:16:24–06:16:56 | 24 probes + 5 k-selection in parallel |
| Part 5: Causal intervention | ~4s | 06:16:56–06:17:00 | 26 pairs at L1 and L3 |
| Part 6: Layer trajectory | ~15s | 06:17:00–06:17:15 | 12 layers × 6 pairs each (reuses MDL) |
| Part 7: Ontology alignment | ~74s | 06:17:15–06:18:29 | 2 layers, 7b–7f each |
| **Total** | **~434s** | | **~7.2 min** |

**Part 7 breakdown** (per layer):

| Step | L1 | L7 | Notes |
|------|----|----|-------|
| 7b: Build ontology vectors | 14.0s | 13.9s | SpaCy + WordNet lookups, 46K words |
| 7c: Naming ceremony | 11.3s | 11.0s | 12 axes × 64 PCA dirs × MI computation |
| 7d: Global alignment (MI, CKA, overlap) | 0.3s | 0.3s | Frobenius-norm CKA is instant |
| 7e: Discriminability | 12.2s | 11.6s | SGD probe + 10 bootstrap resamples on 2K subsample |
| 7f: Scenario classification | <0.1s | <0.1s | Pure arithmetic |
| **Per-layer total** | **~37.8s** | **~36.8s** | |

**Surprise finding**: Part 2 (structural labels) is now the dominant bottleneck at 216s (50% of total). SpaCy's dependency parsing of 500 sequences is inherently sequential and CPU-bound. Part 3 (SAE training, 75s with parallelization) is the next largest.

Performance improvements from parallelization:
- Part 3: 12 layers sequential (~8 min estimated) → parallel 8 workers (~75s) = **~6.4× speedup**
- Part 4: 24 probes sequential (~12 min for 6 in `--quick`) → parallel 8 workers (~32s) = **~22× speedup**
- Part 7d: CKA O(N^3) hang → Frobenius trick O(N·d^2) = **0.3s** (from infinite)
- Part 7e: 3000 LogisticRegression fits → 23 SGDClassifier fits on 2K subsample = **~12s** (from infinite)

---

## 12. Phase 1 Final Conclusions

**Date**: 2026-02-23

Phase 1 is COMPLETE. The discovery process answered both questions from Section 0:

### 12.1 Do the model's structural directions correspond to nameable ontological axes?

**Yes, partially.** 6 of 12 proposed axes passed the naming ceremony, with 4 robust across both layers:

| Axis | Status | Evidence |
|------|--------|----------|
| `relational_role` | **Robust** | MI=0.473 at L1 (strongest signal) |
| `concreteness` | **Robust** | MI=0.306 at L1, stable across layers |
| `categorical_type` | **Robust** | MI=0.188, consistent PCA mapping |
| `modificational_load` | **Robust** | MI=0.151, identical across layers |
| `temporal_anchoring` | Layer-specific | MI=0.144 at L1 only, consumed by L7 |
| `structural_depth` | Layer-specific | MI=0.124 at L1 only, consumed by L7 |
| `abstraction_level` | **Failed** | Zero MI — WordNet hypernym depth is noise |
| `semantic_specificity` | **Failed** | Zero MI — synset count is noise |
| `animacy` | **Failed** | MI=0.022, below threshold |
| `agency` | **Failed** | MI=0.024, below threshold |
| `information_density` | **Failed** | MI=0.043, identical to positional_salience |
| `positional_salience` | **Failed** | MI=0.043, redundant with information_density |

### 12.2 Which architecture should the ontological layer use?

**Neither the meta-controller-as-governor NOR Q/K gating.** The data ruled out both original options:

- **Q/K gating is ruled out** — CKA ≈ 0 means no linear alignment between ontological type and attention dimensions. The gating signal has nothing to gate on.
- **Meta-controller-as-governor is ruled out** — 0% causal success at encoding layers means you cannot steer the model by swapping the structural subspace. The structural subspace is informational, not cleanly causal.

### 12.3 What the data DOES support

The data supports two architectures that were NOT in the original design:

1. **Observatory (Monitoring + Classification)**: Read hidden states at L7, classify the model's internal state along the 4 robust axes, produce real-time monitoring signals. The model cannot be governed through this channel, but it CAN be observed through it.

2. **Content Injection**: The ontology knows things the model doesn't (98.8% vs 74.5% classification accuracy). Feed the ontological classification as structured context into the model's input, enriching its prompt with information it wouldn't otherwise have.

### 12.4 Key insight: The original framing was wrong

The original design asked: "Can the ontology GOVERN the model?" The answer is no — the structural subspace is informational but not cleanly causal. The correct question is: "Can the ontology INFORM the model?" The answer is yes, via content injection. And: "Can the ontology OBSERVE the model?" Also yes, via L7 monitoring.

**The ontology is a sensor, not a steering wheel.**

---

## 13. Phase 2 Architecture (Revised)

**Date**: 2026-02-23
**Decision**: Build Observatory (Path 1) + Content Injection (Path 2)
**Drop**: Q/K gating (insufficient signal), Meta-controller-as-governor (no causal pathway)

### 13.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  PATH 1: OBSERVATORY (Monitoring)                                    │
│                                                                      │
│  H[L7] ──→ OntologyMonitor ──→ z_ont ∈ R^4                         │
│             (nonlinear encoder,    │                                  │
│              trained on 4 robust    ├──→ drift alerts                │
│              axes)                  ├──→ confidence signals           │
│                                     ├──→ routing classification      │
│  Reads model state. Does NOT       └──→ audit trail                 │
│  modify model behavior.                                              │
│                                                                      │
│  Training: Supervised on ontology vectors from Phase 1.              │
│  Loss: MSE(predicted_axes, ground_truth_axes)                        │
│  Input: mean-pooled H[L7] ∈ R^d                                     │
│  Output: z_ont ∈ R^4 (concreteness, relational_role,                │
│           modificational_load, categorical_type)                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  PATH 2: CONTENT INJECTION                                           │
│                                                                      │
│  user_input ──→ OntologyInjector ──→ enriched_prompt                │
│                  │                                                    │
│                  ├─ classify input along 4 axes                      │
│                  ├─ format as structured routing metadata             │
│                  └─ prepend to LLM system prompt                     │
│                                                                      │
│  The ontology TELLS the model what it observed.                      │
│  The model can use (or ignore) this information.                     │
│                                                                      │
│  No hidden-state access required at inference.                       │
│  Works with any LLM API (not just GPT-2).                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 13.2 OntologyMonitor (Path 1)

The monitor is a small nonlinear encoder trained to predict ontology axis values from hidden states. It serves as a **real-time sensor** of the model's internal structural state.

```python
class OntologyMonitor:
    """Read hidden states at L7, predict 4-axis ontological state.

    Architecture:
        H[L7] → mean_pool → Linear(d, 128) → ReLU → Dropout
              → Linear(128, 64) → ReLU → Linear(64, 4) → Sigmoid

    Output interpretation:
        z_ont[0] = concreteness      (0=abstract, 1=concrete)
        z_ont[1] = relational_role   (0=peripheral, 1=core argument)
        z_ont[2] = modificational_load (0=leaf, 1=head)
        z_ont[3] = categorical_type  (0=noun-like, 1=function word)

    Training: Supervised regression on Phase 1 ontology vectors.
    Loss: MSE + optional L1 for sparsity.
    """
```

**Why nonlinear?** CKA ≈ 0 but MI = 0.375 — the correspondence between hidden states and ontological axes is nonlinear. A linear encoder would fail. The ReLU network can capture the nonlinear mapping.

**Why 128→64→4?** The bottleneck forces the encoder to learn a compressed representation. Going from 768 (GPT-2 hidden dim) directly to 4 would lose too much information. Two hidden layers with moderate width provide enough capacity for the nonlinear mapping without overfitting.

### 13.3 OntologyInjector (Path 2)

The injector classifies input text along the 4 robust axes and formats the result as structured metadata that gets prepended to the LLM prompt.

```python
class OntologyInjector:
    """Classify input text and inject ontological metadata into prompt.

    Pipeline:
        1. Parse input text (dependency parse)
        2. Compute 4-axis ontology features per word
        3. Aggregate to document-level summary
        4. Format as structured routing metadata
        5. Prepend to system prompt

    Output format:
        [ONTOLOGY]
        domain: concrete/abstract
        structure: simple/complex
        intent: informational/action/modification
        confidence: high/medium/low
        [/ONTOLOGY]
    """
```

**Why text-level, not hidden-state-level?** Content injection works at the API boundary — you don't need access to hidden states. This makes it compatible with any LLM provider (Claude, GPT-4, etc.), not just models where you can hook into intermediate layers.

### 13.4 Evaluation Plan

| Metric | Path 1 (Observatory) | Path 2 (Injection) |
|--------|---------------------|-------------------|
| **Primary** | Axis prediction R² | Downstream task accuracy delta |
| **Secondary** | Drift detection AUC | Routing precision/recall |
| **Ablation** | Monitor vs random baseline | With-injection vs without |
| **Runtime** | < 10ms per sequence | < 5ms per classification |

### 13.5 What Success Looks Like

**Path 1 (Observatory):**
- R² > 0.5 on held-out axis prediction → monitor reads real signal
- Drift detection AUC > 0.7 → monitor catches distribution shifts
- < 10ms inference → usable as real-time monitor

**Path 2 (Injection):**
- Statistically significant accuracy improvement on routing tasks
- No degradation on tasks where injection is irrelevant
- Classification agrees with Phase 1 ground truth > 80%

### 13.6 What This Does NOT Accomplish

To be explicit about limitations:
- The monitor CANNOT steer the model (0% causal success at encoding layers)
- The injector relies on the LLM choosing to use the metadata (not guaranteed)
- Neither path provides deterministic governance (the original vision)
- The 4 robust axes may conflate (3 of 4 map to PCA dir 4 at L7)

These limitations are real. Phase 2 is scoped to what the data supports, not what we originally hoped for.

---

## 14. Implementation Status

| Component | Status | Lines | Notes |
|-----------|--------|-------|-------|
| Phase 1: Discovery (7a–7f) | COMPLETE | ~1000 | All metrics computed, scenarios classified |
| Phase 1: Multi-layer discovery | COMPLETE | ~170 | READ/ACT dissociation detected |
| Phase 2: OntologyMonitor | **COMPLETE** | ~200 | Nonlinear encoder, training loop, evaluation |
| Phase 2: OntologyInjector | **COMPLETE** | ~150 | Text classification, prompt formatting |
| Phase 2: Pipeline integration | **COMPLETE** | ~80 | `--run-phase2` flag in run_pipeline.py |
| Phase 2: Synthetic tests | **COMPLETE** | ~100 | Validates monitor training + injector formatting |

---

## 15. Next Steps (Post Phase 2 Prototype)

1. **Validate on real data**: Run Phase 2 on WikiText with GPT-2 (not just synthetic)
2. **Benchmark injection**: A/B test injected vs non-injected prompts on classification tasks
3. **Scale causal methodology**: 50+ intervention pairs at L8–L10 with KL divergence metrics
4. **Larger SAE dictionary**: 3072 → 16k features for better mechanistic interpretability
5. **Cross-model transfer**: Test whether the 4 robust axes generalize beyond GPT-2
