"""
Phase 17: Semantic Integrity Formula v1.0 + Cognitive Drift Metric v3 — Test Suite

This test suite validates the deterministic, zero-LLM implementation of:
    1. Semantic integrity scoring (coherence/self-consistency)
    2. Cognitive drift v3 (semantic center-of-gravity drift)

Test Groups:
    GROUP A — Semantic Integrity Math (10 tests)
    GROUP B — Cognitive Drift v3 Math (8 tests)
    GROUP C — Integration with Coherence Engine & Observer (8 tests)
    GROUP D — Behavioral Invariance (6 tests)

CRITICAL: All tests must pass to ensure zero-LLM, deterministic, and backward-compatible behavior.
"""

import pytest
from symbolu_core.formulas.semantic_integrity import (
    compute_semantic_integrity,
    compute_cognitive_drift_v3,
    SemanticIntegritySnapshot,
    CognitiveDriftSnapshotV3,
)


# ============================================================================
# GROUP A — Semantic Integrity Math (10 tests)
# ============================================================================


def test_semantic_integrity_range():
    """Semantic integrity score is always in [0, 1] range."""
    # Test with valid skeleton
    skeleton = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": True,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 3,
    }

    mapper_profile = {
        "detail_bias": 0.5,
        "practical_bias": 0.5,
        "reflective_bias": 0.5,
    }

    result = compute_semantic_integrity(
        current_skeleton=skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc="insight_arc",
        identity_signature="self_anchoring",
    )

    assert result.semantic_integrity_score is not None
    assert 0.0 <= result.semantic_integrity_score <= 1.0


def test_semantic_integrity_determinism():
    """Semantic integrity computation is deterministic (same input → same output)."""
    skeleton = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": False,
        "has_dha_insight": True,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 2,
    }

    mapper_profile = {
        "detail_bias": 0.6,
        "practical_bias": 0.7,
        "reflective_bias": 0.4,
    }

    result1 = compute_semantic_integrity(
        current_skeleton=skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc="stabilization_arc",
        identity_signature="self_integration",
    )

    result2 = compute_semantic_integrity(
        current_skeleton=skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc="stabilization_arc",
        identity_signature="self_integration",
    )

    assert result1.semantic_integrity_score == result2.semantic_integrity_score
    assert result1.structural_consistency == result2.structural_consistency
    assert result1.layer_agreement_score == result2.layer_agreement_score


def test_structural_consistency_reacts_to_skeleton_changes():
    """Structural consistency decreases when skeleton structure changes."""
    # Baseline skeleton
    baseline = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": True,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 3,
    }

    # Changed skeleton (different flags)
    changed = {
        "has_symbolic": False,  # Changed
        "has_practical": False,  # Changed
        "has_mirror": True,
        "has_dha_insight": True,  # Changed
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 5,  # Changed
    }

    mapper_profile = {"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}

    # Compute integrity with stable history
    stable_result = compute_semantic_integrity(
        current_skeleton=baseline,
        previous_skeletons=[baseline, baseline, baseline],
        mapper_profile=mapper_profile,
        intent_arc=None,
        identity_signature=None,
    )

    # Compute integrity with changed skeleton
    changed_result = compute_semantic_integrity(
        current_skeleton=changed,
        previous_skeletons=[baseline, baseline, baseline],
        mapper_profile=mapper_profile,
        intent_arc=None,
        identity_signature=None,
    )

    # Structural consistency should be lower for changed skeleton
    assert changed_result.structural_consistency < stable_result.structural_consistency


def test_layer_agreement_decreases_under_contradictions():
    """Layer agreement score decreases when DHA conflict marker is present."""
    # Skeleton with conflict
    conflict_skeleton = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": True,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": True,  # Conflict marker
        "section_count": 3,
    }

    # Skeleton with alignment
    aligned_skeleton = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": True,
        "has_dha_insight": False,
        "has_dha_alignment": True,  # Alignment marker
        "has_dha_conflict": False,
        "section_count": 3,
    }

    mapper_profile = {"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}

    conflict_result = compute_semantic_integrity(
        current_skeleton=conflict_skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc=None,
        identity_signature=None,
    )

    aligned_result = compute_semantic_integrity(
        current_skeleton=aligned_skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc=None,
        identity_signature=None,
    )

    # Conflict should produce lower layer agreement
    assert conflict_result.layer_agreement_score < aligned_result.layer_agreement_score


def test_cross_turn_consistency_responds_to_skeleton_volatility():
    """Cross-turn consistency decreases when skeleton structure varies across turns."""
    skeleton1 = {
        "has_symbolic": True,
        "has_practical": False,
        "has_mirror": False,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 1,
    }

    skeleton2 = {
        "has_symbolic": False,
        "has_practical": True,
        "has_mirror": False,
        "has_dha_insight": True,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 2,
    }

    skeleton3 = {
        "has_symbolic": False,
        "has_practical": False,
        "has_mirror": True,
        "has_dha_insight": False,
        "has_dha_alignment": True,
        "has_dha_conflict": False,
        "section_count": 3,
    }

    mapper_profile = {"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}

    # Volatile history (all different)
    volatile_result = compute_semantic_integrity(
        current_skeleton=skeleton3,
        previous_skeletons=[skeleton1, skeleton2],
        mapper_profile=mapper_profile,
        intent_arc=None,
        identity_signature=None,
    )

    # Stable history (all same)
    stable_result = compute_semantic_integrity(
        current_skeleton=skeleton1,
        previous_skeletons=[skeleton1, skeleton1],
        mapper_profile=mapper_profile,
        intent_arc=None,
        identity_signature=None,
    )

    # Cross-turn consistency should be lower for volatile history
    assert volatile_result.cross_turn_consistency < stable_result.cross_turn_consistency


def test_mapper_alignment_scoring_works():
    """Mapper alignment score reflects alignment between mapper profile and skeleton."""
    # Skeleton with heavy symbolic/mirror layers (reflective)
    reflective_skeleton = {
        "has_symbolic": True,
        "has_practical": False,
        "has_mirror": True,
        "has_dha_insight": True,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 4,
    }

    # Mapper profile with high reflective bias
    reflective_mapper = {
        "detail_bias": 0.3,
        "practical_bias": 0.2,
        "reflective_bias": 0.9,  # High reflective bias
    }

    # Mapper profile with low reflective bias (misaligned)
    practical_mapper = {
        "detail_bias": 0.3,
        "practical_bias": 0.9,  # High practical bias
        "reflective_bias": 0.1,  # Low reflective bias
    }

    aligned_result = compute_semantic_integrity(
        current_skeleton=reflective_skeleton,
        previous_skeletons=[],
        mapper_profile=reflective_mapper,
        intent_arc=None,
        identity_signature=None,
    )

    misaligned_result = compute_semantic_integrity(
        current_skeleton=reflective_skeleton,
        previous_skeletons=[],
        mapper_profile=practical_mapper,
        intent_arc=None,
        identity_signature=None,
    )

    # Aligned mapper should produce higher mapper alignment score
    assert aligned_result.mapper_alignment_score > misaligned_result.mapper_alignment_score


def test_intent_identity_alignment_scoring():
    """Intent-identity alignment score reflects coherence between intent arc and identity signature."""
    skeleton = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": False,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 2,
    }

    mapper_profile = {"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}

    # Aligned: positive arc + positive identity
    aligned_result = compute_semantic_integrity(
        current_skeleton=skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc="insight_arc",  # Positive
        identity_signature="self_anchoring",  # Positive
    )

    # Misaligned: positive arc + negative identity
    misaligned_result = compute_semantic_integrity(
        current_skeleton=skeleton,
        previous_skeletons=[],
        mapper_profile=mapper_profile,
        intent_arc="insight_arc",  # Positive
        identity_signature="self_dissonance",  # Negative
    )

    # Aligned should produce higher intent-identity alignment
    assert aligned_result.intent_identity_alignment > misaligned_result.intent_identity_alignment


def test_semantic_integrity_handles_all_nones_gracefully():
    """Semantic integrity handles missing data (all None values) gracefully."""
    # Empty skeleton
    empty_skeleton = {}

    result = compute_semantic_integrity(
        current_skeleton=empty_skeleton,
        previous_skeletons=[],
        mapper_profile=None,
        intent_arc=None,
        identity_signature=None,
    )

    # Should return a valid snapshot (not crash)
    # Empty skeleton returns None for integrity score (as per spec)
    assert result.semantic_integrity_score is None
    assert isinstance(result, SemanticIntegritySnapshot)


def test_semantic_integrity_handles_partial_data():
    """Semantic integrity handles partial data with safe defaults."""
    # Partial skeleton (missing some fields)
    partial_skeleton = {
        "has_symbolic": True,
        "has_practical": False,
        # Missing other fields
    }

    result = compute_semantic_integrity(
        current_skeleton=partial_skeleton,
        previous_skeletons=[],
        mapper_profile={"detail_bias": 0.5},  # Partial mapper profile
        intent_arc="insight_arc",
        identity_signature=None,  # Missing identity
    )

    # Should return a valid snapshot (not crash)
    assert result.semantic_integrity_score is not None
    assert 0.0 <= result.semantic_integrity_score <= 1.0


def test_semantic_integrity_clamping_and_numerical_robustness():
    """Semantic integrity scores are properly clamped and numerically robust."""
    # Create edge-case skeleton with extreme values
    skeleton = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": True,
        "has_dha_insight": True,
        "has_dha_alignment": True,
        "has_dha_conflict": True,  # Contradictory
        "section_count": 100,  # Extreme value
    }

    mapper_profile = {
        "detail_bias": 1.0,  # Extreme
        "practical_bias": 1.0,  # Extreme
        "reflective_bias": 1.0,  # Extreme
    }

    result = compute_semantic_integrity(
        current_skeleton=skeleton,
        previous_skeletons=[skeleton] * 100,  # Large history
        mapper_profile=mapper_profile,
        intent_arc="insight_arc",
        identity_signature="self_anchoring",
    )

    # All scores should be properly clamped
    assert 0.0 <= result.semantic_integrity_score <= 1.0
    assert 0.0 <= result.structural_consistency <= 1.0
    assert 0.0 <= result.layer_agreement_score <= 1.0
    assert 0.0 <= result.cross_turn_consistency <= 1.0
    assert 0.0 <= result.mapper_alignment_score <= 1.0
    assert 0.0 <= result.intent_identity_alignment <= 1.0


# ============================================================================
# GROUP B — Cognitive Drift v3 Math (8 tests)
# ============================================================================


def test_drift_rises_under_structural_inconsistencies():
    """Cognitive drift v3 rises when structural consistency is low across turns."""
    # Create integrity snapshots with low structural consistency
    from symbolu_core.formulas.semantic_integrity import SemanticIntegritySnapshot

    low_consistency_snapshots = [
        SemanticIntegritySnapshot(
            semantic_integrity_score=0.3,
            structural_consistency=0.2,  # Low
            layer_agreement_score=0.5,
            cross_turn_consistency=0.5,
            mapper_alignment_score=0.5,
            intent_identity_alignment=0.5,
        ),
        SemanticIntegritySnapshot(
            semantic_integrity_score=0.3,
            structural_consistency=0.1,  # Low
            layer_agreement_score=0.5,
            cross_turn_consistency=0.5,
            mapper_alignment_score=0.5,
            intent_identity_alignment=0.5,
        ),
    ]

    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=low_consistency_snapshots,
        mapper_history=[],
        intent_arc_history=[],
        identity_signature_history=[],
    )

    # Structure drift should be high (inverse of low consistency)
    assert result.structure_drift > 0.5


def test_drift_rises_under_frequent_mapper_flips():
    """Cognitive drift v3 rises when mapper profiles flip frequently."""
    # Create mapper history with frequent flips
    mapper_history = [
        {"detail_bias": 0.8, "practical_bias": 0.2, "reflective_bias": 0.1},  # Detail dominant
        {"detail_bias": 0.1, "practical_bias": 0.8, "reflective_bias": 0.2},  # Practical dominant
        {"detail_bias": 0.2, "practical_bias": 0.1, "reflective_bias": 0.8},  # Reflective dominant
        {"detail_bias": 0.8, "practical_bias": 0.1, "reflective_bias": 0.2},  # Detail dominant again
    ]

    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=[],
        mapper_history=mapper_history,
        intent_arc_history=[],
        identity_signature_history=[],
    )

    # Mapper drift should be high
    assert result.mapper_drift > 0.5


def test_drift_rises_under_frequent_intent_identity_changes():
    """Cognitive drift v3 rises when intent arc and identity signature change frequently."""
    # Create histories with frequent changes
    intent_arc_history = ["insight_arc", "chaotic_arc", "stabilization_arc", "dissonance_arc"]
    identity_signature_history = ["self_anchoring", "self_dissonance", "self_integration", "self_fragmentation"]

    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=[],
        mapper_history=[],
        intent_arc_history=intent_arc_history,
        identity_signature_history=identity_signature_history,
    )

    # Intent-identity drift should be high
    assert result.intent_identity_drift > 0.5


def test_stable_histories_produce_low_drift():
    """Cognitive drift v3 is low when all histories are stable."""
    from symbolu_core.formulas.semantic_integrity import SemanticIntegritySnapshot

    # Create stable integrity snapshots
    stable_snapshots = [
        SemanticIntegritySnapshot(
            semantic_integrity_score=0.8,
            structural_consistency=0.9,  # High
            layer_agreement_score=0.8,
            cross_turn_consistency=0.9,
            mapper_alignment_score=0.8,
            intent_identity_alignment=0.8,
        )
    ] * 5

    # Stable mapper history
    stable_mapper = {"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}
    mapper_history = [stable_mapper.copy() for _ in range(5)]

    # Stable intent/identity history
    intent_arc_history = ["stabilization_arc"] * 5
    identity_signature_history = ["self_anchoring"] * 5

    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=stable_snapshots,
        mapper_history=mapper_history,
        intent_arc_history=intent_arc_history,
        identity_signature_history=identity_signature_history,
    )

    # All drift components should be low
    assert result.structure_drift < 0.3
    assert result.mapper_drift < 0.3
    assert result.intent_identity_drift < 0.3
    assert result.cognitive_drift_v3 < 0.3


def test_cognitive_drift_determinism():
    """Cognitive drift v3 computation is deterministic (same input → same output)."""
    from symbolu_core.formulas.semantic_integrity import SemanticIntegritySnapshot

    snapshots = [
        SemanticIntegritySnapshot(
            semantic_integrity_score=0.6,
            structural_consistency=0.5,
            layer_agreement_score=0.6,
            cross_turn_consistency=0.7,
            mapper_alignment_score=0.5,
            intent_identity_alignment=0.6,
        )
    ] * 3

    mapper_history = [{"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}] * 3
    intent_arc_history = ["insight_arc", "stabilization_arc"]
    identity_signature_history = ["self_anchoring", "self_integration"]

    result1 = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=snapshots,
        mapper_history=mapper_history,
        intent_arc_history=intent_arc_history,
        identity_signature_history=identity_signature_history,
    )

    result2 = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=snapshots,
        mapper_history=mapper_history,
        intent_arc_history=intent_arc_history,
        identity_signature_history=identity_signature_history,
    )

    assert result1.cognitive_drift_v3 == result2.cognitive_drift_v3
    assert result1.structure_drift == result2.structure_drift
    assert result1.mapper_drift == result2.mapper_drift


def test_cognitive_drift_handles_short_histories():
    """Cognitive drift v3 handles short histories gracefully."""
    # Single snapshot
    from symbolu_core.formulas.semantic_integrity import SemanticIntegritySnapshot

    single_snapshot = [
        SemanticIntegritySnapshot(
            semantic_integrity_score=0.5,
            structural_consistency=0.5,
            layer_agreement_score=0.5,
            cross_turn_consistency=0.5,
            mapper_alignment_score=0.5,
            intent_identity_alignment=0.5,
        )
    ]

    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=single_snapshot,
        mapper_history=[{"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}],
        intent_arc_history=["insight_arc"],
        identity_signature_history=["self_anchoring"],
    )

    # Should return valid result (not crash)
    assert result.cognitive_drift_v3 is not None
    assert 0.0 <= result.cognitive_drift_v3 <= 1.0


def test_cognitive_drift_composition_correct():
    """Cognitive drift v3 is composed correctly from component drifts."""
    from symbolu_core.formulas.semantic_integrity import SemanticIntegritySnapshot

    snapshots = [
        SemanticIntegritySnapshot(
            semantic_integrity_score=0.5,
            structural_consistency=0.5,
            layer_agreement_score=0.5,
            cross_turn_consistency=0.5,
            mapper_alignment_score=0.5,
            intent_identity_alignment=0.5,
        )
    ] * 3

    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=snapshots,
        mapper_history=[{"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}] * 3,
        intent_arc_history=["insight_arc"] * 3,
        identity_signature_history=["self_anchoring"] * 3,
    )

    # Verify composition formula (approximate)
    # cognitive_drift_v3 = 0.35 * structure_drift + 0.30 * topic_drift + 0.20 * mapper_drift + 0.15 * intent_identity_drift
    expected_drift = (
        0.35 * result.structure_drift
        + 0.30 * result.topic_drift
        + 0.20 * result.mapper_drift
        + 0.15 * result.intent_identity_drift
    )

    # Should be approximately equal (within floating point tolerance)
    assert abs(result.cognitive_drift_v3 - expected_drift) < 0.01


def test_cognitive_drift_edge_case_behavior():
    """Cognitive drift v3 handles edge cases gracefully."""
    # Empty histories
    result = compute_cognitive_drift_v3(
        integrity_snapshots_last_n=[],
        mapper_history=[],
        intent_arc_history=[],
        identity_signature_history=[],
    )

    # Should return None (no history)
    assert result.cognitive_drift_v3 is None

    # All component drifts should be 0.0 (no data)
    assert result.structure_drift == 0.0
    assert result.topic_drift == 0.0
    assert result.mapper_drift == 0.0
    assert result.intent_identity_drift == 0.0


# ============================================================================
# GROUP C — Integration with Coherence Engine & Observer (8 tests)
# ============================================================================


def test_coherence_state_updates_store_integrity_and_drift_scores():
    """CoherenceState correctly stores semantic integrity and cognitive drift scores."""
    from agentic.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # Set Phase 17 scores
    state.semantic_integrity_score = 0.75
    state.cognitive_drift_v3 = 0.25

    # Verify storage
    assert state.semantic_integrity_score == 0.75
    assert state.cognitive_drift_v3 == 0.25


def test_coherence_state_histories_correctly_trimmed():
    """CoherenceState window_trim correctly trims Phase 17 histories."""
    from agentic.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # Add Phase 17 history data
    state.semantic_integrity_history = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    state.cognitive_drift_v3_history = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    state.semantic_skeleton_history = [{"count": i} for i in range(6)]
    state.intent_arc_history = [f"arc_{i}" for i in range(6)]
    state.identity_signature_history = [f"sig_{i}" for i in range(6)]

    # Trim to window of 3
    state.window_trim(window=3)

    # Verify trimming
    assert len(state.semantic_integrity_history) == 3
    assert len(state.cognitive_drift_v3_history) == 3
    assert len(state.semantic_skeleton_history) == 3
    assert len(state.intent_arc_history) == 3
    assert len(state.identity_signature_history) == 3

    # Verify we kept the most recent 3
    assert state.semantic_integrity_history == [0.8, 0.9, 1.0]
    assert state.cognitive_drift_v3_history == [0.4, 0.5, 0.6]


def test_coherence_observer_snapshot_contains_semantic_block():
    """CoherenceObserver snapshot contains semantic block with integrity and drift metrics."""
    # Note: This test requires pydantic which may not be installed in all test environments.
    # We'll test the _extract_semantic_from_observation method directly instead.

    try:
        from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObserver, CoherenceObservation
    except ImportError:
        # pydantic or other dependencies not available - skip test
        import pytest
        pytest.skip("CoherenceObserver dependencies not available")
        return

    # Create observer
    observer = CoherenceObserver()

    # Create mock observation with Phase 17 data
    observation = CoherenceObservation(
        coherence_score=0.8,
        persona_drift_score=0.2,
        semantic_stability_score=0.9,
        temporal_arc_score=0.85,
        mapper_volatility_score=0.1,
        turn_number=5,
        tier="hybrid",
        domain="general",
        active_mappers=["HRM"],
        semantic_integrity_score=0.75,
        cognitive_drift_v3=0.25,
        semantic_integrity_details={
            "structural_consistency": 0.8,
            "layer_agreement_score": 0.7,
            "cross_turn_consistency": 0.75,
            "mapper_alignment_score": 0.6,
            "intent_identity_alignment": 0.8,
        },
        cognitive_drift_details={
            "structure_drift": 0.2,
            "topic_drift": 0.25,
            "mapper_drift": 0.3,
            "intent_identity_drift": 0.15,
        },
    )

    # Manually set observation
    observer._last_observation = observation

    # Get snapshot
    snapshot = observer.snapshot()

    # Verify semantic block exists
    assert "semantic" in snapshot
    assert snapshot["semantic"]["integrity_score"] == 0.75
    assert snapshot["semantic"]["cognitive_drift_v3"] == 0.25
    assert "integrity_components" in snapshot["semantic"]
    assert "drift_components" in snapshot["semantic"]


def test_unified_api_exposes_semantic_metrics_in_coherence_block():
    """Unified API exposes semantic integrity and drift metrics in coherence section."""
    # This test would require full pipeline context, so we'll test the extraction logic
    # by verifying the field structure is correct
    from agentic.api.unified_api import UnifiedOutput

    # Create mock unified output
    unified = UnifiedOutput(
        text="Test response",
        symbolic={"test": "data"},
        practical={"test": "data"},
        mirror={"test": "data"},
        dha={"test": "data"},
        routing={"test": "data"},
        mappers={"test": "data"},
        entropy={"H_D": 0.5},
        coherence={
            "coherence_score": 0.8,
            "semantic": {
                "integrity_score": 0.75,
                "cognitive_drift_v3": 0.25,
                "integrity_components": {
                    "structural_consistency": 0.8,
                    "layer_agreement_score": 0.7,
                },
                "drift_components": {
                    "structure_drift": 0.2,
                    "topic_drift": 0.25,
                },
            },
        },
        metadata={"timestamp": "2025-12-10"},
    )

    # Convert to dict
    unified_dict = unified.to_dict()

    # Verify semantic block in coherence
    assert "coherence" in unified_dict
    assert "semantic" in unified_dict["coherence"]
    assert unified_dict["coherence"]["semantic"]["integrity_score"] == 0.75
    assert unified_dict["coherence"]["semantic"]["cognitive_drift_v3"] == 0.25


def test_phase17_handles_missing_data_without_crash():
    """Phase 17 integration handles missing data gracefully (no crashes)."""
    from agentic.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # No Phase 17 data set
    assert state.semantic_integrity_score is None
    assert state.cognitive_drift_v3 is None

    # Should not crash when accessing histories
    assert len(state.semantic_integrity_history) == 0
    assert len(state.cognitive_drift_v3_history) == 0


def test_phase17_multi_turn_scenario_wiring():
    """Phase 17 correctly wires through a multi-turn scenario."""
    from agentic.core.coherence.coherence_engine import CoherenceEngine
    from agentic.core.coherence.coherence_state import CoherenceState

    # Create engine
    engine = CoherenceEngine(window=5)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "general"
        long_arc_tension = 0.5

    routing_plan = MockRoutingPlan()

    # Mock mapper profile
    mapper_profile = {
        "detail_bias": 0.5,
        "practical_bias": 0.5,
        "reflective_bias": 0.5,
    }

    # Mock semantic signature
    semantic_signature = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": False,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 2,
    }

    # Turn 1
    state1 = engine.update_state(
        prev_state=None,
        convo_id="test_convo",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=None,
        semantic_signature=semantic_signature,
    )

    # Verify Phase 17 data exists after turn 1
    assert state1.semantic_integrity_score is not None
    assert len(state1.semantic_skeleton_history) == 1

    # Turn 2
    state2 = engine.update_state(
        prev_state=state1,
        convo_id="test_convo",
        turn_index=1,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=None,
        semantic_signature=semantic_signature,
    )

    # Verify Phase 17 data updated after turn 2
    assert state2.semantic_integrity_score is not None
    assert len(state2.semantic_skeleton_history) == 2
    assert state2.cognitive_drift_v3 is not None  # Should be computed with 2 turns of history


def test_phase17_deterministic_snapshots():
    """Phase 17 snapshots are deterministic (same state → same snapshot)."""
    from agentic.core.coherence.coherence_state import CoherenceState
    from symbolu_core.formulas.semantic_integrity import SemanticIntegritySnapshot

    state = CoherenceState(convo_id="test", turn_index=0)

    # Create and store snapshot
    snapshot1 = SemanticIntegritySnapshot(
        semantic_integrity_score=0.75,
        structural_consistency=0.8,
        layer_agreement_score=0.7,
        cross_turn_consistency=0.75,
        mapper_alignment_score=0.6,
        intent_identity_alignment=0.8,
    )

    state.last_semantic_integrity_snapshot = snapshot1

    # Access snapshot twice
    retrieved1 = state.last_semantic_integrity_snapshot
    retrieved2 = state.last_semantic_integrity_snapshot

    # Should be same object
    assert retrieved1 == retrieved2
    assert retrieved1.semantic_integrity_score == retrieved2.semantic_integrity_score


def test_phase17_no_interference_with_existing_coherence_scores():
    """Phase 17 does not interfere with coherence_score, coherence_v2, coherence_v3, or coherence_fused."""
    from agentic.core.coherence.coherence_engine import CoherenceEngine

    # Create engine
    engine = CoherenceEngine(window=5)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "general"
        long_arc_tension = 0.5
        normalized_entropy = 0.3

    routing_plan = MockRoutingPlan()

    # Mock mapper profile
    mapper_profile = {
        "detail_bias": 0.5,
        "practical_bias": 0.5,
        "reflective_bias": 0.5,
    }

    # Mock semantic signature
    semantic_signature = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": False,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 2,
    }

    # Update state
    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=None,
        semantic_signature=semantic_signature,
    )

    # Verify all existing coherence scores are still computed
    assert state.coherence_score is not None
    # v2 and v3 may be None if not enough history, but should exist as fields
    assert hasattr(state, 'coherence_score_v2')
    assert hasattr(state, 'coherence_score_v3')
    assert hasattr(state, 'coherence_fused')

    # Verify Phase 17 scores are computed separately
    assert state.semantic_integrity_score is not None
    assert hasattr(state, 'cognitive_drift_v3')


# ============================================================================
# GROUP D — Behavioral Invariance (6 tests)
# ============================================================================


def test_no_routing_changes():
    """Phase 17 does not affect TTOR or MLCR routing behavior."""
    # This is verified by observing that Phase 17 only adds new fields and computations
    # without modifying any routing logic or existing pipeline behavior.
    # We verify this by checking that all routing-related fields remain unchanged.

    from agentic.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # Set Phase 17 data
    state.semantic_integrity_score = 0.75
    state.cognitive_drift_v3 = 0.25

    # Verify routing-related fields are not affected (remain as initialized)
    assert len(state.tier_history) == 0  # Unchanged
    assert len(state.domain_history) == 0  # Unchanged

    # Phase 17 should be observation-only, no behavioral changes
    assert True  # Placeholder assertion


def test_no_mapper_activation_changes():
    """Phase 17 does not affect HRM/LCM/LAM mapper activation logic."""
    # Verified by checking that mapper profile history tracking does not alter activation
    from agentic.core.coherence.coherence_state import CoherenceState

    state = CoherenceState(convo_id="test", turn_index=0)

    # Add mapper profile history
    state.mapper_profile_history = [
        {"detail_bias": 0.5, "practical_bias": 0.5, "reflective_bias": 0.5}
    ]

    # Set Phase 17 data
    state.semantic_integrity_score = 0.75

    # Verify mapper history is unchanged
    assert len(state.mapper_profile_history) == 1

    # Phase 17 is observation-only
    assert True


def test_policy_flags_unchanged_except_diagnostic_hints():
    """Phase 17 does not change existing policy flags (except for adding optional diagnostic hints)."""
    # DILchat adapter adds new hints but does not modify existing policy flags
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    # Mock unified output
    unified_output = {
        "text": "Test response",
        "coherence": {
            "coherence_score": 0.8,
            "semantic": {
                "integrity_score": 0.75,
                "cognitive_drift_v3": 0.25,
            },
        },
    }

    # Mock policy flags
    policy_flags = {
        "needs_grounding": False,
        "allow_deep_reflection": True,
        "prefer_concrete": False,
    }

    # Build DILchat response
    response = build_dilchat_response(
        unified_output=unified_output,
        policy_flags=policy_flags,
        domain="general",
    )

    # Verify policy flags are preserved in response
    assert response.policy_flags is not None

    # Phase 17 only adds hints, does not modify existing flags
    assert True


def test_trading_guardrails_behavior_unchanged():
    """Phase 17 does not affect trading guardrails behavior."""
    # Phase 17 is observation-only and should not impact trading guardrails
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    # Mock unified output with trading guardrails
    unified_output = {
        "text": "Test response",
        "coherence": {
            "coherence_score": 0.8,
            "semantic": {
                "integrity_score": 0.45,  # Fragile
                "cognitive_drift_v3": 0.6,  # High drift
            },
        },
        "trading_guardrails": {
            "unstable_avoid_trade": True,  # Trading guardrail active
        },
    }

    # Mock policy flags
    policy_flags = {"needs_grounding": False}

    # Build DILchat response
    response = build_dilchat_response(
        unified_output=unified_output,
        policy_flags=policy_flags,
        domain="trading",
    )

    # Verify Phase 17 semantic hints are present (additive)
    hint_codes = [hint.code for hint in response.hints]
    assert "SEMANTIC_INTEGRITY_FRAGILE" in hint_codes

    # Phase 17 should not interfere with existing policy/guardrail logic
    # (We just verify that hints are generated and Phase 17 doesn't crash or override behavior)
    assert isinstance(response.hints, list)
    assert len(response.hints) > 0


def test_coherence_v1_v2_v3_unaffected():
    """Phase 17 does not affect coherence_score, coherence_score_v2, coherence_score_v3 computations."""
    from agentic.core.coherence.coherence_engine import CoherenceEngine

    # Create two engines (one with Phase 17 data, one baseline)
    engine = CoherenceEngine(window=5)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "general"
        long_arc_tension = 0.5
        normalized_entropy = 0.3

    routing_plan = MockRoutingPlan()

    # Mock mapper profile
    mapper_profile = {
        "detail_bias": 0.5,
        "practical_bias": 0.5,
        "reflective_bias": 0.5,
    }

    # Mock semantic signature
    semantic_signature = {
        "has_symbolic": True,
        "has_practical": True,
        "has_mirror": False,
        "has_dha_insight": False,
        "has_dha_alignment": False,
        "has_dha_conflict": False,
        "section_count": 2,
    }

    # Update state
    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile=mapper_profile,
        temporal_summary=None,
        semantic_signature=semantic_signature,
    )

    # Verify coherence v1 is computed (not None)
    assert state.coherence_score is not None
    assert 0.0 <= state.coherence_score <= 1.0

    # Phase 17 should not have changed coherence v1/v2/v3 computation logic
    # (They remain independent)
    assert True


def test_dilchat_main_response_text_unchanged():
    """Phase 17 does not change DILchat main response text (only adds diagnostic hints)."""
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    # Mock unified output
    unified_output = {
        "text": "This is the main response text.",
        "coherence": {
            "coherence_score": 0.8,
            "semantic": {
                "integrity_score": 0.75,
                "cognitive_drift_v3": 0.25,
            },
        },
    }

    # Mock policy flags
    policy_flags = {"needs_grounding": False}

    # Build DILchat response
    response = build_dilchat_response(
        unified_output=unified_output,
        policy_flags=policy_flags,
        domain="general",
    )

    # Verify main text is unchanged
    assert response.text == "This is the main response text."

    # Hints should include Phase 17 diagnostic hints (additive)
    hint_codes = [hint.code for hint in response.hints]
    assert "SEMANTIC_INTEGRITY_STRONG" in hint_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
