# Part 7: Ontology Alignment — Discovery & Validation

**Status**: Discovery phase
**Date**: 2026-02-22
**Depends on**: Parts 1–6 of causal subspace pipeline (validated)

---

## 0. Discovery Framing

We do not yet know how — or whether — an ontological layer should exist. Parts 1–6 proved that the model encodes grammatical structure in a causally load-bearing subspace. Part 7 is a **discovery process** to determine whether external ontological categories have any correspondence to this internal structure, and if so, what the natural interface looks like.

The outcome is one of four scenarios, each leading to a different architecture (or none):

```
Scenario A: Isomorphic (MI >> 0.3, CKA > 0.8)
  The model already encodes something that maps cleanly onto human
  ontological categories.  The "ontological layer" is a LENS, not
  a mechanism — it labels what the model already does.
  → Deliverable: interpretability/diagnostic tool.
  → No governance needed.

Scenario B: Partial Overlap (MI ~ 0.2–0.5, CKA ~ 0.3–0.6)
  Some ontological categories align with model structure, others
  don't.  There's a bridge, but it's partial.
  → Deliverable: governance on the aligned dimensions.
  → But we need to discover WHICH surface the overlap lives on
    before committing to an architecture.

Scenario C: Orthogonal (MI < 0.05)
  The model encodes structure in a way that has no correspondence
  to human ontological categories.  Its encoding is alien but valid.
  → Deliverable: NO-GO.  Scientifically informative (proves the model
    found structure humans didn't name).
  → No architecture will bridge this.

Scenario D: Complementary (MI low, but ont + H >> H for classification)
  The ontology captures aspects the model DOESN'T have.  It adds
  information, not policy.
  → Deliverable: content injection (Architecture A), not governance.
  → Honest admission: governance may be wrong, injection may be right.
  → This contradicts the governance principle but may be the truth.
```

**The discovery process determines which scenario we're in.  The architecture follows from the evidence, not the other way around.**

---

## 1. Motivation

Parts 1–6 established that:
- Transformer hidden states encode grammatical role information in a low-dimensional subspace (MDL compression > 1.5x)
- This subspace is causally load-bearing (12.5% causal success, 28.98x specificity over random)
- Information crystallizes at middle layers and is consumed downstream

**Part 7 asks**: Does the model's structural encoding have a natural interface to human ontological categories? If so, what is its shape? The answer determines whether an ontological layer is a lens, a governor, an injector, or nothing.

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

## 2. Two-Phase Structure

Part 7 is split into two phases. Phase 1 is cheap and determines the scenario. Phase 2 depends on Phase 1's outcome.

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: DISCOVERY  (run always, ~2 min)               │
│                                                         │
│  7a. Build ontology vectors                             │
│  7b. Compute alignment metrics (MI, CKA, overlap)       │
│  7b+. Per-head alignment breakdown                      │
│  7b+. Discriminability analysis (ont vs embeddings)      │
│                                                         │
│  Output: scenario classification (A / B / C / D)        │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┬──────────────┐
          ▼              ▼              ▼              ▼
      Scenario A     Scenario B     Scenario C     Scenario D
      Isomorphic     Partial        Orthogonal     Complementary
          │              │              │              │
          ▼              ▼              ▼              ▼
      Phase 2A:      Phase 2B:      STOP.          Phase 2D:
      Build lens     Governance     Report          Test content
      (labeling      probe          findings.       injection
       tool)         (test C1/C2/                   (Architecture A)
                      C3 surfaces)
```

### Phase 1 inputs (from existing pipeline)

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
  │  PHASE 1: Discovery (always runs)               │
  │                                                 │
  │  7a. Build ontology vectors                     │
  │      ├── WordNet hypernym depth                 │
  │      ├── Animacy / concreteness features        │
  │      └── Dependency-derived role prototypes     │
  │                                                 │
  │  7b. Alignment measurement                      │
  │      ├── MI(ontology, subspace projection)      │
  │      ├── CKA(ontology features, model H)        │
  │      ├── Per-head alignment breakdown           │
  │      └── Subspace angle overlap                 │
  │                                                 │
  │  7c. Discriminability analysis                   │
  │      ├── Classify roles from ontology features  │
  │      ├── Classify roles from model embeddings   │
  │      ├── Classify roles from ont + H (concat)   │
  │      └── Bootstrap confidence intervals         │
  │                                                 │
  │  → SCENARIO CLASSIFICATION (A / B / C / D)      │
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
class DiscoveryResult:
    """Output of Phase 1: discovery.  Determines which scenario we're in."""

    layer_idx: int

    # 7a: Ontology vectors
    ontology_dim: int = 0               # dimensionality of ontology feature space
    n_words_with_ontology: int = 0      # coverage (words with valid ontology vectors)
    coverage_ratio: float = 0.0         # n_words_with_ontology / total_words

    # 7b: Alignment metrics (global)
    alignment_mi: float = 0.0           # mutual information (nats)
    alignment_mi_normalized: float = 0.0 # MI / min(H(X), H(Y))
    subspace_overlap: float = 0.0       # principal angle cosine (0=orthogonal, 1=aligned)
    cka_similarity: float = 0.0         # centered kernel alignment

    # 7b+: Per-head alignment breakdown
    per_head_mi: List[float] = field(default_factory=list)  # [n_heads] MI per head
    structural_heads: List[int] = field(default_factory=list)  # head indices with MI > threshold

    # 7c: Discriminability
    ontology_role_accuracy: float = 0.0 # classify roles from ontology features alone
    embedding_role_accuracy: float = 0.0 # classify roles from model embeddings alone
    concat_role_accuracy: float = 0.0   # classify roles from [ont; H] concatenated
    discriminability_gap: float = 0.0   # concat_acc - embedding_acc (does ontology ADD info?)
    accuracy_ci_low: float = 0.0        # bootstrap CI lower
    accuracy_ci_high: float = 0.0       # bootstrap CI upper

    # Scenario classification
    scenario: str = ""                  # "A", "B", "C", or "D"
    scenario_confidence: float = 0.0    # how clearly we fall into one scenario
    scenario_evidence: List[str] = field(default_factory=list)  # human-readable reasoning

    # What to do next
    recommended_phase2: str = ""        # "lens", "governance_probe", "stop", "injection_test"
```

---

## 3b. Space-Transfer Gap: Why the Subspace Validation Is Necessary but Not Sufficient

### The problem

Parts 3–5 validated U_k in **h-space** (block or attention sublayer output):

```
h_out = h_in + W_O @ concat(softmax(Q_h K_h^T / √d) @ V_h) + MLP(...)
                                                        ↑
U_k was derived from PCA on this h_out ─────────────────┘
```

But the three governance surfaces operate in different spaces:

```
C1 operates on: per-head outputs  head_h = attn_h @ V_h
C2 operates on: V_h = LN(h_in) @ W_V^h
C3 operates on: attention logits  Q_h @ K_h^T
```

None of these are h_out. The validated structural directions U_k live in h_out-space and do **not** transfer directly to V-space or per-head space.

### Why applying U_k to V is wrong

```
Claim in the design:    V_governed = V - (V @ U_k) @ U_k^T + (V @ U_k ⊙ gate) @ U_k^T
What this actually does: projects V onto h-space directions, which W_V may have rotated

If W_V is an arbitrary rotation:
  structural_directions_in_V = W_V^{-T} @ U_k    (NOT U_k itself)
  V @ U_k ≠ "structural components of V"
  V @ U_k = "whatever V happens to overlap with h-space structural directions"
```

### What the subspace validation DOES give us

| What we know | From which part | How it helps governance |
|-------------|----------------|----------------------|
| Structural info exists at layer L | Part 4 (MDL) | **Layer selection**: apply governance at crystallization layer |
| Dimensionality is k | Part 4 (MDL top-k) | **Budget**: governance has k degrees of freedom |
| The subspace is causally load-bearing | Part 5 (intervention) | **Existence proof**: there IS something to govern |
| Information crystallizes then is consumed | Part 6 (trajectory) | **Timing**: governance should act at peak, not after consumption |
| Per-head entropy varies | Part 1 (attention entropy) | **Head heterogeneity**: some heads are structural candidates |

### What we still need: the Space-Transfer Step

Before governance can operate, we need to derive structural bases in each surface's native space:

```python
def derive_governance_bases(
    model: nn.Module,
    store: HiddenStateStore,
    annotations: StructuralAnnotations,
    target_layer: int,
    k: int,
) -> Dict[str, Any]:
    """Derive structural bases in each governance surface's native space.

    This bridges the gap between the h-space validation (Parts 3-5)
    and the governance surfaces (C1, C2, C3).

    Returns
    -------
    bases : dict with keys:
        'per_head_structural_score' : np.ndarray [n_heads]
            MDL compression ratio per head — which heads carry structural info.
            Derived by running MDL probe on per-head outputs separately.

        'V_basis_per_head' : Dict[int, np.ndarray]  head_idx → [d_v, k_v]
            Structural subspace in V-space for each structurally-relevant head.
            Derived by PCA on V_h = LN(h_in) @ W_V^h, validated by MDL.

        'attention_structural_patterns' : np.ndarray [n_heads, T, T]
            Average attention pattern for structurally-complex inputs.
            Baseline for C3 attention prior.
    """
```

**Per-head structural decomposition** (for C1):
1. For each head h, extract its individual output: `head_h_out = attn_h @ V_h` → [N, d_head]
2. Run MDL probe on `head_h_out` with `labels_role`
3. Heads with compression > 1.2x are "structural heads"
4. C1 uses this to set informed initial gate values

**V-space basis derivation** (for C2):
1. Extract `V_h = LN(h_in) @ W_V^h` for the target layer's structural heads
2. Run PCA on V_h → get V-space components
3. Run MDL probe on V_h projected onto top-k V-components
4. The validated V-components become C2's gating basis (replacing U_k)

**Attention pattern baseline** (for C3):
1. Compute mean attention patterns for sentences with clear structural roles
2. Compute mean attention patterns for structurally ambiguous sentences
3. The difference is the "structural attention template" that C3's prior should approximate

### Updated data flow with space-transfer

```
Parts 1-6 outputs
    │
    ├── U_k [d, k] in h-space ───── proves structure exists (layer, dim, causal)
    │
    ▼
┌───────────────────────────────┐
│  SPACE-TRANSFER STEP          │
│  (new, required before 7c)    │
│                               │
│  For each head h at layer L:  │
│    1. Extract head_h output   │
│    2. MDL probe → structural? │
│    3. If yes: PCA on V_h      │
│       → U_k_V^h [d_v, k_v]   │
│                               │
│  Also:                        │
│    4. Attention pattern avg    │
│       → structural template   │
└───────────────┬───────────────┘
                │
    ┌───────────┼───────────────┐
    ▼           ▼               ▼
   C1          C2              C3
  (uses       (uses            (uses
  per-head    U_k_V^h          attn
  MDL scores) not U_k!)        template)
```

### Cost estimate for space-transfer

| Operation | Per head? | Cost |
|-----------|-----------|------|
| Extract head outputs | Yes × n_heads | ~10s (forward hooks, no backward) |
| MDL probe per head | Yes × n_heads | ~5s × 12 = 60s |
| PCA on V_h | Only structural heads | ~2s × ~4 heads = 8s |
| Attention template | Once | ~5s |
| **Total** | | **~80s** |

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
    """Gates structural subspace components of V per token.

    IMPORTANT: Uses U_k_V (V-space basis from space-transfer step),
    NOT the h-space U_k from Parts 3-5.  See §3b for why.
    """

    def __init__(self, ont_dim: int, subspace_k: int):
        # Per-token gate: ont[i] → which V-subspace dims flow
        self.W_v = nn.Linear(ont_dim, subspace_k)  # ~F*k ≈ 51*16 = 816 params

    def forward(
        self,
        V: torch.Tensor,              # [batch, seq, d_v]
        U_k_V: torch.Tensor,          # [d_v, k_v] V-SPACE structural basis
        ont_features: torch.Tensor,   # [batch, seq, F]
    ) -> torch.Tensor:
        gate = torch.sigmoid(self.W_v(ont_features))  # [batch, seq, k_v]

        # Project V onto its own structural subspace (NOT h-space U_k)
        proj = V @ U_k_V                   # [batch, seq, k_v]
        proj_gated = proj * gate           # [batch, seq, k_v]

        # Replace: keep V_⊥ unchanged, gate structural component
        V_governed = V - proj @ U_k_V.T + proj_gated @ U_k_V.T
        return V_governed
```

**What this tests**: The structural subspace U_k_V (derived by running PCA + MDL on V_h = LN(h) @ W_V in the space-transfer step, §3b) carries grammatical role information *in V's native space*. If the ontology can selectively gate specific V-subspace dimensions — e.g., suppressing "position encoding" components while preserving "role identity" components — it demonstrates fine-grained governance over information flow.

**Why U_k_V and not U_k**: The h-space basis U_k was validated by Parts 3-5 on block/attention output. V lives in a different space (pre-output-projection, pre-residual). Applying U_k to V would project onto arbitrary directions. The space-transfer step (§3b) derives and validates U_k_V in V's own coordinate system.

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

## 7. Scenario Classification (Phase 1 output)

Phase 1 produces a `DiscoveryResult` with a scenario classification. This replaces the old GO/NO-GO binary with a four-way routing decision.

```python
def classify_scenario(result: DiscoveryResult) -> DiscoveryResult:
    """Classify which scenario we're in based on Phase 1 measurements.

    This is the central decision point. Everything downstream follows
    from this classification.
    """
    mi = result.alignment_mi
    cka = result.cka_similarity
    coverage = result.coverage_ratio
    ont_acc = result.ontology_role_accuracy
    emb_acc = result.embedding_role_accuracy
    concat_acc = result.concat_role_accuracy
    gap = result.discriminability_gap  # concat_acc - emb_acc

    evidence = []

    # --- Low coverage is an immediate problem ---
    if coverage < 0.1:
        result.scenario = "C"  # effectively orthogonal if we can't even compute
        evidence.append(f"Coverage too low ({coverage:.1%}): can't measure alignment")
        result.recommended_phase2 = "stop"
        result.scenario_evidence = evidence
        return result

    # --- Scenario A: Isomorphic ---
    # High MI + high CKA = model already encodes something ontology-like
    if mi > 0.5 and cka > 0.6:
        result.scenario = "A"
        evidence.append(f"MI={mi:.3f} >> 0.3 and CKA={cka:.3f} > 0.6: strong alignment")
        evidence.append("Model's structural encoding maps cleanly onto ontological categories")
        result.recommended_phase2 = "lens"
        result.scenario_confidence = min(mi / 0.5, cka / 0.6, 1.0)

    # --- Scenario C: Orthogonal ---
    # Near-zero MI = no correspondence
    elif mi < 0.05:
        result.scenario = "C"
        evidence.append(f"MI={mi:.4f} ≈ 0: ontology is orthogonal to model encoding")
        if ont_acc > 0.4:
            evidence.append(f"But ontology CAN predict roles ({ont_acc:.1%}) — "
                          "the model just doesn't use these features")
        result.recommended_phase2 = "stop"
        result.scenario_confidence = 1.0 - mi / 0.05

    # --- Scenario D: Complementary ---
    # Low MI but ontology ADDS info beyond what model has
    elif mi < 0.2 and gap > 0.05 and concat_acc > emb_acc + 0.03:
        result.scenario = "D"
        evidence.append(f"MI={mi:.3f} is low but concat accuracy ({concat_acc:.1%}) "
                      f"> embedding accuracy ({emb_acc:.1%}) by {gap:.1%}")
        evidence.append("Ontology captures information the model DOESN'T have")
        evidence.append("This suggests content injection, not governance")
        result.recommended_phase2 = "injection_test"
        result.scenario_confidence = gap / 0.1

    # --- Scenario B: Partial overlap ---
    else:
        result.scenario = "B"
        evidence.append(f"MI={mi:.3f}, CKA={cka:.3f}: partial alignment")
        if result.structural_heads:
            evidence.append(f"Structural heads: {result.structural_heads} "
                          "(MI varies across heads)")
        evidence.append("Some ontological categories align, others don't")
        result.recommended_phase2 = "governance_probe"
        result.scenario_confidence = mi / 0.5

    result.scenario_evidence = evidence
    return result
```

**Decision matrix**:

| Metrics | Scenario | Meaning | Phase 2 |
|---------|----------|---------|---------|
| MI > 0.5, CKA > 0.6 | **A: Isomorphic** | Model already "knows" the ontology | Build interpretability lens |
| MI 0.2–0.5, CKA 0.3–0.6 | **B: Partial overlap** | Some categories align | Probe governance surfaces |
| MI < 0.05 | **C: Orthogonal** | No correspondence | Stop. Report findings. |
| MI < 0.2, concat >> emb | **D: Complementary** | Ontology adds new info | Test content injection |

### What each Phase 2 looks like

**Phase 2A (Lens)**: No intervention needed. Build a mapping from subspace directions to ontological labels. Deliverable: visualization/diagnostic tool that labels what each PCA direction "means" in ontological terms.

**Phase 2B (Governance probe)**: Test C1/C2/C3 surfaces on the dimensions where alignment exists. Use the space-transfer step (§3b) to derive per-head and V-space bases. This is the only scenario where the governance architecture from §1b applies. See §4c for details.

**Phase 2C (Stop)**: Document findings. The model's structural encoding is real (Parts 3-5 proved it) but alien to human ontological categories. This is scientifically interesting — it means the model found structure humans didn't name.

**Phase 2D (Injection test)**: Test Architecture A (content injection: K_eff = K + W_ont @ ont). This contradicts the governance principle, but if the evidence points here, we should follow the evidence. If injection helps, the ontology's value is as a content source, not a policy layer.

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
