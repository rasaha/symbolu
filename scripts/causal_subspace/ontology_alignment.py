"""
Part 7 — Ontology Alignment Discovery
=======================================

Discovery-first approach to determine whether the model's structural
subspace (validated in Parts 1–6) corresponds to nameable ontological
axes, and if so, which architecture should exploit that correspondence.

Phase 1 (this module):
    7a. Define 12 proposed ontological axes
    7b. Build per-axis feature vectors from word annotations
    7c. Naming ceremony: per-axis MI with each PCA direction
    7d. Global alignment (MI, CKA, subspace overlap)
    7e. Discriminability (ont vs H vs concat)
    7f. Scenario classification (A / B / C / D)

Phase 2 (stubs only — architecture depends on Phase 1 outcome):
    Option 1: Parallel latent state meta-controller
    Option 2: Q/K dimension gating
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AXIS_NAMES: List[str] = [
    "abstraction_level",     # 0: WordNet hypernym depth
    "concreteness",          # 1: Brysbaert norms or POS heuristic
    "animacy",               # 2: WordNet hypernym chain → organism
    "agency",                # 3: dep_relation + animacy
    "temporal_anchoring",    # 4: verb tense / dep type
    "structural_depth",      # 5: dep_depth from Part 2
    "information_density",   # 6: word frequency proxy
    "relational_role",       # 7: distance to grammatical role centroids
    "modificational_load",   # 8: number of dependents (heuristic)
    "semantic_specificity",  # 9: 1/n_synsets (WordNet)
    "positional_salience",   # 10: position in sentence
    "categorical_type",      # 11: POS category compressed to scalar
]

N_AXES = len(AXIS_NAMES)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class OntologyConfig:
    """Configuration for ontology alignment discovery."""

    # Naming ceremony
    mi_n_bins: int = 20              # bins for MI estimation
    naming_mi_threshold: float = 0.1  # axis survives if max MI > this

    # Alignment metrics
    cka_kernel: str = "linear"        # "linear" or "rbf"

    # Discriminability
    n_bootstrap: int = 200
    bootstrap_ci: float = 0.95

    device: str = "cpu"
    seed: int = 42


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryResult:
    """Output of Phase 1: discovery. Determines which scenario we're in."""

    layer_idx: int

    # 7b: Ontology vectors
    ontology_dim: int = N_AXES
    n_words_with_ontology: int = 0
    coverage_ratio: float = 0.0

    # 7c: Naming ceremony (per-axis MI with PCA directions)
    per_axis_mi: Dict[str, float] = field(default_factory=dict)
    per_axis_best_pca: Dict[str, int] = field(default_factory=dict)
    n_validated_axes: int = 0
    validated_axes: List[str] = field(default_factory=list)

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
    scenario_evidence: List[str] = field(default_factory=list)
    recommended_phase2: str = ""


@dataclass
class MultiLayerDiscoveryResult:
    """Discovery results across multiple layers.

    Structure can peak at one layer (crystallization) while causal effect
    peaks at another. The ontological layer may need to READ from one
    layer and ACT at another. This dataclass captures that dissociation.
    """

    # Per-layer results
    per_layer: Dict[int, DiscoveryResult] = field(default_factory=dict)

    # Which layer is best for what
    best_alignment_layer: int = -1       # highest MI — where to READ ontology
    best_causal_layer: int = -1          # highest causal effect — where to ACT
    dissociation: bool = False           # True if read_layer != act_layer

    # Merged scenario (from best alignment layer)
    scenario: str = ""
    scenario_evidence: List[str] = field(default_factory=list)
    recommended_phase2: str = ""

    # Architecture routing based on dissociation
    meta_controller_read_layer: int = -1   # Option 1 reads from here
    meta_controller_act_layer: int = -1    # Option 1 governs here
    qk_gating_layer: int = -1             # Option 2 operates here

    # Merged validated axes (union across layers)
    all_validated_axes: List[str] = field(default_factory=list)
    n_validated_axes: int = 0


# ---------------------------------------------------------------------------
# 7b. Build 12-axis ontology vectors
# ---------------------------------------------------------------------------

def _try_wordnet_features(word: str) -> Tuple[float, float, float]:
    """Try to get WordNet-based features for a word.

    Returns (hypernym_depth_normalized, animacy, semantic_specificity).
    All NaN if WordNet unavailable or word not found.
    """
    try:
        from nltk.corpus import wordnet as wn
    except ImportError:
        return (float("nan"), float("nan"), float("nan"))

    synsets = wn.synsets(word.lower())
    if not synsets:
        return (float("nan"), float("nan"), float("nan"))

    # Use most common synset (first)
    ss = synsets[0]

    # Hypernym depth (normalized by max ~20)
    depth = ss.min_depth()
    depth_norm = min(depth / 20.0, 1.0)

    # Animacy: check if hypernym chain contains 'organism'
    animacy = 0.0
    hypernym_paths = ss.hypernym_paths()
    for path in hypernym_paths:
        for ancestor in path:
            if "organism" in ancestor.name() or "animal" in ancestor.name():
                animacy = 1.0
                break
        if animacy > 0:
            break

    # Semantic specificity: fewer synsets = more specific
    n_synsets = len(synsets)
    specificity = 1.0 / n_synsets

    return (depth_norm, animacy, specificity)


def _concreteness_heuristic(dep_relation: str, pos_guess: str) -> float:
    """Heuristic concreteness based on dependency relation and POS.

    Nouns are more concrete than verbs, which are more concrete
    than function words. Returns [0, 1].
    """
    if dep_relation in ("nsubj", "nsubjpass", "dobj", "iobj", "obj", "pobj"):
        return 0.7  # core arguments tend to be concrete
    if dep_relation in ("ROOT", "root"):
        return 0.4  # verbs: medium
    if dep_relation in ("amod", "nummod"):
        return 0.6  # modifiers: somewhat concrete
    if dep_relation in ("det", "aux", "mark", "cc", "punct", "case"):
        return 0.2  # function words: abstract
    return 0.5  # default


def _agency_score(dep_relation: str, animacy: float) -> float:
    """Agency = subject AND animate. Graded score."""
    is_subject = dep_relation in ("nsubj", "nsubjpass", "csubj")
    if is_subject and animacy > 0.5:
        return 1.0
    if is_subject:
        return 0.5  # inanimate subject — lower agency
    if animacy > 0.5:
        return 0.3  # animate but not subject
    return 0.0


def _temporal_anchoring(dep_relation: str) -> float:
    """Temporal anchoring: verbs get higher scores."""
    if dep_relation in ("ROOT", "root"):
        return 0.7  # main verb
    if dep_relation in ("aux", "auxpass"):
        return 0.5  # auxiliary verb
    if dep_relation in ("advcl", "xcomp", "ccomp"):
        return 0.6  # clausal complement
    return 0.0  # non-verbal


def _categorical_type(dep_relation: str) -> float:
    """Compress POS-like info to a single scalar.

    noun-like=0.0, verb-like=0.33, adj/adv-like=0.67, function=1.0
    """
    noun_deps = {"nsubj", "nsubjpass", "dobj", "iobj", "obj", "pobj", "nmod"}
    verb_deps = {"ROOT", "root", "aux", "auxpass", "xcomp", "ccomp", "advcl"}
    mod_deps = {"amod", "advmod", "nummod"}

    if dep_relation in noun_deps:
        return 0.0
    if dep_relation in verb_deps:
        return 0.33
    if dep_relation in mod_deps:
        return 0.67
    return 1.0


def build_ontology_vectors(
    words: list,
    H: np.ndarray,
    labels: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build 12-axis ontology feature vectors for annotated words.

    Parameters
    ----------
    words : list of WordAnnotation
        Word annotations from Part 2.
    H : np.ndarray [N_w, d]
        Hidden states at the target layer.
    labels : np.ndarray [N_w]
        Grammatical role labels.

    Returns
    -------
    ont_features : np.ndarray [N_w, 12]
        Ontology feature vectors. NaN for unavailable axes.
    valid_mask : np.ndarray [N_w] bool
        True where ≥ 8 of 12 axes have values.
    """
    N = len(words)
    ont = np.full((N, N_AXES), np.nan, dtype=np.float32)

    # Pre-compute role centroids for axis 7 (relational_role)
    unique_labels = np.unique(labels)
    centroids = {}
    for lbl in unique_labels:
        mask = labels == lbl
        if mask.sum() > 0:
            centroids[lbl] = H[mask].mean(axis=0)

    # Normalize H for distance computation
    H_norms = np.linalg.norm(H, axis=1, keepdims=True)
    H_norms = np.maximum(H_norms, 1e-8)

    # Max sentence length for normalization
    max_pos = max((w.position_in_sentence for w in words), default=1)
    max_pos = max(max_pos, 1)

    # Max depth for normalization
    max_depth = max((w.dep_depth for w in words), default=1)
    max_depth = max(max_depth, 1)

    for i, w in enumerate(words):
        dep = w.dep_relation

        # WordNet-based axes (may be NaN)
        wn_depth, wn_animacy, wn_specificity = _try_wordnet_features(w.word)
        ont[i, 0] = wn_depth               # abstraction_level
        ont[i, 9] = wn_specificity          # semantic_specificity

        # Concreteness (heuristic fallback if no norms)
        if not np.isnan(wn_depth):
            # More specific (deeper) = more concrete, roughly
            ont[i, 1] = wn_depth
        else:
            ont[i, 1] = _concreteness_heuristic(dep, "")

        # Animacy
        if not np.isnan(wn_animacy):
            ont[i, 2] = wn_animacy
        else:
            # Heuristic: subjects of action verbs are more likely animate
            ont[i, 2] = 0.5 if dep in ("nsubj",) else 0.0

        # Agency (depends on animacy)
        animacy_val = ont[i, 2] if not np.isnan(ont[i, 2]) else 0.0
        ont[i, 3] = _agency_score(dep, animacy_val)

        # Temporal anchoring
        ont[i, 4] = _temporal_anchoring(dep)

        # Structural depth (always available from Part 2)
        ont[i, 5] = w.dep_depth / max_depth

        # Information density (proxy: position-based, later words are rarer)
        # Real implementation would use word frequency. This is a placeholder.
        ont[i, 6] = min(w.position_in_sentence / max(max_pos, 1), 1.0)

        # Relational role (distance to centroids)
        if centroids:
            dists = []
            for lbl in sorted(centroids.keys()):
                d = np.linalg.norm(H[i] - centroids[lbl])
                dists.append(d)
            if dists:
                max_d = max(dists) if max(dists) > 0 else 1.0
                # Normalized: closer to own centroid = higher score
                own_label = labels[i]
                if own_label in centroids:
                    own_dist = np.linalg.norm(H[i] - centroids[own_label])
                    ont[i, 7] = 1.0 - (own_dist / max_d)
                else:
                    ont[i, 7] = 0.5

        # Modificational load (heuristic: modifiers get lower, heads get higher)
        if dep in ("ROOT", "root"):
            ont[i, 8] = 1.0
        elif dep in ("nsubj", "dobj", "obj"):
            ont[i, 8] = 0.6
        elif dep in ("amod", "advmod", "nummod", "det"):
            ont[i, 8] = 0.2
        else:
            ont[i, 8] = 0.4

        # Positional salience
        ont[i, 10] = w.position_in_sentence / max(max_pos, 1)

        # Categorical type
        ont[i, 11] = _categorical_type(dep)

    # Valid mask: word has ≥ 8 non-NaN axes
    valid_count = np.sum(~np.isnan(ont), axis=1)
    valid_mask = valid_count >= 8

    # Replace remaining NaNs with 0.5 (neutral) for valid words
    ont_clean = ont.copy()
    nan_mask = np.isnan(ont_clean)
    ont_clean[nan_mask] = 0.5

    logger.info(
        "Ontology vectors: %d/%d words valid (%.1f%%), %d axes",
        valid_mask.sum(), N, valid_mask.mean() * 100, N_AXES,
    )

    return ont_clean, valid_mask


# ---------------------------------------------------------------------------
# 7c. Naming Ceremony
# ---------------------------------------------------------------------------

def _compute_binned_mi(x: np.ndarray, y: np.ndarray, n_bins: int = 20) -> float:
    """Compute mutual information between two 1-D arrays using binning.

    Uses histogram-based estimation with bias correction. Returns MI in nats.
    The number of bins is capped at sqrt(N) to reduce finite-sample bias.
    """
    N = len(x)
    if N < 10:
        return 0.0

    # Handle constant arrays
    if x.std() < 1e-10 or y.std() < 1e-10:
        return 0.0

    # Cap bins at sqrt(N) to reduce upward bias from sparse joint table
    effective_bins = min(n_bins, max(int(math.sqrt(N)), 3))

    # Bin both variables
    x_bins = np.digitize(x, np.linspace(x.min() - 1e-10, x.max() + 1e-10, effective_bins + 1))
    y_bins = np.digitize(y, np.linspace(y.min() - 1e-10, y.max() + 1e-10, effective_bins + 1))

    # Joint histogram
    joint = np.zeros((effective_bins + 2, effective_bins + 2), dtype=np.float64)
    for xi, yi in zip(x_bins, y_bins):
        joint[xi, yi] += 1
    joint /= N

    # Marginals
    px = joint.sum(axis=1)
    py = joint.sum(axis=0)

    # MI = sum p(x,y) * log(p(x,y) / (p(x)*p(y)))
    mi = 0.0
    for i in range(joint.shape[0]):
        for j in range(joint.shape[1]):
            if joint[i, j] > 0 and px[i] > 0 and py[j] > 0:
                mi += joint[i, j] * math.log(joint[i, j] / (px[i] * py[j]))

    # Bias correction: subtract expected MI under independence
    # For uniform marginals, E[MI] ≈ (B-1)^2 / (2*N*ln(2)) (in nats: divide by ln(2))
    # This is a rough correction; exact correction depends on marginals.
    n_nonempty_x = int((px > 0).sum())
    n_nonempty_y = int((py > 0).sum())
    bias = (n_nonempty_x - 1) * (n_nonempty_y - 1) / (2.0 * N)
    mi_corrected = max(mi - bias, 0.0)

    return mi_corrected


def run_naming_ceremony(
    ont_features: np.ndarray,
    H_proj: np.ndarray,
    n_bins: int = 20,
    threshold: float = 0.1,
) -> Tuple[Dict[str, float], Dict[str, int], List[str]]:
    """For each of the 12 axes, compute MI with each PCA direction.

    Parameters
    ----------
    ont_features : np.ndarray [N, 12]
        Ontology features (12 axes).
    H_proj : np.ndarray [N, k]
        Hidden states projected onto PCA basis.
    n_bins : int
        Bins for MI estimation.
    threshold : float
        Axis survives if max MI > threshold.

    Returns
    -------
    per_axis_mi : dict
        axis_name → max MI with any PCA direction
    per_axis_best_pca : dict
        axis_name → which PCA direction it best maps to
    validated_axes : list
        Names of axes that passed the threshold
    """
    n_axes = ont_features.shape[1]
    k = H_proj.shape[1]

    per_axis_mi: Dict[str, float] = {}
    per_axis_best_pca: Dict[str, int] = {}

    for ax_idx in range(min(n_axes, len(AXIS_NAMES))):
        ax_name = AXIS_NAMES[ax_idx]
        ax_values = ont_features[:, ax_idx]

        best_mi = 0.0
        best_dir = 0
        for pca_dir in range(k):
            mi = _compute_binned_mi(ax_values, H_proj[:, pca_dir], n_bins)
            if mi > best_mi:
                best_mi = mi
                best_dir = pca_dir

        per_axis_mi[ax_name] = best_mi
        per_axis_best_pca[ax_name] = best_dir

    validated = [name for name, mi in per_axis_mi.items() if mi > threshold]

    logger.info(
        "Naming ceremony: %d/%d axes validated (threshold=%.2f)",
        len(validated), len(AXIS_NAMES), threshold,
    )
    for name in AXIS_NAMES:
        status = "PASS" if name in validated else "FAIL"
        mi_val = per_axis_mi.get(name, 0.0)
        pca_dir = per_axis_best_pca.get(name, -1)
        logger.info("  [%s] %s: MI=%.4f (best PCA dir=%d)", status, name, mi_val, pca_dir)

    return per_axis_mi, per_axis_best_pca, validated


# ---------------------------------------------------------------------------
# 7d. Global Alignment Metrics
# ---------------------------------------------------------------------------

def compute_alignment_mi(
    ont_features: np.ndarray,
    H_proj: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 20,
) -> Tuple[float, float]:
    """Compute MI between ontology features and subspace projections.

    Strategy: discretize first PC of each, compute MI.
    Also compute normalized MI.

    Returns (mi_raw, mi_normalized).
    """
    # Use first PC of ontology features and first PC of H_proj
    from sklearn.decomposition import PCA

    if ont_features.shape[0] < 10 or H_proj.shape[0] < 10:
        return 0.0, 0.0

    n_comp_ont = min(3, ont_features.shape[1], ont_features.shape[0])
    n_comp_h = min(3, H_proj.shape[1], H_proj.shape[0])

    pca_ont = PCA(n_components=n_comp_ont)
    pca_h = PCA(n_components=n_comp_h)

    ont_pc = pca_ont.fit_transform(ont_features)
    h_pc = pca_h.fit_transform(H_proj)

    # Compute MI between each pair of PCs, take max
    best_mi = 0.0
    for i in range(ont_pc.shape[1]):
        for j in range(h_pc.shape[1]):
            mi = _compute_binned_mi(ont_pc[:, i], h_pc[:, j], n_bins)
            best_mi = max(best_mi, mi)

    # Normalize by entropy
    # H(X) for discrete bins ≈ log(n_bins) at maximum
    h_x = math.log(max(n_bins, 2))
    mi_norm = best_mi / h_x if h_x > 0 else 0.0

    return best_mi, mi_norm


def compute_subspace_overlap(
    ont_features: np.ndarray,
    U_k: np.ndarray,
    H: np.ndarray,
) -> float:
    """Compute principal angle overlap between ontology and model subspaces.

    Returns value in [0, 1]: 0 = orthogonal, 1 = aligned.

    Uses vectorized correlation matrix instead of per-pair pearsonr loops.
    """
    from sklearn.decomposition import PCA

    N = ont_features.shape[0]
    if N < 10:
        return 0.0

    k = U_k.shape[1]

    # PCA on ontology features
    k_ont = min(k, ont_features.shape[1], N - 1)
    if k_ont < 1:
        return 0.0

    pca_ont = PCA(n_components=k_ont)
    ont_proj = pca_ont.fit_transform(ont_features)  # [N, k_ont]

    # Project H onto structural subspace
    H_proj = H @ U_k  # [N, k]

    # Vectorized correlation: corrcoef on the concatenated columns
    n_pairs = min(ont_proj.shape[1], H_proj.shape[1])
    if N <= 2 or n_pairs < 1:
        return 0.0

    # Standardize columns
    ont_std = (ont_proj - ont_proj.mean(axis=0)) / (ont_proj.std(axis=0, ddof=1) + 1e-10)
    h_std = (H_proj - H_proj.mean(axis=0)) / (H_proj.std(axis=0, ddof=1) + 1e-10)

    # Cross-correlation matrix: [k_ont, k] — all correlations at once
    corr_matrix = np.abs(ont_std.T @ h_std) / (N - 1)  # [k_ont, k]

    # Top-k correlations (principal angle proxies)
    all_corrs = corr_matrix.ravel()
    all_corrs.sort()
    top_k = all_corrs[-n_pairs:]
    return float(np.mean(top_k))


def compute_cka(
    X: np.ndarray,
    Y: np.ndarray,
    kernel: str = "linear",
) -> float:
    """Centered Kernel Alignment between two representation matrices.

    CKA in [0, 1]: 1 = identical representational structure.

    Uses the efficient Frobenius-norm formulation for linear CKA:
        trace(K_X @ K_Y) = ||X^T @ Y||_F^2
    which avoids materializing the N×N kernel matrices (O(N*d^2) vs O(N^3)).
    """
    N = X.shape[0]
    if N < 3:
        return 0.0

    # Center
    X = X - X.mean(axis=0, keepdims=True)
    Y = Y - Y.mean(axis=0, keepdims=True)

    if kernel == "linear":
        # Efficient formulation: trace(K_X K_Y) = ||X^T Y||_F^2
        # where K_X = X X^T, K_Y = Y Y^T
        # This is O(N * d_x * d_y) instead of O(N^2 * d + N^3)
        M_xy = X.T @ Y   # [d_x, d_y]
        M_xx = X.T @ X   # [d_x, d_x]
        M_yy = Y.T @ Y   # [d_y, d_y]

        hsic_xy = float(np.sum(M_xy ** 2)) / ((N - 1) ** 2)
        hsic_xx = float(np.sum(M_xx ** 2)) / ((N - 1) ** 2)
        hsic_yy = float(np.sum(M_yy ** 2)) / ((N - 1) ** 2)

        denom = math.sqrt(hsic_xx * hsic_yy)
        if denom < 1e-10:
            return 0.0

        return float(hsic_xy / denom)

    return 0.0  # Only linear kernel implemented


# ---------------------------------------------------------------------------
# 7e. Discriminability Analysis
# ---------------------------------------------------------------------------

def measure_discriminability(
    ont_features: np.ndarray,
    H: np.ndarray,
    labels: np.ndarray,
    n_bootstrap: int = 200,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict[str, float]:
    """Compare role classification: ontology features vs model embeddings.

    Uses a single stratified train/test split with SGDClassifier (linear SVM)
    for speed.  The discriminability gap only needs to determine whether the
    ontology adds information beyond the model embeddings — a single split
    on a subsample is more than adequate for that go/no-go decision.

    Returns dict with accuracies and approximate CI.
    """
    from sklearn.linear_model import SGDClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score

    rng = np.random.RandomState(seed)
    n_classes = len(np.unique(labels))

    if len(labels) < 20 or n_classes < 2:
        return {
            "ontology_accuracy": 0.0,
            "embedding_accuracy": 0.0,
            "concat_accuracy": 0.0,
            "gap": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
        }

    N = len(labels)
    logger.info("  7e: N=%d samples, %d classes, subsampling...", N, n_classes)

    # Subsample aggressively — 2000 samples is plenty for a linear probe
    MAX_SAMPLES = 2000
    if N > MAX_SAMPLES:
        idx_sub = rng.choice(N, size=MAX_SAMPLES, replace=False)
        ont_features = ont_features[idx_sub]
        H = H[idx_sub]
        labels = labels[idx_sub]
        N = MAX_SAMPLES
        logger.info("  7e: Subsampled to %d", N)

    # Concatenated features
    concat = np.hstack([ont_features, H])

    def _split_accuracy(X, y, name=""):
        """Single train/test split accuracy with SGDClassifier."""
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=seed, stratify=y,
        )
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_tr)
        X_te = scaler.transform(X_te)
        clf = SGDClassifier(
            loss="hinge", max_iter=200, tol=1e-3, random_state=seed,
        )
        clf.fit(X_tr, y_tr)
        acc = accuracy_score(y_te, clf.predict(X_te))
        logger.info("  7e: %s accuracy = %.1f%%", name, acc * 100)
        return float(acc)

    ont_acc = _split_accuracy(ont_features, labels, "ontology")
    emb_acc = _split_accuracy(H, labels, "embedding")
    concat_acc = _split_accuracy(concat, labels, "concat")
    gap = concat_acc - emb_acc

    # Quick bootstrap CI on the gap — 10 resampled splits, no CV
    logger.info("  7e: Running %d bootstrap resamples for CI...", 10)
    gaps = []
    for i in range(10):
        idx = rng.choice(N, size=N, replace=True)
        b_emb = _split_accuracy(H[idx], labels[idx], f"boot{i+1}-emb")
        b_concat = _split_accuracy(concat[idx], labels[idx], f"boot{i+1}-cat")
        gaps.append(b_concat - b_emb)

    alpha = (1 - ci) / 2
    ci_low = float(np.percentile(gaps, alpha * 100))
    ci_high = float(np.percentile(gaps, (1 - alpha) * 100))

    logger.info(
        "Discriminability: ont=%.1f%%, emb=%.1f%%, concat=%.1f%%, gap=%.1f%% [%.1f%%, %.1f%%]",
        ont_acc * 100, emb_acc * 100, concat_acc * 100,
        gap * 100, ci_low * 100, ci_high * 100,
    )

    return {
        "ontology_accuracy": ont_acc,
        "embedding_accuracy": emb_acc,
        "concat_accuracy": concat_acc,
        "gap": gap,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


# ---------------------------------------------------------------------------
# 7f. Scenario Classification
# ---------------------------------------------------------------------------

def classify_scenario(result: DiscoveryResult) -> DiscoveryResult:
    """Classify which scenario we're in based on Phase 1 measurements.

    This is the central decision point. Everything downstream follows
    from this classification.
    """
    N = result.n_validated_axes
    mi = result.alignment_mi
    cka = result.cka_similarity
    coverage = result.coverage_ratio
    gap = result.discriminability_gap

    evidence: List[str] = []

    # --- Low coverage: can't measure anything ---
    if coverage < 0.1:
        result.scenario = "C"
        evidence.append(f"Coverage too low ({coverage:.1%}): can't measure alignment")
        result.recommended_phase2 = "stop"
        result.scenario_confidence = 0.0
        result.scenario_evidence = evidence
        return result

    # --- Scenario A: Isomorphic ---
    if N >= 8 and mi > 0.5 and cka > 0.6:
        result.scenario = "A"
        evidence.append(f"{N}/12 axes validated, MI={mi:.3f}, CKA={cka:.3f}")
        evidence.append("Model's structural encoding maps onto ontological categories")
        evidence.append("Both architectures (meta-controller + Q/K gating) are viable")
        result.recommended_phase2 = "build_both"
        result.scenario_confidence = min(N / 12.0, mi / 0.5, cka / 0.6, 1.0)

    # --- Scenario C: Orthogonal ---
    elif mi < 0.05 or N <= 2:
        result.scenario = "C"
        evidence.append(f"MI={mi:.4f}, validated axes={N}: no correspondence")
        if N <= 2:
            evidence.append(f"Only {N}/12 axes passed naming ceremony")
        evidence.append("Model's structural encoding is real but alien to our ontology")
        result.recommended_phase2 = "stop"
        result.scenario_confidence = max(1.0 - mi / 0.05, 1.0 - N / 3.0, 0.0)

    # --- Scenario D: Complementary ---
    elif mi < 0.2 and gap > 0.05:
        result.scenario = "D"
        evidence.append(f"MI={mi:.3f} low but discriminability gap={gap:.1%}")
        evidence.append("Ontology adds info the model doesn't have")
        evidence.append("Content injection, not governance")
        result.recommended_phase2 = "injection_test"
        result.scenario_confidence = min(gap / 0.1, 1.0)

    # --- Scenario B: Partial overlap ---
    else:
        result.scenario = "B"
        evidence.append(f"MI={mi:.3f}, CKA={cka:.3f}, {N} validated axes")
        if result.validated_axes:
            evidence.append(f"Surviving axes: {', '.join(result.validated_axes)}")
        evidence.append("Meta-controller (Option 1) on surviving axes")
        result.recommended_phase2 = "meta_controller"
        result.scenario_confidence = min(mi / 0.5, N / 8.0, 1.0)

    result.scenario_evidence = evidence
    return result


# ---------------------------------------------------------------------------
# Phase 2 Stubs
# ---------------------------------------------------------------------------

class OntologyMetaController:
    """Phase 2, Option 1: Parallel latent state meta-controller.

    NOT IMPLEMENTED — stub showing the interface.

    H[layer] → encoder → z_ont ∈ R^N → control signals

    Trained on validated axes only. N = number of axes that
    survived the naming ceremony.
    """

    def __init__(self, d_model: int, n_axes: int):
        import torch.nn as nn
        self.encoder = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Linear(64, n_axes),
            nn.Sigmoid(),
        )

    def forward(self, H):
        """H: [batch, seq, d] → [batch, N] ontological state."""
        import torch
        h_pool = H.mean(dim=1)
        return self.encoder(h_pool)


class QKDimensionGating:
    """Phase 2, Option 2: Q/K dimension gating.

    NOT IMPLEMENTED — stub showing the interface.

    gate = σ(W_gate @ ont_per_token)
    q' = q ⊙ gate
    k' = k ⊙ gate
    """

    def __init__(self, n_axes: int, d_head: int):
        import torch.nn as nn
        self.W_gate = nn.Linear(n_axes, d_head)

    def forward(self, Q, K, ont):
        """Gate Q and K based on ontological features.

        Q, K: [batch, seq, d_head]
        ont: [batch, seq, n_axes]
        Returns gated (Q', K').
        """
        import torch
        gate = torch.sigmoid(self.W_gate(ont))
        return Q * gate, K * gate


# ---------------------------------------------------------------------------
# Main discovery entry point
# ---------------------------------------------------------------------------

def run_ontology_discovery(
    annotations,
    H: np.ndarray,
    labels: np.ndarray,
    U_k: np.ndarray,
    layer_idx: int = 0,
    cfg: Optional[OntologyConfig] = None,
) -> DiscoveryResult:
    """Run the full Phase 1 ontology discovery pipeline.

    Parameters
    ----------
    annotations : StructuralAnnotations
        Word annotations from Part 2.
    H : np.ndarray [N_w, d]
        Hidden states at the crystallization layer.
    labels : np.ndarray [N_w]
        Grammatical role labels.
    U_k : np.ndarray [d, k]
        MDL-validated PCA basis from Part 4.
    layer_idx : int
        Which layer these hidden states come from.
    cfg : OntologyConfig, optional

    Returns
    -------
    DiscoveryResult with scenario classification.
    """
    if cfg is None:
        cfg = OntologyConfig()

    result = DiscoveryResult(layer_idx=layer_idx)

    import time as _time

    # 7b: Build ontology vectors
    _t = _time.time()
    logger.info("7b: Building 12-axis ontology vectors (H shape=%s)...", H.shape)
    ont_features, valid_mask = build_ontology_vectors(
        annotations.words, H, labels,
    )

    result.n_words_with_ontology = int(valid_mask.sum())
    result.coverage_ratio = float(valid_mask.mean()) if len(valid_mask) > 0 else 0.0
    logger.info("7b: Done in %.1fs — %d/%d words valid (%.0f%%)",
                _time.time() - _t, valid_mask.sum(), len(valid_mask),
                result.coverage_ratio * 100)

    # Filter to valid words
    ont_valid = ont_features[valid_mask]
    H_valid = H[valid_mask]
    labels_valid = labels[valid_mask]

    if ont_valid.shape[0] < 20:
        logger.warning("Too few valid words (%d) for alignment analysis", ont_valid.shape[0])
        result.scenario = "C"
        result.scenario_evidence = [f"Only {ont_valid.shape[0]} valid words"]
        result.recommended_phase2 = "stop"
        return result

    # Project onto structural subspace
    H_proj = H_valid @ U_k  # [N, k]
    logger.info("  Projected: H_valid %s @ U_k %s → H_proj %s",
                H_valid.shape, U_k.shape, H_proj.shape)

    # 7c: Naming ceremony
    _t = _time.time()
    logger.info("7c: Running naming ceremony...")
    per_axis_mi, per_axis_best_pca, validated = run_naming_ceremony(
        ont_valid, H_proj, cfg.mi_n_bins, cfg.naming_mi_threshold,
    )
    result.per_axis_mi = per_axis_mi
    result.per_axis_best_pca = per_axis_best_pca
    result.n_validated_axes = len(validated)
    result.validated_axes = validated
    logger.info("7c: Done in %.1fs — %d axes validated: %s",
                _time.time() - _t, len(validated), validated)

    # 7d: Global alignment
    _t = _time.time()
    logger.info("7d: Computing global alignment metrics (ont=%s, H_proj=%s)...",
                ont_valid.shape, H_proj.shape)
    mi_raw, mi_norm = compute_alignment_mi(
        ont_valid, H_proj, labels_valid, cfg.mi_n_bins,
    )
    result.alignment_mi = mi_raw
    result.alignment_mi_normalized = mi_norm
    logger.info("  7d: MI done (raw=%.4f, norm=%.4f)", mi_raw, mi_norm)
    result.subspace_overlap = compute_subspace_overlap(ont_valid, U_k, H_valid)
    logger.info("  7d: Subspace overlap done (%.4f)", result.subspace_overlap)
    result.cka_similarity = compute_cka(H_proj, ont_valid, cfg.cka_kernel)
    logger.info("7d: Done in %.1fs — MI=%.4f, overlap=%.4f, CKA=%.4f",
                _time.time() - _t, mi_raw, result.subspace_overlap,
                result.cka_similarity)

    # 7e: Discriminability
    _t = _time.time()
    logger.info("7e: Measuring discriminability (ont=%s, H=%s, %d classes)...",
                ont_valid.shape, H_valid.shape, len(np.unique(labels_valid)))
    disc = measure_discriminability(
        ont_valid, H_valid, labels_valid,
        cfg.n_bootstrap, cfg.bootstrap_ci, cfg.seed,
    )
    result.ontology_role_accuracy = disc["ontology_accuracy"]
    result.embedding_role_accuracy = disc["embedding_accuracy"]
    result.concat_role_accuracy = disc["concat_accuracy"]
    result.discriminability_gap = disc["gap"]
    result.accuracy_ci_low = disc["ci_low"]
    result.accuracy_ci_high = disc["ci_high"]
    logger.info("7e: Done in %.1fs — gap=%.1f%%", _time.time() - _t, disc["gap"] * 100)

    # 7f: Scenario classification
    logger.info("7f: Classifying scenario...")
    result = classify_scenario(result)

    logger.info(
        "Discovery complete: Scenario %s (confidence=%.2f), %d validated axes, "
        "recommended Phase 2: %s",
        result.scenario, result.scenario_confidence,
        result.n_validated_axes, result.recommended_phase2,
    )

    return result


def run_multi_layer_discovery(
    annotations,
    hidden_states: Dict[int, np.ndarray],
    labels: np.ndarray,
    U_k: np.ndarray,
    layers: List[int],
    causal_success_by_layer: Optional[Dict[int, float]] = None,
    cfg: Optional[OntologyConfig] = None,
) -> MultiLayerDiscoveryResult:
    """Run ontology discovery at multiple layers.

    The key insight from the L0/L2 dissociation: structure can peak at
    one layer (crystallization, high MDL compression) while causal effect
    peaks at another (high causal success rate). The meta-controller should
    READ from the layer with strongest ontological alignment, and ACT at
    the layer with strongest causal effect. Q/K gating operates where
    causal effect is highest (where attention routing matters most).

    Parameters
    ----------
    annotations : StructuralAnnotations
        Word annotations from Part 2.
    hidden_states : dict[int, np.ndarray]
        Per-layer hidden states, each [N_w, d].
    labels : np.ndarray [N_w]
        Grammatical role labels.
    U_k : np.ndarray [d, k]
        MDL-validated PCA basis.
    layers : list[int]
        Which layers to run discovery on. Typically
        [crystallization_layer, peak_causal_layer].
    causal_success_by_layer : dict[int, float], optional
        Causal success rate per layer from Part 5. Used to identify
        the peak causal layer. If None, falls back to alignment MI
        for layer selection.
    cfg : OntologyConfig, optional

    Returns
    -------
    MultiLayerDiscoveryResult with per-layer results and routing.
    """
    if cfg is None:
        cfg = OntologyConfig()

    multi = MultiLayerDiscoveryResult()

    # Run discovery at each layer
    for layer_idx in layers:
        if layer_idx not in hidden_states:
            logger.warning("Layer %d not in hidden_states, skipping", layer_idx)
            continue

        H = hidden_states[layer_idx]
        logger.info("=" * 60)
        logger.info("Running ontology discovery at layer %d", layer_idx)
        logger.info("=" * 60)

        result = run_ontology_discovery(
            annotations, H, labels, U_k,
            layer_idx=layer_idx, cfg=cfg,
        )
        multi.per_layer[layer_idx] = result

    if not multi.per_layer:
        logger.warning("No layers produced results")
        multi.scenario = "C"
        multi.scenario_evidence = ["No valid layers for discovery"]
        multi.recommended_phase2 = "stop"
        return multi

    # --- Find best alignment layer (highest MI) ---
    best_align = max(multi.per_layer.items(), key=lambda kv: kv[1].alignment_mi)
    multi.best_alignment_layer = best_align[0]

    # --- Find best causal layer ---
    if causal_success_by_layer:
        # Use actual causal data from Part 5
        valid_causal = {
            l: rate for l, rate in causal_success_by_layer.items()
            if l in multi.per_layer
        }
        if valid_causal:
            multi.best_causal_layer = max(valid_causal, key=valid_causal.get)
        else:
            multi.best_causal_layer = multi.best_alignment_layer
    else:
        # Fallback: use alignment MI as proxy
        multi.best_causal_layer = multi.best_alignment_layer

    # --- Detect dissociation ---
    multi.dissociation = (multi.best_alignment_layer != multi.best_causal_layer)

    # --- Architecture routing ---
    # Meta-controller: reads from alignment layer, acts at causal layer
    multi.meta_controller_read_layer = multi.best_alignment_layer
    multi.meta_controller_act_layer = multi.best_causal_layer

    # Q/K gating: operates at causal layer (where attention routing matters)
    multi.qk_gating_layer = multi.best_causal_layer

    # --- Merge validated axes (union across layers) ---
    all_axes = set()
    for result in multi.per_layer.values():
        all_axes.update(result.validated_axes)
    multi.all_validated_axes = sorted(all_axes, key=lambda a: AXIS_NAMES.index(a) if a in AXIS_NAMES else 99)
    multi.n_validated_axes = len(multi.all_validated_axes)

    # --- Use best alignment layer's scenario as the overall scenario ---
    best_result = multi.per_layer[multi.best_alignment_layer]
    multi.scenario = best_result.scenario
    multi.recommended_phase2 = best_result.recommended_phase2

    # --- Build evidence incorporating dissociation ---
    evidence = list(best_result.scenario_evidence)

    if multi.dissociation:
        align_layer = multi.best_alignment_layer
        causal_layer = multi.best_causal_layer
        align_mi = multi.per_layer[align_layer].alignment_mi
        causal_mi = multi.per_layer[causal_layer].alignment_mi if causal_layer in multi.per_layer else 0.0

        evidence.append(
            f"DISSOCIATION: structure peaks at L{align_layer} (MI={align_mi:.3f}) "
            f"but causal effect peaks at L{causal_layer}"
        )
        evidence.append(
            f"Meta-controller should READ from L{align_layer}, ACT at L{causal_layer}"
        )
        evidence.append(
            f"Q/K gating should operate at L{causal_layer} "
            f"(where attention routing is causally active)"
        )

        # Check if causal layer has any alignment at all
        if causal_layer in multi.per_layer:
            causal_result = multi.per_layer[causal_layer]
            if causal_result.n_validated_axes == 0:
                evidence.append(
                    f"WARNING: L{causal_layer} (causal peak) has 0 validated axes — "
                    f"Q/K gating may not have signal to work with"
                )
    else:
        evidence.append(
            f"No dissociation: alignment and causal effect both peak at "
            f"L{multi.best_alignment_layer}"
        )

    # Report per-layer summary
    for layer_idx in sorted(multi.per_layer.keys()):
        r = multi.per_layer[layer_idx]
        evidence.append(
            f"  L{layer_idx}: MI={r.alignment_mi:.3f}, CKA={r.cka_similarity:.3f}, "
            f"validated={r.n_validated_axes}/12, scenario={r.scenario}"
        )

    multi.scenario_evidence = evidence

    logger.info("Multi-layer discovery complete:")
    logger.info("  Best alignment: L%d (MI=%.3f)", multi.best_alignment_layer,
                multi.per_layer[multi.best_alignment_layer].alignment_mi)
    logger.info("  Best causal: L%d", multi.best_causal_layer)
    logger.info("  Dissociation: %s", multi.dissociation)
    logger.info("  Validated axes (union): %d (%s)",
                multi.n_validated_axes, ", ".join(multi.all_validated_axes))
    logger.info("  Overall scenario: %s → %s", multi.scenario, multi.recommended_phase2)

    return multi
