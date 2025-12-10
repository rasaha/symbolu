"""
Phase 8 Integration Tests: Guna/Kosha Resonance Engine
=======================================================

Comprehensive integration tests for Phase 8 Guna/Kosha resonance wiring.

Test Groups:
- Group A: Wiring & Propagation (5 tests)
- Group B: Behavioral Invariance (6 tests)
- Group C: Missing Data & Graceful Degradation (5 tests)

All tests verify that Guna/Kosha metrics are observation-only and do NOT
affect routing, mappers, policy, or any decision logic.
"""

import pytest
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver
from symbolu.service.sessions.session_store import SessionStore, compute_session_summary
from symbolu.service.sessions.session_models import SessionState
from symbolu.api.unified_api import build_unified_output
from symbolu.adapter.dilchat_adapter import build_dilchat_response
from datetime import datetime


# =============================================================================
# FIXTURES & TEST DATA
# =============================================================================


@pytest.fixture
def mock_routing_plan_with_guna_kosha():
    """Mock routing plan with Guna/Kosha data."""
    class MockRoutingPlan:
        def __init__(self):
            self.tier = "hybrid"
            self.domain = "general"
            self.long_arc_tension = 0.5
            self.guna_probs = {"sattva": 0.4, "rajas": 0.3, "tamas": 0.3}
            self.kosha_probs = {
                "annamaya": 0.3,
                "pranamaya": 0.25,
                "manomaya": 0.2,
                "vijnanamaya": 0.15,
                "anandamaya": 0.1,
            }
    return MockRoutingPlan()


@pytest.fixture
def mock_routing_plan_without_guna_kosha():
    """Mock routing plan WITHOUT Guna/Kosha data."""
    class MockRoutingPlan:
        def __init__(self):
            self.tier = "hybrid"
            self.domain = "general"
            self.long_arc_tension = 0.5
    return MockRoutingPlan()


@pytest.fixture
def mock_temporal_summary_with_guna_kosha():
    """Mock temporal summary with Guna/Kosha data."""
    return {
        "smi": 0.7,
        "bhava_id": 3,
        "bhava_direction": "upward",
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "guna_probs": {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2},
        "kosha_probs": {
            "annamaya": 0.4,
            "pranamaya": 0.3,
            "manomaya": 0.2,
            "vijnanamaya": 0.1,
        },
        "flags": {},
    }


@pytest.fixture
def mock_mapper_profile():
    """Mock mapper profile."""
    return {
        "resolution_level": "medium",
        "arc_mode": "short",
        "detail_bias": 0.5,
        "practical_bias": 0.5,
        "reflective_bias": 0.5,
    }


# =============================================================================
# GROUP A: WIRING & PROPAGATION
# =============================================================================


def test_coherence_state_stores_guna_kosha_metrics(
    mock_routing_plan_with_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """CoherenceState should store Guna/Kosha metrics when inputs are present."""
    engine = CoherenceEngine(window=10)

    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    # Verify Guna/Kosha metrics are populated
    assert state.guna_resonance_index is not None, "Guna resonance should be computed"
    assert 0.0 <= state.guna_resonance_index <= 1.0, "Guna resonance should be in [0, 1]"

    assert state.kosha_resonance_index is not None, "Kosha resonance should be computed"
    assert 0.0 <= state.kosha_resonance_index <= 1.0, "Kosha resonance should be in [0, 1]"

    assert state.kosha_activation_vector is not None, "Kosha activation vector should be present"
    assert len(state.kosha_activation_vector) == 5, "Kosha vector should have 5 elements"


def test_session_summary_aggregates_guna_kosha_metrics():
    """SessionSummary should aggregate avg_guna_resonance and avg_kosha_resonance."""
    # Create mock session state with coherence history containing Guna/Kosha metrics
    session_state = SessionState(
        session_id="test_session_1",
        created_at=datetime.utcnow(),
        domain="general",
    )

    # Add 3 coherence snapshots with Guna/Kosha metrics
    session_state.coherence_history = [
        {"guna_resonance_index": 0.8, "kosha_resonance_index": 0.7},
        {"guna_resonance_index": 0.85, "kosha_resonance_index": 0.75},
        {"guna_resonance_index": 0.9, "kosha_resonance_index": 0.8},
    ]

    session_state.turns = [{}] * 3  # Mock turns

    # Compute summary
    summary = compute_session_summary(session_state)

    # Verify aggregates
    assert summary.avg_guna_resonance is not None, "avg_guna_resonance should be computed"
    assert abs(summary.avg_guna_resonance - 0.85) < 0.01, "avg_guna_resonance should be 0.85"

    assert summary.avg_kosha_resonance is not None, "avg_kosha_resonance should be computed"
    assert abs(summary.avg_kosha_resonance - 0.75) < 0.01, "avg_kosha_resonance should be 0.75"


def test_coherence_observer_surfaces_guna_kosha_metrics(
    mock_routing_plan_with_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """CoherenceObserver should surface Guna/Kosha metrics in observations."""
    # Create coherence state with Guna/Kosha metrics
    engine = CoherenceEngine(window=10)
    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    # Mock pipeline context
    class MockContext:
        def __init__(self, coherence_state):
            self.coherence_state = coherence_state
            self.mlcr = None

    ctx = MockContext(state)

    # Observe
    observer = CoherenceObserver()
    observation = observer.observe("test input", ctx, state)

    # Verify Guna/Kosha metrics are in observation
    assert observation.guna_resonance_index is not None
    assert observation.kosha_resonance_index is not None

    # Verify they appear in serialized output
    obs_dict = observation.to_dict()
    assert "guna_resonance_index" in obs_dict
    assert "kosha_resonance_index" in obs_dict


def test_unified_output_contains_guna_kosha_in_formulas(
    mock_routing_plan_with_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """UnifiedOutput should contain Guna/Kosha metrics in formulas section."""
    # Create coherence state with Guna/Kosha metrics
    engine = CoherenceEngine(window=10)
    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    # Mock pipeline context
    class MockContext:
        def __init__(self, coherence_state):
            self.coherence_state = coherence_state
            self.fusion = None
            self.dha = None
            self.mlcr = None
            self.coherence_report = {}
            self.rendered = None

    ctx = MockContext(state)

    # Build unified output
    unified = build_unified_output("test response", ctx)
    unified_dict = unified.to_dict()

    # Verify formulas section contains Guna/Kosha metrics
    assert "formulas" in unified_dict
    assert unified_dict["formulas"] is not None
    assert "guna_resonance_index" in unified_dict["formulas"]
    assert "kosha_resonance_index" in unified_dict["formulas"]
    assert "kosha_activation_vector" in unified_dict["formulas"]


def test_dilchat_diagnostics_surface_guna_kosha_metrics():
    """DILchat adapter should surface Guna/Kosha metrics in diagnostics."""
    # Create mock unified output with formulas containing Guna/Kosha
    unified_output = {
        "text": "test response",
        "formulas": {
            "guna_resonance_index": 0.85,
            "kosha_resonance_index": 0.75,
            "kosha_activation_vector": [0.3, 0.25, 0.2, 0.15, 0.1],
        },
        "coherence": {
            "coherence_score": 0.8,
        },
        "metadata": {
            "domain": "general",
        },
    }

    policy_flags = {}

    # Build DILchat response
    dilchat_response = build_dilchat_response(unified_output, policy_flags, domain="general")
    dilchat_dict = dilchat_response.to_dict()

    # Verify formulas field contains Guna/Kosha metrics (diagnostics)
    assert "formulas" in dilchat_dict
    assert dilchat_dict["formulas"]["guna_resonance_index"] == 0.85
    assert dilchat_dict["formulas"]["kosha_resonance_index"] == 0.75
    assert dilchat_dict["formulas"]["kosha_activation_vector"] == [0.3, 0.25, 0.2, 0.15, 0.1]


# =============================================================================
# GROUP B: BEHAVIORAL INVARIANCE
# =============================================================================


def test_guna_kosha_does_not_affect_routing(
    mock_routing_plan_with_guna_kosha,
    mock_routing_plan_without_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """Guna/Kosha metrics should NOT affect routing decisions (TTOR invariant)."""
    engine = CoherenceEngine(window=10)

    # Create two states: one with Guna/Kosha, one without
    state_with = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    temporal_summary_without_guna_kosha = mock_temporal_summary_with_guna_kosha.copy()
    temporal_summary_without_guna_kosha.pop("guna_probs", None)
    temporal_summary_without_guna_kosha.pop("kosha_probs", None)

    state_without = engine.update_state(
        prev_state=None,
        convo_id="test_convo_2",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_without_guna_kosha,
        semantic_signature={},
    )

    # Verify core coherence scores are NOT affected by Guna/Kosha presence
    assert state_with.coherence_score == state_without.coherence_score, \
        "Coherence score v1 should be invariant to Guna/Kosha"
    assert state_with.persona_drift_score == state_without.persona_drift_score, \
        "Persona drift should be invariant to Guna/Kosha"
    assert state_with.semantic_stability_score == state_without.semantic_stability_score, \
        "Semantic stability should be invariant to Guna/Kosha"


def test_guna_kosha_does_not_affect_mapper_activation(
    mock_routing_plan_with_guna_kosha,
    mock_routing_plan_without_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """Guna/Kosha metrics should NOT affect mapper activation (HRM/LCM/LAM invariant)."""
    engine = CoherenceEngine(window=10)

    state_with = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    temporal_summary_without = mock_temporal_summary_with_guna_kosha.copy()
    temporal_summary_without.pop("guna_probs", None)
    temporal_summary_without.pop("kosha_probs", None)

    state_without = engine.update_state(
        prev_state=None,
        convo_id="test_convo_2",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_without,
        semantic_signature={},
    )

    # Verify mapper volatility is NOT affected
    assert state_with.mapper_volatility_score == state_without.mapper_volatility_score, \
        "Mapper volatility should be invariant to Guna/Kosha"


def test_guna_kosha_does_not_affect_coherence_v1_and_v2(
    mock_routing_plan_with_guna_kosha,
    mock_routing_plan_without_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """Guna/Kosha should NOT affect coherence_score (v1) or coherence_score_v2."""
    engine = CoherenceEngine(window=10)

    state_with = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    temporal_summary_without = mock_temporal_summary_with_guna_kosha.copy()
    temporal_summary_without.pop("guna_probs", None)
    temporal_summary_without.pop("kosha_probs", None)

    state_without = engine.update_state(
        prev_state=None,
        convo_id="test_convo_2",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_without,
        semantic_signature={},
    )

    # Verify coherence scores are identical
    assert state_with.coherence_score == state_without.coherence_score, \
        "Coherence v1 should be invariant to Guna/Kosha"

    # Both should have same coherence_score_v2 (or both None)
    assert state_with.coherence_score_v2 == state_without.coherence_score_v2, \
        "Coherence v2 should be invariant to Guna/Kosha"


def test_guna_kosha_does_not_affect_temporal_arc_score(
    mock_routing_plan_with_guna_kosha,
    mock_routing_plan_without_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """Guna/Kosha should NOT affect temporal_arc_score."""
    engine = CoherenceEngine(window=10)

    state_with = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    temporal_summary_without = mock_temporal_summary_with_guna_kosha.copy()
    temporal_summary_without.pop("guna_probs", None)
    temporal_summary_without.pop("kosha_probs", None)

    state_without = engine.update_state(
        prev_state=None,
        convo_id="test_convo_2",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_without,
        semantic_signature={},
    )

    # Verify temporal arc is invariant
    assert state_with.temporal_arc_score == state_without.temporal_arc_score, \
        "Temporal arc score should be invariant to Guna/Kosha"


def test_guna_kosha_does_not_affect_phase3_derived_metrics(
    mock_routing_plan_with_guna_kosha,
    mock_routing_plan_without_guna_kosha,
    mock_temporal_summary_with_guna_kosha,
    mock_mapper_profile,
):
    """Guna/Kosha should NOT affect Phase 3 derived metrics (resonance/tension/arc_alignment)."""
    engine = CoherenceEngine(window=10)

    state_with = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_with_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=mock_temporal_summary_with_guna_kosha,
        semantic_signature={},
    )

    temporal_summary_without = mock_temporal_summary_with_guna_kosha.copy()
    temporal_summary_without.pop("guna_probs", None)
    temporal_summary_without.pop("kosha_probs", None)

    state_without = engine.update_state(
        prev_state=None,
        convo_id="test_convo_2",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_without,
        semantic_signature={},
    )

    # Verify Phase 3 derived metrics are invariant
    assert state_with.resonance_index == state_without.resonance_index, \
        "Resonance index should be invariant to Guna/Kosha"
    assert state_with.tension_index == state_without.tension_index, \
        "Tension index should be invariant to Guna/Kosha"
    assert state_with.arc_alignment_index == state_without.arc_alignment_index, \
        "Arc alignment index should be invariant to Guna/Kosha"


def test_guna_kosha_does_not_create_new_policy_flags():
    """Guna/Kosha metrics should NOT generate new policy flags."""
    # This test verifies that Guna/Kosha presence doesn't trigger any
    # policy engine behavior changes

    # Create mock unified output with Guna/Kosha
    unified_output = {
        "text": "test",
        "formulas": {
            "guna_resonance_index": 0.2,  # Low guna resonance (extreme skew)
            "kosha_resonance_index": 0.3,  # Low kosha resonance (spike)
        },
        "coherence": {"coherence_score": 0.8},
        "metadata": {"domain": "general"},
    }

    # Empty policy flags
    policy_flags = {}

    # Build DILchat response
    dilchat_response = build_dilchat_response(unified_output, policy_flags, domain="general")

    # Verify no new policy-driven badges or hints were created based on Guna/Kosha
    # (policy flags remain empty, so response should not have policy-triggered elements)
    dilchat_dict = dilchat_response.to_dict()

    # Guna/Kosha should only appear in formulas (diagnostics), not in badges or hints
    if "badges" in dilchat_dict:
        # No badges should reference guna or kosha
        for badge in dilchat_dict.get("badges", []):
            assert "guna" not in badge.get("label", "").lower()
            assert "kosha" not in badge.get("label", "").lower()


# =============================================================================
# GROUP C: MISSING DATA & GRACEFUL DEGRADATION
# =============================================================================


def test_missing_guna_kosha_input_sets_metrics_to_none(
    mock_routing_plan_without_guna_kosha,
    mock_mapper_profile,
):
    """When Guna/Kosha inputs are missing, metrics should be None."""
    engine = CoherenceEngine(window=10)

    temporal_summary_without_guna_kosha = {
        "smi": 0.7,
        "bhava_id": 3,
        "bhava_direction": "upward",
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "flags": {},
    }

    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_without_guna_kosha,
        semantic_signature={},
    )

    # Verify Guna/Kosha metrics are None when inputs missing
    assert state.guna_resonance_index is None, "Guna resonance should be None without input"
    assert state.kosha_resonance_index is None, "Kosha resonance should be None without input"
    assert state.kosha_activation_vector is None, "Kosha vector should be None without input"


def test_unified_output_valid_json_without_guna_kosha(
    mock_routing_plan_without_guna_kosha,
    mock_mapper_profile,
):
    """UnifiedOutput should be valid JSON even without Guna/Kosha data."""
    engine = CoherenceEngine(window=10)

    temporal_summary = {
        "smi": 0.7,
        "bhava_id": 3,
        "bhava_direction": "upward",
        "delta_smi": 0.1,
        "bhava_gap": 0.2,
        "tension_corridor": 0.3,
        "flags": {},
    }

    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary,
        semantic_signature={},
    )

    class MockContext:
        def __init__(self, coherence_state):
            self.coherence_state = coherence_state
            self.fusion = None
            self.dha = None
            self.mlcr = None
            self.coherence_report = {}
            self.rendered = None

    ctx = MockContext(state)

    # Build unified output
    unified = build_unified_output("test response", ctx)
    unified_dict = unified.to_dict()

    # Verify it's valid JSON (no errors)
    import json
    json_str = json.dumps(unified_dict)
    assert json_str is not None

    # Guna/Kosha keys should not appear in formulas if no data
    if "formulas" in unified_dict and unified_dict["formulas"]:
        assert "guna_resonance_index" not in unified_dict["formulas"]
        assert "kosha_resonance_index" not in unified_dict["formulas"]


def test_pipeline_runs_without_errors_missing_guna_kosha(
    mock_routing_plan_without_guna_kosha,
    mock_mapper_profile,
):
    """Full pipeline should run without errors when Guna/Kosha inputs are missing."""
    engine = CoherenceEngine(window=10)

    temporal_summary = {
        "smi": 0.7,
        "bhava_id": 3,
        "bhava_direction": "upward",
        "flags": {},
    }

    # This should not raise any exceptions
    try:
        state = engine.update_state(
            prev_state=None,
            convo_id="test_convo_1",
            turn_index=0,
            routing_plan=mock_routing_plan_without_guna_kosha,
            mapper_profile=mock_mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature={},
        )

        # Observer should also work
        observer = CoherenceObserver()
        class MockContext:
            def __init__(self, cs):
                self.coherence_state = cs
                self.mlcr = None
        ctx = MockContext(state)
        observation = observer.observe("test", ctx, state)

        # Unified output should work
        unified = build_unified_output("test", ctx)

        # All succeeded
        assert True

    except Exception as e:
        pytest.fail(f"Pipeline should not raise exceptions without Guna/Kosha: {e}")


def test_session_summary_handles_missing_guna_kosha_gracefully():
    """SessionSummary should handle missing Guna/Kosha data gracefully."""
    # Create mock session state without Guna/Kosha metrics
    session_state = SessionState(
        session_id="test_session_1",
        created_at=datetime.utcnow(),
        domain="general",
    )

    # Coherence history without Guna/Kosha
    session_state.coherence_history = [
        {"coherence_score": 0.8},
        {"coherence_score": 0.85},
    ]

    session_state.turns = [{}] * 2

    # Should not raise
    summary = compute_session_summary(session_state)

    # Guna/Kosha aggregates should be None
    assert summary.avg_guna_resonance is None
    assert summary.avg_kosha_resonance is None


def test_partial_guna_kosha_data_handled_gracefully(
    mock_routing_plan_without_guna_kosha,
    mock_mapper_profile,
):
    """Pipeline should handle partial Guna/Kosha data (only guna OR only kosha)."""
    engine = CoherenceEngine(window=10)

    # Only guna_probs, no kosha_probs
    temporal_summary_partial = {
        "smi": 0.7,
        "bhava_id": 3,
        "bhava_direction": "upward",
        "guna_probs": {"sattva": 0.5, "rajas": 0.3, "tamas": 0.2},
        "flags": {},
    }

    state = engine.update_state(
        prev_state=None,
        convo_id="test_convo_1",
        turn_index=0,
        routing_plan=mock_routing_plan_without_guna_kosha,
        mapper_profile=mock_mapper_profile,
        temporal_summary=temporal_summary_partial,
        semantic_signature={},
    )

    # Should compute guna resonance but not kosha
    assert state.guna_resonance_index is not None
    assert 0.0 <= state.guna_resonance_index <= 1.0

    # Kosha metrics should be set to defaults (0.0 for index, empty/zero vector)
    # per the wrapper's graceful handling
    assert state.kosha_resonance_index is not None  # Wrapper sets to 0.0
    assert state.kosha_activation_vector is not None  # Wrapper sets to [0.0, ...]
