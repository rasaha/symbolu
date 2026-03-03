#!/usr/bin/env python3
"""
End-to-End Synthetic Evaluation — Phase 1 + Phase 2
=====================================================

Runs the complete causal subspace pipeline on purely synthetic data:

Phase 1 (Parts 3-6):
  - Feature disentanglement (PCA + SAE + K-means)
  - MDL probing (information-theoretic validation)
  - Causal interchange intervention (toy transformer)
  - Layer trajectory mapping

Phase 2 (Part 7):
  - Controlled ground-truth dataset with subspace structure
  - OntologyMonitor training with train/val/test splits
  - Per-axis R², MAE, rank correlation with bootstrap 95% CIs
  - Robustness under distribution shift (noise, scale, rotate)
  - Drift detection validation
  - OntologyInjector evaluation on 49 diverse sentences
  - SNR sensitivity analysis

Part 8: JEPA-Observatory Integration:
  - Alignment matrix [4 x 32] between ontological axes and Sovereign State
  - OntologyBridge linear probe training (S -> z_ont)
  - Synthetic anomaly detection (domain shift, trajectory break, etc.)
  - Integration scenario classification (E/F/G)
  - CascadeObservatory / ParallelObservatory test
  - Domain-adaptive Vritti thresholds

No model download, GPU, or internet connection required.

Usage::

    # Phase 1 only (default)
    python scripts/causal_subspace/test_synthetic.py

    # Phase 1 + Phase 2
    python scripts/causal_subspace/test_synthetic.py --run-phase2

    # Quick smoke test
    python scripts/causal_subspace/test_synthetic.py --quick --run-phase2

    # Phase 2 only
    python scripts/causal_subspace/test_synthetic.py --parts 7

    # Save results
    python scripts/causal_subspace/test_synthetic.py --run-phase2 --output results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

# Ensure project root is on path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.disentanglement import (
    DisentanglementConfig,
    run_disentanglement,
)
from scripts.causal_subspace.mdl_probing import (
    MDLProbeConfig,
    run_mdl_probe,
    select_top_k_components,
)
from scripts.causal_subspace.causal_intervention import (
    InterventionResult,
    build_pca_basis,
    build_subspace_basis,
    _random_orthonormal_basis,
)
from scripts.causal_subspace.trajectory import (
    compute_layer_trajectory,
    plot_trajectory_ascii,
)
from scripts.causal_subspace.ontology_alignment import (
    AXIS_NAMES,
    N_AXES,
    OntologyMonitor,
    OntologyInjector,
    MonitorResult,
    InjectionMetadata,
    ROBUST_AXES,
    N_ROBUST,
    ROBUST_AXIS_INDICES,
)
from scripts.causal_subspace.jepa_observatory import (
    run_integration_evaluation,
)

logger = logging.getLogger("causal_subspace.synthetic")


# ---------------------------------------------------------------------------
# Phase 1: Synthetic data generators
# ---------------------------------------------------------------------------

def generate_synthetic_hidden_states(
    n_samples: int,
    d_model: int,
    n_layers: int,
    n_classes: int,
    signal_growth: float = 0.8,
    noise_decay: float = 0.15,
    seed: int = 42,
) -> tuple[Dict[int, np.ndarray], np.ndarray]:
    """Generate multi-layer hidden states with controllable class structure.

    Later layers have stronger class signal (mimicking how real transformers
    crystallize structure in middle-to-late layers).
    """
    rng = np.random.RandomState(seed)
    labels = rng.randint(0, n_classes, size=n_samples).astype(np.int32)
    class_means = rng.randn(n_classes, d_model).astype(np.float32)

    states: Dict[int, np.ndarray] = {}
    for layer in range(n_layers):
        signal = 0.3 + layer * signal_growth
        noise = max(2.5 - layer * noise_decay, 0.1)

        H = np.zeros((n_samples, d_model), dtype=np.float32)
        for i in range(n_samples):
            H[i] = class_means[labels[i]] * signal + rng.randn(d_model) * noise
        states[layer] = H

    return states, labels


class _ToyTransformerBlock(nn.Module):
    def __init__(self, d_model: int):
        super().__init__()
        self.proj = nn.Linear(d_model, d_model, bias=False)
        nn.init.eye_(self.proj.weight)
        with torch.no_grad():
            self.proj.weight.add_(torch.randn_like(self.proj.weight) * 0.01)

    def forward(self, x):
        return self.proj(x)


class _ToyTransformer(nn.Module):
    """Toy transformer with hookable blocks for activation patching tests."""

    def __init__(self, d_model: int, n_layers: int, vocab_size: int = 1000):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)
        self.transformer = nn.Module()
        self.transformer.h = nn.ModuleList(
            [_ToyTransformerBlock(d_model) for _ in range(n_layers)]
        )
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, input_ids, **kwargs):
        h = self.embed(input_ids)
        for block in self.transformer.h:
            h = block(h)
        return _LogitOutput(self.lm_head(h))


class _LogitOutput:
    def __init__(self, logits):
        self.logits = logits


class _ToyTokenizer:
    def __init__(self, vocab_size: int = 1000):
        self.vocab_size = vocab_size
        self.pad_token = "<pad>"
        self.pad_token_id = 0
        self.eos_token = "<eos>"
        self.eos_token_id = 1

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        return [ord(c) % self.vocab_size for c in text if c.strip()]

    def decode(self, ids) -> str:
        return "".join(chr(i + 65) for i in ids)


# ---------------------------------------------------------------------------
# Phase 2: Controlled dataset with known subspace structure
# ---------------------------------------------------------------------------

@dataclass
class EvalDataset:
    """Controlled dataset with known ground-truth ontology structure."""
    hidden_states: np.ndarray   # [N, d_model]
    ont_features: np.ndarray    # [N, 12]
    valid_mask: np.ndarray      # [N] bool
    labels: np.ndarray          # [N] int
    split: str = "train"

    @property
    def N(self) -> int:
        return self.hidden_states.shape[0]

    @property
    def d_model(self) -> int:
        return self.hidden_states.shape[1]


def generate_controlled_dataset(
    n_samples: int = 5000,
    d_model: int = 768,
    n_classes: int = 5,
    signal_snr: float = 3.0,
    seed: int = 42,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
) -> Tuple[EvalDataset, EvalDataset, EvalDataset]:
    """Generate train/val/test splits with known ontological structure.

    For each robust axis j, a random 10-dim subspace S_j encodes the axis
    value along its first principal direction, scaled by signal_snr.
    """
    rng = np.random.RandomState(seed)
    labels = rng.randint(0, n_classes, size=n_samples).astype(np.int32)

    # Class profiles on all 12 axes
    class_profiles = np.zeros((n_classes, N_AXES), dtype=np.float32)
    for c in range(n_classes):
        for j, ax_idx in enumerate(ROBUST_AXIS_INDICES):
            class_profiles[c, ax_idx] = 0.15 + 0.7 * (c * N_ROBUST + j) / (n_classes * N_ROBUST)
        for ax_idx in range(N_AXES):
            if ax_idx not in ROBUST_AXIS_INDICES:
                class_profiles[c, ax_idx] = rng.uniform(0.3, 0.7)

    ont_features = np.zeros((n_samples, N_AXES), dtype=np.float32)
    for i in range(n_samples):
        c = labels[i]
        for ax_idx in range(N_AXES):
            noise_std = 0.05 if ax_idx in ROBUST_AXIS_INDICES else 0.15
            ont_features[i, ax_idx] = class_profiles[c, ax_idx] + rng.randn() * noise_std
    ont_features = np.clip(ont_features, 0.0, 1.0)

    # Subspace bases for each robust axis
    subspace_dim = min(10, d_model // (N_ROBUST + 1))
    subspace_bases = {}
    for ax_idx in ROBUST_AXIS_INDICES:
        raw = rng.randn(d_model, subspace_dim).astype(np.float32)
        Q, _ = np.linalg.qr(raw)
        subspace_bases[ax_idx] = Q[:, :subspace_dim]

    # Hidden states: noise + signal in each subspace
    H = rng.randn(n_samples, d_model).astype(np.float32)
    for ax_idx in ROBUST_AXIS_INDICES:
        basis = subspace_bases[ax_idx]
        for i in range(n_samples):
            signal_vec = basis[:, 0] * ont_features[i, ax_idx] * signal_snr
            for k in range(1, min(3, subspace_dim)):
                signal_vec += basis[:, k] * rng.randn() * 0.3
            H[i] += signal_vec

    valid_mask = np.ones(n_samples, dtype=bool)

    # Split
    perm = rng.permutation(n_samples)
    n_test = int(n_samples * test_frac)
    n_val = int(n_samples * val_frac)
    n_train = n_samples - n_val - n_test

    def _make(indices, name):
        return EvalDataset(
            hidden_states=H[indices].copy(),
            ont_features=ont_features[indices].copy(),
            valid_mask=valid_mask[indices].copy(),
            labels=labels[indices].copy(),
            split=name,
        )

    return _make(perm[:n_train], "train"), _make(perm[n_train:n_train + n_val], "val"), _make(perm[n_train + n_val:], "test")


def generate_shifted_dataset(
    base: EvalDataset,
    shift_type: str = "noise",
    seed: int = 99,
) -> EvalDataset:
    """Generate a distribution-shifted version of the dataset."""
    rng = np.random.RandomState(seed)
    H = base.hidden_states.copy()

    if shift_type == "noise":
        H += rng.randn(*H.shape).astype(np.float32) * 2.0
    elif shift_type == "scale":
        H *= 0.5
    elif shift_type == "rotate":
        d = H.shape[1]
        A = rng.randn(d, d).astype(np.float32) * 0.1
        H = H @ (np.eye(d, dtype=np.float32) + (A - A.T) * 0.05)
    else:
        raise ValueError(f"Unknown shift_type: {shift_type}")

    return EvalDataset(
        hidden_states=H, ont_features=base.ont_features.copy(),
        valid_mask=base.valid_mask.copy(), labels=base.labels.copy(),
        split=f"shifted_{shift_type}",
    )


# ---------------------------------------------------------------------------
# Phase 2: Evaluation metrics
# ---------------------------------------------------------------------------

def compute_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1.0 - ss_res / max(ss_tot, 1e-10))


def compute_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def compute_rank_correlation(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    n = len(y_true)
    if n < 3:
        return 0.0
    ranks_true = np.argsort(np.argsort(y_true)).astype(float)
    ranks_pred = np.argsort(np.argsort(y_pred)).astype(float)
    d = ranks_true - ranks_pred
    return float(1.0 - 6.0 * np.sum(d ** 2) / (n * (n ** 2 - 1)))


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn,
    n_bootstrap: int = 500,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """Returns (point_estimate, ci_low, ci_high)."""
    rng = np.random.RandomState(seed)
    n = len(y_true)
    point = metric_fn(y_true, y_pred)
    boot_vals = []
    for _ in range(n_bootstrap):
        idx = rng.randint(0, n, size=n)
        boot_vals.append(metric_fn(y_true[idx], y_pred[idx]))
    alpha = (1 - ci) / 2
    return point, float(np.percentile(boot_vals, alpha * 100)), float(np.percentile(boot_vals, (1 - alpha) * 100))


# ---------------------------------------------------------------------------
# Phase 2: Monitor evaluation
# ---------------------------------------------------------------------------

def evaluate_monitor(
    monitor: OntologyMonitor,
    dataset: EvalDataset,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Any]:
    """Per-axis R², MAE, rank correlation with 95% CIs."""
    result = monitor.predict(dataset.hidden_states)
    pred = result.z_ont
    gt = dataset.ont_features[:, ROBUST_AXIS_INDICES]

    metrics: Dict[str, Any] = {"split": dataset.split, "n_samples": dataset.N, "per_axis": {}}
    r2_vals, mae_vals, rho_vals = [], [], []

    for j, axis_name in enumerate(ROBUST_AXES):
        y_true, y_pred = gt[:, j], pred[:, j]
        r2, r2_lo, r2_hi = bootstrap_ci(y_true, y_pred, compute_r2, n_bootstrap, seed=seed + j)
        mae, mae_lo, mae_hi = bootstrap_ci(y_true, y_pred, compute_mae, n_bootstrap, seed=seed + j + 100)
        rho, rho_lo, rho_hi = bootstrap_ci(y_true, y_pred, compute_rank_correlation, n_bootstrap, seed=seed + j + 200)
        metrics["per_axis"][axis_name] = {
            "r2": r2, "r2_ci": [r2_lo, r2_hi],
            "mae": mae, "mae_ci": [mae_lo, mae_hi],
            "rank_corr": rho, "rank_corr_ci": [rho_lo, rho_hi],
        }
        r2_vals.append(r2); mae_vals.append(mae); rho_vals.append(rho)

    metrics["mean_r2"] = float(np.mean(r2_vals))
    metrics["mean_mae"] = float(np.mean(mae_vals))
    metrics["mean_rank_corr"] = float(np.mean(rho_vals))
    return metrics


# ---------------------------------------------------------------------------
# Phase 2: Injector evaluation
# ---------------------------------------------------------------------------

INJECTOR_TEST_CASES: List[Dict[str, Any]] = [
    # Concrete
    {"text": "The cat sat on the mat.", "expected_domain": "concrete"},
    {"text": "Water flows downhill through the rocky canyon.", "expected_domain": "concrete"},
    {"text": "The red car is parked in front of the house.", "expected_domain": "concrete"},
    {"text": "A dog chased the ball across the green field.", "expected_domain": "concrete"},
    {"text": "The stone wall crumbled under the weight.", "expected_domain": "concrete"},
    {"text": "She placed the book on the wooden table.", "expected_domain": "concrete"},
    {"text": "The fire burned through the dry wood quickly.", "expected_domain": "concrete"},
    {"text": "Rain fell on the metal roof all night.", "expected_domain": "concrete"},
    # Abstract
    {"text": "Democracy requires the consent of the governed.", "expected_domain": "abstract"},
    {"text": "The concept of justice varies across cultures.", "expected_domain": "abstract"},
    {"text": "If the hypothesis holds, then the theory is validated.", "expected_domain": "abstract"},
    {"text": "Freedom and responsibility are fundamentally intertwined.", "expected_domain": "abstract"},
    {"text": "The epistemological foundations of science require careful scrutiny.", "expected_domain": "abstract"},
    {"text": "Although the correlation is strong, causation is not established.", "expected_domain": "abstract"},
    {"text": "Every theoretical framework has implicit assumptions.", "expected_domain": "abstract"},
    # Action-oriented
    {"text": "Run the tests and deploy to production.", "expected_intent": "action"},
    {"text": "Build the Docker container and push to the registry.", "expected_intent": "action"},
    {"text": "Find all broken links and fix them immediately.", "expected_intent": "action"},
    {"text": "Open the door, walk through, and close it behind you.", "expected_intent": "action"},
    {"text": "Write a function that sorts the array in place.", "expected_intent": "action"},
    {"text": "Start the server, run migrations, and seed the database.", "expected_intent": "action"},
    {"text": "Take the keys, go to the store, and buy milk.", "expected_intent": "action"},
    # Modification-heavy
    {"text": "The extremely carefully crafted beautifully ornate design.", "expected_structure": "complex"},
    {"text": "Running quickly and silently through heavily forested areas.", "expected_structure": "complex"},
    {"text": "The remarkably impressive overwhelmingly positive results.", "expected_structure": "complex"},
    {"text": "Slowly, deliberately, and thoughtfully he composed his response.", "expected_structure": "complex"},
    # Technical / mixed
    {"text": "Implement a distributed database with eventual consistency.", "expected_domain": "mixed"},
    {"text": "The algorithm has O(n log n) time complexity.", "expected_domain": "mixed"},
    {"text": "Configure the load balancer for round-robin distribution.", "expected_domain": "mixed"},
    {"text": "The neural network converges after 100 epochs.", "expected_domain": "mixed"},
    {"text": "Optimize the SQL query by adding composite indexes.", "expected_domain": "mixed"},
    # Short / minimal
    {"text": "Hello.", "expected_confidence": "low"},
    {"text": "Yes or no?", "expected_confidence": "low"},
    {"text": "Why?", "expected_confidence": "low"},
    # Long / rich
    {"text": "The ancient oak tree, standing tall and majestic in the center of the village square, "
             "had witnessed generations of celebrations, mourning, and quiet contemplation beneath "
             "its sprawling branches.", "expected_domain": "concrete"},
    {"text": "Despite numerous philosophical objections and deeply held reservations about the "
             "fundamental epistemological limitations of purely empirical approaches to understanding "
             "consciousness, the research program has yielded surprisingly actionable insights.",
     "expected_domain": "abstract"},
    # Questions
    {"text": "What is the meaning of life?", "expected_domain": "abstract"},
    {"text": "Where is the nearest gas station?", "expected_domain": "concrete"},
    {"text": "How does photosynthesis work?", "expected_domain": "mixed"},
    {"text": "Can you explain quantum entanglement?", "expected_domain": "abstract"},
    # Imperative
    {"text": "Stop the process immediately.", "expected_intent": "action"},
    {"text": "Please read this document carefully.", "expected_intent": "action"},
    {"text": "Make sure to close all open connections.", "expected_intent": "action"},
    # Emotional / reflective
    {"text": "I feel overwhelmed by the complexity of it all.", "expected_domain": "abstract"},
    {"text": "The sunset over the ocean was breathtakingly beautiful.", "expected_domain": "concrete"},
    {"text": "Happiness is not something you find but something you create.", "expected_domain": "abstract"},
    # Mixed domain
    {"text": "The computer crashed because of a memory leak in the garbage collector.", "expected_domain": "concrete"},
    {"text": "We need to rethink our approach to sustainable urban development.", "expected_domain": "abstract"},
    {"text": "The bridge between theory and practice is built through experimentation.", "expected_domain": "abstract"},
]


def evaluate_injector(injector: OntologyInjector) -> Dict[str, Any]:
    """Evaluate OntologyInjector on diverse English text."""
    results: Dict[str, Any] = {
        "n_test_cases": len(INJECTOR_TEST_CASES),
        "classifications": [],
        "format_checks": {"all_valid_tags": True, "all_valid_scores": True},
        "accuracy": {"domain": {"correct": 0, "total": 0},
                     "intent": {"correct": 0, "total": 0},
                     "structure": {"correct": 0, "total": 0}},
        "consistency_check": True,
        "coverage": 0,
    }
    n_ok = 0

    for case in INJECTOR_TEST_CASES:
        text = case["text"]
        try:
            meta = injector.classify(text)
            enriched = injector.inject("You are helpful.", text)

            results["classifications"].append({
                "text": text[:60], "domain": meta.domain, "structure": meta.structure,
                "intent": meta.intent, "confidence": meta.confidence,
                "primary_role": meta.primary_role,
                "scores": {k: round(v, 4) for k, v in meta.raw_scores.items()},
            })

            if "[ONTOLOGY]" not in enriched or "[/ONTOLOGY]" not in enriched:
                results["format_checks"]["all_valid_tags"] = False
            for v in meta.raw_scores.values():
                if not (0.0 <= v <= 1.0):
                    results["format_checks"]["all_valid_scores"] = False

            for key in ("domain", "intent", "structure"):
                if f"expected_{key}" in case:
                    results["accuracy"][key]["total"] += 1
                    if getattr(meta, key) == case[f"expected_{key}"]:
                        results["accuracy"][key]["correct"] += 1

            meta2 = injector.classify(text)
            if meta.domain != meta2.domain or meta.intent != meta2.intent or meta.structure != meta2.structure:
                results["consistency_check"] = False

            n_ok += 1
        except Exception as e:
            results["classifications"].append({"text": text[:60], "error": str(e)})

    results["coverage"] = n_ok / max(len(INJECTOR_TEST_CASES), 1)
    for key in ("domain", "intent", "structure"):
        acc = results["accuracy"][key]
        acc["rate"] = acc["correct"] / max(acc["total"], 1)
    return results


# ---------------------------------------------------------------------------
# Phase 2: Drift detection
# ---------------------------------------------------------------------------

def evaluate_drift_detection(
    monitor: OntologyMonitor,
    in_dist: EvalDataset,
    shifted: EvalDataset,
) -> Dict[str, Any]:
    in_result = monitor.predict(in_dist.hidden_states)
    shifted_result = monitor.predict(shifted.hidden_states)
    return {
        "in_distribution_drift": in_result.drift_score,
        "shifted_drift": shifted_result.drift_score,
        "drift_ratio": shifted_result.drift_score / max(in_result.drift_score, 1e-6),
        "shift_detected": shifted_result.drift_score > in_result.drift_score * 1.5,
    }


# ---------------------------------------------------------------------------
# Phase 1: Part runners
# ---------------------------------------------------------------------------

def run_part3_disentanglement(
    states: Dict[int, np.ndarray],
    layers: List[int],
    cfg: DisentanglementConfig,
) -> Dict[int, Dict[str, Any]]:
    """Part 3: PCA + SAE + K-means on each layer."""
    results = {}
    for layer_idx in layers:
        H = states[layer_idx]
        dr = run_disentanglement(H, layer_idx, cfg)

        sparsity_info = {}
        if dr.sae_features is not None:
            l0 = (dr.sae_features > 0).sum(axis=1)
            sparsity_info = {
                "mean_l0": float(l0.mean()),
                "std_l0": float(l0.std()),
                "pct_active": float(l0.mean() / dr.sae_features.shape[1] * 100),
                "sae_dim": dr.sae_features.shape[1],
                "reconstruction_loss": dr.sae_reconstruction_loss,
            }

        results[layer_idx] = {
            "pca_cumvar_90": float(dr.pca_cumulative_variance[-1])
                if dr.pca_cumulative_variance is not None else 0.0,
            "n_pca_components": len(dr.pca_explained_variance)
                if dr.pca_explained_variance is not None else 0,
            "n_clusters": len(np.unique(dr.cluster_labels))
                if dr.cluster_labels is not None else 0,
            **sparsity_info,
        }
        print(f"  Layer {layer_idx}: PCA cumvar={results[layer_idx]['pca_cumvar_90']:.1%}, "
              f"SAE active={sparsity_info.get('pct_active', 0):.1f}%, "
              f"clusters={results[layer_idx]['n_clusters']}")

    return results


def run_part4_mdl(
    states: Dict[int, np.ndarray],
    labels: np.ndarray,
    layers: List[int],
    cfg: MDLProbeConfig,
) -> tuple[Dict[int, Dict], Dict[int, Any], int]:
    """Part 4: MDL probing per layer. Returns results, raw objects, optimal_k."""
    mdl_results = {}
    mdl_objects = {}

    for layer_idx in layers:
        H = states[layer_idx]
        r = run_mdl_probe(H, labels, layer_idx, "role", cfg)
        mdl_objects[layer_idx] = r
        mdl_results[layer_idx] = {
            "compression_ratio": r.compression_ratio,
            "compression_vs_uniform": r.compression_vs_uniform,
            "bits_per_label": r.online_code_length / max(r.n_samples, 1),
            "n_classes": r.n_classes,
        }
        print(f"  Layer {layer_idx}: compression={r.compression_ratio:.2f}x (vs prior), "
              f"{r.compression_vs_uniform:.2f}x (vs uniform), "
              f"bits/label={r.online_code_length / max(r.n_samples, 1):.3f}")

    best_layer = max(mdl_results, key=lambda l: mdl_results[l]["compression_ratio"])
    H_best = states[best_layer]
    candidate_ks = [4, 8, 16, 32]
    optimal_k, _, _pca_basis = select_top_k_components(
        H_best, labels, best_layer, "role", candidate_ks, cfg,
    )
    print(f"  Best layer: {best_layer}, optimal k: {optimal_k}")

    return mdl_results, mdl_objects, optimal_k


def run_part5_intervention_synthetic(
    states: Dict[int, np.ndarray],
    labels: np.ndarray,
    layers: List[int],
    d_model: int,
    n_layers: int,
    subspace_k: int,
    n_pairs: int = 20,
    seed: int = 42,
) -> Dict[int, Dict]:
    """Part 5: Causal intervention using a toy transformer."""
    from scripts.causal_subspace.causal_intervention import (
        InterventionConfig,
        run_causal_intervention,
    )

    model = _ToyTransformer(d_model, n_layers)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    tokenizer = _ToyTokenizer()
    cfg = InterventionConfig(n_pairs=n_pairs, device="cpu", seed=seed)
    results = {}

    for layer_idx in layers:
        H = states[layer_idx]
        U_k = build_pca_basis(H, subspace_k)
        ir = run_causal_intervention(model, tokenizer, U_k, layer_idx, cfg)
        results[layer_idx] = {
            "n_pairs": ir.n_pairs_tested,
            "flip_rate": ir.flip_rate,
            "fluency_rate": ir.fluency_rate,
            "causal_success_rate": ir.causal_success_rate,
            "control_kl_mean": ir.control_kl_mean,
            "random_kl_mean": ir.random_kl_mean,
            "specificity_ratio": ir.specificity_ratio,
            "adaptive_threshold": ir.adaptive_kl_threshold,
        }
        print(f"  Layer {layer_idx}: flip={ir.flip_rate:.1%}, "
              f"fluency={ir.fluency_rate:.1%}, "
              f"causal_success={ir.causal_success_rate:.1%}, "
              f"specificity={ir.specificity_ratio:.2f}x")

    return results


# ---------------------------------------------------------------------------
# Phase 2: Comprehensive evaluation runner
# ---------------------------------------------------------------------------

def run_phase2_comprehensive(
    d_model: int,
    n_samples: int = 5000,
    n_classes: int = 5,
    signal_snr: float = 3.0,
    n_epochs: int = 150,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run the comprehensive Phase 2 evaluation suite.

    Generates a controlled dataset at the given d_model, trains the monitor,
    and evaluates with CIs, robustness, drift, injector, and SNR analysis.
    """
    all_results: Dict[str, Any] = {
        "config": {
            "d_model": d_model, "n_samples": n_samples,
            "n_classes": n_classes, "signal_snr": signal_snr,
            "n_epochs": n_epochs, "n_bootstrap": n_bootstrap,
        },
    }

    # --- Step 1: Generate controlled dataset ---
    print(f"\n  Generating controlled dataset (N={n_samples}, d={d_model}, SNR={signal_snr})...")

    train_ds, val_ds, test_ds = generate_controlled_dataset(
        n_samples=n_samples, d_model=d_model, n_classes=n_classes,
        signal_snr=signal_snr, seed=seed,
    )
    print(f"  Train: {train_ds.N}  Val: {val_ds.N}  Test: {test_ds.N}")

    all_results["dataset"] = {
        "train_n": train_ds.N, "val_n": val_ds.N, "test_n": test_ds.N,
    }

    # --- Step 2: Train OntologyMonitor ---
    print(f"\n  Training OntologyMonitor (epochs={n_epochs})...")

    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
    train_result = monitor.train_monitor(
        H=train_ds.hidden_states, ont_features=train_ds.ont_features,
        valid_mask=train_ds.valid_mask, n_epochs=n_epochs,
        batch_size=256, val_split=0.0, seed=seed,
    )
    print(f"  Train loss: {train_result.final_train_loss:.4f}, "
          f"R² (internal): {train_result.r2_mean:.3f}")

    all_results["training"] = {
        "epochs": train_result.epochs_trained,
        "train_loss": train_result.final_train_loss,
        "r2_internal": train_result.r2_mean,
    }

    # --- Step 3: Val evaluation ---
    print(f"\n  Validation evaluation...")
    val_metrics = evaluate_monitor(monitor, val_ds, n_bootstrap=n_bootstrap, seed=seed)
    print(f"  Val R²={val_metrics['mean_r2']:.3f}  MAE={val_metrics['mean_mae']:.4f}  "
          f"rho={val_metrics['mean_rank_corr']:.3f}")
    for axis, m in val_metrics["per_axis"].items():
        print(f"    {axis:25s}  R²={m['r2']:.3f} [{m['r2_ci'][0]:.3f}, {m['r2_ci'][1]:.3f}]"
              f"  MAE={m['mae']:.4f}  rho={m['rank_corr']:.3f}")
    all_results["val_metrics"] = val_metrics

    # --- Step 4: Test evaluation (held-out) ---
    print(f"\n  Test evaluation (held-out)...")
    test_metrics = evaluate_monitor(monitor, test_ds, n_bootstrap=n_bootstrap, seed=seed + 1)
    print(f"  Test R²={test_metrics['mean_r2']:.3f}  MAE={test_metrics['mean_mae']:.4f}  "
          f"rho={test_metrics['mean_rank_corr']:.3f}")
    for axis, m in test_metrics["per_axis"].items():
        print(f"    {axis:25s}  R²={m['r2']:.3f} [{m['r2_ci'][0]:.3f}, {m['r2_ci'][1]:.3f}]"
              f"  MAE={m['mae']:.4f}  rho={m['rank_corr']:.3f}")
    all_results["test_metrics"] = test_metrics

    # --- Step 5: Robustness under distribution shift ---
    print(f"\n  Robustness under distribution shift...")
    shift_results = {}
    for shift_type in ["noise", "scale", "rotate"]:
        shifted_ds = generate_shifted_dataset(test_ds, shift_type=shift_type, seed=seed + 10)
        shift_m = evaluate_monitor(monitor, shifted_ds, n_bootstrap=min(n_bootstrap, 200), seed=seed + 20)
        shift_results[shift_type] = shift_m
        drop = test_metrics["mean_r2"] - shift_m["mean_r2"]
        print(f"    {shift_type:8s}  R²={shift_m['mean_r2']:.3f}  (drop={drop:+.3f})")
    all_results["robustness"] = shift_results

    # --- Step 6: Drift detection ---
    print(f"\n  Drift detection validation...")
    drift_results = {}
    for shift_type in ["noise", "scale", "rotate"]:
        shifted_ds = generate_shifted_dataset(test_ds, shift_type=shift_type, seed=seed + 30)
        drift = evaluate_drift_detection(monitor, test_ds, shifted_ds)
        drift_results[shift_type] = drift
        detected = "YES" if drift["shift_detected"] else "NO"
        print(f"    {shift_type:8s}  in={drift['in_distribution_drift']:.3f}  "
              f"shifted={drift['shifted_drift']:.3f}  "
              f"ratio={drift['drift_ratio']:.2f}x  detected={detected}")
    all_results["drift_detection"] = drift_results

    # --- Step 7: Injector evaluation ---
    print(f"\n  OntologyInjector evaluation ({len(INJECTOR_TEST_CASES)} sentences)...")
    injector = OntologyInjector()
    injector_results = evaluate_injector(injector)

    print(f"  Coverage: {injector_results['coverage']:.0%}  "
          f"Tags: {injector_results['format_checks']['all_valid_tags']}  "
          f"Deterministic: {injector_results['consistency_check']}")
    for key in ("domain", "intent", "structure"):
        acc = injector_results["accuracy"][key]
        if acc["total"] > 0:
            print(f"    {key:12s} accuracy: {acc['correct']}/{acc['total']} ({acc['rate']:.0%})")

    print(f"\n  Sample classifications:")
    for entry in injector_results["classifications"][:6]:
        if "error" not in entry:
            print(f"    '{entry['text'][:45]:45s}' -> "
                  f"{entry['domain']}/{entry['structure']}/{entry['intent']} "
                  f"({entry['confidence']})")
    all_results["injector"] = injector_results

    # --- Step 8: SNR sensitivity ---
    print(f"\n  SNR sensitivity analysis...")
    snr_results = {}
    for snr in [0.5, 1.0, 2.0, 3.0, 5.0]:
        train_s, _, test_s = generate_controlled_dataset(
            n_samples=min(n_samples, 2000), d_model=d_model,
            n_classes=n_classes, signal_snr=snr, seed=seed + int(snr * 10),
        )
        m = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
        m.train_monitor(
            H=train_s.hidden_states, ont_features=train_s.ont_features,
            valid_mask=train_s.valid_mask, n_epochs=min(n_epochs, 80),
            batch_size=256, val_split=0.0, seed=seed,
        )
        test_m = evaluate_monitor(m, test_s, n_bootstrap=min(n_bootstrap, 100), seed=seed)
        snr_results[snr] = test_m["mean_r2"]
        print(f"    SNR={snr:.1f}  ->  test R²={test_m['mean_r2']:.3f}")
    all_results["snr_sensitivity"] = snr_results

    # --- Step 9: JEPA-Observatory Integration (Part 8) ---
    print(f"\n  JEPA-Observatory Integration (Part 8)...")

    integration_results = run_integration_evaluation(
        hidden_states=train_ds.hidden_states,
        ont_features=train_ds.ont_features,
        valid_mask=train_ds.valid_mask,
        d_model=d_model,
        state_dim=32,
        n_epochs_bridge=min(n_epochs, 100),
        n_epochs_monitor=min(n_epochs, 80),
        seed=seed,
    )
    all_results["jepa_integration"] = integration_results

    int_scenario = integration_results.get("scenario", {})
    print(f"  Integration scenario: {int_scenario.get('classification', '?')} "
          f"({int_scenario.get('recommended_architecture', '?')})")
    for ev in int_scenario.get("evidence", []):
        print(f"    {ev}")

    bridge_r2 = integration_results.get("bridge", {}).get("r2_mean", 0.0)
    print(f"  Bridge R²: {bridge_r2:.3f}")

    for anom_type, anom_data in integration_results.get("anomaly_detection", {}).items():
        print(f"    {anom_type:20s}  JEPA={anom_data['jepa_auc']:.3f}  "
              f"Ont={anom_data['ontology_auc']:.3f}  "
              f"Combined={anom_data['combined_auc']:.3f}")

    # --- Collect Phase 2 checks ---
    checks: List[Tuple[str, bool, str]] = []

    test_r2 = test_metrics["mean_r2"]
    checks.append(("Monitor test R² > 0.3", test_r2 > 0.3, f"R²={test_r2:.3f}"))

    all_positive = all(m["r2"] > 0 for m in test_metrics["per_axis"].values())
    checks.append(("All per-axis R² > 0", all_positive, ""))

    gap = abs(val_metrics["mean_r2"] - test_metrics["mean_r2"])
    checks.append(("Val-test R² gap < 0.1", gap < 0.1, f"gap={gap:.3f}"))

    rho = test_metrics["mean_rank_corr"]
    checks.append(("Test rank corr > 0.3", rho > 0.3, f"rho={rho:.3f}"))

    if "noise" in shift_results:
        noise_r2 = shift_results["noise"]["mean_r2"]
        drop_pct = (test_r2 - noise_r2) / max(abs(test_r2), 1e-6)
        checks.append(("Noise robustness (R² drop < 50%)", drop_pct < 0.5, f"drop={drop_pct:.0%}"))

    n_detected = sum(1 for d in drift_results.values() if d["shift_detected"])
    checks.append(("Drift detection fires (>=2/3)", n_detected >= 2, f"{n_detected}/3"))

    checks.append(("Injector 100% coverage", injector_results["coverage"] >= 1.0,
                    f"{injector_results['coverage']:.0%}"))
    checks.append(("Injector deterministic", injector_results["consistency_check"], ""))
    checks.append(("Injector format valid",
                    injector_results["format_checks"]["all_valid_tags"]
                    and injector_results["format_checks"]["all_valid_scores"], ""))

    snr_vals = sorted(snr_results.keys())
    if len(snr_vals) >= 3:
        checks.append(("R² increases with SNR",
                        snr_results[snr_vals[-1]] > snr_results[snr_vals[0]],
                        f"SNR={snr_vals[0]:.0f}->{snr_results[snr_vals[0]]:.3f}, "
                        f"SNR={snr_vals[-1]:.0f}->{snr_results[snr_vals[-1]]:.3f}"))

    dom_acc = injector_results["accuracy"]["domain"]
    if dom_acc["total"] > 0:
        checks.append(("Injector domain accuracy > 50%", dom_acc["rate"] > 0.5,
                        f"{dom_acc['correct']}/{dom_acc['total']} ({dom_acc['rate']:.0%})"))

    # Part 8: JEPA-Observatory Integration checks
    for int_check in integration_results.get("checks", []):
        checks.append((
            f"[Part 8] {int_check['name']}",
            int_check["passed"],
            int_check.get("detail", ""),
        ))

    all_results["checks"] = [
        {"name": n, "passed": p, "detail": d} for n, p, d in checks
    ]
    all_results["monitor_r2_mean"] = test_r2
    all_results["monitor_inference_ok"] = True
    all_results["injector_format_ok"] = (
        injector_results["format_checks"]["all_valid_tags"]
        and injector_results["format_checks"]["all_valid_scores"]
    )

    return all_results


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_synthetic_pipeline(
    n_samples: int = 500,
    d_model: int = 64,
    n_layers: int = 6,
    n_classes: int = 5,
    sae_epochs: int = 10,
    sae_expansion: int = 2,
    n_clusters: int = 8,
    mdl_portions: int = 8,
    n_pairs: int = 20,
    subspace_k: int = 8,
    layers: Optional[List[int]] = None,
    parts: Optional[List[int]] = None,
    run_phase2: bool = False,
    phase2_epochs: int = 50,
    phase2_samples: int = 5000,
    phase2_snr: float = 3.0,
    phase2_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run the full causal subspace pipeline on synthetic data.

    Phase 1 (Parts 3-6) tests disentanglement, MDL, intervention, trajectory.
    Phase 2 (Part 7) tests monitor + injector with comprehensive evaluation.
    """
    parts_to_run = set(parts) if parts else {3, 4, 5, 6}

    results: Dict[str, Any] = {
        "mode": "synthetic",
        "config": {
            "n_samples": n_samples, "d_model": d_model,
            "n_layers": n_layers, "n_classes": n_classes,
            "subspace_k": subspace_k,
        },
    }

    t0 = time.time()

    # --- Generate Phase 1 synthetic data ---
    run_phase1 = bool(parts_to_run & {3, 4, 5, 6})

    if run_phase1:
        print("\n" + "=" * 70)
        print("GENERATING SYNTHETIC DATA")
        print("=" * 70)

        states, labels = generate_synthetic_hidden_states(
            n_samples, d_model, n_layers, n_classes, seed=seed,
        )
        active_layers = layers if layers else list(range(n_layers))
        active_layers = [l for l in active_layers if l < n_layers]

        unique, counts = np.unique(labels, return_counts=True)
        dist = ", ".join(f"class_{u}={c}" for u, c in zip(unique, counts))
        print(f"  Samples: {n_samples}, Dimension: {d_model}, Layers: {n_layers}")
        print(f"  Classes: {n_classes} — {dist}")
        print(f"  Active layers: {active_layers}")

        results["data"] = {
            "n_samples": n_samples, "n_layers": n_layers,
            "class_distribution": {int(u): int(c) for u, c in zip(unique, counts)},
        }
    else:
        active_layers = []

    # --- Part 3: Disentanglement ---
    optimal_k = subspace_k
    mdl_objects = None

    if 3 in parts_to_run:
        print("\n" + "=" * 70)
        print("PART 3: FEATURE DISENTANGLEMENT (PCA + SAE + CLUSTERING)")
        print("=" * 70)

        dis_cfg = DisentanglementConfig(
            sae_expansion_factor=sae_expansion,
            sae_epochs=sae_epochs,
            sae_batch_size=min(256, n_samples),
            n_clusters=n_clusters,
            seed=seed,
            device="cpu",
        )
        results["disentanglement"] = run_part3_disentanglement(
            states, active_layers, dis_cfg,
        )

    # --- Part 4: MDL Probing ---
    if 4 in parts_to_run:
        print("\n" + "=" * 70)
        print("PART 4: MDL PROBING (INFORMATION-THEORETIC VALIDATION)")
        print("=" * 70)

        mdl_cfg = MDLProbeConfig(
            n_portions=mdl_portions, probe_epochs=15,
            seed=seed, device="cpu",
        )
        mdl_results, mdl_objects, optimal_k = run_part4_mdl(
            states, labels, active_layers, mdl_cfg,
        )
        results["mdl_probing"] = mdl_results
        results["optimal_k"] = optimal_k

    # --- Part 5: Causal Intervention ---
    if 5 in parts_to_run:
        print("\n" + "=" * 70)
        print("PART 5: CAUSAL INTERCHANGE INTERVENTION (THE ACID TEST)")
        print("=" * 70)

        if len(active_layers) > 3:
            mid = len(active_layers) // 2
            int_layers = [active_layers[0], active_layers[mid], active_layers[-1]]
        else:
            int_layers = active_layers

        results["causal_intervention"] = run_part5_intervention_synthetic(
            states, labels, int_layers, d_model, n_layers,
            optimal_k, n_pairs, seed,
        )

    # --- Part 6: Layer Trajectory ---
    if 6 in parts_to_run:
        print("\n" + "=" * 70)
        print("PART 6: LAYER TRAJECTORY MAPPING")
        print("=" * 70)

        mdl_cfg = MDLProbeConfig(
            n_portions=mdl_portions, probe_epochs=15,
            seed=seed, device="cpu",
        )
        trajectory = compute_layer_trajectory(
            hidden_states={l: states[l] for l in active_layers},
            labels=labels,
            label_name="synthetic_role",
            subspace_k=optimal_k,
            mdl_cfg=mdl_cfg,
            run_interventions=False,
            precomputed_mdl=mdl_objects,
        )
        print("\n" + plot_trajectory_ascii(trajectory))

        results["trajectory"] = {
            "layers": trajectory.layers,
            "mdl_compression": trajectory.mdl_compression,
            "crystallization_layer": trajectory.crystallization_layer,
            "consumption_layer": trajectory.consumption_layer,
            "peak_compression": trajectory.peak_compression,
        }

    # --- Phase 2: Comprehensive Monitor + Injector evaluation (Parts 7-8) ---
    if run_phase2 or 7 in parts_to_run or 8 in parts_to_run:
        print("\n" + "=" * 70)
        print("PHASE 2: COMPREHENSIVE MONITOR + INJECTOR EVALUATION")
        print("=" * 70)

        results["phase2"] = run_phase2_comprehensive(
            d_model=d_model,
            n_samples=phase2_samples,
            n_classes=n_classes,
            signal_snr=phase2_snr,
            n_epochs=phase2_epochs,
            n_bootstrap=phase2_bootstrap,
            seed=seed,
        )

    # --- Unified Summary ---
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("UNIFIED VALIDATION SUMMARY")
    print("=" * 70)

    n_checks = 0
    n_pass = 0

    def _check(name: str, passed: bool, detail: str = ""):
        nonlocal n_checks, n_pass
        n_checks += 1
        if passed:
            n_pass += 1
        status = "PASS" if passed else "FAIL"
        detail_str = f"  ({detail})" if detail else ""
        print(f"  [{status}] {name}{detail_str}")

    # Phase 1 checks
    if "mdl_probing" in results:
        for layer_idx in active_layers:
            if layer_idx in results["mdl_probing"]:
                comp = results["mdl_probing"][layer_idx]["compression_ratio"]
                _check(f"Layer {layer_idx} MDL compression > 1", comp > 1.0, f"{comp:.2f}x")

    if "mdl_probing" in results and len(active_layers) >= 4:
        first_half = [results["mdl_probing"][l]["compression_ratio"]
                      for l in active_layers[:len(active_layers)//2]
                      if l in results["mdl_probing"]]
        second_half = [results["mdl_probing"][l]["compression_ratio"]
                       for l in active_layers[len(active_layers)//2:]
                       if l in results["mdl_probing"]]
        if first_half and second_half:
            _check("Later layers compress better",
                   np.mean(second_half) > np.mean(first_half),
                   f"first={np.mean(first_half):.2f}x, second={np.mean(second_half):.2f}x")

    if "disentanglement" in results:
        for layer_idx in active_layers:
            if layer_idx in results["disentanglement"]:
                pct = results["disentanglement"][layer_idx].get("pct_active", 100)
                _check(f"Layer {layer_idx} SAE sparsity", 0.5 < pct < 95, f"{pct:.1f}% active")

    if "trajectory" in results:
        crystal = results["trajectory"]["crystallization_layer"]
        _check("Crystallization layer found", crystal >= 0, f"layer {crystal}")

    # Phase 2 checks
    if "phase2" in results:
        p2 = results["phase2"]
        for chk in p2.get("checks", []):
            _check(chk["name"], chk["passed"], chk["detail"])

    print(f"\n  Result: {n_pass}/{n_checks} checks passed")
    print(f"  Elapsed: {elapsed:.1f}s")
    print("=" * 70)

    results["summary"] = {
        "checks_passed": n_pass,
        "checks_total": n_checks,
        "elapsed_seconds": elapsed,
    }

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end synthetic evaluation (Phase 1 + Phase 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Phase 1 only
  python scripts/causal_subspace/test_synthetic.py

  # Phase 1 + Phase 2
  python scripts/causal_subspace/test_synthetic.py --run-phase2

  # Quick smoke test (both phases)
  python scripts/causal_subspace/test_synthetic.py --quick --run-phase2

  # Phase 2 only
  python scripts/causal_subspace/test_synthetic.py --parts 7

  # Save results
  python scripts/causal_subspace/test_synthetic.py --run-phase2 --output results.json
        """,
    )
    # Phase 1 args
    parser.add_argument("--n-samples", type=int, default=500,
                        help="Phase 1 token samples (default: 500)")
    parser.add_argument("--d-model", type=int, default=64,
                        help="Hidden dimension (default: 64)")
    parser.add_argument("--n-layers", type=int, default=6,
                        help="Simulated transformer layers (default: 6)")
    parser.add_argument("--n-classes", type=int, default=5,
                        help="Structural classes (default: 5)")
    parser.add_argument("--sae-epochs", type=int, default=10)
    parser.add_argument("--sae-expansion", type=int, default=2)
    parser.add_argument("--n-clusters", type=int, default=8)
    parser.add_argument("--mdl-portions", type=int, default=8)
    parser.add_argument("--n-pairs", type=int, default=20)
    parser.add_argument("--subspace-k", type=int, default=8)
    parser.add_argument("--layers", type=int, nargs="*", default=None)
    parser.add_argument("--parts", type=int, nargs="*", default=None,
                        help="Parts to run (3-6=Phase1, 7=Phase2, 8=JEPA Integration)")
    # Phase 2 args
    parser.add_argument("--run-phase2", action="store_true",
                        help="Run Phase 2 comprehensive evaluation")
    parser.add_argument("--phase2-epochs", type=int, default=150,
                        help="Phase 2 monitor training epochs (default: 150)")
    parser.add_argument("--phase2-samples", type=int, default=5000,
                        help="Phase 2 controlled dataset size (default: 5000)")
    parser.add_argument("--phase2-snr", type=float, default=3.0,
                        help="Phase 2 signal-to-noise ratio (default: 3.0)")
    parser.add_argument("--phase2-bootstrap", type=int, default=500,
                        help="Bootstrap resamples for CIs (default: 500)")
    # Common
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (reduced data)")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.quick:
        args.n_samples = min(args.n_samples, 200)
        args.n_layers = min(args.n_layers, 4)
        args.sae_epochs = min(args.sae_epochs, 3)
        args.n_pairs = min(args.n_pairs, 5)
        args.n_clusters = min(args.n_clusters, 4)
        args.phase2_epochs = min(args.phase2_epochs, 50)
        args.phase2_samples = min(args.phase2_samples, 1000)
        args.phase2_bootstrap = min(args.phase2_bootstrap, 100)

    results = run_synthetic_pipeline(
        n_samples=args.n_samples,
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_classes=args.n_classes,
        sae_epochs=args.sae_epochs,
        sae_expansion=args.sae_expansion,
        n_clusters=args.n_clusters,
        mdl_portions=args.mdl_portions,
        n_pairs=args.n_pairs,
        subspace_k=args.subspace_k,
        layers=args.layers,
        parts=args.parts,
        run_phase2=args.run_phase2,
        phase2_epochs=args.phase2_epochs,
        phase2_samples=args.phase2_samples,
        phase2_snr=args.phase2_snr,
        phase2_bootstrap=args.phase2_bootstrap,
        seed=args.seed,
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
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=_serialize)
        print(f"\nResults saved to {output_path}")

    summary = results.get("summary", {})
    if summary.get("checks_passed", 0) < summary.get("checks_total", 0):
        sys.exit(1)

    return results


if __name__ == "__main__":
    main()
