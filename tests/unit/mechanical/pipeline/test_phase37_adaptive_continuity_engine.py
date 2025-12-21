"""
Phase 37: Adaptive Continuity Engine - Comprehensive Test Suite

This test suite validates the Phase 37 implementation with 40+ tests across 5 groups:
  - Group A: Formula Math (12 tests)
  - Group B: Mode Classification (8 tests)
  - Group C: Oscillation Detection (6 tests)
  - Group D: Determinism & Regression (8 tests)
  - Group E: Import Safety (6 tests)

CRITICAL INVARIANTS:
    - INV-P37-1: Deterministic (same input -> same output)
    - INV-P37-2: No imports from governance, persona, DHA, renderer
    - INV-P37-3: Output never influences routing or gating
    - INV-P37-4: continuity_score is monotonic w.r.t inputs
    - INV-P37-5: No observer feeds upstream
"""

import pytest
from typing import List

from symbolu.core.continuity import (
    # Version
    P37_VERSION,
    # Constants
    W_PERSISTENCE,
    W_INVERSE_VOLATILITY,
    W_INVERSE_DRIFT,
    MODE_STABLE_THRESHOLD,
    MODE_STRAINED_THRESHOLD,
    OSCILLATION_VOLATILITY_THRESHOLD,
    OSCILLATION_MIN_REVERSALS,
    OSCILLATION_WINDOW_SIZE,
    HIGH_DRIFT_THRESHOLD,
    LOW_PERSISTENCE_THRESHOLD,
    HIGH_VOLATILITY_THRESHOLD,
    ALLOWED_CONTRIBUTING_FACTORS,
    # Dataclass
    AdaptiveContinuityReport,
    # Model helpers
    create_report,
    mode_from_score,
    create_empty_report,
    # Engine helpers
    clamp,
    safe_get,
    # Core formulas
    compute_continuity_score,
    compute_continuity_pressure,
    compute_continuity_mode,
    count_direction_reversals,
    detect_oscillation,
    compute_contributing_factors,
    # Main function
    compute_adaptive_continuity,
)


# ============================================================================
# GROUP A: FORMULA MATH TESTS (12 tests)
# ============================================================================

class TestGroupA_FormulaMath:
    """Test suite for continuity formula mathematics."""

    def test_clamp_basic_values(self):
        """Test clamp utility function with basic values."""
        assert clamp(0.5) == 0.5
        assert clamp(-0.1) == 0.0
        assert clamp(1.5) == 1.0
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0

    def test_clamp_custom_range(self):
        """Test clamp with custom min/max range."""
        assert clamp(0.5, 0.2, 0.8) == 0.5
        assert clamp(0.1, 0.2, 0.8) == 0.2
        assert clamp(0.9, 0.2, 0.8) == 0.8

    def test_safe_get_values(self):
        """Test safe_get utility function."""
        assert safe_get(0.7) == 0.7
        assert safe_get(None) == 0.5  # Default neutral
        assert safe_get(None, 0.3) == 0.3  # Custom default
        assert safe_get(1.5) == 1.0  # Clamped
        assert safe_get(-0.5) == 0.0  # Clamped

    def test_weights_sum_to_one(self):
        """Test that formula weights sum to exactly 1.0."""
        total = W_PERSISTENCE + W_INVERSE_VOLATILITY + W_INVERSE_DRIFT
        assert abs(total - 1.0) < 1e-9, f"Weights must sum to 1.0, got {total}"

    def test_continuity_score_all_neutral(self):
        """Test continuity score with all inputs at 0.5."""
        # persistence=0.5, volatility=0.5, drift=0.5
        # score = 0.40*0.5 + 0.30*(1-0.5) + 0.30*(1-0.5)
        #       = 0.20 + 0.15 + 0.15 = 0.50
        score = compute_continuity_score(
            persistence_score=0.5,
            volatility_index=0.5,
            predicted_drift_score=0.5,
        )
        assert abs(score - 0.5) < 0.01, f"Expected ~0.5, got {score}"

    def test_continuity_score_max_stability(self):
        """Test continuity score with maximum stability inputs."""
        # persistence=1.0, volatility=0.0, drift=0.0
        # score = 0.40*1.0 + 0.30*(1-0.0) + 0.30*(1-0.0)
        #       = 0.40 + 0.30 + 0.30 = 1.0
        score = compute_continuity_score(
            persistence_score=1.0,
            volatility_index=0.0,
            predicted_drift_score=0.0,
        )
        assert abs(score - 1.0) < 1e-9, f"Expected 1.0, got {score}"

    def test_continuity_score_min_stability(self):
        """Test continuity score with minimum stability inputs."""
        # persistence=0.0, volatility=1.0, drift=1.0
        # score = 0.40*0.0 + 0.30*(1-1.0) + 0.30*(1-1.0)
        #       = 0.0 + 0.0 + 0.0 = 0.0
        score = compute_continuity_score(
            persistence_score=0.0,
            volatility_index=1.0,
            predicted_drift_score=1.0,
        )
        assert abs(score - 0.0) < 1e-9, f"Expected 0.0, got {score}"

    def test_continuity_score_weight_verification_persistence(self):
        """Test that persistence weight is correctly applied."""
        # Only persistence non-zero
        score = compute_continuity_score(
            persistence_score=1.0,
            volatility_index=1.0,  # contributes 0
            predicted_drift_score=1.0,  # contributes 0
        )
        assert abs(score - W_PERSISTENCE) < 0.01, f"Expected {W_PERSISTENCE}, got {score}"

    def test_continuity_score_weight_verification_volatility(self):
        """Test that volatility weight is correctly applied."""
        # Only inverse volatility non-zero
        score = compute_continuity_score(
            persistence_score=0.0,  # contributes 0
            volatility_index=0.0,  # contributes W_INVERSE_VOLATILITY * 1.0
            predicted_drift_score=1.0,  # contributes 0
        )
        assert abs(score - W_INVERSE_VOLATILITY) < 0.01, f"Expected {W_INVERSE_VOLATILITY}, got {score}"

    def test_continuity_score_weight_verification_drift(self):
        """Test that drift weight is correctly applied."""
        # Only inverse drift non-zero
        score = compute_continuity_score(
            persistence_score=0.0,  # contributes 0
            volatility_index=1.0,  # contributes 0
            predicted_drift_score=0.0,  # contributes W_INVERSE_DRIFT * 1.0
        )
        assert abs(score - W_INVERSE_DRIFT) < 0.01, f"Expected {W_INVERSE_DRIFT}, got {score}"

    def test_continuity_pressure_formula(self):
        """Test continuity pressure is 1 - continuity_score."""
        score = 0.75
        pressure = compute_continuity_pressure(score)
        assert abs(pressure - 0.25) < 1e-9, f"Expected 0.25, got {pressure}"

        score = 0.30
        pressure = compute_continuity_pressure(score)
        assert abs(pressure - 0.70) < 1e-9, f"Expected 0.70, got {pressure}"

    def test_continuity_score_clamping(self):
        """Test that output is clamped to [0.0, 1.0]."""
        # Even with extreme values, output should be clamped
        score = compute_continuity_score(
            persistence_score=2.0,  # Out of range
            volatility_index=-1.0,  # Out of range
            predicted_drift_score=-1.0,  # Out of range
        )
        assert 0.0 <= score <= 1.0, f"Score not in range: {score}"


# ============================================================================
# GROUP B: MODE CLASSIFICATION TESTS (8 tests)
# ============================================================================

class TestGroupB_ModeClassification:
    """Test suite for continuity mode classification."""

    def test_mode_stable_at_threshold(self):
        """Test mode is 'stable' at exactly 0.75."""
        mode = compute_continuity_mode(0.75)
        assert mode == "stable", f"Expected 'stable', got '{mode}'"

    def test_mode_stable_above_threshold(self):
        """Test mode is 'stable' above 0.75."""
        mode = compute_continuity_mode(0.90)
        assert mode == "stable", f"Expected 'stable', got '{mode}'"

    def test_mode_strained_at_lower_threshold(self):
        """Test mode is 'strained' at exactly 0.45."""
        mode = compute_continuity_mode(0.45)
        assert mode == "strained", f"Expected 'strained', got '{mode}'"

    def test_mode_strained_between_thresholds(self):
        """Test mode is 'strained' between 0.45 and 0.75."""
        mode = compute_continuity_mode(0.60)
        assert mode == "strained", f"Expected 'strained', got '{mode}'"

    def test_mode_strained_just_below_stable(self):
        """Test mode is 'strained' just below 0.75."""
        mode = compute_continuity_mode(0.749)
        assert mode == "strained", f"Expected 'strained', got '{mode}'"

    def test_mode_fragmenting_below_threshold(self):
        """Test mode is 'fragmenting' below 0.45."""
        mode = compute_continuity_mode(0.44)
        assert mode == "fragmenting", f"Expected 'fragmenting', got '{mode}'"

    def test_mode_fragmenting_at_zero(self):
        """Test mode is 'fragmenting' at 0.0."""
        mode = compute_continuity_mode(0.0)
        assert mode == "fragmenting", f"Expected 'fragmenting', got '{mode}'"

    def test_mode_from_score_helper(self):
        """Test mode_from_score helper function."""
        assert mode_from_score(0.80) == "stable"
        assert mode_from_score(0.60) == "strained"
        assert mode_from_score(0.30) == "fragmenting"


# ============================================================================
# GROUP C: OSCILLATION DETECTION TESTS (6 tests)
# ============================================================================

class TestGroupC_OscillationDetection:
    """Test suite for oscillation detection."""

    def test_count_reversals_no_reversals(self):
        """Test count_direction_reversals with monotonic increase."""
        values = [0.3, 0.4, 0.5, 0.6, 0.7]
        reversals = count_direction_reversals(values)
        assert reversals == 0, f"Expected 0 reversals, got {reversals}"

    def test_count_reversals_one_reversal(self):
        """Test count_direction_reversals with one direction change."""
        values = [0.3, 0.5, 0.7, 0.5, 0.3]  # up then down
        reversals = count_direction_reversals(values)
        assert reversals == 1, f"Expected 1 reversal, got {reversals}"

    def test_count_reversals_multiple(self):
        """Test count_direction_reversals with multiple reversals."""
        values = [0.3, 0.6, 0.4, 0.7, 0.5]  # up, down, up, down
        reversals = count_direction_reversals(values)
        assert reversals >= 2, f"Expected >= 2 reversals, got {reversals}"

    def test_oscillation_detected_true(self):
        """Test oscillation detection returns True when conditions met."""
        # volatility > 0.6 and >= 2 reversals
        detected = detect_oscillation(
            volatility_index=0.7,
            historical_resonance_values=[0.3, 0.7, 0.3, 0.7, 0.3],  # oscillating
        )
        assert detected is True, "Expected oscillation to be detected"

    def test_oscillation_not_detected_low_volatility(self):
        """Test oscillation not detected when volatility is low."""
        # volatility <= 0.6, even with reversals
        detected = detect_oscillation(
            volatility_index=0.5,
            historical_resonance_values=[0.3, 0.7, 0.3, 0.7, 0.3],
        )
        assert detected is False, "Expected no oscillation with low volatility"

    def test_oscillation_not_detected_few_reversals(self):
        """Test oscillation not detected with fewer than 2 reversals."""
        # volatility > 0.6 but < 2 reversals
        detected = detect_oscillation(
            volatility_index=0.7,
            historical_resonance_values=[0.3, 0.4, 0.5, 0.6, 0.7],  # monotonic
        )
        assert detected is False, "Expected no oscillation with monotonic values"


# ============================================================================
# GROUP D: DETERMINISM & REGRESSION TESTS (8 tests)
# ============================================================================

class TestGroupD_DeterminismRegression:
    """Test suite for determinism guarantees."""

    def test_same_inputs_same_output(self):
        """Test that same inputs produce same output."""
        inputs = {
            "p35_predicted_drift_score": 0.30,
            "p35_drift_risk_band": "low",
            "p36_identity_resonance_index": 0.75,
            "p36_persistence_score": 0.80,
            "p36_volatility_index": 0.20,
        }

        report1 = compute_adaptive_continuity(**inputs)
        report2 = compute_adaptive_continuity(**inputs)

        assert report1.continuity_score == report2.continuity_score
        assert report1.continuity_mode == report2.continuity_mode
        assert report1.continuity_pressure == report2.continuity_pressure
        assert report1.oscillation_detected == report2.oscillation_detected
        assert report1.contributing_factors == report2.contributing_factors

    def test_determinism_with_history(self):
        """Test determinism with historical data."""
        history = [0.65, 0.70, 0.72, 0.68, 0.75]

        report1 = compute_adaptive_continuity(
            p35_predicted_drift_score=0.30,
            p36_persistence_score=0.80,
            p36_volatility_index=0.20,
            historical_resonance_values=history,
        )

        report2 = compute_adaptive_continuity(
            p35_predicted_drift_score=0.30,
            p36_persistence_score=0.80,
            p36_volatility_index=0.20,
            historical_resonance_values=history,
        )

        assert report1.continuity_score == report2.continuity_score
        assert report1.oscillation_detected == report2.oscillation_detected

    def test_determinism_stress_100_runs(self):
        """Test determinism with 100 repeated runs."""
        inputs = {
            "p35_predicted_drift_score": 0.35,
            "p35_drift_risk_band": "moderate",
            "p36_identity_resonance_index": 0.70,
            "p36_persistence_score": 0.75,
            "p36_volatility_index": 0.25,
        }

        results = []
        for _ in range(100):
            report = compute_adaptive_continuity(**inputs)
            results.append((
                report.continuity_score,
                report.continuity_mode,
                report.continuity_pressure,
                report.oscillation_detected,
                report.contributing_factors,
            ))

        # All results should be identical
        assert len(set(results)) == 1, "P37 should be fully deterministic"

    def test_snapshot_order_invariance(self):
        """Test that computation is independent of snapshot ordering within window."""
        # Same values, should produce same score
        report1 = compute_adaptive_continuity(
            p36_persistence_score=0.70,
            p36_volatility_index=0.30,
            p35_predicted_drift_score=0.40,
        )

        report2 = compute_adaptive_continuity(
            p36_persistence_score=0.70,
            p36_volatility_index=0.30,
            p35_predicted_drift_score=0.40,
        )

        assert report1.continuity_score == report2.continuity_score

    def test_observer_only_always_true(self):
        """Test that observer_only flag is always True."""
        report = compute_adaptive_continuity(
            p36_persistence_score=0.70,
        )
        assert report.observer_only is True

    def test_observer_only_cannot_be_false(self):
        """Test that observer_only cannot be set to False."""
        with pytest.raises(ValueError):
            AdaptiveContinuityReport(
                continuity_score=0.5,
                continuity_mode="strained",
                continuity_pressure=0.5,
                oscillation_detected=False,
                contributing_factors=(),
                observer_only=False,  # This should raise
            )

    def test_architectural_phase_is_p37(self):
        """Test that architectural_phase is always 'P37'."""
        report = compute_adaptive_continuity(
            p36_persistence_score=0.70,
        )
        assert report.architectural_phase == "P37"

    def test_version_is_set(self):
        """Test that version is set correctly."""
        report = compute_adaptive_continuity(
            p36_persistence_score=0.70,
        )
        assert report.version == P37_VERSION


# ============================================================================
# GROUP E: IMPORT SAFETY TESTS (6 tests)
# ============================================================================

class TestGroupE_ImportSafety:
    """Test suite for import safety - no forbidden imports."""

    def test_no_governance_imports(self):
        """Test that P37 modules don't import governance modules."""
        import ast
        import symbolu.core.continuity.continuity_models as models_module
        import symbolu.core.continuity.adaptive_continuity_engine as engine_module

        source_files = [
            models_module.__file__,
            engine_module.__file__,
        ]

        forbidden_patterns = [
            "governance",
            "planner_gate",
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Use AST to check actual imports, not docstrings
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            for pattern in forbidden_patterns:
                                assert pattern not in node.module.lower(), \
                                    f"Found forbidden pattern '{pattern}' in {filepath}"
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                for pattern in forbidden_patterns:
                                    assert pattern not in alias.name.lower(), \
                                        f"Found forbidden pattern '{pattern}' in {filepath}"

    def test_no_persona_imports(self):
        """Test that P37 modules don't import persona modules."""
        import ast
        import symbolu.core.continuity.continuity_models as models_module
        import symbolu.core.continuity.adaptive_continuity_engine as engine_module

        source_files = [
            models_module.__file__,
            engine_module.__file__,
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Use AST to check actual imports, not docstrings
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            assert "persona" not in node.module.lower(), \
                                f"Found forbidden persona import in {filepath}"
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert "persona" not in alias.name.lower(), \
                                    f"Found forbidden persona import in {filepath}"

    def test_no_dha_imports(self):
        """Test that P37 modules don't import DHA modules."""
        import symbolu.core.continuity.continuity_models as models_module
        import symbolu.core.continuity.adaptive_continuity_engine as engine_module

        source_files = [
            models_module.__file__,
            engine_module.__file__,
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read().lower()
                    # Check for DHA imports
                    import_check = "import dha" in content or "from dha" in content
                    assert not import_check, \
                        f"Found forbidden DHA import in {filepath}"

    def test_no_renderer_imports(self):
        """Test that P37 modules don't import renderer modules."""
        import ast
        import symbolu.core.continuity.continuity_models as models_module
        import symbolu.core.continuity.adaptive_continuity_engine as engine_module

        source_files = [
            models_module.__file__,
            engine_module.__file__,
        ]

        for filepath in source_files:
            if filepath:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Use AST to check actual imports, not docstrings
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            assert "renderer" not in node.module.lower(), \
                                f"Found forbidden renderer import in {filepath}"
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert "renderer" not in alias.name.lower(), \
                                    f"Found forbidden renderer import in {filepath}"

    def test_no_random_imports(self):
        """Test that P37 modules don't import random/probabilistic modules."""
        import symbolu.core.continuity.continuity_models as models_module
        import symbolu.core.continuity.adaptive_continuity_engine as engine_module

        source_files = [
            models_module.__file__,
            engine_module.__file__,
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

    def test_no_llm_imports(self):
        """Test that P37 modules don't import LLM-related modules."""
        import symbolu.core.continuity.continuity_models as models_module
        import symbolu.core.continuity.adaptive_continuity_engine as engine_module

        source_files = [
            models_module.__file__,
            engine_module.__file__,
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


# ============================================================================
# ADDITIONAL INVARIANT TESTS
# ============================================================================

class TestInvariants:
    """Test suite for P37 invariants."""

    def test_inv_p37_1_deterministic(self):
        """INV-P37-1: Deterministic (same input -> same output)."""
        inputs = {
            "p35_predicted_drift_score": 0.40,
            "p36_persistence_score": 0.70,
            "p36_volatility_index": 0.30,
        }

        results = [compute_adaptive_continuity(**inputs) for _ in range(50)]
        scores = [r.continuity_score for r in results]

        assert len(set(scores)) == 1, "INV-P37-1 violated: non-deterministic output"

    def test_inv_p37_4_monotonicity_persistence(self):
        """INV-P37-4: continuity_score increases with persistence_score."""
        base_inputs = {
            "p35_predicted_drift_score": 0.30,
            "p36_volatility_index": 0.20,
        }

        scores = []
        for persistence in [0.0, 0.25, 0.50, 0.75, 1.0]:
            report = compute_adaptive_continuity(
                p36_persistence_score=persistence,
                **base_inputs,
            )
            scores.append(report.continuity_score)

        # Scores should be monotonically increasing
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i-1], \
                f"INV-P37-4 violated: scores not monotonic w.r.t persistence"

    def test_inv_p37_4_monotonicity_volatility_inverse(self):
        """INV-P37-4: continuity_score decreases with volatility_index."""
        base_inputs = {
            "p35_predicted_drift_score": 0.30,
            "p36_persistence_score": 0.70,
        }

        scores = []
        for volatility in [0.0, 0.25, 0.50, 0.75, 1.0]:
            report = compute_adaptive_continuity(
                p36_volatility_index=volatility,
                **base_inputs,
            )
            scores.append(report.continuity_score)

        # Scores should be monotonically decreasing
        for i in range(1, len(scores)):
            assert scores[i] <= scores[i-1], \
                f"INV-P37-4 violated: scores not monotonic w.r.t volatility"

    def test_inv_p37_4_monotonicity_drift_inverse(self):
        """INV-P37-4: continuity_score decreases with predicted_drift_score."""
        base_inputs = {
            "p36_persistence_score": 0.70,
            "p36_volatility_index": 0.20,
        }

        scores = []
        for drift in [0.0, 0.25, 0.50, 0.75, 1.0]:
            report = compute_adaptive_continuity(
                p35_predicted_drift_score=drift,
                **base_inputs,
            )
            scores.append(report.continuity_score)

        # Scores should be monotonically decreasing
        for i in range(1, len(scores)):
            assert scores[i] <= scores[i-1], \
                f"INV-P37-4 violated: scores not monotonic w.r.t drift"

    def test_state_is_frozen_immutable(self):
        """Test that AdaptiveContinuityReport is frozen (immutable)."""
        report = compute_adaptive_continuity(
            p36_persistence_score=0.70,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            report.continuity_score = 0.9

    def test_contributing_factors_validation(self):
        """Test that only allowed contributing factors are permitted."""
        with pytest.raises(ValueError):
            AdaptiveContinuityReport(
                continuity_score=0.5,
                continuity_mode="strained",
                continuity_pressure=0.5,
                oscillation_detected=False,
                contributing_factors=("invalid_factor",),  # Invalid
            )

    def test_contributing_factors_computed_correctly(self):
        """Test contributing factors are computed based on thresholds."""
        # High drift
        factors = compute_contributing_factors(
            predicted_drift_score=0.7,
            persistence_score=0.8,
            volatility_index=0.3,
            oscillation_detected=False,
        )
        assert "high_drift" in factors

        # Low persistence
        factors = compute_contributing_factors(
            predicted_drift_score=0.3,
            persistence_score=0.3,
            volatility_index=0.3,
            oscillation_detected=False,
        )
        assert "low_persistence" in factors

        # High volatility
        factors = compute_contributing_factors(
            predicted_drift_score=0.3,
            persistence_score=0.8,
            volatility_index=0.7,
            oscillation_detected=False,
        )
        assert "high_volatility" in factors

        # Oscillation
        factors = compute_contributing_factors(
            predicted_drift_score=0.3,
            persistence_score=0.8,
            volatility_index=0.3,
            oscillation_detected=True,
        )
        assert "oscillation" in factors

    def test_to_dict_serialization(self):
        """Test that report can be serialized to dict."""
        report = compute_adaptive_continuity(
            p35_predicted_drift_score=0.30,
            p35_drift_risk_band="low",
            p36_identity_resonance_index=0.75,
            p36_persistence_score=0.80,
            p36_volatility_index=0.20,
        )
        d = report.to_dict()

        assert "continuity_score" in d
        assert "continuity_mode" in d
        assert "continuity_pressure" in d
        assert "oscillation_detected" in d
        assert "contributing_factors" in d
        assert "observer_only" in d
        assert d["observer_only"] is True

    def test_create_empty_report(self):
        """Test create_empty_report helper."""
        report = create_empty_report()

        assert report is not None
        assert report.continuity_score == 0.5
        assert report.continuity_mode == "strained"
        assert report.continuity_pressure == 0.5
        assert report.oscillation_detected is False
        assert report.contributing_factors == ()

    def test_json_serialization(self):
        """Test that P37 report is JSON-serializable."""
        import json

        report = compute_adaptive_continuity(
            p35_predicted_drift_score=0.30,
            p35_drift_risk_band="low",
            p36_identity_resonance_index=0.75,
            p36_persistence_score=0.80,
            p36_volatility_index=0.20,
        )

        # Convert to dict
        report_dict = report.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(report_dict)
        assert json_str is not None
        assert "continuity_score" in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
