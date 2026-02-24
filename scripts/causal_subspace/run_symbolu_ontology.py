#!/usr/bin/env python3
"""
Ontology Alignment Evaluation for SymbolU Models
=================================================

Runs the ontology alignment discovery pipeline (Phase 1 / Phase 2 / Phase 3)
on a trained SymbolU model checkpoint instead of GPT-2.

This tests whether the SymbolU ontological hybrid model — which has ontology
*engineered into its architecture* (12D OntologicalBridge, R-Matrix, Bhava) —
produces richer alignment than GPT-2's emergent 4-axis result.

Key questions this answers:
    1. Do more than 4 of the 12 external axes survive the naming ceremony?
    2. Does the engineered 12D bridge correlate with the 12 external axes?
    3. Does the model hit Scenario A (Isomorphic) instead of GPT-2's Scenario B?
    4. Is CKA non-zero? (GPT-2 had CKA ≈ 0)
    5. Does causal success improve with ontological grounding?

Phase 3 (SymbolU-specific, NEW):
    - Compare the OntologicalBridge's 12D output against the 12 external axes
    - Measure MI between each bridge dimension (O1–O12) and each external axis
    - Determine if the engineered ontology captures what the external axes measure

Usage::

    # Phase 1: Discovery on a trained SymbolU checkpoint
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-phase1 --output results_symbolu.json

    # Phase 1 + 2: Full observatory + injection
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-phase1 --run-phase2 --output results_symbolu.json

    # Phase 3: Bridge alignment (requires Phase 1)
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-phase1 --run-phase3 --output results_symbolu.json

    # Hybrid health eval only (anchor + learned refinement)
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-hybrid --output results_hybrid.json

    # Hybrid with custom loss weights
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-hybrid --hybrid-alpha 1.0 --hybrid-beta 0.2 --hybrid-gamma 0.1

    # Full pipeline (all phases + hybrid health), quick mode
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-all --quick --output results_symbolu.json

    # Compare with GPT-2 baseline
    python scripts/causal_subspace/run_symbolu_ontology.py \\
        --checkpoint checkpoints/best.pt \\
        --run-all --compare-gpt2 --output comparison.json

Author: SymbolU Team
Date: 2026-02-24
"""

from __future__ import annotations

import os

# Prevent OpenBLAS/MKL thread deadlocks
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure project root is on path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import torch
import torch.nn as nn

from scripts.causal_subspace.ontology_alignment import (
    AXIS_NAMES,
    N_AXES,
    N_ROBUST,
    ROBUST_AXES,
    ROBUST_AXIS_INDICES,
    DiscoveryResult,
    MultiLayerDiscoveryResult,
    OntologyConfig,
    OntologyInjector,
    OntologyMonitor,
    Phase2Result,
    build_ontology_vectors,
    classify_scenario,
    compute_alignment_mi,
    compute_cka,
    compute_subspace_overlap,
    measure_discriminability,
    run_multi_layer_discovery,
    run_naming_ceremony,
    run_ontology_discovery,
    run_phase2,
)

logger = logging.getLogger("symbolu_ontology")


# ---------------------------------------------------------------------------
# Phase 3 result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BridgeAlignmentResult:
    """Phase 3: Alignment between OntologicalBridge 12D and external 12 axes."""

    # Per bridge-dim × external-axis MI matrix
    bridge_axis_mi: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Best matching external axis for each bridge dimension
    bridge_best_axis: Dict[str, str] = field(default_factory=dict)
    bridge_best_mi: Dict[str, float] = field(default_factory=dict)

    # Global alignment between bridge 12D and external 12D
    global_mi: float = 0.0
    global_cka: float = 0.0

    # How many bridge dims have a meaningful external counterpart (MI > threshold)
    n_aligned_dims: int = 0
    aligned_dims: List[str] = field(default_factory=list)

    # Comparison: bridge-as-predictor vs hidden-state-as-predictor
    bridge_role_accuracy: float = 0.0
    hidden_role_accuracy: float = 0.0
    bridge_discriminability_gap: float = 0.0


# ---------------------------------------------------------------------------
# Hybrid Health Result
# ---------------------------------------------------------------------------

@dataclass
class HybridHealthResult:
    """Hybrid Anchor + Learned Refinement evaluation.

    Measures the three-part loss decomposition:
        L = α·L_alignment + β·L_diversity + γ·L_entropy

    And classifies the hybrid health scenario:
        A (Healthy Alignment): 6-8 axes correlated, structured but not rigid
        B (Partial Drift):     Model reinterprets 2-3 axes beyond heuristics
        C (Collapse):          Multiple axes map to same PCA direction, MI low
    """

    # --- Loss decomposition (computed on bridge output vs external axes) ---
    L_alignment: float = 0.0       # MSE between bridge 12D and external 12D (lower = better)
    L_diversity: float = 0.0       # 1 - normalized entropy of axis activations (0 = diverse)
    L_entropy: float = 0.0         # Mean per-token entropy deficit (0 = balanced)
    L_total: float = 0.0           # α·L_alignment + β·L_diversity + γ·L_entropy
    alpha: float = 1.0
    beta: float = 0.1
    gamma: float = 0.05

    # --- Per-axis alignment ---
    per_axis_alignment: Dict[str, float] = field(default_factory=dict)  # MSE per axis
    per_axis_corr: Dict[str, float] = field(default_factory=dict)       # Pearson r per axis
    per_axis_deviation: Dict[str, float] = field(default_factory=dict)  # Where bridge != anchor

    # --- Diversity metrics ---
    axis_entropy: float = 0.0           # Entropy of mean axis activations (bits)
    max_entropy: float = 0.0            # log2(12) = max possible
    axis_covariance_penalty: float = 0.0  # Off-diagonal cov magnitude (orthogonality)
    collapsed_axes: List[str] = field(default_factory=list)  # Axes with near-zero variance

    # --- Entropy balance ---
    per_token_entropy_mean: float = 0.0   # Mean entropy across tokens
    per_token_entropy_std: float = 0.0    # Std of per-token entropy (uniformity)
    dominant_axis_fraction: float = 0.0   # Fraction of tokens where one axis > 50%

    # --- Hybrid health classification ---
    scenario: str = "C"                    # A (Healthy) / B (Partial Drift) / C (Collapse)
    scenario_confidence: float = 0.0
    n_strongly_aligned: int = 0            # Axes with r > 0.5
    n_partially_aligned: int = 0           # Axes with 0.2 < r < 0.5
    n_drifted: int = 0                     # Axes where bridge deviates meaningfully
    n_collapsed: int = 0                   # Axes with near-zero variance

    # --- Deviation analysis ---
    drift_axes: List[str] = field(default_factory=list)      # Axes where bridge > anchor
    drift_descriptions: Dict[str, str] = field(default_factory=dict)  # Why each drifted

    # --- Expected training trajectory markers ---
    alignment_saturated: bool = False      # CKA ≈ 1.0 → overfitting to heuristics
    geometry_random: bool = False           # CKA ≈ 0.0 → no alignment at all
    structured_nonlinear: bool = False     # 0.2 < CKA < 0.8 → ideal hybrid zone


# ---------------------------------------------------------------------------
# SymbolU Model Loader
# ---------------------------------------------------------------------------

def _load_symbolu_model(
    checkpoint_path: Optional[str],
    model_type: str = "ontological_hybrid",
    model_size: str = "small",
    device: Optional[str] = None,
    vocab_size: int = 50257,
    override_n_layer: Optional[int] = None,
    override_n_head: Optional[int] = None,
    override_n_embd: Optional[int] = None,
) -> Tuple[nn.Module, Dict[str, Any]]:
    """Load a SymbolU model from checkpoint, or create a fresh one.

    When checkpoint_path is None (or the file does not exist), the model is
    created with random initialization.  This is useful for measuring the
    architectural prior before any training has occurred.

    Returns (model, config_dict) where config_dict has model architecture info.
    """
    from train_unified_llm import MODEL_PRESETS

    # Determine architecture from preset or overrides
    preset = MODEL_PRESETS.get(model_size, MODEL_PRESETS["small"])
    embed_dim = override_n_embd or preset["embed_dim"]
    num_layers = override_n_layer or preset["num_layers"]
    num_heads = override_n_head or preset["num_heads"]

    config_dict = {
        "model_type": model_type,
        "model_size": model_size,
        "embed_dim": embed_dim,
        "num_layers": num_layers,
        "num_heads": num_heads,
        "vocab_size": vocab_size,
        "from_checkpoint": False,
    }

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device_t = torch.device(device)

    # Load checkpoint if provided and exists
    checkpoint = None
    if checkpoint_path and os.path.isfile(checkpoint_path):
        logger.info("Loading checkpoint: %s", checkpoint_path)
        checkpoint = torch.load(checkpoint_path, map_location=device_t, weights_only=False)
        config_dict["from_checkpoint"] = True

        # Try to infer model type from checkpoint
        if "config" in checkpoint:
            saved_cfg = checkpoint["config"]
            if isinstance(saved_cfg, dict):
                config_dict["model_type"] = saved_cfg.get("model_type", model_type)
                config_dict["model_size"] = saved_cfg.get("model_size", model_size)
                config_dict["embed_dim"] = saved_cfg.get("embed_dim", embed_dim)
                config_dict["num_layers"] = saved_cfg.get("num_layers", num_layers)
                config_dict["num_heads"] = saved_cfg.get("num_heads", num_heads)
                config_dict["vocab_size"] = saved_cfg.get("vocab_size", vocab_size)
    else:
        if checkpoint_path:
            logger.warning("Checkpoint not found: %s — using random initialization", checkpoint_path)
        else:
            logger.info("No checkpoint specified — using random initialization")

    # Create model using the factory function
    try:
        from train_unified_llm import UnifiedTrainingConfig, create_model
        training_cfg = UnifiedTrainingConfig(
            model_type=config_dict["model_type"],
            model_size=config_dict["model_size"],
            vocab_size=config_dict["vocab_size"],
        )
        # Apply overrides
        if override_n_embd:
            training_cfg.n_embd = override_n_embd
        if override_n_layer:
            training_cfg.n_layer = override_n_layer
        if override_n_head:
            training_cfg.n_head = override_n_head

        model = create_model(training_cfg, device_t)
    except Exception as e:
        logger.warning("create_model failed (%s), trying direct construction", e)
        # Fallback: construct model directly
        from symbolu.phase_transformer import HybridPhaseTransformer
        model = HybridPhaseTransformer(
            vocab_size=config_dict["vocab_size"],
            embed_dim=config_dict["embed_dim"],
            num_layers=config_dict["num_layers"],
            num_heads=config_dict["num_heads"],
        )

    # Load weights from checkpoint if available
    if checkpoint is not None:
        state_dict_key = "model_state_dict" if "model_state_dict" in checkpoint else "state_dict"
        if state_dict_key in checkpoint:
            try:
                model.load_state_dict(checkpoint[state_dict_key], strict=False)
                logger.info("Loaded model weights (strict=False)")
            except Exception as e:
                logger.warning("Could not load state dict: %s", e)
        else:
            logger.warning("No state_dict found in checkpoint, using initialized weights")
    else:
        logger.info("Using randomly initialized weights (no checkpoint)")

    model.to(device_t)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    logger.info(
        "Model loaded: %s (%s), %d layers, %d-dim, %.1fM params%s",
        config_dict["model_type"],
        config_dict["model_size"],
        config_dict["num_layers"],
        config_dict["embed_dim"],
        sum(p.numel() for p in model.parameters()) / 1e6,
        "" if config_dict["from_checkpoint"] else " [random init]",
    )

    return model, config_dict


# ---------------------------------------------------------------------------
# Data Collection for SymbolU models
# ---------------------------------------------------------------------------

def _collect_symbolu_hidden_states(
    model: nn.Module,
    config_dict: Dict[str, Any],
    max_sequences: int = 500,
    max_seq_len: int = 256,
    batch_size: int = 8,
    device: Optional[str] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Collect hidden states from a SymbolU model on WikiText data.

    Returns a dict with:
        - states: {layer_idx: np.ndarray [N, d]}
        - tokens: list[str]
        - sequence_ids: np.ndarray [N]
        - d_model: int
        - n_layers: int
        - bridge_output: np.ndarray [N, 12] (if OntologicalBridge exists)
    """
    from train_unified_llm import HiddenStateExtractor

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    device_t = torch.device(device)
    num_layers = config_dict["num_layers"]
    embed_dim = config_dict["embed_dim"]

    # Load tokenizer (with robust fallback)
    tokenizer = None
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
    except Exception:
        pass

    if tokenizer is None:
        from train_unified_llm import _SimpleByteTokenizer
        tokenizer = _SimpleByteTokenizer()
        logger.info("Using byte-level fallback tokenizer (HF tokenizer unavailable)")

    # Load WikiText data
    logger.info("Loading WikiText data (%d sequences, max_len=%d)...", max_sequences, max_seq_len)
    try:
        from datasets import load_dataset
        dataset = load_dataset("wikitext", "wikitext-103-raw-v1", split="train")
        texts = []
        for item in dataset:
            text = item["text"].strip()
            if len(text) > 50:
                texts.append(text)
                if len(texts) >= max_sequences:
                    break
    except Exception:
        logger.warning("Could not load WikiText, generating synthetic data")
        rng = np.random.RandomState(seed)
        texts = [
            "The cat sat on the mat and looked out the window at the birds.",
            "Scientists discovered a new species of deep-sea fish in the Pacific Ocean.",
            "The economy showed signs of recovery after the prolonged downturn.",
        ] * (max_sequences // 3 + 1)
        texts = texts[:max_sequences]

    # Setup hidden state extraction
    extractor = HiddenStateExtractor(model, num_layers=num_layers)

    # Check if model has OntologicalBridge
    has_bridge = hasattr(model, 'onto_bridge') and model.onto_bridge is not None
    bridge_outputs = [] if has_bridge else None

    # Collect hidden states
    all_states = {l: [] for l in range(num_layers)}
    all_tokens = []
    all_seq_ids = []

    np.random.seed(seed)
    torch.manual_seed(seed)

    logger.info("Running forward passes...")
    seq_id = 0
    for batch_start in range(0, len(texts), batch_size):
        batch_texts = texts[batch_start:batch_start + batch_size]

        # Tokenize
        if hasattr(tokenizer, 'encode_plus'):
            encoded = tokenizer(
                batch_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_seq_len,
            )
            input_ids = encoded["input_ids"].to(device_t)
        else:
            # Fallback for simple tokenizer
            ids_list = []
            for text in batch_texts:
                ids = tokenizer.encode(text)[:max_seq_len]
                ids_list.append(ids)
            max_len = max(len(ids) for ids in ids_list)
            padded = [ids + [0] * (max_len - len(ids)) for ids in ids_list]
            input_ids = torch.tensor(padded, dtype=torch.long, device=device_t)

        # Forward pass
        extractor.clear()
        with torch.no_grad():
            try:
                output = model(input_ids, return_hidden=True)
            except TypeError:
                # Model may not support return_hidden
                try:
                    output = model(input_ids, extract_layers=list(range(num_layers)))
                except TypeError:
                    output = model(input_ids)

        # Extract hidden states
        hidden_states = extractor.get_hidden_states(
            output if isinstance(output, dict) else {"logits": output},
            input_ids,
        )

        # Extract bridge output if available
        if has_bridge and isinstance(output, dict):
            bridge_repr = output.get("onto_repr", None)
            if bridge_repr is not None:
                # [B, seq, 12] → flatten to [B*seq, 12]
                bridge_flat = bridge_repr.detach().cpu().numpy().reshape(-1, 12)
            else:
                # Try running bridge manually on layer 9 hidden state
                try:
                    l9_idx = min(8, num_layers - 1)  # Layer 9 = index 8
                    if l9_idx < len(hidden_states) and hidden_states[l9_idx] is not None:
                        bridge_repr, _ = model.onto_bridge(hidden_states[l9_idx])
                        bridge_flat = bridge_repr.detach().cpu().numpy().reshape(-1, 12)
                    else:
                        bridge_flat = None
                except Exception:
                    bridge_flat = None
        else:
            bridge_flat = None

        # Flatten batch × seq → tokens
        B, T = input_ids.shape
        for b in range(B):
            for t in range(T):
                tok_id = input_ids[b, t].item()
                if tok_id == 0:  # Skip padding
                    continue

                # Decode token
                try:
                    tok_str = tokenizer.decode([tok_id])
                except Exception:
                    tok_str = f"<{tok_id}>"

                all_tokens.append(tok_str)
                all_seq_ids.append(seq_id)

                for l in range(num_layers):
                    if l < len(hidden_states) and hidden_states[l] is not None:
                        h = hidden_states[l]
                        if h.dim() == 3:
                            all_states[l].append(h[b, t].cpu().numpy())
                        elif h.dim() == 2:
                            all_states[l].append(h[b].cpu().numpy())

                if bridge_flat is not None:
                    flat_idx = b * T + t
                    if flat_idx < bridge_flat.shape[0]:
                        bridge_outputs.append(bridge_flat[flat_idx])

            seq_id += 1

        if (batch_start // batch_size + 1) % 10 == 0:
            logger.info(
                "  Processed %d/%d sequences (%d tokens so far)",
                min(batch_start + batch_size, len(texts)),
                len(texts),
                len(all_tokens),
            )

    # Stack into arrays
    states_np = {}
    for l in range(num_layers):
        if all_states[l]:
            states_np[l] = np.stack(all_states[l], axis=0).astype(np.float32)
        else:
            logger.warning("No hidden states captured for layer %d", l)

    result = {
        "states": states_np,
        "tokens": all_tokens,
        "sequence_ids": np.array(all_seq_ids),
        "d_model": embed_dim,
        "n_layers": num_layers,
    }

    if bridge_outputs:
        result["bridge_output"] = np.stack(bridge_outputs, axis=0).astype(np.float32)
        logger.info("Bridge output captured: %s", result["bridge_output"].shape)

    logger.info(
        "Data collection complete: %d tokens, %d layers, %d-dim",
        len(all_tokens), len(states_np), embed_dim,
    )

    return result


# ---------------------------------------------------------------------------
# Structural Labels (reuse existing pipeline)
# ---------------------------------------------------------------------------

def _annotate_tokens(
    tokens: List[str],
    sequence_ids: np.ndarray,
    states: Dict[int, np.ndarray],
) -> Any:
    """Run structural annotation on collected tokens.

    Returns StructuralAnnotations from the existing pipeline.
    """
    from scripts.causal_subspace.structural_labels import annotate_structural_labels

    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
    except Exception:
        tokenizer = None

    annotations = annotate_structural_labels(
        token_strings=tokens,
        sequence_ids=sequence_ids,
        hidden_states=states,
        tokenizer=tokenizer,
    )
    return annotations


# ---------------------------------------------------------------------------
# Hybrid Health Evaluation
# ---------------------------------------------------------------------------

def run_hybrid_health_eval(
    bridge_output: np.ndarray,
    ont_features: np.ndarray,
    valid_mask: np.ndarray,
    alpha: float = 1.0,
    beta: float = 0.1,
    gamma: float = 0.05,
    strong_threshold: float = 0.5,
    partial_threshold: float = 0.2,
    collapse_var_threshold: float = 0.01,
    n_bins: int = 20,
) -> HybridHealthResult:
    """Evaluate the hybrid anchor + learned refinement health.

    Measures the three-loss decomposition that governs the OntologicalBridge:
        L = α·L_alignment + β·L_diversity + γ·L_entropy

    Then classifies hybrid health:
        A (Healthy):       6+ axes strongly aligned, CKA in [0.2, 0.8]
        B (Partial Drift): 3-5 strong, 2+ drifted (bridge reinterprets)
        C (Collapse):      <3 aligned, or axes collapsed to same direction

    Parameters
    ----------
    bridge_output : np.ndarray [N, 12]
        OntologicalBridge output for each token.
    ont_features : np.ndarray [N, 12]
        Static external 12-axis ontology vectors.
    valid_mask : np.ndarray [N] bool
        Which tokens have valid annotations.
    alpha, beta, gamma : float
        Loss weights for alignment, diversity, entropy.
    strong_threshold : float
        Pearson r threshold for "strongly aligned" (default 0.5).
    partial_threshold : float
        Pearson r threshold for "partially aligned" (default 0.2).
    collapse_var_threshold : float
        Variance threshold below which an axis is "collapsed".
    n_bins : int
        Bins for MI estimation.
    """
    from scripts.causal_subspace.ontology_alignment import _compute_binned_mi

    result = HybridHealthResult(alpha=alpha, beta=beta, gamma=gamma)

    bridge_valid = bridge_output[valid_mask]
    ont_valid = ont_features[valid_mask]
    N = bridge_valid.shape[0]

    if N < 20:
        logger.warning("Too few valid tokens (%d) for hybrid eval", N)
        return result

    logger.info("Hybrid health eval: N=%d valid tokens", N)

    # ===================================================================
    # L_alignment: Per-axis MSE + Pearson correlation
    # ===================================================================
    # Normalize both to [0, 1] range for fair comparison
    def _safe_normalize(x: np.ndarray) -> np.ndarray:
        mn, mx = x.min(axis=0), x.max(axis=0)
        rng = mx - mn
        rng[rng < 1e-10] = 1.0
        return (x - mn) / rng

    bridge_norm = _safe_normalize(bridge_valid)
    ont_norm = _safe_normalize(ont_valid)

    per_axis_mse = np.mean((bridge_norm - ont_norm) ** 2, axis=0)  # [12]
    result.L_alignment = float(per_axis_mse.mean())

    for i, name in enumerate(AXIS_NAMES):
        result.per_axis_alignment[name] = float(per_axis_mse[i])

        # Pearson correlation per axis
        b_col = bridge_valid[:, i]
        o_col = ont_valid[:, i]
        b_std, o_std = b_col.std(), o_col.std()
        if b_std > 1e-8 and o_std > 1e-8:
            r = float(np.corrcoef(b_col, o_col)[0, 1])
            if np.isnan(r):
                r = 0.0
        else:
            r = 0.0
        result.per_axis_corr[name] = r

        # Deviation: where bridge meaningfully disagrees with anchor
        # Use residual MSE after accounting for linear fit
        if b_std > 1e-8 and o_std > 1e-8:
            # Residual after best linear fit
            coeffs = np.polyfit(o_col, b_col, 1)
            predicted = np.polyval(coeffs, o_col)
            residual_var = np.var(b_col - predicted)
            total_var = np.var(b_col)
            deviation = residual_var / max(total_var, 1e-10)
        else:
            deviation = 1.0
        result.per_axis_deviation[name] = float(deviation)

    logger.info("  L_alignment = %.4f (mean MSE across 12 axes)", result.L_alignment)

    # ===================================================================
    # L_diversity: Axis specialization / orthogonality
    # ===================================================================
    aspect_means = np.mean(np.abs(bridge_valid), axis=0)  # [12]
    aspect_probs = aspect_means / (aspect_means.sum() + 1e-10)
    axis_entropy = -np.sum(aspect_probs * np.log2(aspect_probs + 1e-10))
    max_ent = np.log2(12)
    result.axis_entropy = float(axis_entropy)
    result.max_entropy = float(max_ent)
    result.L_diversity = float(1.0 - axis_entropy / max_ent)  # 0 = perfectly diverse

    # Covariance penalty: off-diagonal magnitude
    cov_matrix = np.cov(bridge_valid.T)  # [12, 12]
    diag_mask = ~np.eye(12, dtype=bool)
    off_diag = np.abs(cov_matrix[diag_mask])
    result.axis_covariance_penalty = float(off_diag.mean())

    # Collapsed axes: variance too low
    axis_vars = np.var(bridge_valid, axis=0)
    for i, name in enumerate(AXIS_NAMES):
        if axis_vars[i] < collapse_var_threshold:
            result.collapsed_axes.append(name)
    result.n_collapsed = len(result.collapsed_axes)

    logger.info("  L_diversity = %.4f (entropy=%.2f/%.2f bits, cov_penalty=%.4f)",
                result.L_diversity, result.axis_entropy, result.max_entropy,
                result.axis_covariance_penalty)
    if result.collapsed_axes:
        logger.info("  Collapsed axes: %s", ", ".join(result.collapsed_axes))

    # ===================================================================
    # L_entropy: Per-token axis balance
    # ===================================================================
    # For each token, compute entropy of its 12D activation distribution
    token_abs = np.abs(bridge_valid) + 1e-10  # [N, 12]
    token_probs = token_abs / token_abs.sum(axis=1, keepdims=True)
    token_entropies = -np.sum(token_probs * np.log2(token_probs), axis=1)  # [N]

    result.per_token_entropy_mean = float(token_entropies.mean())
    result.per_token_entropy_std = float(token_entropies.std())

    # Entropy deficit: how far below max entropy
    entropy_deficit = max_ent - token_entropies.mean()
    result.L_entropy = float(max(0.0, entropy_deficit / max_ent))

    # Dominant axis fraction: tokens where one axis > 50% of total activation
    max_frac = token_probs.max(axis=1)  # [N]
    result.dominant_axis_fraction = float(np.mean(max_frac > 0.5))

    logger.info("  L_entropy = %.4f (token_entropy=%.2f±%.2f, dominant_frac=%.1f%%)",
                result.L_entropy, result.per_token_entropy_mean,
                result.per_token_entropy_std, result.dominant_axis_fraction * 100)

    # ===================================================================
    # Total loss
    # ===================================================================
    result.L_total = (alpha * result.L_alignment +
                      beta * result.L_diversity +
                      gamma * result.L_entropy)

    logger.info("  L_total = %.4f (α=%.2f, β=%.2f, γ=%.2f)",
                result.L_total, alpha, beta, gamma)

    # ===================================================================
    # Classify axes: strongly aligned / partially aligned / drifted
    # ===================================================================
    for name in AXIS_NAMES:
        r = result.per_axis_corr[name]
        dev = result.per_axis_deviation[name]

        if r >= strong_threshold:
            result.n_strongly_aligned += 1
        elif r >= partial_threshold:
            result.n_partially_aligned += 1

        # Drift: bridge correlates moderately but deviation is high
        # (it's capturing something the heuristic doesn't)
        if r >= partial_threshold and dev > 0.5:
            result.n_drifted += 1
            result.drift_axes.append(name)
            result.drift_descriptions[name] = (
                f"r={r:.3f} but residual_dev={dev:.3f} — bridge encodes "
                f"beyond heuristic {name.split('_')[1].lower()}"
            )

    logger.info("  Axis classification: %d strong, %d partial, %d drifted, %d collapsed",
                result.n_strongly_aligned, result.n_partially_aligned,
                result.n_drifted, result.n_collapsed)

    # ===================================================================
    # Hybrid health scenario classification
    # ===================================================================
    cka = float(compute_cka(bridge_valid, ont_valid))

    # CKA regime detection
    result.alignment_saturated = cka > 0.95   # Near-perfect = just regressing to heuristics
    result.geometry_random = cka < 0.05       # No alignment at all
    result.structured_nonlinear = 0.2 <= cka <= 0.95  # Ideal hybrid zone

    total_meaningful = result.n_strongly_aligned + result.n_partially_aligned

    # Scenario A (Healthy Alignment):
    #   6+ strong axes AND total meaningful (strong+partial) >= 8
    #   This means most of the ontology is embedded, possibly with some
    #   partial alignment on abstract axes (O9-O12). Not brittle.
    n_weak = 12 - total_meaningful
    if (result.n_strongly_aligned >= 6 and
            total_meaningful >= 8 and
            result.n_collapsed <= 2 and
            not result.geometry_random):
        result.scenario = "A"
        result.scenario_confidence = min(1.0, total_meaningful / 10.0)
    # Scenario B (Partial Drift):
    #   3+ strong axes but total meaningful < 8, OR drift detected
    #   Mid-training or bridge is reinterpreting some axes
    elif (result.n_strongly_aligned >= 3 and
          not result.geometry_random):
        result.scenario = "B"
        result.scenario_confidence = min(1.0, total_meaningful / 8.0)
    else:
        result.scenario = "C"
        # Confidence scales with how far from healthy
        result.scenario_confidence = max(0.0, 1.0 - total_meaningful / 6.0)

    scenario_names = {
        "A": "Healthy Alignment",
        "B": "Partial Drift (good hybrid behavior)",
        "C": "Collapse / Pre-training",
    }
    logger.info("  Hybrid scenario: %s — %s (confidence=%.2f, CKA=%.4f)",
                result.scenario, scenario_names[result.scenario],
                result.scenario_confidence, cka)

    if result.drift_axes:
        logger.info("  Drifted axes (bridge reinterpretation):")
        for ax in result.drift_axes:
            logger.info("    %s: %s", ax, result.drift_descriptions[ax])

    if result.alignment_saturated:
        logger.warning("  WARNING: CKA=%.3f — bridge may be overfitting to heuristics", cka)
    if result.geometry_random:
        logger.warning("  WARNING: CKA=%.3f — no alignment, α may be too low or bridge untrained", cka)

    return result


# ---------------------------------------------------------------------------
# Phase 3: Bridge Alignment Analysis
# ---------------------------------------------------------------------------

def run_phase3_bridge_alignment(
    bridge_output: np.ndarray,
    ont_features: np.ndarray,
    valid_mask: np.ndarray,
    H: np.ndarray,
    labels: np.ndarray,
    mi_threshold: float = 0.1,
    n_bins: int = 20,
) -> BridgeAlignmentResult:
    """Phase 3: Measure alignment between OntologicalBridge 12D and external axes.

    This is unique to SymbolU — GPT-2 has no bridge.

    Parameters
    ----------
    bridge_output : np.ndarray [N, 12]
        OntologicalBridge output (O1–O12 dimensions).
    ont_features : np.ndarray [N, 12]
        External 12-axis ontology vectors from Phase 1.
    valid_mask : np.ndarray [N] bool
        Which tokens have valid ontology features.
    H : np.ndarray [N, d]
        Hidden states for discriminability comparison.
    labels : np.ndarray [N]
        Grammatical role labels.
    mi_threshold : float
        Threshold for considering a bridge-axis pair as aligned.
    n_bins : int
        Bins for MI estimation.

    Returns
    -------
    BridgeAlignmentResult with alignment metrics.
    """
    from scripts.causal_subspace.ontology_alignment import _compute_binned_mi
    from train_unified_llm import ONTOLOGICAL_LAYER_NAMES

    result = BridgeAlignmentResult()

    # Filter to valid tokens
    bridge_valid = bridge_output[valid_mask]
    ont_valid = ont_features[valid_mask]
    H_valid = H[valid_mask]
    labels_valid = labels[valid_mask]

    N = bridge_valid.shape[0]
    if N < 20:
        logger.warning("Too few valid tokens (%d) for Phase 3", N)
        return result

    logger.info("Phase 3: Bridge alignment analysis (N=%d valid tokens)", N)

    # --- Per bridge-dim × external-axis MI matrix ---
    bridge_dim_names = [name.split("_", 1)[1] if "_" in name else name
                        for name in ONTOLOGICAL_LAYER_NAMES]

    for b_idx in range(min(12, bridge_valid.shape[1])):
        b_name = bridge_dim_names[b_idx] if b_idx < len(bridge_dim_names) else f"bridge_{b_idx}"
        result.bridge_axis_mi[b_name] = {}

        best_mi = 0.0
        best_axis = ""

        for a_idx in range(min(12, ont_valid.shape[1])):
            a_name = AXIS_NAMES[a_idx]
            mi = _compute_binned_mi(bridge_valid[:, b_idx], ont_valid[:, a_idx], n_bins)
            result.bridge_axis_mi[b_name][a_name] = float(mi)

            if mi > best_mi:
                best_mi = mi
                best_axis = a_name

        result.bridge_best_axis[b_name] = best_axis
        result.bridge_best_mi[b_name] = best_mi

        status = "ALIGNED" if best_mi > mi_threshold else "unaligned"
        logger.info(
            "  Bridge %s → best external axis: %s (MI=%.4f) [%s]",
            b_name, best_axis, best_mi, status,
        )

    # Count aligned dimensions
    result.aligned_dims = [
        name for name, mi in result.bridge_best_mi.items()
        if mi > mi_threshold
    ]
    result.n_aligned_dims = len(result.aligned_dims)

    # --- Global alignment ---
    n_dims = min(bridge_valid.shape[1], ont_valid.shape[1])
    result.global_cka = compute_cka(bridge_valid[:, :n_dims], ont_valid[:, :n_dims])
    logger.info("  Global CKA (bridge vs external): %.4f", result.global_cka)

    # Global MI using PCA
    from sklearn.decomposition import PCA
    n_comp = min(3, N - 1, n_dims)
    if n_comp >= 1:
        pca_bridge = PCA(n_components=n_comp).fit_transform(bridge_valid[:, :n_dims])
        pca_ext = PCA(n_components=n_comp).fit_transform(ont_valid[:, :n_dims])
        best_global_mi = 0.0
        for i in range(n_comp):
            for j in range(n_comp):
                mi = _compute_binned_mi(pca_bridge[:, i], pca_ext[:, j], n_bins)
                best_global_mi = max(best_global_mi, mi)
        result.global_mi = best_global_mi
        logger.info("  Global MI (bridge vs external): %.4f", result.global_mi)

    # --- Discriminability: bridge 12D vs hidden states for role classification ---
    logger.info("  Running discriminability: bridge vs hidden states...")
    disc_bridge = measure_discriminability(
        bridge_valid[:, :n_dims], H_valid, labels_valid,
        n_bootstrap=10, ci=0.95, seed=42,
    )
    result.bridge_role_accuracy = disc_bridge["ontology_accuracy"]
    result.hidden_role_accuracy = disc_bridge["embedding_accuracy"]
    result.bridge_discriminability_gap = disc_bridge["gap"]

    logger.info(
        "  Discriminability: bridge=%.1f%%, hidden=%.1f%%, gap=%.1f%%",
        result.bridge_role_accuracy * 100,
        result.hidden_role_accuracy * 100,
        result.bridge_discriminability_gap * 100,
    )

    logger.info(
        "Phase 3 complete: %d/%d bridge dims aligned, CKA=%.4f, MI=%.4f",
        result.n_aligned_dims, n_dims, result.global_cka, result.global_mi,
    )

    return result


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_symbolu_ontology_pipeline(
    checkpoint_path: Optional[str],
    model_type: str = "ontological_hybrid",
    model_size: str = "small",
    max_sequences: int = 500,
    max_seq_len: int = 256,
    batch_size: int = 8,
    run_phase1: bool = True,
    run_phase2_flag: bool = False,
    run_phase3_flag: bool = False,
    run_hybrid_flag: bool = False,
    phase2_epochs: int = 100,
    ontology_mi_threshold: float = 0.1,
    subspace_k: int = 16,
    compare_gpt2: bool = False,
    hybrid_alpha: float = 1.0,
    hybrid_beta: float = 0.1,
    hybrid_gamma: float = 0.05,
    device: Optional[str] = None,
    seed: int = 42,
    override_n_layer: Optional[int] = None,
    override_n_head: Optional[int] = None,
    override_n_embd: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the full ontology alignment evaluation on a SymbolU model.

    Returns a dict containing all results.
    """
    # Auto-detect GPU
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    results: Dict[str, Any] = {
        "model": "symbolu",
        "checkpoint": checkpoint_path,
        "device": device,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    t0 = time.time()

    # ===================================================================
    # STEP 1: Load Model
    # ===================================================================
    print("\n" + "=" * 70)
    print(f"STEP 1: LOADING SYMBOLU MODEL  [device: {device}]")
    print("=" * 70)

    model, config_dict = _load_symbolu_model(
        checkpoint_path=checkpoint_path,
        model_type=model_type,
        model_size=model_size,
        device=device,
        override_n_layer=override_n_layer,
        override_n_head=override_n_head,
        override_n_embd=override_n_embd,
    )
    results["model_config"] = config_dict
    init_mode = "from checkpoint" if config_dict["from_checkpoint"] else "random init"
    print(f"  Model: {config_dict['model_type']} ({config_dict['model_size']}) [{init_mode}]")
    print(f"  Architecture: {config_dict['num_layers']}L / {config_dict['embed_dim']}D / "
          f"{config_dict['num_heads']}H")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M")
    if checkpoint_path:
        print(f"  Checkpoint: {checkpoint_path}")

    has_bridge = hasattr(model, 'onto_bridge') and model.onto_bridge is not None
    print(f"  OntologicalBridge: {'Present' if has_bridge else 'Not present'}")

    # ===================================================================
    # STEP 2: Collect Hidden States
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 2: COLLECTING HIDDEN STATES")
    print("=" * 70)

    data = _collect_symbolu_hidden_states(
        model=model,
        config_dict=config_dict,
        max_sequences=max_sequences,
        max_seq_len=max_seq_len,
        batch_size=batch_size,
        device=device,
        seed=seed,
    )

    print(f"  Tokens collected: {len(data['tokens'])}")
    print(f"  Layers captured: {len(data['states'])}")
    if "bridge_output" in data:
        print(f"  Bridge output: {data['bridge_output'].shape}")

    results["data_collection"] = {
        "n_tokens": len(data["tokens"]),
        "n_layers": data["n_layers"],
        "d_model": data["d_model"],
        "has_bridge_output": "bridge_output" in data,
    }

    # ===================================================================
    # STEP 3: Structural Label Alignment
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 3: STRUCTURAL LABEL ALIGNMENT")
    print("=" * 70)

    annotations = _annotate_tokens(
        tokens=data["tokens"],
        sequence_ids=data["sequence_ids"],
        states=data["states"],
    )

    print(f"  Words annotated: {len(annotations.words)}")
    print(f"  Sentences: {annotations.n_sentences}")

    results["annotations"] = {
        "n_words": len(annotations.words),
        "n_sentences": annotations.n_sentences,
    }

    # ===================================================================
    # STEP 4: MDL Probing (for PCA basis)
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 4: MDL PROBING (PCA BASIS EXTRACTION)")
    print("=" * 70)

    from scripts.causal_subspace.mdl_probing import (
        MDLProbeConfig,
        run_mdl_probe,
        select_top_k_components,
    )
    from scripts.causal_subspace.causal_intervention import build_pca_basis

    mdl_cfg = MDLProbeConfig(n_portions=10, seed=seed, device=device)

    # Find crystallization layer (best MDL compression)
    best_compression = 0.0
    best_layer = 0
    mdl_results = {}

    active_layers = sorted(data["states"].keys())
    for layer_idx in active_layers:
        H = annotations.hidden_states[layer_idx]
        r = run_mdl_probe(H, annotations.labels_role, layer_idx, "grammatical_role", mdl_cfg)
        mdl_results[layer_idx] = {
            "compression_ratio": r.compression_ratio,
            "bits_per_label": r.online_code_length / max(r.n_samples, 1),
        }
        if r.compression_ratio > best_compression:
            best_compression = r.compression_ratio
            best_layer = layer_idx

    print(f"  MDL compression ratios:")
    for l in active_layers:
        marker = " ***" if l == best_layer else ""
        print(f"    Layer {l}: {mdl_results[l]['compression_ratio']:.2f}x "
              f"({mdl_results[l]['bits_per_label']:.3f} bits/label){marker}")

    print(f"\n  Crystallization layer: L{best_layer} (compression={best_compression:.2f}x)")

    # Build PCA basis at crystallization layer
    H_crystal = annotations.hidden_states[best_layer]
    candidate_dims = [8, 16, 32, 64]
    try:
        optimal_k_result = select_top_k_components(
            H_crystal, annotations.labels_role,
            best_layer, "grammatical_role", candidate_dims, mdl_cfg,
        )
        # select_top_k_components returns (optimal_k, results_list, pca_basis)
        if isinstance(optimal_k_result, tuple):
            optimal_k = optimal_k_result[0]
        else:
            optimal_k = optimal_k_result
    except Exception as e:
        logger.warning("select_top_k_components failed: %s, using default k=%d", e, subspace_k)
        optimal_k = subspace_k
    optimal_k = max(optimal_k, subspace_k)
    pca_basis = build_pca_basis(H_crystal, optimal_k)

    print(f"  PCA basis: k={optimal_k} (from L{best_layer})")

    results["mdl_probing"] = {
        "per_layer": mdl_results,
        "crystallization_layer": best_layer,
        "peak_compression": best_compression,
        "pca_k": optimal_k,
    }

    # ===================================================================
    # PHASE 1: Ontology Discovery
    # ===================================================================
    ontology_result: Optional[MultiLayerDiscoveryResult] = None
    ont_features_cache = {}  # Cache for Phase 2/3

    if run_phase1:
        print("\n" + "=" * 70)
        print("PHASE 1: ONTOLOGY ALIGNMENT DISCOVERY")
        print("=" * 70)

        ont_cfg = OntologyConfig(
            naming_mi_threshold=ontology_mi_threshold,
            device=device,
            seed=seed,
        )

        # Run at multiple layers: crystallization + middle + last
        discovery_layers = sorted(set([
            best_layer,
            config_dict["num_layers"] // 2,    # Middle layer
            config_dict["num_layers"] - 1,      # Last layer
        ]))
        discovery_layers = [l for l in discovery_layers if l in data["states"]]

        print(f"  Discovery layers: {discovery_layers}")

        # Build hidden states dict for discovery layers
        discovery_hidden = {}
        for l in discovery_layers:
            if l in annotations.hidden_states:
                discovery_hidden[l] = annotations.hidden_states[l]

        ontology_result = run_multi_layer_discovery(
            annotations=annotations,
            hidden_states=discovery_hidden,
            labels=annotations.labels_role,
            U_k=pca_basis,
            layers=discovery_layers,
            cfg=ont_cfg,
        )

        # Print results
        print(f"\n  --- Phase 1 Results ---")
        print(f"  Overall scenario: {ontology_result.scenario}")
        print(f"  Recommended Phase 2: {ontology_result.recommended_phase2}")
        print(f"  Validated axes ({ontology_result.n_validated_axes}/12): "
              f"{', '.join(ontology_result.all_validated_axes) or '(none)'}")
        print(f"  Best alignment layer: L{ontology_result.best_alignment_layer}")
        print(f"  Dissociation: {ontology_result.dissociation}")

        for layer_idx in sorted(ontology_result.per_layer.keys()):
            r = ontology_result.per_layer[layer_idx]
            print(f"\n  Layer {layer_idx}:")
            print(f"    Scenario: {r.scenario} (confidence={r.scenario_confidence:.2f})")
            print(f"    MI: {r.alignment_mi:.4f}, CKA: {r.cka_similarity:.4f}")
            print(f"    Validated: {r.n_validated_axes}/12 ({', '.join(r.validated_axes) or 'none'})")
            print(f"    Discriminability gap: {r.discriminability_gap:.1%}")

            # Per-axis MI table
            print(f"    Per-axis MI:")
            for axis_name in AXIS_NAMES:
                mi = r.per_axis_mi.get(axis_name, 0.0)
                status = "PASS" if mi > ontology_mi_threshold else "fail"
                pca_dir = r.per_axis_best_pca.get(axis_name, -1)
                print(f"      [{status:4s}] {axis_name:25s}: MI={mi:.4f} (PCA dir={pca_dir})")

        # Cache ontology features for Phase 2/3
        read_layer = ontology_result.best_alignment_layer
        if read_layer in annotations.hidden_states:
            H_read = annotations.hidden_states[read_layer]
            ont_feat, valid_mask = build_ontology_vectors(
                annotations.words, H_read, annotations.labels_role,
            )
            ont_features_cache = {
                "ont_features": ont_feat,
                "valid_mask": valid_mask,
                "read_layer": read_layer,
                "H_read": H_read,
            }

        results["phase1"] = {
            "scenario": ontology_result.scenario,
            "recommended_phase2": ontology_result.recommended_phase2,
            "n_validated_axes": ontology_result.n_validated_axes,
            "validated_axes": ontology_result.all_validated_axes,
            "best_alignment_layer": ontology_result.best_alignment_layer,
            "dissociation": ontology_result.dissociation,
            "per_layer": {},
        }
        for layer_idx, r in ontology_result.per_layer.items():
            results["phase1"]["per_layer"][layer_idx] = {
                "scenario": r.scenario,
                "alignment_mi": r.alignment_mi,
                "cka_similarity": r.cka_similarity,
                "n_validated_axes": r.n_validated_axes,
                "validated_axes": r.validated_axes,
                "per_axis_mi": r.per_axis_mi,
                "discriminability_gap": r.discriminability_gap,
                "ontology_role_accuracy": r.ontology_role_accuracy,
                "embedding_role_accuracy": r.embedding_role_accuracy,
                "concat_role_accuracy": r.concat_role_accuracy,
            }

    # ===================================================================
    # PHASE 2: Observatory + Injection
    # ===================================================================
    if run_phase2_flag:
        if not ont_features_cache:
            print("\n  Phase 2 requires Phase 1. Skipping.")
        else:
            print("\n" + "=" * 70)
            print("PHASE 2: OBSERVATORY + INJECTION PROTOTYPE")
            print("=" * 70)

            read_layer = ont_features_cache["read_layer"]
            H_read = ont_features_cache["H_read"]
            ont_features = ont_features_cache["ont_features"]
            valid_mask = ont_features_cache["valid_mask"]

            print(f"  Monitor read layer: L{read_layer}")
            print(f"  Training epochs: {phase2_epochs}")

            phase2_result = run_phase2(
                annotations=annotations,
                hidden_states={read_layer: H_read},
                labels=annotations.labels_role,
                ont_features=ont_features,
                valid_mask=valid_mask,
                read_layer=read_layer,
                n_epochs=phase2_epochs,
                seed=seed,
            )

            print(f"\n  --- Phase 2 Results ---")
            print(f"  Monitor R² (mean): {phase2_result.monitor_r2_mean:.3f}")
            for axis, r2 in phase2_result.monitor_r2_per_axis.items():
                print(f"    {axis}: R²={r2:.3f}")

            print(f"\n  Injector classifications:")
            for test in phase2_result.injector_test_results:
                print(f"    '{test['input'][:40]}...'")
                print(f"      → {test['domain']}/{test['structure']}/{test['intent']}")

            results["phase2"] = {
                "monitor_r2_mean": phase2_result.monitor_r2_mean,
                "monitor_r2_per_axis": phase2_result.monitor_r2_per_axis,
                "monitor_train_loss": phase2_result.monitor_train_loss,
                "monitor_val_loss": phase2_result.monitor_val_loss,
                "injector_test_results": phase2_result.injector_test_results,
            }

    # ===================================================================
    # PHASE 3: Bridge Alignment (SymbolU-specific)
    # ===================================================================
    if run_phase3_flag:
        if "bridge_output" not in data:
            print("\n  Phase 3 requires OntologicalBridge output. "
                  "Model has no bridge or bridge output was not captured. Skipping.")
        elif not ont_features_cache:
            print("\n  Phase 3 requires Phase 1 ontology vectors. Skipping.")
        else:
            print("\n" + "=" * 70)
            print("PHASE 3: BRIDGE ALIGNMENT (SYMBOLU-SPECIFIC)")
            print("=" * 70)

            bridge_output = data["bridge_output"]
            ont_features = ont_features_cache["ont_features"]
            valid_mask = ont_features_cache["valid_mask"]
            H_read = ont_features_cache["H_read"]

            # Ensure shapes match
            n_tokens = min(bridge_output.shape[0], ont_features.shape[0],
                           H_read.shape[0], len(valid_mask))
            bridge_output = bridge_output[:n_tokens]
            ont_features = ont_features[:n_tokens]
            valid_mask = valid_mask[:n_tokens]
            H_read = H_read[:n_tokens]
            labels = annotations.labels_role[:n_tokens]

            bridge_result = run_phase3_bridge_alignment(
                bridge_output=bridge_output,
                ont_features=ont_features,
                valid_mask=valid_mask,
                H=H_read,
                labels=labels,
                mi_threshold=ontology_mi_threshold,
            )

            print(f"\n  --- Phase 3 Results ---")
            print(f"  Bridge dims aligned: {bridge_result.n_aligned_dims}/12")
            print(f"  Global CKA (bridge vs external): {bridge_result.global_cka:.4f}")
            print(f"  Global MI (bridge vs external): {bridge_result.global_mi:.4f}")
            print(f"  Bridge role accuracy: {bridge_result.bridge_role_accuracy:.1%}")
            print(f"  Hidden role accuracy: {bridge_result.hidden_role_accuracy:.1%}")

            print(f"\n  Bridge dimension → Best external axis:")
            from train_unified_llm import ONTOLOGICAL_LAYER_NAMES
            for b_name in bridge_result.bridge_best_axis:
                ext_axis = bridge_result.bridge_best_axis[b_name]
                mi = bridge_result.bridge_best_mi[b_name]
                status = "ALIGNED" if mi > ontology_mi_threshold else "unaligned"
                print(f"    {b_name:20s} → {ext_axis:25s} MI={mi:.4f} [{status}]")

            results["phase3"] = {
                "n_aligned_dims": bridge_result.n_aligned_dims,
                "aligned_dims": bridge_result.aligned_dims,
                "global_cka": bridge_result.global_cka,
                "global_mi": bridge_result.global_mi,
                "bridge_role_accuracy": bridge_result.bridge_role_accuracy,
                "hidden_role_accuracy": bridge_result.hidden_role_accuracy,
                "bridge_discriminability_gap": bridge_result.bridge_discriminability_gap,
                "bridge_best_axis": bridge_result.bridge_best_axis,
                "bridge_best_mi": bridge_result.bridge_best_mi,
                "bridge_axis_mi": bridge_result.bridge_axis_mi,
            }

    # ===================================================================
    # HYBRID HEALTH: Anchor + Learned Refinement Evaluation
    # ===================================================================
    if run_hybrid_flag:
        if "bridge_output" not in data and not ont_features_cache:
            print("\n  Hybrid eval requires bridge output OR Phase 1 ontology vectors. Skipping.")
        else:
            print("\n" + "=" * 70)
            print("HYBRID HEALTH: ANCHOR + LEARNED REFINEMENT EVALUATION")
            print("=" * 70)
            print(f"  Loss weights: α={hybrid_alpha}, β={hybrid_beta}, γ={hybrid_gamma}")
            print(f"  L = α·L_alignment + β·L_diversity + γ·L_entropy")

            ont_features = ont_features_cache["ont_features"]
            valid_mask = ont_features_cache["valid_mask"]

            if "bridge_output" in data:
                # Use actual OntologicalBridge output
                bridge_for_hybrid = data["bridge_output"]
                hybrid_source = "OntologicalBridge"
            else:
                # No bridge — use top-12 PCA directions as proxy
                # This lets us evaluate hybrid health even before bridge is trained
                from sklearn.decomposition import PCA
                H_read = ont_features_cache["H_read"]
                pca_12 = PCA(n_components=12).fit_transform(H_read)
                bridge_for_hybrid = pca_12
                hybrid_source = "PCA-12 proxy (no bridge)"

            print(f"  Source: {hybrid_source}")

            # Align shapes
            n_tokens = min(bridge_for_hybrid.shape[0], ont_features.shape[0],
                           len(valid_mask))
            bridge_for_hybrid = bridge_for_hybrid[:n_tokens]
            ont_features_h = ont_features[:n_tokens]
            valid_mask_h = valid_mask[:n_tokens]

            hybrid_result = run_hybrid_health_eval(
                bridge_output=bridge_for_hybrid,
                ont_features=ont_features_h,
                valid_mask=valid_mask_h,
                alpha=hybrid_alpha,
                beta=hybrid_beta,
                gamma=hybrid_gamma,
            )

            # Print results
            scenario_names = {
                "A": "Healthy Alignment",
                "B": "Partial Drift (good hybrid behavior)",
                "C": "Collapse / Pre-training",
            }

            print(f"\n  --- Hybrid Health Results ---")
            print(f"  Scenario: {hybrid_result.scenario} — "
                  f"{scenario_names.get(hybrid_result.scenario, '?')} "
                  f"(confidence={hybrid_result.scenario_confidence:.2f})")
            print(f"\n  Loss decomposition:")
            print(f"    L_alignment = {hybrid_result.L_alignment:.4f} "
                  f"(α·L = {hybrid_alpha * hybrid_result.L_alignment:.4f})")
            print(f"    L_diversity = {hybrid_result.L_diversity:.4f} "
                  f"(β·L = {hybrid_beta * hybrid_result.L_diversity:.4f})")
            print(f"    L_entropy   = {hybrid_result.L_entropy:.4f} "
                  f"(γ·L = {hybrid_gamma * hybrid_result.L_entropy:.4f})")
            print(f"    L_total     = {hybrid_result.L_total:.4f}")

            print(f"\n  Axis diversity:")
            print(f"    Entropy: {hybrid_result.axis_entropy:.2f} / {hybrid_result.max_entropy:.2f} bits")
            print(f"    Covariance penalty: {hybrid_result.axis_covariance_penalty:.4f}")
            if hybrid_result.collapsed_axes:
                print(f"    COLLAPSED: {', '.join(hybrid_result.collapsed_axes)}")

            print(f"\n  Token-level entropy balance:")
            print(f"    Mean entropy: {hybrid_result.per_token_entropy_mean:.2f} bits")
            print(f"    Entropy std:  {hybrid_result.per_token_entropy_std:.2f}")
            print(f"    Dominant axis fraction: {hybrid_result.dominant_axis_fraction:.1%}")

            print(f"\n  Axis classification:")
            print(f"    Strongly aligned (r≥0.5):  {hybrid_result.n_strongly_aligned}")
            print(f"    Partially aligned (r≥0.2): {hybrid_result.n_partially_aligned}")
            print(f"    Drifted (reinterpreted):   {hybrid_result.n_drifted}")
            print(f"    Collapsed (var≈0):         {hybrid_result.n_collapsed}")

            print(f"\n  Per-axis detail:")
            print(f"    {'Axis':25s} {'r':>8s} {'MSE':>8s} {'Dev':>8s} {'Status'}")
            print(f"    {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*20}")
            for name in AXIS_NAMES:
                r = hybrid_result.per_axis_corr.get(name, 0.0)
                mse = hybrid_result.per_axis_alignment.get(name, 0.0)
                dev = hybrid_result.per_axis_deviation.get(name, 0.0)
                if name in hybrid_result.collapsed_axes:
                    status = "COLLAPSED"
                elif name in hybrid_result.drift_axes:
                    status = "DRIFTED"
                elif r >= 0.5:
                    status = "STRONG"
                elif r >= 0.2:
                    status = "PARTIAL"
                else:
                    status = "weak"
                print(f"    {name:25s} {r:>8.3f} {mse:>8.4f} {dev:>8.3f} {status}")

            if hybrid_result.drift_axes:
                print(f"\n  Drift analysis (bridge reinterpretation beyond heuristics):")
                for ax in hybrid_result.drift_axes:
                    print(f"    {ax}: {hybrid_result.drift_descriptions[ax]}")

            # CKA regime
            regime = "IDEAL (structured nonlinear)" if hybrid_result.structured_nonlinear else \
                     "SATURATED (overfitting to heuristics)" if hybrid_result.alignment_saturated else \
                     "RANDOM (no alignment)" if hybrid_result.geometry_random else "intermediate"
            print(f"\n  CKA regime: {regime}")

            # Store results
            results["hybrid_health"] = {
                "scenario": hybrid_result.scenario,
                "scenario_confidence": hybrid_result.scenario_confidence,
                "source": hybrid_source,
                "L_alignment": hybrid_result.L_alignment,
                "L_diversity": hybrid_result.L_diversity,
                "L_entropy": hybrid_result.L_entropy,
                "L_total": hybrid_result.L_total,
                "alpha": hybrid_alpha,
                "beta": hybrid_beta,
                "gamma": hybrid_gamma,
                "axis_entropy": hybrid_result.axis_entropy,
                "max_entropy": hybrid_result.max_entropy,
                "axis_covariance_penalty": hybrid_result.axis_covariance_penalty,
                "collapsed_axes": hybrid_result.collapsed_axes,
                "per_token_entropy_mean": hybrid_result.per_token_entropy_mean,
                "per_token_entropy_std": hybrid_result.per_token_entropy_std,
                "dominant_axis_fraction": hybrid_result.dominant_axis_fraction,
                "n_strongly_aligned": hybrid_result.n_strongly_aligned,
                "n_partially_aligned": hybrid_result.n_partially_aligned,
                "n_drifted": hybrid_result.n_drifted,
                "n_collapsed": hybrid_result.n_collapsed,
                "drift_axes": hybrid_result.drift_axes,
                "per_axis_corr": hybrid_result.per_axis_corr,
                "per_axis_alignment": hybrid_result.per_axis_alignment,
                "per_axis_deviation": hybrid_result.per_axis_deviation,
                "alignment_saturated": hybrid_result.alignment_saturated,
                "geometry_random": hybrid_result.geometry_random,
                "structured_nonlinear": hybrid_result.structured_nonlinear,
            }

    # ===================================================================
    # OPTIONAL: GPT-2 Comparison
    # ===================================================================
    if compare_gpt2:
        print("\n" + "=" * 70)
        print("GPT-2 BASELINE COMPARISON")
        print("=" * 70)

        from scripts.causal_subspace.run_pipeline import run_full_pipeline

        print("  Running GPT-2 pipeline (this may take several minutes)...")
        gpt2_results = run_full_pipeline(
            model_name="gpt2",
            max_sequences=max_sequences,
            max_seq_len=max_seq_len,
            batch_size=batch_size,
            run_ontology=True,
            run_phase2_flag=run_phase2_flag,
            phase2_epochs=phase2_epochs,
            ontology_mi_threshold=ontology_mi_threshold,
            device=device,
            seed=seed,
        )

        results["gpt2_comparison"] = {
            "gpt2_ontology": gpt2_results.get("ontology_alignment", {}),
            "gpt2_phase2": gpt2_results.get("phase2", {}),
        }

        # Print comparison table
        if "ontology_alignment" in gpt2_results and ontology_result is not None:
            gpt2_ont = gpt2_results["ontology_alignment"]
            print(f"\n  {'Metric':<35s} {'SymbolU':>12s} {'GPT-2':>12s} {'Delta':>12s}")
            print(f"  {'-'*35} {'-'*12} {'-'*12} {'-'*12}")

            su_n = ontology_result.n_validated_axes
            g2_n = gpt2_ont.get("n_validated_axes", 0)
            print(f"  {'Validated axes':35s} {su_n:>12d} {g2_n:>12d} {su_n - g2_n:>+12d}")

            su_scenario = ontology_result.scenario
            g2_scenario = gpt2_ont.get("scenario", "?")
            print(f"  {'Scenario':35s} {su_scenario:>12s} {g2_scenario:>12s}")

            # Per-layer MI comparison
            su_best = ontology_result.best_alignment_layer
            if su_best in ontology_result.per_layer:
                su_mi = ontology_result.per_layer[su_best].alignment_mi
                g2_mi_data = gpt2_ont.get("per_layer", {})
                g2_mi = max((v.get("alignment_mi", 0) for v in g2_mi_data.values()), default=0)
                print(f"  {'Best MI':35s} {su_mi:>12.4f} {g2_mi:>12.4f} {su_mi - g2_mi:>+12.4f}")

            su_axes = set(ontology_result.all_validated_axes)
            g2_axes = set(gpt2_ont.get("validated_axes", []))
            new_axes = su_axes - g2_axes
            if new_axes:
                print(f"\n  NEW axes validated by SymbolU (not in GPT-2): {', '.join(new_axes)}")

    # ===================================================================
    # FINAL REPORT
    # ===================================================================
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)

    print(f"\n  Model: {config_dict['model_type']} ({config_dict['model_size']}) [{init_mode}]")
    if checkpoint_path:
        print(f"  Checkpoint: {checkpoint_path}")
    print(f"  Tokens analyzed: {len(data['tokens'])}")

    if ontology_result:
        scenario_names = {"A": "Isomorphic", "B": "Partial Overlap",
                          "C": "Orthogonal", "D": "Complementary"}
        sname = scenario_names.get(ontology_result.scenario, ontology_result.scenario)
        print(f"\n  Phase 1: Scenario {ontology_result.scenario} ({sname})")
        print(f"    Validated axes: {ontology_result.n_validated_axes}/12")
        print(f"    Axes: {', '.join(ontology_result.all_validated_axes) or 'none'}")

    if "phase2" in results:
        print(f"\n  Phase 2: Monitor R²={results['phase2']['monitor_r2_mean']:.3f}")

    if "phase3" in results:
        print(f"\n  Phase 3: {results['phase3']['n_aligned_dims']}/12 bridge dims aligned")
        print(f"    CKA={results['phase3']['global_cka']:.4f}, "
              f"MI={results['phase3']['global_mi']:.4f}")

    if "hybrid_health" in results:
        hh = results["hybrid_health"]
        hybrid_scenario_names = {
            "A": "Healthy Alignment",
            "B": "Partial Drift",
            "C": "Collapse/Pre-training",
        }
        print(f"\n  Hybrid Health: Scenario {hh['scenario']} "
              f"({hybrid_scenario_names.get(hh['scenario'], '?')})")
        print(f"    L_total={hh['L_total']:.4f} "
              f"(align={hh['L_alignment']:.4f}, "
              f"div={hh['L_diversity']:.4f}, "
              f"ent={hh['L_entropy']:.4f})")
        print(f"    Axes: {hh['n_strongly_aligned']} strong, "
              f"{hh['n_partially_aligned']} partial, "
              f"{hh['n_drifted']} drifted, "
              f"{hh['n_collapsed']} collapsed")

    print(f"\n  Total elapsed: {elapsed:.1f}s")
    print("=" * 70)

    results["elapsed_seconds"] = elapsed
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Ontology Alignment Evaluation for SymbolU Models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Phase 1 discovery on a checkpoint
  python scripts/causal_subspace/run_symbolu_ontology.py \\
      --checkpoint checkpoints/best.pt --run-phase1

  # All three phases
  python scripts/causal_subspace/run_symbolu_ontology.py \\
      --checkpoint checkpoints/best.pt --run-all

  # Quick smoke test
  python scripts/causal_subspace/run_symbolu_ontology.py \\
      --checkpoint checkpoints/best.pt --run-all --quick

  # Compare with GPT-2
  python scripts/causal_subspace/run_symbolu_ontology.py \\
      --checkpoint checkpoints/best.pt --run-all --compare-gpt2

  # No checkpoint — evaluate random-init architecture priors
  python scripts/causal_subspace/run_symbolu_ontology.py \\
      --no-checkpoint --model-type ontological_hybrid --model-size small --run-all
        """,
    )

    # Checkpoint (optional — omit or use --no-checkpoint for random init)
    parser.add_argument(
        "--checkpoint", type=str, default=None,
        help="Path to trained SymbolU model checkpoint (.pt file). "
             "Omit or use --no-checkpoint to evaluate with random initialization.",
    )
    parser.add_argument(
        "--no-checkpoint", action="store_true",
        help="Evaluate a randomly initialized model (no trained weights). "
             "Useful for measuring the architecture's structural prior.",
    )

    # Model architecture
    parser.add_argument(
        "--model-type", type=str, default="ontological_hybrid",
        choices=["ontological", "phase", "hybrid", "gen2", "standard",
                 "ontological_hybrid", "binding_cache", "ontological_binding_cache"],
        help="Model architecture type (default: ontological_hybrid)",
    )
    parser.add_argument(
        "--model-size", type=str, default="small",
        choices=["tiny", "small", "medium", "large"],
        help="Model size preset (default: small)",
    )
    parser.add_argument("--n-layer", type=int, default=None, help="Override num_layers")
    parser.add_argument("--n-head", type=int, default=None, help="Override num_heads")
    parser.add_argument("--n-embd", type=int, default=None, help="Override embed_dim")

    # Phase control
    parser.add_argument(
        "--run-phase1", action="store_true",
        help="Run Phase 1: Ontology discovery (naming ceremony, MI, CKA, scenario)",
    )
    parser.add_argument(
        "--run-phase2", action="store_true",
        help="Run Phase 2: Observatory monitor + content injection prototype",
    )
    parser.add_argument(
        "--run-phase3", action="store_true",
        help="Run Phase 3: Bridge alignment (SymbolU-specific, requires OntologicalBridge)",
    )
    parser.add_argument(
        "--run-hybrid", action="store_true",
        help="Run Hybrid Health eval: L=α·L_alignment + β·L_diversity + γ·L_entropy",
    )
    parser.add_argument(
        "--run-all", action="store_true",
        help="Run all phases including hybrid health",
    )

    # Hybrid loss weights
    parser.add_argument(
        "--hybrid-alpha", type=float, default=1.0,
        help="Weight for alignment loss in hybrid eval (default: 1.0)",
    )
    parser.add_argument(
        "--hybrid-beta", type=float, default=0.1,
        help="Weight for diversity loss in hybrid eval (default: 0.1)",
    )
    parser.add_argument(
        "--hybrid-gamma", type=float, default=0.05,
        help="Weight for entropy loss in hybrid eval (default: 0.05)",
    )

    # Data collection
    parser.add_argument(
        "--max-sequences", type=int, default=500,
        help="Number of WikiText sequences to process (default: 500)",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=256,
        help="Max token length per sequence (default: 256)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=8,
        help="Batch size for forward passes (default: 8)",
    )

    # Ontology parameters
    parser.add_argument(
        "--ontology-mi-threshold", type=float, default=0.1,
        help="MI threshold for axis validation (default: 0.1)",
    )
    parser.add_argument(
        "--phase2-epochs", type=int, default=100,
        help="Training epochs for the ontology monitor (default: 100)",
    )
    parser.add_argument(
        "--subspace-k", type=int, default=16,
        help="Minimum PCA subspace dimensionality (default: 16)",
    )

    # Comparison
    parser.add_argument(
        "--compare-gpt2", action="store_true",
        help="Also run the pipeline on GPT-2 for side-by-side comparison",
    )

    # General
    _default_device = "cuda" if torch.cuda.is_available() else "cpu"
    parser.add_argument(
        "--device", type=str, default=_default_device,
        help=f"Device: cpu or cuda (default: auto-detected → {_default_device})",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default=None, help="Save results to JSON file")
    parser.add_argument("--quick", action="store_true", help="Quick smoke test (reduced data)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # --run-all implies all phases + hybrid
    if args.run_all:
        args.run_phase1 = True
        args.run_phase2 = True
        args.run_phase3 = True
        args.run_hybrid = True

    # --run-phase2, --run-phase3, --run-hybrid require --run-phase1
    if (args.run_phase2 or args.run_phase3 or args.run_hybrid) and not args.run_phase1:
        args.run_phase1 = True

    # Default: at least run phase1
    if not (args.run_phase1 or args.run_phase2 or args.run_phase3 or args.run_hybrid):
        args.run_phase1 = True

    # Handle checkpoint: --no-checkpoint or missing file
    checkpoint_path = args.checkpoint
    if args.no_checkpoint:
        checkpoint_path = None
    elif checkpoint_path and not os.path.isfile(checkpoint_path):
        print(f"  WARNING: Checkpoint not found: {checkpoint_path}")
        print(f"  Proceeding with random initialization (same as --no-checkpoint).")
        print(f"  This evaluates the architecture's structural prior before training.\n")
        checkpoint_path = None

    # Quick mode overrides
    if args.quick:
        args.max_sequences = min(args.max_sequences, 50)
        args.phase2_epochs = min(args.phase2_epochs, 20)

    results = run_symbolu_ontology_pipeline(
        checkpoint_path=checkpoint_path,
        model_type=args.model_type,
        model_size=args.model_size,
        max_sequences=args.max_sequences,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
        run_phase1=args.run_phase1,
        run_phase2_flag=args.run_phase2,
        run_phase3_flag=args.run_phase3,
        run_hybrid_flag=args.run_hybrid,
        phase2_epochs=args.phase2_epochs,
        ontology_mi_threshold=args.ontology_mi_threshold,
        subspace_k=args.subspace_k,
        compare_gpt2=args.compare_gpt2,
        hybrid_alpha=args.hybrid_alpha,
        hybrid_beta=args.hybrid_beta,
        hybrid_gamma=args.hybrid_gamma,
        device=args.device,
        seed=args.seed,
        override_n_layer=args.n_layer,
        override_n_head=args.n_head,
        override_n_embd=args.n_embd,
    )

    if args.output:
        output_path = Path(args.output)

        def _serialize(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (torch.Tensor,)):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=_serialize)
        print(f"\nResults saved to {output_path}")

    return results


if __name__ == "__main__":
    main()
