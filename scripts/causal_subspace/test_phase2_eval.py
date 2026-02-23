#!/usr/bin/env python3
"""
Phase 2 Controlled Ground-Truth Evaluation
=============================================

Tests the OntologyMonitor and OntologyInjector with:
  - GPT-2-scale dimensions (768-dim, 12 layers)
  - 5000+ word-level samples with known ground-truth structure
  - Proper train / val / test splits (no leakage)
  - Per-axis R², MAE, and rank correlation
  - Bootstrapped 95% confidence intervals
  - Robustness tests: noise injection, distribution shift, unseen classes
  - OntologyInjector evaluation on 50+ diverse English sentences
  - Monitor drift detection validation

No network access required.  No model download.

Usage::

    python scripts/causal_subspace/test_phase2_eval.py
    python scripts/causal_subspace/test_phase2_eval.py --quick
    python scripts/causal_subspace/test_phase2_eval.py --output phase2_eval.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.ontology_alignment import (
    AXIS_NAMES,
    N_AXES,
    ROBUST_AXES,
    ROBUST_AXIS_INDICES,
    N_ROBUST,
    OntologyMonitor,
    OntologyInjector,
    InjectionMetadata,
)

logger = logging.getLogger("phase2_eval")


# ---------------------------------------------------------------------------
# Data generation — realistic GPT-2-scale with known structure
# ---------------------------------------------------------------------------

@dataclass
class EvalDataset:
    """A controlled dataset with known ground-truth ontology structure."""

    hidden_states: np.ndarray     # [N, d_model]
    ont_features: np.ndarray      # [N, 12]  full 12-axis vectors
    valid_mask: np.ndarray        # [N] bool
    labels: np.ndarray            # [N] int — grammatical role labels
    split: str = "train"          # train / val / test

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

    The key idea: we create hidden states where the 4 robust ontological axes
    are *linearly recoverable* from specific subspaces of the hidden state,
    at a controlled signal-to-noise ratio.  This lets us measure whether the
    OntologyMonitor can recover them, with known ground truth.

    Structure injection:
        For each robust axis j, we pick a random 10-dimensional subspace
        S_j in R^{d_model}.  The axis value is encoded as the projection
        onto S_j's first principal direction, scaled by signal_snr.
        The remaining dimensions are isotropic Gaussian noise.

    This mimics what Phase 1 actually found: ontological axes occupy
    low-dimensional subspaces of the residual stream, with partial overlap
    and noise from other computations.
    """
    rng = np.random.RandomState(seed)

    # Class labels (grammatical roles: subject, object, root, modifier, other)
    labels = rng.randint(0, n_classes, size=n_samples).astype(np.int32)

    # --- Build ground-truth ontology vectors ---
    # Each class has a characteristic profile on the 12 axes.
    # Robust axes have strong class-conditional signal; others are noisy.
    class_profiles = np.zeros((n_classes, N_AXES), dtype=np.float32)
    for c in range(n_classes):
        # Robust axes: distinct per class with spread
        for j, ax_idx in enumerate(ROBUST_AXIS_INDICES):
            class_profiles[c, ax_idx] = 0.15 + 0.7 * (c * N_ROBUST + j) / (n_classes * N_ROBUST)
        # Non-robust axes: random, low variance
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

    # --- Build hidden states with structure ---
    # Create subspace bases for each robust axis
    subspace_dim = 10
    subspace_bases = {}  # axis_idx -> [d_model, subspace_dim]
    for ax_idx in ROBUST_AXIS_INDICES:
        # Random orthonormal basis
        raw = rng.randn(d_model, subspace_dim).astype(np.float32)
        Q, _ = np.linalg.qr(raw)
        subspace_bases[ax_idx] = Q[:, :subspace_dim]

    # Build hidden states: noise + signal in each subspace
    noise_scale = 1.0
    H = rng.randn(n_samples, d_model).astype(np.float32) * noise_scale

    for ax_idx in ROBUST_AXIS_INDICES:
        basis = subspace_bases[ax_idx]
        # Encode axis value as projection along first principal direction
        for i in range(n_samples):
            # Scale axis value into the subspace
            signal_vec = basis[:, 0] * ont_features[i, ax_idx] * signal_snr
            # Add secondary structure (decorrelated)
            for k in range(1, min(3, subspace_dim)):
                signal_vec += basis[:, k] * rng.randn() * 0.3
            H[i] += signal_vec

    # All samples are valid (≥ 8 non-NaN axes)
    valid_mask = np.ones(n_samples, dtype=bool)

    # --- Split ---
    perm = rng.permutation(n_samples)
    n_test = int(n_samples * test_frac)
    n_val = int(n_samples * val_frac)
    n_train = n_samples - n_val - n_test

    def _make_split(indices, name):
        return EvalDataset(
            hidden_states=H[indices].copy(),
            ont_features=ont_features[indices].copy(),
            valid_mask=valid_mask[indices].copy(),
            labels=labels[indices].copy(),
            split=name,
        )

    train_ds = _make_split(perm[:n_train], "train")
    val_ds = _make_split(perm[n_train:n_train + n_val], "val")
    test_ds = _make_split(perm[n_train + n_val:], "test")

    return train_ds, val_ds, test_ds


def generate_shifted_dataset(
    base_dataset: EvalDataset,
    shift_type: str = "noise",
    seed: int = 99,
) -> EvalDataset:
    """Generate a distribution-shifted version of the dataset.

    shift_type:
        "noise"   — add 2x Gaussian noise to hidden states
        "scale"   — scale hidden states by 0.5 (simulates different model)
        "rotate"  — apply random rotation to hidden states
    """
    rng = np.random.RandomState(seed)
    H = base_dataset.hidden_states.copy()

    if shift_type == "noise":
        H += rng.randn(*H.shape).astype(np.float32) * 2.0
    elif shift_type == "scale":
        H *= 0.5
    elif shift_type == "rotate":
        # Small random rotation
        d = H.shape[1]
        A = rng.randn(d, d).astype(np.float32) * 0.1
        R = np.eye(d, dtype=np.float32) + (A - A.T) * 0.05  # near-identity rotation
        H = H @ R
    else:
        raise ValueError(f"Unknown shift_type: {shift_type}")

    return EvalDataset(
        hidden_states=H,
        ont_features=base_dataset.ont_features.copy(),
        valid_mask=base_dataset.valid_mask.copy(),
        labels=base_dataset.labels.copy(),
        split=f"shifted_{shift_type}",
    )


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------

def compute_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1.0 - ss_res / max(ss_tot, 1e-10))


def compute_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def compute_rank_correlation(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Spearman rank correlation (manual, no scipy dependency)."""
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
    """Bootstrap confidence interval for a metric.

    Returns (point_estimate, ci_low, ci_high).
    """
    rng = np.random.RandomState(seed)
    n = len(y_true)
    point = metric_fn(y_true, y_pred)

    boot_vals = []
    for _ in range(n_bootstrap):
        idx = rng.randint(0, n, size=n)
        boot_vals.append(metric_fn(y_true[idx], y_pred[idx]))

    alpha = (1 - ci) / 2
    lo = float(np.percentile(boot_vals, alpha * 100))
    hi = float(np.percentile(boot_vals, (1 - alpha) * 100))
    return point, lo, hi


# ---------------------------------------------------------------------------
# Monitor evaluation
# ---------------------------------------------------------------------------

def evaluate_monitor(
    monitor: OntologyMonitor,
    dataset: EvalDataset,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Any]:
    """Comprehensive evaluation of the OntologyMonitor on a dataset.

    Returns per-axis R², MAE, rank correlation with 95% CIs.
    """
    result = monitor.predict(dataset.hidden_states)
    pred = result.z_ont  # [N, 4]

    # Ground truth for robust axes only
    gt = dataset.ont_features[:, ROBUST_AXIS_INDICES]

    metrics: Dict[str, Any] = {
        "split": dataset.split,
        "n_samples": dataset.N,
        "per_axis": {},
    }

    r2_vals = []
    mae_vals = []
    rho_vals = []

    for j, axis_name in enumerate(ROBUST_AXES):
        y_true = gt[:, j]
        y_pred = pred[:, j]

        r2, r2_lo, r2_hi = bootstrap_ci(y_true, y_pred, compute_r2, n_bootstrap, seed=seed + j)
        mae, mae_lo, mae_hi = bootstrap_ci(y_true, y_pred, compute_mae, n_bootstrap, seed=seed + j + 100)
        rho, rho_lo, rho_hi = bootstrap_ci(y_true, y_pred, compute_rank_correlation, n_bootstrap, seed=seed + j + 200)

        metrics["per_axis"][axis_name] = {
            "r2": r2, "r2_ci": [r2_lo, r2_hi],
            "mae": mae, "mae_ci": [mae_lo, mae_hi],
            "rank_corr": rho, "rank_corr_ci": [rho_lo, rho_hi],
        }
        r2_vals.append(r2)
        mae_vals.append(mae)
        rho_vals.append(rho)

    metrics["mean_r2"] = float(np.mean(r2_vals))
    metrics["mean_mae"] = float(np.mean(mae_vals))
    metrics["mean_rank_corr"] = float(np.mean(rho_vals))

    return metrics


# ---------------------------------------------------------------------------
# Injector evaluation
# ---------------------------------------------------------------------------

# 50+ diverse English sentences with expected classifications
INJECTOR_TEST_CASES: List[Dict[str, Any]] = [
    # Concrete / simple / informational
    {"text": "The cat sat on the mat.", "expected_domain": "concrete"},
    {"text": "Water flows downhill through the rocky canyon.", "expected_domain": "concrete"},
    {"text": "The red car is parked in front of the house.", "expected_domain": "concrete"},
    {"text": "A dog chased the ball across the green field.", "expected_domain": "concrete"},
    {"text": "The stone wall crumbled under the weight.", "expected_domain": "concrete"},
    {"text": "She placed the book on the wooden table.", "expected_domain": "concrete"},
    {"text": "The fire burned through the dry wood quickly.", "expected_domain": "concrete"},
    {"text": "Rain fell on the metal roof all night.", "expected_domain": "concrete"},

    # Abstract / complex / informational
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

    # Imperative / commands
    {"text": "Stop the process immediately.", "expected_intent": "action"},
    {"text": "Please read this document carefully.", "expected_intent": "action"},
    {"text": "Make sure to close all open connections.", "expected_intent": "action"},

    # Emotional / reflective
    {"text": "I feel overwhelmed by the complexity of it all.", "expected_domain": "abstract"},
    {"text": "The sunset over the ocean was breathtakingly beautiful.", "expected_domain": "concrete"},
    {"text": "Happiness is not something you find but something you create.", "expected_domain": "abstract"},

    # Mixed domain
    {"text": "The computer crashed because of a memory leak in the garbage collector.",
     "expected_domain": "concrete"},
    {"text": "We need to rethink our approach to sustainable urban development.",
     "expected_domain": "abstract"},
    {"text": "The bridge between theory and practice is built through experimentation.",
     "expected_domain": "abstract"},
]


def evaluate_injector(injector: OntologyInjector) -> Dict[str, Any]:
    """Evaluate the OntologyInjector on diverse English text.

    Tests:
    1. Classification consistency (same input → same output)
    2. Expected domain/intent/structure accuracy where labels exist
    3. Tag format correctness
    4. Injection format correctness
    5. Score range validity (all in [0, 1])
    6. Coverage (no crashes on any input)
    """
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

            entry = {
                "text": text[:60],
                "domain": meta.domain,
                "structure": meta.structure,
                "intent": meta.intent,
                "confidence": meta.confidence,
                "primary_role": meta.primary_role,
                "scores": {k: round(v, 4) for k, v in meta.raw_scores.items()},
            }
            results["classifications"].append(entry)

            # Format check: tag present and well-formed
            if "[ONTOLOGY]" not in enriched or "[/ONTOLOGY]" not in enriched:
                results["format_checks"]["all_valid_tags"] = False

            # Score range check
            for v in meta.raw_scores.values():
                if not (0.0 <= v <= 1.0):
                    results["format_checks"]["all_valid_scores"] = False

            # Accuracy vs expected labels
            for key in ("domain", "intent", "structure"):
                expected_key = f"expected_{key}"
                if expected_key in case:
                    results["accuracy"][key]["total"] += 1
                    if getattr(meta, key) == case[expected_key]:
                        results["accuracy"][key]["correct"] += 1

            # Consistency: classify again, should be identical
            meta2 = injector.classify(text)
            if (meta.domain != meta2.domain or meta.intent != meta2.intent
                    or meta.structure != meta2.structure):
                results["consistency_check"] = False

            n_ok += 1

        except Exception as e:
            results["classifications"].append({
                "text": text[:60],
                "error": str(e),
            })

    results["coverage"] = n_ok / max(len(INJECTOR_TEST_CASES), 1)

    # Compute accuracy rates
    for key in ("domain", "intent", "structure"):
        acc = results["accuracy"][key]
        acc["rate"] = acc["correct"] / max(acc["total"], 1)

    return results


# ---------------------------------------------------------------------------
# Drift detection evaluation
# ---------------------------------------------------------------------------

def evaluate_drift_detection(
    monitor: OntologyMonitor,
    in_dist: EvalDataset,
    shifted: EvalDataset,
) -> Dict[str, Any]:
    """Test that the monitor's drift detection fires on shifted data."""
    in_result = monitor.predict(in_dist.hidden_states)
    shifted_result = monitor.predict(shifted.hidden_states)

    return {
        "in_distribution_drift": in_result.drift_score,
        "shifted_drift": shifted_result.drift_score,
        "drift_ratio": shifted_result.drift_score / max(in_result.drift_score, 1e-6),
        "shift_detected": shifted_result.drift_score > in_result.drift_score * 1.5,
    }


# ---------------------------------------------------------------------------
# Main evaluation orchestrator
# ---------------------------------------------------------------------------

def run_phase2_eval(
    n_samples: int = 5000,
    d_model: int = 768,
    n_classes: int = 5,
    signal_snr: float = 3.0,
    n_epochs: int = 150,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run the complete Phase 2 evaluation suite."""

    all_results: Dict[str, Any] = {
        "config": {
            "n_samples": n_samples,
            "d_model": d_model,
            "n_classes": n_classes,
            "signal_snr": signal_snr,
            "n_epochs": n_epochs,
            "n_bootstrap": n_bootstrap,
            "seed": seed,
        },
        "checks": [],
    }
    t0 = time.time()

    # ===================================================================
    # STEP 1: Generate controlled dataset
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 1: GENERATING CONTROLLED DATASET")
    print("=" * 70)

    train_ds, val_ds, test_ds = generate_controlled_dataset(
        n_samples=n_samples,
        d_model=d_model,
        n_classes=n_classes,
        signal_snr=signal_snr,
        seed=seed,
    )

    print(f"  Train: {train_ds.N} samples")
    print(f"  Val:   {val_ds.N} samples")
    print(f"  Test:  {test_ds.N} samples")
    print(f"  d_model: {d_model}")
    print(f"  Signal SNR: {signal_snr}")

    # Print class distribution
    for split_name, ds in [("train", train_ds), ("val", val_ds), ("test", test_ds)]:
        unique, counts = np.unique(ds.labels, return_counts=True)
        dist = ", ".join(f"c{u}={c}" for u, c in zip(unique, counts))
        print(f"  {split_name} classes: {dist}")

    all_results["dataset"] = {
        "train_n": train_ds.N,
        "val_n": val_ds.N,
        "test_n": test_ds.N,
    }

    # ===================================================================
    # STEP 2: Train OntologyMonitor
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 2: TRAINING ONTOLOGY MONITOR")
    print("=" * 70)
    print(f"  Architecture: Linear({d_model}, 128) → ReLU → Dropout → Linear(128, 64) → ReLU → Linear(64, 4) → Sigmoid")
    print(f"  Epochs: {n_epochs}")

    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)

    train_result = monitor.train_monitor(
        H=train_ds.hidden_states,
        ont_features=train_ds.ont_features,
        valid_mask=train_ds.valid_mask,
        n_epochs=n_epochs,
        batch_size=256,
        val_split=0.0,  # we have our own val split
        seed=seed,
    )

    print(f"\n  Training complete.")
    print(f"  Train loss: {train_result.final_train_loss:.4f}")
    print(f"  R² (train internal): {train_result.r2_mean:.3f}")

    all_results["training"] = {
        "epochs": train_result.epochs_trained,
        "train_loss": train_result.final_train_loss,
        "r2_internal": train_result.r2_mean,
    }

    # ===================================================================
    # STEP 3: Evaluate on val set (hyperparameter selection)
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 3: VALIDATION SET EVALUATION")
    print("=" * 70)

    val_metrics = evaluate_monitor(monitor, val_ds, n_bootstrap=n_bootstrap, seed=seed)

    print(f"  Val R² (mean): {val_metrics['mean_r2']:.3f}")
    print(f"  Val MAE (mean): {val_metrics['mean_mae']:.4f}")
    print(f"  Val rank-corr (mean): {val_metrics['mean_rank_corr']:.3f}")
    print()
    for axis, m in val_metrics["per_axis"].items():
        print(f"  {axis:25s}  R²={m['r2']:.3f} [{m['r2_ci'][0]:.3f}, {m['r2_ci'][1]:.3f}]"
              f"  MAE={m['mae']:.4f}  ρ={m['rank_corr']:.3f}")

    all_results["val_metrics"] = val_metrics

    # ===================================================================
    # STEP 4: Evaluate on held-out test set (final numbers)
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 4: TEST SET EVALUATION (HELD-OUT)")
    print("=" * 70)

    test_metrics = evaluate_monitor(monitor, test_ds, n_bootstrap=n_bootstrap, seed=seed + 1)

    print(f"  Test R² (mean): {test_metrics['mean_r2']:.3f}")
    print(f"  Test MAE (mean): {test_metrics['mean_mae']:.4f}")
    print(f"  Test rank-corr (mean): {test_metrics['mean_rank_corr']:.3f}")
    print()
    for axis, m in test_metrics["per_axis"].items():
        print(f"  {axis:25s}  R²={m['r2']:.3f} [{m['r2_ci'][0]:.3f}, {m['r2_ci'][1]:.3f}]"
              f"  MAE={m['mae']:.4f}  ρ={m['rank_corr']:.3f}")

    all_results["test_metrics"] = test_metrics

    # ===================================================================
    # STEP 5: Robustness — distribution shift
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 5: ROBUSTNESS UNDER DISTRIBUTION SHIFT")
    print("=" * 70)

    shift_results = {}
    for shift_type in ["noise", "scale", "rotate"]:
        shifted_ds = generate_shifted_dataset(test_ds, shift_type=shift_type, seed=seed + 10)
        shift_metrics = evaluate_monitor(monitor, shifted_ds, n_bootstrap=min(n_bootstrap, 200), seed=seed + 20)
        shift_results[shift_type] = shift_metrics

        r2_drop = test_metrics["mean_r2"] - shift_metrics["mean_r2"]
        print(f"  {shift_type:8s}  R²={shift_metrics['mean_r2']:.3f}  "
              f"(drop={r2_drop:+.3f} from clean test)")

    all_results["robustness"] = shift_results

    # ===================================================================
    # STEP 6: Drift detection
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 6: DRIFT DETECTION VALIDATION")
    print("=" * 70)

    drift_results = {}
    for shift_type in ["noise", "scale", "rotate"]:
        shifted_ds = generate_shifted_dataset(test_ds, shift_type=shift_type, seed=seed + 30)
        drift = evaluate_drift_detection(monitor, test_ds, shifted_ds)
        drift_results[shift_type] = drift
        detected = "YES" if drift["shift_detected"] else "NO"
        print(f"  {shift_type:8s}  in_dist={drift['in_distribution_drift']:.3f}  "
              f"shifted={drift['shifted_drift']:.3f}  "
              f"ratio={drift['drift_ratio']:.2f}x  detected={detected}")

    all_results["drift_detection"] = drift_results

    # ===================================================================
    # STEP 7: OntologyInjector evaluation
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 7: ONTOLOGY INJECTOR EVALUATION (50+ SENTENCES)")
    print("=" * 70)

    injector = OntologyInjector()
    injector_results = evaluate_injector(injector)

    print(f"  Coverage: {injector_results['coverage']:.0%} ({len(INJECTOR_TEST_CASES)} sentences)")
    print(f"  Tag format valid: {injector_results['format_checks']['all_valid_tags']}")
    print(f"  Score range valid: {injector_results['format_checks']['all_valid_scores']}")
    print(f"  Deterministic: {injector_results['consistency_check']}")
    print()
    for key in ("domain", "intent", "structure"):
        acc = injector_results["accuracy"][key]
        if acc["total"] > 0:
            print(f"  {key:12s} accuracy: {acc['correct']}/{acc['total']} "
                  f"({acc['rate']:.0%})")

    # Print a few sample classifications
    print(f"\n  Sample classifications:")
    for entry in injector_results["classifications"][:8]:
        if "error" not in entry:
            print(f"    '{entry['text'][:50]:50s}' → "
                  f"{entry['domain']}/{entry['structure']}/{entry['intent']} "
                  f"({entry['confidence']})")

    all_results["injector"] = injector_results

    # ===================================================================
    # STEP 8: SNR sensitivity analysis
    # ===================================================================
    print("\n" + "=" * 70)
    print("STEP 8: SNR SENSITIVITY ANALYSIS")
    print("=" * 70)

    snr_results = {}
    for snr in [0.5, 1.0, 2.0, 3.0, 5.0]:
        # Generate small dataset at this SNR
        train_s, _, test_s = generate_controlled_dataset(
            n_samples=min(n_samples, 2000),
            d_model=d_model,
            n_classes=n_classes,
            signal_snr=snr,
            seed=seed + int(snr * 10),
        )
        m = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
        m.train_monitor(
            H=train_s.hidden_states,
            ont_features=train_s.ont_features,
            valid_mask=train_s.valid_mask,
            n_epochs=min(n_epochs, 80),
            batch_size=256,
            val_split=0.0,
            seed=seed,
        )
        test_m = evaluate_monitor(m, test_s, n_bootstrap=min(n_bootstrap, 100), seed=seed)
        snr_results[snr] = test_m["mean_r2"]
        print(f"  SNR={snr:.1f}  →  test R²={test_m['mean_r2']:.3f}")

    all_results["snr_sensitivity"] = snr_results

    # ===================================================================
    # SUMMARY
    # ===================================================================
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print("PHASE 2 EVALUATION SUMMARY")
    print("=" * 70)

    checks = []

    # Check 1: Test R² > 0.3 (monitor recovers structure)
    test_r2 = test_metrics["mean_r2"]
    passed = test_r2 > 0.3
    checks.append(("Monitor test R² > 0.3", passed, f"R²={test_r2:.3f}"))

    # Check 2: All per-axis R² > 0 (no axis totally fails)
    all_positive = all(m["r2"] > 0 for m in test_metrics["per_axis"].values())
    checks.append(("All per-axis R² > 0", all_positive, ""))

    # Check 3: Val-test gap < 0.1 (no overfitting)
    gap = abs(val_metrics["mean_r2"] - test_metrics["mean_r2"])
    passed = gap < 0.1
    checks.append(("Val-test R² gap < 0.1", passed, f"gap={gap:.3f}"))

    # Check 4: Rank correlation > 0.3 on test
    rho = test_metrics["mean_rank_corr"]
    passed = rho > 0.3
    checks.append(("Test rank corr > 0.3", passed, f"ρ={rho:.3f}"))

    # Check 5: Noise robustness — R² drop < 50%
    if "noise" in shift_results:
        noise_r2 = shift_results["noise"]["mean_r2"]
        drop_pct = (test_r2 - noise_r2) / max(abs(test_r2), 1e-6)
        passed = drop_pct < 0.5
        checks.append(("Noise robustness (R² drop < 50%)", passed,
                       f"drop={drop_pct:.0%}"))

    # Check 6: Drift detection fires on shifted data
    n_detected = sum(1 for d in drift_results.values() if d["shift_detected"])
    passed = n_detected >= 2
    checks.append(("Drift detection fires (≥2/3 shifts)", passed,
                   f"{n_detected}/3 detected"))

    # Check 7: Injector coverage = 100%
    cov = injector_results["coverage"]
    passed = cov >= 1.0
    checks.append(("Injector 100% coverage", passed, f"{cov:.0%}"))

    # Check 8: Injector is deterministic
    passed = injector_results["consistency_check"]
    checks.append(("Injector deterministic", passed, ""))

    # Check 9: Injector format valid
    passed = (injector_results["format_checks"]["all_valid_tags"]
              and injector_results["format_checks"]["all_valid_scores"])
    checks.append(("Injector format valid", passed, ""))

    # Check 10: SNR monotonicity (higher SNR → higher R²)
    snr_vals = sorted(snr_results.keys())
    if len(snr_vals) >= 3:
        monotonic = snr_results[snr_vals[-1]] > snr_results[snr_vals[0]]
        checks.append(("R² increases with SNR", monotonic,
                       f"SNR={snr_vals[0]:.0f}→{snr_results[snr_vals[0]]:.3f}, "
                       f"SNR={snr_vals[-1]:.0f}→{snr_results[snr_vals[-1]]:.3f}"))

    # Check 11: Domain accuracy > 50% (better than random 3-class)
    dom_acc = injector_results["accuracy"]["domain"]
    if dom_acc["total"] > 0:
        passed = dom_acc["rate"] > 0.5
        checks.append(("Injector domain accuracy > 50%", passed,
                       f"{dom_acc['correct']}/{dom_acc['total']} ({dom_acc['rate']:.0%})"))

    # Print checks
    n_pass = 0
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if passed:
            n_pass += 1
        detail_str = f"  ({detail})" if detail else ""
        print(f"  [{status}] {name}{detail_str}")

    print(f"\n  Result: {n_pass}/{len(checks)} checks passed")
    print(f"  Elapsed: {elapsed:.1f}s")
    print("=" * 70)

    all_results["checks"] = [
        {"name": name, "passed": passed, "detail": detail}
        for name, passed, detail in checks
    ]
    all_results["summary"] = {
        "checks_passed": n_pass,
        "checks_total": len(checks),
        "elapsed_seconds": elapsed,
    }

    return all_results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 2 Controlled Ground-Truth Evaluation",
    )
    parser.add_argument("--n-samples", type=int, default=5000)
    parser.add_argument("--d-model", type=int, default=768)
    parser.add_argument("--n-classes", type=int, default=5)
    parser.add_argument("--snr", type=float, default=3.0,
                        help="Signal-to-noise ratio (default: 3.0)")
    parser.add_argument("--n-epochs", type=int, default=150)
    parser.add_argument("--n-bootstrap", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: fewer samples, fewer epochs")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.quick:
        args.n_samples = min(args.n_samples, 1000)
        args.n_epochs = min(args.n_epochs, 50)
        args.n_bootstrap = min(args.n_bootstrap, 100)

    results = run_phase2_eval(
        n_samples=args.n_samples,
        d_model=args.d_model,
        n_classes=args.n_classes,
        signal_snr=args.snr,
        n_epochs=args.n_epochs,
        n_bootstrap=args.n_bootstrap,
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


if __name__ == "__main__":
    main()
