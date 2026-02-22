#!/usr/bin/env python3
"""
Causal Subspace Extraction & Validation — Main Orchestrator
=============================================================

Runs the complete 6-part pipeline:

    Part 1: Precision Data Collection
    Part 2: Structural Label Alignment
    Part 3: Feature Disentanglement (PCA + SAE + Clustering)
    Part 4: MDL Probing (Information-Theoretic Validation)
    Part 5: Causal Interchange Intervention (Activation Patching)
    Part 6: Layer Trajectory Mapping

Usage::

    # Full pipeline with GPT-2 (124M params)
    python scripts/causal_subspace/run_pipeline.py

    # Quick smoke test (fewer sequences, fewer pairs)
    python scripts/causal_subspace/run_pipeline.py --quick

    # Specific model
    python scripts/causal_subspace/run_pipeline.py --model gpt2

    # Skip expensive causal interventions
    python scripts/causal_subspace/run_pipeline.py --skip-interventions

    # Output results to JSON
    python scripts/causal_subspace/run_pipeline.py --output results.json

    # Specific layers only
    python scripts/causal_subspace/run_pipeline.py --layers 0 3 6 9 11

Deliverables:
    1. SAE feature sparsity distributions
    2. MDL probe compression ratios (bits per label)
    3. Causal interchange success rates
    4. Layer trajectory plots of the structural invariant
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

from scripts.causal_subspace.data_collection import (
    DataCollectionConfig,
    HiddenStateStore,
    collect_hidden_states,
)
from scripts.causal_subspace.structural_labels import (
    GRAMMATICAL_ROLES,
    StructuralAnnotations,
    annotate_structural_labels,
)
from scripts.causal_subspace.disentanglement import (
    DisentanglementConfig,
    DisentanglementResult,
    run_disentanglement,
)
from scripts.causal_subspace.mdl_probing import (
    MDLProbeConfig,
    MDLProbeResult,
    run_mdl_probe,
    select_top_k_components,
)
from scripts.causal_subspace.causal_intervention import (
    InterventionConfig,
    InterventionResult,
    build_pca_basis,
    build_subspace_basis,
    run_causal_intervention,
)
from scripts.causal_subspace.trajectory import (
    LayerTrajectory,
    compute_layer_trajectory,
    plot_trajectory_ascii,
)

logger = logging.getLogger("causal_subspace")


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_full_pipeline(
    model_name: str = "gpt2",
    max_sequences: int = 500,
    max_seq_len: int = 256,
    batch_size: int = 8,
    sae_epochs: int = 50,
    sae_expansion: int = 4,
    sae_sparsity: float = 1e-3,
    n_clusters: int = 32,
    mdl_portions: int = 10,
    n_intervention_pairs: int = 50,
    subspace_k: int = 16,
    layers: Optional[List[int]] = None,
    skip_interventions: bool = False,
    device: str = "cpu",
    seed: int = 42,
    activation_source: str = "block",
) -> Dict[str, Any]:
    """Run the complete causal subspace extraction and validation pipeline.

    Returns a dict containing all deliverables.
    """
    results: Dict[str, Any] = {
        "model_name": model_name,
        "activation_source": activation_source,
        "config": {
            "max_sequences": max_sequences,
            "max_seq_len": max_seq_len,
            "subspace_k": subspace_k,
            "sae_expansion": sae_expansion,
            "n_clusters": n_clusters,
            "activation_source": activation_source,
        },
    }

    t0 = time.time()

    # ===================================================================
    # PART 1: Data Collection
    # ===================================================================
    print("\n" + "=" * 70)
    print("PART 1: PRECISION DATA COLLECTION")
    print("=" * 70)

    source_desc = "attention sublayer" if activation_source == "attention" else "block (MLP residual)"
    print(f"  Activation source: {source_desc}")
    print(f"  Loading model and running forward passes ({max_sequences} sequences)...",
          flush=True)

    data_cfg = DataCollectionConfig(
        model_name=model_name,
        max_sequences=max_sequences,
        max_seq_len=max_seq_len,
        batch_size=batch_size,
        device=device,
        seed=seed,
        activation_source=activation_source,
    )
    store = collect_hidden_states(data_cfg)

    print(f"  Collected {len(store.tokens)} tokens across {store.n_layers} layers")
    print(f"  Hidden dimension: {store.d_model}")
    if store.attention_entropy:
        print(f"  Attention entropy: {store.n_heads} heads/layer "
              f"(collected for Part 7 gating analysis)")

    # Keep model + tokenizer for later parts
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)

    import torch
    device_t = torch.device(device)
    model.to(device_t)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ===================================================================
    # PART 2: Structural Label Alignment
    # ===================================================================
    print("\n" + "=" * 70)
    print("PART 2: STRUCTURAL LABEL ALIGNMENT")
    print("=" * 70)

    annotations = annotate_structural_labels(
        token_strings=store.tokens,
        sequence_ids=store.sequence_ids,
        hidden_states=store.states,
        tokenizer=tokenizer,
    )
    print(f"  {len(annotations.words)} words annotated across "
          f"{annotations.n_sentences} sentences")
    print(f"  Role distribution: {_label_distribution(annotations.labels_role, GRAMMATICAL_ROLES)}")

    # Filter layers if requested
    active_layers = layers if layers else list(range(store.n_layers))
    active_layers = [l for l in active_layers if l < store.n_layers]

    # ===================================================================
    # PART 3: Feature Disentanglement (per layer)
    # ===================================================================
    print("\n" + "=" * 70)
    print("PART 3: FEATURE DISENTANGLEMENT (PCA + SAE + CLUSTERING)")
    print("=" * 70)

    dis_cfg = DisentanglementConfig(
        sae_expansion_factor=sae_expansion,
        sae_sparsity_coeff=sae_sparsity,
        sae_epochs=sae_epochs,
        n_clusters=n_clusters,
        seed=seed,
        device=device,
    )

    disentanglement_results: Dict[int, DisentanglementResult] = {}
    sae_sparsity_distributions: Dict[int, Dict] = {}

    for layer_idx in active_layers:
        print(f"\n--- Layer {layer_idx} (PCA + SAE {sae_epochs}ep + K-means) ---",
              flush=True)
        H = annotations.hidden_states[layer_idx]
        dr = run_disentanglement(H, layer_idx, dis_cfg)
        disentanglement_results[layer_idx] = dr

        # Sparsity distribution
        if dr.sae_features is not None:
            l0_per_sample = (dr.sae_features > 0).sum(axis=1)
            sae_sparsity_distributions[layer_idx] = {
                "mean_l0": float(l0_per_sample.mean()),
                "std_l0": float(l0_per_sample.std()),
                "min_l0": int(l0_per_sample.min()),
                "max_l0": int(l0_per_sample.max()),
                "median_l0": float(np.median(l0_per_sample)),
                "sae_dim": dr.sae_features.shape[1],
                "pct_active": float(l0_per_sample.mean() / dr.sae_features.shape[1] * 100),
                "reconstruction_loss": dr.sae_reconstruction_loss,
            }
            print(f"  SAE: {sae_sparsity_distributions[layer_idx]['pct_active']:.1f}% features active, "
                  f"recon={dr.sae_reconstruction_loss:.4f}")

    results["sae_sparsity_distributions"] = sae_sparsity_distributions

    # ===================================================================
    # PART 4: MDL Probing
    # ===================================================================
    print("\n" + "=" * 70)
    print("PART 4: MDL PROBING (INFORMATION-THEORETIC VALIDATION)")
    print("=" * 70)

    mdl_cfg = MDLProbeConfig(
        n_portions=mdl_portions,
        seed=seed,
        device=device,
    )

    mdl_results: Dict[str, Dict[int, Dict]] = {}
    # Keep raw MDLProbeResult objects to avoid redundant recomputation in Part 6
    mdl_result_objects: Dict[str, Dict[int, MDLProbeResult]] = {}

    # Probe for grammatical role labels
    label_sets = {
        "grammatical_role": annotations.labels_role,
        "dep_depth": np.clip(annotations.labels_depth, 0, 5),  # bin depths
    }

    for label_name, label_arr in label_sets.items():
        print(f"\n--- MDL Probe: {label_name} ---")
        mdl_results[label_name] = {}
        mdl_result_objects[label_name] = {}

        for layer_idx in active_layers:
            H = annotations.hidden_states[layer_idx]
            r = run_mdl_probe(H, label_arr, layer_idx, label_name, mdl_cfg)
            mdl_result_objects[label_name][layer_idx] = r
            mdl_results[label_name][layer_idx] = {
                "compression_ratio": r.compression_ratio,
                "compression_vs_uniform": r.compression_vs_uniform,
                "online_code_length": r.online_code_length,
                "prior_code_length": r.prior_code_length,
                "uniform_code_length": r.uniform_code_length,
                "bits_per_label": r.online_code_length / max(r.n_samples, 1),
                "n_classes": r.n_classes,
            }
            print(f"  Layer {layer_idx}: compression={r.compression_ratio:.2f}x (vs prior), "
                  f"{r.compression_vs_uniform:.2f}x (vs uniform), "
                  f"bits/label={r.online_code_length / max(r.n_samples, 1):.3f}")

    results["mdl_compression_ratios"] = mdl_results

    # Select best layer for interventions
    role_compressions = {
        l: mdl_results["grammatical_role"][l]["compression_ratio"]
        for l in active_layers
        if l in mdl_results["grammatical_role"]
    }
    best_layer = max(role_compressions, key=role_compressions.get) if role_compressions else active_layers[len(active_layers) // 2]

    # Also find optimal k for best layer
    print(f"\n--- Finding optimal subspace dimensionality at layer {best_layer} ---")
    H_best = annotations.hidden_states[best_layer]
    candidate_ks = [4, 8, 16, 32, 64]
    optimal_k, k_results, best_pca_basis = select_top_k_components(
        H_best, annotations.labels_role, best_layer,
        "grammatical_role", candidate_ks, mdl_cfg,
    )
    print(f"  Optimal k = {optimal_k}")
    results["optimal_k"] = optimal_k

    # ===================================================================
    # PART 5: Causal Interchange Intervention
    # ===================================================================
    print("\n" + "=" * 70)
    print("PART 5: CAUSAL INTERCHANGE INTERVENTION (THE ACID TEST)")
    print("=" * 70)

    intervention_results: Dict[int, Dict] = {}

    if not skip_interventions:
        int_cfg = InterventionConfig(
            n_pairs=n_intervention_pairs,
            device=device,
            seed=seed,
            activation_source=activation_source,
        )

        # Run at best layer and a few surrounding layers
        intervention_layers = [best_layer]
        if best_layer > 0 and best_layer - 2 in active_layers:
            intervention_layers.insert(0, best_layer - 2)
        if best_layer + 2 < store.n_layers and best_layer + 2 in active_layers:
            intervention_layers.append(best_layer + 2)

        for layer_idx in intervention_layers:
            print(f"\n--- Causal intervention at Layer {layer_idx} ---")
            H = annotations.hidden_states[layer_idx]
            # Use global PCA basis (matching what MDL validated) instead of
            # class-conditional PCA which produces a misaligned subspace.
            if layer_idx == best_layer and best_pca_basis is not None:
                U_k = best_pca_basis  # exact basis MDL validated
            else:
                U_k = build_pca_basis(H, optimal_k)

            ir = run_causal_intervention(model, tokenizer, U_k, layer_idx, int_cfg)

            intervention_results[layer_idx] = {
                "n_pairs": ir.n_pairs_tested,
                "flip_rate": ir.flip_rate,
                "fluency_rate": ir.fluency_rate,
                "causal_success_rate": ir.causal_success_rate,
                "n_causal_successes": ir.n_causal_successes,
                # New causal rigor metrics
                "specificity_ratio": ir.specificity_ratio,
                "cross_specificity_ratio": ir.cross_specificity_ratio,
                "swap_vs_ablation_ratio": ir.swap_vs_ablation_ratio,
                "control_kl_mean": ir.control_kl_mean,
                "random_kl_mean": ir.random_kl_mean,
                "unrelated_kl_mean": ir.unrelated_kl_mean,
                "ablation_kl_mean": ir.ablation_kl_mean,
                "adaptive_kl_threshold": ir.adaptive_kl_threshold,
            }
            print(f"  Pairs: {ir.n_pairs_tested}, "
                  f"Flip: {ir.flip_rate * 100:.1f}%, "
                  f"Fluency: {ir.fluency_rate * 100:.1f}%, "
                  f"Causal success: {ir.causal_success_rate * 100:.1f}%")
            print(f"  Specificity: vs_random={ir.specificity_ratio:.2f}x, "
                  f"vs_unrelated={ir.cross_specificity_ratio:.2f}x, "
                  f"swap/ablation={ir.swap_vs_ablation_ratio:.2f}x")
    else:
        print("  (Skipped — use --skip-interventions=false to enable)")

    results["causal_intervention"] = intervention_results

    # ===================================================================
    # PART 6: Layer Trajectory Mapping
    # ===================================================================
    print("\n" + "=" * 70)
    print("PART 6: LAYER TRAJECTORY MAPPING")
    print("=" * 70)

    trajectory = compute_layer_trajectory(
        hidden_states={l: annotations.hidden_states[l] for l in active_layers},
        labels=annotations.labels_role,
        label_name="grammatical_role",
        model=model if not skip_interventions else None,
        tokenizer=tokenizer if not skip_interventions else None,
        subspace_k=optimal_k,
        mdl_cfg=mdl_cfg,
        intervention_cfg=InterventionConfig(
            n_pairs=max(10, n_intervention_pairs // 5),
            device=device,
            seed=seed,
            activation_source=activation_source,
        ) if not skip_interventions else None,
        run_interventions=not skip_interventions,
        precomputed_mdl=mdl_result_objects.get("grammatical_role"),
        activation_source=activation_source,
    )

    # Print trajectory
    print("\n" + plot_trajectory_ascii(trajectory))

    results["trajectory"] = {
        "layers": trajectory.layers,
        "mdl_compression": trajectory.mdl_compression,
        "mdl_bits_per_label": trajectory.mdl_bits_per_label,
        "causal_success_rate": trajectory.causal_success_rate,
        "pca_cumvar_at_k": trajectory.pca_cumvar_at_k,
        "crystallization_layer": trajectory.crystallization_layer,
        "consumption_layer": trajectory.consumption_layer,
        "peak_compression": trajectory.peak_compression,
        "peak_causal_success": trajectory.peak_causal_success,
    }

    # ===================================================================
    # Attention Entropy Summary (for Part 7 go/no-go)
    # ===================================================================
    if store.attention_entropy:
        attn_entropy_summary: Dict[int, Dict] = {}
        for layer_idx in active_layers:
            if layer_idx in store.attention_entropy:
                ae = store.attention_entropy[layer_idx]  # [N_tokens, n_heads]
                attn_entropy_summary[layer_idx] = {
                    "mean_entropy": float(ae.mean()),
                    "std_entropy": float(ae.std()),
                    "per_head_mean": [float(x) for x in ae.mean(axis=0)],
                    "per_head_std": [float(x) for x in ae.std(axis=0)],
                    "min_head_entropy": float(ae.mean(axis=0).min()),
                    "max_head_entropy": float(ae.mean(axis=0).max()),
                    "n_heads": int(ae.shape[1]),
                }
        results["attention_entropy"] = attn_entropy_summary

    # ===================================================================
    # FINAL REPORT
    # ===================================================================
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)

    print(f"\nModel: {model_name}")
    print(f"Tokens analyzed: {len(store.tokens)}")
    print(f"Words annotated: {len(annotations.words)}")
    print(f"Layers analyzed: {len(active_layers)}")

    print(f"\n1. SAE Feature Sparsity:")
    for layer_idx in active_layers:
        if layer_idx in sae_sparsity_distributions:
            sp = sae_sparsity_distributions[layer_idx]
            print(f"   Layer {layer_idx}: {sp['pct_active']:.1f}% active "
                  f"(L0={sp['mean_l0']:.1f}±{sp['std_l0']:.1f}), "
                  f"recon={sp['reconstruction_loss']:.4f}")

    print(f"\n2. MDL Compression Ratios (bits per label):")
    for label_name in mdl_results:
        print(f"   [{label_name}]")
        for layer_idx in active_layers:
            if layer_idx in mdl_results[label_name]:
                m = mdl_results[label_name][layer_idx]
                print(f"     Layer {layer_idx}: {m['compression_ratio']:.2f}x "
                      f"({m['bits_per_label']:.3f} bits/label)")

    print(f"\n3. Causal Interchange Success Rates:")
    if intervention_results:
        for layer_idx, ir in intervention_results.items():
            print(f"   Layer {layer_idx}: {ir['causal_success_rate'] * 100:.1f}% "
                  f"(flip={ir['flip_rate'] * 100:.1f}%, fluency={ir['fluency_rate'] * 100:.1f}%)")
            print(f"     Specificity: vs_random={ir.get('specificity_ratio', 0):.2f}x, "
                  f"vs_unrelated={ir.get('cross_specificity_ratio', 0):.2f}x, "
                  f"swap/ablation={ir.get('swap_vs_ablation_ratio', 0):.2f}x")
    else:
        print("   (Not run)")

    print(f"\n4. Layer Trajectory:")
    print(f"   Crystallization: Layer {trajectory.crystallization_layer} "
          f"(compression={trajectory.peak_compression:.2f}x)")
    print(f"   Consumption: Layer {trajectory.consumption_layer}")
    print(f"   Peak causal success: {trajectory.peak_causal_success * 100:.1f}%")

    if store.attention_entropy:
        print(f"\n5. Attention Entropy (per-head, per-layer):")
        for layer_idx in active_layers:
            if layer_idx in results.get("attention_entropy", {}):
                ae = results["attention_entropy"][layer_idx]
                print(f"   Layer {layer_idx}: mean={ae['mean_entropy']:.3f} nats "
                      f"(heads: {ae['min_head_entropy']:.3f}–{ae['max_head_entropy']:.3f})")

    print(f"\nTotal pipeline elapsed: {elapsed:.1f}s")
    print("=" * 70)

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_distribution(labels: np.ndarray, names: List[str]) -> str:
    """Pretty-print label distribution."""
    if labels is None:
        return "(none)"
    unique, counts = np.unique(labels, return_counts=True)
    parts = []
    for u, c in zip(unique, counts):
        name = names[u] if u < len(names) else f"class_{u}"
        parts.append(f"{name}={c}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Causal Subspace Extraction & Validation Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model", type=str, default="gpt2",
        help="HuggingFace model name (default: gpt2, 124M params)",
    )
    parser.add_argument(
        "--max-sequences", type=int, default=500,
        help="Number of corpus sequences to process",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=256,
        help="Max token length per sequence",
    )
    parser.add_argument(
        "--batch-size", type=int, default=8,
        help="Batch size for forward passes",
    )
    parser.add_argument(
        "--sae-epochs", type=int, default=50,
        help="SAE training epochs per layer",
    )
    parser.add_argument(
        "--sae-expansion", type=int, default=4,
        help="SAE hidden dim = d_model * expansion",
    )
    parser.add_argument(
        "--sae-sparsity", type=float, default=1e-3,
        help="SAE L1 sparsity coefficient",
    )
    parser.add_argument(
        "--n-clusters", type=int, default=32,
        help="K-means clusters for SAE features",
    )
    parser.add_argument(
        "--mdl-portions", type=int, default=10,
        help="Number of prequential portions for MDL probing",
    )
    parser.add_argument(
        "--n-pairs", type=int, default=50,
        help="Number of intervention pairs",
    )
    parser.add_argument(
        "--subspace-k", type=int, default=16,
        help="Initial subspace dimensionality",
    )
    parser.add_argument(
        "--layers", type=int, nargs="*", default=None,
        help="Specific layers to analyze (default: all)",
    )
    parser.add_argument(
        "--skip-interventions", action="store_true",
        help="Skip causal interventions (faster)",
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
        "--activation-source", type=str, default="block",
        choices=["block", "attention"],
        help="Activation source: 'block' (MLP residual stream) or "
             "'attention' (attention sublayer output, no MLP)",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick smoke test (reduced data, fewer epochs)",
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

    # Quick mode overrides
    if args.quick:
        args.max_sequences = min(args.max_sequences, 50)
        args.sae_epochs = min(args.sae_epochs, 10)
        args.n_pairs = min(args.n_pairs, 10)
        args.layers = args.layers or [0, 5, 11]

    results = run_full_pipeline(
        model_name=args.model,
        max_sequences=args.max_sequences,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
        sae_epochs=args.sae_epochs,
        sae_expansion=args.sae_expansion,
        sae_sparsity=args.sae_sparsity,
        n_clusters=args.n_clusters,
        mdl_portions=args.mdl_portions,
        n_intervention_pairs=args.n_pairs,
        subspace_k=args.subspace_k,
        layers=args.layers,
        skip_interventions=args.skip_interventions,
        device=args.device,
        seed=args.seed,
        activation_source=args.activation_source,
    )

    if args.output:
        output_path = Path(args.output)
        # Convert numpy types for JSON serialization
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

    return results


if __name__ == "__main__":
    main()
