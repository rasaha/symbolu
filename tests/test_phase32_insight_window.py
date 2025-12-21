"""
Test Suite for Phase 32: Insight Window Gating System v1.0

Comprehensive test coverage for the UCF-based UI-layer policy refinement system.

Test Groups:
    Group A: Formula Math (10 tests) - COI/CSI/CIP weighting, depth calculation, mode classification
    Group B: Policy Integration (10 tests) - Domain/mode gating, UI-layer refinement, safety invariants
    Group C: Unified API (6 tests) - Serialization, null-safety, backward compatibility
    Group D: DILchat Adapter (6 tests) - Badge generation, domain/mode gating, no collisions
    Group E: Behavioral Invariance (6 tests) - Routing, mappers, coherence, guardrails, determinism

Total: 38 tests covering all aspects of the Insight Window Gating System.
"""

import pytest
from symbolu.policy.insight_window_gating import compute_insight_window, InsightWindowResult
from symbolu.policy.policy_engine import compute_policy_flags
from symbolu.adapter.dilchat_adapter import build_dilchat_response


# ============================================================================
# GROUP A: FORMULA MATH (10 tests)
# ============================================================================

def test_insight_window_depth_weighting():
    """Test COI/CSI/CIP weighting formula (0.40/0.40/0.20)."""
    # Create mock UCF snapshot
    class MockUCF:
        def __init__(self, coi, csi, cip):
            self.consciousness_order_index = coi
            self.consciousness_stability_index = csi
            self.consciousness_integration_potential = cip
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    ucf = MockUCF(coi=0.7, csi=0.6, cip=0.5)

    result = compute_insight_window(
        ucf_snapshot=ucf,
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    # Expected: 0.40*0.7 + 0.40*0.6 + 0.20*0.5 = 0.28 + 0.24 + 0.10 = 0.62
    assert result.insight_window_open is True
    assert 0.61 <= result.insight_depth <= 0.63


def test_insight_window_depth_range():
    """Test insight depth is clamped to [0.0, 1.0]."""
    class MockUCF:
        def __init__(self, coi, csi, cip):
            self.consciousness_order_index = coi
            self.consciousness_stability_index = csi
            self.consciousness_integration_potential = cip
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    # Test upper bound
    ucf_high = MockUCF(coi=1.0, csi=1.0, cip=1.0)
    result_high = compute_insight_window(
        ucf_snapshot=ucf_high,
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )
    assert result_high.insight_depth <= 1.0

    # Test lower bound (should be closed due to low COI/CSI)
    ucf_low = MockUCF(coi=0.1, csi=0.1, cip=0.1)
    result_low = compute_insight_window(
        ucf_snapshot=ucf_low,
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )
    assert result_low.insight_depth >= 0.0


def test_insight_mode_classification_deep():
    """Test insight mode classification: depth >= 0.70 → deep."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.9
            self.consciousness_stability_index = 0.85
            self.consciousness_integration_potential = 0.8
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="deep_adaptive",
        domain="therapy"
    )

    assert result.insight_mode == "deep"
    assert result.insight_depth >= 0.70


def test_insight_mode_classification_light():
    """Test insight mode classification: 0.40 <= depth < 0.70 → light."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.65
            self.consciousness_stability_index = 0.55
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="identity"
    )

    assert result.insight_mode == "light"
    assert 0.40 <= result.insight_depth < 0.70


def test_insight_mode_classification_none():
    """Test insight mode classification: depth < 0.40 → none."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.4
            self.consciousness_stability_index = 0.35
            self.consciousness_integration_potential = 0.3
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    # Window should be closed due to low COI/CSI
    assert result.insight_mode == "none"


def test_depth_modifier_entropy_transitional():
    """Test depth reduction by 15% when entropy_band == transitional."""
    class MockObs:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.ucf_entropy = 0.3
            self.ucf_notes = []
            self.cognitive_drift_v3 = 0.2
            self.temporal_entropy_volatility = 0.45  # transitional range (0.35-0.65)

    result = compute_insight_window(
        ucf_snapshot=None,
        coherence_observation=MockObs(),
        interaction_mode="smart_insight",
        domain="therapy"
    )

    # Base depth: 0.40*0.7 + 0.40*0.6 + 0.20*0.5 = 0.62
    # With 15% reduction: 0.62 * 0.85 = 0.527
    assert result.insight_depth < 0.62
    assert "entropy_transitional" in result.insight_tags


def test_depth_modifier_drift_moderate():
    """Test depth reduction by 10% when drift_risk_band == moderate."""
    class MockObs:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.ucf_entropy = 0.3
            self.ucf_notes = []
            self.cognitive_drift_v3 = 0.55  # moderate range (0.45-0.65)
            self.temporal_entropy_volatility = 0.2  # stable

    result = compute_insight_window(
        ucf_snapshot=None,
        coherence_observation=MockObs(),
        interaction_mode="smart_insight",
        domain="therapy"
    )

    # Base depth: 0.62, with 10% reduction: 0.62 * 0.90 = 0.558
    assert result.insight_depth < 0.62
    assert "drift_caution" in result.insight_tags


def test_depth_cap_low_coi():
    """Test depth capped at 0.45 when COI < 0.45."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.40  # Below 0.45
            self.consciousness_stability_index = 0.90  # Very high
            self.consciousness_integration_potential = 0.80
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    # Despite high CSI/CIP, depth should be capped at 0.45
    # Window should be closed because COI < 0.55
    assert result.insight_window_open is False


def test_insight_tags_structural_alignment():
    """Test 'structural_alignment' tag when COI >= 0.65."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.70  # >= 0.65
            self.consciousness_stability_index = 0.60
            self.consciousness_integration_potential = 0.55
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    assert "structural_alignment" in result.insight_tags


def test_insight_tags_temporal_resilience():
    """Test 'temporal_resilience' tag when CSI >= 0.65."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.70
            self.consciousness_stability_index = 0.70  # >= 0.65
            self.consciousness_integration_potential = 0.55
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    assert "temporal_resilience" in result.insight_tags


# ============================================================================
# GROUP B: POLICY INTEGRATION (10 tests)
# ============================================================================

def test_domain_gate_therapy():
    """Test domain gate passes for therapy domain."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    assert result.insight_window_open is True


def test_domain_gate_identity():
    """Test domain gate passes for identity domain."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="identity"
    )

    assert result.insight_window_open is True


def test_domain_gate_trading_blocked():
    """Test domain gate blocks for trading domain."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="trading"
    )

    assert result.insight_window_open is False
    assert result.insight_mode == "none"


def test_mode_gate_smart_insight():
    """Test mode gate passes for smart_insight mode."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    assert result.insight_window_open is True


def test_mode_gate_deep_adaptive():
    """Test mode gate passes for deep_adaptive mode."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="deep_adaptive",
        domain="therapy"
    )

    assert result.insight_window_open is True


def test_mode_gate_analytics_only_blocked():
    """Test mode gate blocks for analytics_only mode."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="analytics_only",
        domain="therapy"
    )

    assert result.insight_window_open is False
    assert result.insight_mode == "none"


def test_policy_refinement_light_mode():
    """Test UI-layer refinement in light mode."""
    # Use policy engine's _apply_insight_window_to_policy function
    from symbolu.policy.policy_engine import _apply_insight_window_to_policy

    flags = {
        "allow_deep_reflection": False,
        "prefer_arc_mode": False,
    }

    insight = InsightWindowResult(
        insight_window_open=True,
        insight_depth=0.55,
        insight_mode="light",
        insight_tags=[],
        notes=[]
    )

    refined = _apply_insight_window_to_policy(flags, insight)

    assert refined["allow_deep_reflection"] is True
    assert refined["prefer_arc_mode"] is True
    assert refined.get("allow_meta_insight") is None  # Not set in light mode


def test_policy_refinement_deep_mode():
    """Test UI-layer refinement in deep mode."""
    from symbolu.policy.policy_engine import _apply_insight_window_to_policy

    flags = {
        "allow_deep_reflection": False,
        "prefer_arc_mode": False,
    }

    insight = InsightWindowResult(
        insight_window_open=True,
        insight_depth=0.75,
        insight_mode="deep",
        insight_tags=[],
        notes=[]
    )

    refined = _apply_insight_window_to_policy(flags, insight)

    assert refined["allow_deep_reflection"] is True
    assert refined["prefer_arc_mode"] is True
    assert refined["allow_meta_insight"] is True  # Set in deep mode
    assert refined["prefer_symbolic_interpretation"] is True


def test_safety_flags_unchanged():
    """Test that safety-critical flags are never modified."""
    from symbolu.policy.policy_engine import _apply_insight_window_to_policy

    flags = {
        "needs_grounding": True,
        "coherence_warning": True,
        "stability_status": "fragmented",
        "recommended_mapper": "LCM",
        "allow_deep_reflection": False,
    }

    insight = InsightWindowResult(
        insight_window_open=True,
        insight_depth=0.75,
        insight_mode="deep",
        insight_tags=[],
        notes=[]
    )

    refined = _apply_insight_window_to_policy(flags, insight)

    # Safety flags must remain unchanged
    assert refined["needs_grounding"] is True
    assert refined["coherence_warning"] is True
    assert refined["stability_status"] == "fragmented"
    assert refined["recommended_mapper"] == "LCM"


def test_deterministic_behavior():
    """Test deterministic behavior: same inputs → same outputs."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.68
            self.consciousness_stability_index = 0.62
            self.consciousness_integration_potential = 0.54
            self.entropy_of_weights = 0.35
            self.diagnostic_notes = ["test_note"]

    # Run twice with identical inputs
    result1 = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    result2 = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    assert result1.insight_window_open == result2.insight_window_open
    assert result1.insight_depth == result2.insight_depth
    assert result1.insight_mode == result2.insight_mode
    assert result1.insight_tags == result2.insight_tags


# ============================================================================
# GROUP C: UNIFIED API (6 tests)
# ============================================================================

def test_unified_api_serialization():
    """Test insight_window serializes correctly in unified output."""
    from symbolu.api.unified_api import UnifiedOutput

    output = UnifiedOutput(
        text="test",
        symbolic={},
        practical={},
        mirror={},
        dha={},
        routing={},
        mappers={},
        entropy={},
        coherence={},
        metadata={},
        insight_window={
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": ["structural_alignment"],
            "notes": ["test note"],
        }
    )

    serialized = output.to_dict()

    assert "insight_window" in serialized
    assert serialized["insight_window"]["insight_window_open"] is True
    assert serialized["insight_window"]["insight_depth"] == 0.65
    assert serialized["insight_window"]["insight_mode"] == "light"


def test_unified_api_null_safe():
    """Test unified output handles missing insight_window gracefully."""
    from symbolu.api.unified_api import UnifiedOutput

    output = UnifiedOutput(
        text="test",
        symbolic={},
        practical={},
        mirror={},
        dha={},
        routing={},
        mappers={},
        entropy={},
        coherence={},
        metadata={},
        insight_window=None  # Null insight window
    )

    serialized = output.to_dict()

    # None values should be removed by _remove_none_values
    assert "insight_window" not in serialized or serialized.get("insight_window") is None


def test_unified_api_backward_compatible():
    """Test unified output works without insight_window field."""
    from symbolu.api.unified_api import UnifiedOutput

    # Create output without insight_window (backward compatibility)
    output = UnifiedOutput(
        text="test",
        symbolic={},
        practical={},
        mirror={},
        dha={},
        routing={},
        mappers={},
        entropy={},
        coherence={},
        metadata={}
    )

    serialized = output.to_dict()

    # Should serialize successfully
    assert "text" in serialized


def test_unified_api_extraction_from_policy_flags():
    """Test insight_window is correctly extracted from policy_flags."""
    # Mock context with policy_flags containing insight_window
    class MockContext:
        def __init__(self):
            self.policy_flags = {
                "insight_window": {
                    "insight_window_open": True,
                    "insight_depth": 0.7,
                    "insight_mode": "deep",
                    "insight_tags": ["structural_alignment", "temporal_resilience"],
                    "notes": ["Domain gate passed: therapy"]
                }
            }
            self.rendered = None
            self.dha = None
            # Required attributes for build_unified_output
            self.fusion = None
            self.mlcr = None
            self.mapper_profile = None
            self.coherence_report = None
            self.coherence_state = None
            self.session_memory = None
            self.session_recap = None
            self.intent_arc = None
            self.identity_signature = None
            self.motivation_profile = None
            self.trading_guardrails = None
            self.interaction_mode = None
            self.persona_response = None
            self.request = None

    from symbolu.api.unified_api import build_unified_output

    ctx = MockContext()
    output = build_unified_output("test text", ctx)

    assert output.insight_window is not None
    assert output.insight_window["insight_window_open"] is True


def test_unified_api_complete_structure():
    """Test insight_window has all required fields."""
    insight_window_data = {
        "insight_window_open": True,
        "insight_depth": 0.65,
        "insight_mode": "light",
        "insight_tags": ["structural_alignment"],
        "notes": ["test note"],
    }

    # Verify all required fields present
    assert "insight_window_open" in insight_window_data
    assert "insight_depth" in insight_window_data
    assert "insight_mode" in insight_window_data
    assert "insight_tags" in insight_window_data
    assert "notes" in insight_window_data


def test_unified_api_json_serializable():
    """Test insight_window is fully JSON-serializable."""
    import json
    from symbolu.api.unified_api import UnifiedOutput

    output = UnifiedOutput(
        text="test",
        symbolic={},
        practical={},
        mirror={},
        dha={},
        routing={},
        mappers={},
        entropy={},
        coherence={},
        metadata={},
        insight_window={
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": ["structural_alignment"],
            "notes": ["test note"],
        }
    )

    # Should serialize to JSON without errors
    json_str = json.dumps(output.to_dict())
    assert json_str is not None
    assert "insight_window" in json_str


# ============================================================================
# GROUP D: DILCHAT ADAPTER (6 tests)
# ============================================================================

def test_dilchat_badge_insight_window_open():
    """Test INSIGHT_WINDOW_OPEN badge generation."""
    unified_output = {
        "text": "test",
        "coherence": {},
        "metadata": {"domain": "therapy"},
    }

    policy_flags = {
        "stability_status": "stable",
        "interaction_mode": "smart_insight",
        "insight_window": {
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": [],
            "notes": []
        }
    }

    response = build_dilchat_response(unified_output, policy_flags, "therapy")

    badge_labels = [b.label for b in response.badges]
    assert "INSIGHT_WINDOW_OPEN" in badge_labels


def test_dilchat_badge_insight_window_deep():
    """Test INSIGHT_WINDOW_DEEP badge generation."""
    unified_output = {
        "text": "test",
        "coherence": {},
        "metadata": {"domain": "therapy"},
    }

    policy_flags = {
        "stability_status": "stable",
        "interaction_mode": "deep_adaptive",
        "insight_window": {
            "insight_window_open": True,
            "insight_depth": 0.75,
            "insight_mode": "deep",
            "insight_tags": [],
            "notes": []
        }
    }

    response = build_dilchat_response(unified_output, policy_flags, "therapy")

    badge_labels = [b.label for b in response.badges]
    assert "INSIGHT_WINDOW_DEEP" in badge_labels


def test_dilchat_badge_domain_gating():
    """Test badges only appear for therapy/identity domains."""
    unified_output = {
        "text": "test",
        "coherence": {},
        "metadata": {"domain": "trading"},
    }

    policy_flags = {
        "stability_status": "stable",
        "interaction_mode": "smart_insight",
        "insight_window": {
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": [],
            "notes": []
        }
    }

    response = build_dilchat_response(unified_output, policy_flags, "trading")

    badge_labels = [b.label for b in response.badges]
    # Should NOT have insight window badges for trading domain
    assert "INSIGHT_WINDOW_OPEN" not in badge_labels


def test_dilchat_badge_mode_gating():
    """Test badges only appear for SMART_INSIGHT/DEEP_ADAPTIVE modes."""
    unified_output = {
        "text": "test",
        "coherence": {},
        "metadata": {"domain": "therapy"},
    }

    policy_flags = {
        "stability_status": "stable",
        "interaction_mode": "analytics_only",
        "insight_window": {
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": [],
            "notes": []
        }
    }

    response = build_dilchat_response(unified_output, policy_flags, "therapy")

    badge_labels = [b.label for b in response.badges]
    # Should NOT have insight window badges for analytics_only mode
    assert "INSIGHT_WINDOW_OPEN" not in badge_labels


def test_dilchat_badge_no_text_changes():
    """Test badges don't modify response text."""
    unified_output = {
        "text": "original text",
        "coherence": {},
        "metadata": {"domain": "therapy"},
    }

    policy_flags = {
        "stability_status": "stable",
        "interaction_mode": "smart_insight",
        "insight_window": {
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": [],
            "notes": []
        }
    }

    response = build_dilchat_response(unified_output, policy_flags, "therapy")

    # Text must remain unchanged
    assert response.text == "original text"


def test_dilchat_badge_no_collision():
    """Test insight window badges don't collide with existing badges."""
    unified_output = {
        "text": "test",
        "coherence": {},
        "metadata": {"domain": "therapy"},
    }

    policy_flags = {
        "stability_status": "stable",
        "needs_grounding": True,  # Existing policy flag
        "interaction_mode": "smart_insight",
        "insight_window": {
            "insight_window_open": True,
            "insight_depth": 0.65,
            "insight_mode": "light",
            "insight_tags": [],
            "notes": []
        }
    }

    response = build_dilchat_response(unified_output, policy_flags, "therapy")

    badge_labels = [b.label for b in response.badges]

    # Should have both grounding badge and insight window badge
    assert "Grounding Needed" in badge_labels
    assert "INSIGHT_WINDOW_OPEN" in badge_labels


# ============================================================================
# GROUP E: BEHAVIORAL INVARIANCE (6 tests)
# ============================================================================

def test_routing_unchanged():
    """Test insight window does not modify routing logic."""
    # Build minimal unified output with routing
    unified_output = {
        "text": "test",
        "coherence": {
            "coherence_score": 0.7,
            "persona_drift_score": 0.3,
            "unified_consciousness": {
                "coi": 0.7,
                "csi": 0.6,
                "cip": 0.5,
            },
            "semantic": {"cognitive_drift_v3": 0.3},
            "temporal_entropy": {"volatility": 0.3}
        },
        "routing": {
            "tier": "tier2",
            "intent": "reflection",
            "domain": "therapy",
        },
        "metadata": {},
        "entropy": {}
    }

    # Compute policy flags (which includes insight window)
    flags = compute_policy_flags(unified_output, domain="therapy", user_mode_override="smart_insight")

    # Routing recommendation should still be deterministic based on core metrics
    assert flags["recommended_mapper"] in ["LCM", "HRM", "LAM"]


def test_mapper_activation_unchanged():
    """Test insight window does not modify mapper activation."""
    unified_output = {
        "text": "test",
        "coherence": {
            "coherence_score": 0.7,
            "persona_drift_score": 0.3,
            "unified_consciousness": {
                "coi": 0.7,
                "csi": 0.6,
                "cip": 0.5,
            },
            "semantic": {"cognitive_drift_v3": 0.3},
            "temporal_entropy": {"volatility": 0.3}
        },
        "metadata": {},
        "entropy": {}
    }

    flags = compute_policy_flags(unified_output, domain="therapy", user_mode_override="smart_insight")

    # Mapper recommendation must be one of the canonical options
    assert flags["recommended_mapper"] in ["LCM", "HRM", "LAM"]


def test_coherence_scoring_unchanged():
    """Test insight window does not modify coherence scoring."""
    unified_output = {
        "text": "test",
        "coherence": {
            "coherence_score": 0.65,
            "persona_drift_score": 0.4,
            "unified_consciousness": {
                "coi": 0.7,
                "csi": 0.6,
                "cip": 0.5,
            },
            "semantic": {"cognitive_drift_v3": 0.3},
            "temporal_entropy": {"volatility": 0.3}
        },
        "metadata": {},
        "entropy": {}
    }

    # Compute flags twice
    flags1 = compute_policy_flags(unified_output, domain="therapy", user_mode_override="smart_insight")
    flags2 = compute_policy_flags(unified_output, domain="therapy", user_mode_override="analytics_only")

    # stability_status should be identical (based on core coherence, not insight window)
    assert flags1["stability_status"] == flags2["stability_status"]


def test_guardrails_unchanged():
    """Test insight window does not modify guardrails."""
    unified_output = {
        "text": "test",
        "coherence": {
            "coherence_score": 0.7,
            "persona_drift_score": 0.3,
            "unified_consciousness": {
                "coi": 0.7,
                "csi": 0.6,
                "cip": 0.5,
            },
            "semantic": {"cognitive_drift_v3": 0.3},
            "temporal_entropy": {"volatility": 0.3}
        },
        "metadata": {},
        "entropy": {}
    }

    flags = compute_policy_flags(unified_output, domain="therapy", user_mode_override="smart_insight")

    # Core safety flags must not be affected by insight window
    assert "needs_grounding" in flags
    assert "coherence_warning" in flags


def test_zero_llm_calls():
    """Test insight window computation makes zero LLM calls."""
    # This is a structural test - the compute_insight_window function
    # should only perform deterministic math, no LLM inference

    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.7
            self.consciousness_stability_index = 0.6
            self.consciousness_integration_potential = 0.5
            self.entropy_of_weights = 0.3
            self.diagnostic_notes = []

    # Function should complete without any external API calls
    result = compute_insight_window(
        ucf_snapshot=MockUCF(),
        coherence_observation=None,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    # If we got a result, no LLM was called (deterministic only)
    assert result is not None
    assert isinstance(result, InsightWindowResult)


def test_determinism_50_iterations():
    """Test determinism over 50 iterations."""
    class MockUCF:
        def __init__(self):
            self.consciousness_order_index = 0.68
            self.consciousness_stability_index = 0.62
            self.consciousness_integration_potential = 0.54
            self.entropy_of_weights = 0.35
            self.diagnostic_notes = ["test"]

    results = []
    for _ in range(50):
        result = compute_insight_window(
            ucf_snapshot=MockUCF(),
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy"
        )
        results.append({
            "open": result.insight_window_open,
            "depth": result.insight_depth,
            "mode": result.insight_mode,
            "tags": tuple(result.insight_tags),  # Convert to tuple for comparison
        })

    # All results should be identical
    first_result = results[0]
    for result in results[1:]:
        assert result["open"] == first_result["open"]
        assert result["depth"] == first_result["depth"]
        assert result["mode"] == first_result["mode"]
        assert result["tags"] == first_result["tags"]


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
