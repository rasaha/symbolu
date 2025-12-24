#!/usr/bin/env python3
"""
Evidential Training Script
===========================

Train the ontological engine with Bayesian uncertainty quantification.

Usage:
    python scripts/train_evidential.py --epochs 10 --benchmark
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Train Evidential Ontological Engine with uncertainty"
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--kl-weight", type=float, default=0.1,
                       help="KL divergence weight for regularization")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="model_evidential.pt")
    parser.add_argument("--benchmark", action="store_true")

    args = parser.parse_args()

    try:
        from symbolu.ontological import (
            EvidentialOntologicalEngine,
            EvidentialTrainer,
            EvidentialConfig,
        )
    except ImportError as e:
        print(f"Error: {e}")
        print("Install: pip install torch sentence-transformers")
        sys.exit(1)

    print("=" * 60)
    print("EVIDENTIAL ONTOLOGICAL ENGINE")
    print("=" * 60)
    print(f"Epochs: {args.epochs}")
    print(f"KL weight: {args.kl_weight}")
    print(f"Seed: {args.seed}")
    print("=" * 60)

    config = EvidentialConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        kl_weight=args.kl_weight,
        seed=args.seed,
    )

    trainer = EvidentialTrainer(config=config)
    result = trainer.train(epochs=args.epochs)

    trainer.save(args.output)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Best validation accuracy: {result['best_val_acc']:.2%}")

    if args.benchmark:
        trainer.benchmark()


if __name__ == "__main__":
    main()
