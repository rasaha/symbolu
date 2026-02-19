#!/usr/bin/env python3
"""
Binding Benchmark Runner
=========================

Runs the full binding benchmark:
  1. Generate synthetic dataset (200 examples)
  2. Train + evaluate Model A (softmax baseline)
  3. Train + evaluate Model B (resonance interference)
  4. Statistical comparison
  5. Print structured report

Usage:
    python -m resonant_model.run_benchmark
    python -m resonant_model.run_benchmark --num-examples 200 --epochs 10
"""

import argparse
import sys
import time

import torch

from resonant_model.dataset import generate_dataset
from resonant_model.heads import (
    HeadConfig,
    SoftmaxBindingHead,
    ResonanceBindingHead,
    count_parameters,
)
from resonant_model.evaluator import train_and_evaluate
from resonant_model.statistics import BindingStatistics, format_report


def main():
    parser = argparse.ArgumentParser(description="Run binding benchmark")
    parser.add_argument("--num-examples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--embed-dim", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--lambda-interference", type=float, default=0.3)
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    device = torch.device(args.device)

    print("=" * 72)
    print("BINDING BENCHMARK")
    print("=" * 72)
    print()

    # Step 1: Generate dataset
    print(f"Generating {args.num_examples} binding examples (seed={args.seed})...")
    dataset = generate_dataset(
        num_examples=args.num_examples,
        seed=args.seed,
    )
    print(f"  Template distribution: {dataset.template_distribution}")
    print()

    # Config
    config = HeadConfig(
        embed_dim=args.embed_dim,
        num_heads=args.num_heads,
        num_layers=args.num_layers,
    )

    # Step 2: Model A — Softmax baseline
    print("Training Model A (softmax baseline)...")
    model_a = SoftmaxBindingHead(config)
    print(f"  Parameters: {count_parameters(model_a):,}")
    t0 = time.time()
    result_a = train_and_evaluate(
        model_a, dataset,
        model_name="softmax_baseline",
        epochs=args.epochs,
        lr=args.lr,
        device=device,
        config=config,
    )
    print(f"  Accuracy: {result_a.accuracy:.1%} ({time.time() - t0:.1f}s)")
    print()

    # Step 3: Model B — Resonance interference
    print("Training Model B (resonance interference)...")
    model_b = ResonanceBindingHead(
        config, lambda_interference=args.lambda_interference,
    )
    print(f"  Parameters: {count_parameters(model_b):,}")
    t0 = time.time()
    result_b = train_and_evaluate(
        model_b, dataset,
        model_name="resonance_interference",
        epochs=args.epochs,
        lr=args.lr,
        device=device,
        config=config,
    )
    print(f"  Accuracy: {result_b.accuracy:.1%} ({time.time() - t0:.1f}s)")
    print()

    # Step 4: Statistical comparison
    print("Running statistical comparison...")
    stats = BindingStatistics()
    report = stats.compare(result_a, result_b)
    print()

    # Step 5: Print report
    print(format_report(report))

    return report


if __name__ == "__main__":
    main()
