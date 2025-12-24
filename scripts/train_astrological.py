#!/usr/bin/env python3
"""
Astrological Ontological Engine Training
=========================================

Train the ontological engine with semantically-grounded Bhava
using astrological correspondences.

Usage:
    python scripts/train_astrological.py --epochs 10 --benchmark
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Train Astrological Ontological Engine"
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="model_astrological.pt")
    parser.add_argument("--benchmark", action="store_true")

    args = parser.parse_args()

    try:
        import torch
        import torch.nn.functional as F
        import numpy as np
        from symbolu.ontological import (
            AstrologicalOntologicalEngine,
            PLANETARY_MAP,
            BHAVA_PAIRS,
        )
        from symbolu.ontological.multi_domain_dataset import MultiDomainDataset
        from symbolu.ontological.encoder import get_encoder
        from symbolu.ontological.types import LAYER_NAMES
    except ImportError as e:
        print(f"Error: {e}")
        print("Install: pip install torch sentence-transformers")
        sys.exit(1)

    print("=" * 60)
    print("ASTROLOGICAL ONTOLOGICAL ENGINE")
    print("=" * 60)
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"Learning rate: {args.lr}")
    print("=" * 60)

    # Set seeds
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    # Create engine
    engine = AstrologicalOntologicalEngine()
    print(engine.summary())

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    engine = engine.to(device)

    # Generate dataset
    print("Generating multi-domain dataset...")
    dataset = MultiDomainDataset.generate(
        samples_per_domain=100,
        seed=args.seed,
    )

    # Encode
    encoder = get_encoder("minilm")
    texts = dataset.get_texts()
    labels = dataset.get_labels()

    print("Encoding texts...")
    embeddings = torch.tensor(
        np.array([encoder.encode(t) for t in texts]),
        dtype=torch.float32
    )
    labels = torch.tensor(labels, dtype=torch.float32)

    # Split
    n = len(embeddings)
    n_val = int(n * 0.2)
    indices = torch.randperm(n)

    train_emb = embeddings[indices[n_val:]].to(device)
    train_labels = labels[indices[n_val:]].to(device)
    val_emb = embeddings[indices[:n_val]].to(device)
    val_labels = labels[indices[:n_val]].to(device)

    print(f"Train: {len(train_emb)}, Val: {len(val_emb)}")

    # Optimizer
    optimizer = torch.optim.AdamW(engine.parameters(), lr=args.lr)

    # Training loop
    print(f"\nTraining for {args.epochs} epochs...")
    best_val_acc = 0.0

    for epoch in range(args.epochs):
        engine.train()

        # Shuffle
        perm = torch.randperm(len(train_emb))
        train_emb = train_emb[perm]
        train_labels = train_labels[perm]

        total_loss = 0
        total_correct = 0

        for i in range(0, len(train_emb), args.batch_size):
            batch_emb = train_emb[i:i + args.batch_size]
            batch_labels = train_labels[i:i + args.batch_size]

            optimizer.zero_grad()

            output = engine(batch_emb)

            # Evidential loss
            alpha = output["alpha"]
            S = torch.sum(alpha, dim=1, keepdim=True)
            targets = batch_labels / (batch_labels.sum(dim=1, keepdim=True) + 1e-8)

            log_likelihood = torch.sum(
                targets * (torch.digamma(alpha) - torch.digamma(S)),
                dim=1
            )
            loss = -log_likelihood.mean()

            # Bhava regularization - encourage diverse activation
            bhava = output["bhava"]
            bhava_var = bhava.var(dim=1).mean()
            loss = loss - 0.01 * bhava_var  # Encourage variance

            loss.backward()
            optimizer.step()

            total_loss += loss.item()

            # Accuracy
            pred = torch.argmax(output["ontological"], dim=1)
            target = torch.argmax(batch_labels, dim=1)
            total_correct += (pred == target).sum().item()

        train_acc = total_correct / len(train_emb)

        # Validation
        engine.eval()
        with torch.no_grad():
            val_output = engine(val_emb)
            val_pred = torch.argmax(val_output["ontological"], dim=1)
            val_target = torch.argmax(val_labels, dim=1)
            val_acc = (val_pred == val_target).float().mean().item()
            val_uncertainty = val_output["uncertainty"].mean().item()

        print(f"Epoch {epoch + 1}: train_acc={train_acc:.2%}, "
              f"val_acc={val_acc:.2%}, uncertainty={val_uncertainty:.3f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc

    # Save model
    torch.save({
        "engine_state": engine.state_dict(),
        "best_val_acc": best_val_acc,
    }, args.output)
    print(f"\nSaved to {args.output}")

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Best validation accuracy: {best_val_acc:.2%}")

    if args.benchmark:
        print("\n" + "=" * 60)
        print("ASTROLOGICAL BENCHMARK")
        print("=" * 60)

        # Test examples
        test_texts = [
            ("What is consciousness?", "O1_THINKING"),
            ("Create a beautiful painting", "O2_FORMING"),
            ("Calculate 25 multiplied by 4", "O6_REASONING"),
            ("I feel so happy today", "O4_TAGGING"),
            ("Lead the team to victory", "O5_DIRECTING"),
            ("What is the meaning of life?", "O7_PURPOSING"),
            ("Observe your thoughts without judgment", "O8_META_OBSERVING"),
            ("Everything is connected", "O9_UNIFYING"),
            ("Let go and surrender", "O10_ABSOLVING"),
        ]

        print("\nSample Astrological Analysis:")
        print("-" * 60)

        correct = 0
        for text, expected in test_texts:
            result = engine.analyze(text)

            is_correct = result["dominant_layer"] == expected
            correct += int(is_correct)
            status = "OK" if is_correct else "MISS"

            print(f"\n[{status}] \"{text}\"")
            print(f"  Predicted: {result['dominant_layer']} ({result['confidence']:.0%})")
            print(f"  Expected:  {expected}")
            print(f"  Planet:    {result['planet']} ({result['sanskrit']}) - {result['energy']}")
            print(f"  Element:   {result['element']}")
            print(f"  Bhava:     {result['dominant_bhava']}")
            print(f"             {result['bhava_description']}")
            print(f"  Active:    {', '.join([s['name'] for s in result['active_sub_layers'][:3]])}")

        print(f"\n\nTest Accuracy: {correct}/{len(test_texts)} ({correct/len(test_texts):.0%})")


if __name__ == "__main__":
    main()
