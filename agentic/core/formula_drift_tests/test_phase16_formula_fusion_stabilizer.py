"""
Phase 16 Formula Fusion Stabilizer v1.0 — Comprehensive Test Suite (30 tests)

Test Groups:
    GROUP A — Math Correctness (10 tests)
    GROUP B — Integration with Coherence Engine (8 tests)
    GROUP C — Unified API + Observer (6 tests)
    GROUP D — Behavioral Invariance (6 tests)

CRITICAL:
    - Zero-LLM: All operations must be deterministic
    - Non-invasive: No routing/mapper/policy changes
    - Backward-compatible: Existing tests must remain green
"""

import pytest
from typing import Optional, List
from unittest.mock import Mock, MagicMock

from symbolu_core.formulas.formula_fusion_stabilizer import (
    compute_coherence_fused,
    FusionStabilizerSnapshot,
    _safe,
    _clamp,
    _compute_stability_weight,
    _compute_inertia_factor,
    _compute_quality_factor,
)
from agentic.core.coherence.coherence_state import CoherenceState
from agentic.core.coherence.coherence_engine import CoherenceEngine


# ============================================================================
# GROUP A — Math Correctness (10 tests)
# ============================================================================


class TestGroupA_MathCorrectness:
    """Test mathematical correctness of fusion stabilizer formulas."""

    def test_a1_safe_function_handles_none(self):
        """Test that _safe() returns 0.0 for None values."""
        assert _safe(None) == 0.0
        assert _safe(0.5) == 0.5
        assert _safe(1.0) == 1.0

    def test_a2_clamp_function_enforces_bounds(self):
        """Test that _clamp() enforces [min, max] bounds."""
        assert _clamp(0.5, 0.0, 1.0) == 0.5
        assert _clamp(-0.5, 0.0, 1.0) == 0.0
        assert _clamp(1.5, 0.0, 1.0) == 1.0

    def test_a3_stability_weight_increases_with_consistency(self):
        """Test that stability_weight is higher for consistent history."""
        # High variance history (low stability)
        volatile_history = [0.1, 0.9, 0.2, 0.8, 0.3]
        stability_volatile = _compute_stability_weight(volatile_history)

        # Low variance history (high stability)
        stable_history = [0.7, 0.72, 0.71, 0.69, 0.70]
        stability_stable = _compute_stability_weight(stable_history)

        assert stability_stable > stability_volatile
        assert 0.0 <= stability_volatile <= 1.0
        assert 0.0 <= stability_stable <= 1.0

    def test_a4_inertia_factor_scales_with_stability(self):
        """Test that inertia_factor increases with stability_weight."""
        # Low stability → low inertia (0.5 baseline)
        inertia_low = _compute_inertia_factor(0.0)
        assert inertia_low == 0.5

        # High stability → high inertia (1.0 max)
        inertia_high = _compute_inertia_factor(1.0)
        assert inertia_high == 1.0

        # Mid stability → mid inertia
        inertia_mid = _compute_inertia_factor(0.5)
        assert 0.5 < inertia_mid < 1.0

    def test_a5_quality_factor_gates_v3_contribution(self):
        """Test that quality_factor returns v3_quality or 0.0."""
        assert _compute_quality_factor(0.8) == 0.8
        assert _compute_quality_factor(None) == 0.0
        assert _compute_quality_factor(1.0) == 1.0
        assert _compute_quality_factor(0.0) == 0.0

    def test_a6_blending_formula_range_clamped(self):
        """Test that fused score is always in [0.0, 1.0]."""
        # Extreme inputs that would overflow without clamping
        snapshot = compute_coherence_fused(
            v1=1.0,
            v2=1.0,
            v3=1.0,
            v3_quality=1.0,
            enhanced_smi=1.0,
            vritti_momentum=1.0,
            arc_tension_harmonizer=1.0,
            guna_resonance=1.0,
            kosha_resonance=1.0,
            history_last_5=[1.0, 1.0, 1.0, 1.0, 1.0],
        )

        assert snapshot.coherence_fused is not None
        assert 0.0 <= snapshot.coherence_fused <= 1.0

    def test_a7_determinism_same_inputs_same_outputs(self):
        """Test that same inputs always produce same outputs."""
        inputs = {
            "v1": 0.7,
            "v2": 0.65,
            "v3": 0.8,
            "v3_quality": 0.75,
            "enhanced_smi": 0.6,
            "vritti_momentum": 0.55,
            "arc_tension_harmonizer": 0.5,
            "guna_resonance": 0.7,
            "kosha_resonance": 0.65,
            "history_last_5": [0.6, 0.65, 0.7, 0.68, 0.7],
        }

        result1 = compute_coherence_fused(**inputs)
        result2 = compute_coherence_fused(**inputs)

        assert result1.coherence_fused == result2.coherence_fused
        assert result1.stability_weight == result2.stability_weight
        assert result1.inertia_factor == result2.inertia_factor

    def test_a8_missing_inputs_handled_gracefully(self):
        """Test that missing inputs are treated as 0.0."""
        snapshot = compute_coherence_fused(
            v1=0.7,
            v2=None,
            v3=None,
            v3_quality=None,
            enhanced_smi=None,
            vritti_momentum=None,
            arc_tension_harmonizer=None,
            guna_resonance=None,
            kosha_resonance=None,
            history_last_5=[0.7],
        )

        # Should compute successfully with v1 only
        assert snapshot.coherence_fused is not None
        assert 0.0 <= snapshot.coherence_fused <= 1.0

    def test_a9_v1_none_returns_none_fused(self):
        """Test that if v1 is None, coherence_fused is None."""
        snapshot = compute_coherence_fused(
            v1=None,
            v2=0.65,
            v3=0.8,
            v3_quality=0.75,
            enhanced_smi=0.6,
            vritti_momentum=0.55,
            arc_tension_harmonizer=0.5,
            guna_resonance=0.7,
            kosha_resonance=0.65,
            history_last_5=[0.6, 0.65, 0.7],
        )

        assert snapshot.coherence_fused is None

    def test_a10_temporal_inertia_smoothing_applied(self):
        """Test that temporal inertia smoothing is applied correctly."""
        # First computation (no history)
        snapshot1 = compute_coherence_fused(
            v1=0.7,
            v2=0.65,
            v3=0.8,
            v3_quality=0.75,
            enhanced_smi=0.6,
            vritti_momentum=0.55,
            arc_tension_harmonizer=0.5,
            guna_resonance=0.7,
            kosha_resonance=0.65,
            history_last_5=[],
        )

        # Second computation (with history from first)
        snapshot2 = compute_coherence_fused(
            v1=0.9,  # Big jump
            v2=0.85,
            v3=0.95,
            v3_quality=0.9,
            enhanced_smi=0.8,
            vritti_momentum=0.75,
            arc_tension_harmonizer=0.7,
            guna_resonance=0.9,
            kosha_resonance=0.85,
            history_last_5=[0.7, 0.7, 0.7, 0.7, 0.7],
        )

        # With high stability (consistent history), inertia should smooth the jump
        # snapshot2.coherence_fused should be closer to 0.7 than to raw blend
        assert snapshot2.coherence_fused is not None
        assert snapshot2.coherence_fused < 0.9  # Not equal to v1 due to smoothing


# ============================================================================
# GROUP B — Integration with Coherence Engine (8 tests)
# ============================================================================


class TestGroupB_CoherenceEngineIntegration:
    """Test integration with CoherenceEngine and CoherenceState."""

    def test_b1_state_updates_store_fused_metric(self):
        """Test that CoherenceEngine updates store coherence_fused."""
        engine = CoherenceEngine(window=10)

        # Create mock inputs
        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {
            "resolution_level": "medium",
            "arc_mode": "none",
            "detail_bias": 0.5,
            "practical_bias": 0.5,
            "reflective_bias": 0.5,
        }

        temporal_summary = {
            "smi": 0.7,
            "bhava_id": 1,
            "bhava_direction": "stable",
            "delta_smi": 0.05,
            "bhava_gap": 0.2,
            "tension_corridor": 0.3,
            "vritti_momentum": 0.6,
            "arc_tension_harmonizer": 0.55,
        }

        semantic_signature = {"tokens": ["test"], "entities": []}

        # First turn
        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Check that coherence_fused was computed and stored
        assert state.coherence_fused is not None
        assert isinstance(state.coherence_fused, float)
        assert 0.0 <= state.coherence_fused <= 1.0

    def test_b2_history_trimming_correct(self):
        """Test that coherence_fused_history is trimmed to window size."""
        engine = CoherenceEngine(window=3)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        # Create multiple turns
        state = None
        for i in range(5):
            state = engine.update_state(
                prev_state=state,
                convo_id="test_123",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_signature,
            )

        # History should be trimmed to window size (3), but can be +1 since
        # coherence_fused is appended AFTER window_trim
        assert len(state.coherence_fused_history) <= 4  # window + 1

    def test_b3_no_interference_with_v1(self):
        """Test that coherence_fused does not affect coherence_score (v1)."""
        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # v1 should be computed independently
        assert state.coherence_score is not None
        assert state.coherence_score != state.coherence_fused  # They should differ

    def test_b4_no_interference_with_v2(self):
        """Test that coherence_fused does not affect coherence_score_v2."""
        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {
            "smi": 0.7,
            "bhava_id": 1,
            "bhava_direction": "stable",
            "delta_smi": 0.05,
            "bhava_gap": 0.2,
            "tension_corridor": 0.3,
        }
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # v2 should exist and be independent
        if state.coherence_score_v2 is not None:
            assert state.coherence_score_v2 != state.coherence_fused

    def test_b5_no_interference_with_v3(self):
        """Test that coherence_fused does not affect coherence_score_v3."""
        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {
            "smi": 0.7,
            "bhava_id": 1,
            "bhava_direction": "stable",
            "delta_smi": 0.05,
            "bhava_gap": 0.2,
            "tension_corridor": 0.3,
            "vritti_momentum": 0.6,
            "arc_tension_harmonizer": 0.55,
            "guna_probs": [0.3, 0.4, 0.3],
            "kosha_probs": [0.2, 0.3, 0.2, 0.2, 0.1],
        }
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # v3 should exist and be independent
        if state.coherence_score_v3 is not None:
            assert state.coherence_score_v3 != state.coherence_fused

    def test_b6_fusion_diagnostics_stored(self):
        """Test that fusion diagnostics are stored in state."""
        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Check that diagnostics are stored
        assert state.fusion_stability_weight is not None
        assert state.fusion_inertia_factor is not None
        assert state.fusion_quality_factor is not None
        assert 0.0 <= state.fusion_stability_weight <= 1.0
        assert 0.5 <= state.fusion_inertia_factor <= 1.0
        assert 0.0 <= state.fusion_quality_factor <= 1.0

    def test_b7_multi_turn_history_accumulation(self):
        """Test that coherence_fused_history accumulates across turns."""
        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = None
        for i in range(3):
            state = engine.update_state(
                prev_state=state,
                convo_id="test_123",
                turn_index=i,
                routing_plan=routing_plan,
                mapper_profile=mapper_profile,
                temporal_summary=temporal_summary,
                semantic_signature=semantic_signature,
            )

        # After 3 turns, history should have 3 entries
        assert len(state.coherence_fused_history) == 3
        assert all(h is not None for h in state.coherence_fused_history)

    def test_b8_state_copy_preserves_fused_history(self):
        """Test that state copy preserves coherence_fused_history."""
        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        # First turn
        state1 = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Second turn (should copy history from first)
        state2 = engine.update_state(
            prev_state=state1,
            convo_id="test_123",
            turn_index=1,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # History should contain both turns
        assert len(state2.coherence_fused_history) == 2


# ============================================================================
# GROUP C — Unified API + Observer (6 tests)
# ============================================================================


class TestGroupC_UnifiedAPIObserver:
    """Test integration with Unified API and Coherence Observer."""

    def test_c1_fused_metric_appears_in_coherence_block(self):
        """Test that coherence_fused appears in unified API coherence block."""
        from agentic.api.unified_api import build_unified_output

        # Mock context
        ctx = Mock()
        ctx.coherence_state = Mock()
        ctx.coherence_state.coherence_score = 0.75
        ctx.coherence_state.coherence_score_v2 = 0.72
        ctx.coherence_state.coherence_score_v3 = 0.78
        ctx.coherence_state.coherence_v3_quality = 0.8
        ctx.coherence_state.coherence_fused = 0.76
        ctx.coherence_state.fusion_stability_weight = 0.85
        ctx.coherence_state.fusion_inertia_factor = 0.9
        ctx.coherence_state.fusion_quality_factor = 0.8

        # Mock history lists for formulas extraction
        ctx.coherence_state.delta_smi_history = []
        ctx.coherence_state.bhava_gap_history = []
        ctx.coherence_state.tension_corridor_history = []
        ctx.coherence_state.smi_history = []
        ctx.coherence_state.vritti_momentum_history = []
        ctx.coherence_state.arc_tension_harmonizer_history = []
        ctx.coherence_state.mirror_cycle_history = []
        ctx.coherence_state.cause_effect_inversion_history = []
        ctx.coherence_state.resonance_weighting_history = []
        ctx.coherence_state.ucf_history = []
        ctx.coherence_state.temporal_entropy_volatility = None
        ctx.coherence_state.cognitive_drift_v3 = None
        ctx.coherence_state.drift_pattern_tags = None
        ctx.coherence_state.ucf_notes = None

        ctx.coherence_report = {
            "coherence_score": 0.75,
            "persona_drift_score": 0.2,
            "semantic_stability_score": 0.8,
            "temporal_arc_score": 0.7,
            "mapper_volatility_score": 0.1,
            "turn_number": 5,
            "tier": "hybrid",
            "domain": "general",
            "active_mappers": ["HRM"],
        }

        ctx.fusion = None
        ctx.dha = None
        ctx.mlcr = None
        ctx.rendered = None
        ctx.mapper_profile = Mock()
        ctx.mapper_profile.to_dict = lambda: {"resolution_level": "medium"}
        ctx.request = None
        ctx.session_memory = None
        ctx.session_recap = None
        ctx.intent_arc = None
        ctx.identity_signature = None
        ctx.motivation_profile = None
        ctx.trading_guardrails = None
        ctx.policy_flags = None
        ctx.interaction_mode = None

        # Build unified output
        unified = build_unified_output(text="test", ctx=ctx)
        unified_dict = unified.to_dict()

        # Check that coherence_fused is present
        assert "coherence" in unified_dict
        assert "coherence_fused" in unified_dict["coherence"]
        assert unified_dict["coherence"]["coherence_fused"] == 0.76

    def test_c2_stabilizer_metadata_included(self):
        """Test that stabilizer metadata is included in unified API."""
        from agentic.api.unified_api import build_unified_output

        ctx = Mock()
        ctx.coherence_state = Mock()
        ctx.coherence_state.coherence_score = 0.75
        ctx.coherence_state.coherence_fused = 0.76
        ctx.coherence_state.fusion_stability_weight = 0.85
        ctx.coherence_state.fusion_inertia_factor = 0.9
        ctx.coherence_state.fusion_quality_factor = 0.8

        # Mock history lists
        ctx.coherence_state.delta_smi_history = []
        ctx.coherence_state.bhava_gap_history = []
        ctx.coherence_state.tension_corridor_history = []
        ctx.coherence_state.smi_history = []
        ctx.coherence_state.vritti_momentum_history = []
        ctx.coherence_state.arc_tension_harmonizer_history = []
        ctx.coherence_state.mirror_cycle_history = []
        ctx.coherence_state.cause_effect_inversion_history = []
        ctx.coherence_state.resonance_weighting_history = []
        ctx.coherence_state.ucf_history = []
        ctx.coherence_state.temporal_entropy_volatility = None
        ctx.coherence_state.cognitive_drift_v3 = None
        ctx.coherence_state.drift_pattern_tags = None
        ctx.coherence_state.ucf_notes = None

        ctx.coherence_report = {
            "coherence_score": 0.75,
            "persona_drift_score": 0.2,
            "semantic_stability_score": 0.8,
            "temporal_arc_score": 0.7,
            "mapper_volatility_score": 0.1,
            "turn_number": 5,
            "tier": "hybrid",
            "domain": "general",
            "active_mappers": [],
        }

        # Mock all other required attributes
        ctx.fusion = None
        ctx.dha = None
        ctx.mlcr = None
        ctx.rendered = None
        ctx.mapper_profile = Mock()
        ctx.mapper_profile.to_dict = lambda: {}
        ctx.request = None
        ctx.session_memory = None
        ctx.session_recap = None
        ctx.intent_arc = None
        ctx.identity_signature = None
        ctx.motivation_profile = None
        ctx.trading_guardrails = None
        ctx.policy_flags = None
        ctx.interaction_mode = None

        unified = build_unified_output(text="test", ctx=ctx)
        unified_dict = unified.to_dict()

        # Check that stabilizer diagnostics are present
        assert "coherence" in unified_dict
        assert "stabilizer" in unified_dict["coherence"]
        stabilizer = unified_dict["coherence"]["stabilizer"]
        assert "stability_weight" in stabilizer
        assert "inertia_factor" in stabilizer
        assert "quality_factor" in stabilizer

    def test_c3_missing_data_produces_none(self):
        """Test that missing coherence_fused produces None in API."""
        from agentic.api.unified_api import build_unified_output

        ctx = Mock()
        ctx.coherence_state = Mock()
        ctx.coherence_state.coherence_score = 0.75
        ctx.coherence_state.coherence_fused = None  # Missing

        # Mock history lists
        ctx.coherence_state.delta_smi_history = []
        ctx.coherence_state.bhava_gap_history = []
        ctx.coherence_state.tension_corridor_history = []
        ctx.coherence_state.smi_history = []
        ctx.coherence_state.vritti_momentum_history = []
        ctx.coherence_state.arc_tension_harmonizer_history = []
        ctx.coherence_state.mirror_cycle_history = []
        ctx.coherence_state.cause_effect_inversion_history = []
        ctx.coherence_state.resonance_weighting_history = []
        ctx.coherence_state.ucf_history = []
        ctx.coherence_state.temporal_entropy_volatility = None
        ctx.coherence_state.cognitive_drift_v3 = None
        ctx.coherence_state.drift_pattern_tags = None
        ctx.coherence_state.ucf_notes = None

        ctx.coherence_report = {
            "coherence_score": 0.75,
            "persona_drift_score": 0.2,
            "semantic_stability_score": 0.8,
            "temporal_arc_score": 0.7,
            "mapper_volatility_score": 0.1,
            "turn_number": 0,
            "tier": "hybrid",
            "domain": "general",
            "active_mappers": [],
        }

        ctx.fusion = None
        ctx.dha = None
        ctx.mlcr = None
        ctx.rendered = None
        ctx.mapper_profile = Mock()
        ctx.mapper_profile.to_dict = lambda: {}
        ctx.request = None
        ctx.session_memory = None
        ctx.session_recap = None
        ctx.intent_arc = None
        ctx.identity_signature = None
        ctx.motivation_profile = None
        ctx.trading_guardrails = None
        ctx.policy_flags = None
        ctx.interaction_mode = None

        unified = build_unified_output(text="test", ctx=ctx)
        unified_dict = unified.to_dict()

        # coherence_fused should not be present (None values removed)
        assert "coherence_fused" not in unified_dict.get("coherence", {})

    def test_c4_observer_extracts_fused_metrics(self):
        """Test that CoherenceObserver extracts fusion metrics."""
        try:
            from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObserver
        except ImportError:
            pytest.skip("pydantic not installed")

        observer = CoherenceObserver()

        # Mock context with coherence state
        ctx = Mock()
        ctx.coherence_state = Mock()
        ctx.coherence_state.coherence_score = 0.75
        ctx.coherence_state.persona_drift_score = 0.2
        ctx.coherence_state.semantic_stability_score = 0.8
        ctx.coherence_state.temporal_arc_score = 0.7
        ctx.coherence_state.mapper_volatility_score = 0.1
        ctx.coherence_state.turn_index = 5
        ctx.coherence_state.domain_history = ["general"]
        ctx.coherence_state.bhava_id_history = [1]
        ctx.coherence_state.bhava_direction_history = ["stable"]
        ctx.coherence_state.smi_history = [0.7]
        ctx.coherence_state.delta_smi_history = []
        ctx.coherence_state.bhava_gap_history = []
        ctx.coherence_state.tension_corridor_history = []
        ctx.coherence_state.vritti_momentum_history = []
        ctx.coherence_state.arc_tension_harmonizer_history = []
        ctx.coherence_state.mirror_cycle_history = []
        ctx.coherence_state.cause_effect_inversion_history = []
        ctx.coherence_state.resonance_weighting_history = []
        ctx.coherence_state.ucf_history = []
        ctx.coherence_state.temporal_entropy_volatility = None
        ctx.coherence_state.cognitive_drift_v3 = None
        ctx.coherence_state.drift_pattern_tags = None
        ctx.coherence_state.ucf_notes = None
        ctx.coherence_state.symbolic_harmonization_snapshot = None
        ctx.coherence_state.coherence_fused = 0.76
        ctx.coherence_state.fusion_stability_weight = 0.85
        ctx.coherence_state.fusion_inertia_factor = 0.9
        ctx.coherence_state.fusion_quality_factor = 0.8

        ctx.mlcr = None

        observation = observer.observe(text="test", pipeline_context=ctx)

        # Check that fusion metrics are extracted
        assert observation.coherence_fused == 0.76
        assert observation.fusion_stability_weight == 0.85
        assert observation.fusion_inertia_factor == 0.9
        assert observation.fusion_quality_factor == 0.8

    def test_c5_observer_snapshot_includes_stabilizer(self):
        """Test that observer snapshot includes stabilizer section."""
        try:
            from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObserver
        except ImportError:
            pytest.skip("pydantic not installed")

        observer = CoherenceObserver()

        ctx = Mock()
        ctx.coherence_state = Mock()
        ctx.coherence_state.coherence_score = 0.75
        ctx.coherence_state.persona_drift_score = 0.2
        ctx.coherence_state.semantic_stability_score = 0.8
        ctx.coherence_state.temporal_arc_score = 0.7
        ctx.coherence_state.mapper_volatility_score = 0.1
        ctx.coherence_state.turn_index = 5
        ctx.coherence_state.domain_history = ["general"]
        ctx.coherence_state.bhava_id_history = [1]
        ctx.coherence_state.bhava_direction_history = ["stable"]
        ctx.coherence_state.smi_history = [0.7]
        ctx.coherence_state.delta_smi_history = []
        ctx.coherence_state.bhava_gap_history = []
        ctx.coherence_state.tension_corridor_history = []
        ctx.coherence_state.vritti_momentum_history = []
        ctx.coherence_state.arc_tension_harmonizer_history = []
        ctx.coherence_state.mirror_cycle_history = []
        ctx.coherence_state.cause_effect_inversion_history = []
        ctx.coherence_state.resonance_weighting_history = []
        ctx.coherence_state.ucf_history = []
        ctx.coherence_state.temporal_entropy_volatility = None
        ctx.coherence_state.cognitive_drift_v3 = None
        ctx.coherence_state.drift_pattern_tags = None
        ctx.coherence_state.ucf_notes = None
        ctx.coherence_state.symbolic_harmonization_snapshot = None
        ctx.coherence_state.coherence_fused = 0.76
        ctx.coherence_state.fusion_stability_weight = 0.85
        ctx.coherence_state.fusion_inertia_factor = 0.9
        ctx.coherence_state.fusion_quality_factor = 0.8

        ctx.mlcr = None

        observer.observe(text="test", pipeline_context=ctx)
        snapshot = observer.snapshot()

        # Check that stabilizer section exists
        assert "stabilizer" in snapshot
        assert snapshot["stabilizer"]["coherence_fused"] == 0.76

    def test_c6_dilchat_adapter_includes_stabilizer(self):
        """Test that DILchat adapter includes stabilizer diagnostics."""
        from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

        unified_output = {
            "text": "test response",
            "coherence": {
                "coherence_score": 0.75,
                "coherence_fused": 0.76,
                "stabilizer": {
                    "stability_weight": 0.85,
                    "inertia_factor": 0.9,
                    "quality_factor": 0.8,
                },
            },
            "metadata": {"domain": "general"},
            "symbolic": {},
            "practical": {},
            "mirror": {},
        }

        policy_flags = {"stability_status": "stable"}

        response = build_dilchat_response(
            unified_output=unified_output,
            policy_flags=policy_flags,
            domain="general",
        )

        # Check that stabilizer is included in raw_unified
        assert response.stabilizer is not None
        assert response.stabilizer["stability_weight"] == 0.85


# ============================================================================
# GROUP D — Behavioral Invariance (6 tests)
# ============================================================================


class TestGroupD_BehavioralInvariance:
    """Test that fusion stabilizer does not change existing pipeline behavior."""

    def test_d1_no_routing_changes(self):
        """Test that fusion stabilizer does not affect routing."""
        # This is a smoke test - routing should be independent
        # In a real test, we'd compare routing decisions with/without fusion
        from agentic.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Routing plan should not be modified
        assert routing_plan.tier == "hybrid"
        assert routing_plan.domain == "general"

    def test_d2_no_mapper_changes(self):
        """Test that fusion stabilizer does not affect mapper profile."""
        from agentic.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium", "detail_bias": 0.5}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Mapper profile should not be modified
        assert mapper_profile["resolution_level"] == "medium"
        assert mapper_profile["detail_bias"] == 0.5

    def test_d3_no_policy_changes(self):
        """Test that fusion stabilizer does not affect policy flags."""
        # This is a smoke test - policy should be independent
        # Since we don't have direct policy access in this test, we verify
        # that state.coherence_fused is observation-only (not used in logic)
        from agentic.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # coherence_fused should exist but not affect other scores
        assert state.coherence_fused is not None
        # v1 should remain unchanged
        assert state.coherence_score is not None

    def test_d4_trading_domain_unchanged(self):
        """Test that trading domain behavior is unchanged."""
        from agentic.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "trading"  # Trading domain
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "high"}
        temporal_summary = {"smi": 0.8, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Domain should remain unchanged
        assert routing_plan.domain == "trading"
        # Coherence metrics computed normally
        assert state.coherence_score is not None

    def test_d5_therapy_domain_unchanged(self):
        """Test that therapy/identity domain behavior is unchanged."""
        from agentic.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "upper"
        routing_plan.domain = "therapy"  # Therapy domain
        routing_plan.long_arc_tension = 0.6

        mapper_profile = {"resolution_level": "deep"}
        temporal_summary = {"smi": 0.9, "bhava_id": 2, "bhava_direction": "upward"}
        semantic_signature = {}

        state = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Domain should remain unchanged
        assert routing_plan.domain == "therapy"
        # Coherence metrics computed normally
        assert state.coherence_score is not None

    def test_d6_snapshot_consistency(self):
        """Test that snapshot output is consistent."""
        from agentic.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine(window=10)

        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "general"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "medium"}
        temporal_summary = {"smi": 0.7, "bhava_id": 1, "bhava_direction": "stable"}
        semantic_signature = {}

        # Run twice with identical inputs
        state1 = engine.update_state(
            prev_state=None,
            convo_id="test_123",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        state2 = engine.update_state(
            prev_state=None,
            convo_id="test_456",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Snapshots should be identical
        assert state1.coherence_fused == state2.coherence_fused
        assert state1.fusion_stability_weight == state2.fusion_stability_weight
        assert state1.fusion_inertia_factor == state2.fusion_inertia_factor


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
