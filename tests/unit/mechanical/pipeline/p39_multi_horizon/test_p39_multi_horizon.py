"""
Phase 39 - Multi-Horizon Temporal Forecasting Tests

Test suite for P39 following the TESTING.md policy:
    - Exactly one test per invariant
    - Each test must declare which invariant it proves

INVARIANTS TESTED:
    - INV-P39-1: Observer-only (no influence on any authoritative phase)
    - INV-P39-2: Deterministic (same inputs -> same outputs)
    - INV-P39-3: Horizon monotonicity (flag if long_term > short_term, don't correct)
    - INV-P39-4: No horizon can exceed Phase 38 base forecast
    - INV-P39-5: Absence-safe (missing inputs degrade confidence, never inflate)
"""

import inspect
import pytest
from dataclasses import dataclass
from typing import Any, Optional

from symbolu.mechanical.pipeline.p39_multi_horizon import (
    P39_VERSION,
    ALPHA,
    BETA,
    GAMMA,
    MultiHorizonForecast,
    classify_band,
    create_forecast,
    clamp,
    compute_short_term,
    compute_medium_term,
    compute_long_term,
    compute_horizon_divergence,
    check_monotonicity_violation,
    resolve_multi_horizon,
    maybe_run_p39,
    run_p39_directly,
    is_p39_disabled,
    has_p39_forecast,
    get_p39_forecast,
    get_short_term_score,
    get_medium_term_score,
    get_long_term_score,
    get_horizon_divergence,
    get_p39_version,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockP38:
    """Mock P38 report for testing."""
    forecast_score: float = 0.7


@dataclass
class MockP19:
    """Mock P19 report for testing."""
    drift_fusion_index: float = 0.3


@dataclass
class MockP18:
    """Mock P18 report for testing."""
    volatility_band: str = "MED"
    entropy_now: float = 0.5


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p38: Optional[MockP38] = None
    p19: Optional[MockP19] = None
    p18: Optional[MockP18] = None
    p39_multi_horizon: Optional[MultiHorizonForecast] = None
    _p39_disabled: bool = False

    # Upstream authoritative phases that P39 MUST NOT modify
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None
    p10_acoustic: Optional[Any] = None


# ============================================================================
# INVARIANT TESTS - One test per invariant as required by TESTING.md
# ============================================================================


# Proves INV-P39-1: Observer-only (no influence on any authoritative phase)
def test_inv_p39_1_observer_only_no_upstream_modification():
    """
    Invariant: INV-P39-1
    Proves that P39 does not modify any upstream authoritative phase envelopes.

    P39 must be observer-only: it reads from P38, P18, P19 but must never
    modify P6 regime, P7 discourse, semantic frame, lexical frame, or acoustics.
    """
    ctx = MockPipelineContext(
        p38=MockP38(forecast_score=0.8),
        p19=MockP19(drift_fusion_index=0.3),
        p18=MockP18(volatility_band="MED"),
        p6_regime="test_regime",
        p7_discourse_envelope="test_discourse",
        semantic_frame="test_semantic",
        lexical_frame="test_lexical",
        p10_acoustic="test_acoustic",
    )

    # Store original values
    original_p6 = ctx.p6_regime
    original_p7 = ctx.p7_discourse_envelope
    original_semantic = ctx.semantic_frame
    original_lexical = ctx.lexical_frame
    original_acoustic = ctx.p10_acoustic

    # Run P39
    result = maybe_run_p39(ctx)

    # Verify P39 ran successfully
    assert result is not None
    assert ctx.p39_multi_horizon is not None

    # Verify NO upstream phases were modified (INV-P39-1)
    assert ctx.p6_regime == original_p6, "P39 modified P6 regime"
    assert ctx.p7_discourse_envelope == original_p7, "P39 modified P7 discourse"
    assert ctx.semantic_frame == original_semantic, "P39 modified semantic frame"
    assert ctx.lexical_frame == original_lexical, "P39 modified lexical frame"
    assert ctx.p10_acoustic == original_acoustic, "P39 modified P10 acoustic"

    # Verify observer_only flag is True
    assert result.observer_only is True


# Proves INV-P39-2: Deterministic (same inputs -> same outputs)
def test_inv_p39_2_deterministic_same_inputs_same_outputs():
    """
    Invariant: INV-P39-2
    Proves that identical inputs always produce identical outputs.

    P39 uses only deterministic math with fixed formulas. No LLM calls,
    no randomness, no external state dependencies.
    """
    inputs = {
        "p38_forecast_score": 0.75,
        "drift_fusion_index": 0.35,
        "entropy_volatility": 0.45,
    }

    # Run 10 times and collect results
    results = []
    for _ in range(10):
        result = run_p39_directly(**inputs)
        results.append(result)

    # All results must be identical
    first = results[0]
    for i, result in enumerate(results[1:], start=2):
        assert result.short_term_score == first.short_term_score, \
            f"Run {i} short_term differs from run 1"
        assert result.medium_term_score == first.medium_term_score, \
            f"Run {i} medium_term differs from run 1"
        assert result.long_term_score == first.long_term_score, \
            f"Run {i} long_term differs from run 1"
        assert result.short_term_band == first.short_term_band, \
            f"Run {i} short_term_band differs from run 1"
        assert result.medium_term_band == first.medium_term_band, \
            f"Run {i} medium_term_band differs from run 1"
        assert result.long_term_band == first.long_term_band, \
            f"Run {i} long_term_band differs from run 1"
        assert result.horizon_divergence == first.horizon_divergence, \
            f"Run {i} horizon_divergence differs from run 1"


# Proves INV-P39-3: Horizon monotonicity (flag if long_term > short_term, don't correct)
def test_inv_p39_3_monotonicity_flags_violation_without_correction():
    """
    Invariant: INV-P39-3
    Proves that if long_term > short_term, we flag the divergence but DO NOT correct it.

    Under normal operation with the formula:
        short_term = P38.score
        medium_term = P38.score - ALPHA * drift
        long_term = P38.score - BETA * drift - GAMMA * volatility

    long_term should never exceed short_term. But if inputs somehow cause it
    (e.g., negative drift which shouldn't happen), we flag via monotonicity_violated
    but we do NOT artificially correct the values.

    This test verifies the monotonicity check function works correctly.
    """
    # Test case 1: Normal case - short > long (no violation)
    assert check_monotonicity_violation(short_term=0.8, long_term=0.6) is False

    # Test case 2: Edge case - short == long (no violation)
    assert check_monotonicity_violation(short_term=0.7, long_term=0.7) is False

    # Test case 3: Violation case - long > short (violation flagged)
    assert check_monotonicity_violation(short_term=0.5, long_term=0.6) is True

    # Test case 4: Verify in full resolver that monotonicity_violated is set correctly
    # Normal inputs should not trigger violation
    result_normal = run_p39_directly(
        p38_forecast_score=0.8,
        drift_fusion_index=0.5,
        entropy_volatility=0.5,
    )
    assert result_normal.monotonicity_violated is False
    assert result_normal.short_term_score >= result_normal.long_term_score

    # Verify the flag exists and is accessible
    assert hasattr(result_normal, 'monotonicity_violated')


# Proves INV-P39-4: No horizon can exceed Phase 38 base forecast
def test_inv_p39_4_no_horizon_exceeds_p38_base():
    """
    Invariant: INV-P39-4
    Proves that no horizon score can exceed the Phase 38 base forecast.

    The formulas only subtract from P38.score, never add:
        short_term = P38.score
        medium_term = P38.score - ALPHA * drift
        long_term = P38.score - BETA * drift - GAMMA * volatility

    Even with zero drift and volatility, scores are clamped to P38.score max.
    """
    test_cases = [
        # (p38_score, drift, volatility)
        (0.9, 0.0, 0.0),   # Zero degradation
        (0.5, 0.3, 0.4),   # Normal inputs
        (1.0, 0.0, 0.0),   # Max P38 score
        (0.3, 0.8, 0.9),   # High degradation
        (0.75, 0.5, 0.5),  # Moderate inputs
    ]

    for p38_score, drift, volatility in test_cases:
        result = run_p39_directly(
            p38_forecast_score=p38_score,
            drift_fusion_index=drift,
            entropy_volatility=volatility,
        )

        # All horizons must be <= P38 score (INV-P39-4)
        assert result.short_term_score <= p38_score, \
            f"short_term {result.short_term_score} exceeds P38 {p38_score}"
        assert result.medium_term_score <= p38_score, \
            f"medium_term {result.medium_term_score} exceeds P38 {p38_score}"
        assert result.long_term_score <= p38_score, \
            f"long_term {result.long_term_score} exceeds P38 {p38_score}"

        # Short term should equal P38 score exactly (no degradation)
        assert result.short_term_score == clamp(p38_score), \
            f"short_term should equal P38 score"


# Proves INV-P39-5: Absence-safe (missing inputs degrade confidence, never inflate)
def test_inv_p39_5_absence_safe_missing_inputs_degrade():
    """
    Invariant: INV-P39-5
    Proves that missing optional inputs degrade confidence (lower scores), never inflate.

    When drift_fusion_index or entropy_volatility are missing (None), we use
    conservative defaults (0.5) that degrade medium/long term scores.
    We never use optimistic defaults (0.0) that would inflate scores.
    """
    p38_score = 0.8

    # Case 1: With explicit inputs (lower drift/volatility = higher scores)
    result_with_inputs = run_p39_directly(
        p38_forecast_score=p38_score,
        drift_fusion_index=0.0,  # No drift
        entropy_volatility=0.0,  # No volatility
    )

    # Case 2: With missing inputs (uses conservative defaults 0.5)
    result_missing_inputs = run_p39_directly(
        p38_forecast_score=p38_score,
        drift_fusion_index=None,  # Missing
        entropy_volatility=None,  # Missing
    )

    # Short term should be the same (doesn't depend on optional inputs)
    assert result_with_inputs.short_term_score == result_missing_inputs.short_term_score

    # Medium and long term should be LOWER (more degraded) with missing inputs
    # because defaults (0.5) > explicit zero inputs (0.0)
    assert result_missing_inputs.medium_term_score <= result_with_inputs.medium_term_score, \
        "Missing drift should NOT inflate medium_term score"
    assert result_missing_inputs.long_term_score <= result_with_inputs.long_term_score, \
        "Missing volatility should NOT inflate long_term score"

    # Verify the conservative defaults are actually being applied
    # With drift=0.5 default: medium_term = 0.8 - 0.15*0.5 = 0.725
    expected_medium = p38_score - ALPHA * 0.5
    assert abs(result_missing_inputs.medium_term_score - expected_medium) < 1e-9

    # With drift=0.5, volatility=0.5 defaults:
    # long_term = 0.8 - 0.25*0.5 - 0.15*0.5 = 0.8 - 0.125 - 0.075 = 0.6
    expected_long = p38_score - BETA * 0.5 - GAMMA * 0.5
    assert abs(result_missing_inputs.long_term_score - expected_long) < 1e-9


# ============================================================================
# IMPORT SAFETY TEST (Architectural, not counted against invariant limit)
# ============================================================================


class TestImportSafety:
    """Tests for import safety - no forbidden dependencies."""

    def test_no_acoustic_imports_in_schema(self):
        """Verify p39_schema.py does not import acoustic modules."""
        import symbolu.mechanical.pipeline.p39_multi_horizon.p39_schema as module
        source = inspect.getsource(module)
        import_lines = [
            line for line in source.split("\n")
            if line.strip().startswith(("from ", "import "))
        ]
        import_text = "\n".join(import_lines).lower()
        assert "p22_acoustic" not in import_text
        assert "p10_acoustic" not in import_text
        assert "p13_acoustic" not in import_text

    def test_no_governance_imports_in_resolver(self):
        """Verify p39_resolver.py does not import governance/renderer modules."""
        import symbolu.mechanical.pipeline.p39_multi_horizon.p39_resolver as module
        source = inspect.getsource(module)
        import_lines = [
            line for line in source.split("\n")
            if line.strip().startswith(("from ", "import "))
        ]
        import_text = "\n".join(import_lines).lower()
        assert "renderer" not in import_text
        assert "dha_engine" not in import_text
        assert "persona_engine" not in import_text

    def test_no_observer_imports_in_integration(self):
        """Verify P39 does not import observer modules like P22, P23, P24."""
        import symbolu.mechanical.pipeline.p39_multi_horizon.p39_integration as module
        source = inspect.getsource(module)
        import_lines = [
            line for line in source.split("\n")
            if line.strip().startswith(("from ", "import "))
        ]
        import_text = "\n".join(import_lines).lower()
        assert "p22_acoustic_witness" not in import_text
        assert "p23_alignment" not in import_text
        assert "p24_projection" not in import_text


# ============================================================================
# SCHEMA VALIDATION TESTS (Structural, supporting the invariants)
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation - structural correctness."""

    def test_observer_only_must_be_true(self):
        """Verify observer_only cannot be set to False."""
        with pytest.raises(ValueError, match="observer_only must be True"):
            MultiHorizonForecast(
                short_term_score=0.8,
                medium_term_score=0.7,
                long_term_score=0.6,
                short_term_band="stable",
                medium_term_band="strained",
                long_term_band="strained",
                horizon_divergence=0.2,
                observer_only=False,  # Should raise
            )

    def test_scores_must_be_in_range(self):
        """Verify scores must be in [0.0, 1.0]."""
        with pytest.raises(ValueError):
            create_forecast(
                short_term_score=1.5,  # Out of range
                medium_term_score=0.7,
                long_term_score=0.6,
                short_term_band="stable",
                medium_term_band="strained",
                long_term_band="strained",
                horizon_divergence=0.2,
            )

    def test_band_must_be_valid(self):
        """Verify bands must be valid values."""
        with pytest.raises(ValueError):
            create_forecast(
                short_term_score=0.8,
                medium_term_score=0.7,
                long_term_score=0.6,
                short_term_band="invalid_band",  # Invalid
                medium_term_band="strained",
                long_term_band="strained",
                horizon_divergence=0.2,
            )

    def test_classify_band_thresholds(self):
        """Verify band classification thresholds are correct."""
        # Stable: >= 0.75
        assert classify_band(0.75) == "stable"
        assert classify_band(0.80) == "stable"
        assert classify_band(1.0) == "stable"

        # Strained: >= 0.45 and < 0.75
        assert classify_band(0.74) == "strained"
        assert classify_band(0.50) == "strained"
        assert classify_band(0.45) == "strained"

        # Volatile: < 0.45
        assert classify_band(0.44) == "volatile"
        assert classify_band(0.30) == "volatile"
        assert classify_band(0.0) == "volatile"


class TestWeights:
    """Tests for formula weight constraints."""

    def test_weights_sum_constraint(self):
        """Verify weights satisfy: ALPHA + BETA + GAMMA <= 1.0."""
        total = ALPHA + BETA + GAMMA
        assert total <= 1.0, f"Weight sum {total} exceeds 1.0"

    def test_weight_values(self):
        """Verify individual weight values."""
        assert ALPHA == 0.15
        assert BETA == 0.25
        assert GAMMA == 0.15


class TestVersionAndMetadata:
    """Tests for version and metadata."""

    def test_version_is_correct(self):
        """Verify version is 1.0.0."""
        assert P39_VERSION == "1.0.0"
        assert get_p39_version() == "1.0.0"

    def test_to_dict_serialization(self):
        """Verify to_dict produces correct serialization."""
        result = run_p39_directly(
            p38_forecast_score=0.8,
            drift_fusion_index=0.3,
            entropy_volatility=0.4,
        )
        d = result.to_dict()

        assert "short_term_score" in d
        assert "medium_term_score" in d
        assert "long_term_score" in d
        assert "short_term_band" in d
        assert "medium_term_band" in d
        assert "long_term_band" in d
        assert "horizon_divergence" in d
        assert "observer_only" in d
        assert d["observer_only"] is True
        assert "inputs" in d
        assert d["inputs"]["p38_forecast_score"] == 0.8


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
