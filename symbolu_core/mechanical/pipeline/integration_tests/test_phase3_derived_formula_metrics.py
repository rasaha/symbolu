"""
Phase 3 Derived Formula Metrics Integration Tests
==================================================

Tests for Phase 3 Symbol-U Formula Integration Plan v1.0.

These tests verify that Phase 3 derived formula metrics (Resonance Index, Tension Index,
Arc Alignment Index) are correctly computed and propagated through:
- Coherence state
- Session summary
- Coherence observer
- Unified output
- DILchat adapter

All changes must be:
- Zero-LLM (deterministic)
- Non-invasive (no behavior changes to existing scores/routing/policy)
- CI-safe (all tests pass)
- Observation-only (derived metrics don't affect existing behavior)

Test Coverage:
1. Coherence Derived Metric Sanity - deterministic computation, value ranges
2. Session Summary Aggregation - multi-turn averaging
3. Observer & Unified API - wiring through observability layer
4. Behavioral Invariance - no changes to existing scores/routing
"""

import pytest
from typing import Dict, Any, Optional
from dataclasses import asdict

from agentic.core.coherence.coherence_engine import CoherenceEngine
from agentic.core.coherence.coherence_state import CoherenceState
from symbolu_core.service.sessions.session_store import SessionStore, compute_session_summary
from symbolu_core.service.sessions.session_models import SessionState
from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObserver


# ==============================================================================
# Test Group 1: Coherence Derived Metric Sanity
# ==============================================================================


def test_derived_metrics_high_resonance_scenario():
    """
    Test resonance_index computation for high-resonance scenario.

    High resonance = high SMI, small gap, small |ΔSMI|
    Expected: high resonance_index (close to 1.0)
    """
    engine = CoherenceEngine(window=10)

    # Create initial state
    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Simulate high SMI, small gap, small delta scenario
    state.smi_history = [0.9]  # High SMI
    state.delta_smi_history = [0.05]  # Small delta (stable)
    state.bhava_gap_history = [0.1]  # Small gap (close states)
    state.tension_corridor_history = [0.2]  # Low tension

    # Trigger derived metric computation
    engine._update_derived_formula_metrics(state)

    # Assertions
    assert state.resonance_index is not None
    assert 0.0 <= state.resonance_index <= 1.0
    assert state.resonance_index > 0.7, f"Expected high resonance, got {state.resonance_index}"

    assert state.tension_index is not None
    assert 0.0 <= state.tension_index <= 1.0
    assert state.tension_index < 0.4, f"Expected low tension, got {state.tension_index}"

    assert state.arc_alignment_index is not None
    assert 0.0 <= state.arc_alignment_index <= 1.0
    # Positive delta means improving
    assert state.arc_alignment_index > 0.6, f"Expected good alignment, got {state.arc_alignment_index}"


def test_derived_metrics_high_tension_scenario():
    """
    Test tension_index computation for high-tension scenario.

    High tension = high tension corridor, large |ΔSMI|
    Expected: high tension_index (close to 1.0)
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Simulate high tension scenario
    state.smi_history = [0.4]  # Moderate SMI
    state.delta_smi_history = [-0.3]  # Large negative delta (unstable)
    state.bhava_gap_history = [0.8]  # Large gap (far states)
    state.tension_corridor_history = [0.9]  # High tension

    engine._update_derived_formula_metrics(state)

    assert state.tension_index is not None
    assert 0.0 <= state.tension_index <= 1.0
    assert state.tension_index > 0.7, f"Expected high tension, got {state.tension_index}"

    assert state.resonance_index is not None
    assert state.resonance_index < 0.5, f"Expected low resonance, got {state.resonance_index}"


def test_derived_metrics_improving_trajectory():
    """
    Test arc_alignment_index for improving trajectory (positive ΔSMI).

    Improving trajectory = positive delta_smi
    Expected: higher arc_alignment_index
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Improving trajectory
    state.smi_history = [0.7]
    state.delta_smi_history = [0.2]  # Positive delta (improving)
    state.bhava_gap_history = [0.2]
    state.tension_corridor_history = [0.3]

    engine._update_derived_formula_metrics(state)

    assert state.arc_alignment_index is not None
    assert state.arc_alignment_index > 0.6, f"Expected good alignment for improving trajectory, got {state.arc_alignment_index}"


def test_derived_metrics_declining_trajectory():
    """
    Test arc_alignment_index for declining trajectory (negative ΔSMI).

    Declining trajectory = negative delta_smi
    Expected: lower arc_alignment_index than improving case
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Declining trajectory
    state.smi_history = [0.7]
    state.delta_smi_history = [-0.2]  # Negative delta (declining)
    state.bhava_gap_history = [0.2]
    state.tension_corridor_history = [0.3]

    engine._update_derived_formula_metrics(state)

    assert state.arc_alignment_index is not None

    # Compare with improving case
    state2 = CoherenceState(convo_id="test_convo", turn_index=0)
    state2.smi_history = [0.7]
    state2.delta_smi_history = [0.2]  # Positive
    state2.bhava_gap_history = [0.2]
    state2.tension_corridor_history = [0.3]
    engine._update_derived_formula_metrics(state2)

    assert state.arc_alignment_index < state2.arc_alignment_index, \
        "Declining trajectory should have lower arc_alignment than improving"


def test_derived_metrics_no_formula_data():
    """
    Test that derived metrics are None when formula data is missing.
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(
        convo_id="test_convo",
        turn_index=0,
    )

    # Empty histories (no formula data)
    state.smi_history = []
    state.delta_smi_history = []
    state.bhava_gap_history = []
    state.tension_corridor_history = []

    engine._update_derived_formula_metrics(state)

    assert state.resonance_index is None
    assert state.tension_index is None
    assert state.arc_alignment_index is None


def test_derived_metrics_determinism():
    """
    Test that derived metrics are deterministic (same inputs → same outputs).
    """
    engine = CoherenceEngine(window=10)

    # Run 1
    state1 = CoherenceState(convo_id="test_convo", turn_index=0)
    state1.smi_history = [0.65]
    state1.delta_smi_history = [0.15]
    state1.bhava_gap_history = [0.33]
    state1.tension_corridor_history = [0.42]
    engine._update_derived_formula_metrics(state1)

    # Run 2 (identical inputs)
    state2 = CoherenceState(convo_id="test_convo", turn_index=0)
    state2.smi_history = [0.65]
    state2.delta_smi_history = [0.15]
    state2.bhava_gap_history = [0.33]
    state2.tension_corridor_history = [0.42]
    engine._update_derived_formula_metrics(state2)

    # Assert exact equality
    assert state1.resonance_index == state2.resonance_index
    assert state1.tension_index == state2.tension_index
    assert state1.arc_alignment_index == state2.arc_alignment_index


def test_derived_metrics_value_ranges():
    """
    Test that all derived metrics are always in [0.0, 1.0] range.
    """
    engine = CoherenceEngine(window=10)

    # Test extreme values
    test_cases = [
        # (smi, delta_smi, bhava_gap, tension_corridor)
        (0.0, 0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0, 1.0),
        (0.0, 1.0, 0.0, 1.0),
        (1.0, -1.0, 1.0, 0.0),
        (0.5, 0.0, 0.5, 0.5),
    ]

    for smi, delta, gap, tension in test_cases:
        state = CoherenceState(convo_id="test_convo", turn_index=0)
        state.smi_history = [smi]
        state.delta_smi_history = [delta]
        state.bhava_gap_history = [gap]
        state.tension_corridor_history = [tension]

        engine._update_derived_formula_metrics(state)

        assert 0.0 <= state.resonance_index <= 1.0, \
            f"resonance_index out of range for inputs {test_cases}"
        assert 0.0 <= state.tension_index <= 1.0, \
            f"tension_index out of range for inputs {test_cases}"
        assert 0.0 <= state.arc_alignment_index <= 1.0, \
            f"arc_alignment_index out of range for inputs {test_cases}"


# ==============================================================================
# Test Group 2: Session Summary Aggregation
# ==============================================================================


def test_session_summary_derived_metrics_multi_turn():
    """
    Test that session summary correctly aggregates derived metrics over multiple turns.
    """
    store = SessionStore()
    session = store.create_session(domain="test")

    # Simulate 3 turns with varying derived metrics
    coherence_history = [
        {
            "coherence_score": 0.8,
            "resonance_index": 0.7,
            "tension_index": 0.3,
            "arc_alignment_index": 0.75,
        },
        {
            "coherence_score": 0.85,
            "resonance_index": 0.75,
            "tension_index": 0.25,
            "arc_alignment_index": 0.8,
        },
        {
            "coherence_score": 0.9,
            "resonance_index": 0.8,
            "tension_index": 0.2,
            "arc_alignment_index": 0.85,
        },
    ]

    session.coherence_history = coherence_history
    session.turns = [{} for _ in range(3)]  # 3 turns

    summary = compute_session_summary(session)

    # Check averages
    assert summary.avg_resonance_index is not None
    assert abs(summary.avg_resonance_index - 0.75) < 0.01  # (0.7 + 0.75 + 0.8) / 3

    assert summary.avg_tension_index is not None
    assert abs(summary.avg_tension_index - 0.25) < 0.01  # (0.3 + 0.25 + 0.2) / 3

    assert summary.avg_arc_alignment_index is not None
    assert abs(summary.avg_arc_alignment_index - 0.8) < 0.01  # (0.75 + 0.8 + 0.85) / 3


def test_session_summary_derived_metrics_no_data():
    """
    Test that session summary handles missing derived metric data gracefully.
    """
    store = SessionStore()
    session = store.create_session(domain="test")

    # Empty coherence history
    session.coherence_history = []
    session.turns = []

    summary = compute_session_summary(session)

    assert summary.avg_resonance_index is None
    assert summary.avg_tension_index is None
    assert summary.avg_arc_alignment_index is None


def test_session_summary_derived_metrics_partial_data():
    """
    Test aggregation when some turns have derived metrics and some don't.
    """
    store = SessionStore()
    session = store.create_session(domain="test")

    coherence_history = [
        {
            "coherence_score": 0.8,
            # No derived metrics in first turn
        },
        {
            "coherence_score": 0.85,
            "resonance_index": 0.7,
            "tension_index": 0.3,
            "arc_alignment_index": 0.75,
        },
        {
            "coherence_score": 0.9,
            "resonance_index": 0.8,
            "tension_index": 0.2,
            "arc_alignment_index": 0.85,
        },
    ]

    session.coherence_history = coherence_history
    session.turns = [{} for _ in range(3)]

    summary = compute_session_summary(session)

    # Should average only the turns with data
    assert summary.avg_resonance_index is not None
    assert abs(summary.avg_resonance_index - 0.75) < 0.01  # (0.7 + 0.8) / 2

    assert summary.avg_tension_index is not None
    assert abs(summary.avg_tension_index - 0.25) < 0.01  # (0.3 + 0.2) / 2

    assert summary.avg_arc_alignment_index is not None
    assert abs(summary.avg_arc_alignment_index - 0.8) < 0.01  # (0.75 + 0.85) / 2


# ==============================================================================
# Test Group 3: Observer & Unified API
# ==============================================================================


def test_coherence_observer_includes_derived_metrics():
    """
    Test that CoherenceObserver extracts and includes derived metrics in observations.
    """
    observer = CoherenceObserver()

    # Create mock coherence state with derived metrics
    coherence_state = CoherenceState(
        convo_id="test_convo",
        turn_index=1,
    )
    coherence_state.resonance_index = 0.75
    coherence_state.tension_index = 0.3
    coherence_state.arc_alignment_index = 0.8
    coherence_state.coherence_score = 0.85
    coherence_state.persona_drift_score = 0.1
    coherence_state.semantic_stability_score = 0.9
    coherence_state.temporal_arc_score = 0.8
    coherence_state.mapper_volatility_score = 0.2

    # Create mock pipeline context
    class MockContext:
        def __init__(self):
            self.coherence_state = coherence_state
            self.mlcr = None

    ctx = MockContext()

    observation = observer.observe("test text", ctx, coherence_state)

    # Verify derived metrics are in observation
    assert observation.resonance_index == 0.75
    assert observation.tension_index == 0.3
    assert observation.arc_alignment_index == 0.8


def test_coherence_observer_snapshot_includes_derived_metrics():
    """
    Test that CoherenceObserver.snapshot() includes derived metrics in formulas section.
    """
    observer = CoherenceObserver()

    coherence_state = CoherenceState(
        convo_id="test_convo",
        turn_index=1,
    )
    coherence_state.resonance_index = 0.75
    coherence_state.tension_index = 0.3
    coherence_state.arc_alignment_index = 0.8
    coherence_state.smi_history = [0.7]
    coherence_state.coherence_score = 0.85
    coherence_state.persona_drift_score = 0.1
    coherence_state.semantic_stability_score = 0.9
    coherence_state.temporal_arc_score = 0.8
    coherence_state.mapper_volatility_score = 0.2

    class MockContext:
        def __init__(self):
            self.coherence_state = coherence_state
            self.mlcr = None

    ctx = MockContext()
    observer.observe("test text", ctx, coherence_state)

    snapshot = observer.snapshot()

    assert "formulas" in snapshot
    formulas = snapshot["formulas"]
    assert "resonance_index" in formulas
    assert formulas["resonance_index"] == 0.75
    assert "tension_index" in formulas
    assert formulas["tension_index"] == 0.3
    assert "arc_alignment_index" in formulas
    assert formulas["arc_alignment_index"] == 0.8


def test_unified_output_derived_metrics():
    """
    Test that derived metrics appear in UnifiedOutput formulas.derived section.
    """
    from agentic.api.unified_api import build_unified_output

    # Create mock coherence state
    coherence_state = CoherenceState(
        convo_id="test_convo",
        turn_index=1,
    )
    coherence_state.resonance_index = 0.75
    coherence_state.tension_index = 0.3
    coherence_state.arc_alignment_index = 0.8
    coherence_state.smi_history = [0.7]

    # Create mock context
    class MockContext:
        def __init__(self):
            self.coherence_state = coherence_state
            self.fusion = None
            self.dha = None
            self.mlcr = None
            self.mapper_profile = None
            self.coherence_report = {
                "coherence_score": 0.85,
                "turn_number": 1,
                "tier": "hybrid",
                "domain": "test",
            }

    ctx = MockContext()

    unified = build_unified_output("test output", ctx)

    # Check formulas section
    assert unified.formulas is not None
    assert "derived" in unified.formulas
    derived = unified.formulas["derived"]
    assert derived["resonance_index"] == 0.75
    assert derived["tension_index"] == 0.3
    assert derived["arc_alignment_index"] == 0.8


def test_dilchat_response_includes_derived_metrics():
    """
    Test that DILchat response includes derived metrics in formulas field.
    """
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    unified_output = {
        "text": "test response",
        "coherence": {
            "coherence_score": 0.85,
            "persona_drift_score": 0.1,
            "temporal_arc_score": 0.8,
        },
        "metadata": {"domain": "test"},
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "formulas": {
            "smi": 0.7,
            "delta_smi": 0.1,
            "derived": {
                "resonance_index": 0.75,
                "tension_index": 0.3,
                "arc_alignment_index": 0.8,
            },
        },
    }

    policy_flags = {
        "stability_status": "stable",
        "needs_grounding": False,
    }

    response = build_dilchat_response(unified_output, policy_flags, "test")

    # Check formulas field
    assert response.formulas is not None
    assert "derived" in response.formulas
    derived = response.formulas["derived"]
    assert derived["resonance_index"] == 0.75
    assert derived["tension_index"] == 0.3
    assert derived["arc_alignment_index"] == 0.8


def test_dilchat_no_badges_from_derived_metrics():
    """
    Test that derived metrics do NOT generate new badges (Phase 3 constraint).
    """
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    # High-resonance scenario
    unified_output = {
        "text": "test response",
        "coherence": {
            "coherence_score": 0.85,
            "persona_drift_score": 0.1,
            "temporal_arc_score": 0.8,
        },
        "metadata": {"domain": "test"},
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "formulas": {
            "derived": {
                "resonance_index": 0.95,  # Very high
                "tension_index": 0.05,    # Very low
                "arc_alignment_index": 0.9,  # Very high
            },
        },
    }

    policy_flags = {
        "stability_status": "stable",
    }

    response = build_dilchat_response(unified_output, policy_flags, "test")

    # Check that badges don't reference derived metrics
    for badge in response.badges:
        assert "resonance" not in badge.label.lower()
        assert "tension_index" not in badge.label.lower()
        assert "arc_alignment" not in badge.label.lower()


def test_dilchat_no_hints_from_derived_metrics():
    """
    Test that derived metrics do NOT generate new hints (Phase 3 constraint).
    """
    from symbolu_core.adapter.dilchat_adapter import build_dilchat_response

    # High-tension scenario
    unified_output = {
        "text": "test response",
        "coherence": {
            "coherence_score": 0.5,
            "persona_drift_score": 0.3,
            "temporal_arc_score": 0.6,
        },
        "metadata": {"domain": "test"},
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "formulas": {
            "derived": {
                "resonance_index": 0.2,   # Very low
                "tension_index": 0.95,    # Very high
                "arc_alignment_index": 0.3,  # Low
            },
        },
    }

    policy_flags = {
        "stability_status": "fragmented",
    }

    response = build_dilchat_response(unified_output, policy_flags, "test")

    # Check that hints don't reference derived metrics
    for hint in response.hints:
        assert "resonance" not in hint.code.lower()
        assert "tension_index" not in hint.code.lower()
        assert "arc_alignment" not in hint.code.lower()


# ==============================================================================
# Test Group 4: Behavioral Invariance
# ==============================================================================


def test_derived_metrics_do_not_affect_coherence_score():
    """
    Test that derived metrics do NOT affect the overall coherence_score calculation.

    This is critical: Phase 3 metrics are observation-only.
    """
    engine = CoherenceEngine(window=10)

    # Create two identical states
    state1 = CoherenceState(convo_id="test1", turn_index=0)
    state1.domain_history = ["test"]
    state1.mapper_profile_history = [{"resolution_level": "medium"}]
    state1.smi_history = [0.7]
    state1.bhava_id_history = [3]
    state1.bhava_direction_history = ["upward"]
    state1.tension_history = [0.3]
    state1.temporal_flags_history = [{"tension_corridor": False}]
    state1.delta_smi_history = [0.1]
    state1.bhava_gap_history = [0.2]
    state1.tension_corridor_history = [0.3]

    state2 = CoherenceState(convo_id="test2", turn_index=0)
    state2.domain_history = ["test"]
    state2.mapper_profile_history = [{"resolution_level": "medium"}]
    state2.smi_history = [0.7]
    state2.bhava_id_history = [3]
    state2.bhava_direction_history = ["upward"]
    state2.tension_history = [0.3]
    state2.temporal_flags_history = [{"tension_corridor": False}]
    state2.delta_smi_history = [0.1]
    state2.bhava_gap_history = [0.2]
    state2.tension_corridor_history = [0.3]

    # Compute derived metrics for both
    engine._compute_persona_drift(state1)
    engine._compute_semantic_stability(state1, {})
    engine._compute_mapper_volatility(state1)
    engine._compute_temporal_arc(state1)
    state1.coherence_score = engine._compute_overall_coherence(state1)
    engine._update_derived_formula_metrics(state1)

    engine._compute_persona_drift(state2)
    engine._compute_semantic_stability(state2, {})
    engine._compute_mapper_volatility(state2)
    engine._compute_temporal_arc(state2)
    state2.coherence_score = engine._compute_overall_coherence(state2)
    engine._update_derived_formula_metrics(state2)

    # Assert coherence_score is identical despite derived metrics being computed
    assert state1.coherence_score == state2.coherence_score

    # But derived metrics should exist
    assert state1.resonance_index is not None
    assert state2.resonance_index is not None


def test_derived_metrics_do_not_affect_existing_scores():
    """
    Test that existing component scores are unchanged by derived metrics.
    """
    engine = CoherenceEngine(window=10)

    state = CoherenceState(convo_id="test", turn_index=0)
    state.domain_history = ["test"]
    state.mapper_profile_history = [{"resolution_level": "medium"}]
    state.smi_history = [0.7]
    state.bhava_id_history = [3]
    state.bhava_direction_history = ["upward"]
    state.tension_history = [0.3]
    state.temporal_flags_history = [{"tension_corridor": False}]
    state.delta_smi_history = [0.1]
    state.bhava_gap_history = [0.2]
    state.tension_corridor_history = [0.3]

    # Compute existing scores BEFORE derived metrics
    persona_drift_before = engine._compute_persona_drift(state)
    semantic_stability_before = engine._compute_semantic_stability(state, {})
    mapper_volatility_before = engine._compute_mapper_volatility(state)
    temporal_arc_before = engine._compute_temporal_arc(state)
    coherence_before = engine._compute_overall_coherence(state)

    # Now compute derived metrics
    engine._update_derived_formula_metrics(state)

    # Recompute existing scores AFTER derived metrics
    persona_drift_after = engine._compute_persona_drift(state)
    semantic_stability_after = engine._compute_semantic_stability(state, {})
    mapper_volatility_after = engine._compute_mapper_volatility(state)
    temporal_arc_after = engine._compute_temporal_arc(state)
    coherence_after = engine._compute_overall_coherence(state)

    # Assert no changes
    assert persona_drift_before == persona_drift_after
    assert semantic_stability_before == semantic_stability_after
    assert mapper_volatility_before == mapper_volatility_after
    assert temporal_arc_before == temporal_arc_after
    assert coherence_before == coherence_after


def test_derived_metrics_json_serialization():
    """
    Test that derived metrics are JSON-safe and serialize correctly.
    """
    from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObservation
    import json

    observation = CoherenceObservation(
        coherence_score=0.85,
        persona_drift_score=0.1,
        semantic_stability_score=0.9,
        temporal_arc_score=0.8,
        mapper_volatility_score=0.2,
        turn_number=1,
        tier="hybrid",
        domain="test",
        active_mappers=["HRM", "LCM"],
        resonance_index=0.75,
        tension_index=0.3,
        arc_alignment_index=0.8,
    )

    # Convert to dict
    obs_dict = observation.to_dict()

    # Verify JSON serialization
    json_str = json.dumps(obs_dict)
    assert isinstance(json_str, str)

    # Deserialize and check values
    deserialized = json.loads(json_str)
    assert deserialized["resonance_index"] == 0.75
    assert deserialized["tension_index"] == 0.3
    assert deserialized["arc_alignment_index"] == 0.8
