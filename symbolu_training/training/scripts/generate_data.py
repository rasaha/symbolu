"""
Training Data Generation Script
================================

Generates training data for consumer provider models.
Produces intent classification and paraphrase similarity datasets.
"""

import json
import os
from pathlib import Path
from datetime import datetime

from symbolu_training.training.schemas import TrainingDataset
from symbolu_training.training.generators.intent_generator import IntentPairGenerator
from symbolu_training.training.generators.paraphrase_generator import ParaphrasePairGenerator
from symbolu_training.training.scripts.validate import DataValidator, validate_training_data


def generate_training_data(
    output_dir: str = "symbolu/training/data/raw",
    intent_count: int = 2000,
    paraphrase_count: int = 1500,
    seed: int = 42,
    validate: bool = True,
) -> TrainingDataset:
    """
    Generate training data for consumer providers.

    Args:
        output_dir: Directory to save generated data
        intent_count: Number of intent pairs to generate
        paraphrase_count: Number of paraphrase pairs to generate
        seed: Random seed for reproducibility
        validate: Whether to validate the generated data

    Returns:
        TrainingDataset object
    """
    print(f"Generating training data (seed={seed})...")
    print(f"  Intent pairs: {intent_count}")
    print(f"  Paraphrase pairs: {paraphrase_count}")

    # Generate intent pairs
    print("\n[1/4] Generating intent pairs...")
    intent_generator = IntentPairGenerator(seed=seed)
    intent_pairs = intent_generator.generate(count=intent_count)
    print(f"  Generated {len(intent_pairs)} intent pairs")

    # Generate paraphrase pairs
    print("\n[2/4] Generating paraphrase pairs...")
    para_generator = ParaphrasePairGenerator(seed=seed)

    # Generate from templates
    template_pairs = para_generator.generate(count=paraphrase_count // 2)
    print(f"  Generated {len(template_pairs)} template-based pairs")

    # Generate from intent pairs
    derived_pairs = para_generator.generate_from_intent_pairs(
        intent_pairs=intent_pairs,
        pairs_per_query=3,
    )
    print(f"  Generated {len(derived_pairs)} intent-derived pairs")

    # Combine paraphrase pairs
    all_paraphrase_pairs = template_pairs + derived_pairs[:paraphrase_count // 2]
    print(f"  Total paraphrase pairs: {len(all_paraphrase_pairs)}")

    # Create dataset
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset = TrainingDataset(
        name="symbolu_consumer_training",
        version=version,
        intent_pairs=intent_pairs,
        paraphrase_pairs=all_paraphrase_pairs,
    )

    # Validate if requested
    if validate:
        print("\n[3/4] Validating generated data...")
        validator = DataValidator(
            min_intent_pairs=100,
            min_paraphrase_pairs=100,
        )
        result = validator.validate_dataset(dataset)
        print(result)

        if not result.is_valid:
            print("\nWARNING: Generated data has validation errors!")
            print("Continuing with export anyway...")

    # Save to files
    print("\n[4/4] Saving to files...")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save intent pairs as JSONL
    intent_file = output_path / f"intent_pairs_{version}.jsonl"
    with open(intent_file, "w") as f:
        for pair in intent_pairs:
            f.write(json.dumps({
                "query": pair.query,
                "intent": pair.intent.value,
                "confidence": pair.confidence,
                "source": pair.source,
            }) + "\n")
    print(f"  Saved intent pairs: {intent_file}")

    # Save paraphrase pairs as JSONL
    para_file = output_path / f"paraphrase_pairs_{version}.jsonl"
    with open(para_file, "w") as f:
        for pair in all_paraphrase_pairs:
            f.write(json.dumps({
                "query_a": pair.query_a,
                "query_b": pair.query_b,
                "similar": pair.similar,
                "similarity_score": pair.similarity_score,
                "source": pair.source,
            }) + "\n")
    print(f"  Saved paraphrase pairs: {para_file}")

    # Save full dataset as JSON
    dataset_file = output_path / f"dataset_{version}.json"
    with open(dataset_file, "w") as f:
        json.dump({
            "name": dataset.name,
            "version": dataset.version,
            "intent_pairs_count": len(dataset.intent_pairs),
            "paraphrase_pairs_count": len(dataset.paraphrase_pairs),
            "files": {
                "intent_pairs": str(intent_file.name),
                "paraphrase_pairs": str(para_file.name),
            },
        }, f, indent=2)
    print(f"  Saved dataset manifest: {dataset_file}")

    print(f"\n✓ Training data generation complete!")
    print(f"  Output directory: {output_path}")

    return dataset


def split_dataset(
    dataset: TrainingDataset,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> dict:
    """
    Split dataset into train/val/test sets.

    Args:
        dataset: TrainingDataset to split
        train_ratio: Ratio for training set
        val_ratio: Ratio for validation set
        test_ratio: Ratio for test set
        seed: Random seed

    Returns:
        Dictionary with train/val/test splits
    """
    import random
    rng = random.Random(seed)

    # Split intent pairs
    intent_pairs = list(dataset.intent_pairs)
    rng.shuffle(intent_pairs)

    n_intent = len(intent_pairs)
    train_end = int(n_intent * train_ratio)
    val_end = train_end + int(n_intent * val_ratio)

    intent_train = intent_pairs[:train_end]
    intent_val = intent_pairs[train_end:val_end]
    intent_test = intent_pairs[val_end:]

    # Split paraphrase pairs
    para_pairs = list(dataset.paraphrase_pairs)
    rng.shuffle(para_pairs)

    n_para = len(para_pairs)
    train_end = int(n_para * train_ratio)
    val_end = train_end + int(n_para * val_ratio)

    para_train = para_pairs[:train_end]
    para_val = para_pairs[train_end:val_end]
    para_test = para_pairs[val_end:]

    return {
        "train": {
            "intent_pairs": intent_train,
            "paraphrase_pairs": para_train,
        },
        "val": {
            "intent_pairs": intent_val,
            "paraphrase_pairs": para_val,
        },
        "test": {
            "intent_pairs": intent_test,
            "paraphrase_pairs": para_test,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate training data")
    parser.add_argument(
        "--output-dir",
        default="symbolu/training/data/raw",
        help="Output directory for generated data",
    )
    parser.add_argument(
        "--intent-count",
        type=int,
        default=2000,
        help="Number of intent pairs to generate",
    )
    parser.add_argument(
        "--paraphrase-count",
        type=int,
        default=1500,
        help="Number of paraphrase pairs to generate",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation",
    )

    args = parser.parse_args()

    generate_training_data(
        output_dir=args.output_dir,
        intent_count=args.intent_count,
        paraphrase_count=args.paraphrase_count,
        seed=args.seed,
        validate=not args.no_validate,
    )
