"""
Training Script
===============

Main training pipeline for consumer provider models.
Trains both embedding encoder and intent router.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from symbolu_training.training.schemas import TrainingDataset, QueryIntentPair, ParaphrasePair
from symbolu_training.training.trainers.embedding_trainer import (
    EmbeddingTrainer,
    EmbeddingTrainerConfig,
)
from symbolu_training.training.trainers.router_trainer import (
    RouterTrainer,
    RouterTrainerConfig,
)
from symbolu_training.training.scripts.validate import DataValidator


def load_intent_pairs(path: str) -> list:
    """Load intent pairs from JSONL file."""
    pairs = []
    with open(path, "r") as f:
        for line in f:
            data = json.loads(line)
            from symbolu_training.training.schemas import IntentLabel
            pairs.append(QueryIntentPair(
                query=data["query"],
                intent=IntentLabel(data["intent"]),
                confidence=data.get("confidence", 1.0),
                source=data.get("source", "synthetic"),
            ))
    return pairs


def load_paraphrase_pairs(path: str) -> list:
    """Load paraphrase pairs from JSONL file."""
    pairs = []
    with open(path, "r") as f:
        for line in f:
            data = json.loads(line)
            pairs.append(ParaphrasePair(
                query_a=data["query_a"],
                query_b=data["query_b"],
                similar=data["similar"],
                similarity_score=data.get("similarity_score"),
                source=data.get("source", "synthetic"),
            ))
    return pairs


def train_models(
    intent_pairs: list,
    paraphrase_pairs: list,
    output_dir: str = "symbolu/training/checkpoints",
    embedding_epochs: int = 10,
    router_epochs: int = 20,
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """
    Train both embedding and router models.

    Args:
        intent_pairs: List of QueryIntentPair for router training
        paraphrase_pairs: List of ParaphrasePair for embedding training
        output_dir: Directory to save checkpoints
        embedding_epochs: Number of embedding training epochs
        router_epochs: Number of router training epochs
        seed: Random seed
        verbose: Whether to print progress

    Returns:
        Dictionary with training results
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {
        "timestamp": timestamp,
        "embedding": {},
        "router": {},
    }

    # Train embedding model
    if verbose:
        print("\n" + "=" * 50)
        print("Training Embedding Model")
        print("=" * 50)
        print(f"Paraphrase pairs: {len(paraphrase_pairs)}")

    embedding_config = EmbeddingTrainerConfig(
        epochs=embedding_epochs,
        seed=seed,
    )
    embedding_trainer = EmbeddingTrainer(embedding_config)
    embedding_metrics = embedding_trainer.train(paraphrase_pairs, verbose=verbose)

    embedding_path = output_path / f"embedding_{timestamp}.json"
    embedding_trainer.save(str(embedding_path))

    results["embedding"] = {
        "path": str(embedding_path),
        "final_loss": embedding_metrics[-1].loss if embedding_metrics else 0,
        "final_accuracy": embedding_metrics[-1].accuracy if embedding_metrics else 0,
        "epochs": len(embedding_metrics),
    }

    if verbose:
        print(f"\nEmbedding model saved to: {embedding_path}")

    # Train router model
    if verbose:
        print("\n" + "=" * 50)
        print("Training Router Model")
        print("=" * 50)
        print(f"Intent pairs: {len(intent_pairs)}")

    router_config = RouterTrainerConfig(
        epochs=router_epochs,
        seed=seed,
    )
    router_trainer = RouterTrainer(router_config, embedder=embedding_trainer)
    router_metrics = router_trainer.train(intent_pairs, verbose=verbose)

    router_path = output_path / f"router_{timestamp}.json"
    router_trainer.save(str(router_path))

    results["router"] = {
        "path": str(router_path),
        "final_loss": router_metrics[-1].loss if router_metrics else 0,
        "final_accuracy": router_metrics[-1].accuracy if router_metrics else 0,
        "epochs": len(router_metrics),
        "per_class_accuracy": router_metrics[-1].per_class_accuracy if router_metrics else {},
    }

    if verbose:
        print(f"\nRouter model saved to: {router_path}")
        print("\n" + "=" * 50)
        print("Training Complete!")
        print("=" * 50)
        print(f"\nResults:")
        print(f"  Embedding accuracy: {results['embedding']['final_accuracy']:.2%}")
        print(f"  Router accuracy: {results['router']['final_accuracy']:.2%}")

    # Save results summary
    summary_path = output_path / f"training_summary_{timestamp}.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    return results


def main():
    parser = argparse.ArgumentParser(description="Train consumer provider models")
    parser.add_argument(
        "--intent-pairs",
        required=True,
        help="Path to intent pairs JSONL file",
    )
    parser.add_argument(
        "--paraphrase-pairs",
        required=True,
        help="Path to paraphrase pairs JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default="symbolu/training/checkpoints",
        help="Output directory for checkpoints",
    )
    parser.add_argument(
        "--embedding-epochs",
        type=int,
        default=10,
        help="Number of embedding training epochs",
    )
    parser.add_argument(
        "--router-epochs",
        type=int,
        default=20,
        help="Number of router training epochs",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output",
    )

    args = parser.parse_args()

    # Load data
    intent_pairs = load_intent_pairs(args.intent_pairs)
    paraphrase_pairs = load_paraphrase_pairs(args.paraphrase_pairs)

    # Validate
    validator = DataValidator(min_intent_pairs=10, min_paraphrase_pairs=10)
    intent_result = validator.validate_intent_pairs(intent_pairs)
    para_result = validator.validate_paraphrase_pairs(paraphrase_pairs)

    if not intent_result.is_valid:
        print("WARNING: Intent pairs validation failed!")
        for error in intent_result.errors:
            print(f"  - {error}")

    if not para_result.is_valid:
        print("WARNING: Paraphrase pairs validation failed!")
        for error in para_result.errors:
            print(f"  - {error}")

    # Train
    results = train_models(
        intent_pairs=intent_pairs,
        paraphrase_pairs=paraphrase_pairs,
        output_dir=args.output_dir,
        embedding_epochs=args.embedding_epochs,
        router_epochs=args.router_epochs,
        seed=args.seed,
        verbose=not args.quiet,
    )

    return results


if __name__ == "__main__":
    main()
