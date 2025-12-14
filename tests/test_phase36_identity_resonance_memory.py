"""
Phase 36: Identity Resonance Memory - Comprehensive Test Suite

This test suite validates the Phase 36 implementation with 46 tests across 6 groups:
  - Group A: Formula Math (10 tests)
  - Group B: Memory Accumulation (8 tests)
  - Group C: Volatility & Persistence (8 tests)
  - Group D: Read-Only Proof (7 tests)
  - Group E: Determinism (7 tests)
  - Group F: Import Safety (6 tests)

CRITICAL INVARIANTS:
    - INV-P36-1: Memory never alters present cognition
    - INV-P36-2: Memory is append-only
    - INV-P36-3: No authority escalation
    - INV-P36-4: Deterministic math only
    - INV-P36-5: Acoustic signals forbidden
"""

import pytest
from datetime import datetime
from typing import List, Optional

from symbolu.core.predictive.identity_memory import (
    # Version
    P36_VERSION,
    # Enums
    IdentityStabilityBand,
    # Constants
    W_UCF_SCORE,
    W_IDENTITY_HARMONICS,
    W_SCHEMA_STABILITY,
    W_INVERSE_DRIFT,
    PERSISTENCE_STABLE_THRESHOLD,
    PERSISTENCE_FRAGILE_THRESHOLD,
    VOLATILITY_STABLE_THRESHOLD,
    VOLATILITY_FRAGILE_THRESHOLD,
    DEFAULT_MEMORY_DEPTH,
    MAX_MEMORY_DEPTH,
    # Dataclass
    IdentityResonanceMemoryState,
    # State helpers
    create_state,
    stability_band_from_scores,
    create_empty_state,
    create_initial_state,
    # Formula helpers
    clamp,
    safe_get,
    # Core formulas
    compute_identity_resonance_index,
    compute_variance,
    compute_persistence_score,
    compute_volatility_index,
    compute_stability_band,
    compute_all_metrics,
    # Store functions
    compute_identity_resonance_memory,
    extract_resonance_history,
    get_latest_resonance_value,
    get_stability_trend,
    append_to_history,
)

from symbolu.mechanical.pipeline.p36_identity_resonance_memory import (
    update_identity_resonance_memory,
    extract_p36_from_coherence_state,
)


# ============================================================================
# GROUP A: FORMULA MATH TESTS (10 tests)
# ============================================================================

class TestGroupA_FormulaMath:
    """Test suite for identity resonance memory formula mathematics."""

    def test_clamp_function_basic(self):
        """Test _clamp utility function with basic values."""
        assert clamp(0.5) == 0.5
        assert clamp(-0.1) == 0.0
        assert clamp(1.5) == 1.0
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0

    def test_clamp_function_custom_range(self):
        """Test _clamp with custom min/max range."""
        assert clamp(0.5, 0.2, 0.8) == 0.5
        assert clamp(0.1, 0.2, 0.8) == 0.2
        assert clamp(0.9, 0.2, 0.8) == 0.8

    def test_safe_get_function(self):
        """Test safe_get utility function."""
        assert safe_get(0.7) == 0.7
        assert safe_get(None) == 0.5  # Default neutral
        assert safe_get(None, 0.3) == 0.3  # Custom default
        assert safe_get(1.5) == 1.0  # Clamped
        assert safe_get(-0.5) == 0.0  # Clamped

    def test_weights_sum_to_one(self):
        """Test that formula weights sum to exactly 1.0."""
        total = W_UCF_SCORE + W_IDENTITY_HARMONICS + W_SCHEMA_STABILITY + W_INVERSE_DRIFT
        assert abs(total - 1.0) < 1e-9, f"Weights must sum to 1.0, got {total}"

    def test_identity_resonance_index_basic(self):
        """Test basic identity resonance index computation."""
        # All inputs at 0.5 should give 0.5
        index = compute_identity_resonance_index(
            ucf_score=0.5,
            identity_harmonics_score=0.5,
            schema_stability=0.5,
            predicted_drift_score=0.5,
        )
        assert abs(index - 0.5) < 0.01, f"Expected ~0.5, got {index}"

    def test_identity_resonance_index_high_values(self):
        """Test identity resonance index with high input values."""
        # High values should give high index
        index = compute_identity_resonance_index(
            ucf_score=1.0,
            identity_harmonics_score=1.0,
            schema_stability=1.0,
            predicted_drift_score=0.0,  # Low drift = high stability
        )
        assert abs(index - 1.0) < 1e-9, f"Expected 1.0, got {index}"

    def test_identity_resonance_index_low_values(self):
        """Test identity resonance index with low input values."""
        # Low values should give low index
        index = compute_identity_resonance_index(
            ucf_score=0.0,
            identity_harmonics_score=0.0,
            schema_stability=0.0,
            predicted_drift_score=1.0,  # High drift = low stability
        )
        assert abs(index - 0.0) < 1e-9, f"Expected 0.0, got {index}"

    def test_identity_resonance_index_weight_application(self):
        """Test that weights are correctly applied in formula."""
        # Test each weight individually
        index = compute_identity_resonance_index(
            ucf_score=1.0,
            identity_harmonics_score=0.0,
            schema_stability=0.0,
            predicted_drift_score=1.0,  # This contributes 0 via (1-drift)
        )
        assert abs(index - W_UCF_SCORE) < 0.01, f"Expected {W_UCF_SCORE}, got {index}"

    def test_identity_resonance_index_missing_inputs(self):
        """Test identity resonance index with missing inputs (defaults to 0.5)."""
        index = compute_identity_resonance_index()  # All None
        # Should default to 0.5 for all inputs
        assert abs(index - 0.5) < 0.01, f"Expected ~0.5, got {index}"

    def test_compute_variance_basic(self):
        """Test variance computation."""
        assert compute_variance([0.5, 0.5, 0.5]) == 0.0
        assert abs(compute_variance([0.0, 1.0]) - 0.25) < 0.01
        assert compute_variance([]) == 0.0
        assert compute_variance([0.5]) == 0.0


# ============================================================================
# GROUP B: MEMORY ACCUMULATION TESTS (8 tests)
# ============================================================================

class TestGroupB_MemoryAccumulation:
    """Test suite for memory accumulation and append-only behavior."""

    def test_append_only_behavior(self):
        """Test that history is append-only and never modified."""
        # Create initial state
        state1 = compute_identity_resonance_memory(
            ucf_score=0.7,
            identity_harmonics_score=0.8,
            schema_stability=0.6,
            predicted_drift_score=0.3,
        )

        # Create second state with history
        state2 = compute_identity_resonance_memory(
            ucf_score=0.75,
            identity_harmonics_score=0.85,
            schema_stability=0.65,
            predicted_drift_score=0.25,
            prior_states=[state1],
        )

        # Verify first state is unchanged
        assert state1.memory_depth == 1
        # Verify second state has accumulated history
        assert state2.memory_depth == 2

    def test_memory_depth_correctness(self):
        """Test that memory depth is correctly tracked."""
        states = []
        for i in range(5):
            state = compute_identity_resonance_memory(
                ucf_score=0.5 + i * 0.05,
                prior_states=states,
            )
            states.append(state)

        # Each state should have increasing depth
        for i, state in enumerate(states):
            assert state.memory_depth == i + 1, f"Expected depth {i + 1}, got {state.memory_depth}"

    def test_memory_depth_cap_at_max(self):
        """Test that memory depth is capped at MAX_MEMORY_DEPTH."""
        states = []
        for i in range(MAX_MEMORY_DEPTH + 3):
            state = compute_identity_resonance_memory(
                ucf_score=0.5 + (i % 10) * 0.05,
                prior_states=states,
            )
            states.append(state)

        # Final state should have depth capped at MAX_MEMORY_DEPTH
        assert states[-1].memory_depth <= MAX_MEMORY_DEPTH

    def test_append_to_history_function(self):
        """Test append_to_history helper function."""
        state1 = create_empty_state()
        state2 = compute_identity_resonance_memory(ucf_score=0.6)

        history = [state1]
        new_history = append_to_history(state2, history)

        # Original history unchanged
        assert len(history) == 1
        # New history has both
        assert len(new_history) == 2

    def test_extract_resonance_history(self):
        """Test extract_resonance_history function."""
        states = []
        for i in range(5):
            state = compute_identity_resonance_memory(
                ucf_score=0.5 + i * 0.1,
                prior_states=states,
            )
            states.append(state)

        history = extract_resonance_history(states)
        assert len(history) == 5

    def test_get_latest_resonance_value(self):
        """Test get_latest_resonance_value function."""
        state1 = compute_identity_resonance_memory(ucf_score=0.6)
        state2 = compute_identity_resonance_memory(ucf_score=0.8, prior_states=[state1])

        latest = get_latest_resonance_value([state1, state2])
        assert latest == state2.identity_resonance_index

    def test_empty_history_handling(self):
        """Test handling of empty history."""
        state = compute_identity_resonance_memory(
            ucf_score=0.7,
            prior_states=None,
        )
        assert state.memory_depth == 1
        assert state.persistence_score == 1.0
        assert state.volatility_index == 0.0

    def test_historical_resonance_values_stored(self):
        """Test that historical resonance values are stored in state."""
        states = []
        for i in range(3):
            state = compute_identity_resonance_memory(
                ucf_score=0.5 + i * 0.1,
                prior_states=states,
            )
            states.append(state)

        # Last state should have all historical values
        assert len(states[-1].historical_resonance_values) == 3


# ============================================================================
# GROUP C: VOLATILITY & PERSISTENCE TESTS (8 tests)
# ============================================================================

class TestGroupC_VolatilityPersistence:
    """Test suite for volatility and persistence calculations."""

    def test_persistence_score_constant_values(self):
        """Test persistence score with constant resonance values."""
        values = [0.7, 0.7, 0.7, 0.7, 0.7]
        persistence = compute_persistence_score(values)
        assert persistence == 1.0, f"Expected 1.0 for constant values, got {persistence}"

    def test_persistence_score_varying_values(self):
        """Test persistence score with varying resonance values."""
        values = [0.3, 0.5, 0.7, 0.5, 0.3]
        persistence = compute_persistence_score(values)
        # Should be less than 1.0 due to variance
        assert persistence < 1.0, f"Expected < 1.0 for varying values, got {persistence}"
        assert persistence > 0.0, f"Expected > 0.0, got {persistence}"

    def test_volatility_index_constant_values(self):
        """Test volatility index with constant resonance values."""
        values = [0.7, 0.7, 0.7, 0.7, 0.7]
        volatility = compute_volatility_index(values)
        assert volatility == 0.0, f"Expected 0.0 for constant values, got {volatility}"

    def test_volatility_index_increasing_values(self):
        """Test volatility index with increasing resonance values."""
        values = [0.3, 0.4, 0.5, 0.6, 0.7]
        volatility = compute_volatility_index(values)
        # Average delta is 0.1
        assert abs(volatility - 0.1) < 0.01, f"Expected ~0.1, got {volatility}"

    def test_stability_band_stable(self):
        """Test stability band classification as 'stable'."""
        band = compute_stability_band(
            persistence_score=0.80,  # >= 0.75
            volatility_index=0.15,   # < 0.20
        )
        assert band == "stable"

    def test_stability_band_fragile_low_persistence(self):
        """Test stability band classification as 'fragile' due to low persistence."""
        band = compute_stability_band(
            persistence_score=0.35,  # < 0.40
            volatility_index=0.15,
        )
        assert band == "fragile"

    def test_stability_band_fragile_high_volatility(self):
        """Test stability band classification as 'fragile' due to high volatility."""
        band = compute_stability_band(
            persistence_score=0.80,
            volatility_index=0.50,  # >= 0.45
        )
        assert band == "fragile"

    def test_stability_band_soft(self):
        """Test stability band classification as 'soft'."""
        band = compute_stability_band(
            persistence_score=0.60,  # Between thresholds
            volatility_index=0.25,   # Between thresholds
        )
        assert band == "soft"


# ============================================================================
# GROUP D: READ-ONLY PROOF TESTS (7 tests)
# ============================================================================

class TestGroupD_ReadOnlyProof:
    """Test suite proving P36 is read-only and doesn't alter other phases."""

    def test_observer_only_flag_always_true(self):
        """Test that observer_only flag is always True."""
        state = compute_identity_resonance_memory(ucf_score=0.7)
        assert state.observer_only is True

    def test_observer_only_cannot_be_set_false(self):
        """Test that observer_only cannot be set to False."""
        with pytest.raises(ValueError):
            IdentityResonanceMemoryState(
                identity_resonance_index=0.5,
                identity_stability_band="soft",
                persistence_score=0.8,
                volatility_index=0.2,
                memory_depth=1,
                memory_timestamp=datetime.utcnow(),
                observer_only=False,  # This should raise
            )

    def test_state_is_frozen_immutable(self):
        """Test that IdentityResonanceMemoryState is frozen (immutable)."""
        state = compute_identity_resonance_memory(ucf_score=0.7)
        with pytest.raises(Exception):  # FrozenInstanceError
            state.identity_resonance_index = 0.9

    def test_architectural_phase_is_p36(self):
        """Test that architectural_phase is always 'P36'."""
        state = compute_identity_resonance_memory(ucf_score=0.7)
        assert state.architectural_phase == "P36"

    def test_version_is_set(self):
        """Test that version is set correctly."""
        state = compute_identity_resonance_memory(ucf_score=0.7)
        assert state.version == P36_VERSION

    def test_no_mutation_of_inputs(self):
        """Test that inputs are not mutated by computation."""
        prior_states = []
        for i in range(3):
            state = compute_identity_resonance_memory(
                ucf_score=0.5 + i * 0.1,
                prior_states=prior_states,
            )
            prior_states.append(state)

        original_count = len(prior_states)

        # Compute new state - should not modify prior_states
        _ = compute_identity_resonance_memory(
            ucf_score=0.9,
            prior_states=prior_states,
        )

        # Prior states should not be modified
        assert len(prior_states) == original_count

    def test_to_dict_serialization(self):
        """Test that state can be serialized to dict."""
        state = compute_identity_resonance_memory(
            ucf_score=0.7,
            identity_harmonics_score=0.8,
            schema_stability=0.6,
            predicted_drift_score=0.3,
        )
        d = state.to_dict()

        assert "identity_resonance_index" in d
        assert "identity_stability_band" in d
        assert "persistence_score" in d
        assert "volatility_index" in d
        assert "observer_only" in d
        assert d["observer_only"] is True


# ============================================================================
# GROUP E: DETERMINISM TESTS (7 tests)
# ============================================================================

class TestGroupE_Determinism:
    """Test suite for determinism guarantees."""

    def test_same_inputs_same_output(self):
        """Test that same inputs produce same output."""
        inputs = {
            "ucf_score": 0.7,
            "identity_harmonics_score": 0.8,
            "schema_stability": 0.6,
            "predicted_drift_score": 0.3,
        }

        state1 = compute_identity_resonance_memory(**inputs)
        state2 = compute_identity_resonance_memory(**inputs)

        assert state1.identity_resonance_index == state2.identity_resonance_index
        assert state1.persistence_score == state2.persistence_score
        assert state1.volatility_index == state2.volatility_index
        assert state1.identity_stability_band == state2.identity_stability_band

    def test_determinism_with_history(self):
        """Test determinism with historical data."""
        # Build identical histories
        def build_history():
            states = []
            for i in range(5):
                state = compute_identity_resonance_memory(
                    ucf_score=0.5 + i * 0.05,
                    prior_states=states,
                )
                states.append(state)
            return states

        history1 = build_history()
        history2 = build_history()

        # Final states should be identical
        assert history1[-1].identity_resonance_index == history2[-1].identity_resonance_index
        assert history1[-1].persistence_score == history2[-1].persistence_score
        assert history1[-1].volatility_index == history2[-1].volatility_index

    def test_determinism_stress_100_runs(self):
        """Test determinism with 100 repeated runs."""
        inputs = {
            "ucf_score": 0.7,
            "identity_harmonics_score": 0.8,
            "schema_stability": 0.6,
            "predicted_drift_score": 0.3,
        }

        results = []
        for _ in range(100):
            state = compute_identity_resonance_memory(**inputs)
            results.append((
                state.identity_resonance_index,
                state.persistence_score,
                state.volatility_index,
                state.identity_stability_band,
            ))

        # All results should be identical
        assert len(set(results)) == 1, "P36 should be fully deterministic"

    def test_compute_all_metrics_determinism(self):
        """Test compute_all_metrics determinism."""
        args = {
            "ucf_score": 0.7,
            "identity_harmonics_score": 0.8,
            "schema_stability": 0.6,
            "predicted_drift_score": 0.3,
            "historical_resonance_values": [0.65, 0.70, 0.72],
        }

        result1 = compute_all_metrics(**args)
        result2 = compute_all_metrics(**args)

        assert result1 == result2

    def test_stability_band_determinism(self):
        """Test stability band classification is deterministic."""
        for _ in range(50):
            band = stability_band_from_scores(0.60, 0.25)
            assert band == "soft"

    def test_variance_determinism(self):
        """Test variance computation is deterministic."""
        values = [0.3, 0.5, 0.7, 0.5, 0.3]
        results = [compute_variance(values) for _ in range(100)]
        assert len(set(results)) == 1

    def test_formula_output_determinism(self):
        """Test that formula outputs are deterministic."""
        for _ in range(50):
            index = compute_identity_resonance_index(
                ucf_score=0.75,
                identity_harmonics_score=0.80,
                schema_stability=0.70,
                predicted_drift_score=0.30,
            )
            expected = (
                W_UCF_SCORE * 0.75
                + W_IDENTITY_HARMONICS * 0.80
                + W_SCHEMA_STABILITY * 0.70
                + W_INVERSE_DRIFT * (1.0 - 0.30)
            )
            assert abs(index - expected) < 1e-9


# ============================================================================
# GROUP F: IMPORT SAFETY TESTS (6 tests)
# ============================================================================

class TestGroupF_ImportSafety:
    """Test suite for import safety - no forbidden imports."""

    def test_no_acoustic_observer_imports(self):
        """Test that P36 modules don't import acoustic observers (P22-P24)."""
        import symbolu.core.predictive.identity_memory.memory_state as state_module
        import symbolu.core.predictive.identity_memory.memory_formula as formula_module
        import symbolu.core.predictive.identity_memory.memory_store as store_module

        source_files = [
            state_module.__file__,
            formula_module.__file__,
            store_module.__file__,
        ]

        forbidden_patterns = [
            "p22_acoustic",
            "p23_alignment",
            "p24_projection",
            "acoustic_witness",
            "acoustic_observer",
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read().lower()
                    for pattern in forbidden_patterns:
                        assert pattern not in content, \
                            f"Found forbidden pattern '{pattern}' in {filepath}"

    def test_no_governance_imports(self):
        """Test that P36 modules don't import governance modules."""
        import symbolu.core.predictive.identity_memory.memory_state as state_module
        import symbolu.core.predictive.identity_memory.memory_formula as formula_module
        import symbolu.core.predictive.identity_memory.memory_store as store_module

        source_files = [
            state_module.__file__,
            formula_module.__file__,
            store_module.__file__,
        ]

        forbidden_patterns = [
            "governance",
            "planner_gate",
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read().lower()
                    for pattern in forbidden_patterns:
                        assert pattern not in content, \
                            f"Found forbidden pattern '{pattern}' in {filepath}"

    def test_no_renderer_imports(self):
        """Test that P36 modules don't import renderer modules."""
        import symbolu.core.predictive.identity_memory.memory_state as state_module
        import symbolu.core.predictive.identity_memory.memory_formula as formula_module
        import symbolu.core.predictive.identity_memory.memory_store as store_module

        source_files = [
            state_module.__file__,
            formula_module.__file__,
            store_module.__file__,
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read().lower()
                    # Check for renderer imports (not just mentions in docstrings)
                    import_lines = [l for l in content.split('\n')
                                    if 'import' in l and 'renderer' in l]
                    assert not import_lines, \
                        f"Found forbidden renderer import in {filepath}"

    def test_no_llm_imports(self):
        """Test that P36 modules don't import LLM-related modules."""
        import symbolu.core.predictive.identity_memory.memory_state as state_module
        import symbolu.core.predictive.identity_memory.memory_formula as formula_module
        import symbolu.core.predictive.identity_memory.memory_store as store_module

        source_files = [
            state_module.__file__,
            formula_module.__file__,
            store_module.__file__,
        ]

        forbidden_patterns = [
            "openai",
            "anthropic",
            "langchain",
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read().lower()
                    for pattern in forbidden_patterns:
                        # Check for import statements
                        import_check = f"import {pattern}" in content or f"from {pattern}" in content
                        assert not import_check, \
                            f"Found forbidden LLM import '{pattern}' in {filepath}"

    def test_no_random_imports(self):
        """Test that P36 modules don't import random/probabilistic modules."""
        import symbolu.core.predictive.identity_memory.memory_state as state_module
        import symbolu.core.predictive.identity_memory.memory_formula as formula_module
        import symbolu.core.predictive.identity_memory.memory_store as store_module

        source_files = [
            state_module.__file__,
            formula_module.__file__,
            store_module.__file__,
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Check for random imports
                    assert "import random" not in content, \
                        f"Found forbidden 'import random' in {filepath}"
                    assert "from random" not in content, \
                        f"Found forbidden 'from random' in {filepath}"
                    assert "numpy.random" not in content, \
                        f"Found forbidden 'numpy.random' in {filepath}"

    def test_no_insight_gating_imports(self):
        """Test that P36 doesn't import insight gating (P32) modules."""
        import symbolu.core.predictive.identity_memory.memory_state as state_module
        import symbolu.core.predictive.identity_memory.memory_formula as formula_module
        import symbolu.core.predictive.identity_memory.memory_store as store_module

        source_files = [
            state_module.__file__,
            formula_module.__file__,
            store_module.__file__,
        ]

        forbidden_patterns = [
            "p32",
            "insight_gating",
            "insight_window",
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read().lower()
                    for pattern in forbidden_patterns:
                        import_check = f"import {pattern}" in content or f"from {pattern}" in content
                        assert not import_check, \
                            f"Found forbidden pattern '{pattern}' in {filepath}"


# ============================================================================
# ADDITIONAL INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for Phase 36."""

    def test_coherence_state_has_p36_fields(self):
        """Test that CoherenceState has Phase 36 fields."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Check Phase 36 fields exist
        assert hasattr(state, 'identity_resonance_memory_snapshot')
        assert hasattr(state, 'identity_resonance_memory_history')
        assert hasattr(state, 'current_ims')
        assert hasattr(state, 'current_iep')
        assert hasattr(state, 'current_ida')
        assert hasattr(state, 'current_irm_memory_band')
        assert hasattr(state, 'current_irm_tags')

    def test_update_identity_resonance_memory_basic(self):
        """Test basic update_identity_resonance_memory function."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)
        state.current_coi = 0.75
        state.current_cih = 0.80
        state.persona_schema_stability = 0.70
        state.current_drift_magnitude_prediction = 0.30

        updated = update_identity_resonance_memory(state)

        assert updated.identity_resonance_memory_snapshot is not None
        assert updated.current_ims is not None
        assert updated.current_iep is not None
        assert updated.current_ida is not None
        assert updated.current_irm_memory_band in ("stable", "soft", "fragile")

    def test_extract_p36_from_coherence_state(self):
        """Test extract_p36_from_coherence_state function."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)
        state.current_coi = 0.75

        updated = update_identity_resonance_memory(state)
        p36_data = extract_p36_from_coherence_state(updated)

        assert p36_data is not None
        assert "identity_resonance_index" in p36_data
        assert "identity_stability_band" in p36_data
        assert "observer_only" in p36_data
        assert p36_data["observer_only"] is True

    def test_window_trim_includes_p36_histories(self):
        """Test that window_trim trims P36 histories."""
        from symbolu.core.coherence.coherence_state import CoherenceState

        state = CoherenceState(convo_id="test", turn_index=0)

        # Add some P36 history
        for i in range(5):
            state.ims_history.append(0.5 + i * 0.1)
            state.iep_history.append(0.8)
            state.ida_history.append(0.9)
            state.irm_memory_band_history.append("stable")

        # Trim to window of 3
        state.window_trim(3)

        assert len(state.ims_history) == 3
        assert len(state.iep_history) == 3
        assert len(state.ida_history) == 3
        assert len(state.irm_memory_band_history) == 3

    def test_stability_trend_analysis(self):
        """Test get_stability_trend function."""
        states = []
        # Create improving trend: fragile -> soft -> stable
        bands = ["fragile", "fragile", "soft", "soft", "stable"]
        for i, band in enumerate(bands):
            state = create_state(
                identity_resonance_index=0.5 + i * 0.1,
                identity_stability_band=band,
                persistence_score=0.5 + i * 0.1,
                volatility_index=0.4 - i * 0.05,
                memory_depth=1,
            )
            states.append(state)

        trend = get_stability_trend(states)
        assert trend == "stabilizing"

    def test_create_initial_state(self):
        """Test create_initial_state helper."""
        state = create_initial_state(
            ucf_score=0.8,
            identity_harmonics_score=0.7,
            schema_stability=0.6,
            predicted_drift_score=0.2,
        )

        assert state is not None
        assert state.memory_depth == 1
        assert state.persistence_score == 1.0
        assert state.volatility_index == 0.0

    def test_create_empty_state(self):
        """Test create_empty_state helper."""
        state = create_empty_state()

        assert state is not None
        assert state.identity_resonance_index == 0.5
        assert state.identity_stability_band == "soft"
        assert state.memory_depth == 0

    def test_json_serialization(self):
        """Test that P36 state is JSON-serializable."""
        import json

        state = compute_identity_resonance_memory(
            ucf_score=0.7,
            identity_harmonics_score=0.8,
            schema_stability=0.6,
            predicted_drift_score=0.3,
        )

        # Convert to dict
        state_dict = state.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(state_dict)
        assert json_str is not None
        assert "identity_resonance_index" in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
