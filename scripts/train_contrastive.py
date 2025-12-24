#!/usr/bin/env python3
"""
Contrastive Training Script
===========================

Train the ontological engine with contrastive loss for
reasoning vs creativity domain separation.

Usage:
    # Quick test with synthetic data
    python scripts/train_contrastive.py --epochs 5 --synthetic

    # Full training with HuggingFace datasets
    python scripts/train_contrastive.py --epochs 10 --huggingface

    # With local data files
    python scripts/train_contrastive.py --epochs 10 \
        --gsm8k data/gsm8k.jsonl \
        --stories data/rocstories.csv
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Train ontological engine with contrastive loss"
    )
    parser.add_argument(
        "--epochs", type=int, default=10,
        help="Number of training epochs (default: 10)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=16,
        help="Batch size (default: 16)"
    )
    parser.add_argument(
        "--lr", type=float, default=1e-4,
        help="Learning rate (default: 1e-4)"
    )
    parser.add_argument(
        "--synthetic", action="store_true",
        help="Use synthetic data for testing"
    )
    parser.add_argument(
        "--huggingface", action="store_true",
        help="Load datasets from HuggingFace"
    )
    parser.add_argument(
        "--gsm8k", type=str, default=None,
        help="Path to GSM8K JSONL file"
    )
    parser.add_argument(
        "--stories", type=str, default=None,
        help="Path to ROCStories CSV file"
    )
    parser.add_argument(
        "--samples", type=int, default=500,
        help="Number of samples per domain (default: 500)"
    )
    parser.add_argument(
        "--device", type=str, default="auto",
        help="Device: 'auto', 'cuda', 'mps', 'cpu' (default: auto)"
    )
    parser.add_argument(
        "--model-path", type=str, default=None,
        help="Path to local MiniLM model (for offline use)"
    )
    parser.add_argument(
        "--output", type=str, default="model_contrastive.pt",
        help="Output model path (default: model_contrastive.pt)"
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Run benchmark after training"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--val-split", type=float, default=0.2,
        help="Validation split ratio (default: 0.2)"
    )
    parser.add_argument(
        "--patience", type=int, default=3,
        help="Early stopping patience (default: 3)"
    )

    args = parser.parse_args()

    # Import here to allow --help without torch
    try:
        from symbolu.ontological.contrastive_trainer import (
            ContrastiveTrainer,
            ContrastiveConfig,
        )
    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease install required packages:")
        print("  pip install torch sentence-transformers")
        sys.exit(1)

    # Create config
    config = ContrastiveConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        device=args.device,
        model_path=args.model_path,
        reasoning_samples=args.samples,
        creativity_samples=args.samples,
        use_huggingface=args.huggingface,
        seed=args.seed,
        validation_split=args.val_split,
        early_stopping_patience=args.patience,
    )

    print("=" * 60)
    print("CONTRASTIVE TRAINING")
    print("=" * 60)
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"Learning rate: {args.lr}")
    print(f"Samples per domain: {args.samples}")
    print(f"Device: {args.device}")
    print(f"Seed: {args.seed}")
    print(f"Validation split: {args.val_split:.0%}")
    print(f"Early stopping patience: {args.patience}")
    print(f"Data source: {'synthetic' if args.synthetic else 'huggingface' if args.huggingface else 'local files'}")
    print("=" * 60)

    # Create trainer
    trainer = ContrastiveTrainer(config=config)

    # Train
    use_synthetic = args.synthetic or (not args.huggingface and not args.gsm8k)
    result = trainer.train(
        epochs=args.epochs,
        use_synthetic=use_synthetic,
        gsm8k_path=args.gsm8k,
        stories_path=args.stories,
    )

    # Save model
    trainer.save(args.output)
    print(f"\nModel saved to: {args.output}")

    # Print results
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Best train separation: {result['best_separation']:.2%}")
    if 'best_val_separation' in result:
        print(f"Best val separation: {result['best_val_separation']:.2%}")

    # Benchmark
    if args.benchmark:
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)
        trainer.benchmark()


if __name__ == "__main__":
    main()
