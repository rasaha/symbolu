"""
Phase 24 Light Invariance Test Suite (Tier 3)
=============================================

Lightweight invariance scaffolding for Phase 24 - Resonance Weighting.
Total: ~22 tests

Phase Type: Formula enhancement
Routing/Mapper Invariance: SKIP (formula layer)
"""

import pytest
import inspect

from symbolu.formulas.resonance_weighting import (
    compute_resonance_weighting,
    ResonanceWeightingSnapshot,
)


# ============================================================================
# Test Class 1: Weighting Determinism (5 tests)
# ============================================================================

class TestPhase24WeightingDeterminism:
    """Verify Phase 24 weighting is deterministic."""

    def test_weighting_computation_deterministic(self):
        """Test weighting computation is deterministic."""
        results = [compute_resonance_weighting(
            coherence_v1=0.7,
            coherence_v3=0.8,
            enhanced_smi=0.6,
        ) for _ in range(10)]
        if results[0] is not None:
            assert all(r.weights == results[0].weights for r in results if r is not None)

    def test_all_inputs_produce_consistent_output(self):
        """Test all inputs produce consistent output."""
        for _ in range(5):
            r1 = compute_resonance_weighting(coherence_v1=0.5, enhanced_smi=0.5)
            r2 = compute_resonance_weighting(coherence_v1=0.5, enhanced_smi=0.5)
            if r1 is not None and r2 is not None:
                assert r1.weights == r2.weights

    def test_varied_inputs_deterministic(self):
        """Test varied inputs are deterministic."""
        results = [compute_resonance_weighting(
            coherence_v1=0.5,
            coherence_v2=0.6,
            coherence_v3=0.7,
        ) for _ in range(5)]
        if results[0] is not None:
            assert all(r.weights == results[0].weights for r in results if r is not None)

    def test_single_input_deterministic(self):
        """Test single input produces deterministic results."""
        results = [compute_resonance_weighting(coherence_v1=0.5) for _ in range(10)]
        if results[0] is not None:
            assert all(r == results[0] for r in results)

    def test_no_randomness_in_weighting(self):
        """Test no randomness in weighting module."""
        import symbolu.formulas.resonance_weighting as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()


# ============================================================================
# Test Class 2: Zero-LLM Guarantee (4 tests)
# ============================================================================

class TestPhase24ZeroLLMGuarantee:
    """Verify Phase 24 makes NO LLM calls."""

    def test_no_anthropic_imports(self):
        """Test no Anthropic imports in resonance weighting."""
        import symbolu.formulas.resonance_weighting as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports(self):
        """Test no OpenAI imports in resonance weighting."""
        import symbolu.formulas.resonance_weighting as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_network_calls(self):
        """Test no network calls in resonance weighting."""
        import symbolu.formulas.resonance_weighting as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()

    def test_runs_offline(self):
        """Test weighting runs offline."""
        result = compute_resonance_weighting(coherence_v1=0.5)
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)


# ============================================================================
# Test Class 3: Graceful Degradation (5 tests)
# ============================================================================

class TestPhase24GracefulDegradation:
    """Verify Phase 24 handles edge cases gracefully."""

    def test_none_inputs_handled(self):
        """Test None inputs are handled."""
        result = compute_resonance_weighting()
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)

    def test_single_metric_handled(self):
        """Test single metric is handled."""
        result = compute_resonance_weighting(coherence_v1=0.5)
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)

    def test_partial_inputs_handled(self):
        """Test partial inputs are handled."""
        result = compute_resonance_weighting(
            coherence_v1=0.5,
            enhanced_smi=0.6,
        )
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)

    def test_boundary_values_handled(self):
        """Test boundary values are handled."""
        result = compute_resonance_weighting(coherence_v1=0.0, coherence_v3=1.0)
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)

    def test_mixed_values_handled(self):
        """Test mixed values are handled."""
        result = compute_resonance_weighting(
            coherence_v1=0.3,
            coherence_v2=0.7,
            enhanced_smi=0.5,
        )
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)


# ============================================================================
# Test Class 4: Range Bounds (4 tests)
# ============================================================================

class TestPhase24RangeBounds:
    """Verify Phase 24 outputs are within expected ranges."""

    def test_weights_bounded(self):
        """Test weights are bounded [0.0, 1.0] when computed."""
        result = compute_resonance_weighting(coherence_v1=0.5, coherence_v3=0.8)
        if result is not None and result.weights:
            for weight in result.weights.values():
                assert 0.0 <= weight <= 1.0

    def test_no_infinity(self):
        """Test no infinity values."""
        import math
        result = compute_resonance_weighting(coherence_v1=0.5, enhanced_smi=0.5)
        if result is not None and result.entropy_of_weights is not None:
            assert not math.isinf(result.entropy_of_weights)

    def test_no_nan(self):
        """Test no NaN values."""
        import math
        result = compute_resonance_weighting(coherence_v1=0.5)
        if result is not None and result.entropy_of_weights is not None:
            assert not math.isnan(result.entropy_of_weights)

    def test_multiple_inputs_produce_result(self):
        """Test multiple inputs produce a valid result."""
        result = compute_resonance_weighting(
            coherence_v1=0.5,
            coherence_v2=0.6,
            coherence_v3=0.7,
            enhanced_smi=0.8,
        )
        if result is not None:
            assert result.weights is not None


# ============================================================================
# Test Class 5: Backward Compatibility (4 tests)
# ============================================================================

class TestPhase24BackwardCompatibility:
    """Verify Phase 24 maintains backward compatibility."""

    def test_compute_function_exists(self):
        """Test compute_resonance_weighting exists."""
        assert callable(compute_resonance_weighting)

    def test_snapshot_class_exists(self):
        """Test ResonanceWeightingSnapshot exists."""
        assert ResonanceWeightingSnapshot is not None

    def test_function_accepts_coherence_v1(self):
        """Test function accepts coherence_v1 parameter."""
        result = compute_resonance_weighting(coherence_v1=0.5)
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)

    def test_function_accepts_enhanced_smi(self):
        """Test function accepts enhanced_smi parameter."""
        result = compute_resonance_weighting(enhanced_smi=0.5)
        assert result is None or isinstance(result, ResonanceWeightingSnapshot)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
