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

Phase 2 (implemented):
    Path 1: OntologyMonitor — Observatory (read hidden states, classify)
    Path 2: OntologyInjector — Content injection (enrich prompts)
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
    "O1_POTENTIAL",         # 0: Latent capacity — unrealized, dormant tokens
    "O2_IDENTITY",          # 1: Classification — naming, labeling, reference
    "O3_EXECUTION",         # 2: Action — verbs, behaviors, output
    "O4_STRUCTURE",         # 3: Form — physical patterns, embodiment
    "O5_COGNITION",         # 4: Perception — attention, emotion, mental movement
    "O6_AGENCY",            # 5: Control — intent, authorship, steering
    "O7_REASONING",         # 6: Discrimination — logic, inference, analysis
    "O8_PURPOSE",           # 7: Meaning — motivation, intrinsic direction
    "O9_WITNESSES",         # 8: Meta-observation — awareness, reflection
    "O10_UNIFYING",         # 9: Coherence — synthesis, harmony, integration
    "O11_INTEGRATION",      # 10: Resolution — consolidation, completion
    "O12_ABSOLVING",        # 11: Termination — release, dissolution, boundary
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
    borderline_axes: List[str] = field(default_factory=list)  # MI within margin of threshold

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

    # Merged scenario (reclassified using union of axes + best metrics)
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

def _ensure_wordnet() -> bool:
    """Download WordNet corpus if missing. Returns True on success."""
    try:
        import nltk
        from nltk.corpus import wordnet as wn
    except ImportError:
        return False
    try:
        wn.synsets("test")
        return True
    except LookupError:
        nltk.download("wordnet", quiet=True)
        try:
            wn._LazyCorpusLoader__load()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            wn.synsets("test")
            return True
        except LookupError:
            return False


_wordnet_ready: Optional[bool] = None


# ── Bhava feature helpers ──────────────────────────────────────────────────
# Each function returns a [0, 1] score for a single token's activation on
# the corresponding Bhava dimension, using dependency relation, position,
# sentence depth, and optionally WordNet.

def _bhava_potential(dep: str, position_norm: float, depth_norm: float) -> float:
    """O1_POTENTIAL — Latent capacity: unrealized, dormant tokens.

    High for function words, determiners, latent placeholders — tokens that
    carry structural potential but have not yet resolved into meaning.
    """
    # Function words carry latent potential (they enable but don't express)
    latent_deps = {"det", "mark", "case", "cc", "punct", "expl"}
    if dep in latent_deps:
        return 0.8
    # Sentence-initial tokens carry more unrealized potential
    pos_score = max(0.0, 1.0 - position_norm)  # early = high
    if dep in ("aux", "auxpass"):
        return 0.6 + 0.2 * pos_score
    return 0.1 + 0.2 * pos_score


def _bhava_identity(dep: str, word: str) -> float:
    """O2_IDENTITY — Naming, labeling, classification, reference.

    High for nouns, proper nouns, nominal subjects — tokens that name things.
    """
    # Nouns/subjects = identity-bearing
    identity_deps = {"nsubj", "nsubjpass", "nmod", "pobj", "appos", "attr"}
    if dep in identity_deps:
        return 0.9
    if dep in ("dobj", "iobj", "obj"):
        return 0.7  # objects name things too
    if dep in ("compound", "flat", "name"):
        return 0.8
    # Proper-noun-like heuristic: capitalized
    if word and word[0].isupper():
        return 0.7
    return 0.1


def _bhava_execution(dep: str) -> float:
    """O3_EXECUTION — Action, behaviors, output, karma.

    High for verbs, predicates — tokens that denote doing/happening.
    """
    if dep in ("ROOT", "root"):
        return 1.0  # main predicate = pure action
    if dep in ("xcomp", "ccomp", "advcl", "relcl", "parataxis"):
        return 0.8  # clausal complements are secondary actions
    if dep in ("aux", "auxpass"):
        return 0.5  # auxiliaries support action
    if dep in ("conj",) and False:  # placeholder for verb conj detection
        return 0.7
    return 0.05


def _bhava_structure(dep: str, depth_norm: float) -> float:
    """O4_STRUCTURE — Form, physical patterns, embodiment, foundation.

    High for tokens that provide structural scaffolding: depth, nesting,
    compounds, prepositional frameworks.
    """
    # Deep structural nesting = high structure
    struct_score = depth_norm * 0.6
    if dep in ("prep", "case", "mark"):
        struct_score += 0.4  # structural connectors
    elif dep in ("compound", "flat", "fixed"):
        struct_score += 0.3  # compound structure
    elif dep in ("cc", "conj"):
        struct_score += 0.2  # coordination structure
    elif dep in ("punct",):
        struct_score += 0.3  # punctuation is structural scaffolding
    return min(struct_score, 1.0)


def _bhava_cognition(dep: str, word: str) -> float:
    """O5_COGNITION — Perception, attention, emotion, mental movement.

    High for sensory/cognitive verbs, adjectives expressing perception
    or emotion, attention-directing words.
    """
    w = word.lower().strip(".,!?;:\"'()[]{}—-")
    # Cognitive/perceptual vocabulary (common set)
    cognitive_words = {
        "think", "know", "believe", "feel", "see", "hear", "notice",
        "understand", "realize", "perceive", "sense", "recognize",
        "imagine", "wonder", "consider", "expect", "hope", "fear",
        "love", "hate", "like", "want", "need", "wish", "prefer",
        "remember", "forget", "learn", "discover", "observe", "watch",
    }
    if w in cognitive_words:
        return 0.9
    # Adjectives with emotional/perceptual content
    if dep in ("amod",):
        return 0.4  # modifiers can express perception
    # Adverbs of manner (perception-modulating)
    if dep in ("advmod",):
        return 0.3
    return 0.05


def _bhava_agency(dep: str, position_norm: float) -> float:
    """O6_AGENCY — Control, intent, authorship, steering.

    High for subjects of active verbs, imperative markers, directive words.
    Agents that steer meaning.
    """
    if dep in ("nsubj",):
        return 0.9  # active subject = agent
    if dep in ("nsubjpass", "csubj"):
        return 0.5  # passive/clausal subject = reduced agency
    if dep in ("ROOT", "root"):
        return 0.6  # predicate controls sentence flow
    if dep in ("dobj", "obj"):
        return 0.2  # objects are acted upon
    # Sentence-initial position correlates with topic/agent
    if position_norm < 0.15:
        return 0.5
    return 0.1


def _bhava_reasoning(dep: str, word: str) -> float:
    """O7_REASONING — Logic, discrimination, inference, analysis.

    High for logical connectives, comparative/analytical words, subordination.
    """
    w = word.lower().strip(".,!?;:\"'()[]{}—-")
    reasoning_words = {
        "because", "therefore", "however", "although", "if", "unless",
        "since", "thus", "hence", "while", "whereas", "whether",
        "but", "yet", "despite", "moreover", "furthermore", "indeed",
        "consequently", "nevertheless", "rather", "instead", "otherwise",
        "than", "compared", "between", "among", "versus", "either",
        "neither", "both", "nor", "so", "then",
    }
    if w in reasoning_words:
        return 0.9
    if dep in ("mark", "cc"):
        return 0.6  # structural markers of logical relations
    if dep in ("advcl", "ccomp"):
        return 0.5  # clausal complements often express reasoning
    if dep in ("nummod",):
        return 0.4  # numerical = analytical
    return 0.05


def _bhava_purpose(dep: str, word: str) -> float:
    """O8_PURPOSE — Meaning, motivation, intrinsic direction, transformation.

    High for purposive constructions, infinitival complements, goal-words.
    """
    w = word.lower().strip(".,!?;:\"'()[]{}—-")
    purpose_words = {
        "to", "for", "towards", "into", "become", "achieve", "aim",
        "goal", "purpose", "reason", "cause", "why", "order", "sake",
        "mean", "meaning", "means", "intend", "plan", "seek", "strive",
        "transform", "change", "create", "build", "develop", "grow",
    }
    if w in purpose_words:
        return 0.8
    if dep in ("xcomp",):
        return 0.7  # infinitival complements express purpose
    if dep in ("advcl",):
        return 0.4  # adverbial clauses can express purpose
    if dep in ("prep",) and w in ("for", "to", "towards"):
        return 0.7
    return 0.05


def _bhava_witnesses(dep: str, word: str, depth_norm: float) -> float:
    """O9_WITNESSES — Meta-observation, awareness, reflection, monitoring.

    High for meta-linguistic markers, discourse markers, evaluative adverbs,
    parentheticals, and deeply embedded reflexive structures.
    """
    w = word.lower().strip(".,!?;:\"'()[]{}—-")
    meta_words = {
        "apparently", "perhaps", "maybe", "probably", "clearly",
        "obviously", "certainly", "actually", "really", "indeed",
        "basically", "essentially", "supposedly", "reportedly",
        "literally", "arguably", "seemingly", "presumably",
        "note", "recall", "observe", "reflect", "itself", "themselves",
    }
    if w in meta_words:
        return 0.9
    if dep in ("parataxis", "intj"):
        return 0.7  # parenthetical = meta-commentary
    if dep in ("advmod",) and depth_norm > 0.5:
        return 0.5  # deep adverbs tend to be evaluative
    return 0.05


def _bhava_unifying(dep: str, position_norm: float, depth_norm: float) -> float:
    """O10_UNIFYING — Coherence, synthesis, harmony, integration.

    High for coordinating conjunctions, summary positions, tokens that
    bring together disparate elements.
    """
    if dep in ("cc", "conj"):
        return 0.8  # coordination = unification
    if dep in ("ROOT", "root") and position_norm > 0.7:
        return 0.6  # late predicates synthesize
    # Low depth + late position = summary/unifying
    synthesis = position_norm * 0.4 + (1.0 - depth_norm) * 0.3
    if dep in ("appos",):
        synthesis += 0.3  # appositives integrate information
    return min(synthesis, 1.0)


def _bhava_integration(dep: str, position_norm: float) -> float:
    """O11_INTEGRATION — Resolution, consolidation, completion of parts.

    High for sentence-final elements, completive constructions, objects
    that complete the predicate.
    """
    # Late position = resolution
    resolve_score = position_norm * 0.5
    if dep in ("dobj", "obj", "iobj"):
        resolve_score += 0.4  # objects complete the action
    elif dep in ("attr", "oprd"):
        resolve_score += 0.3  # predicate complements resolve meaning
    elif dep in ("pobj",):
        resolve_score += 0.3  # prepositional objects complete phrases
    elif dep in ("punct",) and position_norm > 0.9:
        resolve_score += 0.3  # final punctuation = closure
    return min(resolve_score, 1.0)


def _bhava_absolving(dep: str, word: str, position_norm: float) -> float:
    """O12_ABSOLVING — Termination, release, dissolution, final boundary.

    High for sentence-ending tokens, terminators, negation (dissolution
    of meaning), and boundary markers.
    """
    w = word.lower().strip(".,!?;:\"'()[]{}—-")
    # Terminal punctuation
    if dep in ("punct",) and position_norm > 0.9:
        return 0.9
    # Negation = dissolution of meaning
    if dep in ("neg",):
        return 0.8
    dissolution_words = {
        "not", "never", "no", "none", "nothing", "neither", "nowhere",
        "end", "stop", "finish", "terminate", "cancel", "remove",
        "delete", "destroy", "lose", "lost", "gone", "done", "over",
        "finally", "last", "ultimate", "complete", "final",
    }
    if w in dissolution_words:
        return 0.8
    # Very late position = boundary
    if position_norm > 0.95:
        return 0.5
    return 0.05


def build_ontology_vectors(
    words: list,
    H: np.ndarray,
    labels: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build 12-axis Bhava ontology vectors (O1–O12) for annotated words.

    Each token receives a 12D activation vector where each dimension
    corresponds to one of the 12 ontological Bhavas from the SymbolU
    architecture:

        [0] O1_POTENTIAL    — latent capacity, unrealized
        [1] O2_IDENTITY     — naming, labeling, classification
        [2] O3_EXECUTION    — action, behavior, output
        [3] O4_STRUCTURE    — form, patterns, foundation
        [4] O5_COGNITION    — perception, attention, emotion
        [5] O6_AGENCY       — control, intent, steering
        [6] O7_REASONING    — logic, inference, analysis
        [7] O8_PURPOSE      — meaning, motivation, direction
        [8] O9_WITNESSES    — meta-observation, reflection
        [9] O10_UNIFYING    — coherence, synthesis
        [10] O11_INTEGRATION — resolution, consolidation
        [11] O12_ABSOLVING  — termination, release, boundary

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
        Bhava activation vectors per token (all values in [0, 1]).
    valid_mask : np.ndarray [N_w] bool
        Always True (all 12 axes are computed for every token).
    """
    N = len(words)
    ont = np.zeros((N, N_AXES), dtype=np.float32)

    # Max sentence length for normalization
    max_pos = max((w.position_in_sentence for w in words), default=1)
    max_pos = max(max_pos, 1)

    # Max depth for normalization
    max_depth = max((w.dep_depth for w in words), default=1)
    max_depth = max(max_depth, 1)

    for i, w in enumerate(words):
        dep = w.dep_relation
        pos_norm = w.position_in_sentence / max_pos
        depth_norm = w.dep_depth / max_depth

        ont[i, 0] = _bhava_potential(dep, pos_norm, depth_norm)
        ont[i, 1] = _bhava_identity(dep, w.word)
        ont[i, 2] = _bhava_execution(dep)
        ont[i, 3] = _bhava_structure(dep, depth_norm)
        ont[i, 4] = _bhava_cognition(dep, w.word)
        ont[i, 5] = _bhava_agency(dep, pos_norm)
        ont[i, 6] = _bhava_reasoning(dep, w.word)
        ont[i, 7] = _bhava_purpose(dep, w.word)
        ont[i, 8] = _bhava_witnesses(dep, w.word, depth_norm)
        ont[i, 9] = _bhava_unifying(dep, pos_norm, depth_norm)
        ont[i, 10] = _bhava_integration(dep, pos_norm)
        ont[i, 11] = _bhava_absolving(dep, w.word, pos_norm)

    # All 12 axes are always computed — every token is valid
    valid_mask = np.ones(N, dtype=bool)

    logger.info(
        "Ontology vectors: %d/%d words valid (%.1f%%), %d axes",
        valid_mask.sum(), N, valid_mask.mean() * 100, N_AXES,
    )

    return ont, valid_mask


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
    borderline_margin: float = 0.01,
) -> Tuple[Dict[str, float], Dict[str, int], List[str], List[str]]:
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
    borderline_margin : float
        Axes with MI in [threshold - margin, threshold] are reported as
        borderline (near-misses that may validate with more data or training).

    Returns
    -------
    per_axis_mi : dict
        axis_name → max MI with any PCA direction
    per_axis_best_pca : dict
        axis_name → which PCA direction it best maps to
    validated_axes : list
        Names of axes that passed the threshold
    borderline_axes : list
        Names of axes within borderline_margin below the threshold
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
    borderline_lo = threshold - borderline_margin
    borderline = [
        name for name, mi in per_axis_mi.items()
        if borderline_lo <= mi <= threshold and name not in validated
    ]

    logger.info(
        "Naming ceremony: %d/%d axes validated (threshold=%.2f), %d borderline (margin=%.3f)",
        len(validated), len(AXIS_NAMES), threshold, len(borderline), borderline_margin,
    )
    for name in AXIS_NAMES:
        mi_val = per_axis_mi.get(name, 0.0)
        pca_dir = per_axis_best_pca.get(name, -1)
        if name in validated:
            status = "PASS"
        elif name in borderline:
            status = "NEAR"
        else:
            status = "FAIL"
        logger.info("  [%s] %s: MI=%.4f (best PCA dir=%d)", status, name, mi_val, pca_dir)

    return per_axis_mi, per_axis_best_pca, validated, borderline


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
    elif mi <= 0.2 and gap > 0.05:
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
# Phase 2: OntologyMonitor (Path 1 — Observatory)
# ---------------------------------------------------------------------------

# The 4 robust Bhava axes for Phase 2 monitoring — these span the
# spectrum from concrete identity through action to meta-observation.
ROBUST_AXES: List[str] = [
    "O2_IDENTITY",         # idx 1 — naming/classification
    "O3_EXECUTION",        # idx 2 — action/behavior
    "O6_AGENCY",           # idx 5 — control/steering
    "O9_WITNESSES",        # idx 8 — meta-observation/reflection
]

ROBUST_AXIS_INDICES: List[int] = [
    AXIS_NAMES.index(a) for a in ROBUST_AXES
]

N_ROBUST = len(ROBUST_AXES)


@dataclass
class MonitorResult:
    """Output of the OntologyMonitor on a batch of sequences."""

    # Per-sequence ontological state [batch, 4]
    z_ont: Any = None  # np.ndarray or torch.Tensor

    # Human-readable axis names
    axis_names: List[str] = field(default_factory=lambda: list(ROBUST_AXES))

    # Monitoring signals derived from z_ont
    domain_label: str = ""           # "concrete" / "abstract" / "mixed"
    structure_label: str = ""        # "simple" / "complex"
    intent_label: str = ""           # "informational" / "action" / "modification"
    confidence: float = 0.0          # mean activation magnitude

    # Drift detection: distance from training distribution centroid
    drift_score: float = 0.0


@dataclass
class MonitorTrainResult:
    """Training metrics for the OntologyMonitor."""
    epochs_trained: int = 0
    final_train_loss: float = 0.0
    final_val_loss: float = 0.0
    r2_per_axis: Dict[str, float] = field(default_factory=dict)
    r2_mean: float = 0.0


class OntologyMonitor:
    """Phase 2, Path 1: Real-time observatory of model internal state.

    Reads hidden states at a target layer (typically L7 = best alignment),
    predicts the 4 robust ontological axis values, and produces monitoring
    signals (drift alerts, confidence, routing classification).

    Architecture:
        H[layer] → mean_pool → Linear(d, 128) → ReLU → Dropout(0.1)
                 → Linear(128, 64) → ReLU → Linear(64, 4) → Sigmoid

    Training: Supervised regression on Phase 1 ontology vectors (robust axes only).
    Loss: MSE(predicted, ground_truth) for the 4 robust axes.
    """

    def __init__(self, d_model: int, n_axes: int = N_ROBUST, dropout: float = 0.1):
        import torch
        import torch.nn as nn

        self.d_model = d_model
        self.n_axes = n_axes
        self.encoder = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, n_axes),
            nn.Sigmoid(),
        )
        # Training distribution centroid for drift detection
        self._centroid: Optional[np.ndarray] = None
        self._centroid_std: Optional[np.ndarray] = None

    def forward(self, H) -> Any:
        """Predict ontological state from hidden states.

        Parameters
        ----------
        H : torch.Tensor
            Either [batch, seq, d] (sequence-level) → mean-pools over seq
            or [batch, d] (already pooled).

        Returns
        -------
        z_ont : torch.Tensor [batch, n_axes]
            Predicted axis values in [0, 1].
        """
        import torch

        if H.dim() == 3:
            h_pool = H.mean(dim=1)
        elif H.dim() == 2:
            h_pool = H
        else:
            raise ValueError(f"Expected 2D or 3D tensor, got {H.dim()}D")

        return self.encoder(h_pool)

    def predict(self, H_np: np.ndarray) -> MonitorResult:
        """Predict ontological state from numpy hidden states.

        Parameters
        ----------
        H_np : np.ndarray [N, d] or [batch, seq, d]

        Returns
        -------
        MonitorResult with z_ont and derived labels.
        """
        import torch

        was_training = self.encoder.training
        self.encoder.eval()

        with torch.no_grad():
            H_t = torch.from_numpy(H_np.astype(np.float32))
            z = self.forward(H_t).cpu().numpy()

        if was_training:
            self.encoder.train()

        result = MonitorResult(z_ont=z, axis_names=list(ROBUST_AXES))

        # Derive labels from mean axis values
        z_mean = z.mean(axis=0) if z.ndim == 2 else z

        # concreteness → domain
        if z_mean[0] > 0.6:
            result.domain_label = "concrete"
        elif z_mean[0] < 0.4:
            result.domain_label = "abstract"
        else:
            result.domain_label = "mixed"

        # modificational_load → structure complexity
        result.structure_label = "complex" if z_mean[2] > 0.5 else "simple"

        # categorical_type → intent
        cat_val = z_mean[3]
        if cat_val < 0.2:
            result.intent_label = "informational"  # noun-like
        elif cat_val < 0.5:
            result.intent_label = "action"          # verb-like
        else:
            result.intent_label = "modification"    # modifier/function

        # confidence = mean activation magnitude
        result.confidence = float(np.mean(np.abs(z_mean)))

        # drift detection
        if self._centroid is not None:
            diff = z_mean - self._centroid
            # Normalized Mahalanobis-like distance
            std = np.maximum(self._centroid_std, 1e-6)
            result.drift_score = float(np.mean(np.abs(diff) / std))

        return result

    def train_monitor(
        self,
        H: np.ndarray,
        ont_features: np.ndarray,
        valid_mask: np.ndarray,
        n_epochs: int = 100,
        lr: float = 1e-3,
        batch_size: int = 256,
        val_split: float = 0.2,
        seed: int = 42,
    ) -> MonitorTrainResult:
        """Train the monitor on Phase 1 ontology vectors.

        Parameters
        ----------
        H : np.ndarray [N_w, d]
            Hidden states at the target layer.
        ont_features : np.ndarray [N_w, 12]
            Full 12-axis ontology vectors from Phase 1.
        valid_mask : np.ndarray [N_w] bool
            Which words have valid ontology features.
        n_epochs : int
            Training epochs.
        lr : float
            Learning rate.
        batch_size : int
        val_split : float
            Fraction of data for validation.
        seed : int

        Returns
        -------
        MonitorTrainResult with training metrics.
        """
        import torch
        import torch.nn as nn

        rng = np.random.RandomState(seed)

        # Filter to valid words and extract robust axes only
        H_valid = H[valid_mask].astype(np.float32)
        targets = ont_features[valid_mask][:, ROBUST_AXIS_INDICES].astype(np.float32)

        N = H_valid.shape[0]
        if N < 20:
            logger.warning("Too few valid samples (%d) to train monitor", N)
            return MonitorTrainResult()

        # Train/val split
        perm = rng.permutation(N)
        n_val = max(int(N * val_split), 1)
        val_idx = perm[:n_val]
        train_idx = perm[n_val:]

        H_train = torch.from_numpy(H_valid[train_idx])
        y_train = torch.from_numpy(targets[train_idx])
        H_val = torch.from_numpy(H_valid[val_idx])
        y_val = torch.from_numpy(targets[val_idx])

        # Store centroid for drift detection
        self._centroid = targets[train_idx].mean(axis=0)
        self._centroid_std = targets[train_idx].std(axis=0)

        # Training
        optimizer = torch.optim.Adam(self.encoder.parameters(), lr=lr)
        criterion = nn.MSELoss()

        self.encoder.train()
        train_loss = 0.0
        val_loss = 0.0

        for epoch in range(n_epochs):
            # Shuffle training data
            idx = torch.randperm(len(train_idx))
            epoch_loss = 0.0
            n_batches = 0

            for start in range(0, len(train_idx), batch_size):
                batch_idx = idx[start:start + batch_size]
                H_batch = H_train[batch_idx]
                y_batch = y_train[batch_idx]

                pred = self.encoder(H_batch)
                loss = criterion(pred, y_batch)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            train_loss = epoch_loss / max(n_batches, 1)

            if (epoch + 1) % 20 == 0 or epoch == n_epochs - 1:
                self.encoder.eval()
                with torch.no_grad():
                    val_pred = self.encoder(H_val)
                    val_loss = criterion(val_pred, y_val).item()
                self.encoder.train()
                logger.info(
                    "  Monitor epoch %d/%d: train_loss=%.4f, val_loss=%.4f",
                    epoch + 1, n_epochs, train_loss, val_loss,
                )

        # Final evaluation
        self.encoder.eval()
        with torch.no_grad():
            val_pred = self.encoder(H_val).cpu().numpy()
            val_true = y_val.cpu().numpy()

        # R² per axis
        r2_per_axis = {}
        for i, axis_name in enumerate(ROBUST_AXES):
            ss_res = np.sum((val_true[:, i] - val_pred[:, i]) ** 2)
            ss_tot = np.sum((val_true[:, i] - val_true[:, i].mean()) ** 2)
            r2 = 1.0 - ss_res / max(ss_tot, 1e-10)
            r2_per_axis[axis_name] = float(r2)

        r2_mean = float(np.mean(list(r2_per_axis.values())))

        logger.info(
            "Monitor training complete: R²=%.3f (per-axis: %s)",
            r2_mean,
            ", ".join(f"{k}={v:.3f}" for k, v in r2_per_axis.items()),
        )

        return MonitorTrainResult(
            epochs_trained=n_epochs,
            final_train_loss=train_loss,
            final_val_loss=val_loss,
            r2_per_axis=r2_per_axis,
            r2_mean=r2_mean,
        )


# ---------------------------------------------------------------------------
# Phase 2: OntologyInjector (Path 2 — Content Injection)
# ---------------------------------------------------------------------------

@dataclass
class InjectionMetadata:
    """Structured ontological metadata for prompt injection."""

    domain: str = "mixed"              # concrete / abstract / mixed
    structure: str = "simple"          # simple / complex
    intent: str = "informational"      # informational / action / modification
    confidence: str = "medium"         # high / medium / low
    primary_role: str = "unknown"      # subject / object / root / modifier
    raw_scores: Dict[str, float] = field(default_factory=dict)

    def format_tag(self) -> str:
        """Format as structured tag for prompt injection."""
        lines = [
            "[ONTOLOGY]",
            f"domain: {self.domain}",
            f"structure: {self.structure}",
            f"intent: {self.intent}",
            f"confidence: {self.confidence}",
            f"primary_role: {self.primary_role}",
            "[/ONTOLOGY]",
        ]
        return "\n".join(lines)


class OntologyInjector:
    """Phase 2, Path 2: Classify input text and inject Bhava metadata.

    Works at the API boundary — no hidden-state access required. Computes
    the 4 robust Bhava axis scores (O2_IDENTITY, O3_EXECUTION, O6_AGENCY,
    O9_WITNESSES) using lightweight word-level heuristics, and formats them
    as structured metadata prepended to the LLM system prompt.

    Compatible with any LLM API (Claude, GPT-4, local models).
    """

    def classify(self, text: str) -> InjectionMetadata:
        """Classify input text along the 4 robust Bhava axes.

        Parameters
        ----------
        text : str
            Input text to classify.

        Returns
        -------
        InjectionMetadata with domain, structure, intent, confidence.
        """
        words = text.split()
        if not words:
            return InjectionMetadata()

        # Per-word Bhava activation scores (lightweight — no dep parse)
        identity_scores = []
        execution_scores = []
        agency_scores = []
        witness_scores = []

        n_words = len(words)
        for idx, word in enumerate(words):
            w = word.lower().strip(".,!?;:\"'()[]{}—-")
            if not w:
                continue
            pos_norm = idx / max(n_words - 1, 1)

            # O2_IDENTITY — naming/classification
            identity_scores.append(self._word_identity(w))

            # O3_EXECUTION — action/behavior
            execution_scores.append(self._word_execution(w))

            # O6_AGENCY — control/steering
            agency_scores.append(self._word_agency(w, pos_norm))

            # O9_WITNESSES — meta-observation
            witness_scores.append(self._word_witnesses(w))

        if not identity_scores:
            return InjectionMetadata()

        scores = {
            "O2_IDENTITY": float(np.mean(identity_scores)),
            "O3_EXECUTION": float(np.mean(execution_scores)),
            "O6_AGENCY": float(np.mean(agency_scores)),
            "O9_WITNESSES": float(np.mean(witness_scores)),
        }

        meta = InjectionMetadata(raw_scores=scores)

        # Domain: identity-dominant = concrete, witness-dominant = abstract
        if scores["O2_IDENTITY"] > scores["O9_WITNESSES"] + 0.15:
            meta.domain = "concrete"
        elif scores["O9_WITNESSES"] > scores["O2_IDENTITY"] + 0.15:
            meta.domain = "abstract"
        else:
            meta.domain = "mixed"

        # Structure: high agency = directed/complex
        meta.structure = "complex" if scores["O6_AGENCY"] > 0.4 else "simple"

        # Intent: dominated by execution vs identity vs witness
        dominant = max(scores, key=scores.get)  # type: ignore[arg-type]
        if dominant == "O3_EXECUTION":
            meta.intent = "action"
        elif dominant == "O9_WITNESSES":
            meta.intent = "reflection"
        elif dominant == "O2_IDENTITY":
            meta.intent = "informational"
        else:
            meta.intent = "directive"

        # Confidence from score dispersion
        score_vals = list(scores.values())
        dispersion = float(np.std(score_vals))
        if dispersion > 0.2:
            meta.confidence = "high"
        elif dispersion > 0.1:
            meta.confidence = "medium"
        else:
            meta.confidence = "low"

        # Primary Bhava
        meta.primary_role = dominant

        return meta

    # ── Lightweight per-word Bhava heuristics (no dep parse) ──────────

    @staticmethod
    def _word_identity(w: str) -> float:
        """O2_IDENTITY: naming/classification potential."""
        # Capitalized or long words tend to be identity-bearing
        if w[0:1].isupper():
            return 0.8
        # Short function words are not identity-bearing
        if len(w) <= 2:
            return 0.1
        if len(w) >= 6:
            return 0.5  # longer words more likely nouns
        return 0.3

    @staticmethod
    def _word_execution(w: str) -> float:
        """O3_EXECUTION: action/behavior potential."""
        action_suffixes = ("ing", "ed", "ize", "ify", "ate")
        action_words = {
            "run", "make", "do", "get", "set", "go", "put", "take",
            "build", "create", "implement", "deploy", "test", "send",
            "write", "read", "start", "stop", "move", "change",
        }
        if w in action_words:
            return 0.9
        if any(w.endswith(s) for s in action_suffixes):
            return 0.6
        return 0.1

    @staticmethod
    def _word_agency(w: str, pos_norm: float) -> float:
        """O6_AGENCY: control/steering potential."""
        agent_words = {
            "i", "we", "you", "he", "she", "they", "it",
            "must", "should", "will", "can", "need", "want",
        }
        if w in agent_words:
            return 0.8
        # Early position = more agentive
        if pos_norm < 0.15:
            return 0.5
        return 0.15

    @staticmethod
    def _word_witnesses(w: str) -> float:
        """O9_WITNESSES: meta-observation/reflection potential."""
        meta_words = {
            "apparently", "perhaps", "maybe", "probably", "clearly",
            "obviously", "actually", "really", "indeed", "basically",
            "essentially", "note", "recall", "observe", "seems",
            "appears", "might", "could", "would", "somehow",
        }
        if w in meta_words:
            return 0.9
        # Question words are reflective
        if w in ("why", "how", "what", "whether", "if"):
            return 0.6
        return 0.05

    def inject(self, system_prompt: str, user_input: str) -> str:
        """Classify user input and prepend ontological metadata to system prompt.

        Parameters
        ----------
        system_prompt : str
            Original system prompt.
        user_input : str
            User's input message.

        Returns
        -------
        enriched_prompt : str
            System prompt with ontological metadata prepended.
        """
        meta = self.classify(user_input)
        tag = meta.format_tag()
        return f"{tag}\n\n{system_prompt}"

    # --- Word-level heuristics ---

    # Common function words (abstract)
    _FUNCTION_WORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "must", "need", "dare",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "and", "but", "or", "nor", "not", "so", "yet", "both",
        "either", "neither", "each", "every", "all", "any", "few", "more",
        "most", "other", "some", "such", "no", "only", "own", "same", "than",
        "too", "very", "just", "because", "if", "when", "while", "although",
        "that", "which", "who", "whom", "whose", "this", "these", "those",
        "it", "its", "he", "she", "they", "them", "we", "us", "you", "i",
        "me", "my", "your", "his", "her", "our", "their",
    })

    # Common concrete nouns
    _CONCRETE_NOUNS = frozenset({
        "car", "house", "dog", "cat", "tree", "water", "food", "book", "door",
        "table", "chair", "phone", "computer", "road", "city", "person", "hand",
        "face", "eye", "head", "body", "room", "wall", "floor", "window",
        "sun", "moon", "earth", "fire", "stone", "metal", "wood", "glass",
    })

    # Common action verbs
    _ACTION_VERBS = frozenset({
        "run", "walk", "jump", "eat", "drink", "write", "read", "build",
        "break", "throw", "catch", "push", "pull", "open", "close", "move",
        "turn", "start", "stop", "give", "take", "make", "put", "get",
        "go", "come", "see", "look", "find", "keep", "tell", "say",
        "think", "know", "feel", "try", "leave", "call", "ask", "work",
    })

    # (Old generic helpers removed — Bhava-specific helpers are above)


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
    per_axis_mi, per_axis_best_pca, validated, borderline = run_naming_ceremony(
        ont_valid, H_proj, cfg.mi_n_bins, cfg.naming_mi_threshold,
    )
    result.per_axis_mi = per_axis_mi
    result.per_axis_best_pca = per_axis_best_pca
    result.n_validated_axes = len(validated)
    result.validated_axes = validated
    result.borderline_axes = borderline
    logger.info("7c: Done in %.1fs — %d axes validated: %s%s",
                _time.time() - _t, len(validated), validated,
                f" ({len(borderline)} borderline: {borderline})" if borderline else "")

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
    all_borderline = set()
    for result in multi.per_layer.values():
        all_axes.update(result.validated_axes)
        all_borderline.update(result.borderline_axes)
    # Borderline axes that are validated at another layer shouldn't stay borderline
    all_borderline -= all_axes
    multi.all_validated_axes = sorted(all_axes, key=lambda a: AXIS_NAMES.index(a) if a in AXIS_NAMES else 99)
    multi.n_validated_axes = len(multi.all_validated_axes)

    # --- Re-classify overall scenario using merged multi-layer evidence ---
    # Instead of copying one layer's scenario, use the union of validated axes
    # and best metrics across all layers. This prevents edge cases where an axis
    # barely fails at the best-MI layer but passes at another, changing N and
    # cascading into a wrong scenario.
    best_result = multi.per_layer[multi.best_alignment_layer]
    merged = DiscoveryResult(layer_idx=-1)  # synthetic merged result
    merged.n_validated_axes = multi.n_validated_axes  # union count
    merged.validated_axes = multi.all_validated_axes
    merged.alignment_mi = max(r.alignment_mi for r in multi.per_layer.values())
    merged.cka_similarity = max(r.cka_similarity for r in multi.per_layer.values())
    merged.coverage_ratio = max(r.coverage_ratio for r in multi.per_layer.values())
    merged.discriminability_gap = max(r.discriminability_gap for r in multi.per_layer.values())
    # Merge per-axis MI: take the best MI for each axis across all layers
    merged_per_axis_mi: Dict[str, float] = {}
    for r in multi.per_layer.values():
        for ax_name, mi_val in r.per_axis_mi.items():
            merged_per_axis_mi[ax_name] = max(merged_per_axis_mi.get(ax_name, 0.0), mi_val)
    merged.per_axis_mi = merged_per_axis_mi
    merged = classify_scenario(merged)

    multi.scenario = merged.scenario
    multi.recommended_phase2 = merged.recommended_phase2

    # Log if merged scenario differs from best layer's per-layer scenario
    if merged.scenario != best_result.scenario:
        logger.info(
            "Multi-layer reclassification: %s → %s "
            "(best layer L%d had %s with N=%d, merged N=%d)",
            best_result.scenario, merged.scenario,
            multi.best_alignment_layer, best_result.scenario,
            best_result.n_validated_axes, multi.n_validated_axes,
        )

    # --- Build evidence incorporating dissociation ---
    evidence = list(merged.scenario_evidence)
    if merged.scenario != best_result.scenario:
        evidence.append(
            f"RECLASSIFIED: Best layer L{multi.best_alignment_layer} was Scenario "
            f"{best_result.scenario} (N={best_result.n_validated_axes}), but merged "
            f"union has N={multi.n_validated_axes} → Scenario {merged.scenario}"
        )
    if all_borderline:
        bl_sorted = sorted(all_borderline, key=lambda a: AXIS_NAMES.index(a) if a in AXIS_NAMES else 99)
        evidence.append(
            f"Borderline axes (near threshold): {', '.join(bl_sorted)}"
        )

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


# ---------------------------------------------------------------------------
# Phase 2 Runner
# ---------------------------------------------------------------------------

@dataclass
class Phase2Result:
    """Output of Phase 2: Observatory + Injection prototype."""

    # Monitor training results
    monitor_trained: bool = False
    monitor_r2_mean: float = 0.0
    monitor_r2_per_axis: Dict[str, float] = field(default_factory=dict)
    monitor_train_loss: float = 0.0
    monitor_val_loss: float = 0.0

    # Monitor inference test
    monitor_sample_predictions: List[Dict[str, float]] = field(default_factory=list)

    # Injector classification tests
    injector_test_results: List[Dict[str, str]] = field(default_factory=list)


def run_phase2(
    annotations,
    hidden_states: Dict[int, np.ndarray],
    labels: np.ndarray,
    ont_features: np.ndarray,
    valid_mask: np.ndarray,
    read_layer: int,
    n_epochs: int = 100,
    seed: int = 42,
) -> Phase2Result:
    """Run Phase 2: train monitor and test injector.

    Parameters
    ----------
    annotations : StructuralAnnotations
        Word annotations from Phase 1.
    hidden_states : dict[int, np.ndarray]
        Per-layer hidden states.
    labels : np.ndarray [N_w]
        Grammatical role labels.
    ont_features : np.ndarray [N_w, 12]
        Full 12-axis ontology vectors from Phase 1.
    valid_mask : np.ndarray [N_w] bool
        Which words have valid ontology features.
    read_layer : int
        Layer to read hidden states from (typically best alignment layer).
    n_epochs : int
        Training epochs for the monitor.
    seed : int

    Returns
    -------
    Phase2Result with training metrics and test outputs.
    """
    result = Phase2Result()

    H = hidden_states[read_layer]
    d_model = H.shape[1]

    # --- Path 1: Train OntologyMonitor ---
    logger.info("=" * 60)
    logger.info("PHASE 2, PATH 1: Training OntologyMonitor")
    logger.info("=" * 60)
    logger.info("  d_model=%d, n_axes=%d, read_layer=L%d", d_model, N_ROBUST, read_layer)

    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)

    train_result = monitor.train_monitor(
        H=H,
        ont_features=ont_features,
        valid_mask=valid_mask,
        n_epochs=n_epochs,
        seed=seed,
    )

    result.monitor_trained = True
    result.monitor_r2_mean = train_result.r2_mean
    result.monitor_r2_per_axis = train_result.r2_per_axis
    result.monitor_train_loss = train_result.final_train_loss
    result.monitor_val_loss = train_result.final_val_loss

    logger.info("  Monitor R²=%.3f (per-axis: %s)",
                train_result.r2_mean,
                ", ".join(f"{k}={v:.3f}" for k, v in train_result.r2_per_axis.items()))

    # Run monitor inference on a few samples
    logger.info("  Running monitor inference on sample data...")
    H_valid = H[valid_mask]
    n_samples = min(5, H_valid.shape[0])
    for i in range(n_samples):
        h_sample = H_valid[i:i + 1]
        monitor_out = monitor.predict(h_sample)
        sample_dict = {
            axis: float(monitor_out.z_ont[0, j])
            for j, axis in enumerate(ROBUST_AXES)
        }
        sample_dict["domain"] = monitor_out.domain_label
        sample_dict["structure"] = monitor_out.structure_label
        sample_dict["intent"] = monitor_out.intent_label
        result.monitor_sample_predictions.append(sample_dict)

    # --- Path 2: Test OntologyInjector ---
    logger.info("=" * 60)
    logger.info("PHASE 2, PATH 2: Testing OntologyInjector")
    logger.info("=" * 60)

    injector = OntologyInjector()

    test_inputs = [
        "The cat sat on the mat.",
        "Implement a distributed database with eventual consistency.",
        "Running quickly through the heavily forested area.",
        "Is this good or bad?",
        "Build, test, and deploy the application to production servers.",
    ]

    for text in test_inputs:
        meta = injector.classify(text)
        test_dict = {
            "input": text,
            "domain": meta.domain,
            "structure": meta.structure,
            "intent": meta.intent,
            "confidence": meta.confidence,
            "primary_role": meta.primary_role,
        }
        test_dict.update({f"score_{k}": f"{v:.3f}" for k, v in meta.raw_scores.items()})
        result.injector_test_results.append(test_dict)
        logger.info("  Input: %s", text[:50])
        logger.info("    → domain=%s, structure=%s, intent=%s, confidence=%s",
                     meta.domain, meta.structure, meta.intent, meta.confidence)

    # Test injection formatting
    sample_enriched = injector.inject(
        "You are a helpful assistant.",
        test_inputs[0],
    )
    logger.info("  Sample enriched prompt:\n%s", sample_enriched)

    logger.info("Phase 2 complete.")
    return result
