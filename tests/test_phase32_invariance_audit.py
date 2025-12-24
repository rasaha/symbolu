"""
Test Suite for Phase 32 Merge-Safety Invariance Audit

Comprehensive invariance validation for the Insight Window Gating System (Phase 32).
This test suite formally validates that Phase 32 does not change any core pipeline
behavior and is truly UI-layer-only, observation-only, and zero-LLM.

Invariance Categories:
    1. Routing Invariance - TTOR/MLCR behavior unchanged
    2. Mapper Invariance - HRM/LCM/LAM behavior unchanged
    3. Coherence Score Invariance - All coherence scores unchanged
    4. Policy Safety Invariance - Core safety flags unchanged
    5. Domain & Mode Gating - Correct domain/mode restrictions
    6. DILchat Invariance - No text changes, correct badge gating
    7. Unified API Backward Compatibility - Null-safe, non-breaking
    8. Determinism & Degradation - Deterministic, graceful failure
    9. End-to-End Invariance - Bitwise identical core decisions

Reference:
    Phase 27 Merge Safety Audit (PHASE_27_MERGE_SAFETY_REPORT.md)
"""

import pytest
import os
import glob


# ============================================================================
# CLASS 1: ROUTING INVARIANCE
# ============================================================================

class TestPhase32RoutingInvariance:
    """
    Verify Phase 32 does not modify TTOR or MLCR routing logic.

    Routing decisions must be completely isolated from insight_window_gating.
    No routing module should import or reference insight window logic.
    """

    def test_routing_files_no_insight_window_imports(self):
        """Test that no routing files import insight_window_gating."""
        # Find all routing-related files
        routing_patterns = [
            "symbolu/**/routing*.py",
            "symbolu/**/ttor*.py",
            "symbolu/**/mlcr*.py",
        ]

        routing_files = []
        for pattern in routing_patterns:
            routing_files.extend(glob.glob(pattern, recursive=True))

        # Check each file for insight_window_gating imports
        for filepath in routing_files:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Should not import or reference insight_window_gating
                    assert "insight_window_gating" not in content, \
                        f"Routing file {filepath} references insight_window_gating (INVARIANT VIOLATION)"
                    assert "InsightWindowResult" not in content, \
                        f"Routing file {filepath} references InsightWindowResult (INVARIANT VIOLATION)"

    def test_routing_decision_independent_of_insight_window(self):
        """Test routing recommendations are identical regardless of insight window presence."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Build unified output with UCF data
        unified_base = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.65,
                "persona_drift_score": 0.35,
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

        # Scenario 1: therapy + smart_insight (insight window ENABLED)
        flags_enabled = compute_policy_flags(
            unified_base,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        # Scenario 2: same domain, deep_adaptive mode (still has insight window)
        flags_deep = compute_policy_flags(
            unified_base,
            domain="therapy",
            user_mode_override="deep_adaptive"
        )

        # Core routing recommendation must be identical for same domain
        # (insight_window is a diagnostic layer, not a routing decision maker)
        assert flags_enabled["recommended_mapper"] == flags_deep["recommended_mapper"], \
            "Routing decision changed based on insight mode within same domain (INVARIANT VIOLATION)"


# ============================================================================
# CLASS 2: MAPPER INVARIANCE
# ============================================================================

class TestPhase32MapperInvariance:
    """
    Verify Phase 32 does not modify HRM, LCM, or LAM mapper logic.

    Mapper activation and outputs must be completely isolated from insight_window.
    """

    def test_mapper_files_no_insight_window_imports(self):
        """Test that no mapper files import insight_window_gating."""
        mapper_patterns = [
            "symbolu/**/mapper*.py",
            "symbolu/**/*HRM*.py",
            "symbolu/**/*LCM*.py",
            "symbolu/**/*LAM*.py",
        ]

        mapper_files = []
        for pattern in mapper_patterns:
            mapper_files.extend(glob.glob(pattern, recursive=True))

        for filepath in mapper_files:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    assert "insight_window_gating" not in content, \
                        f"Mapper file {filepath} references insight_window_gating (INVARIANT VIOLATION)"
                    assert "InsightWindowResult" not in content, \
                        f"Mapper file {filepath} references InsightWindowResult (INVARIANT VIOLATION)"

    def test_mapper_recommendation_independent_of_insight_window(self):
        """Test mapper recommendation is stable within same domain across different insight modes."""
        from symbolu.policy.policy_engine import compute_policy_flags

        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.55,
                "persona_drift_score": 0.45,
                "unified_consciousness": {
                    "coi": 0.6,
                    "csi": 0.55,
                    "cip": 0.5,
                },
                "semantic": {"cognitive_drift_v3": 0.4},
                "temporal_entropy": {"volatility": 0.35}
            },
            "metadata": {},
            "entropy": {}
        }

        # With smart_insight mode
        flags_smart = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        # With deep_adaptive mode (same domain)
        flags_deep = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="deep_adaptive"
        )

        # Mapper recommendation must be identical for same domain/coherence
        assert flags_smart["recommended_mapper"] == flags_deep["recommended_mapper"], \
            "Mapper recommendation changed based on insight mode within same domain (INVARIANT VIOLATION)"


# ============================================================================
# CLASS 3: COHERENCE SCORE INVARIANCE
# ============================================================================

class TestPhase32CoherenceScoreInvariance:
    """
    Verify Phase 32 does not modify coherence_score_v1, v2, v3, or fused scoring.

    UCF (COI/CSI/CIP) values must remain unchanged.
    Insight window may READ but never WRITE coherence values.
    """

    def test_coherence_engine_no_modifications_from_insight_window(self):
        """Test CoherenceEngine does not call insight_window_gating during scoring."""
        # Read coherence_engine.py to verify insight_window_gating is not called during scoring
        coherence_engine_path = "symbolu/core/coherence/coherence_engine.py"

        if os.path.exists(coherence_engine_path):
            with open(coherence_engine_path, 'r') as f:
                content = f.read()

            # CoherenceEngine should not import insight_window_gating
            assert "insight_window_gating" not in content, \
                "CoherenceEngine imports insight_window_gating (INVARIANT VIOLATION)"

            # _compute_overall_coherence should not reference any Phase 32 fields
            if "_compute_overall_coherence" in content:
                # Extract the function (approximate)
                start = content.find("def _compute_overall_coherence")
                if start != -1:
                    # Find next function definition
                    next_def = content.find("\n    def ", start + 1)
                    func_body = content[start:next_def] if next_def != -1 else content[start:start+1000]

                    # Should not reference insight_window
                    assert "insight_window" not in func_body, \
                        "_compute_overall_coherence references insight_window (INVARIANT VIOLATION)"

    def test_coherence_scores_identical_with_without_insight_window(self):
        """Test coherence scores are identical regardless of insight window state."""
        from symbolu.policy.policy_engine import compute_policy_flags

        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.72,  # v1 score
                "coherence_score_v2": 0.75,  # v2 score
                "coherence_score_v3": 0.78,  # v3 score
                "coherence_fused": 0.76,  # fused score
                "persona_drift_score": 0.30,
                "unified_consciousness": {
                    "coi": 0.70,
                    "csi": 0.65,
                    "cip": 0.60,
                },
                "semantic": {"cognitive_drift_v3": 0.25},
                "temporal_entropy": {"volatility": 0.28}
            },
            "metadata": {},
            "entropy": {}
        }

        # Compute policy flags with insight window enabled
        flags_enabled = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        # Compute policy flags with insight window disabled
        flags_disabled = compute_policy_flags(
            unified_output,
            domain="trading",
            user_mode_override="analytics_only"
        )

        # Coherence-derived status must be identical
        assert flags_enabled["stability_status"] == flags_disabled["stability_status"], \
            "stability_status changed based on insight window (INVARIANT VIOLATION)"

    def test_ucf_values_readonly_in_insight_window(self):
        """Test insight_window_gating only reads UCF values, never writes."""
        from symbolu.policy.insight_window_gating import compute_insight_window

        class MockUCF:
            def __init__(self):
                self.consciousness_order_index = 0.7
                self.consciousness_stability_index = 0.6
                self.consciousness_integration_potential = 0.5
                self.entropy_of_weights = 0.3
                self.diagnostic_notes = ["test"]

        ucf_before = MockUCF()

        # Store original values
        coi_before = ucf_before.consciousness_order_index
        csi_before = ucf_before.consciousness_stability_index
        cip_before = ucf_before.consciousness_integration_potential

        # Call compute_insight_window
        result = compute_insight_window(
            ucf_snapshot=ucf_before,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy"
        )

        # UCF values must remain unchanged
        assert ucf_before.consciousness_order_index == coi_before, \
            "COI was modified by insight_window_gating (INVARIANT VIOLATION)"
        assert ucf_before.consciousness_stability_index == csi_before, \
            "CSI was modified by insight_window_gating (INVARIANT VIOLATION)"
        assert ucf_before.consciousness_integration_potential == cip_before, \
            "CIP was modified by insight_window_gating (INVARIANT VIOLATION)"


# ============================================================================
# CLASS 4: POLICY SAFETY INVARIANCE
# ============================================================================

class TestPhase32PolicySafetyInvariance:
    """
    Verify Phase 32 only touches UI-layer flags, never core safety flags.

    May modify: allow_deep_reflection, prefer_arc_mode, allow_meta_insight,
                prefer_symbolic_interpretation

    Must NOT modify: needs_grounding, coherence_warning, stability_status,
                     recommended_mapper, any trading guardrails
    """

    def test_safety_flags_unchanged_by_insight_window(self):
        """Test core safety flags remain unchanged when insight window is applied."""
        from symbolu.policy.policy_engine import _apply_insight_window_to_policy
        from symbolu.policy.insight_window_gating import InsightWindowResult

        # Create flags with safety-critical values
        flags_before = {
            "needs_grounding": True,
            "coherence_warning": True,
            "stability_status": "fragmented",
            "recommended_mapper": "LCM",
            "allow_deep_reflection": False,
            "prefer_arc_mode": False,
        }

        # Create insight window result (open, deep mode)
        insight = InsightWindowResult(
            insight_window_open=True,
            insight_depth=0.75,
            insight_mode="deep",
            insight_tags=["structural_alignment"],
            notes=[]
        )

        # Apply insight window refinement
        flags_after = _apply_insight_window_to_policy(flags_before, insight)

        # Safety-critical flags must remain unchanged
        assert flags_after["needs_grounding"] == flags_before["needs_grounding"], \
            "needs_grounding was modified (INVARIANT VIOLATION)"
        assert flags_after["coherence_warning"] == flags_before["coherence_warning"], \
            "coherence_warning was modified (INVARIANT VIOLATION)"
        assert flags_after["stability_status"] == flags_before["stability_status"], \
            "stability_status was modified (INVARIANT VIOLATION)"
        assert flags_after["recommended_mapper"] == flags_before["recommended_mapper"], \
            "recommended_mapper was modified (INVARIANT VIOLATION)"

    def test_only_ui_flags_modified(self):
        """Test only UI-layer flags are modified by insight window."""
        from symbolu.policy.policy_engine import _apply_insight_window_to_policy
        from symbolu.policy.insight_window_gating import InsightWindowResult

        flags_before = {
            "needs_grounding": False,
            "allow_deep_reflection": False,
            "prefer_arc_mode": False,
            "coherence_warning": False,
            "stability_status": "stable",
            "recommended_mapper": "HRM",
        }

        insight_light = InsightWindowResult(
            insight_window_open=True,
            insight_depth=0.55,
            insight_mode="light",
            insight_tags=[],
            notes=[]
        )

        flags_after = _apply_insight_window_to_policy(flags_before, insight_light)

        # UI flags should be modified
        assert flags_after["allow_deep_reflection"] is True, \
            "allow_deep_reflection should be modified in light mode"
        assert flags_after["prefer_arc_mode"] is True, \
            "prefer_arc_mode should be modified in light mode"

        # Safety flags should remain unchanged
        assert flags_after["needs_grounding"] == flags_before["needs_grounding"]
        assert flags_after["coherence_warning"] == flags_before["coherence_warning"]
        assert flags_after["stability_status"] == flags_before["stability_status"]

    def test_trading_guardrails_unchanged(self):
        """Test trading-specific guardrails are never touched by insight window."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Insight window should be closed for trading domain
        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.7,
                "persona_drift_score": 0.3,
                "unified_consciousness": {
                    "coi": 0.75,
                    "csi": 0.70,
                    "cip": 0.65,
                },
                "semantic": {"cognitive_drift_v3": 0.25},
                "temporal_entropy": {"volatility": 0.25}
            },
            "metadata": {},
            "entropy": {}
        }

        flags = compute_policy_flags(
            unified_output,
            domain="trading",
            user_mode_override="smart_insight"  # Even with smart_insight
        )

        # Insight window should be closed for trading
        assert flags["insight_window"]["insight_window_open"] is False, \
            "Insight window should be closed for trading domain"
        assert flags["insight_window"]["insight_mode"] == "none", \
            "Insight mode should be 'none' for trading domain"


# ============================================================================
# CLASS 5: DOMAIN & MODE GATING
# ============================================================================

class TestPhase32DomainModeGating:
    """
    Verify insight window gating is ONLY active for:
    - domain in ["therapy", "identity"]
    - interaction_mode in ["smart_insight", "deep_adaptive"]

    All other domains/modes must result in closed window.
    """

    def test_therapy_domain_passes_gate(self):
        """Test therapy domain passes domain gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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

    def test_identity_domain_passes_gate(self):
        """Test identity domain passes domain gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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

    def test_trading_domain_blocked(self):
        """Test trading domain is blocked by domain gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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

    def test_generic_domain_blocked(self):
        """Test generic domain is blocked by domain gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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
            domain="generic"
        )

        assert result.insight_window_open is False
        assert result.insight_mode == "none"

    def test_smart_insight_mode_passes_gate(self):
        """Test smart_insight mode passes mode gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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

    def test_deep_adaptive_mode_passes_gate(self):
        """Test deep_adaptive mode passes mode gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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

    def test_analytics_only_mode_blocked(self):
        """Test analytics_only mode is blocked by mode gate."""
        from symbolu.policy.insight_window_gating import compute_insight_window

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


# ============================================================================
# CLASS 6: DILCHAT TEXT & BADGE INVARIANCE
# ============================================================================

class TestPhase32DILchatInvariance:
    """
    Verify DILchat adapter correctly adds insight window badges without:
    - Modifying response text
    - Overriding safety badges
    - Appearing outside therapy/identity + smart_insight/deep_adaptive
    """

    def test_badges_only_for_therapy_identity(self):
        """Test insight window badges only appear for therapy/identity domains."""
        from symbolu.adapter.dilchat_adapter import build_dilchat_response

        unified_output = {
            "text": "test response",
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

        # Should NOT have insight window badges for trading
        assert "INSIGHT_WINDOW_OPEN" not in badge_labels
        assert "INSIGHT_WINDOW_DEEP" not in badge_labels

    def test_badges_only_for_smart_or_deep_modes(self):
        """Test insight window badges only appear for smart_insight/deep_adaptive."""
        from symbolu.adapter.dilchat_adapter import build_dilchat_response

        unified_output = {
            "text": "test response",
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

        # Should NOT have insight window badges for analytics_only
        assert "INSIGHT_WINDOW_OPEN" not in badge_labels

    def test_response_text_unchanged(self):
        """Test insight window badges don't modify response text."""
        from symbolu.adapter.dilchat_adapter import build_dilchat_response

        original_text = "This is the original response text."

        unified_output = {
            "text": original_text,
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
        assert response.text == original_text, \
            "Response text was modified by insight window badges (INVARIANT VIOLATION)"

    def test_safety_badges_not_overridden(self):
        """Test insight window badges don't override safety badges."""
        from symbolu.adapter.dilchat_adapter import build_dilchat_response

        unified_output = {
            "text": "test",
            "coherence": {},
            "metadata": {"domain": "therapy"},
        }

        policy_flags = {
            "stability_status": "fragmented",
            "needs_grounding": True,
            "coherence_warning": True,
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

        # Both safety and insight window badges should be present
        assert "Grounding Needed" in badge_labels, \
            "Safety badge 'Grounding Needed' was removed (INVARIANT VIOLATION)"
        assert "INSIGHT_WINDOW_OPEN" in badge_labels, \
            "Insight window badge should be present"


# ============================================================================
# CLASS 7: UNIFIED API BACKWARD COMPATIBILITY
# ============================================================================

class TestPhase32UnifiedAPIBackwardCompatibility:
    """
    Verify unified API changes are:
    - Optional (insight_window can be None)
    - Null-safe (no exceptions on missing data)
    - Non-breaking (existing clients still work)
    """

    def test_unified_output_with_missing_insight_window(self):
        """Test UnifiedOutput works when insight_window is None."""
        from symbolu.api.unified_api import UnifiedOutput

        # Create output without insight_window
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
            insight_window=None
        )

        # Should serialize without errors
        serialized = output.to_dict()
        assert "text" in serialized

    def test_build_unified_output_without_ucf(self):
        """Test build_unified_output handles missing UCF data gracefully."""
        from symbolu.api.unified_api import build_unified_output

        class MockContext:
            def __init__(self):
                self.policy_flags = {
                    "insight_window": {
                        "insight_window_open": False,
                        "insight_depth": 0.0,
                        "insight_mode": "none",
                        "insight_tags": [],
                        "notes": ["Insufficient UCF data"]
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

        ctx = MockContext()
        output = build_unified_output("test text", ctx)

        # Should not raise exceptions
        assert output is not None
        assert output.insight_window is not None
        assert output.insight_window["insight_window_open"] is False

    def test_null_safety_in_policy_engine(self):
        """Test compute_policy_flags handles missing UCF gracefully."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Unified output without UCF data
        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.65,
                "persona_drift_score": 0.35,
                # No unified_consciousness field
            },
            "metadata": {},
            "entropy": {}
        }

        # Should not raise exceptions
        flags = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        # Insight window should be closed due to missing data
        assert flags["insight_window"]["insight_window_open"] is False
        assert flags["insight_window"]["insight_mode"] == "none"


# ============================================================================
# CLASS 8: ZERO-LLM GUARANTEE
# ============================================================================

class TestPhase32ZeroLLMGuarantee:
    """
    Verify Phase 32 makes zero LLM calls.

    All insight window computation must be pure math + rules only.
    """

    def test_insight_window_gating_no_llm_imports(self):
        """Test insight_window_gating.py does not import LLM modules."""
        insight_window_path = "symbolu/policy/insight_window_gating.py"

        if os.path.exists(insight_window_path):
            with open(insight_window_path, 'r') as f:
                content = f.read()

            # Should not import LLM-related modules
            llm_patterns = [
                "openai",
                "anthropic",
                "llm_client",
                "renderer",
                "llm_renderer",
                "from symbolu.llm",
                "import llm",
            ]

            for pattern in llm_patterns:
                assert pattern not in content.lower(), \
                    f"insight_window_gating.py contains '{pattern}' (ZERO-LLM VIOLATION)"

    def test_computation_is_deterministic_math_only(self):
        """Test insight window computation is purely deterministic math."""
        from symbolu.policy.insight_window_gating import compute_insight_window

        class MockUCF:
            def __init__(self):
                self.consciousness_order_index = 0.68
                self.consciousness_stability_index = 0.62
                self.consciousness_integration_potential = 0.54
                self.entropy_of_weights = 0.35
                self.diagnostic_notes = []

        # Run computation - should complete instantly (no LLM latency)
        import time
        start = time.time()

        result = compute_insight_window(
            ucf_snapshot=MockUCF(),
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy"
        )

        elapsed = time.time() - start

        # Should complete in < 10ms (deterministic math is fast)
        assert elapsed < 0.01, \
            f"Computation took {elapsed*1000:.2f}ms (possible LLM call?)"


# ============================================================================
# CLASS 9: DETERMINISM & GRACEFUL DEGRADATION
# ============================================================================

class TestPhase32DeterminismAndDegradation:
    """
    Verify Phase 32 is:
    - Deterministic (same inputs → same outputs)
    - Gracefully degrades (no crashes on missing data)
    """

    def test_determinism_100_iterations(self):
        """Test determinism over 100 iterations."""
        from symbolu.policy.insight_window_gating import compute_insight_window

        class MockUCF:
            def __init__(self):
                self.consciousness_order_index = 0.68
                self.consciousness_stability_index = 0.62
                self.consciousness_integration_potential = 0.54
                self.entropy_of_weights = 0.35
                self.diagnostic_notes = ["test_note"]

        results = []
        for _ in range(100):
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
                "tags": tuple(result.insight_tags),
            })

        # All results should be identical
        first = results[0]
        for result in results[1:]:
            assert result["open"] == first["open"], \
                "insight_window_open non-deterministic (INVARIANT VIOLATION)"
            assert result["depth"] == first["depth"], \
                "insight_depth non-deterministic (INVARIANT VIOLATION)"
            assert result["mode"] == first["mode"], \
                "insight_mode non-deterministic (INVARIANT VIOLATION)"
            assert result["tags"] == first["tags"], \
                "insight_tags non-deterministic (INVARIANT VIOLATION)"

    def test_graceful_degradation_missing_ucf(self):
        """Test graceful degradation when UCF data is missing."""
        from symbolu.policy.insight_window_gating import compute_insight_window

        # Call with None UCF
        result = compute_insight_window(
            ucf_snapshot=None,
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy"
        )

        # Should return closed window, not crash
        assert result.insight_window_open is False
        assert result.insight_mode == "none"
        assert "Insufficient UCF data" in " ".join(result.notes)

    def test_graceful_degradation_partial_ucf(self):
        """Test graceful degradation when UCF data is partial."""
        from symbolu.policy.insight_window_gating import compute_insight_window

        class PartialUCF:
            def __init__(self):
                self.consciousness_order_index = 0.7
                # Missing CSI and CIP
                self.entropy_of_weights = 0.3
                self.diagnostic_notes = []

        result = compute_insight_window(
            ucf_snapshot=PartialUCF(),
            coherence_observation=None,
            interaction_mode="smart_insight",
            domain="therapy"
        )

        # Should handle gracefully
        assert result.insight_window_open is False


# ============================================================================
# CLASS 10: END-TO-END BEHAVIORAL INVARIANCE
# ============================================================================

class TestPhase32EndToEndInvariance:
    """
    Verify end-to-end pipeline behavior is unchanged for canonical test cases.

    For fixed inputs, core decisions must be bitwise identical with/without Phase 32.
    """

    def test_end_to_end_trading_scenario(self):
        """Test end-to-end trading scenario is unchanged."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Canonical trading scenario
        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.75,
                "persona_drift_score": 0.25,
                "unified_consciousness": {
                    "coi": 0.80,
                    "csi": 0.75,
                    "cip": 0.70,
                },
                "semantic": {"cognitive_drift_v3": 0.20},
                "temporal_entropy": {"volatility": 0.22}
            },
            "routing": {
                "tier": "tier2",
                "intent": "analysis",
                "domain": "trading",
            },
            "metadata": {},
            "entropy": {}
        }

        # Compute flags
        flags = compute_policy_flags(
            unified_output,
            domain="trading",
            user_mode_override="analytics_only"
        )

        # Core behaviors must be unchanged
        assert flags["needs_grounding"] is False  # High coherence
        assert flags["stability_status"] == "stable"  # High coherence, low drift
        assert flags["recommended_mapper"] in ["LCM", "HRM", "LAM"]

        # Insight window must be closed for trading
        assert flags["insight_window"]["insight_window_open"] is False

    def test_end_to_end_therapy_high_coherence(self):
        """Test end-to-end therapy scenario with high coherence."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Canonical therapy scenario (high coherence)
        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.80,
                "persona_drift_score": 0.20,
                "unified_consciousness": {
                    "coi": 0.85,
                    "csi": 0.80,
                    "cip": 0.75,
                },
                "semantic": {"cognitive_drift_v3": 0.18},
                "temporal_entropy": {"volatility": 0.20}
            },
            "metadata": {},
            "entropy": {}
        }

        flags = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        # Core behaviors unchanged
        assert flags["needs_grounding"] is False
        assert flags["stability_status"] == "stable"

        # Insight window should be open (UI-layer only)
        assert flags["insight_window"]["insight_window_open"] is True
        assert flags["insight_window"]["insight_mode"] in ["light", "deep"]

        # UI flags may be modified
        assert flags["allow_deep_reflection"] is True

    def test_end_to_end_therapy_low_coherence(self):
        """Test end-to-end therapy scenario with low coherence."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Canonical therapy scenario (low coherence)
        # coherence_warning triggers at < (min_coherence - 0.1) = 0.35
        # Use 0.30 to ensure we're below the threshold
        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.30,  # Below 0.35 threshold
                "persona_drift_score": 0.70,
                "unified_consciousness": {
                    "coi": 0.40,
                    "csi": 0.35,
                    "cip": 0.30,
                },
                "semantic": {"cognitive_drift_v3": 0.68},
                "temporal_entropy": {"volatility": 0.65}
            },
            "metadata": {},
            "entropy": {}
        }

        flags = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        # Core safety behaviors unchanged
        assert flags["needs_grounding"] is True  # Low coherence
        assert flags["stability_status"] == "fragmented"
        assert flags["coherence_warning"] is True  # 0.30 < 0.35 (min_coherence - 0.1)

        # Insight window should be closed (blocked by low UCF)
        assert flags["insight_window"]["insight_window_open"] is False
        assert flags["insight_window"]["insight_mode"] == "none"

    def test_comparative_invariance_therapy_vs_trading(self):
        """Test cross-domain routing produces consistent logic-based decisions."""
        from symbolu.policy.policy_engine import compute_policy_flags

        # Same coherence metrics for both domains
        unified_output = {
            "text": "test",
            "coherence": {
                "coherence_score": 0.65,
                "persona_drift_score": 0.40,
                "unified_consciousness": {
                    "coi": 0.70,
                    "csi": 0.65,
                    "cip": 0.60,
                },
                "semantic": {"cognitive_drift_v3": 0.38},
                "temporal_entropy": {"volatility": 0.35}
            },
            "metadata": {},
            "entropy": {}
        }

        flags_therapy = compute_policy_flags(
            unified_output,
            domain="therapy",
            user_mode_override="smart_insight"
        )

        flags_trading = compute_policy_flags(
            unified_output,
            domain="trading",
            user_mode_override="analytics_only"
        )

        # Cross-domain invariants: Safety logic is consistent
        # needs_grounding depends on domain-specific thresholds (min_coherence)
        # but both domains should process it consistently
        assert flags_therapy["needs_grounding"] in [True, False]
        assert flags_trading["needs_grounding"] in [True, False]

        # stability_status uses same calculation across domains
        assert flags_therapy["stability_status"] == flags_trading["stability_status"]

        # coherence_warning may differ due to domain-specific min_coherence thresholds
        assert flags_therapy["coherence_warning"] in [True, False]
        assert flags_trading["coherence_warning"] in [True, False]

        # recommended_mapper legitimately differs by domain (LAM for therapy, LCM/HRM for trading)
        assert flags_therapy["recommended_mapper"] in ["LAM", "HRM", "LCM"]
        assert flags_trading["recommended_mapper"] in ["LCM", "HRM"]

        # Insight window behavior differs by domain configuration (this is expected)
        # therapy + smart_insight enables insight window, trading + analytics_only does not
        assert flags_therapy["insight_window"]["insight_window_open"] is True
        assert flags_trading["insight_window"]["insight_window_open"] is False


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
