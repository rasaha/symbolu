#!/usr/bin/env python3
"""
eval-real-data — Evaluate bridge + governance on real LLM hidden states
========================================================================

Phase 2 evaluation: takes the .pt file produced by extract_real_states.py
and runs the full JEPA-Observatory pipeline on real hidden states:

  1. Project H → 32D Sovereign State via SovereignStateProjector
  2. Build ontology vectors from dependency parsing
  3. Train OntologyBridge (S → z_ont) and measure R²
  4. Train OntologyMonitor (H → z_ont) and compute drift scores
  5. Evaluate anomaly detection AUC per behavioral category
  6. Run governance components (coherence, mismatch, governor)
  7. Compare with synthetic baseline

The key hypothesis: R² on real data > R² on synthetic (0.36) because
real hidden states have genuine semantic structure.

Usage::

    # Basic evaluation
    python scripts/causal_subspace/eval_real_data.py \\
        --input real_hidden_states.pt

    # Full evaluation with governance + comparison
    python scripts/causal_subspace/eval_real_data.py \\
        --input real_hidden_states.pt --governance --compare-synthetic

    # GPU accelerated bridge training
    python scripts/causal_subspace/eval_real_data.py \\
        --input real_hidden_states.pt --device cuda --governance

    # Custom bridge config
    python scripts/causal_subspace/eval_real_data.py \\
        --input real_hidden_states.pt --bridge-type mlp --hidden-dim 128 \\
        --n-epochs 500

    # Save results to JSON
    python scripts/causal_subspace/eval_real_data.py \\
        --input real_hidden_states.pt --governance --output results.json
"""

from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.ontology_alignment import (
    N_AXES,
    N_ROBUST,
    ROBUST_AXES,
    ROBUST_AXIS_INDICES,
    OntologyMonitor,
)
from scripts.causal_subspace.jepa_observatory import (
    OntologyBridge,
    TrajectoryCoherenceLoss,
    TrajectoryMismatchDetector,
    MismatchEvent,
    DisagreementGovernor,
    GovernanceReport,
    compute_alignment_matrix,
    compute_detection_auc,
)
from scripts.causal_subspace.check_alignment import (
    classify_outcome,
    generate_synthetic_hidden_states,
    SOVEREIGN_DIM_NAMES,
)
# structural_labels is used internally for dep parse when spaCy is available
from scripts.causal_subspace.extract_real_states import (
    BEHAVIORAL_CATEGORIES,
    CATEGORY_TO_IDX,
)
from symbolu.jepa.state_projector import SovereignStateProjector
from symbolu.jepa.predictor import VrittiValidatedPredictor

logger = logging.getLogger("eval_real_data")


# ── Box drawing ────────────────────────────────────────────────────────────

H_LINE = "\u2500"
V_LINE = "\u2502"
TL = "\u250c"
TR = "\u2510"
BL = "\u2514"
BR = "\u2518"
T_RIGHT = "\u251c"
CHECK = "\u2713"
CROSS_MARK = "\u2717"
BAR_FULL = "\u2588"


# ── MLPBridge (same as train_bridge.py) ──────────────────────────────────

class MLPBridge(nn.Module):
    """Nonlinear bridge: Sovereign State → ontological axes via 2-layer MLP."""

    def __init__(self, state_dim: int = 32, n_axes: int = N_ROBUST, hidden_dim: int = 64):
        super().__init__()
        self.state_dim = state_dim
        self.n_axes = n_axes
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, n_axes),
            nn.Sigmoid(),
        )

    def forward(self, s: torch.Tensor) -> torch.Tensor:
        return self.net(s)

    def train_bridge(
        self,
        S: np.ndarray,
        z_ont: np.ndarray,
        n_epochs: int = 300,
        lr: float = 1e-3,
        batch_size: int = 256,
        val_split: float = 0.2,
        seed: int = 42,
    ) -> Dict[str, Any]:
        rng = np.random.RandomState(seed)
        N = S.shape[0]
        perm = rng.permutation(N)
        n_val = max(int(N * val_split), 1)
        val_idx, train_idx = perm[:n_val], perm[n_val:]

        S_train = torch.from_numpy(S[train_idx].astype(np.float32))
        z_train = torch.from_numpy(z_ont[train_idx].astype(np.float32))
        S_val = torch.from_numpy(S[val_idx].astype(np.float32))
        z_val = torch.from_numpy(z_ont[val_idx].astype(np.float32))

        optimizer = torch.optim.Adam(self.parameters(), lr=lr)
        criterion = nn.MSELoss()

        self.train()
        train_loss = 0.0
        for epoch in range(n_epochs):
            idx = torch.randperm(len(train_idx))
            epoch_loss, n_batches = 0.0, 0
            for start in range(0, len(train_idx), batch_size):
                batch_idx = idx[start:start + batch_size]
                pred = self.forward(S_train[batch_idx])
                loss = criterion(pred, z_train[batch_idx])
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1
            train_loss = epoch_loss / max(n_batches, 1)

        self.eval()
        with torch.no_grad():
            val_pred = self.forward(S_val).cpu().numpy()
            val_true = z_val.cpu().numpy()

        r2_per_axis = {}
        for i in range(self.n_axes):
            axis_name = ROBUST_AXES[i] if i < len(ROBUST_AXES) else f"axis_{i}"
            ss_res = np.sum((val_true[:, i] - val_pred[:, i]) ** 2)
            ss_tot = np.sum((val_true[:, i] - val_true[:, i].mean()) ** 2)
            r2_per_axis[axis_name] = float(1.0 - ss_res / max(ss_tot, 1e-10))

        return {
            "r2_mean": float(np.mean(list(r2_per_axis.values()))),
            "r2_per_axis": r2_per_axis,
            "train_loss": train_loss,
            "n_train": len(train_idx),
            "n_val": n_val,
        }


# ---------------------------------------------------------------------------
# Ontology vector construction for real data
# ---------------------------------------------------------------------------

def build_ontology_for_real_tokens(
    tokens: List[str],
    sentence_ids: np.ndarray,
    hidden_states: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build 12-axis ontology vectors for real tokens using dependency parsing.

    Falls back to heuristic features if spaCy is unavailable.

    Returns:
        ont_features [N, 12], valid_mask [N]
    """
    N = len(tokens)
    d_model = hidden_states.shape[1]

    # Try to use the structural_labels module for dependency parsing
    try:
        annotations = _build_via_structural_labels(tokens, sentence_ids)
        if annotations is not None:
            return annotations
    except Exception as e:
        logger.warning("Structural label parsing failed: %s. Using heuristics.", e)

    # Fallback: heuristic ontology features from token properties
    logger.info("Building heuristic ontology vectors for %d tokens...", N)
    return _heuristic_ontology_features(tokens, sentence_ids, hidden_states)


def _build_via_structural_labels(
    tokens: List[str],
    sentence_ids: np.ndarray,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Try to use spaCy-based structural labels."""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        return None

    # Reconstruct sentences from tokens
    unique_sids = np.unique(sentence_ids)
    sentences: List[str] = []
    for sid in unique_sids:
        mask = sentence_ids == sid
        sent_tokens = [tokens[i] for i in range(len(tokens)) if mask[i]]
        sentences.append("".join(sent_tokens).strip())

    if not sentences:
        return None

    # Parse with spaCy
    N = len(tokens)
    ont_features = np.zeros((N, 12), dtype=np.float32)
    valid_mask = np.ones(N, dtype=bool)

    tok_idx = 0
    for sid, sent in zip(unique_sids, sentences):
        doc = nlp(sent)
        n_sent_tokens = int((sentence_ids == sid).sum())

        for i, spacy_token in enumerate(doc):
            if tok_idx + i >= N:
                break

            dep = spacy_token.dep_
            word = spacy_token.text
            pos_norm = i / max(len(doc) - 1, 1)
            depth_norm = _dep_depth(spacy_token) / max(5.0, 1.0)

            # Build 12-axis features (same logic as ontology_alignment.py)
            ont_features[tok_idx + i] = _compute_bhava_vector(
                dep, word, pos_norm, depth_norm,
            )

        tok_idx += n_sent_tokens

    logger.info("Built ontology vectors via spaCy for %d tokens", N)
    return ont_features, valid_mask


def _dep_depth(token) -> int:
    """Compute dependency tree depth for a spaCy token."""
    depth = 0
    current = token
    while current.head != current:
        depth += 1
        current = current.head
    return depth


def _compute_bhava_vector(
    dep: str,
    word: str,
    pos_norm: float,
    depth_norm: float,
) -> np.ndarray:
    """Compute 12-axis Bhava vector for a single token."""
    vec = np.zeros(12, dtype=np.float32)

    # O1: POTENTIAL — latent capacity
    latent_deps = {"det", "mark", "case", "cc", "punct", "expl"}
    if dep in latent_deps:
        vec[0] = 0.8
    elif dep in ("aux", "auxpass"):
        vec[0] = 0.6 + 0.2 * max(0, 1 - pos_norm)
    else:
        vec[0] = 0.1 + 0.2 * max(0, 1 - pos_norm)

    # O2: IDENTITY — naming, classification
    identity_deps = {"nsubj", "nsubjpass", "nmod", "pobj", "appos", "attr"}
    if dep in identity_deps:
        vec[1] = 0.9
    elif dep in ("dobj", "iobj", "obj"):
        vec[1] = 0.7
    elif dep in ("compound", "flat", "name"):
        vec[1] = 0.8
    elif word and word[0].isupper():
        vec[1] = 0.7
    else:
        vec[1] = 0.1

    # O3: EXECUTION — action
    if dep in ("ROOT", "root"):
        vec[2] = 1.0
    elif dep in ("xcomp", "ccomp", "advcl", "relcl", "parataxis"):
        vec[2] = 0.8
    elif dep in ("aux", "auxpass"):
        vec[2] = 0.5
    else:
        vec[2] = 0.05

    # O4: STRUCTURE — form
    struct_score = depth_norm * 0.6
    if dep in ("prep", "case", "mark"):
        struct_score += 0.4
    elif dep in ("compound", "flat", "fixed"):
        struct_score += 0.3
    elif dep in ("cc", "conj"):
        struct_score += 0.2
    elif dep in ("punct",):
        struct_score += 0.3
    vec[3] = min(struct_score, 1.0)

    # O5: COGNITION — perception, emotion
    w = word.lower().strip(".,!?;:\"'()[]{}—-") if word else ""
    cognitive_words = {
        "think", "know", "believe", "feel", "see", "hear", "notice",
        "understand", "realize", "perceive", "sense", "recognize",
        "imagine", "wonder", "consider", "expect", "hope", "fear",
    }
    if w in cognitive_words:
        vec[4] = 0.9
    elif dep in ("amod",):
        vec[4] = 0.4
    else:
        vec[4] = 0.1

    # O6: AGENCY — control, intent
    if dep in ("nsubj",) and word and word[0].isupper():
        vec[5] = 0.9
    elif dep in ("nsubj", "agent"):
        vec[5] = 0.8
    elif dep in ("root", "ROOT"):
        vec[5] = 0.6
    else:
        vec[5] = 0.1

    # O7: REASONING — logic, discrimination
    reasoning_words = {
        "because", "therefore", "however", "although", "if", "then",
        "thus", "hence", "since", "unless", "whereas", "implies",
    }
    if w in reasoning_words:
        vec[6] = 0.9
    elif dep in ("mark", "advcl"):
        vec[6] = 0.5
    else:
        vec[6] = 0.1

    # O8: PURPOSE — meaning, motivation
    purpose_words = {
        "to", "for", "in order", "so that", "because", "why",
        "goal", "purpose", "aim", "objective", "intention",
    }
    if w in purpose_words:
        vec[7] = 0.8
    elif dep in ("xcomp", "advcl"):
        vec[7] = 0.6
    else:
        vec[7] = 0.1

    # O9: WITNESSES — meta-observation
    meta_words = {
        "seems", "appears", "apparently", "reportedly", "arguably",
        "perhaps", "maybe", "likely", "possibly", "presumably",
    }
    if w in meta_words:
        vec[8] = 0.9
    elif dep in ("advmod",) and depth_norm > 0.5:
        vec[8] = 0.4
    else:
        vec[8] = 0.1

    # O10: UNIFYING — coherence, synthesis
    if dep in ("cc", "conj"):
        vec[9] = 0.7
    elif dep in ("root", "ROOT") and pos_norm > 0.7:
        vec[9] = 0.6
    else:
        vec[9] = 0.1 + 0.2 * pos_norm

    # O11: INTEGRATION — resolution
    if dep in ("conj",) and pos_norm > 0.5:
        vec[10] = 0.6
    elif pos_norm > 0.8:
        vec[10] = 0.5
    else:
        vec[10] = 0.1 + 0.2 * pos_norm

    # O12: ABSOLVING — termination
    if dep in ("punct",) and w in (".", "!", "?"):
        vec[11] = 0.9
    elif pos_norm > 0.9:
        vec[11] = 0.6
    else:
        vec[11] = 0.05

    return vec


def _heuristic_ontology_features(
    tokens: List[str],
    sentence_ids: np.ndarray,
    hidden_states: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build heuristic ontology features without dependency parsing.

    Uses token properties (position, capitalization, punctuation) as proxies.
    """
    N = len(tokens)
    ont_features = np.zeros((N, 12), dtype=np.float32)
    valid_mask = np.ones(N, dtype=bool)

    unique_sids = np.unique(sentence_ids)
    for sid in unique_sids:
        mask = sentence_ids == sid
        indices = np.where(mask)[0]
        n_sent = len(indices)

        for local_pos, global_idx in enumerate(indices):
            pos_norm = local_pos / max(n_sent - 1, 1)
            word = tokens[global_idx].strip()
            w = word.lower().strip(".,!?;:\"'()[]{}—-")

            # Heuristic features
            is_upper = word and word[0].isupper() and local_pos > 0
            is_punct = word in (".", ",", "!", "?", ";", ":", "-", "(", ")") or \
                       w == ""  # stripped to nothing = punctuation
            is_long = len(w) > 6

            # O1: POTENTIAL — early position
            ont_features[global_idx, 0] = max(0, 1 - pos_norm) * 0.5 + (0.3 if is_punct else 0)

            # O2: IDENTITY — capitalized words
            ont_features[global_idx, 1] = 0.8 if is_upper else (0.3 if is_long else 0.1)

            # O3: EXECUTION — early content words
            ont_features[global_idx, 2] = 0.5 if (pos_norm < 0.3 and not is_punct) else 0.1

            # O4: STRUCTURE — position and punctuation
            ont_features[global_idx, 3] = 0.3 + 0.3 * pos_norm + (0.3 if is_punct else 0)

            # O5: COGNITION — cognitive words
            cognitive_words = {"think", "know", "believe", "feel", "see", "understand"}
            ont_features[global_idx, 4] = 0.9 if w in cognitive_words else 0.1

            # O6: AGENCY — subject-like position
            ont_features[global_idx, 5] = 0.6 if (pos_norm < 0.2 and is_upper) else 0.1

            # O7: REASONING — logical connectives
            reasoning_words = {"because", "therefore", "however", "although", "if", "then"}
            ont_features[global_idx, 6] = 0.9 if w in reasoning_words else 0.1

            # O8: PURPOSE — purpose words
            purpose_words = {"to", "for", "goal", "purpose", "aim"}
            ont_features[global_idx, 7] = 0.7 if w in purpose_words else 0.1

            # O9: WITNESSES — hedging words
            meta_words = {"seems", "appears", "perhaps", "maybe", "likely"}
            ont_features[global_idx, 8] = 0.8 if w in meta_words else 0.1

            # O10: UNIFYING — late position conjunctions
            ont_features[global_idx, 9] = 0.2 + 0.3 * pos_norm

            # O11: INTEGRATION — late position
            ont_features[global_idx, 10] = 0.1 + 0.4 * pos_norm

            # O12: ABSOLVING — sentence-final
            if is_punct and word.strip() in (".", "!", "?"):
                ont_features[global_idx, 11] = 0.9
            else:
                ont_features[global_idx, 11] = 0.1 * pos_norm

    return ont_features, valid_mask


# ---------------------------------------------------------------------------
# Core evaluation pipeline
# ---------------------------------------------------------------------------

def evaluate_on_real_data(
    hidden_states: np.ndarray,
    labels: np.ndarray,
    tokens: List[str],
    sentence_ids: np.ndarray,
    metadata: Dict[str, Any],
    bridge_type: str = "linear",
    hidden_dim: int = 64,
    n_epochs_bridge: int = 200,
    n_epochs_monitor: int = 100,
    state_dim: int = 32,
    run_governance: bool = False,
    compare_synthetic: bool = False,
    seed: int = 42,
    device: str = "cpu",
) -> Dict[str, Any]:
    """Run the full evaluation pipeline on real hidden states.

    Returns dict with all results, suitable for JSON serialization.
    """
    results: Dict[str, Any] = {"metadata": metadata}
    d_model = hidden_states.shape[1]
    N = hidden_states.shape[0]

    logger.info("=" * 60)
    logger.info("Phase 2 Evaluation: Real LLM Hidden States")
    logger.info("=" * 60)
    logger.info("  Model: %s", metadata.get("model_name", "unknown"))
    logger.info("  Layer: %s", metadata.get("target_layer", "?"))
    logger.info("  Tokens: %d, d_model: %d", N, d_model)

    torch.manual_seed(seed)
    rng = np.random.RandomState(seed)

    # ── Step 1: Build ontology vectors ────────────────────────────────────
    logger.info("\nStep 1: Building ontology vectors from dependency parsing...")
    t0 = time.time()

    ont_features, valid_mask = build_ontology_for_real_tokens(
        tokens, sentence_ids, hidden_states,
    )

    H_valid = hidden_states[valid_mask]
    ont_valid = ont_features[valid_mask]
    labels_valid = labels[valid_mask]
    z_ont_robust = ont_valid[:, ROBUST_AXIS_INDICES]  # [N, 4]
    N_valid = H_valid.shape[0]

    logger.info("  Ontology vectors built: %d valid tokens (%.1fs)",
                N_valid, time.time() - t0)

    results["ontology"] = {
        "n_valid": N_valid,
        "n_total": N,
        "coverage": N_valid / max(N, 1),
        "ont_means": ont_valid.mean(axis=0).tolist(),
        "ont_stds": ont_valid.std(axis=0).tolist(),
    }

    # ── Step 2: Project to Sovereign State ────────────────────────────────
    logger.info("\nStep 2: Projecting to 32D Sovereign State...")
    t0 = time.time()

    projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
    dev = torch.device(device)
    projector.to(dev)

    # Process in batches to handle large datasets
    batch_size = 2048
    S_parts = []
    for start in range(0, N_valid, batch_size):
        end = min(start + batch_size, N_valid)
        h_batch = torch.from_numpy(H_valid[start:end].astype(np.float32)).to(dev)
        with torch.no_grad():
            s_batch = projector(h_batch).cpu().numpy()
        S_parts.append(s_batch)
    S = np.concatenate(S_parts, axis=0)  # [N_valid, 32]

    logger.info("  Sovereign State projected: [%d, %d] (%.1fs)",
                S.shape[0], S.shape[1], time.time() - t0)

    results["sovereign_state"] = {
        "shape": list(S.shape),
        "means": S.mean(axis=0).tolist(),
        "stds": S.std(axis=0).tolist(),
    }

    # ── Step 3: Compute alignment matrix ──────────────────────────────────
    logger.info("\nStep 3: Computing alignment matrix [4 x 32]...")
    t0 = time.time()

    corr_matrix = compute_alignment_matrix(z_ont_robust, S)

    alignment_map = {}
    for j in range(N_ROBUST):
        axis_name = ROBUST_AXES[j]
        best_dim = int(np.argmax(np.abs(corr_matrix[j])))
        best_corr = float(corr_matrix[j, best_dim])
        dim_name = SOVEREIGN_DIM_NAMES[best_dim] if best_dim < len(SOVEREIGN_DIM_NAMES) else f"dim_{best_dim}"
        alignment_map[axis_name] = {
            "best_dim": best_dim,
            "best_dim_name": dim_name,
            "best_corr": best_corr,
        }
        logger.info("  %s → %s (corr=%.3f)", axis_name, dim_name, best_corr)

    results["alignment"] = {
        "map": alignment_map,
        "max_abs_corr": float(np.max(np.abs(corr_matrix))),
        "mean_abs_corr": float(np.mean(np.max(np.abs(corr_matrix), axis=1))),
        "n_strong": int(np.sum(np.max(np.abs(corr_matrix), axis=1) > 0.5)),
        "n_moderate": int(np.sum(np.max(np.abs(corr_matrix), axis=1) > 0.3)),
    }
    logger.info("  Alignment: %d strong, %d moderate (%.1fs)",
                results["alignment"]["n_strong"],
                results["alignment"]["n_moderate"],
                time.time() - t0)

    # ── Step 4: Train bridge ──────────────────────────────────────────────
    logger.info("\nStep 4: Training %s bridge (S → z_ont)...", bridge_type)
    t0 = time.time()

    if bridge_type == "mlp":
        bridge = MLPBridge(state_dim=state_dim, n_axes=N_ROBUST, hidden_dim=hidden_dim)
    else:
        bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)

    bridge_metrics = bridge.train_bridge(
        S, z_ont_robust,
        n_epochs=n_epochs_bridge, seed=seed,
    )

    results["bridge"] = {
        "type": bridge_type,
        "r2_mean": bridge_metrics["r2_mean"],
        "r2_per_axis": bridge_metrics["r2_per_axis"],
        "train_loss": bridge_metrics["train_loss"],
        "n_train": bridge_metrics["n_train"],
        "n_val": bridge_metrics["n_val"],
    }

    logger.info("  Bridge R²=%.3f (per-axis: %s) [%.1fs]",
                bridge_metrics["r2_mean"],
                ", ".join(f"{k}={v:.3f}" for k, v in bridge_metrics["r2_per_axis"].items()),
                time.time() - t0)

    # ── Step 5: Train monitor ─────────────────────────────────────────────
    logger.info("\nStep 5: Training OntologyMonitor (H → z_ont)...")
    t0 = time.time()

    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
    monitor.train_monitor(
        H=H_valid, ont_features=ont_valid,
        valid_mask=np.ones(N_valid, dtype=bool),
        n_epochs=n_epochs_monitor, seed=seed,
    )
    logger.info("  Monitor trained (%.1fs)", time.time() - t0)

    # ── Step 6: Anomaly detection by behavioral category ──────────────────
    logger.info("\nStep 6: Anomaly detection per behavioral category...")

    predictor = VrittiValidatedPredictor(
        state_dim=state_dim, hidden_dim=128, prediction_steps=2,
    )
    predictor.to(dev)

    normal_mask = labels_valid == CATEGORY_TO_IDX["normal"]
    n_normal = int(normal_mask.sum())

    if n_normal < 20:
        logger.warning("  Only %d normal tokens — skipping AUC computation", n_normal)
        results["anomaly_detection"] = {"skipped": True, "reason": "insufficient_normal"}
    else:
        H_normal = H_valid[normal_mask]
        S_normal = S[normal_mask]

        # Compute baseline scores on normal data
        with torch.no_grad():
            s_normal_t = torch.from_numpy(S_normal.astype(np.float32)).to(dev)
            s_pred_normal, _ = predictor(s_normal_t)
            jepa_error_normal = ((s_pred_normal - s_normal_t) ** 2).mean(dim=-1)
            if jepa_error_normal.dim() > 1:
                jepa_error_normal = jepa_error_normal.mean(dim=-1)
            jepa_scores_normal = jepa_error_normal.cpu().numpy()

        # Monitor scores on normal
        normal_result = monitor.predict(H_normal)
        if monitor._centroid is not None:
            ont_scores_normal = np.mean(
                np.abs(normal_result.z_ont - monitor._centroid) /
                np.maximum(monitor._centroid_std, 1e-6), axis=1,
            )
        else:
            ont_scores_normal = np.zeros(n_normal)

        anomaly_results = {}
        for cat_name, cat_idx in CATEGORY_TO_IDX.items():
            if cat_name == "normal":
                continue

            cat_mask = labels_valid == cat_idx
            n_cat = int(cat_mask.sum())
            if n_cat < 10:
                logger.info("  %s: %d tokens (too few, skipping)", cat_name, n_cat)
                continue

            H_cat = H_valid[cat_mask]
            S_cat = S[cat_mask]

            # JEPA scores
            with torch.no_grad():
                s_cat_t = torch.from_numpy(S_cat.astype(np.float32)).to(dev)
                s_pred_cat, _ = predictor(s_cat_t)
                jepa_error_cat = ((s_pred_cat - s_cat_t) ** 2).mean(dim=-1)
                if jepa_error_cat.dim() > 1:
                    jepa_error_cat = jepa_error_cat.mean(dim=-1)
                jepa_scores_cat = jepa_error_cat.cpu().numpy()

            # Monitor scores
            cat_result = monitor.predict(H_cat)
            if monitor._centroid is not None:
                ont_scores_cat = np.mean(
                    np.abs(cat_result.z_ont - monitor._centroid) /
                    np.maximum(monitor._centroid_std, 1e-6), axis=1,
                )
            else:
                ont_scores_cat = np.zeros(n_cat)

            # Combined: concat normal+anomaly, binary labels
            all_jepa = np.concatenate([jepa_scores_normal, jepa_scores_cat])
            all_ont = np.concatenate([ont_scores_normal, ont_scores_cat])
            all_combined = 0.5 * all_jepa / max(all_jepa.max(), 1e-6) + \
                           0.5 * all_ont / max(all_ont.max(), 1e-6)
            all_labels = np.concatenate([
                np.zeros(n_normal, dtype=np.int32),
                np.ones(n_cat, dtype=np.int32),
            ])

            jepa_auc = compute_detection_auc(all_jepa, all_labels)
            ont_auc = compute_detection_auc(all_ont, all_labels)
            combined_auc = compute_detection_auc(all_combined, all_labels)

            anomaly_results[cat_name] = {
                "n_tokens": n_cat,
                "jepa_auc": jepa_auc,
                "ont_auc": ont_auc,
                "combined_auc": combined_auc,
                "best_auc": max(jepa_auc, ont_auc, combined_auc),
                "jepa_mean_score": float(jepa_scores_cat.mean()),
                "ont_mean_score": float(ont_scores_cat.mean()),
            }

            logger.info(
                "  %s: JEPA=%.3f, Ont=%.3f, Combined=%.3f (%d tokens)",
                cat_name, jepa_auc, ont_auc, combined_auc, n_cat,
            )

        results["anomaly_detection"] = anomaly_results

    # ── Step 7: Governance components ─────────────────────────────────────
    if run_governance:
        logger.info("\nStep 7: Governance component evaluation...")
        t0 = time.time()

        # 7a: Coherence loss
        coherence_loss_fn = TrajectoryCoherenceLoss(
            predictor=predictor,
            state_projector=projector,
            lambda_coherence=0.1,
            freeze_predictor=True,
        )

        seq_len = min(20, N_valid)
        h_seq = torch.from_numpy(
            H_valid[:seq_len].astype(np.float32)
        ).unsqueeze(0).to(dev)

        loss_val = coherence_loss_fn(h_seq)
        metrics = coherence_loss_fn.metrics(h_seq)

        results["governance_coherence"] = {
            "loss_value": float(loss_val.detach()),
            "coherence_loss_raw": metrics["coherence_loss"],
            "weighted_loss": metrics["weighted_loss"],
            "mean_step_distance": metrics["mean_step_distance"],
            "has_gradient": loss_val.requires_grad,
        }
        logger.info("  CoherenceLoss=%.4f, step_dist=%.4f",
                     metrics["coherence_loss"], metrics["mean_step_distance"])

        # 7b: Mismatch detector
        detector = TrajectoryMismatchDetector(
            predictor=predictor,
            state_projector=projector,
            ema_alpha=0.95,
            threshold_multiplier=2.5,
        )

        # Normal sequence baseline
        n_seq = min(50, N_valid)
        normal_events = detector.detect_sequence(H_valid[:n_seq])
        normal_scores = [e.mismatch_score for e in normal_events]

        # Inject break
        detector.reset()
        h_break = H_valid[:n_seq].copy()
        break_pos = min(25, n_seq - 2)
        h_break[break_pos] = rng.randn(d_model).astype(np.float32) * 3.0
        break_events = detector.detect_sequence(h_break)

        if break_pos < len(break_events):
            break_event = break_events[break_pos]
            break_score = break_event.mismatch_score
        else:
            break_score = 0.0

        mean_normal = float(np.mean(normal_scores)) if normal_scores else 0.0

        results["governance_mismatch"] = {
            "mean_normal_score": mean_normal,
            "break_score": break_score,
            "ratio": break_score / max(mean_normal, 1e-10),
            "break_is_significant": break_event.is_significant if break_pos < len(break_events) else False,
        }
        logger.info("  Mismatch: normal=%.4f, break=%.4f (%.1fx)",
                     mean_normal, break_score,
                     break_score / max(mean_normal, 1e-10))

        # 7c: Governor
        governor = DisagreementGovernor(
            monitor=monitor,
            predictor=predictor,
            state_projector=projector,
            bridge=bridge if isinstance(bridge, OntologyBridge) else None,
        )

        # Calibrate on normal data
        n_cal = min(200, n_normal, N_valid)
        if n_normal > 0:
            cal_data = H_valid[normal_mask][:n_cal]
        else:
            cal_data = H_valid[:n_cal]
        governor.calibrate(cal_data, multiplier=2.0)

        # Assess each behavioral category
        governor_results = {}
        for cat_name, cat_idx in CATEGORY_TO_IDX.items():
            cat_mask_local = labels_valid == cat_idx
            n_cat = int(cat_mask_local.sum())
            if n_cat < 5:
                continue

            sample_size = min(20, n_cat)
            sample_idx = np.where(cat_mask_local)[0][:sample_size]
            h_sample = H_valid[sample_idx]

            report = governor.assess(h_sample)
            governor_results[cat_name] = {
                "regime": report.regime,
                "disagreement_score": report.disagreement_score,
                "ontology_score": report.ontology_score,
                "trajectory_score": report.trajectory_score,
                "residual_score": report.residual_score,
                "explanation": report.explanation[:200],
            }
            logger.info("  Governor %s: regime=%s, score=%.3f",
                        cat_name, report.regime, report.disagreement_score)

        results["governance_governor"] = governor_results
        logger.info("  Governance evaluation complete (%.1fs)", time.time() - t0)

    # ── Step 8: Compare with synthetic baseline ───────────────────────────
    if compare_synthetic:
        logger.info("\nStep 8: Comparing with synthetic baseline...")
        t0 = time.time()

        H_synth, ont_synth, mask_synth = generate_synthetic_hidden_states(
            n_samples=min(N_valid, 5000), d_model=d_model, seed=seed,
        )

        synth_projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
        with torch.no_grad():
            S_synth = synth_projector(
                torch.from_numpy(H_synth.astype(np.float32))
            ).cpu().numpy()

        z_ont_synth = ont_synth[:, ROBUST_AXIS_INDICES]

        synth_bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
        synth_metrics = synth_bridge.train_bridge(
            S_synth, z_ont_synth, n_epochs=n_epochs_bridge, seed=seed,
        )

        results["synthetic_comparison"] = {
            "synthetic_r2_mean": synth_metrics["r2_mean"],
            "synthetic_r2_per_axis": synth_metrics["r2_per_axis"],
            "real_r2_mean": bridge_metrics["r2_mean"],
            "real_r2_per_axis": bridge_metrics["r2_per_axis"],
            "improvement": bridge_metrics["r2_mean"] - synth_metrics["r2_mean"],
            "improved": bridge_metrics["r2_mean"] > synth_metrics["r2_mean"],
        }

        logger.info("  Synthetic R²=%.3f vs Real R²=%.3f (delta=%+.3f)",
                     synth_metrics["r2_mean"], bridge_metrics["r2_mean"],
                     bridge_metrics["r2_mean"] - synth_metrics["r2_mean"])
        logger.info("  Comparison complete (%.1fs)", time.time() - t0)

    # ── Step 9: Negative controls ─────────────────────────────────────────
    logger.info("\nStep 9: Negative controls (anti-self-confirmation)...")
    t0 = time.time()
    controls = {}

    # Control 1: Label shuffle — R² must collapse to ~0
    z_shuffled = z_ont_robust.copy()
    for j in range(z_shuffled.shape[1]):
        rng.shuffle(z_shuffled[:, j])
    shuffle_bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
    shuffle_metrics = shuffle_bridge.train_bridge(
        S, z_shuffled, n_epochs=n_epochs_bridge, seed=seed + 999,
    )
    controls["label_shuffle"] = {
        "r2_mean": shuffle_metrics["r2_mean"],
        "r2_per_axis": shuffle_metrics["r2_per_axis"],
        "passed": shuffle_metrics["r2_mean"] < 0.05,
        "detail": f"Shuffled R²={shuffle_metrics['r2_mean']:.4f} {'< 0.05 OK' if shuffle_metrics['r2_mean'] < 0.05 else '>= 0.05 LEAKAGE'}",
    }
    logger.info("  Label shuffle: R²=%.4f %s",
                shuffle_metrics["r2_mean"],
                CHECK if controls["label_shuffle"]["passed"] else CROSS_MARK)

    # Control 2: Random projector — R² should drop to synthetic baseline
    random_projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
    # Re-initialize with fresh random weights
    for p in random_projector.parameters():
        if p.dim() >= 2:
            nn.init.xavier_normal_(p, gain=0.5)
        else:
            nn.init.zeros_(p)
    random_projector.to(dev)

    S_random_parts = []
    for start in range(0, N_valid, 2048):
        end = min(start + 2048, N_valid)
        h_batch = torch.from_numpy(H_valid[start:end].astype(np.float32)).to(dev)
        with torch.no_grad():
            s_batch = random_projector(h_batch).cpu().numpy()
        S_random_parts.append(s_batch)
    S_random = np.concatenate(S_random_parts, axis=0)

    rand_bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
    rand_metrics = rand_bridge.train_bridge(
        S_random, z_ont_robust, n_epochs=n_epochs_bridge, seed=seed + 888,
    )
    r2_delta = bridge_metrics["r2_mean"] - rand_metrics["r2_mean"]
    controls["random_projector"] = {
        "r2_mean": rand_metrics["r2_mean"],
        "r2_per_axis": rand_metrics["r2_per_axis"],
        "real_r2_mean": bridge_metrics["r2_mean"],
        "delta": r2_delta,
        "passed": r2_delta > 0.02,
        "detail": f"Random R²={rand_metrics['r2_mean']:.4f} vs Real R²={bridge_metrics['r2_mean']:.4f} (delta={r2_delta:+.4f})",
    }
    logger.info("  Random projector: R²=%.4f, delta=%+.4f %s",
                rand_metrics["r2_mean"], r2_delta,
                CHECK if controls["random_projector"]["passed"] else CROSS_MARK)

    # Control 3: Embedding distance baseline (L2 from centroid in raw H-space)
    if n_normal > 20 and any(
        int((labels_valid == CATEGORY_TO_IDX[c]).sum()) > 10
        for c in ["trajectory_break", "domain_shift", "adversarial", "subtle_drift"]
    ):
        centroid_H = H_normal.mean(axis=0)
        dist_normal = np.linalg.norm(H_normal - centroid_H, axis=1)

        baseline_results = {}
        for cat_name in ["trajectory_break", "domain_shift", "adversarial", "subtle_drift"]:
            cat_idx = CATEGORY_TO_IDX[cat_name]
            cat_mask_local = labels_valid == cat_idx
            n_cat = int(cat_mask_local.sum())
            if n_cat < 10:
                continue

            H_cat_ctrl = H_valid[cat_mask_local]
            dist_cat = np.linalg.norm(H_cat_ctrl - centroid_H, axis=1)

            all_dist = np.concatenate([dist_normal, dist_cat])
            all_labels_ctrl = np.concatenate([
                np.zeros(n_normal, dtype=np.int32),
                np.ones(n_cat, dtype=np.int32),
            ])
            baseline_auc = compute_detection_auc(all_dist, all_labels_ctrl)
            baseline_results[cat_name] = {"embedding_distance_auc": baseline_auc}

            # Compare with our combined AUC
            our_auc = results.get("anomaly_detection", {}).get(cat_name, {}).get("combined_auc", 0)
            beats = our_auc > baseline_auc
            baseline_results[cat_name]["our_combined_auc"] = our_auc
            baseline_results[cat_name]["beats_baseline"] = beats
            logger.info("  Baseline %s: embedding_dist=%.3f vs ours=%.3f %s",
                        cat_name, baseline_auc, our_auc,
                        CHECK if beats else CROSS_MARK)

        controls["embedding_distance_baseline"] = baseline_results

    controls["all_passed"] = all(
        v.get("passed", True) for k, v in controls.items()
        if isinstance(v, dict) and "passed" in v
    )
    results["negative_controls"] = controls
    logger.info("  Negative controls complete (%.1fs)", time.time() - t0)

    return results


# ---------------------------------------------------------------------------
# Pretty print results
# ---------------------------------------------------------------------------

def print_results(results: Dict[str, Any]) -> None:
    """Print results in a human-readable format."""
    meta = results.get("metadata", {})
    bridge = results.get("bridge", {})

    print(f"\n{TL}{H_LINE * 58}{TR}")
    print(f"{V_LINE}  Phase 2 Results: Real LLM Hidden States{' ' * 16}{V_LINE}")
    print(f"{T_RIGHT}{H_LINE * 58}{TR}")

    print(f"{V_LINE}  Model:  {meta.get('model_name', '?'):20s}  Layer: {meta.get('target_layer', '?'):<5}  {V_LINE}")
    print(f"{V_LINE}  Tokens: {meta.get('n_tokens', 0):>7,}             d_model: {meta.get('d_model', 0):<5}  {V_LINE}")

    # Bridge R²
    print(f"{T_RIGHT}{H_LINE * 58}{TR}")
    print(f"{V_LINE}  Bridge R² ({bridge.get('type', 'linear')}){' ' * 37}{V_LINE}")
    print(f"{T_RIGHT}{H_LINE * 58}{TR}")

    r2_per_axis = bridge.get("r2_per_axis", {})
    r2_mean = bridge.get("r2_mean", 0)
    for axis, r2 in r2_per_axis.items():
        bar_len = max(0, int(r2 * 40))
        bar = BAR_FULL * bar_len + "░" * (40 - bar_len)
        status = CHECK if r2 > 0.2 else CROSS_MARK
        print(f"{V_LINE}  {status} {axis:12s}  {r2:+.3f}  {bar}  {V_LINE}")

    print(f"{T_RIGHT}{H_LINE * 58}{TR}")
    r2_status = CHECK if r2_mean > 0.36 else "~" if r2_mean > 0.2 else CROSS_MARK
    print(f"{V_LINE}  {r2_status} Mean R²: {r2_mean:.3f}  (synthetic baseline: 0.360){' ' * 8}{V_LINE}")

    # Anomaly detection
    anom = results.get("anomaly_detection", {})
    if anom and not anom.get("skipped"):
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        print(f"{V_LINE}  Anomaly Detection AUC{' ' * 35}{V_LINE}")
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        for cat, data in anom.items():
            best = data.get("best_auc", 0)
            status = CHECK if best > 0.7 else "~" if best > 0.55 else CROSS_MARK
            print(f"{V_LINE}  {status} {cat:20s}  JEPA={data.get('jepa_auc', 0):.3f}  "
                  f"Ont={data.get('ont_auc', 0):.3f}  Comb={data.get('combined_auc', 0):.3f}  {V_LINE}")

    # Governance
    gov = results.get("governance_governor", {})
    if gov:
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        print(f"{V_LINE}  Governor Regime Classification{' ' * 26}{V_LINE}")
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        for cat, data in gov.items():
            regime = data.get("regime", "?")
            score = data.get("disagreement_score", 0)
            print(f"{V_LINE}  {cat:20s}  {regime:20s}  score={score:.3f}  {V_LINE}")

    # Synthetic comparison
    comp = results.get("synthetic_comparison", {})
    if comp:
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        improved = comp.get("improved", False)
        delta = comp.get("improvement", 0)
        status = CHECK if improved else CROSS_MARK
        print(f"{V_LINE}  {status} Real vs Synthetic: R² delta = {delta:+.3f}{' ' * 19}{V_LINE}")
        print(f"{V_LINE}    Real:      {comp.get('real_r2_mean', 0):.3f}{' ' * 39}{V_LINE}")
        print(f"{V_LINE}    Synthetic: {comp.get('synthetic_r2_mean', 0):.3f}{' ' * 39}{V_LINE}")

    # Negative controls
    controls = results.get("negative_controls", {})
    if controls:
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        print(f"{V_LINE}  Negative Controls{' ' * 39}{V_LINE}")
        print(f"{T_RIGHT}{H_LINE * 58}{TR}")
        for key in ["label_shuffle", "random_projector"]:
            data = controls.get(key, {})
            if data:
                status = CHECK if data.get("passed") else CROSS_MARK
                print(f"{V_LINE}  {status} {key:20s}  {data.get('detail', '')[:35]:35s}  {V_LINE}")

        baselines = controls.get("embedding_distance_baseline", {})
        if baselines:
            for cat, bdata in baselines.items():
                beats = bdata.get("beats_baseline", False)
                status = CHECK if beats else CROSS_MARK
                baseline_auc = bdata.get("embedding_distance_auc", 0)
                our_auc = bdata.get("our_combined_auc", 0)
                print(f"{V_LINE}  {status} vs baseline {cat:15s}  "
                      f"ours={our_auc:.3f} base={baseline_auc:.3f}  {V_LINE}")

    print(f"{BL}{H_LINE * 58}{BR}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate bridge + governance on real LLM hidden states",
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Input .pt file from extract_real_states.py",
    )
    parser.add_argument(
        "--bridge-type", choices=["linear", "mlp"], default="linear",
        help="Bridge type (default: linear)",
    )
    parser.add_argument(
        "--hidden-dim", type=int, default=64,
        help="Hidden dim for MLP bridge (default: 64)",
    )
    parser.add_argument(
        "--n-epochs", type=int, default=200,
        help="Bridge training epochs (default: 200)",
    )
    parser.add_argument(
        "--n-epochs-monitor", type=int, default=100,
        help="Monitor training epochs (default: 100)",
    )
    parser.add_argument(
        "--state-dim", type=int, default=32,
        help="Sovereign State dimension (default: 32)",
    )
    parser.add_argument(
        "--device", default="cpu",
        help="Device for projector/predictor: cpu or cuda (default: cpu)",
    )
    parser.add_argument(
        "--governance", action="store_true",
        help="Run governance component evaluation",
    )
    parser.add_argument(
        "--compare-synthetic", action="store_true",
        help="Compare with synthetic baseline",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load extracted states
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    logger.info("Loading extracted states from %s...", input_path)
    data = torch.load(str(input_path), map_location="cpu", weights_only=False)

    hidden_states = data["hidden_states"].numpy()
    labels = data["labels"].numpy()
    sentence_ids = data["sentence_ids"].numpy()
    tokens = data["tokens"]
    metadata = data["metadata"]

    logger.info("Loaded: %d tokens, d_model=%d, model=%s",
                hidden_states.shape[0], hidden_states.shape[1],
                metadata.get("model_name", "unknown"))

    # Run evaluation
    results = evaluate_on_real_data(
        hidden_states=hidden_states,
        labels=labels,
        tokens=tokens,
        sentence_ids=sentence_ids,
        metadata=metadata,
        bridge_type=args.bridge_type,
        hidden_dim=args.hidden_dim,
        n_epochs_bridge=args.n_epochs,
        n_epochs_monitor=args.n_epochs_monitor,
        state_dim=args.state_dim,
        run_governance=args.governance,
        compare_synthetic=args.compare_synthetic,
        seed=args.seed,
        device=args.device,
    )

    # Print results
    print_results(results)

    # Save to JSON
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Make results JSON-serializable
        def _to_serializable(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=_to_serializable)
        logger.info("Results saved to %s", output_path)


if __name__ == "__main__":
    main()
