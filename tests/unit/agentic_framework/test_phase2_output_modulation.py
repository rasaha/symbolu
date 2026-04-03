"""
Phase 2: Output Modulation Path Wiring — Tests
================================================

Tests verifying:
1. Output modulation adapter: DHA extraction, guna modulation, entropy gate
2. DHA result dict extraction (from maybe_run_dha output)
3. DHA result object extraction (from DHAResult dataclass)
4. Guna modulation E = G × P × T computation via adapter
5. Entropy gate passthrough
6. Fail-closed semantics: missing signals do not weaken output
7. Combined resolution with all three signal sources
8. Signal surfacing: adapter output can populate unified output fields
"""

import pytest
from dataclasses import dataclass
from typing import Dict, Optional

from agentic.agentic_framework.signal_adapters.output_modulation_adapter import (
    resolve_output_modulation,
    OutputModulationResolution,
    _extract_dha,
    _compute_guna_modulation,
    _dominant_from_weights,
)


# =========================================================================
# Fake DHA result types for testing
# =========================================================================

@dataclass
class FakeToneWeights:
    sweet: float = 0.5
    jolt: float = 0.3
    metaphor: float = 0.2

    def to_dict(self):
        return {"sweet": self.sweet, "jolt": self.jolt, "metaphor": self.metaphor}


@dataclass
class FakeDHAResult:
    tone_weights: FakeToneWeights = None
    I: float = 0.7
    R: float = 0.9
    D: float = 0.63
    suppressed: bool = False
    dominant_tone: str = "sweet"

    def __post_init__(self):
        if self.tone_weights is None:
            self.tone_weights = FakeToneWeights()


# =========================================================================
# DHA EXTRACTION TESTS
# =========================================================================


class TestDHAExtractionFromDict:
    """Test DHA extraction from dict (as returned by maybe_run_dha)."""

    def test_dict_with_tone_weights(self):
        dha_dict = {
            "tone_weights": {"sweet": 0.6, "jolt": 0.25, "metaphor": 0.15},
            "I": 0.8,
            "R": 0.95,
            "D": 0.76,
            "suppressed": False,
        }
        result = _extract_dha(dha_dict)
        assert result["dha_available"] is True
        assert result["dha_tone_weights"]["sweet"] == 0.6
        assert result["dha_intensity"] == 0.8
        assert result["dha_restraint"] == 0.95
        assert result["dha_delivery_factor"] == 0.76
        assert result["dha_dominant_tone"] == "sweet"
        assert result["dha_suppressed"] is False

    def test_dict_without_tone_weights(self):
        dha_dict = {"I": 0.5, "R": 0.5}
        result = _extract_dha(dha_dict)
        assert result["dha_available"] is False

    def test_empty_dict(self):
        result = _extract_dha({})
        assert result["dha_available"] is False

    def test_none_input(self):
        result = _extract_dha(None)
        assert result["dha_available"] is False


class TestDHAExtractionFromObject:
    """Test DHA extraction from DHAResult-like object."""

    def test_object_with_tone_weights(self):
        dha_obj = FakeDHAResult(
            tone_weights=FakeToneWeights(sweet=0.7, jolt=0.2, metaphor=0.1),
            I=0.85,
            R=0.9,
            D=0.765,
            suppressed=False,
        )
        result = _extract_dha(dha_obj)
        assert result["dha_available"] is True
        assert result["dha_tone_weights"]["sweet"] == 0.7
        assert result["dha_intensity"] == 0.85
        assert result["dha_dominant_tone"] == "sweet"

    def test_malformed_object(self):
        result = _extract_dha(object())
        assert result["dha_available"] is False


# =========================================================================
# GUNA MODULATION TESTS
# =========================================================================


class TestGunaModulation:
    """Test guna modulation E = G × P × T computation."""

    def test_default_computation(self):
        result = _compute_guna_modulation(
            C_s=0.7, M=0.3, H=0.2, tier="consumer", base_intensity=1.0,
        )
        assert result["guna_modulation_available"] is True
        assert result["guna_E"] is not None
        assert result["guna_G"] is not None
        assert result["guna_P"] is not None
        assert result["guna_T_scalar"] is not None
        assert result["guna_output_intensity"] is not None
        assert result["guna_vector"] is not None
        # E = G * P * T, and output_intensity = base * E
        E = result["guna_E"]
        assert abs(result["guna_output_intensity"] - 1.0 * E) < 1e-9

    def test_guna_vector_sums_to_one(self):
        result = _compute_guna_modulation(
            C_s=0.5, M=0.5, H=0.5, tier="consumer", base_intensity=1.0,
        )
        gv = result["guna_vector"]
        total = gv["sattva"] + gv["rajas"] + gv["tamas"]
        assert abs(total - 1.0) < 1e-6

    def test_different_tiers(self):
        """Different tiers should produce different T scalars."""
        r1 = _compute_guna_modulation(
            C_s=0.5, M=0.3, H=0.2, tier="enterprise_tier_1", base_intensity=1.0,
        )
        r2 = _compute_guna_modulation(
            C_s=0.5, M=0.3, H=0.2, tier="consumer", base_intensity=1.0,
        )
        # Both should succeed
        assert r1["guna_modulation_available"] is True
        assert r2["guna_modulation_available"] is True
        # Tier scalars differ (enterprise_tier_1 = 1.0, consumer = 0.85)
        assert r1["guna_T_scalar"] != r2["guna_T_scalar"]

    def test_base_intensity_scales_output(self):
        r1 = _compute_guna_modulation(
            C_s=0.7, M=0.3, H=0.2, tier="consumer", base_intensity=1.0,
        )
        r2 = _compute_guna_modulation(
            C_s=0.7, M=0.3, H=0.2, tier="consumer", base_intensity=0.5,
        )
        # Same E factor, different output intensity
        assert abs(r1["guna_E"] - r2["guna_E"]) < 1e-9
        assert abs(r2["guna_output_intensity"] - r1["guna_output_intensity"] * 0.5) < 1e-9

    def test_clamped_inputs(self):
        """Values outside [0,1] should be clamped."""
        result = _compute_guna_modulation(
            C_s=1.5, M=-0.3, H=2.0, tier="consumer", base_intensity=1.0,
        )
        assert result["guna_modulation_available"] is True


# =========================================================================
# FULL RESOLUTION TESTS
# =========================================================================


class TestResolveOutputModulation:
    """Test full resolve_output_modulation() function."""

    def test_all_signals_available(self):
        dha_dict = {
            "tone_weights": {"sweet": 0.5, "jolt": 0.3, "metaphor": 0.2},
            "I": 0.75,
            "R": 0.9,
            "D": 0.675,
            "suppressed": False,
        }
        resolution = resolve_output_modulation(
            dha_result=dha_dict,
            C_s=0.7,
            M=0.3,
            H=0.2,
            tier="consumer",
            base_intensity=1.0,
            entropy_gate="ALLOW_WITH_MODULATION",
            entropy_combined=0.45,
        )
        assert resolution.dha_available is True
        assert resolution.guna_modulation_available is True
        assert resolution.entropy_gate == "ALLOW_WITH_MODULATION"
        assert resolution.entropy_combined == 0.45
        assert "dha_formula" in resolution.source_detail
        assert "guna_modulation" in resolution.source_detail
        assert "entropy_gate" in resolution.source_detail

    def test_no_signals_available(self):
        resolution = resolve_output_modulation()
        assert resolution.dha_available is False
        assert resolution.guna_modulation_available is True  # guna always computes with defaults
        assert resolution.entropy_gate is None
        assert "guna_modulation" in resolution.source_detail

    def test_dha_only(self):
        dha_dict = {
            "tone_weights": {"sweet": 0.4, "jolt": 0.4, "metaphor": 0.2},
            "I": 0.6,
            "R": 0.8,
            "D": 0.48,
        }
        resolution = resolve_output_modulation(dha_result=dha_dict)
        assert resolution.dha_available is True
        assert resolution.dha_tone_weights["sweet"] == 0.4
        assert resolution.dha_delivery_factor == 0.48

    def test_entropy_gate_enum_conversion(self):
        """Entropy gate with .value attribute should be converted to string."""
        from enum import Enum

        class FakeGate(Enum):
            BLOCK = "BLOCK"

        resolution = resolve_output_modulation(entropy_gate=FakeGate.BLOCK)
        assert resolution.entropy_gate == "BLOCK"

    def test_entropy_gate_string_passthrough(self):
        resolution = resolve_output_modulation(entropy_gate="ALLOW")
        assert resolution.entropy_gate == "ALLOW"


class TestFailClosed:
    """Verify fail-closed semantics for output modulation."""

    def test_missing_dha_does_not_affect_guna(self):
        """Missing DHA should not prevent guna modulation."""
        resolution = resolve_output_modulation(C_s=0.8, M=0.2, H=0.1)
        assert resolution.dha_available is False
        assert resolution.guna_modulation_available is True
        assert resolution.guna_E is not None

    def test_malformed_dha_does_not_crash(self):
        resolution = resolve_output_modulation(dha_result=object())
        assert resolution.dha_available is False
        assert resolution.guna_modulation_available is True

    def test_no_entropy_gate_is_none(self):
        """When no entropy gate provided, it should be None (not weakened)."""
        resolution = resolve_output_modulation()
        assert resolution.entropy_gate is None

    def test_to_dict_round_trip(self):
        """Resolution should be fully serializable."""
        resolution = resolve_output_modulation(
            dha_result={
                "tone_weights": {"sweet": 0.5, "jolt": 0.3, "metaphor": 0.2},
                "I": 0.7, "R": 0.9, "D": 0.63,
            },
            C_s=0.7, M=0.3, H=0.2,
            entropy_gate="ALLOW",
            entropy_combined=0.3,
        )
        d = resolution.to_dict()
        assert isinstance(d, dict)
        assert d["dha_available"] is True
        assert d["guna_modulation_available"] is True
        assert d["entropy_gate"] == "ALLOW"
        assert d["entropy_combined"] == 0.3
        assert d["source_detail"] is not None


# =========================================================================
# INTEGRATION: Signal surfacing in output
# =========================================================================


class TestSignalSurfacing:
    """Verify adapter output can populate unified output fields."""

    def test_resolution_fields_map_to_output_keys(self):
        """All fields needed for unified output are present in resolution."""
        resolution = resolve_output_modulation(
            dha_result={
                "tone_weights": {"sweet": 0.5, "jolt": 0.3, "metaphor": 0.2},
                "I": 0.7, "R": 0.9, "D": 0.63,
            },
            C_s=0.7, M=0.3, H=0.2,
            entropy_gate="ALLOW_WITH_MODULATION",
            entropy_combined=0.45,
        )
        d = resolution.to_dict()

        # These keys are what unified_api extracts
        assert "dha_tone_weights" in d
        assert "dha_intensity" in d
        assert "dha_delivery_factor" in d
        assert "dha_dominant_tone" in d
        assert "guna_E" in d
        assert "guna_vector" in d
        assert "guna_output_intensity" in d
        assert "entropy_gate" in d
        assert "entropy_combined" in d

    def test_adapter_importable_from_signal_adapters(self):
        """Output modulation adapter should be importable from signal_adapters."""
        from agentic.agentic_framework import signal_adapters
        assert hasattr(signal_adapters, "resolve_output_modulation")
        assert hasattr(signal_adapters, "OutputModulationResolution")


class TestDominantFromWeights:
    """Test _dominant_from_weights helper."""

    def test_sweet_dominant(self):
        assert _dominant_from_weights({"sweet": 0.6, "jolt": 0.2, "metaphor": 0.2}) == "sweet"

    def test_jolt_dominant(self):
        assert _dominant_from_weights({"sweet": 0.2, "jolt": 0.5, "metaphor": 0.3}) == "jolt"

    def test_metaphor_dominant(self):
        assert _dominant_from_weights({"sweet": 0.1, "jolt": 0.2, "metaphor": 0.7}) == "metaphor"

    def test_empty_dict(self):
        assert _dominant_from_weights({}) is None

    def test_none_input(self):
        assert _dominant_from_weights(None) is None
