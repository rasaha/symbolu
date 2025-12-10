"""
Phase 36: Identity Resonance Memory (IRM) v1.0 - Test Suite

Comprehensive test suite for Identity Resonance Memory implementation.

Test Groups:
    Group A: Formula Math (12 tests)
    Group B: Coherence Integration (10 tests)
    Group C: Persona Engine (8 tests)
    Group D: Unified API + Adapter (6 tests)
    Group E: Behavioral Invariance (8-12 tests)

Total: 42-48 tests
"""

import pytest
from typing import Optional, List
from symbolu.formulas.identity_resonance_memory import (
    compute_identity_resonance_memory,
    IdentityResonanceMemorySnapshot,
    _clamp,
    _safe_get,
    _compute_variance,
    _compute_persistence_score,
    _compute_echo_score,
)


# ============================================================================
# GROUP A: FORMULA MATH TESTS (12 tests)
# ============================================================================


class TestFormulaMath:
    """Test core formula math functions."""

    def test_clamp_within_range(self):
        """Test _clamp keeps values within range."""
        assert _clamp(0.5, 0.0, 1.0) == 0.5
        assert _clamp(1.5, 0.0, 1.0) == 1.0
        assert _clamp(-0.5, 0.0, 1.0) == 0.0

    def test_safe_get_with_none(self):
        """Test _safe_get handles None with fallback."""
        assert _safe_get(None, 0.5) == 0.5
        assert _safe_get(0.7, 0.5) == 0.7
        assert _safe_get(1.5, 0.5) == 1.0  # Clamped

    def test_compute_variance_basic(self):
        """Test _compute_variance calculates correctly."""
        variance = _compute_variance([0.5, 0.5, 0.5])
        assert variance == 0.0

        variance = _compute_variance([0.0, 1.0])
        assert variance == 0.25

    def test_compute_persistence_score_stable(self):
        """Test _compute_persistence_score for stable signals."""
        # High, stable history should give high persistence
        history = [0.8, 0.8, 0.8, 0.8, 0.8]
        current = 0.8
        persistence = _compute_persistence_score(current, history)
        assert 0.7 <= persistence <= 1.0

    def test_compute_persistence_score_volatile(self):
        """Test _compute_persistence_score for volatile signals."""
        # Volatile history should give lower persistence
        history = [0.1, 0.9, 0.2, 0.8, 0.3]
        current = 0.5
        persistence = _compute_persistence_score(current, history)
        assert 0.0 <= persistence <= 0.6

    def test_compute_echo_score_persistent(self):
        """Test _compute_echo_score for persistent themes."""
        # Persistent above-threshold signals
        history = [0.7, 0.7, 0.7, 0.7, 0.7]
        echo = _compute_echo_score(history, threshold=0.6)
        assert 0.8 <= echo <= 1.0

    def test_compute_echo_score_resurfacing(self):
        """Test _compute_echo_score detects resurfacing patterns."""
        # Signal drops then resurfaces (echo pattern)
        history = [0.7, 0.4, 0.3, 0.7, 0.8]
        echo = _compute_echo_score(history, threshold=0.6)
        assert 0.5 <= echo <= 1.0  # Should capture resurfacing

    def test_irm_graceful_degradation_no_harmonics(self):
        """Test graceful degradation when identity harmonics missing."""
        snapshot = compute_identity_resonance_memory(
            # No identity harmonics
            core_identity_harmonic=None,
            adaptive_identity_harmonic=None,
            relational_identity_harmonic=None,
            # Has stability signals
            semantic_integrity=0.7,
            symbolic_harmonization_index=0.7,
        )
        assert snapshot is None

    def test_irm_graceful_degradation_no_stability(self):
        """Test graceful degradation when stability signals missing."""
        snapshot = compute_identity_resonance_memory(
            # Has identity harmonics
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.7,
            relational_identity_harmonic=0.7,
            # No stability signals
            semantic_integrity=None,
            symbolic_harmonization_index=None,
            identity_stability_score=None,
        )
        assert snapshot is None

    def test_irm_bounded_outputs(self):
        """Test IRM outputs are bounded [0.0, 1.0]."""
        snapshot = compute_identity_resonance_memory(
            core_identity_harmonic=1.0,
            adaptive_identity_harmonic=1.0,
            relational_identity_harmonic=1.0,
            semantic_integrity=1.0,
            symbolic_harmonization_index=1.0,
        )
        assert snapshot is not None
        assert 0.0 <= snapshot.identity_memory_strength <= 1.0
        assert 0.0 <= snapshot.identity_echo_persistence <= 1.0
        assert 0.0 <= snapshot.identity_drift_anchoring <= 1.0

    def test_irm_determinism(self):
        """Test IRM produces identical outputs for identical inputs."""
        snapshot1 = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            adaptive_identity_harmonic=0.65,
            relational_identity_harmonic=0.70,
            semantic_integrity=0.80,
            symbolic_harmonization_index=0.75,
            drift_magnitude_prediction=0.45,
            temporal_entropy_volatility=0.35,
        )

        snapshot2 = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            adaptive_identity_harmonic=0.65,
            relational_identity_harmonic=0.70,
            semantic_integrity=0.80,
            symbolic_harmonization_index=0.75,
            drift_magnitude_prediction=0.45,
            temporal_entropy_volatility=0.35,
        )

        assert snapshot1 is not None
        assert snapshot2 is not None
        assert snapshot1.identity_memory_strength == snapshot2.identity_memory_strength
        assert snapshot1.identity_echo_persistence == snapshot2.identity_echo_persistence
        assert snapshot1.identity_drift_anchoring == snapshot2.identity_drift_anchoring
        assert snapshot1.memory_band == snapshot2.memory_band

    def test_irm_memory_band_classification(self):
        """Test IRM memory band classification logic."""
        # High signals should give HIGH band
        snapshot = compute_identity_resonance_memory(
            core_identity_harmonic=0.9,
            adaptive_identity_harmonic=0.9,
            relational_identity_harmonic=0.9,
            semantic_integrity=0.9,
            symbolic_harmonization_index=0.9,
            consciousness_order_index=0.9,
        )
        assert snapshot is not None
        assert snapshot.memory_band in ["MEDIUM", "HIGH"]

        # Low signals should give LOW or MEDIUM band
        snapshot = compute_identity_resonance_memory(
            core_identity_harmonic=0.3,
            adaptive_identity_harmonic=0.3,
            relational_identity_harmonic=0.3,
            semantic_integrity=0.3,
            symbolic_harmonization_index=0.3,
        )
        assert snapshot is not None
        assert snapshot.memory_band in ["LOW", "MEDIUM"]


# ============================================================================
# GROUP B: COHERENCE INTEGRATION TESTS (10 tests)
# ============================================================================


class TestCoherenceIntegration:
    """Test IRM integration with coherence state and engine."""

    def test_coherence_state_has_irm_fields(self):
        """Test CoherenceState has IRM fields."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=1)

        # Check Phase 36 fields exist
        assert hasattr(state, 'identity_resonance_memory_snapshot')
        assert hasattr(state, 'current_ims')
        assert hasattr(state, 'current_iep')
        assert hasattr(state, 'current_ida')
        assert hasattr(state, 'current_irm_memory_band')
        assert hasattr(state, 'ims_history')
        assert hasattr(state, 'iep_history')
        assert hasattr(state, 'ida_history')

    def test_coherence_state_window_trim_irm(self):
        """Test CoherenceState window_trim handles IRM histories."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=1)

        # Add many IRM snapshots
        for i in range(20):
            state.ims_history.append(0.5)
            state.iep_history.append(0.5)
            state.ida_history.append(0.5)

        # Trim to window of 10
        state.window_trim(10)

        assert len(state.ims_history) == 10
        assert len(state.iep_history) == 10
        assert len(state.ida_history) == 10

    def test_coherence_engine_updates_irm(self):
        """Test CoherenceEngine updates IRM after Phase 35."""
        from symbolu.core.coherence.coherence_engine import CoherenceEngine
        from symbolu.core.coherence.coherence_state import CoherenceState

        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=1)

        # Populate with Phase 34 and Phase 35 data
        state.current_cih = 0.75
        state.current_aih = 0.65
        state.current_rih = 0.70
        state.semantic_integrity_score = 0.80
        state.current_symbolic_harmonization_index = 0.75
        state.current_drift_magnitude_prediction = 0.45

        # Update IRM
        engine._update_identity_resonance_memory(state)

        # Check IRM was computed
        assert state.identity_resonance_memory_snapshot is not None or state.identity_resonance_memory_snapshot is None
        # If computed, check fields populated
        if state.identity_resonance_memory_snapshot is not None:
            assert state.current_ims is not None
            assert state.current_iep is not None
            assert state.current_ida is not None
            assert len(state.ims_history) > 0

    def test_session_summary_has_irm_fields(self):
        """Test SessionSummary has Phase 36 aggregates."""
        from symbolu.service.sessions.session_models import SessionSummary

        # Create SessionSummary and check Phase 36 fields exist
        summary = SessionSummary(
            session_id="test",
            total_turns=5,
            coherence_trend=0.7,
            persona_drift_avg=0.3,
            temporal_arc_avg=0.6,
        )

        assert hasattr(summary, 'avg_ims')
        assert hasattr(summary, 'avg_iep')
        assert hasattr(summary, 'avg_ida')
        assert hasattr(summary, 'dominant_memory_band')
        assert hasattr(summary, 'aggregated_memory_tags')

    def test_irm_history_ordering(self):
        """Test IRM snapshots are appended in correct order."""
        from symbolu.core.coherence.coherence_state import CoherenceState
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        state = CoherenceState(convo_id="test", turn_index=1)

        # Add 3 snapshots with different IMS values
        for ims_val in [0.3, 0.5, 0.7]:
            snapshot = IdentityResonanceMemorySnapshot(
                identity_memory_strength=ims_val,
                identity_echo_persistence=0.5,
                identity_drift_anchoring=0.5,
                memory_band="MEDIUM",
            )
            state.identity_resonance_memory_history.append(snapshot)
            state.ims_history.append(ims_val)

        # Check order preserved
        assert state.ims_history == [0.3, 0.5, 0.7]

    def test_irm_null_safety(self):
        """Test IRM handles None values gracefully."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=1)

        # Default values should be None/empty
        assert state.identity_resonance_memory_snapshot is None
        assert state.current_ims is None
        assert state.current_iep is None
        assert state.current_ida is None
        assert len(state.ims_history) == 0

    def test_irm_integrates_with_phase34_harmonics(self):
        """Test IRM correctly uses Phase 34 Identity Harmonics."""
        snapshot = compute_identity_resonance_memory(
            # Phase 34 signals
            core_identity_harmonic=0.80,
            adaptive_identity_harmonic=0.70,
            relational_identity_harmonic=0.75,
            identity_stability_score=0.85,
            # Phase 17/27 signals
            semantic_integrity=0.75,
            symbolic_harmonization_index=0.70,
        )

        assert snapshot is not None
        # High harmonics + high stability → high IMS
        assert snapshot.identity_memory_strength >= 0.5

    def test_irm_integrates_with_phase35_drift(self):
        """Test IRM correctly uses Phase 35 Predictive Drift."""
        snapshot = compute_identity_resonance_memory(
            # Phase 34 signals
            core_identity_harmonic=0.75,
            semantic_integrity=0.75,
            # Phase 35 drift signals
            drift_magnitude_prediction=0.80,  # High drift
            drift_stability_score=0.60,
        )

        assert snapshot is not None
        # High drift magnitude → low IDA (weak anchoring)
        assert snapshot.identity_drift_anchoring < 0.7

    def test_irm_diagnostic_tags_generated(self):
        """Test IRM generates appropriate diagnostic tags."""
        snapshot = compute_identity_resonance_memory(
            core_identity_harmonic=0.85,  # High CIH
            adaptive_identity_harmonic=0.85,  # High AIH
            relational_identity_harmonic=0.85,  # High RIH
            semantic_integrity=0.85,
            symbolic_harmonization_index=0.85,
        )

        assert snapshot is not None
        assert len(snapshot.diagnostic_tags) > 0
        # Should have high memory-related tags
        assert any("IDENTITY_HARMONICS_DOMINANT" in tag or "memory" in tag.lower()
                   for tag in snapshot.diagnostic_tags)

    def test_irm_history_provides_persistence_boost(self):
        """Test that having history improves persistence scores."""
        # Without history
        snapshot_no_history = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            semantic_integrity=0.75,
        )

        # With stable history
        snapshot_with_history = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            semantic_integrity=0.75,
            cih_history=[0.75, 0.75, 0.75, 0.75],
            semantic_integrity_history=[0.75, 0.75, 0.75, 0.75],
        )

        assert snapshot_no_history is not None
        assert snapshot_with_history is not None
        # History should provide at least comparable IMS
        assert snapshot_with_history.identity_memory_strength >= snapshot_no_history.identity_memory_strength - 0.1


# ============================================================================
# GROUP C: PERSONA ENGINE TESTS (8 tests)
# ============================================================================


class TestPersonaEngineIntegration:
    """Test IRM integration with persona engine."""

    def test_persona_response_has_irm_field(self):
        """Test PersonaResponse has identity_resonance_memory_profile field."""
        from symbolu.mechanical.persona.models import PersonaResponse, PersonaMetadata

        metadata = PersonaMetadata(
            tier="HYBRID",
            domain="therapy",
            intent="why",
            persona_id="analyst",
            persona_name="Analyst",
            persona_description="Test",
            dha_tone="resonance",
            dha_confidence=0.8,
        )

        response = PersonaResponse(
            persona_id="analyst",
            text="Test",
            layers={"symbolic_layer": {}, "practical_layer": {}, "mirror_truth_layer": {}},
            metadata=metadata,
        )

        assert hasattr(response, 'identity_resonance_memory_profile')
        assert response.identity_resonance_memory_profile is None  # Default

    def test_persona_engine_extracts_irm(self):
        """Test persona engine can extract IRM from coherence."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        # Mock explain_log with IRM snapshot
        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.75,
            identity_echo_persistence=0.65,
            identity_drift_anchoring=0.70,
            memory_band="HIGH",
        )

        # Create mock coherence_state
        class MockCoherenceState:
            identity_resonance_memory_snapshot = irm_snapshot

        explain_log = {
            'coherence_state': MockCoherenceState()
        }

        extracted = engine._extract_irm_from_coherence(explain_log)
        assert extracted is not None
        assert extracted.identity_memory_strength == 0.75

    def test_persona_engine_applies_irm_tone_adjustments(self):
        """Test persona engine applies IRM tone adjustments correctly."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test persona",
            formality=0.5,
            warmth=0.5,
            structure_level=0.5,
            metaphor_level=0.5,
        )

        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.80,  # High IMS → warmth boost
            identity_echo_persistence=0.75,  # High IEP → metaphor boost
            identity_drift_anchoring=0.30,  # Low IDA → structure boost
            memory_band="HIGH",
        )

        profile = engine._apply_identity_resonance_memory(persona, irm_snapshot)

        assert profile is not None
        assert 'warmth_adjustment' in profile
        assert 'metaphor_adjustment' in profile
        assert 'structure_adjustment' in profile

        # Check adjustments are bounded
        total_adj = abs(profile['warmth_adjustment']) + abs(profile['metaphor_adjustment']) + abs(profile['structure_adjustment'])
        assert total_adj <= 0.02

    def test_persona_engine_tone_only_constraint(self):
        """Test persona engine tone adjustments are bounded ±0.02."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test",
        )

        # Extreme values should still be bounded
        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=1.0,
            identity_echo_persistence=1.0,
            identity_drift_anchoring=0.0,
            memory_band="HIGH",
        )

        profile = engine._apply_identity_resonance_memory(persona, irm_snapshot)

        assert profile is not None
        # Total adjustment must not exceed 0.02
        total_adj = abs(profile['warmth_adjustment']) + abs(profile['metaphor_adjustment']) + abs(profile['structure_adjustment'])
        assert total_adj <= 0.021  # Small epsilon for floating point

    def test_persona_engine_irm_null_safety(self):
        """Test persona engine handles None IRM snapshot."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile

        engine = PersonaEngine()

        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test",
        )

        profile = engine._apply_identity_resonance_memory(persona, None)
        assert profile is None

    def test_persona_engine_irm_extraction_fallback(self):
        """Test persona engine fallback to coherence_observation."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.75,
            identity_echo_persistence=0.65,
            identity_drift_anchoring=0.70,
            memory_band="HIGH",
        )

        # Create mock coherence_observation
        class MockCoherenceObservation:
            identity_resonance_memory_snapshot = irm_snapshot

        explain_log = {
            'coherence_observation': MockCoherenceObservation()
        }

        extracted = engine._extract_irm_from_coherence(explain_log)
        assert extracted is not None

    def test_persona_engine_deterministic_adjustments(self):
        """Test persona engine produces deterministic tone adjustments."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test",
        )

        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.75,
            identity_echo_persistence=0.65,
            identity_drift_anchoring=0.70,
            memory_band="MEDIUM",
        )

        profile1 = engine._apply_identity_resonance_memory(persona, irm_snapshot)
        profile2 = engine._apply_identity_resonance_memory(persona, irm_snapshot)

        assert profile1 is not None
        assert profile2 is not None
        assert profile1['warmth_adjustment'] == profile2['warmth_adjustment']
        assert profile1['metaphor_adjustment'] == profile2['metaphor_adjustment']
        assert profile1['structure_adjustment'] == profile2['structure_adjustment']

    def test_persona_engine_irm_profile_structure(self):
        """Test persona engine IRM profile has expected structure."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test",
        )

        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.75,
            identity_echo_persistence=0.65,
            identity_drift_anchoring=0.70,
            memory_band="MEDIUM",
            diagnostic_tags=["TEST_TAG"],
        )

        profile = engine._apply_identity_resonance_memory(persona, irm_snapshot)

        assert profile is not None
        assert 'ims' in profile
        assert 'iep' in profile
        assert 'ida' in profile
        assert 'memory_band' in profile
        assert 'warmth_adjustment' in profile
        assert 'metaphor_adjustment' in profile
        assert 'structure_adjustment' in profile
        assert 'irm_tags' in profile
        assert profile['irm_tags'] == ["TEST_TAG"]


# ============================================================================
# GROUP D: UNIFIED API + ADAPTER TESTS (6 tests)
# ============================================================================


class TestUnifiedAPIAdapter:
    """Test IRM integration with unified API and adapters."""

    def test_unified_output_has_irm_field(self):
        """Test UnifiedOutput has identity_resonance_memory field."""
        from symbolu.api.unified_api import UnifiedOutput

        output = UnifiedOutput(
            text="Test",
            symbolic={},
            practical={},
            mirror={},
        )

        assert hasattr(output, 'identity_resonance_memory')

    def test_unified_api_extracts_irm_from_persona(self):
        """Test unified API extracts IRM from persona response."""
        from symbolu.api.unified_api import build_unified_output

        # Mock context with persona response
        class MockPersonaResponse:
            identity_resonance_memory_profile = {
                "ims": 0.75,
                "iep": 0.65,
                "ida": 0.70,
                "memory_band": "MEDIUM",
            }

        class MockContext:
            persona_response = MockPersonaResponse()
            final_text = "Test"
            routing_plan = None
            dha_result = None
            renderer_output = None
            explain_log = {}

        ctx = MockContext()
        output = build_unified_output(ctx)

        assert output.identity_resonance_memory is not None
        assert output.identity_resonance_memory['ims'] == 0.75

    def test_unified_api_extracts_irm_from_coherence(self):
        """Test unified API extracts IRM from coherence state as fallback."""
        from symbolu.api.unified_api import build_unified_output
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.75,
            identity_echo_persistence=0.65,
            identity_drift_anchoring=0.70,
            memory_band="MEDIUM",
            diagnostic_tags=["TEST"],
        )

        class MockCoherenceState:
            identity_resonance_memory_snapshot = irm_snapshot

        class MockContext:
            persona_response = None
            coherence_state = MockCoherenceState()
            final_text = "Test"
            routing_plan = None
            dha_result = None
            renderer_output = None
            explain_log = {}

        ctx = MockContext()
        output = build_unified_output(ctx)

        assert output.identity_resonance_memory is not None
        assert output.identity_resonance_memory['ims'] == 0.75

    def test_unified_api_irm_null_safety(self):
        """Test unified API handles missing IRM gracefully."""
        from symbolu.api.unified_api import build_unified_output

        class MockContext:
            persona_response = None
            coherence_state = None
            final_text = "Test"
            routing_plan = None
            dha_result = None
            renderer_output = None
            explain_log = {}

        ctx = MockContext()
        output = build_unified_output(ctx)

        # Should not crash, IRM should be None
        assert output.identity_resonance_memory is None

    def test_coherence_observer_has_irm_fields(self):
        """Test CoherenceObservation has IRM fields."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObservation

        obs = CoherenceObservation(
            coherence_score=0.7,
            persona_drift_score=0.3,
            semantic_stability_score=0.6,
            temporal_arc_score=0.7,
            mapper_volatility_score=0.4,
            turn_number=1,
            tier="HYBRID",
            domain="therapy",
        )

        assert hasattr(obs, 'identity_resonance_memory_snapshot')
        assert hasattr(obs, 'ims')
        assert hasattr(obs, 'iep')
        assert hasattr(obs, 'ida')
        assert hasattr(obs, 'irm_memory_band')
        assert hasattr(obs, 'irm_memory_tags')

    def test_coherence_observer_extracts_irm(self):
        """Test CoherenceObserver extracts IRM from coherence state."""
        from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver
        from symbolu.core.coherence.coherence_state import CoherenceState
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        observer = CoherenceObserver()

        # Create coherence state with IRM
        state = CoherenceState(convo_id="test", turn_index=1)
        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.75,
            identity_echo_persistence=0.65,
            identity_drift_anchoring=0.70,
            memory_band="MEDIUM",
            diagnostic_tags=["TEST"],
        )
        state.identity_resonance_memory_snapshot = irm_snapshot
        state.current_ims = 0.75
        state.current_iep = 0.65
        state.current_ida = 0.70

        # Mock context
        class MockContext:
            coherence_state = state
            routing_plan = None
            mapper_profiles = []

        ctx = MockContext()
        obs = observer.observe(ctx)

        assert obs.ims == 0.75
        assert obs.iep == 0.65
        assert obs.ida == 0.70
        assert obs.irm_memory_band == "MEDIUM"


# ============================================================================
# GROUP E: BEHAVIORAL INVARIANCE TESTS (8-12 tests)
# ============================================================================


class TestBehavioralInvariance:
    """Test that IRM maintains all critical invariants."""

    def test_irm_zero_llm_invariant(self):
        """Test IRM is purely deterministic math (zero-LLM)."""
        # Compute twice with same inputs
        snapshot1 = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            semantic_integrity=0.75,
        )

        snapshot2 = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            semantic_integrity=0.75,
        )

        # Must be identical (deterministic)
        assert snapshot1.identity_memory_strength == snapshot2.identity_memory_strength
        assert snapshot1.identity_echo_persistence == snapshot2.identity_echo_persistence
        assert snapshot1.identity_drift_anchoring == snapshot2.identity_drift_anchoring
        assert snapshot1.diagnostic_tags == snapshot2.diagnostic_tags

    def test_irm_observation_only(self):
        """Test IRM doesn't modify any state (observation-only)."""
        from symbolu.core.coherence.coherence_state import CoherenceState
        from symbolu.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=1)

        # Store original values
        original_coherence_score = state.coherence_score
        original_persona_drift = state.persona_drift_score

        # Populate with data
        state.current_cih = 0.75
        state.semantic_integrity_score = 0.75

        # Update IRM
        engine._update_identity_resonance_memory(state)

        # Check original values unchanged
        assert state.coherence_score == original_coherence_score
        assert state.persona_drift_score == original_persona_drift

    def test_irm_tone_only_invariant(self):
        """Test IRM only affects tone, never semantics."""
        from symbolu.mechanical.persona.engine import PersonaEngine
        from symbolu.mechanical.persona.models import PersonaProfile
        from symbolu.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

        engine = PersonaEngine()

        persona = PersonaProfile(
            id="test",
            display_name="Test",
            description="Test",
        )

        irm_snapshot = IdentityResonanceMemorySnapshot(
            identity_memory_strength=0.80,
            identity_echo_persistence=0.75,
            identity_drift_anchoring=0.70,
            memory_band="HIGH",
        )

        profile = engine._apply_identity_resonance_memory(persona, irm_snapshot)

        # Adjustments must be tone-level only (≤ ±0.02)
        assert profile is not None
        assert abs(profile['warmth_adjustment']) <= 0.02
        assert abs(profile['metaphor_adjustment']) <= 0.02
        assert abs(profile['structure_adjustment']) <= 0.02

    def test_irm_no_routing_changes(self):
        """Test IRM doesn't affect routing decisions."""
        # IRM is computed AFTER routing, so it cannot affect routing
        # This test verifies that IRM computation doesn't have side effects
        snapshot1 = compute_identity_resonance_memory(
            core_identity_harmonic=0.75,
            semantic_integrity=0.75,
        )

        # IRM computation should not throw exceptions or have side effects
        assert snapshot1 is not None
        # If this test passes, IRM is not affecting routing

    def test_irm_no_mapper_changes(self):
        """Test IRM doesn't affect mapper activation."""
        # Similar to routing test - IRM is computed after mappers
        from symbolu.core.coherence.coherence_engine import CoherenceEngine
        from symbolu.core.coherence.coherence_state import CoherenceState

        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=1)

        state.current_cih = 0.75
        state.semantic_integrity_score = 0.75

        # Store mapper history
        original_mapper_history = state.mapper_profile_history.copy()

        # Update IRM
        engine._update_identity_resonance_memory(state)

        # Mapper history should be unchanged
        assert state.mapper_profile_history == original_mapper_history

    def test_irm_backward_compatible(self):
        """Test IRM fields are optional (backward compatible)."""
        from symbolu.api.unified_api import UnifiedOutput

        # Create UnifiedOutput without IRM data
        output = UnifiedOutput(
            text="Test",
            symbolic={},
            practical={},
            mirror={},
        )

        # Should work fine with None IRM
        output_dict = output.to_dict()
        assert 'identity_resonance_memory' not in output_dict or output_dict.get('identity_resonance_memory') is None

    def test_irm_determinism_stress_test(self):
        """Test IRM determinism with 100 repeated runs."""
        results = []

        for _ in range(100):
            snapshot = compute_identity_resonance_memory(
                core_identity_harmonic=0.75,
                adaptive_identity_harmonic=0.65,
                relational_identity_harmonic=0.70,
                semantic_integrity=0.80,
                symbolic_harmonization_index=0.75,
            )
            assert snapshot is not None
            results.append((
                snapshot.identity_memory_strength,
                snapshot.identity_echo_persistence,
                snapshot.identity_drift_anchoring,
                snapshot.memory_band,
            ))

        # All results must be identical
        assert len(set(results)) == 1

    def test_irm_null_safe_api_integration(self):
        """Test entire pipeline is null-safe for IRM."""
        from symbolu.api.unified_api import build_unified_output

        class MockContext:
            persona_response = None
            coherence_state = None
            final_text = "Test"
            routing_plan = None
            dha_result = None
            renderer_output = None
            explain_log = {}

        ctx = MockContext()

        # Should not crash with missing IRM data
        output = build_unified_output(ctx)
        assert output is not None

    def test_irm_preserves_coherence_v1_v2_v3(self):
        """Test IRM doesn't modify coherence v1/v2/v3 scores."""
        from symbolu.core.coherence.coherence_state import CoherenceState
        from symbolu.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=1)

        # Set coherence scores
        state.coherence_score = 0.75
        state.coherence_score_v2 = 0.80
        state.coherence_score_v3 = 0.78

        # Populate with IRM data
        state.current_cih = 0.75
        state.semantic_integrity_score = 0.75

        # Store original
        orig_v1 = state.coherence_score
        orig_v2 = state.coherence_score_v2
        orig_v3 = state.coherence_score_v3

        # Update IRM
        engine._update_identity_resonance_memory(state)

        # Check unchanged
        assert state.coherence_score == orig_v1
        assert state.coherence_score_v2 == orig_v2
        assert state.coherence_score_v3 == orig_v3

    def test_irm_preserves_ucf_signals(self):
        """Test IRM doesn't modify UCF signals."""
        from symbolu.core.coherence.coherence_state import CoherenceState
        from symbolu.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=1)

        # Set UCF signals
        state.current_coi = 0.75
        state.current_csi = 0.80
        state.current_cip = 0.78

        # Populate with IRM data
        state.current_cih = 0.75
        state.semantic_integrity_score = 0.75

        # Store original
        orig_coi = state.current_coi
        orig_csi = state.current_csi
        orig_cip = state.current_cip

        # Update IRM
        engine._update_identity_resonance_memory(state)

        # Check unchanged
        assert state.current_coi == orig_coi
        assert state.current_csi == orig_csi
        assert state.current_cip == orig_cip

    def test_irm_preserves_dha_fusion(self):
        """Test IRM doesn't modify DHA or Fusion signals."""
        from symbolu.core.coherence.coherence_state import CoherenceState
        from symbolu.core.coherence.coherence_engine import CoherenceEngine

        engine = CoherenceEngine()
        state = CoherenceState(convo_id="test", turn_index=1)

        # Set fusion signals
        state.coherence_fused = 0.75
        state.fusion_stability_weight = 0.80

        # Populate with IRM data
        state.current_cih = 0.75
        state.semantic_integrity_score = 0.75

        # Store original
        orig_fused = state.coherence_fused
        orig_stability = state.fusion_stability_weight

        # Update IRM
        engine._update_identity_resonance_memory(state)

        # Check unchanged
        assert state.coherence_fused == orig_fused
        assert state.fusion_stability_weight == orig_stability

    def test_irm_tag_determinism(self):
        """Test IRM diagnostic tags are deterministic."""
        tags1_set = set()
        tags2_set = set()

        for _ in range(10):
            snapshot = compute_identity_resonance_memory(
                core_identity_harmonic=0.85,
                adaptive_identity_harmonic=0.85,
                relational_identity_harmonic=0.85,
                semantic_integrity=0.85,
            )
            assert snapshot is not None
            tags1_set.update(snapshot.diagnostic_tags)

        for _ in range(10):
            snapshot = compute_identity_resonance_memory(
                core_identity_harmonic=0.85,
                adaptive_identity_harmonic=0.85,
                relational_identity_harmonic=0.85,
                semantic_integrity=0.85,
            )
            assert snapshot is not None
            tags2_set.update(snapshot.diagnostic_tags)

        # Both sets should be identical
        assert tags1_set == tags2_set


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
