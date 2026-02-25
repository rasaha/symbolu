#!/usr/bin/env python3
"""
run-phase2 — Unified CLI for Phase 2: Real LLM Hidden State Validation
=======================================================================

End-to-end pipeline that extracts hidden states from a real LLM, runs
the full JEPA-Observatory evaluation, and produces a comparison report
against the Phase 1 synthetic baseline.

This is the single entry point for GPU testing. It chains:
  1. extract_real_states.py — Extract hidden states with behavioral labels
  2. eval_real_data.py     — Bridge + governance evaluation

Usage::

    ┌─────────────────────────────────────────────────────────────┐
    │  Quick Test (CPU, GPT-2, built-in texts, ~2 min)           │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │  python scripts/causal_subspace/run_phase2.py               │
    │      --model gpt2 --quick                                   │
    │                                                             │
    ├─────────────────────────────────────────────────────────────┤
    │  Standard Run (GPU, GPT-2 medium, HF datasets, ~5 min)     │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │  python scripts/causal_subspace/run_phase2.py               │
    │      --model gpt2-medium --device cuda                      │
    │                                                             │
    ├─────────────────────────────────────────────────────────────┤
    │  Full Run (GPU, all extensions, ~10 min)                    │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │  python scripts/causal_subspace/run_phase2.py               │
    │      --model gpt2-medium --device cuda                      │
    │      --governance --compare-synthetic                        │
    │      --max-sequences 1000 --output results/phase2.json      │
    │                                                             │
    ├─────────────────────────────────────────────────────────────┤
    │  Large Model (GPU, Llama-2-7B, ~20 min)                    │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │  python scripts/causal_subspace/run_phase2.py               │
    │      --model meta-llama/Llama-2-7b-hf --device cuda         │
    │      --layer 16 --governance --compare-synthetic             │
    │      --batch-size 4 --max-sequences 500                     │
    │      --output results/phase2_llama2.json                    │
    │                                                             │
    ├─────────────────────────────────────────────────────────────┤
    │  MLP Bridge (nonlinear mapping test)                        │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │  python scripts/causal_subspace/run_phase2.py               │
    │      --model gpt2 --device cuda --bridge-type mlp           │
    │      --hidden-dim 128 --n-epochs 500 --governance           │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘

GPU Requirements:
  - GPT-2 (124M params):       ~500 MB VRAM, any GPU
  - GPT-2 Medium (345M):       ~1.5 GB VRAM
  - GPT-2 Large (774M):        ~3 GB VRAM
  - Llama-2-7B (7B):           ~14 GB VRAM (fp16)
  - Llama-2-13B (13B):         ~26 GB VRAM (fp16)

Dependencies:
  pip install transformers datasets torch
  # Optional for better ontology vectors:
  pip install spacy && python -m spacy download en_core_web_sm
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import torch

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.extract_real_states import (
    BEHAVIORAL_CATEGORIES,
    assemble_behavioral_corpus,
    extract_hidden_states,
)
from scripts.causal_subspace.eval_real_data import (
    evaluate_on_real_data,
    print_results,
)

logger = logging.getLogger("run_phase2")


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2: End-to-end real LLM hidden state validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick CPU test (~2 min)
  python scripts/causal_subspace/run_phase2.py --model gpt2 --quick

  # Standard GPU run (~5 min)
  python scripts/causal_subspace/run_phase2.py --model gpt2-medium --device cuda

  # Full evaluation (~10 min)
  python scripts/causal_subspace/run_phase2.py --model gpt2-medium --device cuda \\
      --governance --compare-synthetic --output results/phase2.json
        """,
    )

    # Model selection
    parser.add_argument(
        "--model", default="gpt2",
        help="HuggingFace model name (default: gpt2)",
    )
    parser.add_argument(
        "--layer", type=int, default=None,
        help="Target layer index (default: 2/3 depth)",
    )
    parser.add_argument(
        "--device", default=None,
        help="Device: cpu or cuda (default: auto-detect)",
    )

    # Data
    parser.add_argument(
        "--max-sequences", type=int, default=500,
        help="Max texts per behavioral category (default: 500)",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=256,
        help="Max tokens per text (default: 256)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=8,
        help="Batch size for extraction (default: 8)",
    )
    parser.add_argument(
        "--categories",
        help="Comma-separated categories (default: all 5)",
    )
    parser.add_argument(
        "--no-hf", action="store_true",
        help="Skip HuggingFace downloads; use built-in texts only",
    )

    # Bridge config
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

    # Evaluation modes
    parser.add_argument(
        "--governance", action="store_true",
        help="Run governance evaluation (coherence, mismatch, governor)",
    )
    parser.add_argument(
        "--compare-synthetic", action="store_true",
        help="Compare with synthetic baseline",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: built-in texts only, 50 seqs/cat, 100 epochs",
    )

    # Output
    parser.add_argument(
        "--output", "-o",
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--cache-dir", default=None,
        help="Directory to cache extracted states (reuse across runs)",
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

    # Auto-detect device
    if args.device is None:
        args.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Auto-detected device: %s", args.device)

    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA requested but not available. Falling back to CPU.")
        args.device = "cpu"

    if args.device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1e9
        logger.info("GPU: %s (%.1f GB)", gpu_name, gpu_mem)

    # Quick mode overrides
    if args.quick:
        args.no_hf = True
        args.max_sequences = 50
        args.n_epochs = 100
        logger.info("Quick mode: built-in texts, 50 seqs/cat, 100 epochs")

    # Parse categories
    categories = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(",")]

    t_start = time.time()

    # ── Step 1: Check for cached states ───────────────────────────────────
    cache_path = None
    if args.cache_dir:
        cache_dir = Path(args.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        model_slug = args.model.replace("/", "_")
        layer_str = f"L{args.layer}" if args.layer else "Lauto"
        cache_path = cache_dir / f"states_{model_slug}_{layer_str}_{args.max_sequences}.pt"

    extracted = None
    if cache_path and cache_path.exists():
        logger.info("Loading cached states from %s", cache_path)
        data = torch.load(str(cache_path), map_location="cpu", weights_only=False)
        extracted = {
            "hidden_states": data["hidden_states"].numpy(),
            "labels": data["labels"].numpy(),
            "sentence_ids": data["sentence_ids"].numpy(),
            "tokens": data["tokens"],
            "metadata": data["metadata"],
        }
        logger.info("Loaded %d tokens from cache", extracted["hidden_states"].shape[0])

    # ── Step 2: Extract hidden states ─────────────────────────────────────
    if extracted is None:
        logger.info("\n" + "=" * 60)
        logger.info("Step 1/2: Extracting hidden states from %s", args.model)
        logger.info("=" * 60)

        corpus = assemble_behavioral_corpus(
            categories=categories,
            max_per_category=args.max_sequences,
            use_hf=not args.no_hf,
        )

        if not corpus:
            logger.error("No texts assembled. Exiting.")
            sys.exit(1)

        extracted = extract_hidden_states(
            corpus=corpus,
            model_name=args.model,
            target_layer=args.layer,
            max_seq_len=args.max_seq_len,
            batch_size=args.batch_size,
            device=args.device,
        )

        # Cache if requested
        if cache_path:
            torch.save({
                "hidden_states": torch.from_numpy(extracted["hidden_states"]),
                "labels": torch.from_numpy(extracted["labels"]),
                "sentence_ids": torch.from_numpy(extracted["sentence_ids"]),
                "tokens": extracted["tokens"],
                "metadata": extracted["metadata"],
            }, str(cache_path))
            logger.info("Cached states to %s (%.1f MB)",
                        cache_path, cache_path.stat().st_size / 1e6)

    # ── Step 3: Run evaluation ────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("Step 2/2: Running Phase 2 evaluation")
    logger.info("=" * 60)

    results = evaluate_on_real_data(
        hidden_states=extracted["hidden_states"],
        labels=extracted["labels"],
        tokens=extracted["tokens"],
        sentence_ids=extracted["sentence_ids"],
        metadata=extracted["metadata"],
        bridge_type=args.bridge_type,
        hidden_dim=args.hidden_dim,
        n_epochs_bridge=args.n_epochs,
        state_dim=32,
        run_governance=args.governance,
        compare_synthetic=args.compare_synthetic,
        seed=args.seed,
        device=args.device,
    )

    # ── Print results ─────────────────────────────────────────────────────
    print_results(results)

    # ── Save results ──────────────────────────────────────────────────────
    if args.output:
        import json
        import numpy as np

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

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

    elapsed = time.time() - t_start
    logger.info("\nTotal elapsed: %.1fs", elapsed)

    # ── Final summary ─────────────────────────────────────────────────────
    bridge = results.get("bridge", {})
    r2_mean = bridge.get("r2_mean", 0)
    comp = results.get("synthetic_comparison", {})

    print("\n" + "=" * 60)
    print("  Phase 2 Summary")
    print("=" * 60)
    print(f"  Model:         {extracted['metadata'].get('model_name', '?')}")
    print(f"  Device:        {args.device}")
    print(f"  Tokens:        {extracted['hidden_states'].shape[0]:,}")
    print(f"  Bridge R²:     {r2_mean:.3f}")
    if comp:
        print(f"  Synthetic R²:  {comp.get('synthetic_r2_mean', 0):.3f}")
        delta = comp.get("improvement", 0)
        print(f"  Improvement:   {delta:+.3f} {'✓' if delta > 0 else '✗'}")
    print(f"  Time:          {elapsed:.1f}s")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
