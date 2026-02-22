# Part 7: Ontology Alignment Validation — Design Document

**Status**: Draft
**Date**: 2026-02-22
**Depends on**: Parts 1–6 of causal subspace pipeline (validated)

---

## 1. Motivation

Parts 1–6 established that:
- Transformer hidden states encode grammatical role information in a low-dimensional subspace (MDL compression > 1.5x)
- This subspace is causally load-bearing (12.5% causal success, 28.98x specificity over random)
- Information crystallizes at middle layers and is consumed downstream

**Part 7 asks**: Can we align an *external ontological structure* with this validated subspace, and can that alignment serve as a gating signal that improves or controls model behavior?

If yes → the ontology provides interpretable, steerable handles on the model's internal representations.
If no → the model's structural encoding is self-consistent but opaque to external categorical systems.

---

## 2. Architecture

```
Existing pipeline outputs
    │
    ├── store.states[layer]            # [N_tok, d]   raw hidden states
    ├── store.attention_entropy[layer]  # [N_tok, H]   per-head entropy
    ├── annotations.hidden_states[layer]# [N_w, d]     word-level states
    ├── annotations.labels_role         # [N_w]        grammatical roles
    ├── best_pca_basis                  # [d, k]       MDL-validated basis
    ├── disentanglement.sae_features    # [N_w, s]     sparse features
    ├── disentanglement.cluster_labels  # [N_w]        contextual clusters
    ├── trajectory.crystallization_layer# int
    └── trajectory.consumption_layer    # int
        │
        ▼
  ┌─────────────────────────────────────────────────┐
  │  PART 7: Ontology Alignment Validation          │
  │                                                 │
  │  7a. Build ontology vectors                     │
  │      ├── WordNet hypernym depth                 │
  │      ├── Animacy / concreteness features        │
  │      └── Dependency-derived role prototypes     │
  │                                                 │
  │  7b. Compute alignment metrics                  │
  │      ├── Mutual information (MI)                │
  │      ├── Projection overlap (subspace angles)   │
  │      └── CKA similarity                         │
  │                                                 │
  │  7c. Simulate ontology-gated inference          │
  │      ├── Fit lightweight gate on frozen acts    │
  │      ├── Measure perplexity impact              │
  │      └── Measure attention entropy change       │
  │                                                 │
  │  7d. Ontology discriminability analysis         │
  │      ├── Classify roles from ontology features  │
  │      ├── Compare vs model embedding baseline    │
  │      └── Bootstrap confidence intervals         │
  └─────────────────────────────────────────────────┘
        │
        ▼
  GO / NO-GO decision (see §7)
```

---

## 3. Module Design

### 3.1 File: `ontology_alignment.py`

New module alongside existing pipeline components.

```python
# scripts/causal_subspace/ontology_alignment.py

@dataclass
class OntologyConfig:
    """Configuration for ontology alignment validation."""

    # Ontology vector construction
    use_wordnet: bool = True
    use_concreteness: bool = True
    use_role_prototypes: bool = True
    prototype_n_samples: int = 100      # samples per role for prototype

    # Alignment metrics
    mi_n_bins: int = 20                 # bins for MI estimation
    cka_kernel: str = "linear"          # "linear" or "rbf"

    # Gating simulation
    gate_lr: float = 1e-3
    gate_epochs: int = 30
    gate_batch_size: int = 256
    gate_hidden_dim: int = 64           # small MLP for gating

    # Discriminability
    n_bootstrap: int = 200
    bootstrap_ci: float = 0.95

    device: str = "cpu"
    seed: int = 42


@dataclass
class OntologyAlignmentResult:
    """Output of ontology alignment validation for one layer."""

    layer_idx: int

    # 7a: Ontology vectors
    ontology_dim: int = 0               # dimensionality of ontology feature space
    n_words_with_ontology: int = 0      # coverage (words with valid ontology vectors)
    coverage_ratio: float = 0.0         # n_words_with_ontology / total_words

    # 7b: Alignment metrics
    alignment_mi: float = 0.0           # mutual information (nats)
    alignment_mi_normalized: float = 0.0 # MI / min(H(X), H(Y))
    subspace_overlap: float = 0.0       # principal angle cosine (0=orthogonal, 1=aligned)
    cka_similarity: float = 0.0         # centered kernel alignment

    # 7c: Gating simulation
    gated_perplexity_ratio: float = 0.0 # patched_ppl / original_ppl
    gated_entropy_delta: float = 0.0    # mean(entropy_gated - entropy_original)
    gate_sparsity: float = 0.0          # fraction of gate values < 0.1

    # 7d: Discriminability
    ontology_role_accuracy: float = 0.0 # classify roles from ontology features
    embedding_role_accuracy: float = 0.0 # classify roles from model embeddings
    discriminability_gap: float = 0.0   # ontology_acc - embedding_acc
    accuracy_ci_low: float = 0.0        # bootstrap CI lower
    accuracy_ci_high: float = 0.0       # bootstrap CI upper

    # GO/NO-GO
    go_decision: bool = False
    go_reasons: List[str] = field(default_factory=list)
    nogo_reasons: List[str] = field(default_factory=list)
```

---

## 4. Subpart Specifications

### 4a. Build Ontology Vectors

**Goal**: Construct a feature vector `ont[i] ∈ R^F` for each word `i` in the annotated corpus, encoding external ontological properties.

**Feature sources** (concatenated into a single vector per word):

| Feature | Dim | Source | Description |
|---------|-----|--------|-------------|
| WordNet hypernym depth | 1 | NLTK WordNet | Depth of most common synset in hypernym tree (0=entity, higher=specific) |
| WordNet lexicographer file | 26 | NLTK WordNet | One-hot over lex file categories (noun.animal, verb.motion, etc.) |
| Concreteness rating | 1 | Brysbaert et al. 2014 norms | 1–5 scale (abstract→concrete). Fallback: 3.0 |
| Animacy | 1 | WordNet "entity→organism" path | Binary: is the word's hypernym chain animate? |
| POS tag | ~17 | spaCy or heuristic | One-hot over Universal POS tags |
| Role prototype distance | 5 | Computed from Part 2 labels | Euclidean distance from mean hidden state of each grammatical role |

**Total ontology dimension**: F ≈ 51 (exact depends on POS tag set and WordNet coverage)

**Implementation**:

```python
def build_ontology_vectors(
    annotations: StructuralAnnotations,
    H: np.ndarray,                       # [N_w, d] hidden states at target layer
    labels: np.ndarray,                  # [N_w] role labels
    cfg: OntologyConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build ontology feature vectors for annotated words.

    Returns
    -------
    ont_features : np.ndarray [N_w, F]
        Ontology feature vectors.  NaN rows for words without coverage.
    valid_mask : np.ndarray [N_w] bool
        True where ontology features are available.
    """
```

**Key design decisions**:
- Words not in WordNet (function words, subword artifacts) get NaN → excluded from MI computation
- Role prototype distances are computed from the same layer's hidden states, creating a bridge between model space and ontology space
- All features are standardized (zero mean, unit variance) before alignment computation

### 4b. Compute Alignment Metrics

Three complementary measures, each capturing a different aspect of alignment:

#### Mutual Information (MI)

Measures statistical dependence between ontology-predicted role and model-subspace-predicted role.

```python
def compute_alignment_mi(
    ont_features: np.ndarray,    # [N, F]
    H_proj: np.ndarray,          # [N, k]  (H projected onto U_k)
    labels: np.ndarray,          # [N]     ground-truth roles
    n_bins: int = 20,
) -> Tuple[float, float]:
    """Compute MI between ontology features and subspace projections.

    Strategy:
    1. Discretize both ont_features and H_proj into bins
    2. Compute MI(ont_binned; H_proj_binned)  (direct MI)
    3. Also compute MI(ont_pred_role; subspace_pred_role)
       where predictions come from k-NN or linear probe

    Returns (mi_raw, mi_normalized).
    """
```

**Threshold**: MI > 0.3 nats for GO (this is substantial — random is ~0.0, perfect alignment is ~log(5) ≈ 1.6 nats for 5 roles).

#### Subspace Overlap (Principal Angles)

Measures geometric alignment between the ontology feature subspace and the model's structural subspace.

```python
def compute_subspace_overlap(
    ont_features: np.ndarray,    # [N, F]
    U_k: np.ndarray,             # [d, k]  structural basis
    H: np.ndarray,               # [N, d]  hidden states
) -> float:
    """Compute principal angle overlap.

    Strategy:
    1. PCA on ont_features → O_k ∈ R^{F × k_ont}  (ontology subspace)
    2. Project H onto both U_k and O_k
    3. Compute canonical correlations between projections
    4. Return mean cosine of principal angles

    Result ∈ [0, 1]: 0 = orthogonal, 1 = perfectly aligned.
    """
```

#### CKA Similarity

Centered Kernel Alignment — measures representational similarity between two representation matrices regardless of dimensionality.

```python
def compute_cka(
    X: np.ndarray,    # [N, d1]  (model subspace projections)
    Y: np.ndarray,    # [N, d2]  (ontology features)
    kernel: str = "linear",
) -> float:
    """Linear or RBF CKA between two representation matrices.

    CKA ∈ [0, 1]: 1 = identical representational structure.
    """
```

### 4c. Simulate Ontology-Gated Inference

**Goal**: Test whether an ontology-derived gating signal can modulate model behavior meaningfully without destroying fluency.

**Gating mechanism**: A small MLP that takes ontology features and outputs a gate vector in the structural subspace.

```
ont_features [F] → MLP(F, hidden, k) → σ(·) → gate [k] ∈ [0, 1]^k

h_gated = h - U_k @ U_k^T @ h + U_k @ diag(gate) @ U_k^T @ h
```

This selectively scales each structural subspace component based on ontology-derived features. When `gate[i] = 1.0`, the component passes through unchanged. When `gate[i] = 0.0`, the component is ablated.

**Training objective**: The gate MLP is trained to minimize a combination of:
1. **Role prediction loss**: Cross-entropy on grammatical role prediction from gated activations (encourages the gate to preserve role-discriminative information)
2. **Sparsity penalty**: L1 on gate values (encourages selective gating)
3. **Reconstruction penalty**: MSE between gated and original activations (prevents catastrophic perturbation)

```python
L = L_role(gate) + λ_sparse * ||gate||_1 + λ_recon * ||h_gated - h||^2
```

**Evaluation** (on held-out words, no gradient):

| Metric | Computation | GO threshold |
|--------|-------------|--------------|
| Perplexity ratio | Run gated activations through remaining layers, compute PPL ratio | < 2.0 |
| Attention entropy delta | Compare attention entropy at subsequent layers with/without gating | Negative (entropy drops = more structured attention) |
| Gate sparsity | Fraction of gate dimensions consistently < 0.1 | > 0.3 (some components are unused → parsimony) |

**Implementation**:

```python
@dataclass
class GateSimulator:
    """Lightweight MLP that maps ontology features to subspace gates."""
    mlp: nn.Module          # F → hidden → k, with sigmoid output
    U_k: torch.Tensor       # [d, k] structural basis

    def forward(self, h: torch.Tensor, ont: torch.Tensor) -> torch.Tensor:
        """Apply ontology gate to hidden state.

        Parameters
        ----------
        h : [batch, d]   hidden state at target layer
        ont : [batch, F]  ontology features for these words

        Returns
        -------
        h_gated : [batch, d]
        """
        gate = torch.sigmoid(self.mlp(ont))       # [batch, k]
        proj = self.U_k.T @ h.unsqueeze(-1)       # [batch, k, 1]
        proj_gated = proj * gate.unsqueeze(-1)     # [batch, k, 1]
        h_gated = h - (self.U_k @ proj).squeeze(-1) + (self.U_k @ proj_gated).squeeze(-1)
        return h_gated


def simulate_gated_inference(
    model: nn.Module,
    store: HiddenStateStore,
    annotations: StructuralAnnotations,
    ont_features: np.ndarray,
    U_k: np.ndarray,
    target_layer: int,
    cfg: OntologyConfig,
) -> Dict[str, float]:
    """Train gate MLP and measure impact on model behavior.

    Returns dict with:
        perplexity_ratio, entropy_delta, gate_sparsity,
        role_accuracy_gated, gate_weights (for inspection).
    """
```

**Critical constraint**: The model is frozen. Only the gate MLP (tiny — ~F*hidden + hidden*k ≈ 51*64 + 64*16 ≈ 4.3K parameters) is trained. This ensures we're measuring alignment, not fine-tuning.

### 4d. Ontology Discriminability Analysis

**Goal**: Determine whether ontology features carry *additional* information about grammatical roles beyond what model embeddings provide.

```python
def measure_discriminability(
    ont_features: np.ndarray,    # [N, F]
    H: np.ndarray,               # [N, d]
    labels: np.ndarray,          # [N] role labels
    n_bootstrap: int = 200,
) -> Dict[str, float]:
    """Compare role classification accuracy: ontology features vs model embeddings.

    Strategy:
    1. Linear probe (logistic regression) on ont_features → labels
    2. Linear probe on H (raw model embeddings) → labels
    3. Linear probe on [ont_features; H] (concatenated) → labels
    4. Bootstrap all three to get confidence intervals

    If concat > max(ont, H), ontology adds complementary information.
    If ont ≈ H, ontology encodes redundant (but interpretable) features.
    If ont << H, ontology is not useful.
    """
```

---

## 5. Integration with `run_pipeline.py`

```python
# After Part 6 (trajectory), before Final Report:

# ===================================================================
# PART 7: Ontology Alignment Validation (GO/NO-GO)
# ===================================================================
if not skip_ontology:
    print("\n" + "=" * 70)
    print("PART 7: ONTOLOGY ALIGNMENT VALIDATION")
    print("=" * 70)

    ont_cfg = OntologyConfig(device=device, seed=seed)
    cryst_layer = trajectory.crystallization_layer

    # Target the crystallization layer — where structural info peaks
    H = annotations.hidden_states[cryst_layer]
    labels = annotations.labels_role

    # 7a: Build ontology vectors
    ont_features, valid_mask = build_ontology_vectors(
        annotations, H, labels, ont_cfg,
    )
    H_valid = H[valid_mask]
    labels_valid = labels[valid_mask]
    ont_valid = ont_features[valid_mask]

    # 7b: Alignment metrics
    U_k = best_pca_basis  # from Part 4 (MDL-validated)
    H_proj = H_valid @ U_k  # project onto structural subspace

    mi_raw, mi_norm = compute_alignment_mi(
        ont_valid, H_proj, labels_valid, ont_cfg.mi_n_bins,
    )
    overlap = compute_subspace_overlap(ont_valid, U_k, H_valid)
    cka = compute_cka(H_proj, ont_valid, ont_cfg.cka_kernel)

    # 7c: Gating simulation
    gate_results = simulate_gated_inference(
        model, store, annotations, ont_features,
        U_k, cryst_layer, ont_cfg,
    )

    # 7d: Discriminability
    disc_results = measure_discriminability(
        ont_valid, H_valid, labels_valid, ont_cfg.n_bootstrap,
    )

    # Assemble result
    ont_result = OntologyAlignmentResult(
        layer_idx=cryst_layer,
        ontology_dim=ont_valid.shape[1],
        n_words_with_ontology=int(valid_mask.sum()),
        coverage_ratio=float(valid_mask.mean()),
        alignment_mi=mi_raw,
        alignment_mi_normalized=mi_norm,
        subspace_overlap=overlap,
        cka_similarity=cka,
        gated_perplexity_ratio=gate_results["perplexity_ratio"],
        gated_entropy_delta=gate_results["entropy_delta"],
        gate_sparsity=gate_results["gate_sparsity"],
        ontology_role_accuracy=disc_results["ontology_accuracy"],
        embedding_role_accuracy=disc_results["embedding_accuracy"],
        discriminability_gap=disc_results["gap"],
        accuracy_ci_low=disc_results["ci_low"],
        accuracy_ci_high=disc_results["ci_high"],
    )

    # GO/NO-GO decision
    ont_result = evaluate_go_nogo(ont_result)
    results["ontology_alignment"] = asdict(ont_result)
```

---

## 6. Data Flow Diagram (Detailed)

```
                    ┌─────────────────────┐
                    │  annotations.words   │
                    │  (word text, POS,    │
                    │   dep_relation)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   7a. build_ontology │
                    │        _vectors()    │
                    │                      │
                    │  WordNet lookup ──────── hypernym depth, lex file,
                    │  Concreteness DB ────── concreteness, animacy
                    │  POS tags ───────────── one-hot POS
                    │  Role prototypes ────── dist to role centroids
                    │                      │
                    │  → ont_features [N,F] │
                    │  → valid_mask [N]     │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
  ┌──────────────┐   ┌────────────────┐    ┌────────────────┐
  │  7b. Align   │   │ 7c. Gate sim   │    │  7d. Discrim   │
  │              │   │                │    │                │
  │  ont ←→ U_k  │   │  ont → MLP →   │    │  ont → probe → │
  │  MI, overlap, │   │  gate → patch  │    │  accuracy      │
  │  CKA         │   │  → PPL, H(attn)│    │  vs H → probe  │
  └──────┬───────┘   └───────┬────────┘    └───────┬────────┘
         │                   │                     │
         └─────────────────┐ │ ┌───────────────────┘
                           ▼ ▼ ▼
                    ┌──────────────────┐
                    │  GO / NO-GO      │
                    │  Decision Logic  │
                    └──────────────────┘
```

---

## 7. GO / NO-GO Decision Logic

```python
def evaluate_go_nogo(result: OntologyAlignmentResult) -> OntologyAlignmentResult:
    """Apply GO/NO-GO decision criteria."""

    # --- GO conditions (ALL must hold) ---
    go_checks = [
        (result.alignment_mi > 0.3,
         f"MI = {result.alignment_mi:.3f} > 0.3"),
        (result.gated_perplexity_ratio < 2.0,
         f"PPL ratio = {result.gated_perplexity_ratio:.2f} < 2.0"),
        (result.gated_entropy_delta < 0.0,
         f"Entropy delta = {result.gated_entropy_delta:.3f} < 0 (more structured)"),
        (result.coverage_ratio > 0.3,
         f"Coverage = {result.coverage_ratio:.1%} > 30%"),
    ]

    # --- Hard NO-GO conditions (ANY triggers) ---
    nogo_checks = [
        (result.alignment_mi < 0.05,
         f"MI ≈ 0 ({result.alignment_mi:.4f}): ontology orthogonal to model"),
        (result.gated_perplexity_ratio > 5.0,
         f"PPL ratio = {result.gated_perplexity_ratio:.1f}: gating destroys fluency"),
        (result.coverage_ratio < 0.1,
         f"Coverage = {result.coverage_ratio:.1%}: ontology covers too few words"),
    ]

    result.go_reasons = [msg for ok, msg in go_checks if ok]
    result.nogo_reasons = [msg for triggered, msg in nogo_checks if triggered]

    # GO requires all go_checks pass AND no hard nogo triggered
    all_go = all(ok for ok, _ in go_checks)
    any_nogo = any(triggered for triggered, _ in nogo_checks)
    result.go_decision = all_go and not any_nogo

    return result
```

**Decision matrix**:

| Scenario | MI | PPL ratio | Entropy Δ | Coverage | Decision |
|----------|-----|-----------|-----------|----------|----------|
| Strong alignment | > 0.3 | < 2.0 | < 0 | > 30% | **GO** |
| Weak alignment | 0.05–0.3 | < 2.0 | any | > 30% | INVESTIGATE |
| Orthogonal | < 0.05 | any | any | any | **NO-GO** |
| Destructive gating | any | > 5.0 | any | any | **NO-GO** |
| Low coverage | any | any | any | < 10% | **NO-GO** |

---

## 8. Testing Strategy

### Unit tests (`tests/test_causal_subspace.py`)

```python
class TestOntologyAlignment:

    def test_build_ontology_vectors_shape(self, synthetic_hidden_states):
        """Ontology vectors have expected shape [N, F]."""

    def test_ontology_coverage(self, synthetic_hidden_states):
        """Coverage ratio is between 0 and 1, valid_mask is boolean."""

    def test_alignment_mi_separable(self):
        """MI is high when ontology features predict subspace projections."""

    def test_alignment_mi_random(self):
        """MI is near zero when features and projections are independent."""

    def test_subspace_overlap_identical(self):
        """Overlap is 1.0 when subspaces are identical."""

    def test_subspace_overlap_orthogonal(self):
        """Overlap is 0.0 when subspaces are orthogonal."""

    def test_cka_identity(self):
        """CKA is 1.0 when representations are identical."""

    def test_gate_preserves_fluency(self):
        """Gated perplexity ratio < 2.0 with identity gate."""

    def test_gate_ablation_increases_ppl(self):
        """All-zero gate increases perplexity (subspace is load-bearing)."""

    def test_discriminability_bootstrap_ci(self):
        """Bootstrap CIs are valid (low < mean < high)."""

    def test_go_nogo_all_pass(self):
        """GO when all criteria met."""

    def test_go_nogo_hard_nogo(self):
        """NO-GO when any hard condition triggered."""
```

### Synthetic test (`test_synthetic.py`)

Add `run_part7_ontology_alignment_synthetic()` that:
1. Creates synthetic ontology features correlated with role labels
2. Runs the full Part 7 pipeline
3. Verifies GO decision with synthetic aligned data
4. Verifies NO-GO decision with random ontology features

### Real test (`test_real.py`)

Add validation checks:
```python
# Check 7a: Ontology alignment MI
# Check 7b: Gated perplexity
# Check 7c: Attention entropy change
# Check 7d: Ontology discriminability
# Check 7e: GO/NO-GO decision
```

---

## 9. Dependencies

**New external dependencies** (all available via pip):

| Package | Purpose | Already in project? |
|---------|---------|---------------------|
| `nltk` (wordnet) | Hypernym depth, lexicographer files, animacy | No — add to requirements |
| `scikit-learn` | Logistic regression, mutual_info_score | Yes (already used) |
| `scipy` | Bootstrap, canonical correlations | Yes (already used) |

**WordNet data** is downloaded on first use via `nltk.download('wordnet')`. The concreteness norms can be bundled as a small CSV (~40K entries, ~500KB) or fetched on first run.

---

## 10. Computational Cost Estimate

| Subpart | Operations | Estimated time (CPU, 200 seqs) |
|---------|-----------|-------------------------------|
| 7a. Build ontology vectors | WordNet lookups + POS + prototypes | ~10–30s |
| 7b. Alignment metrics | MI + principal angles + CKA | ~5–15s |
| 7c. Gate simulation | Train small MLP (30 epochs) + eval | ~30–120s |
| 7d. Discriminability | 3 probes × 200 bootstraps | ~30–60s |
| **Total** | | **~1.5–4 min** |

This is substantially cheaper than Part 5 (causal interventions) which requires 6 forward passes per pair through the full model.

---

## 11. Implementation Plan

| Step | Task | Files | Depends on |
|------|------|-------|------------|
| 1 | Create `OntologyConfig` and `OntologyAlignmentResult` dataclasses | `ontology_alignment.py` | — |
| 2 | Implement `build_ontology_vectors()` with WordNet + POS + prototypes | `ontology_alignment.py` | Step 1 |
| 3 | Implement `compute_alignment_mi()`, `compute_subspace_overlap()`, `compute_cka()` | `ontology_alignment.py` | Step 1 |
| 4 | Implement `GateSimulator` and `simulate_gated_inference()` | `ontology_alignment.py` | Steps 1–2 |
| 5 | Implement `measure_discriminability()` with bootstrap | `ontology_alignment.py` | Step 1 |
| 6 | Implement `evaluate_go_nogo()` | `ontology_alignment.py` | Steps 1–5 |
| 7 | Unit tests for each component | `tests/test_causal_subspace.py` | Steps 1–6 |
| 8 | Integrate into `run_pipeline.py` as Part 7 | `run_pipeline.py` | Steps 1–6 |
| 9 | Add synthetic test coverage | `test_synthetic.py` | Steps 7–8 |
| 10 | Add real-model validation checks | `test_real.py` | Steps 7–8 |
| 11 | Update `__init__.py` exports | `__init__.py` | Step 8 |

---

## 12. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| WordNet coverage too low for subword tokens | Medium | Fall back to lemmatized forms; use POS + role prototypes as backup features |
| MI estimation noisy at small N | Medium | Use k-NN MI estimator (Kraskov et al.) instead of binning; increase corpus size |
| Gate MLP overfits on small corpus | Medium | Strong L2 regularization + early stopping; cross-validation |
| Concreteness norms not available for all words | Low | Default to 3.0 (middle); flag low-coverage in results |
| CKA dominated by first PCA component | Low | Use debiased CKA variant (Nguyen et al. 2021) |

---

## 13. Open Questions

1. **Which layer to target?** Current plan: crystallization layer (peak MDL compression). Alternative: run on multiple layers and report the best.

2. **Ontology granularity**: Should we use coarse roles (5 classes: subject/object/root/modifier/other) or finer-grained semantic roles (agent/patient/instrument/location/...)?

3. **Concreteness norms**: Bundle as CSV in repo, or download on first use? Bundling is more reliable but adds to repo size.

4. **Gate architecture**: Simple linear gate (`ont → σ(W·ont + b)`) vs MLP? Linear is more interpretable but MLP has more capacity. Start with linear, escalate if alignment is weak.
