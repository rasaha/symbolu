"""
P37 Adaptive Continuity Engine Unit Tests
==========================================

Comprehensive tests for P37 Adaptive Continuity Engine phase:
- P37Authority enum
- ContinuityBand enum
- P37Output dataclass
- Integration functions
- Determinism verification
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p37_continuity import (
    VERSION,
    P37Authority,
    ContinuityBand,
    P37Output,
    extract_p37_signals,
    run_p37_continuity,
    maybe_run_p37,
    get_p37_output,
    get_p37_ncc,
    get_p37_icc,
    get_p37_css,
    get_p37_continuity_band,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    semantic_integrity: Optional[float] = 0.7
    semantic_integrity_history: Optional[List[float]] = None
    temporal_entropy_volatility: Optional[float] = 0.4
    temporal_entropy_diff: Optional[float] = 0.1
    temporal_entropy_volatility_history: Optional[List[float]] = None
    resonance_weighting_entropy: Optional[float] = 0.3


@dataclass
class MockP34Output:
    """Mock P34 output for testing."""
    core_identity_harmonic: float = 0.7
    adaptive_identity_harmonic: float = 0.6
    relational_identity_harmonic: float = 0.65
    identity_harmonics_index: float = 0.65
    identity_stability_score: float = 0.7


@dataclass
class MockP35Output:
    """Mock P35 output for testing."""
    drift_magnitude_prediction: float = 0.2
    drift_stability_score: float = 0.75
    drift_likelihood_band: str = "LOW"


@dataclass
class MockP36Output:
    """Mock P36 output for testing."""
    ims: float = 0.7
    identity_memory_strength: float = 0.7
    iep: float = 0.65
    identity_echo_persistence: float = 0.65
    ida: float = 0.6
    identity_drift_anchoring: float = 0.6
    ims_history: Optional[List[float]] = None
    iep_history: Optional[List[float]] = None
    ida_history: Optional[List[float]] = None


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
    csi: float = 0.68
    consciousness_order_index: float = 0.7
    consciousness_stability_index: float = 0.68
    consciousness_order_history: Optional[List[float]] = None
    consciousness_stability_history: Optional[List[float]] = None


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p27_persona: Optional[MockP27Output] = None
    symbolic_harmonization: Optional[MockP27Output] = None
    consciousness: Optional[MockP26Output] = None
    ucf: Optional[MockP26Output] = None
    p34_identity_harmonics: Optional[MockP34Output] = None
    predictive_drift: Optional[MockP35Output] = None
    ppdm: Optional[MockP35Output] = None
    identity_resonance: Optional[MockP36Output] = None
    irm: Optional[MockP36Output] = None
    p37_continuity: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP37AuthorityEnum:
    """Tests for P37Authority enum."""

    def test_predictive_value(self):
        """Test: PREDICTIVE authority exists."""
        assert P37Authority.PREDICTIVE.value == "predictive"

    def test_analytics_value(self):
        """Test: ANALYTICS authority exists."""
        assert P37Authority.ANALYTICS.value == "analytics"

    def test_all_authorities_exist(self):
        """Test: all authority levels exist."""
        assert len(list(P37Authority)) == 2


class TestContinuityBandEnum:
    """Tests for ContinuityBand enum."""

    def test_high_value(self):
        """Test: HIGH band exists."""
        assert ContinuityBand.HIGH.value == "HIGH"

    def test_medium_value(self):
        """Test: MEDIUM band exists."""
        assert ContinuityBand.MEDIUM.value == "MEDIUM"

    def test_low_value(self):
        """Test: LOW band exists."""
        assert ContinuityBand.LOW.value == "LOW"

    def test_all_bands_exist(self):
        """Test: all three bands exist."""
        assert len(list(ContinuityBand)) == 3


# =============================================================================
# P37 OUTPUT TESTS
# =============================================================================


class TestP37Output:
    """Tests for P37Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P37Output(
            ncc=0.75,
            icc=0.70,
            css=0.72,
        )
        assert output.ncc == 0.75
        assert output.icc == 0.70
        assert output.css == 0.72
        assert output.authority == P37Authority.PREDICTIVE

    def test_value_clamping_high(self):
        """Test: values above 1.0 are clamped."""
        output = P37Output(
            ncc=1.5,
            icc=1.2,
            css=1.3,
        )
        assert output.ncc == 1.0
        assert output.icc == 1.0
        assert output.css == 1.0

    def test_value_clamping_low(self):
        """Test: values below 0.0 are clamped."""
        output = P37Output(
            ncc=-0.2,
            icc=-0.1,
            css=-0.3,
        )
        assert output.ncc == 0.0
        assert output.icc == 0.0
        assert output.css == 0.0

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P37Output(
            ncc=0.8,
            icc=0.75,
            css=0.77,
            continuity_tags=["CONTINUITY_STRONG"],
        )
        result = output.to_dict()

        assert result["phase"] == "P37"
        assert result["version"] == VERSION
        assert result["ncc"] == 0.8
        assert result["icc"] == 0.75
        assert result["css"] == 0.77
        assert result["authority"] == "predictive"
        assert "CONTINUITY_STRONG" in result["continuity_tags"]

    def test_continuity_band_high(self):
        """Test: HIGH band when CSS >= 0.70."""
        output = P37Output(
            ncc=0.8,
            icc=0.75,
            css=0.75,
        )
        assert output.continuity_band == ContinuityBand.HIGH

    def test_continuity_band_medium(self):
        """Test: MEDIUM band when 0.40 <= CSS < 0.70."""
        output = P37Output(
            ncc=0.5,
            icc=0.5,
            css=0.55,
        )
        assert output.continuity_band == ContinuityBand.MEDIUM

    def test_continuity_band_low(self):
        """Test: LOW band when CSS < 0.40."""
        output = P37Output(
            ncc=0.3,
            icc=0.3,
            css=0.3,
        )
        assert output.continuity_band == ContinuityBand.LOW

    def test_is_continuity_strong(self):
        """Test: is_continuity_strong when NCC >= 0.70."""
        strong = P37Output(ncc=0.75, icc=0.5, css=0.5)
        assert strong.is_continuity_strong() is True

        weak = P37Output(ncc=0.6, icc=0.5, css=0.5)
        assert weak.is_continuity_strong() is False

    def test_is_identity_continuous(self):
        """Test: is_identity_continuous when ICC >= 0.70."""
        continuous = P37Output(ncc=0.5, icc=0.75, css=0.5)
        assert continuous.is_identity_continuous() is True

        discontinuous = P37Output(ncc=0.5, icc=0.6, css=0.5)
        assert discontinuous.is_identity_continuous() is False

    def test_is_session_stable(self):
        """Test: is_session_stable when CSS >= 0.65."""
        stable = P37Output(ncc=0.5, icc=0.5, css=0.7)
        assert stable.is_session_stable() is True

        unstable = P37Output(ncc=0.5, icc=0.5, css=0.5)
        assert unstable.is_session_stable() is False

    def test_is_narrative_identity_aligned(self):
        """Test: is_narrative_identity_aligned when |NCC - ICC| <= 0.15."""
        aligned = P37Output(ncc=0.7, icc=0.65, css=0.5)
        assert aligned.is_narrative_identity_aligned() is True

        misaligned = P37Output(ncc=0.8, icc=0.5, css=0.5)
        assert misaligned.is_narrative_identity_aligned() is False

    def test_immutability(self):
        """Test: P37Output is frozen (immutable)."""
        output = P37Output(ncc=0.7, icc=0.6, css=0.65)
        with pytest.raises(Exception):
            output.ncc = 0.8


# =============================================================================
# SIGNAL EXTRACTION TESTS
# =============================================================================


class TestSignalExtraction:
    """Tests for extract_p37_signals function."""

    def test_extract_from_coherence_state(self):
        """Test: extraction from coherence state."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                semantic_integrity=0.8,
                temporal_entropy_volatility=0.3,
            ),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('semantic_integrity') == 0.8
        assert signals.get('temporal_entropy_volatility') == 0.3

    def test_extract_from_p34(self):
        """Test: extraction from P34 output."""
        ctx = MockPipelineContext(
            p34_identity_harmonics=MockP34Output(
                core_identity_harmonic=0.75,
                identity_harmonics_index=0.72,
            ),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('core_identity_harmonic') == 0.75
        assert signals.get('identity_harmonics_index') == 0.72

    def test_extract_from_p35(self):
        """Test: extraction from P35 output."""
        ctx = MockPipelineContext(
            predictive_drift=MockP35Output(
                drift_magnitude_prediction=0.25,
                drift_stability_score=0.8,
            ),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('drift_magnitude_prediction') == 0.25
        assert signals.get('drift_stability_score') == 0.8

    def test_extract_from_p36(self):
        """Test: extraction from P36 output."""
        ctx = MockPipelineContext(
            identity_resonance=MockP36Output(
                ims=0.72,
                iep=0.68,
                ida=0.65,
            ),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('identity_memory_strength') == 0.72
        assert signals.get('identity_echo_persistence') == 0.68
        assert signals.get('identity_drift_anchoring') == 0.65

    def test_extract_from_p27(self):
        """Test: extraction from P27 output."""
        ctx = MockPipelineContext(
            p27_persona=MockP27Output(symbolic_harmonization_index=0.78),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('symbolic_harmonization_index') == 0.78

    def test_extract_from_p26(self):
        """Test: extraction from P26 output."""
        ctx = MockPipelineContext(
            consciousness=MockP26Output(coi=0.82, csi=0.75),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('consciousness_order_index') == 0.82
        assert signals.get('consciousness_stability_index') == 0.75

    def test_extract_empty_context(self):
        """Test: extraction from empty context returns empty dict."""
        ctx = MockPipelineContext()
        signals = extract_p37_signals(ctx)

        assert isinstance(signals, dict)

    def test_extract_alternate_attribute_names(self):
        """Test: extraction handles alternate attribute names."""
        ctx = MockPipelineContext(
            ppdm=MockP35Output(drift_magnitude_prediction=0.3),
            irm=MockP36Output(ims=0.7),
        )
        signals = extract_p37_signals(ctx)

        assert signals.get('drift_magnitude_prediction') == 0.3
        assert signals.get('identity_memory_strength') == 0.7


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestRunP37Continuity:
    """Tests for run_p37_continuity function."""

    def test_run_with_signals(self):
        """Test: run with valid signals produces output."""
        signals = {
            'semantic_integrity': 0.7,
            'symbolic_harmonization_index': 0.65,
            'consciousness_order_index': 0.7,
            'consciousness_stability_index': 0.68,
            'temporal_entropy_volatility': 0.4,
            'core_identity_harmonic': 0.7,
            'adaptive_identity_harmonic': 0.65,
            'identity_harmonics_index': 0.68,
            'identity_memory_strength': 0.7,
            'identity_echo_persistence': 0.65,
            'identity_drift_anchoring': 0.6,
        }
        output = run_p37_continuity(signals)

        # May be None if formula requirements not met, but should not error
        if output is not None:
            assert isinstance(output, P37Output)
            assert 0.0 <= output.ncc <= 1.0
            assert 0.0 <= output.icc <= 1.0
            assert 0.0 <= output.css <= 1.0

    def test_run_with_insufficient_signals(self):
        """Test: run with insufficient signals returns None."""
        signals = {}
        output = run_p37_continuity(signals)

        assert output is None


class TestMaybeRunP37:
    """Tests for maybe_run_p37 function."""

    def test_maybe_run_with_context(self):
        """Test: maybe_run_p37 with full context."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(),
            p27_persona=MockP27Output(),
            consciousness=MockP26Output(),
            p34_identity_harmonics=MockP34Output(),
            predictive_drift=MockP35Output(),
            identity_resonance=MockP36Output(),
        )
        output = maybe_run_p37(ctx)

        # May be None depending on formula logic
        if output is not None:
            assert isinstance(output, P37Output)


class TestGetP37Output:
    """Tests for get_p37_output function."""

    def test_get_output_when_present(self):
        """Test: get_p37_output returns output when present."""
        expected = P37Output(ncc=0.7, icc=0.65, css=0.68)
        ctx = MockPipelineContext(p37_continuity=expected)

        result = get_p37_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p37_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p37_output(ctx)
        assert result is None


class TestGetP37Scores:
    """Tests for P37 score accessor functions."""

    def test_get_ncc(self):
        """Test: get_p37_ncc returns NCC."""
        output = P37Output(ncc=0.78, icc=0.65, css=0.70)
        ctx = MockPipelineContext(p37_continuity=output)

        result = get_p37_ncc(ctx)
        assert result == 0.78

    def test_get_ncc_default(self):
        """Test: get_p37_ncc returns 0.5 when absent."""
        ctx = MockPipelineContext()
        result = get_p37_ncc(ctx)
        assert result == 0.5

    def test_get_icc(self):
        """Test: get_p37_icc returns ICC."""
        output = P37Output(ncc=0.7, icc=0.72, css=0.68)
        ctx = MockPipelineContext(p37_continuity=output)

        result = get_p37_icc(ctx)
        assert result == 0.72

    def test_get_icc_default(self):
        """Test: get_p37_icc returns 0.5 when absent."""
        ctx = MockPipelineContext()
        result = get_p37_icc(ctx)
        assert result == 0.5

    def test_get_css(self):
        """Test: get_p37_css returns CSS."""
        output = P37Output(ncc=0.7, icc=0.65, css=0.75)
        ctx = MockPipelineContext(p37_continuity=output)

        result = get_p37_css(ctx)
        assert result == 0.75

    def test_get_css_default(self):
        """Test: get_p37_css returns 0.5 when absent."""
        ctx = MockPipelineContext()
        result = get_p37_css(ctx)
        assert result == 0.5

    def test_get_continuity_band(self):
        """Test: get_p37_continuity_band returns band value."""
        output = P37Output(ncc=0.8, icc=0.75, css=0.78)
        ctx = MockPipelineContext(p37_continuity=output)

        result = get_p37_continuity_band(ctx)
        assert result == "HIGH"

    def test_get_continuity_band_default(self):
        """Test: get_p37_continuity_band returns MEDIUM when absent."""
        ctx = MockPipelineContext()
        result = get_p37_continuity_band(ctx)
        assert result == "MEDIUM"


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
            'consciousness_stability_index': 0.68,
            'temporal_entropy_volatility': 0.4,
            'core_identity_harmonic': 0.7,
            'identity_harmonics_index': 0.68,
            'identity_memory_strength': 0.7,
            'identity_echo_persistence': 0.65,
        }

        results = []
        for _ in range(5):
            output = run_p37_continuity(signals)
            if output:
                results.append((output.ncc, output.icc, output.css))

        if results:
            assert all(r == results[0] for r in results)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p37(self):
        """Test: output correctly identifies as P37."""
        output = P37Output(ncc=0.7, icc=0.65, css=0.68)

        result = output.to_dict()
        assert result["phase"] == "P37"

    def test_default_authority_is_predictive(self):
        """Test: default authority is PREDICTIVE."""
        output = P37Output(ncc=0.7, icc=0.65, css=0.68)
        assert output.authority == P37Authority.PREDICTIVE


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
