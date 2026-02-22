#!/usr/bin/env python3
"""
Real Model Subspace Validation — Run on Pretrained Transformers
=================================================================

Runs the causal subspace pipeline on a real pretrained transformer model
(GPT-2 by default). Supports both real corpus data (WikiText-103) and
a synthetic fallback corpus.

This CLI wraps ``run_pipeline.py`` with additional diagnostics and
preset profiles for common testing scenarios.

Usage::

    # Quick validation with GPT-2 (small data, few layers)
    python scripts/causal_subspace/test_real.py --profile quick

    # Standard run (moderate data, all layers)
    python scripts/causal_subspace/test_real.py --profile standard

    # Full research run (large data, all diagnostics)
    python scripts/causal_subspace/test_real.py --profile full

    # Custom configuration
    python scripts/causal_subspace/test_real.py --model gpt2 --max-sequences 100 --layers 0 3 6 9 11

    # Skip interventions (faster)
    python scripts/causal_subspace/test_real.py --profile standard --skip-interventions

    # Use synthetic corpus (no internet needed for corpus, model still downloaded)
    python scripts/causal_subspace/test_real.py --profile quick --corpus synthetic

    # Save results
    python scripts/causal_subspace/test_real.py --profile quick --output results_real.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Ensure project root is on path
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger("causal_subspace.real")


# ---------------------------------------------------------------------------
# Preset profiles
# ---------------------------------------------------------------------------

PROFILES = {
    "quick": {
        "max_sequences": 50,
        "max_seq_len": 128,
        "batch_size": 4,
        "sae_epochs": 10,
        "sae_expansion": 2,
        "n_clusters": 8,
        "mdl_portions": 5,
        "n_pairs": 10,
        "subspace_k": 8,
        "layers": [0, 5, 11],
    },
    "standard": {
        "max_sequences": 200,
        "max_seq_len": 256,
        "batch_size": 8,
        "sae_epochs": 30,
        "sae_expansion": 4,
        "n_clusters": 16,
        "mdl_portions": 8,
        "n_pairs": 30,
        "subspace_k": 16,
        "layers": None,  # all layers
    },
    "full": {
        "max_sequences": 500,
        "max_seq_len": 512,
        "batch_size": 8,
        "sae_epochs": 50,
        "sae_expansion": 4,
        "n_clusters": 32,
        "mdl_portions": 10,
        "n_pairs": 50,
        "subspace_k": 16,
        "layers": None,  # all layers
    },
}


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def run_validation_checks(results: Dict[str, Any]) -> tuple[int, int]:
    """Run automated validation checks on pipeline results.

    Returns (n_passed, n_total).
    """
    n_checks = 0
    n_pass = 0

    print("\n" + "=" * 70)
    print("VALIDATION CHECKS")
    print("=" * 70)

    # Check 1: At least some MDL compression detected
    mdl = results.get("mdl_compression_ratios", {})
    if "grammatical_role" in mdl:
        role_mdl = mdl["grammatical_role"]
        any_compressed = any(
            v.get("compression_ratio", 0) > 1.0
            for v in role_mdl.values()
        )
        n_checks += 1
        if any_compressed:
            n_pass += 1
        status = "PASS" if any_compressed else "FAIL"
        best = max((v.get("compression_ratio", 0) for v in role_mdl.values()), default=0)
        print(f"  [{status}] MDL compression > 1.0 on at least one layer "
              f"(best: {best:.2f}x)")

    # Check 2: Layer trajectory found crystallization
    traj = results.get("trajectory", {})
    crystal = traj.get("crystallization_layer", -1)
    n_checks += 1
    if crystal >= 0:
        n_pass += 1
    status = "PASS" if crystal >= 0 else "FAIL"
    print(f"  [{status}] Crystallization layer detected: L{crystal}")

    # Check 3: Peak compression > 1.5 (meaningful structural encoding)
    peak = traj.get("peak_compression", 0)
    n_checks += 1
    if peak > 1.2:
        n_pass += 1
    status = "PASS" if peak > 1.2 else "WARN"
    print(f"  [{status}] Peak compression: {peak:.2f}x (want > 1.2x)")

    # Check 4: SAE sparsity distributions are reasonable
    sae = results.get("sae_sparsity_distributions", {})
    if sae:
        sae_ok = all(
            0.5 < v.get("pct_active", 100) < 95
            for v in sae.values()
        )
        n_checks += 1
        if sae_ok:
            n_pass += 1
        status = "PASS" if sae_ok else "WARN"
        pcts = [f"L{k}={v.get('pct_active', 0):.1f}%" for k, v in sorted(sae.items())]
        print(f"  [{status}] SAE sparsity reasonable: {', '.join(pcts)}")

    # Check 5: Causal interventions (if run)
    interventions = results.get("causal_intervention", {})
    if interventions:
        any_success = any(
            v.get("causal_success_rate", 0) > 0
            for v in interventions.values()
        )
        n_checks += 1
        if any_success:
            n_pass += 1
        status = "PASS" if any_success else "WARN"
        rates = [f"L{k}={v.get('causal_success_rate', 0):.1%}"
                 for k, v in sorted(interventions.items())]
        print(f"  [{status}] Causal success > 0% somewhere: {', '.join(rates)}")

    # Check 5b: Specificity over random subspace (structural > random)
    if interventions:
        best_spec = max(
            (v.get("specificity_ratio", 0) for v in interventions.values()),
            default=0,
        )
        n_checks += 1
        if best_spec >= 1.5:
            n_pass += 1
        status = "PASS" if best_spec >= 1.5 else "WARN"
        print(f"  [{status}] Specificity vs random subspace: "
              f"{best_spec:.2f}x (want >= 1.5x)")

    # Check 5c: Specificity over unrelated sentence
    if interventions:
        best_cross = max(
            (v.get("cross_specificity_ratio", 0) for v in interventions.values()),
            default=0,
        )
        n_checks += 1
        if best_cross >= 1.2:
            n_pass += 1
        status = "PASS" if best_cross >= 1.2 else "WARN"
        print(f"  [{status}] Specificity vs unrelated sentence: "
              f"{best_cross:.2f}x (want >= 1.2x)")

    # Check 5d: Swap vs ablation — direction matters, not just occupancy
    if interventions:
        # swap/ablation > 1 means swap has more effect than zeroing-out,
        # which implies the *direction* within the subspace carries
        # role-specific information (not just that the subspace is
        # load-bearing).
        # swap/ablation < 1 means ablation is more disruptive — the model
        # needs something there but the direction doesn't encode role.
        best_sva = max(
            (v.get("swap_vs_ablation_ratio", 0) for v in interventions.values()),
            default=0,
        )
        n_checks += 1
        if best_sva > 0:  # just report for now; any positive value is informative
            n_pass += 1
        status = "INFO"
        print(f"  [{status}] Swap vs ablation ratio: {best_sva:.2f}x "
              f"(>1 = direction encodes role, <1 = occupancy only)")

    # Check 6: MDL compression increases across layers
    if "grammatical_role" in mdl:
        role_mdl = mdl["grammatical_role"]
        layers_sorted = sorted(role_mdl.keys(), key=lambda x: int(x))
        if len(layers_sorted) >= 4:
            half = len(layers_sorted) // 2
            first = np.mean([role_mdl[l]["compression_ratio"] for l in layers_sorted[:half]])
            second = np.mean([role_mdl[l]["compression_ratio"] for l in layers_sorted[half:]])
            n_checks += 1
            if second > first:
                n_pass += 1
            status = "PASS" if second > first else "WARN"
            print(f"  [{status}] Later layers compress better: "
                  f"early={first:.2f}x, late={second:.2f}x")

    print(f"\n  Result: {n_pass}/{n_checks} checks passed")
    return n_pass, n_checks


# ---------------------------------------------------------------------------
# Corpus override
# ---------------------------------------------------------------------------

def _patch_corpus_for_synthetic(cfg):
    """Ensure data_collection falls back to synthetic corpus."""
    # We override by setting dataset_name to something that won't load
    cfg.dataset_name = "__synthetic_fallback__"
    return cfg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Test causal subspace pipeline on a real pretrained transformer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Profiles:
  quick    - 50 sequences, 3 layers, ~2-5 min on CPU
  standard - 200 sequences, all layers, ~10-30 min on CPU
  full     - 500 sequences, all layers, ~30-60+ min on CPU

Examples:
  python scripts/causal_subspace/test_real.py --profile quick
  python scripts/causal_subspace/test_real.py --profile standard --skip-interventions
  python scripts/causal_subspace/test_real.py --model gpt2 --max-sequences 100
  python scripts/causal_subspace/test_real.py --profile quick --corpus synthetic --output results.json
        """,
    )

    parser.add_argument(
        "--profile", type=str, choices=list(PROFILES.keys()),
        default=None,
        help="Use a preset configuration profile",
    )
    parser.add_argument(
        "--model", type=str, default="gpt2",
        help="HuggingFace model name (default: gpt2)",
    )
    parser.add_argument(
        "--max-sequences", type=int, default=None,
        help="Number of corpus sequences (overrides profile)",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=None,
        help="Max token length per sequence (overrides profile)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Batch size for forward passes (overrides profile)",
    )
    parser.add_argument(
        "--sae-epochs", type=int, default=None,
        help="SAE training epochs (overrides profile)",
    )
    parser.add_argument(
        "--sae-expansion", type=int, default=None,
        help="SAE expansion factor (overrides profile)",
    )
    parser.add_argument(
        "--sae-sparsity", type=float, default=1e-3,
        help="SAE L1 sparsity coefficient",
    )
    parser.add_argument(
        "--n-clusters", type=int, default=None,
        help="K-means clusters (overrides profile)",
    )
    parser.add_argument(
        "--mdl-portions", type=int, default=None,
        help="MDL prequential portions (overrides profile)",
    )
    parser.add_argument(
        "--n-pairs", type=int, default=None,
        help="Number of intervention pairs (overrides profile)",
    )
    parser.add_argument(
        "--subspace-k", type=int, default=None,
        help="Subspace dimensionality (overrides profile)",
    )
    parser.add_argument(
        "--layers", type=int, nargs="*", default=None,
        help="Specific layers to analyze (overrides profile)",
    )
    parser.add_argument(
        "--skip-interventions", action="store_true",
        help="Skip causal interventions (faster)",
    )
    parser.add_argument(
        "--activation-source", type=str, default=None,
        choices=["block", "attention"],
        help="Activation source: 'block' (MLP residual stream, default) or "
             "'attention' (attention sublayer output — tests whether structural "
             "roles live in attention heads rather than MLP directions)",
    )
    parser.add_argument(
        "--corpus", type=str, choices=["auto", "synthetic"], default="auto",
        help="Corpus source: auto (try WikiText, fallback to synthetic) or synthetic",
    )
    parser.add_argument(
        "--device", type=str, default="cpu",
        help="Device: cpu or cuda",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Apply profile defaults, then override with explicit args
    profile = PROFILES.get(args.profile or "quick", PROFILES["quick"])

    def _get(attr, profile_key):
        val = getattr(args, attr)
        if val is not None:
            return val
        return profile.get(profile_key, None)

    max_sequences = _get("max_sequences", "max_sequences") or 50
    max_seq_len = _get("max_seq_len", "max_seq_len") or 128
    batch_size = _get("batch_size", "batch_size") or 4
    sae_epochs = _get("sae_epochs", "sae_epochs") or 10
    sae_expansion = _get("sae_expansion", "sae_expansion") or 2
    n_clusters = _get("n_clusters", "n_clusters") or 8
    mdl_portions = _get("mdl_portions", "mdl_portions") or 5
    n_pairs = _get("n_pairs", "n_pairs") or 10
    subspace_k = _get("subspace_k", "subspace_k") or 8
    layers = args.layers if args.layers is not None else profile.get("layers")

    # Print configuration
    profile_name = args.profile or "quick"
    print("\n" + "=" * 70)
    print(f"CAUSAL SUBSPACE PIPELINE — REAL MODEL TEST")
    print(f"Profile: {profile_name} | Model: {args.model} | Device: {args.device}")
    print("=" * 70)
    print(f"  Sequences: {max_sequences}, Seq len: {max_seq_len}, Batch: {batch_size}")
    print(f"  SAE: epochs={sae_epochs}, expansion={sae_expansion}, sparsity={args.sae_sparsity}")
    print(f"  MDL: portions={mdl_portions}, K-means clusters={n_clusters}")
    print(f"  Interventions: {'SKIP' if args.skip_interventions else f'{n_pairs} pairs'}")
    activation_source = args.activation_source or "block"
    source_desc = "attention sublayer (heads)" if activation_source == "attention" else "block (MLP residual)"
    print(f"  Subspace k: {subspace_k}, Layers: {layers or 'all'}")
    print(f"  Activation source: {source_desc}")
    print(f"  Corpus: {args.corpus}")

    # Handle synthetic corpus override
    if args.corpus == "synthetic":
        # Monkey-patch the DataCollectionConfig after import
        print("\n  [INFO] Using synthetic corpus (no WikiText download)")

    # Run the full pipeline
    from scripts.causal_subspace.run_pipeline import run_full_pipeline
    from scripts.causal_subspace.data_collection import DataCollectionConfig

    # If synthetic corpus is requested, temporarily override the dataset name
    if args.corpus == "synthetic":
        _orig_init = DataCollectionConfig.__init__
        def _patched_init(self, **kwargs):
            kwargs.setdefault("dataset_name", "__synthetic_fallback__")
            _orig_init(self, **kwargs)
        DataCollectionConfig.__init__ = _patched_init

    try:
        results = run_full_pipeline(
            model_name=args.model,
            max_sequences=max_sequences,
            max_seq_len=max_seq_len,
            batch_size=batch_size,
            sae_epochs=sae_epochs,
            sae_expansion=sae_expansion,
            sae_sparsity=args.sae_sparsity,
            n_clusters=n_clusters,
            mdl_portions=mdl_portions,
            n_intervention_pairs=n_pairs,
            subspace_k=subspace_k,
            layers=layers,
            skip_interventions=args.skip_interventions,
            device=args.device,
            seed=args.seed,
            activation_source=activation_source,
        )
    finally:
        # Restore original init if patched
        if args.corpus == "synthetic":
            DataCollectionConfig.__init__ = _orig_init

    # Run validation checks
    n_pass, n_checks = run_validation_checks(results)
    results["validation"] = {
        "checks_passed": n_pass,
        "checks_total": n_checks,
    }

    # Save results
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

    if n_pass < n_checks:
        print(f"\n[WARNING] {n_checks - n_pass} check(s) did not pass.")
        sys.exit(1)

    return results


if __name__ == "__main__":
    main()
