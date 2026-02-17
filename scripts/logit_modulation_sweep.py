#!/usr/bin/env python3
"""
Logit Modulation Alpha/Beta Sweep CLI
=======================================

Command-line tool for running hyperparameter sweeps and ablation
studies on the logit modulation decoding rule:

    modified_logits = base_logits + α·R_y − β·C_y

Usage examples:

    # Ablation study with synthetic data
    python scripts/logit_modulation_sweep.py --mode ablation

    # Alpha/beta sweep
    python scripts/logit_modulation_sweep.py --mode sweep \\
        --alpha 0.0 0.1 0.5 1.0 2.0 \\
        --beta  0.0 0.1 0.5 1.0 2.0

    # Sweep with custom sample count
    python scripts/logit_modulation_sweep.py --mode sweep \\
        --n_samples 500 --vocab_size 1000

    # Save results to file
    python scripts/logit_modulation_sweep.py --mode ablation \\
        --output results/sweep.json

Author: Sovereign-1 Training Initiative
Date: February 2026
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import numpy as np

try:
    import torch
except ImportError:
    print("ERROR: PyTorch is required. Install with: pip install torch")
    sys.exit(1)

from symbolu.inference.logit_modulation import (
    LogitModulationConfig,
    LogitModulator,
    ModulationMode,
)
from symbolu.inference.logit_modulation_benchmark import (
    LogitModulationBenchmark,
    SweepResult,
)
from symbolu.inference.retrieval_scorer import (
    RetrievalScorer,
    RetrievalScorerConfig,
    RetrievalStrategy,
)
from symbolu.inference.penalty_scorer import (
    PenaltyScorer,
    PenaltyScorerConfig,
)


def generate_synthetic_data(
    n_samples: int,
    vocab_size: int,
    embed_dim: int,
    seed: int = 42,
) -> dict:
    """Generate synthetic benchmark data.

    Creates realistic logits, retrieval scores, penalty scores, and
    target IDs for benchmarking the logit modulation pipeline.

    Args:
        n_samples: Number of evaluation samples.
        vocab_size: Vocabulary size.
        embed_dim: Embedding dimension.
        seed: Random seed for reproducibility.

    Returns:
        dict with keys: base_logits, retrieval_scores, penalty_scores,
        target_ids, vocab_embeddings, context_embeddings.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Base logits (typical model output range)
    base_logits = torch.randn(n_samples, vocab_size) * 3.0

    # Vocab and context embeddings
    vocab_embeddings = torch.randn(vocab_size, embed_dim)
    vocab_embeddings = torch.nn.functional.normalize(vocab_embeddings, dim=-1)

    context_embeddings = torch.randn(n_samples, embed_dim)
    context_embeddings = torch.nn.functional.normalize(context_embeddings, dim=-1)

    # Retrieval scores via cosine similarity
    retrieval_scorer = RetrievalScorer(
        RetrievalScorerConfig(
            strategy=RetrievalStrategy.COSINE,
            normalize_scores=True,
        )
    )
    retrieval_scores = retrieval_scorer.score(context_embeddings, vocab_embeddings)

    # Penalty scores (sparse: only some tokens get penalized)
    penalty_scores = torch.zeros(n_samples, vocab_size)
    # Add repetition-like penalties to ~10% of tokens
    penalty_mask = torch.rand(n_samples, vocab_size) < 0.1
    penalty_scores[penalty_mask] = torch.rand(penalty_mask.sum()) * 3.0

    # Target IDs: use argmax of logits with some noise to simulate
    # imperfect ground truth
    noisy_logits = base_logits + torch.randn_like(base_logits) * 0.5
    target_ids = torch.argmax(noisy_logits, dim=-1)

    return {
        "base_logits": base_logits,
        "retrieval_scores": retrieval_scores,
        "penalty_scores": penalty_scores,
        "target_ids": target_ids,
        "vocab_embeddings": vocab_embeddings,
        "context_embeddings": context_embeddings,
    }


def run_ablation(args, data: dict) -> None:
    """Run 4-condition ablation and print report."""
    benchmark = LogitModulationBenchmark(device="cpu")

    results = benchmark.run_ablation(
        base_logits=data["base_logits"],
        target_ids=data["target_ids"],
        retrieval_scores=data["retrieval_scores"],
        penalty_scores=data["penalty_scores"],
        alpha=args.default_alpha,
        beta=args.default_beta,
    )

    report = benchmark.generate_report(results)
    print(report)

    if args.output:
        benchmark.save_results(results, args.output)
        print(f"\nResults saved to {args.output}")


def run_sweep(args, data: dict) -> None:
    """Run alpha/beta sweep and print report."""
    benchmark = LogitModulationBenchmark(device="cpu")

    sweep = benchmark.run_alpha_beta_sweep(
        base_logits=data["base_logits"],
        target_ids=data["target_ids"],
        retrieval_scores=data["retrieval_scores"],
        penalty_scores=data["penalty_scores"],
        alpha_values=args.alpha,
        beta_values=args.beta,
    )

    report = benchmark.generate_sweep_report(sweep)
    print(report)

    if args.output:
        ablation = benchmark.run_ablation(
            base_logits=data["base_logits"],
            target_ids=data["target_ids"],
            retrieval_scores=data["retrieval_scores"],
            penalty_scores=data["penalty_scores"],
            alpha=args.default_alpha,
            beta=args.default_beta,
        )
        benchmark.save_results(ablation, args.output, sweep=sweep)
        print(f"\nResults saved to {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Logit Modulation Alpha/Beta Sweep",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        choices=["ablation", "sweep", "both"],
        default="both",
        help="Which evaluation to run (default: both)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        nargs="+",
        default=[0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
        help="Alpha values for sweep",
    )
    parser.add_argument(
        "--beta",
        type=float,
        nargs="+",
        default=[0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
        help="Beta values for sweep",
    )
    parser.add_argument(
        "--default_alpha",
        type=float,
        default=1.0,
        help="Default alpha for ablation (default: 1.0)",
    )
    parser.add_argument(
        "--default_beta",
        type=float,
        default=1.0,
        help="Default beta for ablation (default: 1.0)",
    )
    parser.add_argument(
        "--n_samples",
        type=int,
        default=200,
        help="Number of synthetic evaluation samples (default: 200)",
    )
    parser.add_argument(
        "--vocab_size",
        type=int,
        default=500,
        help="Vocabulary size for synthetic data (default: 500)",
    )
    parser.add_argument(
        "--embed_dim",
        type=int,
        default=64,
        help="Embedding dimension for synthetic data (default: 64)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save results JSON",
    )

    args = parser.parse_args()

    print(f"Generating synthetic data: {args.n_samples} samples, "
          f"vocab={args.vocab_size}, dim={args.embed_dim}, seed={args.seed}")
    data = generate_synthetic_data(
        n_samples=args.n_samples,
        vocab_size=args.vocab_size,
        embed_dim=args.embed_dim,
        seed=args.seed,
    )
    print()

    if args.mode in ("ablation", "both"):
        run_ablation(args, data)
        print()

    if args.mode in ("sweep", "both"):
        run_sweep(args, data)


if __name__ == "__main__":
    main()
