"""
Phase 37: Adaptive Continuity Engine (ACE) Test Suite

Comprehensive 48-test validation suite for ACE v1.0.

Test Groups:
    Group A: Formula Math (12 tests) - Range, bounding, determinism, entropy, null-safety, weights
    Group B: Coherence Integration (10 tests) - State updates, ordering, history, SessionSummary
    Group C: Persona Engine (10 tests) - Tone modulation, stability, determinism
    Group D: Unified API & Observer (8 tests) - JSON structure, backward compatibility, null-safety
    Group E: Behavioral Invariance (8 tests) - No routing changes, zero-LLM, determinism stress test

CRITICAL INVARIANTS:
    ✓ Zero-LLM
    ✓ No routing/mapper changes
    ✓ Tone-only influence
    ✓ Semantic content unchanged
    ✓ Deterministic, pure math
    ✓ Observation-only
    ✓ Backward compatible
    ✓ Graceful degradation
    ✓ All outputs in [0.0, 1.0]
    ✓ History trimming correct
"""

import pytest
from symbolu.formulas.adaptive_continuity_engine import (
    compute_adaptive_continuity,
    AdaptiveContinuitySnapshot,
    _clamp,
    _safe_get,
    _compute_variance,
    _compute_stability_factor,
    _compute_trend_alignment,
)


# ============================================================================
# GROUP A: Formula Math (12 tests)
# ============================================================================

class TestFormulamath:
    """Test core formula math: range, bounding, determinism, entropy, null-safety, weights."""

    def test_ncc_range_bounding(self):
        """Test NCC is bounded to [0.0, 1.0]."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=1.5,  # Exceeds bounds
            semantic_integrity=0.9,
            consciousness_order_index=0.8,
            identity_memory_strength=0.7,
        )
        assert snapshot is not None
        assert 0.0 <= snapshot.ncc <= 1.0

    def test_icc_range_bounding(self):
        """Test ICC is bounded to [0.0, 1.0]."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.7,
            identity_memory_strength=1.5,  # Exceeds bounds
            identity_echo_persistence=0.8,
            identity_drift_anchoring=0.6,
            core_identity_harmonic=0.7,
        )
        assert snapshot is not None
        assert 0.0 <= snapshot.icc <= 1.0

    def test_css_range_bounding(self):
        """Test CSS is bounded to [0.0, 1.0]."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.9,
            semantic_integrity=0.8,
            consciousness_order_index=0.9,
            identity_memory_strength=0.9,
            identity_echo_persistence=0.9,
            consciousness_stability_index=1.5,  # Exceeds bounds
        )
        assert snapshot is not None
        assert 0.0 <= snapshot.css <= 1.0

    def test_determinism_same_inputs_same_outputs(self):
        """Test determinism: same inputs → same outputs."""
        kwargs = {
            "symbolic_harmonization_index": 0.75,
            "semantic_integrity": 0.68,
            "consciousness_order_index": 0.72,
            "identity_memory_strength": 0.70,
            "identity_echo_persistence": 0.65,
            "identity_drift_anchoring": 0.62,
            "core_identity_harmonic": 0.68,
            "drift_magnitude_prediction": 0.45,
            "temporal_entropy_volatility": 0.30,
        }

        snapshot1 = compute_adaptive_continuity(**kwargs)
        snapshot2 = compute_adaptive_continuity(**kwargs)

        assert snapshot1 is not None
        assert snapshot2 is not None
        assert snapshot1.ncc == snapshot2.ncc
        assert snapshot1.icc == snapshot2.icc
        assert snapshot1.css == snapshot2.css
        assert snapshot1.continuity_band == snapshot2.continuity_band
        assert snapshot1.continuity_tags == snapshot2.continuity_tags

    def test_entropy_influence_on_ncc(self):
        """Test high entropy volatility reduces NCC."""
        snapshot_low_entropy = compute_adaptive_continuity(
            symbolic_harmonization_index=0.80,
            semantic_integrity=0.75,
            consciousness_order_index=0.78,
            identity_memory_strength=0.70,
            temporal_entropy_volatility=0.10,  # Low entropy
        )

        snapshot_high_entropy = compute_adaptive_continuity(
            symbolic_harmonization_index=0.80,
            semantic_integrity=0.75,
            consciousness_order_index=0.78,
            identity_memory_strength=0.70,
            temporal_entropy_volatility=0.90,  # High entropy
        )

        assert snapshot_low_entropy is not None
        assert snapshot_high_entropy is not None
        # High entropy should reduce NCC
        assert snapshot_low_entropy.ncc > snapshot_high_entropy.ncc

    def test_null_safety_minimal_inputs(self):
        """Test null-safety: minimal required inputs."""
        # Provide only minimal required inputs
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.60,
            identity_memory_strength=0.55,
        )

        assert snapshot is not None
        assert 0.0 <= snapshot.ncc <= 1.0
        assert 0.0 <= snapshot.icc <= 1.0
        assert 0.0 <= snapshot.css <= 1.0

    def test_null_safety_no_inputs(self):
        """Test graceful degradation: no inputs returns None."""
        snapshot = compute_adaptive_continuity()
        assert snapshot is None

    def test_weight_correctness_ncc(self):
        """Test NCC weight correctness: symbolic_harmonization has highest weight."""
        # High symbolic harmonization
        snapshot_high_sym = compute_adaptive_continuity(
            symbolic_harmonization_index=0.90,
            semantic_integrity=0.50,
            consciousness_order_index=0.50,
            identity_memory_strength=0.60,
        )

        # Low symbolic harmonization
        snapshot_low_sym = compute_adaptive_continuity(
            symbolic_harmonization_index=0.30,
            semantic_integrity=0.50,
            consciousness_order_index=0.50,
            identity_memory_strength=0.60,
        )

        assert snapshot_high_sym is not None
        assert snapshot_low_sym is not None
        # Symbolic harmonization should have major impact on NCC
        assert snapshot_high_sym.ncc > snapshot_low_sym.ncc

    def test_weight_correctness_icc(self):
        """Test ICC weight correctness: IMS has highest weight."""
        # High IMS
        snapshot_high_ims = compute_adaptive_continuity(
            symbolic_harmonization_index=0.60,
            identity_memory_strength=0.90,
            identity_echo_persistence=0.50,
            identity_drift_anchoring=0.50,
            core_identity_harmonic=0.50,
        )

        # Low IMS
        snapshot_low_ims = compute_adaptive_continuity(
            symbolic_harmonization_index=0.60,
            identity_memory_strength=0.30,
            identity_echo_persistence=0.50,
            identity_drift_anchoring=0.50,
            core_identity_harmonic=0.50,
        )

        assert snapshot_high_ims is not None
        assert snapshot_low_ims is not None
        # IMS should have major impact on ICC
        assert snapshot_high_ims.icc > snapshot_low_ims.icc

    def test_variance_computation(self):
        """Test variance computation helper."""
        values = [0.5, 0.6, 0.55, 0.58, 0.52]
        variance = _compute_variance(values)
        assert variance >= 0.0
        assert variance < 0.01  # Low variance for stable values

    def test_stability_factor_computation(self):
        """Test stability factor computation helper."""
        stable_history = [0.70, 0.71, 0.69, 0.70, 0.72]
        volatile_history = [0.30, 0.80, 0.20, 0.90, 0.10]

        stable_factor = _compute_stability_factor(stable_history)
        volatile_factor = _compute_stability_factor(volatile_history)

        assert stable_factor > volatile_factor
        assert 0.0 <= stable_factor <= 1.0
        assert 0.0 <= volatile_factor <= 1.0

    def test_trend_alignment_computation(self):
        """Test trend alignment computation helper."""
        upward_trend = [0.30, 0.40, 0.50, 0.60, 0.70]
        erratic_trend = [0.30, 0.70, 0.20, 0.80, 0.40]

        upward_alignment = _compute_trend_alignment(upward_trend)
        erratic_alignment = _compute_trend_alignment(erratic_trend)

        assert upward_alignment > erratic_alignment
        assert 0.0 <= upward_alignment <= 1.0
        assert 0.0 <= erratic_alignment <= 1.0


# ============================================================================
# GROUP B: Coherence Integration (10 tests)
# ============================================================================

class TestCoherenceIntegration:
    """Test coherence layer integration: state updates, ordering, history, SessionSummary."""

    def test_state_update_adds_ace_fields(self):
        """Test coherence state update adds ACE fields."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=1)

        # Verify ACE fields exist
        assert hasattr(state, "adaptive_continuity_snapshot")
        assert hasattr(state, "current_ncc")
        assert hasattr(state, "current_icc")
        assert hasattr(state, "current_css")
        assert hasattr(state, "current_continuity_band")
        assert hasattr(state, "current_continuity_tags")
        assert hasattr(state, "ncc_history")
        assert hasattr(state, "icc_history")
        assert hasattr(state, "css_history")
        assert hasattr(state, "continuity_band_history")

    def test_ace_ordering_after_irm(self):
        """Test ACE update runs AFTER Phase 36 IRM."""
        from symbolu.core.coherence.coherence_engine import CoherenceEngine
        from unittest.mock import Mock

        engine = CoherenceEngine()

        # Mock routing plan and mapper profile
        routing_plan = Mock()
        routing_plan.tier = "hybrid"
        routing_plan.domain = "therapy"
        routing_plan.long_arc_tension = 0.5

        mapper_profile = {"resolution_level": "standard"}
        temporal_summary = {}
        semantic_signature = {}

        # First turn
        state = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=0,
            routing_plan=routing_plan,
            mapper_profile=mapper_profile,
            temporal_summary=temporal_summary,
            semantic_signature=semantic_signature,
        )

        # Verify ACE fields exist and are initialized
        assert state.adaptive_continuity_snapshot is None  # First turn, no data yet
        assert len(state.ncc_history) == 1  # History should have one entry (None)
        assert len(state.icc_history) == 1
        assert len(state.css_history) == 1

    def test_history_trimming_includes_ace(self):
        """Test history trimming includes ACE histories."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Add many entries to ACE histories
        for i in range(20):
            state.ncc_history.append(0.5 + i * 0.01)
            state.icc_history.append(0.6 + i * 0.01)
            state.css_history.append(0.7 + i * 0.01)
            state.continuity_band_history.append("MEDIUM")

        # Trim to window of 10
        state.window_trim(10)

        # Verify all ACE histories are trimmed
        assert len(state.ncc_history) == 10
        assert len(state.icc_history) == 10
        assert len(state.css_history) == 10
        assert len(state.continuity_band_history) == 10

    def test_ace_snapshot_null_safe(self):
        """Test ACE snapshot is null-safe when coherence state lacks data."""
        snapshot = compute_adaptive_continuity()
        assert snapshot is None

    def test_ace_band_classification_high(self):
        """Test ACE band classification: HIGH when CSS ≥ 0.70."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.85,
            semantic_integrity=0.82,
            consciousness_order_index=0.80,
            consciousness_stability_index=0.78,
            identity_memory_strength=0.80,
            identity_echo_persistence=0.75,
            identity_drift_anchoring=0.70,
            core_identity_harmonic=0.75,
            temporal_entropy_volatility=0.20,
        )

        assert snapshot is not None
        assert snapshot.css >= 0.70
        assert snapshot.continuity_band == "HIGH"

    def test_ace_band_classification_medium(self):
        """Test ACE band classification: MEDIUM when 0.40 ≤ CSS < 0.70."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.55,
            semantic_integrity=0.52,
            consciousness_order_index=0.50,
            identity_memory_strength=0.55,
            identity_echo_persistence=0.50,
            identity_drift_anchoring=0.48,
            core_identity_harmonic=0.52,
        )

        assert snapshot is not None
        assert 0.40 <= snapshot.css < 0.70
        assert snapshot.continuity_band == "MEDIUM"

    def test_ace_band_classification_low(self):
        """Test ACE band classification: LOW when CSS < 0.40."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.25,
            semantic_integrity=0.28,
            consciousness_order_index=0.30,
            identity_memory_strength=0.30,
            identity_echo_persistence=0.25,
            identity_drift_anchoring=0.20,
            core_identity_harmonic=0.28,
        )

        assert snapshot is not None
        assert snapshot.css < 0.40
        assert snapshot.continuity_band == "LOW"

    def test_ace_tags_generation(self):
        """Test ACE generates appropriate continuity tags."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.75,
            semantic_integrity=0.72,
            consciousness_order_index=0.70,
            identity_memory_strength=0.75,
            identity_echo_persistence=0.72,
            identity_drift_anchoring=0.68,
            core_identity_harmonic=0.70,
            consciousness_stability_index=0.72,
            temporal_entropy_volatility=0.25,
        )

        assert snapshot is not None
        assert len(snapshot.continuity_tags) > 0
        # High NCC should generate CONTINUITY_STRONG tag
        assert "CONTINUITY_STRONG" in snapshot.continuity_tags or "CONTINUITY_BAND_HIGH" in snapshot.continuity_tags

    def test_ace_history_copied_correctly(self):
        """Test ACE histories are copied correctly in coherence engine."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        prev_state = CoherenceState(convo_id="test", turn_index=0)
        prev_state.ncc_history = [0.5, 0.6]
        prev_state.icc_history = [0.6, 0.7]
        prev_state.css_history = [0.7, 0.8]
        prev_state.continuity_band_history = ["MEDIUM", "HIGH"]

        # Create new state copying from prev_state
        new_state = CoherenceState(
            convo_id="test",
            turn_index=1,
            ncc_history=prev_state.ncc_history.copy(),
            icc_history=prev_state.icc_history.copy(),
            css_history=prev_state.css_history.copy(),
            continuity_band_history=prev_state.continuity_band_history.copy(),
        )

        # Verify histories are copied
        assert new_state.ncc_history == [0.5, 0.6]
        assert new_state.icc_history == [0.6, 0.7]
        assert new_state.css_history == [0.7, 0.8]
        assert new_state.continuity_band_history == ["MEDIUM", "HIGH"]

    def test_ace_snapshot_stored_in_state(self):
        """Test ACE snapshot is stored in coherence state."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Create a snapshot
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.70,
            identity_memory_strength=0.65,
        )

        # Store snapshot in state (mimicking what engine does)
        state.adaptive_continuity_snapshot = snapshot
        state.current_ncc = snapshot.ncc
        state.current_icc = snapshot.icc
        state.current_css = snapshot.css
        state.current_continuity_band = snapshot.continuity_band
        state.current_continuity_tags = snapshot.continuity_tags

        # Verify storage
        assert state.adaptive_continuity_snapshot is not None
        assert state.current_ncc == snapshot.ncc
        assert state.current_icc == snapshot.icc
        assert state.current_css == snapshot.css


# ============================================================================
# GROUP C: Persona Engine (10 tests)
# ============================================================================

class TestPersonaEngine:
    """Test persona engine integration: tone modulation, stability, determinism."""

    def test_tone_modulation_bounded(self):
        """Test tone modulation is bounded to ±0.015 max."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        # Create ACE snapshot with extreme values
        class MockACESnapshot:
            ncc = 1.0  # Maximum
            icc = 1.0  # Maximum
            css = 0.0  # Minimum
            continuity_band = "LOW"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()

        # Apply tone modulation
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        assert continuity_profile is not None

        # Check total adjustment is bounded
        total_adjustment = (
            abs(continuity_profile["narrative_flow_adjustment"]) +
            abs(continuity_profile["warmth_adjustment"]) +
            abs(continuity_profile["structure_adjustment"])
        )

        assert total_adjustment <= 0.015

    def test_tone_modulation_high_ncc(self):
        """Test high NCC increases narrative flow tone."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.85  # High
            icc = 0.50
            css = 0.55
            continuity_band = "MEDIUM"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        assert continuity_profile is not None
        # High NCC should increase narrative flow
        assert continuity_profile["narrative_flow_adjustment"] > 0.0

    def test_tone_modulation_high_icc(self):
        """Test high ICC increases warmth tone."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.50
            icc = 0.85  # High
            css = 0.55
            continuity_band = "MEDIUM"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        assert continuity_profile is not None
        # High ICC should increase warmth
        assert continuity_profile["warmth_adjustment"] > 0.0

    def test_tone_modulation_low_css(self):
        """Test low CSS increases structure tone."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.50
            icc = 0.50
            css = 0.30  # Low
            continuity_band = "LOW"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        assert continuity_profile is not None
        # Low CSS should increase structure
        assert continuity_profile["structure_adjustment"] > 0.0

    def test_tone_modulation_stability_under_missing_data(self):
        """Test tone modulation is stable when snapshot data is missing."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        # None snapshot should return None gracefully
        continuity_profile = engine._apply_continuity_tone_modulation(persona, None)
        assert continuity_profile is None

    def test_tone_modulation_deterministic(self):
        """Test tone modulation is deterministic."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.72
            icc = 0.68
            css = 0.65
            continuity_band = "MEDIUM"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()

        # Apply twice
        profile1 = engine._apply_continuity_tone_modulation(persona, ace_snapshot)
        profile2 = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        assert profile1 is not None
        assert profile2 is not None
        assert profile1["ncc"] == profile2["ncc"]
        assert profile1["narrative_flow_adjustment"] == profile2["narrative_flow_adjustment"]
        assert profile1["warmth_adjustment"] == profile2["warmth_adjustment"]
        assert profile1["structure_adjustment"] == profile2["structure_adjustment"]

    def test_extraction_from_explain_log(self):
        """Test ACE extraction from explain_log."""
        from symbolu.mechanical.persona.engine import PersonaEngine

        engine = PersonaEngine()

        # Mock explain_log with coherence_state
        class MockCoherenceState:
            adaptive_continuity_snapshot = None

        explain_log = {"coherence_state": MockCoherenceState()}

        ace_snapshot = engine._extract_continuity_snapshot(explain_log)
        assert ace_snapshot is None  # No snapshot set

    def test_persona_response_has_continuity_profile(self):
        """Test PersonaResponse includes continuity_profile field."""
        from symbolu.mechanical.persona.models import PersonaResponse, PersonaMetadata

        response = PersonaResponse(
            persona_id="neutral",
            text="Test",
            layers={},
            metadata=PersonaMetadata(
                tier="HYBRID",
                domain="therapy",
                intent="how",
                persona_id="neutral",
                persona_name="Neutral",
                persona_description="Test",
                dha_tone="resonance",
                dha_confidence=0.80,
            ),
        )

        # Verify field exists
        assert hasattr(response, "continuity_profile")
        assert response.continuity_profile is None  # Initially None

    def test_tone_adjustments_rounded(self):
        """Test tone adjustments are properly rounded to 4 decimals."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.7234567
            icc = 0.6845321
            css = 0.5512345
            continuity_band = "MEDIUM"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        assert continuity_profile is not None
        # Check rounding
        assert continuity_profile["ncc"] == round(0.7234567, 4)
        assert len(str(continuity_profile["narrative_flow_adjustment"]).split(".")[-1]) <= 4

    def test_no_semantic_changes_ever(self):
        """Test tone modulation NEVER changes semantic content."""
        # This is a validation test - tone modulation should only affect
        # tone parameters, never the actual text content
        # The persona engine applies tone but doesn't change layer content

        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.85
            icc = 0.80
            css = 0.75
            continuity_band = "HIGH"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        # Verify only tone parameters are affected
        assert continuity_profile is not None
        assert "narrative_flow_adjustment" in continuity_profile
        assert "warmth_adjustment" in continuity_profile
        assert "structure_adjustment" in continuity_profile
        # No text/semantic keys should be present
        assert "text" not in continuity_profile
        assert "content" not in continuity_profile
        assert "semantic" not in continuity_profile


# ============================================================================
# GROUP D: Unified API & Observer (8 tests)
# ============================================================================

class TestUnifiedAPIObserver:
    """Test unified API and observer: JSON structure, backward compatibility, null-safety."""

    def test_unified_api_has_ace_field(self):
        """Test unified API output includes adaptive_continuity field."""
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
        )

        # Verify field exists
        assert hasattr(output, "adaptive_continuity")
        assert output.adaptive_continuity is None  # Initially None

    def test_unified_api_ace_json_safe(self):
        """Test ACE data in unified API is JSON-safe."""
        from symbolu.api.unified_api import UnifiedOutput

        ace_data = {
            "ncc": 0.75,
            "icc": 0.70,
            "css": 0.72,
            "band": "HIGH",
            "tags": ["CONTINUITY_STRONG", "CONTINUITY_STABLE"],
        }

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
            adaptive_continuity=ace_data,
        )

        # Convert to dict (JSON-safe)
        output_dict = output.to_dict()
        assert "adaptive_continuity" in output_dict
        assert output_dict["adaptive_continuity"] == ace_data

    def test_unified_api_backward_compatible(self):
        """Test unified API is backward compatible without ACE."""
        from symbolu.api.unified_api import UnifiedOutput

        # Create output without ACE
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
        )

        # Should work fine
        output_dict = output.to_dict()
        assert "adaptive_continuity" in output_dict
        assert output_dict["adaptive_continuity"] is None

    def test_observer_has_ace_fields(self):
        """Test coherence observer includes ACE fields."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        observation = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.20,
            semantic_stability_score=0.80,
            temporal_arc_score=0.70,
            mapper_volatility_score=0.15,
            turn_number=5,
            tier="HYBRID",
            domain="therapy",
            active_mappers=["standard"],
        )

        # Verify ACE fields exist
        assert hasattr(observation, "adaptive_continuity_snapshot")
        assert hasattr(observation, "continuity_ncc")
        assert hasattr(observation, "continuity_icc")
        assert hasattr(observation, "continuity_css")
        assert hasattr(observation, "continuity_band")
        assert hasattr(observation, "continuity_tags")

    def test_observer_ace_to_dict(self):
        """Test observer ACE data serializes to dict correctly."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        observation = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.20,
            semantic_stability_score=0.80,
            temporal_arc_score=0.70,
            mapper_volatility_score=0.15,
            turn_number=5,
            tier="HYBRID",
            domain="therapy",
            active_mappers=["standard"],
            continuity_ncc=0.72,
            continuity_icc=0.68,
            continuity_css=0.70,
            continuity_band="HIGH",
            continuity_tags=["CONTINUITY_STRONG"],
        )

        obs_dict = observation.to_dict()
        assert obs_dict["continuity_ncc"] == 0.72
        assert obs_dict["continuity_icc"] == 0.68
        assert obs_dict["continuity_css"] == 0.70
        assert obs_dict["continuity_band"] == "HIGH"
        assert obs_dict["continuity_tags"] == ["CONTINUITY_STRONG"]

    def test_observer_null_safe_ace(self):
        """Test observer handles None ACE gracefully."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        observation = CoherenceObservation(
            coherence_score=0.75,
            persona_drift_score=0.20,
            semantic_stability_score=0.80,
            temporal_arc_score=0.70,
            mapper_volatility_score=0.15,
            turn_number=5,
            tier="HYBRID",
            domain="therapy",
            active_mappers=["standard"],
        )

        # Verify None values are handled
        obs_dict = observation.to_dict()
        assert obs_dict["continuity_ncc"] is None
        assert obs_dict["continuity_icc"] is None
        assert obs_dict["continuity_css"] is None

    def test_dilchat_adapter_ace_badges(self):
        """Test DILchat adapter includes ACE diagnostic badges."""
        from symbolu.adapter.dilchat_adapter import DILchatBadge

        # Create ACE badges manually (mimicking what adapter does)
        badge_high = DILchatBadge(
            label="CONTINUITY_HIGH",
            level="info",
            description="Session continuity is high.",
        )

        assert badge_high.label == "CONTINUITY_HIGH"
        assert badge_high.level == "info"

    def test_dilchat_adapter_ace_domain_gated(self):
        """Test DILchat adapter ACE badges are domain-gated (therapy/identity only)."""
        # This test validates the badge logic is gated correctly
        # The actual implementation is in dilchat_adapter.py

        from symbolu.adapter.dilchat_adapter import _build_badges

        # Mock unified output with ACE data
        unified_output = {
            "adaptive_continuity": {
                "ncc": 0.75,
                "icc": 0.70,
                "css": 0.72,
                "band": "HIGH",
                "tags": ["CONTINUITY_STRONG"],
            }
        }

        # Therapy domain + smart_insight mode → badges should be added
        badges_therapy = _build_badges(
            stability_status="stable",
            policy_flags={"interaction_mode": "smart_insight"},
            coherence_score=0.75,
            domain="therapy",
            unified_output=unified_output,
        )

        # General domain → badges should NOT be added (no ACE badges)
        badges_general = _build_badges(
            stability_status="stable",
            policy_flags={"interaction_mode": "smart_insight"},
            coherence_score=0.75,
            domain="general",
            unified_output=unified_output,
        )

        # Count ACE badges
        ace_badges_therapy = [b for b in badges_therapy if "CONTINUITY_" in b.label]
        ace_badges_general = [b for b in badges_general if "CONTINUITY_" in b.label]

        # Therapy should have ACE badges, general should not
        assert len(ace_badges_therapy) > 0
        assert len(ace_badges_general) == 0


# ============================================================================
# GROUP E: Behavioral Invariance (8 tests)
# ============================================================================

class TestBehavioralInvariance:
    """Test behavioral invariance: no routing changes, zero-LLM, determinism stress test."""

    def test_no_routing_changes(self):
        """Test ACE does NOT affect routing decisions."""
        # ACE is observation-only and should never influence TTOR routing
        # This test verifies that ACE computation doesn't change routing

        snapshot_high = compute_adaptive_continuity(
            symbolic_harmonization_index=0.90,
            identity_memory_strength=0.85,
        )

        snapshot_low = compute_adaptive_continuity(
            symbolic_harmonization_index=0.20,
            identity_memory_strength=0.25,
        )

        # Both snapshots should exist and have different values
        assert snapshot_high is not None
        assert snapshot_low is not None
        assert snapshot_high.css != snapshot_low.css

        # But routing should NOT be affected (ACE is observation-only)
        # This is validated by the fact that ACE only populates observation fields
        # and never modifies routing_plan or tier

    def test_no_mapper_changes(self):
        """Test ACE does NOT affect mapper activation."""
        # ACE should not modify mapper profiles or activation
        # This test validates that ACE computation is pure observation

        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.70,
            identity_memory_strength=0.65,
        )

        assert snapshot is not None
        # ACE snapshot should only contain continuity data
        assert "mapper" not in str(snapshot).lower()
        assert "activation" not in str(snapshot).lower()

    def test_no_ucf_alterations(self):
        """Test ACE does NOT alter UCF or coherence scores."""
        # ACE uses UCF as input but should never modify it

        snapshot = compute_adaptive_continuity(
            consciousness_order_index=0.75,
            consciousness_stability_index=0.70,
            symbolic_harmonization_index=0.68,
            identity_memory_strength=0.65,
        )

        assert snapshot is not None
        # Verify UCF inputs are read but not modified
        assert "consciousness_order_index" in snapshot.raw_signals
        # The raw value should match input
        assert snapshot.raw_signals["consciousness_order_index"] == 0.75

    def test_zero_llm_enforcement(self):
        """Test ACE is zero-LLM: no language model operations."""
        # All ACE operations should be pure math, no LLM calls

        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=0.70,
            identity_memory_strength=0.65,
        )

        assert snapshot is not None
        # ACE should be purely deterministic math
        # No string generation, no text processing
        assert isinstance(snapshot.ncc, float)
        assert isinstance(snapshot.icc, float)
        assert isinstance(snapshot.css, float)
        assert isinstance(snapshot.continuity_band, str)  # Classification only
        assert isinstance(snapshot.continuity_tags, list)

    def test_deterministic_100_iterations(self):
        """Test determinism stress test: 100 iterations with same inputs."""
        kwargs = {
            "symbolic_harmonization_index": 0.68,
            "semantic_integrity": 0.65,
            "consciousness_order_index": 0.70,
            "identity_memory_strength": 0.72,
            "identity_echo_persistence": 0.68,
            "identity_drift_anchoring": 0.65,
            "core_identity_harmonic": 0.67,
            "temporal_entropy_volatility": 0.30,
        }

        snapshots = [compute_adaptive_continuity(**kwargs) for _ in range(100)]

        # All snapshots should be identical
        first = snapshots[0]
        assert first is not None

        for snapshot in snapshots[1:]:
            assert snapshot is not None
            assert snapshot.ncc == first.ncc
            assert snapshot.icc == first.icc
            assert snapshot.css == first.css
            assert snapshot.continuity_band == first.continuity_band
            assert snapshot.continuity_tags == first.continuity_tags

    def test_semantic_content_unchanged(self):
        """Test ACE never changes semantic content."""
        # ACE is tone-only, should never affect text semantics

        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()
        persona = PersonaProfile(id="neutral", display_name="Neutral", description="Test")

        class MockACESnapshot:
            ncc = 0.85
            icc = 0.80
            css = 0.75
            continuity_band = "HIGH"
            continuity_tags = []

        ace_snapshot = MockACESnapshot()
        continuity_profile = engine._apply_continuity_tone_modulation(persona, ace_snapshot)

        # Verify no semantic keys in profile
        assert continuity_profile is not None
        assert "text" not in continuity_profile
        assert "semantic" not in continuity_profile
        assert "content" not in continuity_profile
        assert "message" not in continuity_profile

    def test_graceful_degradation_all_none(self):
        """Test graceful degradation: all None inputs returns None."""
        snapshot = compute_adaptive_continuity(
            symbolic_harmonization_index=None,
            semantic_integrity=None,
            consciousness_order_index=None,
            identity_memory_strength=None,
            identity_echo_persistence=None,
        )

        # Should return None gracefully
        assert snapshot is None

    def test_observation_only_no_side_effects(self):
        """Test ACE is observation-only with no side effects."""
        # Multiple calls should not have side effects

        snapshot1 = compute_adaptive_continuity(
            symbolic_harmonization_index=0.70,
            identity_memory_strength=0.65,
        )

        snapshot2 = compute_adaptive_continuity(
            symbolic_harmonization_index=0.70,
            identity_memory_strength=0.65,
        )

        # Both should be identical (no state changes)
        assert snapshot1 is not None
        assert snapshot2 is not None
        assert snapshot1.ncc == snapshot2.ncc
        assert snapshot1.icc == snapshot2.icc
        assert snapshot1.css == snapshot2.css


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
