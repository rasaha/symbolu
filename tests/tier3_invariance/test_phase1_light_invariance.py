"""
Phase 1 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 1 - Resonance Formulas.
Total: ~22 tests

Test Coverage:
    1. TestPhase1FormulaDeterminism (5 tests)
    2. TestPhase1ZeroLLMGuarantee (4 tests)
    3. TestPhase1GracefulDegradation (5 tests)
    4. TestPhase1RangeBounds (4 tests)
    5. TestPhase1BackwardCompatibility (4 tests)

Phase Type: Foundational (mathematical core)
Routing/Mapper Invariance: SKIP (foundational layer, no routing)
"""

import pytest
import inspect

from symbolu.formulas.resonance_formulas import (
    compute_smi,
    compute_delta_smi,
    compute_bhava_gap,
    compute_tension_corridor,
)


# ============================================================================
# Test Class 1: Formula Determinism (5 tests)
# ============================================================================

class TestPhase1FormulaDeterminism:
    """Verify Phase 1 formulas are 100% deterministic."""

    def test_smi_deterministic_two_iterations(self):
        """Test SMI determinism across 2 iterations."""
        result1 = compute_smi(0.5, 0.5, 0.5)
        result2 = compute_smi(0.5, 0.5, 0.5)
        assert result1 == result2

    def test_smi_deterministic_ten_iterations(self):
        """Test SMI determinism across 10 iterations."""
        results = [compute_smi(0.7, 0.3, 0.6) for _ in range(10)]
        assert len(set(results)) == 1

    def test_delta_smi_deterministic_ten_iterations(self):
        """Test delta SMI determinism across 10 iterations."""
        results = [compute_delta_smi(0.8, 0.5) for _ in range(10)]
        assert len(set(results)) == 1

    def test_bhava_gap_deterministic_ten_iterations(self):
        """Test bhava gap determinism across 10 iterations."""
        results = [compute_bhava_gap(3, 7) for _ in range(10)]
        assert len(set(results)) == 1

    def test_tension_corridor_deterministic_ten_iterations(self):
        """Test tension corridor determinism across 10 iterations."""
        # tension_corridor takes (delta_smi, bhava_gap)
        results = [compute_tension_corridor(0.4, 0.5) for _ in range(10)]
        assert len(set(results)) == 1


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase1ZeroLLMGuarantee:
    """Verify Phase 1 makes NO LLM calls."""

    def test_no_anthropic_imports(self):
        """Test no Anthropic imports in resonance_formulas module."""
        import symbolu.formulas.resonance_formulas as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports(self):
        """Test no OpenAI imports in resonance_formulas module."""
        import symbolu.formulas.resonance_formulas as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_calls(self):
        """Test no network call imports in resonance_formulas module."""
        import symbolu.formulas.resonance_formulas as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()
        assert 'urllib' not in source.lower()
        assert 'httpx' not in source.lower()

    def test_runs_completely_offline(self):
        """Test that all formulas can run completely offline."""
        # These should all execute without any network
        smi = compute_smi(0.5, 0.5, 0.5)
        delta = compute_delta_smi(0.6, 0.4)
        gap = compute_bhava_gap(2, 8)
        # tension_corridor takes (delta_smi, bhava_gap)
        tension = compute_tension_corridor(0.3, 0.5)
        assert all(x is not None for x in [smi, delta, gap, tension])


# ============================================================================
# Test Class 3: Graceful Degradation (5 tests)
# ============================================================================

class TestPhase1GracefulDegradation:
    """Verify Phase 1 handles edge cases gracefully."""

    def test_delta_smi_handles_none_previous(self):
        """Test delta SMI handles None previous value (first turn)."""
        result = compute_delta_smi(0.5, None)
        assert result == 0.0

    def test_smi_handles_zero_inputs(self):
        """Test SMI handles all-zero inputs."""
        result = compute_smi(0.0, 0.0, 0.0)
        assert result == 0.0
        assert isinstance(result, float)

    def test_smi_handles_max_inputs(self):
        """Test SMI handles all-max inputs."""
        result = compute_smi(1.0, 1.0, 1.0)
        assert result == 1.0
        assert isinstance(result, float)

    def test_bhava_gap_handles_same_position(self):
        """Test bhava gap handles same position (zero gap)."""
        result = compute_bhava_gap(5, 5)
        assert result == 0

    def test_formulas_raise_on_invalid_not_crash(self):
        """Test formulas raise ValueError on invalid input, not crash."""
        with pytest.raises(ValueError):
            compute_smi(-0.1, 0.5, 0.5)  # Negative input
        with pytest.raises(ValueError):
            compute_smi(1.5, 0.5, 0.5)  # Above 1.0


# ============================================================================
# Test Class 4: Range Bounds (4 tests)
# ============================================================================

class TestPhase1RangeBounds:
    """Verify Phase 1 outputs are within expected ranges."""

    def test_smi_output_bounded_0_to_1(self):
        """Test SMI output is in [0.0, 1.0] range."""
        test_cases = [
            (0.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (0.5, 0.5, 0.5),
            (0.1, 0.9, 0.3),
        ]
        for dr, vi, bp in test_cases:
            result = compute_smi(dr, vi, bp)
            assert 0.0 <= result <= 1.0, f"SMI out of bounds for inputs {dr}, {vi}, {bp}"

    def test_delta_smi_bounded_minus1_to_1(self):
        """Test delta SMI is in [-1.0, 1.0] range."""
        test_cases = [
            (0.0, 1.0),  # Max negative
            (1.0, 0.0),  # Max positive
            (0.5, 0.5),  # Zero
        ]
        for smi, prev in test_cases:
            result = compute_delta_smi(smi, prev)
            assert -1.0 <= result <= 1.0

    def test_bhava_gap_bounded_0_to_1(self):
        """Test bhava gap is in [0.0, 1.0] range (normalized)."""
        for pos1 in range(12):
            for pos2 in range(12):
                result = compute_bhava_gap(pos1, pos2)
                assert 0.0 <= result <= 1.0

    def test_tension_corridor_bounded_0_to_1(self):
        """Test tension corridor is in [0.0, 1.0] range."""
        # tension_corridor takes (delta_smi, bhava_gap)
        test_cases = [
            (0.0, 0.0),
            (1.0, 1.0),
            (-0.5, 0.5),
        ]
        for delta, gap in test_cases:
            result = compute_tension_corridor(delta, gap)
            assert 0.0 <= result <= 1.0


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase1BackwardCompatibility:
    """Verify Phase 1 maintains backward compatibility."""

    def test_smi_signature_unchanged(self):
        """Test SMI function signature hasn't changed."""
        sig = inspect.signature(compute_smi)
        params = list(sig.parameters.keys())
        assert 'dimensional_resonance' in params
        assert 'vrtti_intensity' in params
        assert 'bhava_position' in params

    def test_delta_smi_signature_unchanged(self):
        """Test delta SMI function signature hasn't changed."""
        sig = inspect.signature(compute_delta_smi)
        params = list(sig.parameters.keys())
        assert 'smi' in params
        assert 'previous_smi' in params

    def test_return_types_stable(self):
        """Test return types are stable floats."""
        assert isinstance(compute_smi(0.5, 0.5, 0.5), float)
        assert isinstance(compute_delta_smi(0.5, 0.3), float)
        assert isinstance(compute_bhava_gap(3, 7), float)  # Returns normalized float
        assert isinstance(compute_tension_corridor(0.3, 0.5), float)

    def test_canonical_values_unchanged(self):
        """Test canonical values haven't drifted."""
        # These are baseline values that should remain stable
        smi = compute_smi(0.5, 0.5, 0.5)
        assert 0.49 <= smi <= 0.51  # Should be ~0.5

        delta = compute_delta_smi(0.7, 0.3)
        assert 0.39 <= delta <= 0.41  # Should be 0.4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
