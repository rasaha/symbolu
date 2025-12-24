#!/usr/bin/env python3
"""
Ontological Engine Demo
========================

Demonstrates the learnable 100D ontological engine:
- 10 Ontological dimensions (O1-O10)
- 90 Bhava sub-layers (relational dynamics)
- Multi-task heads for reasoning and creativity
- Training on synthetic data

Run with:
    python -m symbolu.ontological.demo
"""

from symbolu.ontological.engine import OntologicalEngine, create_engine
from symbolu.ontological.types import OntologicalConfig, LAYER_NAMES
from symbolu.ontological.bhava import (
    BhavaComputer90,
    FullOntologicalVector100,
    summarize_bhava_structure,
    BHAVA_SUBLAYER_NAMES,
)
from symbolu.ontological.heads import MultiTaskHead
from symbolu.ontological.trainer import (
    OntologicalTrainer,
    TrainerConfig,
    generate_reasoning_examples,
    generate_creativity_examples,
    generate_mixed_examples,
)


def demo_architecture():
    """Show the 100D architecture."""
    print("\n" + "=" * 70)
    print("LEARNABLE 100D ONTOLOGICAL ENGINE")
    print("=" * 70)

    print("\n📊 ARCHITECTURE OVERVIEW:")
    print("-" * 40)
    print("Total Dimensions: 100")
    print("  ├── 10 Ontological Layers (what)")
    print("  └── 90 Bhava Sub-Layers (how they relate)")
    print()

    print("🔟 ONTOLOGICAL DIMENSIONS:")
    for i, name in enumerate(LAYER_NAMES):
        print(f"  O{i+1}: {name.replace('O' + str(i+1) + '_', '')}")
    print()

    print("🔄 BHAVA SUB-LAYER TYPES (10 per pair):")
    for i, sublayer in enumerate(BHAVA_SUBLAYER_NAMES):
        print(f"  B{i+1}: {sublayer}")
    print()

    print("📐 BHAVA STRUCTURE:")
    print("  9 Ontological Pairs × 10 Sub-Layers = 90 Bhavas")
    print("  Example: O1↔O2 has 10 Bhavas (FOUNDATION, COMMUNICATION, ...)")


def demo_engine():
    """Demonstrate the ontological engine."""
    print("\n" + "=" * 70)
    print("ENGINE DEMO")
    print("=" * 70)

    # Create engine
    engine = create_engine(
        hidden_dims=(512, 256),
        use_skip_connections=True,
        dropout=0.1,
    )

    print("\n" + engine.summary())

    # Analyze some texts
    texts = [
        "If A implies B and B implies C, then A implies C",
        "The painting evokes dreamlike wonder and beauty",
        "Execute the deployment script immediately",
        "I feel deeply connected to this moment",
    ]

    print("\n📝 SAMPLE ANALYSES:")
    print("-" * 40)

    bhava = BhavaComputer90(mode="multiplicative")
    task_head = MultiTaskHead()

    for text in texts:
        print(f"\nText: \"{text[:50]}...\"" if len(text) > 50 else f"\nText: \"{text}\"")

        # Get ontological vector
        onto_vec = engine.analyze(text)
        print(f"  Dominant: {onto_vec.dominant_layer()}")

        # Get full 100D vector
        full_vec = bhava.get_full_vector(list(onto_vec.values))
        print(f"  Top Bhava: {full_vec.dominant_bhava()}")

        # Get task scores
        task_scores = task_head.forward(list(onto_vec.values))
        print(f"  Reasoning: {task_scores['reasoning_score']:.3f}")
        print(f"  Creativity: {task_scores['creativity_score']:.3f}")


def demo_bhava_structure():
    """Show the full Bhava structure."""
    print("\n" + summarize_bhava_structure())


def demo_training():
    """Demonstrate training on synthetic data."""
    print("\n" + "=" * 70)
    print("TRAINING DEMO")
    print("=" * 70)

    # Generate synthetic data
    print("\n📊 Generating synthetic training data...")
    train_data = generate_mixed_examples(200)
    eval_data = generate_mixed_examples(50)

    print(f"  Training examples: {len(train_data)}")
    print(f"  Evaluation examples: {len(eval_data)}")

    # Create trainer
    config = TrainerConfig(
        epochs=3,
        batch_size=16,
        learning_rate=1e-4,
        log_every_n_steps=5,
        use_bhava=True,
    )

    trainer = OntologicalTrainer(trainer_config=config)

    print("\n🏋️ Training...")
    print("-" * 40)

    # Train (short demo)
    state = trainer.train(train_data, eval_data)

    print(f"\n✅ Training complete!")
    print(f"  Final step: {state.step}")
    print(f"  Best loss: {state.best_loss:.4f}")


def demo_prediction():
    """Show prediction with full breakdown."""
    print("\n" + "=" * 70)
    print("PREDICTION DEMO")
    print("=" * 70)

    trainer = OntologicalTrainer()

    # Test different types of text
    test_texts = [
        ("Reasoning", "The logical conclusion follows from the premises"),
        ("Creative", "Stars dance like whispered dreams across velvet sky"),
        ("Action", "Run the tests and deploy to production"),
        ("Reflective", "What is the meaning of existence?"),
    ]

    for category, text in test_texts:
        print(f"\n📝 {category}: \"{text}\"")
        print("-" * 50)

        result = trainer.predict(text)

        # Ontological breakdown
        print("\nOntological Vector (10D):")
        onto = result["ontological"]
        sorted_onto = sorted(onto.items(), key=lambda x: x[1], reverse=True)[:3]
        for name, val in sorted_onto:
            bar = "█" * int((val + 1) * 10)  # Scale from [-1,1] to [0,20]
            print(f"  {name:20s} {val:+.3f} {bar}")

        # Bhava breakdown (top 3)
        print("\nTop Bhava Relationships (from 90D):")
        bhava = result["bhava"]
        sorted_bhava = sorted(bhava.items(), key=lambda x: x[1], reverse=True)[:3]
        for name, val in sorted_bhava:
            bar = "█" * int((val + 1) * 10)
            print(f"  {name:30s} {val:+.3f} {bar}")

        # Task scores
        print(f"\nTask Scores:")
        print(f"  Reasoning:  {result['reasoning']['overall']:.3f}")
        print(f"  Creativity: {result['creativity']['overall']:.3f}")
        print(f"  Novelty:    {result['novelty']:.3f}")


def demo_comparison():
    """Compare reasoning vs creativity texts."""
    print("\n" + "=" * 70)
    print("REASONING VS CREATIVITY COMPARISON")
    print("=" * 70)

    engine = create_engine()
    bhava = BhavaComputer90(mode="multiplicative")
    task_head = MultiTaskHead()

    reasoning_text = "Given the axioms, we derive that P implies Q"
    creative_text = "Colors sing melodies of forgotten summer dreams"

    print(f"\n🧠 Reasoning: \"{reasoning_text}\"")
    print(f"🎨 Creative:  \"{creative_text}\"")

    for label, text in [("Reasoning", reasoning_text), ("Creative", creative_text)]:
        onto_vec = engine.analyze(text)
        full_vec = bhava.get_full_vector(list(onto_vec.values))
        task_scores = task_head.forward(list(onto_vec.values))

        print(f"\n{label} Analysis:")
        print(f"  O7_REASONING: {onto_vec.values[5]:+.3f}")
        print(f"  O2_FORMING:   {onto_vec.values[1]:+.3f}")
        print(f"  Task Reasoning Score:  {task_scores['reasoning_score']:.3f}")
        print(f"  Task Creativity Score: {task_scores['creativity_score']:.3f}")


def main():
    """Run all demos."""
    print("\n" + "🌟" * 35)
    print("   LEARNABLE 100D ONTOLOGICAL ENGINE DEMO")
    print("🌟" * 35)

    # Show architecture
    demo_architecture()

    # Show Bhava structure
    demo_bhava_structure()

    # Demo engine
    demo_engine()

    # Demo predictions
    demo_prediction()

    # Compare reasoning vs creativity
    demo_comparison()

    # Demo training (quick)
    demo_training()

    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETE")
    print("=" * 70)
    print("\nThe 100D Ontological Engine provides:")
    print("  ✓ 10 interpretable ontological dimensions")
    print("  ✓ 90 Bhava sub-layers for relational dynamics")
    print("  ✓ Learnable through gradient descent")
    print("  ✓ Multi-task heads for reasoning & creativity")
    print("  ✓ Full interpretability - every dimension has meaning")
    print()


if __name__ == "__main__":
    main()
