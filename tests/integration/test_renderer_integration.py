#!/usr/bin/env python3
"""
Test Renderer Integration
=========================

Tests the integration of FusionRenderer and VarnaHybridRenderer into the pipeline.
"""

import sys


def test_renderer_imports():
    """Test that renderer integration imports correctly."""
    print("=" * 60)
    print("TEST 1: Renderer Integration Imports")
    print("=" * 60)

    from symbolu.mechanical.pipeline.renderer_integration import (
        IntegratedRenderedOutput,
        run_integrated_renderer,
        build_fusion_output_from_context,
        create_legacy_rendered_output,
    )

    print("1.1 All renderer integration functions imported successfully")
    print("  - IntegratedRenderedOutput")
    print("  - run_integrated_renderer")
    print("  - build_fusion_output_from_context")
    print("  - create_legacy_rendered_output")

    print("\n[PASS] Renderer Integration Imports Test")
    return True


def test_fusion_output_builder():
    """Test FusionOutput builder with mock context."""
    print("\n" + "=" * 60)
    print("TEST 2: FusionOutput Builder")
    print("=" * 60)

    from symbolu.mechanical.pipeline.renderer_integration import build_fusion_output_from_context
    from symbolu.mechanical.hrm import HighResolutionMap
    from symbolu.mechanical.lcm import LowContextMap

    # Create mock context
    class MockRequest:
        text = "What is the meaning of consciousness?"
        render_mode = "standard"

    class MockDha:
        guarded_text = "Consciousness is the awareness of one's existence and experience."
        tone_profile = "reflective"
        readiness_level = "MEDIUM"

    class MockMlcr:
        @property
        def explain_log(self):
            return {"meta": {"tier": "UPPER", "intent": "WHY", "domain": "philosophy"}}

    class MockFusion:
        trace = {"conflicts_resolved": []}

    class MockPersona:
        active_persona_id = "sage"

    class MockContext:
        request = MockRequest()
        dha = MockDha()
        mlcr = MockMlcr()
        fusion = MockFusion()
        persona = MockPersona()
        router_mode = "linear"

        hrm_map = HighResolutionMap(
            dominant_aspects=["Purpose", "Universal"],
            suppressed_aspects=["Execution"],
            anchor_profile={"Meaning": 0.6, "Collective": 0.3},
            entropy_profile={"regime": "medium", "entropy_mix": 0.5},
            conflict_zones=["identity_integration_gap"],
            resolution_hints=["deep_processing"],
            tier="upper",
            domain="philosophy",
        )

        lcm_map = LowContextMap(
            task_type="generic",
            key_terms=["meaning", "consciousness"],
            numeric_features={"count": 0},
            complexity_score=0.6,
            entropy_regime="medium",
            recommended_engine="persona",
        )

        lam_map = None  # No LAM for this test

        mapper_summary = {
            "hrm_active": True,
            "lam_active": False,
            "lcm_active": True,
            "channel_scores": {"hrm": 0.7, "lcm": 0.5, "moe": 0.55},
        }

    ctx = MockContext()

    # Build FusionOutput
    fusion_output = build_fusion_output_from_context(ctx)

    print(f"2.1 FusionOutput built successfully")
    print(f"    Query: {fusion_output.query[:40]}...")
    print(f"    Merged response: {fusion_output.merged_response[:40]}...")
    print(f"    Channel weights: {fusion_output.channel_weights}")
    print(f"    HRM content keys: {list(fusion_output.hrm_content.keys())}")
    print(f"    LCM content keys: {list(fusion_output.lcm_content.keys())}")

    assert fusion_output.query == "What is the meaning of consciousness?"
    assert "Consciousness" in fusion_output.merged_response
    assert "hrm" in fusion_output.channel_weights
    assert "dominant_aspects" in fusion_output.hrm_content
    assert "task_type" in fusion_output.lcm_content

    print("\n[PASS] FusionOutput Builder Test")
    return True


def test_integrated_renderer_with_mock():
    """Test integrated renderer with mock context."""
    print("\n" + "=" * 60)
    print("TEST 3: Integrated Renderer")
    print("=" * 60)

    from symbolu.mechanical.pipeline.renderer_integration import run_integrated_renderer
    from symbolu.mechanical.hrm import HighResolutionMap
    from symbolu.mechanical.lcm import LowContextMap

    # Create mock context
    class MockRequest:
        text = "Love conquers all obstacles"
        render_mode = "standard"

    class MockDha:
        guarded_text = "Love is a powerful force that overcomes challenges."
        tone_profile = "warm"
        readiness_level = "HIGH"

    class MockMlcr:
        @property
        def explain_log(self):
            return {"meta": {"tier": "UPPER", "intent": "WHY", "domain": "therapy"}}

    class MockFusion:
        trace = {}

    class MockPersona:
        active_persona_id = "friendly"

    class MockContext:
        request = MockRequest()
        dha = MockDha()
        mlcr = MockMlcr()
        fusion = MockFusion()
        persona = MockPersona()
        router_mode = "linear"

        hrm_map = HighResolutionMap(
            dominant_aspects=["Purpose", "Agency"],
            suppressed_aspects=["Form"],
            anchor_profile={"Belonging": 0.5, "Meaning": 0.3},
            entropy_profile={"regime": "low", "entropy_mix": 0.3},
            conflict_zones=[],
            resolution_hints=["connection_emphasis"],
            tier="upper",
            domain="therapy",
        )

        lcm_map = None
        lam_map = None

        mapper_summary = {
            "hrm_active": True,
            "lam_active": False,
            "lcm_active": False,
            "channel_scores": {"hrm": 0.75, "lcm": 0.4, "moe": 0.5},
        }

    ctx = MockContext()

    # Run integrated renderer
    result = run_integrated_renderer(ctx)

    print(f"3.1 Integrated renderer output:")
    print(f"    Raw text: {result.raw_text[:40]}...")
    print(f"    Mode: {result.mode}")
    print(f"    Phoneme harmony: {result.phoneme_harmony:.3f}")

    if result.symbolic_layer:
        print(f"\n3.2 Symbolic Layer:")
        print(f"    Theme: {result.symbolic_layer.theme}")
        print(f"    Archetype: {result.symbolic_layer.archetype}")
        print(f"    Dominant channel: {result.symbolic_layer.dominant_channel}")

    if result.practical_layer:
        print(f"\n3.3 Practical Layer:")
        print(f"    Domain: {result.practical_layer.domain}")
        print(f"    Coherence: {result.practical_layer.coherence_score:.3f}")

    if result.varna_analysis:
        print(f"\n3.4 Varṇa Analysis:")
        print(f"    Dominant layer: {result.varna_analysis.dominant_layer}")
        print(f"    Overall harmony: {result.varna_analysis.overall_harmony:.3f}")
        print(f"    Bridge meanings: {list(result.varna_analysis.bridge_meanings)[:3]}...")

    if result.phoneme_routing:
        print(f"\n3.5 Phoneme Routing:")
        print(f"    Model type: {result.phoneme_routing['model_type']}")
        print(f"    Confidence: {result.phoneme_routing['confidence']:.3f}")

    # Verify structure
    assert result.raw_text is not None
    assert result.mode == "standard"
    assert isinstance(result.meta, dict)

    print("\n[PASS] Integrated Renderer Test")
    return True


def test_integrated_output_to_dict():
    """Test IntegratedRenderedOutput serialization."""
    print("\n" + "=" * 60)
    print("TEST 4: Output Serialization")
    print("=" * 60)

    from symbolu.mechanical.pipeline.renderer_integration import IntegratedRenderedOutput

    # Create output without complex VarnaAnalysisResult
    output = IntegratedRenderedOutput(
        raw_text="Test output",
        mode="standard",
        varna_analysis=None,  # Skip complex mock
        phoneme_routing={"model_type": "reasoning", "confidence": 0.8},
        phoneme_harmony=0.8,
        meta={"test": True},
    )

    # Convert to dict
    output_dict = output.to_dict()

    print(f"4.1 Output serialization:")
    print(f"    Keys: {list(output_dict.keys())}")
    print(f"    Raw text: {output_dict['raw_text']}")
    print(f"    Mode: {output_dict['mode']}")
    print(f"    Phoneme routing: {output_dict['phoneme_routing']}")
    print(f"    Phoneme harmony: {output_dict['phoneme_harmony']}")

    assert output_dict["raw_text"] == "Test output"
    assert output_dict["mode"] == "standard"
    assert output_dict["phoneme_harmony"] == 0.8
    assert output_dict["phoneme_routing"]["model_type"] == "reasoning"

    print("\n[PASS] Output Serialization Test")
    return True


def test_legacy_compatibility():
    """Test legacy output format compatibility."""
    print("\n" + "=" * 60)
    print("TEST 5: Legacy Compatibility")
    print("=" * 60)

    from symbolu.mechanical.pipeline.renderer_integration import (
        IntegratedRenderedOutput,
        create_legacy_rendered_output,
    )

    integrated = IntegratedRenderedOutput(
        raw_text="Legacy compatible output",
        mode="standard",
        meta={"persona_id": "sage", "pipeline_version": "3.1"},
    )

    legacy = create_legacy_rendered_output(integrated)

    print(f"5.1 Legacy output:")
    print(f"    raw_text: {legacy['raw_text']}")
    print(f"    mode: {legacy['mode']}")
    print(f"    meta keys: {list(legacy['meta'].keys())}")

    assert legacy["raw_text"] == "Legacy compatible output"
    assert legacy["mode"] == "standard"
    assert "persona_id" in legacy["meta"]

    print("\n[PASS] Legacy Compatibility Test")
    return True


def test_mode_mapping():
    """Test render mode mappings."""
    print("\n" + "=" * 60)
    print("TEST 6: Mode Mappings")
    print("=" * 60)

    from symbolu.mechanical.pipeline.renderer_integration import (
        get_render_mode,
        get_domain,
        get_hybrid_mode,
    )
    from symbolu.mechanical.renderer.fusion_renderer import RenderMode, Domain
    from symbolu.mechanical.renderer.varna_hybrid_renderer import HybridRenderMode

    # Test render mode mapping
    modes = [
        ("minimal", RenderMode.MINIMAL),
        ("standard", RenderMode.STANDARD),
        ("enhanced", RenderMode.SYMBOLIC),
        ("symbolic", RenderMode.SYMBOLIC),
        ("regulated", RenderMode.REGULATED),
        ("unknown", RenderMode.STANDARD),
    ]

    print("6.1 Render mode mapping:")
    for mode_str, expected in modes:
        result = get_render_mode(mode_str)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"    {mode_str:12s} -> {result.value:12s} {status}")
        assert result == expected

    # Test domain mapping
    domains = [
        ("general", Domain.GENERAL),
        ("finance", Domain.FINANCE),
        ("trading", Domain.FINANCE),
        ("medical", Domain.MEDICAL),
        ("therapy", Domain.PSYCHOLOGY),
    ]

    print("\n6.2 Domain mapping:")
    for domain_str, expected in domains:
        result = get_domain(domain_str)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"    {domain_str:12s} -> {result.value:12s} {status}")
        assert result == expected

    # Test hybrid mode mapping
    hybrid_modes = [
        ("minimal", HybridRenderMode.PHONEME_ONLY),
        ("standard", HybridRenderMode.HYBRID_FAST),
        ("enhanced", HybridRenderMode.HYBRID_FULL),
    ]

    print("\n6.3 Hybrid mode mapping:")
    for mode_str, expected in hybrid_modes:
        result = get_hybrid_mode(mode_str)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"    {mode_str:12s} -> {result.value:15s} {status}")
        assert result == expected

    print("\n[PASS] Mode Mappings Test")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("RENDERER INTEGRATION TEST SUITE")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_renderer_imports()
        all_passed &= test_fusion_output_builder()
        all_passed &= test_integrated_renderer_with_mock()
        all_passed &= test_integrated_output_to_dict()
        all_passed &= test_legacy_compatibility()
        all_passed &= test_mode_mapping()

        print("\n" + "=" * 60)
        if all_passed:
            print("ALL TESTS PASSED")
        else:
            print("SOME TESTS FAILED")
        print("=" * 60 + "\n")

        return 0 if all_passed else 1

    except Exception as e:
        print(f"\nTEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
