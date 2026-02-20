"""
Part 5 — Causal Interchange Intervention (The Acid Test)
==========================================================

Once the top-k components/features are identified by the MDL probe, define
the structural subspace basis U_k.

Instead of simply ablating the subspace (which can push activations OOD and
break the model for non-causal reasons), perform **Activation Patching**
(Interchange Intervention):

1. Take two distinct sequences:
    - Sequence A: where word X is the **subject**
    - Sequence B: where word Y is the **object**

2. Isolate the structural subspace for both:
    h_{A,proj} = U_k @ U_k^T @ h_A
    h_{B,proj} = U_k @ U_k^T @ h_B

3. Swap the projections and reinject into the residual stream:
    h_{A,patched} = (h_A - h_{A,proj}) + h_{B,proj}

4. Run the forward pass to completion.

**Causal Proof**: If swapping the structural subspace dynamically changes
the model's structural downstream predictions (attention routing, syntactic
behavior) **without destroying output fluency**, the subspace is causally
responsible for structural computation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class InterventionConfig:
    """Configuration for causal interchange interventions."""

    n_pairs: int = 100
    """Number of (seq_A, seq_B) pairs to test."""

    target_layer: int = -1
    """Layer at which to perform the intervention (-1 = auto-select)."""

    max_seq_len: int = 128
    """Max sequence length for intervention pairs."""

    fluency_threshold: float = 2.0
    """Max ratio of patched_perplexity / original_perplexity before
    declaring fluency destroyed."""

    device: str = "cpu"
    seed: int = 42


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class InterventionResult:
    """Output of the causal interchange intervention for one layer."""

    layer_idx: int = 0

    n_pairs_tested: int = 0
    n_structural_flips: int = 0
    n_fluency_preserved: int = 0
    n_causal_successes: int = 0  # flip AND fluent

    flip_rate: float = 0.0
    fluency_rate: float = 0.0
    causal_success_rate: float = 0.0

    # Control baseline (identity patch) statistics
    control_kl_mean: float = 0.0
    control_kl_std: float = 0.0
    adaptive_kl_threshold: float = 0.0

    # Random subspace control statistics
    random_kl_mean: float = 0.0
    random_kl_std: float = 0.0
    specificity_ratio: float = 0.0  # real_kl / random_kl (>1 = specific)

    # Per-pair diagnostics
    pair_details: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Subspace basis construction
# ---------------------------------------------------------------------------

def build_subspace_basis(
    H: np.ndarray,
    labels: np.ndarray,
    k: int,
) -> np.ndarray:
    """Construct an orthonormal basis U_k ∈ R^{d × k} for the structural
    subspace using PCA on the label-conditioned hidden states.

    Specifically: compute PCA on the class-conditional means, then take the
    top-k directions.  This gives the directions that best separate the
    structural roles.

    Parameters
    ----------
    H : np.ndarray [N, d]
    labels : np.ndarray [N]  (integer class labels)
    k : int  (subspace dimensionality)

    Returns
    -------
    U_k : np.ndarray [d, k]  orthonormal columns
    """
    unique_labels = np.unique(labels)
    class_means = []
    for c in unique_labels:
        mask = labels == c
        if mask.sum() > 0:
            class_means.append(H[mask].mean(axis=0))
    class_means = np.stack(class_means)  # [n_classes, d]

    # Center the class means
    grand_mean = class_means.mean(axis=0)
    centered = class_means - grand_mean

    # SVD to find top-k discriminative directions
    U, S, Vt = np.linalg.svd(centered, full_matrices=False)
    actual_k = min(k, Vt.shape[0])
    U_k = Vt[:actual_k].T  # [d, actual_k]

    logger.info(
        "Built subspace basis: d=%d, k=%d, singular values=%s",
        H.shape[1], actual_k,
        ", ".join(f"{s:.3f}" for s in S[:actual_k]),
    )
    return U_k


# ---------------------------------------------------------------------------
# Intervention pair generation
# ---------------------------------------------------------------------------

@dataclass
class InterventionPair:
    """A pair of sequences for interchange intervention."""

    seq_a_ids: List[int]  # token IDs for sequence A
    seq_b_ids: List[int]  # token IDs for sequence B
    target_pos_a: int  # position of the structural target in A
    target_pos_b: int  # position of the structural target in B
    role_a: str  # structural role of target in A (e.g., "subject")
    role_b: str  # structural role of target in B (e.g., "object")


def generate_intervention_pairs(
    tokenizer,
    n_pairs: int,
    seed: int = 42,
) -> List[InterventionPair]:
    """Generate pairs of sentences with known structural role differences.

    Each pair has:
        - Sequence A: a word in a subject role
        - Sequence B: a word in an object role

    The pairs are constructed so that the structural difference is clear
    and the overall sentence structure is similar.
    """
    import random
    random.seed(seed)

    templates_subject = [
        "The {entity} {verb} the {other} in the {place}.",
        "{entity} quickly {verb} the {other} near the {place}.",
        "The tall {entity} {verb} the small {other}.",
        "{entity} and the {other} {verb} together.",
    ]
    templates_object = [
        "The {other} {verb} the {entity} in the {place}.",
        "The {other} quickly {verb} {entity} near the {place}.",
        "The small {other} {verb} the tall {entity}.",
        "The {other} {verb} together with {entity}.",
    ]

    entities = ["professor", "student", "scientist", "artist",
                "doctor", "engineer", "writer", "musician"]
    others = ["cat", "bird", "tree", "river", "stone", "flower"]
    verbs = ["observed", "studied", "followed", "examined",
             "noticed", "described", "measured", "crossed"]
    places = ["garden", "laboratory", "forest", "library", "museum"]

    pairs = []
    for _ in range(n_pairs):
        entity = random.choice(entities)
        other = random.choice(others)
        verb = random.choice(verbs)
        place = random.choice(places)

        tmpl_a = random.choice(templates_subject)
        tmpl_b = random.choice(templates_object)

        text_a = tmpl_a.format(entity=entity, other=other, verb=verb, place=place)
        text_b = tmpl_b.format(entity=entity, other=other, verb=verb, place=place)

        ids_a = tokenizer.encode(text_a, add_special_tokens=False)
        ids_b = tokenizer.encode(text_b, add_special_tokens=False)

        # Find target position: the entity token in each sequence
        entity_tokens = tokenizer.encode(" " + entity, add_special_tokens=False)
        pos_a = _find_subtoken_position(ids_a, entity_tokens)
        pos_b = _find_subtoken_position(ids_b, entity_tokens)

        if pos_a is not None and pos_b is not None:
            pairs.append(InterventionPair(
                seq_a_ids=ids_a,
                seq_b_ids=ids_b,
                target_pos_a=pos_a,
                target_pos_b=pos_b,
                role_a="subject",
                role_b="object",
            ))

    logger.info("Generated %d intervention pairs (requested %d)", len(pairs), n_pairs)
    return pairs


def _find_subtoken_position(
    sequence: List[int],
    pattern: List[int],
) -> Optional[int]:
    """Find the starting position of pattern in sequence."""
    for i in range(len(sequence) - len(pattern) + 1):
        if sequence[i : i + len(pattern)] == pattern:
            return i + len(pattern) - 1  # last sub-token
    return None


# ---------------------------------------------------------------------------
# Activation patching
# ---------------------------------------------------------------------------

class _PatchHook:
    """Forward hook that patches the hidden state at a specific layer.

    For the target position, replaces:
        h_patched = (h_original - U_k @ U_k^T @ h_original) + U_k @ U_k^T @ h_donor
    """

    def __init__(
        self,
        U_k: torch.Tensor,
        donor_hidden: torch.Tensor,
        target_pos: int,
    ):
        self.U_k = U_k  # [d, k]
        self.donor_hidden = donor_hidden  # [d]
        self.target_pos = target_pos
        self.original_hidden: Optional[torch.Tensor] = None
        self.patched_hidden: Optional[torch.Tensor] = None

    def __call__(self, module, inp, out):
        if isinstance(out, tuple):
            h = out[0]
            rest = out[1:]
        else:
            h = out
            rest = None

        # Save original
        self.original_hidden = h[:, self.target_pos, :].clone().detach()

        # Project original onto subspace
        h_orig_at_pos = h[0, self.target_pos, :]  # [d]
        proj_orig = self.U_k @ (self.U_k.T @ h_orig_at_pos)  # [d]

        # Project donor onto subspace
        proj_donor = self.U_k @ (self.U_k.T @ self.donor_hidden)  # [d]

        # Patch: remove original projection, add donor projection
        h_patched = h.clone()
        h_patched[0, self.target_pos, :] = (
            h_orig_at_pos - proj_orig + proj_donor
        )
        self.patched_hidden = h_patched[:, self.target_pos, :].clone().detach()

        if rest is not None:
            return (h_patched,) + rest
        return h_patched


def _random_orthonormal_basis(d: int, k: int, seed: int = 0) -> np.ndarray:
    """Generate a random orthonormal basis of shape [d, k].

    Uses QR decomposition of a random Gaussian matrix.
    """
    rng = np.random.RandomState(seed)
    A = rng.randn(d, k).astype(np.float64)
    Q, _ = np.linalg.qr(A)
    return Q[:, :k].astype(np.float32)


def _compute_logit_metrics(
    original_logits: torch.Tensor,
    patched_logits: torch.Tensor,
    seq_ids: List[int],
    target_pos: int,
) -> Dict:
    """Shared metric computation for both real and control patches.

    Returns dict with kl_divergence, max_prob_change, perplexity_ratio,
    original_ppl, patched_ppl.
    """
    original_log_probs = F.log_softmax(original_logits[0], dim=-1)
    patched_log_probs = F.log_softmax(patched_logits[0], dim=-1)

    # Full-sequence perplexity (not just next-token)
    original_nll = 0.0
    patched_nll = 0.0
    n_tokens = len(seq_ids) - 1

    for t in range(n_tokens):
        next_token = seq_ids[t + 1]
        original_nll -= original_log_probs[t, next_token].item()
        patched_nll -= patched_log_probs[t, next_token].item()

    original_ppl = np.exp(original_nll / max(n_tokens, 1))
    patched_ppl = np.exp(patched_nll / max(n_tokens, 1))
    ppl_ratio = patched_ppl / max(original_ppl, 1e-10)

    # KL divergence at target position
    pos = target_pos
    orig_probs = torch.softmax(original_logits[0, pos], dim=-1)
    patch_probs = torch.softmax(patched_logits[0, pos], dim=-1)

    kl_div = F.kl_div(
        patch_probs.log().unsqueeze(0),
        orig_probs.unsqueeze(0),
        reduction="sum",
    ).item()

    # Wider context window: ±5 tokens to catch long-range syntactic effects
    context_range = range(
        max(0, pos - 5),
        min(len(seq_ids), pos + 6),
    )
    max_prob_change = 0.0
    for t in context_range:
        orig_p = torch.softmax(original_logits[0, t], dim=-1)
        patch_p = torch.softmax(patched_logits[0, t], dim=-1)
        diff = (orig_p - patch_p).abs().max().item()
        max_prob_change = max(max_prob_change, diff)

    return {
        "kl_divergence": kl_div,
        "max_prob_change": max_prob_change,
        "perplexity_ratio": ppl_ratio,
        "original_ppl": original_ppl,
        "patched_ppl": patched_ppl,
    }


def run_single_intervention(
    model: nn.Module,
    tokenizer,
    pair: InterventionPair,
    U_k: np.ndarray,
    target_layer_idx: int,
    device: torch.device,
    kl_threshold: Optional[float] = None,
    pair_idx: int = 0,
) -> Dict:
    """Run a single interchange intervention with two control baselines.

    Runs FOUR forward passes:
        1. Original (no patch)           — baseline
        2. Identity control              — swap A's own subspace back in
        3. Random subspace control       — swap B's projection through a
           random orthonormal basis of the same dimensionality k
        4. Structural patch (real)       — swap B's structural subspace into A

    **Causal specificity** requires that the real patch KL significantly
    exceeds BOTH the identity control AND the random subspace control.
    This rules out both numerical noise (identity) and general perturbation
    sensitivity (random).

    Returns dict with structural_flip, fluency_preserved, and detailed metrics.
    """
    from scripts.causal_subspace.data_collection import _find_transformer_blocks

    blocks = _find_transformer_blocks(model)
    target_block = blocks[target_layer_idx]

    U_k_t = torch.tensor(U_k, dtype=torch.float32, device=device)
    d, k = U_k.shape

    # Build random orthonormal basis of same shape for the random control
    U_rand = _random_orthonormal_basis(d, k, seed=pair_idx)
    U_rand_t = torch.tensor(U_rand, dtype=torch.float32, device=device)

    # --- Run sequence B to get donor hidden state ---
    ids_b = torch.tensor([pair.seq_b_ids], dtype=torch.long, device=device)

    donor_captured = {}

    def capture_hook(module, inp, out):
        h = out[0] if isinstance(out, tuple) else out
        donor_captured["h"] = h.detach()

    handle = target_block.register_forward_hook(capture_hook)
    with torch.no_grad():
        model(input_ids=ids_b)
    handle.remove()

    donor_h = donor_captured["h"][0, pair.target_pos_b, :].to(device)  # [d]

    # --- Run sequence A to get its own hidden state (for controls) ---
    ids_a = torch.tensor([pair.seq_a_ids], dtype=torch.long, device=device)

    self_captured = {}

    def self_capture_hook(module, inp, out):
        h = out[0] if isinstance(out, tuple) else out
        self_captured["h"] = h.detach()

    handle = target_block.register_forward_hook(self_capture_hook)
    with torch.no_grad():
        original_output = model(input_ids=ids_a)
    handle.remove()

    original_logits = original_output.logits if hasattr(original_output, "logits") else original_output["logits"]
    self_h = self_captured["h"][0, pair.target_pos_a, :].to(device)  # [d]

    # --- Control A: Identity patch (swap A's own subspace back in) ---
    control_hook = _PatchHook(U_k_t, self_h, pair.target_pos_a)
    handle = target_block.register_forward_hook(control_hook)
    with torch.no_grad():
        control_output = model(input_ids=ids_a)
    handle.remove()
    control_logits = control_output.logits if hasattr(control_output, "logits") else control_output["logits"]

    # --- Control B: Random subspace patch (swap B's projection through ---
    #     a random orthonormal basis of the same dimensionality)
    random_hook = _PatchHook(U_rand_t, donor_h, pair.target_pos_a)
    handle = target_block.register_forward_hook(random_hook)
    with torch.no_grad():
        random_output = model(input_ids=ids_a)
    handle.remove()
    random_logits = random_output.logits if hasattr(random_output, "logits") else random_output["logits"]

    # --- Real patch: swap B's structural subspace into A ---
    patch_hook = _PatchHook(U_k_t, donor_h, pair.target_pos_a)
    handle = target_block.register_forward_hook(patch_hook)
    with torch.no_grad():
        patched_output = model(input_ids=ids_a)
    handle.remove()
    patched_logits = patched_output.logits if hasattr(patched_output, "logits") else patched_output["logits"]

    # --- Compute metrics for all three interventions ---
    control_metrics = _compute_logit_metrics(
        original_logits, control_logits, pair.seq_a_ids, pair.target_pos_a,
    )
    random_metrics = _compute_logit_metrics(
        original_logits, random_logits, pair.seq_a_ids, pair.target_pos_a,
    )
    real_metrics = _compute_logit_metrics(
        original_logits, patched_logits, pair.seq_a_ids, pair.target_pos_a,
    )

    # --- Structural flip detection (requires specificity over BOTH controls) ---
    if kl_threshold is not None:
        effective_threshold = kl_threshold
    else:
        # Threshold: must exceed both identity and random controls
        identity_floor = max(control_metrics["kl_divergence"] * 3.0, 0.01)
        random_floor = max(random_metrics["kl_divergence"] * 1.5, 0.01)
        effective_threshold = max(identity_floor, random_floor)

    structural_flip = (
        real_metrics["kl_divergence"] > effective_threshold
        or real_metrics["max_prob_change"] > max(
            control_metrics["max_prob_change"] * 3.0,
            random_metrics["max_prob_change"] * 1.5,
            0.03,
        )
    )

    # Fluency: perplexity ratio still bounded
    fluency_preserved = real_metrics["perplexity_ratio"] < 2.0

    return {
        "structural_flip": structural_flip,
        "fluency_preserved": fluency_preserved,
        # Real patch metrics
        "kl_divergence": real_metrics["kl_divergence"],
        "max_prob_change": real_metrics["max_prob_change"],
        "perplexity_ratio": real_metrics["perplexity_ratio"],
        "original_ppl": real_metrics["original_ppl"],
        "patched_ppl": real_metrics["patched_ppl"],
        # Identity control metrics (null baseline — numerical noise)
        "control_kl": control_metrics["kl_divergence"],
        "control_max_prob_change": control_metrics["max_prob_change"],
        "control_ppl_ratio": control_metrics["perplexity_ratio"],
        # Random subspace control metrics (perturbation sensitivity baseline)
        "random_kl": random_metrics["kl_divergence"],
        "random_max_prob_change": random_metrics["max_prob_change"],
        "random_ppl_ratio": random_metrics["perplexity_ratio"],
        "effective_threshold": effective_threshold,
    }


# ---------------------------------------------------------------------------
# Main intervention pipeline
# ---------------------------------------------------------------------------

def run_causal_intervention(
    model: nn.Module,
    tokenizer,
    U_k: np.ndarray,
    target_layer: int,
    cfg: InterventionConfig,
) -> InterventionResult:
    """Run the full causal interchange intervention protocol.

    Parameters
    ----------
    model : nn.Module  (frozen pretrained model)
    tokenizer : HuggingFace tokenizer
    U_k : np.ndarray [d, k]  (structural subspace basis)
    target_layer : int
    cfg : InterventionConfig

    Returns
    -------
    InterventionResult
    """
    device = torch.device(cfg.device)
    model.to(device)
    model.eval()

    pairs = generate_intervention_pairs(tokenizer, cfg.n_pairs, cfg.seed)

    result = InterventionResult(layer_idx=target_layer)
    result.n_pairs_tested = len(pairs)

    # Phase 1: Run all pairs to collect control & random KL statistics
    control_kls: List[float] = []
    random_kls: List[float] = []
    real_kls: List[float] = []

    for i, pair in enumerate(pairs):
        try:
            detail = run_single_intervention(
                model, tokenizer, pair, U_k, target_layer, device,
                pair_idx=i,
            )
        except Exception as e:
            logger.warning("Pair %d failed: %s", i, e)
            continue

        result.pair_details.append(detail)
        control_kls.append(detail.get("control_kl", 0.0))
        random_kls.append(detail.get("random_kl", 0.0))
        real_kls.append(detail.get("kl_divergence", 0.0))

    # Phase 2: Compute adaptive threshold from BOTH control distributions
    # Real flips must exceed mean + 3*std of identity control KL
    # AND demonstrate specificity over random subspace control
    if control_kls:
        result.control_kl_mean = float(np.mean(control_kls))
        result.control_kl_std = float(np.std(control_kls))
        identity_threshold = result.control_kl_mean + 3.0 * result.control_kl_std
    else:
        identity_threshold = 0.01

    if random_kls:
        result.random_kl_mean = float(np.mean(random_kls))
        result.random_kl_std = float(np.std(random_kls))
        random_threshold = result.random_kl_mean + 2.0 * result.random_kl_std
    else:
        random_threshold = 0.01

    # Adaptive threshold: must exceed both identity noise floor and random
    # perturbation sensitivity baseline
    result.adaptive_kl_threshold = max(
        identity_threshold,
        random_threshold,
        0.01,  # absolute floor
    )

    # Specificity ratio: how much more does the structural patch shift
    # outputs compared to a random subspace patch?  >1 means specific.
    if result.random_kl_mean > 1e-10 and real_kls:
        result.specificity_ratio = float(np.mean(real_kls)) / result.random_kl_mean
    else:
        result.specificity_ratio = 0.0

    logger.info(
        "Control baselines: identity KL=%.4f±%.4f, random KL=%.4f±%.4f, "
        "specificity_ratio=%.2f, adaptive_threshold=%.4f",
        result.control_kl_mean, result.control_kl_std,
        result.random_kl_mean, result.random_kl_std,
        result.specificity_ratio,
        result.adaptive_kl_threshold,
    )

    # Phase 3: Re-evaluate flips using the adaptive threshold
    # A flip is only real if the structural patch KL exceeds the threshold
    # derived from BOTH control distributions
    for detail in result.pair_details:
        real_kl = detail.get("kl_divergence", 0.0)
        real_prob = detail.get("max_prob_change", 0.0)
        control_prob = detail.get("control_max_prob_change", 0.0)
        random_prob = detail.get("random_max_prob_change", 0.0)

        structural_flip = (
            real_kl > result.adaptive_kl_threshold
            or real_prob > max(control_prob * 3.0, random_prob * 1.5, 0.03)
        )
        detail["structural_flip"] = structural_flip

        if structural_flip:
            result.n_structural_flips += 1
        if detail.get("fluency_preserved", False):
            result.n_fluency_preserved += 1
        if structural_flip and detail.get("fluency_preserved", False):
            result.n_causal_successes += 1

    n = max(result.n_pairs_tested, 1)
    result.flip_rate = result.n_structural_flips / n
    result.fluency_rate = result.n_fluency_preserved / n
    result.causal_success_rate = result.n_causal_successes / n

    logger.info(
        "Causal intervention [layer=%d]: %d pairs, "
        "flip_rate=%.1f%%, fluency_rate=%.1f%%, causal_success=%.1f%% "
        "(adaptive_threshold=%.4f, specificity=%.2fx)",
        target_layer, result.n_pairs_tested,
        result.flip_rate * 100,
        result.fluency_rate * 100,
        result.causal_success_rate * 100,
        result.adaptive_kl_threshold,
        result.specificity_ratio,
    )

    return result
