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

**Part 7 asks**: Can we align an *external ontological structure* with this validated subspace, and can that alignment serve as a governance signal — controlling which computational pathways activate — without injecting content?

If yes → the ontology provides interpretable, steerable control over the model's structural computation.
If no → the model's structural encoding is self-consistent but opaque to external categorical systems.

---

## 1b. Architectural Role: Why Governance, Not K/V

A transformer's forward pass has three kinds of entities:

```
K (keys)   = "what does this token contain?"     → content identity
V (values) = "what information does it provide?" → content payload
Q (queries)= "what is this token looking for?"   → content request
```

All three are **content entities** — they encode *what*. The ontology is not a fourth content entity. It is a **process controller** — it encodes *whether*.

### Three candidate architectures (and why only one is governance)

```
Architecture A: Content Injection (NOT governance)
─────────────────────────────────────────────────
  K_eff = K + W_ont @ ont_features
  V_eff = V + W_ont @ ont_features

  Problem: The ontology becomes another embedding. It competes with
  the model's learned representations. This is fine-tuning with
  extra inputs, not governance. The ontology's categorical
  knowledge is reduced to a vector that gets mixed into content.

Architecture B: Hidden-State Mask (NOT governance)
─────────────────────────────────────────────────
  h_masked = h_⊥ + U_k @ diag(gate) @ U_k^T @ h

  Problem: Modifies WHAT the token represents. Architecturally
  identical to LoRA / conditional LayerNorm / activation masking.
  The ontology is a perturbation on content, not a policy on
  process. Changes data, not mechanism.

Architecture C: Pathway Governance (THIS is governance)
─────────────────────────────────────────────────────
  The ontology controls WHICH computational pathways are
  active and HOW information flows, without modifying the
  information itself.

  Three governance surfaces:
    C1. Head-level gating    — which attention heads fire
    C2. Subspace gating on V — which structural components of V flow
    C3. Attention prior       — structural bias on attention routing
```

### Architecture C in detail

The ontology operates at three governance surfaces, each controlling a different aspect of the attention mechanism:

```
Standard attention (no governance):

  attn = softmax(Q K^T / √d)          ← content-based routing
  out  = attn @ V                      ← content aggregation
  out  = Σ_h W_O^h · head_h(Q,K,V)    ← multi-head combination

With ontology governance:

  ┌──────────────────────────────────────────────────┐
  │ C1. Head Governance                              │
  │                                                  │
  │   head_gate = σ(W_head @ mean_ont)  ∈ [0,1]^H   │
  │   out = Σ_h  head_gate[h] · W_O^h · head_h      │
  │                                                  │
  │   The ontology decides which attention heads      │
  │   are structurally relevant. Some heads           │
  │   specialize in positional structure (low         │
  │   entropy), others in content (high entropy).     │
  │   The ontology selectively activates heads        │
  │   based on the categorical context.               │
  │                                                  │
  │   Input: mean(ont_features) over sequence         │
  │   Output: per-head scalar gate                    │
  │   What it controls: which COMPUTATIONS happen     │
  │   What it doesn't touch: Q, K, V content          │
  └──────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────┐
  │ C2. Value-Subspace Governance                    │
  │                                                  │
  │   For each head h:                               │
  │     V_h = h @ W_V^h                              │
  │     proj = U_k^T @ V_h              [k per token]│
  │     gate = σ(W_v @ ont_per_token)   [k per token]│
  │     V_governed = V_h - U_k@proj + U_k@(gate⊙proj)│
  │     head_h = attn @ V_governed                   │
  │                                                  │
  │   The ontology decides which STRUCTURAL           │
  │   components of V flow through. Content outside   │
  │   the structural subspace (V_⊥) passes unchanged.│
  │                                                  │
  │   Input: per-token ont_features                   │
  │   Output: per-token, per-subspace-dim gate        │
  │   What it controls: which V INFORMATION flows     │
  │   What it doesn't touch: attention routing (Q·K)  │
  └──────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────┐
  │ C3. Attention Prior (structural routing bias)    │
  │                                                  │
  │   ont_bias[i,j] = W_bias @ (ont[i] ⊕ ont[j])    │
  │   attn = softmax(Q K^T / √d  +  ont_bias)       │
  │                                                  │
  │   The ontology provides a PRIOR on which tokens   │
  │   should attend to which, based on their          │
  │   ontological relationship. Example:              │
  │     animate-agent → inanimate-patient: bias +0.5  │
  │     modifier → head-noun: bias +0.3               │
  │     unrelated pair: bias 0.0                      │
  │                                                  │
  │   Input: pairwise ont_features (⊕ = concat)       │
  │   Output: scalar attention bias per (i,j) pair    │
  │   What it controls: HOW attention routes           │
  │   What it doesn't touch: Q, K, V content          │
  └──────────────────────────────────────────────────┘
```

### The three-entity separation

```
  CONTENT PLANE (K, V)          GOVERNANCE PLANE (Ontology)
  ────────────────────          ─────────────────────────────
  "The professor taught         "animate-agent(professor),
   the student in the            animate-patient(student),
   library"                      location(library),
                                 action(taught)"
       │                              │
       │ K: what tokens contain       │ no content injection
       │ V: what tokens provide       │ only gates/biases
       │ Q: what tokens seek          │
       │                              │
       └──────────┬───────────────────┘
                  │
                  ▼
          ATTENTION MECHANISM
          (Q·K routing + V aggregation)
          governed by ontology gates

  Key invariant: removing the ontology returns the model
  to its original behavior (gates → 1.0, biases → 0.0).
  The ontology is purely subtractive/modulatory — it never
  adds information that wasn't already in the model.
```

### Why this matters

1. **K/V are learned end-to-end** from data. They encode whatever the model found useful. They are opaque.
2. **The ontology is externally defined** from linguistic knowledge. It encodes categorical structure that humans understand. It is interpretable.
3. **Governance means the ontology controls process, not content.** It decides which attention heads activate (C1), which structural V-components flow (C2), and which tokens should attend to which (C3). It never modifies the actual representations.

This separation ensures:
- The model's content computation is preserved (no representation damage)
- The ontology's effect is interpretable (each gate/bias has a categorical meaning)
- The governance is reversible (set gates=1, biases=0 → original model)
- The ontology can't hallucinate (it has no content to inject)

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
  │  7c. Simulate ontology governance               │
  │      ├── C1: Head-level gating (which heads)   │
  │      ├── C2: V-subspace gating (which info)    │
  │      ├── C3: Attention prior (which routing)   │
  │      ├── Measure perplexity impact per surface │
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

    # 7c: Governance simulation (three surfaces)
    # C1: Head-level gating
    c1_entropy_delta: float = 0.0       # attention entropy change from head gating
    c1_perplexity_ratio: float = 0.0    # PPL with head gating / PPL original
    c1_heads_suppressed: int = 0        # heads with gate < 0.1

    # C2: Value-subspace gating
    c2_gate_sparsity: float = 0.0       # fraction of V-subspace gates < 0.1
    c2_perplexity_ratio: float = 0.0    # PPL with V gating / PPL original
    c2_role_preservation: float = 0.0   # role accuracy from gated V / original

    # C3: Attention prior
    c3_attention_mi: float = 0.0        # MI between ont_bias and actual attention
    c3_perplexity_ratio: float = 0.0    # PPL with attention prior / PPL original

    # Combined
    combined_perplexity_ratio: float = 0.0  # PPL all surfaces / PPL original
    combined_entropy_delta: float = 0.0     # entropy change with all surfaces

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

### 4c. Simulate Ontology Governance

**Goal**: Test whether ontology-derived governance signals can modulate model computation — controlling *which pathways activate* and *what information flows* — without injecting content or destroying fluency.

**Key constraint**: The ontology never modifies Q, K, or V content. It only gates, biases, or scales the *mechanism*. Setting all gates to 1.0 and biases to 0.0 recovers the original model exactly.

#### Governance Surface C1: Head-Level Gating

Which attention heads should fire given the structural context?

```python
class HeadGovernor:
    """Gates attention heads based on sequence-level ontology features."""

    def __init__(self, ont_dim: int, n_heads: int):
        # Tiny linear map: mean(ont) → per-head gate
        self.W_head = nn.Linear(ont_dim, n_heads)  # ~F*H ≈ 51*12 = 612 params

    def forward(
        self,
        head_outputs: torch.Tensor,   # [batch, seq, n_heads, d_head]
        ont_features: torch.Tensor,   # [batch, seq, F]
    ) -> torch.Tensor:
        # Sequence-level ontology signal (mean pool over positions)
        ont_seq = ont_features.mean(dim=1)             # [batch, F]
        head_gate = torch.sigmoid(self.W_head(ont_seq)) # [batch, n_heads]

        # Gate each head's output (broadcast over seq and d_head)
        # head_gate[:, None, :, None] → [batch, 1, n_heads, 1]
        gated = head_outputs * head_gate[:, None, :, None]
        return gated
```

**What this tests**: Part 1 collected per-head attention entropy. Some heads are low-entropy (structural — attend to fixed positional patterns) and others are high-entropy (contextual — attend broadly). If the ontology can selectively activate structural heads when processing structurally-complex sentences, it demonstrates governance over the model's computational routing.

**Training signal**: Attention entropy at the *next* layer should decrease (more structured) when governance is active on structurally-complex inputs, without perplexity increasing.

#### Governance Surface C2: Value-Subspace Gating

Which structural components of V are allowed to flow?

```python
class ValueSubspaceGovernor:
    """Gates structural subspace components of V per token."""

    def __init__(self, ont_dim: int, subspace_k: int):
        # Per-token gate: ont[i] → which V-subspace dims flow
        self.W_v = nn.Linear(ont_dim, subspace_k)  # ~F*k ≈ 51*16 = 816 params

    def forward(
        self,
        V: torch.Tensor,              # [batch, seq, d]
        U_k: torch.Tensor,            # [d, k] structural basis
        ont_features: torch.Tensor,   # [batch, seq, F]
    ) -> torch.Tensor:
        gate = torch.sigmoid(self.W_v(ont_features))  # [batch, seq, k]

        # Project V onto structural subspace
        proj = V @ U_k                     # [batch, seq, k]
        proj_gated = proj * gate           # [batch, seq, k]

        # Replace: keep V_⊥ unchanged, gate structural component
        V_governed = V - proj @ U_k.T + proj_gated @ U_k.T
        return V_governed
```

**What this tests**: The structural subspace U_k (validated by MDL and causal intervention) carries grammatical role information in V. If the ontology can selectively gate specific subspace dimensions — e.g., suppressing "position encoding" components while preserving "role identity" components — it demonstrates fine-grained governance over information flow.

**Key distinction from Architecture B (hidden-state mask)**: This gates V *within the attention mechanism*, not h between layers. The attention routing (Q·K) is untouched. The ontology controls what information the attention mechanism *delivers*, not what tokens *represent*.

#### Governance Surface C3: Attention Prior

Should the ontology bias which tokens attend to which?

```python
class AttentionPrior:
    """Provides structural attention bias from pairwise ontology features."""

    def __init__(self, ont_dim: int, n_heads: int):
        # Pairwise: concat(ont[i], ont[j]) → per-head bias scalar
        self.W_bias = nn.Linear(ont_dim * 2, n_heads)  # ~2F*H ≈ 1224 params

    def forward(
        self,
        ont_features: torch.Tensor,   # [batch, seq, F]
        n_heads: int,
    ) -> torch.Tensor:
        B, T, F = ont_features.shape

        # Compute pairwise ontology relationships
        ont_i = ont_features.unsqueeze(2).expand(B, T, T, F)  # [B, T, T, F]
        ont_j = ont_features.unsqueeze(1).expand(B, T, T, F)  # [B, T, T, F]
        ont_pair = torch.cat([ont_i, ont_j], dim=-1)          # [B, T, T, 2F]

        # Per-head attention bias
        bias = self.W_bias(ont_pair)    # [B, T, T, n_heads]
        bias = bias.permute(0, 3, 1, 2) # [B, n_heads, T, T]

        return bias  # added to Q·K^T / √d before softmax
```

**What this tests**: Whether ontological relationships (e.g., "animate agent should attend to inanimate patient") align with the model's learned attention patterns. This is the strongest governance claim — the ontology provides a structural *prior* on routing, and the model's content-based routing (Q·K) adjusts from that baseline.

**Note**: C3 is O(T²) in sequence length. For validation (short sequences, ~20 tokens), this is fine. For production use, sparse approximations would be needed.

#### Combined Governance Simulation

```python
def simulate_governance(
    model: nn.Module,
    store: HiddenStateStore,
    annotations: StructuralAnnotations,
    ont_features: np.ndarray,
    U_k: np.ndarray,
    target_layer: int,
    cfg: OntologyConfig,
) -> Dict[str, Any]:
    """Train and evaluate all three governance surfaces.

    Each surface is trained independently with the same objective:
    - Minimize: λ_role * L_role + λ_sparse * ||gates||_1
    - Subject to: perplexity ratio < 2.0 (hard constraint via early stopping)

    The model is FROZEN. Only governance parameters are trained.
    Total trainable parameters: ~2,700 (C1: 612, C2: 816, C3: 1,224).

    Returns dict with per-surface metrics:
        c1_head_gate_entropy_delta, c1_perplexity_ratio,
        c2_value_gate_sparsity, c2_perplexity_ratio,
        c3_attention_prior_mi, c3_perplexity_ratio,
        combined_entropy_delta, combined_perplexity_ratio.
    """
```

**Evaluation** (on held-out words, no gradient):

| Surface | Metric | Computation | GO threshold |
|---------|--------|-------------|--------------|
| C1 | Entropy delta | Attention entropy at layer+1 with/without head gating | < 0 (more structured) |
| C1 | Perplexity ratio | PPL with head gating / PPL original | < 2.0 |
| C2 | Gate sparsity | Fraction of V-subspace gates < 0.1 | > 0.3 |
| C2 | Role preservation | Role accuracy from gated V vs original V | > 0.8× original |
| C3 | Attention MI | MI between ont_bias and actual attention patterns | > 0.1 |
| C3 | Perplexity ratio | PPL with attention prior / PPL original | < 2.0 |
| All | Combined PPL ratio | PPL with all three surfaces / PPL original | < 2.0 |

**Critical constraint**: The model is frozen. Total trainable governance parameters: ~2,700 (compared to GPT-2's 124M). This ensures we're measuring alignment, not fine-tuning.

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

    # 7c: Governance simulation (three surfaces)
    gov_results = simulate_governance(
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
        # C1: Head governance
        c1_entropy_delta=gov_results["c1_entropy_delta"],
        c1_perplexity_ratio=gov_results["c1_perplexity_ratio"],
        c1_heads_suppressed=gov_results["c1_heads_suppressed"],
        # C2: Value-subspace governance
        c2_gate_sparsity=gov_results["c2_gate_sparsity"],
        c2_perplexity_ratio=gov_results["c2_perplexity_ratio"],
        c2_role_preservation=gov_results["c2_role_preservation"],
        # C3: Attention prior
        c3_attention_mi=gov_results["c3_attention_mi"],
        c3_perplexity_ratio=gov_results["c3_perplexity_ratio"],
        # Combined
        combined_perplexity_ratio=gov_results["combined_perplexity_ratio"],
        combined_entropy_delta=gov_results["combined_entropy_delta"],
        # Discriminability
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
  ┌──────────────┐   ┌────────────────────┐  ┌────────────────┐
  │  7b. Align   │   │ 7c. Governance sim │  │  7d. Discrim   │
  │              │   │                    │  │                │
  │  ont ←→ U_k  │   │  C1: head gates    │  │  ont → probe → │
  │  MI, overlap, │   │  C2: V-sub gates   │  │  accuracy      │
  │  CKA         │   │  C3: attn prior    │  │  vs H → probe  │
  │              │   │  → PPL, H(attn)    │  │                │
  └──────┬───────┘   └───────┬────────────┘  └───────┬────────┘
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
    """Apply GO/NO-GO decision criteria.

    The ontology earns GO by demonstrating:
    1. It aligns with the model's structural subspace (MI)
    2. It can govern without destroying fluency (PPL)
    3. At least one governance surface produces measurable structural effect
    4. It covers enough of the vocabulary to be useful
    """

    # --- GO conditions (ALL must hold) ---
    go_checks = [
        (result.alignment_mi > 0.3,
         f"MI = {result.alignment_mi:.3f} > 0.3"),
        (result.combined_perplexity_ratio < 2.0,
         f"Combined PPL ratio = {result.combined_perplexity_ratio:.2f} < 2.0"),
        (result.combined_entropy_delta < 0.0,
         f"Entropy delta = {result.combined_entropy_delta:.3f} < 0 (more structured)"),
        (result.coverage_ratio > 0.3,
         f"Coverage = {result.coverage_ratio:.1%} > 30%"),
    ]

    # --- Per-surface informativeness (at least ONE must show effect) ---
    surface_active = (
        result.c1_entropy_delta < -0.01              # head gating sharpens attention
        or result.c2_gate_sparsity > 0.3             # V-gating is selective
        or result.c3_attention_mi > 0.1              # attention prior is informative
    )
    go_checks.append((
        surface_active,
        f"At least one governance surface is active: "
        f"C1Δ={result.c1_entropy_delta:.3f}, "
        f"C2sp={result.c2_gate_sparsity:.2f}, "
        f"C3MI={result.c3_attention_mi:.3f}",
    ))

    # --- Hard NO-GO conditions (ANY triggers) ---
    nogo_checks = [
        (result.alignment_mi < 0.05,
         f"MI ≈ 0 ({result.alignment_mi:.4f}): ontology orthogonal to model"),
        (result.combined_perplexity_ratio > 5.0,
         f"PPL ratio = {result.combined_perplexity_ratio:.1f}: governance destroys fluency"),
        (result.coverage_ratio < 0.1,
         f"Coverage = {result.coverage_ratio:.1%}: ontology covers too few words"),
        # Any single surface catastrophically destroys fluency
        (max(result.c1_perplexity_ratio, result.c2_perplexity_ratio,
             result.c3_perplexity_ratio) > 10.0,
         "A single governance surface causes PPL > 10x: architecture mismatch"),
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

| Scenario | MI | Combined PPL | Surface active? | Coverage | Decision |
|----------|-----|-------------|-----------------|----------|----------|
| Strong alignment | > 0.3 | < 2.0 | Yes | > 30% | **GO** |
| Weak alignment | 0.05–0.3 | < 2.0 | Yes | > 30% | INVESTIGATE |
| Aligned but inert | > 0.3 | < 2.0 | No | > 30% | INVESTIGATE |
| Orthogonal | < 0.05 | any | any | any | **NO-GO** |
| Destructive | any | > 5.0 | any | any | **NO-GO** |
| Low coverage | any | any | any | < 10% | **NO-GO** |
| Surface catastrophe | any | any | PPL > 10x on one | any | **NO-GO** |

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
