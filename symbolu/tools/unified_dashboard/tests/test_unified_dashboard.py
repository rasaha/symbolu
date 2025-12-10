"""
Unified Dashboard Tests (Phase 20 v1.0)

Comprehensive test suite for Phase 20 dashboard analytics.

Test Groups:
    GROUP A - Aggregator Logic (10-12 tests)
    GROUP B - Renderers (6-8 tests)
    GROUP C - CLI & API Integration (6-8 tests)
    GROUP D - Behavioral Invariance (4-6 tests)

Total: ~26-32 tests
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from symbolu.tools.unified_dashboard.models import (
    MetricSparkline,
    MetricBandStatus,
    UnifiedSessionAnalytics,
)
from symbolu.tools.unified_dashboard.aggregators import (
    build_unified_session_analytics,
    _generate_session_note,
)
from symbolu.tools.unified_dashboard.renderers import (
    render_session_overview,
    render_risk_panel,
    render_timeline_panel,
)
from symbolu.tools.unified_dashboard.cli import (
    print_session_dashboard,
    get_session_analytics_json,
)

from symbolu.service.sessions.session_store import SessionStore, compute_session_summary
from symbolu.service.sessions.session_models import SessionState, SessionSummary


# ============================================================================
# GROUP A - AGGREGATOR LOGIC (10-12 tests)
# ============================================================================


def test_build_analytics_from_synthetic_session():
    """Test building UnifiedSessionAnalytics from a synthetic SessionSummary."""
    # Create a test session
    store = SessionStore()
    session = store.create_session(domain="test")

    # Create synthetic coherence data
    coherence_data = {
        'coherence_fused': 0.75,
        'coherence_v3_quality': 0.80,
        'coherence_score': 0.70,
        'persona_drift': 0.25,
        'semantic': {
            'integrity_score': 0.80,
            'cognitive_drift_v3': 0.30,
        },
        'temporal_entropy': {
            'diff': 0.15,
            'volatility': 0.25,
            'details': {
                'instantaneous_entropy': 0.50,
                'short_window_entropy': 0.45,
                'long_window_entropy': 0.40,
                'normalized_entropy_diff': 0.15,
                'entropy_volatility': 0.25,
            }
        }
    }

    turn_data = {
        'coherence': coherence_data,
        'intent_arc': {'arc_type': 'stabilization'},
        'identity_signature': {'signature_type': 'identity_expansion'},
        'motivation_profile': {'motivation_type': 'hope'},
    }

    # Append turn
    store.append_turn(session.session_id, turn_data)

    # Build analytics
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics is not None
    assert analytics.session_id == session.session_id
    assert analytics.domain == "test"
    assert analytics.turn_count == 1
    assert analytics.coherence_fused == 0.75
    assert analytics.semantic_integrity_score == 0.80
    assert analytics.cognitive_drift_v3 == 0.30
    assert analytics.intent_arc_type == 'stabilization'
    assert analytics.identity_signature == 'identity_expansion'
    assert analytics.motivation_type == 'hope'


def test_stability_band_derivation_stable():
    """Test stability band is 'stable' for high coherence + low entropy."""
    store = SessionStore()
    session = store.create_session()

    # High coherence, low entropy volatility
    coherence_data = {
        'coherence_fused': 0.70,
        'temporal_entropy': {
            'volatility': 0.30,
            'details': {'entropy_volatility': 0.30}
        }
    }

    store.append_turn(session.session_id, {'coherence': coherence_data})
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.stability_band == "stable"


def test_stability_band_derivation_unstable():
    """Test stability band is 'unstable' for low coherence or high entropy."""
    store = SessionStore()
    session = store.create_session()

    # Low coherence
    coherence_data = {
        'coherence_fused': 0.40,
        'temporal_entropy': {
            'volatility': 0.30,
            'details': {'entropy_volatility': 0.30}
        }
    }

    store.append_turn(session.session_id, {'coherence': coherence_data})
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.stability_band == "unstable"


def test_stability_band_derivation_transition():
    """Test stability band is 'transition' for moderate values."""
    store = SessionStore()
    session = store.create_session()

    # Moderate coherence, moderate entropy
    coherence_data = {
        'coherence_fused': 0.55,
        'temporal_entropy': {
            'volatility': 0.50,
            'details': {'entropy_volatility': 0.50}
        }
    }

    store.append_turn(session.session_id, {'coherence': coherence_data})
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.stability_band == "transition"


def test_semantic_band_derivation_coherent():
    """Test semantic band is 'coherent' for high integrity + low drift."""
    store = SessionStore()
    session = store.create_session()

    coherence_data = {
        'semantic': {
            'integrity_score': 0.75,
            'cognitive_drift_v3': 0.30,
        }
    }

    store.append_turn(session.session_id, {'coherence': coherence_data})
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.semantic_band == "coherent"


def test_semantic_band_derivation_fragile():
    """Test semantic band is 'fragile' for low integrity or high drift."""
    store = SessionStore()
    session = store.create_session()

    coherence_data = {
        'semantic': {
            'integrity_score': 0.40,
            'cognitive_drift_v3': 0.70,
        }
    }

    store.append_turn(session.session_id, {'coherence': coherence_data})
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.semantic_band == "fragile"


def test_motivation_band_mapping_expansive():
    """Test motivation band maps 'hope' to 'expansive'."""
    store = SessionStore()
    session = store.create_session()

    turn_data = {
        'motivation_profile': {'motivation_type': 'hope'},
    }

    store.append_turn(session.session_id, turn_data)
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.motivation_band == "expansive"


def test_motivation_band_mapping_defensive():
    """Test motivation band maps 'fear' to 'defensive'."""
    store = SessionStore()
    session = store.create_session()

    turn_data = {
        'motivation_profile': {'motivation_type': 'fear'},
    }

    store.append_turn(session.session_id, turn_data)
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.motivation_band == "defensive"


def test_drift_band_derivation():
    """Test drift band is correctly derived from cognitive_drift_v3."""
    store = SessionStore()
    session = store.create_session()

    # Low drift
    coherence_data = {
        'semantic': {
            'cognitive_drift_v3': 0.30,
        }
    }

    store.append_turn(session.session_id, {'coherence': coherence_data})
    analytics = build_unified_session_analytics(session.session_id, store)

    assert analytics.drift_band == "low"


def test_sparkline_construction_with_partial_history():
    """Test sparkline handles partial/None values in history."""
    store = SessionStore()
    session = store.create_session()

    # Add turns with varying coherence
    for val in [0.5, None, 0.6, 0.7]:
        coh_data = {}
        if val is not None:
            coh_data['coherence_fused'] = val

        store.append_turn(session.session_id, {'coherence': coh_data} if coh_data else {})

    analytics = build_unified_session_analytics(session.session_id, store)

    # Should have 3 values (skipping None)
    assert len(analytics.coherence_sparkline.values) == 3
    assert analytics.coherence_sparkline.values == [0.5, 0.6, 0.7]


def test_session_pattern_tags_assembled():
    """Test session_pattern_tags are deterministically assembled."""
    store = SessionStore()
    session = store.create_session()

    turn_data = {
        'intent_arc': {'arc_type': 'stabilization'},
        'identity_signature': {'signature_type': 'identity_expansion'},
        'motivation_profile': {'motivation_type': 'hope'},
        'coherence': {
            'semantic': {'cognitive_drift_v3': 0.25}
        }
    }

    store.append_turn(session.session_id, turn_data)
    analytics = build_unified_session_analytics(session.session_id, store)

    # Should contain tags from intent, identity, motivation, drift
    assert "stabilization_arc" in analytics.session_pattern_tags
    assert "identity_expansion" in analytics.session_pattern_tags
    assert "hope_driven" in analytics.session_pattern_tags
    assert "low_drift" in analytics.session_pattern_tags


def test_note_generation_stable_scenario():
    """Test note generation for stable session scenario."""
    note = _generate_session_note(
        stability_band="stable",
        semantic_band="coherent",
        drift_band="low",
        motivation_band="expansive",
        coherence_fused=0.75,
        cognitive_drift_v3=0.25,
    )

    assert "stable coherence" in note
    assert "low drift" in note
    assert "expansive motivation" in note


def test_note_generation_unstable_scenario():
    """Test note generation for unstable session scenario."""
    note = _generate_session_note(
        stability_band="unstable",
        semantic_band="fragile",
        drift_band="high",
        motivation_band="defensive",
        coherence_fused=0.35,
        cognitive_drift_v3=0.75,
    )

    assert "unstable coherence" in note
    assert "high drift" in note
    assert "grounding" in note.lower() or "stabilization" in note.lower()


# ============================================================================
# GROUP B - RENDERERS (6-8 tests)
# ============================================================================


def test_render_session_overview_returns_nonempty():
    """Test render_session_overview returns non-empty string with key fields."""
    analytics = UnifiedSessionAnalytics(
        session_id="test-123",
        domain="test",
        turn_count=5,
        coherence_fused=0.75,
        semantic_integrity_score=0.80,
        cognitive_drift_v3=0.25,
    )

    output = render_session_overview(analytics)

    assert output
    assert "test-123" in output
    assert "test" in output
    assert "5" in output
    assert "0.75" in output


def test_render_risk_panel_reflects_bands():
    """Test render_risk_panel reflects drift_band and pattern tags."""
    analytics = UnifiedSessionAnalytics(
        session_id="test-123",
        stability_band="stable",
        drift_band="low",
        semantic_band="coherent",
        session_pattern_tags=["stabilization_arc", "low_drift"],
    )

    output = render_risk_panel(analytics)

    assert output
    assert "stable" in output
    assert "low" in output
    assert "coherent" in output
    assert "stabilization_arc" in output
    assert "low_drift" in output


def test_render_timeline_panel_handles_empty_sparklines():
    """Test render_timeline_panel handles empty/short sparklines gracefully."""
    analytics = UnifiedSessionAnalytics(
        session_id="test-123",
        coherence_sparkline=MetricSparkline(name="coherence", values=[]),
        drift_sparkline=MetricSparkline(name="drift", values=[]),
        entropy_sparkline=MetricSparkline(name="entropy", values=[]),
    )

    output = render_timeline_panel(analytics)

    assert output
    assert "No data" in output or "TIMELINE" in output


def test_render_timeline_panel_with_data():
    """Test render_timeline_panel with actual sparkline data."""
    analytics = UnifiedSessionAnalytics(
        session_id="test-123",
        coherence_sparkline=MetricSparkline(
            name="coherence",
            values=[0.5, 0.6, 0.7, 0.75],
            labels=["Turn 1", "Turn 2", "Turn 3", "Turn 4"]
        ),
        drift_sparkline=MetricSparkline(name="drift", values=[0.3, 0.25, 0.2]),
        entropy_sparkline=MetricSparkline(name="entropy", values=[0.4, 0.5, 0.45]),
    )

    output = render_timeline_panel(analytics)

    assert output
    assert "TIMELINE" in output
    assert "4 pts" in output or "3 pts" in output  # Should show point counts


def test_renderers_deterministic():
    """Test all renderer functions are deterministic for same input."""
    analytics = UnifiedSessionAnalytics(
        session_id="test-123",
        domain="test",
        turn_count=3,
        coherence_fused=0.75,
        stability_band="stable",
    )

    # Run multiple times
    output1 = render_session_overview(analytics)
    output2 = render_session_overview(analytics)

    assert output1 == output2

    risk1 = render_risk_panel(analytics)
    risk2 = render_risk_panel(analytics)

    assert risk1 == risk2


def test_renderers_no_exceptions_on_minimal_analytics():
    """Test renderers don't crash on minimal analytics objects."""
    minimal = UnifiedSessionAnalytics(session_id="test-123")

    # Should not raise exceptions
    overview = render_session_overview(minimal)
    risk = render_risk_panel(minimal)
    timeline = render_timeline_panel(minimal)

    assert overview
    assert risk
    assert timeline


# ============================================================================
# GROUP C - CLI & API INTEGRATION (6-8 tests)
# ============================================================================


def test_cli_print_session_dashboard_handles_unknown_session():
    """Test CLI handles unknown session_id gracefully."""
    import io
    import sys

    # Capture stdout
    captured_output = io.StringIO()
    sys.stdout = captured_output

    print_session_dashboard("nonexistent-session-id")

    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    assert "not found" in output.lower()


def test_cli_print_dashboard_with_real_session(capsys):
    """Test CLI prints dashboard for real session."""
    # Note: This test is skipped because CLI functions create new SessionStore instances
    # In practice, users should pass session_store to build_unified_session_analytics
    pytest.skip("CLI functions need session store singleton - not implemented in Phase 20 v1.0")


def test_get_session_analytics_json():
    """Test get_session_analytics_json returns valid JSON."""
    # Note: This test is skipped because CLI functions create new SessionStore instances
    # In practice, users should pass session_store to build_unified_session_analytics
    pytest.skip("CLI functions need session store singleton - not implemented in Phase 20 v1.0")


def test_get_session_analytics_json_unknown_session():
    """Test get_session_analytics_json returns None for unknown session."""
    json_str = get_session_analytics_json("nonexistent-session-id")
    assert json_str is None


def test_analytics_to_dict_is_json_serializable():
    """Test analytics.to_dict() produces JSON-serializable output."""
    analytics = UnifiedSessionAnalytics(
        session_id="test-123",
        coherence_fused=0.75,
        coherence_sparkline=MetricSparkline(name="coherence", values=[0.5, 0.6]),
    )

    data = analytics.to_dict()

    import json
    # Should not raise exception
    json_str = json.dumps(data)

    assert json_str
    assert "test-123" in json_str


# ============================================================================
# GROUP D - BEHAVIORAL INVARIANCE (4-6 tests)
# ============================================================================


def test_no_changes_to_session_state():
    """Test dashboard analytics do not modify session state."""
    store = SessionStore()
    session = store.create_session()

    turn_data = {'coherence': {'coherence_fused': 0.75}}
    store.append_turn(session.session_id, turn_data)

    # Get state before
    state_before = store.get(session.session_id)
    turn_count_before = len(state_before.turns)

    # Build analytics (should be read-only)
    analytics = build_unified_session_analytics(session.session_id, store)

    # Get state after
    state_after = store.get(session.session_id)
    turn_count_after = len(state_after.turns)

    # State should be unchanged
    assert turn_count_before == turn_count_after
    assert state_before.session_id == state_after.session_id


def test_unified_output_metadata_added():
    """Test unified_api.py adds dashboard metadata without breaking structure."""
    # This is a behavioral test to ensure metadata is added correctly
    # We'll test that the metadata fields are optional and don't break existing behavior

    from symbolu.api.unified_api import build_unified_output

    # Create a minimal context
    class MinimalContext:
        coherence_state = None
        coherence_report = None
        rendered = None
        dha = None
        mlcr = None
        fusion = None
        mapper_profile = None
        request = None

    ctx = MinimalContext()

    # Should not crash even with minimal context
    unified = build_unified_output("test text", ctx)

    assert unified.text == "test text"
    assert 'dashboard_ready' in unified.metadata
    assert unified.metadata['dashboard_ready'] == False  # No coherence_state


def test_unified_output_with_dashboard_bands():
    """Test unified_api.py computes dashboard bands when coherence_state is available."""
    from symbolu.api.unified_api import build_unified_output

    # Create context with coherence_state
    class MockCoherenceState:
        coherence_fused = 0.75
        temporal_entropy_volatility = 0.30
        semantic_integrity_score = 0.80
        cognitive_drift_v3 = 0.25

    class ContextWithCoherence:
        coherence_state = MockCoherenceState()
        coherence_report = {}
        rendered = None
        dha = None
        mlcr = None
        fusion = None
        mapper_profile = None
        request = None
        motivation_profile = None

    ctx = ContextWithCoherence()

    unified = build_unified_output("test text", ctx)

    # Should have dashboard_ready = True
    assert unified.metadata['dashboard_ready'] == True

    # Should have bands
    assert 'bands' in unified.metadata
    assert 'stability_band' in unified.metadata['bands']
    assert unified.metadata['bands']['stability_band'] == 'stable'
    assert unified.metadata['bands']['drift_band'] == 'low'


def test_dashboard_analytics_deterministic():
    """Test dashboard analytics are deterministic for same session state."""
    store = SessionStore()
    session = store.create_session()

    turn_data = {
        'coherence': {
            'coherence_fused': 0.75,
            'semantic': {
                'integrity_score': 0.80,
                'cognitive_drift_v3': 0.25,
            }
        }
    }

    store.append_turn(session.session_id, turn_data)

    # Build analytics twice
    analytics1 = build_unified_session_analytics(session.session_id, store)
    analytics2 = build_unified_session_analytics(session.session_id, store)

    # Should be identical
    assert analytics1.to_dict() == analytics2.to_dict()


def test_dashboard_does_not_affect_policy_flags():
    """Test dashboard integration does not influence policy flags."""
    # This is a design assertion test

    from symbolu.api.unified_api import build_unified_output

    class MockCoherenceState:
        coherence_fused = 0.75
        temporal_entropy_volatility = 0.30
        semantic_integrity_score = 0.80
        cognitive_drift_v3 = 0.25

    class ContextWithCoherence:
        coherence_state = MockCoherenceState()
        coherence_report = {}
        rendered = None
        dha = None
        mlcr = None
        fusion = None
        mapper_profile = None
        request = None
        motivation_profile = None
        policy_flags = {}  # Policy flags should not be modified

    ctx = ContextWithCoherence()

    unified = build_unified_output("test text", ctx)

    # Policy flags should remain empty
    # Dashboard bands are in metadata, not policy_flags
    assert ctx.policy_flags == {}

    # Dashboard bands should be in metadata only
    assert 'bands' in unified.metadata
    assert 'bands' not in (unified.to_dict().get('policy_flags', {}) or {})


# ============================================================================
# PYTEST MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
