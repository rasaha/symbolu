#!/usr/bin/env python3
"""
Synthetic Subspace Validation — No Model Download Required
============================================================

Runs the full 6-part causal subspace pipeline on purely synthetic data.
This tests every algorithm (PCA, SAE, MDL, activation patching, trajectory)
without needing a HuggingFace model, GPU, or internet connection.

Usage::

    # Default: 6-layer toy model, 500 samples, 5 classes
    python scripts/causal_subspace/test_synthetic.py

    # Larger test
    python scripts/causal_subspace/test_synthetic.py --n-samples 2000 --n-layers 12 --d-model 128

    # Quick smoke test
    python scripts/causal_subspace/test_synthetic.py --quick

    # Save results to JSON
    python scripts/causal_subspace/test_synthetic.py --output results_synthetic.json

    # Test specific parts only
    python scripts/causal_subspace/test_synthetic.py --parts 3 4 5

    # Verbose logging
    python scripts/causal_subspace/test_synthetic.py -v
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    build_subspace_basis,
    _random_orthonormal_basis,
)
from scripts.causal_subspace.trajectory import (
    compute_layer_trajectory,
    plot_trajectory_ascii,
)

logger = logging.getLogger("causal_subspace.synthetic")


# ---------------------------------------------------------------------------
# Synthetic data generators
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

    Parameters
    ----------
    n_samples : int
        Number of token positions.
    d_model : int
        Hidden dimension.
    n_layers : int
        Number of simulated layers.
    n_classes : int
        Number of structural classes.
    signal_growth : float
        Signal strength grows as base + layer * signal_growth.
    noise_decay : float
        Noise strength decays as base - layer * noise_decay.
    seed : int

    Returns
    -------
    states : dict[int, np.ndarray]  (layer → [N, d])
    labels : np.ndarray [N]  (integer class labels)
    """
    rng = np.random.RandomState(seed)
    labels = rng.randint(0, n_classes, size=n_samples).astype(np.int32)

    # Class means: each class has a distinct direction in R^d
    class_means = rng.randn(n_classes, d_model).astype(np.float32)

    states: Dict[int, np.ndarray] = {}
    for layer in range(n_layers):
        signal = 0.3 + layer * signal_growth
        noise = 2.5 - layer * noise_decay
        noise = max(noise, 0.1)

        H = np.zeros((n_samples, d_model), dtype=np.float32)
        for i in range(n_samples):
            H[i] = class_means[labels[i]] * signal + rng.randn(d_model) * noise
        states[layer] = H

    return states, labels


class _ToyTransformerBlock(nn.Module):
    """A minimal transformer block that applies a linear projection."""

    def __init__(self, d_model: int):
        super().__init__()
        self.proj = nn.Linear(d_model, d_model, bias=False)
        nn.init.eye_(self.proj.weight)
        # Add small random perturbation
        with torch.no_grad():
            self.proj.weight.add_(torch.randn_like(self.proj.weight) * 0.01)

    def forward(self, x):
        return self.proj(x)


class _ToyTransformer(nn.Module):
    """A toy transformer that returns logits and has hookable blocks.

    Has the same interface expected by the activation patching code:
    - transformer.h is a ModuleList of blocks
    - forward returns an object with .logits attribute
    """

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
        logits = self.lm_head(h)
        return _LogitOutput(logits)


class _LogitOutput:
    def __init__(self, logits):
        self.logits = logits


class _ToyTokenizer:
    """Minimal tokenizer interface for synthetic tests."""

    def __init__(self, vocab_size: int = 1000):
        self.vocab_size = vocab_size
        self.pad_token = "<pad>"
        self.pad_token_id = 0
        self.eos_token = "<eos>"
        self.eos_token_id = 1

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        # Deterministic encoding based on characters
        return [ord(c) % self.vocab_size for c in text if c.strip()]

    def decode(self, ids) -> str:
        return "".join(chr(i + 65) for i in ids)


# ---------------------------------------------------------------------------
# Part runners
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

    # Find best layer and optimal k
    best_layer = max(mdl_results, key=lambda l: mdl_results[l]["compression_ratio"])
    H_best = states[best_layer]
    candidate_ks = [4, 8, 16, 32]
    optimal_k, _ = select_top_k_components(
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
    """Part 5: Causal intervention using a toy transformer.

    Builds a toy model, constructs the subspace basis from synthetic states,
    and runs activation patching on template-generated sentence pairs.
    """
    from scripts.causal_subspace.causal_intervention import (
        InterventionConfig,
        run_causal_intervention,
    )

    # Build toy model
    model = _ToyTransformer(d_model, n_layers)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    tokenizer = _ToyTokenizer()

    cfg = InterventionConfig(n_pairs=n_pairs, device="cpu", seed=seed)
    results = {}

    for layer_idx in layers:
        H = states[layer_idx]
        U_k = build_subspace_basis(H, labels, subspace_k)

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
# Main synthetic pipeline
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
    seed: int = 42,
) -> Dict[str, Any]:
    """Run the causal subspace pipeline on synthetic data.

    Returns a dict containing all results and diagnostics.
    """
    parts_to_run = set(parts) if parts else {3, 4, 5, 6}

    results: Dict[str, Any] = {
        "mode": "synthetic",
        "config": {
            "n_samples": n_samples,
            "d_model": d_model,
            "n_layers": n_layers,
            "n_classes": n_classes,
            "subspace_k": subspace_k,
        },
    }

    t0 = time.time()

    # --- Generate synthetic data ---
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
        "n_samples": n_samples,
        "n_layers": n_layers,
        "class_distribution": {int(u): int(c) for u, c in zip(unique, counts)},
    }

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
            n_portions=mdl_portions,
            probe_epochs=15,
            seed=seed,
            device="cpu",
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

        # Pick a subset of layers for interventions (expensive)
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
            n_portions=mdl_portions,
            probe_epochs=15,
            seed=seed,
            device="cpu",
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

    # --- Summary ---
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("SYNTHETIC VALIDATION SUMMARY")
    print("=" * 70)

    n_checks = 0
    n_pass = 0

    # Check: MDL compression > 1 on later layers (signal should be learnable)
    if "mdl_probing" in results:
        for layer_idx in active_layers:
            if layer_idx in results["mdl_probing"]:
                comp = results["mdl_probing"][layer_idx]["compression_ratio"]
                passed = comp > 1.0
                status = "PASS" if passed else "WARN"
                n_checks += 1
                if passed:
                    n_pass += 1
                print(f"  [{status}] Layer {layer_idx} MDL compression: {comp:.2f}x")

    # Check: Later layers compress better than early layers
    if "mdl_probing" in results and len(active_layers) >= 4:
        first_half = [
            results["mdl_probing"][l]["compression_ratio"]
            for l in active_layers[:len(active_layers)//2]
            if l in results["mdl_probing"]
        ]
        second_half = [
            results["mdl_probing"][l]["compression_ratio"]
            for l in active_layers[len(active_layers)//2:]
            if l in results["mdl_probing"]
        ]
        if first_half and second_half:
            passed = np.mean(second_half) > np.mean(first_half)
            status = "PASS" if passed else "WARN"
            n_checks += 1
            if passed:
                n_pass += 1
            print(f"  [{status}] Later layers compress better: "
                  f"first_half={np.mean(first_half):.2f}x, "
                  f"second_half={np.mean(second_half):.2f}x")

    # Check: SAE sparsity is reasonable
    if "disentanglement" in results:
        for layer_idx in active_layers:
            if layer_idx in results["disentanglement"]:
                pct = results["disentanglement"][layer_idx].get("pct_active", 100)
                passed = 0.5 < pct < 95
                status = "PASS" if passed else "WARN"
                n_checks += 1
                if passed:
                    n_pass += 1
                print(f"  [{status}] Layer {layer_idx} SAE sparsity: {pct:.1f}% active")

    # Check: Trajectory found crystallization
    if "trajectory" in results:
        crystal = results["trajectory"]["crystallization_layer"]
        passed = crystal >= 0
        status = "PASS" if passed else "WARN"
        n_checks += 1
        if passed:
            n_pass += 1
        print(f"  [{status}] Crystallization layer: {crystal}")

    print(f"\n  Checks: {n_pass}/{n_checks} passed")
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
        description="Test causal subspace pipeline on synthetic data (no model download)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default synthetic test
  python scripts/causal_subspace/test_synthetic.py

  # Quick smoke test
  python scripts/causal_subspace/test_synthetic.py --quick

  # Large-scale synthetic test
  python scripts/causal_subspace/test_synthetic.py --n-samples 2000 --d-model 128 --n-layers 12

  # Test only MDL + trajectory
  python scripts/causal_subspace/test_synthetic.py --parts 4 6

  # Save results to JSON
  python scripts/causal_subspace/test_synthetic.py --output results.json
        """,
    )
    parser.add_argument(
        "--n-samples", type=int, default=500,
        help="Number of synthetic token samples (default: 500)",
    )
    parser.add_argument(
        "--d-model", type=int, default=64,
        help="Hidden dimension (default: 64)",
    )
    parser.add_argument(
        "--n-layers", type=int, default=6,
        help="Number of simulated transformer layers (default: 6)",
    )
    parser.add_argument(
        "--n-classes", type=int, default=5,
        help="Number of structural classes (default: 5)",
    )
    parser.add_argument(
        "--sae-epochs", type=int, default=10,
        help="SAE training epochs (default: 10)",
    )
    parser.add_argument(
        "--sae-expansion", type=int, default=2,
        help="SAE expansion factor (default: 2)",
    )
    parser.add_argument(
        "--n-clusters", type=int, default=8,
        help="K-means clusters (default: 8)",
    )
    parser.add_argument(
        "--mdl-portions", type=int, default=8,
        help="MDL prequential portions (default: 8)",
    )
    parser.add_argument(
        "--n-pairs", type=int, default=20,
        help="Number of intervention pairs (default: 20)",
    )
    parser.add_argument(
        "--subspace-k", type=int, default=8,
        help="Subspace dimensionality (default: 8)",
    )
    parser.add_argument(
        "--layers", type=int, nargs="*", default=None,
        help="Specific layers to test (default: all)",
    )
    parser.add_argument(
        "--parts", type=int, nargs="*", default=None,
        help="Specific pipeline parts to run (3=disentangle, 4=MDL, 5=intervention, 6=trajectory)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick smoke test (reduced data)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging",
    )

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

    # Exit with error if checks failed
    summary = results.get("summary", {})
    if summary.get("checks_passed", 0) < summary.get("checks_total", 0):
        sys.exit(1)

    return results


if __name__ == "__main__":
    main()
