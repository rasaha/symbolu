#!/usr/bin/env python3
"""
Train UnifiedOntologicalEngineV2 with Inter-Layer Bhava Relationships
======================================================================

Simple training script for the new V2 architecture.

Usage:
    python -m symbolu.ontological.train_v2
"""

import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict, Any

from symbolu.ontological.unified_engine import UnifiedOntologicalEngineV2
from symbolu.ontological.types import LAYER_NAMES, REASONING_LAYERS, CREATIVITY_LAYERS


def train_v2(epochs: int = 15, batch_size: int = 32, lr: float = 1e-4):
    """Train the V2 engine with inter-layer Bhava relationships."""

    print("=" * 60)
    print("TRAINING UnifiedOntologicalEngineV2")
    print("=" * 60)

    # Initialize engine
    engine = UnifiedOntologicalEngineV2()
    print(engine.summary())

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    engine = engine.to(device)
    print(f"Device: {device}")

    # Generate training data
    print("\nGenerating multi-domain dataset...")
    from symbolu.ontological.multi_domain_dataset import MultiDomainDataset
    from symbolu.ontological.encoder import get_encoder

    dataset = MultiDomainDataset.generate(samples_per_domain=100, seed=42)

    # Encode texts
    encoder = get_encoder("minilm")
    texts = dataset.get_texts()
    labels = dataset.get_labels()

    print("Encoding texts...")
    embeddings = torch.tensor(
        np.array([encoder.encode(t) for t in texts]),
        dtype=torch.float32
    )
    labels = torch.tensor(labels, dtype=torch.float32)

    # Generate task targets
    reasoning_targets = torch.zeros(len(labels))
    creativity_targets = torch.zeros(len(labels))

    for i, sample in enumerate(dataset.samples):
        domain = sample.primary_domain
        if domain in ["O5_COGNITION", "O7_REASONING", "O9_WITNESSES"]:
            reasoning_targets[i] = 1.0
        if domain in ["O4_STRUCTURE", "O8_PURPOSE", "O10_UNIFYING"]:
            creativity_targets[i] = 1.0

    # Split data
    n = len(embeddings)
    n_val = int(n * 0.2)
    indices = torch.randperm(n)

    train_idx = indices[n_val:]
    val_idx = indices[:n_val]

    train_emb = embeddings[train_idx].to(device)
    train_labels = labels[train_idx].to(device)
    train_reasoning = reasoning_targets[train_idx].to(device)
    train_creativity = creativity_targets[train_idx].to(device)

    val_emb = embeddings[val_idx].to(device)
    val_labels = labels[val_idx].to(device)

    print(f"Train: {len(train_emb)}, Val: {len(val_emb)}")

    # Optimizer
    optimizer = torch.optim.AdamW(engine.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_acc = 0.0
    history = []

    print(f"\nTraining for {epochs} epochs...")
    print("-" * 60)

    for epoch in range(epochs):
        engine.train()

        # KL annealing
        kl_weight = min(1.0, epoch / (epochs / 2)) * 0.1

        # Shuffle
        perm = torch.randperm(len(train_emb))
        train_emb = train_emb[perm]
        train_labels = train_labels[perm]
        train_reasoning = train_reasoning[perm]
        train_creativity = train_creativity[perm]

        total_loss = 0
        total_correct = 0
        total_coherence = 0
        n_batches = 0

        for i in range(0, len(train_emb), batch_size):
            batch_emb = train_emb[i:i + batch_size]
            batch_labels = train_labels[i:i + batch_size]
            batch_reasoning = train_reasoning[i:i + batch_size]
            batch_creativity = train_creativity[i:i + batch_size]

            optimizer.zero_grad()

            output = engine(batch_emb)
            losses = engine.compute_loss(
                output,
                batch_labels,
                reasoning_targets=batch_reasoning,
                creativity_targets=batch_creativity,
                kl_weight=kl_weight,
                coherence_weight=0.2,
                task_weight=0.2,
            )

            losses["total"].backward()
            optimizer.step()

            total_loss += losses["total"].item()
            total_coherence += output["coherence"].mean().item()
            n_batches += 1

            # Accuracy
            pred = torch.argmax(output["ontological"], dim=1)
            target = torch.argmax(batch_labels, dim=1)
            total_correct += (pred == target).sum().item()

        scheduler.step()

        train_acc = total_correct / len(train_emb)
        avg_coherence = total_coherence / n_batches

        # Validation
        engine.eval()
        with torch.no_grad():
            val_output = engine(val_emb)
            val_pred = torch.argmax(val_output["ontological"], dim=1)
            val_target = torch.argmax(val_labels, dim=1)
            val_acc = (val_pred == val_target).float().mean().item()
            val_coherence = val_output["coherence"].mean().item()
            val_uncertainty = val_output["uncertainty"].mean().item()

        print(f"Epoch {epoch + 1:2d}: train_acc={train_acc:.2%}, val_acc={val_acc:.2%}, "
              f"coherence={val_coherence:.4f}, uncertainty={val_uncertainty:.3f}")

        history.append({
            "epoch": epoch + 1,
            "train_acc": train_acc,
            "val_acc": val_acc,
            "coherence": val_coherence,
            "uncertainty": val_uncertainty,
        })

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # Save best model
            torch.save(engine.state_dict(), "checkpoints/unified_v2_best.pt")

    print("-" * 60)
    print(f"\nBest validation accuracy: {best_val_acc:.2%}")

    # Final test
    print("\n" + "=" * 60)
    print("TESTING TRAINED MODEL")
    print("=" * 60)

    test_texts = [
        "What is the nature of consciousness?",
        "Implement a sorting algorithm",
        "The melody dances through shadows",
        "If A implies B and B implies C, then A implies C",
        "AI systems must be fair and transparent",
    ]

    for text in test_texts:
        result = engine.analyze(text)
        print(f"\n\"{text[:50]}...\"")
        print(f"  Layer: {result['dominant_layer']} ({result['confidence']:.1%})")
        print(f"  Coherence: {result['coherence']:.4f}")
        print(f"  Certainty: {result['certainty_level']}")
        if result['strongest_relationships']:
            top_rel = result['strongest_relationships'][0]
            print(f"  Top relationship: {top_rel['from']} → {top_rel['to']} ({top_rel['bhava']})")

    return engine, history


if __name__ == "__main__":
    import os
    os.makedirs("checkpoints", exist_ok=True)

    engine, history = train_v2(epochs=15)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print("\nModel saved to: checkpoints/unified_v2_best.pt")
    print("\nTo load and use:")
    print("  engine = UnifiedOntologicalEngineV2()")
    print("  engine.load_state_dict(torch.load('checkpoints/unified_v2_best.pt'))")
    print("  result = engine.analyze('Your text here')")
