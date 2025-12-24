#!/usr/bin/env python3
"""
Multi-Domain Training Script
=============================

Train the ontological engine on all 10 domains with multi-label support.

Usage:
    # Quick test
    python scripts/train_multi_domain.py --epochs 5 --samples 50

    # Full training
    python scripts/train_multi_domain.py --epochs 20 --samples 200

    # With benchmark
    python scripts/train_multi_domain.py --epochs 10 --benchmark
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Train ontological engine on all 10 domains"
    )
    parser.add_argument(
        "--epochs", type=int, default=10,
        help="Number of training epochs (default: 10)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Batch size (default: 32)"
    )
    parser.add_argument(
        "--lr", type=float, default=1e-4,
        help="Learning rate (default: 1e-4)"
    )
    parser.add_argument(
        "--samples", type=int, default=100,
        help="Samples per domain (default: 100)"
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
        "--output", type=str, default="model_multi_domain.pt",
        help="Output model path (default: model_multi_domain.pt)"
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
        "--patience", type=int, default=5,
        help="Early stopping patience (default: 5)"
    )
    parser.add_argument(
        "--label-smoothing", type=float, default=0.1,
        help="Label smoothing (default: 0.1)"
    )

    args = parser.parse_args()

    # Import here to allow --help without torch
    try:
        from symbolu.ontological.multi_domain_trainer import (
            MultiDomainTrainer,
            MultiDomainConfig,
        )
    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease install required packages:")
        print("  pip install torch sentence-transformers")
        sys.exit(1)

    # Create config
    config = MultiDomainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        device=args.device,
        model_path=args.model_path,
        samples_per_domain=args.samples,
        seed=args.seed,
        validation_split=args.val_split,
        early_stopping_patience=args.patience,
        label_smoothing=args.label_smoothing,
    )

    print("=" * 60)
    print("MULTI-DOMAIN TRAINING (10 LAYERS)")
    print("=" * 60)
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"Learning rate: {args.lr}")
    print(f"Samples per domain: {args.samples}")
    print(f"Total samples: {args.samples * 10}")
    print(f"Device: {args.device}")
    print(f"Seed: {args.seed}")
    print(f"Validation split: {args.val_split:.0%}")
    print(f"Early stopping patience: {args.patience}")
    print(f"Label smoothing: {args.label_smoothing}")
    print("=" * 60)

    # Create trainer
    trainer = MultiDomainTrainer(config=config)

    # Train
    result = trainer.train(epochs=args.epochs)

    # Save model
    trainer.save(args.output)
    print(f"\nModel saved to: {args.output}")

    # Print results
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Best train accuracy: {result['best_accuracy']:.2%}")
    print(f"Best val accuracy: {result['best_val_accuracy']:.2%}")

    # Benchmark
    if args.benchmark:
        print("\n")
        trainer.benchmark()


if __name__ == "__main__":
    main()
