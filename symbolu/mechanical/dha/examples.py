"""
DHA Engine v3.0 - Examples
==========================

Example usage demonstrating the DHA Engine pipeline.

Examples show:
    1. Basic pipeline execution
    2. Different delivery profiles based on user state
    3. Integration patterns with other modules
"""

from typing import Dict, Any


def example_1_basic_pipeline():
    """
    Example 1: Basic DHA Pipeline

    Shows the simplest usage of the DHA Engine.
    """
    from symbolu.mechanical.dha.dha_engine import DHAEngine

    print("\n" + "=" * 60)
    print("Example 1: Basic DHA Pipeline")
    print("=" * 60)

    # Initialize engine
    engine = DHAEngine()

    # Sample renderer output (what FusionRenderer would produce)
    renderer_output = {
        "text": "You need to understand that your current approach has fundamental flaws. The pattern you're repeating is causing problems in multiple areas of your life."
    }

    # User state metadata
    metadata = {
        "readiness_score": 0.8,      # High readiness
        "resistance_score": 0.2,     # Low resistance
        "emotional_entropy": 0.3,    # Stable emotions
        "ego_state": "open",
        "folded_truths": ["acceptance", "growth"]
    }

    # Run the pipeline
    result = engine.run(
        renderer_output=renderer_output,
        metadata=metadata
    )

    print(f"\nDelivery Profile: {result.delivery_profile}")
    print(f"\nOriginal Message:\n{result.original_message}")
    print(f"\nAdapted Message:\n{result.adapted_message}")
    print(f"\nDiagnostics:")
    print(f"  - Readiness Level: {result.diagnostics['readiness_analysis']['level']}")
    print(f"  - Resistance Level: {result.diagnostics['resistance_analysis']['level']}")
    print(f"  - Confidence: {result.diagnostics['tone_selection']['confidence']}")

    return result


def example_2_high_resistance():
    """
    Example 2: High Resistance User

    Shows INVERSE_JOLT profile selection for resistant users.
    """
    from symbolu.mechanical.dha.dha_engine import DHAEngine

    print("\n" + "=" * 60)
    print("Example 2: High Resistance User (INVERSE_JOLT)")
    print("=" * 60)

    engine = DHAEngine()

    renderer_output = {
        "text": "Perhaps you might want to consider that there could be some areas where improvement is possible, if you feel comfortable exploring them."
    }

    # High resistance metadata
    metadata = {
        "readiness_score": 0.5,
        "resistance_score": 0.85,    # High resistance
        "emotional_entropy": 0.6,
        "ego_state": "defensive",
        "folded_truths": []
    }

    result = engine.run(
        renderer_output=renderer_output,
        metadata=metadata
    )

    print(f"\nDelivery Profile: {result.delivery_profile}")
    print(f"\nOriginal Message:\n{result.original_message}")
    print(f"\nAdapted Message:\n{result.adapted_message}")
    print(f"\nReasoning: {result.diagnostics['tone_selection']['reasoning']}")

    return result


def example_3_low_readiness():
    """
    Example 3: Low Readiness User

    Shows SYMBOLIC_METAPHOR profile for users not ready for direct truth.
    """
    from symbolu.mechanical.dha.dha_engine import DHAEngine

    print("\n" + "=" * 60)
    print("Example 3: Low Readiness User (SYMBOLIC_METAPHOR)")
    print("=" * 60)

    engine = DHAEngine()

    renderer_output = {
        "text": "The relationship dynamics here show a clear pattern of avoidance that stems from early attachment experiences."
    }

    # Low readiness, medium resistance
    metadata = {
        "readiness_score": 0.25,     # Low readiness
        "resistance_score": 0.5,     # Medium resistance
        "emotional_entropy": 0.4,
        "ego_state": "guarded",
        "folded_truths": []
    }

    result = engine.run(
        renderer_output=renderer_output,
        metadata=metadata
    )

    print(f"\nDelivery Profile: {result.delivery_profile}")
    print(f"\nOriginal Message:\n{result.original_message}")
    print(f"\nAdapted Message:\n{result.adapted_message}")
    print(f"\nReasoning: {result.diagnostics['tone_selection']['reasoning']}")

    return result


def example_4_analysis_only():
    """
    Example 4: Analysis Only (No Text Modulation)

    Shows how to analyze user state without adapting text.
    """
    from symbolu.mechanical.dha.dha_engine import DHAEngine

    print("\n" + "=" * 60)
    print("Example 4: Analysis Only (Pre-flight Check)")
    print("=" * 60)

    engine = DHAEngine()

    # Various user states to analyze
    user_states = [
        {"readiness_score": 0.9, "resistance_score": 0.1, "ego_state": "open"},
        {"readiness_score": 0.3, "resistance_score": 0.8, "ego_state": "defensive"},
        {"readiness_score": 0.5, "resistance_score": 0.5, "ego_state": "neutral"},
    ]

    for i, metadata in enumerate(user_states):
        analysis = engine.analyze_only(metadata)
        print(f"\nUser State {i + 1}:")
        print(f"  - Readiness: {metadata['readiness_score']} → {analysis['readiness']['readiness_level']}")
        print(f"  - Resistance: {metadata['resistance_score']} → {analysis['resistance']['resistance_level']}")
        print(f"  - Recommended Profile: {analysis['recommended_profile']}")
        print(f"  - Confidence: {analysis['confidence']:.2f}")


def example_5_full_integration():
    """
    Example 5: Full Integration Pattern

    Shows how DHA integrates with Fusion, Persona, and Renderer.
    """
    print("\n" + "=" * 60)
    print("Example 5: Full Integration Pattern")
    print("=" * 60)

    # Note: This example shows the PATTERN of integration.
    # In production, you would import actual modules:
    #
    # from symbolu.mechanical.fusion.fusion_engine import FusionEngine
    # from symbolu.mechanical.persona.engine import PersonaEngine
    # from symbolu.mechanical.renderer.fusion_renderer import FusionRenderer
    # from symbolu.mechanical.dha.dha_engine import DHAEngine

    from symbolu.mechanical.dha.dha_engine import DHAEngine

    # Simulated upstream outputs
    fusion_output = {
        "domain": "psychology",
        "complexity": 0.7,
        "merged_response": "Analysis indicates pattern recognition issues.",
        "confidence": 0.85
    }

    persona_output = {
        "persona_id": "sage",
        "tone": "resonance",
        "layers": {
            "symbolic": {"theme": "growth"},
            "practical": {"actions": ["reflect", "journal"]},
            "mirror": {"truth": "avoidance pattern"}
        }
    }

    renderer_output = {
        "text": "The pattern you're experiencing reflects a deeper avoidance of vulnerability. Your symbolic layer suggests growth is possible, while the practical steps involve reflection and journaling. The mirror truth reveals this avoidance pattern clearly."
    }

    metadata = {
        "readiness_score": 0.7,
        "resistance_score": 0.3,
        "emotional_entropy": 0.4,
        "ego_state": "receptive",
        "folded_truths": ["self-awareness"]
    }

    # Initialize and run DHA
    engine = DHAEngine()

    result = engine.run(
        fusion_output=fusion_output,
        persona_output=persona_output,
        renderer_output=renderer_output,
        metadata=metadata
    )

    print(f"\nIntegration Result:")
    print(f"  - Profile: {result.delivery_profile}")
    print(f"  - Process Time: {result.diagnostics['process_time_ms']:.2f}ms")
    print(f"\nOriginal:\n{result.original_message[:100]}...")
    print(f"\nAdapted:\n{result.adapted_message[:150]}...")

    # Show statistics
    print(f"\nEngine Stats:")
    stats = engine.get_stats()
    print(f"  - Total Runs: {stats['total_runs']}")
    print(f"  - Profile Counts: {stats['profile_counts']}")

    return result


def run_all_examples():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# DHA Engine v3.0 - Complete Examples")
    print("#" * 60)

    example_1_basic_pipeline()
    example_2_high_resistance()
    example_3_low_readiness()
    example_4_analysis_only()
    example_5_full_integration()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_examples()
