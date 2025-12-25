#!/usr/bin/env python3
"""
Train UnifiedOntologicalEngineV2 with Inter-Layer Bhava Relationships
======================================================================

Simple training script for the new V2 architecture.

Usage:
    python -m symbolu.ontological.train_v2
    python -m symbolu.ontological.train_v2 --save-data
"""

import json
import argparse
import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict, Any, List
from pathlib import Path

from symbolu.ontological.unified_engine import UnifiedOntologicalEngineV2
from symbolu.ontological.types import LAYER_NAMES, REASONING_LAYERS, CREATIVITY_LAYERS
from symbolu.ontological.bhava_relationships import (
    ASPECT_STRENGTH_MATRIX,
    BHAVA_SIGNIFICANCES,
    get_relationship_meaning,
)


def extract_drishti_data(engine: UnifiedOntologicalEngineV2, device: torch.device) -> Dict[str, Any]:
    """
    Extract current Drishti (aspect) pattern data from the trained engine.

    Returns learned aspect strengths and relationship statistics.
    """
    engine.eval()

    # Get learned aspect strengths from the bhava_engine
    bhava_module = engine.bhava_engine.bhava_relationships
    learned_aspects = bhava_module.aspect_strengths.detach().cpu().numpy().tolist()

    # Get the DrishtiAttention patterns
    drishti_attention = engine.bhava_engine.drishti_attention
    learned_drishti = drishti_attention.drishti_patterns.detach().cpu().numpy().tolist()

    # Compare with initial Vedic patterns
    initial_aspects = ASPECT_STRENGTH_MATRIX

    # Calculate deviation from Vedic patterns
    aspect_deviation = []
    for i in range(12):
        for j in range(12):
            initial = initial_aspects[i][j]
            learned = learned_aspects[i][j]
            deviation = learned - initial
            if abs(deviation) > 0.01:  # Only track significant changes
                aspect_deviation.append({
                    "from_layer": LAYER_NAMES[i],
                    "to_layer": LAYER_NAMES[j],
                    "initial": initial,
                    "learned": learned,
                    "deviation": deviation,
                })

    # Sort by absolute deviation
    aspect_deviation.sort(key=lambda x: abs(x["deviation"]), reverse=True)

    return {
        "learned_aspect_matrix": learned_aspects,
        "learned_drishti_patterns": learned_drishti,
        "initial_aspect_matrix": initial_aspects,
        "significant_deviations": aspect_deviation[:20],  # Top 20 changes
        "total_deviations": len(aspect_deviation),
    }


def extract_relationship_stats(
    output: Dict[str, torch.Tensor],
    top_k: int = 10
) -> Dict[str, Any]:
    """Extract relationship statistics from model output."""

    rel_matrix = output["relationship_matrix"].detach().cpu().numpy()
    coherence = output["coherence"].detach().cpu().numpy()

    # Average across batch
    avg_matrix = rel_matrix.mean(axis=0)
    avg_coherence = coherence.mean()

    # Find strongest relationships
    flat = avg_matrix.flatten()
    top_indices = np.argsort(np.abs(flat))[-top_k:][::-1]

    strongest = []
    for idx in top_indices:
        i, j = idx // 12, idx % 12
        meaning = get_relationship_meaning(i, j)
        strongest.append({
            "from": LAYER_NAMES[i],
            "to": LAYER_NAMES[j],
            "strength": float(flat[idx]),
            "bhava": meaning["relationship_bhava"]["name"],
            "interpretation": meaning["interpretation"],
        })

    # Pattern distribution
    pattern_counts = {
        "Conjunction": 0, "Opposition": 0, "Trine": 0,
        "Adjacent": 0, "Square": 0, "Sextile": 0, "Quincunx": 0
    }
    pattern_strengths = {k: [] for k in pattern_counts}

    for i in range(12):
        for j in range(12):
            diff = abs(i - j)
            circular_diff = min(diff, 12 - diff)
            strength = abs(avg_matrix[i][j])

            if circular_diff == 0:
                pattern = "Conjunction"
            elif circular_diff == 6:
                pattern = "Opposition"
            elif circular_diff in [4, 8]:
                pattern = "Trine"
            elif circular_diff in [1, 11]:
                pattern = "Adjacent"
            elif circular_diff in [3, 9]:
                pattern = "Square"
            elif circular_diff in [2, 10]:
                pattern = "Sextile"
            else:
                pattern = "Quincunx"

            pattern_counts[pattern] += 1
            pattern_strengths[pattern].append(strength)

    # Average strength per pattern
    pattern_avg_strength = {
        k: float(np.mean(v)) if v else 0.0
        for k, v in pattern_strengths.items()
    }

    return {
        "avg_coherence": float(avg_coherence),
        "relationship_matrix": avg_matrix.tolist(),
        "strongest_relationships": strongest,
        "pattern_distribution": pattern_counts,
        "pattern_avg_strength": pattern_avg_strength,
    }


def train_v2(
    epochs: int = 15,
    batch_size: int = 32,
    lr: float = 1e-4,
    save_data: bool = False,
    output_dir: str = "data"
):
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

    # Store initial Drishti patterns
    initial_drishti = extract_drishti_data(engine, device)

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
                coherence_weight=0.5,  # Increased to encourage coherent relationships
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

            # Extract relationship stats
            rel_stats = extract_relationship_stats(val_output)

        print(f"Epoch {epoch + 1:2d}: train_acc={train_acc:.2%}, val_acc={val_acc:.2%}, "
              f"coherence={val_coherence:.4f}, uncertainty={val_uncertainty:.3f}")

        # Store epoch data with Drishti patterns
        epoch_data = {
            "epoch": epoch + 1,
            "train_acc": train_acc,
            "val_acc": val_acc,
            "coherence": val_coherence,
            "uncertainty": val_uncertainty,
            "pattern_avg_strength": rel_stats["pattern_avg_strength"],
            "strongest_relationships": rel_stats["strongest_relationships"][:5],
        }
        history.append(epoch_data)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # Save best model
            torch.save(engine.state_dict(), "checkpoints/unified_v2_best.pt")

    print("-" * 60)
    print(f"\nBest validation accuracy: {best_val_acc:.2%}")

    # Extract final Drishti patterns
    final_drishti = extract_drishti_data(engine, device)

    # Final validation relationship stats
    engine.eval()
    with torch.no_grad():
        val_output = engine(val_emb)
        final_rel_stats = extract_relationship_stats(val_output, top_k=20)

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

    test_results = []
    for text in test_texts:
        result = engine.analyze(text)
        print(f"\n\"{text[:50]}...\"")
        print(f"  Layer: {result['dominant_layer']} ({result['confidence']:.1%})")
        print(f"  Coherence: {result['coherence']:.4f}")
        print(f"  Certainty: {result['certainty_level']}")
        if result['strongest_relationships']:
            top_rel = result['strongest_relationships'][0]
            print(f"  Top relationship: {top_rel['from']} → {top_rel['to']} ({top_rel['bhava']})")

        test_results.append({
            "text": text,
            "dominant_layer": result["dominant_layer"],
            "confidence": result["confidence"],
            "coherence": result["coherence"],
            "certainty_level": result["certainty_level"],
            "strongest_relationships": result["strongest_relationships"],
        })

    # Show Drishti pattern evolution
    print("\n" + "=" * 60)
    print("DRISHTI PATTERN EVOLUTION")
    print("=" * 60)

    print("\nPattern Average Strengths (Final):")
    for pattern, strength in final_rel_stats["pattern_avg_strength"].items():
        print(f"  {pattern:<12}: {strength:.4f}")

    print(f"\nSignificant Aspect Deviations from Vedic Patterns: {final_drishti['total_deviations']}")
    if final_drishti["significant_deviations"]:
        print("\nTop 5 Learned Deviations:")
        for dev in final_drishti["significant_deviations"][:5]:
            direction = "↑" if dev["deviation"] > 0 else "↓"
            print(f"  {dev['from_layer']} → {dev['to_layer']}: "
                  f"{dev['initial']:.2f} → {dev['learned']:.2f} ({direction}{abs(dev['deviation']):.3f})")

    # Save training data if requested
    if save_data:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        training_data = {
            "config": {
                "epochs": epochs,
                "batch_size": batch_size,
                "learning_rate": lr,
                "best_val_acc": best_val_acc,
            },
            "history": history,
            "initial_drishti": {
                "aspect_matrix": initial_drishti["initial_aspect_matrix"],
            },
            "final_drishti": {
                "learned_aspect_matrix": final_drishti["learned_aspect_matrix"],
                "learned_drishti_patterns": final_drishti["learned_drishti_patterns"],
                "significant_deviations": final_drishti["significant_deviations"],
                "total_deviations": final_drishti["total_deviations"],
            },
            "final_relationship_stats": {
                "avg_coherence": final_rel_stats["avg_coherence"],
                "pattern_distribution": final_rel_stats["pattern_distribution"],
                "pattern_avg_strength": final_rel_stats["pattern_avg_strength"],
                "strongest_relationships": final_rel_stats["strongest_relationships"],
                "relationship_matrix": final_rel_stats["relationship_matrix"],
            },
            "test_results": test_results,
            "bhava_significances": [
                {
                    "number": i,
                    "name": BHAVA_SIGNIFICANCES[i]["name"],
                    "meaning": BHAVA_SIGNIFICANCES[i]["meaning"],
                    "description": BHAVA_SIGNIFICANCES[i]["description"],
                }
                for i in range(1, 13)
            ],
            "layer_names": LAYER_NAMES,
        }

        data_file = output_path / "training_drishti_data.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(training_data, f, indent=2, ensure_ascii=False)

        print(f"\nTraining data saved to: {data_file}")

    return engine, history


if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(description="Train UnifiedOntologicalEngineV2")
    parser.add_argument("--epochs", type=int, default=15, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--save-data", action="store_true", help="Save training data to JSON")
    parser.add_argument("--output-dir", default="data", help="Output directory for data")

    args = parser.parse_args()

    os.makedirs("checkpoints", exist_ok=True)

    engine, history = train_v2(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        save_data=args.save_data,
        output_dir=args.output_dir,
    )

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print("\nModel saved to: checkpoints/unified_v2_best.pt")
    print("\nTo load and use:")
    print("  engine = UnifiedOntologicalEngineV2()")
    print("  engine.load_state_dict(torch.load('checkpoints/unified_v2_best.pt'))")
    print("  result = engine.analyze('Your text here')")

    if args.save_data:
        print(f"\nTraining data saved to: {args.output_dir}/training_drishti_data.json")
