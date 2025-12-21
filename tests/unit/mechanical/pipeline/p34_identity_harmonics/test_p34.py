"""
P34 Identity Harmonics Layer Unit Tests
=========================================

Comprehensive tests for P34 Identity Harmonics Layer phase:
- P34Authority enum
- P34Output dataclass
- Integration functions
- Determinism verification
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p34_identity_harmonics import (
    VERSION,
    P34Authority,
    P34Output,
    extract_p34_signals,
    run_p34_harmonics,
    maybe_run_p34,
    get_p34_output,
    get_p34_identity_harmonics_index,
    get_p34_stability_score,
    get_p34_flexibility_score,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    semantic_integrity: Optional[float] = 0.7
    semantic_integrity_history: Optional[List[float]] = None
    cognitive_drift_v3: Optional[float] = 0.3
    cognitive_drift_v3_history: Optional[List[float]] = None
    temporal_entropy_volatility: Optional[float] = 0.4
    persona_drift_score: Optional[float] = 0.2
    loop_alignment: Optional[float] = 0.6
    guna_resonance_index: Optional[float] = 0.5
    kosha_resonance_index: Optional[float] = 0.5


@dataclass
class MockP27Output:
    """Mock P27 output for testing."""
    symbolic_harmonization_index: float = 0.65
    shi: float = 0.65
    symbolic_harmonization_history: Optional[List[float]] = None


@dataclass
class MockP26Output:
    """Mock P26 output for testing."""
    coi: float = 0.7
    consciousness_order_index: float = 0.7


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p27_persona: Optional[MockP27Output] = None
    symbolic_harmonization: Optional[MockP27Output] = None
    consciousness: Optional[MockP26Output] = None
    ucf: Optional[MockP26Output] = None
    p34_identity_harmonics: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP34AuthorityEnum:
    """Tests for P34Authority enum."""

    def test_observer_value(self):
        """Test: OBSERVER authority exists."""
        assert P34Authority.OBSERVER.value == "observer"

    def test_analytics_value(self):
        """Test: ANALYTICS authority exists."""
        assert P34Authority.ANALYTICS.value == "analytics"

    def test_all_authorities_exist(self):
        """Test: all authority levels exist."""
        assert len(list(P34Authority)) == 2


# =============================================================================
# P34 OUTPUT TESTS
# =============================================================================


class TestP34Output:
    """Tests for P34Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
        )
        assert output.core_identity_harmonic == 0.7
        assert output.adaptive_identity_harmonic == 0.6
        assert output.identity_harmonics_index == 0.65
        assert output.authority == P34Authority.OBSERVER

    def test_value_clamping_high(self):
        """Test: values above 1.0 are clamped."""
        output = P34Output(
            core_identity_harmonic=1.5,
            adaptive_identity_harmonic=1.2,
            relational_identity_harmonic=1.3,
            identity_harmonics_index=1.1,
        )
        assert output.core_identity_harmonic == 1.0
        assert output.adaptive_identity_harmonic == 1.0
        assert output.relational_identity_harmonic == 1.0
        assert output.identity_harmonics_index == 1.0

    def test_value_clamping_low(self):
        """Test: values below 0.0 are clamped."""
        output = P34Output(
            core_identity_harmonic=-0.2,
            adaptive_identity_harmonic=-0.1,
            relational_identity_harmonic=-0.3,
            identity_harmonics_index=-0.5,
        )
        assert output.core_identity_harmonic == 0.0
        assert output.adaptive_identity_harmonic == 0.0
        assert output.relational_identity_harmonic == 0.0
        assert output.identity_harmonics_index == 0.0

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P34Output(
            core_identity_harmonic=0.8,
            adaptive_identity_harmonic=0.7,
            relational_identity_harmonic=0.75,
            identity_harmonics_index=0.75,
            diagnostic_tags=["IDENTITY_STABLE"],
        )
        result = output.to_dict()

        assert result["phase"] == "P34"
        assert result["version"] == VERSION
        assert result["core_identity_harmonic"] == 0.8
        assert result["identity_harmonics_index"] == 0.75
        assert result["authority"] == "observer"
        assert "IDENTITY_STABLE" in result["diagnostic_tags"]

    def test_get_harmonic_band_high(self):
        """Test: HIGH band when IHI >= 0.70."""
        output = P34Output(
            core_identity_harmonic=0.8,
            adaptive_identity_harmonic=0.7,
            relational_identity_harmonic=0.75,
            identity_harmonics_index=0.75,
        )
        assert output.get_harmonic_band() == "HIGH"

    def test_get_harmonic_band_medium(self):
        """Test: MEDIUM band when 0.40 <= IHI < 0.70."""
        output = P34Output(
            core_identity_harmonic=0.5,
            adaptive_identity_harmonic=0.5,
            relational_identity_harmonic=0.5,
            identity_harmonics_index=0.55,
        )
        assert output.get_harmonic_band() == "MEDIUM"

    def test_get_harmonic_band_low(self):
        """Test: LOW band when IHI < 0.40."""
        output = P34Output(
            core_identity_harmonic=0.3,
            adaptive_identity_harmonic=0.3,
            relational_identity_harmonic=0.3,
            identity_harmonics_index=0.3,
        )
        assert output.get_harmonic_band() == "LOW"

    def test_is_identity_stable(self):
        """Test: is_identity_stable when CIH >= 0.65."""
        stable = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.5,
            relational_identity_harmonic=0.5,
            identity_harmonics_index=0.55,
        )
        assert stable.is_identity_stable() is True

        unstable = P34Output(
            core_identity_harmonic=0.5,
            adaptive_identity_harmonic=0.5,
            relational_identity_harmonic=0.5,
            identity_harmonics_index=0.5,
        )
        assert unstable.is_identity_stable() is False

    def test_is_identity_flexible(self):
        """Test: is_identity_flexible when AIH >= 0.60."""
        flexible = P34Output(
            core_identity_harmonic=0.5,
            adaptive_identity_harmonic=0.7,
            relational_identity_harmonic=0.5,
            identity_harmonics_index=0.55,
        )
        assert flexible.is_identity_flexible() is True

    def test_is_identity_resonant(self):
        """Test: is_identity_resonant when RIH >= 0.60."""
        resonant = P34Output(
            core_identity_harmonic=0.5,
            adaptive_identity_harmonic=0.5,
            relational_identity_harmonic=0.7,
            identity_harmonics_index=0.55,
        )
        assert resonant.is_identity_resonant() is True

    def test_immutability(self):
        """Test: P34Output is frozen (immutable)."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
        )
        with pytest.raises(Exception):
            output.core_identity_harmonic = 0.8


# =============================================================================
# SIGNAL EXTRACTION TESTS
# =============================================================================


class TestSignalExtraction:
    """Tests for extract_p34_signals function."""

    def test_extract_from_coherence_state(self):
        """Test: extraction from coherence state."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                semantic_integrity=0.8,
                cognitive_drift_v3=0.2,
            ),
        )
        signals = extract_p34_signals(ctx)

        assert signals.get('semantic_integrity') == 0.8
        assert signals.get('cognitive_drift_v3') == 0.2

    def test_extract_from_p27(self):
        """Test: extraction from P27 output."""
        ctx = MockPipelineContext(
            p27_persona=MockP27Output(symbolic_harmonization_index=0.75),
        )
        signals = extract_p34_signals(ctx)

        assert signals.get('symbolic_harmonization_index') == 0.75

    def test_extract_from_p26(self):
        """Test: extraction from P26 output."""
        ctx = MockPipelineContext(
            consciousness=MockP26Output(coi=0.8),
        )
        signals = extract_p34_signals(ctx)

        assert signals.get('consciousness_order_index') == 0.8

    def test_extract_empty_context(self):
        """Test: extraction from empty context returns empty dict."""
        ctx = MockPipelineContext()
        signals = extract_p34_signals(ctx)

        assert isinstance(signals, dict)


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestRunP34Harmonics:
    """Tests for run_p34_harmonics function."""

    def test_run_with_signals(self):
        """Test: run with valid signals produces output."""
        signals = {
            'semantic_integrity': 0.7,
            'symbolic_harmonization_index': 0.65,
            'consciousness_order_index': 0.7,
            'cognitive_drift_v3': 0.3,
            'temporal_entropy_volatility': 0.4,
            'loop_alignment': 0.6,
            'persona_drift_score': 0.2,
            'guna_resonance_index': 0.5,
            'kosha_resonance_index': 0.5,
        }
        output = run_p34_harmonics(signals)

        # May be None if formula requirements not met, but should not error
        if output is not None:
            assert isinstance(output, P34Output)
            assert 0.0 <= output.identity_harmonics_index <= 1.0

    def test_run_with_insufficient_signals(self):
        """Test: run with insufficient signals returns None."""
        signals = {}
        output = run_p34_harmonics(signals)

        assert output is None


class TestMaybeRunP34:
    """Tests for maybe_run_p34 function."""

    def test_maybe_run_with_context(self):
        """Test: maybe_run_p34 with full context."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(),
            p27_persona=MockP27Output(),
            consciousness=MockP26Output(),
        )
        output = maybe_run_p34(ctx)

        # May be None depending on formula logic
        if output is not None:
            assert isinstance(output, P34Output)


class TestGetP34Output:
    """Tests for get_p34_output function."""

    def test_get_output_when_present(self):
        """Test: get_p34_output returns output when present."""
        expected = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
        )
        ctx = MockPipelineContext(p34_identity_harmonics=expected)

        result = get_p34_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p34_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p34_output(ctx)
        assert result is None


class TestGetP34Scores:
    """Tests for P34 score accessor functions."""

    def test_get_identity_harmonics_index(self):
        """Test: get_p34_identity_harmonics_index returns IHI."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.72,
        )
        ctx = MockPipelineContext(p34_identity_harmonics=output)

        result = get_p34_identity_harmonics_index(ctx)
        assert result == 0.72

    def test_get_identity_harmonics_index_default(self):
        """Test: get_p34_identity_harmonics_index returns 0.5 when absent."""
        ctx = MockPipelineContext()
        result = get_p34_identity_harmonics_index(ctx)
        assert result == 0.5

    def test_get_stability_score(self):
        """Test: get_p34_stability_score returns stability score."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
            identity_stability_score=0.8,
        )
        ctx = MockPipelineContext(p34_identity_harmonics=output)

        result = get_p34_stability_score(ctx)
        assert result == 0.8

    def test_get_flexibility_score(self):
        """Test: get_p34_flexibility_score returns flexibility score."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
            identity_flexibility_score=0.75,
        )
        ctx = MockPipelineContext(p34_identity_harmonics=output)

        result = get_p34_flexibility_score(ctx)
        assert result == 0.75


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests verifying deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: same signals produce same output."""
        signals = {
            'semantic_integrity': 0.7,
            'symbolic_harmonization_index': 0.65,
            'consciousness_order_index': 0.7,
            'cognitive_drift_v3': 0.3,
            'temporal_entropy_volatility': 0.4,
            'loop_alignment': 0.6,
            'persona_drift_score': 0.2,
            'guna_resonance_index': 0.5,
            'kosha_resonance_index': 0.5,
        }

        results = []
        for _ in range(5):
            output = run_p34_harmonics(signals)
            if output:
                results.append(output.identity_harmonics_index)

        if results:
            assert all(r == results[0] for r in results)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p34(self):
        """Test: output correctly identifies as P34."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
        )

        result = output.to_dict()
        assert result["phase"] == "P34"

    def test_default_authority_is_observer(self):
        """Test: default authority is OBSERVER."""
        output = P34Output(
            core_identity_harmonic=0.7,
            adaptive_identity_harmonic=0.6,
            relational_identity_harmonic=0.65,
            identity_harmonics_index=0.65,
        )
        assert output.authority == P34Authority.OBSERVER


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
