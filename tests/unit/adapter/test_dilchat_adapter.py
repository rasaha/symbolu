"""
Comprehensive test suite for DILchat Adapter Layer v1.0

Tests verify:
1. Basic structure and serialization
2. Badge behavior for different stability scenarios
3. Grounding and alert badges
4. Deep reflection and arc mode hints
5. Concrete preference hints
6. Layer summary extraction
7. JSON serialization and determinism
"""

import json
import pytest
from symbolu.adapter.dilchat_adapter import (
    DILchatBadge,
    DILchatHint,
    DILchatResponse,
    build_dilchat_payload,
    build_dilchat_response,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def base_unified_output():
    """Base unified output for testing."""
    return {
        "text": "Let's explore your feelings about this situation.",
        "coherence": {
            "coherence_score": 0.85,
            "persona_drift_score": 0.30,
            "temporal_arc_score": 0.75,
            "semantic_stability_score": 0.90,
            "mapper_volatility_score": 0.20,
        },
        "symbolic": {
            "summary": "Deep identity exploration",
            "reasoning": "User is ready for reflective work",
        },
        "practical": {
            "text": "Practical advice here",
            "summary": "Concrete steps for moving forward",
        },
        "mirror": {
            "summary": "Mirror-truth reflection",
        },
        "metadata": {
            "domain": "therapy",
            "timestamp": "2025-01-09T12:00:00Z",
        },
        "entropy": {
            "normalized_entropy": 0.35,
        },
    }


@pytest.fixture
def stable_policy_flags():
    """Policy flags for stable scenario."""
    return {
        "needs_grounding": False,
        "allow_deep_reflection": True,
        "prefer_concrete": False,
        "prefer_arc_mode": False,
        "coherence_warning": False,
        "stability_status": "stable",
        "recommended_style": "reflective",
        "recommended_mapper": "HRM",
    }


@pytest.fixture
def fragmented_policy_flags():
    """Policy flags for fragmented scenario."""
    return {
        "needs_grounding": True,
        "allow_deep_reflection": False,
        "prefer_concrete": True,
        "prefer_arc_mode": False,
        "coherence_warning": True,
        "stability_status": "fragmented",
        "recommended_style": "precise",
        "recommended_mapper": "LCM",
    }


@pytest.fixture
def recovering_policy_flags():
    """Policy flags for recovering scenario."""
    return {
        "needs_grounding": False,
        "allow_deep_reflection": False,
        "prefer_concrete": False,
        "prefer_arc_mode": True,
        "coherence_warning": False,
        "stability_status": "recovering",
        "recommended_style": "exploratory",
        "recommended_mapper": "LAM",
    }


# ============================================================================
# TEST 1: Basic Structure
# ============================================================================


def test_basic_structure(base_unified_output, stable_policy_flags):
    """Test that build_dilchat_payload returns correct keys."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    # Verify main keys exist
    assert "text" in payload
    assert "badges" in payload
    assert "hints" in payload
    assert "coherence_score" in payload
    assert "stability_status" in payload
    assert "domain" in payload

    # Verify text content
    assert payload["text"] == "Let's explore your feelings about this situation."

    # Verify coherence data
    assert payload["coherence_score"] == 0.85
    assert payload["stability_status"] == "stable"
    assert payload["domain"] == "therapy"


def test_response_to_dict_structure(base_unified_output, stable_policy_flags):
    """Test DILchatResponse.to_dict() returns correct structure."""
    response = build_dilchat_response(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    result = response.to_dict()

    # Verify it's a dictionary
    assert isinstance(result, dict)

    # Verify badges are dicts
    assert isinstance(result["badges"], list)
    if len(result["badges"]) > 0:
        assert isinstance(result["badges"][0], dict)
        assert "label" in result["badges"][0]
        assert "level" in result["badges"][0]
        assert "description" in result["badges"][0]

    # Verify hints are dicts
    assert isinstance(result["hints"], list)
    if len(result["hints"]) > 0:
        assert isinstance(result["hints"][0], dict)
        assert "code" in result["hints"][0]
        assert "message" in result["hints"][0]


# ============================================================================
# TEST 2: Badge Behavior - Stable Scenario
# ============================================================================


def test_stable_scenario_badge(base_unified_output, stable_policy_flags):
    """Test stable scenario produces 'Stable' badge with level 'info'."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find stable badge
    stable_badge = None
    for badge in badges:
        if badge["label"] == "Stable":
            stable_badge = badge
            break

    assert stable_badge is not None, "Should have 'Stable' badge"
    assert stable_badge["level"] == "info"
    assert "stable" in stable_badge["description"].lower()


def test_deep_reflection_badge(base_unified_output, stable_policy_flags):
    """Test deep reflection badge appears when allow_deep_reflection=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find deep reflection badge
    deep_badge = None
    for badge in badges:
        if "Deep Reflection" in badge["label"]:
            deep_badge = badge
            break

    assert deep_badge is not None, "Should have 'Deep Reflection' badge"
    assert deep_badge["level"] == "info"
    assert "stable" in deep_badge["description"].lower()


# ============================================================================
# TEST 3: Badge Behavior - Recovering Scenario
# ============================================================================


def test_recovering_scenario_badge(base_unified_output, recovering_policy_flags):
    """Test recovering scenario produces 'Recovering' badge."""
    payload = build_dilchat_payload(
        base_unified_output,
        recovering_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find recovering badge
    recovering_badge = None
    for badge in badges:
        if badge["label"] == "Recovering":
            recovering_badge = badge
            break

    assert recovering_badge is not None, "Should have 'Recovering' badge"
    assert recovering_badge["level"] == "info"
    assert "recovering" in recovering_badge["description"].lower()


def test_arc_mode_badge(base_unified_output, recovering_policy_flags):
    """Test arc mode badge appears when prefer_arc_mode=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        recovering_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find arc badge
    arc_badge = None
    for badge in badges:
        if "Long-Arc" in badge["label"]:
            arc_badge = badge
            break

    assert arc_badge is not None, "Should have 'Long-Arc Active' badge"
    assert arc_badge["level"] == "info"
    assert "temporal" in arc_badge["description"].lower() or "arc" in arc_badge["description"].lower()


# ============================================================================
# TEST 4: Badge Behavior - Fragmented Scenario
# ============================================================================


def test_fragmented_scenario_badge(base_unified_output, fragmented_policy_flags):
    """Test fragmented scenario produces 'Fragmented' badge with warning level."""
    payload = build_dilchat_payload(
        base_unified_output,
        fragmented_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find fragmented badge
    fragmented_badge = None
    for badge in badges:
        if badge["label"] == "Fragmented":
            fragmented_badge = badge
            break

    assert fragmented_badge is not None, "Should have 'Fragmented' badge"
    assert fragmented_badge["level"] == "warning"
    assert "fragmented" in fragmented_badge["description"].lower()


# ============================================================================
# TEST 5: Grounding Badges
# ============================================================================


def test_grounding_needed_badge(base_unified_output, fragmented_policy_flags):
    """Test grounding needed badge appears when needs_grounding=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        fragmented_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find grounding badge
    grounding_badge = None
    for badge in badges:
        if "Grounding" in badge["label"]:
            grounding_badge = badge
            break

    assert grounding_badge is not None, "Should have 'Grounding Needed' badge"
    assert grounding_badge["level"] in ["warning", "critical"]
    assert "unstable" in grounding_badge["description"].lower() or "grounding" in grounding_badge["description"].lower()


def test_grounding_badge_escalates_with_coherence_warning(base_unified_output, fragmented_policy_flags):
    """Test grounding badge level escalates to 'critical' when coherence_warning=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        fragmented_policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Find grounding badge
    grounding_badge = None
    for badge in badges:
        if "Grounding" in badge["label"]:
            grounding_badge = badge
            break

    assert grounding_badge is not None
    # Should be critical because coherence_warning=True in fragmented_policy_flags
    assert grounding_badge["level"] == "critical"


# ============================================================================
# TEST 6: Hint Behavior - Grounding
# ============================================================================


def test_grounding_hint(base_unified_output, fragmented_policy_flags):
    """Test GROUNDING hint appears when needs_grounding=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        fragmented_policy_flags,
        domain="therapy"
    )

    hints = payload["hints"]

    # Find GROUNDING hint
    grounding_hint = None
    for hint in hints:
        if hint["code"] == "GROUNDING":
            grounding_hint = hint
            break

    assert grounding_hint is not None, "Should have 'GROUNDING' hint"
    assert "concrete" in grounding_hint["message"].lower()


def test_coherence_alert_hint(base_unified_output, fragmented_policy_flags):
    """Test COHERENCE_ALERT hint appears when coherence_warning=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        fragmented_policy_flags,
        domain="therapy"
    )

    hints = payload["hints"]

    # Find COHERENCE_ALERT hint
    alert_hint = None
    for hint in hints:
        if hint["code"] == "COHERENCE_ALERT":
            alert_hint = hint
            break

    assert alert_hint is not None, "Should have 'COHERENCE_ALERT' hint"
    assert "coherence" in alert_hint["message"].lower() or "degraded" in alert_hint["message"].lower()


# ============================================================================
# TEST 7: Hint Behavior - Deep Reflection
# ============================================================================


def test_deep_reflection_hint(base_unified_output, stable_policy_flags):
    """Test DEEP_REFLECTION hint appears when allow_deep_reflection=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    hints = payload["hints"]

    # Find DEEP_REFLECTION hint
    deep_hint = None
    for hint in hints:
        if hint["code"] == "DEEP_REFLECTION":
            deep_hint = hint
            break

    assert deep_hint is not None, "Should have 'DEEP_REFLECTION' hint"
    assert "safe" in deep_hint["message"].lower() or "deeper" in deep_hint["message"].lower()


# ============================================================================
# TEST 8: Hint Behavior - Arc Mode
# ============================================================================


def test_prefer_arc_hint(base_unified_output, recovering_policy_flags):
    """Test PREFER_ARC hint appears when prefer_arc_mode=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        recovering_policy_flags,
        domain="therapy"
    )

    hints = payload["hints"]

    # Find PREFER_ARC hint
    arc_hint = None
    for hint in hints:
        if hint["code"] == "PREFER_ARC":
            arc_hint = hint
            break

    assert arc_hint is not None, "Should have 'PREFER_ARC' hint"
    assert "temporal" in arc_hint["message"].lower() or "arc" in arc_hint["message"].lower()


# ============================================================================
# TEST 9: Hint Behavior - Concrete Preference
# ============================================================================


def test_prefer_concrete_hint(base_unified_output, fragmented_policy_flags):
    """Test PREFER_CONCRETE hint appears when prefer_concrete=True."""
    payload = build_dilchat_payload(
        base_unified_output,
        fragmented_policy_flags,
        domain="therapy"
    )

    hints = payload["hints"]

    # Find PREFER_CONCRETE hint
    concrete_hint = None
    for hint in hints:
        if hint["code"] == "PREFER_CONCRETE":
            concrete_hint = hint
            break

    assert concrete_hint is not None, "Should have 'PREFER_CONCRETE' hint"
    assert "practical" in concrete_hint["message"].lower() or "steps" in concrete_hint["message"].lower()


# ============================================================================
# TEST 10: Layer Summaries
# ============================================================================


def test_layer_summaries_extraction(base_unified_output, stable_policy_flags):
    """Test layer summaries are correctly extracted from unified output."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    # Verify symbolic summary
    assert "symbolic_summary" in payload
    # Should extract from either 'summary' or 'reasoning' field
    assert payload["symbolic_summary"] in [
        "Deep identity exploration",
        "User is ready for reflective work"
    ]

    # Verify practical summary
    assert "practical_summary" in payload
    assert payload["practical_summary"] in [
        "Concrete steps for moving forward",
        "Practical advice here"
    ]

    # Verify mirror summary
    assert "mirror_summary" in payload
    assert payload["mirror_summary"] == "Mirror-truth reflection"


def test_missing_layer_summaries(stable_policy_flags):
    """Test that missing layer summaries result in None (omitted in serialization)."""
    minimal_unified = {
        "text": "Hello",
        "coherence": {"coherence_score": 0.8},
        "symbolic": {},  # No summary
        "practical": {},  # No summary
        "mirror": {},    # No summary
        "metadata": {"domain": "generic"},
    }

    payload = build_dilchat_payload(
        minimal_unified,
        stable_policy_flags,
        domain="generic"
    )

    # These should be omitted from serialization (not in dict)
    assert "symbolic_summary" not in payload
    assert "practical_summary" not in payload
    assert "mirror_summary" not in payload


# ============================================================================
# TEST 11: Serialization - None Removal
# ============================================================================


def test_none_values_removed(stable_policy_flags):
    """Test that to_dict() removes None values."""
    minimal_unified = {
        "text": "Hello world",
        "coherence": {"coherence_score": 0.75},
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "metadata": {"domain": "generic"},
    }

    response = build_dilchat_response(
        minimal_unified,
        stable_policy_flags,
        domain="generic"
    )

    result = response.to_dict()

    # Verify None values are not in the dict
    for key, value in result.items():
        assert value is not None, f"Key '{key}' should not be None in serialized output"


# ============================================================================
# TEST 12: Serialization - JSON Compatibility
# ============================================================================


def test_json_serialization(base_unified_output, stable_policy_flags):
    """Test that to_dict() output is JSON-serializable."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    # Should not raise exception
    json_string = json.dumps(payload)

    # Verify it's valid JSON
    assert isinstance(json_string, str)

    # Verify round-trip
    parsed = json.loads(json_string)
    assert parsed["text"] == base_unified_output["text"]
    assert parsed["domain"] == "therapy"


# ============================================================================
# TEST 13: Determinism
# ============================================================================


def test_determinism(base_unified_output, stable_policy_flags):
    """Test that same input produces same output (deterministic)."""
    # Build payload twice
    payload1 = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    payload2 = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    # Serialize to JSON and compare
    json1 = json.dumps(payload1, sort_keys=True)
    json2 = json.dumps(payload2, sort_keys=True)

    assert json1 == json2, "Same input should produce identical output (deterministic)"


# ============================================================================
# TEST 14: Domain Metadata
# ============================================================================


def test_domain_from_metadata(base_unified_output, stable_policy_flags):
    """Test domain is extracted from metadata correctly."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="generic"  # Fallback domain
    )

    # Should use domain from metadata, not fallback
    assert payload["domain"] == "therapy"


def test_domain_fallback(stable_policy_flags):
    """Test domain fallback when not in metadata."""
    minimal_unified = {
        "text": "Hello",
        "coherence": {"coherence_score": 0.8},
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "metadata": {},  # No domain in metadata
    }

    payload = build_dilchat_payload(
        minimal_unified,
        stable_policy_flags,
        domain="trading"  # Fallback domain
    )

    # Should use fallback domain
    assert payload["domain"] == "trading"


# ============================================================================
# TEST 15: Multiple Badges Scenario
# ============================================================================


def test_multiple_badges(base_unified_output):
    """Test scenario with multiple badges (recovering + arc mode)."""
    policy_flags = {
        "needs_grounding": False,
        "allow_deep_reflection": False,
        "prefer_concrete": False,
        "prefer_arc_mode": True,  # Arc mode enabled
        "coherence_warning": False,
        "stability_status": "recovering",
    }

    payload = build_dilchat_payload(
        base_unified_output,
        policy_flags,
        domain="therapy"
    )

    badges = payload["badges"]

    # Should have at least 2 badges: Recovering + Long-Arc Active
    assert len(badges) >= 2

    badge_labels = [b["label"] for b in badges]
    assert "Recovering" in badge_labels
    assert "Long-Arc Active" in badge_labels


# ============================================================================
# TEST 16: Multiple Hints Scenario
# ============================================================================


def test_multiple_hints(base_unified_output):
    """Test scenario with multiple hints."""
    policy_flags = {
        "needs_grounding": True,
        "allow_deep_reflection": False,
        "prefer_concrete": True,
        "prefer_arc_mode": False,
        "coherence_warning": True,
        "stability_status": "fragmented",
    }

    payload = build_dilchat_payload(
        base_unified_output,
        policy_flags,
        domain="therapy"
    )

    hints = payload["hints"]

    # Should have multiple hints
    assert len(hints) >= 3

    hint_codes = [h["code"] for h in hints]
    assert "GROUNDING" in hint_codes
    assert "PREFER_CONCRETE" in hint_codes
    assert "COHERENCE_ALERT" in hint_codes


# ============================================================================
# TEST 17: Raw Data Preservation
# ============================================================================


def test_raw_data_preserved(base_unified_output, stable_policy_flags):
    """Test that raw unified output and policy flags are preserved."""
    payload = build_dilchat_payload(
        base_unified_output,
        stable_policy_flags,
        domain="therapy"
    )

    # Verify raw data is included
    assert "raw_unified" in payload
    assert "policy_flags" in payload

    # Verify raw data matches input
    assert payload["raw_unified"]["text"] == base_unified_output["text"]
    assert payload["policy_flags"]["stability_status"] == stable_policy_flags["stability_status"]


# ============================================================================
# TEST 18: Empty Policy Flags
# ============================================================================


def test_empty_policy_flags(base_unified_output):
    """Test adapter handles empty policy flags gracefully."""
    empty_flags = {}

    payload = build_dilchat_payload(
        base_unified_output,
        empty_flags,
        domain="therapy"
    )

    # Should still produce valid payload
    assert "text" in payload
    assert "badges" in payload
    assert "hints" in payload

    # Badges and hints should be empty or minimal
    # (no policy flags means no badges/hints)
    assert isinstance(payload["badges"], list)
    assert isinstance(payload["hints"], list)
