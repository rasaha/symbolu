#!/usr/bin/env python3
"""
Unified Training Script
========================

Train the unified ontological engine with ALL features:
- 10-class evidential classification
- Bayesian uncertainty quantification
- 90D Bhava relational dynamics
- Reasoning/Creativity task heads

Usage:
    python scripts/train_unified.py --epochs 15 --benchmark
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Train Unified Ontological Engine (all features)"
    )
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="model_unified.pt")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--kl-weight", type=float, default=0.1)
    parser.add_argument("--bhava-weight", type=float, default=0.3)
    parser.add_argument("--task-weight", type=float, default=0.2)

    args = parser.parse_args()

    try:
        from symbolu.ontological import (
            UnifiedOntologicalEngine,
            UnifiedTrainer,
            UnifiedConfig,
        )
    except ImportError as e:
        print(f"Error: {e}")
        print("Install: pip install torch sentence-transformers")
        sys.exit(1)

    print("=" * 60)
    print("UNIFIED ONTOLOGICAL ENGINE")
    print("The Best of All Worlds")
    print("=" * 60)
    print(f"Epochs: {args.epochs}")
    print(f"KL weight: {args.kl_weight}")
    print(f"Bhava weight: {args.bhava_weight}")
    print(f"Task weight: {args.task_weight}")
    print("=" * 60)

    config = UnifiedConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        seed=args.seed,
        kl_weight=args.kl_weight,
        bhava_weight=args.bhava_weight,
        task_weight=args.task_weight,
    )

    trainer = UnifiedTrainer(config=config)
    result = trainer.train(epochs=args.epochs)

    trainer.save(args.output)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Best validation accuracy: {result['best_val_acc']:.2%}")

    if args.benchmark:
        trainer.benchmark()

    # Demo analysis
    print("\n" + "=" * 60)
    print("DEMO ANALYSIS")
    print("=" * 60)

    demos = [
        "What is the meaning of existence?",
        "Calculate 25 multiplied by 4",
        "Paint a beautiful sunset over mountains",
        "Execute the deployment script now",
    ]

    for text in demos:
        r = trainer.engine.analyze(text)
        print(f"\n'{text[:40]}...'")
        print(f"  Layer: {r['dominant_layer']} ({r['confidence']:.0%})")
        print(f"  Uncertainty: {r['uncertainty']:.2f} ({r['certainty_level']})")
        print(f"  Reasoning: {r['reasoning_score']:.2f}, Creativity: {r['creativity_score']:.2f}")


if __name__ == "__main__":
    main()
