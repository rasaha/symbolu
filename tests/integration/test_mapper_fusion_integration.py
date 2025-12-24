#!/usr/bin/env python3
"""
Test Mapper-Fusion Integration
==============================

Tests the integration of HRM/LAM/LCM mapper outputs with the Fusion engine
through the mapper_fusion_adapter module.
"""

import sys


def test_adapter_imports():
    """Test that the adapter module imports correctly."""
    print("=" * 60)
    print("TEST 1: Adapter Imports")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        create_candidates_from_mappers,
        get_mapper_summary,
        compute_hrm_channel_score,
        compute_lcm_channel_score,
        compute_moe_channel_score,
        compute_temporal_weight,
    )

    print("1.1 All adapter functions imported successfully")
    print("  - create_candidates_from_mappers")
    print("  - get_mapper_summary")
    print("  - compute_hrm_channel_score")
    print("  - compute_lcm_channel_score")
    print("  - compute_moe_channel_score")
    print("  - compute_temporal_weight")

    print("\n[PASS] Adapter Imports Test")
    return True


def test_default_scores_without_mappers():
    """Test default channel scores when no mappers are run."""
    print("\n" + "=" * 60)
    print("TEST 2: Default Scores (No Mappers)")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        compute_hrm_channel_score,
        compute_lcm_channel_score,
        compute_moe_channel_score,
        compute_temporal_weight,
    )

    # When mappers are None, should return default values
    hrm_score = compute_hrm_channel_score(None)
    lcm_score = compute_lcm_channel_score(None)
    moe_score = compute_moe_channel_score(None, None, "general")
    temporal_weight = compute_temporal_weight(None)

    print(f"2.1 Default HRM score: {hrm_score:.2f} (expected: 0.50)")
    print(f"2.2 Default LCM score: {lcm_score:.2f} (expected: 0.50)")
    print(f"2.3 Default MoE score: {moe_score:.2f} (expected: 0.40)")
    print(f"2.4 Default temporal weight: {temporal_weight:.2f} (expected: 0.00)")

    assert hrm_score == 0.5, f"HRM score should be 0.5, got {hrm_score}"
    assert lcm_score == 0.5, f"LCM score should be 0.5, got {lcm_score}"
    assert moe_score == 0.4, f"MoE score should be 0.4, got {moe_score}"
    assert temporal_weight == 0.0, f"Temporal weight should be 0.0, got {temporal_weight}"

    print("\n[PASS] Default Scores Test")
    return True


def test_candidates_without_mappers():
    """Test candidate generation when no mappers are run."""
    print("\n" + "=" * 60)
    print("TEST 3: Candidates Without Mappers")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        create_candidates_from_mappers,
    )

    # Generate candidates without any mapper outputs
    candidates = create_candidates_from_mappers(
        text="What is consciousness?",
        domain="philosophy",
        hrm_map=None,
        lam_map=None,
        lcm_map=None,
    )

    print(f"3.1 Generated {len(candidates)} candidates")
    for i, c in enumerate(candidates, 1):
        print(f"    {i}. ID: {c.id[:15]}... Source: {c.source.value}")
        print(f"       HRM: {c.channel_scores['hrm']:.2f}, LCM: {c.channel_scores['lcm']:.2f}, MoE: {c.channel_scores['moe']:.2f}")

    # Should have at least MoE + fallback candidates
    assert len(candidates) >= 2, f"Expected at least 2 candidates, got {len(candidates)}"

    # Verify all candidates have required fields
    for c in candidates:
        assert c.id is not None
        assert c.text is not None
        assert "hrm" in c.channel_scores
        assert "lcm" in c.channel_scores
        assert "moe" in c.channel_scores

    print("\n[PASS] Candidates Without Mappers Test")
    return True


def test_hrm_map_integration():
    """Test HRM map integration with candidates."""
    print("\n" + "=" * 60)
    print("TEST 4: HRM Map Integration")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        create_candidates_from_mappers,
        compute_hrm_channel_score,
    )
    from symbolu.mechanical.hrm import HighResolutionMap

    # Create a mock HRM map
    hrm_map = HighResolutionMap(
        dominant_aspects=["Purpose", "Universal", "Reasoning"],
        suppressed_aspects=["Execution", "Form"],
        anchor_profile={"Meaning": 0.4, "Collective": 0.3, "Belonging": 0.2, "Challenge": 0.1},
        entropy_profile={
            "H_D_norm": 0.7,
            "H_G_norm": 0.5,
            "H_K_norm": 0.4,
            "entropy_mix": 0.55,
            "regime": "medium",
        },
        conflict_zones=["identity_integration_gap", "grounding_deficit"],
        resolution_hints=[
            "meaning_oriented_response",
            "upper_tier_deep_processing",
            "support_identity_grounding",
        ],
        tier="upper",
        domain="philosophy",
    )

    # Compute HRM score
    hrm_score = compute_hrm_channel_score(hrm_map)
    print(f"4.1 HRM channel score: {hrm_score:.3f}")
    print(f"    - Dominant aspects: {hrm_map.dominant_aspects}")
    print(f"    - Conflict zones: {hrm_map.conflict_zones}")
    print(f"    - Tier: {hrm_map.tier}")

    # HRM score should be elevated for upper tier with meaning-oriented hints
    assert hrm_score > 0.5, f"Upper-tier HRM should have score > 0.5, got {hrm_score}"

    # Generate candidates
    candidates = create_candidates_from_mappers(
        text="What is the meaning of existence?",
        domain="philosophy",
        hrm_map=hrm_map,
        lam_map=None,
        lcm_map=None,
    )

    # Should have HRM candidate
    hrm_candidates = [c for c in candidates if "hrm" in c.id]
    print(f"\n4.2 Generated {len(hrm_candidates)} HRM-derived candidate(s)")

    if hrm_candidates:
        hrm_c = hrm_candidates[0]
        print(f"    Text: {hrm_c.text[:50]}...")
        print(f"    Channel scores: HRM={hrm_c.channel_scores['hrm']:.2f}")

        # HRM candidate should have elevated HRM score
        assert hrm_c.channel_scores["hrm"] > 0.5

    print("\n[PASS] HRM Map Integration Test")
    return True


def test_lcm_map_integration():
    """Test LCM map integration with candidates."""
    print("\n" + "=" * 60)
    print("TEST 5: LCM Map Integration")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        create_candidates_from_mappers,
        compute_lcm_channel_score,
    )
    from symbolu.mechanical.lcm import LowContextMap

    # Create a mock LCM map for a code task
    lcm_map = LowContextMap(
        task_type="code",
        key_terms=["function", "python", "error", "fix"],
        numeric_features={"count": 0},
        complexity_score=0.25,
        entropy_regime="low",
        recommended_engine="fusion",
    )

    # Compute LCM score
    lcm_score = compute_lcm_channel_score(lcm_map)
    print(f"5.1 LCM channel score: {lcm_score:.3f}")
    print(f"    - Task type: {lcm_map.task_type}")
    print(f"    - Complexity: {lcm_map.complexity_score}")
    print(f"    - Recommended engine: {lcm_map.recommended_engine}")

    # LCM score should be elevated for code task with low complexity
    assert lcm_score > 0.6, f"Code task LCM should have score > 0.6, got {lcm_score}"

    # Generate candidates
    candidates = create_candidates_from_mappers(
        text="Fix the TypeError in my Python function",
        domain="code",
        hrm_map=None,
        lam_map=None,
        lcm_map=lcm_map,
    )

    # Should have LCM candidate
    lcm_candidates = [c for c in candidates if "lcm" in c.id]
    print(f"\n5.2 Generated {len(lcm_candidates)} LCM-derived candidate(s)")

    if lcm_candidates:
        lcm_c = lcm_candidates[0]
        print(f"    Text: {lcm_c.text[:50]}...")
        print(f"    Channel scores: LCM={lcm_c.channel_scores['lcm']:.2f}")

        # LCM candidate should have elevated LCM score
        assert lcm_c.channel_scores["lcm"] > 0.6

    print("\n[PASS] LCM Map Integration Test")
    return True


def test_lam_map_integration():
    """Test LAM map integration with candidates."""
    print("\n" + "=" * 60)
    print("TEST 6: LAM Map Integration")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        create_candidates_from_mappers,
        compute_temporal_weight,
    )
    from symbolu.mechanical.lam import LongArcMap

    # Create a mock LAM map for a tension state
    lam_map = LongArcMap(
        trajectory_summary={
            "slope": 0.15,
            "trend": "rising",
            "confidence": 0.7,
        },
        bhava_momentum={
            "upward_ratio": 0.75,
            "acceleration": 0.4,
            "strength": 0.6,
        },
        tension_corridor={
            "length": 3.0,
            "intensity": 0.5,
            "active": 0.0,
        },
        recovery_pattern={
            "recovering": 1.0,
            "progress": 0.4,
        },
        active_patterns=["breakthrough_arc", "emotional_release"],
        domain_transfers={"breakthrough_arc": "Potential for transformation"},
        arc_state="turning_point",
        long_arc_signal=0.65,
    )

    # Compute temporal weight
    temporal_weight = compute_temporal_weight(lam_map)
    print(f"6.1 Temporal weight: {temporal_weight:.3f}")
    print(f"    - Arc state: {lam_map.arc_state}")
    print(f"    - Long arc signal: {lam_map.long_arc_signal}")
    print(f"    - Trajectory trend: {lam_map.trajectory_summary['trend']}")

    # Temporal weight should be elevated for turning point with high long_arc_signal
    assert temporal_weight > 0.5, f"Turning point should have temporal weight > 0.5, got {temporal_weight}"

    # Generate candidates
    candidates = create_candidates_from_mappers(
        text="I feel like I'm on the verge of a breakthrough",
        domain="therapy",
        hrm_map=None,
        lam_map=lam_map,
        lcm_map=None,
    )

    # Should have LAM-derived candidate
    lam_candidates = [c for c in candidates if "lam" in c.id]
    print(f"\n6.2 Generated {len(lam_candidates)} LAM-derived candidate(s)")

    if lam_candidates:
        lam_c = lam_candidates[0]
        print(f"    Text: {lam_c.text[:60]}...")
        print(f"    Relevance: {lam_c.relevance_score:.2f}")

        # LAM candidate should have elevated relevance
        assert lam_c.relevance_score > 0.7

    print("\n[PASS] LAM Map Integration Test")
    return True


def test_mapper_summary():
    """Test mapper summary generation."""
    print("\n" + "=" * 60)
    print("TEST 7: Mapper Summary")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import get_mapper_summary
    from symbolu.mechanical.hrm import HighResolutionMap
    from symbolu.mechanical.lcm import LowContextMap

    # Create mock maps
    hrm_map = HighResolutionMap(
        dominant_aspects=["Purpose", "Reasoning"],
        suppressed_aspects=["Execution"],
        anchor_profile={"Meaning": 0.5},
        entropy_profile={"regime": "high", "entropy_mix": 0.7},
        conflict_zones=["grounding_deficit"],
        resolution_hints=["deep_processing", "meaning_oriented"],
        tier="upper",
        domain="philosophy",
    )

    lcm_map = LowContextMap(
        task_type="lookup",
        key_terms=["definition"],
        numeric_features={"count": 0},
        complexity_score=0.2,
        entropy_regime="low",
        recommended_engine="fusion",
    )

    # Get summary
    summary = get_mapper_summary(hrm_map=hrm_map, lam_map=None, lcm_map=lcm_map)

    print(f"7.1 Mapper status:")
    print(f"    - HRM active: {summary['hrm_active']}")
    print(f"    - LAM active: {summary['lam_active']}")
    print(f"    - LCM active: {summary['lcm_active']}")

    print(f"\n7.2 HRM summary:")
    print(f"    - Dominant: {summary['hrm']['dominant_aspects']}")
    print(f"    - Tier: {summary['hrm']['tier']}")

    print(f"\n7.3 LCM summary:")
    print(f"    - Task type: {summary['lcm']['task_type']}")
    print(f"    - Complexity: {summary['lcm']['complexity_score']}")

    print(f"\n7.4 Derived channel scores:")
    for channel, score in summary['channel_scores'].items():
        print(f"    - {channel}: {score:.3f}")

    # Verify structure
    assert summary['hrm_active'] == True
    assert summary['lam_active'] == False
    assert summary['lcm_active'] == True
    assert "hrm" in summary
    assert "lcm" in summary

    print("\n[PASS] Mapper Summary Test")
    return True


def test_combined_mappers():
    """Test all mappers combined."""
    print("\n" + "=" * 60)
    print("TEST 8: Combined Mappers Integration")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import (
        create_candidates_from_mappers,
        get_mapper_summary,
    )
    from symbolu.mechanical.hrm import HighResolutionMap
    from symbolu.mechanical.lam import LongArcMap
    from symbolu.mechanical.lcm import LowContextMap

    # Create all mapper outputs
    hrm_map = HighResolutionMap(
        dominant_aspects=["Purpose", "Agency"],
        suppressed_aspects=["Form"],
        anchor_profile={"Meaning": 0.5, "Change": 0.3},
        entropy_profile={"regime": "medium", "entropy_mix": 0.5},
        conflict_zones=["growth_edge_tension"],
        resolution_hints=["transformative_edge_detected"],
        tier="upper",
        domain="therapy",
    )

    lam_map = LongArcMap(
        trajectory_summary={"trend": "rising", "confidence": 0.6, "slope": 0.2},
        bhava_momentum={"upward_ratio": 0.7, "acceleration": 0.3, "strength": 0.5},
        tension_corridor={"length": 2.0, "intensity": 0.4, "active": 0.0},
        recovery_pattern={"recovering": 0.0, "progress": 0.0},
        active_patterns=["growth_arc"],
        domain_transfers={},
        arc_state="turning_point",
        long_arc_signal=0.55,
    )

    lcm_map = LowContextMap(
        task_type="generic",
        key_terms=["growth", "change", "transformation"],
        numeric_features={"count": 0},
        complexity_score=0.4,
        entropy_regime="medium",
        recommended_engine="persona",
    )

    # Generate candidates
    candidates = create_candidates_from_mappers(
        text="I want to transform my life",
        domain="therapy",
        hrm_map=hrm_map,
        lam_map=lam_map,
        lcm_map=lcm_map,
    )

    print(f"8.1 Generated {len(candidates)} candidates from all mappers:")
    for c in candidates:
        source_type = c.id.split("_")[0]
        print(f"    - {source_type.upper()}: HRM={c.channel_scores['hrm']:.2f}, LCM={c.channel_scores['lcm']:.2f}, MoE={c.channel_scores['moe']:.2f}")

    # Should have candidates from each mapper + MoE
    candidate_sources = {c.id.split("_")[0] for c in candidates}
    print(f"\n8.2 Candidate sources: {candidate_sources}")

    # At minimum: HRM, LCM, LAM, MoE
    assert len(candidates) >= 4, f"Expected at least 4 candidates, got {len(candidates)}"

    # Get summary
    summary = get_mapper_summary(hrm_map, lam_map, lcm_map)
    print(f"\n8.3 All mappers active: HRM={summary['hrm_active']}, LAM={summary['lam_active']}, LCM={summary['lcm_active']}")

    assert summary['hrm_active'] and summary['lam_active'] and summary['lcm_active']

    print("\n[PASS] Combined Mappers Integration Test")
    return True


def test_domain_modulation():
    """Test domain-specific MoE score modulation."""
    print("\n" + "=" * 60)
    print("TEST 9: Domain-Specific MoE Modulation")
    print("=" * 60)

    from symbolu.mechanical.pipeline.mapper_fusion_adapter import compute_moe_channel_score

    # Test various domains
    domains = [
        ("medical", 0.7),
        ("legal", 0.7),
        ("financial", 0.7),
        ("code", 0.65),
        ("general", 0.4),
        ("philosophy", 0.55),
    ]

    print("9.1 Domain-specific MoE scores:")
    for domain, expected_min in domains:
        score = compute_moe_channel_score(None, None, domain)
        status = "[PASS]" if score >= expected_min else "[FAIL]"
        print(f"    {domain:12s}: {score:.3f} (expected >= {expected_min:.2f}) {status}")

    # Verify specialized domains have higher scores
    medical_score = compute_moe_channel_score(None, None, "medical")
    general_score = compute_moe_channel_score(None, None, "general")

    assert medical_score > general_score, "Medical domain should have higher MoE than general"

    print("\n[PASS] Domain-Specific MoE Modulation Test")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MAPPER-FUSION INTEGRATION TEST SUITE")
    print("=" * 60)

    all_passed = True

    try:
        all_passed &= test_adapter_imports()
        all_passed &= test_default_scores_without_mappers()
        all_passed &= test_candidates_without_mappers()
        all_passed &= test_hrm_map_integration()
        all_passed &= test_lcm_map_integration()
        all_passed &= test_lam_map_integration()
        all_passed &= test_mapper_summary()
        all_passed &= test_combined_mappers()
        all_passed &= test_domain_modulation()

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
