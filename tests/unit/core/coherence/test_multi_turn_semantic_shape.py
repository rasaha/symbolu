"""
Tests for Multi-turn Semantic Shape Coherence.

Validates:
- Semantic skeleton stability over time
- Mapper volatility penalties on coherence
- Temporal arc score rewards for recovery patterns
- Overall coherence score combining all metrics
"""

import pytest
from symbolu.core.coherence.semantic_skeleton import (
    build_semantic_signature,
    compute_semantic_stability,
)
from symbolu.core.coherence.temporal_arc_tracer import (
    compute_temporal_arc_score,
    compute_tension_trend,
)
from symbolu.core.coherence.coherence_engine import CoherenceEngine


class TestSemanticSkeleton:
    """Test semantic skeleton construction and stability."""

    def test_build_semantic_signature_fusion_layers(self):
        """Test semantic signature captures fusion layers."""
        fusion_output = {
            "layers": {
                "symbolic": {"content": "deep meaning"},
                "practical": {"content": "concrete steps"},
                "mirror": None,
            },
            "sections": ["intro", "body", "conclusion"],
        }
        dha_output = {}

        signature = build_semantic_signature(fusion_output, dha_output)

        assert signature["has_symbolic"] is True
        assert signature["has_practical"] is True
        assert signature["has_mirror"] is False
        assert signature["section_count"] == 3

    def test_build_semantic_signature_dha_markers(self):
        """Test semantic signature captures DHA markers."""
        fusion_output = {}
        dha_output = {
            "insight": "key realization",
            "alignment_marker": True,
            "conflict_marker": False,
            "sections": ["insight", "guidance"],
        }

        signature = build_semantic_signature(fusion_output, dha_output)

        assert signature["has_dha_insight"] is True
        assert signature["has_dha_alignment"] is True
        assert signature["has_dha_conflict"] is False
        assert signature["section_count"] == 2

    def test_build_semantic_signature_combined(self):
        """Test semantic signature with both fusion and DHA."""
        fusion_output = {
            "layers": {"symbolic": {"content": "meaning"}},
            "sections": ["part1"],
        }
        dha_output = {
            "insight": "realization",
            "sections": ["part2"],
        }

        signature = build_semantic_signature(fusion_output, dha_output)

        assert signature["has_symbolic"] is True
        assert signature["has_dha_insight"] is True
        assert signature["section_count"] == 2  # Combined from both

    def test_semantic_stability_perfect_stability(self):
        """Test that identical skeletons result in perfect stability."""
        skeleton_history = [
            {
                "has_symbolic": True,
                "has_practical": True,
                "has_mirror": False,
                "has_dha_insight": True,
                "has_dha_alignment": False,
                "has_dha_conflict": False,
            }
        ] * 5

        stability = compute_semantic_stability(skeleton_history)

        assert stability == 1.0

    def test_semantic_stability_total_instability(self):
        """Test that all flags flipping results in zero stability."""
        skeleton_history = [
            {
                "has_symbolic": True,
                "has_practical": False,
                "has_mirror": True,
                "has_dha_insight": False,
                "has_dha_alignment": True,
                "has_dha_conflict": False,
            },
            {
                "has_symbolic": False,
                "has_practical": True,
                "has_mirror": False,
                "has_dha_insight": True,
                "has_dha_alignment": False,
                "has_dha_conflict": True,
            },
        ]

        stability = compute_semantic_stability(skeleton_history)

        # All 6 flags flipped = 0 stability
        assert stability == 0.0

    def test_semantic_stability_improves_over_time(self):
        """Test that stability improves as structure becomes consistent."""
        # Start with oscillations, then stabilize
        skeleton_history_early = [
            {"has_symbolic": True, "has_practical": False, "has_mirror": False,
             "has_dha_insight": True, "has_dha_alignment": False, "has_dha_conflict": False},
            {"has_symbolic": False, "has_practical": True, "has_mirror": True,
             "has_dha_insight": False, "has_dha_alignment": True, "has_dha_conflict": False},
            {"has_symbolic": True, "has_practical": False, "has_mirror": False,
             "has_dha_insight": True, "has_dha_alignment": False, "has_dha_conflict": False},
        ]

        skeleton_history_late = [
            {"has_symbolic": True, "has_practical": True, "has_mirror": False,
             "has_dha_insight": True, "has_dha_alignment": True, "has_dha_conflict": False},
            {"has_symbolic": True, "has_practical": True, "has_mirror": False,
             "has_dha_insight": True, "has_dha_alignment": True, "has_dha_conflict": False},
            {"has_symbolic": True, "has_practical": True, "has_mirror": False,
             "has_dha_insight": True, "has_dha_alignment": True, "has_dha_conflict": False},
        ]

        stability_early = compute_semantic_stability(skeleton_history_early)
        stability_late = compute_semantic_stability(skeleton_history_late)

        # Later stability should be higher (perfect in this case)
        assert stability_late > stability_early
        assert stability_late == 1.0

    def test_semantic_stability_empty_history(self):
        """Test that empty history returns perfect stability."""
        stability = compute_semantic_stability([])

        assert stability == 1.0

    def test_semantic_stability_single_turn(self):
        """Test that single turn returns perfect stability."""
        skeleton_history = [
            {"has_symbolic": True, "has_practical": False, "has_mirror": False,
             "has_dha_insight": True, "has_dha_alignment": False, "has_dha_conflict": False}
        ]

        stability = compute_semantic_stability(skeleton_history)

        assert stability == 1.0


class TestTemporalArcTracer:
    """Test temporal arc scoring."""

    def test_temporal_arc_high_with_recovery_patterns(self):
        """Test that recovery patterns result in high temporal arc score."""
        temporal_flags_history = [
            {"recovery_trajectory": True, "resilience_pattern": True,
             "tension_corridor": False, "chronic_stress": False},
            {"recovery_trajectory": True, "resilience_pattern": True,
             "tension_corridor": False, "chronic_stress": False},
            {"recovery_trajectory": True, "resilience_pattern": False,
             "tension_corridor": False, "chronic_stress": False},
        ]
        tension_history = [0.3, 0.25, 0.2]  # Decreasing tension

        score = compute_temporal_arc_score(temporal_flags_history, tension_history)

        # Recovery patterns should boost score
        assert score > 0.5

    def test_temporal_arc_low_with_chronic_stress(self):
        """Test that chronic stress and tension corridor reduce arc score."""
        temporal_flags_history = [
            {"recovery_trajectory": False, "resilience_pattern": False,
             "tension_corridor": True, "chronic_stress": True},
            {"recovery_trajectory": False, "resilience_pattern": False,
             "tension_corridor": True, "chronic_stress": True},
            {"recovery_trajectory": False, "resilience_pattern": False,
             "tension_corridor": True, "chronic_stress": True},
        ]
        tension_history = [0.8, 0.85, 0.9]  # Increasing tension

        score = compute_temporal_arc_score(temporal_flags_history, tension_history)

        # Negative patterns should reduce score
        assert score < 0.5

    def test_temporal_arc_smooth_tension(self):
        """Test that smooth tension history increases arc score."""
        temporal_flags_history = [
            {"recovery_trajectory": False, "resilience_pattern": False,
             "tension_corridor": False, "chronic_stress": False},
        ] * 5
        tension_history = [0.5, 0.5, 0.5, 0.5, 0.5]  # Perfectly smooth

        score = compute_temporal_arc_score(temporal_flags_history, tension_history)

        # Smooth tension should contribute positively
        assert score >= 0.4

    def test_temporal_arc_volatile_tension(self):
        """Test that volatile tension reduces arc score."""
        temporal_flags_history = [
            {"recovery_trajectory": False, "resilience_pattern": False,
             "tension_corridor": False, "chronic_stress": False},
        ] * 5
        tension_history = [0.1, 0.9, 0.2, 0.8, 0.3]  # Wild oscillations

        score = compute_temporal_arc_score(temporal_flags_history, tension_history)

        # Volatile tension should reduce score
        assert score < 0.5

    def test_temporal_arc_empty_history(self):
        """Test that empty history returns neutral score."""
        score = compute_temporal_arc_score([], [])

        assert score == 0.5  # Neutral

    def test_tension_trend_detection(self):
        """Test tension trend detection."""
        increasing = [0.2, 0.3, 0.4, 0.5, 0.6]
        decreasing = [0.6, 0.5, 0.4, 0.3, 0.2]
        stable = [0.5, 0.5, 0.5, 0.5, 0.5]

        assert compute_tension_trend(increasing) == "increasing"
        assert compute_tension_trend(decreasing) == "decreasing"
        assert compute_tension_trend(stable) == "stable"


class TestMapperVolatilityPenalty:
    """Test that mapper volatility penalizes coherence."""

    def test_mapper_volatility_penalizes_coherence(self):
        """Test that rapid mapper changes reduce coherence score."""
        engine = CoherenceEngine(window=10)

        # Scenario A: Stable mapper configuration
        state_stable = None
        for i in range(6):
            from symbolu.core.coherence.tests.test_coherence_state import MockRoutingPlan
            routing_plan = MockRoutingPlan(tier="hybrid", domain="task", tension=0.5)
            mapper_profile = {
                "resolution_level": "medium",
                "arc_mode": "none",
                "detail_bias": 0.5,
                "practical_bias": 0.5,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": 5,
                "bhava_direction": "stable",
                "smi": 0.5,
                "flags": {"recovery_trajectory": True},
            }
            semantic_sig = {"has_symbolic": True}

            state_stable = engine.update_state(
                prev_state=state_stable,
                convo_id="test_stable",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # Scenario B: Volatile mapper configuration
        state_volatile = None
        for i in range(6):
            from symbolu.core.coherence.tests.test_coherence_state import MockRoutingPlan
            routing_plan = MockRoutingPlan(tier="hybrid", domain="task", tension=0.5)
            mapper_profile = {
                "resolution_level": ["low", "high", "medium"][i % 3],
                "arc_mode": ["none", "identity", "temporal"][i % 3],
                "detail_bias": float(i % 10) / 10.0,
                "practical_bias": float((9 - i) % 10) / 10.0,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": 5,
                "bhava_direction": "stable",
                "smi": 0.5,
                "flags": {"recovery_trajectory": True},
            }
            semantic_sig = {"has_symbolic": True}

            state_volatile = engine.update_state(
                prev_state=state_volatile,
                convo_id="test_volatile",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # Volatile mapper should have higher volatility score
        assert state_volatile.mapper_volatility_score > state_stable.mapper_volatility_score

        # Volatile mapper should have lower overall coherence
        assert state_volatile.coherence_score < state_stable.coherence_score


class TestOverallCoherence:
    """Test overall coherence score combining all metrics."""

    def test_overall_coherence_combines_all_metrics(self):
        """Test that coherence combines semantic, temporal, persona, and mapper metrics."""
        engine = CoherenceEngine(window=10)

        # Scenario A: High coherence (stable, recovery, low drift)
        state_high = None
        for i in range(6):
            from symbolu.core.coherence.tests.test_coherence_state import MockRoutingPlan
            routing_plan = MockRoutingPlan(tier="hybrid", domain="task", tension=0.4)
            mapper_profile = {
                "resolution_level": "medium",
                "arc_mode": "none",
                "detail_bias": 0.5,
                "practical_bias": 0.5,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": 5,
                "bhava_direction": "stable",
                "smi": 0.6,
                "flags": {
                    "recovery_trajectory": True,
                    "resilience_pattern": True,
                    "tension_corridor": False,
                    "chronic_stress": False,
                },
            }
            semantic_sig = {
                "has_symbolic": True,
                "has_practical": True,
                "has_mirror": False,
                "has_dha_insight": True,
                "has_dha_alignment": True,
                "has_dha_conflict": False,
            }

            state_high = engine.update_state(
                prev_state=state_high,
                convo_id="test_high",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # Scenario B: Low coherence (unstable, chronic stress, high drift)
        state_low = None
        domains = ["task", "therapy", "finance", "identity", "spiritual", "task"]
        for i in range(6):
            from symbolu.core.coherence.tests.test_coherence_state import MockRoutingPlan
            routing_plan = MockRoutingPlan(tier="hybrid", domain=domains[i], tension=0.8)
            mapper_profile = {
                "resolution_level": ["low", "high", "medium"][i % 3],
                "arc_mode": ["none", "identity", "temporal"][i % 3],
                "detail_bias": float(i % 10) / 10.0,
                "practical_bias": float((9 - i) % 10) / 10.0,
                "reflective_bias": 0.5,
            }
            temporal_summary = {
                "bhava_id": i * 2,  # Big jumps
                "bhava_direction": "upward" if i % 2 == 0 else "downward",
                "smi": 0.3,
                "flags": {
                    "recovery_trajectory": False,
                    "resilience_pattern": False,
                    "tension_corridor": True,
                    "chronic_stress": True,
                },
            }
            semantic_sig = {
                "has_symbolic": i % 2 == 0,
                "has_practical": i % 3 == 0,
                "has_mirror": i % 2 == 1,
                "has_dha_insight": i % 3 == 1,
                "has_dha_alignment": False,
                "has_dha_conflict": i % 2 == 0,
            }

            state_low = engine.update_state(
                prev_state=state_low,
                convo_id="test_low",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_sig,
            )

        # High coherence scenario should score significantly higher
        assert state_high.coherence_score > state_low.coherence_score

        # Verify component scores are as expected
        assert state_high.persona_drift_score < state_low.persona_drift_score
        assert state_high.temporal_arc_score > state_low.temporal_arc_score
        assert state_high.mapper_volatility_score < state_low.mapper_volatility_score

        # Verify bounds
        assert 0.0 <= state_high.coherence_score <= 1.0
        assert 0.0 <= state_low.coherence_score <= 1.0

    def test_coherence_score_formula_weights(self):
        """Test that coherence score follows documented formula."""
        # Create a controlled state
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=5)
        state.semantic_stability_score = 0.8
        state.temporal_arc_score = 0.6
        state.persona_drift_score = 0.3
        state.mapper_volatility_score = 0.2

        # Manual calculation
        expected_coherence = (
            0.30 * 0.8  # semantic_stability
            + 0.25 * 0.6  # temporal_arc
            + 0.25 * (1.0 - 0.3)  # 1 - persona_drift
            + 0.20 * (1.0 - 0.2)  # 1 - mapper_volatility
        )

        # Test via engine
        engine = CoherenceEngine(window=10)
        actual_coherence = engine._compute_overall_coherence(state)

        assert abs(actual_coherence - expected_coherence) < 0.001
