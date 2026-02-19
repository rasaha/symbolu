#!/usr/bin/env python3
"""
Binding Benchmark Runner
=========================

Runs the full binding benchmark:
  1. Generate synthetic dataset (200 examples)
  2. Train + evaluate Model A (softmax baseline)
  3. Train + evaluate Model B (selected variant)
  4. Statistical comparison
  5. Print structured report
  6. Behavioral pass criteria evaluation
  7. Interference cross-term diagnostics (when model supports it)

Model B variants:
  resonance           — Original broadcast interference (key-side bias)
  quadratic           — Bilinear attention control (no interference)
  query_conditioned   — Query-conditioned interference interaction (O(L²))
  feature_interference — Interference injected as embedding feature

Usage:
    python -m resonant_model.run_benchmark
    python -m resonant_model.run_benchmark --model-b-type query_conditioned
    python -m resonant_model.run_benchmark --model-b-type feature_interference
    python -m resonant_model.run_benchmark --model-b-type quadratic
"""

import argparse
import time

import torch

from resonant_model.dataset import generate_dataset
from resonant_model.heads import (
    HeadConfig,
    SoftmaxBindingHead,
    ResonanceBindingHead,
    QuadraticBindingHead,
    QueryConditionedBindingHead,
    FeatureInterferenceBindingHead,
    count_parameters,
)
from resonant_model.evaluator import train_and_evaluate
from resonant_model.statistics import BindingStatistics, format_report
from resonant_model.pass_criteria import PassCriteria, format_pass_result
from resonant_model.diagnostics import (
    extract_log_entries,
    write_log,
    run_validation,
    format_validation_report,
)

MODEL_B_TYPES = {
    "resonance": ("Resonance Interference (broadcast)", ResonanceBindingHead),
    "quadratic": ("Quadratic Bilinear (control)", QuadraticBindingHead),
    "query_conditioned": ("Query-Conditioned Interference", QueryConditionedBindingHead),
    "feature_interference": ("Feature Interference (embedding)", FeatureInterferenceBindingHead),
}


def _build_model_b(model_type: str, config: HeadConfig, lambda_val: float):
    """Build the selected Model B variant."""
    if model_type == "resonance":
        return ResonanceBindingHead(config, lambda_interference=lambda_val)
    elif model_type == "quadratic":
        return QuadraticBindingHead(config, lambda_bilinear=lambda_val)
    elif model_type == "query_conditioned":
        return QueryConditionedBindingHead(config, lambda_interference=lambda_val)
    elif model_type == "feature_interference":
        return FeatureInterferenceBindingHead(config, lambda_interference=lambda_val)
    else:
        raise ValueError(f"Unknown model-b-type: {model_type}")


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
    parser.add_argument("--model-b-type", type=str, default="resonance",
                        choices=list(MODEL_B_TYPES.keys()),
                        help="Model B variant to test against baseline")
    parser.add_argument("--gate-entropy-weight", type=float, default=0.0,
                        help="Weight for gate entropy regularization (prevents degenerate gates)")
    parser.add_argument("--gate-variance-weight", type=float, default=0.0,
                        help="Weight for gate variance encouragement (prevents constant gates)")
    parser.add_argument("--gate-lr-multiplier", type=float, default=1.0,
                        help="Learning rate multiplier for gate parameters")
    parser.add_argument("--warmup-epochs", type=int, default=0,
                        help="Epochs to freeze amplitude projections (force gate dynamics)")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--log-path", type=str, default=None,
                        help="Path to write JSONL diagnostic log")
    args = parser.parse_args()

    device = torch.device(args.device)
    model_b_label, _ = MODEL_B_TYPES[args.model_b_type]

    print("=" * 72)
    print("BINDING BENCHMARK")
    print(f"  Model B: {model_b_label}")
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

    # Step 3: Model B — Selected variant
    print(f"Training Model B ({model_b_label})...")
    model_b = _build_model_b(args.model_b_type, config, args.lambda_interference)
    print(f"  Parameters: {count_parameters(model_b):,}")
    if args.gate_entropy_weight > 0 or args.gate_variance_weight > 0:
        print(f"  Gate entropy weight: {args.gate_entropy_weight}")
        print(f"  Gate variance weight: {args.gate_variance_weight}")
    if args.gate_lr_multiplier != 1.0:
        print(f"  Gate LR multiplier: {args.gate_lr_multiplier}x")
    if args.warmup_epochs > 0:
        print(f"  Warmup epochs: {args.warmup_epochs} (amplitude projections frozen)")
    t0 = time.time()
    result_b = train_and_evaluate(
        model_b, dataset,
        model_name=args.model_b_type,
        epochs=args.epochs,
        lr=args.lr,
        device=device,
        config=config,
        gate_entropy_weight=args.gate_entropy_weight,
        gate_variance_weight=args.gate_variance_weight,
        gate_lr_multiplier=args.gate_lr_multiplier,
        warmup_epochs=args.warmup_epochs,
    )
    print(f"  Accuracy: {result_b.accuracy:.1%} ({time.time() - t0:.1f}s)")
    print()

    # Step 4: Statistical comparison
    print("Running statistical comparison...")
    stats = BindingStatistics()
    report = stats.compare(result_a, result_b)
    print()

    # Step 5: Print comparison report
    print(format_report(report))
    print()

    # Step 6: Behavioral pass criteria evaluation
    print("Evaluating behavioral pass criteria...")
    pass_eval = PassCriteria()
    pass_result = pass_eval.evaluate(result_a, result_b)
    print()
    print(format_pass_result(pass_result))

    # Step 7: Interference diagnostics (only for models with get_last_internals)
    validation = None
    if hasattr(model_b, "get_last_internals"):
        print()
        print("Extracting interference cross-term diagnostics...")
        log_entries = extract_log_entries(
            model_b, dataset, result_b, config, device,
        )
        if args.log_path:
            write_log(log_entries, args.log_path)
            print(f"  JSONL log written to: {args.log_path}")

        validation = run_validation(log_entries, result_a, result_b)
        print()
        print(format_validation_report(validation))
    else:
        print()
        print(f"  (Skipping interference diagnostics — {args.model_b_type} "
              f"has no interference mechanism to diagnose)")

    return report, pass_result, validation


if __name__ == "__main__":
    main()
