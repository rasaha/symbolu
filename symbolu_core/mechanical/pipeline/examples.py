"""
Symbol-U Pipeline Examples (v3.0)

Demo script for the v3.0 linear pipeline.

Run with:
    python -m mechanical.pipeline.examples

This file demonstrates:
1. Basic pipeline usage
2. Custom render modes
3. Accessing pipeline context and diagnostics
4. Using the convenience function
"""

from __future__ import annotations


def example_basic_usage() -> None:
    """Basic pipeline usage example."""
    print("=" * 60)
    print("Example 1: Basic Pipeline Usage")
    print("=" * 60)

    from mechanical.pipeline import SymbolUPipeline, UserRequest

    # Create pipeline
    pipeline = SymbolUPipeline()

    # Create a request
    request = UserRequest(
        text="Why do I feel stuck in my career?",
        user_id="demo_user_001",
    )

    # Run the pipeline
    result = pipeline.run(request)

    # Display results
    print(f"\nInput: {request.text}")
    print(f"\nOutput:")
    print(f"  Raw Text: {result.raw_text[:200]}..." if len(result.raw_text) > 200 else f"  Raw Text: {result.raw_text}")
    print(f"  Mode: {result.mode}")
    print(f"  Persona: {result.meta.get('persona_id')}")
    print(f"  Tone Profile: {result.meta.get('tone_profile')}")
    print(f"  Readiness Level: {result.meta.get('readiness_level')}")
    print()


def example_render_modes() -> None:
    """Example showing different render modes."""
    print("=" * 60)
    print("Example 2: Different Render Modes")
    print("=" * 60)

    from mechanical.pipeline import SymbolUPipeline, UserRequest

    pipeline = SymbolUPipeline()
    query = "How can I improve my communication skills?"

    modes = ["minimal", "standard", "enhanced", "regulated"]

    for mode in modes:
        request = UserRequest(
            text=query,
            render_mode=mode,
        )
        result = pipeline.run(request)
        print(f"\n[{mode.upper()}] Output mode: {result.mode}")
        print(f"  Persona: {result.meta.get('persona_id')}")
    print()


def example_with_metadata() -> None:
    """Example with custom metadata for readiness/resistance hints."""
    print("=" * 60)
    print("Example 3: Custom Metadata (Readiness/Resistance)")
    print("=" * 60)

    from mechanical.pipeline import SymbolUPipeline, UserRequest

    pipeline = SymbolUPipeline()

    # High readiness, low resistance
    request_open = UserRequest(
        text="I want to understand my patterns better",
        metadata={
            "readiness_score": 0.9,
            "resistance_score": 0.1,
            "ego_state": "open",
        },
    )

    # Low readiness, high resistance
    request_defensive = UserRequest(
        text="I want to understand my patterns better",
        metadata={
            "readiness_score": 0.3,
            "resistance_score": 0.8,
            "ego_state": "defensive",
        },
    )

    result_open = pipeline.run(request_open)
    result_defensive = pipeline.run(request_defensive)

    print(f"\nSame query, different user states:")
    print(f"\nOpen State (high readiness, low resistance):")
    print(f"  Tone: {result_open.meta.get('tone_profile')}")
    print(f"  Readiness: {result_open.meta.get('readiness_level')}")

    print(f"\nDefensive State (low readiness, high resistance):")
    print(f"  Tone: {result_defensive.meta.get('tone_profile')}")
    print(f"  Readiness: {result_defensive.meta.get('readiness_level')}")
    print()


def example_convenience_function() -> None:
    """Example using the run_pipeline convenience function."""
    print("=" * 60)
    print("Example 4: Convenience Function")
    print("=" * 60)

    from mechanical.pipeline.orchestrator import run_pipeline

    result = run_pipeline(
        text="What is the meaning of consciousness?",
        render_mode="standard",
    )

    print(f"\nUsing run_pipeline():")
    print(f"  Output mode: {result.mode}")
    print(f"  Persona: {result.meta.get('persona_id')}")
    print(f"  MLCR Tier: {result.meta.get('mlcr_tier')}")
    print(f"  MLCR Intent: {result.meta.get('mlcr_intent')}")
    print()


def example_pipeline_context() -> None:
    """Example showing how to access intermediate pipeline context."""
    print("=" * 60)
    print("Example 5: Accessing Pipeline Context")
    print("=" * 60)

    from mechanical.pipeline import SymbolUPipeline, UserRequest, PipelineContext

    pipeline = SymbolUPipeline()

    # We can inspect intermediate states by accessing the context
    # during a custom run (this is for advanced debugging)
    request = UserRequest(text="Help me find balance in my life")

    # Run and capture final output
    result = pipeline.run(request)

    # The result.meta contains key pipeline decisions
    print(f"\nPipeline Trace (from result.meta):")
    print(f"  Pipeline Version: {result.meta.get('pipeline_version')}")
    print(f"  Router Mode: {result.meta.get('router_mode')}")
    print(f"  Persona ID: {result.meta.get('persona_id')}")
    print(f"  MLCR Tier: {result.meta.get('mlcr_tier')}")
    print(f"  MLCR Intent: {result.meta.get('mlcr_intent')}")
    print(f"  DHA Tone: {result.meta.get('tone_profile')}")
    print(f"  Readiness: {result.meta.get('readiness_level')}")
    print()


def example_router_info() -> None:
    """Example showing router modes and their descriptions."""
    print("=" * 60)
    print("Example 6: Router Mode Information")
    print("=" * 60)

    from mechanical.pipeline import PipelineRouter

    router = PipelineRouter()

    print("\nAvailable Router Modes:")
    for mode in router.VALID_MODES:
        explanation = router.explain(mode)
        is_current = " (v3.0 active)" if mode == "linear" else " (v3.1+ future)"
        print(f"\n  [{mode}]{is_current}")
        print(f"    {explanation}")
    print()


def main() -> None:
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Symbol-U Pipeline v3.0 - Examples")
    print("=" * 60 + "\n")

    try:
        example_basic_usage()
        example_render_modes()
        example_with_metadata()
        example_convenience_function()
        example_pipeline_context()
        example_router_info()

        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're running from the project root:")
        print("  python -m mechanical.pipeline.examples")
    except Exception as e:
        print(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    main()
