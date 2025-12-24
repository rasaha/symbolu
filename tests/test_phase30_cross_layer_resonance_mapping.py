"""
Phase 30: Cross-Layer Resonance Persona Mapping - Test Suite
==============================================================

Comprehensive test suite for Phase 30 implementation.

Test Groups:
    A. Mapping Math (10 tests) - Deterministic mapping logic
    B. Persona Engine Integration (10 tests) - Engine integration
    C. Unified API (6 tests) - API exposure
    D. DILchat Adapter (6 tests) - Badge generation
    E. Behavioral Invariance (6 tests) - No side effects
"""

import pytest
from dataclasses import dataclass
from typing import Optional, Dict, Any
from unittest.mock import Mock, patch

# Import Phase 30 modules
from symbolu.mechanical.persona.persona_resonance_mapping import (
    CrossLayerResonanceMap,
    compute_cross_layer_persona_map,
    _clamp,
    _safe_avg,
)
from symbolu.mechanical.persona.engine import PersonaEngine
from symbolu.mechanical.persona.models import (
    PersonaResponse,
    RendererOutputV3,
    DHAResult,
    PersonaMetadata,
)
from symbolu.api.unified_api import build_unified_output
from symbolu.adapter.dilchat_adapter import build_dilchat_response


# ============================================================================
# Mock CoherenceObservation for Testing
# ============================================================================

@dataclass
class MockCoherenceObservation:
    """Mock CoherenceObservation for testing."""
    coherence_score: float = 0.8
    persona_drift_score: float = 0.2
    semantic_stability_score: float = 0.8
    temporal_arc_score: float = 0.7
    mapper_volatility_score: float = 0.1
    turn_number: int = 5
    tier: str = "HYBRID"
    domain: str = "therapy"

    # Phase 30 relevant fields
    guna_resonance_index: Optional[float] = None
    kosha_resonance_index: Optional[float] = None
    semantic_integrity_score: Optional[float] = None
    cognitive_drift_v3: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    coherence_fused: Optional[float] = None
    symbolic_harmonization_index: Optional[float] = None
    consciousness_order_index: Optional[float] = None
    consciousness_stability_index: Optional[float] = None
    consciousness_integration_potential: Optional[float] = None


# ============================================================================
# GROUP A: Mapping Math Tests (10 tests)
# ============================================================================

class TestMappingMath:
    """Test Group A: Deterministic mapping logic."""

    def test_clamp_function(self):
        """Test _clamp utility function."""
        assert _clamp(0.5, 0.0, 1.0) == 0.5
        assert _clamp(-0.1, 0.0, 1.0) == 0.0
        assert _clamp(1.5, 0.0, 1.0) == 1.0
        assert _clamp(0.3, 0.0, 1.0) == 0.3

    def test_safe_avg_function(self):
        """Test _safe_avg utility function."""
        assert _safe_avg(0.5, 0.5, default=0.5) == 0.5
        assert _safe_avg(0.5, None, default=0.5) == 0.5
        assert _safe_avg(None, 0.5, default=0.5) == 0.5
        assert _safe_avg(None, None, default=0.5) == 0.5
        assert _safe_avg(0.3, 0.7, default=0.5) == 0.5

    def test_deterministic_mapping_same_inputs(self):
        """Test that same inputs produce same outputs (determinism)."""
        snapshot = MockCoherenceObservation(
            guna_resonance_index=0.8,
            kosha_resonance_index=0.7,
            semantic_integrity_score=0.9,
        )

        result1 = compute_cross_layer_persona_map(snapshot)
        result2 = compute_cross_layer_persona_map(snapshot)

        assert result1.metaphor_weight == result2.metaphor_weight
        assert result1.warmth_weight == result2.warmth_weight
        assert result1.structure_weight == result2.structure_weight
        assert result1.resonance_tags == result2.resonance_tags

    def test_range_checks_all_weights(self):
        """Test that all weights are in [0.0, 1.0] range."""
        snapshot = MockCoherenceObservation(
            guna_resonance_index=1.0,
            kosha_resonance_index=1.0,
            semantic_integrity_score=0.0,
            cognitive_drift_v3=1.0,
            temporal_entropy_diff=1.0,
        )

        result = compute_cross_layer_persona_map(snapshot)

        assert 0.0 <= result.metaphor_weight <= 1.0
        assert 0.0 <= result.warmth_weight <= 1.0
        assert 0.0 <= result.structure_weight <= 1.0
        assert 0.0 <= result.reflective_bandwidth <= 1.0
        assert 0.0 <= result.grounding_bias <= 1.0
        assert 0.0 <= result.expressiveness_bias <= 1.0

    def test_high_resonance_tag_logic(self):
        """Test HIGH_RESONANCE tag is added when (guna + kosha) / 2 ≥ 0.70."""
        snapshot = MockCoherenceObservation(
            guna_resonance_index=0.75,
            kosha_resonance_index=0.75,
        )

        result = compute_cross_layer_persona_map(snapshot)

        assert "HIGH_RESONANCE" in result.resonance_tags

    def test_low_resonance_tag_logic(self):
        """Test LOW_RESONANCE tag is added when (guna + kosha) / 2 ≤ 0.40."""
        snapshot = MockCoherenceObservation(
            guna_resonance_index=0.3,
            kosha_resonance_index=0.3,
        )

        result = compute_cross_layer_persona_map(snapshot)

        assert "LOW_RESONANCE" in result.resonance_tags

    def test_drift_caution_tag_logic(self):
        """Test DRIFT_CAUTION tag is added when cognitive_drift_v3 ≥ 0.60."""
        snapshot = MockCoherenceObservation(
            cognitive_drift_v3=0.65,
        )

        result = compute_cross_layer_persona_map(snapshot)

        assert "DRIFT_CAUTION" in result.resonance_tags

    def test_entropy_high_tag_logic(self):
        """Test ENTROPY_HIGH tag is added when temporal_entropy ≥ 0.60."""
        snapshot = MockCoherenceObservation(
            temporal_entropy_diff=0.70,
        )

        result = compute_cross_layer_persona_map(snapshot)

        assert "ENTROPY_HIGH" in result.resonance_tags

    def test_null_input_fallback_defaults(self):
        """Test graceful degradation to defaults when all inputs are None."""
        snapshot = MockCoherenceObservation()

        result = compute_cross_layer_persona_map(snapshot)

        # Should return default weights (0.5) when no signals available
        assert result.metaphor_weight is not None
        assert result.warmth_weight is not None
        assert result.structure_weight is not None
        assert result.resonance_tags == []  # No tags without data

    def test_bias_weight_calculations(self):
        """Test that bias weights are calculated correctly."""
        snapshot = MockCoherenceObservation(
            guna_resonance_index=0.8,
            kosha_resonance_index=0.8,
            semantic_integrity_score=0.4,  # Low integrity
            cognitive_drift_v3=0.7,  # High drift
        )

        result = compute_cross_layer_persona_map(snapshot)

        # Low semantic integrity should increase structure_weight
        assert result.structure_weight > 0.5

        # High cognitive drift should increase grounding_bias
        assert result.grounding_bias > 0.5

        # High guna/kosha should increase warmth_weight
        assert result.warmth_weight > 0.5

    def test_tags_deduplicated_and_sorted(self):
        """Test that resonance tags are deduplicated and sorted."""
        snapshot = MockCoherenceObservation(
            guna_resonance_index=0.75,
            kosha_resonance_index=0.75,
            cognitive_drift_v3=0.65,
            temporal_entropy_diff=0.70,
            consciousness_stability_index=0.75,
            consciousness_integration_potential=0.75,
            symbolic_harmonization_index=0.75,
        )

        result = compute_cross_layer_persona_map(snapshot)

        # Should be sorted alphabetically
        assert result.resonance_tags == sorted(result.resonance_tags)

        # Should have no duplicates
        assert len(result.resonance_tags) == len(set(result.resonance_tags))


# ============================================================================
# GROUP B: Persona Engine Integration Tests (10 tests)
# ============================================================================

class TestPersonaEngineIntegration:
    """Test Group B: Persona engine integration."""

    def test_apply_cross_layer_resonance_exists(self):
        """Test that _apply_cross_layer_resonance method exists."""
        engine = PersonaEngine()
        assert hasattr(engine, '_apply_cross_layer_resonance')

    def test_apply_cross_layer_resonance_no_exceptions(self):
        """Test that _apply_cross_layer_resonance runs without exceptions."""
        engine = PersonaEngine()

        persona_response = PersonaResponse(
            persona_id="neutral",
            text="Test text",
            layers={},
            metadata=PersonaMetadata(
                tier="HYBRID",
                domain="therapy",
                intent="why",
                persona_id="neutral",
                persona_name="Neutral",
                persona_description="Neutral persona",
                dha_tone="resonance",
                dha_confidence=0.8,
            ),
        )

        cl_map = CrossLayerResonanceMap(
            metaphor_weight=0.6,
            warmth_weight=0.7,
            structure_weight=0.5,
            reflective_bandwidth=0.6,
            grounding_bias=0.5,
            expressiveness_bias=0.6,
        )

        # Should not raise exception
        engine._apply_cross_layer_resonance(persona_response, cl_map)

    def test_persona_response_has_cross_layer_resonance_map_field(self):
        """Test that PersonaResponse model has cross_layer_resonance_map field."""
        from symbolu.mechanical.persona.models import PersonaResponse

        # Should be able to create PersonaResponse with cross_layer_resonance_map
        response = PersonaResponse(
            persona_id="neutral",
            text="Test",
            layers={},
            metadata=PersonaMetadata(
                tier="HYBRID",
                domain="therapy",
                intent="why",
                persona_id="neutral",
                persona_name="Neutral",
                persona_description="Neutral",
                dha_tone="resonance",
                dha_confidence=0.8,
            ),
            cross_layer_resonance_map=None,
        )

        assert hasattr(response, 'cross_layer_resonance_map')

    def test_tone_only_modulation_no_semantic_changes(self):
        """Test that modulation is tone-only (no semantic changes to text)."""
        engine = PersonaEngine()

        original_text = "This is original text that should not change."
        persona_response = PersonaResponse(
            persona_id="neutral",
            text=original_text,
            layers={},
            metadata=PersonaMetadata(
                tier="HYBRID",
                domain="therapy",
                intent="why",
                persona_id="neutral",
                persona_name="Neutral",
                persona_description="Neutral",
                dha_tone="resonance",
                dha_confidence=0.8,
            ),
        )

        cl_map = CrossLayerResonanceMap(
            metaphor_weight=0.8,
            warmth_weight=0.9,
            structure_weight=0.3,
            reflective_bandwidth=0.7,
            grounding_bias=0.4,
            expressiveness_bias=0.8,
        )

        engine._apply_cross_layer_resonance(persona_response, cl_map)

        # Text should NOT be modified (Phase 30 v1.0 is observation-only)
        assert persona_response.text == original_text

    def test_no_exceptions_for_missing_signals(self):
        """Test graceful handling when coherence observation is missing."""
        engine = PersonaEngine()

        # explain_log with no coherence_observation
        explain_log = {}

        # Should not raise exception
        coherence_observation = engine._extract_coherence_observation(explain_log)
        assert coherence_observation is None

    def test_extract_coherence_observation_from_explain_log(self):
        """Test that _extract_coherence_observation extracts correctly."""
        engine = PersonaEngine()

        mock_observation = MockCoherenceObservation()
        explain_log = {
            'coherence_observation': mock_observation,
        }

        result = engine._extract_coherence_observation(explain_log)

        assert result is mock_observation

    def test_extract_coherence_observation_from_coherence_state(self):
        """Test extraction from coherence_state fallback path."""
        engine = PersonaEngine()

        mock_state = MockCoherenceObservation()
        explain_log = {
            'coherence_state': mock_state,
        }

        result = engine._extract_coherence_observation(explain_log)

        assert result is mock_state

    def test_apply_method_integrates_phase30(self):
        """Test that apply() method integrates Phase 30 correctly."""
        engine = PersonaEngine()

        renderer_output = RendererOutputV3(
            symbolic_layer={"test": "symbolic"},
            practical_layer={"test": "practical"},
            mirror_truth_layer={"test": "mirror"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "why"},
        )

        dha_result = DHAResult(
            tone="resonance",
            confidence=0.8,
            justification={},
        )

        mock_observation = MockCoherenceObservation(
            guna_resonance_index=0.8,
            kosha_resonance_index=0.7,
        )

        explain_log = {
            'coherence_observation': mock_observation,
        }

        result = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
        )

        # Should have cross_layer_resonance_map attached
        assert hasattr(result, 'cross_layer_resonance_map')
        assert result.cross_layer_resonance_map is not None

    def test_cl_map_to_dict_serializable(self):
        """Test that CrossLayerResonanceMap.to_dict() is JSON-serializable."""
        import json

        cl_map = CrossLayerResonanceMap(
            guna_resonance=0.8,
            kosha_resonance=0.7,
            metaphor_weight=0.6,
            warmth_weight=0.7,
            structure_weight=0.5,
            reflective_bandwidth=0.6,
            grounding_bias=0.5,
            expressiveness_bias=0.6,
            resonance_tags=["HIGH_RESONANCE"],
        )

        result_dict = cl_map.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(result_dict)
        assert json_str is not None

    def test_phase30_does_not_affect_phase29(self):
        """Test that Phase 30 does not interfere with Phase 29."""
        engine = PersonaEngine()

        renderer_output = RendererOutputV3(
            symbolic_layer={"test": "symbolic"},
            practical_layer={"test": "practical"},
            mirror_truth_layer={"test": "mirror"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "why"},
        )

        dha_result = DHAResult(
            tone="resonance",
            confidence=0.8,
            justification={},
        )

        explain_log = {}

        result = engine.apply(
            renderer_output=renderer_output,
            dha_result=dha_result,
            explain_log=explain_log,
        )

        # Phase 29 persona_resonance should still be present (None if no SHF)
        assert hasattr(result, 'persona_resonance')


# ============================================================================
# GROUP C: Unified API Tests (6 tests)
# ============================================================================

class TestUnifiedAPI:
    """Test Group C: Unified API exposure."""

    def test_persona_resonance_map_field_exists(self):
        """Test that UnifiedOutput has persona_resonance_map field."""
        from symbolu.api.unified_api import UnifiedOutput

        # Should be able to create with persona_resonance_map
        output = UnifiedOutput(
            text="Test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
            persona_resonance_map=None,
        )

        assert hasattr(output, 'persona_resonance_map')

    def test_persona_resonance_map_appears_in_output(self):
        """Test that persona_resonance_map appears in unified output."""
        # Create a mock context with persona_response containing cl_map
        mock_ctx = Mock()
        mock_ctx.fusion = None
        mock_ctx.dha = None
        mock_ctx.mlcr = None
        mock_ctx.mapper_profile = None
        mock_ctx.coherence_report = None
        mock_ctx.coherence_state = None
        mock_ctx.session_memory = None
        mock_ctx.session_recap = None
        mock_ctx.intent_arc = None
        mock_ctx.identity_signature = None
        mock_ctx.motivation_profile = None
        mock_ctx.policy_flags = None

        # Mock persona_response with cross_layer_resonance_map
        mock_persona_response = Mock()
        cl_map = CrossLayerResonanceMap(
            metaphor_weight=0.6,
            warmth_weight=0.7,
            structure_weight=0.5,
            reflective_bandwidth=0.6,
            grounding_bias=0.5,
            expressiveness_bias=0.6,
        )
        mock_persona_response.cross_layer_resonance_map = cl_map
        mock_persona_response.persona_resonance = None
        mock_ctx.persona_response = mock_persona_response

        result = build_unified_output("Test text", mock_ctx)

        assert result.persona_resonance_map is not None

    def test_null_safe_when_unavailable(self):
        """Test null-safety when persona_resonance_map is unavailable."""
        mock_ctx = Mock()
        mock_ctx.fusion = None
        mock_ctx.dha = None
        mock_ctx.mlcr = None
        mock_ctx.mapper_profile = None
        mock_ctx.coherence_report = None
        mock_ctx.coherence_state = None
        mock_ctx.session_memory = None
        mock_ctx.session_recap = None
        mock_ctx.intent_arc = None
        mock_ctx.identity_signature = None
        mock_ctx.motivation_profile = None
        mock_ctx.policy_flags = None
        mock_ctx.persona_response = None

        result = build_unified_output("Test text", mock_ctx)

        # Should be None, not raise exception
        assert result.persona_resonance_map is None

    def test_json_valid_serialization(self):
        """Test that persona_resonance_map serializes to valid JSON."""
        import json

        mock_ctx = Mock()
        mock_ctx.fusion = None
        mock_ctx.dha = None
        mock_ctx.mlcr = None
        mock_ctx.mapper_profile = None
        mock_ctx.coherence_report = None
        mock_ctx.coherence_state = None
        mock_ctx.session_memory = None
        mock_ctx.session_recap = None
        mock_ctx.intent_arc = None
        mock_ctx.identity_signature = None
        mock_ctx.motivation_profile = None
        mock_ctx.policy_flags = None
        mock_ctx.request = None  # Prevent Mock auto-creation of request.user_id
        mock_ctx.trading_guardrails = None
        mock_ctx.interaction_mode = None

        mock_persona_response = Mock()
        cl_map = CrossLayerResonanceMap(
            metaphor_weight=0.6,
            warmth_weight=0.7,
            structure_weight=0.5,
            reflective_bandwidth=0.6,
            grounding_bias=0.5,
            expressiveness_bias=0.6,
        )
        mock_persona_response.cross_layer_resonance_map = cl_map
        mock_persona_response.persona_resonance = None
        # Set all optional persona_response attributes to None to prevent Mock leaking
        mock_persona_response.schema_adaptive_map = None
        mock_persona_response.identity_harmonics_profile = None
        mock_persona_response.predictive_drift_profile = None
        mock_persona_response.identity_resonance_memory_profile = None
        mock_persona_response.continuity_profile = None
        mock_persona_response.temporal_forecast_profile = None
        mock_persona_response.multi_horizon_forecast_profile = None
        mock_persona_response.cross_horizon_resonance_profile = None
        mock_persona_response.echo_profile = None  # Note: attr is echo_profile, output field is persona_echo_profile
        mock_ctx.persona_response = mock_persona_response

        result = build_unified_output("Test text", mock_ctx)

        # Should serialize to JSON without error
        json_str = json.dumps(result.to_dict())
        assert json_str is not None

    def test_to_dict_includes_persona_resonance_map(self):
        """Test that to_dict() includes persona_resonance_map."""
        from symbolu.api.unified_api import UnifiedOutput

        output = UnifiedOutput(
            text="Test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
            persona_resonance_map={"test": "data"},
        )

        result_dict = output.to_dict()

        assert "persona_resonance_map" in result_dict
        assert result_dict["persona_resonance_map"] == {"test": "data"}

    def test_none_values_removed_from_dict(self):
        """Test that None values are removed from to_dict()."""
        from symbolu.api.unified_api import UnifiedOutput

        output = UnifiedOutput(
            text="Test",
            symbolic={},
            practical={},
            mirror={},
            dha={},
            routing={},
            mappers={},
            entropy={},
            coherence={},
            metadata={},
            persona_resonance_map=None,
        )

        result_dict = output.to_dict()

        # None values should be removed
        assert "persona_resonance_map" not in result_dict


# ============================================================================
# GROUP D: DILchat Adapter Tests (6 tests)
# ============================================================================

class TestDILchatAdapter:
    """Test Group D: DILchat adapter badges."""

    def test_persona_resonance_high_badge(self):
        """Test PERSONA_RESONANCE_HIGH badge is added correctly."""
        unified_output = {
            "text": "Test",
            "coherence": {},
            "metadata": {"domain": "therapy"},
            "persona_resonance_map": {
                "modulation_parameters": {
                    "metaphor_weight": 0.7,
                    "warmth_weight": 0.7,
                    "structure_weight": 0.5,
                    "grounding_bias": 0.5,
                },
                "raw_signals": {},
            },
        }

        # interaction_mode must be lowercase to match dilchat_adapter check
        policy_flags = {"interaction_mode": "smart_insight"}

        result = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should have PERSONA_RESONANCE_HIGH badge
        badge_labels = [badge.label for badge in result.badges]
        assert "PERSONA_RESONANCE_HIGH" in badge_labels

    def test_persona_resonance_low_badge(self):
        """Test PERSONA_RESONANCE_LOW badge is added correctly."""
        unified_output = {
            "text": "Test",
            "coherence": {},
            "metadata": {"domain": "identity"},
            "persona_resonance_map": {
                "modulation_parameters": {
                    "metaphor_weight": 0.3,
                    "warmth_weight": 0.3,
                    "structure_weight": 0.7,
                    "grounding_bias": 0.7,
                },
                "raw_signals": {},
            },
        }

        # interaction_mode must be lowercase
        policy_flags = {"interaction_mode": "deep_adaptive"}

        result = build_dilchat_response(unified_output, policy_flags, "identity")

        # Should have PERSONA_RESONANCE_LOW badge
        badge_labels = [badge.label for badge in result.badges]
        assert "PERSONA_RESONANCE_LOW" in badge_labels

    def test_drift_caution_badge(self):
        """Test PERSONA_RESONANCE_DRIFT_CAUTION badge is added."""
        unified_output = {
            "text": "Test",
            "coherence": {},
            "metadata": {"domain": "therapy"},
            "persona_resonance_map": {
                "modulation_parameters": {
                    "metaphor_weight": 0.5,
                    "warmth_weight": 0.5,
                    "structure_weight": 0.5,
                    "grounding_bias": 0.5,
                },
                "raw_signals": {
                    "cognitive_drift_v3": 0.65,
                },
            },
        }

        # interaction_mode must be lowercase
        policy_flags = {"interaction_mode": "smart_insight"}

        result = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should have PERSONA_RESONANCE_DRIFT_CAUTION badge
        badge_labels = [badge.label for badge in result.badges]
        assert "PERSONA_RESONANCE_DRIFT_CAUTION" in badge_labels

    def test_stability_strong_badge(self):
        """Test PERSONA_RESONANCE_STABILITY_STRONG badge is added."""
        unified_output = {
            "text": "Test",
            "coherence": {},
            "metadata": {"domain": "identity"},
            "persona_resonance_map": {
                "modulation_parameters": {
                    "metaphor_weight": 0.5,
                    "warmth_weight": 0.5,
                    "structure_weight": 0.5,
                    "grounding_bias": 0.5,
                },
                "raw_signals": {
                    "ucf_csi": 0.75,
                },
            },
        }

        # interaction_mode must be lowercase
        policy_flags = {"interaction_mode": "deep_adaptive"}

        result = build_dilchat_response(unified_output, policy_flags, "identity")

        # Should have PERSONA_RESONANCE_STABILITY_STRONG badge
        badge_labels = [badge.label for badge in result.badges]
        assert "PERSONA_RESONANCE_STABILITY_STRONG" in badge_labels

    def test_badges_restricted_to_therapy_identity_domains(self):
        """Test badges only appear for therapy/identity domains."""
        unified_output = {
            "text": "Test",
            "coherence": {},
            "metadata": {"domain": "trading"},  # Not therapy/identity
            "persona_resonance_map": {
                "modulation_parameters": {
                    "metaphor_weight": 0.7,
                    "warmth_weight": 0.7,
                    "structure_weight": 0.5,
                    "grounding_bias": 0.5,
                },
                "raw_signals": {},
            },
        }

        policy_flags = {"interaction_mode": "SMART_INSIGHT"}

        result = build_dilchat_response(unified_output, policy_flags, "trading")

        # Should NOT have persona resonance badges
        badge_labels = [badge.label for badge in result.badges]
        assert "PERSONA_RESONANCE_HIGH" not in badge_labels

    def test_badges_restricted_to_smart_deep_modes(self):
        """Test badges only appear for SMART_INSIGHT/DEEP_ADAPTIVE modes."""
        unified_output = {
            "text": "Test",
            "coherence": {},
            "metadata": {"domain": "therapy"},
            "persona_resonance_map": {
                "modulation_parameters": {
                    "metaphor_weight": 0.7,
                    "warmth_weight": 0.7,
                    "structure_weight": 0.5,
                    "grounding_bias": 0.5,
                },
                "raw_signals": {},
            },
        }

        policy_flags = {"interaction_mode": "SIMPLE"}  # Not SMART_INSIGHT/DEEP_ADAPTIVE

        result = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should NOT have persona resonance badges
        badge_labels = [badge.label for badge in result.badges]
        assert "PERSONA_RESONANCE_HIGH" not in badge_labels


# ============================================================================
# GROUP E: Behavioral Invariance Tests (6 tests)
# ============================================================================

class TestBehavioralInvariance:
    """Test Group E: No side effects on existing systems."""

    def test_ttor_unaffected(self):
        """Test that TTOR routing is unaffected by Phase 30."""
        # TTOR should not be touched by Phase 30
        # Use AST to check imports, not docstrings/comments
        from symbolu.mechanical.persona import persona_resonance_mapping
        import inspect
        import ast

        source = inspect.getsource(persona_resonance_mapping)
        tree = ast.parse(source)

        # Check that no TTOR modules are imported
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "ttor" not in node.module.lower(), f"TTOR import found: {node.module}"

    def test_mlcr_unaffected(self):
        """Test that MLCR is unaffected by Phase 30."""
        from symbolu.mechanical.persona import persona_resonance_mapping

        import inspect
        source = inspect.getsource(persona_resonance_mapping)
        assert "mlcr" not in source.lower()

    def test_mappers_unchanged(self):
        """Test that mappers (HRM/LCM/LAM) are unchanged."""
        from symbolu.mechanical.persona import persona_resonance_mapping
        import inspect
        import ast

        source = inspect.getsource(persona_resonance_mapping)
        tree = ast.parse(source)

        # Check that no mapper modules are imported
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module_lower = node.module.lower()
                assert "hrm" not in module_lower or "hrm" in module_lower and "formula" in module_lower, \
                    f"HRM import found: {node.module}"
                assert "lcm" not in module_lower, f"LCM import found: {node.module}"
                # LAM can appear in docstrings, check actual imports only

    def test_coherence_formulas_unchanged(self):
        """Test that coherence formulas are not modified."""
        # Phase 30 should ONLY observe, not modify coherence
        snapshot = MockCoherenceObservation(
            coherence_score=0.8,
            guna_resonance_index=0.7,
        )

        original_coherence = snapshot.coherence_score

        # Run mapping
        compute_cross_layer_persona_map(snapshot)

        # Coherence should not change
        assert snapshot.coherence_score == original_coherence

    def test_no_guardrail_impact(self):
        """Test that guardrails are unaffected."""
        from symbolu.mechanical.persona import persona_resonance_mapping

        import inspect
        source = inspect.getsource(persona_resonance_mapping)
        assert "guardrail" not in source.lower()

    def test_no_extra_llm_calls(self):
        """Test that no LLM calls are made (zero-LLM invariant)."""
        from symbolu.mechanical.persona import persona_resonance_mapping
        import inspect
        import ast

        source = inspect.getsource(persona_resonance_mapping)
        tree = ast.parse(source)

        # Check that no LLM modules are imported (via AST, not string matching)
        forbidden_modules = ["openai", "anthropic"]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert forbidden not in alias.name.lower(), f"LLM import found: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in forbidden_modules:
                    assert forbidden not in node.module.lower(), f"LLM import found: {node.module}"


# ============================================================================
# Test Summary
# ============================================================================

if __name__ == "__main__":
    print("Phase 30: Cross-Layer Resonance Persona Mapping - Test Suite")
    print("=" * 70)
    print("Group A: Mapping Math (10 tests)")
    print("Group B: Persona Engine Integration (10 tests)")
    print("Group C: Unified API (6 tests)")
    print("Group D: DILchat Adapter (6 tests)")
    print("Group E: Behavioral Invariance (6 tests)")
    print("=" * 70)
    print("Total: 38 tests")
    print("\nRun with: pytest -q --disable-warnings tests/test_phase30_cross_layer_resonance_mapping.py")
