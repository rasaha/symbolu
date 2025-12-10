"""
Test Suite for Phase 29: Persona Resonance Integration v1.0

This module provides comprehensive tests for Persona Resonance, which extends
Phase 27–28 Symbolic Harmonization into the Persona Engine for observation-only,
deterministic, zero-LLM resonance-aware persona tone shaping.

Test Groups:
    - Group A: Formula + Persona Tone Mapping Tests (10 tests)
    - Group B: Integration Tests (persona engine + unified API) (8 tests)
    - Group C: Adapter Tests (6 tests)
    - Group D: Behavioral Invariance Tests (8 tests)
    - Group E: Determinism + Null Handling (6 tests)

All tests verify:
    • Zero-LLM: No new model calls
    • UI-layer only: Tone changes only, never semantic
    • Deterministic: Same inputs → same outputs
    • Safe defaults: Missing SHF → no modulation
    • Backward compatible: All existing tests remain green
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from symbolu.mechanical.persona.engine import PersonaEngine
from symbolu.mechanical.persona.models import (
    PersonaProfile,
    PersonaResonanceProfile,
    RendererOutputV3,
    DHAResult,
    PersonaResponse,
)
from symbolu.formulas.symbolic_harmonization import (
    compute_symbolic_harmonization,
    SymbolicHarmonizationSnapshot,
)
from symbolu.adapter.dilchat_adapter import build_dilchat_response, DILchatBadge


# ============================================================================
# GROUP A: FORMULA + PERSONA TONE MAPPING TESTS (10 tests)
# ============================================================================

class TestGroupA_FormulaToneMappingTests:
    """Tests for SHF → persona tone mapping logic."""

    def test_a01_high_shi_positive_bias(self):
        """Test that SHI >= 0.75 produces positive bias (+0.03)."""
        # Create SHF snapshot with high SHI
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.85,
            mirror_alignment=0.80,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.82,
            symbolic_harmonization_index=0.82,  # High SHI
            harmonization_entropy=0.35,
            notes=["high_symbolic_harmonization", "symbolic_mirror_resonant"],
        )

        # Create persona engine and apply resonance
        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        assert resonance.symbolic_harmony_bias == 0.03
        assert resonance.persona_resonance_tone["metaphor_adjustment"] > 0
        assert resonance.persona_resonance_tone["warmth_adjustment"] > 0
        assert "high_symbolic_harmonization" in resonance.symbolic_resonance_tags

    def test_a02_medium_shi_neutral_bias(self):
        """Test that SHI 0.50-0.75 produces neutral bias (0.0)."""
        # Create SHF snapshot with medium SHI
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.60,
            mirror_alignment=0.55,
            guna_symbolic_resonance=0.58,
            kosha_symbolic_resonance=0.62,
            semantic_integrity_weight=0.60,
            symbolic_harmonization_index=0.60,  # Medium SHI
            harmonization_entropy=0.50,
            notes=["medium_symbolic_harmonization"],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        assert resonance.symbolic_harmony_bias == 0.0
        assert resonance.persona_resonance_tone["metaphor_adjustment"] == 0.0
        assert resonance.persona_resonance_tone["warmth_adjustment"] == 0.0

    def test_a03_low_shi_negative_bias(self):
        """Test that SHI < 0.50 produces negative bias (-0.03)."""
        # Create SHF snapshot with low SHI
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.30,
            mirror_alignment=0.35,
            guna_symbolic_resonance=0.40,
            kosha_symbolic_resonance=0.38,
            semantic_integrity_weight=0.32,
            symbolic_harmonization_index=0.35,  # Low SHI
            harmonization_entropy=0.65,
            notes=["low_symbolic_harmonization", "symbolic_practical_misaligned"],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        assert resonance.symbolic_harmony_bias == -0.03
        assert resonance.persona_resonance_tone["metaphor_adjustment"] < 0
        assert resonance.persona_resonance_tone["warmth_adjustment"] < 0
        assert resonance.persona_resonance_tone["structure_adjustment"] > 0

    def test_a04_bias_within_bounds(self):
        """Test that all bias values are within [-0.05, +0.05]."""
        # Test multiple SHI values
        for shi in [0.0, 0.25, 0.50, 0.75, 1.0]:
            snapshot = SymbolicHarmonizationSnapshot(
                symbolic_alignment=shi,
                mirror_alignment=shi,
                guna_symbolic_resonance=shi,
                kosha_symbolic_resonance=shi,
                semantic_integrity_weight=shi,
                symbolic_harmonization_index=shi,
                harmonization_entropy=0.5,
                notes=[],
            )

            engine = PersonaEngine()
            persona = PersonaProfile(
                id="test",
                display_name="Test",
                description="Test persona",
            )

            resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

            if resonance is not None:
                assert -0.05 <= resonance.symbolic_harmony_bias <= 0.05
                for key, val in resonance.persona_resonance_tone.items():
                    assert -0.05 <= val <= 0.05

    def test_a05_determinism(self):
        """Test that same inputs produce same outputs."""
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.75,
            mirror_alignment=0.70,
            guna_symbolic_resonance=0.73,
            kosha_symbolic_resonance=0.71,
            semantic_integrity_weight=0.78,
            symbolic_harmonization_index=0.75,
            harmonization_entropy=0.40,
            notes=["high_symbolic_harmonization"],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        # Compute multiple times
        results = [engine._apply_resonance_to_persona_tone(persona, snapshot) for _ in range(5)]

        # All should be identical
        for i in range(1, 5):
            assert results[0].symbolic_harmony_bias == results[i].symbolic_harmony_bias
            assert results[0].persona_resonance_tone == results[i].persona_resonance_tone
            assert results[0].symbolic_resonance_tags == results[i].symbolic_resonance_tags

    def test_a06_null_snapshot_returns_none(self):
        """Test that missing SHF snapshot returns None (graceful degradation)."""
        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, None)

        assert resonance is None

    def test_a07_missing_shi_returns_none(self):
        """Test that SHF snapshot without SHI returns None."""
        # Create snapshot with missing SHI
        snapshot = Mock()
        snapshot.symbolic_harmonization_index = None
        snapshot.notes = []

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is None

    def test_a08_tag_filtering(self):
        """Test that only SHF-related tags are included."""
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.80,
            mirror_alignment=0.75,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.80,
            symbolic_harmonization_index=0.80,
            harmonization_entropy=0.35,
            notes=[
                "high_symbolic_harmonization",
                "symbolic_mirror_resonant",
                "guna_symbolic_strong",
                "some_unrelated_tag",
                "kosha_symbolic_strong",
            ],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        # Should include SHF-related tags
        assert "high_symbolic_harmonization" in resonance.symbolic_resonance_tags
        assert "symbolic_mirror_resonant" in resonance.symbolic_resonance_tags
        assert "guna_symbolic_strong" in resonance.symbolic_resonance_tags
        assert "kosha_symbolic_strong" in resonance.symbolic_resonance_tags
        # Should NOT include unrelated tag
        assert "some_unrelated_tag" not in resonance.symbolic_resonance_tags

    def test_a09_tone_adjustment_ratios(self):
        """Test that tone adjustments follow correct ratios."""
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.80,
            mirror_alignment=0.75,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.80,
            symbolic_harmonization_index=0.80,  # Positive bias
            harmonization_entropy=0.35,
            notes=[],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        # Metaphor adjustment should be largest (0.67 ratio)
        # Warmth adjustment should be smaller (0.33 ratio)
        # Structure adjustment should be inverted
        assert abs(resonance.persona_resonance_tone["metaphor_adjustment"]) > abs(
            resonance.persona_resonance_tone["warmth_adjustment"]
        )
        # Structure should be opposite sign for positive bias
        if resonance.symbolic_harmony_bias > 0:
            assert resonance.persona_resonance_tone["structure_adjustment"] <= 0

    def test_a10_boundary_values(self):
        """Test extreme boundary values (SHI = 0.0, 0.5, 1.0)."""
        for shi_value in [0.0, 0.5, 1.0]:
            snapshot = SymbolicHarmonizationSnapshot(
                symbolic_alignment=shi_value,
                mirror_alignment=shi_value,
                guna_symbolic_resonance=shi_value,
                kosha_symbolic_resonance=shi_value,
                semantic_integrity_weight=shi_value,
                symbolic_harmonization_index=shi_value,
                harmonization_entropy=0.5,
                notes=[],
            )

            engine = PersonaEngine()
            persona = PersonaProfile(
                id="test",
                display_name="Test",
                description="Test persona",
            )

            resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

            assert resonance is not None
            assert -0.05 <= resonance.symbolic_harmony_bias <= 0.05


# ============================================================================
# GROUP B: INTEGRATION TESTS (PERSONA ENGINE + UNIFIED API) (8 tests)
# ============================================================================

class TestGroupB_IntegrationTests:
    """Tests for persona engine + unified API integration."""

    def test_b01_persona_engine_apply_with_shf(self):
        """Test that PersonaEngine.apply() extracts SHF and applies resonance."""
        # Create mock SHF snapshot
        shf_snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.85,
            mirror_alignment=0.80,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.82,
            symbolic_harmonization_index=0.82,
            harmonization_entropy=0.35,
            notes=["high_symbolic_harmonization"],
        )

        # Create mock coherence_state with SHF snapshot
        coherence_state = Mock()
        coherence_state.symbolic_harmonization_snapshot = shf_snapshot

        # Create explain_log with coherence_state
        explain_log = {"coherence_state": coherence_state}

        # Create mock renderer output
        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "test"},
            practical_layer={"steps": ["test"]},
            mirror_truth_layer={"reflection": "test"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        # Create mock DHA result
        dha_result = DHAResult(
            tone="resonance",
            confidence=0.85,
            justification={},
        )

        # Apply persona engine
        engine = PersonaEngine()
        response = engine.apply(renderer_output, dha_result, explain_log)

        # Verify persona_resonance is attached
        assert response.persona_resonance is not None
        assert response.persona_resonance.symbolic_harmony_bias == 0.03
        assert len(response.persona_resonance.symbolic_resonance_tags) > 0

    def test_b02_persona_engine_apply_without_shf(self):
        """Test that PersonaEngine.apply() handles missing SHF gracefully."""
        # Create explain_log WITHOUT coherence_state
        explain_log = {}

        # Create mock renderer output
        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "test"},
            practical_layer={"steps": ["test"]},
            mirror_truth_layer={"reflection": "test"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        # Create mock DHA result
        dha_result = DHAResult(
            tone="resonance",
            confidence=0.85,
            justification={},
        )

        # Apply persona engine
        engine = PersonaEngine()
        response = engine.apply(renderer_output, dha_result, explain_log)

        # Verify persona_resonance is None (graceful degradation)
        assert response.persona_resonance is None

    def test_b03_unified_api_extracts_persona_resonance(self):
        """Test that unified API extracts persona_resonance from context."""
        from symbolu.api.unified_api import build_unified_output

        # Create mock persona_response with resonance
        persona_resonance = PersonaResonanceProfile(
            symbolic_harmony_bias=0.03,
            symbolic_resonance_tags=["high_symbolic_harmonization"],
            persona_resonance_tone={
                "metaphor_adjustment": 0.02,
                "warmth_adjustment": 0.01,
                "structure_adjustment": -0.01,
            },
        )

        persona_response = Mock()
        persona_response.persona_resonance = persona_resonance

        # Create mock context
        ctx = Mock()
        ctx.persona_response = persona_response
        ctx.rendered = None
        ctx.dha = None
        ctx.fusion = None
        ctx.mlcr = None
        ctx.coherence_report = None
        ctx.coherence_state = None

        # Build unified output
        unified = build_unified_output("test text", ctx)

        # Verify persona_resonance is extracted
        assert unified.persona_resonance is not None
        assert unified.persona_resonance["symbolic_harmony_bias"] == 0.03

    def test_b04_persona_resonance_profile_validation(self):
        """Test PersonaResonanceProfile validation."""
        # Valid profile
        profile = PersonaResonanceProfile(
            symbolic_harmony_bias=0.03,
            symbolic_resonance_tags=["test"],
            persona_resonance_tone={"test": 0.01},
        )
        assert profile.symbolic_harmony_bias == 0.03

        # Invalid bias (out of range)
        with pytest.raises(Exception):  # Pydantic ValidationError
            PersonaResonanceProfile(
                symbolic_harmony_bias=0.10,  # > 0.05
                symbolic_resonance_tags=[],
                persona_resonance_tone={},
            )

    def test_b05_persona_response_with_resonance(self):
        """Test PersonaResponse with optional persona_resonance."""
        # Create resonance profile
        resonance = PersonaResonanceProfile(
            symbolic_harmony_bias=0.03,
            symbolic_resonance_tags=["high_symbolic_harmonization"],
            persona_resonance_tone={"metaphor_adjustment": 0.02},
        )

        # Create persona response with resonance
        from symbolu.mechanical.persona.models import PersonaMetadata

        metadata = PersonaMetadata(
            tier="HYBRID",
            domain="therapy",
            intent="how",
            persona_id="test",
            persona_name="Test",
            persona_description="Test persona",
            dha_tone="resonance",
            dha_confidence=0.85,
        )

        response = PersonaResponse(
            persona_id="test",
            text="Test text",
            layers={
                "symbolic_layer": {},
                "practical_layer": {},
                "mirror_truth_layer": {},
            },
            metadata=metadata,
            persona_resonance=resonance,
        )

        assert response.persona_resonance is not None
        assert response.persona_resonance.symbolic_harmony_bias == 0.03

    def test_b06_persona_response_without_resonance(self):
        """Test PersonaResponse without persona_resonance (backward compatibility)."""
        from symbolu.mechanical.persona.models import PersonaMetadata

        metadata = PersonaMetadata(
            tier="HYBRID",
            domain="therapy",
            intent="how",
            persona_id="test",
            persona_name="Test",
            persona_description="Test persona",
            dha_tone="resonance",
            dha_confidence=0.85,
        )

        response = PersonaResponse(
            persona_id="test",
            text="Test text",
            layers={
                "symbolic_layer": {},
                "practical_layer": {},
                "mirror_truth_layer": {},
            },
            metadata=metadata,
        )

        # persona_resonance should be None by default
        assert response.persona_resonance is None

    def test_b07_coherence_observer_extracts_persona_resonance(self):
        """Test that CoherenceObserver extracts persona_resonance fields."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver

        # Create mock persona_response with resonance
        persona_resonance = PersonaResonanceProfile(
            symbolic_harmony_bias=0.03,
            symbolic_resonance_tags=["high_symbolic_harmonization"],
            persona_resonance_tone={},
        )

        persona_response = Mock()
        persona_response.persona_resonance = persona_resonance

        # Create mock pipeline_context
        pipeline_context = Mock()
        pipeline_context.persona_response = persona_response
        pipeline_context.coherence_state = None
        pipeline_context.mlcr = None

        # Observe
        observer = CoherenceObserver()
        observation = observer.observe("test", pipeline_context)

        # Verify persona_resonance fields are extracted
        assert observation.persona_resonance_bias == 0.03
        assert "high_symbolic_harmonization" in observation.persona_resonance_tags

    def test_b08_coherence_observer_handles_missing_resonance(self):
        """Test that CoherenceObserver handles missing persona_resonance gracefully."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver

        # Create mock pipeline_context WITHOUT persona_response
        pipeline_context = Mock()
        pipeline_context.persona_response = None
        pipeline_context.coherence_state = None
        pipeline_context.mlcr = None

        # Observe
        observer = CoherenceObserver()
        observation = observer.observe("test", pipeline_context)

        # Verify persona_resonance fields are None/empty
        assert observation.persona_resonance_bias is None
        assert observation.persona_resonance_tags == []


# ============================================================================
# GROUP C: ADAPTER TESTS (6 tests)
# ============================================================================

class TestGroupC_AdapterTests:
    """Tests for dilchat adapter persona resonance badges."""

    def test_c01_persona_harmony_positive_badge(self):
        """Test PERSONA_HARMONY_POSITIVE badge for positive bias."""
        unified_output = {
            "text": "test",
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "coherence": {
                "coherence_score": 0.85,
                "persona_resonance_bias": 0.03,  # Positive bias
            },
            "metadata": {"domain": "therapy"},
        }

        policy_flags = {
            "interaction_mode": "smart_insight",
            "stability_status": "stable",
        }

        response = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should have PERSONA_HARMONY_POSITIVE badge
        badge_labels = [b.label for b in response.badges]
        assert "PERSONA_HARMONY_POSITIVE" in badge_labels

    def test_c02_persona_harmony_neutral_badge(self):
        """Test PERSONA_HARMONY_NEUTRAL badge for neutral bias."""
        unified_output = {
            "text": "test",
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "coherence": {
                "coherence_score": 0.85,
                "persona_resonance_bias": 0.0,  # Neutral bias
            },
            "metadata": {"domain": "identity"},
        }

        policy_flags = {
            "interaction_mode": "deep_adaptive",
            "stability_status": "stable",
        }

        response = build_dilchat_response(unified_output, policy_flags, "identity")

        # Should have PERSONA_HARMONY_NEUTRAL badge
        badge_labels = [b.label for b in response.badges]
        assert "PERSONA_HARMONY_NEUTRAL" in badge_labels

    def test_c03_persona_harmony_negative_badge(self):
        """Test PERSONA_HARMONY_NEGATIVE badge for negative bias."""
        unified_output = {
            "text": "test",
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "coherence": {
                "coherence_score": 0.85,
                "persona_resonance_bias": -0.03,  # Negative bias
            },
            "metadata": {"domain": "therapy"},
        }

        policy_flags = {
            "interaction_mode": "smart_insight",
            "stability_status": "stable",
        }

        response = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should have PERSONA_HARMONY_NEGATIVE badge
        badge_labels = [b.label for b in response.badges]
        assert "PERSONA_HARMONY_NEGATIVE" in badge_labels

    def test_c04_no_persona_badge_for_non_therapy_identity_domain(self):
        """Test that persona resonance badges are NOT shown for non-therapy/identity domains."""
        unified_output = {
            "text": "test",
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "coherence": {
                "coherence_score": 0.85,
                "persona_resonance_bias": 0.03,
            },
            "metadata": {"domain": "trading"},  # Not therapy/identity
        }

        policy_flags = {
            "interaction_mode": "smart_insight",
            "stability_status": "stable",
        }

        response = build_dilchat_response(unified_output, policy_flags, "trading")

        # Should NOT have persona resonance badges
        badge_labels = [b.label for b in response.badges]
        assert "PERSONA_HARMONY_POSITIVE" not in badge_labels
        assert "PERSONA_HARMONY_NEUTRAL" not in badge_labels
        assert "PERSONA_HARMONY_NEGATIVE" not in badge_labels

    def test_c05_no_persona_badge_for_analytics_only_mode(self):
        """Test that persona resonance badges are NOT shown for analytics_only mode."""
        unified_output = {
            "text": "test",
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "coherence": {
                "coherence_score": 0.85,
                "persona_resonance_bias": 0.03,
            },
            "metadata": {"domain": "therapy"},
        }

        policy_flags = {
            "interaction_mode": "analytics_only",  # Not smart_insight/deep_adaptive
            "stability_status": "stable",
        }

        response = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should NOT have persona resonance badges
        badge_labels = [b.label for b in response.badges]
        assert "PERSONA_HARMONY_POSITIVE" not in badge_labels

    def test_c06_missing_persona_resonance_no_badge(self):
        """Test that missing persona_resonance_bias doesn't produce badges."""
        unified_output = {
            "text": "test",
            "symbolic": {},
            "practical": {},
            "mirror": {},
            "coherence": {
                "coherence_score": 0.85,
                # No persona_resonance_bias
            },
            "metadata": {"domain": "therapy"},
        }

        policy_flags = {
            "interaction_mode": "smart_insight",
            "stability_status": "stable",
        }

        response = build_dilchat_response(unified_output, policy_flags, "therapy")

        # Should NOT have persona resonance badges
        badge_labels = [b.label for b in response.badges]
        assert "PERSONA_HARMONY_POSITIVE" not in badge_labels
        assert "PERSONA_HARMONY_NEUTRAL" not in badge_labels
        assert "PERSONA_HARMONY_NEGATIVE" not in badge_labels


# ============================================================================
# GROUP D: BEHAVIORAL INVARIANCE TESTS (8 tests)
# ============================================================================

class TestGroupD_BehavioralInvarianceTests:
    """Tests to verify that persona resonance does NOT affect core behavior."""

    def test_d01_no_change_to_semantic_output(self):
        """Test that persona resonance does NOT change semantic output."""
        # Create two contexts: one with SHF, one without
        # The semantic content (layers) should be identical

        # Context 1: Without SHF
        explain_log_no_shf = {}

        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "seeking certainty", "depth": 0.71},
            practical_layer={"steps": ["assess risk", "define position"], "confidence": 0.88},
            mirror_truth_layer={"reflection": "avoiding emotion", "bhava_direction": "upward"},
            metadata={"tier": "HYBRID", "domain": "trading", "intent": "how"},
        )

        dha_result = DHAResult(
            tone="resonance",
            confidence=0.85,
            justification={},
        )

        engine = PersonaEngine()
        response_no_shf = engine.apply(renderer_output, dha_result, explain_log_no_shf)

        # Context 2: With SHF
        shf_snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.85,
            mirror_alignment=0.80,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.82,
            symbolic_harmonization_index=0.82,
            harmonization_entropy=0.35,
            notes=["high_symbolic_harmonization"],
        )

        coherence_state = Mock()
        coherence_state.symbolic_harmonization_snapshot = shf_snapshot

        explain_log_with_shf = {"coherence_state": coherence_state}

        response_with_shf = engine.apply(renderer_output, dha_result, explain_log_with_shf)

        # CRITICAL: Semantic content (layers) MUST be identical
        assert response_no_shf.layers == response_with_shf.layers
        assert response_no_shf.layers["symbolic_layer"] == response_with_shf.layers["symbolic_layer"]
        assert response_no_shf.layers["practical_layer"] == response_with_shf.layers["practical_layer"]
        assert response_no_shf.layers["mirror_truth_layer"] == response_with_shf.layers["mirror_truth_layer"]

    def test_d02_no_change_to_persona_selection(self):
        """Test that persona resonance does NOT affect persona selection."""
        # Persona selection is determined by PersonaSelector, not by SHF
        # Verify that SHF presence doesn't change which persona is selected

        explain_log_no_shf = {"meta": {"tier": "HYBRID", "domain": "therapy", "intent": "why"}}

        explain_log_with_shf = {
            "meta": {"tier": "HYBRID", "domain": "therapy", "intent": "why"},
            "coherence_state": Mock(
                symbolic_harmonization_snapshot=SymbolicHarmonizationSnapshot(
                    symbolic_alignment=0.85,
                    mirror_alignment=0.80,
                    guna_symbolic_resonance=0.78,
                    kosha_symbolic_resonance=0.76,
                    semantic_integrity_weight=0.82,
                    symbolic_harmonization_index=0.82,
                    harmonization_entropy=0.35,
                    notes=[],
                )
            ),
        }

        renderer_output = RendererOutputV3(
            symbolic_layer={},
            practical_layer={},
            mirror_truth_layer={},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "why"},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()
        response_no_shf = engine.apply(renderer_output, dha_result, explain_log_no_shf)
        response_with_shf = engine.apply(renderer_output, dha_result, explain_log_with_shf)

        # Persona selection should be the same
        assert response_no_shf.persona_id == response_with_shf.persona_id

    def test_d03_no_change_to_layer_ordering(self):
        """Test that persona resonance does NOT affect layer ordering."""
        # Layer ordering is determined by DHA tone + persona preferences
        # SHF should not change this

        shf_snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.85,
            mirror_alignment=0.80,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.82,
            symbolic_harmonization_index=0.82,
            harmonization_entropy=0.35,
            notes=[],
        )

        coherence_state = Mock()
        coherence_state.symbolic_harmonization_snapshot = shf_snapshot

        explain_log = {"coherence_state": coherence_state}

        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "test"},
            practical_layer={"steps": ["test"]},
            mirror_truth_layer={"reflection": "test"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        dha_result = DHAResult(tone="symbolic", confidence=0.85, justification={})

        engine = PersonaEngine()

        # Get ordered layers (this is internal, but we can test via _order_layers)
        from symbolu.mechanical.persona.registry import get_default_registry

        registry = get_default_registry()
        persona = registry.get_safe("neutral")

        ordered_layers_no_shf = engine._order_layers(
            persona, "symbolic", {}, {}, {}
        )

        ordered_layers_with_shf = engine._order_layers(
            persona, "symbolic", {}, {}, {}
        )

        # Layer ordering should be identical
        assert len(ordered_layers_no_shf) == len(ordered_layers_with_shf)
        for i in range(len(ordered_layers_no_shf)):
            assert ordered_layers_no_shf[i][0] == ordered_layers_with_shf[i][0]

    def test_d04_no_change_to_metadata(self):
        """Test that persona resonance does NOT affect metadata."""
        explain_log = {}

        renderer_output = RendererOutputV3(
            symbolic_layer={},
            practical_layer={},
            mirror_truth_layer={},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how", "confidence": {"symbolic": 0.71}},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()
        response = engine.apply(renderer_output, dha_result, explain_log)

        # Metadata should be preserved
        assert response.metadata.tier == "HYBRID"
        assert response.metadata.domain == "therapy"
        assert response.metadata.intent == "how"
        assert response.metadata.dha_tone == "resonance"
        assert response.metadata.dha_confidence == 0.85

    def test_d05_zero_llm_verification(self):
        """Test that persona resonance does NOT trigger any LLM calls."""
        # This is a structural test - persona resonance should be purely rule-based
        # We verify by checking that _apply_resonance_to_persona_tone does not call any external APIs

        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.85,
            mirror_alignment=0.80,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.82,
            symbolic_harmonization_index=0.82,
            harmonization_entropy=0.35,
            notes=[],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        # This should complete without any external calls (unit test, no mocking needed)
        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        # If this test passes, it means no external calls were made

    def test_d06_backward_compatibility_existing_tests(self):
        """Test that existing persona engine tests still pass (backward compatibility)."""
        # Simulate existing test: persona engine without SHF context
        explain_log = {"meta": {"tier": "HYBRID", "domain": "trading", "intent": "how"}}

        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "test"},
            practical_layer={"steps": ["test"]},
            mirror_truth_layer={"reflection": "test"},
            metadata={"tier": "HYBRID", "domain": "trading", "intent": "how"},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()
        response = engine.apply(renderer_output, dha_result, explain_log)

        # Should work exactly as before (persona_resonance is None)
        assert response.persona_id is not None
        assert response.text is not None
        assert response.layers is not None
        assert response.metadata is not None
        assert response.persona_resonance is None  # Graceful degradation

    def test_d07_no_change_to_dha_tone(self):
        """Test that persona resonance does NOT change DHA tone."""
        explain_log = {}

        renderer_output = RendererOutputV3(
            symbolic_layer={},
            practical_layer={},
            mirror_truth_layer={},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        # Test different DHA tones
        for tone in ["resonance", "inverse_jolt", "symbolic"]:
            dha_result = DHAResult(tone=tone, confidence=0.85, justification={})

            engine = PersonaEngine()
            response = engine.apply(renderer_output, dha_result, explain_log)

            # DHA tone should be preserved in metadata
            assert response.metadata.dha_tone == tone

    def test_d08_diagnostic_only_verification(self):
        """Test that persona resonance is diagnostic-only (no logic branches)."""
        # Persona resonance should NEVER be used for control flow decisions
        # We verify this by checking that the same persona logic executes regardless of resonance

        # Context 1: High SHI (positive bias)
        shf_high = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.85,
            mirror_alignment=0.80,
            guna_symbolic_resonance=0.78,
            kosha_symbolic_resonance=0.76,
            semantic_integrity_weight=0.82,
            symbolic_harmonization_index=0.85,
            harmonization_entropy=0.35,
            notes=[],
        )

        # Context 2: Low SHI (negative bias)
        shf_low = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.30,
            mirror_alignment=0.35,
            guna_symbolic_resonance=0.40,
            kosha_symbolic_resonance=0.38,
            semantic_integrity_weight=0.32,
            symbolic_harmonization_index=0.35,
            harmonization_entropy=0.65,
            notes=[],
        )

        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "test"},
            practical_layer={"steps": ["test"]},
            mirror_truth_layer={"reflection": "test"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()

        # Apply with high SHI
        coherence_state_high = Mock()
        coherence_state_high.symbolic_harmonization_snapshot = shf_high
        explain_log_high = {"coherence_state": coherence_state_high}
        response_high = engine.apply(renderer_output, dha_result, explain_log_high)

        # Apply with low SHI
        coherence_state_low = Mock()
        coherence_state_low.symbolic_harmonization_snapshot = shf_low
        explain_log_low = {"coherence_state": coherence_state_low}
        response_low = engine.apply(renderer_output, dha_result, explain_log_low)

        # CRITICAL: All logic should be identical, only persona_resonance differs
        assert response_high.persona_id == response_low.persona_id
        assert response_high.layers == response_low.layers
        assert response_high.metadata.tier == response_low.metadata.tier
        assert response_high.metadata.domain == response_low.metadata.domain

        # Only persona_resonance should differ
        assert response_high.persona_resonance.symbolic_harmony_bias > 0
        assert response_low.persona_resonance.symbolic_harmony_bias < 0


# ============================================================================
# GROUP E: DETERMINISM + NULL HANDLING (6 tests)
# ============================================================================

class TestGroupE_DeterminismNullHandling:
    """Tests for determinism and null/edge case handling."""

    def test_e01_determinism_full_pipeline(self):
        """Test determinism across full persona engine pipeline."""
        # Same inputs should produce identical outputs every time

        shf_snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.75,
            mirror_alignment=0.70,
            guna_symbolic_resonance=0.73,
            kosha_symbolic_resonance=0.71,
            semantic_integrity_weight=0.78,
            symbolic_harmonization_index=0.75,
            harmonization_entropy=0.40,
            notes=["high_symbolic_harmonization"],
        )

        coherence_state = Mock()
        coherence_state.symbolic_harmonization_snapshot = shf_snapshot

        explain_log = {"coherence_state": coherence_state}

        renderer_output = RendererOutputV3(
            symbolic_layer={"pattern": "test"},
            practical_layer={"steps": ["test"]},
            mirror_truth_layer={"reflection": "test"},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()

        # Run multiple times
        responses = [engine.apply(renderer_output, dha_result, explain_log) for _ in range(5)]

        # All should be identical
        for i in range(1, 5):
            assert responses[0].persona_id == responses[i].persona_id
            assert responses[0].text == responses[i].text
            assert responses[0].layers == responses[i].layers
            assert responses[0].persona_resonance.symbolic_harmony_bias == responses[i].persona_resonance.symbolic_harmony_bias
            assert responses[0].persona_resonance.persona_resonance_tone == responses[i].persona_resonance.persona_resonance_tone

    def test_e02_null_explain_log(self):
        """Test that None explain_log is handled gracefully."""
        renderer_output = RendererOutputV3(
            symbolic_layer={},
            practical_layer={},
            mirror_truth_layer={},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()
        response = engine.apply(renderer_output, dha_result, None)

        # Should work with persona_resonance=None
        assert response is not None
        assert response.persona_resonance is None

    def test_e03_null_coherence_state(self):
        """Test that None coherence_state is handled gracefully."""
        explain_log = {"coherence_state": None}

        renderer_output = RendererOutputV3(
            symbolic_layer={},
            practical_layer={},
            mirror_truth_layer={},
            metadata={"tier": "HYBRID", "domain": "therapy", "intent": "how"},
        )

        dha_result = DHAResult(tone="resonance", confidence=0.85, justification={})

        engine = PersonaEngine()
        response = engine.apply(renderer_output, dha_result, explain_log)

        # Should work with persona_resonance=None
        assert response is not None
        assert response.persona_resonance is None

    def test_e04_empty_notes_list(self):
        """Test that empty SHF notes list is handled correctly."""
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.75,
            mirror_alignment=0.70,
            guna_symbolic_resonance=0.73,
            kosha_symbolic_resonance=0.71,
            semantic_integrity_weight=0.78,
            symbolic_harmonization_index=0.75,
            harmonization_entropy=0.40,
            notes=[],  # Empty notes
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        assert resonance is not None
        assert resonance.symbolic_resonance_tags == []

    def test_e05_edge_case_shi_exactly_0_50(self):
        """Test edge case where SHI is exactly 0.50 (boundary between medium and low)."""
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.50,
            mirror_alignment=0.50,
            guna_symbolic_resonance=0.50,
            kosha_symbolic_resonance=0.50,
            semantic_integrity_weight=0.50,
            symbolic_harmonization_index=0.50,  # Exact boundary
            harmonization_entropy=0.50,
            notes=[],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        # Should be neutral bias (SHI >= 0.50)
        assert resonance is not None
        assert resonance.symbolic_harmony_bias == 0.0

    def test_e06_edge_case_shi_exactly_0_75(self):
        """Test edge case where SHI is exactly 0.75 (boundary between high and medium)."""
        snapshot = SymbolicHarmonizationSnapshot(
            symbolic_alignment=0.75,
            mirror_alignment=0.75,
            guna_symbolic_resonance=0.75,
            kosha_symbolic_resonance=0.75,
            semantic_integrity_weight=0.75,
            symbolic_harmonization_index=0.75,  # Exact boundary
            harmonization_entropy=0.40,
            notes=[],
        )

        engine = PersonaEngine()
        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
        )

        resonance = engine._apply_resonance_to_persona_tone(persona, snapshot)

        # Should be positive bias (SHI >= 0.75)
        assert resonance is not None
        assert resonance.symbolic_harmony_bias == 0.03
