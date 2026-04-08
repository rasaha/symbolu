"""
Phase 1: Governance Signal Rewiring — Signal Adapter Tests
==========================================================

Tests verifying:
1. Vritti signal adapter: real source path and fallback approximation path
2. Entropy signal adapter: full result, scalar, and unavailable paths
3. Confidence penalty computation from entropy
4. Signal source provenance metadata in resolutions
5. Fail-closed semantics: signal unavailability does not weaken governance
6. Backward compatibility: fallback produces same results as direct approx
"""

import pytest
from dataclasses import dataclass
from typing import Dict, Optional

from agentic.agentic_framework.signal_adapters.vritti_adapter import (
    resolve_vritti_signal,
    VrittiResolution,
    VrittiSignalSource,
)
from agentic.agentic_framework.signal_adapters.entropy_adapter import (
    resolve_entropy_signal,
    EntropyResolution,
    _compute_confidence_penalty,
    _ENTROPY_LOW_THRESHOLD,
    _ENTROPY_HIGH_THRESHOLD,
    _MAX_CONFIDENCE_PENALTY,
)
from agentic.agentic_framework.jepa_governance import approximate_vritti


# =========================================================================
# Fake ChittaVrittiResult for testing real vritti path
# =========================================================================

@dataclass
class FakeChittaVrittiResult:
    """Minimal duck-typed ChittaVrittiResult for testing."""
    vritti: Dict[str, float]
    coherence: float
    score: float
    dominant_vritti: str


@dataclass
class FakeEntropyResult:
    """Minimal duck-typed EntropyResult for testing."""
    combined_entropy: float
    guna_entropy: float
    kosha_entropy: float
    cross_domain_entropy: float
    gate: str  # or an enum with .value


# =========================================================================
# VRITTI ADAPTER TESTS
# =========================================================================


class TestVrittiAdapterRealPath:
    """Test vritti adapter with real ChittaVrittiResult."""

    def test_real_vritti_returns_real_source(self):
        result = FakeChittaVrittiResult(
            vritti={"pramana": 0.6, "viparyaya": 0.1, "vikalpa": 0.1,
                    "smrti": 0.1, "nidra": 0.1},
            coherence=0.85,
            score=0.9,
            dominant_vritti="pramana",
        )
        resolution = resolve_vritti_signal(vritti_result=result)
        assert resolution.source == VrittiSignalSource.REAL
        assert resolution.degraded is False
        assert resolution.distribution["pramana"] == 0.6
        assert resolution.coherence == 0.85
        assert resolution.score == 0.9
        assert "chitta_vritti engine" in resolution.source_detail

    def test_real_vritti_preserves_smrti(self):
        """Real path should preserve non-zero smrti (which approx hardcodes to 0)."""
        result = FakeChittaVrittiResult(
            vritti={"pramana": 0.3, "viparyaya": 0.1, "vikalpa": 0.1,
                    "smrti": 0.4, "nidra": 0.1},
            coherence=0.7,
            score=0.8,
            dominant_vritti="smrti",
        )
        resolution = resolve_vritti_signal(vritti_result=result)
        assert resolution.source == VrittiSignalSource.REAL
        assert resolution.distribution["smrti"] == 0.4

    def test_malformed_vritti_result_degrades_to_approximation(self):
        """Malformed result should fall back to approximation, not crash."""
        bad_result = object()  # No vritti/coherence/score attributes
        resolution = resolve_vritti_signal(
            vritti_result=bad_result,
            quality=0.7,
            coherence=0.8,
            overall_confidence=0.6,
        )
        assert resolution.source == VrittiSignalSource.APPROXIMATED
        assert resolution.degraded is True


class TestVrittiAdapterFallbackPath:
    """Test vritti adapter fallback to approximation."""

    def test_no_vritti_result_uses_approximation(self):
        resolution = resolve_vritti_signal(
            quality=0.7,
            coherence=0.8,
            overall_confidence=0.6,
        )
        assert resolution.source == VrittiSignalSource.APPROXIMATED
        assert resolution.degraded is True
        assert "approximate_vritti" in resolution.source_detail

    def test_fallback_matches_direct_approximate_vritti(self):
        """Fallback should produce identical distribution to direct call."""
        q, c, conf = 0.7, 0.8, 0.6
        resolution = resolve_vritti_signal(
            quality=q, coherence=c, overall_confidence=conf,
        )
        direct = approximate_vritti(
            quality=q, coherence=c, overall_confidence=conf,
        )
        for key in ("pramana", "viparyaya", "vikalpa", "smrti", "nidra"):
            assert abs(resolution.distribution[key] - direct[key]) < 1e-9

    def test_fallback_still_has_five_vritti_keys(self):
        resolution = resolve_vritti_signal()
        expected = {"pramana", "viparyaya", "vikalpa", "smrti", "nidra"}
        assert set(resolution.distribution.keys()) == expected

    def test_default_signals_produce_valid_distribution(self):
        """Default (0.5, 0.5, 0.5) should produce a valid distribution."""
        resolution = resolve_vritti_signal()
        total = sum(resolution.distribution.values())
        assert abs(total - 1.0) < 1e-6

    def test_zero_signals_produce_dormancy(self):
        """All-zero signals should produce valid output (nidra-dominant)."""
        resolution = resolve_vritti_signal(
            quality=0.0, coherence=0.0, overall_confidence=0.0,
        )
        assert resolution.distribution["nidra"] > 0
        total = sum(resolution.distribution.values())
        assert abs(total - 1.0) < 1e-6


class TestVrittiAdapterPreference:
    """Test that real vritti is preferred over approximation."""

    def test_real_takes_precedence_even_with_fallback_args(self):
        """When both vritti_result and scalar args provided, real wins."""
        result = FakeChittaVrittiResult(
            vritti={"pramana": 0.9, "viparyaya": 0.0, "vikalpa": 0.0,
                    "smrti": 0.05, "nidra": 0.05},
            coherence=0.95,
            score=0.99,
            dominant_vritti="pramana",
        )
        resolution = resolve_vritti_signal(
            vritti_result=result,
            quality=0.1,  # Would produce very different approximation
            coherence=0.1,
            overall_confidence=0.1,
        )
        assert resolution.source == VrittiSignalSource.REAL
        assert resolution.distribution["pramana"] == 0.9


# =========================================================================
# ENTROPY ADAPTER TESTS
# =========================================================================


class TestEntropyAdapterFullResult:
    """Test entropy adapter with full EntropyResult object."""

    def test_full_entropy_result(self):
        result = FakeEntropyResult(
            combined_entropy=0.5,
            guna_entropy=0.3,
            kosha_entropy=0.4,
            cross_domain_entropy=0.6,
            gate="ALLOW_WITH_MODULATION",
        )
        resolution = resolve_entropy_signal(entropy_result=result)
        assert resolution.available is True
        assert resolution.combined_entropy == 0.5
        assert resolution.guna_entropy == 0.3
        assert resolution.kosha_entropy == 0.4
        assert resolution.cross_domain_entropy == 0.6
        assert resolution.gate == "ALLOW_WITH_MODULATION"
        assert resolution.confidence_penalty > 0  # 0.5 > low threshold
        assert "entropy engine" in resolution.source_detail

    def test_entropy_with_enum_gate(self):
        """Entropy gate as an enum with .value attribute."""
        from enum import Enum

        class FakeGate(Enum):
            ALLOW = "ALLOW"

        @dataclass
        class FakeResult:
            combined_entropy: float = 0.1
            guna_entropy: float = 0.1
            kosha_entropy: float = 0.1
            cross_domain_entropy: float = 0.1
            gate: FakeGate = FakeGate.ALLOW

        resolution = resolve_entropy_signal(entropy_result=FakeResult())
        assert resolution.gate == "ALLOW"


class TestEntropyAdapterScalarPath:
    """Test entropy adapter with direct scalar value."""

    def test_scalar_entropy(self):
        resolution = resolve_entropy_signal(combined_entropy=0.4)
        assert resolution.available is True
        assert resolution.combined_entropy == 0.4
        assert resolution.guna_entropy is None
        assert "direct scalar" in resolution.source_detail

    def test_scalar_clamped_to_range(self):
        """Values outside [0,1] should be clamped."""
        resolution = resolve_entropy_signal(combined_entropy=1.5)
        assert resolution.combined_entropy == 1.0
        resolution = resolve_entropy_signal(combined_entropy=-0.3)
        assert resolution.combined_entropy == 0.0


class TestEntropyAdapterUnavailable:
    """Test entropy adapter when no data available."""

    def test_no_entropy_data(self):
        resolution = resolve_entropy_signal()
        assert resolution.available is False
        assert resolution.combined_entropy is None
        assert resolution.confidence_penalty == 0.0
        assert "no entropy data" in resolution.source_detail

    def test_malformed_entropy_result_treated_as_unavailable(self):
        resolution = resolve_entropy_signal(entropy_result=object())
        assert resolution.available is False
        assert resolution.confidence_penalty == 0.0


class TestEntropyAdapterFailClosed:
    """Verify entropy absence does not weaken governance."""

    def test_unavailable_entropy_has_zero_penalty(self):
        """When entropy is unavailable, penalty is 0 (no weakening)."""
        resolution = resolve_entropy_signal()
        assert resolution.confidence_penalty == 0.0

    def test_low_entropy_has_zero_penalty(self):
        """Low entropy (system coherent) should not penalize."""
        resolution = resolve_entropy_signal(combined_entropy=0.1)
        assert resolution.confidence_penalty == 0.0


# =========================================================================
# CONFIDENCE PENALTY COMPUTATION
# =========================================================================


class TestConfidencePenalty:
    """Test bounded confidence penalty from entropy."""

    def test_below_low_threshold_no_penalty(self):
        assert _compute_confidence_penalty(0.0) == 0.0
        assert _compute_confidence_penalty(_ENTROPY_LOW_THRESHOLD) == 0.0

    def test_above_high_threshold_max_penalty(self):
        assert _compute_confidence_penalty(_ENTROPY_HIGH_THRESHOLD) == _MAX_CONFIDENCE_PENALTY
        assert _compute_confidence_penalty(1.0) == _MAX_CONFIDENCE_PENALTY

    def test_midpoint_proportional_penalty(self):
        mid = (_ENTROPY_LOW_THRESHOLD + _ENTROPY_HIGH_THRESHOLD) / 2
        penalty = _compute_confidence_penalty(mid)
        assert 0 < penalty < _MAX_CONFIDENCE_PENALTY
        assert abs(penalty - _MAX_CONFIDENCE_PENALTY / 2) < 1e-9

    def test_penalty_never_exceeds_max(self):
        """Penalty should never exceed the configured maximum."""
        for entropy in [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]:
            penalty = _compute_confidence_penalty(entropy)
            assert 0 <= penalty <= _MAX_CONFIDENCE_PENALTY

    def test_penalty_monotonically_increases(self):
        """Higher entropy should never produce lower penalty."""
        prev = 0.0
        for e in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            p = _compute_confidence_penalty(e)
            assert p >= prev
            prev = p


# =========================================================================
# INTEGRATION: Governance behavior stability
# =========================================================================


class TestGovernanceStability:
    """Verify governance behavior remains stable when real signal absent."""

    def test_approximation_still_produces_valid_5vritti(self):
        """Without real signals, vritti adapter still returns valid 5D dist."""
        resolution = resolve_vritti_signal(
            quality=0.8, coherence=0.9, overall_confidence=0.7,
        )
        assert len(resolution.distribution) == 5
        total = sum(resolution.distribution.values())
        assert abs(total - 1.0) < 1e-6
        assert resolution.distribution["smrti"] == 0.0  # As before

    def test_no_entropy_no_confidence_impact(self):
        """Without entropy data, governance confidence is not reduced."""
        resolution = resolve_entropy_signal()
        assert resolution.confidence_penalty == 0.0

    def test_signal_adapters_importable(self):
        """Signal adapters module should be importable."""
        from agentic.agentic_framework import signal_adapters
        assert hasattr(signal_adapters, "resolve_vritti_signal")
        assert hasattr(signal_adapters, "resolve_entropy_signal")
        assert hasattr(signal_adapters, "VrittiResolution")
        assert hasattr(signal_adapters, "EntropyResolution")
